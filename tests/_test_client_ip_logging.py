"""每条请求都要能回答"这是谁发来的"：access 日志、对话日志、usage 行都要带 IP。

回归背景：网关放在反代后面，access 日志只有 `"POST /v1/chat/completions" 200 -`，
出问题时要按时间戳去 nginx 日志里反查来源；usage 行更没有来源字段，统计页只能
看到"有人烧了一堆 token"，看不出是不是同一个客户端在刷。

这套件钉三件事：

  1. 来源 IP 的判定（client_ip_of）与限流键同一套规则：对端可信才读
     X-Real-IP / X-Forwarded-For，否则用 socket 对端地址；永远不返回空串。
  2. access 日志与 chat/媒体完成行都以 IP 打头或带 ip= 标签。
  3. usage 行写入 client_ip，但**只在调用方拿得到时写**——不传的调用点保持
     与旧行完全一致，历史数据不需要迁移。

No network: usage 写进临时目录。
"""
import json
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TMP = tempfile.mkdtemp(prefix="wb-client-ip-")
os.environ["ACCOUNTS_DIR"] = os.path.join(_TMP, "accounts")
os.environ["WB_PROXY_USAGE_DIR"] = _TMP
os.makedirs(os.environ["ACCOUNTS_DIR"], exist_ok=True)

import wb_proxy as P  # noqa: E402  (its own data root)

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % label)
    else:
        FAIL += 1
        print("  [FAIL] %s  %s" % (label, extra))


def last_row():
    with open(P.USAGE_LOG, encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return rows[-1]


class _FakeHandler(object):
    """只装 log_message 需要的几个属性，不碰 socket。"""

    def __init__(self, ip, command="GET", path="/v1/models"):
        self.client_ip = ip
        self.command = command
        self.path = path

    log_message = P.Handler.log_message


def main():
    print("client ip is carried by logs and usage rows")

    # ---- 1. 判定规则与限流键一致 ----
    with mock.patch.object(P, "TRUSTED_PROXIES", ()):
        check("untrusted peer keeps socket address",
              P.client_ip_of("192.168.1.50", {"X-Real-IP": "203.0.113.7"}) == "192.168.1.50")
        check("trusted loopback reads X-Real-IP",
              P.client_ip_of("127.0.0.1", {"X-Real-IP": "203.0.113.7"}) == "203.0.113.7")
        check("forwarded-for first hop",
              P.client_ip_of("127.0.0.1", {"X-Forwarded-For": "198.51.100.9, 10.0.0.1"})
              == "198.51.100.9")
        check("empty peer never yields empty string",
              P.client_ip_of("", {}) == "-")

    # ---- 2. access 日志以 IP 打头 ----
    with mock.patch.object(P, "log") as logged:
        _FakeHandler("203.0.113.7").log_message('"%s" %s %s', "GET /v1/models HTTP/1.1", 200, "-")
    line = logged.call_args[0][0]
    check("access log starts with ip", line.startswith("203.0.113.7 "), line)
    check("access log keeps request text", "GET /v1/models" in line, line)

    # 没有 IP 的处理器（测试桩、异常路径）退回 "-"，不能炸
    with mock.patch.object(P, "log") as logged:
        handler = _FakeHandler("x")
        del handler.client_ip
        handler.log_message('"%s" %s %s', "GET /x HTTP/1.1", 500, "-")
    check("missing ip renders dash", logged.call_args[0][0].startswith("- "),
          logged.call_args[0][0])

    # ---- 3. usage 行带 client_ip ----
    P.record_usage("gpt-4o", {"prompt_tokens": 5, "completion_tokens": 2,
                              "total_tokens": 7}, stream=False, kind="chat",
                   client_ip="203.0.113.7")
    row = last_row()
    check("row carries client_ip", row.get("client_ip") == "203.0.113.7", row.get("client_ip"))

    # 不传就不写：旧调用点与历史行的形状保持不变
    P.record_usage("gpt-4o", {"prompt_tokens": 5, "completion_tokens": 2,
                              "total_tokens": 7}, stream=False, kind="chat")
    row = last_row()
    check("row omits field when unknown", "client_ip" not in row,
          {k: v for k, v in row.items() if k == "client_ip"})

    # ---- 4. 完成日志带 ip= ----
    with mock.patch.object(P, "log") as logged:
        P.record_usage("gpt-4o", {"prompt_tokens": 5, "completion_tokens": 2,
                                  "total_tokens": 7}, stream=False, kind="chat",
                       client_ip="203.0.113.7")
    done = [c[0][0] for c in logged.call_args_list if c[0] and isinstance(c[0][0], str)]
    chat_done = [m for m in done if m.startswith("chat done:")]
    check("chat done log has ip tag",
          bool(chat_done) and " ip=203.0.113.7" in chat_done[0], chat_done[:1])

    print("SUMMARY: PASS=%d FAIL=%d" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
