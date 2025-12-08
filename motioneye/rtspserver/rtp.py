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

"""RTP Packetizer for video and audio streams.

Implements RTP packetization according to RFC 3550 (RTP),
RFC 6184 (H.264/RTP), and RFC 3640 (AAC/RTP).
"""

import struct
import time
import random
from typing import List, Optional, Tuple, Generator
from dataclasses import dataclass, field


# RTP Header constants
RTP_VERSION = 2
RTP_HEADER_SIZE = 12


@dataclass
class RTPPacket:
    """Represents an RTP packet."""
    version: int = RTP_VERSION
    padding: bool = False
    extension: bool = False
    csrc_count: int = 0
    marker: bool = False
    payload_type: int = 96
    sequence_number: int = 0
    timestamp: int = 0
    ssrc: int = 0
    csrc_list: List[int] = field(default_factory=list)
    payload: bytes = b''
    
    def to_bytes(self) -> bytes:
        """Serialize the RTP packet to bytes."""
        # First byte: V=2, P, X, CC
        byte0 = (self.version << 6) | (int(self.padding) << 5) | \
                (int(self.extension) << 4) | self.csrc_count
        
        # Second byte: M, PT
        byte1 = (int(self.marker) << 7) | (self.payload_type & 0x7F)
        
        header = struct.pack(
            '!BBHII',
            byte0,
            byte1,
            self.sequence_number & 0xFFFF,
            self.timestamp & 0xFFFFFFFF,
            self.ssrc & 0xFFFFFFFF,
        )
        
        # Add CSRC list if present
        for csrc in self.csrc_list[:self.csrc_count]:
            header += struct.pack('!I', csrc)
            
        return header + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RTPPacket':
        """Deserialize an RTP packet from bytes."""
        if len(data) < RTP_HEADER_SIZE:
            raise ValueError("RTP packet too short")
            
        byte0, byte1, seq, ts, ssrc = struct.unpack('!BBHII', data[:12])
        
        version = (byte0 >> 6) & 0x03
        padding = bool((byte0 >> 5) & 0x01)
        extension = bool((byte0 >> 4) & 0x01)
        csrc_count = byte0 & 0x0F
        marker = bool((byte1 >> 7) & 0x01)
        payload_type = byte1 & 0x7F
        
        offset = RTP_HEADER_SIZE
        csrc_list = []
        for _ in range(csrc_count):
            csrc = struct.unpack('!I', data[offset:offset+4])[0]
            csrc_list.append(csrc)
            offset += 4
            
        payload = data[offset:]
        
        return cls(
            version=version,
            padding=padding,
            extension=extension,
            csrc_count=csrc_count,
            marker=marker,
            payload_type=payload_type,
            sequence_number=seq,
            timestamp=ts,
            ssrc=ssrc,
            csrc_list=csrc_list,
            payload=payload,
        )


class RTPPacketizer:
    """Base class for RTP packetization."""
    
    def __init__(
        self,
        payload_type: int = 96,
        clock_rate: int = 90000,
        ssrc: Optional[int] = None,
        mtu: int = 1400,
    ):
        """Initialize the RTP packetizer.
        
        Args:
            payload_type: RTP payload type number
            clock_rate: Clock rate in Hz (90000 for video, 8000 for audio)
            ssrc: Synchronization source identifier (random if not provided)
            mtu: Maximum transmission unit for fragmentation
        """
        self.payload_type = payload_type
        self.clock_rate = clock_rate
        self.ssrc = ssrc if ssrc is not None else random.randint(0, 0xFFFFFFFF)
        self.mtu = mtu
        self.sequence_number = random.randint(0, 0xFFFF)
        self._start_time = time.time()
        self._base_timestamp = random.randint(0, 0xFFFFFFFF)
        
    def get_timestamp(self, pts: Optional[float] = None) -> int:
        """Get RTP timestamp for the current time or given PTS.
        
        Args:
            pts: Presentation timestamp in seconds (None for current time)
            
        Returns:
            32-bit RTP timestamp
        """
        if pts is None:
            elapsed = time.time() - self._start_time
        else:
            elapsed = pts
        return (self._base_timestamp + int(elapsed * self.clock_rate)) & 0xFFFFFFFF
    
    def next_sequence(self) -> int:
        """Get and increment the sequence number."""
        seq = self.sequence_number
        self.sequence_number = (self.sequence_number + 1) & 0xFFFF
        return seq
    
    def create_packet(
        self,
        payload: bytes,
        timestamp: int,
        marker: bool = False,
    ) -> RTPPacket:
        """Create a single RTP packet.
        
        Args:
            payload: Packet payload data
            timestamp: RTP timestamp
            marker: Marker bit value
            
        Returns:
            RTP packet
        """
        return RTPPacket(
            payload_type=self.payload_type,
            sequence_number=self.next_sequence(),
            timestamp=timestamp,
            ssrc=self.ssrc,
            marker=marker,
            payload=payload,
        )


