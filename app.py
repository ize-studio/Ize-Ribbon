import select
import signal
import json
import sys
import termios
import threading
import tty
import time

from config_store import ROOT, update_activity
from bluetooth import reconnect_remembered_devices
from display import show, show_message
from documents import current_document, ensure_initial_document, new_document, read_text, write_text
from evdev_keys import EvdevKeyReader
from git_sync import request_git_sync, start_git_sync, stop_git_sync
from hangul_input import apply_hangul_key
from keyboard_status import keyboard_connected
from language import current_language, cycle_language
from menu import MenuState
from network_status import client_wifi_connected, setup_ap_active, startup_display_lines
from power import shutdown_after_notice


ESCAPE_KEYS = {
    "\x1b[A": "up",
    "\x1b[B": "down",
    "\x1b[C": "right",
    "\x1b[D": "left",
    "\x1bOA": "up",
    "\x1bOB": "down",
    "\x1bOC": "right",
    "\x1bOD": "left",
}

ESCAPE_FINAL_KEYS = {
    "A": "up",
    "B": "down",
    "C": "right",
    "D": "left",
}
_terminal_escape_keys: dict[str, str] | None = None

_render_event = threading.Event()
_render_lock = threading.Lock()
_display_lock = threading.Lock()
_render_overlay: list[str] | None = None
_render_text: str | None = None
_render_partial = False
_render_lightweight = False
_render_stop = False
_render_generation = 0
_render_request_generation = 0
_shutdown_notice = False
_SHUTDOWN_LINES = ["Powering off", "Power off", "Please wait"]
_SAVE_DEBOUNCE_SECONDS = 0.8
_save_event = threading.Event()
_save_lock = threading.Lock()
_save_dirty = False
_save_stop = False
_save_text = ""
_save_path = None
_save_request_time = 0.0


def render_worker() -> None:
    global _render_overlay, _render_text, _render_partial, _render_lightweight
    while True:
        _render_event.wait()
        _render_event.clear()
        if _render_stop:
            return
        with _render_lock:
            overlay = _render_overlay
            text = _render_text
            partial = _render_partial
            lightweight = _render_lightweight
            generation = _render_request_generation
            _render_overlay = None
            _render_text = None
            _render_partial = False
            _render_lightweight = False
        if generation != _render_generation:
            continue
        with _display_lock:
            if generation != _render_generation:
                continue
            show(overlay, partial=partial, text_override=text, lightweight=lightweight)


def request_render(
    overlay_lines: list[str] | None = None,
    partial: bool = False,
    text: str | None = None,
    lightweight: bool = False,
) -> None:
    global _render_overlay, _render_text, _render_partial, _render_lightweight
    global _render_request_generation
    with _render_lock:
        _render_overlay = overlay_lines
        _render_text = text
        _render_partial = partial
        _render_lightweight = lightweight
        _render_request_generation = _render_generation
    _render_event.set()


def sync_show(
    overlay_lines: list[str] | None = None,
    partial: bool = False,
    text: str | None = None,
    lightweight: bool = False,
) -> None:
    global _render_overlay, _render_text, _render_partial, _render_lightweight
    global _render_generation, _render_request_generation
    with _render_lock:
        _render_generation += 1
        _render_request_generation = _render_generation
        _render_overlay = None
        _render_text = None
        _render_partial = False
        _render_lightweight = False
        _render_event.clear()
    with _display_lock:
        show(overlay_lines, partial=partial, text_override=text, lightweight=lightweight)


def sync_message(message: str | list[str]) -> None:
    global _render_overlay, _render_text, _render_partial, _render_lightweight
    global _render_generation, _render_request_generation
    with _render_lock:
        _render_generation += 1
        _render_request_generation = _render_generation
        _render_overlay = None
        _render_text = None
        _render_partial = False
        _render_lightweight = False
        _render_event.clear()
    with _display_lock:
        show_message(message)


