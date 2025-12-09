# Changelog

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [0.43.1b26]

### Corrigé

- **Bug critique RTSP : aucune vidéo reçue par les clients** (`rtspserver/server.py`) :
  - **Cause** : Le session stockait l'URL demandée par le client (ex: `/stream`) au lieu de l'ID réel du stream (ex: `cam2`)
  - **Conséquence** : Le broadcast de frames ne matchait pas les sessions (session.stream_url="stream" ≠ stream_id="cam2")
  - **Solution** : Dans `handle_setup()`, résolution de l'URL demandée vers l'ID réel via `get_stream_config()`
  - Ajout de logs de debug pour tracer le mapping URL → stream_id

### Amélioré

- **Debug RTSP** (`rtspserver/session.py`) :
  - Ajout de logs dans `broadcast_video_frame()` pour tracer le matching session/stream

## [0.43.1b25]

### Ajouté

- **Script d'installation** (`setup_script_from_source.sh`) :
  - Nouvelle fonction `setup_motion_user()` qui ajoute l'utilisateur `motion` aux groupes requis
  - Groupes ajoutés : `video` (caméras), `audio` (microphones ALSA), `gpio` (Raspberry Pi)
  - Appelée automatiquement lors de `install` et `update`
  - Résout le problème "no soundcards found" quand motionEye tourne sous l'utilisateur `motion`

### Amélioré

- **Détection audio** (`audioctl.py`) :
  - Logs plus détaillés pour diagnostiquer les problèmes de permissions

## [0.43.1b24]

### Corrigé

- **Détection audio ALSA** (`audioctl.py`) :
  - Parsing simplifié et plus robuste avec `re.search()` au lieu de `re.match()`
  - Logs au niveau INFO pour faciliter le debug
  - Gestion des caractères spéciaux (ex: ® dans "Microsoft® LifeCam")
  - Extraction du nom depuis les premiers crochets `[description]`

## [0.43.1b23]

### Supprimé

- **Code audio legacy supprimé** :
  - Suppression de `motioneye/audiostream.py` (FFmpeg restreamer legacy)
  - Suppression de la section "Audio Stream (Legacy)" dans l'UI
  - Suppression des settings legacy : `AUDIO_ENABLED`, `AUDIO_DEVICE`, `AUDIO_DEVICE_NAME`, `AUDIO_VIDEO_SOURCE`, `AUDIO_RTSP_PORT`, `AUDIO_RTSP_PATH`
  - Nettoyage de `audioctl.py` : conserve uniquement `detect_audio_devices()` et `get_default_audio_device()`

### Corrigé

- **Détection audio ALSA améliorée** (`audioctl.py`) :
  - Ajout de logs de debug pour diagnostiquer la détection
  - Option "Default Audio Device" ajoutée seulement si aucun device réel trouvé
  - Affiche le nom complet du périphérique (ex: "Microsoft® LifeCam HD-5000")

### Amélioré

- **Logs RTSP étendus** (`rtspserver/server.py`) :
  - Log de chaque requête RTSP (OPTIONS, DESCRIBE, SETUP, PLAY)
  - Log du code de réponse pour chaque requête
  - Facilite le debug des connexions clients

## [0.43.1b22]

### Corrigé

#### Détection audio - Regex et périphérique par défaut (2025-12-09)

Correction de la détection des périphériques audio ALSA.

**Problème :** Les périphériques avec des noms alphanumériques (ex: "HD5000" pour Microsoft® LifeCam HD-5000) n'étaient pas détectés correctement, affichant "Périphérique par défaut" au lieu du vrai nom.

**Corrections apportées :**

- `motioneye/audioctl.py` :
  - Regex améliorée : `(\w+)` → `(\S+)` pour capturer les noms de device ALSA non-standards
  - Format device changé de `plug:hw:` à `plughw:` (format ALSA standard)
  - Nettoyage des descriptions avec suffixes `[subdesc]`
  - `get_default_audio_device()` retourne maintenant le premier périphérique matériel réel au lieu de "plug:default"

#### Persistance des settings RTSP (2025-12-09)

