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

"""RTSP Protocol constants and utilities."""

from enum import IntEnum
from typing import Dict

# RTSP Version
RTSP_VERSION = "RTSP/1.0"

# Default ports
DEFAULT_RTSP_PORT = 554
DEFAULT_RTP_PORT = 5004
DEFAULT_RTCP_PORT = 5005


class RTSPMethod(IntEnum):
    """RTSP request methods."""
    OPTIONS = 1
    DESCRIBE = 2
    SETUP = 3
    PLAY = 4
    PAUSE = 5
    TEARDOWN = 6
    GET_PARAMETER = 7
    SET_PARAMETER = 8
    ANNOUNCE = 9
    RECORD = 10


class RTSPStatusCode(IntEnum):
    """RTSP response status codes."""
    # 1xx Informational
    CONTINUE = 100

    # 2xx Success
    OK = 200
    CREATED = 201
    LOW_ON_STORAGE = 250

    # 3xx Redirection
    MULTIPLE_CHOICES = 300
    MOVED_PERMANENTLY = 301
    MOVED_TEMPORARILY = 302
    SEE_OTHER = 303
    NOT_MODIFIED = 304
    USE_PROXY = 305

    # 4xx Client Error
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    PAYMENT_REQUIRED = 402
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    NOT_ACCEPTABLE = 406
    PROXY_AUTH_REQUIRED = 407
    REQUEST_TIMEOUT = 408
    GONE = 410
    LENGTH_REQUIRED = 411
    PRECONDITION_FAILED = 412
    REQUEST_ENTITY_TOO_LARGE = 413
    REQUEST_URI_TOO_LONG = 414
    UNSUPPORTED_MEDIA_TYPE = 415
    PARAMETER_NOT_UNDERSTOOD = 451
    CONFERENCE_NOT_FOUND = 452
    NOT_ENOUGH_BANDWIDTH = 453
    SESSION_NOT_FOUND = 454
    METHOD_NOT_VALID = 455
    HEADER_FIELD_NOT_VALID = 456
    INVALID_RANGE = 457
    PARAMETER_READ_ONLY = 458
    AGGREGATE_OPERATION_NOT_ALLOWED = 459
    ONLY_AGGREGATE_OPERATION_ALLOWED = 460
    UNSUPPORTED_TRANSPORT = 461
    DESTINATION_UNREACHABLE = 462

    # 5xx Server Error
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504
    VERSION_NOT_SUPPORTED = 505
    OPTION_NOT_SUPPORTED = 551


# Status code reason phrases
STATUS_PHRASES: Dict[int, str] = {
    100: "Continue",
    200: "OK",
    201: "Created",
    250: "Low on Storage Space",
    300: "Multiple Choices",
    301: "Moved Permanently",
    302: "Moved Temporarily",
    303: "See Other",
    304: "Not Modified",
    305: "Use Proxy",
    400: "Bad Request",
    401: "Unauthorized",
    402: "Payment Required",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    406: "Not Acceptable",
    407: "Proxy Authentication Required",
    408: "Request Timeout",
    410: "Gone",
    411: "Length Required",
    412: "Precondition Failed",
    413: "Request Entity Too Large",
    414: "Request-URI Too Long",
    415: "Unsupported Media Type",
    451: "Parameter Not Understood",
    452: "Conference Not Found",
    453: "Not Enough Bandwidth",
    454: "Session Not Found",
    455: "Method Not Valid in This State",
    456: "Header Field Not Valid for Resource",
    457: "Invalid Range",
    458: "Parameter Is Read-Only",
    459: "Aggregate Operation Not Allowed",
    460: "Only Aggregate Operation Allowed",
    461: "Unsupported Transport",
    462: "Destination Unreachable",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
    505: "RTSP Version Not Supported",
    551: "Option not supported",
}


# RTP Payload types
class RTPPayloadType(IntEnum):
    """Standard RTP payload types."""
    PCMU = 0        # G.711 μ-law
    PCMA = 8        # G.711 A-law
    G722 = 9
    L16_STEREO = 10
    L16_MONO = 11
    MPA = 14        # MPEG Audio
    G728 = 15
    G729 = 18
    H261 = 31
    MPV = 32        # MPEG Video
    MP2T = 33       # MPEG-2 TS
    H263 = 34
    # Dynamic payload types (96-127)
    DYNAMIC_MIN = 96
    DYNAMIC_MAX = 127


# Common dynamic payload types used in motionEye
PAYLOAD_TYPE_H264 = 96
PAYLOAD_TYPE_AAC = 97
PAYLOAD_TYPE_OPUS = 98
PAYLOAD_TYPE_PCMU = 0
PAYLOAD_TYPE_PCMA = 8


def get_status_phrase(code: int) -> str:
    """Get the reason phrase for an RTSP status code."""
    return STATUS_PHRASES.get(code, "Unknown")


def parse_transport_header(transport: str) -> Dict[str, str]:
    """Parse an RTSP Transport header.
    
    Args:
        transport: The Transport header value
        
    Returns:
        Dictionary of transport parameters
    """
    params = {}
    parts = transport.split(';')
    
    for part in parts:
        part = part.strip()
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.strip()] = value.strip()
        else:
            # Protocol specification like RTP/AVP or RTP/AVP/TCP
            if '/' in part:
                params['protocol'] = part
            else:
                params[part] = True
                
    return params


def build_transport_header(params: Dict[str, str]) -> str:
    """Build an RTSP Transport header from parameters.
    
    Args:
        params: Dictionary of transport parameters
        
    Returns:
        Formatted Transport header value
    """
    parts = []
    
    # Protocol must come first
    if 'protocol' in params:
        parts.append(params['protocol'])
        
    for key, value in params.items():
        if key == 'protocol':
            continue
        if value is True:
            parts.append(key)
        else:
            parts.append(f'{key}={value}')
            
    return ';'.join(parts)
