# Copyright (c) 2025 motionEye contributors
# This file is part of motionEye.

"""Tests for RTSP server components."""

import struct
import time
import unittest

from motioneye.rtspserver.rtp import (
    RTPPacket,
    H264Packetizer,
    AudioPacketizer,
    RTCPPacket,
    get_ntp_timestamp,
)
from motioneye.rtspserver.sdp import SDPGenerator, generate_simple_sdp
from motioneye.rtspserver.protocol import (
    parse_transport_header,
    build_transport_header,
    get_status_phrase,
    RTSPStatusCode,
)


class TestRTPPacket(unittest.TestCase):
    """Tests for RTP packet serialization."""
    
    def test_create_packet(self):
        """Test creating and serializing an RTP packet."""
        packet = RTPPacket(
            payload_type=96,
            sequence_number=1234,
            timestamp=567890,
            ssrc=0x12345678,
            marker=True,
            payload=b'test payload',
        )
        
        data = packet.to_bytes()
        
        # Check header
        self.assertEqual(len(data), 12 + len(b'test payload'))
        
        # Version should be 2
        self.assertEqual((data[0] >> 6) & 0x03, 2)
        
        # Marker bit should be set
        self.assertTrue(data[1] & 0x80)
        
        # Payload type should be 96
        self.assertEqual(data[1] & 0x7F, 96)
        
        # Sequence number
        seq = struct.unpack('!H', data[2:4])[0]
        self.assertEqual(seq, 1234)
        
        # Timestamp
        ts = struct.unpack('!I', data[4:8])[0]
        self.assertEqual(ts, 567890)
        
        # SSRC
        ssrc = struct.unpack('!I', data[8:12])[0]
        self.assertEqual(ssrc, 0x12345678)
        
    def test_parse_packet(self):
        """Test parsing an RTP packet."""
        original = RTPPacket(
            payload_type=97,
            sequence_number=9999,
            timestamp=123456,
            ssrc=0xABCDEF01,
            marker=False,
            payload=b'audio data',
        )
        
        data = original.to_bytes()
        parsed = RTPPacket.from_bytes(data)
        
        self.assertEqual(parsed.payload_type, 97)
        self.assertEqual(parsed.sequence_number, 9999)
        self.assertEqual(parsed.timestamp, 123456)
        self.assertEqual(parsed.ssrc, 0xABCDEF01)
        self.assertFalse(parsed.marker)
        self.assertEqual(parsed.payload, b'audio data')


class TestH264Packetizer(unittest.TestCase):
    """Tests for H.264 video packetization."""
    
    def test_single_nal_unit(self):
        """Test packetizing a small NAL unit."""
        packetizer = H264Packetizer(payload_type=96)
        
        # Small NAL unit (will fit in single packet)
        nal_data = b'\x65' + b'\x00' * 100  # IDR frame header + data
        
        packets = list(packetizer.packetize_nal(nal_data, timestamp=12345))
        
        # Should produce single packet
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].payload, nal_data)
        self.assertTrue(packets[0].marker)  # Last packet of access unit
        
    def test_fragmented_nal_unit(self):
        """Test packetizing a large NAL unit with FU-A fragmentation."""
        packetizer = H264Packetizer(payload_type=96, mtu=200)
        
        # Large NAL unit that will require fragmentation
        nal_data = b'\x65' + b'\xAB' * 500  # IDR frame header + data
        
        packets = list(packetizer.packetize_nal(nal_data, timestamp=12345))
        
        # Should produce multiple packets
        self.assertGreater(len(packets), 1)
        
        # First packet should have FU-A start indicator
        first_payload = packets[0].payload
        fu_indicator = first_payload[0]
        fu_header = first_payload[1]
        
        # FU indicator type should be 28 (FU-A)
        self.assertEqual(fu_indicator & 0x1F, 28)
        
        # Start bit should be set in first fragment
        self.assertTrue(fu_header & 0x80)
        
        # Last packet should have marker bit and end indicator
        self.assertTrue(packets[-1].marker)
        last_fu_header = packets[-1].payload[1]
        self.assertTrue(last_fu_header & 0x40)  # End bit
        
    def test_extract_nal_units(self):
        """Test extracting NAL units from H.264 byte stream."""
        # Create test stream with multiple NAL units
        stream = (
            b'\x00\x00\x00\x01\x67\x42\x00\x1f'  # SPS
            b'\x00\x00\x00\x01\x68\xce\x3c\x80'  # PPS
            b'\x00\x00\x01\x65\x88\x84'          # IDR (3-byte start code)
        )
        
        nals = H264Packetizer._extract_nal_units(stream)
        
        self.assertEqual(len(nals), 3)
        self.assertEqual(nals[0][0] & 0x1F, 7)  # SPS type
        self.assertEqual(nals[1][0] & 0x1F, 8)  # PPS type
        self.assertEqual(nals[2][0] & 0x1F, 5)  # IDR type


