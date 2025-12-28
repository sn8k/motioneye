# motionEye - Project Overview

## Introduction
**motionEye** is a web-based interface for the [motion](https://motion-project.github.io/) daemon, a video surveillance program with motion detection. It provides a user-friendly UI to configure cameras, view live streams, and manage recordings.

## Architecture
The project is built using **Python** and the **Tornado** web framework. It acts as a frontend that communicates with the `motion` daemon, often running on the same machine.

### Tech Stack
- **Language**: Python 3.7+
- **Web Framework**: Tornado (Asynchronous networking library)
- **Templating**: Jinja2
- **Frontend**: HTML, CSS, JavaScript (jQuery based)
- **Dependencies**: `pillow` (image processing), `pycurl` (network), `babel` (localization)

## Directory Structure
- **`motioneye/`**: Main application source code.
    - **`handlers/`**: Tornado request handlers (Controllers).
        - `main.py`: Main dashboard logic.
        - `config.py`: Configuration management.
        - `action.py`: Handling specific actions (snapshot, record, etc.).
    - **`controls/`**: Modules for system-level controls (V4L2, Power, WiFi).
    - **`rtspserver/`**: Native RTSP server for Synology Surveillance Station integration.
        - `server.py`: Main RTSP protocol handler.
        - `session.py`: RTSP session and RTP channel management.
        - `source.py`: FFmpeg transcoder (MJPEG→H.264).
        - `integration.py`: Bridge between motionEye cameras and RTSP.
        - `config.py`: RTSP UI configuration options.
    - **`templates/`**: Jinja2 HTML templates for the UI.
    - **`static/`**: Static assets (CSS, JS, Images).
    - **`locale/`**: Translation files (`.po`, `.mo`).
    - **`scripts/`**: Shell scripts for system tasks.
    - **`extra/`**: Configuration samples and init scripts.
- **`docker/`**: Docker build context and compose files.
- **`tests/`**: Unit tests.

## Key Components
- **`meyectl.py`**: The Command Line Interface (CLI) entry point. It handles commands like `startserver`, `stopserver`, etc.
- **`server.py`**: Sets up the Tornado `Application`, routes, and starts the HTTP server.
- **`motionctl.py`**: Interface for interacting with the `motion` daemon (reloading config, checking status).
- **`config.py`**: Handles parsing and saving configuration files.
- **`audioctl.py`**: Audio device detection (ALSA) for RTSP streaming.
- **`settings.py`**: Global settings definitions (must declare all config options for persistence).
- **`controls/wifictl.py`**: WiFi network management with auto-detection, failover, and IP configuration.

## Development
- **Entry Point**: The application is typically started via `meyectl startserver`.
- **Configuration**: Configuration is stored in `motioneye.conf` and individual `thread-*.conf` files for motion.
- **Localization**: The project supports multiple languages using `gettext` and `babel`.
- **Settings Persistence**: New config options MUST be declared in `settings.py` for `meyectl.py` to load them.

## Deployment
- Can be installed via `pip`.
- Docker images are available.
- Systemd integration is provided in `extra/`.

## Current Version
**0.43.1b49** - Network and LED settings rebuilt at startup

## MUST DO : 
- keep this file up-to-date
- Keep changelog of every (even small) modifications.
- ALWAYS update motioneye version.
- PAS DE DATES DANS LES CHANGELOGS ! on ecrit les changelogs versions apres version