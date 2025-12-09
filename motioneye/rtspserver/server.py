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

"""RTSP Server implementation for motionEye.

This module provides a complete RTSP server compatible with Synology
Surveillance Station and other standard RTSP clients. It implements
RFC 2326 (RTSP) and supports both UDP and TCP (interleaved) transport.
"""

import asyncio
import base64
import hashlib
import logging
import re
import socket
import struct
from typing import Optional, Dict, Tuple, Callable, Any, List
from dataclasses import dataclass, field
from urllib.parse import urlparse, unquote

from motioneye.rtspserver.protocol import (
    RTSP_VERSION, RTSPStatusCode, get_status_phrase,
    parse_transport_header, build_transport_header,
    PAYLOAD_TYPE_H264, PAYLOAD_TYPE_PCMU, PAYLOAD_TYPE_AAC,
)
from motioneye.rtspserver.sdp import SDPGenerator
from motioneye.rtspserver.session import (
    RTSPSession, SessionManager, SessionState, TransportMode, RTPChannel
)


@dataclass
class RTSPRequest:
    """Parsed RTSP request."""
    method: str
    uri: str
    version: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b''
    
    @classmethod
    def parse(cls, data: bytes) -> Optional['RTSPRequest']:
        """Parse an RTSP request from bytes.
        
        Args:
            data: Raw request data
            
        Returns:
            Parsed request or None if invalid
        """
        try:
            # Split headers and body
            if b'\r\n\r\n' in data:
                header_part, body = data.split(b'\r\n\r\n', 1)
            else:
                header_part = data
                body = b''
                
            lines = header_part.decode('utf-8').split('\r\n')
            if not lines:
                return None
                
            # Parse request line
            request_line = lines[0].split(' ')
            if len(request_line) < 3:
                return None
                
            method = request_line[0]
            uri = request_line[1]
            version = request_line[2]
            
            # Parse headers
            headers = {}
            for line in lines[1:]:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
                    
            return cls(
                method=method,
                uri=uri,
                version=version,
                headers=headers,
                body=body,
            )
        except Exception as e:
            logging.debug(f"Failed to parse RTSP request: {e}")
            return None


@dataclass
class RTSPResponse:
    """RTSP response builder."""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: str = ""
    
    def to_bytes(self) -> bytes:
        """Serialize response to bytes."""
        lines = [f"{RTSP_VERSION} {self.status_code} {get_status_phrase(self.status_code)}"]
        
        for key, value in self.headers.items():
            lines.append(f"{key}: {value}")
            
        if self.body:
            lines.append(f"Content-Length: {len(self.body)}")
            
        lines.append("")  # Empty line before body
        
        if self.body:
            lines.append(self.body)
        else:
            lines.append("")
            
        return "\r\n".join(lines).encode('utf-8')


@dataclass 
class StreamConfig:
    """Configuration for an RTSP stream."""
    stream_id: str
    name: str = "Camera"
    has_video: bool = True
    has_audio: bool = False
    video_codec: str = "H264"
    audio_codec: str = "PCMU"
    video_payload_type: int = PAYLOAD_TYPE_H264
    audio_payload_type: int = PAYLOAD_TYPE_PCMU
    width: int = 1920
    height: int = 1080
    framerate: int = 25
    audio_sample_rate: int = 8000
    audio_channels: int = 1
    
    # H.264 parameters
    sps_base64: Optional[str] = None
    pps_base64: Optional[str] = None
    profile_level_id: str = "42001f"
    
    # Raw SPS/PPS for sending to newly connected clients
    sps_raw: Optional[bytes] = None
    pps_raw: Optional[bytes] = None
    
    # Data source callbacks
    video_source: Optional[Callable[[], bytes]] = None
    audio_source: Optional[Callable[[], bytes]] = None


