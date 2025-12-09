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

"""RTSP streaming integration for motionEye.

This module provides the main integration layer between motionEye's
camera system and the RTSP server, enabling cameras to be streamed
via RTSP for clients like Synology Surveillance Station.
"""

import asyncio
import base64
import logging
import os
import threading
from typing import Optional, Dict, Any, List

from motioneye import config, settings
from motioneye.rtspserver.server import RTSPServer, StreamConfig
from motioneye.rtspserver.source import VideoSourceManager, VideoSourceConfig


# Global server instance
_server: Optional[RTSPServer] = None
_source_manager: Optional[VideoSourceManager] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None


def get_rtsp_settings() -> Dict[str, Any]:
    """Get RTSP server settings.
    
    Returns:
        Dictionary of RTSP settings
    """
    return {
        'enabled': getattr(settings, 'RTSP_ENABLED', False),
        'port': getattr(settings, 'RTSP_PORT', 8554),
        'listen': getattr(settings, 'RTSP_LISTEN', '0.0.0.0'),
        'username': getattr(settings, 'RTSP_USERNAME', None),
        'password': getattr(settings, 'RTSP_PASSWORD', None),
        'audio_enabled': getattr(settings, 'RTSP_AUDIO_ENABLED', False),
        'audio_device': getattr(settings, 'RTSP_AUDIO_DEVICE', None) or getattr(settings, 'AUDIO_DEVICE', 'plug:default'),
        'video_bitrate': getattr(settings, 'RTSP_VIDEO_BITRATE', 2000),
        'video_preset': getattr(settings, 'RTSP_VIDEO_PRESET', 'ultrafast'),
    }


def _send_sps_pps_to_waiting_clients(stream_id: str, stream_config: StreamConfig):
    """Send SPS/PPS to clients that are playing but haven't received it yet.
    
    This handles the case where a client connects before FFmpeg has produced
    the SPS/PPS parameters.
    
    Args:
        stream_id: Stream identifier
        stream_config: Stream configuration with SPS/PPS data
    """
    if not _server:
        return
        
    sessions = _server.session_manager.get_playing_sessions()
    for session in sessions:
        # Check if this session is for our stream
        session_stream = session.stream_url.strip('/').split('/')[0] if session.stream_url else ''
        if session_stream == stream_id or stream_id in session.stream_url:
            # Check if we already sent SPS/PPS to this session
            if not hasattr(session, '_sps_pps_sent'):
                session._sps_pps_sent = True
                logging.info(f"Sending delayed SPS/PPS to session {session.session_id}")
                try:
                    # Combine SPS + PPS into one frame so they share the same timestamp
                    combined = stream_config.sps_raw + stream_config.pps_raw
                    session.send_video_frame(combined)
                except Exception as e:
                    logging.warning(f"Failed to send delayed SPS/PPS: {e}")


def is_running() -> bool:
    """Check if the RTSP server is running.
    
    Returns:
        True if running
    """
    return _server is not None and _thread is not None and _thread.is_alive()


def start():
    """Start the RTSP server."""
    global _server, _source_manager, _loop, _thread
    
    rtsp_settings = get_rtsp_settings()
    
    if not rtsp_settings['enabled']:
        logging.debug("RTSP server disabled via settings")
        return
        
    if is_running():
        logging.debug("RTSP server already running")
        return
        
    logging.info("Starting RTSP server...")
    
    # Create source manager
    _source_manager = VideoSourceManager()
    
    # Create server
    _server = RTSPServer(
        listen_address=rtsp_settings['listen'],
        port=rtsp_settings['port'],
        username=rtsp_settings['username'],
        password=rtsp_settings['password'],
    )
    
    # Configure streams for each enabled camera
    _configure_camera_streams(rtsp_settings)
    
    # Start in separate thread with its own event loop
    _thread = threading.Thread(target=_run_server_thread, daemon=True)
    _thread.start()
    
    logging.info(
        f"RTSP server starting on {rtsp_settings['listen']}:{rtsp_settings['port']}"
    )


def stop():
    """Stop the RTSP server."""
    global _server, _source_manager, _loop, _thread
    
    if not is_running():
        return
        
    logging.info("Stopping RTSP server...")
    
    # Stop event loop
    if _loop:
        _loop.call_soon_threadsafe(_loop.stop)
        
    # Wait for thread
    if _thread:
        _thread.join(timeout=5)
        _thread = None
        
    # Cleanup
    if _source_manager:
        for camera_id in list(_source_manager.sources.keys()):
            _source_manager.stop_source(camera_id)
        _source_manager = None
        
    _server = None
    _loop = None
    
    logging.info("RTSP server stopped")


