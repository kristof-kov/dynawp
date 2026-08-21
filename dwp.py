"""dwp — Create macOS Light/Dark dynamic wallpapers."""

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
    """Return True if val is a valid hex color string and not an existing file on disk."""
    if os.path.isfile(val):
        return False
    return HEX_COLOR_PATTERN.fullmatch(val.strip()) is not None


def create_color_image(r: float, g: float, b: float, width: int, height: int):
    """Create a solid color CGImageRef with given sRGB color and dimensions."""
    color_space = Quartz.CGColorSpaceCreateWithName(Quartz.kCGColorSpaceSRGB)
    ctx = Quartz.CGBitmapContextCreate(
        None, width, height, 8, 0, color_space,
        Quartz.kCGImageAlphaPremultipliedLast,
    )
    if not ctx:
        print("Error: failed to create bitmap context for solid color", file=sys.stderr)
        raise SystemExit(1)

    Quartz.CGContextSetRGBFillColor(ctx, r, g, b, 1.0)
    Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, width, height))
    return Quartz.CGBitmapContextCreateImage(ctx)


def load_image(path: str) -> tuple:
    """Return (CGImageRef, width, height)."""
    url = NSURL.fileURLWithPath_(os.path.abspath(path))
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if not source:
        print(f"Error: Cannot read image: {path}", file=sys.stderr)
        raise SystemExit(1)

    image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None)
    if not image:
        print(f"Error: Cannot decode image: {path}", file=sys.stderr)
        raise SystemExit(1)

    w = Quartz.CGImageGetWidth(image)
    h = Quartz.CGImageGetHeight(image)
    return image, w, h


def resize_image(image, target_w: int, target_h: int):
    """Scale to cover, then center-crop to exact target size."""
    src_w = Quartz.CGImageGetWidth(image)
    src_h = Quartz.CGImageGetHeight(image)

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
        print("Error: failed to create bitmap context", file=sys.stderr)
        raise SystemExit(1)

    Quartz.CGContextSetInterpolationQuality(ctx, Quartz.kCGInterpolationHigh)
    Quartz.CGContextDrawImage(
        ctx,
        Quartz.CGRectMake(-offset_x, -offset_y, scaled_w, scaled_h),
        image,
    )
    return Quartz.CGBitmapContextCreateImage(ctx)


def reconcile_dimensions(light_img, lw, lh, dark_img, dw, dh):
    """Resize the smaller image to match the larger. Returns (light, dark, w, h)."""
    if lw == dw and lh == dh:
        return light_img, dark_img, lw, lh

    print(f"⚠️ Dimension mismatch: light={lw}×{lh}, dark={dw}×{dh}", file=sys.stderr)

    if lw * lh >= dw * dh:
        target_w, target_h = lw, lh
        dark_img = resize_image(dark_img, target_w, target_h)
        print(f"   Resized dark image → {target_w}×{target_h}", file=sys.stderr)
    else:
        target_w, target_h = dw, dh
        light_img = resize_image(light_img, target_w, target_h)
        print(f"   Resized light image → {target_w}×{target_h}", file=sys.stderr)

    return light_img, dark_img, target_w, target_h


def _build_apr_payload() -> str:
    """Return base64-encoded binary plist for apple_desktop:apr."""
    plist_data = {"l": 0, "d": 1}
    bplist = plistlib.dumps(plist_data, fmt=plistlib.FMT_BINARY)
    return base64.b64encode(bplist).decode("ascii")


def _build_metadata(base64_apr: str):
    """Return a CGImageMetadataRef with the apple_desktop:apr tag."""
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
        print("Error: failed to create metadata tag", file=sys.stderr)
        raise SystemExit(1)

    ok = Quartz.CGImageMetadataSetTagWithPath(metadata, None, APR_PATH, tag)
    if not ok:
        print("Error: failed to set metadata tag path", file=sys.stderr)
        raise SystemExit(1)

    return metadata


def create_wallpaper(light_img, dark_img, output_path: str) -> None:
    """Create a 2-image HEIC with apple_desktop:apr metadata."""
    base64_apr = _build_apr_payload()
    metadata = _build_metadata(base64_apr)

    out_url = NSURL.fileURLWithPath_(os.path.abspath(output_path))
    destination = Quartz.CGImageDestinationCreateWithURL(
        out_url, "public.heic", 2, None,
    )
    if not destination:
        print("Error: failed to create HEIC destination", file=sys.stderr)
        raise SystemExit(1)

    Quartz.CGImageDestinationAddImageAndMetadata(
        destination, light_img, metadata, None,
    )
    Quartz.CGImageDestinationAddImage(destination, dark_img, None)

    if not Quartz.CGImageDestinationFinalize(destination):
        print("Error: failed to finalize HEIC file", file=sys.stderr)
        raise SystemExit(1)


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
        raise SystemExit(1)


