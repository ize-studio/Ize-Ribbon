from pathlib import Path


KEYBOARD_HINTS = ("keyboard", "kbd")


def keyboard_connected() -> bool:
    by_id = Path("/dev/input/by-id")
    if not by_id.exists():
        return False
    try:
        names = " ".join(p.name.lower() for p in by_id.iterdir())
    except OSError:
        return False
    return any(hint in names for hint in KEYBOARD_HINTS)
