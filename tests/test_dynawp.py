"""Tests for dynawp."""

import io
import os
import plistlib
import base64
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import Quartz
import dynawp
from dynawp import DWPError
from Foundation import NSURL


class TestHexColors(unittest.TestCase):
    def test_parse_hex_color_6_digit(self):
        self.assertEqual(dynawp.parse_hex_color("#ffffff"), (1.0, 1.0, 1.0))
        self.assertEqual(dynawp.parse_hex_color("#000000"), (0.0, 0.0, 0.0))
        self.assertEqual(dynawp.parse_hex_color("ffffff"), (1.0, 1.0, 1.0))
        self.assertEqual(dynawp.parse_hex_color("#FF0000"), (1.0, 0.0, 0.0))

    def test_parse_hex_color_3_digit(self):
        self.assertEqual(dynawp.parse_hex_color("#fff"), (1.0, 1.0, 1.0))
        self.assertEqual(dynawp.parse_hex_color("#000"), (0.0, 0.0, 0.0))
        self.assertEqual(dynawp.parse_hex_color("f00"), (1.0, 0.0, 0.0))

    def test_parse_hex_color_invalid(self):
        self.assertIsNone(dynawp.parse_hex_color("invalid"))
        self.assertIsNone(dynawp.parse_hex_color("#12"))
        self.assertIsNone(dynawp.parse_hex_color("#12345"))
        self.assertIsNone(dynawp.parse_hex_color("#gggggg"))

    def test_is_hex_color(self):
        self.assertTrue(dynawp.is_hex_color("#ffffff"))
        self.assertTrue(dynawp.is_hex_color("1e1e2e"))
        self.assertTrue(dynawp.is_hex_color("#000"))
        self.assertFalse(dynawp.is_hex_color("nonexistent.jpg"))

    def test_is_hex_color_file_collision(self):
        # When a file exists with a bare hex name, it should treat as file (return False)
        with patch("os.path.isfile", side_effect=lambda p: p == "abc123"):
            self.assertFalse(dynawp.is_hex_color("abc123"))
            # Prefixing with # forces hex color interpretation even if a file exists
            self.assertTrue(dynawp.is_hex_color("#abc123"))


class TestResolution(unittest.TestCase):
    def test_parse_resolution_explicit(self):
        self.assertEqual(dynawp.parse_resolution("3840x2160"), (3840, 2160))
        self.assertEqual(dynawp.parse_resolution("1920X1080"), (1920, 1080))
        self.assertEqual(dynawp.parse_resolution("  2560x1440  "), (2560, 1440))

    def test_parse_resolution_auto(self):
        w, h = dynawp.parse_resolution("auto")
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
                    dynawp.parse_resolution(case)

    def test_get_primary_screen_resolution_fallback(self):
        mock_nsscreen = MagicMock()
        mock_nsscreen.screens.return_value = []
        with patch("dynawp.NSScreen", mock_nsscreen):
            w, h = dynawp.get_primary_screen_resolution()
            self.assertEqual((w, h), (dynawp.DEFAULT_COLOR_WIDTH, dynawp.DEFAULT_COLOR_HEIGHT))


class TestMetadataAndPayload(unittest.TestCase):
    def test_apr_payload(self):
        payload = dynawp._build_apr_payload()
        decoded = base64.b64decode(payload)
        plist = plistlib.loads(decoded)
        self.assertEqual(plist, {"l": 0, "d": 1})


