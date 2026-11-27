"""MCP / 去水印 / 嵌入三条新路由的接线测试。

`_test_mcp.py` 钉的是协议层（纯函数，不认识 HTTP），`_test_watermark.py` 与
`_test_embeddings.py` 钉的是各自的算法与上游交互。这一层补的是**它们与 Handler
之间的接缝**，那是最容易出问题的地方：

  - `_capture_call` 能不能真的把既有 REST 路径的响应截下来（MCP 复用 REST 的
    选号 / 计费逻辑，靠的就是它）
  - 开关关着回的是 403 而不是 404（"功能在，只是没开"）
  - 工具的业务失败变成 isError 而不是 JSON-RPC 错误
  - 去水印的 URL 入口只认产物域（不收口就是一个 SSRF 探针）
  - 嵌入命中 `model_not_found` 不换号（换号只会把同一个错误重放一遍）

Run with: python tests/_test_mcp_routes.py
"""
import base64
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.TemporaryDirectory(prefix="wb-mcp-routes-")
os.environ["ACCOUNTS_DIR"] = os.path.join(_TMP.name, "accounts")
os.environ["WB_PROXY_USAGE_DIR"] = os.path.join(_TMP.name, "usage")
os.environ["WB_MEDIA_DIR"] = os.path.join(_TMP.name, "media")
os.makedirs(os.environ["ACCOUNTS_DIR"], exist_ok=True)

import wb_embeddings
import wb_mcp
import wb_proxy as P
import wb_settings
import wb_watermark


# ---------------------------------------------------------------- 替身

class FakeHandler(P.Handler):
    """不初始化 socket 的 Handler 替身。

    `_json` / `_error` 保留 `_capture` 语义：真实实现里这两个方法在 `_capture`
    非 None 时**不写 socket**、只把 `(status, body)` 存起来。替身必须照做，
    否则 `_capture_call` 的测试会绕开被测代码。
    """

    def __init__(self, body=None):
        self.body = body if body is not None else {}
        self.key_entry = {"id": "k-1"}
        self.sent = None
        self.sent_kind = None
        self.empty = None
        self.path = "/mcp"
        self.close_connection = False

    # --- 出口
    def _json(self, code, obj):
        if self._capture is not None:
            self._capture = (code, obj)
            return obj
        self.sent_kind = "json"
        self.sent = (code, obj)
        return obj

    def _error(self, code, message, err_type="server_error", reset_at=None):
        if self._capture is not None:
            self._capture = (code, {"error": {"message": message, "type": err_type,
                                              "code": code}})
            return None
        self.sent_kind = "error"
        self.sent = (code, message, err_type)
        return None

    def _empty_response(self, code):
        self.empty = code

    # --- 入口
    def _read_payload(self, max_bytes=None, allow_list=False):
        return self.body

    def _drain_rejected_body(self, length=0, budget_seconds=2.0):
        pass

    def _authorized(self):
        return True

    def _key_id(self):
        return "k-1"

    def _key_realm(self):
        return ""


class FakeAccount(object):
    def __init__(self, uid):
        self.uid = uid
        self.errors = []
        self.successes = []

    def note_error(self, message, cooldown=60, single_account=False, model=None,
                   until=None, detail=None):
        self.errors.append(message)

    def note_success(self, model=None):
        self.successes.append(model)


class FakePool(object):
    def __init__(self, accounts):
        self.accounts = list(accounts)

    def pick(self, realm=None, exclude=None, model=None, page=None, allowed=None):
        exclude = exclude or set()
        for account in self.accounts:
            if account.uid in exclude:
                continue
            return account
        return None


def make_png(width=32, height=200, blank=120, blank_lum=255):
    """造一张「上面有内容、底部一条纯白留白」的 PNG。

    每一行都必须**横向也有变化**：留白检测看的是每行亮度的标准差，一整行同色
    的行会被判成留白。写成「每行一个颜色」的话整张图都是"纯色行"，检测器会
    正确地回 UniformError——那是 fixture 的错，不是被测代码的错。
    """
    rows = []
    for y in range(height):
        if y < height - blank:
            row = bytearray()
            for x in range(width):
                row += bytes(((x * 17 + y * 7) % 256, 40, 200))
            rows.append(bytes(row))
        else:
            rows.append(bytes([blank_lum, blank_lum, blank_lum] * width))
    return wb_watermark.encode_png(wb_watermark.Raster(width, height, b"".join(rows)))


def data_url(payload, mime="image/png"):
    return "data:%s;base64,%s" % (mime, base64.b64encode(payload).decode("ascii"))


# ---------------------------------------------------------------- 接线

