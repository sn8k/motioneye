<!-- version: 2025-08-27.2 -->

# User Manual

## Audio Prerequisites
motionEye relies on **PyAudio** and **ffmpeg-python** for sound features. Install `alsa-utils` and `ffmpeg` on the host and expose `/dev/snd` to containers to access audio hardware.

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
It requires `msgfmt` and optionally `po2json` when generating JSON files. The script exits early with a clear message if a required tool is missing.

Run the script without arguments to compile every locale:

```
l10n/make_mo.sh
```

Install the script system-wide and compile the translations:

```
l10n/make_mo.sh --install [/path/to/make_mo]
```

Remove an installed copy:

```
l10n/make_mo.sh --remove [/path/to/make_mo]
```

Generate JSON translations alongside `.mo` files:

```
l10n/make_mo.sh --json
```

## JavaScript Translation Update
To refresh the browser translation files:

1. Regenerate the template:

```
make -B motioneye/locale/motioneye.js.pot
```

2. Merge the template into each locale:

```
for p in motioneye/locale/*/LC_MESSAGES/motioneye.js.po; do
    msgmerge --no-wrap -N -U "$p" motioneye/locale/motioneye.js.pot
done
```

3. Set `Project-Id-Version: motionEye 0.43.1b9` and update the `PO-Revision-Date` header in every `.js.po`.

4. Compile the JSON assets:

```
make motioneye/static/js/motioneye.*.json
```

5. Confirm that the new audio strings appear in the generated JSON files.
