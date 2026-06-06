import subprocess
import time


AP_SSID = "Ize-Ribbon"
AP_PASSWORD = "izeribbon"
AP_CONNECTION = "Ize-Ribbon-Setup"
BOOT_GRACE_SECONDS = 60
RETRY_SECONDS = 10


def active_wifi_connections() -> list[str]:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"],
        text=True,
        capture_output=True,
    )
    names: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] == "802-11-wireless" and parts[2].startswith("wlan"):
            names.append(parts[0])
    return names


def has_client_wifi() -> bool:
    return any(name != AP_CONNECTION for name in active_wifi_connections())


def has_setup_ap() -> bool:
    return AP_CONNECTION in active_wifi_connections()


def start_access_point() -> None:
    if has_setup_ap():
        return
    subprocess.run(["nmcli", "connection", "delete", AP_CONNECTION], text=True, capture_output=True)
    subprocess.run(
        [
            "nmcli",
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
        ],
        check=False,
    )


def main() -> None:
    missing_since: float | None = None
    grace_seconds = BOOT_GRACE_SECONDS

    while True:
        if has_client_wifi() or has_setup_ap():
            missing_since = None
            time.sleep(RETRY_SECONDS)
            continue

        now = time.time()
        if missing_since is None:
            missing_since = now
        if now - missing_since >= grace_seconds:
            start_access_point()
            grace_seconds = RETRY_SECONDS
        time.sleep(RETRY_SECONDS)


if __name__ == "__main__":
    main()
