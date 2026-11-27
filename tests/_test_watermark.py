"""Image bottom-blank stripping (pure-stdlib PNG path) and input classification.

Run with: python _test_watermark.py
No upstream credentials or outbound network are used: every fixture PNG is
built by the module's own encoder.
"""
import base64
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock

_startup_dir = tempfile.TemporaryDirectory(prefix="watermark-")
os.environ["ACCOUNTS_DIR"] = _startup_dir.name
os.environ["WB_PROXY_USAGE_DIR"] = _startup_dir.name
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wb_watermark as wm


def build_raster(width, height, content_rows, blank_value=255):
    """A width x height RGB image: striped content on top, flat bottom below."""
    data = bytearray(width * height * 3)
    stride = width * 3
    for y in range(height):
        base = y * stride
        if y < content_rows:
            for x in range(width):
                value = 255 if (x + y) % 2 == 0 else 0
                off = base + x * 3
                data[off] = value
                data[off + 1] = value
                data[off + 2] = value
        else:
            for x in range(width):
                off = base + x * 3
                data[off] = blank_value
                data[off + 1] = blank_value
                data[off + 2] = blank_value
    return wm.Raster(width, height, data)


def png_of(width=64, height=300, content_rows=200, blank_value=255):
    return wm.encode_png(build_raster(width, height, content_rows, blank_value))