def restart():
    """Restart the RTSP server."""
    stop()
    start()


def _run_server_thread():
    """Run the server in its own thread."""
    global _loop
    
    try:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        
        _loop.run_until_complete(_server.start())
        _loop.run_forever()
        
    except Exception as e:
        logging.error(f"RTSP server thread error: {e}", exc_info=True)
    finally:
        if _loop:
            try:
                _loop.run_until_complete(_server.stop())
            except Exception:
                pass
            _loop.close()


def _configure_camera_streams(rtsp_settings: Dict[str, Any]):
    """Configure RTSP streams for all enabled cameras.
    
    Args:
        rtsp_settings: RTSP server settings
    """
    try:
        cameras = config.get_enabled_local_motion_cameras()
    except Exception as e:
        logging.warning(f"Could not get camera list for RTSP: {e}")
        return
        
    for camera_config in cameras:
        camera_id = camera_config.get('@id')
        if camera_id is None:
            continue
            
        try:
            _configure_single_camera(camera_id, camera_config, rtsp_settings)
        except Exception as e:
            logging.error(f"Failed to configure camera {camera_id} for RTSP: {e}")


def _configure_single_camera(
    camera_id: int,
    camera_config: Dict[str, Any],
    rtsp_settings: Dict[str, Any],
):
    """Configure RTSP stream for a single camera.
    
    Args:
        camera_id: Camera ID
        camera_config: Camera configuration
        rtsp_settings: RTSP settings
    """
    # Get Motion stream URL
    stream_port = camera_config.get('stream_port')
    if not stream_port:
        logging.warning(f"Camera {camera_id} has no stream_port, skipping RTSP")
        return
        
    source_url = f"http://127.0.0.1:{stream_port}"
    
    # Get video settings
    width = camera_config.get('width', 1920)
    height = camera_config.get('height', 1080)
    framerate = camera_config.get('framerate', 25)
    
    # Camera name
    camera_name = camera_config.get('@name', f'Camera {camera_id}')
    
    # Stream ID (URL path)
    stream_id = f"cam{camera_id}"
    
    # Create video source config
    source_config = VideoSourceConfig(
        camera_id=camera_id,
        source_url=source_url,
        width=width,
        height=height,
        framerate=framerate,
        bitrate=rtsp_settings['video_bitrate'],
        preset=rtsp_settings['video_preset'],
        audio_enabled=rtsp_settings['audio_enabled'],
        audio_device=rtsp_settings['audio_device'],
    )
    
    # Add to source manager
    transcoder = _source_manager.add_source(camera_id, source_url, source_config)
    
    # Create stream config
    stream_config = StreamConfig(
        stream_id=stream_id,
        name=camera_name,
        has_video=True,
        has_audio=rtsp_settings['audio_enabled'],
        width=width,
        height=height,
        framerate=framerate,
    )
    
    # Add stream to server
    _server.add_stream(stream_id, stream_config)
    
    # Connect source to server for broadcasting
    # Use counter to log periodically
    frame_counter = [0]  # Use list to allow modification in closure
    
    def on_video_frame(data: bytes):
        if _server:
            frame_counter[0] += 1
            if frame_counter[0] == 1:
                logging.info(f"First video frame received for {stream_id} ({len(data)} bytes)")
            elif frame_counter[0] % 500 == 0:
                logging.debug(f"Video frames for {stream_id}: {frame_counter[0]}")
            
            # Update SPS/PPS in stream config if available from transcoder
            # Also send to any playing sessions that haven't received it yet
            sps_updated = False
            pps_updated = False
            
            if transcoder.sps_with_start_code and stream_config.sps_raw is None:
                stream_config.sps_raw = transcoder.sps_with_start_code
                # Also set base64 version for SDP (without start code)
                if transcoder.sps:
                    stream_config.sps_base64 = base64.b64encode(transcoder.sps).decode('ascii')
                    logging.info(f"Updated SPS in stream config for {stream_id} (base64: {len(stream_config.sps_base64)} chars)")
                else:
                    logging.info(f"Updated SPS in stream config for {stream_id}")
                sps_updated = True
            if transcoder.pps_with_start_code and stream_config.pps_raw is None:
                stream_config.pps_raw = transcoder.pps_with_start_code
                # Also set base64 version for SDP (without start code)
                if transcoder.pps:
                    stream_config.pps_base64 = base64.b64encode(transcoder.pps).decode('ascii')
                    logging.info(f"Updated PPS in stream config for {stream_id} (base64: {len(stream_config.pps_base64)} chars)")
                else:
                    logging.info(f"Updated PPS in stream config for {stream_id}")
                pps_updated = True
            
            # If we just got SPS/PPS, send to any waiting clients
            if (sps_updated or pps_updated) and stream_config.sps_raw and stream_config.pps_raw:
                _send_sps_pps_to_waiting_clients(stream_id, stream_config)
            
            # Check if this is an IDR frame (NAL type 5) - prefix with SPS+PPS
            # This ensures decoder always has parameters before keyframes
            frame_to_send = data
            if stream_config.sps_raw and stream_config.pps_raw and len(data) > 4:
                # Get NAL type from data (skip start code)
                if data.startswith(b'\x00\x00\x00\x01'):
                    nal_type = data[4] & 0x1F
                elif data.startswith(b'\x00\x00\x01'):
                    nal_type = data[3] & 0x1F
                else:
                    nal_type = 0
                    
                # NAL type 5 = IDR frame (keyframe)
                if nal_type == 5:
                    # Prefix with SPS + PPS for complete access unit
                    frame_to_send = stream_config.sps_raw + stream_config.pps_raw + data
                    if frame_counter[0] <= 5:
                        logging.info(f"Prefixed IDR frame with SPS+PPS for {stream_id}")
            
            _server.broadcast_frame(stream_id, video_data=frame_to_send)
            
    def on_audio_samples(data: bytes):
        if _server:
            _server.broadcast_frame(stream_id, audio_data=data, is_aac_audio=False)
            
    _source_manager.add_frame_callback(camera_id, on_video_frame)
    if rtsp_settings['audio_enabled']:
        _source_manager.add_audio_callback(camera_id, on_audio_samples)
        
    # Start the source
    if _source_manager.start_source(camera_id):
        logging.info(f"Started RTSP source for camera {camera_id}")
    else:
        logging.error(f"Failed to start RTSP source for camera {camera_id}")
    
    logging.info(
        f"Configured RTSP stream for camera {camera_id} ({camera_name}) at /{stream_id}"
    )


