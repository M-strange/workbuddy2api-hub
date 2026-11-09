"""来源 IP 归属地：面板「请求记录」与「来源 IP」上的省 / 市标签。

回归背景：网关记下了每个请求的客户端地址，但「203.0.113.7 是谁」还得自己去查。
这一层把地址解析成「江苏 苏州」，内网 / 本机在本地就能判定，公网地址交给
ip-api（失败退 pconline），结果按 7 天缓存、按 40 次 / 分钟限速，查询只在后台
线程里跑——面板读的是缓存，查不到就空着，绝不影响请求本身。

这套件钉五件事：

  1. 标签拼接：中国给「省 市」（去掉「市」后缀），国外给「国家 城市」。
  2. 本机 / 内网不发请求就有标签；占位符（未知）不是地址，不入队。
  3. 缓存语义：成功 7 天、失败退避 10 分钟、限速闸门、超限淘汰。
  4. 后台链路真的会写缓存（monkeypatch 掉网络），标注函数按开关工作。
  5. 聚合载荷 /usage/by-client-ip 的 ips 行带上 geo 字段。

No network: lookup 被替换成固定返回。
"""
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_TMP = tempfile.mkdtemp(prefix="wb-client-geo-")
os.environ["ACCOUNTS_DIR"] = os.path.join(_TMP, "accounts")
os.environ["WB_PROXY_USAGE_DIR"] = _TMP
os.makedirs(os.environ["ACCOUNTS_DIR"], exist_ok=True)

import wb_client_geo as G  # noqa: E402
import wb_proxy as P  # noqa: E402
import wb_settings  # noqa: E402

PASS = FAIL = 0


def check(label, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] %s" % label)
    else:
        FAIL += 1
        print("  [FAIL] %s  %s" % (label, extra))


class Resp(object):
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body


# ---- 1. 标签 ---------------------------------------------------------------
check("中国：省 + 市，去掉「市」后缀",
      G.label_of({"country": "中国", "region": "江苏省", "city": "苏州市"}) == "江苏 苏州",
      repr(G.label_of({"country": "中国", "region": "江苏省", "city": "苏州市"})))
check("中国：只有省", G.label_of({"country": "中国", "region": "北京市"}) == "北京",
      repr(G.label_of({"country": "中国", "region": "北京市"})))
check("中国：只有国家", G.label_of({"country": "中国"}) == "中国",
      repr(G.label_of({"country": "中国"})))
check("国外：国家 + 城市", G.label_of({"country": "美国", "city": "Los Angeles"}) == "美国 Los Angeles",
      repr(G.label_of({"country": "美国", "city": "Los Angeles"})))
check("空记录给空串", G.label_of({}) == "", repr(G.label_of({})))
check("非 dict 不炸", G.label_of("nope") == "", repr(G.label_of("nope")))

# ---- 2. 本地地址 -----------------------------------------------------------
check("回环是本机", G.local_label("127.0.0.1") == "本机", repr(G.local_label("127.0.0.1")))
check("IPv6 回环是本机", G.local_label("::1") == "本机", repr(G.local_label("::1")))
check("192.168 是内网", G.local_label("192.168.1.5") == "内网", repr(G.local_label("192.168.1.5")))
check("10.x 是内网", G.local_label("10.1.2.3") == "内网", repr(G.local_label("10.1.2.3")))
check("169.254 是内网", G.local_label("169.254.3.9") == "内网", repr(G.local_label("169.254.3.9")))
check("公网没有本地标签", G.local_label("8.8.8.8") == "", repr(G.local_label("8.8.8.8")))
check("占位符不是地址", G.is_address("(未知)") is False, repr(G.is_address("(未知)")))
check("IP 是地址", G.is_address("203.0.113.7") is True, repr(G.is_address("203.0.113.7")))

