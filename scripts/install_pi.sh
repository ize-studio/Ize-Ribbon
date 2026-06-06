#!/usr/bin/env bash
set -euo pipefail

PROJECT=/home/ize/ize-ribbon

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash scripts/install_pi.sh" >&2
  exit 1
fi

apt update
apt install -y \
  git \
  python3-pil \
  python3-numpy \
  python3-rpi.gpio \
  python3-spidev \
  python3-flask \
  fonts-dejavu-core \
  avahi-daemon \
  bluez \
  network-manager \
  dosfstools

systemctl enable --now avahi-daemon
systemctl enable --now bluetooth
usermod -aG bluetooth,netdev ize || true

install -d -o ize -g ize "$PROJECT/docs" "$PROJECT/fonts" /run/ize-ribbon
chown -R ize:ize "$PROJECT"

if [ ! -f "$PROJECT/fonts/DungGeunMo.ttf" ]; then
  echo "Missing $PROJECT/fonts/DungGeunMo.ttf" >&2
fi

if [ ! -f "$PROJECT/fonts/NotoSansMono-Regular.ttf" ]; then
  echo "Missing $PROJECT/fonts/NotoSansMono-Regular.ttf" >&2
fi

if ! python3 - <<'PY'
import sys
try:
    import waveshare_epd.epd2in13_V4
except Exception as exc:
    sys.exit(1)
PY
then
  echo "waveshare_epd is not importable. If you already have it under ~/e-Paper, keep WAVESHARE_LIB_DIR in systemd/ize-ribbon.service." >&2
fi

install -m 0644 "$PROJECT/systemd/ize-ribbon.service" /etc/systemd/system/ize-ribbon.service
install -m 0644 "$PROJECT/systemd/ize-ribbon-boot-splash.service" /etc/systemd/system/ize-ribbon-boot-splash.service
install -m 0644 "$PROJECT/systemd/ize-ribbon-network-fallback.service" /etc/systemd/system/ize-ribbon-network-fallback.service
install -m 0644 "$PROJECT/systemd/ize-ribbon-web.service" /etc/systemd/system/ize-ribbon-web.service
install -m 0644 "$PROJECT/systemd/ize-ribbon-idle-shutdown.service" /etc/systemd/system/ize-ribbon-idle-shutdown.service

cat >/etc/sudoers.d/ize-ribbon <<'EOF'
ize ALL=(root) NOPASSWD: /sbin/shutdown, /usr/sbin/shutdown, /usr/bin/nmcli, /usr/bin/bluetoothctl, /usr/sbin/rfkill, /bin/bash /home/ize/ize-ribbon/scripts/refresh_usb_export.sh
EOF
chmod 0440 /etc/sudoers.d/ize-ribbon

systemctl daemon-reload
systemctl disable getty@tty1.service || true
systemctl enable ize-ribbon-boot-splash.service ize-ribbon-network-fallback.service ize-ribbon.service ize-ribbon-web.service ize-ribbon-idle-shutdown.service

echo "Install complete. Reboot recommended."
