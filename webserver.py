import subprocess
from html import escape

from flask import Flask, redirect, render_template_string, request, send_file, url_for

from bluetooth import connect_device, devices, scan_for_devices
from config_store import ROOT, load_config, save_config, update_activity
from documents import counts, list_documents, new_document, preview, read_text, set_current_document, write_text
from language import set_selected_languages
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
            f"<td>{chars}자 / {words}단어</td>"
            f"<td><a class='button' href='{url_for('edit_doc', name=path.name)}'>열기</a> "
            f"<a class='button' href='{url_for('download_doc', name=path.name)}'>받기</a></td></tr>"
        )
    body = f"""
    <section class="row">
      <form method="post" action="{url_for('create_doc')}"><button>새 문서 만들기</button></form>
      <form method="post" action="{url_for('refresh_usb')}"><button>USB export refresh</button></form>
      <a class="button" href="{url_for('settings')}">설정</a>
      <a class="button" href="{url_for('bluetooth_page')}">Bluetooth 키보드</a>
      <a class="button" href="{url_for('wifi_page')}">Wi-Fi</a>
      <form method="post" action="{url_for('power_off')}"><button>Power Off</button></form>
    </section>
    <section>
      <table>
        <thead><tr><th>번호</th><th>미리보기</th><th>분량</th><th></th></tr></thead>
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
    <section><a class="button" href="{url_for('index')}">목록</a></section>
    <form method="post">
      <textarea name="text">{text}</textarea>
      <p class="row">
        <button>저장</button>
        <button name="open" value="1">저장하고 현재 문서로 열기</button>
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
    <section><a class="button" href="{url_for('index')}">목록</a></section>
    <form method="post">
      <p>카운트</p>
      <select name="count_mode">
        <option value="off" {'selected' if config.get('count_mode') == 'off' else ''}>OFF</option>
        <option value="words" {'selected' if config.get('count_mode') == 'words' else ''}>단어</option>
        <option value="chars" {'selected' if config.get('count_mode') == 'chars' else ''}>글자</option>
      </select>
      <p>자동잠자기</p>
      <select name="idle_seconds">
        {''.join(f"<option value='{v}' {'selected' if int(config.get('idle_shutdown_seconds', 300)) == v and config.get('idle_shutdown_enabled', True) else ''}>{label}</option>" for label, v in [('1분',60),('5분',300),('10분',600),('30분',1800),('1시간',3600)])}
        <option value="0" {'selected' if not config.get('idle_shutdown_enabled', True) else ''}>OFF</option>
      </select>
      <p>배터리 표시</p>
      <select name="battery_source">
        <option value="manual" {'selected' if config.get('battery_source') == 'manual' else ''}>manual</option>
        <option value="auto" {'selected' if config.get('battery_source') == 'auto' else ''}>auto</option>
      </select>
      <input name="battery_manual_text" value="{escape(config.get('battery_manual_text', '--%'))}" maxlength="8">
      <p>언어 선택</p>
      <p class="muted">EN은 항상 첫 번째로 고정됩니다. 아래 지원 후보 전체 중에서 EN을 포함해 최대 5개까지 사용할 수 있습니다.</p>
      <div>{''.join(checks)}</div>
      <p><button>저장</button></p>
    </form>
    """
    return page(body)


@app.post("/settings")
def save_settings():
    config = load_config()
    config["count_mode"] = request.form.get("count_mode", "chars")
    idle = int(request.form.get("idle_seconds", "300"))
    config["idle_shutdown_enabled"] = idle != 0
    config["idle_shutdown_seconds"] = idle
    config["battery_source"] = request.form.get("battery_source", "manual")
    config["battery_manual_text"] = request.form.get("battery_manual_text", "--%")[:8]
    save_config(config)
    set_selected_languages(request.form.getlist("language"))
    update_activity()
    return redirect(url_for("settings"))


@app.get("/bluetooth")
def bluetooth_page():
    rows = []
    for item in devices():
        name = escape(item["name"])
        mac = escape(item["mac"])
        rows.append(
            f"<tr><td>{name}</td><td>{mac}</td>"
            f"<td><form method='post' action='{url_for('bluetooth_connect')}'><input type='hidden' name='mac' value='{mac}'><button>연결</button></form></td></tr>"
        )
    body = f"""
    <section><a class="button" href="{url_for('index')}">목록</a></section>
    <section class="notice">키보드를 페어링 모드로 둔 뒤 스캔을 누르십시오. 스캔은 약 10초 동안 실행됩니다.</section>
    <section class="row">
      <form method="post" action="{url_for('bluetooth_scan')}"><button>스캔</button></form>
    </section>
    <section>
      <table>
        <thead><tr><th>이름</th><th>MAC</th><th></th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>
    <section>
      <form method="post" action="{url_for('bluetooth_connect')}">
        <p>목록에 없으면 MAC 주소 입력</p>
        <input name="mac" placeholder="AA:BB:CC:DD:EE:FF">
        <button>pair / trust / connect</button>
      </form>
    </section>
    """
    return page(body)


@app.post("/bluetooth/scan")
def bluetooth_scan():
    scan_for_devices()
    update_activity()
    return redirect(url_for("bluetooth_page"))


@app.post("/bluetooth/connect")
def bluetooth_connect():
    mac = request.form.get("mac", "").strip()
    if mac:
        connect_device(mac)
    update_activity()
    return redirect(url_for("bluetooth_page"))


@app.get("/wifi")
def wifi_page():
    options = "".join(f"<option value='{escape(ssid)}'>{escape(ssid)}</option>" for ssid in visible_networks())
    body = f"""
    <section><a class="button" href="{url_for('index')}">목록</a></section>
    <form method="post">
      <p>SSID</p>
      <input name="ssid" list="ssids">
      <datalist id="ssids">{options}</datalist>
      <p>비밀번호</p>
      <input name="password" type="password">
      <p><button>연결</button></p>
    </form>
    """
    return page(body)


@app.post("/wifi")
def wifi_connect():
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "")
    if ssid:
        connect_wifi(ssid, password)
    update_activity()
    return redirect(url_for("wifi_page"))


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
