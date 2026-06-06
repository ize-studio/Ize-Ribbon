from pathlib import Path
import re
import subprocess

from config_store import load_config


def external_power_connected() -> bool:
    config = load_config()
    assume_when_unknown = bool(config.get("assume_external_power_when_unknown", True))
    root = Path("/sys/class/power_supply")
    if not root.exists():
        return assume_when_unknown
    saw_battery = False
    saw_external = False
    for item in root.iterdir():
        type_path = item / "type"
        online_path = item / "online"
        status_path = item / "status"
        try:
            supply_type = type_path.read_text(encoding="utf-8").strip().lower()
            if supply_type in {"mains", "usb", "usb_c", "usb-c", "ac"} and online_path.exists():
                saw_external = True
                return online_path.read_text(encoding="utf-8").strip() == "1"
            if supply_type == "battery" and status_path.exists():
                saw_battery = True
                status = status_path.read_text(encoding="utf-8").strip().lower()
                if status in {"charging", "full"}:
                    return True
        except OSError:
            continue
    if saw_battery and not saw_external:
        return False
    return assume_when_unknown


def _auto_capacity() -> str | None:
    root = Path("/sys/class/power_supply")
    if root.exists():
        for item in root.iterdir():
            type_path = item / "type"
            capacity_path = item / "capacity"
            try:
                if type_path.read_text(encoding="utf-8").strip().lower() == "battery":
                    value = capacity_path.read_text(encoding="utf-8").strip()
                    if value.isdigit():
                        return f"{value}%"
            except OSError:
                continue
    for command in (["upower", "-d"], ["acpi", "-b"]):
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=2)
        except (OSError, subprocess.SubprocessError):
            continue
        match = re.search(r"(\d{1,3})%", result.stdout)
        if match:
            return f"{min(100, int(match.group(1)))}%"
    return None


def _percent_from_lipo_voltage(voltage: float) -> int:
    curve = [
        (4.20, 100),
        (4.10, 90),
        (4.00, 80),
        (3.92, 70),
        (3.85, 60),
        (3.79, 50),
        (3.73, 40),
        (3.68, 30),
        (3.61, 20),
        (3.50, 10),
        (3.30, 0),
    ]
    if voltage >= curve[0][0]:
        return 100
    if voltage <= curve[-1][0]:
        return 0
    for (high_v, high_pct), (low_v, low_pct) in zip(curve, curve[1:]):
        if low_v <= voltage <= high_v:
            ratio = (voltage - low_v) / (high_v - low_v)
            return round(low_pct + ratio * (high_pct - low_pct))
    return 0


def _ina219_capacity_text() -> str | None:
    try:
        import smbus2
    except ImportError:
        return None

    config = load_config()
    addresses = config.get("battery_ina219_addresses", [0x43, 0x40, 0x41, 0x44, 0x45])
    try:
        bus = smbus2.SMBus(1)
    except OSError:
        return None
    try:
        for address in addresses:
            try:
                raw = bus.read_i2c_block_data(int(address), 0x02, 2)
            except (OSError, TypeError, ValueError):
                continue
            value = (raw[0] << 8) | raw[1]
            voltage = ((value >> 3) * 4) / 1000
            if 2.5 <= voltage <= 6.5:
                return f"{_percent_from_lipo_voltage(voltage)}%"
    finally:
        bus.close()
    return None


def battery_text() -> str:
    config = load_config()
    if config.get("battery_source") == "auto":
        return _auto_capacity() or _ina219_capacity_text() or config.get("battery_manual_text", "--%")
    return config.get("battery_manual_text", "--%")