**Problème :** Les paramètres RTSP n'étaient pas persistants car `RTSP_AUDIO_DEVICE` n'était pas déclaré dans `settings.py`.

**Correction :**

- `motioneye/settings.py` :
  - Ajout de `RTSP_AUDIO_DEVICE = None` pour permettre le chargement depuis le fichier de config

### Modifié

- `motioneye/__init__.py` : Version 0.43.1b22+20251209

## [0.43.1b21] - 2025-12-09

### Corrigé

#### Serveur RTSP - Streaming vidéo (2025-12-09)

Correction du serveur RTSP qui n'envoyait pas les données vidéo aux clients.

**Problème :** Le serveur RTSP acceptait les connexions mais ne transmettait aucune donnée.

**Corrections apportées :**

- `motioneye/rtspserver/session.py` :
  - Amélioration de `broadcast_video_frame()` et `broadcast_audio_samples()` pour matcher correctement les sessions avec les streams
  - Le matching utilise maintenant plusieurs méthodes (comparaison exacte, containment, fallback)
  - Ajout de try/except pour éviter les crashes silencieux

- `motioneye/rtspserver/source.py` :
  - Ajout de logs détaillés dans `start()` avec la commande FFmpeg complète
  - Amélioration de `_build_ffmpeg_command()` avec options MJPEG explicites
  - Ajout du thread `_read_stderr` pour capturer les erreurs FFmpeg
  - Logs de progression dans `_read_video_output()` (toutes les 100 frames)
  - Affichage du code de sortie FFmpeg en cas d'erreur

#### Interface utilisateur - Suppression du doublon Audio (2025-12-09)

Suppression de la section "Audio RTSP" redondante avec "RTSP Server".

**Modifications :**

- `motioneye/audioctl.py` - Refonte :
  - Section renommée "Audio Stream (Legacy)" pour distinguer du serveur natif
  - Préfixe `audio_legacy_` pour toutes les options
  - Description clarifiée : "FFmpeg-based audio/video muxing"

- `motioneye/rtspserver/config.py` :
  - Ajout de l'option `rtsp_audio_device` avec sélection par dropdown
  - Import des fonctions de détection depuis `audioctl`

- `motioneye/rtspserver/integration.py` :
  - Utilisation de `RTSP_AUDIO_DEVICE` en priorité sur `AUDIO_DEVICE`

### Modifié

- `motioneye/__init__.py` : Version 0.43.1b21+20251209

## [0.43.1b20] - 2025-12-08

### Ajouté

#### Détection automatique des périphériques audio (2025-12-09)

Amélioration de la gestion des périphériques audio avec détection automatique.

**Fichier modifié :**

- `motioneye/audioctl.py` - Refonte complète :
  - Fonction `detect_audio_devices()` : détection automatique des périphériques ALSA et PulseAudio
  - Fonction `get_default_audio_device()` : sélection intelligente du périphérique par défaut
  - Menu déroulant dans l'UI pour sélectionner le périphérique audio
  - Affichage des périphériques détectés dans l'interface
  - Cache de 30 secondes pour éviter les appels répétés à `arecord`
  - Correction du bug de persistance des valeurs vides (crash au démarrage)

**Correction de bugs :**

- Correction de `_persist_setting()` dans `audioctl.py` et `rtspserver/config.py` :
  - Les valeurs vides/None ne sont plus écrites dans la config
  - Évite l'erreur "invalid configuration line" au démarrage

#### Serveur RTSP Natif (2025-12-09)

Implémentation complète d'un serveur RTSP natif pour le streaming audio/vidéo, compatible avec Synology Surveillance Station.

**Nouveaux fichiers créés :**

- `motioneye/rtspserver/__init__.py` - Package exports et fonctions wrapper
- `motioneye/rtspserver/protocol.py` - Constantes et utilitaires RTSP (RFC 2326)
  - Enum `RTSPMethod` et `RTSPStatusCode`
  - Parsing et construction des en-têtes Transport
  - Codes de statut RTSP complets (1xx à 5xx)
  