class TestImageOperations(unittest.TestCase):
    def test_create_color_image(self):
        img = dynawp.create_color_image(1.0, 0.0, 0.0, 200, 100)
        self.assertIsNotNone(img)
        self.assertEqual(Quartz.CGImageGetWidth(img), 200)
        self.assertEqual(Quartz.CGImageGetHeight(img), 100)

    def test_create_color_image_zero_or_negative_dimension(self):
        with self.assertRaises(DWPError):
            dynawp.create_color_image(1.0, 0.0, 0.0, 0, 100)
        with self.assertRaises(DWPError):
            dynawp.create_color_image(1.0, 0.0, 0.0, 100, -10)

    def test_resize_image(self):
        src_img = dynawp.create_color_image(0.0, 1.0, 0.0, 200, 100)
        resized = dynawp.resize_image(src_img, 400, 300)
        self.assertEqual(Quartz.CGImageGetWidth(resized), 400)
        self.assertEqual(Quartz.CGImageGetHeight(resized), 300)

    def test_resize_image_zero_dimensions(self):
        src_img = dynawp.create_color_image(0.0, 1.0, 0.0, 200, 100)
        with self.assertRaises(DWPError):
            dynawp.resize_image(src_img, 0, 100)
        with self.assertRaises(DWPError):
            dynawp.resize_image(src_img, 100, -50)


