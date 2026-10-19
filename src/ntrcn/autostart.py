"""Starting ntrcn on login through an XDG autostart entry."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from ntrcn import APP_ID

DESKTOP_FILE = Path(__file__).with_name(f"{APP_ID}.desktop")
AUTOSTART_FILE = Path.home() / ".config" / "autostart" / f"{APP_ID}.desktop"
_SRC_DIR = Path(__file__).resolve().parent.parent


def _command() -> str:
    """Return how to start this very copy of ntrcn."""
    if shutil.which("ntrcn"):
        return "ntrcn"
    # Running from a source checkout without the launcher installed.
    return f'env PYTHONPATH="{_SRC_DIR}" {sys.executable} -m ntrcn'


def is_enabled() -> bool:
    """Tell whether ntrcn starts on login."""
    return AUTOSTART_FILE.is_file()


def set_enabled(enabled: bool) -> None:
    """Create or remove the autostart entry, the main part of the app's desktop file."""
    if not enabled:
        AUTOSTART_FILE.unlink(missing_ok=True)
        return
    entry = DESKTOP_FILE.read_text(encoding="utf-8").split("\n[Desktop Action")[0]
    entry = re.sub(r"(?m)^Actions=.*\n", "", entry)
    entry = re.sub(r"(?m)^Exec=.*$", lambda _: f"Exec={_command()}", entry).rstrip() + "\n"
    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(entry, encoding="utf-8")