class PngRoundTripTests(unittest.TestCase):
    def test_encode_decode_keeps_size_and_pixels(self):
        source = build_raster(16, 40, 20)
        decoded = wm.decode_png(wm.encode_png(source))
        self.assertEqual(decoded.width, 16)
        self.assertEqual(decoded.height, 40)
        self.assertEqual(bytes(decoded.data), bytes(source.data))

    def test_signature_is_checked(self):
        with self.assertRaises(wm.NotImageError):
            wm.decode_png(b"not a png at all")

    def test_truncated_png_is_rejected(self):
        data = png_of(16, 40, 20)
        with self.assertRaises(wm.NotImageError):
            wm.decode_png(data[:len(data) // 2])

    def test_pixel_budget_is_enforced_before_decoding(self):
        data = png_of(16, 40, 20)
        with mock.patch.object(wm, "MAX_PIXELS", 100):
            with self.assertRaises(wm.TooLargeError):
                wm.decode_png(data)

    def test_sixteen_bit_png_is_refused(self):
        data = png_of(16, 40, 20)
        # Rewrite IHDR's bit depth byte (offset 8 signature + 4 len + 4 type + 8).
        broken = bytearray(data)
        broken[24] = 16
        with self.assertRaises(wm.NotImageError):
            wm.decode_png(bytes(broken))


class StripTests(unittest.TestCase):
    def test_bottom_blank_is_cropped(self):
        result, payload = wm.strip(png_of())
        self.assertEqual(result["object"], "image.strip")
        self.assertEqual(result["width"], 64)
        self.assertEqual(result["height"], 300)
        self.assertEqual(result["boundary"], 200)
        self.assertEqual(result["blank_px"], 100)
        self.assertEqual(result["out_height"], 200)
        self.assertEqual(result["out_width"], 64)
        self.assertTrue(result["safe"])
        self.assertEqual(result["format"], "png")
        self.assertEqual(result["usage"]["credit"], 0)
        self.assertEqual(result["bytes_out"], len(payload))
        out = wm.decode_png(payload)
        self.assertEqual(out.height, 200)

    def test_blank_ratio_and_lum_are_reported(self):
        result, _payload = wm.strip(png_of())
        self.assertAlmostEqual(result["blank_ratio"], 0.3333, places=3)
        self.assertAlmostEqual(result["blank_lum"], 255.0, places=1)

    def test_keep_blank_keeps_extra_rows(self):
        result, _payload = wm.strip(png_of(), keep_blank=10)
        self.assertEqual(result["out_height"], 210)

    def test_keep_blank_is_clamped_to_image(self):
        result, _payload = wm.strip(png_of(), keep_blank=10000)
        self.assertEqual(result["out_height"], 300)

    def test_no_blank_raises_with_measurements(self):
        data = png_of(content_rows=300)
        with self.assertRaises(wm.NoBlankError) as caught:
            wm.strip(data)
        error = caught.exception
        self.assertEqual(error.status, 422)
        self.assertEqual(error.code, "no_blank_strip")
        self.assertEqual(error.result["blank_px"], 0)
        self.assertIn("原图 64x300", error.message)

    def test_short_blank_is_rejected(self):
        # 40px of blank is below the 90px default gate: that is a picture border,
        # not a watermark strip.
        data = png_of(height=140, content_rows=100)
        with self.assertRaises(wm.NoBlankError) as caught:
            wm.strip(data)
        self.assertEqual(caught.exception.result["blank_px"], 40)

    def test_min_blank_px_can_lower_the_gate(self):
        data = png_of(height=140, content_rows=100)
        result, _payload = wm.strip(data, min_blank_px=40)
        self.assertEqual(result["out_height"], 100)

    def test_grey_blank_is_rejected(self):
        data = png_of(blank_value=200)
        with self.assertRaises(wm.NoBlankError) as caught:
            wm.strip(data)
        self.assertLess(caught.exception.result["blank_lum"], 248.0)

    def test_white_lum_can_lower_the_gate(self):
        result, _payload = wm.strip(png_of(blank_value=200), white_lum=190)
        self.assertEqual(result["out_height"], 200)

    def test_uniform_image_is_rejected(self):
        data = wm.encode_png(build_raster(16, 40, 0))
        with self.assertRaises(wm.UniformError):
            wm.strip(data)

    def test_bad_arguments_are_reported_as_request_errors(self):
        for kwargs in ({"min_blank_px": "abc"}, {"keep_blank": "abc"},
                       {"quality": "abc"}, {"quality": 0}, {"quality": 200},
                       {"white_lum": "abc"}):
            with self.assertRaises(wm.StripError) as caught:
                wm.strip(png_of(), **kwargs)
            self.assertEqual(caught.exception.code, "invalid_request")

    def test_jpeg_output_falls_back_to_png(self):
        result, payload = wm.strip(png_of(), fmt="jpeg")
        # 编不出 JPEG：说 png 而不是假装存了 jpg。
        self.assertEqual(result["format"], "png")
        self.assertTrue(payload.startswith(wm.PNG_SIGNATURE))

    def test_unknown_format_is_rejected(self):
        with self.assertRaises(wm.StripError) as caught:
            wm.strip(png_of(), fmt="webp")
        self.assertEqual(caught.exception.code, "invalid_request")


class FormatAndInputTests(unittest.TestCase):
    def test_choose_format_follows_input_by_default(self):
        self.assertEqual(wm.choose_format("", "png"), "png")
        self.assertEqual(wm.choose_format("", "jpeg"), "jpeg")
        self.assertEqual(wm.choose_format("", "webp"), "png")
        self.assertEqual(wm.choose_format("jpg", "png"), "jpeg")
        self.assertEqual(wm.choose_format("PNG", "jpeg"), "png")

    def test_classify_input_data_url(self):
        kind, body = wm.classify_input("data:image/png;base64,AAAA")
        self.assertEqual(kind, "data")
        self.assertEqual(body, "AAAA")

    def test_classify_input_data_url_requires_base64(self):
        with self.assertRaises(wm.StripError):
            wm.classify_input("data:image/png,AAAA")

    def test_classify_input_url(self):
        kind, body = wm.classify_input("https://example.invalid/a.png")
        self.assertEqual(kind, "url")
        self.assertEqual(body, "https://example.invalid/a.png")

    def test_classify_input_raw_base64(self):
        raw = base64.b64encode(png_of(8, 20, 10)).decode("ascii")
        kind, body = wm.classify_input(raw)
        self.assertEqual(kind, "base64")
        self.assertEqual(body, raw)

    def test_classify_input_rejects_empty(self):
        for value in ("", "   ", None, 12):
            with self.assertRaises(wm.StripError):
                wm.classify_input(value)


class NonPngTests(unittest.TestCase):
    def test_jpeg_is_a_415(self):
        # Minimal JPEG magic: the module must not try to parse it itself.
        fake = b"\xff\xd8\xff\xe0" + b"\x00" * 64
        with self.assertRaises(wm.NotImageError) as caught:
            wm.decode_any(fake)
        self.assertEqual(caught.exception.status, 415)

    def test_oversized_payload_is_rejected(self):
        with mock.patch.object(wm, "MAX_BYTES", 8):
            with self.assertRaises(wm.TooLargeError):
                wm.decode_any(wm.PNG_SIGNATURE + b"\x00" * 32)

    def test_empty_payload_is_rejected(self):
        with self.assertRaises(wm.NotImageError):
            wm.decode_any(b"")


if __name__ == "__main__":
    unittest.main(verbosity=2)