cache = G.GeoCache("")
now = 1000000.0
check("没查过的地址标签为空", cache.label("1.2.3.4", now) == "", repr(cache.label("1.2.3.4", now)))
check("没查过的地址要排队", cache.due(["1.2.3.4", "127.0.0.1", "(未知)", "1.2.3.4"], now) == ["1.2.3.4"],
      repr(cache.due(["1.2.3.4", "127.0.0.1", "(未知)", "1.2.3.4"], now)))

# ---- 3. 缓存语义 -----------------------------------------------------------
cache.put("1.2.3.4", {"label": "江苏 苏州", "country": "中国", "region": "江苏",
                      "city": "苏州", "isp": "CHINANET"}, now)
check("命中缓存", cache.label("1.2.3.4", now + 60) == "江苏 苏州", repr(cache.label("1.2.3.4", now + 60)))
check("命中后不再排队", cache.due(["1.2.3.4"], now + 60) == [], repr(cache.due(["1.2.3.4"], now + 60)))
check("7 天后过期", cache.label("1.2.3.4", now + G.TTL + 1) == "",
      repr(cache.label("1.2.3.4", now + G.TTL + 1)))
cache.put("5.6.7.8", {}, now)
check("失败记录不显示标签", cache.label("5.6.7.8", now + 5) == "", repr(cache.label("5.6.7.8", now + 5)))
check("失败记录 10 分钟内不重查", cache.due(["5.6.7.8"], now + 5) == [],
      repr(cache.due(["5.6.7.8"], now + 5)))
check("失败退避到期后重查", cache.due(["5.6.7.8"], now + G.FAIL_TTL + 1) == ["5.6.7.8"],
      repr(cache.due(["5.6.7.8"], now + G.FAIL_TTL + 1)))

rl = G.GeoCache("")
allowed = sum(1 for _ in range(G.RATE_LIMIT + 5) if rl.allow(now))
check("限速闸门按窗口计数", allowed == G.RATE_LIMIT, "allowed=%d" % allowed)
check("窗口过了放行", rl.allow(now + G.RATE_WINDOW + 1) is True, "窗口外仍被挡")

# ---- 4. 查询与回退 ---------------------------------------------------------
def good(request, timeout):
    if "ip-api" not in request.full_url:
        raise AssertionError("不该走到兜底: " + request.full_url)
    return Resp(json.dumps({"status": "success", "country": "中国",
                            "regionName": "江苏", "city": "苏州市",
                            "isp": "CHINANET"}).encode("utf-8"))

record = G.lookup("221.227.155.89", opener=good)
check("ip-api 命中给标签", record.get("label") == "江苏 苏州", repr(record))


def pconline_only(request, timeout):
    if "ip-api" in request.full_url:
        raise OSError("blocked")
    body = json.dumps({"pro": "江苏省", "city": "南通市",
                       "addr": "江苏省南通市 电信ADSL"}).encode("gbk")
    return Resp(body)

record = G.lookup("221.227.155.89", opener=pconline_only)
check("ip-api 挂了退到 pconline（GBK 解码）", record.get("label") == "江苏 南通", repr(record))


def broken(request, timeout):
    raise OSError("down")

check("两边都挂给空记录", G.lookup("221.227.155.89", opener=broken) == {},
      repr(G.lookup("221.227.155.89", opener=broken)))

# ---- 5. 开关 --------------------------------------------------------------
check("默认开启", wb_settings.client_geo_enabled(os.environ["ACCOUNTS_DIR"]) is True, "默认不是开")
wb_settings.set_client_geo_enabled(os.environ["ACCOUNTS_DIR"], False)
check("可以关掉", wb_settings.client_geo_enabled(os.environ["ACCOUNTS_DIR"]) is False, "关不掉")
P.reset_client_geo_state()
check("proxy 侧读到关闭", P.client_geo_enabled() is False, "proxy 仍读作开")
wb_settings.set_client_geo_enabled(os.environ["ACCOUNTS_DIR"], True)
P.reset_client_geo_state()
check("重新打开", P.client_geo_enabled() is True, "proxy 仍读作关")

