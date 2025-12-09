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

"""Video source capture for RTSP streaming.

This module handles capturing video from Motion's MJPEG streams and 
converting them to H.264 for RTSP streaming.
"""

import asyncio
import logging
import subprocess
import threading
import time
from typing import Optional, Callable, Dict, Any, Tuple
from dataclasses import dataclass

from motioneye import config, mediafiles, settings


@dataclass
class VideoSourceConfig:
    """Configuration for a video source."""
    camera_id: int
    source_url: str  # Motion MJPEG stream URL
    width: int = 1920
    height: int = 1080
    framerate: int = 25
    bitrate: int = 2000  # kbps
    
    # H.264 encoding settings
    preset: str = "ultrafast"
    tune: str = "zerolatency"
    profile: str = "baseline"
    level: str = "3.1"
    
    # Audio settings
    audio_enabled: bool = False
    audio_device: str = "plug:default"
    audio_codec: str = "pcm_mulaw"  # G.711 μ-law for compatibility
    audio_sample_rate: int = 8000
    audio_channels: int = 1


class FFmpegTranscoder:
    """Transcodes MJPEG to H.264 using FFmpeg."""
    
    def __init__(
        self,
        source_url: str,
        on_video_frame: Callable[[bytes], None],
        on_audio_samples: Optional[Callable[[bytes], None]] = None,
        config: Optional[VideoSourceConfig] = None,
    ):
        """Initialize the transcoder.
        
        Args:
            source_url: Input MJPEG stream URL
            on_video_frame: Callback for H.264 video frames
            on_audio_samples: Callback for audio samples
            config: Video source configuration
        """
        self.source_url = source_url
        self.on_video_frame = on_video_frame
        self.on_audio_samples = on_audio_samples
        self.config = config or VideoSourceConfig(camera_id=0, source_url=source_url)
        
        self._process: Optional[subprocess.Popen] = None
        self._running = False
        self._video_thread: Optional[threading.Thread] = None
        self._audio_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        
        # Stored SPS/PPS for client configuration
        self.sps: Optional[bytes] = None
        self.pps: Optional[bytes] = None
        self.sps_with_start_code: Optional[bytes] = None
        self.pps_with_start_code: Optional[bytes] = None
        
    def start(self) -> bool:
        """Start the FFmpeg transcoder.
        
        Returns:
            True if started successfully
        """
        ffmpeg_info = mediafiles.find_ffmpeg()
        if not ffmpeg_info:
            logging.error("FFmpeg not found, cannot start transcoder")
            return False
            
        binary, version, _ = ffmpeg_info
        logging.info(f"Starting transcoder with ffmpeg {version} for {self.source_url}")
        
        self._running = True
        
        # Build FFmpeg command
        cmd = self._build_ffmpeg_command(binary)
        logging.info(f"FFmpeg command: {' '.join(cmd)}")
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            
            # Start reader thread
            self._video_thread = threading.Thread(
                target=self._read_video_output,
                daemon=True,
                name=f"ffmpeg-video-{self.config.camera_id}",
            )
            self._video_thread.start()
            
            # Start stderr reader for debugging
            self._stderr_thread = threading.Thread(
                target=self._read_stderr,
                daemon=True,
                name=f"ffmpeg-stderr-{self.config.camera_id}",
            )
            self._stderr_thread.start()
            
            logging.info(f"Transcoder started for camera {self.config.camera_id}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start transcoder: {e}", exc_info=True)
            self._running = False
            return False
    
    def _read_stderr(self):
        """Read and log FFmpeg stderr output."""
        while self._running and self._process and self._process.poll() is None:
            try:
                line = self._process.stderr.readline()
                if line:
                    line_text = line.decode('utf-8', errors='replace').strip()
                    # Log errors and warnings as INFO for visibility
                    if any(x in line_text.lower() for x in ['error', 'warning', 'failed', 'invalid']):
                        logging.warning(f"FFmpeg: {line_text}")
                    else:
                        logging.info(f"FFmpeg: {line_text}")
            except Exception:
                break
        logging.info(f"FFmpeg stderr reader stopped for camera {self.config.camera_id}")
            
    def stop(self):
        """Stop the transcoder."""
        self._running = False
        
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            except Exception as e:
                logging.error(f"Error stopping transcoder: {e}")
            finally:
                self._process = None
                
        if self._video_thread:
            self._video_thread.join(timeout=2)
            self._video_thread = None
        
        if self._stderr_thread:
            self._stderr_thread.join(timeout=2)
            self._stderr_thread = None
            
        logging.info(f"Transcoder stopped for camera {self.config.camera_id}")
        
    def _build_ffmpeg_command(self, binary: str) -> list:
        """Build FFmpeg command line.
        
        Args:
            binary: FFmpeg binary path
            
        Returns:
            Command list
        """
        cmd = [
            binary,
            '-hide_banner',
            '-loglevel', 'info',  # More verbose for debugging
            # Input options for MJPEG stream
            '-fflags', '+genpts+nobuffer',
            '-flags', 'low_delay',
            '-probesize', '32768',  # Increased from 32 for better stream analysis
            '-analyzeduration', '500000',  # 0.5 seconds
            '-f', 'mjpeg',  # Explicit format for MJPEG input
            '-i', self.source_url,
        ]
        
        # Add audio input if enabled
        if self.config.audio_enabled and self.on_audio_samples:
            cmd.extend([
                '-f', 'alsa',
                '-i', self.config.audio_device,
            ])
            
        # Video encoding options
        # Ensure minimum output framerate for smooth streaming
        output_fps = max(self.config.framerate, 10)
        
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', self.config.preset,
            '-tune', self.config.tune,
            '-profile:v', self.config.profile,
            '-level', self.config.level,
            '-b:v', f'{self.config.bitrate}k',
            '-maxrate', f'{self.config.bitrate}k',
            '-bufsize', f'{self.config.bitrate * 2}k',
            '-g', str(output_fps * 2),  # GOP size
            '-keyint_min', str(output_fps),
            '-sc_threshold', '0',
            '-flags', '+cgop',  # Force closed GOP
            '-r', str(output_fps),
            '-pix_fmt', 'yuv420p',
            '-x264-params', 'aud=1:repeat-headers=1',  # Emit AUD + repeat SPS/PPS
        ])
        
        # Output format - raw H.264 Annex B format
        cmd.extend([
            '-f', 'h264',
            '-bsf:v', 'h264_mp4toannexb',
            'pipe:1',
        ])
        
        return cmd
        
    def _read_video_output(self):
        """Read H.264 output from FFmpeg."""
        buffer = b''
        start_code_4 = b'\x00\x00\x00\x01'
        start_code_3 = b'\x00\x00\x01'
        frame_count = 0
        
        logging.info(f"Video reader started for camera {self.config.camera_id}")
        
        while self._running and self._process and self._process.poll() is None:
            try:
                chunk = self._process.stdout.read(8192)
                if not chunk:
                    if self._running:
                        logging.warning(f"FFmpeg stdout closed for camera {self.config.camera_id}")
                    break
                    
                buffer += chunk
                
                # Find and process NAL units
                while True:
                    # Find start code
                    pos4 = buffer.find(start_code_4)
                    pos3 = buffer.find(start_code_3)
                    
                    if pos4 == -1 and pos3 == -1:
                        # No start code found, need more data
                        break
                        
                    # Use earliest start code
                    if pos4 != -1 and (pos3 == -1 or pos4 <= pos3):
                        pos = pos4
                        code_len = 4
                    else:
                        pos = pos3
                        code_len = 3
                        
                    if pos > 0:
                        # Data before first start code - discard
                        buffer = buffer[pos:]
                        continue
                        
                    # Find next start code
                    next_pos4 = buffer.find(start_code_4, code_len)
                    next_pos3 = buffer.find(start_code_3, code_len)
                    
                    if next_pos4 == -1 and next_pos3 == -1:
                        # Only partial NAL, need more data
                        break
                        
                    # Determine next NAL start
                    if next_pos4 != -1 and (next_pos3 == -1 or next_pos4 <= next_pos3):
                        next_pos = next_pos4
                    else:
                        next_pos = next_pos3
                        
                    # Extract complete NAL unit (with start code)
                    nal_data = buffer[:next_pos]
                    buffer = buffer[next_pos:]
                    
                    # Process NAL unit
                    self._process_nal_unit(nal_data)
                    frame_count += 1
                    
                    if frame_count <= 10 or frame_count % 100 == 0:
                        logging.info(f"Camera {self.config.camera_id}: processed {frame_count} NAL units, last size={len(nal_data)} bytes")
                    
            except Exception as e:
                if self._running:
                    logging.error(f"Error reading video output: {e}", exc_info=True)
                break
                
        # Process remaining data
        if buffer and self._running:
            self._process_nal_unit(buffer)
        
        # Check process exit code
        if self._process:
            exit_code = self._process.poll()
            if exit_code is not None and exit_code != 0:
                logging.error(f"FFmpeg exited with code {exit_code} for camera {self.config.camera_id}")
        
        logging.info(f"Video reader stopped for camera {self.config.camera_id}, total frames: {frame_count}")
            
    def _process_nal_unit(self, nal_data: bytes):
        """Process a single NAL unit.
        
        Args:
            nal_data: NAL unit with start code
        """
        if len(nal_data) < 5:
            return
            
        # Get NAL type (skip start code)
        if nal_data.startswith(b'\x00\x00\x00\x01'):
            nal_header = nal_data[4]
            nal_content = nal_data[4:]
        elif nal_data.startswith(b'\x00\x00\x01'):
            nal_header = nal_data[3]
            nal_content = nal_data[3:]
        else:
            return
            
        nal_type = nal_header & 0x1F
        
        # Store SPS (type 7) and PPS (type 8) - both raw content and with start code
        if nal_type == 7:
            self.sps = nal_content
            self.sps_with_start_code = nal_data
            logging.info(f"Captured SPS: {len(self.sps)} bytes")
        elif nal_type == 8:
            self.pps = nal_content
            self.pps_with_start_code = nal_data
            logging.info(f"Captured PPS: {len(self.pps)} bytes")
            
        # Send to callback
        if self.on_video_frame:
            self.on_video_frame(nal_data)