class CaptureCallTests(unittest.TestCase):
    def setUp(self):
        self.handler = FakeHandler()

    def test_captures_json(self):
        def fake(path, payload):
            self.handler._json(200, {"ok": path})

        status, body = self.handler._capture_call(fake, "/v1/x", {})
        self.assertEqual((status, body), (200, {"ok": "/v1/x"}))
        # 截获的响应不能同时漏给真正的出口。
        self.assertIsNone(self.handler.sent)

    def test_captures_error(self):
        def fake():
            self.handler._error(429, "slow down", "rate_limit_error")

        status, body = self.handler._capture_call(fake)
        self.assertEqual(status, 429)
        self.assertEqual(body["error"]["message"], "slow down")

    def test_restores_capture_state(self):
        def fake():
            self.handler._json(200, {})

        self.handler._capture_call(fake)
        self.assertIsNone(self.handler._capture)

    def test_restores_capture_state_on_exception(self):
        def boom():
            raise RuntimeError("nope")

        with self.assertRaises(RuntimeError):
            self.handler._capture_call(boom)
        self.assertIsNone(self.handler._capture)

    def test_silent_handler_reports_502(self):
        status, body = self.handler._capture_call(lambda: None)
        self.assertEqual(status, 502)
        self.assertIn("没有产生响应", body["error"]["message"])


