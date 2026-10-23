"""Global shortcuts registered with KDE (kglobalaccel) and set in System Settings."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from typing import Any, NamedTuple

import dbus
from PySide6.QtGui import QKeySequence

logger = logging.getLogger(__name__)

SERVICE = "org.kde.kglobalaccel"
COMPONENT = "ntrcn"
SHORTCUTS_SETTINGS_COMMAND = ["systemsettings", "kcm_keys"]
# setShortcutKeys flags: make the keys the default, or apply them unless the user has
# configured something else.
_IS_DEFAULT, _SET_PRESENT = 8, 2


class Shortcut(NamedTuple):
    """An action that can be bound to a global shortcut."""

    id: str
    title: str
    default: str  # QKeySequence text, e.g. "Shift+Pause"


def _keys(sequence: str) -> dbus.Array:
    """A key sequence as kglobalaccel expects it: a list of (four combined Qt keys)."""
    seq = QKeySequence(sequence)
    combined = [seq[i].toCombined() for i in range(seq.count())]  # type: ignore[index]
    combined += [0] * (4 - len(combined))
    return dbus.Array(
        [dbus.Struct([dbus.Array(combined, signature="i")], signature="ai")], signature="(ai)"
    )


def keys_text(keys: Any) -> str:
    """Human-readable text of kglobalaccel keys, e.g. "Shift+Pause"."""
    sequences = [QKeySequence(*[int(k) for k in seq[0] if k]) for seq in keys]
    return ", ".join(
        seq.toString(QKeySequence.SequenceFormat.NativeText)
        for seq in sequences
        if not seq.isEmpty()
    )


def open_shortcut_settings() -> None:
    """Open the shortcuts page of System Settings."""
    try:
        subprocess.Popen(SHORTCUTS_SETTINGS_COMMAND)
    except OSError as err:
        logger.warning("Cannot open shortcut settings: %s", err)


class GlobalShortcuts:
    """Registers the actions with kglobalaccel and reports when their shortcut is pressed."""

    def __init__(
        self, bus: dbus.Bus, shortcuts: list[Shortcut], on_pressed: Callable[[str], None]
    ) -> None:
        """Register ``shortcuts``; ``on_pressed`` gets the id of the action triggered."""
        self._shortcuts = shortcuts
        self._kga: Any = None
        try:
            self._kga = dbus.Interface(
                bus.get_object(SERVICE, "/kglobalaccel"), "org.kde.KGlobalAccel"
            )
            for shortcut in shortcuts:
                action = self._action(shortcut)
                self._kga.doRegister(action)
                self._kga.setShortcutKeys(action, _keys(shortcut.default), dbus.UInt32(_IS_DEFAULT))
                self._kga.setShortcutKeys(
                    action, _keys(shortcut.default), dbus.UInt32(_SET_PRESENT)
                )
            path = self._kga.getComponent(COMPONENT)
            self._remove_stale_actions(bus.get_object(SERVICE, path))
        except dbus.DBusException as err:
            logger.warning("Global shortcuts are not available: %s", err)
            self._kga = None
            return
        bus.add_signal_receiver(
            lambda _component, action, _time: on_pressed(str(action)),
            "globalShortcutPressed",
            "org.kde.kglobalaccel.Component",
            SERVICE,
            path,
        )

    @staticmethod
    def _action(shortcut: Shortcut) -> list[str]:
        return [COMPONENT, shortcut.id, "ntrcn", shortcut.title]

    def _remove_stale_actions(self, component: Any) -> None:
        """Forget actions of earlier versions so they do not linger in System Settings.

        ``shortcutNames`` lists inactive actions too, unlike ``allActionsForComponent``.
        """
        ours = {shortcut.id for shortcut in self._shortcuts}
        names = component.shortcutNames(dbus_interface="org.kde.kglobalaccel.Component")
        for name in names:
            if str(name) not in ours:
                self._kga.unregister(COMPONENT, str(name))

    def text(self, shortcut_id: str) -> str:
        """Current shortcut of an action as text, empty if none or unavailable."""
        shortcut = next((s for s in self._shortcuts if s.id == shortcut_id), None)
        if self._kga is None or shortcut is None:
            return ""
        try:
            return keys_text(self._kga.shortcutKeys(self._action(shortcut)))
        except dbus.DBusException:
            return ""
