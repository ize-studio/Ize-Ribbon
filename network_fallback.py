import subprocess
import time


AP_SSID = "Ize-Ribbon"
AP_PASSWORD = "izeribbon"
WAIT_SECONDS = 180


def has_ipv4_address() -> bool:
    result = subprocess.run(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"],
        text=True,
        capture_output=True,
    )
    for line in result.stdout.splitlines():
        parts = line.split(":")
        if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
            return True
    return False


def start_access_point() -> None:
    subprocess.run(["nmcli", "connection", "delete", "Ize-Ribbon-Setup"], text=True, capture_output=True)
    subprocess.run(
        [
            "nmcli",
            "device",
            "wifi",
            "hotspot",
            "ifname",
            "wlan0",
            "con-name",
            "Ize-Ribbon-Setup",
            "ssid",
            AP_SSID,
            "password",
            AP_PASSWORD,
        ],
        check=False,
    )


def main() -> None:
    deadline = time.time() + WAIT_SECONDS
    while time.time() < deadline:
        if has_ipv4_address():
            return
        time.sleep(5)
    if not has_ipv4_address():
        start_access_point()


if __name__ == "__main__":
    main()
