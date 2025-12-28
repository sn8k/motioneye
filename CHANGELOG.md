# Changelog

Toutes les modifications notables apportées à ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [0.43.1b47]

### Corrigé

- **Sections Network et Hardware toujours visibles** (`controls/wifictl.py`, `controls/ledctl.py`) :
  - `_is_wifi_configurable()` retourne désormais toujours `True` pour exposer la section Network par défaut
  - Suppression des gardes `_is_raspberry_pi()` sur la section Hardware/LED pour l'afficher par défaut
  - Le backend continue de protéger l'application des changements si le support système est absent

## [0.43.1b46]

### Amélioré

- **Détection automatique du gestionnaire réseau** (`controls/wifictl.py`) :
  - Nouvelle fonction `_is_wifi_configurable()` qui détecte NetworkManager ou dhcpcd automatiquement
  - Plus besoin de configurer `WPA_SUPPLICANT_CONF` dans settings pour voir la section Network
  - Fallback sur la présence de `nmcli` ou `/etc/dhcpcd.conf` si le service n'est pas actif
  - Ajout de `FORCE_NETWORK_SETTINGS` dans settings.py pour forcer l'affichage

- **Détection Raspberry Pi améliorée** (`controls/ledctl.py`) :
  - Vérification de `/sys/firmware/devicetree/base/model` en plus de `/proc/device-tree/model`
  - Ajout de `FORCE_HARDWARE_SETTINGS` dans settings.py pour forcer l'affichage sur non-Pi

- **Nouveaux paramètres settings.py** :
  - `FORCE_NETWORK_SETTINGS = False` - Force l'affichage de la section Network
  - `FORCE_HARDWARE_SETTINGS = False` - Force l'affichage de la section Hardware

## [0.43.1b45]

### Corrigé

- **Sections additionnelles main visibles sans caméra** (`templates/main.html`, `static/js/main.js`) :
  - Ajout de la classe `additional-section-main` pour distinguer les sections principales des sections caméra
  - Le JavaScript ne masque plus les sections principales (Network, Hardware) quand aucune caméra n'est configurée
  - Les sections principales restent visibles pour les utilisateurs non-admin (seules les sections caméra sont masquées)

## [0.43.1b44]

### Amélioré

- **Sections Network et Hardware accessibles sans caméra** (`server.py`) :
  - Import des modules `wifictl` et `ledctl` au démarrage du serveur
  - Les sections "Network" (WiFi) et "Hardware" (LED) sont maintenant visibles dans les paramètres même si aucune caméra n'est configurée

## [0.43.1b43]

### Ajouté

- **Placeholder LED Control Raspberry Pi** (`controls/ledctl.py`) :
  - Section "Hardware" dans l'interface de configuration
  - Contrôle de la LED power (on/off, mode: default-on, heartbeat, none)
  - Contrôle de la LED activité (on/off, mode: mmc0, heartbeat, none)
  - Détection automatique du Raspberry Pi
  - Fonctionnalité placeholder - implémentation à compléter

- **Placeholder Network Storage** (`controls/netstoragectl.py`) :
  - Section "Network Storage" dans l'interface de configuration
  - Support protocoles : Local, SMB/CIFS, NFS, SSHFS
  - Configuration serveur, partage, credentials
  - Option failover vers stockage local
  - Test de connexion
  - Fonctionnalité placeholder - implémentation à compléter

- **Placeholder Media Gallery** (`handlers/gallery.py`) :
  - Handler pour la galerie de médias
  - Routes pour images, vidéos, timeline
  - API de listing avec filtres et pagination
  - Page placeholder avec liste des fonctionnalités prévues
  - Fonctionnalité placeholder - implémentation à compléter

- **TODO.md** : Liste complète des tâches pour rendre les fonctionnalités opérationnelles

## [0.43.1b42]

### Amélioré

