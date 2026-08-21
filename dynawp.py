"""dynawp - create macOS light/dark dynamic wallpapers."""

from __future__ import annotations

import argparse
import base64
import os
import plistlib
import re
import sys

import Quartz
from AppKit import NSScreen, NSWorkspace
from Foundation import NSURL


class DWPError(Exception):
    """Base exception for dynawp errors."""
    pass


SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".webp",
}

HEX_COLOR_PATTERN = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
RESOLUTION_PATTERN = re.compile(r"^(\d+)[xX](\d+)$")
DEFAULT_COLOR_WIDTH = 3840
DEFAULT_COLOR_HEIGHT = 2160

APPLE_NAMESPACE = "http://ns.apple.com/namespace/1.0/"
APPLE_PREFIX = "apple_desktop"
APR_TAG = "apr"
APR_PATH = f"{APPLE_PREFIX}:{APR_TAG}"


def get_primary_screen_resolution() -> tuple[int, int]:
    """Return primary display's physical pixel resolution (w, h), or default fallback."""
    try:
        screens = NSScreen.screens()
        if screens:
            main_screen = screens[0]
            frame = main_screen.frame()
            scale = main_screen.backingScaleFactor()
            w = int(round(frame.size.width * scale))
            h = int(round(frame.size.height * scale))
            if w > 0 and h > 0:
                return w, h
    except Exception:
        pass
    return DEFAULT_COLOR_WIDTH, DEFAULT_COLOR_HEIGHT


def parse_resolution(val: str) -> tuple[int, int]:
    """
    Parse a resolution string: 'auto' or 'WIDTHxHEIGHT' (e.g., '3840x2160').
    Raises ValueError if format is invalid or dimensions are <= 0.
    """
    cleaned = val.strip().lower()
    if cleaned == "auto":
        return get_primary_screen_resolution()

    match = RESOLUTION_PATTERN.fullmatch(cleaned)
    if not match:
        raise ValueError(
            f"Invalid resolution '{val}'. Expected format: 'WIDTHxHEIGHT' (e.g. '3840x2160') or 'auto'."
        )

    w, h = int(match.group(1)), int(match.group(2))
    if w <= 0 or h <= 0:
        raise ValueError(f"Resolution dimensions must be positive integers, got {w}x{h}.")
    return w, h


def parse_hex_color(val: str) -> tuple[float, float, float] | None:
    """Parse hex color string (#RGB, #RRGGBB, RGB, RRGGBB) to (r, g, b) normalized floats."""
    match = HEX_COLOR_PATTERN.fullmatch(val.strip())
    if not match:
        return None
    hex_str = match.group(1)
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return r, g, b


def is_hex_color(val: str) -> bool:
    """
    Return True if val is a valid hex color string.

    If val starts with '#', it is unambiguously treated as a hex color.
    Otherwise, if a file named val exists on disk, it is treated as a file path.
    Prefix with '#' to force interpretation as a hex color when a file with
    the same name exists.
    """
    stripped = val.strip()
    if stripped.startswith("#"):
        return HEX_COLOR_PATTERN.fullmatch(stripped) is not None
    if os.path.isfile(val):
        return False
    return HEX_COLOR_PATTERN.fullmatch(stripped) is not None


def create_color_image(r: float, g: float, b: float, width: int, height: int):
    """Create a solid color CGImageRef with given sRGB color and dimensions. Raises DWPError on failure."""
    if width <= 0 or height <= 0:
        raise DWPError(f"Color image dimensions must be positive integers, got {width}x{height}")

    color_space = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    ctx = Quartz.CGBitmapContextCreate(
        None, width, height, 8, 0, color_space,
        Quartz.kCGImageAlphaPremultipliedLast,
    )
    if not ctx:
        raise DWPError("Failed to create bitmap context for solid color")

    Quartz.CGContextSetRGBFillColor(ctx, r, g, b, 1.0)
    Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, width, height))
    img = Quartz.CGBitmapContextCreateImage(ctx)
    if not img:
        raise DWPError("Failed to create image from bitmap context for solid color")
    return img


