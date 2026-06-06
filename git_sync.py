import subprocess
import threading
import time

from config_store import ROOT, load_config
from network_status import client_wifi_connected


_SYNC_EVENT = threading.Event()
_STOP_EVENT = threading.Event()
_LOCK = threading.Lock()
_THREAD: threading.Thread | None = None
_LAST_REQUEST = 0.0


def docs_repo():
    return ROOT / "docs"


def _git_command(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    config = load_config()
    env = None
    ssh_key = config.get("github_sync_ssh_key")
    if ssh_key:
        env = {
            "GIT_SSH_COMMAND": f"ssh -i {ssh_key} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
        }
    return subprocess.run(
        ["git", *args],
        cwd=docs_repo(),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def _sync_once() -> None:
    if not client_wifi_connected():
        return
    if not (docs_repo() / ".git").exists():
        return
    status = _git_command(["status", "--porcelain"], timeout=8)
    if status.returncode != 0 or not status.stdout.strip():
        return
    _git_command(["add", "."], timeout=8)
    message = time.strftime("Sync ribbon writing %Y-%m-%d %H:%M:%S")
    commit = _git_command(["commit", "-m", message], timeout=15)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
        return
    _git_command(["push"], timeout=30)


def _worker() -> None:
    while not _STOP_EVENT.is_set():
        _SYNC_EVENT.wait(30)
        _SYNC_EVENT.clear()
        if _STOP_EVENT.is_set():
            return
        while True:
            with _LOCK:
                delay = 5 - (time.time() - _LAST_REQUEST)
            if delay <= 0:
                break
            if _STOP_EVENT.wait(min(delay, 1)):
                return
        try:
            _sync_once()
        except Exception:
            pass


def start_git_sync() -> None:
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return
    _THREAD = threading.Thread(target=_worker, daemon=True)
    _THREAD.start()


def request_git_sync() -> None:
    global _LAST_REQUEST
    with _LOCK:
        _LAST_REQUEST = time.time()
    _SYNC_EVENT.set()


def stop_git_sync() -> None:
    _STOP_EVENT.set()
    _SYNC_EVENT.set()