class RTSPClientHandler:
    """Handles a single RTSP client connection."""
    
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        server: 'RTSPServer',
    ):
        self.reader = reader
        self.writer = writer
        self.server = server
        self.session: Optional[RTSPSession] = None
        self.running = True
        
        # Get client address
        peername = writer.get_extra_info('peername')
        self.client_address = peername if peername else ('unknown', 0)
        
    async def handle(self):
        """Main handler loop for the client connection."""
        logging.info(f"RTSP client connected from {self.client_address}")
        
        try:
            buffer = b''
            while self.running:
                # Read data with timeout
                try:
                    data = await asyncio.wait_for(
                        self.reader.read(8192),
                        timeout=60.0
                    )
                except asyncio.TimeoutError:
                    # Check for interleaved RTP data from client (RTCP)
                    continue
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    # Client disconnected abruptly - this is normal
                    logging.debug(f"Client {self.client_address} disconnected abruptly")
                    break
                    
                if not data:
                    break
                    
                buffer += data
                
                # Check for interleaved RTP/RTCP data (starts with $)
                while buffer and buffer[0] == 0x24:
                    if len(buffer) < 4:
                        break
                    channel = buffer[1]
                    length = struct.unpack('!H', buffer[2:4])[0]
                    if len(buffer) < 4 + length:
                        break
                    # Skip interleaved data (RTCP from client)
                    buffer = buffer[4 + length:]
                
                # Process RTSP requests
                while b'\r\n\r\n' in buffer:
                    # Find end of headers
                    header_end = buffer.index(b'\r\n\r\n') + 4
                    
                    # Check Content-Length for body
                    header_part = buffer[:header_end].decode('utf-8', errors='replace')
                    content_length = 0
                    for line in header_part.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            content_length = int(line.split(':', 1)[1].strip())
                            break
                            
                    total_length = header_end + content_length
                    if len(buffer) < total_length:
                        break
                        
                    request_data = buffer[:total_length]
                    buffer = buffer[total_length:]
                    
                    request = RTSPRequest.parse(request_data)
                    if request:
                        response = await self.handle_request(request)
                        if response:
                            self.writer.write(response.to_bytes())
                            await self.writer.drain()
                            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error handling RTSP client: {e}", exc_info=True)
        finally:
            await self.cleanup()
            
    async def cleanup(self):
        """Clean up client connection."""
        self.running = False
        
        if self.session:
            self.server.session_manager.remove_session(self.session.session_id)
            self.session = None
            
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
            
        logging.info(f"RTSP client disconnected: {self.client_address}")
        
    async def handle_request(self, request: RTSPRequest) -> Optional[RTSPResponse]:
        """Route and handle an RTSP request.
        
        Args:
            request: Parsed RTSP request
            
        Returns:
            RTSP response
        """
        # Log all RTSP requests for debugging
        logging.info(f"RTSP {request.method} {request.uri} from {self.client_address}")
        
        # Get CSeq header
        cseq = request.headers.get('CSeq', '0')
        
        # Route to appropriate handler
        handler_map = {
            'OPTIONS': self.handle_options,
            'DESCRIBE': self.handle_describe,
            'SETUP': self.handle_setup,
            'PLAY': self.handle_play,
            'PAUSE': self.handle_pause,
            'TEARDOWN': self.handle_teardown,
            'GET_PARAMETER': self.handle_get_parameter,
            'SET_PARAMETER': self.handle_set_parameter,
        }
        
        handler = handler_map.get(request.method)
        if handler:
            response = await handler(request)
            logging.info(f"RTSP {request.method} response: {response.status_code}")
        else:
            response = RTSPResponse(
                status_code=RTSPStatusCode.METHOD_NOT_ALLOWED
            )
            logging.warning(f"RTSP method not allowed: {request.method}")
            
        # Add common headers
        response.headers['CSeq'] = cseq
        response.headers['Server'] = 'motionEye RTSP Server'
        
        if self.session:
            response.headers['Session'] = f"{self.session.session_id};timeout={int(self.session.timeout)}"
            
        return response
        
    async def handle_options(self, request: RTSPRequest) -> RTSPResponse:
        """Handle OPTIONS request."""
        response = RTSPResponse(status_code=RTSPStatusCode.OK)
        response.headers['Public'] = 'OPTIONS, DESCRIBE, SETUP, PLAY, PAUSE, TEARDOWN, GET_PARAMETER, SET_PARAMETER'
        return response
        
    async def handle_describe(self, request: RTSPRequest) -> RTSPResponse:
        """Handle DESCRIBE request - return SDP."""
        # Parse URI to get stream ID
        parsed = urlparse(request.uri)
        stream_path = parsed.path.strip('/')
        
        # Find stream configuration
        stream_config = self.server.get_stream_config(stream_path)
        if not stream_config:
            return RTSPResponse(status_code=RTSPStatusCode.NOT_FOUND)
            
        # Check authentication if required
        if self.server.require_auth:
            auth_result = self._check_auth(request)
            if not auth_result:
                response = RTSPResponse(status_code=RTSPStatusCode.UNAUTHORIZED)
                response.headers['WWW-Authenticate'] = f'Basic realm="motionEye RTSP"'
                return response
                
        # Generate SDP
        server_ip = self.server.listen_address
        if server_ip == '0.0.0.0':
            # Try to get actual server IP
            server_ip = self._get_server_ip()
            
        sdp_gen = SDPGenerator(
            server_name="motionEye",
            session_name=stream_config.name,
        )
        
        sdp = sdp_gen.generate(
            server_ip=server_ip,
            video_port=0,
            audio_port=0,
            video_codec=stream_config.video_codec,
            audio_codec=stream_config.audio_codec,
            video_payload_type=stream_config.video_payload_type,
            audio_payload_type=stream_config.audio_payload_type,
            has_video=stream_config.has_video,
            has_audio=stream_config.has_audio,
            sps_base64=stream_config.sps_base64,
            pps_base64=stream_config.pps_base64,
            profile_level_id=stream_config.profile_level_id,
            stream_url=request.uri,
        )
        
        response = RTSPResponse(status_code=RTSPStatusCode.OK)
        response.headers['Content-Type'] = 'application/sdp'
        response.headers['Content-Base'] = request.uri + ('/' if not request.uri.endswith('/') else '')
        response.body = sdp
        
        return response
        
    async def handle_setup(self, request: RTSPRequest) -> RTSPResponse:
        """Handle SETUP request - configure RTP transport."""
        # Parse URI for track ID
        parsed = urlparse(request.uri)
        path = parsed.path
        
        # Extract track ID from URL
        track_id = 0
        if 'trackID=' in path:
            try:
                track_id = int(path.split('trackID=')[1].split('/')[0])
            except ValueError:
                pass
                
        # Determine media type from track ID
        media_type = "video" if track_id == 0 else "audio"
        
        # Parse Transport header
        transport_header = request.headers.get('Transport', '')
        if not transport_header:
            return RTSPResponse(status_code=RTSPStatusCode.BAD_REQUEST)
            
        transport_params = parse_transport_header(transport_header)
        
        # Create session if not exists
        session_header = request.headers.get('Session', '')
        if session_header:
            session_id = session_header.split(';')[0]
            self.session = self.server.session_manager.get_session(session_id)
        
        if not self.session:
            self.session = self.server.session_manager.create_session(self.client_address)
            
        # Determine stream URL and resolve to actual stream_id
        stream_path = path.split('/trackID=')[0].strip('/') if '/trackID=' in path else path.strip('/')
        
        # Get the actual stream config to find the real stream_id
        stream_config = self.server.get_stream_config(stream_path)
        if stream_config:
            # Use the actual stream_id for matching during broadcast
            actual_stream_id = None
            for sid, cfg in self.server.streams.items():
                if cfg == stream_config:
                    actual_stream_id = sid
                    break
            self.session.stream_url = actual_stream_id if actual_stream_id else stream_path
            logging.info(f"RTSP SETUP: mapped '{stream_path}' -> stream_id '{self.session.stream_url}'")
        else:
            self.session.stream_url = stream_path
            logging.warning(f"RTSP SETUP: no stream config found for '{stream_path}'")
        
        # Determine transport mode
        protocol = transport_params.get('protocol', 'RTP/AVP')
        
        if 'TCP' in protocol or 'interleaved' in transport_params:
            # TCP interleaved mode
            transport_mode = TransportMode.TCP
            logging.info(f"RTSP SETUP: using TCP interleaved transport")
            
            # Parse interleaved channels
            interleaved = transport_params.get('interleaved', '0-1')
            rtp_ch, rtcp_ch = map(int, interleaved.split('-'))
            
            if media_type == "video":
                channel = self.session.setup_video_channel(
                    track_id=track_id,
                    transport_mode=transport_mode,
                    rtp_channel=rtp_ch,
                    rtcp_channel=rtcp_ch,
                )
            else:
                channel = self.session.setup_audio_channel(
                    track_id=track_id,
                    transport_mode=transport_mode,
                    rtp_channel=rtp_ch,
                    rtcp_channel=rtcp_ch,
                )
                
            # Set TCP writer for interleaved mode
            self.session.tcp_writer = lambda data: self._write_interleaved(data)
            
            # Build response transport
            resp_transport = build_transport_header({
                'protocol': 'RTP/AVP/TCP',
                'unicast': True,
                'interleaved': interleaved,
            })
        else:
            # UDP mode
            transport_mode = TransportMode.UDP
            logging.info(f"RTSP SETUP: using UDP transport")
            
            # Parse client ports
            client_port = transport_params.get('client_port', '0-0')
            rtp_port, rtcp_port = map(int, client_port.split('-'))
            
            if media_type == "video":
                channel = self.session.setup_video_channel(
                    track_id=track_id,
                    transport_mode=transport_mode,
                    client_rtp_port=rtp_port,
                    client_rtcp_port=rtcp_port,
                )
            else:
                channel = self.session.setup_audio_channel(
                    track_id=track_id,
                    transport_mode=transport_mode,
                    client_rtp_port=rtp_port,
                    client_rtcp_port=rtcp_port,
                )
                
            # Build response transport
            resp_transport = build_transport_header({
                'protocol': 'RTP/AVP',
                'unicast': True,
                'client_port': client_port,
                'server_port': f"{channel.server_rtp_port}-{channel.server_rtcp_port}",
            })
            
        self.session.state = SessionState.READY
        
        response = RTSPResponse(status_code=RTSPStatusCode.OK)
        response.headers['Transport'] = resp_transport
        
        return response
        
    async def handle_play(self, request: RTSPRequest) -> RTSPResponse:
        """Handle PLAY request - start streaming."""
        if not self.session:
            return RTSPResponse(status_code=RTSPStatusCode.SESSION_NOT_FOUND)
            
        # Parse Range header if present
        range_header = request.headers.get('Range', 'npt=0.000-')
        
        self.session.play()
        
        # Register session with server for broadcasting
        self.server._register_playing_session(self.session)
        
        response = RTSPResponse(status_code=RTSPStatusCode.OK)
        response.headers['Range'] = range_header
        
        # Build RTP-Info header
        rtp_info_parts = []
        for track_id, channel in self.session.channels.items():
            packetizer = self.session.video_packetizer if channel.media_type == "video" \
                        else self.session.audio_packetizer
            if packetizer:
                url = f"{request.uri.split('/trackID=')[0]}/trackID={track_id}"
                rtp_info_parts.append(
                    f"url={url};seq={packetizer.sequence_number};rtptime={packetizer.get_timestamp()}"
                )
                
        if rtp_info_parts:
            response.headers['RTP-Info'] = ','.join(rtp_info_parts)
            
        return response
        
    async def handle_pause(self, request: RTSPRequest) -> RTSPResponse:
        """Handle PAUSE request."""
        if not self.session:
            return RTSPResponse(status_code=RTSPStatusCode.SESSION_NOT_FOUND)
            
        self.session.pause()
        
        return RTSPResponse(status_code=RTSPStatusCode.OK)
        
    async def handle_teardown(self, request: RTSPRequest) -> RTSPResponse:
        """Handle TEARDOWN request - end session."""
        if self.session:
            self.server.session_manager.remove_session(self.session.session_id)
            self.session = None
            
        return RTSPResponse(status_code=RTSPStatusCode.OK)
        
    async def handle_get_parameter(self, request: RTSPRequest) -> RTSPResponse:
        """Handle GET_PARAMETER request (keepalive)."""
        if self.session:
            self.session.touch()
        return RTSPResponse(status_code=RTSPStatusCode.OK)
        
    async def handle_set_parameter(self, request: RTSPRequest) -> RTSPResponse:
        """Handle SET_PARAMETER request."""
        return RTSPResponse(status_code=RTSPStatusCode.OK)
        
    def _write_interleaved(self, data: bytes):
        """Write interleaved RTP/RTCP data."""
        if self.writer and not self.writer.is_closing():
            try:
                self.writer.write(data)
                # Log first write per connection
                if not hasattr(self, '_interleaved_write_logged'):
                    self._interleaved_write_logged = True
                    logging.info(f"First interleaved write: {len(data)} bytes to {self.client_address}")
            except Exception as e:
                logging.warning(f"Failed to write interleaved data: {e}")
                
    def _check_auth(self, request: RTSPRequest) -> bool:
        """Check authentication header.
        
        Args:
            request: RTSP request
            
        Returns:
            True if authenticated, False otherwise
        """
        auth_header = request.headers.get('Authorization', '')
        if not auth_header:
            return False
            
        if auth_header.startswith('Basic '):
            try:
                credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
                username, password = credentials.split(':', 1)
                return self.server.check_credentials(username, password)
            except Exception:
                return False
                
        return False
        
    def _get_server_ip(self) -> str:
        """Get server IP address visible to client."""
        try:
            sockname = self.writer.get_extra_info('sockname')
            if sockname:
                return sockname[0]
        except Exception:
            pass
        return '127.0.0.1'


