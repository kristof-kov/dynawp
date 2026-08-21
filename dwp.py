"""dwp — Create macOS Light/Dark dynamic wallpapers."""

from __future__ import annotations

import argparse
import base64
import os
import plistlib
import sys

import Quartz
from AppKit import NSScreen, NSWorkspace
from Foundation import NSURL

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".webp",
}

APPLE_NAMESPACE = "http://ns.apple.com/namespace/1.0/"
APPLE_PREFIX = "apple_desktop"
APR_TAG = "apr"
APR_PATH = f"{APPLE_PREFIX}:{APR_TAG}"


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="dwp",
        description="Create macOS Light/Dark dynamic wallpapers",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--info", metavar="FILE",
                       help="Inspect an existing dynamic wallpaper")

    parser.add_argument("light", nargs="?", help="Light-mode image path")
    parser.add_argument("dark", nargs="?", help="Dark-mode image path")
    parser.add_argument("-o", "--output", default="output.heic",
                        help="Output path (default: output.heic)")
    parser.add_argument("--set", action="store_true",
                        help="Set as wallpaper on all displays")

    args = parser.parse_args()
    if args.info is None and (args.light is None or args.dark is None):
        parser.error("two image paths required (or use --info <file>)")
    return args


def _validate_input(path: str) -> None:
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


def main():
    pass


if __name__ == "__main__":
    main()
