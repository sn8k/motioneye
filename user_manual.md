<!-- version: 2025-08-25 -->

# User Manual

## Audio Configuration
motionEye supports audio options per camera:
- **Audio Device** – maps to Motion's `sound_device`.
- **Audio Enabled** – maps to `sound_enabled`.
- **Audio Codec** – maps to `ffmpeg_audio_codec`.
- **Audio Bitrate** – maps to `ffmpeg_audio_bitrate`.

Global defaults reside in `settings.py` (`AUDIO_DEVICE`, `AUDIO_ENABLED`, `AUDIO_CODEC`, `AUDIO_BITRATE`).
