import subprocess
import time

from config_store import update_activity


SHUTDOWN_NOTICE_SECONDS = 10


def shutdown_after_notice() -> None:
    time.sleep(SHUTDOWN_NOTICE_SECONDS)
    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)


def shutdown_now(lines: list[str] | None = None) -> None:
    update_activity()
    result = subprocess.run(["pkill", "-USR1", "-u", "ize", "-f", "/home/ize/ize-ribbon/app.py"], check=False)
    if result.returncode != 0:
        try:
            from display import show_message

            show_message(lines or ["Sleeping", "Power off"])
        except Exception:
            pass
    shutdown_after_notice()
