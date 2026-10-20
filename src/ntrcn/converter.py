"""Retyping text in another layout when a global shortcut is pressed."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from PySide6.QtCore import QTimer

from ntrcn.convert import (
    Fragment,
    Speller,
    next_case,
    next_layout,
    plan_retype,
    plan_typing,
    retyped_text,
    wrong_fragment,
)
from ntrcn.keymap import layout_chars
from ntrcn.keys import MODIFIERS, KeyBuffer, TypedKey
from ntrcn.layouts import KdeLayouts, Layout
from ntrcn.selection import read_primary_selection
from ntrcn.typer import Typer

logger = logging.getLogger(__name__)

# Selections longer than this are most likely not meant to be retyped key by key.
MAX_SELECTION = 2000
# How long to wait for the user to let go of Shift etc. before typing.
RELEASE_TIMEOUT_S = 2.0
RELEASE_POLL_MS = 10
# Key events seen right after we typed may be our own keys echoed back by a remapper
# such as keyd; they must not end up in the buffer.
ECHO_GRACE_S = 0.15
# Pause after switching the layout before typing, so the focused app surely has it.
LAYOUT_SETTLE_S = 0.05


class Converter:
    """Retypes the mistyped text or the selection in another layout."""

    def __init__(
        self,
        kde: KdeLayouts,
        typer: Typer,
        held_keys: Callable[[], set[int]] = set,
        on_layouts_changed: Callable[[list[Layout], int], None] = lambda _layouts, _current: None,
        on_convert: Callable[[], None] = lambda: None,
        speller: Callable[[str], Speller] = lambda _layout: None,
    ) -> None:
        """Wire the converter to Plasma layouts and the virtual keyboard.

        Args:
            kde: Plasma layouts.
            typer: Virtual keyboard to retype with.
            held_keys: Returns the physical keys held right now.
            on_layouts_changed: Called with the layouts and the active index on any change.
            on_convert: Called right before text is retyped (e.g. to start a sound).
            speller: Returns the word check for an XKB layout name, ``None`` if there is
                no dictionary; without dictionaries only the last word is converted.
        """
        self._kde = kde
        self._typer = typer
        self._held_keys = held_keys
        self._on_layouts_changed = on_layouts_changed
        self._on_convert = on_convert
        self._speller = speller
        # Buffer revision and word count of the last conversion, to repeat it.
        self._last_conversion: tuple[int, int] | None = None
        self.buffer = KeyBuffer()
        self._busy = False
        self._mute_until = 0.0
        self.layouts: list[Layout] = []
        self.current = 0
        kde.on_changed(self._on_layout_changed)
        kde.on_list_changed(self.reload_layouts)
        self.reload_layouts()

    def reload_layouts(self) -> None:
        """Re-read the configured layouts from Plasma."""
        self.layouts = self._kde.list()
        self.current = self._kde.current()
        logger.info("Layouts: %s, active %d", [lay.name for lay in self.layouts], self.current)
        self._on_layouts_changed(self.layouts, self.current)

    def _on_layout_changed(self, index: int) -> None:
        self.current = index
        self._on_layouts_changed(self.layouts, index)

    def on_key_press(self, code: int, held: set[int]) -> None:
        """Record a key press from a physical keyboard."""
        if self._busy or time.monotonic() < self._mute_until:
            return
        self.buffer.press(code, held, self.current)

    def fix_typed(self) -> None:
        """Retype the end of the typed text in the right layout (global shortcut)."""
        self._start(self._convert_typed)

    def fix_selection(self) -> None:
        """Retype the selected text in another layout (global shortcut)."""
        self._start(self._convert_selection)

    def change_case(self) -> None:
        """Cycle the case of the selected text (global shortcut)."""
        self._start(self._change_case)

    def _start(self, action: Callable[[], None]) -> None:
        if self._busy:
            return
        self.buffer.undo_reset()  # the shortcut's own key press reset the buffer
        self._run_when_released(action)

    def _run_when_released(self, action: Callable[[], None]) -> None:
        """Run ``action`` once no modifier is physically held, so they don't mix into typing."""
        self._busy = True
        deadline = time.monotonic() + RELEASE_TIMEOUT_S

        def poll() -> None:
            held = self._held_keys()
            if held & MODIFIERS and time.monotonic() < deadline:
                QTimer.singleShot(RELEASE_POLL_MS, poll)
                return
            try:
                if held & MODIFIERS:
                    logger.warning("Modifiers are still held, not converting")
                else:
                    action()
            except Exception:
                logger.exception("Conversion failed")
            finally:
                self._busy = False
                self._mute_until = time.monotonic() + ECHO_GRACE_S

        poll()

    def _switch_to(self, index: int) -> None:
        if index != self.current:
            self._kde.set(index)
            self.current = index
            time.sleep(LAYOUT_SETTLE_S)

    def _convert_typed(self) -> None:
        """Retype the end of what was typed in another layout.

        Pressing the shortcut again right away cycles the same text to the next layout.
        """
        if len(self.layouts) < 2:
            return
        if self._last_conversion and self._last_conversion[0] == self.buffer.revision:
            word_count = self._last_conversion[1]
            keys = self.buffer.tail(word_count)
            target = next_layout(keys[-1].layout, len(self.layouts))
        else:
            words = self.buffer.trailing_words()
            if not words:
                logger.info("Nothing to convert")
                return
            fragment, target = self._find_fragment(words)
            word_count = fragment.words
            keys = self.buffer.tail(word_count)
        self._retype(keys, target)
        self._last_conversion = (self.buffer.revision, word_count)

    def _find_fragment(self, words: list[list[TypedKey]]) -> tuple[Fragment, int]:
        """Pick the target layout whose dictionary confirms most words; the next one if none."""
        source = words[-1][0].layout
        typed = self._texts(words, source)
        count = len(self.layouts)
        targets = [(source + step) % count for step in range(1, count)]  # next one first
        best = (Fragment(1, 0), targets[0])
        for target in targets:
            fragment = wrong_fragment(
                list(zip(typed, self._texts(words, target), strict=True)),
                self._speller(self.layouts[source].name),
                self._speller(self.layouts[target].name),
            )
            if fragment.confirmed > best[0].confirmed:
                best = (fragment, target)
        return best

    def _texts(self, words: list[list[TypedKey]], layout: int) -> list[str]:
        """Return how each word reads in a layout."""
        chars = layout_chars(self.layouts[layout].name, self.layouts[layout].variant)
        return [retyped_text([key.stroke for key in word], chars) for word in words]

    def _retype(self, keys: list[TypedKey], target: int) -> None:
        logger.info("Retyping %d keys in %s", len(keys), self.layouts[target].name)
        self._on_convert()
        self._switch_to(target)
        self._typer.erase(len(keys))
        self._typer.type(key.stroke for key in keys)
        self.buffer.relabel_tail(len(keys), target)

    def _convert_selection(self) -> None:
        text = read_primary_selection()
        if not text or len(text) > MAX_SELECTION:
            logger.info("No suitable selection (%d chars)", len(text))
            return
        charmaps = [layout_chars(lay.name, lay.variant) for lay in self.layouts]
        spellers = [self._speller(lay.name) for lay in self.layouts]
        plan = plan_retype(text, charmaps, spellers)
        if plan is None:
            logger.info("Selection cannot be retyped in another layout")
            return
        # Never log the text itself: it may be anything the user typed.
        logger.info("Retyping %d selected chars in %s", len(text), self.layouts[plan.target].name)
        self._on_convert()
        self._switch_to(plan.target)
        self._typer.type(plan.strokes)
        self.buffer.reset()

    def _change_case(self) -> None:
        text = read_primary_selection()
        if not text or len(text) > MAX_SELECTION:
            logger.info("No suitable selection (%d chars)", len(text))
            return
        changed = next_case(text)
        if changed == text:
            logger.info("Selection has no letters")
            return
        # The current layout first; otherwise one in which the text can be typed.
        order = [self.current] + [i for i in range(len(self.layouts)) if i != self.current]
        for index in order:
            layout = self.layouts[index]
            strokes = plan_typing(changed, layout_chars(layout.name, layout.variant))
            if strokes is not None:
                break
        else:
            logger.info("Selection cannot be typed in any layout")
            return
        logger.info("Changing the case of %d selected chars", len(changed))
        self._on_convert()
        self._switch_to(index)
        self._typer.type(strokes)
        # Select the text again, so that the next press goes on with the cycle.
        self._typer.select_back(len(changed))
        self.buffer.reset()
