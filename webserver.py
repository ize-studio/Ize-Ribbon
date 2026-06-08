import subprocess
from html import escape

from flask import Flask, redirect, render_template_string, request, send_file, url_for

from bluetooth import adapter_status, connect_device, connected_devices, devices, remembered_devices, scan_and_connect_keyboard, scan_for_devices
from config_store import ROOT, load_config, save_config, update_activity
from documents import counts, list_documents, new_document, preview, read_text, set_current_document, write_text
from git_sync import configure_docs_repo, generate_ssh_key, public_key_text, request_git_sync, test_github_connection
from language import current_language, set_selected_languages
from network_status import active_ssid, primary_ip
from power import shutdown_now
from wifi import connect_wifi, visible_networks


app = Flask(__name__)


@app.before_request
def mark_web_activity():
    update_activity()


PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ize Ribbon</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 24px; color: #111; background: #fafafa; }
    main { max-width: 920px; margin: 0 auto; }
    table { width: 100%; border-collapse: collapse; background: white; }
    th, td { border-bottom: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }
    button, a.button { display: inline-block; padding: 8px 12px; border: 1px solid #222; background: white; color: #111; text-decoration: none; cursor: pointer; }
    input, select { padding: 7px; min-width: 220px; }
    textarea { width: 100%; min-height: 45vh; font: 16px/1.45 ui-monospace, monospace; }
    pre { white-space: pre-wrap; padding: 10px 12px; background: #fff; border: 1px solid #ddd; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .muted { color: #666; }
    .notice { padding: 10px 12px; background: #fff; border-left: 4px solid #111; }
    section { margin: 22px 0; }
    label { display: inline-flex; gap: 4px; align-items: center; margin: 4px 10px 4px 0; }
  </style>
</head>
<body>
<main>
  <h1>Ize Ribbon</h1>
  {{ body|safe }}
</main>
</body>
</html>
"""


def page(body: str) -> str:
    return render_template_string(PAGE, body=body)


def notice_from_query() -> str:
    message = request.args.get("message", "")
    if not message:
        return ""
    return f"<section class='notice'><pre>{escape(message)}</pre></section>"


def status_panel() -> str:
    config = load_config()
    port = int(config.get("web_port", 8080))
    ip = primary_ip()
    ssid = active_ssid()
    connected = connected_devices()
    if connected:
        bluetooth_text = ", ".join(escape(item["name"]) for item in connected)
    else:
        known = remembered_devices()
        bluetooth_text = "Not connected"
        if known:
            names = ", ".join(escape(item["name"]) for item in known[:3])
            bluetooth_text += f" (known: {names})"
    wifi_text = f"{escape(ssid or 'Not connected')}"
    url_text = f"http://{escape(ip)}:{port}" if ip else "Waiting for IP"
    input_text = escape(current_language())
    version = escape(str(config.get("version", "2.0")))
    return f"""
    <section class="notice">
      <div><strong>Version</strong>: {version}</div>
      <div><strong>Wi-Fi</strong>: {wifi_text}</div>
      <div><strong>Web UI</strong>: {url_text}</div>
      <div><strong>Bluetooth</strong>: {bluetooth_text}</div>
      <div><strong>Input</strong>: {input_text}</div>
    </section>
    """


@app.get("/")
def index():
    config = load_config()
    rows = []
    for path in list_documents():
        text = read_text(path)
        chars, words = counts(text)
        number = path.stem.replace("note", "")
        rows.append(
            f"<tr><td>{number}</td><td>{escape(preview(text, int(config.get('web_preview_chars', 12))))}</td>"
            f"<td>{chars} chars / {words} words</td>"
            f"<td><a class='button' href='{url_for('edit_doc', name=path.name)}'>Open</a> "
            f"<a class='button' href='{url_for('download_doc', name=path.name)}'>Download</a></td></tr>"
        )
    body = f"""
    {notice_from_query()}
    {status_panel()}
    <section class="row">
      <form method="post" action="{url_for('create_doc')}"><button>New Document</button></form>
      <form method="post" action="{url_for('refresh_usb')}"><button>Refresh USB Export</button></form>
      <a class="button" href="{url_for('settings')}">Settings</a>
      <a class="button" href="{url_for('github_page')}">GitHub Sync</a>
      <a class="button" href="{url_for('bluetooth_page')}">Bluetooth Keyboard</a>
      <a class="button" href="{url_for('wifi_page')}">Wi-Fi</a>
      <form method="post" action="{url_for('power_off')}"><button>Power Off</button></form>
    </section>
    <section>
      <table>
        <thead><tr><th>No.</th><th>Preview</th><th>Length</th><th></th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    """
    return page(body)


@app.post("/documents/new")
def create_doc():
    new_document()
    return redirect(url_for("index"))


@app.get("/documents/<name>")
def edit_doc(name: str):
    path = ROOT / "docs" / name
    if not path.exists() or not name.startswith("note") or path.suffix != ".txt":
        return ("not found", 404)
    text = escape(read_text(path))
    body = f"""
    <section><a class="button" href="{url_for('index')}">Back</a></section>
    <form method="post">
      <textarea name="text">{text}</textarea>
      <p class="row">
        <button>Save</button>
        <button name="open" value="1">Save and Open on Device</button>
      </p>
    </form>
    """
    return page(body)


@app.post("/documents/<name>")
def save_doc(name: str):
    path = ROOT / "docs" / name
    if not path.exists() or not name.startswith("note") or path.suffix != ".txt":
        return ("not found", 404)
    write_text(request.form.get("text", ""), path)
    if request.form.get("open") == "1":
        set_current_document(path)
    return redirect(url_for("edit_doc", name=name))


@app.get("/documents/<name>/download")
def download_doc(name: str):
    path = ROOT / "docs" / name
    if not path.exists() or not name.startswith("note") or path.suffix != ".txt":
        return ("not found", 404)
    return send_file(path, as_attachment=True, download_name=name)


@app.get("/settings")
def settings():
    config = load_config()
    languages = config.get("available_languages", [])
    selected = set(config.get("selected_languages", ["EN", "KO"]))
    checks = []
    for item in languages:
        code = escape(item["code"])
        label = escape(item["label"])
        checked = "checked" if item["code"] == "EN" or item["code"] in selected else ""
        disabled = "disabled" if item["code"] == "EN" else ""
        checks.append(f"<label><input type='checkbox' name='language' value='{code}' {checked} {disabled}> {code} {label}</label>")
    body = f"""
    <section><a class="button" href="{url_for('index')}">Back</a></section>
    <form method="post">
      <p>Counter</p>
      <select name="count_mode">
        <option value="off" {'selected' if config.get('count_mode') == 'off' else ''}>OFF</option>
        <option value="words" {'selected' if config.get('count_mode') == 'words' else ''}>Words</option>
        <option value="chars" {'selected' if config.get('count_mode') == 'chars' else ''}>Characters</option>
      </select>
      <p>Auto Off</p>
      <select name="idle_seconds">
        {''.join(f"<option value='{v}' {'selected' if int(config.get('idle_shutdown_seconds', 1800)) == v and config.get('idle_shutdown_enabled', True) else ''}>{label}</option>" for label, v in [('10 min',600),('30 min',1800),('60 min',3600)])}
      </select>
      <p>Battery Display</p>
      <select name="battery_source">
        <option value="manual" {'selected' if config.get('battery_source') == 'manual' else ''}>manual</option>
        <option value="auto" {'selected' if config.get('battery_source') == 'auto' else ''}>auto</option>
      </select>
      <input name="battery_manual_text" value="{escape(config.get('battery_manual_text', '--%'))}" maxlength="8">
      <p>Input Languages</p>
      <p class="muted">EN is always fixed as the first slot. Select up to five languages including EN.</p>
      <div>{''.join(checks)}</div>
      <p><button>Save</button></p>
    </form>
    """
    return page(body)


@app.post("/settings")
def save_settings():
    config = load_config()
    config["count_mode"] = request.form.get("count_mode", "chars")
    idle = int(request.form.get("idle_seconds", "1800"))
    config["idle_shutdown_enabled"] = idle != 0
    config["idle_shutdown_seconds"] = idle
    config["battery_source"] = request.form.get("battery_source", "manual")
    config["battery_manual_text"] = request.form.get("battery_manual_text", "--%")[:8]
    save_config(config)
    set_selected_languages(request.form.getlist("language"))
    update_activity()
    return redirect(url_for("settings"))


@app.get("/github")
def github_page():
    config = load_config()
    repo = escape(config.get("github_sync_repo", ""))
    key = escape(public_key_text())
    key_block = f"<pre>{key}</pre>" if key else "<p class='muted'>No SSH key has been generated yet.</p>"
    body = f"""
    <section><a class="button" href="{url_for('index')}">Back</a></section>
    {notice_from_query()}
    <section class="notice">
      <div><strong>GitHub Sync</strong></div>
      <div class="muted">Use a private GitHub repository as a Postbox-style writing archive.</div>
    </section>
    <section>
      <form method="post" action="{url_for('github_save')}">
        <p>Repository</p>
        <input name="repo" value="{repo}" placeholder="owner/repository">
        <button>Save Repository</button>
      </form>
    </section>
    <section>
      <form method="post" action="{url_for('github_key')}"><button>Generate SSH Key</button></form>
      <p class="muted">Copy this public key into GitHub repository Settings > Deploy keys. Enable Allow write access.</p>
      {key_block}
    </section>
    <section class="row">
      <form method="post" action="{url_for('github_test')}"><button>Test Connection</button></form>
      <form method="post" action="{url_for('github_connect')}"><button>Connect Docs Folder</button></form>
      <form method="post" action="{url_for('github_sync_now')}"><button>Sync Now</button></form>
    </section>
    """
    return page(body)


@app.post("/github/save")
def github_save():
    repo = request.form.get("repo", "").strip()
    if repo.endswith(".git"):
        repo = repo[:-4]
    repo = repo.replace("https://github.com/", "").replace("git@github.com:", "")
    repo = repo.strip("/")
    config = load_config()
    config["github_sync_repo"] = repo
    config.setdefault("github_sync_ssh_key", "/home/ize/.ssh/ize_ribbon_github_ed25519")
    save_config(config)
    return redirect(url_for("github_page", message=f"Repository saved: {repo}"))


@app.post("/github/key")
def github_key():
    result = generate_ssh_key()
    message = "SSH key is ready." if result.returncode == 0 else (result.stderr or "Failed to generate SSH key.")
    return redirect(url_for("github_page", message=message[-1200:]))


@app.post("/github/test")
def github_test():
    result = test_github_connection()
    output = (result.stdout + result.stderr).strip()
    return redirect(url_for("github_page", message=output[-1200:] or f"Exit code: {result.returncode}"))


@app.post("/github/connect")
def github_connect():
    message = configure_docs_repo()
    return redirect(url_for("github_page", message=message[-2000:]))


@app.post("/github/sync")
def github_sync_now():
    request_git_sync()
    return redirect(url_for("github_page", message="Sync requested. It will run in the background when Wi-Fi is available."))


@app.get("/bluetooth")
def bluetooth_page():
    status = escape(adapter_status())
    rows = []
    for item in devices():
        raw_name = item["name"]
        name = escape(raw_name)
        mac = escape(item["mac"])
        label = "Unnamed device" if raw_name.replace("-", ":").upper() == item["mac"].upper() else name
        rows.append(
            f"<tr><td>{label}<div class='muted'>{mac}</div></td>"
            f"<td><form method='post' action='{url_for('bluetooth_connect')}'><input type='hidden' name='mac' value='{mac}'><button>Connect</button></form></td></tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='2' class='muted'>No Bluetooth devices found yet. Put the keyboard in pairing mode and press Scan.</td></tr>")
    body = f"""
    <section><a class="button" href="{url_for('index')}">Back</a></section>
    {notice_from_query()}
    <section class="notice">Put the keyboard in pairing mode, press Scan, then connect from the list. Legacy keyboards may ask for a PIN or confirmation during pairing.</section>
    <section class="row">
      <form method="post" action="{url_for('bluetooth_auto_connect')}"><button>Scan and Connect Keyboard</button></form>
      <form method="post" action="{url_for('bluetooth_scan')}"><button>Scan Only</button></form>
    </section>
    <section>
      <table>
        <thead><tr><th>Device</th><th></th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    <section>
      <form method="post" action="{url_for('bluetooth_connect')}">
        <p class="muted">Advanced: connect by MAC address only if the device is not listed. For legacy keyboards, enter a PIN, start pairing, then type the same PIN on the keyboard and press Enter.</p>
        <input name="mac" placeholder="AA:BB:CC:DD:EE:FF">
        <input name="pin" placeholder="PIN for legacy keyboard">
        <label><input type="checkbox" name="reset" value="1"> reset old pairing first</label>
        <button>pair / trust / connect</button>
      </form>
    </section>
    <section>
      <p class="muted">Adapter Status</p>
      <pre>{status}</pre>
    </section>
    """
    return page(body)


@app.post("/bluetooth/scan")
def bluetooth_scan():
    found, output = scan_for_devices()
    update_activity()
    names = ", ".join(f"{item['name']} ({item['mac']})" for item in found) or "No devices found during this scan."
    return redirect(url_for("bluetooth_page", message=f"Scan complete. {names}\n\nRaw scan output:\n{output[-2500:]}"))


@app.post("/bluetooth/auto-connect")
def bluetooth_auto_connect():
    message = scan_and_connect_keyboard()
    update_activity()
    return redirect(url_for("bluetooth_page", message=message[-2500:]))


@app.post("/bluetooth/connect")
def bluetooth_connect():
    mac = request.form.get("mac", "").strip()
    pin = request.form.get("pin", "").strip()
    reset = request.form.get("reset") == "1"
    message = ""
    if mac:
        message = connect_device(mac, pin=pin, reset=reset)
    update_activity()
    return redirect(url_for("bluetooth_page", message=message[-1200:]))


@app.get("/wifi")
def wifi_page():
    networks = visible_networks()
    options = "".join(f"<option value='{escape(ssid)}'>{escape(ssid)}</option>" for ssid in networks)
    if not options:
        options = "<option value=''>No Wi-Fi networks found</option>"
    body = f"""
    <section><a class="button" href="{url_for('index')}">Back</a></section>
    {notice_from_query()}
    <form method="post">
      <p>SSID</p>
      <select name="ssid">{options}</select>
      <p>Password</p>
      <input name="password" type="password">
      <p><button>Connect</button></p>
    </form>
    """
    return page(body)


@app.post("/wifi")
def wifi_connect():
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "")
    message = ""
    if ssid:
        message = connect_wifi(ssid, password)
    update_activity()
    return redirect(url_for("wifi_page", message=message[-1200:]))


@app.post("/usb/refresh")
def refresh_usb():
    update_activity()
    subprocess.run(["sudo", "bash", str(ROOT / "scripts" / "refresh_usb_export.sh")], check=False)
    return redirect(url_for("index"))


@app.post("/power/off")
def power_off():
    shutdown_now()
    return page("<section class='notice'>Powering off. The e-paper should show sleep...</section>")


def main() -> None:
    config = load_config()
    app.run(host="0.0.0.0", port=int(config.get("web_port", 8080)))


if __name__ == "__main__":
    main()
