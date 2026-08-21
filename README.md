# dwp

Create macOS Light/Dark dynamic wallpapers from images or hex color codes.

## Requirements

- **macOS**: 10.15 (Catalina) or later
- **Python**: 3.10 or later

## Installation

Install via pip:

```bash
pip install .
```

For development (editable install):

```bash
pip install -e .
```

## Usage

### Create a dynamic wallpaper

`dwp` accepts image files, hex color codes, or a mix of both for light and dark modes:

```bash
# From two images
dwp light.jpg dark.jpg

# From solid colors (automatically matches primary display resolution)
dwp '#ffffff' '#000000'
dwp '#fff' '#000'

# Specify custom resolution (e.g. 5120×2880, 3840×2160, 1920×1080)
dwp '#ffffff' '#000000' -r 5120x2880
dwp light.jpg dark.jpg -r 3840x2160

# Explicitly auto-detect display resolution
dwp light.jpg dark.jpg -r auto

# Mixing an image with a solid color (color matches image dimensions or -r)
dwp light.png '#000000'
dwp '#ffffff' dark.png

# Specify custom output path
dwp light.png dark.png -o ~/Pictures/wallpaper.heic

# Create and immediately set as wallpaper on all displays
dwp light.jpg '#1a1a1a' -o wallpaper.heic --set
```

### Inspect an existing dynamic wallpaper

```bash
dwp --info wallpaper.heic
```

### Running Tests

```bash
python -m unittest discover -s tests -v
```

## Supported Inputs

### Images
`dwp` accepts any image format supported by macOS `CGImageSource`:
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- HEIC / HEIF (`.heic`, `.heif`)
- TIFF (`.tiff`, `.tif`)
- WebP (`.webp`)

### Color Codes
- 6-digit hex: `#ffffff`, `#1e1e2e` (or `ffffff`, `1e1e2e`)
- 3-digit shorthand: `#fff`, `#000` (or `fff`, `000`)
- Case-insensitive (`#FFF`, `#fff`)

## Dimension Mismatch Handling

If the light and dark images have different resolutions:
- `dwp` warns about the dimension mismatch.
- The smaller image is scaled to cover and center-cropped to match the larger image's exact dimensions.

## How It Works

macOS dynamic wallpapers are multi-image HEIC files containing embedded Apple-specific XMP metadata.
`dwp` creates a 2-image HEIC container (index 0: Light, index 1: Dark) using native macOS Core Graphics / Quartz APIs and attaches the `apple_desktop:apr` property containing a base64-encoded binary plist (`{"l": 0, "d": 1}`) to image index 0.

## License

MIT License.
