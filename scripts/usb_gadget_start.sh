#!/usr/bin/env bash
set -euo pipefail

PROJECT=/home/ize/ize-ribbon
IMAGE="$PROJECT/usb_share.img"
G=/sys/kernel/config/usb_gadget/ize_ribbon

modprobe libcomposite
mkdir -p "$G"
cd "$G"

echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "IZERIBBON0001" > strings/0x409/serialnumber
echo "Ize Ribbon" > strings/0x409/manufacturer
echo "Ize Ribbon Text Export" > strings/0x409/product

mkdir -p configs/c.1/strings/0x409
echo "Mass Storage" > configs/c.1/strings/0x409/configuration
echo 120 > configs/c.1/MaxPower

mkdir -p functions/mass_storage.usb0
echo 1 > functions/mass_storage.usb0/stall
echo 1 > functions/mass_storage.usb0/lun.0/ro
echo 0 > functions/mass_storage.usb0/lun.0/removable
echo "$IMAGE" > functions/mass_storage.usb0/lun.0/file

ln -sf functions/mass_storage.usb0 configs/c.1/
UDC=$(ls /sys/class/udc | head -n 1)
echo "$UDC" > UDC