- **Support NetworkManager pour Raspberry Pi OS Bookworm+** (`controls/wifictl.py`) :
  - Auto-détection du gestionnaire réseau (NetworkManager vs dhcpcd)
  - Support complet de `nmcli` pour les versions récentes de Raspberry Pi OS (Bookworm/Debian 12+)
  - Conservation du support `dhcpcd.conf` pour les anciennes versions (Bullseye et antérieures)
  - Création/suppression automatique des connexions NetworkManager avec préfixe `motioneye-wifi-`
  - Lecture des configurations IP existantes depuis NetworkManager
  - Fallback intelligent : détection via `/sys/class/net`, `iw dev`, ou `nmcli device`

## [0.43.1b41]

### Ajouté

- **Gestion avancée du WiFi dans le frontend** (`controls/wifictl.py`) :
  - Auto-détection des interfaces WiFi disponibles avec driver et état
  - Sélection manuelle de l'interface WiFi avec option "Auto"
  - Interface WiFi de secours (fallback) en cas d'indisponibilité
  - Réseau WiFi principal avec SSID et clé PSK
  - Réseau WiFi de secours avec priorité inférieure (failover automatique)
  - Configuration IP statique ou DHCP
  - Paramètres réseau complets : adresse IP, masque, passerelle, DNS primaire/secondaire
  - Validation des adresses IP dans le frontend
  - Persistance des configurations dans wpa_supplicant.conf et dhcpcd.conf

## [0.43.1b40]

### Amélioré

- **Détection d’update UI via version du repo** (`update.py`) :
  - En installation git, on fetch le dépôt et on lit `motioneye/__init__.py` distant pour comparer la VERSION locale et distante
  - Si la VERSION distante est supérieure, l’UI voit une mise à jour disponible même sans comparer les commits

## [0.43.1b39]

### Amélioré

- **RTSP alimente depuis le passthrough caméra** (`rtspserver/integration.py`) :
  - Utilise le flux netcam/passthrough quand il est disponible au lieu du MJPEG local
  - Journalise la source utilisée et l’encodeur choisi pour chaque caméra
- **Encodeur matériel activé pour le RTSP** (`rtspserver/source.py`) :
  - Sélectionne automatiquement l’encodeur H.264 matériel disponible (v4l2m2m, NVENC, QSV, NVMPI) sinon libx264
  - Ajuste la ligne FFmpeg pour accepter des entrées auto-détectées (RTSP/HTTP) en plus du MJPEG

## [0.43.1b38]

### Corrigé

- **RTP envoyait des NALs isolées** (`rtspserver/integration.py`, `rtspserver/source.py`) :
  - Regroupe maintenant les NALs (AUD, SEI, slices) en unités d'accès complètes avant envoi RTP
  - Ajoute `-x264-params aud=1:repeat-headers=1` pour que FFmpeg insère des AUD et répète SPS/PPS
  - Les timestamps RTP correspondent enfin à des frames complètes, évitant les artefacts "concealing" côté client

## [0.43.1b37]

### Corrigé

- **SDP sprop-parameter-sets manquant** (`rtspserver/integration.py`, `rtp.py`) :
  - Les SPS/PPS sont maintenant encodés en base64 pour le SDP
  - Le champ `sprop-parameter-sets` dans le SDP permet au décodeur d'initialiser le codec H.264 avant de recevoir les frames
  - Ajout de logs des types NAL dans le packetizer RTP pour diagnostic

## [0.43.1b36]

### Corrigé

- **Erreur "non-existing PPS referenced" dans les décodeurs H.264** (`rtspserver/integration.py`, `server.py`) :
  - Préfixe automatiquement SPS+PPS à chaque IDR frame (keyframe)
  - Combine SPS+PPS en une seule unité d'accès (même timestamp RTP)
  - Le décodeur reçoit maintenant les paramètres H.264 avant chaque keyframe
  - Résout le problème d'image figée dans VLC et ffplay

## [0.43.1b35]

### Corrigé

