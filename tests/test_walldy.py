"""Tests for walldy."""

import base64
import io
import os
import plistlib
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import Quartz
import walldy
from walldy import WalldyError
from Foundation import NSURL


def _write_test_image(path: str, w: int, h: int, r: float, g: float, b: float) -> None:
    img = walldy.create_color_image(r, g, b, w, h)
    dest = Quartz.CGImageDestinationCreateWithURL(
        NSURL.fileURLWithPath_(path), "public.png", 1, None,
    )
    Quartz.CGImageDestinationAddImage(dest, img, None)
    assert Quartz.CGImageDestinationFinalize(dest)


class TestHexColors(unittest.TestCase):
    def test_parse_hex_color(self):
        for val, expected in [
            ("#ffffff", (1.0, 1.0, 1.0)),
            ("#000000", (0.0, 0.0, 0.0)),
            ("ffffff", (1.0, 1.0, 1.0)),
            ("#FF0000", (1.0, 0.0, 0.0)),
            ("#fff", (1.0, 1.0, 1.0)),
            ("f00", (1.0, 0.0, 0.0)),
        ]:
            with self.subTest(val=val):
                self.assertEqual(walldy.parse_hex_color(val), expected)

    def test_parse_hex_color_invalid(self):
        for val in ("invalid", "#12", "#12345", "#gggggg"):
            with self.subTest(val=val):
                self.assertIsNone(walldy.parse_hex_color(val))


class TestResolution(unittest.TestCase):
    def test_parse_resolution_explicit(self):
        self.assertEqual(walldy.parse_resolution("3840x2160"), (3840, 2160))
        self.assertEqual(walldy.parse_resolution("1920X1080"), (1920, 1080))
        self.assertEqual(walldy.parse_resolution("  2560x1440  "), (2560, 1440))

    def test_parse_resolution_auto(self):
        w, h = walldy.parse_resolution("auto")
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

    def test_parse_resolution_invalid(self):
        for case in ("3840", "0x0", "1080p", "random_string"):
            with self.subTest(case=case):
                with self.assertRaises(WalldyError):
                    walldy.parse_resolution(case)

    def test_get_primary_screen_resolution_fallback(self):
        mock_nsscreen = MagicMock()
        mock_nsscreen.screens.return_value = []
        with patch("walldy.NSScreen", mock_nsscreen):
            w, h = walldy.get_primary_screen_resolution()
            self.assertEqual((w, h), (walldy.DEFAULT_COLOR_WIDTH, walldy.DEFAULT_COLOR_HEIGHT))


class TestMetadataAndPayload(unittest.TestCase):
    def test_apr_payload_round_trip(self):
        plist = plistlib.loads(base64.b64decode(walldy._build_apr_payload()))
        self.assertEqual(plist, {"l": 0, "d": 1})