def load_image(path: str) -> tuple:
    """Return (CGImageRef, width, height). Raises DWPError on failure."""
    url = NSURL.fileURLWithPath_(os.path.abspath(path))
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if not source:
        raise DWPError(f"Cannot read image: {path}")

    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    if not image:
        raise DWPError(f"Cannot decode image: {path}")

    w = Quartz.CGImageGetWidth(image)
    h = Quartz.CGImageGetHeight(image)
    if w <= 0 or h <= 0:
        raise DWPError(f"Invalid image dimensions ({w}x{h}) for: {path}")
    return image, w, h


def resize_image(image, target_w: int, target_h: int):
    """Scale to cover, then center-crop to exact target size. Raises DWPError on failure."""
    src_w = Quartz.CGImageGetWidth(image)
    src_h = Quartz.CGImageGetHeight(image)
    if src_w <= 0 or src_h <= 0:
        raise DWPError(f"Cannot resize degenerate image with dimensions {src_w}x{src_h}")
    if target_w <= 0 or target_h <= 0:
        raise DWPError(f"Target dimensions must be positive integers, got {target_w}x{target_h}")

    scale = max(target_w / src_w, target_h / src_h)
    scaled_w = int(src_w * scale)
    scaled_h = int(src_h * scale)
    offset_x = (scaled_w - target_w) // 2
    offset_y = (scaled_h - target_h) // 2

    color_space = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    ctx = Quartz.CGBitmapContextCreate(
        None, target_w, target_h, 8, 0, color_space,
        Quartz.kCGImageAlphaPremultipliedLast,
    )
    if not ctx:
        raise DWPError("Failed to create bitmap context for resizing")

    Quartz.CGContextSetInterpolationQuality(ctx, Quartz.kCGInterpolationHigh)
    Quartz.CGContextDrawImage(
        ctx,
        Quartz.CGRectMake(-offset_x, -offset_y, scaled_w, scaled_h),
        image,
    )
    img = Quartz.CGBitmapContextCreateImage(ctx)
    if not img:
        raise DWPError("Failed to create resized image from bitmap context")
    return img


def _load_or_create(arg: str, target: tuple[int, int]) -> tuple:
    """Return (CGImageRef, width, height) from an image path or hex color, sized to target."""
    color = parse_hex_color(arg) if is_hex_color(arg) else None
    if color is not None:
        r, g, b = color
        img = create_color_image(r, g, b, target[0], target[1])
        return img, target[0], target[1]
    _validate_image_file(arg)
    return load_image(arg)


def resolve_inputs(light_arg: str, dark_arg: str, target_res: tuple[int, int]) -> tuple:
    """
    Validate and load/create light and dark CGImages at the target resolution.
    Images are scaled to cover and center-cropped if their size differs.
    Returns (light_img, dark_img, width, height).
    """
    light_img, lw, lh = _load_or_create(light_arg, target_res)
    dark_img, dw, dh = _load_or_create(dark_arg, target_res)

    if (lw, lh) != target_res:
        light_img = resize_image(light_img, target_res[0], target_res[1])
    if (dw, dh) != target_res:
        dark_img = resize_image(dark_img, target_res[0], target_res[1])

    return light_img, dark_img, target_res[0], target_res[1]


def _build_apr_payload() -> str:
    """Return base64-encoded binary plist for apple_desktop:apr."""
    plist_data = {"l": 0, "d": 1}
    bplist = plistlib.dumps(plist_data, fmt=plistlib.FMT_BINARY)
    return base64.b64encode(bplist).decode("ascii")


def _build_metadata(base64_apr: str):
    """Return a CGImageMetadataRef with the apple_desktop:apr tag. Raises DWPError on failure."""
    metadata = Quartz.CGImageMetadataCreateMutable()
    Quartz.CGImageMetadataRegisterNamespaceForPrefix(
        metadata, APPLE_NAMESPACE, APPLE_PREFIX, None,
    )

    tag = Quartz.CGImageMetadataTagCreate(
        APPLE_NAMESPACE,
        APPLE_PREFIX,
        APR_TAG,
        Quartz.kCGImageMetadataTypeString,
        base64_apr,
    )
    if not tag:
        raise DWPError("Failed to create metadata tag")

    ok = Quartz.CGImageMetadataSetTagWithPath(metadata, None, APR_PATH, tag)
    if not ok:
        raise DWPError("Failed to set metadata tag path")

    return metadata


