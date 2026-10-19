"""Reading the selected text from the Wayland primary selection."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

TIMEOUT_S = 1.0


def read_primary_selection() -> str:
    """Return the currently selected text, or an empty string if there is none.

    Uses ``wl-paste``, which reads through the data-control protocol and therefore
    works without ntrcn having keyboard focus.
    """
    try:
        result = subprocess.run(
            ["wl-paste", "--primary", "--no-newline", "--type", "text/plain;charset=utf-8"],
            capture_output=True,
            timeout=TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as err:
        logger.warning("Cannot read the primary selection: %s", err)
        return ""
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else ""
