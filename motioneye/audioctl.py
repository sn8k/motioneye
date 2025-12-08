"""UI plumbing and persistence for RTSP audio mux settings."""

import logging
import os
from typing import Any, Dict

from motioneye import audiostream, settings
from motioneye.config import additional_config, additional_section

_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "video_source": None,
    "device_name": None,
    "device": "plug:default",
    "rtsp_port": 8555,
    "rtsp_path": "stream",
}


def _config_file_path() -> str:
    if settings.config_file:
        return settings.config_file

    return os.path.join(settings.CONF_PATH, "motioneye.conf")


def _persist_setting(name: str, value: Any) -> None:
    path = _config_file_path()

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
    except Exception as e:  # pragma: no cover - defensive
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
            new_lines.append(f"{name.lower()} {value}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"{name.lower()} {value}")

    try:
        with open(path, "w") as f:
            f.write("\n".join(new_lines) + "\n")
    except Exception as e:  # pragma: no cover - defensive
        logging.error("Could not persist setting %s to %s: %s", name, path, e)


def _apply_and_restart() -> None:
    audiostream.stop()
    audiostream.start()


def _bool(value: Any) -> bool:
    return str(value).lower() in ("1", "true", "yes", "on")


def _get(key: str) -> Any:
    return getattr(settings, key)


def _set(key: str, value: Any) -> None:
    setattr(settings, key, value)
    _persist_setting(key.lower(), value)
    _apply_and_restart()


def _get_optional_str(value: Any) -> str:
    return "" if value is None else str(value)


def _set_optional_str(key: str, value: Any) -> None:
    if value is None:
        value = ""
    value = str(value).strip()
    setattr(settings, key, value or None)
    _persist_setting(key.lower(), value or "")
    _apply_and_restart()


@additional_section
def audio() -> Dict[str, Any]:
    return {
        "label": "Audio RTSP", 
        "description": "Mux microphone audio with the RTSP feed",
        "open": False,
    }


@additional_config
def audio_enabled() -> Dict[str, Any]:
    return {
        "label": "Enable audio", 
        "description": "Start the ffmpeg restream to mux microphone audio into RTSP.",
        "type": "bool",
        "section": "audio",
        "get": lambda: _bool(_get("AUDIO_ENABLED")),
        "set": lambda enabled: _set("AUDIO_ENABLED", _bool(enabled)),
    }


@additional_config
def audio_device_name() -> Dict[str, Any]:
    return {
        "label": "ALSA card name",
        "description": "Friendly ALSA card name to match (e.g. USB).",
        "type": "str",
        "section": "audio",
        "get": lambda: _get_optional_str(_get("AUDIO_DEVICE_NAME")),
        "set": lambda name: _set_optional_str("AUDIO_DEVICE_NAME", name),
    }


@additional_config
def audio_device() -> Dict[str, Any]:
    return {
        "label": "ALSA device override",
        "description": "Fallback ALSA device string if name lookup fails.",
        "type": "str",
        "section": "audio",
        "get": lambda: _get("AUDIO_DEVICE"),
        "set": lambda device: _set("AUDIO_DEVICE", device or _DEFAULTS["device"]),
    }


@additional_config
def audio_video_source() -> Dict[str, Any]:
    return {
        "label": "Video source URL",
        "description": "Override the video URL to mux with microphone audio.",
        "type": "str",
        "section": "audio",
        "get": lambda: _get_optional_str(_get("AUDIO_VIDEO_SOURCE")),
        "set": lambda source: _set_optional_str("AUDIO_VIDEO_SOURCE", source),
    }


@additional_config
def audio_rtsp_port() -> Dict[str, Any]:
    return {
        "label": "RTSP port",
        "description": "Port number to serve the combined audio/video stream on.",
        "type": "number",
        "section": "audio",
        "min": 1,
        "max": 65535,
        "get": lambda: _get("AUDIO_RTSP_PORT"),
        "set": lambda port: _set("AUDIO_RTSP_PORT", int(port or _DEFAULTS["rtsp_port"])),
    }


@additional_config
def audio_rtsp_path() -> Dict[str, Any]:
    return {
        "label": "RTSP path",
        "description": "Path component for the unified RTSP endpoint.",
        "type": "str",
        "section": "audio",
        "get": lambda: _get("AUDIO_RTSP_PATH"),
        "set": lambda path: _set("AUDIO_RTSP_PATH", str(path or _DEFAULTS["rtsp_path"])),
    }
