"""Deciding what to retype in which layout. Pure functions, no I/O."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from itertools import permutations
from typing import NamedTuple

from evdev import ecodes as e

from ntrcn.keys import Keystroke

# Typed for a line break: Shift+Enter inserts a newline in chats instead of sending the message.
NEWLINE = Keystroke(e.KEY_ENTER, shift=True)

LayoutChars = dict[Keystroke, str]
#: Tells whether a word exists in a language; ``None`` when there is no dictionary.
Speller = Callable[[str], bool] | None

_EDGE_PUNCTUATION = re.compile(r"^\W+|\W+$")


class Retype(NamedTuple):
    """Keys to press, and the layouts the text was typed in and must be retyped in."""

    source: int
    target: int
    strokes: list[Keystroke]


class Fragment(NamedTuple):
    """The trailing words to retype and how many of them the dictionaries confirmed."""

    words: int
    confirmed: int


def next_layout(layout: int, count: int) -> int:
    """Return the layout index following ``layout`` in a list of ``count`` layouts."""
    return (layout + 1) % count


def retyped_text(strokes: Sequence[Keystroke], chars: LayoutChars) -> str:
    """Return the text that ``strokes`` produce in a layout."""
    return "".join("\n" if s == NEWLINE else chars.get(s, "?") for s in strokes)


# --- Dictionaries ------------------------------------------------------------------------


def _known(word: str, speller: Speller) -> bool | None:
    """Look ``word`` up without surrounding punctuation; ``None`` if that says nothing."""
    core = _EDGE_PUNCTUATION.sub("", word)
    if speller is None or not any(char.isalpha() for char in core):
        return None
    return speller(core)


def _is_wrong(typed: str, retyped: str, source: Speller, target: Speller) -> bool:
    """The source language does not know the word, the target one knows its retyped form."""
    return not _known(typed, source) and bool(_known(retyped, target))


def _is_right(typed: str, retyped: str, source: Speller, target: Speller) -> bool:
    """The source language knows the word, the target one does not know its retyped form."""
    return bool(_known(typed, source)) and not _known(retyped, target)


def wrong_fragment(words: Sequence[tuple[str, str]], source: Speller, target: Speller) -> Fragment:
    """Find where text typed in the wrong layout starts, judging by the dictionaries.

    Going back from the end, the fragment stops before the first right word; leading
    words that are not clearly wrong (numbers, names, unknown terms) are left out. The
    last word is always included, since the user asked to convert.

    Args:
        words: Each word as typed and as it reads in the target layout, oldest first.
        source: Dictionary of the layout the words were typed in.
        target: Dictionary of the layout they would be retyped in.
    """
    words_back = 0
    confirmed = 0
    for index, (typed, retyped) in enumerate(reversed(words)):
        if _is_right(typed, retyped, source, target):
            break
        if _is_wrong(typed, retyped, source, target):
            words_back = index + 1
            confirmed += 1
    return Fragment(max(words_back, 1), confirmed)


# --- Selection ---------------------------------------------------------------------------


def _reverse(chars: LayoutChars) -> dict[str, Keystroke]:
    reverse: dict[str, Keystroke] = {}
    # Unshifted strokes first, so a character reachable both ways is typed without Shift.
    for stroke in sorted(chars, key=lambda s: s.shift):
        reverse.setdefault(chars[stroke], stroke)
    return reverse


def detect_source(text: str, layouts: Sequence[LayoutChars]) -> int:
    """Guess which layout ``text`` was typed in: the one covering most of its characters."""
    alphabets = [set(chars.values()) for chars in layouts]
    coverage = [sum(char in alphabet for char in text) for alphabet in alphabets]
    return coverage.index(max(coverage))


def _strokes(text: str, source: LayoutChars, target: LayoutChars) -> list[Keystroke] | None:
    """Map each character back to its key in ``source``; keep characters only in ``target``."""
    from_source, from_target = _reverse(source), _reverse(target)
    strokes: list[Keystroke] = []
    for char in text:
        if char == "\n":
            strokes.append(NEWLINE)
        elif char in from_source:
            strokes.append(from_source[char])
        elif char in from_target:
            strokes.append(from_target[char])
        else:
            return None
    return strokes


def plan_retype(
    text: str, layouts: Sequence[LayoutChars], spellers: Sequence[Speller] = ()
) -> Retype | None:
    """Plan the keystrokes that retype ``text`` as if it had been typed in another layout.

    By default the source is the layout covering most characters and the target the next
    one. With dictionaries (one per layout), the pair of layouts under which most words
    turn from unknown into known wins instead.

    Returns:
        The plan, or ``None`` if fewer than two layouts are given or the text cannot be
        typed at all.
    """
    if len(layouts) < 2 or not text:
        return None
    source = detect_source(text, layouts)
    candidates = [(source, next_layout(source, len(layouts)))]
    if spellers:
        candidates += permutations(range(len(layouts)), 2)
    best: Retype | None = None
    best_score = 0
    for source, target in candidates:
        strokes = _strokes(text, layouts[source], layouts[target])
        if strokes is None:
            continue
        score = 0
        if spellers:
            pairs = zip(text.split(), retyped_text(strokes, layouts[target]).split(), strict=False)
            score = sum(_is_wrong(*pair, spellers[source], spellers[target]) for pair in pairs)
        if best is None or score > best_score:
            best, best_score = Retype(source, target, strokes), score
    return best
