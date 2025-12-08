# Copyright (c) 2025 motionEye contributors
# This file is part of motionEye.
#
# motionEye is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""UI configuration for RTSP server settings."""

import logging
import os
from typing import Any, Dict

from motioneye import settings
from motioneye.config import additional_config, additional_section
from motioneye.audioctl import detect_audio_devices, get_default_audio_device


def _get_rtsp_integration():
    """Lazy import of rtsp_integration to avoid circular imports."""
    from motioneye.rtspserver import integration as rtsp_integration
    return rtsp_integration


def _config_file_path() -> str:
    """Get the path to the configuration file."""
    if settings.config_file:
        return settings.config_file
    return os.path.join(settings.CONF_PATH, "motioneye.conf")


def _persist_setting(name: str, value: Any) -> None:
    """Persist a setting to the configuration file.
    
    Args:
        name: Setting name
        value: Setting value (if None or empty string, the setting is removed)
    """
    path = _config_file_path()
    
    # Convert value to string for comparison
    str_value = "" if value is None else str(value)
    is_empty = str_value.strip() == ""

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        logging.debug("Unable to ensure config directory exists: %s", path)

    lines = []
    try:
        with open(path, "r") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        logging.info("config file %s missing, creating a new one", path)
    except Exception as e:
        logging.error("Could not read config file %s: %s", path, e)
        return

    updated = False
    new_lines = []
    for line in lines:
        if not line or line.lstrip().startswith("#"):
            new_lines.append(line)
            continue

        parts = line.split(" ", 1)
        if len(parts) != 2:
            new_lines.append(line)
            continue

        key, _ = parts
        if key.upper() == name.upper():
            if is_empty:
                # Skip this line (remove the setting)
                updated = True
            else:
                new_lines.append(f"{name.lower()} {str_value}")
                updated = True
        else:
            new_lines.append(line)

    # Only add new setting if it has a non-empty value
    if not updated and not is_empty:
        new_lines.append(f"{name.lower()} {str_value}")

    try:
        with open(path, "w") as f:
            f.write("\n".join(new_lines) + "\n")
    except Exception as e:
        logging.error("Could not persist setting %s to %s: %s", name, path, e)


def _apply_and_restart() -> None:
    """Apply changes and restart the RTSP server."""
    _get_rtsp_integration().restart()


def _bool(value: Any) -> bool:
    """Convert value to boolean."""
    return str(value).lower() in ("1", "true", "yes", "on")


def _get(key: str) -> Any:
    """Get a setting value."""
    return getattr(settings, key, None)


def _set(key: str, value: Any) -> None:
    """Set a setting value and persist it."""
    setattr(settings, key, value)
    _persist_setting(key.lower(), value)
    _apply_and_restart()


def _get_optional_str(value: Any) -> str:
    """Get optional string value."""
    return "" if value is None else str(value)


def _set_optional_str(key: str, value: Any) -> None:
    """Set optional string value."""
    if value is None:
        value = ""
    value = str(value).strip()
    setattr(settings, key, value or None)
    _persist_setting(key.lower(), value or "")
    _apply_and_restart()


# =============================================================================
# Section Definition
# =============================================================================

@additional_section
def rtsp_server() -> Dict[str, Any]:
    """RTSP Server section definition."""
    return {
        "label": "RTSP Server",
        "description": "Native RTSP server for streaming to Synology Surveillance Station and other clients",
        "open": False,
    }


# =============================================================================
# Configuration Options
# =============================================================================

@additional_config
def rtsp_enabled() -> Dict[str, Any]:
    """Enable RTSP server option."""
    return {
        "label": "Enable RTSP Server",
        "description": "Start the native RTSP server for streaming cameras.",
        "type": "bool",
        "section": "rtsp_server",
        "get": lambda: _bool(_get("RTSP_ENABLED")),
        "set": lambda enabled: _set("RTSP_ENABLED", _bool(enabled)),
    }


@additional_config
def rtsp_port() -> Dict[str, Any]:
    """RTSP port option."""
    return {
        "label": "RTSP Port",
        "description": "Port number for the RTSP server (default: 8554).",
        "type": "number",
        "section": "rtsp_server",
        "min": 1,
        "max": 65535,
        "get": lambda: _get("RTSP_PORT") or 8554,
        "set": lambda port: _set("RTSP_PORT", int(port or 8554)),
    }