class H264Packetizer(RTPPacketizer):
    """RTP packetizer for H.264 video streams (RFC 6184).
    
    Supports Single NAL Unit mode and FU-A fragmentation for large NAL units.
    """
    
    # NAL unit types
    NAL_TYPE_MASK = 0x1F
    NAL_FU_A = 28
    NAL_FU_B = 29
    NAL_STAP_A = 24
    NAL_STAP_B = 25
    
    def __init__(
        self,
        payload_type: int = 96,
        ssrc: Optional[int] = None,
        mtu: int = 1400,
    ):
        super().__init__(
            payload_type=payload_type,
            clock_rate=90000,  # H.264 always uses 90kHz clock
            ssrc=ssrc,
            mtu=mtu,
        )
        
    def packetize_nal(
        self,
        nal_unit: bytes,
        timestamp: int,
        is_last: bool = True,
    ) -> Generator[RTPPacket, None, None]:
        """Packetize a single H.264 NAL unit.
        
        Args:
            nal_unit: NAL unit data (without start code)
            timestamp: RTP timestamp
            is_last: True if this is the last NAL in the access unit
            
        Yields:
            RTP packets
        """
        if len(nal_unit) == 0:
            return
            
        # Maximum payload size (accounting for RTP header)
        max_payload = self.mtu - RTP_HEADER_SIZE
        
        if len(nal_unit) <= max_payload:
            # Single NAL unit mode - fits in one packet
            yield self.create_packet(
                payload=nal_unit,
                timestamp=timestamp,
                marker=is_last,
            )
        else:
            # FU-A fragmentation
            yield from self._fragment_nal_fua(nal_unit, timestamp, is_last)
            
    def _fragment_nal_fua(
        self,
        nal_unit: bytes,
        timestamp: int,
        is_last: bool,
    ) -> Generator[RTPPacket, None, None]:
        """Fragment a NAL unit using FU-A mode.
        
        Args:
            nal_unit: NAL unit to fragment
            timestamp: RTP timestamp
            is_last: True if this is the last NAL in the access unit
            
        Yields:
            RTP packets with FU-A headers
        """
        nal_header = nal_unit[0]
        nal_type = nal_header & self.NAL_TYPE_MASK
        nri = nal_header & 0x60  # Keep NRI bits
        
        # FU indicator: F=0, NRI from original, Type=28 (FU-A)
        fu_indicator = nri | self.NAL_FU_A
        
        # Fragment the NAL payload (skip original NAL header)
        payload = nal_unit[1:]
        max_fragment = self.mtu - RTP_HEADER_SIZE - 2  # 2 bytes for FU header
        
        offset = 0
        first = True
        
        while offset < len(payload):
            chunk = payload[offset:offset + max_fragment]
            last_fragment = (offset + len(chunk)) >= len(payload)
            
            # FU header: S=start, E=end, R=0, Type=original NAL type
            fu_header = nal_type
            if first:
                fu_header |= 0x80  # Start bit
                first = False
            if last_fragment:
                fu_header |= 0x40  # End bit
                
            fu_payload = bytes([fu_indicator, fu_header]) + chunk
            
            yield self.create_packet(
                payload=fu_payload,
                timestamp=timestamp,
                marker=is_last and last_fragment,
            )
            
            offset += len(chunk)
            
    def packetize_frame(
        self,
        frame_data: bytes,
        timestamp: Optional[int] = None,
    ) -> Generator[RTPPacket, None, None]:
        """Packetize an H.264 frame (may contain multiple NAL units).
        
        Args:
            frame_data: Frame data with NAL start codes (0x00000001 or 0x000001)
            timestamp: RTP timestamp (current time if None)
            
        Yields:
            RTP packets
        """
        if timestamp is None:
            timestamp = self.get_timestamp()
            
        nal_units = self._extract_nal_units(frame_data)
        
        for i, nal in enumerate(nal_units):
            is_last = (i == len(nal_units) - 1)
            yield from self.packetize_nal(nal, timestamp, is_last)
            
    @staticmethod
    def _extract_nal_units(data: bytes) -> List[bytes]:
        """Extract NAL units from H.264 byte stream.
        
        Args:
            data: H.264 byte stream with start codes
            
        Returns:
            List of NAL units without start codes
        """
        nal_units = []
        start_codes = []
        
        # Find all start codes (0x000001 or 0x00000001)
        i = 0
        while i < len(data) - 3:
            if data[i:i+4] == b'\x00\x00\x00\x01':
                start_codes.append((i, 4))
                i += 4
            elif data[i:i+3] == b'\x00\x00\x01':
                start_codes.append((i, 3))
                i += 3
            else:
                i += 1
                
        # Extract NAL units between start codes
        for j, (pos, code_len) in enumerate(start_codes):
            start = pos + code_len
            if j + 1 < len(start_codes):
                end = start_codes[j + 1][0]
            else:
                end = len(data)
            if start < end:
                nal_units.append(data[start:end])
                
        return nal_units


