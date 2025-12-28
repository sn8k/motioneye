# motionEye - TODO List

Liste des fonctionnalités à implémenter pour rendre les placeholders opérationnels.

---

## 1. 🔴 LED Control (Raspberry Pi)

**Fichier:** `motioneye/controls/ledctl.py`

### Architecture

- [ ] Détecter si on est sur un Raspberry Pi (lecture de `/proc/cpuinfo` ou `/sys/firmware/devicetree/base/model`)
- [ ] Vérifier l'existence des chemins sysfs des LEDs (`/sys/class/leds/PWR`, `/sys/class/leds/ACT`)
- [ ] Gérer les permissions (les LEDs nécessitent root ou des règles udev)

### Implémentation

- [ ] **`_is_raspberry_pi()`** - Implémenter la détection réelle du Pi
  - Lire `/sys/firmware/devicetree/base/model`
  - Vérifier si le modèle contient "Raspberry Pi"
  
- [ ] **`_get_led_settings()`** - Lire l'état actuel des LEDs
  - Lire `/sys/class/leds/PWR/trigger` pour le mode de la LED power
  - Lire `/sys/class/leds/ACT/trigger` pour le mode de la LED activité
  - Parser les triggers disponibles (entre crochets = actif)
  
- [ ] **`_set_led_settings()`** - Appliquer les paramètres
  - Écrire dans `/sys/class/leds/PWR/trigger` (none, default-on, heartbeat, etc.)
  - Écrire dans `/sys/class/leds/ACT/trigger` (none, mmc0, heartbeat, etc.)
  - Gérer la luminosité via `/sys/class/leds/*/brightness`

### Permissions

- [ ] Créer une règle udev pour permettre l'accès aux LEDs sans root
  - Fichier: `/etc/udev/rules.d/99-motioneye-leds.rules`
  - Contenu: `SUBSYSTEM=="leds", MODE="0666"` ou groupe spécifique

### Tests

- [ ] Tester sur Raspberry Pi 3/4/5
- [ ] Vérifier le comportement si les LEDs ne sont pas accessibles
- [ ] Tester la persistence après reboot

---

## 2. 💾 Network Storage

**Fichier:** `motioneye/controls/netstoragectl.py`

### Architecture

- [ ] Définir la structure des points de montage (ex: `/var/lib/motioneye/media`)
- [ ] Gérer les dépendances (cifs-utils, nfs-common, sshfs)
- [ ] Implémenter un système de failover vers stockage local

### Dépendances à vérifier

- [ ] `mount.cifs` pour SMB/CIFS
- [ ] `mount.nfs` pour NFS
- [ ] `sshfs` pour SSHFS
- [ ] Créer une fonction de vérification des dépendances

### Implémentation SMB/CIFS

- [ ] **`_mount_smb()`** - Monter un partage SMB
  - Construire la commande: `mount -t cifs //server/share /mount/point -o user=xxx,pass=xxx`
  - Gérer les options: version du protocole, domaine, etc.
  - Stocker les credentials de façon sécurisée (fichier avec permissions 600)
  
- [ ] **`_unmount_smb()`** - Démonter le partage
  - `umount /mount/point` avec gestion des processus occupant le point

### Implémentation NFS

- [ ] **`_mount_nfs()`** - Monter un export NFS
  - Commande: `mount -t nfs server:/export /mount/point`
  - Options: `vers=4`, `nolock`, `soft`, etc.
  
- [ ] **`_unmount_nfs()`** - Démonter l'export

### Implémentation SSHFS

- [ ] **`_mount_sshfs()`** - Monter via SSHFS
  - Commande: `sshfs user@server:/path /mount/point`
  - Gérer les clés SSH (génération, déploiement)
  - Options: `allow_other`, `reconnect`, `ServerAliveInterval`
  
- [ ] **`_unmount_sshfs()`** - Démonter (fusermount -u)

### Failover

- [ ] Implémenter un watchdog pour surveiller la connexion
- [ ] Basculer automatiquement vers le stockage local si le réseau échoue
- [ ] Synchroniser les fichiers locaux vers le réseau quand la connexion revient
- [ ] Logger les événements de failover

### Configuration Motion

- [ ] Mettre à jour `target_dir` dans les fichiers de configuration motion
- [ ] Redémarrer motion après changement de stockage

### fstab vs montage dynamique

- [ ] Option pour ajouter le montage dans `/etc/fstab`
- [ ] Ou utiliser un montage dynamique au démarrage de motionEye

### Tests

- [ ] Tester la connexion avant de sauvegarder (`_test_network_storage()`)
- [ ] Vérifier l'espace disponible sur le stockage distant
- [ ] Tester la récupération après perte de connexion

---

## 3. 📷 Media Gallery

**Fichier:** `motioneye/handlers/gallery.py`

### Architecture

- [ ] Créer un template Jinja2 pour la galerie (`templates/gallery.html`)
- [ ] Ajouter les routes dans `server.py`
- [ ] Créer les assets CSS/JS (`static/css/gallery.css`, `static/js/gallery.js`)

### Routes à ajouter dans server.py

