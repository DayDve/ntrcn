"""System tray icon showing the active layout."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable

from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ntrcn.appicon import app_icon
from ntrcn.config import Config
from ntrcn.flags import layout_icon
from ntrcn.layouts import Layout

logger = logging.getLogger(__name__)

KEYBOARD_SETTINGS_COMMAND = ["systemsettings", "kcm_keyboard"]


def open_keyboard_settings() -> None:
    """Open Plasma's keyboard settings (layouts, switching keys)."""
    try:
        subprocess.Popen(KEYBOARD_SETTINGS_COMMAND)
    except OSError as err:
        logger.warning("Cannot open keyboard settings: %s", err)


class Tray:
    """Tray indicator with a menu to pick a layout, open settings or quit."""

    def __init__(self, on_select: Callable[[int], None], on_settings: Callable[[], None]) -> None:
        """Create the icon; call :meth:`update` to fill it.

        Args:
            on_select: Called with a layout index when the user picks it in the menu.
            on_settings: Called when the user asks for the settings window.
        """
        #: Settings of the indicator (see ``Config``), used on the next :meth:`update`.
        self.indicator = Config.tray_indicator
        self.text_theme = Config.text_theme
        self.app_icon_theme = Config.app_icon_theme
        self._on_select = on_select
        self._on_settings = on_settings
        self._icon = QSystemTrayIcon()
        self._menu = QMenu()
        self._icon.setContextMenu(self._menu)
        self._icon.activated.connect(self._on_activated)
        self._layouts: list[Layout] = []
        self._current = 0

    def _indicator_icon(self, layout: Layout) -> QIcon:
        if self.indicator == "app_icon":
            return app_icon(self.app_icon_theme)
        return layout_icon(layout.name, layout.label, self.indicator, self.text_theme)

    def update(self, layouts: list[Layout], current: int) -> None:
        """Show ``layouts`` in the menu and the icon of the one at ``current``."""
        self._layouts, self._current = layouts, current
        self._menu.clear()
        group = QActionGroup(self._menu)
        for index, layout in enumerate(layouts):
            action = QAction(layout_icon(layout.name, layout.label), layout.label, self._menu)
            action.setCheckable(True)
            action.setChecked(index == current)
            action.triggered.connect(lambda _=False, i=index: self._on_select(i))
            group.addAction(action)
            self._menu.addAction(action)
        self._menu.addSeparator()
        self._menu.addAction(QIcon.fromTheme("configure"), "Настройки…", self._on_settings)
        self._menu.addAction(
            QIcon.fromTheme("input-keyboard"), "Параметры клавиатуры…", open_keyboard_settings
        )
        self._menu.addSeparator()
        self._menu.addAction(QIcon.fromTheme("application-exit"), "Выход", QApplication.quit)
        if 0 <= current < len(layouts):
            layout = layouts[current]
            self._icon.setIcon(self._indicator_icon(layout))
            self._icon.setToolTip(f"ntrcn: {layout.label}")
        self._icon.setVisible(self.indicator != "none" and QSystemTrayIcon.isSystemTrayAvailable())

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left click cycles to the next layout, like Plasma's own indicator.
        if reason == QSystemTrayIcon.ActivationReason.Trigger and self._layouts:
            self._on_select((self._current + 1) % len(self._layouts))
