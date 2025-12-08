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

"""SDP (Session Description Protocol) generator for RTSP streams."""

import time
from typing import Optional, List, Dict, Any


class SDPGenerator:
    """Generates SDP descriptions for RTSP streams.
    
    Supports generating SDP for H.264 video and AAC/PCM audio streams
    compatible with Synology Surveillance Station and other RTSP clients.
    """
    
    def __init__(
        self,
        server_name: str = "motionEye",
        session_name: str = "Camera Stream",
    ):
        self.server_name = server_name
        self.session_name = session_name
        
    def generate(
        self,
        server_ip: str,
        video_port: int = 0,
        audio_port: int = 0,
        video_codec: str = "H264",
        audio_codec: str = "PCMU",
        video_payload_type: int = 96,
        audio_payload_type: int = 0,
        video_clock_rate: int = 90000,
        audio_clock_rate: int = 8000,
        audio_channels: int = 1,
        sps_base64: Optional[str] = None,
        pps_base64: Optional[str] = None,
        profile_level_id: str = "42001f",
        stream_url: Optional[str] = None,
        has_video: bool = True,
        has_audio: bool = False,
    ) -> str:
        """Generate an SDP description.
        
        Args:
            server_ip: Server IP address
            video_port: RTP port for video (0 for server-selected)
            audio_port: RTP port for audio (0 for server-selected)
            video_codec: Video codec name (H264, H265, MJPEG)
            audio_codec: Audio codec name (PCMU, PCMA, AAC, OPUS)
            video_payload_type: RTP payload type for video
            audio_payload_type: RTP payload type for audio
            video_clock_rate: Video clock rate in Hz
            audio_clock_rate: Audio clock rate in Hz
            audio_channels: Number of audio channels
            sps_base64: Base64 encoded H.264 SPS NAL unit
            pps_base64: Base64 encoded H.264 PPS NAL unit
            profile_level_id: H.264 profile-level-id
            stream_url: Full stream URL for control
            has_video: Include video media description
            has_audio: Include audio media description
            
        Returns:
            SDP description as string
        """
        lines = []
        
        # Session description
        session_id = int(time.time())
        session_version = session_id
        
        # v= protocol version
        lines.append("v=0")
        
        # o= origin
        # o=<username> <sess-id> <sess-version> <nettype> <addrtype> <unicast-address>
        lines.append(f"o=- {session_id} {session_version} IN IP4 {server_ip}")
        
        # s= session name
        lines.append(f"s={self.session_name}")
        
        # i= session information (optional)
        lines.append(f"i={self.server_name} Stream")
        
        # c= connection information
        lines.append(f"c=IN IP4 {server_ip}")
        
        # t= timing (0 0 means permanent session)
        lines.append("t=0 0")
        
        # a= session attributes
        lines.append("a=tool:" + self.server_name)
        lines.append("a=type:broadcast")
        lines.append("a=control:*")
        lines.append("a=range:npt=0-")
        
        # Media descriptions
        if has_video:
            lines.extend(self._generate_video_media(
                video_port=video_port,
                codec=video_codec,
                payload_type=video_payload_type,
                clock_rate=video_clock_rate,
                sps_base64=sps_base64,
                pps_base64=pps_base64,
                profile_level_id=profile_level_id,
                control_url=f"{stream_url}/trackID=0" if stream_url else "trackID=0",
            ))
            
        if has_audio:
            lines.extend(self._generate_audio_media(
                audio_port=audio_port,
                codec=audio_codec,
                payload_type=audio_payload_type,
                clock_rate=audio_clock_rate,
                channels=audio_channels,
                control_url=f"{stream_url}/trackID=1" if stream_url else "trackID=1",
            ))
            
        return "\r\n".join(lines) + "\r\n"
    
    def _generate_video_media(
        self,
        video_port: int,
        codec: str,
        payload_type: int,
        clock_rate: int,
        sps_base64: Optional[str],
        pps_base64: Optional[str],
        profile_level_id: str,
        control_url: str,
    ) -> List[str]:
        """Generate video media description."""
        lines = []
        
        # m= media description
        # m=<media> <port> <proto> <fmt>
        lines.append(f"m=video {video_port} RTP/AVP {payload_type}")
        
        # b= bandwidth (optional, estimate for H.264)
        lines.append("b=AS:2000")
        
        # a= media attributes
        if codec.upper() == "H264":
            # rtpmap for H.264
            lines.append(f"a=rtpmap:{payload_type} H264/{clock_rate}")
            
            # fmtp for H.264 with SPS/PPS if available
            fmtp_parts = [f"packetization-mode=1", f"profile-level-id={profile_level_id}"]
            if sps_base64 and pps_base64:
                fmtp_parts.append(f"sprop-parameter-sets={sps_base64},{pps_base64}")
            lines.append(f"a=fmtp:{payload_type} {';'.join(fmtp_parts)}")
            
        elif codec.upper() == "H265" or codec.upper() == "HEVC":
            lines.append(f"a=rtpmap:{payload_type} H265/{clock_rate}")
            
        elif codec.upper() == "MJPEG":
            lines.append(f"a=rtpmap:{payload_type} JPEG/{clock_rate}")
            
        lines.append(f"a=control:{control_url}")
        lines.append("a=framerate:25")
        
        return lines
    
    def _generate_audio_media(
        self,
        audio_port: int,
        codec: str,
        payload_type: int,
        clock_rate: int,
        channels: int,
        control_url: str,
    ) -> List[str]:
        """Generate audio media description."""
        lines = []
        
        # m= media description
        lines.append(f"m=audio {audio_port} RTP/AVP {payload_type}")
        
        # b= bandwidth
        lines.append("b=AS:128")
        
        # a= media attributes based on codec
        codec_upper = codec.upper()
        
        if codec_upper == "PCMU":
            # G.711 μ-law - standard payload type 0
            lines.append(f"a=rtpmap:{payload_type} PCMU/{clock_rate}/{channels}")
            
        elif codec_upper == "PCMA":
            # G.711 A-law - standard payload type 8
            lines.append(f"a=rtpmap:{payload_type} PCMA/{clock_rate}/{channels}")
            
        elif codec_upper == "AAC" or codec_upper == "MPEG4-GENERIC":
            # AAC audio
            lines.append(f"a=rtpmap:{payload_type} mpeg4-generic/{clock_rate}/{channels}")
            # AAC-LC configuration
            lines.append(
                f"a=fmtp:{payload_type} streamtype=5;profile-level-id=1;"
                f"mode=AAC-hbr;sizelength=13;indexlength=3;indexdeltalength=3"
            )
            
        elif codec_upper == "OPUS":
            lines.append(f"a=rtpmap:{payload_type} opus/{clock_rate}/{channels}")
            lines.append(f"a=fmtp:{payload_type} sprop-stereo={(1 if channels > 1 else 0)}")
            
        elif codec_upper == "G722":
            lines.append(f"a=rtpmap:{payload_type} G722/{clock_rate}/{channels}")
            
        else:
            # Generic
            lines.append(f"a=rtpmap:{payload_type} {codec}/{clock_rate}/{channels}")
            
        lines.append(f"a=control:{control_url}")
        
        return lines


def generate_simple_sdp(
    server_ip: str,
    session_name: str = "motionEye Camera",
    has_audio: bool = False,
) -> str:
    """Generate a simple SDP for a basic H.264 + optional audio stream.
    
    This is a convenience function for common use cases.
    
    Args:
        server_ip: Server IP address
        session_name: Session name
        has_audio: Include audio track
        
    Returns:
        SDP description string
    """
    generator = SDPGenerator(session_name=session_name)
    return generator.generate(
        server_ip=server_ip,
        has_video=True,
        has_audio=has_audio,
        video_codec="H264",
        audio_codec="PCMU",
        video_payload_type=96,
        audio_payload_type=0,
    )
