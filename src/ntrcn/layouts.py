"""Keyboard layouts of KDE Plasma: listing, switching and change notifications."""

from __future__ import annotations

import configparser
import logging
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import dbus

logger = logging.getLogger(__name__)

KXKBRC = Path.home() / ".config" / "kxkbrc"
_SERVICE, _PATH, _INTERFACE = "org.kde.keyboard", "/Layouts", "org.kde.KeyboardLayouts"


class Layout(NamedTuple):
    """An XKB layout configured in Plasma."""

    name: str
    variant: str
    label: str


def read_variants(kxkbrc: Path = KXKBRC) -> list[str]:
    """Return the per-layout XKB variants from kxkbrc (D-Bus does not report them)."""
    config = configparser.ConfigParser(interpolation=None)
    config.read(kxkbrc, encoding="utf-8")
    return config.get("Layout", "VariantList", fallback="").split(",")


class KdeLayouts:
    """Talks to Plasma's ``org.kde.KeyboardLayouts`` D-Bus service.

    Requires the GLib D-Bus main loop to be set as default before construction, so that
    signals are delivered by the running Qt (GLib-based) event loop.
    """

    def __init__(self, bus: dbus.Bus) -> None:
        """Connect to the layout service on the given session bus."""
        self._iface = dbus.Interface(bus.get_object(_SERVICE, _PATH), _INTERFACE)
        self._bus = bus

    def list(self) -> list[Layout]:
        """Return the configured layouts in Plasma's order."""
        variants = read_variants()
        layouts = []
        for i, (name, short_name, _long_name) in enumerate(self._iface.getLayoutsList()):
            variant = variants[i] if i < len(variants) else ""
            layouts.append(Layout(str(name), variant, str(short_name)))
        return layouts

    def current(self) -> int:
        """Return the index of the active layout."""
        return int(self._iface.getLayout())

    def set(self, index: int) -> None:
        """Activate the layout with the given index."""
        if not self._iface.setLayout(dbus.UInt32(index)):
            logger.warning("Plasma refused to switch to layout %d", index)

    def on_changed(self, callback: Callable[[int], None]) -> None:
        """Call ``callback(index)`` whenever the active layout changes."""
        self._subscribe("layoutChanged", lambda index: callback(int(index)))

    def on_list_changed(self, callback: Callable[[], None]) -> None:
        """Call ``callback()`` whenever the set of configured layouts changes."""
        self._subscribe("layoutListChanged", callback)

    def _subscribe(self, signal: str, handler: Callable[..., None]) -> None:
        self._bus.add_signal_receiver(handler, signal, _INTERFACE, _SERVICE, _PATH)
