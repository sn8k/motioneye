# Changelog

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [Non publié]

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
