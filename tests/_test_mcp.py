"""wb_mcp protocol layer: envelopes, notifications, tool dispatch."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_mcp


TOOLS = [
    {"name": "ping_tool", "description": "trivial",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "boom_tool", "description": "always fails",
     "inputSchema": {"type": "object", "properties": {}}},
]


def list_tools():
    return TOOLS


def call_tool(name, arguments):
    if name == "ping_tool":
        return {"ok": True, "echo": arguments}
    if name == "boom_tool":
        raise wb_mcp.ToolError("工具坏了")
    raise wb_mcp.ToolError("没有这个工具：%s" % name)


def rpc(method, params=None, msg_id=1):
    payload = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        payload["params"] = params
    if msg_id is not _MISSING:
        payload["id"] = msg_id
    return payload


class _Missing(object):
    pass


_MISSING = _Missing()


class InitializeTests(unittest.TestCase):
    def test_echoes_known_version(self):
        for version in wb_mcp.PROTOCOL_VERSIONS:
            status, body = wb_mcp.dispatch(
                rpc("initialize", {"protocolVersion": version}), list_tools, call_tool)
            self.assertEqual(status, 200)
            self.assertEqual(body["result"]["protocolVersion"], version)

    def test_unknown_version_falls_back_to_newest(self):
        _, body = wb_mcp.dispatch(
            rpc("initialize", {"protocolVersion": "1999-01-01"}), list_tools, call_tool)
        self.assertEqual(body["result"]["protocolVersion"],
                         wb_mcp.PROTOCOL_VERSIONS[0])

    def test_missing_params_uses_newest(self):
        _, body = wb_mcp.dispatch(rpc("initialize"), list_tools, call_tool)
        self.assertEqual(body["result"]["protocolVersion"],
                         wb_mcp.PROTOCOL_VERSIONS[0])

    def test_server_info_and_capabilities(self):
        _, body = wb_mcp.dispatch(rpc("initialize", {}), list_tools, call_tool)
        result = body["result"]
        self.assertEqual(result["serverInfo"]["name"], wb_mcp.SERVER_NAME)
        self.assertEqual(result["capabilities"], {"tools": {"listChanged": False}})
        self.assertIn("instructions", result)

    def test_custom_version_and_instructions(self):
        _, body = wb_mcp.dispatch(
            rpc("initialize", {}), list_tools, call_tool,
            instructions="用法说明", version="2026.11.5")
        self.assertEqual(body["result"]["instructions"], "用法说明")
        self.assertEqual(body["result"]["serverInfo"]["version"], "2026.11.5")


class NotificationTests(unittest.TestCase):
    def test_missing_id_is_notification(self):
        status, body = wb_mcp.dispatch(
            rpc("notifications/initialized", msg_id=_MISSING), list_tools, call_tool)
        self.assertEqual(status, 202)
        self.assertIsNone(body)

    def test_null_id_is_notification(self):
        status, body = wb_mcp.dispatch(
            rpc("notifications/cancelled", {"requestId": 1}, msg_id=None),
            list_tools, call_tool)
        self.assertEqual(status, 202)
        self.assertIsNone(body)

    def test_unknown_notification_still_202(self):
        # Replying to a notification is forbidden even when the method is unknown.
        status, body = wb_mcp.dispatch(
            rpc("notifications/whatever", msg_id=_MISSING), list_tools, call_tool)
        self.assertEqual(status, 202)
        self.assertIsNone(body)


class ToolsTests(unittest.TestCase):
    def test_tools_list(self):
        status, body = wb_mcp.dispatch(rpc("tools/list"), list_tools, call_tool)
        self.assertEqual(status, 200)
        self.assertEqual([t["name"] for t in body["result"]["tools"]],
                         ["ping_tool", "boom_tool"])

    def test_tools_list_failure_is_rpc_error(self):
        def broken():
            raise RuntimeError("catalogue exploded")
        _, body = wb_mcp.dispatch(rpc("tools/list"), broken, call_tool)
        self.assertEqual(body["error"]["code"], wb_mcp.INTERNAL_ERROR)

    def test_call_success_shape(self):
        _, body = wb_mcp.dispatch(
            rpc("tools/call", {"name": "ping_tool", "arguments": {"a": 1}}),
            list_tools, call_tool)
        result = body["result"]
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"], {"ok": True, "echo": {"a": 1}})
        self.assertEqual(result["content"][0]["type"], "text")
        # The text block is pretty-printed JSON of the same payload.
        self.assertEqual(json.loads(result["content"][0]["text"]),
                         result["structuredContent"])

    def test_call_missing_arguments_defaults_to_empty(self):
        _, body = wb_mcp.dispatch(
            rpc("tools/call", {"name": "ping_tool"}), list_tools, call_tool)
        self.assertEqual(body["result"]["structuredContent"]["echo"], {})

    def test_tool_error_is_not_rpc_error(self):
        _, body = wb_mcp.dispatch(
            rpc("tools/call", {"name": "boom_tool", "arguments": {}}),
            list_tools, call_tool)
        self.assertNotIn("error", body)
        self.assertTrue(body["result"]["isError"])
        self.assertEqual(body["result"]["content"][0]["text"], "工具坏了")

    def test_unknown_tool_is_tool_error(self):
        _, body = wb_mcp.dispatch(
            rpc("tools/call", {"name": "nope", "arguments": {}}),
            list_tools, call_tool)
        self.assertTrue(body["result"]["isError"])

    def test_unexpected_exception_is_tool_error(self):
        def exploding(name, arguments):
            raise ValueError("kaboom")
        _, body = wb_mcp.dispatch(
            rpc("tools/call", {"name": "x", "arguments": {}}),
            list_tools, exploding)
        self.assertTrue(body["result"]["isError"])
        self.assertIn("kaboom", body["result"]["content"][0]["text"])

    def test_missing_name_is_invalid_params(self):
        _, body = wb_mcp.dispatch(
            rpc("tools/call", {"arguments": {}}), list_tools, call_tool)
        self.assertEqual(body["error"]["code"], wb_mcp.INVALID_PARAMS)

    def test_non_dict_arguments_is_invalid_params(self):
        _, body = wb_mcp.dispatch(
            rpc("tools/call", {"name": "ping_tool", "arguments": [1, 2]}),
            list_tools, call_tool)
        self.assertEqual(body["error"]["code"], wb_mcp.INVALID_PARAMS)

    def test_non_dict_params_is_invalid_params(self):
        _, body = wb_mcp.dispatch(
            rpc("tools/call", ["ping_tool"]), list_tools, call_tool)
        self.assertEqual(body["error"]["code"], wb_mcp.INVALID_PARAMS)


class EmptyCataloguesTests(unittest.TestCase):
    def test_resources_and_prompts_are_empty(self):
        for method, key in (("resources/list", "resources"),
                            ("resources/templates/list", "resourceTemplates"),
                            ("prompts/list", "prompts")):
            _, body = wb_mcp.dispatch(rpc(method), list_tools, call_tool)
            self.assertEqual(body["result"], {key: []}, method)


class EnvelopeTests(unittest.TestCase):
    def test_ping(self):
        _, body = wb_mcp.dispatch(rpc("ping"), list_tools, call_tool)
        self.assertEqual(body["result"], {})
        self.assertEqual(body["id"], 1)

    def test_unknown_method(self):
        _, body = wb_mcp.dispatch(rpc("nope/nope"), list_tools, call_tool)
        self.assertEqual(body["error"]["code"], wb_mcp.METHOD_NOT_FOUND)
        self.assertIn("Method not found", body["error"]["message"])

    def test_bad_jsonrpc_version(self):
        payload = {"jsonrpc": "1.0", "method": "ping", "id": 3}
        _, body = wb_mcp.dispatch(payload, list_tools, call_tool)
        self.assertEqual(body["error"]["code"], wb_mcp.INVALID_REQUEST)
        self.assertIn("2.0", body["error"]["message"])

    def test_non_object_payload(self):
        status, body = wb_mcp.dispatch([1, 2, 3], list_tools, call_tool)
        self.assertEqual(status, 200)
        self.assertEqual(body["error"]["code"], wb_mcp.INVALID_REQUEST)

    def test_missing_method(self):
        _, body = wb_mcp.dispatch({"jsonrpc": "2.0", "id": 4},
                                  list_tools, call_tool)
        self.assertEqual(body["error"]["code"], wb_mcp.INVALID_REQUEST)

    def test_id_is_echoed_verbatim(self):
        for msg_id in (7, "abc", 0):
            _, body = wb_mcp.dispatch(rpc("ping", msg_id=msg_id),
                                      list_tools, call_tool)
            self.assertEqual(body["id"], msg_id)

    def test_every_reply_is_json_serialisable(self):
        for payload in (rpc("ping"), rpc("initialize", {}), rpc("tools/list"),
                        rpc("tools/call", {"name": "ping_tool"}),
                        rpc("nope"), {"jsonrpc": "2.0", "id": 1}):
            _, body = wb_mcp.dispatch(payload, list_tools, call_tool)
            json.dumps(body, ensure_ascii=False)


class HelperTests(unittest.TestCase):
    def test_parse_error(self):
        body = wb_mcp.parse_error("unexpected token")
        self.assertEqual(body["error"]["code"], wb_mcp.PARSE_ERROR)
        self.assertIsNone(body["id"])
        self.assertIn("unexpected token", body["error"]["message"])

    def test_pretty_is_indented(self):
        self.assertIn("\n  ", wb_mcp.pretty({"a": 1}))

    def test_choose_protocol_version(self):
        self.assertEqual(wb_mcp.choose_protocol_version(wb_mcp.PROTOCOL_VERSIONS[1]),
                         wb_mcp.PROTOCOL_VERSIONS[1])
        self.assertEqual(wb_mcp.choose_protocol_version(""), wb_mcp.PROTOCOL_VERSIONS[0])
        self.assertEqual(wb_mcp.choose_protocol_version(None), wb_mcp.PROTOCOL_VERSIONS[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
