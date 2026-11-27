"""图片底部留白裁切（去水印后处理）—— 纯标准库实现。

上游生图会在画面底部留一条带平台水印的纯白留白。这个模块只做一件事：找出那条
留白的边界、裁掉它、按原格式重新编码。全程本地，不消耗任何上游积分。

依赖口径：本仓库是「纯 Python 标准库 + 兼容 3.9」（见 CONTRIBUTING.md）。所以解码
与编码全部走内置实现，只认 PNG；其它格式明确回 415 并告诉调用方怎么办，不做
「假装裁了」的静默降级。刻意不挂 Pillow：CI 上没有它，那条路径永远测不到，而一段
只在开发者机器上跑得通的代码比没有这段代码更危险。

算法移植自 misakano7545/workbuddy2api-panel 的 internal/media/strip.go（MIT 许可），
判定口径保持一致（阈值、扫描方向、安全条件），解码 / 编码与 HTTP 层是本仓库自己写的：

  1. 先只读图头拿尺寸，超过 MAX_PIXELS 直接拒——解码之后再拦，内存已经花掉了；
  2. 逐行算亮度（BT.601 定点：77R + 150G + 29B >> 8）与标准差；
  3. **从最后一行往上扫**，找第一个 std >= ROW_STD_THRESHOLD 的行，它的下一行就是
     留白边界 boundary。只扫底部留白那几十到几百行，不扫整图——这是这个端点在
     纯 Python 里跑得动的原因（整图逐像素扫一遍要十几秒）；
  4. blank = height - boundary；safe = blank >= min_blank 且留白平均亮度 >= white_lum；
  5. 不安全就抛 NoBlankError（把实测数字带回去，调用方才知道差多少），安全就裁到
     boundary + keep_blank。
"""

import binascii
import math
import struct
import zlib

#: 底部至少要留这么多像素才算「有可裁的留白」。与 Go 版 DefaultMinBlank 同值：
#: 太小的留白多半是画面本身的白边，裁掉就是裁内容。
DEFAULT_MIN_BLANK = 90

#: 留白的平均亮度门槛（0-255）。低于它就是灰底或带纹理的底，不是水印留白。
DEFAULT_WHITE_LUM = 248.0

#: 重新编码 JPEG 时的质量。裁切不动像素，只丢行，92 基本看不出二次压缩。
DEFAULT_JPEG_QUALITY = 92

#: 像素总数上限。比 Go 版的 100M 收得更紧：那边是编译执行，这边是纯 Python 逐
#: 像素循环，20M（约 4500x4500）已经够覆盖生图的 4M 上限，再大只是给自己找超时。
MAX_PIXELS = 20_000_000

#: 输入字节上限，与 Go 版 watermarkMaxBytes 同值。
MAX_BYTES = 32 << 20

#: keep_blank 的上限：多留一点边是合理的，留几千像素就是把裁切变成了空操作。
MAX_KEEP_BLANK = 4096

#: 一行算「有内容」的标准差门槛。纯白留白逐行几乎零方差，画面边缘、渐变、噪点
#: 都会立刻超过它。与 Go 版 rowStdThreshold 同值。
ROW_STD_THRESHOLD = 2.0

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class StripError(Exception):
    """裁切失败。code 是机器可读分类，status 是建议的 HTTP 状态。

    result 在「图能解、只是不能裁」的分支上带着实测数字（原图尺寸、实际留白、
    实际亮度），调用方据此才知道差多少——只回一句「没有留白」没法调。
    """

    def __init__(self, code, message, status=400):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        self.status = status
        self.result = None


class NotImageError(StripError):
    def __init__(self, message, status=400):
        StripError.__init__(self, "invalid_image", message, status)


class TooLargeError(StripError):
    def __init__(self, message):
        StripError.__init__(self, "too_large", message, 413)


class UniformError(StripError):
    def __init__(self, result):
        StripError.__init__(
            self, "invalid_image",
            "整张图是纯色，找不到内容边界", 400)
        self.result = result


class NoBlankError(StripError):
    def __init__(self, result):
        StripError.__init__(
            self, "no_blank_strip",
            "底部没有可裁的纯白留白：原图 %dx%d，底部留白 %dpx（占 %.1f%%），"
            "留白平均亮度 %.1f（需要 >= %.0f）。先让 edit_image 把画面下方约 1/3 "
            "涂成纯白，再来裁。"
            % (result["width"], result["height"], result["blank_px"],
               result["blank_ratio"] * 100.0, result["blank_lum"],
               result["white_lum"]),
            422)
        self.result = result


