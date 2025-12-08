"""UI plumbing and persistence for RTSP audio mux settings.

This module provides:
- Detection of available ALSA audio input devices
- UI configuration for audio settings
- Persistence of audio settings to motioneye.conf
"""

import logging
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

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

# Cache for detected audio devices
_audio_devices_cache: Optional[List[Tuple[str, str]]] = None
_audio_devices_cache_time: float = 0


def detect_audio_devices() -> List[Tuple[str, str]]:
    """Detect available ALSA audio input devices.
    
    Returns:
        List of tuples (device_id, device_name) for available capture devices.
        Example: [("hw:0,0", "USB Audio Device"), ("hw:1,0", "Built-in Microphone")]
    """
    global _audio_devices_cache, _audio_devices_cache_time
    
    # Cache for 30 seconds to avoid repeated subprocess calls
    if _audio_devices_cache is not None and (time.time() - _audio_devices_cache_time) < 30:
        return _audio_devices_cache
    
    devices: List[Tuple[str, str]] = []
    
    # Always add default as first option
    devices.append(("plug:default", "Default Audio Device"))
    
    try:
        # Method 1: Parse arecord -l output for capture devices
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Parse output like:
            # card 0: Device [USB Audio Device], device 0: USB Audio [USB Audio]
            #   Subdevices: 1/1
            #   Subdevice #0: subdevice #0
            for line in result.stdout.split('\n'):
                match = re.match(
                    r'card\s+(\d+):\s+(\w+)\s+\[([^\]]+)\],\s+device\s+(\d+):\s+(.+)',
                    line
                )
                if match:
                    card_num = match.group(1)
                    device_num = match.group(4)
                    card_name = match.group(3).strip()
                    device_desc = match.group(5).strip()
                    
                    # Create ALSA device identifier
                    device_id = f"hw:{card_num},{device_num}"
                    # Also add plug: version for better compatibility
                    plug_device_id = f"plug:hw:{card_num},{device_num}"
                    
                    # Create friendly name
                    friendly_name = f"{card_name}"
                    if device_desc and device_desc != card_name:
                        friendly_name = f"{card_name} - {device_desc}"
                    
                    # Add both hw: and plug: versions
                    devices.append((plug_device_id, f"{friendly_name} (plug)"))
                    devices.append((device_id, f"{friendly_name} (direct)"))
        
        # Method 2: Also try to get PulseAudio sources if available
        try:
            pa_result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if pa_result.returncode == 0:
                for line in pa_result.stdout.strip().split('\n'):
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        source_name = parts[1]
                        # Filter for input sources (not monitors)
                        if '.monitor' not in source_name and source_name:
                            devices.append((f"pulse:{source_name}", f"PulseAudio: {source_name}"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass  # PulseAudio not available
            
    except subprocess.TimeoutExpired:
        logging.warning("Timeout detecting audio devices")
    except FileNotFoundError:
        logging.warning("arecord not found - ALSA utils may not be installed")
    except Exception as e:
        logging.error("Error detecting audio devices: %s", e)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_devices = []
    for device_id, name in devices:
        if device_id not in seen:
            seen.add(device_id)
            unique_devices.append((device_id, name))
    
    _audio_devices_cache = unique_devices
    _audio_devices_cache_time = time.time()
    
    return unique_devices


def get_default_audio_device() -> str:
    """Get the default audio device.
    
    Returns the first detected device or 'plug:default' if none found.
    """
    devices = detect_audio_devices()
    if devices:
        return devices[0][0]
    return "plug:default"


def _config_file_path() -> str:
    if settings.config_file:
        return settings.config_file
    return os.path.join(settings.CONF_PATH, "motioneye.conf")


def _persist_setting(name: str, value: Any) -> None:
    """Persist a setting to the configuration file.
    
    If value is None or empty string, the setting is removed from the config.
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
    """Apply changes and restart the audio stream."""
    audiostream.stop()
    audiostream.start()


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
    """Get optional string value, returning empty string for None."""
    return "" if value is None else str(value)


def _set_optional_str(key: str, value: Any) -> None:
    """Set optional string value, treating empty as None."""
    if value is None:
        value = ""
    value = str(value).strip()
    setattr(settings, key, value or None)
    _persist_setting(key.lower(), value)
    _apply_and_restart()


# =============================================================================
# Section Definition
# =============================================================================

@additional_section
def audio() -> Dict[str, Any]:
    """Audio RTSP section definition."""
    return {
        "label": "Audio RTSP", 
        "description": "Mux microphone audio with the RTSP feed (legacy ffmpeg mode)",
        "open": False,
    }


# =============================================================================
# Configuration Options
# =============================================================================

@additional_config
def audio_enabled() -> Dict[str, Any]:
    """Enable audio streaming option."""
    return {
        "label": "Enable Audio Streaming", 
        "description": "Start the ffmpeg restream to mux microphone audio into RTSP.",
        "type": "bool",
        "section": "audio",
        "get": lambda: _bool(_get("AUDIO_ENABLED")),
        "set": lambda enabled: _set("AUDIO_ENABLED", _bool(enabled)),
    }


@additional_config
def audio_device() -> Dict[str, Any]:
    """Audio input device selection."""
    def get_device():
        """Get current audio device, defaulting to first detected if not set."""
        current = _get("AUDIO_DEVICE")
        if current:
            return current
        # Return default device if not configured
        return get_default_audio_device()
    
    def set_device(device: str):
        """Set audio device."""
        device = device.strip() if device else get_default_audio_device()
        setattr(settings, "AUDIO_DEVICE", device)
        _persist_setting("audio_device", device)
        _apply_and_restart()
    
    def get_choices():
        """Get list of available audio devices as choices."""
        devices = detect_audio_devices()
        # Format: [(value, display_name), ...]
        return devices if devices else [("plug:default", "Default Audio Device")]
    
    return {
        "label": "Audio Input Device",
        "description": "Select the audio capture device (microphone) to use.",
        "type": "choices",
        "section": "audio",
        "choices": get_choices(),
        "get": get_device,
        "set": set_device,
    }


@additional_config
def audio_device_name() -> Dict[str, Any]:
    """ALSA card name filter (optional, for advanced users)."""
    return {
        "label": "ALSA Card Name Filter",
        "description": "Optional: Filter devices by ALSA card name (e.g. 'USB'). Leave empty to use device selection above.",
        "type": "str",
        "section": "audio",
        "get": lambda: _get_optional_str(_get("AUDIO_DEVICE_NAME")),
        "set": lambda name: _set_optional_str("AUDIO_DEVICE_NAME", name),
    }


@additional_config
def audio_video_source() -> Dict[str, Any]:
    """Video source URL override."""
    return {
        "label": "Video Source URL",
        "description": "Override the video URL to mux with microphone audio. Leave empty to use first camera.",
        "type": "str",
        "section": "audio",
        "get": lambda: _get_optional_str(_get("AUDIO_VIDEO_SOURCE")),
        "set": lambda source: _set_optional_str("AUDIO_VIDEO_SOURCE", source),
    }


@additional_config
def audio_rtsp_port() -> Dict[str, Any]:
    """RTSP port for audio stream."""
    return {
        "label": "RTSP Port",
        "description": "Port number to serve the combined audio/video stream on.",
        "type": "number",
        "section": "audio",
        "min": 1,
        "max": 65535,
        "get": lambda: _get("AUDIO_RTSP_PORT") or _DEFAULTS["rtsp_port"],
        "set": lambda port: _set("AUDIO_RTSP_PORT", int(port or _DEFAULTS["rtsp_port"])),
    }


@additional_config
def audio_rtsp_path() -> Dict[str, Any]:
    """RTSP path for audio stream."""
    return {
        "label": "RTSP Path",
        "description": "Path component for the unified RTSP endpoint.",
        "type": "str",
        "section": "audio",
        "get": lambda: _get("AUDIO_RTSP_PATH") or _DEFAULTS["rtsp_path"],
        "set": lambda path: _set("AUDIO_RTSP_PATH", str(path or _DEFAULTS["rtsp_path"])),
    }


@additional_config
def audio_detected_devices() -> Dict[str, Any]:
    """Display detected audio devices (read-only info)."""
    def get_devices_html():
        """Generate HTML showing detected devices."""
        devices = detect_audio_devices()
        if not devices:
            return "<em>No audio devices detected</em>"
        
        lines = [f"<strong>{len(devices)} device(s) found:</strong><br>"]
        for device_id, name in devices[:5]:  # Show max 5
            lines.append(f"• {name}<br>")
        if len(devices) > 5:
            lines.append(f"<em>... and {len(devices) - 5} more</em>")
        return "".join(lines)
    
    return {
        "label": "Detected Devices",
        "description": "Audio capture devices found on this system.",
        "type": "html",
        "section": "audio",
        "get": get_devices_html,
    }
