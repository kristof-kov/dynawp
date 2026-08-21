"""Tests for dwp."""

import os
import plistlib
import base64
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import Quartz
import dwp
from dwp import DWPError


class TestHexColors(unittest.TestCase):
    def test_parse_hex_color_6_digit(self):
        self.assertEqual(dwp.parse_hex_color("#ffffff"), (1.0, 1.0, 1.0))
        self.assertEqual(dwp.parse_hex_color("#000000"), (0.0, 0.0, 0.0))
        self.assertEqual(dwp.parse_hex_color("ffffff"), (1.0, 1.0, 1.0))
        self.assertEqual(dwp.parse_hex_color("#FF0000"), (1.0, 0.0, 0.0))

    def test_parse_hex_color_3_digit(self):
        self.assertEqual(dwp.parse_hex_color("#fff"), (1.0, 1.0, 1.0))
        self.assertEqual(dwp.parse_hex_color("#000"), (0.0, 0.0, 0.0))
        self.assertEqual(dwp.parse_hex_color("f00"), (1.0, 0.0, 0.0))

    def test_parse_hex_color_invalid(self):
        self.assertIsNone(dwp.parse_hex_color("invalid"))
        self.assertIsNone(dwp.parse_hex_color("#12"))
        self.assertIsNone(dwp.parse_hex_color("#12345"))
        self.assertIsNone(dwp.parse_hex_color("#gggggg"))

    def test_is_hex_color(self):
        self.assertTrue(dwp.is_hex_color("#ffffff"))
        self.assertTrue(dwp.is_hex_color("1e1e2e"))
        self.assertTrue(dwp.is_hex_color("#000"))
        self.assertFalse(dwp.is_hex_color("nonexistent.jpg"))

    def test_is_hex_color_file_collision(self):
        # When a file exists with a bare hex name, it should treat as file (return False)
        with patch("os.path.isfile", side_effect=lambda p: p == "abc123"):
            self.assertFalse(dwp.is_hex_color("abc123"))
            # Prefixing with # forces hex color interpretation even if a file exists
            self.assertTrue(dwp.is_hex_color("#abc123"))


class TestResolution(unittest.TestCase):
    def test_parse_resolution_explicit(self):
        self.assertEqual(dwp.parse_resolution("3840x2160"), (3840, 2160))
        self.assertEqual(dwp.parse_resolution("1920X1080"), (1920, 1080))
        self.assertEqual(dwp.parse_resolution("  2560x1440  "), (2560, 1440))

    def test_parse_resolution_auto(self):
        w, h = dwp.parse_resolution("auto")
        self.assertIsInstance(w, int)
        self.assertIsInstance(h, int)
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_parse_resolution_invalid(self):
        invalid_cases = [
            "3840",
            "3840x",
            "x2160",
            "0x0",
            "0x2160",
            "3840x0",
            "-100x200",
            "4k",
            "5k",
            "1080p",
            "random_string",
        ]
        for case in invalid_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    dwp.parse_resolution(case)

    def test_get_primary_screen_resolution_fallback(self):
        mock_nsscreen = MagicMock()
        mock_nsscreen.screens.return_value = []
        with patch("dwp.NSScreen", mock_nsscreen):
            w, h = dwp.get_primary_screen_resolution()
            self.assertEqual((w, h), (dwp.DEFAULT_COLOR_WIDTH, dwp.DEFAULT_COLOR_HEIGHT))


class TestMetadataAndPayload(unittest.TestCase):
    def test_apr_payload(self):
        payload = dwp._build_apr_payload()
        decoded = base64.b64decode(payload)
        plist = plistlib.loads(decoded)
        self.assertEqual(plist, {"l": 0, "d": 1})


