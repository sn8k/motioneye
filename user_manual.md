<!-- version: 2025-08-26 -->

# User Manual

## Audio Configuration
motionEye supports audio options per camera:
- **Audio Device** – maps to Motion's `sound_device`.
- **Audio Enabled** – maps to `sound_enabled`.
- **Audio Codec** – maps to `ffmpeg_audio_codec`.
- **Audio Bitrate** – maps to `ffmpeg_audio_bitrate`.
- UI now provides a checkbox to enable audio and selectors for device, codec and bitrate.

Global defaults reside in `settings.py` (`AUDIO_DEVICE`, `AUDIO_ENABLED`, `AUDIO_CODEC`, `AUDIO_BITRATE`).
Configuration and preference APIs accept these options via `audio_*` fields in GET or POST requests.

## Audio Detection
Use `list_audio_devices()` to enumerate capture hardware. Templates can check
`has_audio_support` to determine if audio devices are available.

## Timelapse Audio
During video conversion, motionEye now maps existing audio streams with `-map 0:a` and
encodes them using a codec from `FFMPEG_AUDIO_CODEC_MAPPING`. Output files automatically
use the correct extension (e.g., `.mp4`) when video and audio are present.