class TestDWPErrorHandling(unittest.TestCase):
    def test_load_image_nonexistent(self):
        with self.assertRaises(DWPError):
            dynawp.load_image("nonexistent_file_path.png")

    def test_validate_image_file_not_found(self):
        with self.assertRaises(DWPError) as ctx:
            dynawp._validate_image_file("nonexistent.png")
        self.assertIn("File not found", str(ctx.exception))

    def test_validate_image_file_unsupported_ext(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            with self.assertRaises(DWPError) as ctx:
                dynawp._validate_image_file(tmp.name)
            self.assertIn("Unsupported format", str(ctx.exception))


class TestWallpaperEndToEnd(unittest.TestCase):
    def _write_test_image(self, path: str, w: int, h: int, r: float, g: float, b: float) -> None:
        img = dynawp.create_color_image(r, g, b, w, h)
        url = NSURL.fileURLWithPath_(path)
        dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
        Quartz.CGImageDestinationAddImage(dest, img, None)
        self.assertTrue(Quartz.CGImageDestinationFinalize(dest))

    def test_create_and_verify_solid_wallpaper(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            light_img = dynawp.create_color_image(1.0, 1.0, 1.0, 64, 64)
            dark_img = dynawp.create_color_image(0.0, 0.0, 0.0, 64, 64)
            dynawp.create_wallpaper(light_img, dark_img, tmp_path)

            self.assertTrue(os.path.isfile(tmp_path))
            self.assertTrue(dynawp.verify_output(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_resolve_inputs_both_colors_with_target_res(self):
        light_img, dark_img, w, h = dynawp.resolve_inputs("#fff", "#000", target_res=(128, 128))
        self.assertEqual((w, h), (128, 128))
        self.assertEqual(Quartz.CGImageGetWidth(light_img), 128)

    def test_resolve_inputs_image_and_color_mixed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = os.path.join(tmpdir, "light.png")
            self._write_test_image(img_path, 100, 50, 1.0, 0.0, 0.0)

            light_img, dark_img, w, h = dynawp.resolve_inputs(img_path, "#000", target_res=(64, 64))
            self.assertEqual((w, h), (64, 64))
            self.assertEqual(Quartz.CGImageGetWidth(light_img), 64)
            self.assertEqual(Quartz.CGImageGetHeight(light_img), 64)
            self.assertEqual(Quartz.CGImageGetWidth(dark_img), 64)

    def test_resolve_inputs_color_and_image_mixed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = os.path.join(tmpdir, "dark.png")
            self._write_test_image(img_path, 100, 50, 0.0, 0.0, 1.0)

            light_img, dark_img, w, h = dynawp.resolve_inputs("#fff", img_path, target_res=(64, 64))
            self.assertEqual((w, h), (64, 64))
            self.assertEqual(Quartz.CGImageGetWidth(light_img), 64)
            self.assertEqual(Quartz.CGImageGetWidth(dark_img), 64)
            self.assertEqual(Quartz.CGImageGetHeight(dark_img), 64)

    def test_resolve_inputs_two_images_different_sizes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            light_path = os.path.join(tmpdir, "light.png")
            dark_path = os.path.join(tmpdir, "dark.png")
            self._write_test_image(light_path, 100, 50, 1.0, 1.0, 1.0)
            self._write_test_image(dark_path, 30, 70, 0.0, 0.0, 0.0)

            light_img, dark_img, w, h = dynawp.resolve_inputs(light_path, dark_path, target_res=(80, 80))
            self.assertEqual((w, h), (80, 80))
            for img in (light_img, dark_img):
                self.assertEqual(Quartz.CGImageGetWidth(img), 80)
                self.assertEqual(Quartz.CGImageGetHeight(img), 80)


class TestOutputPath(unittest.TestCase):
    def test_resolve_output_path_appends_heic(self):
        self.assertEqual(dynawp.resolve_output_path("wallpaper"), "wallpaper.heic")
        self.assertEqual(dynawp.resolve_output_path("/tmp/pics/wp"), "/tmp/pics/wp.heic")

    def test_resolve_output_path_keeps_heic(self):
        self.assertEqual(dynawp.resolve_output_path("wallpaper.heic"), "wallpaper.heic")
        self.assertEqual(dynawp.resolve_output_path("wallpaper.heif"), "wallpaper.heif")
        self.assertEqual(dynawp.resolve_output_path("WALLPAPER.HEIC"), "WALLPAPER.HEIC")

    def test_resolve_output_path_rejects_other_extensions(self):
        for name in ("out.png", "out.jpg", "out.txt", "out.tiff"):
            with self.subTest(name=name):
                with self.assertRaises(DWPError):
                    dynawp.resolve_output_path(name)


class TestCLIArgs(unittest.TestCase):
    def test_parse_args_basic(self):
        args = dynawp.parse_args(["light.jpg", "dark.jpg"])
        self.assertEqual(args.light, "light.jpg")
        self.assertEqual(args.dark, "dark.jpg")
        self.assertEqual(args.output, "output.heic")
        self.assertIsNone(args.resolution)
        self.assertFalse(args.set)

    def test_parse_args_with_resolution(self):
        args = dynawp.parse_args(["#fff", "#000", "-r", "1920x1080", "-o", "custom.heic", "--set"])
        self.assertEqual(args.light, "#fff")
        self.assertEqual(args.dark, "#000")
        self.assertEqual(args.resolution, "1920x1080")
        self.assertEqual(args.output, "custom.heic")
        self.assertTrue(args.set)

    def test_parse_args_invalid_resolution(self):
        with self.assertRaises(SystemExit):
            dynawp.parse_args(["#fff", "#000", "-r", "invalid"])

    def test_parse_args_info_valid(self):
        args = dynawp.parse_args(["--info", "test.heic"])
        self.assertEqual(args.info, "test.heic")
        self.assertIsNone(args.light)
        self.assertIsNone(args.dark)

    def test_parse_args_info_with_positionals_rejected(self):
        with self.assertRaises(SystemExit):
            dynawp.parse_args(["--info", "file.heic", "light.jpg", "dark.jpg"])

    def test_parse_args_info_with_set_rejected(self):
        with self.assertRaises(SystemExit):
            dynawp.parse_args(["--info", "file.heic", "--set"])

    def test_parse_args_info_with_resolution_rejected(self):
        with self.assertRaises(SystemExit):
            dynawp.parse_args(["--info", "file.heic", "-r", "1920x1080"])

    def test_parse_args_missing_args(self):
        with self.assertRaises(SystemExit):
            dynawp.parse_args([])
        with self.assertRaises(SystemExit):
            dynawp.parse_args(["only_one.jpg"])


class TestMainErrorHandling(unittest.TestCase):
    def test_main_handles_dwp_error_cleanly(self):
        with patch("dynawp.resolve_inputs", side_effect=DWPError("Test error")):
            with patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    dynawp.main(["#fff", "#000"])
                self.assertEqual(ctx.exception.code, 1)

    def test_main_handles_keyboard_interrupt(self):
        with patch("dynawp.resolve_inputs", side_effect=KeyboardInterrupt):
            with patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    dynawp.main(["#fff", "#000"])
                self.assertEqual(ctx.exception.code, 130)


class TestVerifyOutput(unittest.TestCase):
    def test_verify_output_rejects_non_image_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"not an image")
            tmp_path = tmp.name

        try:
            with patch("sys.stderr"), patch("sys.stdout"):
                self.assertFalse(dynawp.verify_output(tmp_path))
        finally:
            os.remove(tmp_path)

    def test_verify_output_rejects_single_image_heic(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            img = dynawp.create_color_image(1.0, 0.0, 0.0, 32, 32)
            dest = Quartz.CGImageDestinationCreateWithURL(
                NSURL.fileURLWithPath_(tmp_path), "public.heic", 1, None,
            )
            Quartz.CGImageDestinationAddImage(dest, img, None)
            self.assertTrue(Quartz.CGImageDestinationFinalize(dest))

            with patch("sys.stderr"), patch("sys.stdout"):
                self.assertFalse(dynawp.verify_output(tmp_path))
        finally:
            os.remove(tmp_path)


class TestInspectFile(unittest.TestCase):
    def test_inspect_dynamic_wallpaper_reports_apr(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            light_img = dynawp.create_color_image(1.0, 1.0, 1.0, 32, 32)
            dark_img = dynawp.create_color_image(0.0, 0.0, 0.0, 32, 32)
            dynawp.create_wallpaper(light_img, dark_img, tmp_path)

            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                dynawp.inspect_file(tmp_path)
            output = mock_out.getvalue()
            self.assertIn("appearance-based (apr)", output)
            self.assertIn("Light -> index 0, Dark -> index 1", output)
        finally:
            os.remove(tmp_path)

    def test_inspect_plain_heic_has_no_dynamic_metadata(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            img = dynawp.create_color_image(0.5, 0.5, 0.5, 32, 32)
            dest = Quartz.CGImageDestinationCreateWithURL(
                NSURL.fileURLWithPath_(tmp_path), "public.heic", 1, None,
            )
            Quartz.CGImageDestinationAddImage(dest, img, None)
            self.assertTrue(Quartz.CGImageDestinationFinalize(dest))

            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                dynawp.inspect_file(tmp_path)
            self.assertIn("no Apple dynamic desktop metadata found", mock_out.getvalue())
        finally:
            os.remove(tmp_path)

    def test_inspect_missing_file_raises(self):
        with self.assertRaises(DWPError):
            dynawp.inspect_file("nonexistent_wallpaper.heic")


class TestSetWallpaper(unittest.TestCase):
    def _make_workspace(self, results):
        workspace = MagicMock()
        workspace.setDesktopImageURL_forScreen_options_error_.side_effect = results
        return workspace

    def test_set_wallpaper_success_on_all_displays(self):
        workspace = self._make_workspace([(True, None), (True, None)])
        screens = [MagicMock(), MagicMock()]
        with patch("dynawp.NSWorkspace") as mock_ns, patch("dynawp.NSScreen") as mock_nsscreen:
            mock_ns.sharedWorkspace.return_value = workspace
            mock_nsscreen.screens.return_value = screens
            dynawp.set_wallpaper("/tmp/fake.heic")
        self.assertEqual(workspace.setDesktopImageURL_forScreen_options_error_.call_count, 2)

    def test_set_wallpaper_partial_failure_raises(self):
        workspace = self._make_workspace([(True, None), (False, "mock error")])
        screens = [MagicMock(), MagicMock()]
        with patch("dynawp.NSWorkspace") as mock_ns, patch("dynawp.NSScreen") as mock_nsscreen:
            mock_ns.sharedWorkspace.return_value = workspace
            mock_nsscreen.screens.return_value = screens
            with patch("sys.stderr"), patch("sys.stdout"):
                with self.assertRaises(DWPError):
                    dynawp.set_wallpaper("/tmp/fake.heic")


if __name__ == "__main__":
    unittest.main()