def create_wallpaper(light_img, dark_img, output_path: str) -> None:
    """Create a 2-image HEIC with apple_desktop:apr metadata. Raises DWPError on failure."""
    base64_apr = _build_apr_payload()
    metadata = _build_metadata(base64_apr)

    out_url = NSURL.fileURLWithPath_(os.path.abspath(output_path))
    destination = Quartz.CGImageDestinationCreateWithURL(
        out_url, "public.heic", 2, None,
    )
    if not destination:
        raise DWPError(f"Failed to create HEIC destination: {output_path}")

    options = {Quartz.kCGImageDestinationLossyCompressionQuality: 0.95}
    Quartz.CGImageDestinationAddImageAndMetadata(
        destination, light_img, metadata, options,
    )
    Quartz.CGImageDestinationAddImage(destination, dark_img, options)

    if not Quartz.CGImageDestinationFinalize(destination):
        raise DWPError(f"Failed to finalize HEIC file: {output_path}")


def verify_output(path: str) -> bool:
    """Re-open the HEIC and validate image count, dimensions, and metadata."""
    url = NSURL.fileURLWithPath_(os.path.abspath(path))
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if not source:
        print("⚠️ verification failed: cannot re-open file", file=sys.stderr)
        return False

    count = Quartz.CGImageSourceGetCount(source)
    if count != 2:
        print(f"⚠️ verification failed: expected 2 images, got {count}", file=sys.stderr)
        return False

    print(f"✅ Dynamic wallpaper created: {path}")
    print(f"   Images: {count}")

    for i in range(count):
        props = Quartz.CGImageSourceCopyPropertiesAtIndex(source, i, None)
        w = props.get("PixelWidth", "?") if props else "?"
        h = props.get("PixelHeight", "?") if props else "?"
        label = "Light" if i == 0 else "Dark "
        print(f"   {label} (index {i}): {w}×{h}")

    metadata = Quartz.CGImageSourceCopyMetadataAtIndex(source, 0, None)
    if not metadata:
        print("   Metadata: ✗ no metadata on first image", file=sys.stderr)
        return False

    tag = Quartz.CGImageMetadataCopyTagWithPath(metadata, None, APR_PATH)
    if not tag:
        print("   Metadata: ✗ apple_desktop:apr NOT FOUND", file=sys.stderr)
        return False

    value = Quartz.CGImageMetadataTagCopyValue(tag)
    try:
        plist = plistlib.loads(base64.b64decode(value))
        if plist == {"l": 0, "d": 1}:
            print("   Metadata: ✓ valid (apple_desktop:apr)")
            return True
        else:
            print(f"   Metadata: ✗ unexpected plist content: {plist}", file=sys.stderr)
            return False
    except Exception as exc:
        print(f"   Metadata: ✗ failed to decode apr payload: {exc}", file=sys.stderr)
        return False


def set_wallpaper(path: str) -> None:
    """Set the wallpaper at path on all connected displays. Raises DWPError on failure."""
    workspace = NSWorkspace.sharedWorkspace()
    file_url = NSURL.fileURLWithPath_(os.path.abspath(path))
    screens = NSScreen.screens()

    failures = 0
    for screen in screens:
        success, error = workspace.setDesktopImageURL_forScreen_options_error_(
            file_url, screen, {}, None,
        )
        if not success:
            print(f"⚠️ Failed to set wallpaper on a display: {error}", file=sys.stderr)
            failures += 1

    total = len(screens)
    ok = total - failures
    if ok > 0:
        print(f"🖥  Wallpaper set on {ok} display(s)")
    if failures:
        raise DWPError(f"Failed to set wallpaper on {failures} display(s)")


