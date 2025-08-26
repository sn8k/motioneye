<!-- version: 2025-08-26.4 -->

2025-08-26
- Added FFMPEG audio codec mapping and optional audio stream inclusion during conversions.
- Ensured converted files use the proper extension matching video and audio content.
- Enabled GET/POST handling for `audio_*` parameters in config and preference APIs.
- Validated and persisted audio configuration values.
- Added camera UI fields for enabling audio, selecting devices, codec and bitrate.
- Updated translation template and bumped version to 0.43.1b8.
- Refreshed JavaScript translation source strings.
- Synchronized all locale PO files with the latest template and incremented `Project-Id-Version`.
- Filled audio msgstr entries for all locales and updated revision dates; bumped Project-Id-Version to 0.43.1b9.
- Restored original .mo translation binaries to avoid binary diffs.
- Added make_mo.sh script to compile translation files with install/remove options.

2025-08-25
- Added audio configuration support (sound_device, sound_enabled, ffmpeg_audio_codec, ffmpeg_audio_bitrate).
- Introduced corresponding camera keys (audio_device, audio_codec, audio_bitrate) with default handling.
- Added Motion option mappings for audio settings across versions.
- Defined global audio defaults in settings.py.
- Added audio device enumeration and `has_audio_support` template helper.
