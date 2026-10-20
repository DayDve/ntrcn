"""User settings stored in ~/.config/ntrcn/config.json."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from ntrcn.i18n import N_

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "ntrcn"
CONFIG_FILE = CONFIG_DIR / "config.json"

#: Kinds of tray indicator and their titles in the settings window.
TRAY_INDICATORS = {
    "flag": N_("Flag"),
    "text": N_("Text"),
    "flag_text": N_("Flag and text"),
    "app_icon": N_("App icon"),
    "none": N_("No indicator"),
}
#: Sound after a conversion: none, the keyboard sound or a file of the user's choice.
SOUND_MODES = {"off": N_("Off"), "on": N_("On"), "custom": N_("Custom sound")}
#: Themes of a text indicator and of the app icon in the tray.
TEXT_THEMES = {"light": N_("Light"), "dark": N_("Dark")}
APP_ICON_THEMES = {"color": N_("Colour"), **TEXT_THEMES}


@dataclass
class Config:
    """All ntrcn settings with their defaults."""

    hotkey: str = "PAUSE"  # evdev key name without the KEY_ prefix
    sound: str = "off"  # one of SOUND_MODES
    sound_file: str = ""  # the user's own sound, for "custom"
    tray_indicator: str = "flag"  # one of TRAY_INDICATORS
    text_theme: str = "light"  # one of TEXT_THEMES
    app_icon_theme: str = "light"  # one of APP_ICON_THEMES


def load_config(path: Path = CONFIG_FILE) -> Config:
    """Read the settings, falling back to defaults for anything missing or invalid."""
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Config()
    except (OSError, ValueError) as err:
        logger.warning("Ignoring unreadable %s: %s", path, err)
        return Config()
    config = Config()
    if not isinstance(data, dict):
        return config
    for f in fields(Config):
        value = data.get(f.name)
        if isinstance(value, type(getattr(config, f.name))):
            setattr(config, f.name, value)
    if config.tray_indicator not in TRAY_INDICATORS:
        config.tray_indicator = Config.tray_indicator
    if config.sound not in SOUND_MODES:
        config.sound = Config.sound
    if config.text_theme not in TEXT_THEMES:
        config.text_theme = Config.text_theme
    if config.app_icon_theme not in APP_ICON_THEMES:
        config.app_icon_theme = Config.app_icon_theme
    return config


def save_config(config: Config, path: Path = CONFIG_FILE) -> None:
    """Write the settings."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, ensure_ascii=False), encoding="utf-8")
