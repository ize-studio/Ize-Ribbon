import time
from pathlib import Path

from battery import battery_percent, external_power_connected
from config_store import load_config
from power import shutdown_lines, shutdown_now


def last_activity(path: Path) -> float:
    try:
        return float(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return time.time()


def main() -> None:
    config = load_config()
    activity_file = Path(config.get("activity_file", "/run/ize-ribbon/activity"))
    try:
        activity_file.parent.mkdir(parents=True, exist_ok=True)
        if not activity_file.exists():
            activity_file.write_text(str(time.time()), encoding="ascii")
    except OSError:
        pass

    while True:
        config = load_config()
        enabled = bool(config.get("idle_shutdown_enabled", True))
        seconds = int(config.get("idle_shutdown_seconds", 1800))
        low_battery_enabled = bool(config.get("low_battery_shutdown_enabled", True))
        low_battery_percent = int(config.get("low_battery_shutdown_percent", 20))
        activity_file = Path(config.get("activity_file", "/run/ize-ribbon/activity"))
        on_external_power = external_power_connected()
        if not on_external_power and low_battery_enabled:
            percent = battery_percent()
            if percent is not None and percent <= low_battery_percent:
                shutdown_now(shutdown_lines("Low battery", f"Battery {percent}%"))
                return
        if enabled and seconds > 0 and time.time() - last_activity(activity_file) >= seconds:
            shutdown_now(shutdown_lines("Idle timeout", f"{seconds // 60} min"))
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
