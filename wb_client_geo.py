"""Where a client address comes from, for the panel's request log.

Only the panel needs this: the gateway never routes on geography, and a lookup
that fails is reported as unknown instead of raised. Failures are cached for
ten minutes so a blocked or rate-limited provider neither slows the request
path nor gets hammered once per poll.

ip-api.com answers in Chinese without a key (45 lookups/minute); pconline's
whois endpoint is the fallback for hosts where ip-api is unreachable. Private
and loopback addresses never leave the process.
"""

import ipaddress
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request

IPAPI = ("http://ip-api.com/json/%s?lang=zh-CN"
         "&fields=status,message,country,regionName,city,isp,query")
PCONLINE = "https://whois.pconline.com.cn/ipJson.jsp?ip=%s&json=true"

LOOKUP_TIMEOUT = 6
#: 一条成功的归属地能放多久（省 / 市几乎不搬家，一周足够）
TTL = 7 * 24 * 3600
#: 查询失败后退避多久：同一地址失败的 10 分钟内不再打外部接口
FAIL_TTL = 600
#: 缓存条数上限：面板公网暴露时扫描器会制造大量一次性地址
MAX_ENTRIES = 2000
#: 免费接口的频率限制（ip-api 45 次 / 分钟），留 5 次余量给手动刷新
RATE_LIMIT = 40
RATE_WINDOW = 60.0

FILE_NAME = "client-geo.json"

LOOPBACK_LABEL = "本机"
PRIVATE_LABEL = "内网"

_SUFFIX = re.compile(r"(省|市|自治区|特别行政区)$")


def _clean(name):
    """把「苏州市」收成「苏州」：面板列窄，省 / 市后缀只是噪声。"""
    text = str(name or "").strip()
    if not text:
        return ""
    return _SUFFIX.sub("", text) or text


def label_of(record):
    """一条查询结果对应的面板标签：「江苏 苏州」/「中国」/「美国 洛杉矶」。

    省市都没有时退回国家名；全空说明「不知道」，返回空串，由调用方决定显示什么。
    """
    if not isinstance(record, dict):
        return ""
    country = _clean(record.get("country"))
    region = _clean(record.get("region"))
    city = _clean(record.get("city"))
    if country == "中国":
        parts = [part for part in (region, city) if part]
        return " ".join(parts) or country
    parts = [part for part in (country, city or region) if part]
    return " ".join(parts)


def is_address(ip):
    """能不能当成一个 IP 去查：占位符（例如未知）不是地址，问了也是白发。"""
    try:
        ipaddress.ip_address(str(ip or "").strip())
    except ValueError:
        return False
    return True


#: 只把真正的内网段标成「内网」：ipaddress 的 is_private 还包含
#: 192.0.2.0/24、203.0.113.0/24 这类文档 / 测试网段，把它们叫内网会让面板说错话
#: （那些地址确实不会出现在真实流量里，但也不该被当成"你的局域网"）。
_PRIVATE_NETWORKS = tuple(ipaddress.ip_network(net) for net in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    "100.64.0.0/10",            # 运营商 NAT：对端看到的就是这个，不是公网地址
    "169.254.0.0/16",           # 链路本地
    "fc00::/7", "fe80::/10",    # IPv6 内网 / 链路本地
))


def _in_private_network(address):
    for network in _PRIVATE_NETWORKS:
        if address.version == network.version and address in network:
            return True
    return False


def is_private(ip):
    """回环 / 内网 / 链路本地：这类地址查外部接口没有意义。"""
    try:
        address = ipaddress.ip_address(str(ip or "").strip())
    except ValueError:
        return False
    return address.is_loopback or _in_private_network(address)


def local_label(ip):
    """不查接口也能给出的标签：本机回环 / 内网，其余返回空串。"""
    try:
        address = ipaddress.ip_address(str(ip or "").strip())
    except ValueError:
        return ""
    if address.is_loopback:
        return LOOPBACK_LABEL
    if _in_private_network(address):
        return PRIVATE_LABEL
    return ""


def _open(request, timeout):
    """Indirection so tests answer without a network."""
    return urllib.request.urlopen(request, timeout=timeout)


def _json(payload):
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return None


def _lookup_ipapi(ip, opener, timeout):
    url = IPAPI % urllib.parse.quote(str(ip), safe="")
    request = urllib.request.Request(url, headers={"User-Agent": "workbuddy2api-hub"})
    body = opener(request, timeout).read()
    payload = _json(body.decode("utf-8", "replace"))
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return None
    return {
        "country": str(payload.get("country") or "").strip(),
        "region": str(payload.get("regionName") or "").strip(),
        "city": str(payload.get("city") or "").strip(),
        "isp": str(payload.get("isp") or "").strip(),
    }


def _lookup_pconline(ip, opener, timeout):
    """pconline 的 whois 接口：GBK 编码，字段是 pro / city / addr。"""
    url = PCONLINE % urllib.parse.quote(str(ip), safe="")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = opener(request, timeout).read()
    text = raw.decode("gbk", "replace")
    start = text.find("{")
    if start < 0:
        return None
    payload = _json(text[start:])
    if not isinstance(payload, dict) or payload.get("err"):
        return None
    region = str(payload.get("pro") or "").strip()
    city = str(payload.get("city") or "").strip()
    if not (region or city):
        return None
    return {"country": "中国", "region": region, "city": city,
            "isp": str(payload.get("addr") or "").strip()}


