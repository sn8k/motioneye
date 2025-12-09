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

"""RTSP Session management."""

import logging
import random
import time
import socket
import struct
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List, Callable
from dataclasses import dataclass, field

from motioneye.rtspserver.rtp import (
    RTPPacket, H264Packetizer, AudioPacketizer, RTCPPacket, get_ntp_timestamp
)


class SessionState(Enum):
    """RTSP session states."""
    INIT = "init"
    READY = "ready"
    PLAYING = "playing"
    RECORDING = "recording"


class TransportMode(Enum):
    """RTP transport modes."""
    UDP = "udp"
    TCP = "tcp"  # Interleaved
    MULTICAST = "multicast"


@dataclass
class RTPChannel:
    """RTP channel configuration for a single media stream."""
    track_id: int
    media_type: str  # "video" or "audio"
    transport_mode: TransportMode = TransportMode.UDP
    
    # UDP transport
    client_rtp_port: int = 0
    client_rtcp_port: int = 0
    server_rtp_port: int = 0
    server_rtcp_port: int = 0
    rtp_socket: Optional[socket.socket] = None
    rtcp_socket: Optional[socket.socket] = None
    
    # TCP interleaved transport
    rtp_channel: int = 0
    rtcp_channel: int = 1
    
    # Client address for UDP
    client_address: str = ""
    
    # Statistics
    packets_sent: int = 0
    bytes_sent: int = 0
    
    def cleanup(self):
        """Clean up sockets."""
        if self.rtp_socket:
            try:
                self.rtp_socket.close()
            except Exception:
                pass
            self.rtp_socket = None
        if self.rtcp_socket:
            try:
                self.rtcp_socket.close()
            except Exception:
                pass
            self.rtcp_socket = None


