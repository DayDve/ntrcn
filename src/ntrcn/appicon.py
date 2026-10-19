"""The ntrcn icon: in colour, and light or dark for the tray."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

from ntrcn import APP_ID

ICONS_DIR = Path(__file__).with_name("icons")
APP_ICON = ICONS_DIR / f"{APP_ID}.svg"
#: Icon file per theme (see ``config.APP_ICON_THEMES``).
THEMED_ICONS = {
    "color": APP_ICON,
    "light": ICONS_DIR / f"{APP_ID}-light.svg",
    "dark": ICONS_DIR / f"{APP_ID}-dark.svg",
}


def app_icon(theme: str = "color") -> QIcon:
    """Return the application icon in the given theme."""
    return QIcon(str(THEMED_ICONS.get(theme, APP_ICON)))
