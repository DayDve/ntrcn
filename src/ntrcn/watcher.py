"""Reads key presses and clicks from all input devices, without grabbing them."""

from __future__ import annotations

import logging

import evdev
from evdev import ecodes as e
from PySide6.QtCore import QObject, QSocketNotifier, QTimer, Signal

from ntrcn.typer import DEVICE_NAME

logger = logging.getLogger(__name__)

RESCAN_INTERVAL_MS = 2000
_CLICK_BUTTONS = frozenset([e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE, e.BTN_TOUCH])
# A touchpad touch this soon after a key press is a palm, not a tap; libinput ignores those
# too ("disable while typing"). Otherwise palms reset the word in the middle of typing.
PALM_GRACE_S = 0.5


def is_click(code: int, event_time: float, last_key_time: float) -> bool:
    """Tell whether a button press may have moved the text caret."""
    if code == e.BTN_TOUCH:
        return event_time - last_key_time >= PALM_GRACE_S
    return code in _CLICK_BUTTONS


def _is_relevant(device: evdev.InputDevice) -> bool:
    keys = set(device.capabilities().get(e.EV_KEY, []))
    is_keyboard = {e.KEY_A, e.KEY_SPACE} <= keys
    return device.name != DEVICE_NAME and (is_keyboard or bool(keys & _CLICK_BUTTONS))


class InputWatcher(QObject):
    """Reports key presses and clicks from every keyboard and pointer.

    Devices plugged in later are picked up by a periodic rescan. Events from the
    ntrcn virtual keyboard itself are never read.
    """

    #: A key was pressed or auto-repeated: its code and the set of other held keys.
    key_pressed = Signal(int, set)
    #: A mouse button or a touchpad tap (not a palm) may have moved the text caret.
    clicked = Signal()

    def __init__(self) -> None:
        """Start watching."""
        super().__init__()
        self._last_key_time = 0.0
        self._devices: dict[str, tuple[evdev.InputDevice, QSocketNotifier]] = {}
        self._held: dict[str, set[int]] = {}
        self._ignored: set[str] = set()
        self._rescan_timer = QTimer(self, interval=RESCAN_INTERVAL_MS)
        self._rescan_timer.timeout.connect(self.rescan)
        self._rescan_timer.start()
        self.rescan()

    def held_keys(self) -> set[int]:
        """Return keys currently held on any device."""
        return set().union(*self._held.values())

    def rescan(self) -> None:
        """Open devices that appeared since the last scan."""
        paths = set(evdev.list_devices())
        self._ignored &= paths
        for path in paths - self._devices.keys() - self._ignored:
            try:
                device = evdev.InputDevice(path)
            except OSError as err:
                logger.debug("Cannot open %s: %s", path, err)
                self._ignored.add(path)
                continue
            if not _is_relevant(device):
                device.close()
                self._ignored.add(path)
                continue
            notifier = QSocketNotifier(device.fd, QSocketNotifier.Type.Read, self)
            notifier.activated.connect(lambda *_, p=path: self._read(p))
            self._devices[path] = (device, notifier)
            self._held[path] = set()
            logger.info("Watching %s (%s)", device.name, path)

    def _drop(self, path: str) -> None:
        device, notifier = self._devices.pop(path)
        notifier.setEnabled(False)
        notifier.deleteLater()
        self._held.pop(path, None)
        try:
            device.close()
        except OSError:
            pass
        logger.info("Device %s is gone", path)

    def _read(self, path: str) -> None:
        device, _ = self._devices[path]
        try:
            events = list(device.read())
        except BlockingIOError:
            return
        except OSError:
            self._drop(path)
            return
        held = self._held[path]
        for event in events:
            if event.type != e.EV_KEY:
                continue
            if event.value == 0:
                held.discard(event.code)
                continue
            if event.value == 1:
                held.add(event.code)
            if event.code in _CLICK_BUTTONS:
                if event.value == 1 and is_click(
                    event.code, event.timestamp(), self._last_key_time
                ):
                    logger.debug("Click on %s: %s", device.name, e.BTN.get(event.code))
                    self.clicked.emit()
            else:
                self._last_key_time = event.timestamp()
                self.key_pressed.emit(event.code, self.held_keys() - {event.code})
