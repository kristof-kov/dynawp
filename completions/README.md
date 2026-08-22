# Shell completions

Completion scripts are provided for zsh, bash, and fish.

## Zsh

Add the directory to your `fpath` in `~/.zshrc`:

```zsh
fpath=(/path/to/walldy/completions $fpath)
autoload -Uz compinit && compinit
```

Or copy `completions/_walldy` to a directory in your existing `fpath` (e.g. `~/.zfunc`).

## Bash

Source the completion script in `~/.bashrc`:

```bash
source /path/to/walldy/completions/walldy.bash
```

## Fish

Copy the completion script into your fish completions folder:

```fish
mkdir -p ~/.config/fish/completions
cp completions/walldy.fish ~/.config/fish/completions/
```