class AudioPacketizer(RTPPacketizer):
    """RTP packetizer for audio streams.
    
    Supports PCM (G.711 μ-law/A-law), AAC, and OPUS audio.
    """
    
    def __init__(
        self,
        payload_type: int = 0,  # 0=PCMU, 8=PCMA
        clock_rate: int = 8000,
        ssrc: Optional[int] = None,
        samples_per_packet: int = 160,  # 20ms at 8kHz
    ):
        super().__init__(
            payload_type=payload_type,
            clock_rate=clock_rate,
            ssrc=ssrc,
            mtu=1400,
        )
        self.samples_per_packet = samples_per_packet
        
    def packetize_pcm(
        self,
        pcm_data: bytes,
        timestamp: Optional[int] = None,
    ) -> Generator[RTPPacket, None, None]:
        """Packetize PCM audio data.
        
        Args:
            pcm_data: PCM audio samples
            timestamp: RTP timestamp (current time if None)
            
        Yields:
            RTP packets
        """
        if timestamp is None:
            timestamp = self.get_timestamp()
            
        # Split into chunks based on samples per packet
        bytes_per_sample = 1  # G.711 is 8 bits per sample
        chunk_size = self.samples_per_packet * bytes_per_sample
        
        offset = 0
        while offset < len(pcm_data):
            chunk = pcm_data[offset:offset + chunk_size]
            
            yield self.create_packet(
                payload=chunk,
                timestamp=timestamp,
                marker=(offset == 0),  # Marker on first packet of talkspurt
            )
            
            timestamp = (timestamp + len(chunk)) & 0xFFFFFFFF
            offset += chunk_size
            
    def packetize_aac(
        self,
        aac_frame: bytes,
        timestamp: Optional[int] = None,
    ) -> Generator[RTPPacket, None, None]:
        """Packetize an AAC audio frame (RFC 3640).
        
        Args:
            aac_frame: Raw AAC frame (without ADTS header)
            timestamp: RTP timestamp (current time if None)
            
        Yields:
            RTP packets with AU headers
        """
        if timestamp is None:
            timestamp = self.get_timestamp()
            
        # AU header for AAC-hbr mode
        # AU-headers-length (16 bits) + AU-size (13 bits) + AU-Index (3 bits)
        au_size = len(aac_frame)
        au_header_length = 16  # bits
        au_header = struct.pack('!H', au_header_length) + \
                   struct.pack('!H', (au_size << 3) & 0xFFF8)
        
        payload = au_header + aac_frame
        
        yield self.create_packet(
            payload=payload,
            timestamp=timestamp,
            marker=True,
        )


