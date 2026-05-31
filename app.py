import select
import sys
import termios
import tty
import time

from config_store import update_activity
from display import show
from documents import append_text, backspace, ensure_initial_document, new_document, read_text, write_text
from language import cycle_language
from menu import MenuState


ESCAPE_KEYS = {
    "\x1b[A": "up",
    "\x1b[B": "down",
    "\x1b[C": "right",
    "\x1b[D": "left",
}


def read_key() -> str | None:
    if not select.select([sys.stdin], [], [], 0.2)[0]:
        return None
    ch = sys.stdin.read(1)
    if ch == "\x1b":
        time.sleep(0.03)
        rest = ""
        while select.select([sys.stdin], [], [], 0)[0]:
            rest += sys.stdin.read(1)
        return ESCAPE_KEYS.get(ch + rest, "esc")
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


def main() -> None:
    ensure_initial_document()
    update_activity()
    menu = MenuState()
    show()

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        while True:
            key = read_key()
            if key is None:
                continue
            if menu.mode != "writing":
                menu.handle(key)
                show(menu.overlay_lines())
                continue
            if key == "esc":
                menu.open()
            elif key == "ctrl_space":
                cycle_language()
            elif key == "ctrl_n":
                new_document()
            elif key == "ctrl_s":
                write_text(read_text())
            elif key == "enter":
                append_text("\n")
            elif key == "backspace":
                backspace()
            elif key in ("up", "down", "left", "right"):
                pass
            elif len(key) == 1 and key.isprintable():
                append_text(key)
            update_activity()
            show(menu.overlay_lines() if menu.mode != "writing" else None)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


if __name__ == "__main__":
    main()
