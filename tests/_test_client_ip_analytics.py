"""面板「来源 IP」：按客户端地址聚合整份 usage 日志。

回归背景：IP 上线后只能一条条翻「请求记录」看是谁发来的，看不出某个客户端
一共烧了多少、用的是哪些号；反过来问「这个号被哪些客户端用过」也没有入口。

这套件钉四件事：

  1. 同一 IP 的多行折进同一个桶，请求数 / token 累加，首末时间取极值。
  2. 没有 client_ip 的历史行落进「(未知)」——那是字段上线前的行，不是解析失败。
  3. error 行不计数（与按账号的折叠同款理由：错误行没有可计费用量）。
  4. 两个方向一起给：ips（谁在用）与 accounts（这个号被哪些客户端用过）；
     并且折算是增量的——追加一行后再算，只多算这一行，旧桶不动。

No network: usage 写进临时目录。
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TMP = tempfile.mkdtemp(prefix="wb-client-ip-agg-")
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


def append(rows):
    with open(P.USAGE_LOG, "a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def make_row(at, ip=None, total=100, model="m1", account="uid-a", error=None):
    row = {
        "at": at,
        "iso": "2026-11-07T00:00:00",
        "model": model,
        "stream": False,
        "outcome": "failed" if error else "completed",
        "kind": "chat",
        "total_tokens": total,
        "prompt_tokens": total // 2,
        "completion_tokens": total - total // 2,
        "account": account,
    }
    if ip:
        row["client_ip"] = ip
    if error:
        row["error"] = error
    return row


def by_ip(payload):
    return {item["ip"]: item for item in payload["ips"]}


def by_account(payload):
    return {item["account"]: item for item in payload["accounts"]}


append([
    make_row(1000, "1.1.1.1", 100),
    make_row(1010, "1.1.1.1", 200, model="m2"),
    make_row(1020, "1.1.1.1", 300, account="uid-b"),
    make_row(1030, "2.2.2.2", 50, account="uid-b"),
    make_row(1040, None, 70),
    make_row(1050, "1.1.1.1", 999, error="boom"),
])

payload = P.usage_by_client_ip(ttl=0)
ips = by_ip(payload)

check("三个桶：两个真实 IP + 一个 (未知)", set(ips) == {"1.1.1.1", "2.2.2.2", "(未知)"}, repr(sorted(ips)))
check("同一 IP 三行合并成一次请求计数 3",
      ips.get("1.1.1.1", {}).get("requests") == 3, repr(ips.get("1.1.1.1")))
check("token 累加 100+200+300=600",
      ips.get("1.1.1.1", {}).get("total_tokens") == 600, repr(ips.get("1.1.1.1")))
check("error 行不计数", "999" not in json.dumps(payload), "error 行的 token 进了聚合")
check("没有 client_ip 的行落进 (未知)",
      ips.get("(未知)", {}).get("requests") == 1, repr(ips.get("(未知)")))
check("首末时间取极值",
      (ips.get("1.1.1.1") or {}).get("first_at") == 1000
      and (ips.get("1.1.1.1") or {}).get("last_at") == 1020,
      repr(ips.get("1.1.1.1")))
check("models 按出现次数排好并截断",
      [m for m, _c in (ips.get("1.1.1.1") or {}).get("models", [])] == ["m1", "m2"],
      repr(ips.get("1.1.1.1", {}).get("models")))

accounts = by_account(payload)
check("账号方向：uid-b 两个客户端都用过",
      sorted(ip for ip, _c in (accounts.get("uid-b") or {}).get("ips", [])) == ["1.1.1.1", "2.2.2.2"],
      repr(accounts.get("uid-b")))
check("账号方向：uid-a 只见过来自 1.1.1.1 与 (未知) 的请求",
      sorted(ip for ip, _c in (accounts.get("uid-a") or {}).get("ips", [])) == ["(未知)", "1.1.1.1"],
      repr(accounts.get("uid-a")))
check("账号方向：uid-b 的请求数是 2（两个客户端各一行）",
      (accounts.get("uid-b") or {}).get("requests") == 2, repr(accounts.get("uid-b")))

# 增量：追加一行新 IP，旧桶不动、新桶出现。
append([make_row(1060, "3.3.3.3", 500, account="uid-c")])
payload2 = P.usage_by_client_ip(ttl=0)
ips2 = by_ip(payload2)
check("增量折叠：新 IP 出现", ips2.get("3.3.3.3", {}).get("requests") == 1, repr(sorted(ips2)))
check("增量折叠：旧桶仍是 3（没有被重复累加）",
      ips2.get("1.1.1.1", {}).get("requests") == 3, repr(ips2.get("1.1.1.1")))
check("增量折叠：旧桶 token 没被重复累加",
      ips2.get("1.1.1.1", {}).get("total_tokens") == 600, repr(ips2.get("1.1.1.1")))
check("排序：token 多的在前",
      payload2["ips"][0]["ip"] == "1.1.1.1", repr([i["ip"] for i in payload2["ips"]]))

# 缓存：TTL 内两次调用返回同一个对象（面板 5 秒一轮不该每次重建）。
cached_a = P.usage_by_client_ip(ttl=60)
cached_b = P.usage_by_client_ip(ttl=60)
check("TTL 内命中同一条缓存", cached_a is cached_b, "两次调用拿到了不同对象")
check("ETag 取得到（缓存条目存在）",
      isinstance(P.usage_by_client_ip_etag(), str), repr(P.usage_by_client_ip_etag()))

print("\n%d passed, %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