@dataclass
class RTSPSession:
    """Represents an RTSP client session."""
    session_id: str
    client_address: Tuple[str, int]
    state: SessionState = SessionState.INIT
    
    # Channel configurations by track ID
    channels: Dict[int, RTPChannel] = field(default_factory=dict)
    
    # Video and audio packetizers
    video_packetizer: Optional[H264Packetizer] = None
    audio_packetizer: Optional[AudioPacketizer] = None
    
    # Session timing
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    timeout: float = 60.0  # Session timeout in seconds
    
    # Stream URL this session is connected to
    stream_url: str = ""
    
    # TCP connection for interleaved mode
    tcp_writer: Optional[Callable[[bytes], None]] = None
    
    @staticmethod
    def generate_session_id() -> str:
        """Generate a random session ID."""
        return f"{random.randint(10000000, 99999999)}"
    
    def touch(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
        
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return (time.time() - self.last_activity) > self.timeout
    
    def setup_video_channel(
        self,
        track_id: int,
        transport_mode: TransportMode,
        client_rtp_port: int = 0,
        client_rtcp_port: int = 0,
        rtp_channel: int = 0,
        rtcp_channel: int = 1,
    ) -> RTPChannel:
        """Set up a video RTP channel.
        
        Args:
            track_id: Track identifier
            transport_mode: UDP or TCP transport
            client_rtp_port: Client RTP port for UDP
            client_rtcp_port: Client RTCP port for UDP
            rtp_channel: Interleaved channel for TCP
            rtcp_channel: RTCP interleaved channel for TCP
            
        Returns:
            Configured RTP channel
        """
        channel = RTPChannel(
            track_id=track_id,
            media_type="video",
            transport_mode=transport_mode,
            client_rtp_port=client_rtp_port,
            client_rtcp_port=client_rtcp_port,
            rtp_channel=rtp_channel,
            rtcp_channel=rtcp_channel,
            client_address=self.client_address[0],
        )
        
        if transport_mode == TransportMode.UDP:
            # Create UDP sockets
            channel.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            channel.rtp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            channel.rtp_socket.bind(('', 0))
            channel.server_rtp_port = channel.rtp_socket.getsockname()[1]
            
            channel.rtcp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            channel.rtcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            channel.rtcp_socket.bind(('', 0))
            channel.server_rtcp_port = channel.rtcp_socket.getsockname()[1]
            
        # Create video packetizer
        if not self.video_packetizer:
            self.video_packetizer = H264Packetizer()
            
        self.channels[track_id] = channel
        return channel
    
    def setup_audio_channel(
        self,
        track_id: int,
        transport_mode: TransportMode,
        client_rtp_port: int = 0,
        client_rtcp_port: int = 0,
        rtp_channel: int = 2,
        rtcp_channel: int = 3,
        payload_type: int = 0,
        clock_rate: int = 8000,
    ) -> RTPChannel:
        """Set up an audio RTP channel.
        
        Args:
            track_id: Track identifier
            transport_mode: UDP or TCP transport
            client_rtp_port: Client RTP port for UDP
            client_rtcp_port: Client RTCP port for UDP
            rtp_channel: Interleaved channel for TCP
            rtcp_channel: RTCP interleaved channel for TCP
            payload_type: RTP payload type
            clock_rate: Audio clock rate
            
        Returns:
            Configured RTP channel
        """
        channel = RTPChannel(
            track_id=track_id,
            media_type="audio",
            transport_mode=transport_mode,
            client_rtp_port=client_rtp_port,
            client_rtcp_port=client_rtcp_port,
            rtp_channel=rtp_channel,
            rtcp_channel=rtcp_channel,
            client_address=self.client_address[0],
        )
        
        if transport_mode == TransportMode.UDP:
            # Create UDP sockets
            channel.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            channel.rtp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            channel.rtp_socket.bind(('', 0))
            channel.server_rtp_port = channel.rtp_socket.getsockname()[1]
            
            channel.rtcp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            channel.rtcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            channel.rtcp_socket.bind(('', 0))
            channel.server_rtcp_port = channel.rtcp_socket.getsockname()[1]
            
        # Create audio packetizer
        if not self.audio_packetizer:
            self.audio_packetizer = AudioPacketizer(
                payload_type=payload_type,
                clock_rate=clock_rate,
            )
            
        self.channels[track_id] = channel
        return channel
    
    def send_video_frame(self, frame_data: bytes, timestamp: Optional[int] = None) -> int:
        """Send a video frame to the client.
        
        Args:
            frame_data: H.264 frame data (with start codes)
            timestamp: RTP timestamp (auto-generated if None)
            
        Returns:
            Number of packets sent
        """
        if not self.video_packetizer:
            logging.debug(f"Session {self.session_id}: no video_packetizer")
            return 0
            
        if self.state != SessionState.PLAYING:
            logging.debug(f"Session {self.session_id}: state is {self.state}, not PLAYING")
            return 0
            
        # Find video channel
        video_channel = None
        for channel in self.channels.values():
            if channel.media_type == "video":
                video_channel = channel
                break
                
        if not video_channel:
            logging.debug(f"Session {self.session_id}: no video channel configured")
            return 0
            
        packets_sent = 0
        for packet in self.video_packetizer.packetize_frame(frame_data, timestamp):
            self._send_rtp_packet(video_channel, packet)
            packets_sent += 1
            
        return packets_sent
    
    def send_audio_samples(
        self,
        audio_data: bytes,
        timestamp: Optional[int] = None,
        is_aac: bool = False,
    ) -> int:
        """Send audio samples to the client.
        
        Args:
            audio_data: Audio sample data
            timestamp: RTP timestamp (auto-generated if None)
            is_aac: True for AAC audio, False for PCM
            
        Returns:
            Number of packets sent
        """
        if not self.audio_packetizer or self.state != SessionState.PLAYING:
            return 0
            
        # Find audio channel
        audio_channel = None
        for channel in self.channels.values():
            if channel.media_type == "audio":
                audio_channel = channel
                break
                
        if not audio_channel:
            return 0
            
        packets_sent = 0
        if is_aac:
            generator = self.audio_packetizer.packetize_aac(audio_data, timestamp)
        else:
            generator = self.audio_packetizer.packetize_pcm(audio_data, timestamp)
            
        for packet in generator:
            self._send_rtp_packet(audio_channel, packet)
            packets_sent += 1
            
        return packets_sent
    
    def _send_rtp_packet(self, channel: RTPChannel, packet: RTPPacket):
        """Send an RTP packet via the appropriate transport.
        
        Args:
            channel: RTP channel configuration
            packet: RTP packet to send
        """
        packet_data = packet.to_bytes()
        
        if channel.transport_mode == TransportMode.TCP:
            # Interleaved mode - wrap in $ framing
            if self.tcp_writer:
                interleaved = bytes([0x24, channel.rtp_channel]) + \
                             struct.pack('!H', len(packet_data)) + packet_data
                try:
                    self.tcp_writer(interleaved)
                    channel.packets_sent += 1
                    channel.bytes_sent += len(packet_data)
                except Exception as e:
                    logging.debug(f"Failed to send interleaved RTP: {e}")
        else:
            # UDP mode
            if channel.rtp_socket and channel.client_rtp_port:
                try:
                    channel.rtp_socket.sendto(
                        packet_data,
                        (channel.client_address, channel.client_rtp_port)
                    )
                    channel.packets_sent += 1
                    channel.bytes_sent += len(packet_data)
                except Exception as e:
                    logging.debug(f"Failed to send UDP RTP: {e}")
                    
    def send_rtcp_sr(self, channel: RTPChannel):
        """Send RTCP Sender Report for a channel.
        
        Args:
            channel: RTP channel to report on
        """
        packetizer = self.video_packetizer if channel.media_type == "video" \
                    else self.audio_packetizer
        if not packetizer:
            return
            
        ntp_ts = get_ntp_timestamp()
        rtp_ts = packetizer.get_timestamp()
        
        sr = RTCPPacket.build_sender_report(
            ssrc=packetizer.ssrc,
            ntp_timestamp=ntp_ts,
            rtp_timestamp=rtp_ts,
            packet_count=channel.packets_sent,
            octet_count=channel.bytes_sent,
        )
        
        if channel.transport_mode == TransportMode.TCP:
            if self.tcp_writer:
                interleaved = bytes([0x24, channel.rtcp_channel]) + \
                             struct.pack('!H', len(sr)) + sr
                try:
                    self.tcp_writer(interleaved)
                except Exception as e:
                    logging.debug(f"Failed to send interleaved RTCP: {e}")
        else:
            if channel.rtcp_socket and channel.client_rtcp_port:
                try:
                    channel.rtcp_socket.sendto(
                        sr,
                        (channel.client_address, channel.client_rtcp_port)
                    )
                except Exception as e:
                    logging.debug(f"Failed to send UDP RTCP: {e}")
                    
    def play(self):
        """Transition to PLAYING state."""
        if self.state in (SessionState.INIT, SessionState.READY):
            self.state = SessionState.PLAYING
            logging.debug(f"Session {self.session_id} now PLAYING")
            
    def pause(self):
        """Transition to READY state."""
        if self.state == SessionState.PLAYING:
            self.state = SessionState.READY
            logging.debug(f"Session {self.session_id} now READY (paused)")
            
    def teardown(self):
        """Clean up session resources."""
        for channel in self.channels.values():
            channel.cleanup()
        self.channels.clear()
        self.state = SessionState.INIT
        logging.debug(f"Session {self.session_id} torn down")


class SessionManager:
    """Manages RTSP sessions."""
    
    def __init__(self, timeout: float = 60.0):
        """Initialize session manager.
        
        Args:
            timeout: Default session timeout in seconds
        """
        self.sessions: Dict[str, RTSPSession] = {}
        self.timeout = timeout
        
    def create_session(self, client_address: Tuple[str, int]) -> RTSPSession:
        """Create a new session.
        
        Args:
            client_address: Client (IP, port) tuple
            
        Returns:
            New RTSP session
        """
        session_id = RTSPSession.generate_session_id()
        while session_id in self.sessions:
            session_id = RTSPSession.generate_session_id()
            
        session = RTSPSession(
            session_id=session_id,
            client_address=client_address,
            timeout=self.timeout,
        )
        self.sessions[session_id] = session
        logging.info(f"Created session {session_id} for {client_address}")
        return session
    
    def get_session(self, session_id: str) -> Optional[RTSPSession]:
        """Get a session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session or None if not found
        """
        session = self.sessions.get(session_id)
        if session:
            session.touch()
        return session
    
    def remove_session(self, session_id: str):
        """Remove a session.
        
        Args:
            session_id: Session identifier
        """
        session = self.sessions.pop(session_id, None)
        if session:
            session.teardown()
            logging.info(f"Removed session {session_id}")
            
    def cleanup_expired(self) -> List[str]:
        """Remove expired sessions.
        
        Returns:
            List of removed session IDs
        """
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired()
        ]
        for sid in expired:
            self.remove_session(sid)
        return expired
    
    def get_playing_sessions(self) -> List[RTSPSession]:
        """Get all sessions in PLAYING state.
        
        Returns:
            List of playing sessions
        """
        return [
            session for session in self.sessions.values()
            if session.state == SessionState.PLAYING
        ]
    
    def broadcast_video_frame(self, stream_id: str, frame_data: bytes):
        """Broadcast a video frame to all playing sessions on a stream.
        
        Args:
            stream_id: Stream identifier to broadcast to
            frame_data: H.264 frame data
        """
        sessions = self.get_playing_sessions()
        if not sessions:
            # No logging here - this is normal when no clients connected
            return
            
        sent_count = 0
        for session in sessions:
            # Match stream_url (may contain full path) with stream_id
            session_stream = session.stream_url.strip('/').split('/')[0] if session.stream_url else ''
            if session_stream == stream_id or stream_id in session.stream_url or not stream_id:
                try:
                    packets = session.send_video_frame(frame_data)
                    if packets > 0:
                        sent_count += 1
                except Exception as e:
                    logging.debug(f"Error sending video to session {session.session_id}: {e}")
                    
        if sent_count > 0 and hasattr(self, '_video_frame_count'):
            self._video_frame_count = getattr(self, '_video_frame_count', 0) + 1
            if self._video_frame_count % 100 == 0:
                logging.debug(f"Broadcast {self._video_frame_count} video frames to {sent_count} sessions")
        elif not hasattr(self, '_video_frame_count'):
            self._video_frame_count = 1
                
    def broadcast_audio_samples(
        self,
        stream_id: str,
        audio_data: bytes,
        is_aac: bool = False,
    ):
        """Broadcast audio samples to all playing sessions on a stream.
        
        Args:
            stream_id: Stream identifier to broadcast to
            audio_data: Audio sample data
            is_aac: True for AAC, False for PCM
        """
        sessions = self.get_playing_sessions()
        for session in sessions:
            session_stream = session.stream_url.strip('/').split('/')[0] if session.stream_url else ''
            if session_stream == stream_id or stream_id in session.stream_url or not stream_id:
                try:
                    session.send_audio_samples(audio_data, is_aac=is_aac)
                except Exception as e:
                    logging.debug(f"Error sending audio to session {session.session_id}: {e}")