def lookup(ip, opener=None, timeout=LOOKUP_TIMEOUT):
    """Ask the providers about one public address; empty dict when unknown.

    ip-api first (Chinese, no key), pconline as fallback. Both failures collapse
    into an empty dict: the caller caches that as a failure and moves on.
    """
    ip = str(ip or "").strip()
    if not ip:
        return {}
    opener = opener or _open
    for fetch in (_lookup_ipapi, _lookup_pconline):
        try:
            record = fetch(ip, opener, timeout)
        except Exception:
            record = None
        if record and (record.get("country") or record.get("region")
                       or record.get("city")):
            record = dict(record)
            record["label"] = label_of(record)
            return record
    return {}


class GeoCache:
    """IP → 归属地的内存缓存，落盘在 usage 目录，重启后复用。

    三类状态只用一条记录表达：ok 为真说明拿到了省市，为假是「查过但没结果」
    （退避 10 分钟），没有记录才是「还没查」。面板只读缓存，查询永远走后台线程。
    """

    def __init__(self, directory, ttl=TTL, fail_ttl=FAIL_TTL,
                 limit=MAX_ENTRIES, filename=FILE_NAME):
        self.directory = directory
        self.path = os.path.join(directory, filename) if directory else ""
        self.ttl = ttl
        self.fail_ttl = fail_ttl
        self.limit = limit
        self._lock = threading.Lock()
        self._entries = {}
        self._calls = []
        self._loaded = False

    # ---- persistence -----------------------------------------------------
    def _load_locked(self):
        if self._loaded:
            return
        self._loaded = True
        if not self.path or not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            entries = payload.get("entries") if isinstance(payload, dict) else None
            if isinstance(entries, dict):
                self._entries = {str(k): v for k, v in entries.items()
                                 if isinstance(v, dict)}
        except Exception:
            # 缓存文件坏了就当没有：归属地是装饰信息，不值得为它报错。
            self._entries = {}

    def _save_locked(self):
        if not self.path:
            return
        payload = {"version": 1, "entries": self._entries}
        tmp = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            os.replace(tmp, self.path)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    # ---- reads -----------------------------------------------------------
    def record(self, ip, now=None):
        """缓存里那条仍然有效的记录；没有 / 过期返回 None。"""
        ip = str(ip or "").strip()
        if not ip:
            return None
        now = time.time() if now is None else now
        with self._lock:
            self._load_locked()
            hit = self._entries.get(ip)
            if not isinstance(hit, dict):
                return None
            age = now - float(hit.get("at") or 0)
            if hit.get("ok"):
                if age <= self.ttl:
                    return dict(hit)
            elif age <= self.fail_ttl:
                return dict(hit)
            return None

    def label(self, ip, now=None):
        """面板直接显示的标签：本机 / 内网 / 「江苏 苏州」/ 空串。"""
        local = local_label(ip)
        if local:
            return local
        hit = self.record(ip, now)
        if not hit or not hit.get("ok"):
            return ""
        return str(hit.get("label") or "")

    def describe(self, ip, now=None):
        """面板要的完整视图：label 加上细化字段和是否已查到。"""
        local = local_label(ip)
        if local:
            return {"ip": ip, "label": local, "country": "", "region": "",
                    "city": "", "isp": "", "ok": True, "local": True, "at": 0}
        hit = self.record(ip, now) or {}
        ok = bool(hit.get("ok"))
        return {
            "ip": ip,
            "label": str(hit.get("label") or "") if ok else "",
            "country": str(hit.get("country") or ""),
            "region": str(hit.get("region") or ""),
            "city": str(hit.get("city") or ""),
            "isp": str(hit.get("isp") or ""),
            "ok": ok,
            "local": False,
            "at": float(hit.get("at") or 0),
        }

    def due(self, ips, now=None):
        """其中还没查过、或已过期、或失败退避到期的地址（保持输入顺序）。"""
        now = time.time() if now is None else now
        out = []
        for ip in ips:
            ip = str(ip or "").strip()
            if not is_address(ip) or local_label(ip):
                continue
            if self.record(ip, now) is None and ip not in out:
                out.append(ip)
        return out

    # ---- writes ----------------------------------------------------------
    def put(self, ip, record, now=None):
        ip = str(ip or "").strip()
        if not ip:
            return
        now = time.time() if now is None else now
        ok = bool(record)
        entry = {"at": now, "ok": ok}
        if ok:
            entry.update({
                "label": str(record.get("label") or ""),
                "country": str(record.get("country") or ""),
                "region": str(record.get("region") or ""),
                "city": str(record.get("city") or ""),
                "isp": str(record.get("isp") or ""),
            })
        with self._lock:
            self._load_locked()
            self._entries[ip] = entry
            if len(self._entries) > self.limit:
                # 超限就按时间淘汰最旧的一半，只留下最近活跃的地址。
                ordered = sorted(self._entries.items(),
                                 key=lambda kv: float((kv[1] or {}).get("at") or 0))
                drop = len(self._entries) - self.limit
                for key, _ in ordered[:max(drop, self.limit // 2)]:
                    self._entries.pop(key, None)
            self._save_locked()

    def allow(self, now=None):
        """限速闸门：窗口内超过 RATE_LIMIT 次就不发请求（返回 False）。"""
        now = time.time() if now is None else now
        with self._lock:
            keep = [at for at in self._calls if now - at < RATE_WINDOW]
            self._calls = keep
            if len(keep) >= RATE_LIMIT:
                return False
            keep.append(now)
            return True

    def stats(self):
        with self._lock:
            self._load_locked()
            total = len(self._entries)
            known = sum(1 for v in self._entries.values()
                        if isinstance(v, dict) and v.get("ok"))
        return {"entries": total, "known": known, "limit": self.limit}