class Raster(object):
    """解码后的图：一律 8-bit RGB，每像素 3 字节，行优先、无行内 padding。

    统一成 RGB 是有意的：生图产物不会是 16-bit、也不靠 alpha 表达内容，多带一条
    通道只会让逐像素循环慢一截。灰度在解码时复制成三份，调色板展开成 RGB。
    """

    __slots__ = ("width", "height", "data")

    def __init__(self, width, height, data):
        self.width = width
        self.height = height
        self.data = data

    @property
    def stride(self):
        return self.width * 3

    def row(self, y):
        base = y * self.stride
        return self.data[base:base + self.stride]


# ---------------------------------------------------------------- PNG 解码

def _png_chunks(data):
    """逐个吐出 (类型, 数据) 的 chunk。到 IEND 或数据用尽为止。"""
    pos = len(PNG_SIGNATURE)
    total = len(data)
    while pos + 8 <= total:
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        start = pos + 8
        end = start + length
        if end > total:
            raise NotImageError("PNG 数据在 %r chunk 处被截断" % ctype)
        yield ctype, data[start:end]
        pos = end + 4  # 跳过 CRC
        if ctype == b"IEND":
            return


def _unfilter(raw, width, height, channels):
    """还原 PNG 的行过滤。5 种过滤器按规范逐个逆运算。

    filter 1/3/4 必须逐字节串行（Paeth 依赖左边那个已经还原过的字节），没有向量
    化的余地；filter 0/2 本可以整行批量算，但为了少两条分支还是走同一条循环——
    真正的加速靠「只扫底部留白」，不靠这里。
    """
    stride = width * channels
    need = (stride + 1) * height
    if len(raw) < need:
        raise NotImageError("PNG 像素数据不完整（要 %d 字节，只有 %d）"
                            % (need, len(raw)))
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                if i >= channels:
                    a = line[i - channels]
                    c = prev[i - channels]
                else:
                    a = 0
                    c = 0
                b = prev[i]
                p = a + b - c
                pa = p - a
                pb = p - b
                pc = p - c
                if pa < 0:
                    pa = -pa
                if pb < 0:
                    pb = -pb
                if pc < 0:
                    pc = -pc
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                line[i] = (line[i] + pr) & 0xFF
        else:
            raise NotImageError("PNG 行过滤类型非法：%d" % ftype)
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def _to_rgb(pixels, width, height, color_type, palette):
    """把任意支持的 PNG 像素布局归一成 8-bit RGB。"""
    count = width * height
    stride = width * 3
    out = bytearray(stride * height)
    if color_type == 2:
        # 已经是 RGB，原样搬。
        out[:] = pixels[:stride * height]
        return out
    if color_type == 0:
        for y in range(height):
            src = y * width
            dst = y * stride
            for x in range(width):
                v = pixels[src + x]
                o = dst + x * 3
                out[o] = v
                out[o + 1] = v
                out[o + 2] = v
        return out
    if color_type == 4:
        for y in range(height):
            src = y * width * 2
            dst = y * stride
            for x in range(width):
                v = pixels[src + x * 2]
                o = dst + x * 3
                out[o] = v
                out[o + 1] = v
                out[o + 2] = v
        return out
    if color_type == 6:
        for y in range(height):
            src = y * width * 4
            dst = y * stride
            for x in range(width):
                o = dst + x * 3
                i = src + x * 4
                out[o] = pixels[i]
                out[o + 1] = pixels[i + 1]
                out[o + 2] = pixels[i + 2]
        return out
    if color_type == 3:
        if not palette:
            raise NotImageError("调色板 PNG 缺 PLTE")
        entries = len(palette) // 3
        for y in range(height):
            src = y * width
            dst = y * stride
            for x in range(width):
                idx = pixels[src + x]
                if idx >= entries:
                    raise NotImageError("PNG 调色板索引越界：%d" % idx)
                o = dst + x * 3
                p = idx * 3
                out[o] = palette[p]
                out[o + 1] = palette[p + 1]
                out[o + 2] = palette[p + 2]
        return out
    raise NotImageError("不支持的 PNG 颜色类型：%d" % color_type)


