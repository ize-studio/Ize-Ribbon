import subprocess
import time

from config_store import update_activity


def shutdown_now() -> None:
    update_activity()
    try:
        from display import show_message

        show_message("sleep...")
        time.sleep(2)
    except Exception:
        pass
    subprocess.run(["sudo", "shutdown", "-h", "now"], check=False)
