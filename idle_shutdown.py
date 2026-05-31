import time
from pathlib import Path
import subprocess

from config_store import load_config


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
        seconds = int(config.get("idle_shutdown_seconds", 300))
        activity_file = Path(config.get("activity_file", "/run/ize-ribbon/activity"))
        if enabled and seconds > 0 and time.time() - last_activity(activity_file) >= seconds:
            try:
                from display import show_message

                show_message("sleep...")
                time.sleep(2)
            except Exception:
                pass
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
            return
        time.sleep(5)


if __name__ == "__main__":
    main()
