import os
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


def ssh_key_path() -> str:
    return str(load_config().get("github_sync_ssh_key", "/home/ize/.ssh/ize_ribbon_github_ed25519"))


def public_key_text() -> str:
    path = ssh_key_path() + ".pub"
    try:
        return open(path, "r", encoding="utf-8").read().strip()
    except OSError:
        return ""


def generate_ssh_key() -> subprocess.CompletedProcess:
    key_path = ssh_key_path()
    os.makedirs(os.path.dirname(key_path), mode=0o700, exist_ok=True)
    if os.path.exists(key_path) and os.path.exists(key_path + ".pub"):
        return subprocess.CompletedProcess(["ssh-keygen"], 0, public_key_text(), "")
    return subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", "ize-ribbon github sync", "-f", key_path],
        text=True,
        capture_output=True,
        timeout=15,
    )


def github_repo_url() -> str:
    repo = load_config().get("github_sync_repo", "").strip()
    return f"git@github.com:{repo}.git" if repo else ""


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key_path()} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
    return env


def _git_command(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=docs_repo(),
        env=git_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def test_github_connection() -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-i", ssh_key_path(), "-o", "IdentitiesOnly=yes", "-o", "StrictHostKeyChecking=accept-new", "-T", "git@github.com"],
        text=True,
        capture_output=True,
        timeout=15,
    )


def configure_docs_repo() -> str:
    repo_url = github_repo_url()
    if not repo_url:
        return "GitHub repository is not set."
    docs_repo().mkdir(parents=True, exist_ok=True)
    messages: list[str] = []
    if not (docs_repo() / ".git").exists():
        result = subprocess.run(["git", "init", "-b", "main"], cwd=docs_repo(), text=True, capture_output=True, timeout=15)
        messages.append(result.stdout + result.stderr)
    for args in (
        ["config", "user.name", "Ize Ribbon"],
        ["config", "user.email", "ribbon@ize.local"],
        ["config", "core.sshCommand", f"ssh -i {ssh_key_path()} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"],
    ):
        result = _git_command(args, timeout=8)
        messages.append(result.stdout + result.stderr)
    _git_command(["remote", "remove", "origin"], timeout=8)
    result = _git_command(["remote", "add", "origin", repo_url], timeout=8)
    messages.append(result.stdout + result.stderr)
    status = _git_command(["status", "--porcelain"], timeout=8)
    if status.stdout.strip():
        _git_command(["add", "."], timeout=8)
        commit = _git_command(["commit", "-m", "Initial ribbon writing sync"], timeout=15)
        messages.append(commit.stdout + commit.stderr)
    push = _git_command(["push", "-u", "origin", "main"], timeout=30)
    messages.append(push.stdout + push.stderr)
    return "\n".join(part.strip() for part in messages if part.strip()) or "GitHub sync is configured."


def _commit_local_changes() -> bool:
    status = _git_command(["status", "--porcelain"], timeout=8)
    if status.returncode != 0 or not status.stdout.strip():
        return True
    _git_command(["add", "."], timeout=8)
    message = time.strftime("Sync ribbon writing %Y-%m-%d %H:%M:%S")
    commit = _git_command(["commit", "-m", message], timeout=15)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
        return False
    return True


def _ref_text(ref: str) -> str:
    result = _git_command(["rev-parse", "--verify", ref], timeout=8)
    return result.stdout.strip() if result.returncode == 0 else ""


def _ref_time(ref: str) -> int:
    result = _git_command(["show", "-s", "--format=%ct", ref], timeout=8)
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def _sync_once() -> None:
    if not client_wifi_connected():
        return
    if not (docs_repo() / ".git").exists():
        return
    if not github_repo_url():
        return
    if not _commit_local_changes():
        return
    fetch = _git_command(["fetch", "origin", "main"], timeout=30)
    if fetch.returncode != 0:
        _git_command(["push", "-u", "origin", "main"], timeout=30)
        return
    local_ref = _ref_text("HEAD")
    remote_ref = _ref_text("origin/main")
    if not remote_ref:
        _git_command(["push", "-u", "origin", "main"], timeout=30)
        return
    if local_ref == remote_ref:
        return
    local_time = _ref_time("HEAD")
    remote_time = _ref_time("origin/main")
    if remote_time >= local_time:
        _git_command(["reset", "--hard", "origin/main"], timeout=15)
    else:
        _git_command(["push", "-u", "origin", "main"], timeout=30)


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
