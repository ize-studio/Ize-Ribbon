# Ize Ribbon

Raspberry Pi Zero 2 W + Waveshare 2.13 inch e-Paper HAT based writing device.

This project is designed for a fresh Raspberry Pi OS Lite 32-bit install:

- Hostname: `ize-ribbon`
- User: `ize`
- Project path on Pi: `/home/ize/ize-ribbon`
- Web UI: `http://ize-ribbon.local:8080`
- Documents: `/home/ize/ize-ribbon/docs/note0001.txt`

## What is included

- ESC-menu based writing app, with no Vim-style command input.
- Minimal shortcuts: `Ctrl+N` for a new document, `Ctrl+S` for save, `Ctrl+Space` for language.
- Numbered document creation: `note0001.txt`, `note0002.txt`, ...
- 2.13 inch e-paper rendering with grayscale-to-1-bit thresholding.
- Web server for documents and settings.
- Boot splash with local web addresses.
- Idle shutdown watcher that shows `sleep...` before shutdown.
- Read-only USB mass-storage export image for taking text files over USB.
- systemd units and setup scripts.

## Files you must add

Put these font files in `fonts/` before installing:

- `DungGeunMo.ttf`
- `NotoSansMono-Regular.ttf`

The app uses the `waveshare_epd` Python package installed separately on the Pi.
If it is not installed as an importable package, set `WAVESHARE_LIB_DIR` in
`systemd/ize-ribbon.service` to the existing Waveshare Python `lib` directory.
The Waveshare driver is intentionally not bundled in this repository.

## Install on Pi

Copy this `ize-ribbon` directory to `/home/ize/ize-ribbon`, then run:

```bash
cd /home/ize/ize-ribbon
sudo bash scripts/install_pi.sh
```

To enable the USB text-file export drive:

```bash
sudo bash scripts/setup_usb_gadget.sh
sudo reboot
```

After reboot, connect the Pi Zero 2 W data USB port to a computer. It should appear as a small read-only drive containing exported `.txt` files.

## First Use

The device needs Wi-Fi access before the web UI can be opened. The recommended first setup path is:

1. Flash Raspberry Pi OS Lite with Raspberry Pi Imager.
2. In Imager settings, set hostname, username, password, Wi-Fi, country, timezone, and SSH.
3. Boot the Pi.
4. The e-paper boot screen shows:

```text
Ize Ribbon
[ Booting... ]
ize-ribbon.local:8080
<device-ip>:8080
```
(trusted local network only / do not expose to the internet)

Open either address in a browser on the same Wi-Fi network.

The Web UI is intended for trusted local-network use only. Do not expose port 8080 to the public internet.

Use the web UI for:

- document list and document editing
- new document creation
- Bluetooth keyboard pairing
- Wi-Fi connection
- device power off
- language selection from all configured supported language candidates, with up to five active slots including fixed `EN`
- idle shutdown and count display settings
- USB text export refresh

To write on the device itself, pair a Bluetooth keyboard from the web UI, then type directly on the keyboard. Text is appended to the current numbered document and saved on the Pi.

If the device cannot join Wi-Fi within about three minutes after boot, it starts a setup access point:
This fallback access point is intended for first-time local setup only.
Use it only on a trusted local network, and change the default password before regular use.

```text
SSID: Ize-Ribbon
Password: izeribbon
Web UI: http://10.42.0.1:8080
```

Use that web UI to enter Wi-Fi credentials, then reboot or reconnect after the Pi joins the normal network.

## Controls

- Type: append text to current document.
- Enter: newline.
- Backspace: delete one character.
- ESC: open or close menu.
- Ctrl+N: create a new numbered document.
- Ctrl+S: save the current document.
- Ctrl+Space: cycle selected languages.
- Menu `Power Off`: show `sleep...`, then shut down Linux.
- Menu Up/Down: move.
- Menu Left/Right: change option values.
- Menu Enter: select/confirm.

## Display language and status

- Hangul characters render with `DungGeunMo.ttf`.
- Latin letters, numbers, and punctuation render with `NotoSansMono-Regular.ttf`.
- Hangul is shifted slightly downward to align visually with Latin text.
- The language setting controls the displayed input-mode slot order. `EN` is fixed first; users can choose up to four additional languages from the full configured candidate list.
- Top and bottom status bars are inverted by default.
- Keyboard warning is shown as `[No KBD]`.
- Language is shown as `[EN]` or `[한]`.

## Notes

The first implementation uses the Linux console input path. Bluetooth keyboards paired with the Pi generally type into `/dev/tty1`, which is enough for the initial device. If later keyboard detection or input needs to bypass the console, the app can be moved to `/dev/input/event*`.

The USB export is deliberately read-only to avoid filesystem corruption. Use the web UI's "USB export refresh" action, or run `sudo bash scripts/refresh_usb_export.sh`, before unplugging if you want the newest text files in the virtual USB drive.

