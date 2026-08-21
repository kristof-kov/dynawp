"""dwp — Create macOS Light/Dark dynamic wallpapers."""

from __future__ import annotations

import argparse
import os
import sys

import Quartz
from Foundation import NSURL

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".webp",
}


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