@additional_config
def rtsp_listen() -> Dict[str, Any]:
    """RTSP listen address option."""
    return {
        "label": "Listen Address",
        "description": "IP address to listen on (0.0.0.0 for all interfaces).",
        "type": "str",
        "section": "rtsp_server",
        "get": lambda: _get("RTSP_LISTEN") or "0.0.0.0",
        "set": lambda addr: _set("RTSP_LISTEN", addr or "0.0.0.0"),
    }


@additional_config
def rtsp_username() -> Dict[str, Any]:
    """RTSP username option."""
    return {
        "label": "Username",
        "description": "Username for RTSP authentication (leave empty to disable).",
        "type": "str",
        "section": "rtsp_server",
        "get": lambda: _get_optional_str(_get("RTSP_USERNAME")),
        "set": lambda username: _set_optional_str("RTSP_USERNAME", username),
    }


@additional_config
def rtsp_password() -> Dict[str, Any]:
    """RTSP password option."""
    return {
        "label": "Password",
        "description": "Password for RTSP authentication.",
        "type": "str",
        "section": "rtsp_server",
        "get": lambda: _get_optional_str(_get("RTSP_PASSWORD")),
        "set": lambda password: _set_optional_str("RTSP_PASSWORD", password),
    }


@additional_config
def rtsp_audio_enabled() -> Dict[str, Any]:
    """Enable audio in RTSP streams option."""
    return {
        "label": "Enable Audio",
        "description": "Include audio from microphone in RTSP streams.",
        "type": "bool",
        "section": "rtsp_server",
        "get": lambda: _bool(_get("RTSP_AUDIO_ENABLED")),
        "set": lambda enabled: _set("RTSP_AUDIO_ENABLED", _bool(enabled)),
    }


@additional_config
def rtsp_audio_device() -> Dict[str, Any]:
    """Audio input device selection for RTSP server."""
    def get_device():
        current = _get("RTSP_AUDIO_DEVICE")
        if current:
            return current
        return get_default_audio_device()
    
    def set_device(device: str):
        device = device.strip() if device else get_default_audio_device()
        setattr(settings, "RTSP_AUDIO_DEVICE", device)
        _persist_setting("rtsp_audio_device", device)
        _apply_and_restart()
    
    def get_choices():
        devices = detect_audio_devices()
        return devices if devices else [("plug:default", "Default Audio Device")]
    
    return {
        "label": "Audio Input Device",
        "description": "Select the microphone/audio capture device for RTSP audio.",
        "type": "choices",
        "section": "rtsp_server",
        "choices": get_choices(),
        "get": get_device,
        "set": set_device,
    }


@additional_config
def rtsp_video_bitrate() -> Dict[str, Any]:
    """Video bitrate option."""
    return {
        "label": "Video Bitrate (kbps)",
        "description": "H.264 encoding bitrate in kilobits per second.",
        "type": "number",
        "section": "rtsp_server",
        "min": 500,
        "max": 10000,
        "get": lambda: _get("RTSP_VIDEO_BITRATE") or 2000,
        "set": lambda bitrate: _set("RTSP_VIDEO_BITRATE", int(bitrate or 2000)),
    }


@additional_config
def rtsp_video_preset() -> Dict[str, Any]:
    """Video preset option."""
    return {
        "label": "Encoding Preset",
        "description": "FFmpeg encoding preset (faster = lower quality, slower = better quality).",
        "type": "choices",
        "section": "rtsp_server",
        "choices": [
            ("ultrafast", "Ultra Fast"),
            ("superfast", "Super Fast"),
            ("veryfast", "Very Fast"),
            ("faster", "Faster"),
            ("fast", "Fast"),
            ("medium", "Medium"),
        ],
        "get": lambda: _get("RTSP_VIDEO_PRESET") or "ultrafast",
        "set": lambda preset: _set("RTSP_VIDEO_PRESET", preset or "ultrafast"),
    }


@additional_config
def rtsp_status() -> Dict[str, Any]:
    """RTSP server status (read-only info)."""
    def get_status_text():
        status = _get_rtsp_integration().get_server_status()
        if status['running']:
            streams = ', '.join(status['streams']) if status['streams'] else 'none'
            return f"Running on port {status['port']} - Streams: {streams} - Sessions: {status['sessions']}"
        return "Stopped"
        
    return {
        "label": "Server Status",
        "description": "Current RTSP server status.",
        "type": "html",
        "section": "rtsp_server",
        "get": get_status_text,
    }
