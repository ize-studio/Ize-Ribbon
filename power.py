import subprocess
import time
import json

from config_store import ROOT, update_activity


SHUTDOWN_NOTICE_SECONDS = 10
SHUTDOWN_NOTICE_PATH = ROOT / "shutdown_notice.json"


def shutdown_lines(reason: str = "Power off", detail: str = "Please wait") -> list[str]:
    return ["Powering off", reason, detail]


def write_shutdown_notice(lines: list[str] | None = None) -> None:
    try:
        SHUTDOWN_NOTICE_PATH.write_text(json.dumps(lines or shutdown_lines()), encoding="utf-8")
    except OSError:
        pass


def shutdown_after_notice() -> None:
    time.sleep(SHUTDOWN_NOTICE_SECONDS)
    result = subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
    if result.returncode != 0:
        try:
            from display import show_message

            show_message(["Shutdown failed", "Device is still on"])
        except Exception:
            pass


def shutdown_now(lines: list[str] | None = None) -> None:
    update_activity()
    write_shutdown_notice(lines)
    result = subprocess.run(["pkill", "-USR1", "-u", "ize", "-f", "/home/ize/ize-ribbon/app.py"], check=False)
    if result.returncode != 0:
        try:
            from display import show_message

            show_message(lines or shutdown_lines())
        except Exception:
            pass
    shutdown_after_notice()
