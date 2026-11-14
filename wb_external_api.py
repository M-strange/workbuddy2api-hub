"""Storage and in-memory state for the external account API.

The gateway's existing API keys are tied to model routing semantics.  This
module deliberately keeps the public account API credentials separate so a
future change to one contract cannot silently widen the other.
"""

import copy
import hmac
import json
import os
import secrets
import threading
import time
from collections import deque


EXTERNAL_KEY_FILE = "external-api.json"
CALL_LOG_FILE = "external-api.jsonl"
SUPPORTED_SCOPES = ("account:auth", "account:read")
CALL_LOG_MAX_BYTES = 2 * 1024 * 1024
CALL_LOG_MAX_RECORDS = 5000
_STORE_LOCK = threading.RLock()
_CALL_LOCK = threading.Lock()


def _store_path(accounts_dir):
    return os.path.join(accounts_dir, EXTERNAL_KEY_FILE)


def _call_log_path(usage_dir):
    return os.path.join(usage_dir, CALL_LOG_FILE)


def _clean_scopes(value):
    if isinstance(value, str):
        raw = [part.strip() for part in value.replace(";", ",").split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    out = []
    for item in raw:
        scope = str(item or "").strip()
        if scope in SUPPORTED_SCOPES and scope not in out:
            out.append(scope)
    return [scope for scope in SUPPORTED_SCOPES if scope in out]


def _mask_key(value):
    value = str(value or "")
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * 8 + value[-4:]


def _clean_key(raw):
    if not isinstance(raw, dict):
        return None
    deleted_at = str(raw.get("deleted_at") or "").strip()
    key = str(raw.get("key") or "").strip()
    if not key and not deleted_at:
        return None
    scopes = _clean_scopes(raw.get("scopes"))
    if not scopes and not deleted_at:
        scopes = list(SUPPORTED_SCOPES)
    return {
        "id": str(raw.get("id") or secrets.token_hex(8)),
        "name": str(raw.get("name") or "").strip() or "未命名",
        "key": key,
        "scopes": scopes,
        "enabled": False if deleted_at else raw.get("enabled", True) is not False,
        "created_at": str(raw.get("created_at") or time.strftime("%Y/%m/%d %H:%M")),
        "deleted_at": deleted_at,
    }


def _load(accounts_dir):
    try:
        with open(_store_path(accounts_dir), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _write(accounts_dir, data):
    os.makedirs(accounts_dir, exist_ok=True)
    path = _store_path(accounts_dir)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    # The file contains the live external credentials.  Tighten permissions
    # before the atomic replace so there is no permissive rename window.
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


def _retired(entry):
    return {
        "id": entry.get("id") or secrets.token_hex(8),
        "name": entry.get("name") or "未命名",
        "key": "",
        "scopes": list(entry.get("scopes") or []),
        "enabled": False,
        "created_at": entry.get("created_at") or "",
        "deleted_at": entry.get("deleted_at") or time.strftime("%Y/%m/%d %H:%M"),
    }


def list_keys(accounts_dir, include_deleted=False):
    data = _load(accounts_dir)
    raw_rows = data.get("keys")
    if not isinstance(raw_rows, list):
        raw_rows = data.get("external_api_keys")
    if not isinstance(raw_rows, list):
        raw_rows = []
    rows = []
    ids = set()
    seen_keys = set()
    for raw in raw_rows:
        entry = _clean_key(raw)
        if entry is None:
            continue
        candidate = entry["id"]
        if candidate in ids:
            suffix = 2
            while "%s-%d" % (candidate, suffix) in ids:
                suffix += 1
            candidate = "%s-%d" % (candidate, suffix)
            entry["id"] = candidate
        ids.add(candidate)
        if entry["key"]:
            if entry["key"] in seen_keys:
                continue
            seen_keys.add(entry["key"])
        if include_deleted or not entry["deleted_at"]:
            rows.append(entry)
    return rows


def save_keys(accounts_dir, keys, delete_ids=None):
    """Upsert external keys and return live entries.

    ``delete_ids`` makes the operation safe for a stale browser tab.  A row is
    retired only when its id is explicitly listed; omitted existing rows stay
    intact.
    """
    with _STORE_LOCK:
        previous = list_keys(accounts_dir, include_deleted=True)
        old_by_id = {entry["id"]: entry for entry in previous}
        explicit_delete = set(str(value) for value in (delete_ids or []))
        upsert = delete_ids is not None
        cleaned = []
        seen_ids = set()
        seen_keys = set()
        for raw in keys or []:
            if not isinstance(raw, dict):
                continue
            entry_id = str(raw.get("id") or "").strip()
            stored = old_by_id.get(entry_id) or {}
            # A stale browser snapshot must never revive a credential that was
            # explicitly deleted after that snapshot was read.
            if stored.get("deleted_at"):
                continue
            value = str(raw.get("key") or "").strip()
            if not value and entry_id:
                value = stored.get("key") or ""
            if not value:
                continue
            candidate = dict(raw, key=value)
            candidate.pop("deleted_at", None)
            entry = _clean_key(candidate)
            if entry is None:
                continue
            if entry_id and entry_id in old_by_id:
                entry["id"] = entry_id
                entry["created_at"] = stored.get("created_at") or entry["created_at"]
            while entry["id"] in seen_ids:
                entry["id"] = secrets.token_hex(8)
            if entry["key"] in seen_keys:
                continue
            seen_ids.add(entry["id"])
            seen_keys.add(entry["key"])
            cleaned.append(entry)
        for old in previous:
            if old["id"] in seen_ids:
                continue
            if upsert and old["id"] not in explicit_delete:
                cleaned.append(old)
                seen_ids.add(old["id"])
                continue
            cleaned.append(_retired(old))
            seen_ids.add(old["id"])
        _write(accounts_dir, {"keys": cleaned})
        return [entry for entry in cleaned if not entry.get("deleted_at")]


def new_key():
    return "sk-ext-" + secrets.token_urlsafe(24)


def match_key(accounts_dir, supplied):
    supplied = str(supplied or "").strip()
    if not supplied:
        return None
    for entry in list_keys(accounts_dir):
        if entry.get("enabled") and hmac.compare_digest(supplied, entry.get("key") or ""):
            return copy.deepcopy(entry)
    return None


def has_scope(entry, scope):
    return bool(entry and scope in (entry.get("scopes") or []))


def panel_key_view(entry):
    return {
        "id": entry.get("id") or "",
        "name": entry.get("name") or "未命名",
        "masked": _mask_key(entry.get("key")),
        "scopes": list(entry.get("scopes") or []),
        "enabled": entry.get("enabled", True) is not False,
        "created_at": entry.get("created_at") or "",
    }


def sanitize_account(account):
    if hasattr(account, "public"):
        account = account.public()
    account = account if isinstance(account, dict) else {}
    if account.get("accountBanned") or account.get("tokenExpired") or account.get("needRelogin"):
        health = "unhealthy"
    elif (account.get("lastError") or account.get("inCooldown") or
          account.get("breakerFor") or account.get("degradeFor")):
        health = "degraded"
    else:
        health = "healthy" if account.get("enabled", True) else "disabled"
    return {
        "uid": str(account.get("uid") or ""),
        "nickname": str(account.get("nickname") or account.get("uid") or ""),
        "realm": str(account.get("realm") or ""),
        "enabled": bool(account.get("enabled")),
        "health": health,
        "health_summary": health,
    }


class AuthorizationRequests(object):
    def __init__(self, pending_ttl=600, final_ttl=1800):
        self.pending_ttl = max(1, int(pending_ttl))
        self.final_ttl = max(1, int(final_ttl))
        self._lock = threading.RLock()
        self._items = {}

    def _prune(self, now):
        for key, item in list(self._items.items()):
            if item.get("expires_at", 0) <= now:
                self._items.pop(key, None)

    def create(self, realm, state, auth_url, key_id=""):
        now = time.time()
        request_id = "ar_" + secrets.token_urlsafe(12)
        with self._lock:
            self._prune(now)
            self._items[request_id] = {
                "request_id": request_id,
                "realm": realm,
                "state": state,
                "auth_url": auth_url,
                "key_id": str(key_id or ""),
                "created_at": now,
                "expires_at": now + self.pending_ttl,
                "result": None,
                "polling": False,
            }
        return request_id

    def _get_locked(self, request_id, key_id, now):
        item = self._items.get(str(request_id or "").strip())
        if item is None:
            return None
        owner = str(item.get("key_id") or "")
        if owner and key_id is not None and owner != str(key_id or ""):
            return None
        if item["expires_at"] <= now:
            if item.get("result") is None:
                item["result"] = {"status": "expired",
                                  "message": "authorization request expired"}
                item["state"] = ""
                item["polling"] = False
                item["expires_at"] = now + self.final_ttl
            else:
                self._items.pop(item["request_id"], None)
                return None
        return item

    def get(self, request_id, key_id=None):
        now = time.time()
        with self._lock:
            item = self._get_locked(request_id, key_id, now)
            if item is None:
                return None
            return copy.deepcopy(item)

    def claim_poll(self, request_id, key_id=None):
        """Return an owned request and reserve a single upstream poll."""
        now = time.time()
        with self._lock:
            item = self._get_locked(request_id, key_id, now)
            if item is None:
                return None
            should_poll = item.get("result") is None and not item.get("polling")
            if should_poll:
                item["polling"] = True
            return copy.deepcopy(item), should_poll

    def release_poll(self, request_id, key_id=None):
        with self._lock:
            item = self._get_locked(request_id, key_id, time.time())
            if item is not None and item.get("result") is None:
                item["polling"] = False

    def finish(self, request_id, result, key_id=None):
        now = time.time()
        with self._lock:
            item = self._get_locked(request_id, key_id, now)
            if item is None:
                return None
            # The first terminal result wins.  A late concurrent response must
            # not replace a successful account import with an error.
            if item.get("result") is not None:
                item["polling"] = False
                return copy.deepcopy(item)
            item["result"] = copy.deepcopy(result or {"status": "error"})
            item["state"] = ""
            item["polling"] = False
            item["expires_at"] = now + self.final_ttl
            return copy.deepcopy(item)


def _compact_call_log(path):
    try:
        if os.path.getsize(path) <= CALL_LOG_MAX_BYTES:
            return
        with open(path, encoding="utf-8", errors="replace") as fh:
            tail = list(deque(fh, maxlen=CALL_LOG_MAX_RECORDS))
    except (FileNotFoundError, OSError):
        return

    selected = []
    selected_bytes = 0
    for line in reversed(tail):
        line_bytes = len(line.encode("utf-8"))
        if selected and selected_bytes + line_bytes > CALL_LOG_MAX_BYTES:
            break
        selected.append(line)
        selected_bytes += line_bytes
    selected.reverse()

    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.writelines(selected)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass


def record_call(usage_dir, row):
    clean = {}
    for key, value in (row or {}).items():
        if key in ("key", "key_secret", "secret", "api_key"):
            continue
        clean[key] = value
    clean.setdefault("at", time.time())
    clean.setdefault("iso", time.strftime("%Y-%m-%dT%H:%M:%S"))
    os.makedirs(usage_dir, exist_ok=True)
    with _CALL_LOCK:
        with open(_call_log_path(usage_dir), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(clean, ensure_ascii=False, separators=(",", ":")) + "\n")
        _compact_call_log(_call_log_path(usage_dir))


def recent_calls(usage_dir, limit=100):
    try:
        limit = max(1, min(CALL_LOG_MAX_RECORDS, int(limit)))
    except (TypeError, ValueError):
        limit = 100
    path = _call_log_path(usage_dir)
    try:
        with open(path, encoding="utf-8") as fh:
            rows = []
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
        return list(reversed(rows[-limit:]))
    except (FileNotFoundError, OSError):
        return []


def recent_calls_page(usage_dir, page=1, page_size=20):
    """Return one newest-first page of call records with stable metadata."""
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = max(1, min(100, int(page_size)))
    except (TypeError, ValueError):
        page_size = 20

    path = _call_log_path(usage_dir)
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except (FileNotFoundError, OSError):
        rows = []

    ordered = list(reversed(rows))
    total = len(ordered)
    pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, pages)
    start = (page - 1) * page_size
    return {
        "records": ordered[start:start + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": pages,
    }
