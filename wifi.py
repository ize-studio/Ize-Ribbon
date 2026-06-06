import subprocess


AP_CONNECTION = "Ize-Ribbon-Setup"
AP_SSID = "Ize-Ribbon"
AP_PASSWORD = "izeribbon"


def nmcli_args(*args: str) -> list[str]:
    return ["sudo", "nmcli", *args]


def known_connections() -> str:
    result = subprocess.run(nmcli_args("-t", "-f", "NAME,TYPE", "connection", "show"), text=True, capture_output=True)
    return result.stdout


def visible_networks() -> list[str]:
    subprocess.run(nmcli_args("dev", "wifi", "rescan"), text=True, capture_output=True, timeout=20)
    result = subprocess.run(
        nmcli_args("-t", "-f", "SSID", "dev", "wifi", "list"),
        text=True,
        capture_output=True,
    )
    seen: list[str] = []
    for line in result.stdout.splitlines():
        ssid = line.strip()
        if ssid and ssid not in seen:
            seen.append(ssid)
    return seen


def start_setup_ap() -> None:
    subprocess.run(nmcli_args("connection", "delete", AP_CONNECTION), text=True, capture_output=True)
    subprocess.run(
        nmcli_args(
            "device",
            "wifi",
            "hotspot",
            "ifname",
            "wlan0",
            "con-name",
            AP_CONNECTION,
            "ssid",
            AP_SSID,
            "password",
            AP_PASSWORD,
        ),
        text=True,
        capture_output=True,
        timeout=30,
    )


def connect_wifi(ssid: str, password: str) -> str:
    args = nmcli_args("dev", "wifi", "connect", ssid)
    if password:
        args.extend(["password", password])
    result = subprocess.run(args, text=True, capture_output=True, timeout=45)
    if result.returncode != 0:
        start_setup_ap()
    return result.stdout + result.stderr
