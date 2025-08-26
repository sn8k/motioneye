<!-- version: 2025-08-26.1 -->

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

## Translation Compilation
The `l10n/make_mo.sh` script builds binary `.mo` files from each `motioneye.po` or `motioneye.js.po` found under `motioneye/locale/*/LC_MESSAGES/`.

Run the script without arguments to compile every locale:

```
l10n/make_mo.sh
```

Install the script system-wide:

```
l10n/make_mo.sh --install [/path/to/make_mo]
```

Remove an installed copy:

```
l10n/make_mo.sh --remove [/path/to/make_mo]
```
