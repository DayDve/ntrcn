"""Virtual keyboard that types keystrokes through /dev/uinput."""

from __future__ import annotations

import time
from collections.abc import Iterable
from typing import Any

from evdev import UInput
from evdev import ecodes as e

from ntrcn.keys import CHAR_KEYS, Keystroke

DEVICE_NAME = "ntrcn virtual keyboard"
# Own USB ids ("NT":"RC"). The evdev default 0001:0001 equals built-in AT keyboards, so
# remappers such as keyd that match by id would grab our device and re-emit its keys.
VENDOR_ID, PRODUCT_ID = 0x4E54, 0x5243
# Pause between events. Some toolkits (Electron, Telegram) drop keys sent faster.
KEY_DELAY = 0.003


class Typer:
    """Owns the uinput device. Create it once at startup: the compositor needs time to see it."""

    def __init__(self) -> None:
        """Register the virtual keyboard.

        Raises:
            PermissionError: If /dev/uinput is not writable by the user.
        """
        keys = CHAR_KEYS | {e.KEY_LEFTSHIFT, e.KEY_BACKSPACE, e.KEY_ENTER}
        # Any: older python3-evdev (Debian 13) has no type hints for UInput's methods.
        self._device: Any = UInput(
            {e.EV_KEY: sorted(keys)}, name=DEVICE_NAME, vendor=VENDOR_ID, product=PRODUCT_ID
        )

    def close(self) -> None:
        """Unregister the virtual keyboard."""
        self._device.close()

    def _key(self, code: int, value: int) -> None:
        self._device.write(e.EV_KEY, code, value)
        self._device.syn()
        time.sleep(KEY_DELAY)

    def tap(self, stroke: Keystroke) -> None:
        """Press and release one key, holding Shift around it if needed."""
        if stroke.shift:
            self._key(e.KEY_LEFTSHIFT, 1)
        self._key(stroke.code, 1)
        self._key(stroke.code, 0)
        if stroke.shift:
            self._key(e.KEY_LEFTSHIFT, 0)

    def type(self, strokes: Iterable[Keystroke]) -> None:
        """Tap the given keys in order."""
        for stroke in strokes:
            self.tap(stroke)

    def erase(self, count: int) -> None:
        """Press Backspace ``count`` times."""
        self.type([Keystroke(e.KEY_BACKSPACE)] * count)