class TestImageOperations(unittest.TestCase):
    def test_create_color_image(self):
        img = dwp.create_color_image(1.0, 0.0, 0.0, 200, 100)
        self.assertIsNotNone(img)
        self.assertEqual(Quartz.CGImageGetWidth(img), 200)
        self.assertEqual(Quartz.CGImageGetHeight(img), 100)

    def test_create_color_image_zero_or_negative_dimension(self):
        with self.assertRaises(DWPError):
            dwp.create_color_image(1.0, 0.0, 0.0, 0, 100)
        with self.assertRaises(DWPError):
            dwp.create_color_image(1.0, 0.0, 0.0, 100, -10)

    def test_resize_image(self):
        src_img = dwp.create_color_image(0.0, 1.0, 0.0, 200, 100)
        resized = dwp.resize_image(src_img, 400, 300)
        self.assertEqual(Quartz.CGImageGetWidth(resized), 400)
        self.assertEqual(Quartz.CGImageGetHeight(resized), 300)

    def test_resize_image_zero_dimensions(self):
        src_img = dwp.create_color_image(0.0, 1.0, 0.0, 200, 100)
        with self.assertRaises(DWPError):
            dwp.resize_image(src_img, 0, 100)
        with self.assertRaises(DWPError):
            dwp.resize_image(src_img, 100, -50)

    def test_reconcile_dimensions_same(self):
        img1 = dwp.create_color_image(1.0, 0.0, 0.0, 100, 100)
        img2 = dwp.create_color_image(0.0, 1.0, 0.0, 100, 100)
        out1, out2, w, h = dwp.reconcile_dimensions(img1, 100, 100, img2, 100, 100)
        self.assertEqual((w, h), (100, 100))

    def test_reconcile_dimensions_different_max_envelope(self):
        # light=1000x2000 (tall) vs dark=1900x1100 (wide)
        # target should be max(w) x max(h) = 1900x2000
        img1 = dwp.create_color_image(1.0, 0.0, 0.0, 1000, 2000)
        img2 = dwp.create_color_image(0.0, 1.0, 0.0, 1900, 1100)
        out1, out2, w, h = dwp.reconcile_dimensions(img1, 1000, 2000, img2, 1900, 1100)
        self.assertEqual((w, h), (1900, 2000))
        self.assertEqual(Quartz.CGImageGetWidth(out1), 1900)
        self.assertEqual(Quartz.CGImageGetHeight(out1), 2000)
        self.assertEqual(Quartz.CGImageGetWidth(out2), 1900)
        self.assertEqual(Quartz.CGImageGetHeight(out2), 2000)


class TestDWPErrorHandling(unittest.TestCase):
    def test_load_image_nonexistent(self):
        with self.assertRaises(DWPError):
            dwp.load_image("nonexistent_file_path.png")

    def test_validate_image_file_not_found(self):
        with self.assertRaises(DWPError) as ctx:
            dwp._validate_image_file("nonexistent.png")
        self.assertIn("File not found", str(ctx.exception))

    def test_validate_image_file_unsupported_ext(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            with self.assertRaises(DWPError) as ctx:
                dwp._validate_image_file(tmp.name)
            self.assertIn("Unsupported format", str(ctx.exception))


class TestWallpaperEndToEnd(unittest.TestCase):
    def test_create_and_verify_solid_wallpaper(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            light_img = dwp.create_color_image(1.0, 1.0, 1.0, 64, 64)
            dark_img = dwp.create_color_image(0.0, 0.0, 0.0, 64, 64)
            dwp.create_wallpaper(light_img, dark_img, tmp_path)

            self.assertTrue(os.path.isfile(tmp_path))
            self.assertTrue(dwp.verify_output(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_resolve_inputs_both_colors_with_target_res(self):
        light_img, dark_img, w, h = dwp.resolve_inputs("#fff", "#000", target_res=(128, 128))
        self.assertEqual((w, h), (128, 128))
        self.assertEqual(Quartz.CGImageGetWidth(light_img), 128)


class TestCLIArgs(unittest.TestCase):
    def test_parse_args_basic(self):
        args = dwp.parse_args(["light.jpg", "dark.jpg"])
        self.assertEqual(args.light, "light.jpg")
        self.assertEqual(args.dark, "dark.jpg")
        self.assertEqual(args.output, "output.heic")
        self.assertIsNone(args.resolution)
        self.assertFalse(args.set)

    def test_parse_args_with_resolution(self):
        args = dwp.parse_args(["#fff", "#000", "-r", "1920x1080", "-o", "custom.heic", "--set"])
        self.assertEqual(args.light, "#fff")
        self.assertEqual(args.dark, "#000")
        self.assertEqual(args.resolution, "1920x1080")
        self.assertEqual(args.output, "custom.heic")
        self.assertTrue(args.set)

    def test_parse_args_invalid_resolution(self):
        with self.assertRaises(SystemExit):
            dwp.parse_args(["#fff", "#000", "-r", "invalid"])

    def test_parse_args_info_valid(self):
        args = dwp.parse_args(["--info", "test.heic"])
        self.assertEqual(args.info, "test.heic")
        self.assertIsNone(args.light)
        self.assertIsNone(args.dark)

    def test_parse_args_info_with_positionals_rejected(self):
        with self.assertRaises(SystemExit):
            dwp.parse_args(["--info", "file.heic", "light.jpg", "dark.jpg"])

    def test_parse_args_info_with_set_rejected(self):
        with self.assertRaises(SystemExit):
            dwp.parse_args(["--info", "file.heic", "--set"])

    def test_parse_args_info_with_resolution_rejected(self):
        with self.assertRaises(SystemExit):
            dwp.parse_args(["--info", "file.heic", "-r", "1920x1080"])

    def test_parse_args_missing_args(self):
        with self.assertRaises(SystemExit):
            dwp.parse_args([])
        with self.assertRaises(SystemExit):
            dwp.parse_args(["only_one.jpg"])


class TestMainErrorHandling(unittest.TestCase):
    def test_main_handles_dwp_error_cleanly(self):
        with patch("dwp.resolve_inputs", side_effect=DWPError("Test error")):
            with patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    dwp.main(["#fff", "#000"])
                self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
