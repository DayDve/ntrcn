"""System tray indicator showing the active layout."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

import dbus
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from ntrcn.appicon import app_icon
from ntrcn.config import Config
from ntrcn.flags import layout_icon
from ntrcn.layouts import Layout
from ntrcn.sni import MenuItem, StatusNotifierItem, tray_available

logger = logging.getLogger(__name__)

KEYBOARD_SETTINGS_COMMAND = ["systemsettings", "kcm_keyboard"]


def open_keyboard_settings() -> None:
    """Open Plasma's keyboard settings (layouts, switching keys)."""
    try:
        subprocess.Popen(KEYBOARD_SETTINGS_COMMAND)
    except OSError as err:
        logger.warning("Cannot open keyboard settings: %s", err)


class Tray:
    """Tray indicator like Plasma's keyboard layout widget, with ntrcn's menu."""

    def __init__(
        self, bus: dbus.Bus, on_select: Callable[[int], None], on_settings: Callable[[], None]
    ) -> None:
        """Create the indicator; call :meth:`update` to show it.

        Args:
            bus: Session bus with the GLib main loop.
            on_select: Called with a layout index to activate.
            on_settings: Called when the user asks for the settings window.
        """
        #: Settings of the indicator (see ``Config``), used on the next :meth:`update`.
        self.indicator = Config.tray_indicator
        self.text_theme = Config.text_theme
        self.app_icon_theme = Config.app_icon_theme
        self._bus = bus
        self._on_select = on_select
        self._on_settings = on_settings
        self._item = StatusNotifierItem(bus, "ntrcn", self._next_layout, self._step_layout)
        self._layouts: list[Layout] = []
        self._current = 0

    def _indicator_icon(self, layout: Layout) -> QIcon:
        if self.indicator == "app_icon":
            return app_icon(self.app_icon_theme)
        return layout_icon(layout.name, layout.label, self.indicator, self.text_theme)

    def _menu(self) -> list[MenuItem]:
        layouts = [
            MenuItem(
                layout.title,
                lambda i=index: self._on_select(i),  # type: ignore[misc]
                icon=layout_icon(layout.name, layout.label),
                checked=index == self._current,
            )
            for index, layout in enumerate(self._layouts)
        ]
        return [
            *layouts,
            MenuItem(),
            MenuItem("Настройки…", self._on_settings, icon_name="configure"),
            MenuItem("Параметры клавиатуры…", open_keyboard_settings, icon_name="input-keyboard"),
            MenuItem(),
            MenuItem("Выход", QApplication.quit, icon_name="application-exit"),
        ]

    def update(self, layouts: list[Layout], current: int) -> None:
        """Show the indicator of the layout at ``current``, or hide it if turned off."""
        self._layouts, self._current = layouts, current
        if self.indicator == "none" or not 0 <= current < len(layouts):
            self._item.hide()
            return
        layout = layouts[current]
        self._item.set_icon(self._indicator_icon(layout))
        self._item.set_tooltip("Раскладка клавиатуры", layout.title)
        self._item.set_menu(self._menu())
        if not self._item.visible and tray_available(self._bus):
            self._item.show()

    def _step_layout(self, step: int) -> None:
        if self._layouts:
            self._on_select((self._current + step) % len(self._layouts))

    def _next_layout(self) -> None:
        self._step_layout(1)
