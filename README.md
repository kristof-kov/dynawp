# dynawp

CLI tool to create macOS light/dark dynamic wallpapers from images, solid hex colors, or a mix of both.

## Requirements

macOS 10.15 (Catalina) or later with Python 3.10+.

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

### Basic examples

```bash
# create from two images
dynawp light.jpg dark.jpg

# create from solid hex colors (auto-detects display resolution)
dynawp '#ffffff' '#1e1e2e'
dynawp '#fff' '#000'

# mix an image with a solid background color
dynawp light.png '#181825'
dynawp '#f5e0dc' dark.png

# create and set as active wallpaper immediately
dynawp light.jpg dark.jpg --set

# specify output path and resolution
dynawp light.jpg dark.jpg -r 3840x2160 -o ~/Pictures/wallpaper.heic
```

### Inspect an existing wallpaper

```bash
dynawp --info wallpaper.heic
```

### CLI options

| Option | Description |
| :--- | :--- |
| `light` | Light-mode image path or hex color (e.g. `#ffffff`, `#fff`, `ffffff`) |
| `dark` | Dark-mode image path or hex color (e.g. `#000000`, `#000`, `000000`) |
| `-o`, `--output` | Output file path (default: `output.heic`) |
| `-r`, `--resolution` | Target resolution (`WIDTHxHEIGHT` or `auto`) |
| `--set` | Apply the wallpaper to all connected displays after generation |
| `--info <file>` | Inspect metadata and frame dimensions of a HEIC wallpaper |
| `-h`, `--help` | Show help message |

## Supported formats

- **Images**: JPEG (`.jpg`, `.jpeg`), PNG (`.png`), HEIC/HEIF (`.heic`, `.heif`), TIFF (`.tiff`, `.tif`), WebP (`.webp`)
- **Colors**: 6-digit hex (`#ffffff`, `ffffff`) and 3-digit shorthand (`#fff`, `fff`), case-insensitive

If images have differing aspect ratios or resolutions, `dynawp` scales to cover and center-crops them to match the bounding dimensions.

## Shell completions

Completion scripts are provided in the `completions/` directory for `zsh`, `bash`, and `fish`.

### Zsh

Add the directory to your `fpath` in `~/.zshrc`:

```zsh
fpath=(/path/to/dynamic-wallpaper/completions $fpath)
autoload -Uz compinit && compinit
```

Or copy `completions/_dynawp` to a directory in your existing `fpath` (e.g. `~/.zfunc`).

### Bash

Source the completion script in `~/.bashrc`:

```bash
source /path/to/dynamic-wallpaper/completions/dynawp.bash
```

### Fish

Copy the completion script into your fish completions folder:

```fish
mkdir -p ~/.config/fish/completions
cp completions/dynawp.fish ~/.config/fish/completions/
```

## Tests

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

## How it works

macOS dynamic wallpapers are multi-image HEIC files with embedded Apple metadata. `dynawp` uses native Core Graphics / Quartz APIs to package a 2-frame HEIC container (frame 0 for Light mode, frame 1 for Dark mode) and embeds the `apple_desktop:apr` appearance payload.

## License

MIT
