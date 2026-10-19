"""Loading C libraries through ctypes with declared function signatures."""

from __future__ import annotations

import ctypes
import ctypes.util
from typing import Any

#: Function name -> (return type, argument types).
Signatures = dict[str, tuple[Any, list[Any]]]


def load_library(name: str, fallback: str, signatures: Signatures) -> ctypes.CDLL:
    """Load ``lib<name>`` (or the ``fallback`` soname) and declare the given functions.

    Raises:
        OSError: If the library is not installed.
    """
    lib = ctypes.CDLL(ctypes.util.find_library(name) or fallback)
    for function, (restype, argtypes) in signatures.items():
        getattr(lib, function).restype = restype
        getattr(lib, function).argtypes = argtypes
    return lib
