# dwp

Create macOS Light/Dark dynamic wallpapers from two images.

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

```bash
# Basic creation (outputs output.heic in current directory)
dwp light.jpg dark.jpg

# Specify custom output path
dwp light.png dark.png -o ~/Pictures/wallpaper.heic

# Create and immediately set as wallpaper on all displays
dwp light.jpg dark.jpg -o wallpaper.heic --set
```

### Inspect an existing dynamic wallpaper

```bash
dwp --info wallpaper.heic
```

## Supported Formats

`dwp` accepts any format supported by macOS `CGImageSource`:
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- HEIC / HEIF (`.heic`, `.heif`)
- TIFF (`.tiff`, `.tif`)
- WebP (`.webp`)

## Dimension Mismatch Handling

If the light and dark images have different resolutions:
- `dwp` warns about the dimension mismatch.
- The smaller image is scaled to cover and center-cropped to match the larger image's exact dimensions.

## How It Works

macOS dynamic wallpapers are multi-image HEIC files containing embedded Apple-specific XMP metadata.
`dwp` creates a 2-image HEIC container (index 0: Light, index 1: Dark) using native macOS Core Graphics / Quartz APIs and attaches the `apple_desktop:apr` property containing a base64-encoded binary plist (`{"l": 0, "d": 1}`) to image index 0.

## License

MIT License.
