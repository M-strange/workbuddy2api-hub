"""External API keys, authorization request state and call-log contracts."""

import json
import os
import sys
import tempfile
import time
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_external_api as external


def check(label, condition, extra=""):
    if not condition:
        raise AssertionError("%s: %s" % (label, extra))
    print("  [PASS] " + label)


def main():
    root = tempfile.mkdtemp(prefix="wb-external-store-")
    accounts = os.path.join(root, "accounts")
    usage = os.path.join(root, "usage")

    print("[1] external keys have independent scopes and soft deletion")
    created = external.save_keys(accounts, [{
        "name": "集成测试",
        "key": "ext-secret-123",
        "scopes": ["account:auth", "account:read", "unknown:scope"],
        "enabled": True,
    }])
    check("one key saved", len(created) == 1, created)
    check("unsupported scope removed", created[0]["scopes"] == ["account:auth", "account:read"], created)
    matched = external.match_key(accounts, "ext-secret-123")
    check("key matches", matched and matched["id"] == created[0]["id"], matched)
    check("wrong key does not match", external.match_key(accounts, "old-gateway-key") is None)

    deleted = external.save_keys(accounts, [], delete_ids=[created[0]["id"]])
    check("deleted key is no longer live", deleted == [], deleted)
    history = external.list_keys(accounts, include_deleted=True)
    check("deleted row remains for history", len(history) == 1, history)
    check("deleted secret is wiped", history[0]["key"] == "", history)
    check("deleted key cannot authenticate", external.match_key(accounts, "ext-secret-123") is None)
    stale_update = external.save_keys(accounts, [dict(created[0], enabled=True)], delete_ids=[])
    check("stale update cannot revive a deleted key", stale_update == [], stale_update)
    check("deleted key stays revoked after stale update",
          external.match_key(accounts, "ext-secret-123") is None)
    if os.name != "nt":
        mode = os.stat(os.path.join(accounts, "external-api.json")).st_mode & 0o777
        check("external key store uses private permissions", mode == 0o600, oct(mode))

    print("\n[2] account output is explicitly redacted")
    account = external.sanitize_account({
        "uid": "uid-1",
        "nickname": "Alice",
        "realm": "intl",
        "enabled": True,
        "accessToken": "access-secret",
        "refreshToken": "refresh-secret",
        "proxy": "http://user:password@example.com:8080",
        "file": "account.json",
    })
    check("safe fields survive", account == {
        "uid": "uid-1", "nickname": "Alice", "realm": "intl", "enabled": True,
        "health": "healthy", "health_summary": "healthy",
    }, account)
    encoded = json.dumps(account, ensure_ascii=False)
    check("token is absent", "access-secret" not in encoded and "refresh-secret" not in encoded)
    check("proxy is absent", "example.com" not in encoded)

    print("\n[3] authorization request cache retains terminal state")
    requests = external.AuthorizationRequests(pending_ttl=60, final_ttl=60)
    request_id = requests.create(
        "intl", "internal-state", "https://auth.example/login", key_id="key-a")
    pending = requests.get(request_id, key_id="key-a")
    check("request can be read", pending["state"] == "internal-state", pending)
    check("another key cannot read the request",
          requests.get(request_id, key_id="key-b") is None)
    first_claim, should_poll = requests.claim_poll(request_id, key_id="key-a")
    second_claim, duplicate_poll = requests.claim_poll(request_id, key_id="key-a")
    check("only one request owns the upstream poll", should_poll and not duplicate_poll,
          (first_claim, second_claim))
    requests.finish(request_id, {"status": "ok", "account": account}, key_id="key-a")
    late = requests.finish(
        request_id, {"status": "error", "message": "late"}, key_id="key-a")
    first = requests.get(request_id, key_id="key-a")
    second = requests.get(request_id, key_id="key-a")
    check("terminal result is retained", first["result"]["status"] == "ok", first)
    check("repeated terminal read is stable", second["result"] == first["result"], second)
    check("late terminal result cannot overwrite success",
          late["result"]["status"] == "ok", late)

    expiring = external.AuthorizationRequests(pending_ttl=1, final_ttl=60)
    expiring_id = expiring.create(
        "intl", "state", "https://auth.example/login", key_id="key-a")
    with mock.patch.object(external.time, "time", return_value=time.time() + 2):
        expired = expiring.get(expiring_id, key_id="key-a")
    check("pending request expires into a stable terminal state",
          expired["result"]["status"] == "expired", expired)

    print("\n[4] call logs contain key ids but never secrets")
    external.record_call(usage, {
        "key_id": "ext-id",
        "key_secret": "ext-secret-123",
        "method": "GET",
        "path": "/v1/accounts?realm=intl",
        "realm": "intl",
        "status": 200,
        "elapsed_ms": 12,
    })
    rows = external.recent_calls(usage, limit=10)
    check("call row is readable", len(rows) == 1 and rows[0]["key_id"] == "ext-id", rows)
    check("secret is not written", "ext-secret-123" not in open(
        os.path.join(usage, "external-api.jsonl"), encoding="utf-8").read())

    print("\n[5] call logs expose stable page metadata")
    for index in range(45):
        external.record_call(usage, {
            "key_id": "ext-id",
            "method": "GET",
            "path": "/v1/accounts?realm=intl",
            "status": 200,
            "elapsed_ms": index,
        })
    page = external.recent_calls_page(usage, page=2, page_size=20)
    check("page metadata is complete", page["page"] == 2 and page["page_size"] == 20
          and page["total"] == 46 and page["pages"] == 3, page)
    check("middle page contains 20 newest-first rows", len(page["records"]) == 20
          and page["records"][0]["elapsed_ms"] == 24, page)
    last = external.recent_calls_page(usage, page=999, page_size=20)
    check("out-of-range page clamps to last page", last["page"] == 3
          and len(last["records"]) == 6, last)

    print("\n[6] call log size is bounded without writing unbounded history")
    bounded_usage = os.path.join(root, "bounded-usage")
    old_bytes, old_records = (
        external.CALL_LOG_MAX_BYTES, external.CALL_LOG_MAX_RECORDS)
    try:
        external.CALL_LOG_MAX_BYTES = 350
        external.CALL_LOG_MAX_RECORDS = 3
        for index in range(20):
            external.record_call(bounded_usage, {
                "key_id": "ext-id",
                "method": "GET",
                "path": "/v1/accounts?realm=intl",
                "status": 200,
                "elapsed_ms": index,
            })
    finally:
        external.CALL_LOG_MAX_BYTES, external.CALL_LOG_MAX_RECORDS = (
            old_bytes, old_records)
    bounded = external.recent_calls(bounded_usage, limit=100)
    bounded_path = os.path.join(bounded_usage, "external-api.jsonl")
    check("record count stays capped", 1 <= len(bounded) <= 3, bounded)
    check("file size stays bounded", os.path.getsize(bounded_path) <= 350,
          os.path.getsize(bounded_path))
    check("newest record survives compaction", bounded[0]["elapsed_ms"] == 19, bounded)

    print("PASS=1 FAIL=0")


if __name__ == "__main__":
    main()
