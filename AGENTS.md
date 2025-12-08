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

## Development
- **Entry Point**: The application is typically started via `meyectl startserver`.
- **Configuration**: Configuration is stored in `motioneye.conf` and individual `thread-*.conf` files for motion.
- **Localization**: The project supports multiple languages using `gettext` and `babel`.

## Deployment
- Can be installed via `pip`.
- Docker images are available.
- Systemd integration is provided in `extra/`.
