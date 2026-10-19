"""Live end-to-end check against a running ntrcn (see ``make e2e``).

Opens a line edit and, only while it has keyboard focus, types into it through a separate
fake "physical" uinput keyboard: a word, the hotkey, the hotkey again, then a selection
and Shift+hotkey. Expected texts are computed from the first two Plasma layouts, whatever
they are. With us + ru layouts and their dictionaries, whole phrases are checked too.
Prints OK/FAIL per check; exits non-zero on failure or lost focus.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from evdev import UInput
from evdev import ecodes as e
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLineEdit

from ntrcn.convert import retyped_text
from ntrcn.keymap import layout_chars
from ntrcn.keys import Keystroke
from ntrcn.layouts import KdeLayouts
from ntrcn.spelling import speller_for

STEP_DELAY_MS = 700
KEY_DELAY_S = 0.01

DBusGMainLoop(set_as_default=True)
app = QApplication(sys.argv)
kde = KdeLayouts(dbus.SessionBus())
layouts = kde.list()[:2]
if len(layouts) < 2:
    sys.exit("e2e needs at least two Plasma layouts")
first, second = (layout_chars(lay.name, lay.variant) for lay in layouts)

edit = QLineEdit()
edit.setWindowTitle("ntrcn e2e")
edit.resize(500, 60)
edit.show()
edit.activateWindow()
keyboard = UInput({e.EV_KEY: list(range(1, 120))}, name="e2e test keyboard")
results: list[tuple[str, object, object]] = []


def strokes(latin: str) -> list[Keystroke]:
    """Keys that type ``latin`` (letters and spaces) on a QWERTY keyboard."""
    return [
        Keystroke(e.KEY_SPACE if char == " " else e.ecodes[f"KEY_{char.upper()}"], char.isupper())
        for char in latin
    ]


def key(code: int, value: int) -> None:
    keyboard.write(e.EV_KEY, code, value)
    keyboard.syn()
    time.sleep(KEY_DELAY_S)


def tap(*strokes: Keystroke) -> None:
    if not edit.isActiveWindow():
        print("FOCUS LOST, abort")
        app.exit(3)
        raise SystemExit
    for stroke in strokes:
        if stroke.shift:
            key(e.KEY_LEFTSHIFT, 1)
        key(stroke.code, 1)
        key(stroke.code, 0)
        if stroke.shift:
            key(e.KEY_LEFTSHIFT, 0)


def expect(name: str, want: object, got: Callable[[], object] = edit.text) -> Callable[[], None]:
    return lambda: results.append((name, got(), want))


def start_over() -> None:
    """Empty the field; Home also makes ntrcn forget what was typed."""
    edit.clear()
    tap(Keystroke(e.KEY_HOME))
    kde.set(0)


typed = strokes("Ghbdtn ")
steps: list[Callable[[], None]] = [
    lambda: kde.set(0),
    lambda: tap(*typed),
    lambda: tap(Keystroke(e.KEY_PAUSE)),
    expect("last word", retyped_text(typed, second)),
    lambda: tap(Keystroke(e.KEY_PAUSE)),
    expect("hotkey again", retyped_text(typed, first)),
    lambda: tap(*strokes("vbh")),
    lambda: tap(Keystroke(e.KEY_HOME, True)),  # select everything
    lambda: tap(Keystroke(e.KEY_PAUSE, True)),
    expect("selection", retyped_text(strokes("Ghbdtn vbh"), second)),
    expect("layout", 1, kde.current),
]
if [lay.name for lay in layouts] == ["us", "ru"] and all(map(speller_for, ("us", "ru"))):
    steps += [
        start_over,
        lambda: tap(*strokes("ghbdtn vbh"), Keystroke(e.KEY_PAUSE)),
        expect("phrase", "привет мир"),
        start_over,
        lambda: tap(*strokes("hello ghbdtn"), Keystroke(e.KEY_PAUSE)),
        expect("phrase after a right word", "hello привет"),
    ]
else:
    print("Phrase checks skipped: they need us + ru layouts with dictionaries")


def run(index: int = 0) -> None:
    if index == 0 and not edit.isActiveWindow():
        print("window is not focused, not typing anything")
        app.exit(2)
        return
    if index == len(steps):
        for name, got, want in results:
            print("OK  " if got == want else "FAIL", name, repr(got), "expected", repr(want))
        app.exit(0 if all(got == want for _, got, want in results) else 1)
        return
    steps[index]()
    QTimer.singleShot(STEP_DELAY_MS, lambda: run(index + 1))


print("Layouts:", ", ".join(lay.name for lay in layouts))
QTimer.singleShot(1500, run)
code = app.exec()
keyboard.close()
sys.exit(code)
