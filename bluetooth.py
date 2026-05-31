import subprocess


def devices() -> str:
    result = subprocess.run(["bluetoothctl", "devices"], text=True, capture_output=True)
    return result.stdout


def paired_devices() -> list[dict[str, str]]:
    result = subprocess.run(["bluetoothctl", "devices"], text=True, capture_output=True)
    items: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split(" ", 2)
        if len(parts) == 3 and parts[0] == "Device":
            items.append({"mac": parts[1], "name": parts[2]})
    return items


def scan_on() -> str:
    result = subprocess.run(["bluetoothctl", "scan", "on"], text=True, capture_output=True, timeout=8)
    return result.stdout + result.stderr


def connect_device(mac: str) -> str:
    commands = f"pair {mac}\ntrust {mac}\nconnect {mac}\nquit\n"
    result = subprocess.run(["bluetoothctl"], input=commands, text=True, capture_output=True, timeout=30)
    return result.stdout + result.stderr
