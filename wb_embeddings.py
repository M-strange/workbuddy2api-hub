"""Text embeddings through the upstream ``/v2/embeddings`` endpoint.

Scope is deliberately narrow: build the request, read the reply, and hand back an
OpenAI-shaped ``/v1/embeddings`` payload. Account rotation, credit accounting
and HTTP framing stay in ``wb_proxy`` — same split as ``wb_media`` (pure logic)
vs ``wb_media_client`` (network).

Two upstream quirks drive the shape of this module:

  * the envelope is ``{code, msg, model, data, usage}`` and **HTTP 200 does not
    mean success** — ``code != 0`` is still a failure. A missing model comes back
    as ``code 11351`` with HTTP 500, so it has to be recognised by code, not by
    status;
  * the embedding registry is separate from the chat registry: ``/v3/config``
    does not list these models, and the only one measured working is ``bge-m3``
    (1024 dimensions).
"""

import json
import urllib.error

import wb_accounts

#: Upstream path. Not under /v3: the chat catalogue endpoint knows nothing about
#: embedding models.
EMBEDDINGS_PATH = "/v2/embeddings"

#: The only embedding model measured working upstream. Kept as a constant because
#: "which model" is not a user choice here — there is exactly one.
EMBEDDING_MODEL_BGE = "bge-m3"

#: Upstream "model does not exist" code, returned with HTTP 500.
CODE_MODEL_NOT_FOUND = 11351

#: Response body ceiling. A batch of 256 x 1024 floats is ~2 MB of JSON, so 16 MB
#: leaves room for a much larger batch without letting a broken reply eat memory.
MAX_RESPONSE_BYTES = 16 << 20

#: Inputs per request. Not an upstream limit — a local guard so one call cannot
#: turn into an unbounded credit spend.
MAX_INPUTS = 256

#: Characters per input. bge-m3 truncates silently past its context anyway; a cap
#: here keeps the failure visible instead of silently embedding a prefix.
MAX_INPUT_CHARS = 8192

DEFAULT_TIMEOUT = 60.0


class EmbeddingError(Exception):
    """A classified failure. ``code`` is the OpenAI error code the client sees."""

    def __init__(self, code, message, status=400, retry_after=None):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after


def normalize_input(raw):
    """Accept a string or a list of strings; reject everything else.

    Rejecting empty strings is not pedantry: an empty input embeds to a vector of
    zeros that silently poisons whatever index it lands in.
    """
    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = raw
    elif raw is None:
        raise EmbeddingError("invalid_request", "input 必填", 400)
    else:
        raise EmbeddingError(
            "invalid_request", "input 必须是字符串或字符串数组", 400)
    if not values:
        raise EmbeddingError("invalid_request", "input 不能是空数组", 400)
    if len(values) > MAX_INPUTS:
        raise EmbeddingError(
            "invalid_request",
            "一次最多 %d 条 input（给了 %d 条）" % (MAX_INPUTS, len(values)), 400)
    out = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise EmbeddingError(
                "invalid_request",
                "input[%d] 不是字符串" % index, 400)
        text = value.strip()
        if not text:
            raise EmbeddingError(
                "invalid_request", "input[%d] 是空字符串" % index, 400)
        if len(text) > MAX_INPUT_CHARS:
            raise EmbeddingError(
                "invalid_request",
                "input[%d] 超过 %d 字符" % (index, MAX_INPUT_CHARS), 400)
        out.append(text)
    return out


def strip_realm_prefix(model):
    """Split an optional ``cn:`` / ``global:`` prefix off a model id.

    The gateway's chat path lets clients pin a realm with a prefix; embeddings
    keep that habit so one client config works on both, but the upstream model id
    itself never carries the prefix.
    """
    if not isinstance(model, str):
        return "", None
    text = model.strip()
    if not text:
        return "", None
    head, sep, rest = text.partition(":")
    if sep:
        lowered = head.strip().lower()
        if lowered in ("cn", "china"):
            return rest.strip(), "cn"
        if lowered in ("global", "intl", "international"):
            return rest.strip(), "intl"
    return text, None


def build_body(model, inputs):
    return {"model": model, "input": list(inputs)}


