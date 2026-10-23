"""Starting ntrcn on login through an XDG autostart entry."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

from ntrcn import APP_ID

AUTOSTART_FILE = Path.home() / ".config" / "autostart" / f"{APP_ID}.desktop"
_SRC_DIR = Path(__file__).resolve().parent.parent


def _command() -> str:
    """Return how to start this very copy of ntrcn."""
    if shutil.which("ntrcn"):
        return "ntrcn"
    # Running from a source checkout without the launcher installed.
    return f'env PYTHONPATH="{_SRC_DIR}" {sys.executable} -m ntrcn'


def is_enabled() -> bool:
    """Tell whether ntrcn starts on login.

    An entry with ``Hidden=true`` is one switched off in the Plasma autostart settings.
    """
    try:
        entry = AUTOSTART_FILE.read_text(encoding="utf-8")
    except OSError:
        return False
    return not re.search(r"(?m)^Hidden\s*=\s*true\s*$", entry)


def set_enabled(enabled: bool) -> None:
    """Create or remove the autostart entry."""
    if not enabled:
        AUTOSTART_FILE.unlink(missing_ok=True)
        return
    entry = f"[Desktop Entry]\nType=Application\nName=ntrcn\nExec={_command()}\nIcon={APP_ID}\n"
    AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(entry, encoding="utf-8")
