<!-- version: 2025-08-26 -->

2025-08-26
- Added FFMPEG audio codec mapping and optional audio stream inclusion during conversions.
- Ensured converted files use the proper extension matching video and audio content.
- Enabled GET/POST handling for `audio_*` parameters in config and preference APIs.
- Validated and persisted audio configuration values.
- Added camera UI fields for enabling audio, selecting devices, codec and bitrate.
- Updated translation template and bumped version to 0.43.1b8.

2025-08-25
- Added audio configuration support (sound_device, sound_enabled, ffmpeg_audio_codec, ffmpeg_audio_bitrate).
- Introduced corresponding camera keys (audio_device, audio_codec, audio_bitrate) with default handling.
- Added Motion option mappings for audio settings across versions.
- Defined global audio defaults in settings.py.
- Added audio device enumeration and `has_audio_support` template helper.