class TestImageOperations(unittest.TestCase):
    def test_create_color_image(self):
        img = walldy.create_color_image(1.0, 0.0, 0.0, 200, 100)
        self.assertEqual((Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)), (200, 100))

    def test_resize_image(self):
        src_img = walldy.create_color_image(0.0, 1.0, 0.0, 200, 100)
        resized = walldy.resize_image(src_img, 400, 300)
        self.assertEqual((Quartz.CGImageGetWidth(resized), Quartz.CGImageGetHeight(resized)), (400, 300))

    def test_load_image_nonexistent(self):
        with self.assertRaises(WalldyError):
            walldy.load_image("nonexistent_file_path.png")

    def test_load_image_corrupt_file(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"not an image file content")
            tmp_path = tmp.name

        try:
            with self.assertRaises(WalldyError):
                walldy.load_image(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestWallpaperEndToEnd(unittest.TestCase):
    def test_create_and_verify_solid_wallpaper(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            light_img = walldy.create_color_image(1.0, 1.0, 1.0, 64, 64)
            dark_img = walldy.create_color_image(0.0, 0.0, 0.0, 64, 64)
            walldy.create_wallpaper(light_img, dark_img, tmp_path)

            self.assertTrue(os.path.isfile(tmp_path))
            with patch("sys.stdout"):
                self.assertTrue(walldy.verify_output(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_resolve_inputs_both_colors(self):
        light_img, dark_img = walldy.resolve_inputs("#fff", "#000", target_res=(128, 128))
        self.assertEqual(Quartz.CGImageGetWidth(light_img), 128)
        self.assertEqual(Quartz.CGImageGetHeight(dark_img), 128)

    def test_resolve_inputs_image_and_color_mixed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = os.path.join(tmpdir, "light.png")
            _write_test_image(img_path, 100, 50, 1.0, 0.0, 0.0)

            light_img, dark_img = walldy.resolve_inputs(img_path, "#000", target_res=(64, 64))
            self.assertEqual(
                (Quartz.CGImageGetWidth(light_img), Quartz.CGImageGetHeight(light_img)), (64, 64),
            )
            self.assertEqual(Quartz.CGImageGetWidth(dark_img), 64)

    def test_resolve_inputs_two_images_different_sizes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            light_path = os.path.join(tmpdir, "light.png")
            dark_path = os.path.join(tmpdir, "dark.png")
            _write_test_image(light_path, 100, 50, 1.0, 1.0, 1.0)
            _write_test_image(dark_path, 30, 70, 0.0, 0.0, 0.0)

            light_img, dark_img = walldy.resolve_inputs(light_path, dark_path, target_res=(80, 80))
            for img in (light_img, dark_img):
                self.assertEqual(
                    (Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)), (80, 80),
                )

    def test_main_happy_path(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            with patch("sys.stdout"):
                walldy.main(["#fff", "#000", "-o", tmp_path, "--force"])
            self.assertTrue(os.path.isfile(tmp_path))
            with patch("sys.stdout"):
                self.assertTrue(walldy.verify_output(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestOutputPath(unittest.TestCase):
    def test_resolve_output_path_appends_heic(self):
        self.assertEqual(walldy.resolve_output_path("wallpaper"), "wallpaper.heic")
        self.assertEqual(walldy.resolve_output_path("/tmp/pics/wp"), "/tmp/pics/wp.heic")

    def test_resolve_output_path_keeps_heic(self):
        self.assertEqual(walldy.resolve_output_path("wallpaper.heic"), "wallpaper.heic")
        self.assertEqual(walldy.resolve_output_path("WALLPAPER.HEIC"), "WALLPAPER.HEIC")

    def test_resolve_output_path_rejects_other_extensions(self):
        for name in ("out.png", "out.jpg", "out.txt", "out.heif"):
            with self.subTest(name=name):
                with self.assertRaises(WalldyError):
                    walldy.resolve_output_path(name)

    def test_resolve_output_path_tilde(self):
        self.assertEqual(
            walldy.resolve_output_path("~/wallpaper"),
            os.path.expanduser("~/wallpaper.heic"),
        )


class TestCLIArgs(unittest.TestCase):
    def test_parse_args_basic(self):
        args = walldy.parse_args(["light.jpg", "dark.jpg"])
        self.assertEqual(args.light, "light.jpg")
        self.assertEqual(args.dark, "dark.jpg")
        self.assertEqual(args.output, "output.heic")
        self.assertIsNone(args.resolution)
        self.assertFalse(args.set)

    def test_parse_args_with_flags(self):
        args = walldy.parse_args(["#fff", "#000", "-r", "1920x1080", "-o", "custom.heic", "-s"])
        self.assertEqual(args.light, "#fff")
        self.assertEqual(args.dark, "#000")
        self.assertEqual(args.resolution, "1920x1080")
        self.assertEqual(args.output, "custom.heic")
        self.assertTrue(args.set)

    def test_parse_args_short_flags_match_long_flags(self):
        self.assertEqual(
            walldy.parse_args(["-i", "wall.heic"]).info,
            walldy.parse_args(["--info", "wall.heic"]).info,
        )
        self.assertTrue(walldy.parse_args(["#fff", "#000", "--set"]).set)
        with self.assertRaises(SystemExit) as ctx:
            walldy.parse_args(["-v"])
        self.assertEqual(ctx.exception.code, 0)

    def test_parse_args_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            walldy.parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_parse_args_force_flag(self):
        self.assertTrue(walldy.parse_args(["#fff", "#000", "--force"]).force)
        self.assertFalse(walldy.parse_args(["#fff", "#000"]).force)

    def test_parse_args_info_valid(self):
        args = walldy.parse_args(["--info", "test.heic"])
        self.assertEqual(args.info, "test.heic")
        self.assertIsNone(args.light)
        self.assertIsNone(args.dark)

    def test_parse_args_info_conflicts_rejected(self):
        for extra in (
            ["light.jpg", "dark.jpg"],
            ["--set"],
            ["-r", "1920x1080"],
            ["-o", "other.heic"],
            ["--force"],
        ):
            with self.subTest(extra=extra):
                with self.assertRaises(SystemExit):
                    walldy.parse_args(["--info", "file.heic", *extra])

    def test_parse_args_missing_args(self):
        with self.assertRaises(SystemExit):
            walldy.parse_args([])
        with self.assertRaises(SystemExit):
            walldy.parse_args(["only_one.jpg"])

    def test_main_invalid_resolution_exits_cleanly(self):
        with patch("sys.stderr"):
            with self.assertRaises(SystemExit) as ctx:
                walldy.main(["#fff", "#000", "-r", "invalid"])
            self.assertEqual(ctx.exception.code, 1)


class TestMainErrorHandling(unittest.TestCase):
    def test_main_handles_dwp_error_cleanly(self):
        with patch("walldy.resolve_inputs", side_effect=WalldyError("Test error")):
            with patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    walldy.main(["#fff", "#000"])
                self.assertEqual(ctx.exception.code, 1)

    def test_main_handles_keyboard_interrupt(self):
        with patch("walldy.resolve_inputs", side_effect=KeyboardInterrupt):
            with patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    walldy.main(["#fff", "#000"])
                self.assertEqual(ctx.exception.code, 130)


class TestVerifyOutput(unittest.TestCase):
    def _make_dynamic_wallpaper(self, tmp_path: str) -> None:
        light_img = walldy.create_color_image(1.0, 1.0, 1.0, 32, 32)
        dark_img = walldy.create_color_image(0.0, 0.0, 0.0, 32, 32)
        walldy.create_wallpaper(light_img, dark_img, tmp_path)

    def test_verify_output_prints_summary_on_success(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            self._make_dynamic_wallpaper(tmp_path)
            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                self.assertTrue(walldy.verify_output(tmp_path))
            output = mock_out.getvalue()
            self.assertIn(f"Dynamic wallpaper created: {tmp_path}", output)
            self.assertIn("Light (index 0)", output)
            self.assertIn("Dark (index 1)", output)
            self.assertIn("Metadata: ok (apple_desktop:apr)", output)
        finally:
            os.remove(tmp_path)

    def test_verify_output_rejects_single_image_heic(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            img = walldy.create_color_image(1.0, 0.0, 0.0, 32, 32)
            dest = Quartz.CGImageDestinationCreateWithURL(
                NSURL.fileURLWithPath_(tmp_path), "public.heic", 1, None,
            )
            Quartz.CGImageDestinationAddImage(dest, img, None)
            self.assertTrue(Quartz.CGImageDestinationFinalize(dest))

            with patch("sys.stdout"), patch("sys.stderr"):
                self.assertFalse(walldy.verify_output(tmp_path))
        finally:
            os.remove(tmp_path)

    def test_verify_output_rejects_non_image_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"not an image")
            tmp_path = tmp.name

        try:
            with patch("sys.stdout"), patch("sys.stderr"):
                self.assertFalse(walldy.verify_output(tmp_path))
        finally:
            os.remove(tmp_path)


class TestInspectFile(unittest.TestCase):
    def test_inspect_dynamic_wallpaper_reports_apr(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            light_img = walldy.create_color_image(1.0, 1.0, 1.0, 32, 32)
            dark_img = walldy.create_color_image(0.0, 0.0, 0.0, 32, 32)
            walldy.create_wallpaper(light_img, dark_img, tmp_path)

            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                walldy.inspect_file(tmp_path)
            output = mock_out.getvalue()
            self.assertIn("appearance-based (apr)", output)
            self.assertIn("Light -> index 0, Dark -> index 1", output)
        finally:
            os.remove(tmp_path)

    def test_inspect_plain_heic_has_no_dynamic_metadata(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            img = walldy.create_color_image(0.5, 0.5, 0.5, 32, 32)
            dest = Quartz.CGImageDestinationCreateWithURL(
                NSURL.fileURLWithPath_(tmp_path), "public.heic", 1, None,
            )
            Quartz.CGImageDestinationAddImage(dest, img, None)
            self.assertTrue(Quartz.CGImageDestinationFinalize(dest))

            with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                walldy.inspect_file(tmp_path)
            self.assertIn("no Apple dynamic desktop metadata found", mock_out.getvalue())
        finally:
            os.remove(tmp_path)

    def test_inspect_missing_file_raises(self):
        with self.assertRaises(WalldyError):
            walldy.inspect_file("nonexistent_wallpaper.heic")

    def test_inspect_solar_and_h24_wallpapers(self):
        for tag, label in [("solar", "solar-based (solar)"), ("h24", "time-based (h24)")]:
            with self.subTest(tag=tag):
                with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
                    tmp_path = tmp.name

                try:
                    img = walldy.create_color_image(0.5, 0.5, 0.5, 32, 32)
                    metadata = Quartz.CGImageMetadataCreateMutable()
                    Quartz.CGImageMetadataRegisterNamespaceForPrefix(
                        metadata, walldy.APPLE_NAMESPACE, walldy.APPLE_PREFIX, None,
                    )
                    apple_tag = Quartz.CGImageMetadataTagCreate(
                        walldy.APPLE_NAMESPACE,
                        walldy.APPLE_PREFIX,
                        tag,
                        Quartz.kCGImageMetadataTypeString,
                        "e30=",
                    )
                    self.assertTrue(
                        Quartz.CGImageMetadataSetTagWithPath(
                            metadata, None, f"{walldy.APPLE_PREFIX}:{tag}", apple_tag,
                        )
                    )
                    dest = Quartz.CGImageDestinationCreateWithURL(
                        NSURL.fileURLWithPath_(tmp_path), "public.heic", 1, None,
                    )
                    Quartz.CGImageDestinationAddImageAndMetadata(dest, img, metadata, None)
                    self.assertTrue(Quartz.CGImageDestinationFinalize(dest))

                    with patch("sys.stdout", new_callable=io.StringIO) as mock_out:
                        walldy.inspect_file(tmp_path)
                    self.assertIn(label, mock_out.getvalue())
                finally:
                    os.remove(tmp_path)


class TestSetWallpaper(unittest.TestCase):
    @patch("walldy.NSScreen")
    @patch("walldy.NSWorkspace")
    def test_set_wallpaper_success_and_failure(self, mock_workspace_cls, mock_screen_cls):
        mock_workspace = MagicMock()
        mock_workspace_cls.sharedWorkspace.return_value = mock_workspace

        screen1 = MagicMock()
        screen2 = MagicMock()
        mock_screen_cls.screens.return_value = [screen1, screen2]

        # Success case
        mock_workspace.setDesktopImageURL_forScreen_options_error_.side_effect = [
            (True, None),
            (True, None),
        ]
        with patch("sys.stdout"):
            walldy.set_wallpaper("test.heic")
        self.assertEqual(mock_workspace.setDesktopImageURL_forScreen_options_error_.call_count, 2)

        # Partial failure case
        mock_workspace.setDesktopImageURL_forScreen_options_error_.reset_mock()
        mock_workspace.setDesktopImageURL_forScreen_options_error_.side_effect = [
            (True, None),
            (False, "error"),
        ]
        with patch("sys.stderr"):
            with self.assertRaises(WalldyError):
                walldy.set_wallpaper("test.heic")


class TestLoadOrCreate(unittest.TestCase):
    def test_disambiguation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                # When file doesn't exist, treated as hex color
                img_color = walldy._load_or_create("aabbcc", (10, 10))
                self.assertIsNotNone(img_color)

                # Create a file named 'aabbcc'
                _write_test_image("aabbcc", 10, 10, 1.0, 1.0, 1.0)

                # When file exists, treated as file
                img_file = walldy._load_or_create("aabbcc", (10, 10))
                self.assertIsNotNone(img_file)

                # #aabbcc always treated as color even if file named '#aabbcc' exists
                _write_test_image("#aabbcc", 10, 10, 1.0, 1.0, 1.0)
                img_hash = walldy._load_or_create("#aabbcc", (10, 10))
                self.assertIsNotNone(img_hash)
            finally:
                os.chdir(orig_cwd)


class TestOverwriteProtection(unittest.TestCase):
    def test_overwrite_protection(self):
        with tempfile.NamedTemporaryFile(suffix=".heic", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Without --force
            with patch("sys.stderr"):
                with self.assertRaises(SystemExit) as ctx:
                    walldy.main(["#fff", "#000", "-o", tmp_path])
                self.assertEqual(ctx.exception.code, 1)

            # With --force
            with patch("sys.stdout"):
                walldy.main(["#fff", "#000", "-o", tmp_path, "--force"])
            self.assertTrue(os.path.isfile(tmp_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
