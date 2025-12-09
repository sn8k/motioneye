"""Audio device detection for RTSP streaming.

This module provides:
- Detection of available ALSA audio input devices
- Helper functions for audio device selection in RTSP server config
"""

import logging
import re
import subprocess
import time
from typing import List, Optional, Tuple

# Cache for detected audio devices
_audio_devices_cache: Optional[List[Tuple[str, str]]] = None
_audio_devices_cache_time: float = 0


def detect_audio_devices() -> List[Tuple[str, str]]:
    """Detect available ALSA audio input devices.
    
    Returns:
        List of tuples (device_id, device_name) for available capture devices.
        Example: [("plughw:0,0", "USB Audio Device"), ("plughw:1,0", "Built-in Microphone")]
    """
    global _audio_devices_cache, _audio_devices_cache_time
    
    # Cache for 30 seconds to avoid repeated subprocess calls
    if _audio_devices_cache is not None and (time.time() - _audio_devices_cache_time) < 30:
        return _audio_devices_cache
    
    devices: List[Tuple[str, str]] = []
    
    try:
        # Parse arecord -l output for capture devices
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        logging.debug(f"arecord -l returncode: {result.returncode}")
        logging.debug(f"arecord -l stdout: {result.stdout}")
        logging.debug(f"arecord -l stderr: {result.stderr}")
        
        if result.returncode == 0 and result.stdout.strip():
            # Parse output like:
            # card 1: HD5000 [Microsoft® LifeCam HD-5000], device 0: USB Audio [USB Audio]
            # Format: card N: SHORTNAME [DESCRIPTION], device M: SUBNAME [SUBDESC]
            for line in result.stdout.split('\n'):
                line = line.strip()
                if not line.startswith('card'):
                    continue
                    
                logging.debug(f"Parsing line: {line}")
                
                # Regex to capture: card NUM: SHORTNAME [DESCRIPTION], device NUM: REST
                match = re.match(
                    r'card\s+(\d+):\s+(\S+)\s+\[([^\]]+)\],\s*device\s+(\d+):\s*(.+)',
                    line
                )
                if match:
                    card_num = match.group(1)
                    short_name = match.group(2)
                    card_desc = match.group(3).strip()
                    device_num = match.group(4)
                    device_info = match.group(5).strip()
                    
                    logging.debug(f"Matched: card={card_num}, short={short_name}, desc={card_desc}, dev={device_num}, info={device_info}")
                    
                    # Clean up device info (remove [subdesc] at end)
                    if '[' in device_info:
                        device_info = device_info.split('[')[0].strip()
                    
                    # Create ALSA device identifier (plughw for format conversion)
                    plug_device_id = f"plughw:{card_num},{device_num}"
                    
                    # Use the descriptive name from brackets
                    friendly_name = card_desc if card_desc else short_name
                    
                    devices.append((plug_device_id, friendly_name))
                    logging.info(f"Detected audio device: {plug_device_id} = {friendly_name}")
                else:
                    logging.debug(f"Line did not match regex: {line}")
                    
    except subprocess.TimeoutExpired:
        logging.warning("Timeout detecting audio devices")
    except FileNotFoundError:
        logging.debug("arecord not found - ALSA utils not installed (normal on non-Linux)")
    except Exception as e:
        logging.error(f"Error detecting audio devices: {e}")
    
    # Add "Default" option only if no real devices found or as fallback
    if not devices:
        devices.append(("plug:default", "Default Audio Device"))
    
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
    
    Returns the first real detected device (not plug:default) or 'plughw:0,0' if none found.
    """
    devices = detect_audio_devices()
    # Skip the "Default Audio Device" entry and get first real device
    for device_id, _ in devices:
        if device_id != "plug:default" and device_id.startswith(("plughw:", "hw:")):
            return device_id
    # Fallback to plug:default
    return "plug:default"
