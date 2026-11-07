"""池子自动探活：超半数账号被本地熔断关着时，后台跑一次一键测试。

Run with: python _test_auto_probe.py
No upstream credentials or outbound network are used.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

_startup_dir = tempfile.TemporaryDirectory(prefix="auto-probe-")
os.environ["ACCOUNTS_DIR"] = _startup_dir.name
os.environ["WB_PROXY_USAGE_DIR"] = _startup_dir.name
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_proxy
import wb_settings


class FakeAccount:
    def __init__(self, uid, realm="cn", enabled=True, ready=True,
                 breaker_until=0.0, cooldown_until=0.0,
                 restricted_until=0.0, model_cool=0.0):
        self.uid = uid
        self.realm = realm
        self.enabled = enabled
        self._ready = ready
        self.breaker_until = breaker_until
        self.degrade_until = 0.0
        self.cooldown_until = cooldown_until
        self.balance_until = 0.0
        self.restricted_until = restricted_until
        self._model_cool = model_cool
        self.note_success_calls = 0

    def ready(self, model=None, refresh=True):
        return self._ready

    def model_cooldown_until(self, model=None):
        return self._model_cool

    def note_success(self, model=None):
        self.note_success_calls += 1


class FakePool:
    def __init__(self, accounts):
        self.accounts = accounts


class AutoProbeSettingsTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="auto-probe-settings-")

    def test_default_is_half_the_pool(self):
        self.assertEqual(wb_settings.auto_probe_percent(self._dir), 50)

    def test_roundtrip(self):
        self.assertEqual(wb_settings.set_auto_probe_percent(self._dir, 0), 0)
        self.assertEqual(wb_settings.auto_probe_percent(self._dir), 0)
        self.assertEqual(wb_settings.set_auto_probe_percent(self._dir, 80), 80)
        self.assertEqual(wb_settings.auto_probe_percent(self._dir), 80)

    def test_out_of_range_values_are_rejected(self):
        for bad in (-1, 101):
            with self.assertRaises(ValueError):
                wb_settings.set_auto_probe_percent(self._dir, bad)
        for bad in ("50", 12.5, True):
            with self.assertRaises(ValueError):
                wb_settings.set_auto_probe_percent(self._dir, bad)

    def test_unreadable_values_fall_back_to_the_default(self):
        import json
        for bad in (True, 999, -5, "50", 12.5):
            with open(os.path.join(self._dir, "settings.json"), "w", encoding="utf-8") as fh:
                json.dump({"auto_probe_percent": bad}, fh)
            self.assertEqual(wb_settings.auto_probe_percent(self._dir), 50)


class PoolParkedStatsTests(unittest.TestCase):
    def test_counts_only_local_penalties(self):
        future = wb_proxy.time.time() + 600
        pool = FakePool([
            FakeAccount("a", ready=False, breaker_until=future),
            FakeAccount("b", ready=False, cooldown_until=future),
            FakeAccount("c", ready=False, model_cool=future),
            FakeAccount("d", ready=False, restricted_until=future),
            FakeAccount("e", ready=True),
            FakeAccount("f", ready=True, enabled=False),
            FakeAccount("g", ready=True, realm="intl"),
        ])
        with mock.patch.object(wb_proxy, "POOL", pool):
            stats = wb_proxy.pool_parked_stats("cn", model="m")
        self.assertEqual(stats["total"], 5)      # 已启用 + 本区域：a,b,c,d,e
        self.assertEqual(stats["parked"], 3)     # a,b,c 是本地惩罚
        self.assertEqual(stats["restricted"], 1)  # d 是风控，不参与触发
        self.assertEqual(stats["blocked"], 0)


class MaybeAutoProbeTests(unittest.TestCase):
    def setUp(self):
        wb_proxy._AUTO_PROBE.update({"running": False, "last_at": 0.0, "last": {}})
        self.future = wb_proxy.time.time() + 600
        self.started = []
        self._orig_pool = wb_proxy.POOL

    def tearDown(self):
        wb_proxy.POOL = self._orig_pool
        wb_proxy._AUTO_PROBE.update({"running": False, "last_at": 0.0, "last": {}})

    def _root(self, parked, ready, percent=50):
        accounts = ([FakeAccount("p%d" % i, ready=False, breaker_until=self.future)
                     for i in range(parked)]
                    + [FakeAccount("r%d" % i, ready=True) for i in range(ready)])
        wb_proxy.POOL = FakePool(accounts)
        return accounts

    def _run(self, percent=50, hold=0.0):
        threads = []

        class RecordingThread:
            def __init__(self, target=None, args=(), name=None, daemon=None):
                threads.append((target, args))
                self._target = target

            def start(self):
                pass

        with mock.patch.object(wb_settings, "auto_probe_percent", return_value=percent), \
                mock.patch.object(wb_proxy, "restriction_hold_remaining", return_value=hold), \
                mock.patch.object(wb_proxy.threading, "Thread", RecordingThread):
            fired = wb_proxy.maybe_auto_probe("cn", "m", reason="test")
        return fired, threads

    def test_more_than_half_parked_fires(self):
        self._root(3, 2)
        fired, threads = self._run()
        self.assertTrue(fired)
        self.assertEqual(len(threads), 1)
        self.assertEqual(threads[0][1][0], "cn")

    def test_exactly_half_does_not_fire(self):
        self._root(2, 2)
        fired, _ = self._run()
        self.assertFalse(fired)

    def test_zero_percent_disables_it(self):
        self._root(5, 0)
        fired, _ = self._run(percent=0)
        self.assertFalse(fired)

    def test_restriction_hold_blocks_it(self):
        self._root(5, 0)
        fired, _ = self._run(hold=120.0)
        self.assertFalse(fired)

    def test_it_does_not_fire_twice_in_a_row(self):
        self._root(3, 1)
        first, _ = self._run()
        second, _ = self._run()
        self.assertTrue(first)
        self.assertFalse(second)


class AutoProbeWorkerTests(unittest.TestCase):
    def setUp(self):
        self._orig_pool = wb_proxy.POOL
        wb_proxy._AUTO_PROBE.update({"running": False, "last_at": 0.0, "last": {}})
        self.future = wb_proxy.time.time() + 600

    def tearDown(self):
        wb_proxy.POOL = self._orig_pool
        wb_proxy._AUTO_PROBE.update({"running": False, "last_at": 0.0, "last": {}})

    def test_it_probes_accounts_and_records_the_run(self):
        ok = FakeAccount("ok")
        blocked = FakeAccount("blocked", restricted_until=self.future)
        wb_proxy.POOL = FakePool([ok, blocked])
        seen = []

        def fake_probe(account, model=None, timeout=30):
            seen.append(account.uid)
            account.note_success(model=model)
            return {"uid": account.uid, "ok": True}

        with mock.patch.object(wb_proxy, "probe_local_network",
                               return_value={"ok": True}), \
                mock.patch.object(wb_proxy, "probe_account", fake_probe):
            wb_proxy._auto_probe_worker("cn", "m", "no usable account")

        # 被 403 限制的账号不进探针名单：那等于换号继续打上游。
        self.assertEqual(seen, ["ok"])
        state = wb_proxy.auto_probe_state()
        self.assertFalse(state["running"])
        self.assertEqual(state["last"]["tested"], 1)
        self.assertEqual(state["last"]["passed"], 1)
        self.assertEqual(state["last"]["trigger"], "no usable account")
        self.assertEqual(ok.note_success_calls, 1)

    def test_local_network_down_skips_the_run(self):
        wb_proxy.POOL = FakePool([FakeAccount("a")])
        with mock.patch.object(wb_proxy, "probe_local_network",
                               return_value={"ok": False}), \
                mock.patch.object(wb_proxy, "probe_account") as probe:
            wb_proxy._auto_probe_worker("cn", "m", "test")
        probe.assert_not_called()
        self.assertEqual(wb_proxy.auto_probe_state()["last"], {})
        self.assertFalse(wb_proxy.auto_probe_state()["running"])


if __name__ == "__main__":
    unittest.main()