- `motioneye/rtspserver/sdp.py` - Générateur SDP (RFC 4566)
  - Classe `SDPGenerator` pour descriptions de session
  - Support H.264 vidéo avec sprop-parameter-sets
  - Support audio PCMU (G.711 μ-law), PCMA, AAC
  - Fonction utilitaire `generate_simple_sdp()`

- `motioneye/rtspserver/rtp.py` - Packetisation RTP/RTCP (RFC 3550)
  - Classe `RTPPacket` avec sérialisation/désérialisation
  - `H264Packetizer` - Packetisation H.264 avec fragmentation FU-A (RFC 6184)
  - `AudioPacketizer` - Packetisation audio PCM
  - `RTCPPacket` - Sender Reports RTCP
  - Fonction `get_ntp_timestamp()` pour horodatage NTP

- `motioneye/rtspserver/session.py` - Gestion des sessions RTSP
  - Classe `RTSPSession` avec états (INIT, READY, PLAYING)
  - `SessionManager` pour création/suppression/nettoyage
  - `RTPChannel` pour configuration transport (UDP/TCP interleaved)
  - Support multi-track (vidéo + audio)

- `motioneye/rtspserver/server.py` - Serveur RTSP principal
  - Classe `RTSPServer` basée sur asyncio
  - `RTSPClientHandler` pour traitement des connexions
  - Support complet des méthodes RTSP :
    - OPTIONS, DESCRIBE, SETUP, PLAY, PAUSE, TEARDOWN
    - GET_PARAMETER (keep-alive)
  - Transport UDP et TCP interleaved
  - Authentification Basic/Digest optionnelle

- `motioneye/rtspserver/source.py` - Capture et transcodage vidéo
  - `FFmpegTranscoder` - Conversion MJPEG → H.264
  - `AudioCapture` - Capture audio ALSA/PulseAudio
  - `VideoSourceManager` - Gestion des sources par caméra

- `motioneye/rtspserver/integration.py` - Intégration motionEye
  - Fonctions `start()`, `stop()`, `restart()`
  - `add_camera_stream()` pour enregistrer les caméras
  - `get_rtsp_settings()` pour configuration

- `motioneye/rtspserver/config.py` - Configuration UI
  - Décorateurs `@additional_section` et `@additional_config`
  - Options : rtsp_enabled, rtsp_port, rtsp_auth, rtsp_audio_enabled

**Fichiers modifiés :**

- `motioneye/settings.py` - Ajout des paramètres RTSP
  - `RTSP_ENABLED` (défaut: False)
  - `RTSP_PORT` (défaut: 8554)
  - `RTSP_LISTEN` (défaut: '0.0.0.0')
  - `RTSP_USERNAME`, `RTSP_PASSWORD`
  - `RTSP_AUDIO_ENABLED` (défaut: True)
  - `RTSP_VIDEO_BITRATE` (défaut: 2000000)
  - `RTSP_VIDEO_PRESET` (défaut: 'ultrafast')

- `motioneye/server.py` - Intégration du démarrage/arrêt RTSP
  - Import du module `rtspserver.integration`
  - Appel `rtsp_integration.start()` au démarrage
  - Appel `rtsp_integration.stop()` à l'arrêt

**Tests créés :**

- `tests/test_rtspserver/__init__.py`
- `tests/test_rtspserver/test_rtp.py` - Tests unitaires RTP

**Caractéristiques techniques :**

- Serveur asynchrone basé sur `asyncio`
- Compatible RFC 2326 (RTSP), RFC 3550 (RTP), RFC 4566 (SDP), RFC 6184 (H.264 RTP)
- Fragmentation FU-A pour gros NAL units H.264
- Support RTCP Sender Reports pour synchronisation
- Gestion automatique des sessions avec timeout
- Port par défaut 8554 (configurable)

### Modifié

- Structure du projet pour supporter le nouveau package `rtspserver/`

### Notes de compatibilité

- Le serveur RTSP est désactivé par défaut (`RTSP_ENABLED=False`)
- Nécessite FFmpeg pour le transcodage MJPEG → H.264
- Compatible Linux uniquement (utilise `fcntl` pour sockets non-bloquants)
- Testé avec Python 3.7+

---

## [0.43.1] - Date de la version précédente

Voir l'historique Git pour les versions antérieures.
