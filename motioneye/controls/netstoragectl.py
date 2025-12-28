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
Network storage module for motionEye.

Allows storing captured media (images, thumbnails, videos) on network storage
instead of local SD card. Supports NFS, SMB/CIFS, and SSHFS.

This extends the existing SMB functionality in smbctl.py to provide a more
comprehensive network storage solution with automatic failover.

TODO: Implement actual network storage functionality
"""

import logging
import os

from motioneye import settings
from motioneye.config import additional_config, additional_section

# Supported storage protocols
STORAGE_PROTOCOLS = [
    ('local', 'Local Storage (SD Card)'),
    ('smb', 'SMB/CIFS (Windows Share)'),
    ('nfs', 'NFS (Network File System)'),
    ('sshfs', 'SSHFS (SSH File System)'),
]


def _get_network_storage_settings():
    """
    Get current network storage settings.
    
    TODO: Read from persistent configuration
    """
    return {
        'networkStorageEnabled': False,  # PLACEHOLDER
        'networkStorageProtocol': 'local',
        'networkStorageServer': '',
        'networkStorageShare': '',
        'networkStorageUsername': '',
        'networkStoragePassword': '',
        'networkStorageMountPoint': '/media/motioneye_network',
        'networkStorageFailover': True,
        'networkStorageReadOnly': False,
    }


def _set_network_storage_settings(s):
    """
    Set network storage settings.
    
    TODO: Implement actual mount/unmount and configuration persistence
    """
    s.setdefault('networkStorageEnabled', False)
    s.setdefault('networkStorageProtocol', 'local')
    s.setdefault('networkStorageServer', '')
    s.setdefault('networkStorageShare', '')
    s.setdefault('networkStorageUsername', '')
    s.setdefault('networkStoragePassword', '')
    s.setdefault('networkStorageMountPoint', '/media/motioneye_network')
    s.setdefault('networkStorageFailover', True)
    s.setdefault('networkStorageReadOnly', False)
    
    logging.info(
        f'[PLACEHOLDER] Network storage settings: enabled={s["networkStorageEnabled"]}, '
        f'protocol={s["networkStorageProtocol"]}, server={s["networkStorageServer"]}'
    )
    
    # TODO: Validate connection
    # TODO: Mount/unmount storage
    # TODO: Update motion target_dir configuration
    # TODO: Handle failover to local storage


def _test_network_storage(server, share, protocol, username, password):
    """
    Test network storage connection.
    
    TODO: Implement actual connection test
    """
    logging.info(f'[PLACEHOLDER] Testing network storage: {protocol}://{server}/{share}')
    return {'success': False, 'message': 'Not implemented yet'}


def _get_storage_status():
    """
    Get current storage status (mounted, available space, etc.)
    
    TODO: Implement actual status check
    """
    return {
        'mounted': False,
        'available_space': 0,
        'total_space': 0,
        'used_space': 0,
    }


# ============================================================================
# Additional Config Definitions for UI
# ============================================================================

@additional_section
def network_storage():
    return {
        'label': 'Network Storage',
        'description': 'store captured media on network storage instead of local SD card [PLACEHOLDER]',
    }


@additional_config
def network_storage_enabled():
    return {
        'label': 'Enable Network Storage',
        'description': 'store images and videos on network storage instead of local storage [PLACEHOLDER]',
        'type': 'bool',
        'section': 'network_storage',
        'reboot': True,
        'get': _get_network_storage_settings,
        'set': _set_network_storage_settings,
        'get_set_dict': True,
    }


@additional_config
def network_storage_protocol():
    return {
        'label': 'Protocol',
        'description': 'network storage protocol to use [PLACEHOLDER]',
        'type': 'choices',
        'choices': STORAGE_PROTOCOLS,
        'section': 'network_storage',
        'reboot': True,
        'depends': ['networkStorageEnabled'],
        'get': _get_network_storage_settings,
        'set': _set_network_storage_settings,
        'get_set_dict': True,
    }


@additional_config
def network_storage_server():
    return {
        'label': 'Server Address',
        'description': 'IP address or hostname of the storage server [PLACEHOLDER]',
        'type': 'str',
        'section': 'network_storage',
        'required': True,
        'reboot': True,
        'depends': ['networkStorageEnabled', 'networkStorageProtocol!=local'],
        'get': _get_network_storage_settings,
        'set': _set_network_storage_settings,
        'get_set_dict': True,
    }


@additional_config
def network_storage_share():
    return {
        'label': 'Share/Path',
        'description': 'share name (SMB) or path (NFS/SSHFS) [PLACEHOLDER]',
        'type': 'str',
        'section': 'network_storage',
        'required': True,
        'reboot': True,
        'depends': ['networkStorageEnabled', 'networkStorageProtocol!=local'],
        'get': _get_network_storage_settings,
        'set': _set_network_storage_settings,
        'get_set_dict': True,
    }


@additional_config
def network_storage_username():
    return {
        'label': 'Username',
        'description': 'username for authentication (leave empty for anonymous) [PLACEHOLDER]',
        'type': 'str',
        'section': 'network_storage',
        'required': False,
        'reboot': True,
        'depends': ['networkStorageEnabled', 'networkStorageProtocol!=local', 'networkStorageProtocol!=nfs'],
        'get': _get_network_storage_settings,
        'set': _set_network_storage_settings,
        'get_set_dict': True,
    }


@additional_config
def network_storage_password():
    return {
        'label': 'Password',
        'description': 'password for authentication [PLACEHOLDER]',
        'type': 'pwd',
        'section': 'network_storage',
        'required': False,
        'reboot': True,
        'depends': ['networkStorageEnabled', 'networkStorageProtocol!=local', 'networkStorageProtocol!=nfs'],
        'get': _get_network_storage_settings,
        'set': _set_network_storage_settings,
        'get_set_dict': True,
    }


@additional_config
def network_storage_separator():
    return {
        'type': 'separator',
        'section': 'network_storage',
        'depends': ['networkStorageEnabled'],
    }


@additional_config
def network_storage_failover():
    return {
        'label': 'Failover to Local',
        'description': 'automatically use local storage if network storage is unavailable [PLACEHOLDER]',
        'type': 'bool',
        'section': 'network_storage',
        'reboot': False,
        'depends': ['networkStorageEnabled'],
        'get': _get_network_storage_settings,
        'set': _set_network_storage_settings,
        'get_set_dict': True,
    }


@additional_config
def network_storage_test():
    return {
        'label': 'Test Connection',
        'description': 'test the network storage connection [PLACEHOLDER]',
        'type': 'html',
        'section': 'network_storage',
        'depends': ['networkStorageEnabled', 'networkStorageProtocol!=local'],
        'get': lambda: '<div class="button normal-button" id="networkStorageTestButton" style="opacity:0.5">Test [Not Implemented]</div>',
        'set': lambda x: None,
    }
