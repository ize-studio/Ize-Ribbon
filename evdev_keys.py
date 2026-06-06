import os
import select
import struct
import time
from pathlib import Path


EVENT_FORMAT = "llHHI"
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)
EV_KEY = 0x01
KEY_RELEASE = 0
KEY_PRESS = 1
KEY_REPEAT = 2

KEY_MAP = {
    1: "esc",
    14: "backspace",
    28: "enter",
    103: "up",
    105: "left",
    106: "right",
    108: "down",
}


def keyboard_event_paths() -> list[Path]:
    return _keyboard_event_paths()


def usb_keyboard_event_paths() -> list[Path]:
    return _keyboard_event_paths(usb_only=True)


def _keyboard_event_paths(usb_only: bool = False) -> list[Path]:
    devices = Path("/proc/bus/input/devices")
    try:
        text = devices.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    paths: list[Path] = []
    for block in text.split("\n\n"):
        lower = block.lower()
        if "keyboard" not in lower and "kbd" not in lower:
            continue
        if usb_only and "usb" not in lower:
            continue
        for line in block.splitlines():
            if not line.startswith("H: Handlers="):
                continue
            for item in line.split("=")[1].split():
                if item.startswith("event"):
                    paths.append(Path("/dev/input") / item)
    return paths


class EvdevKeyReader:
    def __init__(self) -> None:
        self._fds: list[int] = []
        self._last_refresh = 0.0
        self.refresh()

    def refresh(self) -> None:
        self._last_refresh = time.time()
        self.close()
        for path in keyboard_event_paths():
            try:
                self._fds.append(os.open(path, os.O_RDONLY | os.O_NONBLOCK))
            except OSError:
                continue

    def close(self) -> None:
        for fd in self._fds:
            try:
                os.close(fd)
            except OSError:
                pass
        self._fds = []

    def read_key(self, timeout: float = 0.0) -> str | None:
        if not self._fds:
            if time.time() - self._last_refresh >= 2:
                self.refresh()
            return None
        readable, _, _ = select.select(self._fds, [], [], timeout)
        for fd in readable:
            while True:
                try:
                    data = os.read(fd, EVENT_SIZE)
                except BlockingIOError:
                    break
                except OSError:
                    self.refresh()
                    return None
                if len(data) != EVENT_SIZE:
                    break
                _, _, event_type, code, value = struct.unpack(EVENT_FORMAT, data)
                if event_type != EV_KEY or value not in (KEY_PRESS, KEY_REPEAT):
                    continue
                key = KEY_MAP.get(code)
                if key:
                    return key
        return None

    def drain(self, seconds: float = 0.05) -> None:
        while True:
            key = self.read_key(seconds)
            if key is None:
                return
            seconds = 0.0