- **Envoi différé du SPS/PPS** (`rtspserver/integration.py`) :
  - Si un client se connecte avant que FFmpeg ait produit les paramètres H.264 (SPS/PPS),
    ils sont maintenant envoyés dès qu'ils sont disponibles
  - Résout le problème d'image figée quand le client se connecte très rapidement après
    le démarrage du serveur

## [0.43.1b34]

### Amélioré

- **Compteurs de frames/paquets par session** (`rtspserver/session.py`) :
  - Log du nombre total de frames et paquets tous les 100 frames
  - Log de la progression du timestamp RTP tous les 500 paquets TCP
  - Permet de vérifier que les données sont effectivement envoyées au client

## [0.43.1b33]

### Amélioré

- **Diagnostics TCP/UDP par session** (`rtspserver/session.py`, `server.py`) :
  - Log "First video packets sent" pour chaque nouvelle session (pas uniquement la première)
  - Log du premier paquet TCP envoyé par session (channel, taille, seq, timestamp)
  - Warning si tcp_writer manquant en mode TCP
  - Log du premier write interleaved par connexion

## [0.43.1b32]

### Amélioré

- **Réduction du spam dans les logs RTSP** (`rtspserver/session.py`) :
  - Suppression des logs de matching répétitifs dans broadcast_video_frame()
  - Logs de get_playing_sessions() limités aux 3 premiers appels puis tous les 1000

- **Logging du mode transport RTSP** (`rtspserver/server.py`) :
  - Affiche si le client utilise TCP interleaved ou UDP
  - Aide au diagnostic quand la vidéo ne s'affiche pas

## [0.43.1b31]

### Corrigé

- **Image figée dans VLC** (`rtspserver/server.py`, `integration.py`, `source.py`) :
  - Envoi des SPS/PPS au client dès qu'il commence à jouer (PLAY)
  - Permet au décodeur H.264 de décoder immédiatement les P-frames
  - Stockage des SPS/PPS dans StreamConfig pour les envoyer aux nouveaux clients

- **Traceback "Connection reset by peer"** (`rtspserver/server.py`) :
  - Gestion propre des déconnexions brutales (ConnectionResetError, BrokenPipeError)
  - Plus de traceback dans les logs quand un client se déconnecte brusquement

## [0.43.1b30]

### Corrigé

- **FFmpeg transcoder amélioré** (`rtspserver/source.py`) :
  - `probesize` augmenté de 32 à 32768 bytes pour meilleure analyse du stream MJPEG
  - `analyzeduration` augmenté de 0 à 500000 µs (0.5s)
  - Framerate de sortie minimum forcé à 10 fps (évite les problèmes avec caméras configurées en 2 fps)
  - Résout le problème de très peu de frames produites (2 frames au lieu de 125)

## [0.43.1b29]

### Amélioré

- **Logs FFmpeg visibles** (`rtspserver/source.py`) :
  - Les logs stderr de FFmpeg sont maintenant en INFO (étaient en DEBUG)
  - Les erreurs/warnings FFmpeg sont en WARNING pour être plus visibles
  - Log du nombre de NAL units traités avec leur taille
  - Permet de diagnostiquer pourquoi FFmpeg ne produit pas de frames

## [0.43.1b28]

### Amélioré

- **Logs RTSP profonds pour diagnostic sessions** :
  - `rtspserver/server.py` : Log dans broadcast_frame() du nombre de sessions PLAYING
  - `rtspserver/session.py` : Log dans get_playing_sessions() du nombre total de sessions et leurs états
  - Permet de diagnostiquer pourquoi les sessions ne reçoivent pas les frames

## [0.43.1b27]

### Amélioré

- **Logs RTSP étendus pour diagnostic** :
  - `rtspserver/server.py` : Log INFO du mapping stream_path → stream_id dans handle_setup()
  - `rtspserver/session.py` : Logs INFO dans broadcast_video_frame() et send_video_frame()
  - Permet de voir exactement ce qui se passe pendant le broadcast aux clients

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
