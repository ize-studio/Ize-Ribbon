import time

from evdev_keys import usb_keyboard_event_paths
from bluetooth import connected_devices

_CACHE_TIME = 0.0
_CACHE_VALUE = False
_CACHE_SECONDS = 2.0


def keyboard_connected() -> bool:
    global _CACHE_TIME, _CACHE_VALUE
    now = time.time()
    if now - _CACHE_TIME < _CACHE_SECONDS:
        return _CACHE_VALUE
    connected = connected_devices()
    if connected:
        _CACHE_VALUE = True
    else:
        _CACHE_VALUE = bool(usb_keyboard_event_paths())
    _CACHE_TIME = now
    return _CACHE_VALUE
