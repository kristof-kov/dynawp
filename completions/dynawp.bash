_dynawp() {
    local cur prev words cword
    _init_completion || return

    local image_exts="@(jpg|jpeg|JPG|JPEG|png|PNG|heic|heif|HEIC|HEIF|tiff|tif|TIFF|TIF|webp|WEBP)"
    local heic_exts="@(heic|heif|HEIC|HEIF)"
    local resolutions="auto 3840x2160 5120x2880 2560x1440 1920x1080 2880x1800 3024x1964 3456x2234"

    case "$prev" in
        --info)
            COMPREPLY=($(compgen -f -X "!*.$heic_exts" -- "$cur"))
            return 0
            ;;
        -o|--output)
            COMPREPLY=($(compgen -f -X "!*.$heic_exts" -- "$cur"))
            return 0
            ;;
        -r|--resolution)
            COMPREPLY=($(compgen -W "$resolutions" -- "$cur"))
            return 0
            ;;
    esac

    if [[ "$cur" == -* ]]; then
        COMPREPLY=($(compgen -W "-h --help --info -o --output -r --resolution --set" -- "$cur"))
        return 0
    fi

    COMPREPLY=($(compgen -f -X "!*.$image_exts" -- "$cur"))
}

complete -F _dynawp dynawp
complete -F _dynawp dwp
