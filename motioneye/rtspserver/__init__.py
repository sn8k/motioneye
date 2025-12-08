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

"""RTSP server package for motionEye.

This package provides a complete RTSP server implementation compatible with
Synology Surveillance Station and other standard RTSP clients. It supports
both video (H.264) and audio (AAC/G.711) streaming over RTP/RTCP.

Features:
- RFC 2326 compliant RTSP server
- RFC 3550 RTP/RTCP transport
- RFC 6184 H.264 video packetization
- G.711 μ-law and AAC audio support
- Both UDP and TCP (interleaved) transport modes
- Basic authentication support
- Compatible with Synology Surveillance Station
"""

# Core components (no external dependencies)
from motioneye.rtspserver.server import RTSPServer, StreamConfig
from motioneye.rtspserver.session import RTSPSession, SessionManager
from motioneye.rtspserver.rtp import RTPPacketizer, H264Packetizer, AudioPacketizer
from motioneye.rtspserver.sdp import SDPGenerator


def start():
    """Start the RTSP server (lazy import to avoid circular dependencies)."""
    from motioneye.rtspserver import integration
    integration.start()


def stop():
    """Stop the RTSP server."""
    from motioneye.rtspserver import integration
    integration.stop()


def restart():
    """Restart the RTSP server."""
    from motioneye.rtspserver import integration
    integration.restart()


def is_running():
    """Check if RTSP server is running."""
    from motioneye.rtspserver import integration
    return integration.is_running()


def get_stream_urls():
    """Get RTSP stream URLs."""
    from motioneye.rtspserver import integration
    return integration.get_stream_urls()


__all__ = [
    'RTSPServer',
    'StreamConfig',
    'RTSPSession',
    'SessionManager',
    'RTPPacketizer',
    'H264Packetizer',
    'AudioPacketizer',
    'SDPGenerator',
    'start',
    'stop',
    'restart',
    'is_running',
    'get_stream_urls',
]
