# Copyright (c) 2013 Calin Crisan
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

"""
Raspberry Pi LED control module for motionEye.

Controls the Power LED (PWR) and Activity LED (ACT) on Raspberry Pi.

LED control paths:
- Power LED: /sys/class/leds/PWR (or /sys/class/leds/led1)
- Activity LED: /sys/class/leds/ACT (or /sys/class/leds/led0)

Persistent configuration via /boot/config.txt:
- dtparam=pwr_led_trigger=none
- dtparam=pwr_led_activelow=off
- dtparam=act_led_trigger=none
- dtparam=act_led_activelow=off

TODO: Implement actual LED control functionality
"""

import logging
import os

from motioneye import settings
from motioneye.config import additional_config, additional_section

# LED paths on Raspberry Pi
LED_PATHS = {
    'power': ['/sys/class/leds/PWR', '/sys/class/leds/led1'],
    'activity': ['/sys/class/leds/ACT', '/sys/class/leds/led0'],
}

# Boot config file for persistent settings
BOOT_CONFIG = '/boot/config.txt'


def _is_raspberry_pi():
    """
    Check if running on a Raspberry Pi.
    Also returns True if FORCE_HARDWARE_SETTINGS is enabled in settings.
    """
    # Check for force flag in settings (useful for development/testing)
    if getattr(settings, 'FORCE_HARDWARE_SETTINGS', False):
        return True
    
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            return 'Raspberry Pi' in model
    except Exception:
        pass
    
    # Alternative check via /sys/firmware/devicetree/base/model
    try:
        with open('/sys/firmware/devicetree/base/model', 'r') as f:
            model = f.read()
            return 'Raspberry Pi' in model
    except Exception:
        pass
    
    return False


def _get_led_path(led_type):
    """
    Get the sysfs path for a LED type.
    Returns None if LED not found.
    """
    for path in LED_PATHS.get(led_type, []):
        if os.path.exists(path):
            return path
    return None


def _get_led_state(led_type):
    """
    Get the current state of a LED.
    Returns: 'on', 'off', 'heartbeat', 'mmc0', etc.
    
    TODO: Implement actual reading from sysfs
    """
    # PLACEHOLDER: Return default state
    logging.debug(f'[PLACEHOLDER] getting {led_type} LED state')
    return 'default'


def _set_led_state(led_type, state):
    """
    Set the state of a LED.
    state: 'on', 'off', 'heartbeat', 'mmc0', 'default'
    
    TODO: Implement actual writing to sysfs and /boot/config.txt
    """
    # PLACEHOLDER: Log the action
    logging.info(f'[PLACEHOLDER] setting {led_type} LED to {state}')
    return True


def _get_led_settings():
    """
    Get current LED settings.
    """
    return {
        'ledPowerEnabled': True,  # PLACEHOLDER
        'ledPowerMode': 'default',
        'ledActivityEnabled': True,  # PLACEHOLDER
        'ledActivityMode': 'mmc0',
    }


def _set_led_settings(s):
    """
    Set LED settings.
    
    TODO: Implement persistent configuration
    """
    s.setdefault('ledPowerEnabled', True)
    s.setdefault('ledPowerMode', 'default')
    s.setdefault('ledActivityEnabled', True)
    s.setdefault('ledActivityMode', 'mmc0')
    
    logging.info(
        f'[PLACEHOLDER] LED settings: power={s["ledPowerEnabled"]}, '
        f'activity={s["ledActivityEnabled"]}'
    )
    
    # TODO: Write to /boot/config.txt for persistence
    # TODO: Apply immediate changes via sysfs


# ============================================================================
# Additional Config Definitions for UI
# ============================================================================

@additional_section
def hardware():
    if not _is_raspberry_pi():
        return None
    
    return {
        'label': 'Hardware',
        'description': 'configure Raspberry Pi hardware settings',
    }


@additional_config
def led_power_enabled():
    if not _is_raspberry_pi():
        return None
    
    return {
        'label': 'Power LED',
        'description': 'enable or disable the power LED (red LED on most Pi models) [PLACEHOLDER]',
        'type': 'bool',
        'section': 'hardware',
        'reboot': True,
        'get': _get_led_settings,
        'set': _set_led_settings,
        'get_set_dict': True,
    }


@additional_config
def led_power_mode():
    if not _is_raspberry_pi():
        return None
    
    return {
        'label': 'Power LED Mode',
        'description': 'behavior of the power LED [PLACEHOLDER]',
        'type': 'choices',
        'choices': [
            ('default', 'Default (always on)'),
            ('heartbeat', 'Heartbeat'),
            ('off', 'Always off'),
        ],
        'section': 'hardware',
        'reboot': True,
        'depends': ['ledPowerEnabled'],
        'get': _get_led_settings,
        'set': _set_led_settings,
        'get_set_dict': True,
    }


@additional_config
def led_separator():
    if not _is_raspberry_pi():
        return None
    
    return {
        'type': 'separator',
        'section': 'hardware',
    }


@additional_config
def led_activity_enabled():
    if not _is_raspberry_pi():
        return None
    
    return {
        'label': 'Activity LED',
        'description': 'enable or disable the activity LED (green LED, SD card activity) [PLACEHOLDER]',
        'type': 'bool',
        'section': 'hardware',
        'reboot': True,
        'get': _get_led_settings,
        'set': _set_led_settings,
        'get_set_dict': True,
    }


@additional_config
def led_activity_mode():
    if not _is_raspberry_pi():
        return None
    
    return {
        'label': 'Activity LED Mode',
        'description': 'behavior of the activity LED [PLACEHOLDER]',
        'type': 'choices',
        'choices': [
            ('mmc0', 'SD Card Activity (default)'),
            ('heartbeat', 'Heartbeat'),
            ('cpu', 'CPU Activity'),
            ('off', 'Always off'),
        ],
        'section': 'hardware',
        'reboot': True,
        'depends': ['ledActivityEnabled'],
        'get': _get_led_settings,
        'set': _set_led_settings,
        'get_set_dict': True,
    }
