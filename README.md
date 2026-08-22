# dynawp

Create wallpapers that switch between light and dark mode on macOS.

```bash
# from images
dynawp sunrise.jpg midnight.jpg --set

# or even hex colors
dynawp '#ffffff' '#1e1e2e' --set
```

Requires macOS 10.15 (Catalina) or later with Python 3.10+.

## Installation

Install with [pipx](https://pipx.pypa.io/) (recommended):

```bash
brew install pipx   # if you don't have it
pipx install .
```

Or with a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

For development (editable install):

```bash
pip install -e .
```

## Usage

The first argument becomes the Light-mode frame, the second the Dark-mode frame - keep that order in mind when mixing images and colors.

```bash
# two images
dynawp sunrise.jpg midnight.jpg

# solid hex colors
dynawp '#ffffff' '#1e1e2e'
dynawp '#fff' '#000'

# mix an image with a color background
dynawp sunrise.png '#181825'
dynawp '#f5e0dc' midnight.png

# create and apply immediately
dynawp sunrise.jpg midnight.jpg --set

# explicit output path and resolution
dynawp sunrise.jpg midnight.jpg -r 3840x2160 -o ~/Pictures/wallpaper.heic
```

Every created file is re-opened and validated automatically, so a silent failure never leaves you with a broken wallpaper.

### Options

| Option | Description |
| :--- | :--- |
| `light dark` | Image paths or hex colors (`#ffffff`, `fff`) for the Light and Dark frames |
| `-o`, `--output` | Output file path (default: `output.heic`); `.heic` is appended when no extension is given, other extensions are rejected |
| `-r`, `--resolution` | Target resolution (`WIDTHxHEIGHT`). Defaults to your primary display's resolution, same as `auto` |
| `-s`, `--set` | Apply the wallpaper to all connected displays after generation (may not update primary display on macOS Sonoma+) |
| `-f`, `--force` | Overwrite the output file if it already exists |
| `-i`, `--info <file>` | Inspect metadata and frame dimensions of a HEIC wallpaper |
| `-v`, `--version` | Show version |
| `-h`, `--help` | Show help message |

## Supported formats

- **Images**: JPEG (`.jpg`, `.jpeg`), PNG (`.png`), HEIC/HEIF (`.heic`, `.heif`), TIFF (`.tiff`, `.tif`), WebP (`.webp`)
- **Colors**: 6-digit hex (`#ffffff`, `ffffff`) and 3-digit shorthand (`#fff`, `fff`), case-insensitive

If a bare hex string happens to name an existing file on disk, it is treated as a file path - prefix with `#` to force color interpretation.

Images that don't match the target resolution are scaled to cover and center-cropped.

## Exit codes

| Code | Meaning |
| :--- | :--- |
| 0 | Success |
| 1 | Error |
| 130 | Interrupted |

## Shell completions

Completion scripts for zsh, bash, and fish live in [`completions/`](completions/README.md).

## Tests

```bash
python -m unittest discover -s tests -v
```

## How it works

macOS dynamic wallpapers are multi-image HEIC files with embedded Apple metadata. dynawp uses native Quartz APIs to package a 2-frame HEIC (Light at index 0, Dark at index 1) with the `apple_desktop:apr` appearance payload.

## License

MIT
