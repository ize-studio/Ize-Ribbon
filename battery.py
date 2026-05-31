from pathlib import Path

from config_store import load_config


def _auto_capacity() -> str | None:
    root = Path("/sys/class/power_supply")
    if not root.exists():
        return None
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
    return None


def battery_text() -> str:
    config = load_config()
    if config.get("battery_source") == "auto":
        return _auto_capacity() or config.get("battery_manual_text", "--%")
    return config.get("battery_manual_text", "--%")
