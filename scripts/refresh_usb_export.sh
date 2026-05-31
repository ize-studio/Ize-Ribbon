#!/usr/bin/env bash
set -euo pipefail

PROJECT=/home/ize/ize-ribbon
IMAGE="$PROJECT/usb_share.img"
MOUNT="$PROJECT/usb_share"
DOCS="$PROJECT/docs"
SIZE_MB=16

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo." >&2
  exit 1
fi

mkdir -p "$MOUNT"

if mountpoint -q "$MOUNT"; then
  umount "$MOUNT"
fi

if [ ! -f "$IMAGE" ]; then
  dd if=/dev/zero of="$IMAGE" bs=1M count="$SIZE_MB"
  mkfs.vfat -n IZE_RIBBON "$IMAGE"
fi

LOOP=$(losetup --find --show "$IMAGE")
cleanup() {
  if mountpoint -q "$MOUNT"; then umount "$MOUNT"; fi
  losetup -d "$LOOP" || true
}
trap cleanup EXIT

mount "$LOOP" "$MOUNT"
find "$MOUNT" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp "$DOCS"/note*.txt "$MOUNT"/ 2>/dev/null || true
sync

if [ -d /sys/kernel/config/usb_gadget/ize_ribbon/functions/mass_storage.usb0 ]; then
  echo "" > /sys/kernel/config/usb_gadget/ize_ribbon/functions/mass_storage.usb0/lun.0/file || true
  echo "$IMAGE" > /sys/kernel/config/usb_gadget/ize_ribbon/functions/mass_storage.usb0/lun.0/file || true
fi