class TestAudioPacketizer(unittest.TestCase):
    """Tests for audio packetization."""
    
    def test_pcm_packetization(self):
        """Test packetizing PCM audio."""
        packetizer = AudioPacketizer(
            payload_type=0,  # PCMU
            clock_rate=8000,
            samples_per_packet=160,
        )
        
        # 40ms of audio (320 samples)
        audio_data = b'\x80' * 320
        
        packets = list(packetizer.packetize_pcm(audio_data))
        
        # Should produce 2 packets (160 samples each)
        self.assertEqual(len(packets), 2)
        
        # First packet should have marker bit (start of talkspurt)
        self.assertTrue(packets[0].marker)


class TestSDPGenerator(unittest.TestCase):
    """Tests for SDP generation."""
    
    def test_basic_sdp(self):
        """Test generating basic SDP."""
        sdp = generate_simple_sdp(
            server_ip='192.168.1.100',
            session_name='Test Camera',
            has_audio=False,
        )
        
        # Check required fields
        self.assertIn('v=0', sdp)
        self.assertIn('o=-', sdp)
        self.assertIn('s=Test Camera', sdp)
        self.assertIn('c=IN IP4 192.168.1.100', sdp)
        self.assertIn('m=video', sdp)
        self.assertIn('a=rtpmap:96 H264/90000', sdp)
        
    def test_sdp_with_audio(self):
        """Test generating SDP with audio."""
        generator = SDPGenerator(
            server_name="motionEye",
            session_name="Camera with Audio",
        )
        
        sdp = generator.generate(
            server_ip='10.0.0.1',
            has_video=True,
            has_audio=True,
            video_codec='H264',
            audio_codec='PCMU',
        )
        
        # Should have both video and audio media descriptions
        self.assertIn('m=video', sdp)
        self.assertIn('m=audio', sdp)
        self.assertIn('a=rtpmap:0 PCMU/8000/1', sdp)


class TestRTSPProtocol(unittest.TestCase):
    """Tests for RTSP protocol utilities."""
    
    def test_parse_transport_header(self):
        """Test parsing Transport header."""
        # UDP transport
        transport = "RTP/AVP;unicast;client_port=50000-50001"
        params = parse_transport_header(transport)
        
        self.assertEqual(params['protocol'], 'RTP/AVP')
        self.assertTrue(params.get('unicast'))
        self.assertEqual(params['client_port'], '50000-50001')
        
        # TCP interleaved transport
        transport = "RTP/AVP/TCP;unicast;interleaved=0-1"
        params = parse_transport_header(transport)
        
        self.assertEqual(params['protocol'], 'RTP/AVP/TCP')
        self.assertEqual(params['interleaved'], '0-1')
        
    def test_build_transport_header(self):
        """Test building Transport header."""
        params = {
            'protocol': 'RTP/AVP',
            'unicast': True,
            'client_port': '50000-50001',
            'server_port': '60000-60001',
        }
        
        header = build_transport_header(params)
        
        self.assertIn('RTP/AVP', header)
        self.assertIn('unicast', header)
        self.assertIn('client_port=50000-50001', header)
        self.assertIn('server_port=60000-60001', header)
        
    def test_status_phrases(self):
        """Test status code phrases."""
        self.assertEqual(get_status_phrase(200), 'OK')
        self.assertEqual(get_status_phrase(404), 'Not Found')
        self.assertEqual(get_status_phrase(454), 'Session Not Found')
        self.assertEqual(get_status_phrase(RTSPStatusCode.UNAUTHORIZED), 'Unauthorized')


class TestRTCPPacket(unittest.TestCase):
    """Tests for RTCP packet generation."""
    
    def test_sender_report(self):
        """Test building RTCP Sender Report."""
        sr = RTCPPacket.build_sender_report(
            ssrc=0x12345678,
            ntp_timestamp=(3842041088, 0),  # Fixed NTP time
            rtp_timestamp=12345,
            packet_count=100,
            octet_count=50000,
        )
        
        # Check packet type (200 = SR)
        self.assertEqual(sr[1], 200)
        
        # Check SSRC
        ssrc = struct.unpack('!I', sr[4:8])[0]
        self.assertEqual(ssrc, 0x12345678)
        
    def test_sdes_packet(self):
        """Test building RTCP SDES packet."""
        sdes = RTCPPacket.build_sdes(
            ssrc=0xABCDEF01,
            cname='test@motioneye.local',
        )
        
        # Check packet type (202 = SDES)
        self.assertEqual(sdes[1], 202)
        
        # CNAME should be in the packet
        self.assertIn(b'test@motioneye.local', sdes)
        
    def test_bye_packet(self):
        """Test building RTCP BYE packet."""
        bye = RTCPPacket.build_bye(
            ssrcs=[0x12345678],
            reason='Session ended',
        )
        
        # Check packet type (203 = BYE)
        self.assertEqual(bye[1], 203)


class TestNTPTimestamp(unittest.TestCase):
    """Tests for NTP timestamp generation."""
    
    def test_ntp_timestamp(self):
        """Test NTP timestamp generation."""
        ntp_sec, ntp_frac = get_ntp_timestamp()
        
        # NTP seconds should be reasonable (after year 2020)
        # 2020-01-01 in NTP = 3786825600
        self.assertGreater(ntp_sec, 3786825600)
        
        # Fraction should be valid 32-bit value
        self.assertGreaterEqual(ntp_frac, 0)
        self.assertLess(ntp_frac, 2**32)


if __name__ == '__main__':
    unittest.main()
