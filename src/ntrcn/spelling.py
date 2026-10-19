"""Spell checking with the system hunspell dictionaries, chosen by the layout's language."""

from __future__ import annotations

import ctypes
import logging
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path

from PySide6.QtCore import QLocale

from ntrcn.convert import Speller
from ntrcn.native import load_library

logger = logging.getLogger(__name__)

XKB_REGISTRY = Path("/usr/share/X11/xkb/rules/evdev.xml")
#: Where dictionaries downloaded by the user go; searched first.
USER_DICTIONARY_DIR = Path.home() / ".local" / "share" / "hunspell"
DICTIONARY_DIRS = (
    USER_DICTIONARY_DIR,
    Path("/usr/share/hunspell"),
    Path("/usr/share/myspell/dicts"),
    Path("/usr/share/myspell"),
)


@cache
def _layout_languages() -> dict[str, str]:
    """Map XKB layout names to the ISO 639-2 code of their first language."""
    languages: dict[str, str] = {}
    try:
        root = ET.parse(XKB_REGISTRY).getroot()
    except (OSError, ET.ParseError) as err:
        logger.warning("Cannot read the XKB registry %s: %s", XKB_REGISTRY, err)
        return languages
    for layout in root.iter("layout"):
        item = layout.find("configItem")
        name = item.findtext("name") if item is not None else None
        language = item.findtext("languageList/iso639Id") if item is not None else None
        if name and language:
            languages[name] = language
    return languages


def layout_language(layout: str) -> str | None:
    """Return the two-letter language of an XKB layout, e.g. ``ua`` → ``uk``."""
    iso639_2 = _layout_languages().get(layout)
    if iso639_2 is None:
        return None
    language = QLocale.codeToLanguage(iso639_2, QLocale.LanguageCodeType.ISO639Part2)
    if language == QLocale.Language.AnyLanguage:
        return None
    return QLocale.languageToCode(language, QLocale.LanguageCodeType.ISO639Part1) or None


def locale_name(language: str) -> str:
    """Return ``uk_UA`` for ``uk``: the language with its main country."""
    name = QLocale(language).name()
    return name if len(name) == 5 else language


def find_dictionary(language: str, layout: str) -> Path | None:
    """Return the ``.dic`` file for a language, preferring the layout's country variant.

    For layout ``us`` and language ``en``, ``en_US`` is preferred over ``en_GB``.
    """
    preferred = [f"{language}_{layout.upper()}", f"{language}_{language.upper()}", language]
    for directory in DICTIONARY_DIRS:
        for name in preferred:
            path = directory / f"{name}.dic"
            if path.is_file() and path.with_suffix(".aff").is_file():
                return path
    for directory in DICTIONARY_DIRS:
        for path in sorted(directory.glob(f"{language}_*.dic")):
            if path.with_suffix(".aff").is_file():
                return path
    return None


@cache
def _lib() -> ctypes.CDLL:
    p, text = ctypes.c_void_p, ctypes.c_char_p
    return load_library(
        "hunspell-1.7",
        "libhunspell-1.7.so.0",
        {
            "Hunspell_create": (p, [text, text]),
            "Hunspell_spell": (ctypes.c_int, [p, text]),
            "Hunspell_get_dic_encoding": (text, [p]),
        },
    )


class Dictionary:
    """A loaded hunspell dictionary."""

    def __init__(self, dic: Path) -> None:
        """Load the dictionary from ``dic`` and the ``.aff`` file next to it."""
        lib = _lib()
        self.path = dic
        self._handle = lib.Hunspell_create(str(dic.with_suffix(".aff")).encode(), str(dic).encode())
        self._encoding = (lib.Hunspell_get_dic_encoding(self._handle) or b"UTF-8").decode()

    def knows(self, word: str) -> bool:
        """Tell whether ``word`` is spelled correctly."""
        try:
            encoded = word.encode(self._encoding)
        except (UnicodeEncodeError, LookupError):
            return False
        return bool(_lib().Hunspell_spell(self._handle, encoded))


@cache
def dictionary_for(layout: str) -> Dictionary | None:
    """Return the dictionary for an XKB layout, or ``None`` if none is installed."""
    language = layout_language(layout)
    path = find_dictionary(language, layout) if language else None
    if path is None:
        logger.info("No dictionary for layout %s (language %s)", layout, language)
        return None
    try:
        dictionary = Dictionary(path)
    except OSError as err:
        logger.warning("Cannot load hunspell: %s", err)
        return None
    logger.info("Dictionary for layout %s: %s", layout, path)
    return dictionary


def forget_dictionaries() -> None:
    """Drop loaded dictionaries, so newly installed or downloaded ones are picked up."""
    dictionary_for.cache_clear()


def speller_for(layout: str) -> Speller:
    """Return a word check for an XKB layout, or ``None`` without a dictionary."""
    dictionary = dictionary_for(layout)
    return dictionary.knows if dictionary else None
