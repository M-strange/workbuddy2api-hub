"""wb_embeddings: input normalisation, envelope parsing, one upstream call."""

import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_accounts
import wb_embeddings


class FakeAccount(object):
    def __init__(self, base="https://upstream.test", proxy=""):
        self._base = base
        self.proxy = proxy
        self.header_calls = []

    def chat_base_url(self):
        return self._base

    def headers(self, purpose="chat", session_key=None, turn_request_id=None,
                model=None, conversation_id=None, media_identity=None):
        self.header_calls.append({"purpose": purpose, "model": model})
        return {"Authorization": "Bearer token", "X-Test": "1"}


class FakeResponse(object):
    def __init__(self, payload, limit=None):
        if isinstance(payload, bytes):
            self._raw = payload
        else:
            self._raw = json.dumps(payload).encode("utf-8")
        self.limit = limit
        self.closed = False

    def read(self, amount=None):
        if self.limit is not None and amount is not None and amount > self.limit:
            # Behave like a stream that is larger than the ceiling.
            return b"x" * amount
        if amount is None:
            return self._raw
        return self._raw[:amount]

    def close(self):
        self.closed = True


class PatchUrlopen(object):
    """Context manager swapping wb_accounts.urlopen for a scripted fake."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requests = []
        self.kwargs = []
        self._original = None

    def __enter__(self):
        self._original = wb_accounts.urlopen

        def fake(req, timeout=30, proxy=""):
            self.requests.append(req)
            self.kwargs.append({"timeout": timeout, "proxy": proxy})
            if self.error is not None:
                raise self.error
            return self.result

        wb_accounts.urlopen = fake
        return self

    def __exit__(self, *exc_info):
        wb_accounts.urlopen = self._original
        return False


def envelope(data, code=0, msg="", model="bge-m3"):
    return {"code": code, "msg": msg, "model": model, "data": data,
            "usage": {"prompt_tokens": 7, "total_tokens": 7}}


class NormalizeInputTests(unittest.TestCase):
    def test_single_string(self):
        self.assertEqual(wb_embeddings.normalize_input("hi"), ["hi"])

    def test_list_preserved_in_order(self):
        self.assertEqual(wb_embeddings.normalize_input(["a", "b"]), ["a", "b"])

    def test_none_rejected(self):
        with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
            wb_embeddings.normalize_input(None)
        self.assertEqual(ctx.exception.code, "invalid_request")

    def test_number_rejected(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.normalize_input(42)

    def test_empty_list_rejected(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.normalize_input([])

    def test_empty_string_rejected(self):
        with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
            wb_embeddings.normalize_input(["ok", "   "])
        self.assertIn("input[1]", ctx.exception.message)

    def test_non_string_element_rejected(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.normalize_input(["ok", 3])

    def test_too_many_inputs(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.normalize_input(["x"] * (wb_embeddings.MAX_INPUTS + 1))

    def test_input_too_long(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.normalize_input(
                "x" * (wb_embeddings.MAX_INPUT_CHARS + 1))


class RealmPrefixTests(unittest.TestCase):
    def test_cn_prefix(self):
        self.assertEqual(wb_embeddings.strip_realm_prefix("cn:bge-m3"),
                         ("bge-m3", "cn"))

    def test_global_prefix(self):
        self.assertEqual(wb_embeddings.strip_realm_prefix("global:bge-m3"),
                         ("bge-m3", "intl"))

    def test_intl_prefix(self):
        self.assertEqual(wb_embeddings.strip_realm_prefix("INTL:bge-m3"),
                         ("bge-m3", "intl"))

    def test_no_prefix(self):
        self.assertEqual(wb_embeddings.strip_realm_prefix("bge-m3"),
                         ("bge-m3", None))

    def test_unknown_prefix_kept_verbatim(self):
        self.assertEqual(wb_embeddings.strip_realm_prefix("text-embedding-3:small"),
                         ("text-embedding-3:small", None))

    def test_non_string(self):
        self.assertEqual(wb_embeddings.strip_realm_prefix(None), ("", None))


class ParseResponseTests(unittest.TestCase):
    def test_fills_object_and_index(self):
        out = wb_embeddings.parse_response(
            envelope([{"embedding": [0.1, 0.2]}, {"embedding": [0.3]}]), 2)
        self.assertEqual(out["object"], "list")
        self.assertEqual(out["data"][0],
                         {"object": "embedding", "index": 0, "embedding": [0.1, 0.2]})
        self.assertEqual(out["data"][1]["index"], 1)
        self.assertEqual(out["usage"], {"prompt_tokens": 7, "total_tokens": 7})

    def test_upstream_index_is_honoured_and_sorted(self):
        out = wb_embeddings.parse_response(
            envelope([{"embedding": [2], "index": 1},
                      {"embedding": [1], "index": 0}]), 2)
        self.assertEqual([entry["index"] for entry in out["data"]], [0, 1])
        self.assertEqual(out["data"][0]["embedding"], [1])

    def test_index_out_of_range(self):
        with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
            wb_embeddings.parse_response(
                envelope([{"embedding": [1], "index": 5}]), 1)
        self.assertEqual(ctx.exception.status, 502)

    def test_duplicate_index(self):
        with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
            wb_embeddings.parse_response(
                envelope([{"embedding": [1], "index": 0},
                          {"embedding": [2], "index": 0}]), 2)
        self.assertIn("重复", ctx.exception.message)

    def test_non_integer_index(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.parse_response(
                envelope([{"embedding": [1], "index": "0"}]), 1)

    def test_bool_index_rejected(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.parse_response(
                envelope([{"embedding": [1], "index": True}]), 1)

    def test_count_mismatch(self):
        with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
            wb_embeddings.parse_response(envelope([{"embedding": [1]}]), 2)
        self.assertEqual(ctx.exception.status, 502)
        self.assertIn("条数", ctx.exception.message)

    def test_missing_data(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.parse_response({"code": 0}, 1)

    def test_empty_vector_rejected(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.parse_response(envelope([{"embedding": []}]), 1)

    def test_bare_vector_list_accepted(self):
        out = wb_embeddings.parse_response(envelope([[0.5, 0.6]]), 1)
        self.assertEqual(out["data"][0]["embedding"], [0.5, 0.6])

    def test_model_not_found_code(self):
        with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
            wb_embeddings.parse_response(
                {"code": wb_embeddings.CODE_MODEL_NOT_FOUND, "msg": "no model"},
                1)
        self.assertEqual(ctx.exception.code, "model_not_found")
        self.assertEqual(ctx.exception.status, 404)
        self.assertIn("bge-m3", ctx.exception.message)

    def test_other_code_is_upstream_error(self):
        with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
            wb_embeddings.parse_response({"code": 500, "msg": "boom"}, 1)
        self.assertEqual(ctx.exception.code, "upstream_error")
        self.assertEqual(ctx.exception.status, 502)

    def test_non_object(self):
        with self.assertRaises(wb_embeddings.EmbeddingError):
            wb_embeddings.parse_response([1, 2], 1)

    def test_missing_code_treated_as_success(self):
        out = wb_embeddings.parse_response({"data": [{"embedding": [1]}]}, 1)
        self.assertEqual(out["data"][0]["index"], 0)

    def test_model_defaults_when_absent(self):
        out = wb_embeddings.parse_response({"data": [{"embedding": [1]}]}, 1)
        self.assertEqual(out["model"], wb_embeddings.EMBEDDING_MODEL_BGE)


class RequestTests(unittest.TestCase):
    def test_url_body_and_headers(self):
        account = FakeAccount()
        with PatchUrlopen(FakeResponse(envelope([{"embedding": [0.1]}]))) as patch:
            raw = wb_embeddings.request(account, "bge-m3", ["hello"])
        self.assertEqual(raw["code"], 0)
        req = patch.requests[0]
        self.assertEqual(req.full_url,
                         "https://upstream.test" + wb_embeddings.EMBEDDINGS_PATH)
        self.assertEqual(req.get_method(), "POST")
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body, {"model": "bge-m3", "input": ["hello"]})
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(account.header_calls[0]["purpose"], "chat")
        self.assertEqual(patch.kwargs[0]["proxy"], "")

    def test_proxy_forwarded(self):
        account = FakeAccount(proxy="http://127.0.0.1:7890")
        with PatchUrlopen(FakeResponse(envelope([{"embedding": [0.1]}]))) as patch:
            wb_embeddings.request(account, "bge-m3", ["x"])
        self.assertEqual(patch.kwargs[0]["proxy"], "http://127.0.0.1:7890")

    def test_rate_limited(self):
        error = urllib.error.HTTPError(
            "https://upstream.test/v2/embeddings", 429, "Too Many Requests", {}, None)
        with PatchUrlopen(error=error):
            with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
                wb_embeddings.request(FakeAccount(), "bge-m3", ["x"])
        self.assertEqual(ctx.exception.code, "upstream_busy")
        self.assertEqual(ctx.exception.status, 429)
        self.assertEqual(ctx.exception.retry_after, 60)

    def test_upstream_500(self):
        error = urllib.error.HTTPError(
            "https://upstream.test/v2/embeddings", 500, "Server Error", {},
            io.BytesIO(b'{"code":11351,"msg":"model not exist"}'))
        with PatchUrlopen(error=error):
            with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
                wb_embeddings.request(FakeAccount(), "nope", ["x"])
        self.assertEqual(ctx.exception.code, "model_not_found")
        self.assertEqual(ctx.exception.status, 404)

    def test_connection_failure(self):
        with PatchUrlopen(error=OSError("connection reset")):
            with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
                wb_embeddings.request(FakeAccount(), "bge-m3", ["x"])
        self.assertEqual(ctx.exception.code, "upstream_error")
        self.assertIn("connection reset", ctx.exception.message)

    def test_invalid_json(self):
        with PatchUrlopen(FakeResponse(b"<html>nope</html>")):
            with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
                wb_embeddings.request(FakeAccount(), "bge-m3", ["x"])
        self.assertIn("JSON", ctx.exception.message)

    def test_oversized_response(self):
        payload = b"{" + b" " * 32
        with PatchUrlopen(FakeResponse(payload, limit=wb_embeddings.MAX_RESPONSE_BYTES)):
            with self.assertRaises(wb_embeddings.EmbeddingError) as ctx:
                wb_embeddings.request(FakeAccount(), "bge-m3", ["x"])
        self.assertIn("字节", ctx.exception.message)

    def test_response_closed(self):
        response = FakeResponse(envelope([{"embedding": [0.1]}]))
        with PatchUrlopen(response):
            wb_embeddings.request(FakeAccount(), "bge-m3", ["x"])
        self.assertTrue(response.closed)

    def test_embed_end_to_end_shape(self):
        with PatchUrlopen(FakeResponse(envelope(
                [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]))):
            out = wb_embeddings.embed(FakeAccount(), "bge-m3", ["a", "b"])
        self.assertEqual(out["object"], "list")
        self.assertEqual(len(out["data"]), 2)
        self.assertEqual(out["data"][1]["index"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