class RTCPPacket:
    """Base class for RTCP packets."""
    
    # RTCP packet types
    SR = 200   # Sender Report
    RR = 201   # Receiver Report
    SDES = 202  # Source Description
    BYE = 203  # Goodbye
    APP = 204  # Application-defined
    
    @staticmethod
    def build_sender_report(
        ssrc: int,
        ntp_timestamp: Tuple[int, int],
        rtp_timestamp: int,
        packet_count: int,
        octet_count: int,
    ) -> bytes:
        """Build an RTCP Sender Report packet.
        
        Args:
            ssrc: SSRC of sender
            ntp_timestamp: NTP timestamp as (seconds, fraction) tuple
            rtp_timestamp: RTP timestamp of last packet
            packet_count: Total packets sent
            octet_count: Total bytes sent
            
        Returns:
            RTCP SR packet bytes
        """
        # Header: V=2, P=0, RC=0, PT=200, length
        version = 2
        padding = 0
        rc = 0  # No report blocks
        pt = RTCPPacket.SR
        length = 6  # 6 32-bit words after header (minus 1)
        
        header = struct.pack(
            '!BBH',
            (version << 6) | (padding << 5) | rc,
            pt,
            length,
        )
        
        ntp_sec, ntp_frac = ntp_timestamp
        body = struct.pack(
            '!IIIII',
            ssrc,
            ntp_sec,
            ntp_frac,
            rtp_timestamp,
            packet_count,
        ) + struct.pack('!I', octet_count)
        
        return header + body
    
    @staticmethod
    def build_sdes(ssrc: int, cname: str) -> bytes:
        """Build an RTCP SDES (Source Description) packet.
        
        Args:
            ssrc: SSRC identifier
            cname: Canonical name (email or identifier)
            
        Returns:
            RTCP SDES packet bytes
        """
        cname_bytes = cname.encode('utf-8')[:255]
        
        # SDES item: type=1 (CNAME), length, value
        sdes_item = bytes([1, len(cname_bytes)]) + cname_bytes
        
        # Pad to 32-bit boundary
        padding_needed = (4 - ((4 + len(sdes_item)) % 4)) % 4
        sdes_chunk = struct.pack('!I', ssrc) + sdes_item + bytes(padding_needed + 1)
        
        # Header
        version = 2
        padding = 0
        sc = 1  # Source count
        pt = RTCPPacket.SDES
        length = (len(sdes_chunk) // 4)
        
        header = struct.pack(
            '!BBH',
            (version << 6) | (padding << 5) | sc,
            pt,
            length,
        )
        
        return header + sdes_chunk
    
    @staticmethod
    def build_bye(ssrcs: List[int], reason: Optional[str] = None) -> bytes:
        """Build an RTCP BYE packet.
        
        Args:
            ssrcs: List of SSRC identifiers
            reason: Optional reason for leaving
            
        Returns:
            RTCP BYE packet bytes
        """
        version = 2
        padding = 0
        sc = len(ssrcs)
        pt = RTCPPacket.BYE
        
        body = b''.join(struct.pack('!I', ssrc) for ssrc in ssrcs)
        
        if reason:
            reason_bytes = reason.encode('utf-8')[:255]
            body += bytes([len(reason_bytes)]) + reason_bytes
            # Pad to 32-bit boundary
            padding_needed = (4 - ((len(body)) % 4)) % 4
            body += bytes(padding_needed)
            
        length = len(body) // 4
        
        header = struct.pack(
            '!BBH',
            (version << 6) | (padding << 5) | sc,
            pt,
            length,
        )
        
        return header + body


def get_ntp_timestamp() -> Tuple[int, int]:
    """Get current time as NTP timestamp.
    
    Returns:
        Tuple of (seconds since 1900, fractional seconds)
    """
    # NTP epoch is January 1, 1900
    # Unix epoch is January 1, 1970
    # Difference is 70 years = 2208988800 seconds
    NTP_DELTA = 2208988800
    
    now = time.time()
    ntp_sec = int(now) + NTP_DELTA
    ntp_frac = int((now % 1) * (2**32))
    
    return (ntp_sec, ntp_frac)
