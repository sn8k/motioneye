#!/usr/bin/env sh
# version: 2025-08-26.1
# Map host /dev/snd to access ALSA audio devices.
if command -v arecord >/dev/null 2>&1; then
    echo "Available ALSA capture devices:"
    arecord -l || true
fi
# We need to chown at startup time since volumes are mounted as root. This is fugly.
mkdir -p /run/motioneye
chown motion:motion /run/motioneye
[ -f '/etc/motioneye/motioneye.conf' ] || cp -a /etc/motioneye.conf.sample /etc/motioneye/motioneye.conf
exec su -g motion motion -s /bin/dash -c "LANGUAGE=en exec /usr/local/bin/meyectl startserver -c /etc/motioneye/motioneye.conf"
