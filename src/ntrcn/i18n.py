"""Translations of the user interface (gettext, domain "ntrcn")."""

from __future__ import annotations

import gettext
from pathlib import Path

LOCALE_DIR = Path(__file__).with_name("locale")
_translation = gettext.translation("ntrcn", LOCALE_DIR, fallback=True)


def _(message: str) -> str:
    """Translate a user interface string into the user's language."""
    return _translation.gettext(message)


def N_(message: str) -> str:  # noqa: N802 - the usual gettext name
    """Mark a string for translation where it is defined; ``_()`` translates it when shown."""
    return message
