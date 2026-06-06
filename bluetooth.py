import subprocess
import time
import re

from config_store import ROOT


SCAN_CACHE = ROOT / "bluetooth_scan.json"
_READY_CACHE_TIME = 0.0
_READY_CACHE_SECONDS = 60.0


def bluetoothctl_args() -> list[str]:
    return ["sudo", "bluetoothctl"]


def ensure_bluetooth_ready() -> None:
    global _READY_CACHE_TIME
    now = time.time()
    if now - _READY_CACHE_TIME < _READY_CACHE_SECONDS:
        return
    subprocess.run(["sudo", "/usr/sbin/rfkill", "unblock", "bluetooth"], text=True, capture_output=True, timeout=10)
    subprocess.run(
        bluetoothctl_args(),
        input="power on\npairable on\nagent on\ndefault-agent\nquit\n",
        text=True,
        capture_output=True,
        timeout=20,
    )
    _READY_CACHE_TIME = now


def _parse_devices(output: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in output.splitlines():
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
    return result.stdout + result.stderr


def scan_for_devices(seconds: int = 10) -> tuple[list[dict[str, str]], str]:
    ensure_bluetooth_ready()
    proc = subprocess.Popen(
        bluetoothctl_args(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdin is not None
    proc.stdin.write("power on\nagent on\ndefault-agent\nscan on\n")
    proc.stdin.flush()
    time.sleep(seconds)
    proc.stdin.write("devices\nscan off\nquit\n")
    proc.stdin.flush()
    output, _ = proc.communicate(timeout=seconds + 10)
    found = _merge_devices(_parse_devices(output), read_scan_cache())
    write_scan_cache(found)
    return found, output


def connect_device(mac: str) -> str:
    ensure_bluetooth_ready()
    commands = f"power on\nagent on\ndefault-agent\npair {mac}\ntrust {mac}\nconnect {mac}\nquit\n"
    result = subprocess.run(bluetoothctl_args(), input=commands, text=True, capture_output=True, timeout=45)
    return result.stdout + result.stderr