class AudioCapture:
    """Captures audio from ALSA device."""
    
    def __init__(
        self,
        device: str = "plug:default",
        sample_rate: int = 8000,
        channels: int = 1,
        on_samples: Optional[Callable[[bytes], None]] = None,
    ):
        """Initialize audio capture.
        
        Args:
            device: ALSA device identifier
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            on_samples: Callback for audio samples
        """
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.on_samples = on_samples
        
        self._process: Optional[subprocess.Popen] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def start(self) -> bool:
        """Start audio capture.
        
        Returns:
            True if started successfully
        """
        ffmpeg_info = mediafiles.find_ffmpeg()
        if not ffmpeg_info:
            logging.error("FFmpeg not found for audio capture")
            return False
            
        binary, _, _ = ffmpeg_info
        
        cmd = [
            binary,
            '-hide_banner',
            '-loglevel', 'warning',
            '-f', 'alsa',
            '-i', self.device,
            '-ac', str(self.channels),
            '-ar', str(self.sample_rate),
            '-acodec', 'pcm_mulaw',  # G.711 μ-law
            '-f', 'mulaw',
            'pipe:1',
        ]
        
        self._running = True
        
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            
            self._thread = threading.Thread(
                target=self._read_audio,
                daemon=True,
            )
            self._thread.start()
            
            logging.info(f"Audio capture started on {self.device}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to start audio capture: {e}")
            self._running = False
            return False
            
    def stop(self):
        """Stop audio capture."""
        self._running = False
        
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            except Exception:
                pass
            finally:
                self._process = None
                
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
            
    def _read_audio(self):
        """Read audio samples from FFmpeg."""
        # Read 160 samples at a time (20ms at 8kHz)
        chunk_size = 160
        
        while self._running and self._process and self._process.poll() is None:
            try:
                data = self._process.stdout.read(chunk_size)
                if not data:
                    break
                    
                if self.on_samples:
                    self.on_samples(data)
                    
            except Exception as e:
                if self._running:
                    logging.error(f"Error reading audio: {e}")
                break


