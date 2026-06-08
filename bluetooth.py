import os
import pty
import re
import select
import subprocess
import time

from config_store import ROOT


SCAN_CACHE = ROOT / "bluetooth_scan.json"
_READY_CACHE_TIME = 0.0
_READY_CACHE_SECONDS = 60.0
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def bluetoothctl_args() -> list[str]:
    return ["sudo", "bluetoothctl"]


def _clean_output(text: str) -> str:
    return ANSI_RE.sub("", text).replace("\r", "")


def _agent_setup_commands(agent: str = "KeyboardDisplay") -> str:
    return (
        "power on\n"
        "pairable on\n"
        "discoverable on\n"
        "pairable-timeout 0\n"
        "discoverable-timeout 0\n"
        f"agent {agent}\n"
        "default-agent\n"
    )


def ensure_bluetooth_ready(force: bool = False) -> None:
    global _READY_CACHE_TIME
    now = time.time()
    if not force and now - _READY_CACHE_TIME < _READY_CACHE_SECONDS:
        return
    subprocess.run(["sudo", "/usr/sbin/rfkill", "unblock", "bluetooth"], text=True, capture_output=True, timeout=10)
    subprocess.run(
        bluetoothctl_args(),
        input=_agent_setup_commands() + "quit\n",
        text=True,
        capture_output=True,
        timeout=20,
    )
    _READY_CACHE_TIME = now


