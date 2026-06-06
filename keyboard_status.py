import time

from evdev_keys import keyboard_event_paths

_CACHE_TIME = 0.0
_CACHE_VALUE = False


def keyboard_connected() -> bool:
    global _CACHE_TIME, _CACHE_VALUE
    now = time.time()
    if now - _CACHE_TIME < 5:
        return _CACHE_VALUE
    _CACHE_VALUE = bool(keyboard_event_paths())
    _CACHE_TIME = now
    return _CACHE_VALUE