class RTSPServer:
    """RTSP Server for streaming video and audio.
    
    Compatible with Synology Surveillance Station and other RTSP clients.
    """
    
    def __init__(
        self,
        listen_address: str = '0.0.0.0',
        port: int = 554,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize the RTSP server.
        
        Args:
            listen_address: Address to listen on
            port: Port to listen on
            username: Username for authentication (None to disable)
            password: Password for authentication
        """
        self.listen_address = listen_address
        self.port = port
        self.username = username
        self.password = password
        self.require_auth = bool(username and password)
        
        self.session_manager = SessionManager(timeout=60.0)
        self.streams: Dict[str, StreamConfig] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._running = False
        self._clients: List[RTSPClientHandler] = []
        self._cleanup_task: Optional[asyncio.Task] = None
        
    def add_stream(self, stream_id: str, config: StreamConfig):
        """Add a stream configuration.
        
        Args:
            stream_id: Stream identifier (URL path)
            config: Stream configuration
        """
        self.streams[stream_id] = config
        logging.info(f"Added RTSP stream: {stream_id}")
        
    def remove_stream(self, stream_id: str):
        """Remove a stream configuration.
        
        Args:
            stream_id: Stream identifier
        """
        if stream_id in self.streams:
            del self.streams[stream_id]
            logging.info(f"Removed RTSP stream: {stream_id}")
            
    def get_stream_config(self, stream_path: str) -> Optional[StreamConfig]:
        """Get stream configuration by path.
        
        Args:
            stream_path: URL path (may include trackID)
            
        Returns:
            Stream configuration or None
        """
        # Remove trackID if present
        base_path = stream_path.split('/trackID=')[0].strip('/')
        
        # Try exact match first
        if base_path in self.streams:
            return self.streams[base_path]
            
        # Try with different path variations
        for stream_id, config in self.streams.items():
            if stream_id.strip('/') == base_path:
                return config
                
        # If only one stream, return it (default stream)
        if len(self.streams) == 1:
            return list(self.streams.values())[0]
            
        return None
        
    def check_credentials(self, username: str, password: str) -> bool:
        """Check if credentials are valid.
        
        Args:
            username: Username to check
            password: Password to check
            
        Returns:
            True if valid
        """
        return username == self.username and password == self.password
        
    async def start(self):
        """Start the RTSP server."""
        if self._running:
            return
            
        self._running = True
        
        self._server = await asyncio.start_server(
            self._handle_client,
            self.listen_address,
            self.port,
            reuse_address=True,
        )
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        addrs = ', '.join(str(sock.getsockname()) for sock in self._server.sockets)
        logging.info(f"RTSP server started on {addrs}")
        
    async def stop(self):
        """Stop the RTSP server."""
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
                
        # Close all client connections
        for client in self._clients:
            client.running = False
            
        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            
        # Clean up all sessions
        for session_id in list(self.session_manager.sessions.keys()):
            self.session_manager.remove_session(session_id)
            
        logging.info("RTSP server stopped")
        
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Handle a new client connection."""
        handler = RTSPClientHandler(reader, writer, self)
        self._clients.append(handler)
        try:
            await handler.handle()
        finally:
            if handler in self._clients:
                self._clients.remove(handler)
                
    async def _cleanup_loop(self):
        """Periodic cleanup of expired sessions."""
        while self._running:
            try:
                await asyncio.sleep(30)
                expired = self.session_manager.cleanup_expired()
                if expired:
                    logging.debug(f"Cleaned up {len(expired)} expired sessions")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Error in cleanup loop: {e}")
                
    def _register_playing_session(self, session: RTSPSession):
        """Register a session that has started playing.
        
        Sends SPS/PPS to the client so it can decode video immediately.
        """
        # Find the stream config for this session
        stream_id = session.stream_url
        stream_config = self.streams.get(stream_id)
        
        if stream_config and stream_config.sps_raw and stream_config.pps_raw:
            # Send SPS and PPS to the new client
            logging.info(f"Sending SPS/PPS to new session {session.session_id}")
            try:
                # Send SPS first, then PPS
                session.send_video_frame(stream_config.sps_raw)
                session.send_video_frame(stream_config.pps_raw)
            except Exception as e:
                logging.warning(f"Failed to send SPS/PPS to session {session.session_id}: {e}")
        else:
            logging.debug(f"No SPS/PPS available yet for stream {stream_id}")
        
    def broadcast_frame(
        self,
        stream_id: str,
        video_data: Optional[bytes] = None,
        audio_data: Optional[bytes] = None,
        is_aac_audio: bool = False,
    ):
        """Broadcast video/audio data to all connected clients.
        
        Args:
            stream_id: Stream identifier
            video_data: H.264 video frame data
            audio_data: Audio sample data
            is_aac_audio: True if audio is AAC format
        """
        if video_data:
            # Log to see if we reach this point
            sessions = self.session_manager.get_playing_sessions()
            if sessions:
                if not hasattr(self, '_broadcast_logged'):
                    self._broadcast_logged = True
                    logging.info(
                        f"broadcast_frame called: {len(sessions)} playing sessions, "
                        f"stream_id='{stream_id}', video_size={len(video_data)}"
                    )
            self.session_manager.broadcast_video_frame(stream_id, video_data)
        if audio_data:
            self.session_manager.broadcast_audio_samples(
                stream_id, audio_data, is_aac=is_aac_audio
            )
            
    def get_stream_url(self, stream_id: str) -> str:
        """Get the RTSP URL for a stream.
        
        Args:
            stream_id: Stream identifier
            
        Returns:
            Full RTSP URL
        """
        host = self.listen_address
        if host == '0.0.0.0':
            host = socket.gethostname()
        return f"rtsp://{host}:{self.port}/{stream_id}"


# Convenience function for running the server
async def run_rtsp_server(
    listen_address: str = '0.0.0.0',
    port: int = 554,
    streams: Optional[Dict[str, StreamConfig]] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
):
    """Run the RTSP server.
    
    Args:
        listen_address: Address to listen on
        port: Port to listen on
        streams: Dictionary of stream configurations
        username: Authentication username
        password: Authentication password
    """
    server = RTSPServer(
        listen_address=listen_address,
        port=port,
        username=username,
        password=password,
    )
    
    if streams:
        for stream_id, config in streams.items():
            server.add_stream(stream_id, config)
            
    await server.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()
