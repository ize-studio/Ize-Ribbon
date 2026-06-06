import subprocess

from config_store import load_config


AP_CONNECTION = "Ize-Ribbon-Setup"
AP_SSID = "Ize-Ribbon"


def active_wifi_connection_names() -> list[str]:
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"],
            text=True,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    names: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] == "802-11-wireless" and parts[2].startswith("wlan"):
            names.append(parts[0])
    return names


def client_wifi_connected() -> bool:
    return any(name != AP_CONNECTION for name in active_wifi_connection_names())


def setup_ap_active() -> bool:
    return AP_CONNECTION in active_wifi_connection_names()


def active_ipv4_addresses() -> list[str]:
    try:
        result = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "scope", "global"],
            text=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    addresses: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            address = parts[3].split("/", 1)[0]
            if address and not address.startswith("127."):
                addresses.append(address)
    return addresses


def primary_ip() -> str | None:
    addresses = active_ipv4_addresses()
    if not addresses:
        return None
    wlan_addresses = [address for address in addresses if address.startswith(("10.", "172.", "192.168."))]
    return wlan_addresses[0] if wlan_addresses else addresses[0]


def active_ssid() -> str | None:
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
            text=True,
            capture_output=True,
            timeout=8,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in result.stdout.splitlines():
        active, _, ssid = line.partition(":")
        if active == "yes" and ssid:
            return ssid
    return None


def web_url_lines(ip: str | None = None) -> list[str]:
    port = int(load_config().get("web_port", 8080))
    if ip:
        return [f"http://{ip}:{port}", f"ize-ribbon.local:{port}"]
    return ["Waiting for Wi-Fi", "Setup AP: Ize-Ribbon", f"http://10.42.0.1:{port}"]


def network_display_lines() -> list[str]:
    ip = primary_ip()
    ssid = active_ssid()
    port = int(load_config().get("web_port", 8080))
    if client_wifi_connected() and ip:
        return [
            f"WiFi {ssid or 'on'}",
            f"{ip}:{port}",
        ]
    if setup_ap_active():
        return [
            f"AP {AP_SSID}",
            f"10.42.0.1:{port}",
        ]
    return [
        f"AP {AP_SSID}",
        f"10.42.0.1:{port}",
    ]


def startup_display_lines(keyboard_ready: bool = False, wifi_ready: bool | None = None) -> list[str]:
    lines = network_display_lines()
    wifi_ready = client_wifi_connected() if wifi_ready is None else wifi_ready
    if keyboard_ready and wifi_ready:
        return ["READY", *lines]
    if not wifi_ready:
        return ["WEB SETUP", *lines]
    return ["KBD WAIT", *lines]