class McpEndpointTests(unittest.TestCase):
    def setUp(self):
        self.handler = FakeHandler()
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": False})

    def test_initialize_replies_protocol_version(self):
        self.handler.body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                             "params": {"protocolVersion": "2025-03-26"}}
        self.handler._handle_mcp()
        status, body = self.handler.sent
        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(body["result"]["serverInfo"]["name"], wb_mcp.SERVER_NAME)

    def test_notification_replies_202_without_body(self):
        self.handler.body = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self.handler._handle_mcp()
        self.assertEqual(self.handler.empty, 202)
        self.assertIsNone(self.handler.sent)

    def test_tools_list_hides_watermark_when_disabled(self):
        self.handler.body = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        self.handler._handle_mcp()
        names = [tool["name"] for tool in self.handler.sent[1]["result"]["tools"]]
        self.assertNotIn("strip_watermark", names)
        self.assertIn("generate_image", names)

    def test_tools_list_shows_watermark_when_enabled(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        self.handler.body = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        self.handler._handle_mcp()
        names = [tool["name"] for tool in self.handler.sent[1]["result"]["tools"]]
        self.assertIn("strip_watermark", names)

    def test_unknown_method_is_rpc_error(self):
        self.handler.body = {"jsonrpc": "2.0", "id": 3, "method": "nope"}
        self.handler._handle_mcp()
        status, body = self.handler.sent
        self.assertEqual(status, 200)
        self.assertEqual(body["error"]["code"], wb_mcp.METHOD_NOT_FOUND)

    def test_tool_failure_becomes_iserror(self):
        def fake_image(arguments):
            return 402, {"error": {"message": "no credit",
                                   "type": "insufficient_quota", "code": 402}}

        handler = self.handler
        handler._mcp_generate_image = fake_image
        handler.body = {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "generate_image",
                                   "arguments": {"prompt": "a cat"}}}
        handler._handle_mcp()
        result = handler.sent[1]["result"]
        self.assertTrue(result["isError"])
        self.assertIn("HTTP 402", result["content"][0]["text"])

    def test_tool_success_wraps_structured_content(self):
        def fake_image(arguments):
            return 200, {"created": 1, "data": [{"url": "https://x/y.png"}]}

        handler = self.handler
        handler._mcp_generate_image = fake_image
        handler.body = {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                        "params": {"name": "generate_image",
                                   "arguments": {"prompt": "a cat"}}}
        handler._handle_mcp()
        result = handler.sent[1]["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["data"][0]["url"], "https://x/y.png")
        self.assertEqual(json.loads(result["content"][0]["text"]),
                         result["structuredContent"])


class McpHelperTests(unittest.TestCase):
    def test_error_text_carries_status_and_message(self):
        text = P._mcp_error_text(429, {"error": {"message": "slow", "code": 429,
                                                 "retry_after": 12}})
        self.assertTrue(text.startswith("HTTP 429"))
        self.assertIn("slow", text)
        self.assertIn("retry_after", text)

    def test_error_text_falls_back_to_body(self):
        text = P._mcp_error_text(500, {"unexpected": True})
        self.assertIn("unexpected", text)

    def test_error_text_handles_none(self):
        self.assertEqual(P._mcp_error_text(502, None), "HTTP 502")

    def test_task_id_prefers_task_id(self):
        self.assertEqual(P._mcp_task_id({"task_id": "a", "id": "b"}), "a")
        self.assertEqual(P._mcp_task_id({"id": "b"}), "b")
        self.assertEqual(P._mcp_task_id({"task": {"id": "c"}}), "c")

    def test_task_id_rejects_non_string(self):
        self.assertEqual(P._mcp_task_id({"task_id": 7}), "")
        self.assertEqual(P._mcp_task_id({"task_id": "  "}), "")
        self.assertEqual(P._mcp_task_id("nope"), "")


class WatermarkRouteTests(unittest.TestCase):
    def setUp(self):
        self.handler = FakeHandler()
        self.handler.path = "/v1/images/strip-watermark"

    def test_disabled_returns_403_not_404(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": False})
        self.handler._handle_watermark_post({"image": data_url(make_png())})
        self.assertEqual(self.handler.sent[0], 403)

    def test_data_url_roundtrip(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        png = make_png()
        self.handler._handle_watermark_post({"image": data_url(png)})
        status, body = self.handler.sent
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "image.strip")
        self.assertEqual(body["width"], 32)
        self.assertEqual(body["blank_px"], 120)
        self.assertTrue(body["safe"])
        self.assertLess(body["out_height"], body["height"])
        self.assertTrue(body["data_url"].startswith("data:image/png;base64,"))

    def test_meta_only_omits_bytes(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        self.handler._handle_watermark_post({"image": data_url(make_png()),
                                             "return": "meta"})
        status, body = self.handler.sent
        self.assertEqual(status, 200)
        self.assertNotIn("data_url", body)
        self.assertEqual(body["usage"]["credit"], 0)

    def test_no_blank_returns_422_with_numbers(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        self.handler._handle_watermark_post({"image": data_url(make_png(blank=10))})
        status, body = self.handler.sent
        self.assertEqual(status, 422)
        self.assertEqual(body["error"]["code"], "no_blank_strip")
        self.assertIn("留白", body["error"]["message"])

    def test_foreign_host_is_refused(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        self.handler._handle_watermark_post(
            {"image": "http://169.254.169.254/latest/meta-data/"})
        status, body = self.handler.sent
        self.assertEqual(status, 400)
        self.assertIn("产物域", body["error"]["message"])

    def test_product_host_is_allowed(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        png = make_png()
        fetched = []

        def fake_fetch(url):
            fetched.append(url)
            return png

        self.handler._watermark_fetch = fake_fetch
        self.handler._handle_watermark_post(
            {"image": "https://bucket.cos.ap-guangzhou.myqcloud.com/a.png"})
        self.assertEqual(len(fetched), 1)
        self.assertEqual(self.handler.sent[0], 200)

    def test_bad_base64_is_400(self):
        wb_settings.set_watermark_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        self.handler._handle_watermark_post({"image": "not base64 at all!!"})
        self.assertEqual(self.handler.sent[0], 400)


class EmbeddingsRouteTests(unittest.TestCase):
    def setUp(self):
        self.handler = FakeHandler()
        self.handler.path = "/v1/embeddings"
        wb_settings.set_embeddings_config(os.environ["ACCOUNTS_DIR"], {"enabled": True})
        self.account = FakeAccount("acc-1")
        self._saved_pool = P.POOL
        P.POOL = FakePool([self.account])

    def tearDown(self):
        P.POOL = self._saved_pool
        wb_settings.set_embeddings_config(os.environ["ACCOUNTS_DIR"], {"enabled": False})

    def test_disabled_returns_403(self):
        wb_settings.set_embeddings_config(os.environ["ACCOUNTS_DIR"], {"enabled": False})
        self.handler._handle_embeddings_post({"input": "hello"})
        self.assertEqual(self.handler.sent[0], 403)

    def test_success_fills_openai_shape(self):
        raw = {"code": 0, "model": "bge-m3",
               "data": [{"embedding": [0.1, 0.2]}],
               "usage": {"prompt_tokens": 3, "total_tokens": 3}}
        with mock.patch.object(wb_embeddings, "request", return_value=raw):
            self.handler._handle_embeddings_post({"input": "hello"})
        status, body = self.handler.sent
        self.assertEqual(status, 200)
        self.assertEqual(body["object"], "list")
        self.assertEqual(body["data"][0]["object"], "embedding")
        self.assertEqual(body["data"][0]["index"], 0)
        self.assertEqual(self.account.successes, ["bge-m3"])

    def test_model_not_found_does_not_rotate(self):
        calls = []

        def boom(account, model, inputs, timeout=None):
            calls.append(account.uid)
            raise wb_embeddings.EmbeddingError(
                "model_not_found", "no such model: bge-m3", 404)

        with mock.patch.object(wb_embeddings, "request", side_effect=boom):
            self.handler._handle_embeddings_post({"input": "hello", "model": "nope"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.handler.sent[0], 404)

    def test_retryable_error_rotates_accounts(self):
        second = FakeAccount("acc-2")
        P.POOL = FakePool([self.account, second])
        calls = []

        def flaky(account, model, inputs, timeout=None):
            calls.append(account.uid)
            if account.uid == "acc-1":
                raise wb_embeddings.EmbeddingError("upstream_error", "boom", 502)
            return {"code": 0, "data": [{"embedding": [1.0]}],
                    "usage": {"prompt_tokens": 1, "total_tokens": 1}}

        with mock.patch.object(wb_embeddings, "request", side_effect=flaky):
            self.handler._handle_embeddings_post({"input": "hello"})
        self.assertEqual(calls, ["acc-1", "acc-2"])
        self.assertEqual(self.handler.sent[0], 200)

    def test_too_many_inputs_is_400(self):
        wb_settings.set_embeddings_config(os.environ["ACCOUNTS_DIR"],
                                          {"enabled": True, "max_inputs": 2})
        self.handler._handle_embeddings_post({"input": ["a", "b", "c"]})
        self.assertEqual(self.handler.sent[0], 400)

    def test_empty_input_is_400(self):
        self.handler._handle_embeddings_post({"input": []})
        self.assertEqual(self.handler.sent[0], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
