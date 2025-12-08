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

"""Helper to expose microphone audio over RTSP for reuse alongside video streams."""

import logging
import os
import re
import subprocess
from typing import List, Optional, Tuple

from motioneye import mediafiles, settings

_process: Optional[subprocess.Popen] = None

_CARD_PATTERN = re.compile(r"\s*(\d+)\s+\[([^\]]+)\s*\]:\s+([^-]+)-\s*(.*)")


def _parse_cards() -> List[Tuple[int, str, str]]:
    """Parses ``/proc/asound/cards`` and returns a list of card info tuples.

    Each tuple is ``(index, short_name, description)``. We keep parsing lean to
    avoid external dependencies while still letting users pick devices by a
    stable name instead of volatile numeric identifiers.
    """

    try:
        with open('/proc/asound/cards', 'r') as cards_file:
            content = cards_file.read().splitlines()
    except OSError:
        logging.debug('/proc/asound/cards missing, cannot resolve audio devices by name')
        return []

    cards: List[Tuple[int, str, str]] = []
    for line in content:
        match = _CARD_PATTERN.match(line)
        if not match:
            continue

        index = int(match.group(1))
        short_name = match.group(2).strip()
        description = f"{match.group(3).strip()} {match.group(4).strip()}".strip()
        cards.append((index, short_name, description))

    return cards


def _resolve_audio_device() -> str:
    """Returns the ALSA device string to be used for audio capture.

    Prefers resolving ``settings.AUDIO_DEVICE_NAME`` against ALSA card names to
    avoid brittle numeric IDs. Falls back to ``settings.AUDIO_DEVICE``.
    """

    requested_name = getattr(settings, 'AUDIO_DEVICE_NAME', None)

    if requested_name:
        cards = _parse_cards()
        requested_lower = requested_name.lower()

        for index, short_name, description in cards:
            if requested_lower in short_name.lower() or requested_lower in description.lower():
                device = f'plughw:{index},0'
                logging.info(
                    'Resolved audio device name "%s" to ALSA device "%s" (%s)',
                    requested_name,
                    device,
                    description or short_name,
                )
                return device

        logging.warning(
            'Requested audio device name "%s" not found, falling back to AUDIO_DEVICE',
            requested_name,
        )

    return getattr(settings, 'AUDIO_DEVICE', 'plug:default')


def start():
    """Starts a minimal RTSP audio restream using ffmpeg.

    The restream is intentionally simple: we listen on the configured RTSP
    port and expose AAC audio captured from the configured ALSA device. The
    resulting URL is ``rtsp://<listen addr>:<port>/audio`` which can be
    ingested by the existing RTSP pipeline together with video.
    """

    global _process

    if not settings.AUDIO_ENABLED:
        logging.debug('RTSP audio streaming disabled via settings')
        return

    if _process and _process.poll() is None:
        logging.debug('RTSP audio streaming already running')
        return

    ffmpeg_info = mediafiles.find_ffmpeg()
    if ffmpeg_info is None:
        logging.warning('ffmpeg not available, cannot start RTSP audio restream')
        return

    binary, version, _codecs = ffmpeg_info
    logging.info(f'ffmpeg {version} detected, starting RTSP audio restream')

    audio_device = _resolve_audio_device()
    audio_port = getattr(settings, 'AUDIO_RTSP_PORT', 8555)
    listen_address = getattr(settings, 'LISTEN', '0.0.0.0')

    args = [
        binary,
        '-hide_banner',
        '-loglevel',
        'warning',
        '-f',
        'alsa',
        '-i',
        audio_device,
        '-ac',
        '1',
        '-ar',
        '16000',
        '-c:a',
        'aac',
        '-f',
        'rtsp',
        '-rtsp_flags',
        'listen',
        '-rtsp_transport',
        'tcp',
        f'rtsp://{listen_address}:{audio_port}/audio',
    ]

    audio_log = os.path.join(settings.LOG_PATH, 'audio_rtsp.log')
    log_file = open(audio_log, 'w')

    try:
        _process = subprocess.Popen(args, stdout=log_file, stderr=log_file)
    except Exception as e:  # pragma: no cover - defensive logging
        logging.error(f'could not start RTSP audio restream: {e}', exc_info=True)
        return

    logging.info(
        'RTSP audio restream started on %s:%s from device "%s"',
        listen_address,
        audio_port,
        audio_device,
    )


def stop():
    """Stops the RTSP audio restream if running."""

    global _process

    if not _process:
        return

    try:
        _process.terminate()
        _process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _process.kill()
    except Exception as e:  # pragma: no cover - defensive logging
        logging.error(f'error stopping RTSP audio restream: {e}', exc_info=True)
    finally:
        _process = None