def decode_png(data):
    """解码 8-bit 非隔行 PNG。其余变体明确报错，不猜。"""
    if not data.startswith(PNG_SIGNATURE):
        raise NotImageError("不是 PNG：签名不对")
    header = None
    idat = []
    palette = None
    for ctype, body in _png_chunks(data):
        if ctype == b"IHDR":
            header = body
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype == b"PLTE":
            palette = body
        elif ctype == b"IEND":
            break
    if header is None or len(header) < 13:
        raise NotImageError("PNG 缺 IHDR")
    width, height, depth, color_type, _comp, _filt, interlace = struct.unpack(
        ">IIBBBBB", header[:13])
    if width <= 0 or height <= 0:
        raise NotImageError("PNG 尺寸非法：%dx%d" % (width, height))
    if width * height > MAX_PIXELS:
        raise TooLargeError(
            "图太大：%dx%d = %d 像素，上限 %d"
            % (width, height, width * height, MAX_PIXELS))
    if interlace:
        raise NotImageError("不支持隔行（Adam7）PNG")
    if depth != 8:
        raise NotImageError("只支持 8-bit PNG，本图是 %d-bit" % depth)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None:
        raise NotImageError("不支持的 PNG 颜色类型：%d" % color_type)
    if not idat:
        raise NotImageError("PNG 缺 IDAT")
    try:
        raw = zlib.decompress(b"".join(idat))
    except zlib.error as exc:
        raise NotImageError("PNG 像素数据解压失败：%s" % exc)
    pixels = _unfilter(raw, width, height, channels)
    return Raster(width, height, _to_rgb(pixels, width, height, color_type, palette))


# ---------------------------------------------------------------- PNG 编码

def _png_chunk(ctype, body):
    return (struct.pack(">I", len(body)) + ctype + body
            + struct.pack(">I", binascii.crc32(ctype + body) & 0xFFFFFFFF))


def encode_png(raster):
    """按 filter 0（None）逐行打包。裁切后的图没有可压缩的规律，滤波换不来体积。"""
    stride = raster.stride
    raw = bytearray((stride + 1) * raster.height)
    pos = 0
    data = raster.data
    for y in range(raster.height):
        raw[pos] = 0
        pos += 1
        raw[pos:pos + stride] = data[y * stride:(y + 1) * stride]
        pos += stride
    body = zlib.compress(bytes(raw), 6)
    out = bytearray(PNG_SIGNATURE)
    out += _png_chunk(b"IHDR", struct.pack(
        ">IIBBBBB", raster.width, raster.height, 8, 2, 0, 0, 0))
    out += _png_chunk(b"IDAT", body)
    out += _png_chunk(b"IEND", b"")
    return bytes(out)


# ---------------------------------------------------------------- 边界检测

def decode_any(data):
    """解出 Raster 与原格式名。

    只认 PNG。这不是懒：JPEG 解码要写 Huffman + 反量化 + IDCT，几百行纯 Python
    在纯 Python 里跑一张 4K 图要几十秒，而它要解决的问题（裁掉底部白边）用一次
    「让上游输出 PNG」就绕开了。与其偷偷降级，不如把话说清楚。
    """
    if not data:
        raise NotImageError("图片数据是空的")
    if len(data) > MAX_BYTES:
        raise TooLargeError("图片超过 %d 字节上限" % MAX_BYTES)
    if data[:8] == PNG_SIGNATURE:
        return decode_png(data), "png"
    raise NotImageError(
        "只处理 PNG：请让上游输出 PNG（生图默认就是 PNG），"
        "或先把图片转成 PNG 再传", status=415)


def choose_format(requested, source):
    """定输出格式：不指定就跟随输入，其它一律 PNG。"""
    value = (requested or "").strip().lower()
    if not value:
        return "jpeg" if source == "jpeg" else "png"
    if value == "jpg":
        value = "jpeg"
    if value in ("png", "jpeg"):
        return value
    raise StripError(
        "invalid_request", "format 只能是 png 或 jpeg（给定 %r）" % requested, 400)


def encode_any(raster, fmt, quality):
    """编码，返回 (字节, 实际格式)。

    编不出 JPEG：这时退回 PNG，并让返回的格式字段说实话——调用方看 format 就知道
    拿到了什么，不存在「以为存了 jpg」的静默降级。
    """
    return encode_png(raster), "png"


# ---------------------------------------------------------------- 边界检测

def _row_mean_std(raster, y):
    """一行的亮度均值与标准差。用切片步进取三通道，再走定点亮度。

    row[0::3] 这类步长切片是 C 级操作，比在 Python 里逐像素取三个下标快一个
    数量级；亮度用 BT.601 的 8-bit 定点（77R + 150G + 29B >> 8），与 Go 版
    float 版本在阈值 2.0 上的判定一致。
    """
    width = raster.width
    row = raster.row(y)
    s = 0
    sq = 0
    for r, g, b in zip(row[0::3], row[1::3], row[2::3]):
        lum = (77 * r + 150 * g + 29 * b) >> 8
        s += lum
        sq += lum * lum
    mean = s / float(width)
    var = sq / float(width) - mean * mean
    std = math.sqrt(var) if var > 0 else 0.0
    return mean, std


