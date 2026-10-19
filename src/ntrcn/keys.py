"""Keystroke model and the buffer of recently typed keys."""

from __future__ import annotations

import logging
from typing import NamedTuple

from evdev import ecodes as e

logger = logging.getLogger(__name__)

# Keys that produce a character and whose meaning depends on the active layout.
CHAR_KEYS: frozenset[int] = frozenset(
    [
        *range(e.KEY_1, e.KEY_EQUAL + 1),  # 1..0 - =
        *range(e.KEY_Q, e.KEY_RIGHTBRACE + 1),  # q..p [ ]
        *range(e.KEY_A, e.KEY_GRAVE + 1),  # a..l ; ' `
        *range(e.KEY_BACKSLASH, e.KEY_SLASH + 1),  # \ z..m , . /
        e.KEY_102ND,
        e.KEY_SPACE,
    ]
)

SHIFT_KEYS = frozenset([e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT])
# Any of these held while typing a key means a shortcut, not text.
COMMAND_MODIFIERS = frozenset(
    [
        e.KEY_LEFTCTRL,
        e.KEY_RIGHTCTRL,
        e.KEY_LEFTALT,
        e.KEY_RIGHTALT,
        e.KEY_LEFTMETA,
        e.KEY_RIGHTMETA,
    ]
)
MODIFIERS = SHIFT_KEYS | COMMAND_MODIFIERS

# Keys that do not move the caret or change text, so they keep the buffer intact.
NEUTRAL_KEYS = frozenset([e.KEY_CAPSLOCK, e.KEY_NUMLOCK, e.KEY_SCROLLLOCK]) | MODIFIERS

# Upper bound so the buffer cannot grow forever while typing a long text without breaks.
MAX_BUFFER = 256


class Keystroke(NamedTuple):
    """A physical key press, optionally with Shift held."""

    code: int
    shift: bool = False


class TypedKey(NamedTuple):
    """A keystroke together with the layout index that was active when it was typed."""

    stroke: Keystroke
    layout: int


def _is_space(key: TypedKey) -> bool:
    return bool(key.stroke.code == e.KEY_SPACE)


class KeyBuffer:
    """Remembers keys typed since the caret last moved, to retype the end of them."""

    def __init__(self) -> None:
        """Create an empty buffer."""
        self._keys: list[TypedKey] = []
        #: Grows with every change made by typing, so callers can tell nothing was typed.
        self.revision = 0

    def __len__(self) -> int:
        """Return the number of buffered keys."""
        return len(self._keys)

    def reset(self) -> None:
        """Forget everything typed so far."""
        if self._keys:
            logger.debug("Buffer reset, %d keys dropped", len(self._keys))
        self._keys.clear()
        self.revision += 1

    def press(self, code: int, held: set[int], layout: int) -> None:
        """Update the buffer for a key press.

        Args:
            code: evdev key code that was pressed.
            held: evdev codes of keys held at the moment of the press.
            layout: Index of the active keyboard layout.
        """
        if code in NEUTRAL_KEYS:
            return
        self.revision += 1
        if code == e.KEY_BACKSPACE and not held & COMMAND_MODIFIERS:
            if self._keys:
                self._keys.pop()
            return
        if code not in CHAR_KEYS or held & COMMAND_MODIFIERS:
            self.reset()
            return
        self._keys.append(TypedKey(Keystroke(code, bool(held & SHIFT_KEYS)), layout))
        del self._keys[:-MAX_BUFFER]

    def trailing_words(self) -> list[list[TypedKey]]:
        """Return the words at the end that were typed in one layout, oldest first.

        Spaces separate words and are left out; a key typed in another layout than the
        last one ends the run.
        """
        letters = [key for key in self._keys if not _is_space(key)]
        if not letters:
            return []
        layout = letters[-1].layout
        words: list[list[TypedKey]] = [[]]
        for key in reversed(self._keys):
            if _is_space(key):
                if words[-1]:
                    words.append([])
            elif key.layout == layout:
                words[-1].insert(0, key)
            else:
                break
        return [word for word in reversed(words) if word]

    def tail(self, words: int) -> list[TypedKey]:
        """Return the keys from the start of the ``words``-th word from the end.

        Spaces between those words and after the last one are included.
        """
        start = len(self._keys)
        for _ in range(words):
            while start > 0 and _is_space(self._keys[start - 1]):
                start -= 1
            while start > 0 and not _is_space(self._keys[start - 1]):
                start -= 1
        return self._keys[start:]

    def relabel_tail(self, count: int, layout: int) -> None:
        """Mark the last ``count`` keys as typed in ``layout`` after they were retyped."""
        start = len(self._keys) - count
        for i in range(start, len(self._keys)):
            self._keys[i] = self._keys[i]._replace(layout=layout)


def key_code(name: str) -> int | None:
    """Return the evdev code of a key named like ``PAUSE`` or ``F13``, or ``None``."""
    code = e.ecodes.get(f"KEY_{name.upper()}")
    return code if isinstance(code, int) else None


def key_name(code: int) -> str:
    """Return the name of an evdev key code without the ``KEY_`` prefix."""
    name = e.KEY.get(code, str(code))
    if isinstance(name, list):  # aliases, e.g. KEY_MUTE / KEY_MIN_INTERESTING
        name = name[0]
    return str(name).removeprefix("KEY_")
