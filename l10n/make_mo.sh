#!/bin/bash
# version: 2025-08-27.2
# date: 2025-08-27
VERSION="2025-08-27.2"

set -e

usage() {
    cat <<USAGE
Usage: $0 [--install [path]] [--remove [path]] [--json] [-h|--help]
Without options, compiles .po files in motioneye/locale/*/LC_MESSAGES/ to .mo files.
  --install [path]  Copy this script to /usr/local/bin/make_mo or provided path.
  --remove  [path]  Remove script from /usr/local/bin/make_mo or provided path.
  --json            Also generate .json files using po2json.
  -h, --help        Show this help message.
USAGE
}

install_path="/usr/local/bin/make_mo"
run_json=0
script_dir="$(cd "$(dirname "$0")" && pwd)"

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
            "$target"
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
        --json)
            run_json=1
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

if ! command -v msgfmt >/dev/null 2>&1; then
    echo "Error: msgfmt command not found. Please install gettext." >&2
    exit 1
fi

if (( run_json )); then
    if command -v po2json >/dev/null 2>&1; then
        PO2JSON="$(command -v po2json)"
    elif [[ -x "$script_dir/po2json" ]]; then
        PO2JSON="$script_dir/po2json"
    else
        echo "Error: po2json command not found." >&2
        exit 1
    fi
fi

for dir in motioneye/locale/*/LC_MESSAGES; do
    [ -d "$dir" ] || continue
    for po in "$dir"/motioneye.po "$dir"/motioneye.js.po; do
        [ -f "$po" ] || continue
        mo="${po%.po}.mo"
        msgfmt "$po" -o "$mo"
        if (( run_json )); then
            json="${po%.po}.json"
            "$PO2JSON" "$po" "$json"
        fi
    done
done