def add_camera_stream(camera_id: int):
    """Add RTSP stream for a camera.
    
    Called when a new camera is added.
    
    Args:
        camera_id: Camera ID
    """
    if not is_running():
        return
        
    try:
        camera_config = config.get_camera(camera_id)
        rtsp_settings = get_rtsp_settings()
        _configure_single_camera(camera_id, camera_config, rtsp_settings)
    except Exception as e:
        logging.error(f"Failed to add camera {camera_id} to RTSP: {e}")


def remove_camera_stream(camera_id: int):
    """Remove RTSP stream for a camera.
    
    Called when a camera is removed.
    
    Args:
        camera_id: Camera ID
    """
    if not is_running():
        return
        
    stream_id = f"cam{camera_id}"
    
    if _source_manager:
        _source_manager.remove_source(camera_id)
        
    if _server:
        _server.remove_stream(stream_id)
        
    logging.info(f"Removed RTSP stream for camera {camera_id}")


def get_stream_urls() -> Dict[int, str]:
    """Get RTSP URLs for all configured streams.
    
    Returns:
        Dictionary mapping camera IDs to RTSP URLs
    """
    if not _server:
        return {}
        
    urls = {}
    for stream_id in _server.streams:
        # Parse camera ID from stream_id
        if stream_id.startswith('cam'):
            try:
                camera_id = int(stream_id[3:])
                urls[camera_id] = _server.get_stream_url(stream_id)
            except ValueError:
                pass
                
    return urls


def get_server_status() -> Dict[str, Any]:
    """Get RTSP server status.
    
    Returns:
        Status information dictionary
    """
    status = {
        'running': is_running(),
        'port': getattr(settings, 'RTSP_PORT', 8554),
        'listen': getattr(settings, 'RTSP_LISTEN', '0.0.0.0'),
        'streams': [],
        'sessions': 0,
    }
    
    if _server:
        status['streams'] = list(_server.streams.keys())
        status['sessions'] = len(_server.session_manager.sessions)
        
    return status
