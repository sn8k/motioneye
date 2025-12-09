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
        
        logging.info(f"arecord -l returncode: {result.returncode}")
        if result.stdout:
            logging.info(f"arecord -l stdout:\n{result.stdout}")
        if result.stderr:
            logging.debug(f"arecord -l stderr: {result.stderr}")
        
        if result.returncode == 0 and result.stdout.strip():
            # Parse output like:
            # card 1: HD5000 [Microsoft® LifeCam HD-5000], device 0: USB Audio [USB Audio]
            for line in result.stdout.split('\n'):
                original_line = line
                line = line.strip()
                
                # Skip non-card lines
                if not line.lower().startswith('card'):
                    continue
                    
                logging.info(f"Processing card line: '{line}'")
                
                # Simpler parsing: split by known delimiters
                # Format: "card N: NAME [DESC], device M: SUBNAME [SUBDESC]"
                try:
                    # Extract card number
                    card_match = re.search(r'card\s+(\d+)', line)
                    device_match = re.search(r'device\s+(\d+)', line)
                    
                    if card_match and device_match:
                        card_num = card_match.group(1)
                        device_num = device_match.group(1)
                        
                        # Extract description from first [brackets]
                        desc_match = re.search(r'\[([^\]]+)\]', line)
                        if desc_match:
                            friendly_name = desc_match.group(1).strip()
                        else:
                            # Fallback: extract name between ":" and "["
                            name_match = re.search(r'card\s+\d+:\s+(\S+)', line)
                            friendly_name = name_match.group(1) if name_match else f"Card {card_num}"
                        
                        plug_device_id = f"plughw:{card_num},{device_num}"
                        devices.append((plug_device_id, friendly_name))
                        logging.info(f"Detected audio device: {plug_device_id} = {friendly_name}")
                    else:
                        logging.warning(f"Could not parse card/device numbers from: {line}")
                        
                except Exception as parse_error:
                    logging.warning(f"Error parsing line '{line}': {parse_error}")
                    
    except subprocess.TimeoutExpired:
        logging.warning("Timeout detecting audio devices")
    except FileNotFoundError:
        logging.debug("arecord not found - ALSA utils not installed (normal on non-Linux)")
    except Exception as e:
        logging.error(f"Error detecting audio devices: {e}")
    
    # Add "Default" option only if no real devices found
    if not devices:
        logging.warning("No audio devices detected, adding default fallback")
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
