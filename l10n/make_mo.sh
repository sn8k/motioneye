#!/bin/bash
# version: 2025-08-26
# date: 2025-08-26
VERSION="2025-08-26"

set -e

usage() {
    cat <<USAGE
Usage: $0 [--install [path]] [--remove [path]] [-h|--help]
Without options, compiles .po files in motioneye/locale/*/LC_MESSAGES/ to .mo files.
  --install [path]  Copy this script to /usr/local/bin/make_mo or provided path.
  --remove  [path]  Remove script from /usr/local/bin/make_mo or provided path.
  -h, --help        Show this help message.
USAGE
}

install_path="/usr/local/bin/make_mo"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --install)
            target="$install_path"
            if [[ -n "$2" && "$2" != -* ]]; then
                target="$2"
                shift
            fi
            cp "$0" "$target"
            chmod +x "$target"
            echo "Installed to $target"
            exit 0
            ;;
        --remove)
            target="$install_path"
            if [[ -n "$2" && "$2" != -* ]]; then
                target="$2"
                shift
            fi
            rm -f "$target"
            echo "Removed $target"
            exit 0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

for dir in motioneye/locale/*/LC_MESSAGES; do
    [ -d "$dir" ] || continue
    for po in "$dir"/motioneye.po "$dir"/motioneye.js.po; do
        [ -f "$po" ] || continue
        mo="${po%.po}.mo"
        msgfmt "$po" -o "$mo"
    done
done
