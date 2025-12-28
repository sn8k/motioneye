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
WiFi network management module for motionEye.

Supports both:
- NetworkManager (Raspberry Pi OS Bookworm / Debian 12+)
- dhcpcd (Raspberry Pi OS Bullseye and earlier)

The module auto-detects which network manager is in use.
"""

import logging
import os
import re
import shutil
import subprocess

from motioneye import settings
from motioneye.config import additional_config, additional_section

WPA_SUPPLICANT_CONF = settings.WPA_SUPPLICANT_CONF  # @UndefinedVariable

# Cache for WiFi interfaces and network manager type
_wifi_interfaces_cache = None
_network_manager_type = None  # 'networkmanager', 'dhcpcd', or None

# motionEye connection name prefix for NetworkManager
NM_CONNECTION_PREFIX = 'motioneye-wifi'


def _is_wifi_configurable():
    """
    Check if WiFi configuration is available.
    Returns True if NetworkManager or dhcpcd is available,
    OR if WPA_SUPPLICANT_CONF is configured in settings,
    OR if FORCE_NETWORK_SETTINGS is enabled.
    """
    # Always expose WiFi settings in the UI (backend logic still guards writes)
    return True


# ============================================================================
# Network Manager Detection
# ============================================================================

def _detect_network_manager():
    """
    Detect which network manager is in use.
    Returns: 'networkmanager', 'dhcpcd', or None
    """
    global _network_manager_type

    if _network_manager_type is not None:
        return _network_manager_type

    # Check for NetworkManager first (Raspberry Pi OS Bookworm+)
    if shutil.which('nmcli'):
        try:
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'RUNNING', 'general'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and 'running' in result.stdout.lower():
                _network_manager_type = 'networkmanager'
                logging.info('detected NetworkManager as network manager')
                return _network_manager_type
        except Exception as e:
            logging.debug(f'nmcli check failed: {e}')

    # Check for dhcpcd (older Raspberry Pi OS)
    if os.path.exists('/etc/dhcpcd.conf'):
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'dhcpcd'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and 'active' in result.stdout:
                _network_manager_type = 'dhcpcd'
                logging.info('detected dhcpcd as network manager')
                return _network_manager_type
        except Exception:
            # dhcpcd.conf exists but service check failed, still try dhcpcd
            if os.path.exists('/etc/dhcpcd.conf'):
                _network_manager_type = 'dhcpcd'
                logging.info('detected dhcpcd (fallback) as network manager')
                return _network_manager_type

    logging.warning('no supported network manager detected')
    _network_manager_type = None
    return None


# ============================================================================
# WiFi Interface Detection
# ============================================================================

def _detect_wifi_interfaces():
    """
    Detect available WiFi interfaces on the system.
    Returns a list of tuples: (interface_name, driver, is_available)
    """
    global _wifi_interfaces_cache

    interfaces = []

    try:
        # Method 1: Check /sys/class/net for wireless interfaces
        net_path = '/sys/class/net'
        if os.path.exists(net_path):
            for iface in os.listdir(net_path):
                wireless_path = os.path.join(net_path, iface, 'wireless')
                if os.path.exists(wireless_path):
                    # Get driver info
                    driver = 'unknown'
                    driver_path = os.path.join(net_path, iface, 'device', 'driver')
                    if os.path.exists(driver_path):
                        try:
                            driver = os.path.basename(os.readlink(driver_path))
                        except Exception:
                            pass

                    # Check if interface is available
                    operstate_path = os.path.join(net_path, iface, 'operstate')
                    is_available = True
                    if os.path.exists(operstate_path):
                        try:
                            with open(operstate_path) as f:
                                state = f.read().strip()
                                is_available = state not in ['notpresent']
                        except Exception:
                            pass

                    interfaces.append((iface, driver, is_available))
                    logging.debug(
                        f'detected WiFi interface: {iface} (driver: {driver}, available: {is_available})'
                    )

        # Method 2: Use iw if /sys method found nothing
        if not interfaces:
            try:
                result = subprocess.run(
                    ['iw', 'dev'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        m = re.match(r'\s*Interface\s+(\w+)', line)
                        if m:
                            iface = m.group(1)
                            interfaces.append((iface, 'unknown', True))
                            logging.debug(f'detected WiFi interface via iw: {iface}')
            except Exception as e:
                logging.debug(f'iw command failed: {e}')

        # Method 3: Use nmcli if available
        if not interfaces and shutil.which('nmcli'):
            try:
                result = subprocess.run(
                    ['nmcli', '-t', '-f', 'DEVICE,TYPE', 'device'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        parts = line.split(':')
                        if len(parts) >= 2 and parts[1] == 'wifi':
                            iface = parts[0]
                            interfaces.append((iface, 'unknown', True))
                            logging.debug(f'detected WiFi interface via nmcli: {iface}')
            except Exception as e:
                logging.debug(f'nmcli device check failed: {e}')

    except Exception as e:
        logging.error(f'error detecting WiFi interfaces: {e}')

    _wifi_interfaces_cache = interfaces
    return interfaces


def get_wifi_interface_choices():
    """
    Returns a list of choices for the UI dropdown.
    Format: [(value, label), ...]
    """
    interfaces = _detect_wifi_interfaces()
    choices = [('auto', 'Auto (automatic selection)')]

    for iface, driver, is_available in interfaces:
        status = '' if is_available else ' (unavailable)'
        label = f'{iface} ({driver}){status}'
        choices.append((iface, label))

    return choices


def _get_current_interface():
    """
    Get the currently active WiFi interface or the first available one.
    """
    interfaces = _detect_wifi_interfaces()
    available = [iface for iface, _, is_avail in interfaces if is_avail]
    return available[0] if available else None


# ============================================================================
# NetworkManager Functions (Raspberry Pi OS Bookworm+)
# ============================================================================

def _nm_get_wifi_connections():
    """
    Get WiFi connections configured via NetworkManager.
    Returns list of dicts with connection info.
    """
    connections = []

    try:
        # List all WiFi connections
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,TYPE,DEVICE,AUTOCONNECT-PRIORITY', 'connection', 'show'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return connections

        for line in result.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 2 and '802-11-wireless' in parts[1]:
                conn_name = parts[0]
                priority = int(parts[3]) if len(parts) > 3 and parts[3].lstrip('-').isdigit() else 0

                # Get connection details
                conn_info = _nm_get_connection_details(conn_name)
                if conn_info:
                    conn_info['priority'] = priority
                    connections.append(conn_info)

    except Exception as e:
        logging.error(f'error getting NetworkManager WiFi connections: {e}')

    return connections


def _nm_get_connection_details(conn_name):
    """
    Get detailed info for a NetworkManager connection.
    """
    try:
        result = subprocess.run(
            ['nmcli', '-t', '-s', 'connection', 'show', conn_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return None

        info = {'name': conn_name}

        for line in result.stdout.splitlines():
            if ':' not in line:
                continue

            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip()

            if key == '802-11-wireless.ssid':
                info['ssid'] = value
            elif key == '802-11-wireless-security.psk':
                info['psk'] = value
            elif key == 'ipv4.method':
                info['dhcp'] = (value == 'auto')
            elif key == 'ipv4.addresses':
                if value and value != '--':
                    # Format: "192.168.1.100/24"
                    ip_cidr = value.split()[0] if ' ' in value else value
                    if '/' in ip_cidr:
                        ip, cidr = ip_cidr.split('/')
                        info['ip_address'] = ip
                        info['netmask'] = _cidr_to_netmask(int(cidr))
            elif key == 'ipv4.gateway':
                if value and value != '--':
                    info['gateway'] = value
            elif key == 'ipv4.dns':
                if value and value != '--':
                    dns_list = value.replace(',', ' ').split()
                    if len(dns_list) >= 1:
                        info['dns1'] = dns_list[0]
                    if len(dns_list) >= 2:
                        info['dns2'] = dns_list[1]
            elif key == 'connection.interface-name':
                if value and value != '--':
                    info['interface'] = value

        return info

    except Exception as e:
        logging.debug(f'error getting connection details for {conn_name}: {e}')
        return None


def _nm_create_or_update_connection(ssid, psk, interface, priority, ip_config):
    """
    Create or update a NetworkManager WiFi connection.
    """
    conn_name = f'{NM_CONNECTION_PREFIX}-{ssid}'

    try:
        # Check if connection already exists
        result = subprocess.run(
            ['nmcli', 'connection', 'show', conn_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        exists = (result.returncode == 0)

        if exists:
            # Delete existing connection
            subprocess.run(
                ['nmcli', 'connection', 'delete', conn_name],
                capture_output=True,
                timeout=10
            )

        # Build nmcli command
        cmd = [
            'nmcli', 'connection', 'add',
            'type', 'wifi',
            'con-name', conn_name,
            'ssid', ssid,
            'autoconnect', 'yes',
            'connection.autoconnect-priority', str(priority),
        ]

        # Interface binding
        if interface and interface != 'auto':
            cmd.extend(['ifname', interface])
        else:
            cmd.extend(['ifname', '*'])

        # Security
        if psk:
            cmd.extend([
                'wifi-sec.key-mgmt', 'wpa-psk',
                'wifi-sec.psk', psk,
            ])

        # IP configuration
        if ip_config.get('wifiUseDhcp', True):
            cmd.extend(['ipv4.method', 'auto'])
        else:
            cmd.extend(['ipv4.method', 'manual'])

            ip = ip_config.get('wifiIpAddress', '')
            netmask = ip_config.get('wifiNetmask', '255.255.255.0')
            if ip:
                cidr = _netmask_to_cidr(netmask)
                cmd.extend(['ipv4.addresses', f'{ip}/{cidr}'])

            gateway = ip_config.get('wifiGateway', '')
            if gateway:
                cmd.extend(['ipv4.gateway', gateway])

            dns1 = ip_config.get('wifiDns1', '')
            dns2 = ip_config.get('wifiDns2', '')
            dns_servers = ','.join(filter(None, [dns1, dns2]))
            if dns_servers:
                cmd.extend(['ipv4.dns', dns_servers])

        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            logging.info(f'created/updated NetworkManager connection: {conn_name}')
            return True
        else:
            logging.error(f'failed to create NetworkManager connection: {result.stderr}')
            return False

    except Exception as e:
        logging.error(f'error creating NetworkManager connection: {e}')
        return False


def _nm_delete_motioneye_connections():
    """
    Delete all motionEye-managed WiFi connections from NetworkManager.
    """
    try:
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return

        for line in result.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 2:
                conn_name = parts[0]
                if conn_name.startswith(NM_CONNECTION_PREFIX):
                    subprocess.run(
                        ['nmcli', 'connection', 'delete', conn_name],
                        capture_output=True,
                        timeout=10
                    )
                    logging.debug(f'deleted NetworkManager connection: {conn_name}')

    except Exception as e:
        logging.error(f'error deleting NetworkManager connections: {e}')


def _nm_read_ip_config(interface):
    """
    Read current IP configuration from NetworkManager for an interface.
    """
    config = {
        'wifiUseDhcp': True,
        'wifiIpAddress': '',
        'wifiNetmask': '255.255.255.0',
        'wifiGateway': '',
        'wifiDns1': '',
        'wifiDns2': '',
    }

    if not interface:
        return config

    try:
        # Get active connection for interface
        result = subprocess.run(
            ['nmcli', '-t', '-f', 'NAME,DEVICE,TYPE', 'connection', 'show', '--active'],
            capture_output=True,
            text=True,
            timeout=10
        )

        active_conn = None
        for line in result.stdout.splitlines():
            parts = line.split(':')
            if len(parts) >= 3 and parts[1] == interface and '802-11-wireless' in parts[2]:
                active_conn = parts[0]
                break

        if active_conn:
            details = _nm_get_connection_details(active_conn)
            if details:
                config['wifiUseDhcp'] = details.get('dhcp', True)
                config['wifiIpAddress'] = details.get('ip_address', '')
                config['wifiNetmask'] = details.get('netmask', '255.255.255.0')
                config['wifiGateway'] = details.get('gateway', '')
                config['wifiDns1'] = details.get('dns1', '')
                config['wifiDns2'] = details.get('dns2', '')

    except Exception as e:
        logging.debug(f'error reading NetworkManager IP config: {e}')

    return config


# ============================================================================
# dhcpcd Functions (Raspberry Pi OS Bullseye and earlier)
# ============================================================================

def _dhcpcd_read_network_config(interface):
    """
    Read network configuration from dhcpcd.conf for a specific interface.
    """
    config = {
        'wifiUseDhcp': True,
        'wifiIpAddress': '',
        'wifiNetmask': '255.255.255.0',
        'wifiGateway': '',
        'wifiDns1': '',
        'wifiDns2': '',
    }

    if not interface:
        return config

    dhcpcd_conf = '/etc/dhcpcd.conf'
    if not os.path.exists(dhcpcd_conf):
        return config

    try:
        with open(dhcpcd_conf) as f:
            content = f.read()

        # Look for static IP configuration for this interface
        pattern = rf'interface\s+{re.escape(interface)}\s*\n(.*?)(?=\ninterface\s|\Z)'
        m = re.search(pattern, content, re.DOTALL)
        if m:
            block = m.group(1)

            # Check for static IP
            ip_match = re.search(r'static\s+ip_address\s*=\s*([\d.]+)(?:/(\d+))?', block)
            if ip_match:
                config['wifiUseDhcp'] = False
                config['wifiIpAddress'] = ip_match.group(1)
                if ip_match.group(2):
                    cidr = int(ip_match.group(2))
                    config['wifiNetmask'] = _cidr_to_netmask(cidr)

            # Gateway
            gw_match = re.search(r'static\s+routers\s*=\s*([\d.]+)', block)
            if gw_match:
                config['wifiGateway'] = gw_match.group(1)

            # DNS
            dns_match = re.search(r'static\s+domain_name_servers\s*=\s*([\d.\s]+)', block)
            if dns_match:
                dns_servers = dns_match.group(1).split()
                if len(dns_servers) >= 1:
                    config['wifiDns1'] = dns_servers[0]
                if len(dns_servers) >= 2:
                    config['wifiDns2'] = dns_servers[1]

    except Exception as e:
        logging.debug(f'error reading dhcpcd.conf: {e}')

    return config


def _dhcpcd_write_network_config(interface, config):
    """
    Write network configuration to dhcpcd.conf for a specific interface.
    """
    if not interface:
        logging.warning('no WiFi interface specified for network config')
        return

    dhcpcd_conf = '/etc/dhcpcd.conf'
    if not os.path.exists(dhcpcd_conf):
        logging.warning(f'{dhcpcd_conf} does not exist, cannot configure static IP')
        return

    try:
        with open(dhcpcd_conf) as f:
            lines = f.readlines()

        # Remove existing configuration for this interface
        new_lines = []
        skip_block = False
        for line in lines:
            stripped = line.strip()
            if re.match(rf'interface\s+{re.escape(interface)}\s*$', stripped):
                skip_block = True
                continue
            if skip_block and re.match(r'interface\s+\w+', stripped):
                skip_block = False
            if skip_block and stripped and not stripped.startswith('#'):
                continue
            if skip_block and not stripped:
                skip_block = False
            new_lines.append(line)

        # Add new configuration if using static IP
        if not config.get('wifiUseDhcp', True):
            new_lines.append(f'\ninterface {interface}\n')

            ip = config.get('wifiIpAddress', '')
            netmask = config.get('wifiNetmask', '255.255.255.0')
            if ip:
                cidr = _netmask_to_cidr(netmask)
                new_lines.append(f'static ip_address={ip}/{cidr}\n')

            gateway = config.get('wifiGateway', '')
            if gateway:
                new_lines.append(f'static routers={gateway}\n')

            dns1 = config.get('wifiDns1', '')
            dns2 = config.get('wifiDns2', '')
            dns_servers = ' '.join(filter(None, [dns1, dns2]))
            if dns_servers:
                new_lines.append(f'static domain_name_servers={dns_servers}\n')

        with open(dhcpcd_conf, 'w') as f:
            f.writelines(new_lines)

        logging.info(f'updated dhcpcd.conf for {interface}')

    except Exception as e:
        logging.error(f'error writing to dhcpcd.conf: {e}')


# ============================================================================
# wpa_supplicant Functions (used by dhcpcd systems)
# ============================================================================

def _wpa_read_networks():
    """
    Read networks from wpa_supplicant.conf.
    Returns list of dicts with network info.
    """
    networks = []

    if not WPA_SUPPLICANT_CONF or not os.path.exists(WPA_SUPPLICANT_CONF):
        return networks

    try:
        with open(WPA_SUPPLICANT_CONF) as f:
            lines = f.readlines()

        current_network = {}
        in_section = False

        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                continue

            if line.startswith('network=') or line == 'network={':
                in_section = True
                current_network = {'priority': 0}

            elif line.startswith('}') and in_section:
                in_section = False
                if current_network.get('ssid'):
                    networks.append(current_network)
                current_network = {}

            elif in_section:
                m = re.search(r'ssid\s*=\s*"(.*?)"', line)
                if m:
                    current_network['ssid'] = m.group(1)

                m = re.search(r'psk\s*=\s*"?([^"]*)"?', line)
                if m:
                    current_network['psk'] = m.group(1)

                m = re.search(r'priority\s*=\s*(\d+)', line)
                if m:
                    current_network['priority'] = int(m.group(1))

        # Sort by priority (higher = preferred)
        networks.sort(key=lambda x: x.get('priority', 0), reverse=True)

    except Exception as e:
        logging.error(f'error reading wpa_supplicant.conf: {e}')

    return networks


def _wpa_read_motioneye_config():
    """
    Read motionEye-specific configuration from wpa_supplicant.conf comments.
    """
    config = {
        'interface': 'auto',
        'interface_fallback': '',
    }

    if not WPA_SUPPLICANT_CONF or not os.path.exists(WPA_SUPPLICANT_CONF):
        return config

    try:
        with open(WPA_SUPPLICANT_CONF) as f:
            for line in f:
                m = re.search(r'#\s*motioneye_interface\s*=\s*(\S+)', line)
                if m:
                    config['interface'] = m.group(1)

                m = re.search(r'#\s*motioneye_interface_fallback\s*=\s*(\S+)', line)
                if m:
                    config['interface_fallback'] = m.group(1)

    except Exception as e:
        logging.debug(f'error reading motioneye config from wpa_supplicant.conf: {e}')

    return config


def _wpa_write_config(settings_dict):
    """
    Write WiFi configuration to wpa_supplicant.conf.
    """
    if not _is_wifi_configurable():
        return

    try:
        # Read existing file, preserving header
        header_lines = []
        if os.path.exists(WPA_SUPPLICANT_CONF):
            with open(WPA_SUPPLICANT_CONF) as f:
                in_network = False
                for line in f:
                    stripped = line.strip()

                    if stripped.startswith('network=') or stripped == 'network={':
                        in_network = True
                        continue
                    if in_network:
                        if stripped == '}':
                            in_network = False
                        continue
                    if stripped.startswith('# motioneye_'):
                        continue

                    header_lines.append(line)

        # Remove trailing empty lines from header
        while header_lines and not header_lines[-1].strip():
            header_lines.pop()

        # Build new content
        new_lines = header_lines[:]

        # Add motioneye config comments
        new_lines.append(f'\n# motioneye_interface={settings_dict["wifiInterface"]}\n')
        if settings_dict.get('wifiInterfaceFallback'):
            new_lines.append(f'# motioneye_interface_fallback={settings_dict["wifiInterfaceFallback"]}\n')

        # Add networks if enabled
        if settings_dict.get('wifiEnabled') and settings_dict.get('wifiNetworkName'):
            new_lines.append('\n')
            new_lines.append(_create_wpa_network_block(
                ssid=settings_dict['wifiNetworkName'],
                psk=settings_dict.get('wifiNetworkKey', ''),
                priority=10
            ))

        if settings_dict.get('wifiEnabled') and settings_dict.get('wifiNetworkFallback'):
            new_lines.append('\n')
            new_lines.append(_create_wpa_network_block(
                ssid=settings_dict['wifiNetworkFallback'],
                psk=settings_dict.get('wifiNetworkKeyFallback', ''),
                priority=5
            ))

        # Write file
        with open(WPA_SUPPLICANT_CONF, 'w') as f:
            f.writelines(new_lines)

        logging.info(f'wifi settings saved to {WPA_SUPPLICANT_CONF}')

    except Exception as e:
        logging.error(f'error writing wpa_supplicant.conf: {e}')


def _create_wpa_network_block(ssid, psk, priority=0):
    """
    Create a wpa_supplicant network block.
    """
    psk_is_hex = psk and re.match('^[a-f0-9]{64}$', psk, re.I) is not None
    key_mgmt = 'NONE' if not psk else None

    block = 'network={\n'
    block += '    scan_ssid=1\n'
    block += f'    ssid="{ssid}"\n'

    if psk:
        if psk_is_hex:
            block += f'    psk={psk}\n'
        else:
            block += f'    psk="{psk}"\n'

    if key_mgmt:
        block += f'    key_mgmt={key_mgmt}\n'

    if priority > 0:
        block += f'    priority={priority}\n'

    block += '}\n'
    return block


# ============================================================================
# Utility Functions
# ============================================================================

def _cidr_to_netmask(cidr):
    """Convert CIDR notation to netmask."""
    mask = (0xFFFFFFFF >> (32 - cidr)) << (32 - cidr)
    return '.'.join([str((mask >> (8 * i)) & 0xFF) for i in range(3, -1, -1)])


def _netmask_to_cidr(netmask):
    """Convert netmask to CIDR notation."""
    try:
        parts = [int(x) for x in netmask.split('.')]
        binary = ''.join([bin(x)[2:].zfill(8) for x in parts])
        return str(binary.count('1'))
    except Exception:
        return '24'


# ============================================================================
# Main Get/Set Functions
# ============================================================================

def _get_wifi_settings():
    """
    Get WiFi settings. Auto-detects and uses appropriate network manager.
    """
    settings_dict = {
        'wifiEnabled': False,
        'wifiInterface': 'auto',
        'wifiInterfaceFallback': '',
        'wifiNetworkName': '',
        'wifiNetworkKey': '',
        'wifiNetworkFallback': '',
        'wifiNetworkKeyFallback': '',
        'wifiUseDhcp': True,
        'wifiIpAddress': '',
        'wifiNetmask': '255.255.255.0',
        'wifiGateway': '',
        'wifiDns1': '',
        'wifiDns2': '',
    }

    if not _is_wifi_configurable():
        return settings_dict

    nm_type = _detect_network_manager()
    logging.debug(f'reading wifi settings (network manager: {nm_type})')

    if nm_type == 'networkmanager':
        # Read from NetworkManager
        connections = _nm_get_wifi_connections()

        # Filter to motioneye-managed connections
        me_connections = [c for c in connections if c.get('name', '').startswith(NM_CONNECTION_PREFIX)]

        if me_connections:
            # Sort by priority
            me_connections.sort(key=lambda x: x.get('priority', 0), reverse=True)

            settings_dict['wifiEnabled'] = True
            settings_dict['wifiNetworkName'] = me_connections[0].get('ssid', '')
            settings_dict['wifiNetworkKey'] = me_connections[0].get('psk', '')
            settings_dict['wifiInterface'] = me_connections[0].get('interface', 'auto') or 'auto'

            if len(me_connections) > 1:
                settings_dict['wifiNetworkFallback'] = me_connections[1].get('ssid', '')
                settings_dict['wifiNetworkKeyFallback'] = me_connections[1].get('psk', '')

        # Read interface config from wpa_supplicant comments (fallback interface)
        me_config = _wpa_read_motioneye_config()
        if me_config.get('interface_fallback'):
            settings_dict['wifiInterfaceFallback'] = me_config['interface_fallback']

        # Read IP config
        current_iface = settings_dict['wifiInterface']
        if current_iface == 'auto':
            current_iface = _get_current_interface()
        if current_iface:
            ip_config = _nm_read_ip_config(current_iface)
            settings_dict.update(ip_config)

    else:
        # Read from wpa_supplicant.conf (dhcpcd or fallback)
        networks = _wpa_read_networks()

        if networks:
            settings_dict['wifiEnabled'] = True
            settings_dict['wifiNetworkName'] = networks[0].get('ssid', '')
            settings_dict['wifiNetworkKey'] = networks[0].get('psk', '')

            if len(networks) > 1:
                settings_dict['wifiNetworkFallback'] = networks[1].get('ssid', '')
                settings_dict['wifiNetworkKeyFallback'] = networks[1].get('psk', '')

        # Read motioneye config
        me_config = _wpa_read_motioneye_config()
        settings_dict['wifiInterface'] = me_config.get('interface', 'auto')
        settings_dict['wifiInterfaceFallback'] = me_config.get('interface_fallback', '')

        # Read IP config from dhcpcd
        current_iface = settings_dict['wifiInterface']
        if current_iface == 'auto':
            current_iface = _get_current_interface()
        if current_iface:
            ip_config = _dhcpcd_read_network_config(current_iface)
            settings_dict.update(ip_config)

    logging.debug(f"wifi enabled: {settings_dict['wifiEnabled']}, ssid: {settings_dict['wifiNetworkName']}")
    return settings_dict


def _set_wifi_settings(s):
    """
    Set WiFi settings. Auto-detects and uses appropriate network manager.
    """
    s.setdefault('wifiEnabled', False)
    s.setdefault('wifiInterface', 'auto')
    s.setdefault('wifiInterfaceFallback', '')
    s.setdefault('wifiNetworkName', '')
    s.setdefault('wifiNetworkKey', '')
    s.setdefault('wifiNetworkFallback', '')
    s.setdefault('wifiNetworkKeyFallback', '')
    s.setdefault('wifiUseDhcp', True)
    s.setdefault('wifiIpAddress', '')
    s.setdefault('wifiNetmask', '255.255.255.0')
    s.setdefault('wifiGateway', '')
    s.setdefault('wifiDns1', '')
    s.setdefault('wifiDns2', '')

    if not _is_wifi_configurable():
        return

    nm_type = _detect_network_manager()
    logging.debug(
        f'writing wifi settings (network manager: {nm_type}): '
        f'enabled={s["wifiEnabled"]}, interface={s["wifiInterface"]}, ssid="{s["wifiNetworkName"]}"'
    )

    if nm_type == 'networkmanager':
        # Delete existing motionEye connections
        _nm_delete_motioneye_connections()

        # Create new connections if enabled
        if s['wifiEnabled'] and s['wifiNetworkName']:
            _nm_create_or_update_connection(
                ssid=s['wifiNetworkName'],
                psk=s.get('wifiNetworkKey', ''),
                interface=s['wifiInterface'],
                priority=10,
                ip_config=s
            )

        if s['wifiEnabled'] and s.get('wifiNetworkFallback'):
            # Fallback network uses same IP config but lower priority
            _nm_create_or_update_connection(
                ssid=s['wifiNetworkFallback'],
                psk=s.get('wifiNetworkKeyFallback', ''),
                interface=s['wifiInterface'],
                priority=5,
                ip_config=s
            )

        # Also write to wpa_supplicant.conf for interface fallback config
        _wpa_write_config(s)

    else:
        # Write to wpa_supplicant.conf
        _wpa_write_config(s)

        # Write IP config to dhcpcd.conf
        interface = s['wifiInterface']
        if interface == 'auto':
            interface = _get_current_interface()
        if interface:
            _dhcpcd_write_network_config(interface, s)


# ============================================================================
# Additional Config Definitions for UI
# ============================================================================

@additional_section
def network():
    return {
        'label': 'Network',
        'description': 'configure the wireless network connection',
    }


@additional_config
def wifi_enabled():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Wireless Network',
        'description': 'enable this if you want to connect to a wireless network',
        'type': 'bool',
        'section': 'network',
        'reboot': True,
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_interface():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'WiFi Interface',
        'description': 'the wireless network interface to use (auto will select the first available)',
        'type': 'choices',
        'choices': get_wifi_interface_choices(),
        'section': 'network',
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_interface_fallback():
    if not _is_wifi_configurable():
        return None

    choices = get_wifi_interface_choices()
    # Add empty option at the start
    choices = [('', '(none)')] + choices[1:]  # Remove 'auto' and add 'none'

    return {
        'label': 'Fallback Interface',
        'description': 'secondary interface to use if the primary is unavailable',
        'type': 'choices',
        'choices': choices,
        'section': 'network',
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_network_name():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Network Name (SSID)',
        'description': 'the name (SSID) of your wireless network',
        'type': 'str',
        'section': 'network',
        'required': True,
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_network_key():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Network Key (PSK)',
        'description': 'the key (password) required to connect to your wireless network',
        'type': 'pwd',
        'section': 'network',
        'required': False,
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_separator_fallback():
    if not _is_wifi_configurable():
        return None

    return {
        'type': 'separator',
        'section': 'network',
        'depends': ['wifiEnabled'],
    }


@additional_config
def wifi_network_fallback():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Fallback Network (SSID)',
        'description': 'secondary network to connect to if the primary is unavailable',
        'type': 'str',
        'section': 'network',
        'required': False,
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_network_key_fallback():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Fallback Network Key',
        'description': 'the key (password) for the fallback wireless network',
        'type': 'pwd',
        'section': 'network',
        'required': False,
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_separator_ip():
    if not _is_wifi_configurable():
        return None

    return {
        'type': 'separator',
        'section': 'network',
        'depends': ['wifiEnabled'],
    }


@additional_config
def wifi_use_dhcp():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Use DHCP',
        'description': 'obtain IP address automatically from DHCP server',
        'type': 'bool',
        'section': 'network',
        'reboot': True,
        'depends': ['wifiEnabled'],
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_ip_address():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'IP Address',
        'description': 'static IP address (e.g. 192.168.1.100)',
        'type': 'str',
        'section': 'network',
        'required': True,
        'reboot': True,
        'depends': ['wifiEnabled', '!wifiUseDhcp'],
        'validate': 'ip',
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_netmask():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Netmask',
        'description': 'network mask (e.g. 255.255.255.0)',
        'type': 'str',
        'section': 'network',
        'required': True,
        'reboot': True,
        'depends': ['wifiEnabled', '!wifiUseDhcp'],
        'validate': 'ip',
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_gateway():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'Gateway',
        'description': 'default gateway IP address (e.g. 192.168.1.1)',
        'type': 'str',
        'section': 'network',
        'required': False,
        'reboot': True,
        'depends': ['wifiEnabled', '!wifiUseDhcp'],
        'validate': 'ip',
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_dns1():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'DNS Server 1',
        'description': 'primary DNS server IP address',
        'type': 'str',
        'section': 'network',
        'required': False,
        'reboot': True,
        'depends': ['wifiEnabled', '!wifiUseDhcp'],
        'validate': 'ip',
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }


@additional_config
def wifi_dns2():
    if not _is_wifi_configurable():
        return None

    return {
        'label': 'DNS Server 2',
        'description': 'secondary DNS server IP address',
        'type': 'str',
        'section': 'network',
        'required': False,
        'reboot': True,
        'depends': ['wifiEnabled', '!wifiUseDhcp'],
        'validate': 'ip',
        'get': _get_wifi_settings,
        'set': _set_wifi_settings,
        'get_set_dict': True,
    }
