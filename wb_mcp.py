"""MCP (Model Context Protocol) JSON-RPC 2.0 endpoint, protocol layer only.

No I/O and no gateway knowledge lives here: the caller passes in the tool list
and a ``call_tool`` callable, and gets back ``(http_status, body_or_None)``. That
split is what makes the whole protocol surface testable without a socket, and it
keeps the tool implementations next to the REST handlers they reuse.

Shape of the subset, matching what the desktop MCP clients actually send:

  * stateless — replies are always ``application/json``; there is no SSE stream
    and no ``Mcp-Session-Id`` to keep. A client that needs those is out of scope;
  * a message without ``id`` (or with ``id: null``) is a **notification**: it is
    answered with 202 and no body, whether or not the method is known. That is
    what the spec asks for, and it stops a client's fire-and-forget
    ``notifications/initialized`` from turning into a visible error;
  * tool failures are ``isError: true`` inside a 200 reply, **not** JSON-RPC
    errors. Only a malformed request envelope is an RPC error — a client that
    gets -32602 knows its call never reached the gateway.
"""

import json

#: Protocol revisions this server speaks, newest first. The client's requested
#: revision is echoed back when it is in this list; otherwise the newest is
#: announced, which is the spec's documented fallback.
PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

SERVER_NAME = "workbuddy2api"

#: Request body ceiling. Tool arguments are text (a base64 image would be the
#: largest thing here, and edit_image takes URLs/data URLs); 4 MB is generous.
MAX_BODY_BYTES = 4 << 20

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class ToolError(Exception):
    """A tool ran but failed. Surfaces as ``isError: true``, not as an RPC error."""

    def __init__(self, message, code=None):
        Exception.__init__(self, message)
        self.message = message
        self.code = code


def _rpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": code, "message": message}}


def _rpc_result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def parse_error(detail=""):
    """The one reply the caller has to build before it can parse anything."""
    return _rpc_error(None, PARSE_ERROR, "Parse error" + (": " + detail if detail else ""))


def pretty(value):
    """Two-space JSON, matching the Go implementation's MarshalIndent."""
    return json.dumps(value, ensure_ascii=False, indent=2)


def choose_protocol_version(requested):
    if isinstance(requested, str) and requested in PROTOCOL_VERSIONS:
        return requested
    return PROTOCOL_VERSIONS[0]


def initialize_result(requested_version, instructions="", version="dev",
                      tools_changed=False):
    return {
        "protocolVersion": choose_protocol_version(requested_version),
        "capabilities": {"tools": {"listChanged": bool(tools_changed)}},
        "serverInfo": {"name": SERVER_NAME, "version": version},
        "instructions": instructions,
    }


def _tool_reply(payload):
    return {"content": [{"type": "text", "text": pretty(payload)}],
            "structuredContent": payload,
            "isError": False}


def _tool_failure(message):
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _call_tool(params, call_tool):
    if not isinstance(params, dict):
        return _rpc_error(None, INVALID_PARAMS, "params 必须是对象")
    name = params.get("name")
    if not isinstance(name, str) or not name.strip():
        return _rpc_error(None, INVALID_PARAMS, "tools/call 缺 name")
    arguments = params.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return _rpc_error(None, INVALID_PARAMS, "tools/call 的 arguments 必须是对象")
    try:
        return _tool_reply(call_tool(name.strip(), arguments))
    except ToolError as exc:
        return _tool_failure(exc.message)
    except Exception as exc:  # a broken tool must not kill the endpoint
        return _tool_failure("工具执行失败：%s" % exc)


def dispatch(payload, list_tools, call_tool, instructions="", version="dev"):
    """Handle one decoded JSON-RPC message.

    Returns ``(http_status, body)``; ``body`` is None for a notification, which
    the caller must answer with the returned 202 and no payload.
    """
    if not isinstance(payload, dict):
        return 200, _rpc_error(None, INVALID_REQUEST, "请求必须是 JSON 对象")
    msg_id = payload.get("id")
    is_notification = msg_id is None
    method = payload.get("method")
    if not isinstance(method, str) or not method:
        if is_notification:
            return 202, None
        return 200, _rpc_error(msg_id, INVALID_REQUEST, "缺 method")
    if is_notification:
        # Notifications are acknowledged and never answered, including the ones
        # this server does not implement: the spec forbids replying to them.
        return 202, None
    if payload.get("jsonrpc") != "2.0":
        return 200, _rpc_error(msg_id, INVALID_REQUEST, 'jsonrpc 必须是 "2.0"')
    if method == "initialize":
        params = payload.get("params")
        requested = params.get("protocolVersion") if isinstance(params, dict) else None
        return 200, _rpc_result(
            msg_id, initialize_result(requested, instructions, version))
    if method == "ping":
        return 200, _rpc_result(msg_id, {})
    if method == "tools/list":
        try:
            tools = list_tools()
        except Exception as exc:
            return 200, _rpc_error(msg_id, INTERNAL_ERROR, "列出工具失败：%s" % exc)
        return 200, _rpc_result(msg_id, {"tools": tools})
    if method == "tools/call":
        reply = _call_tool(payload.get("params"), call_tool)
        if "error" in reply:
            reply["id"] = msg_id
            return 200, reply
        return 200, _rpc_result(msg_id, reply)
    if method == "resources/list":
        return 200, _rpc_result(msg_id, {"resources": []})
    if method == "resources/templates/list":
        return 200, _rpc_result(msg_id, {"resourceTemplates": []})
    if method == "prompts/list":
        return 200, _rpc_result(msg_id, {"prompts": []})
    return 200, _rpc_error(msg_id, METHOD_NOT_FOUND, "Method not found: %s" % method)
