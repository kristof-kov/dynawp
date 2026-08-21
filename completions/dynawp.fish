complete -c dynawp -s h -l help -d "Show help message"
complete -c dynawp -l info -r -d "Inspect an existing dynamic wallpaper" -a "(__fish_complete_suffix .heic .heif .HEIC .HEIF)"
complete -c dynawp -s o -l output -r -d "Output path (default: output.heic)" -a "(__fish_complete_suffix .heic .HEIC)"
complete -c dynawp -s r -l resolution -r -d "Target resolution (WIDTHxHEIGHT or auto)" -a "auto 3840x2160 5120x2880 2560x1440 1920x1080 2880x1800 3024x1964 3456x2234"
complete -c dynawp -l set -d "Set as wallpaper on all displays"
complete -c dynawp -n "not __fish_seen_subcommand_from --info" -a "(__fish_complete_suffix .jpg .jpeg .png .heic .heif .tiff .tif .webp .JPG .JPEG .PNG .HEIC .HEIF .TIFF .TIF .WEBP)"

complete -c dwp -w dynawp
