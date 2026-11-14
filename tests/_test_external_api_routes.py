"""HTTP contracts for the external account API and its panel endpoints."""

import email
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_external_api as external
import wb_proxy as proxy


class DispatchRequest(proxy.Handler):
    def __init__(self, path, headers=None, command="GET", body=b""):
        self.path = path
        self.command = command
        self.request_version = "HTTP/1.1"
        self.close_connection = True
        raw = "".join("%s: %s\r\n" % item for item in (headers or {}).items())
        self.headers = email.message_from_string(raw)
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.status = None
        self.client_address = ("127.0.0.1", 0)

    def send_response(self, code, message=None):
        self.status = code

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass

    def log_message(self, fmt, *args):
        pass

    def dispatch(self):
        getattr(self, "do_" + self.command)()
        raw = self.wfile.getvalue().decode("utf-8")
        return self.status, json.loads(raw) if raw else None, raw


class FakePool(object):
    def __init__(self):
        self.started = []
        self.polls = 0

    def start_login(self, **kwargs):
        self.started.append(kwargs)
        return {
            "state": "internal-state-1",
            "authUrl": "https://login.example/authorize?state=secret-state",
            "realm": kwargs["realm"],
            "platform": kwargs.get("platform"),
            "proxySlot": None,
            "proxy": "http://user:password@proxy.example:8080",
        }

    def poll_login(self, state):
        self.polls += 1
        return {
            "status": "ok",
            "account": {
                "uid": "uid-intl-1",
                "nickname": "外部账号",
                "realm": "intl",
                "enabled": True,
                "accessToken": "do-not-return",
                "refreshToken": "do-not-return",
                "proxy": "do-not-return",
            },
        }


class ExternalRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wb-external-routes-")
        self.addCleanup(self.tmp.cleanup)
        self.accounts = os.path.join(self.tmp.name, "accounts")
        self.usage = os.path.join(self.tmp.name, "usage")
        os.makedirs(self.accounts, exist_ok=True)
        os.makedirs(self.usage, exist_ok=True)
        self.pool = FakePool()
        rows = external.save_keys(self.accounts, [{
            "id": "ext-full",
            "name": "集成调用方",
            "key": "ext-full-secret",
            "scopes": ["account:auth", "account:read"],
            "enabled": True,
        }])
        self.full_key = rows[0]["key"]
        read_only = external.save_keys(self.accounts, [{
            "id": "ext-read",
            "name": "只读调用方",
            "key": "ext-read-secret",
            "scopes": ["account:read"],
            "enabled": True,
        }], delete_ids=[])
        self.read_key = next(row["key"] for row in external.list_keys(self.accounts)
                             if row["id"] == "ext-read")
        external.save_keys(self.accounts, [{
            "id": "ext-auth-only",
            "name": "另一个授权调用方",
            "key": "ext-auth-only-secret",
            "scopes": ["account:auth"],
            "enabled": True,
        }], delete_ids=[])
        self.auth_only_key = next(
            row["key"] for row in external.list_keys(self.accounts)
            if row["id"] == "ext-auth-only")

    def dispatch(self, path, key=None, command="GET", payload=None, panel=False):
        headers = {}
        if key:
            headers["Authorization"] = "Bearer " + key
        if panel:
            headers["X-Panel-Token"] = proxy.PANEL.create()
        body = b""
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Length"] = str(len(body))
        request = DispatchRequest(path, headers=headers, command=command, body=body)
        with mock.patch.multiple(
            proxy,
            ACCOUNTS_DIR=self.accounts,
            USAGE_DIR=self.usage,
            API_KEY="legacy-gateway-secret",
            POOL=self.pool,
            account_views=lambda realm=None: [{
                "uid": "uid-intl-1",
                "nickname": "账号一",
                "realm": realm or "intl",
                "enabled": True,
                "accessToken": "panel-secret",
                "proxy": "panel-secret",
            }],
        ):
            return request.dispatch()

    def test_external_key_is_required_and_legacy_key_does_not_fallback(self):
        status, body, _ = self.dispatch("/v1/accounts?realm=intl")
        self.assertEqual(status, 401)
        status, body, _ = self.dispatch("/v1/accounts?realm=intl", key="legacy-gateway-secret")
        self.assertEqual(status, 401)
        self.assertEqual(external.recent_calls(self.usage), [],
                         "unauthenticated abuse must not grow the persistent log")

    def test_account_list_requires_read_scope_and_valid_realm(self):
        status, body, raw = self.dispatch("/v1/accounts?realm=intl", key=self.read_key)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["accounts"][0]["uid"], "uid-intl-1")
        self.assertNotIn("panel-secret", raw)
        status, body, _ = self.dispatch("/v1/accounts?realm=codearts", key=self.read_key)
        self.assertEqual(status, 400)
        status, body, _ = self.dispatch("/v1/accounts?realm=intl", key="ext-full-secret")
        self.assertEqual(status, 200)

    def test_authorize_returns_public_request_id_and_repeated_terminal_status(self):
        status, body, raw = self.dispatch(
            "/v1/accounts/authorize", key=self.full_key, command="POST",
            payload={"realm": "intl"})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["request_id"].startswith("ar_"))
        self.assertEqual(body["status"], "pending")
        self.assertIn("auth_url", body)
        self.assertNotIn("internal-state-1", raw)
        self.assertNotIn("proxy.example", raw)
        request_id = body["request_id"]
        records = external.recent_calls(self.usage)
        self.assertEqual(records[0]["path"], "/v1/accounts/authorize")

        status, body, raw = self.dispatch(
            "/v1/accounts/authorize/" + request_id, key=self.full_key)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["status"], "ok")
        self.assertNotIn("do-not-return", raw)
        status, repeated, _ = self.dispatch(
            "/v1/accounts/authorize/" + request_id, key=self.full_key)
        self.assertEqual(status, 200)
        self.assertEqual(repeated, body)
        records = external.recent_calls(self.usage)
        self.assertEqual(
            records[0]["path"], "/v1/accounts/authorize/{request_id}",
            "request ids are capability-like and must not be stored in call logs")

    def test_authorization_request_is_bound_to_the_creating_key(self):
        status, body, _ = self.dispatch(
            "/v1/accounts/authorize", key=self.full_key, command="POST",
            payload={"realm": "intl"})
        self.assertEqual(status, 200, body)
        request_id = body["request_id"]
        status, body, _ = self.dispatch(
            "/v1/accounts/authorize/" + request_id, key=self.auth_only_key)
        self.assertEqual(status, 404, body)
        self.assertEqual(
            self.pool.polls, 0,
            "a different key must not exchange the original login state")

    def test_authorize_requires_auth_scope_and_valid_realm(self):
        status, body, _ = self.dispatch(
            "/v1/accounts/authorize", key=self.read_key, command="POST",
            payload={"realm": "intl"})
        self.assertEqual(status, 403)
        records = external.recent_calls(self.usage, limit=1)
        self.assertEqual(records[0]["status"], 403)
        status, body, _ = self.dispatch(
            "/v1/accounts/authorize", key=self.full_key, command="POST",
            payload={"realm": "cn"})
        self.assertEqual(status, 200)
        status, body, _ = self.dispatch(
            "/v1/accounts/authorize", key=self.full_key, command="POST",
            payload={"realm": "codearts"})
        self.assertEqual(status, 400)
        status, body, _ = self.dispatch(
            "/v1/accounts/authorize/does-not-exist", key=self.full_key)
        self.assertEqual(status, 404)

    def test_panel_can_manage_external_keys_and_read_call_records(self):
        status, body, _ = self.dispatch("/api/external/keys", panel=True)
        self.assertEqual(status, 200, body)
        self.assertEqual(len(body["keys"]), 3)
        status, body, raw = self.dispatch(
            "/api/external/keys", command="POST", panel=True,
            payload={"action": "create", "name": "新项目",
                     "scopes": ["account:read"]})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["key"].startswith("sk-ext-"))
        self.assertEqual(raw.count(body["key"]), 1,
                         "new key should be returned exactly once")
        self.dispatch("/v1/accounts?realm=intl", key=self.full_key)
        status, body, _ = self.dispatch("/api/external/call-records", panel=True)
        self.assertEqual(status, 200, body)
        self.assertGreaterEqual(len(body["records"]), 1)
        status, body, _ = self.dispatch("/api/external/call-records", key=self.full_key)
        self.assertEqual(status, 401)

    def test_deleted_key_cannot_be_reenabled_by_a_stale_update(self):
        status, body, _ = self.dispatch(
            "/api/external/keys", command="POST", panel=True,
            payload={"action": "delete", "id": "ext-full"})
        self.assertEqual(status, 200, body)
        status, body, _ = self.dispatch(
            "/api/external/keys", command="POST", panel=True,
            payload={"action": "update", "id": "ext-full", "enabled": True})
        self.assertEqual(status, 404, body)
        self.assertIsNone(external.match_key(self.accounts, self.full_key))

    def test_internal_errors_are_not_returned_to_external_callers(self):
        with mock.patch.object(
                self.pool, "start_login",
                side_effect=RuntimeError("proxy user:password at internal.example")):
            status, body, raw = self.dispatch(
                "/v1/accounts/authorize", key=self.full_key, command="POST",
                payload={"realm": "intl"})
        self.assertEqual(status, 502, body)
        self.assertNotIn("user:password", raw)
        self.assertNotIn("internal.example", raw)

    def test_panel_call_records_are_paginated(self):
        for index in range(45):
            external.record_call(self.usage, {
                "key_id": "ext-full",
                "method": "GET",
                "path": "/v1/accounts?realm=intl",
                "status": 200,
                "elapsed_ms": index,
            })
        status, body, _ = self.dispatch(
            "/api/external/call-records?page=2&page_size=20", panel=True)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["page"], 2)
        self.assertEqual(body["page_size"], 20)
        self.assertEqual(body["total"], 45)
        self.assertEqual(body["pages"], 3)
        self.assertEqual(len(body["records"]), 20)
        self.assertEqual(body["records"][0]["elapsed_ms"], 24)

        status, body, _ = self.dispatch(
            "/api/external/call-records", panel=True)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["page_size"], 20)
        self.assertEqual(body["total"], 45)
        self.assertEqual(body["pages"], 3)
        self.assertEqual(len(body["records"]), 20)

        status, body, _ = self.dispatch(
            "/api/external/call-records?limit=5", panel=True)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["page_size"], 5)
        self.assertEqual(body["total"], 45)
        self.assertEqual(len(body["records"]), 5)

        status, body, _ = self.dispatch(
            "/api/external/call-records?page=999&page_size=20", panel=True)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["page"], 3)
        self.assertEqual(len(body["records"]), 5)


if __name__ == "__main__":
    unittest.main()
