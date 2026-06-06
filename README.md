# Ize Ribbon

Version 2.0

Ize Ribbon is a Raspberry Pi Zero 2 W based writing device with a Waveshare 2.13 inch e-Paper HAT, Bluetooth or USB keyboard input, a local Web UI, Wi-Fi setup, Korean input, automatic power handling, and optional GitHub private repository sync for Postbox-style writing backup.

The device is designed to keep writing local and fast. Network, GitHub, USB export, and web editing features run around the writing flow instead of blocking typing.

## Security Notes

Ize Ribbon is intended for trusted local-network use only. Do not expose port `8080` to the public internet.

The fallback access point is intended for first-time local setup and recovery. Use it only on a trusted local network, and change the default password before regular use if the device will be used outside a controlled environment.

## Hardware

- Raspberry Pi Zero 2 W
- Waveshare 2.13 inch e-Paper HAT, V4 driver
- Bluetooth keyboard or USB keyboard
- MicroSD with Raspberry Pi OS Lite
- Optional battery or UPS board with INA219-compatible voltage sensor

## Default Paths

- Project: `/home/ize/ize-ribbon`
- Documents: `/home/ize/ize-ribbon/docs`
- Current document setting: `config.json` key `document`
- Web UI: `http://ize-ribbon.local:8080`
- Setup AP Web UI: `http://10.42.0.1:8080`
- GitHub deploy key: `/home/ize/.ssh/ize_ribbon_github_ed25519`
- USB export image: `/home/ize/ize-ribbon/usb_share.img`
- Activity file: `/run/ize-ribbon/activity`

## Required Files

Add these font files to `fonts/` before installation:

- `DungGeunMo.ttf`
- `NotoSansMono-Regular.ttf`

The Waveshare e-Paper Python library is not bundled. The systemd service expects it at:

```text
/home/ize/e-Paper/RaspberryPi_JetsonNano/python/lib
```

If your path is different, update `WAVESHARE_LIB_DIR` in `systemd/ize-ribbon.service`.

## Installation

Flash Raspberry Pi OS Lite, create user `ize`, enable SSH, set hostname `ize-ribbon`, and configure Wi-Fi if available.

Copy this repository to the Pi:

```bash
cd /home/ize/ize-ribbon
sudo bash scripts/install_pi.sh
```

Optional USB text export:

```bash
sudo bash scripts/setup_usb_gadget.sh
sudo reboot
```

After reboot, the device starts these services:

- `ize-ribbon.service`: main writing app on `/dev/tty1`
- `ize-ribbon-web.service`: Web UI on port `8080`
- `ize-ribbon-idle-shutdown.service`: idle power manager
- `ize-ribbon-network-fallback.service`: Wi-Fi setup fallback

## Startup Behavior

At boot, the e-paper screen shows network and keyboard status.

If no keyboard is connected, the device stays on the startup/status screen so the user can find the Web UI and pair or connect a keyboard.

If a keyboard is connected, the device enters the writing screen even when Wi-Fi is not connected. Network setup is always available later through the device menu or Web UI.

If normal Wi-Fi is unavailable, the setup AP remains available:

```text
SSID: Ize-Ribbon
Password: izeribbon
Web UI: http://10.42.0.1:8080
```

## Writing Screen

The writing screen shows:

- Top bar: title, input language, keyboard/battery status
- Body: current document text, six visible lines by default
- Bottom bar: current document label and counter

Text is saved locally first. Save and GitHub sync are intentionally separated from display refresh to reduce typing delay.

## Keyboard Controls

- Type: insert text
- Enter: newline
- Backspace: delete one character
- ESC: open device menu
- Ctrl+N: create new numbered document
- Ctrl+S: save immediately
- Ctrl+Space: cycle selected input languages

Arrow keys are handled through Linux input events when in menus. Bluetooth and USB keyboards are both detected through `/dev/input/event*`.

## Korean Input

`KO` input mode composes Hangul inside the app. `Ctrl+Space` cycles through the selected languages. `EN` is always present as the first slot.

Fonts:

- Korean: `DungGeunMo.ttf`
- Latin and other configured languages: `NotoSansMono-Regular.ttf`

## Device Menu

Open the menu with `ESC`.

Menu items:

- `New Doc`: creates the next numbered document, saves the previous document first, and clears the writing cache for the new document.
- `Docs`: opens the document picker.
- `Network`: shows Wi-Fi/AP status and Web UI address.
- `Auto Off`: selects idle shutdown time.
- `Count`: changes bottom counter mode.
- `Power Off`: shows the sleep/power-off notice, waits briefly, then shuts down Linux.

Menu controls:

- Up/Down: move selection
- Left/Right: change option values
- Enter: select or confirm
- ESC: go back or close menu

### Docs Menu

Shows numbered documents such as:

```text
0001:preview text
0002:preview text
```

Selecting a document changes the current writing file.

### Network Menu

Shows either:

```text
WiFi <ssid>
<ip>:8080
```

or setup AP information:

```text
AP Ize-Ribbon
10.42.0.1:8080
```

### Auto Off Menu

Available values:

- `10m`
- `30m`
- `60m`

When external power is detected or power state is unknown and configured as safe, idle shutdown is skipped.

### Count Menu

Available values:

- `OFF`
- `Words`
- `Chars`

## Web UI

Open the Web UI from the same network:

```text
http://ize-ribbon.local:8080
http://<device-ip>:8080
```

When using setup AP:

```text
http://10.42.0.1:8080
```

The main page shows:

- Version
- Wi-Fi status
- Web UI URL
- Bluetooth keyboard status
- Current input language
- Document table
- Navigation buttons

Main buttons:

- `New Document`
- `Refresh USB Export`
- `Settings`
- `GitHub Sync`
- `Bluetooth Keyboard`
- `Wi-Fi`
- `Power Off`

## Web: Documents

The document table shows:

- Document number
- Preview
- Character/word count
- Open button
- Download button

Opening a document provides:

- Text editor
- `Save`
- `Save and Open on Device`

`Save and Open on Device` writes the web-edited text and makes that file the active device document.

## Web: Settings

Settings include:

- Counter mode: `OFF`, `Words`, `Characters`
- Auto Off: `10 min`, `30 min`, `60 min`
- Battery display: `auto` or `manual`
- Manual battery text
- Input language selection

`EN` is fixed as the first language. Select up to five total languages including `EN`.

## Web: GitHub Sync

GitHub Sync lets the device use a private GitHub repository as a Postbox-style writing archive.

Recommended setup:

1. Create a private GitHub repository.
2. Open `GitHub Sync` in the Ribbon Web UI.
3. Enter repository as `owner/repository`.
4. Press `Save Repository`.
5. Press `Generate SSH Key`.
6. Copy the displayed public key.
7. In GitHub, open the repository settings.
8. Go to `Deploy keys`.
9. Add the public key.
10. Enable `Allow write access`.
11. Press `Test Connection` in the Web UI.
12. Press `Connect Docs Folder`.

The device uses `/home/ize/ize-ribbon/docs` as the Git working tree. Existing documents are committed and pushed to the configured repository.

Automatic sync behavior:

- Local document writes are saved immediately.
- Git commit/push runs in the background.
- Sync only runs when Wi-Fi is connected.
- If Wi-Fi is unavailable, documents remain local and sync later.
- Git work is never required for typing to continue.

Manual actions:

- `Generate SSH Key`: creates the deploy key if missing.
- `Test Connection`: verifies GitHub SSH access.
- `Connect Docs Folder`: initializes or connects `docs/` to the repo.
- `Sync Now`: requests a background sync.

## Web: Bluetooth Keyboard

The Bluetooth page provides:

- Adapter status
- Scan button
- Device list
- Connect button
- Advanced MAC address connection form

Normal flow:

1. Put the keyboard in pairing mode.
2. Press `Scan`.
3. Press `Connect` next to the keyboard.

The device can also use USB keyboards. USB keyboard input is detected through Linux input events and does not require Bluetooth setup.

## Web: Wi-Fi

The Wi-Fi page lists visible SSIDs. Select a network, enter the password, and press `Connect`.

If the normal network cannot be reached, use the setup AP:

```text
SSID: Ize-Ribbon
Password: izeribbon
Web UI: http://10.42.0.1:8080
```

## Web: USB Export

`Refresh USB Export` updates the read-only USB text export image.

The USB export is deliberately read-only to avoid filesystem corruption. Use the Web UI refresh button or:

```bash
sudo bash scripts/refresh_usb_export.sh
```

## Battery Display

Battery display order:

1. Linux power supply capacity from `/sys/class/power_supply`
2. `upower` or `acpi`, if available
3. INA219-compatible voltage sensor over I2C
4. Manual fallback text

When INA219 voltage is used, the app converts LiPo voltage to an approximate percentage.

I2C requirements:

- `dtparam=i2c_arm=on`
- `i2c-dev` loaded
- user in the `i2c` group

## Power Behavior

Power off from the menu or Web UI shows a sleep/power-off notice before shutdown.

Idle shutdown uses the configured Auto Off time. When external power is detected, or when configured to assume external power on unknown power state, idle shutdown is skipped.

## Configuration Reference

Main `config.json` keys:

- `title`: display title
- `version`: firmware/software version
- `document`: current document path
- `font_ko`: Korean font
- `font_latin`: Latin font
- `body_font_size`: body text size
- `line_gap`: body line spacing
- `display_rotation`: `180` for upside-down mounting
- `body_visible_lines`: visible body lines
- `display_tail_chars`: text tail used for fast line layout
- `count_mode`: `off`, `words`, or `chars`
- `idle_shutdown_enabled`: idle shutdown switch
- `idle_shutdown_seconds`: idle timeout
- `selected_languages`: active input languages
- `input_language_index`: current language slot
- `web_port`: Web UI port
- `battery_source`: `auto` or `manual`
- `battery_manual_text`: fallback display
- `assume_external_power_when_unknown`: skip idle shutdown when power state is unknown
- `github_sync_repo`: GitHub repo in `owner/repository` format
- `github_sync_ssh_key`: deploy key path
- `usb_export_image`: USB image path
- `usb_export_mount`: USB export mount path
- `activity_file`: idle activity timestamp path

## Maintenance Commands

Restart services:

```bash
sudo systemctl restart ize-ribbon.service
sudo systemctl restart ize-ribbon-web.service
sudo systemctl restart ize-ribbon-idle-shutdown.service
```

Check status:

```bash
systemctl status ize-ribbon.service
systemctl status ize-ribbon-web.service
systemctl status ize-ribbon-idle-shutdown.service
```

View logs:

```bash
journalctl -u ize-ribbon.service -f
journalctl -u ize-ribbon-web.service -f
```

Manual Git sync check:

```bash
cd /home/ize/ize-ribbon/docs
git status
git log --oneline -5
```

## Version 2.0 Highlights

- GitHub private repository sync through Web UI
- Deploy key generation from the device
- Postbox-style document push from `docs/`
- Linux input event menu handling
- Bluetooth and USB keyboard detection
- Korean input composition
- Six-line writing display
- Faster cached rendering
- Battery percent from Linux or INA219 voltage
- Network/IP display on device and Web UI
- Wi-Fi setup AP fallback
- Safer new-document cache handling
- Sleep/power-off notice before shutdown