def inspect_file(path: str) -> None:
    url = NSURL.fileURLWithPath_(os.path.abspath(path))
    source = Quartz.CGImageSourceCreateWithURL(url, None)
    if not source:
        print(f"Error: cannot read file: {path}", file=sys.stderr)
        raise SystemExit(1)

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dwp",
        description="Create macOS Light/Dark dynamic wallpapers from images or hex color codes",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--info", metavar="FILE",
                       help="Inspect an existing dynamic wallpaper")

    parser.add_argument("light", nargs="?", help="Light-mode image path or hex color (e.g. '#ffffff')")
    parser.add_argument("dark", nargs="?", help="Dark-mode image path or hex color (e.g. '#000000')")
    parser.add_argument("-o", "--output", default="output.heic",
                        help="Output path (default: output.heic)")
    parser.add_argument("-r", "--resolution", metavar="WxH",
                        help="Target resolution: WIDTHxHEIGHT (e.g. 3840x2160) or 'auto'")
    parser.add_argument("--set", action="store_true",
                        help="Set as wallpaper on all displays")

    args = parser.parse_args()
    if args.info is None and (args.light is None or args.dark is None):
        parser.error("two arguments required: image paths or hex color codes (or use --info <file>)")

    if args.resolution is not None:
        try:
            parse_resolution(args.resolution)
        except ValueError as e:
            parser.error(str(e))

    return args


def _validate_image_file(path: str) -> None:
    if not os.path.isfile(path):
        print(f"Error: File not found: {path}", file=sys.stderr)
        raise SystemExit(1)
    ext = os.path.splitext(path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(
            f"Error: Unsupported format '{ext}' for: {path}\n"
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def resolve_inputs(light_arg: str, dark_arg: str, target_res: tuple[int, int] | None = None) -> tuple:
    """
    Validate and load/create light and dark CGImages.
    Returns (light_img, dark_img, width, height).
    """
    light_is_color = is_hex_color(light_arg)
    dark_is_color = is_hex_color(dark_arg)

    if not light_is_color:
        _validate_image_file(light_arg)
    if not dark_is_color:
        _validate_image_file(dark_arg)

    if light_is_color and dark_is_color:
        lr, lg, lb = parse_hex_color(light_arg)  # type: ignore[misc]
        dr, dg, db = parse_hex_color(dark_arg)   # type: ignore[misc]
        w, h = target_res if target_res is not None else get_primary_screen_resolution()
        light_img = create_color_image(lr, lg, lb, w, h)
        dark_img = create_color_image(dr, dg, db, w, h)
        return light_img, dark_img, w, h

    elif not light_is_color and not dark_is_color:
        light_img, lw, lh = load_image(light_arg)
        dark_img, dw, dh = load_image(dark_arg)
        if target_res is not None:
            tw, th = target_res
            if (lw, lh) != (tw, th):
                light_img = resize_image(light_img, tw, th)
            if (dw, dh) != (tw, th):
                dark_img = resize_image(dark_img, tw, th)
            return light_img, dark_img, tw, th
        return reconcile_dimensions(light_img, lw, lh, dark_img, dw, dh)

    elif not light_is_color and dark_is_color:
        light_img, lw, lh = load_image(light_arg)
        dr, dg, db = parse_hex_color(dark_arg)  # type: ignore[misc]
        if target_res is not None:
            tw, th = target_res
            if (lw, lh) != (tw, th):
                light_img = resize_image(light_img, tw, th)
            dark_img = create_color_image(dr, dg, db, tw, th)
            return light_img, dark_img, tw, th
        else:
            dark_img = create_color_image(dr, dg, db, lw, lh)
            return light_img, dark_img, lw, lh

    else:  # light_is_color and not dark_is_color
        dark_img, dw, dh = load_image(dark_arg)
        lr, lg, lb = parse_hex_color(light_arg)  # type: ignore[misc]
        if target_res is not None:
            tw, th = target_res
            if (dw, dh) != (tw, th):
                dark_img = resize_image(dark_img, tw, th)
            light_img = create_color_image(lr, lg, lb, tw, th)
            return light_img, dark_img, tw, th
        else:
            light_img = create_color_image(lr, lg, lb, dw, dh)
            return light_img, dark_img, dw, dh


def main() -> None:
    args = parse_args()

    if args.info:
        inspect_file(args.info)
        return

    target_res = parse_resolution(args.resolution) if args.resolution else None
    light_img, dark_img, _w, _h = resolve_inputs(args.light, args.dark, target_res=target_res)

    create_wallpaper(light_img, dark_img, args.output)

    if not verify_output(args.output):
        print("⚠️ wallpaper was written but verification found issues", file=sys.stderr)
        raise SystemExit(1)

    if args.set:
        set_wallpaper(args.output)


if __name__ == "__main__":
    main()