def request_shutdown_notice(signum, frame) -> None:
    global _shutdown_notice
    global _SHUTDOWN_LINES
    try:
        data = json.loads((ROOT / "shutdown_notice.json").read_text(encoding="utf-8"))
        if isinstance(data, list) and all(isinstance(item, str) for item in data):
            _SHUTDOWN_LINES = data[:4]
    except (OSError, ValueError):
        pass
    _shutdown_notice = True


def request_service_stop(signum, frame) -> None:
    raise SystemExit(0)


def terminal_escape_keys() -> dict[str, str]:
    global _terminal_escape_keys
    if _terminal_escape_keys is not None:
        return _terminal_escape_keys
    keys = dict(ESCAPE_KEYS)
    try:
        import curses

        curses.setupterm()
        for cap, key in (("kcuu1", "up"), ("kcud1", "down"), ("kcuf1", "right"), ("kcub1", "left")):
            value = curses.tigetstr(cap)
            if value:
                keys[value.decode(errors="ignore")] = key
    except Exception:
        pass
    _terminal_escape_keys = keys
    return keys


def drain_tty_pending(seconds: float = 0.08) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline and select.select([sys.stdin], [], [], 0)[0]:
        sys.stdin.read(1)


def save_worker() -> None:
    global _save_dirty
    while True:
        _save_event.wait()
        while True:
            with _save_lock:
                if _save_stop:
                    text = _save_text
                    path = _save_path
                    dirty = _save_dirty
                    _save_dirty = False
                    break
                delay = _SAVE_DEBOUNCE_SECONDS - (time.time() - _save_request_time)
            if delay <= 0:
                with _save_lock:
                    text = _save_text
                    path = _save_path
                    dirty = _save_dirty
                    _save_dirty = False
                    _save_event.clear()
                break
            time.sleep(min(delay, 0.1))
        if dirty and path is not None:
            write_text(text, path)
            request_git_sync()
        if _save_stop:
            return


def request_save(text: str) -> None:
    global _save_dirty, _save_text, _save_path, _save_request_time
    with _save_lock:
        _save_text = text
        _save_path = current_document()
        _save_dirty = True
        _save_request_time = time.time()
    _save_event.set()


def flush_save(text: str | None = None) -> None:
    global _save_dirty, _save_text, _save_path
    with _save_lock:
        if text is not None:
            _save_text = text
            _save_path = current_document()
            _save_dirty = True
        save_text = _save_text
        save_path = _save_path
        dirty = _save_dirty
        _save_dirty = False
        _save_event.clear()
    if dirty and save_path is not None:
        write_text(save_text, save_path)
        request_git_sync()


def read_key() -> str | None:
    if not select.select([sys.stdin], [], [], 0.2)[0]:
        return None
    ch = sys.stdin.read(1)
    if ch == "[":
        if select.select([sys.stdin], [], [], 0.03)[0]:
            suffix = sys.stdin.read(1)
            if suffix in ESCAPE_FINAL_KEYS:
                return None
            return suffix
        return ch
    if ch == "O":
        if select.select([sys.stdin], [], [], 0.03)[0]:
            suffix = sys.stdin.read(1)
            if suffix in ESCAPE_FINAL_KEYS:
                return None
            return suffix
        return ch
    if ch == "\x1b":
        rest = ""
        deadline = time.time() + 0.35
        escape_keys = terminal_escape_keys()
        while time.time() < deadline:
            if not select.select([sys.stdin], [], [], 0.02)[0]:
                continue
            rest += sys.stdin.read(1)
            if ch + rest in escape_keys:
                return escape_keys[ch + rest]
            if rest[0] in ("[", "O") and rest[-1] in ESCAPE_FINAL_KEYS:
                return ESCAPE_FINAL_KEYS[rest[-1]]
            if rest[0] not in ("[", "O"):
                return "esc"
        if rest:
            return None
        return "esc"
    if ch in ("\r", "\n"):
        return "enter"
    if ch in ("\x7f", "\b"):
        return "backspace"
    if ch == "\x00":
        return "ctrl_space"
    if ch == "\x1f":
        return "ctrl_space"
    if ch == "\x0e":
        return "ctrl_n"
    if ch == "\x13":
        return "ctrl_s"
    return ch