```python
(r'^/gallery/?$', GalleryHandler),
(r'^/gallery/(\d+)/?$', GalleryHandler),
(r'^/gallery/(\d+)/(images|videos|timeline)/?$', GalleryHandler),
(r'^/gallery/api/media/?$', GalleryHandler, {'op': 'api'}),
```

### Template gallery.html

- [ ] Header avec navigation par caméra
- [ ] Calendrier/sélecteur de date
- [ ] Grille de vignettes responsive
- [ ] Lightbox pour les images
- [ ] Player vidéo intégré
- [ ] Barre d'outils (télécharger, supprimer, sélection multiple)

### Backend - Listing des médias

- [ ] **`_list_images()`** - Implémenter avec pagination
  - Utiliser `mediafiles.list_media()` existant
  - Générer des vignettes à la volée ou en cache
  - Retourner métadonnées (date, taille, dimensions)

- [ ] **`_list_videos()`** - Implémenter avec pagination
  - Lister les fichiers vidéo
  - Extraire une frame pour la vignette (ffmpeg)
  - Retourner durée, codec, résolution

### Génération de vignettes

- [ ] **`generate_thumbnail()`** - Implémenter
  - Pour images: utiliser PIL/Pillow pour redimensionner
  - Pour vidéos: utiliser ffmpeg pour extraire une frame
  - Cache des vignettes dans un dossier `.thumbnails`
  - Nettoyage automatique des vignettes orphelines

### Timeline/Calendrier

- [ ] **`_get_timeline()`** - Implémenter
  - Lister les dates avec des événements
  - Compter les événements par jour/heure
  - Format compatible avec un composant calendrier JS

### API Media

- [ ] **`_api_list_media()`** - Implémenter l'API JSON
  - Filtrage par type (images/videos/all)
  - Filtrage par date ou plage de dates
  - Pagination (page, per_page)
  - Tri (date, taille, nom)

### Frontend JavaScript

- [ ] Chargement dynamique des médias (infinite scroll ou pagination)
- [ ] Lightbox avec navigation clavier (flèches, échap)
- [ ] Player vidéo avec contrôles (play, pause, seek)
- [ ] Sélection multiple (checkbox, ctrl+click)
- [ ] Actions groupées (télécharger ZIP, supprimer)
- [ ] Préchargement des images suivantes

### Intégration

- [ ] Lien depuis le dashboard principal vers la galerie
- [ ] Bouton "Voir dans la galerie" sur les événements
- [ ] Notification de nouveaux médias

---

## 4. 🔧 Tâches communes

### Settings.py

- [ ] Ajouter les constantes pour les nouveaux paramètres
  - `LED_POWER_ENABLED`, `LED_POWER_MODE`
  - `LED_ACTIVITY_ENABLED`, `LED_ACTIVITY_MODE`
  - `NETWORK_STORAGE_ENABLED`, `NETWORK_STORAGE_PROTOCOL`
  - `NETWORK_STORAGE_SERVER`, `NETWORK_STORAGE_SHARE`
  - etc.

### Internationalisation (i18n)

- [ ] Ajouter les chaînes de traduction dans `locale/motioneye.pot`
- [ ] Mettre à jour les fichiers de traduction (`.po`)
- [ ] Compiler les fichiers `.mo`

### Documentation

- [ ] Documenter les nouvelles fonctionnalités dans le README
- [ ] Ajouter des captures d'écran
- [ ] Documenter les prérequis (dépendances système)

### Tests

- [ ] Écrire des tests unitaires pour `ledctl.py`
- [ ] Écrire des tests unitaires pour `netstoragectl.py`
- [ ] Écrire des tests pour les handlers de la galerie
- [ ] Tests d'intégration sur Raspberry Pi

---

## 5. 📋 Priorités suggérées

### Phase 1 - Fondations
1. LED Control (simple, peu de dépendances)
2. Mise à jour de settings.py

### Phase 2 - Stockage
3. Network Storage - SMB (le plus courant)
4. Network Storage - NFS
5. Failover local

### Phase 3 - Galerie
6. Template et routes de base
7. Listing des images avec vignettes
8. Lightbox
9. Listing des vidéos
10. Player vidéo

### Phase 4 - Finitions
11. SSHFS support
12. Timeline/calendrier
13. Actions groupées
14. i18n
15. Documentation

---

## Notes de développement

### Commandes utiles

```bash
# Tester les LEDs sur Raspberry Pi
cat /sys/class/leds/PWR/trigger
echo none > /sys/class/leds/PWR/trigger
echo default-on > /sys/class/leds/PWR/trigger

# Tester un montage SMB
mount -t cifs //192.168.1.100/share /mnt/test -o user=guest,password=

# Générer une vignette vidéo avec ffmpeg
ffmpeg -i video.mp4 -ss 00:00:01 -vframes 1 -vf scale=200:-1 thumb.jpg
```

### Dépendances Python potentielles

- `Pillow` - déjà présent, pour les vignettes
- `python-dateutil` - pour le parsing de dates

### Ressources

- [Raspberry Pi LED control](https://www.jeffgeerling.com/blogs/jeff-geerling/controlling-pwr-act-leds-raspberry-pi)
- [mount.cifs man page](https://linux.die.net/man/8/mount.cifs)
- [SSHFS documentation](https://github.com/libfuse/sshfs)