def scan_bottom_up(raster):
    """从最后一行往上找内容边界，返回 (boundary, blank_px, blank_lum)。

    boundary 是第一条「有内容」的行的下标 + 1，也就是可以安全保留的行数。
    整图纯色时返回 boundary = 0。
    """
    height = raster.height
    total = 0.0
    counted = 0
    boundary = 0
    for y in range(height - 1, -1, -1):
        mean, std = _row_mean_std(raster, y)
        if std >= ROW_STD_THRESHOLD:
            boundary = y + 1
            break
        total += mean
        counted += 1
    blank = height - boundary
    blank_lum = (total / counted) if counted else 0.0
    return boundary, blank, blank_lum


# ---------------------------------------------------------------- 对外入口

def _finish(result, out_height, bytes_in):
    result["out_width"] = result["width"]
    result["out_height"] = out_height
    result["bytes_in"] = bytes_in
    return result


def strip(data, min_blank_px=None, keep_blank=0, fmt="", quality=None,
          white_lum=None):
    """裁掉底部留白，返回 (result, 输出字节)。

    result 字段与 Go 版 /v1/images/strip-watermark 的回执逐项对齐，方便两边客户端
    共用一套解析。抛 StripError 时异常上的 result 带着实测数字。
    """
    bytes_in = len(data)
    raster, source_format = decode_any(data)
    if min_blank_px is None or min_blank_px == "":
        min_blank = DEFAULT_MIN_BLANK
    else:
        try:
            min_blank = int(min_blank_px)
        except (TypeError, ValueError):
            raise StripError(
                "invalid_request", "min_blank_px 必须是整数", 400)
        if min_blank <= 0:
            min_blank = DEFAULT_MIN_BLANK
        if min_blank > MAX_KEEP_BLANK:
            min_blank = MAX_KEEP_BLANK
    try:
        keep = int(keep_blank or 0)
    except (TypeError, ValueError):
        raise StripError("invalid_request", "keep_blank 必须是整数", 400)
    if keep < 0:
        keep = 0
    if keep > MAX_KEEP_BLANK:
        keep = MAX_KEEP_BLANK
    if quality is None or quality == "":
        jpeg_quality = DEFAULT_JPEG_QUALITY
    else:
        try:
            jpeg_quality = int(quality)
        except (TypeError, ValueError):
            raise StripError("invalid_request", "quality 必须是整数", 400)
        if jpeg_quality < 1 or jpeg_quality > 100:
            raise StripError(
                "invalid_request", "quality 必须在 1-100 之间", 400)
    if white_lum is None or white_lum == "":
        lum_gate = DEFAULT_WHITE_LUM
    else:
        try:
            lum_gate = float(white_lum)
        except (TypeError, ValueError):
            raise StripError("invalid_request", "white_lum 必须是数字", 400)

    boundary, blank, blank_lum = scan_bottom_up(raster)
    result = {
        "object": "image.strip",
        "width": raster.width,
        "height": raster.height,
        "boundary": boundary,
        "blank_px": blank,
        "blank_ratio": round(blank / float(raster.height), 4)
        if raster.height else 0.0,
        "blank_lum": round(blank_lum, 1),
        "min_blank": min_blank,
        "white_lum": lum_gate,
    }
    if boundary == 0:
        raise UniformError(_finish(result, raster.height, bytes_in))
    safe = blank >= min_blank and blank_lum >= lum_gate
    result["safe"] = safe
    if not safe:
        raise NoBlankError(_finish(result, raster.height, bytes_in))
    crop_height = boundary + keep
    if crop_height > raster.height:
        crop_height = raster.height
    if crop_height < 1:
        crop_height = 1
    cropped = Raster(raster.width, crop_height,
                     raster.data[:crop_height * raster.stride])
    out_format = choose_format(fmt, source_format)
    payload, actual_format = encode_any(cropped, out_format, jpeg_quality)
    result.update({
        "out_width": cropped.width,
        "out_height": cropped.height,
        "format": actual_format,
        "bytes_in": bytes_in,
        "bytes_out": len(payload),
        "usage": {"credit": 0, "hint": "本地后处理，不消耗上游积分"},
    })
    return result, payload


def classify_input(value):
    """判断 image 参数是 data URL、公网 URL 还是裸 base64。

    只做分类，不碰网络：真正的取字节在网关层做，那里才有 SSRF 收口（域名白名单
    + 禁 3xx 跟随）。
    """
    if not isinstance(value, str) or not value.strip():
        raise StripError("invalid_request", "image 必填", 400)
    text = value.strip()
    if text.startswith("data:"):
        head, sep, body = text.partition(",")
        if not sep:
            raise StripError("invalid_request", "data URL 缺逗号", 400)
        if ";base64" not in head.lower():
            raise StripError(
                "invalid_request", "data URL 必须是 base64 编码", 400)
        return "data", body
    head = text[:8].lower()
    if head.startswith("http://") or head.startswith("https://"):
        return "url", text
    return "base64", text
