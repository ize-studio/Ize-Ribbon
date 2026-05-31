import subprocess


def known_connections() -> str:
    result = subprocess.run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], text=True, capture_output=True)
    return result.stdout


def visible_networks() -> list[str]:
    subprocess.run(["nmcli", "dev", "wifi", "rescan"], text=True, capture_output=True, timeout=20)
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID", "dev", "wifi", "list"],
        text=True,
        capture_output=True,
    )
    seen: list[str] = []
    for line in result.stdout.splitlines():
        ssid = line.strip()
        if ssid and ssid not in seen:
            seen.append(ssid)
    return seen


def connect_wifi(ssid: str, password: str) -> str:
    args = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        args.extend(["password", password])
    result = subprocess.run(args, text=True, capture_output=True, timeout=45)
    return result.stdout + result.stderr
