#!/usr/bin/env bash
# All-in-one installer/updater for motionEye on Debian Trixie (Raspberry Pi 3B+ x64 Lite).
# Version: 2025.12.08.3
set -euo pipefail

REPO_URL="https://github.com/sn8k/motioneye.git"
INSTALL_DIR="/opt/motioneye"
VENV_DIR="$INSTALL_DIR/.venv"
BRANCH=""

log() {
    echo "[motioneye-aio] $*"
}

require_root() {
    if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
        echo "This script must be run as root (use sudo)." >&2
        exit 1
    fi
}

install_packages() {
    log "Updating apt cache and installing base packages..."
    apt-get update
    apt-get install -y --no-install-recommends \
        git ca-certificates curl python3 python3-venv python3-dev gcc \
        libjpeg62-turbo-dev libcurl4-openssl-dev libssl-dev ffmpeg \
        alsa-utils motion pkg-config zlib1g-dev libfreetype6-dev
}

ensure_repo() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        log "Repository already present, fetching latest changes..."
        git -C "$INSTALL_DIR" fetch --all
        if [[ -n "$BRANCH" ]]; then
            git -C "$INSTALL_DIR" checkout "$BRANCH"
        fi
    else
        log "Cloning motionEye sources into $INSTALL_DIR..."
        mkdir -p "$INSTALL_DIR"
        if [[ -n "$BRANCH" ]]; then
            git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$INSTALL_DIR"
        else
            git clone "$REPO_URL" "$INSTALL_DIR"
        fi
    fi
}

update_repo() {
    log "Pulling latest changes..."
    if [[ -n "$BRANCH" ]]; then
        git -C "$INSTALL_DIR" checkout "$BRANCH"
        git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
    else
        git -C "$INSTALL_DIR" pull --ff-only
    fi
}

setup_venv() {
    if [[ ! -d "$VENV_DIR" ]]; then
        log "Creating virtual environment in $VENV_DIR..."
        python3 -m venv "$VENV_DIR"
    fi
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip wheel
}

install_motioneye() {
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    log "Installing motionEye from local sources..."
    pip install --pre -e "$INSTALL_DIR"
}

initialize_service() {
    # shellcheck disable=SC1090
    source "$VENV_DIR/bin/activate"
    if [[ ! -f /etc/systemd/system/motioneye.service ]]; then
        log "Running motioneye_init to create configuration and service files..."
        motioneye_init
    else
        log "motionEye service already exists; skipping initialization."
    fi
}

restart_service_if_exists() {
    if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q '^motioneye.service'; then
        log "Restarting motionEye service..."
        systemctl daemon-reload
        systemctl enable --now motioneye.service
        systemctl restart motioneye.service
    else
        log "No systemd service detected; you can start motionEye manually with: $VENV_DIR/bin/meyectl startserver"
    fi
}

usage() {
    cat <<USAGE
Usage: $0 [-b|--branch <name>] install|update
  install : fresh installation on Debian Trixie Lite (RPi 3B+ x64)
  update  : update existing installation in $INSTALL_DIR and restart service
USAGE
}

main() {
    ACTION=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -b|--branch)
                if [[ $# -lt 2 ]]; then
                    echo "Missing branch name for $1" >&2
                    usage
                    exit 1
                fi
                BRANCH=$2
                shift 2
                ;;
            install|update)
                ACTION="$1"
                shift
                ;;
            *)
                usage
                exit 1
                ;;
        esac
    done

    if [[ -z "$ACTION" ]]; then
        usage
        exit 1
    fi

    require_root

    case "$ACTION" in
        install)
            install_packages
            ensure_repo
            update_repo
            setup_venv
            install_motioneye
            initialize_service
            restart_service_if_exists
            ;;
        update)
            if [[ ! -d "$INSTALL_DIR" ]]; then
                echo "Installation directory $INSTALL_DIR not found. Run with 'install' first." >&2
                exit 1
            fi
            ensure_repo
            update_repo
            setup_venv
            install_motioneye
            restart_service_if_exists
            ;;
        *)
            usage
            exit 1
            ;;
    esac

    log "Done."
}

main "$@"
