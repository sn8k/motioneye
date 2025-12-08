#!/usr/bin/env bash
# All-in-one installer/updater for motionEye on Debian Trixie (Raspberry Pi 3B+ x64 Lite).
# Version: 2025.12.08.5
set -euo pipefail

REPO_URL="https://github.com/sn8k/motioneye.git"
INSTALL_DIR="/opt/motioneye"
VENV_DIR="$INSTALL_DIR/.venv"
BRANCH=""

log() {
    echo "[motioneye-aio] $*"
}

prompt_branch_selection() {
    if [[ -n "$BRANCH" ]]; then
        log "Using preselected branch '$BRANCH'."
        return
    fi

    local branches=()

    if command -v git >/dev/null 2>&1; then
        log "Fetching available branches from $REPO_URL..."
        mapfile -t branches < <(git ls-remote --heads "$REPO_URL" | awk '{print $2}' | sed 's@refs/heads/@@' | sort)
    else
        log "git is not available yet; defaulting to offering the 'main' branch."
    fi

    if [[ ${#branches[@]} -eq 0 ]]; then
        branches=("main")
    fi

    log "Select the branch to use:"
    PS3="Enter the number of the branch to checkout: "
    select opt in "${branches[@]}"; do
        if [[ -n "$opt" ]]; then
            BRANCH="$opt"
            break
        fi
        echo "Please select a valid branch number."
    done

    log "Branch selected: $BRANCH"
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
    local service_name="motioneye.service"

    if command -v systemctl >/dev/null 2>&1; then
        if systemctl status "$service_name" >/dev/null 2>&1 || [[ -f "/etc/systemd/system/$service_name" ]] || [[ -f "/lib/systemd/system/$service_name" ]]; then
            log "Restarting motionEye service via systemd..."
            systemctl daemon-reload
            systemctl enable --now "$service_name"
            systemctl restart "$service_name"
            return
        fi
    fi

    if command -v service >/dev/null 2>&1 && service motioneye status >/dev/null 2>&1; then
        log "Restarting motionEye service via init system..."
        service motioneye restart
        return
    fi

    log "No system service detected; you can start motionEye manually with: $VENV_DIR/bin/meyectl startserver"
}

prompt_push_branch() {
    local current_branch
    current_branch=$(git -C "$INSTALL_DIR" rev-parse --abbrev-ref HEAD)

    log "Current branch: $current_branch"
    log "Fetching remote branches..."
    git -C "$INSTALL_DIR" fetch --all

    local branches=()
    mapfile -t branches < <(git -C "$INSTALL_DIR" branch -r | sed 's@origin/@@' | sed 's/^[[:space:]]*//' | grep -v '^HEAD' | sort)

    log "Where do you want to push your changes?"
    echo "  1) Current branch ($current_branch)"
    echo "  2) Select an existing remote branch"
    echo "  3) Create a new branch"
    read -rp "Enter choice [1-3]: " choice

    case "$choice" in
        1)
            PUSH_BRANCH="$current_branch"
            ;;
        2)
            log "Available remote branches:"
            PS3="Enter the number of the branch: "
            select opt in "${branches[@]}"; do
                if [[ -n "$opt" ]]; then
                    PUSH_BRANCH="$opt"
                    break
                fi
                echo "Please select a valid branch number."
            done
            ;;
        3)
            read -rp "Enter the name for the new branch: " new_branch
            if [[ -z "$new_branch" ]]; then
                echo "Branch name cannot be empty." >&2
                exit 1
            fi
            PUSH_BRANCH="$new_branch"
            CREATE_NEW_BRANCH=1
            ;;
        *)
            echo "Invalid choice." >&2
            exit 1
            ;;
    esac

    log "Target branch for push: $PUSH_BRANCH"
}

push_changes() {
    log "Checking for local changes..."
    cd "$INSTALL_DIR"

    # Ensure git identity is configured
    if ! git config user.email >/dev/null 2>&1; then
        log "Git user identity not configured."
        read -rp "Enter your email for git commits: " git_email
        if [[ -z "$git_email" ]]; then
            echo "Email cannot be empty." >&2
            exit 1
        fi
        git config user.email "$git_email"
    fi

    if ! git config user.name >/dev/null 2>&1; then
        read -rp "Enter your name for git commits: " git_name
        if [[ -z "$git_name" ]]; then
            echo "Name cannot be empty." >&2
            exit 1
        fi
        git config user.name "$git_name"
    fi

    # Check if there are any changes to commit
    if git diff --quiet && git diff --cached --quiet; then
        log "No local changes detected."
        read -rp "Do you still want to push existing commits? [y/N]: " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            log "Nothing to push. Exiting."
            return
        fi
    else
        # Show status
        log "Local changes detected:"
        git status --short

        read -rp "Do you want to commit these changes? [Y/n]: " confirm
        if [[ ! "$confirm" =~ ^[Nn]$ ]]; then
            # Stage all changes
            git add -A

            # Get commit message
            read -rp "Enter commit message: " commit_msg
            if [[ -z "$commit_msg" ]]; then
                commit_msg="Update from setup script $(date +%Y-%m-%d_%H:%M:%S)"
            fi

            git commit -m "$commit_msg"
            log "Changes committed."
        fi
    fi

    # Handle branch creation/switch if needed
    local current_branch
    current_branch=$(git rev-parse --abbrev-ref HEAD)

    if [[ "${CREATE_NEW_BRANCH:-0}" -eq 1 ]]; then
        log "Creating new branch '$PUSH_BRANCH'..."
        git checkout -b "$PUSH_BRANCH"
    elif [[ "$current_branch" != "$PUSH_BRANCH" ]]; then
        log "Switching to branch '$PUSH_BRANCH'..."
        # Check if branch exists locally
        if git show-ref --verify --quiet "refs/heads/$PUSH_BRANCH"; then
            git checkout "$PUSH_BRANCH"
            git merge "$current_branch" --no-edit
        else
            # Create local branch tracking remote
            git checkout -b "$PUSH_BRANCH" "origin/$PUSH_BRANCH" 2>/dev/null || git checkout -b "$PUSH_BRANCH"
            git merge "$current_branch" --no-edit
        fi
    fi

    # Push to remote
    log "Pushing to origin/$PUSH_BRANCH..."
    if [[ "${CREATE_NEW_BRANCH:-0}" -eq 1 ]]; then
        git push -u origin "$PUSH_BRANCH"
    else
        git push origin "$PUSH_BRANCH"
    fi

    log "Push completed successfully!"
}

usage() {
    cat <<USAGE
Usage: $0 [-b|--branch <name>] install|update|push
  install : fresh installation on Debian Trixie Lite (RPi 3B+ x64)
  update  : update existing installation in $INSTALL_DIR and restart service
  push    : push local changes to GitHub repository
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
            install|update|push)
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

    # Push doesn't need root and has its own branch selection
    if [[ "$ACTION" == "push" ]]; then
        case "$ACTION" in
            push)
                if [[ ! -d "$INSTALL_DIR/.git" ]]; then
                    echo "Git repository not found in $INSTALL_DIR. Run with 'install' first." >&2
                    exit 1
                fi
                prompt_push_branch
                push_changes
                ;;
        esac
        log "Done."
        exit 0
    fi

    prompt_branch_selection
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
