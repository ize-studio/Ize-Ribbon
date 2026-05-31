import subprocess
import time


def _parse_devices(output: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in output.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) == 3 and parts[0] == "Device" and parts[1] not in seen:
            seen.add(parts[1])
            items.append({"mac": parts[1], "name": parts[2]})
    return items


def devices() -> list[dict[str, str]]:
    result = subprocess.run(["bluetoothctl", "devices"], text=True, capture_output=True, timeout=10)
    return _parse_devices(result.stdout)


def scan_for_devices(seconds: int = 10) -> list[dict[str, str]]:
    proc = subprocess.Popen(
        ["bluetoothctl"],
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
    return _parse_devices(output)


def connect_device(mac: str) -> str:
    commands = f"power on\nagent on\ndefault-agent\npair {mac}\ntrust {mac}\nconnect {mac}\nquit\n"
    result = subprocess.run(["bluetoothctl"], input=commands, text=True, capture_output=True, timeout=45)
    return result.stdout + result.stderr
