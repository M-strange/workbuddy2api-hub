"""账号池「暂时没号」时的排队预算（account_queue_seconds）+ 排队助手。
高并发下每账号名额会被占满、或整池刚被上游限流停放，默认立刻回 503 会让客户端
看到「所有请求同时失败」；开了这个预算后这批请求原地等一个名额。

Run with: python _test_account_queue.py
No upstream credentials or outbound network are used.
"""
import json
import os
import sys
import tempfile
import time
import unittest

_startup_dir = tempfile.TemporaryDirectory(prefix="account-queue-")
os.environ["ACCOUNTS_DIR"] = _startup_dir.name
os.environ["WB_PROXY_USAGE_DIR"] = _startup_dir.name
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_proxy
import wb_settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="account-queue-settings-")

    def _write(self, payload):
        with open(os.path.join(self._dir, "settings.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_default_is_off(self):
        self.assertEqual(wb_settings.account_queue_seconds(self._dir), 0)

    def test_roundtrip_does_not_disturb_the_seat_cap(self):
        self.assertEqual(wb_settings.set_account_queue_seconds(self._dir, 25), 25)
        self.assertEqual(wb_settings.account_queue_seconds(self._dir), 25)
        wb_settings.set_account_max_concurrent(self._dir, 3)
        self.assertEqual(wb_settings.account_queue_seconds(self._dir), 25)
        self.assertEqual(wb_settings.account_max_concurrent(self._dir), 3)

    def test_out_of_range_values_are_rejected(self):
        for bad in (-1, 121):
            with self.assertRaises(ValueError):
                wb_settings.set_account_queue_seconds(self._dir, bad)
        for bad in ("30", 1.5, True):
            with self.assertRaises(ValueError):
                wb_settings.set_account_queue_seconds(self._dir, bad)

    def test_unreadable_values_degrade_to_off(self):
        for bad in (True, 999, -5, "30", 2.5):
            self._write({"account_queue_seconds": bad})
            self.assertEqual(wb_settings.account_queue_seconds(self._dir), 0)


class WaitForPoolAccountTests(unittest.TestCase):
    def test_zero_budget_takes_exactly_one_look(self):
        calls = []

        def pick():
            calls.append(1)
            return None

        got, account = wb_proxy.wait_for_pool_account(pick, 0)
        self.assertFalse(got)
        self.assertIsNone(account)
        self.assertEqual(len(calls), 1)

    def test_a_ready_account_is_returned_immediately(self):
        sentinel = object()

        def pick():
            return sentinel

        got, account = wb_proxy.wait_for_pool_account(pick, 5)
        self.assertTrue(got)
        self.assertIs(account, sentinel)

    def test_waits_until_a_seat_frees(self):
        state = {"n": 0}
        sentinel = object()

        def pick():
            state["n"] += 1
            return sentinel if state["n"] >= 3 else None

        started = time.monotonic()
        got, account = wb_proxy.wait_for_pool_account(pick, 5)
        elapsed = time.monotonic() - started
        self.assertTrue(got)
        self.assertIs(account, sentinel)
        # 两次空转之间会睡 100ms，所以第三次命中至少要跨过两个 tick。
        self.assertGreaterEqual(elapsed, 0.15)

    def test_budget_is_bounded(self):
        started = time.monotonic()
        got, account = wb_proxy.wait_for_pool_account(lambda: None, 0.3)
        elapsed = time.monotonic() - started
        self.assertFalse(got)
        self.assertIsNone(account)
        self.assertGreaterEqual(elapsed, 0.25)
        self.assertLess(elapsed, 2.0)


if __name__ == "__main__":
    unittest.main()