def read_text_key() -> str | None:
    return read_key()


def wait_for_startup_ready() -> bool:
    last_lines: list[str] | None = None
    last_refresh = 0.0
    last_reconnect = 0.0
    while True:
        if _shutdown_notice:
            sync_message(_SHUTDOWN_LINES)
            time.sleep(2)
            return False
        update_activity()
        keyboard_ready = keyboard_connected()
        wifi_ready = client_wifi_connected()
        if keyboard_ready:
            break
        now = time.time()
        if (wifi_ready or setup_ap_active()) and now - last_reconnect >= 15:
            reconnect_remembered_devices()
            last_reconnect = now
            keyboard_ready = keyboard_connected()
            if keyboard_ready:
                break
        lines = startup_display_lines(keyboard_ready, wifi_ready)
        if lines != last_lines or now - last_refresh >= 60:
            sync_show(lines)
            last_lines = lines
            last_refresh = now
        time.sleep(2)
    sync_show(startup_display_lines(True, wifi_ready))
    time.sleep(1)
    return True


def main() -> None:
    global _render_stop, _save_stop, _shutdown_notice, _SHUTDOWN_LINES
    signal.signal(signal.SIGUSR1, request_shutdown_notice)
    signal.signal(signal.SIGTERM, request_service_stop)
    ensure_initial_document()
    update_activity()
    menu = MenuState()
    if not wait_for_startup_ready():
        return
    text_cache = read_text()
    sync_show()
    render_thread = threading.Thread(target=render_worker, daemon=True)
    render_thread.start()
    save_thread = threading.Thread(target=save_worker, daemon=True)
    save_thread.start()
    start_git_sync()
    evdev = EvdevKeyReader()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        while True:
            if _shutdown_notice:
                sync_message(_SHUTDOWN_LINES)
                time.sleep(2)
                return
            key = evdev.read_key(0.05)
            if key is not None:
                drain_tty_pending(0.25)
            elif menu.mode == "writing":
                key = read_text_key()
            elif not evdev.has_devices():
                key = read_key()
            if key is None:
                continue
            immediate_render = True
            if menu.mode != "writing":
                menu.handle(key)
                if menu.mode == "newdoc":
                    flush_save(text_cache)
                    new_document()
                    text_cache = read_text()
                    menu.close()
                    sync_show(text=text_cache)
                    continue
                if menu.mode == "poweroff":
                    flush_save(text_cache)
                    _SHUTDOWN_LINES = ["Powering off", "Power off", "Menu"]
                    sync_message(_SHUTDOWN_LINES)
                    shutdown_after_notice()
                    return
                if menu.mode == "writing":
                    sync_show(text=text_cache)
                else:
                    sync_show(menu.overlay_lines())
                continue
            if key == "esc":
                menu.open()
                drain_tty_pending(0.25)
                evdev.drain(0.2)
            elif key == "ctrl_space":
                cycle_language()
            elif key == "ctrl_n":
                flush_save(text_cache)
                new_document()
                text_cache = read_text()
            elif key == "ctrl_s":
                flush_save(text_cache)
            elif key == "enter":
                text_cache += "\n"
                request_save(text_cache)
                immediate_render = False
            elif key == "backspace":
                if text_cache:
                    text_cache = text_cache[:-1]
                    request_save(text_cache)
                immediate_render = False
            elif key in ("up", "down", "left", "right"):
                pass
            elif len(key) == 1 and key.isprintable():
                if current_language() == "KO":
                    text_cache = apply_hangul_key(text_cache, key)
                else:
                    text_cache += key
                request_save(text_cache)
                immediate_render = False
            update_activity()
            if immediate_render:
                if menu.mode != "writing":
                    sync_show(menu.overlay_lines())
                else:
                    request_render(text=text_cache)
            else:
                request_render(partial=True, text=text_cache, lightweight=True)
    finally:
        _render_stop = True
        _render_event.set()
        with _save_lock:
            _save_stop = True
        _save_event.set()
        flush_save(text_cache if "text_cache" in locals() else None)
        stop_git_sync()
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


if __name__ == "__main__":
    main()
