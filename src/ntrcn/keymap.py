"""Character tables of keyboard layouts, computed with libxkbcommon."""

from __future__ import annotations

import ctypes
from functools import cache

from evdev import ecodes as e

from ntrcn.keys import CHAR_KEYS, Keystroke
from ntrcn.native import load_library

# Offset between evdev key codes and XKB key codes.
_EVDEV_OFFSET = 8
_KEY_UP, _KEY_DOWN = 0, 1


class _RuleNames(ctypes.Structure):
    _fields_ = [
        ("rules", ctypes.c_char_p),
        ("model", ctypes.c_char_p),
        ("layout", ctypes.c_char_p),
        ("variant", ctypes.c_char_p),
        ("options", ctypes.c_char_p),
    ]


_P, _INT, _U32 = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32


@cache
def _lib() -> ctypes.CDLL:
    return load_library(
        "xkbcommon",
        "libxkbcommon.so.0",
        {
            "xkb_context_new": (_P, [_INT]),
            "xkb_context_unref": (None, [_P]),
            "xkb_keymap_new_from_names": (_P, [_P, ctypes.POINTER(_RuleNames), _INT]),
            "xkb_keymap_unref": (None, [_P]),
            "xkb_state_new": (_P, [_P]),
            "xkb_state_unref": (None, [_P]),
            "xkb_state_update_key": (_INT, [_P, _U32, _INT]),
            "xkb_state_key_get_utf8": (_INT, [_P, _U32, ctypes.c_char_p, ctypes.c_size_t]),
        },
    )


def _key_char(lib: ctypes.CDLL, state: int, code: int) -> str:
    buf = ctypes.create_string_buffer(16)
    lib.xkb_state_key_get_utf8(state, code + _EVDEV_OFFSET, buf, len(buf))
    return buf.value.decode("utf-8", errors="replace")


@cache
def layout_chars(layout: str, variant: str = "") -> dict[Keystroke, str]:
    """Return the character produced by each keystroke in the given XKB layout.

    Raises:
        ValueError: If XKB cannot compile the layout.
    """
    lib = _lib()
    ctx = lib.xkb_context_new(0)
    names = _RuleNames(None, None, layout.encode(), variant.encode(), None)
    keymap = lib.xkb_keymap_new_from_names(ctx, ctypes.byref(names), 0)
    if not keymap:
        lib.xkb_context_unref(ctx)
        raise ValueError(f"XKB cannot compile layout {layout!r} variant {variant!r}")
    state = lib.xkb_state_new(keymap)
    chars: dict[Keystroke, str] = {}
    try:
        for shift in (False, True):
            if shift:
                lib.xkb_state_update_key(state, e.KEY_LEFTSHIFT + _EVDEV_OFFSET, _KEY_DOWN)
            for code in CHAR_KEYS:
                char = _key_char(lib, state, code)
                if len(char) == 1 and char.isprintable():
                    chars[Keystroke(code, shift)] = char
    finally:
        lib.xkb_state_unref(state)
        lib.xkb_keymap_unref(keymap)
        lib.xkb_context_unref(ctx)
    return chars