def encode_body(body):
    """Compact JSON, matching what the official clients put on the wire."""
    return json.dumps(body, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _reject(detail, code=None):
    """Map an upstream envelope failure onto an EmbeddingError."""
    if code == CODE_MODEL_NOT_FOUND:
        return EmbeddingError(
            "model_not_found",
            "上游没有这个嵌入模型；目前唯一实测可用的是 %s" % EMBEDDING_MODEL_BGE,
            404)
    return EmbeddingError(
        "upstream_error",
        "上游嵌入失败：%s" % (detail or "未知错误"), 502)


def parse_response(raw, want):
    """Normalise an upstream envelope into an OpenAI ``/v1/embeddings`` payload.

    Every item gets ``object`` and ``index``. Upstream omits ``index``; when it is
    present it is validated instead of trusted, and a count mismatch is a hard
    error — silently pairing vectors with the wrong input text is much harder to
    debug than a 502.
    """
    if not isinstance(raw, dict):
        raise EmbeddingError(
            "upstream_error", "上游响应不是 JSON 对象", 502)
    code = raw.get("code")
    if code is None or code == 0:
        pass
    elif code == CODE_MODEL_NOT_FOUND:
        raise _reject(raw.get("msg"), code)
    else:
        raise _reject(raw.get("msg") or ("code %s" % code), code)
    data = raw.get("data")
    if not isinstance(data, list):
        raise EmbeddingError(
            "upstream_error", "上游响应缺 data 数组", 502)
    if len(data) != want:
        raise EmbeddingError(
            "upstream_error",
            "上游返回 %d 条向量，请求是 %d 条；条数不符时无法安全配对"
            % (len(data), want), 502)
    seen = set()
    items = []
    for position, item in enumerate(data):
        if isinstance(item, dict):
            vector = item.get("embedding")
            index = item.get("index")
        else:
            vector = item
            index = None
        if not isinstance(vector, list) or not vector:
            raise EmbeddingError(
                "upstream_error", "第 %d 条向量为空或不是数组" % position, 502)
        if index is None:
            index = position
        else:
            if isinstance(index, bool) or not isinstance(index, int):
                raise EmbeddingError(
                    "upstream_error", "第 %d 条的 index 不是整数" % position, 502)
            if index < 0 or index >= want:
                raise EmbeddingError(
                    "upstream_error",
                    "第 %d 条的 index=%d 越界（共 %d 条）"
                    % (position, index, want), 502)
            if index in seen:
                raise EmbeddingError(
                    "upstream_error",
                    "第 %d 条的 index=%d 重复" % (position, index), 502)
        seen.add(index)
        items.append({"object": "embedding", "index": index, "embedding": vector})
    items.sort(key=lambda entry: entry["index"])
    out = {
        "object": "list",
        "data": items,
        "model": raw.get("model") or EMBEDDING_MODEL_BGE,
    }
    usage = raw.get("usage")
    if isinstance(usage, dict):
        out["usage"] = usage
    return out


def request(account, model, inputs, timeout=None):
    """Send one embeddings call for one account. Returns the parsed envelope.

    Raises EmbeddingError on any classified failure. The caller owns rotation:
    this function never retries, because a retry here would silently multiply the
    credit spend of a single client request.
    """
    url = account.chat_base_url() + EMBEDDINGS_PATH
    headers = account.headers(purpose="chat", model=model)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    body = encode_body(build_body(model, inputs))
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        # Preserve header-name casing on the pooled path, same as chat does.
        req.wb_exact_headers = list(headers.items())
    except Exception:
        pass
    try:
        resp = wb_accounts.urlopen(
            req, timeout=timeout or DEFAULT_TIMEOUT,
            proxy=getattr(account, "proxy", "") or "")
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise EmbeddingError(
                "upstream_busy",
                "上游限流，稍后再试", 429, retry_after=60)
        detail = ""
        code = None
        try:
            detail = exc.read(4096).decode("utf-8", "replace")
        except Exception:
            pass
        # A missing model comes back as HTTP 500 carrying code 11351 in the
        # envelope, so the body has to be inspected before deciding.
        try:
            parsed = json.loads(detail)
            if isinstance(parsed, dict):
                code = parsed.get("code")
                if isinstance(parsed.get("msg"), str) and parsed["msg"]:
                    detail = parsed["msg"]
        except Exception:
            pass
        raise _reject(detail or ("HTTP %d" % exc.code), code)
    except Exception as exc:
        raise EmbeddingError(
            "upstream_error", "连不上上游：%s" % exc, 502)
    try:
        raw = resp.read(MAX_RESPONSE_BYTES + 1)
    except Exception as exc:
        raise EmbeddingError(
            "upstream_error", "读上游响应失败：%s" % exc, 502)
    finally:
        try:
            resp.close()
        except Exception:
            pass
    if len(raw) > MAX_RESPONSE_BYTES:
        raise EmbeddingError(
            "upstream_error",
            "上游响应超过 %d 字节" % MAX_RESPONSE_BYTES, 502)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise EmbeddingError(
            "upstream_error", "上游响应不是合法 JSON", 502)


def embed(account, model, inputs, timeout=None):
    """One call, envelope parsed and normalised. Convenience for tests/tools."""
    return parse_response(request(account, model, inputs, timeout), len(inputs))
