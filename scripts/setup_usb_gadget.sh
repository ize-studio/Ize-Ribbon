#!/usr/bin/env bash
set -euo pipefail

PROJECT=/home/ize/ize-ribbon
if [ -f /boot/firmware/config.txt ]; then
  BOOT_CONFIG=/boot/firmware/config.txt
  CMDLINE=/boot/firmware/cmdline.txt
else
  BOOT_CONFIG=/boot/config.txt
  CMDLINE=/boot/cmdline.txt
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo." >&2
  exit 1
fi

if ! awk '/^\[all\]/{in_all=1; next} /^\[/{in_all=0} in_all && /^dtoverlay=dwc2/{found=1} END{exit found ? 0 : 1}' "$BOOT_CONFIG"; then
  printf '\n[all]\ndtoverlay=dwc2,dr_mode=peripheral\n' >> "$BOOT_CONFIG"
else
  awk '
    /^\[all\]/{in_all=1}
    /^\[/{if ($0 != "[all]") in_all=0}
    in_all && /^dtoverlay=dwc2/{$0="dtoverlay=dwc2,dr_mode=peripheral"}
    {print}
  ' "$BOOT_CONFIG" > "$BOOT_CONFIG.tmp"
  mv "$BOOT_CONFIG.tmp" "$BOOT_CONFIG"
fi

if ! grep -q 'modules-load=dwc2' "$CMDLINE"; then
  cp "$CMDLINE" "$CMDLINE.bak"
  sed -i '1 s/$/ modules-load=dwc2/' "$CMDLINE"
fi

install -m 0755 "$PROJECT/scripts/usb_gadget_start.sh" /usr/local/sbin/ize-ribbon-usb-gadget
install -m 0644 "$PROJECT/systemd/ize-ribbon-usb-gadget.service" /etc/systemd/system/ize-ribbon-usb-gadget.service
systemctl daemon-reload
systemctl enable ize-ribbon-usb-gadget.service

bash "$PROJECT/scripts/refresh_usb_export.sh"

echo "USB gadget configured. Reboot required."