# ---- 6. 标注函数与后台链路 --------------------------------------------------
rows = [{"client_ip": "192.168.1.9"}, {"client_ip": "203.0.113.9"},
        {"client_ip": ""}, {"client_ip": "(未知)"}, {}]
P.client_geo_annotate(rows)
check("内网行标成内网", rows[0]["client_ip_geo"] == "内网", repr(rows[0]))
check("未缓存公网行先空着", rows[1]["client_ip_geo"] == "", repr(rows[1]))
check("空地址不炸", rows[2]["client_ip_geo"] == "" and rows[4].get("client_ip_geo") == "",
      repr(rows[2]) + repr(rows[4]))

calls = []
real_lookup = G.lookup
G.lookup = lambda ip, **kw: calls.append(ip) or {
    "label": "上海 上海", "country": "中国", "region": "上海", "city": "上海", "isp": "x"}
try:
    P._geo_enqueue(["203.0.113.9", "(未知)", "127.0.0.1"])
    deadline = time.time() + 5.0
    while time.time() < deadline and not P.client_geo_cache().record("203.0.113.9"):
        time.sleep(0.02)
    check("后台线程真的查了并写缓存",
          P.client_geo_cache().label("203.0.113.9") == "上海 上海",
          repr(P.client_geo_cache().label("203.0.113.9")))
    check("占位符 / 回环不进查询", calls == ["203.0.113.9"], repr(calls))
    check("查过之后不再排队", P.client_geo_cache().due(["203.0.113.9"]) == [],
          repr(P.client_geo_cache().due(["203.0.113.9"])))
finally:
    G.lookup = real_lookup

# 关闭开关：公网行不再标注，内网照旧。
wb_settings.set_client_geo_enabled(os.environ["ACCOUNTS_DIR"], False)
P.reset_client_geo_state()
try:
    rows = [{"client_ip": "198.51.100.4"}, {"client_ip": "10.9.9.9"}]
    P.client_geo_annotate(rows)
    check("关闭后公网行不标注", rows[0]["client_ip_geo"] == "", repr(rows[0]))
    check("关闭后内网仍标注", rows[1]["client_ip_geo"] == "内网", repr(rows[1]))
finally:
    wb_settings.set_client_geo_enabled(os.environ["ACCOUNTS_DIR"], True)
    P.reset_client_geo_state()

# ---- 7. 聚合载荷带 geo ------------------------------------------------------
row = {"at": 1000, "iso": "2026-11-09T00:00:00", "model": "m1", "stream": False,
       "outcome": "completed", "kind": "chat", "total_tokens": 10,
       "prompt_tokens": 5, "completion_tokens": 5, "account": "uid-a",
       "client_ip": "203.0.113.9"}
with open(P.USAGE_LOG, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(row) + "\n")
payload = P.usage_by_client_ip(ttl=0)
ips = {item["ip"]: item for item in payload["ips"]}
check("ips 行带 geo 字段", "geo" in ips.get("203.0.113.9", {}), repr(ips.get("203.0.113.9")))
check("已查到的地址 geo 有值", ips.get("203.0.113.9", {}).get("geo") == "上海 上海",
      repr(ips.get("203.0.113.9", {})))

# recent_usage 的行同样带地区（同一份缓存）。
recent = P.recent_usage(10)
check("recent 行带 client_ip_geo",
      recent["rows"] and "client_ip_geo" in recent["rows"][0], repr(recent["rows"][:1]))
check("recent 行的地区取自缓存", recent["rows"][0].get("client_ip_geo") == "上海 上海",
      repr(recent["rows"][0].get("client_ip_geo")))

print("\n%d passed, %d failed" % (PASS, FAIL))
shutil.rmtree(_TMP, ignore_errors=True)
sys.exit(1 if FAIL else 0)