class VideoSourceManager:
    """Manages video sources for RTSP streaming."""
    
    def __init__(self):
        self.sources: Dict[int, FFmpegTranscoder] = {}
        self.audio_captures: Dict[int, AudioCapture] = {}
        self._frame_callbacks: Dict[int, list] = {}
        self._audio_callbacks: Dict[int, list] = {}
        
    def add_source(
        self,
        camera_id: int,
        source_url: str,
        config: Optional[VideoSourceConfig] = None,
    ) -> FFmpegTranscoder:
        """Add a video source.
        
        Args:
            camera_id: Camera identifier
            source_url: MJPEG stream URL
            config: Video source configuration
            
        Returns:
            Transcoder instance
        """
        if config is None:
            config = VideoSourceConfig(
                camera_id=camera_id,
                source_url=source_url,
            )
            
        # Create callbacks
        self._frame_callbacks[camera_id] = []
        self._audio_callbacks[camera_id] = []
        
        transcoder = FFmpegTranscoder(
            source_url=source_url,
            on_video_frame=lambda data: self._on_video_frame(camera_id, data),
            on_audio_samples=lambda data: self._on_audio_samples(camera_id, data)
                if config.audio_enabled else None,
            config=config,
        )
        
        self.sources[camera_id] = transcoder
        return transcoder
        
    def remove_source(self, camera_id: int):
        """Remove a video source.
        
        Args:
            camera_id: Camera identifier
        """
        transcoder = self.sources.pop(camera_id, None)
        if transcoder:
            transcoder.stop()
            
        audio = self.audio_captures.pop(camera_id, None)
        if audio:
            audio.stop()
            
        self._frame_callbacks.pop(camera_id, None)
        self._audio_callbacks.pop(camera_id, None)
        
    def start_source(self, camera_id: int) -> bool:
        """Start a video source.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if started successfully
        """
        transcoder = self.sources.get(camera_id)
        if not transcoder:
            return False
        return transcoder.start()
        
    def stop_source(self, camera_id: int):
        """Stop a video source.
        
        Args:
            camera_id: Camera identifier
        """
        transcoder = self.sources.get(camera_id)
        if transcoder:
            transcoder.stop()
            
        audio = self.audio_captures.get(camera_id)
        if audio:
            audio.stop()
            
    def add_frame_callback(self, camera_id: int, callback: Callable[[bytes], None]):
        """Add a callback for video frames.
        
        Args:
            camera_id: Camera identifier
            callback: Callback function
        """
        if camera_id in self._frame_callbacks:
            self._frame_callbacks[camera_id].append(callback)
            
    def add_audio_callback(self, camera_id: int, callback: Callable[[bytes], None]):
        """Add a callback for audio samples.
        
        Args:
            camera_id: Camera identifier
            callback: Callback function
        """
        if camera_id in self._audio_callbacks:
            self._audio_callbacks[camera_id].append(callback)
            
    def _on_video_frame(self, camera_id: int, data: bytes):
        """Handle incoming video frame.
        
        Args:
            camera_id: Camera identifier
            data: H.264 frame data
        """
        callbacks = self._frame_callbacks.get(camera_id, [])
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logging.error(f"Error in video callback: {e}")
                
    def _on_audio_samples(self, camera_id: int, data: bytes):
        """Handle incoming audio samples.
        
        Args:
            camera_id: Camera identifier
            data: Audio samples
        """
        callbacks = self._audio_callbacks.get(camera_id, [])
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logging.error(f"Error in audio callback: {e}")
