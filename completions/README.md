# Shell completions

Completion scripts are provided for zsh, bash, and fish.

## Zsh

Add the directory to your `fpath` in `~/.zshrc`:

```zsh
fpath=(/path/to/dynamic-wallpaper/completions $fpath)
autoload -Uz compinit && compinit
```

Or copy `completions/_dynawp` to a directory in your existing `fpath` (e.g. `~/.zfunc`).

## Bash

Source the completion script in `~/.bashrc`:

```bash
source /path/to/dynamic-wallpaper/completions/dynawp.bash
```

## Fish

Copy the completion script into your fish completions folder:

```fish
mkdir -p ~/.config/fish/completions
cp completions/dynawp.fish ~/.config/fish/completions/
```