def _parse_devices(output: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in _clean_output(output).splitlines():
        match = re.search(r"(?:^|\s)Device\s+([0-9A-Fa-f:]{17})\s+(.+)$", line.strip())
        if match and match.group(1) not in seen:
            seen.add(match.group(1))
            items.append({"mac": match.group(1), "name": match.group(2)})
    return items


def _merge_devices(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            mac = item["mac"]
            if mac not in seen:
                seen.add(mac)
                merged.append(item)
    return merged


def _run_bluetoothctl(commands: str, timeout: int = 30) -> str:
    result = subprocess.run(bluetoothctl_args(), input=commands, text=True, capture_output=True, timeout=timeout)
    return _clean_output(result.stdout + result.stderr)


def _interactive_pair(mac: str, pin: str, agent: str, timeout: int = 25) -> str:
    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        bluetoothctl_args(),
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        text=False,
        close_fds=True,
    )
    os.close(slave_fd)
    output_parts: list[str] = []
    confirm_sent = False
    authorize_sent = False
    pin_sent = False

    def send(command: str) -> None:
        os.write(master_fd, (command + "\n").encode("utf-8", errors="ignore"))

    for command in _agent_setup_commands(agent).splitlines():
        if command:
            send(command)
    send(f"pair {mac}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        ready, _, _ = select.select([master_fd], [], [], 0.5)
        if not ready:
            if device_connected(mac):
                break
            continue
        try:
            chunk = os.read(master_fd, 4096)
        except OSError:
            break
        if not chunk:
            break
        clean = _clean_output(chunk.decode("utf-8", errors="ignore"))
        output_parts.append(clean)
        lowered = "".join(output_parts[-8:]).lower()
        if not confirm_sent and (
            "confirm passkey" in lowered
            or "accept pairing" in lowered
            or "[agent] confirm passkey" in lowered
            or "confirm yes/no" in lowered
        ):
            send("yes")
            confirm_sent = True
        elif not authorize_sent and ("authorize service" in lowered or "[agent] authorize service" in lowered):
            send("yes")
            authorize_sent = True
        elif (
            not pin_sent
            and ("enter pin code" in lowered or "request pin code" in lowered or "request passkey" in lowered)
            and pin
        ):
            send(pin)
            pin_sent = True
        elif "pairing successful" in lowered or "paired: yes" in lowered:
            break

    send(f"trust {mac}")
    send(f"connect {mac}")
    send(f"info {mac}")
    send("quit")
    try:
        deadline = time.time() + 10
        while time.time() < deadline:
            ready, _, _ = select.select([master_fd], [], [], 0.3)
            if not ready:
                if proc.poll() is not None:
                    break
                continue
            chunk = os.read(master_fd, 4096)
            if not chunk:
                break
            output_parts.append(_clean_output(chunk.decode("utf-8", errors="ignore")))
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
    return "".join(output_parts)


def read_scan_cache() -> list[dict[str, str]]:
    try:
        import json

        data = json.loads(SCAN_CACHE.read_text(encoding="utf-8"))
        return [item for item in data if isinstance(item, dict) and "mac" in item and "name" in item]
    except (OSError, ValueError):
        return []


def write_scan_cache(items: list[dict[str, str]]) -> None:
    try:
        import json

        SCAN_CACHE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def devices() -> list[dict[str, str]]:
    ensure_bluetooth_ready()
    result = subprocess.run(bluetoothctl_args() + ["devices"], text=True, capture_output=True, timeout=10)
    return _merge_devices(read_scan_cache(), _parse_devices(result.stdout))


def connected_devices() -> list[dict[str, str]]:
    ensure_bluetooth_ready()
    result = subprocess.run(bluetoothctl_args() + ["devices", "Connected"], text=True, capture_output=True, timeout=10)
    return _parse_devices(result.stdout)


def remembered_devices() -> list[dict[str, str]]:
    ensure_bluetooth_ready()
    result = subprocess.run(bluetoothctl_args() + ["devices"], text=True, capture_output=True, timeout=10)
    return _parse_devices(result.stdout)


def reconnect_remembered_devices() -> str:
    ensure_bluetooth_ready()
    output_parts: list[str] = []
    for item in remembered_devices():
        result = subprocess.run(
            bluetoothctl_args(),
            input=f"power on\nconnect {item['mac']}\nquit\n",
            text=True,
            capture_output=True,
            timeout=20,
        )
        output_parts.append(result.stdout + result.stderr)
        if connected_devices():
            break
    return "\n".join(output_parts)


def adapter_status() -> str:
    ensure_bluetooth_ready()
    result = subprocess.run(bluetoothctl_args() + ["show"], text=True, capture_output=True, timeout=10)
    return _clean_output(result.stdout + result.stderr)


def scan_for_devices(seconds: int = 10) -> tuple[list[dict[str, str]], str]:
    ensure_bluetooth_ready(force=True)
    proc = subprocess.Popen(
        bluetoothctl_args(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdin is not None
    proc.stdin.write(_agent_setup_commands() + "scan on\n")
    proc.stdin.flush()
    time.sleep(seconds)
    proc.stdin.write("devices\nscan off\nquit\n")
    proc.stdin.flush()
    output, _ = proc.communicate(timeout=seconds + 10)
    found = _merge_devices(_parse_devices(output), read_scan_cache())
    write_scan_cache(found)
    return found, output


def device_connected(mac: str) -> bool:
    result = subprocess.run(bluetoothctl_args() + ["info", mac], text=True, capture_output=True, timeout=10)
    return "Connected: yes" in result.stdout


def connect_device(mac: str, pin: str = "", reset: bool = False) -> str:
    ensure_bluetooth_ready(force=True)
    output_parts: list[str] = []
    if reset:
        output_parts.append(_run_bluetoothctl(f"remove {mac}\nquit\n", timeout=15))
        time.sleep(1)
    agent = "KeyboardOnly" if pin else "KeyboardDisplay"
    for attempt in range(1, 4):
        output_parts.append(f"\n--- attempt {attempt} ---\n")
        output_parts.append(_interactive_pair(mac, pin, agent, timeout=30))
        if device_connected(mac):
            output_parts.append("\nConnected.\n")
            return "".join(output_parts)
        time.sleep(1.5)
    if pin:
        output_parts.append("\nNot connected. For legacy keyboards, type the same PIN on the keyboard and press Enter during pairing.\n")
    else:
        output_parts.append("\nNot connected. Put the keyboard back in pairing mode and try once more. If it is a legacy keyboard, use PIN pairing.\n")
    return "".join(output_parts)


def scan_and_connect_keyboard(seconds: int = 18) -> str:
    found, output = scan_for_devices(seconds)
    if not found:
        return f"No Bluetooth devices found.\n\n{output[-2000:]}"
    keyboard_words = ("keyboard", "keys", "keychron", "logitech", "hhkb", "mx keys")
    preferred = [item for item in found if any(word in item["name"].lower() for word in keyboard_words)]
    candidates = preferred or found
    output_parts = [f"Found {len(found)} device(s).\n"]
    for item in candidates[:5]:
        output_parts.append(f"\nTrying {item['name']} ({item['mac']})\n")
        result = connect_device(item["mac"])
        output_parts.append(result[-2000:])
        if device_connected(item["mac"]):
            write_scan_cache(_merge_devices([item], found, read_scan_cache()))
            return "".join(output_parts)
    output_parts.append("\nNo candidate connected.\n")
    return "".join(output_parts)