def inspect_file(path: str) -> None:
    """Inspect an existing dynamic wallpaper file. Raises DWPError on failure."""
    url = NSURL.fileURLWithPath_(os.path.abspath(path))
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if not source:
        raise DWPError(f"Cannot read file: {path}")

    count = Quartz.CGImageSourceGetCount(source)
    print(f"File: {path}")
    print(f"Images: {count}")

    for i in range(count):
        props = Quartz.CGImageSourceCopyPropertiesAtIndex(source, i, None)
        w = props.get("PixelWidth", "?") if props else "?"
        h = props.get("PixelHeight", "?") if props else "?"
        print(f"  [{i}] {w}×{h}")

    metadata = Quartz.CGImageSourceCopyMetadataAtIndex(source, 0, None)
    if not metadata:
        print("Dynamic wallpaper: ✗ no metadata found")
        return

    tag = Quartz.CGImageMetadataCopyTagWithPath(metadata, None, APR_PATH)
    if tag:
        value = Quartz.CGImageMetadataTagCopyValue(tag)
        try:
            plist = plistlib.loads(base64.b64decode(value))
            print("Dynamic wallpaper: ✓ appearance-based (apr)")
            print(f"  Light → index {plist.get('l')}, Dark → index {plist.get('d')}")
        except Exception:
            print("Dynamic wallpaper: ✗ apr metadata present but malformed")
        return

    for key, label in [
        (f"{APPLE_PREFIX}:solar", "solar-based"),
        (f"{APPLE_PREFIX}:h24", "time-based"),
    ]:
        t = Quartz.CGImageMetadataCopyTagWithPath(metadata, None, key)
        if t:
            print(f"Dynamic wallpaper: ✓ {label} ({key.split(':')[1]})")
            return

    print("Dynamic wallpaper: ✗ no Apple dynamic desktop metadata found")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dynawp",
        description="Create macOS Light/Dark dynamic wallpapers from images or hex color codes",
    )

    parser.add_argument("--info", metavar="FILE",
                        help="Inspect an existing dynamic wallpaper")
    parser.add_argument("light", nargs="?", help="Light-mode image path or hex color (e.g. '#ffffff')")
    parser.add_argument("dark", nargs="?", help="Dark-mode image path or hex color (e.g. '#000000')")
    parser.add_argument("-o", "--output", default="output.heic",
                        help="Output path (default: output.heic)")
    parser.add_argument("-r", "--resolution", metavar="WxH",
                        help="Target resolution: WIDTHxHEIGHT (e.g. 3840x2160) or 'auto'")
    parser.add_argument("--set", action="store_true",
                        help="Set as wallpaper on all displays")

    args = parser.parse_args(argv)

    if args.info is not None:
        if args.light is not None or args.dark is not None:
            parser.error("--info cannot be used with light/dark image or color arguments")
        if args.set:
            parser.error("--info cannot be used with --set")
        if args.resolution is not None:
            parser.error("--info cannot be used with -r/--resolution")
    else:
        if args.light is None or args.dark is None:
            parser.error("two arguments required: image paths or hex color codes (or use --info <file>)")

    if args.resolution is not None:
        try:
            parse_resolution(args.resolution)
        except ValueError as e:
            parser.error(str(e))

    return args


def _validate_image_file(path: str) -> None:
    if not os.path.isfile(path):
        raise DWPError(f"File not found: {path}")
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise DWPError(
            f"Unsupported format '{ext}' for: {path}\n"
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def main(argv: list[str] | None = None) -> None:
    try:
        args = parse_args(argv)

        if args.info:
            inspect_file(args.info)
            return

        target_res = parse_resolution(args.resolution) if args.resolution else get_primary_screen_resolution()
        light_img, dark_img, _w, _h = resolve_inputs(args.light, args.dark, target_res)

        create_wallpaper(light_img, dark_img, args.output)

        if not verify_output(args.output):
            raise DWPError("Wallpaper was written but verification found issues")

        if args.set:
            set_wallpaper(args.output)
    except DWPError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
