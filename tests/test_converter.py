import logging
from collections.abc import Callable, Iterable
from typing import Any

import pytest
from evdev import ecodes as e

import ntrcn.converter
from ntrcn.converter import Converter
from ntrcn.keys import Keystroke
from ntrcn.layouts import Layout


class FakeKde:
    def __init__(self, names: tuple[str, ...] = ("us", "ru")) -> None:
        self.index = 0
        self.layouts = [Layout(name, "", name.upper()) for name in names]
        self.changed: Callable[[int], None] = lambda _i: None

    def list(self) -> list[Layout]:
        return self.layouts

    def current(self) -> int:
        return self.index

    def set(self, index: int) -> None:
        self.index = index
        self.changed(index)

    def on_changed(self, callback: Callable[[int], None]) -> None:
        self.changed = callback

    def on_list_changed(self, callback: Callable[[], None]) -> None:
        pass


class FakeTyper:
    def __init__(self) -> None:
        self.log: list[Any] = []
        self.strokes: list[Keystroke] = []

    def erase(self, count: int) -> None:
        self.log.append(("erase", count))

    def type(self, strokes: Iterable[Keystroke]) -> None:
        self.strokes = list(strokes)
        self.log.append(("type", [s.code for s in self.strokes]))

    def select_back(self, count: int) -> None:
        self.log.append(("select", count))


@pytest.fixture
def setup() -> tuple[Converter, FakeKde, FakeTyper]:
    kde, typer = FakeKde(), FakeTyper()
    converter = Converter(kde, typer)  # type: ignore[arg-type]
    return converter, kde, typer


def press(converter: Converter, *codes: int, held: set[int] | None = None) -> None:
    """Press keys; Pause also fires the global shortcut, as KWin does after the key event."""
    for code in codes:
        converter.on_key_press(code, held or set())
        if code == e.KEY_PAUSE:
            if held and e.KEY_LEFTSHIFT in held:
                converter.fix_selection()
            else:
                converter.fix_typed()


def test_pause_retypes_last_word_in_next_layout(setup: Any) -> None:
    converter, kde, typer = setup
    press(converter, e.KEY_G, e.KEY_H, e.KEY_SPACE, e.KEY_PAUSE)
    assert kde.index == 1
    assert typer.log == [("erase", 3), ("type", [e.KEY_G, e.KEY_H, e.KEY_SPACE])]


def test_layout_is_switched_before_typing(setup: Any) -> None:
    # The app gets the new layout with a delay, so switching must come first.
    converter, kde, typer = setup
    kde.changed = lambda _i: typer.log.append("switch")
    press(converter, e.KEY_G, e.KEY_PAUSE)
    assert typer.log == ["switch", ("erase", 1), ("type", [e.KEY_G])]


def test_second_pause_converts_back(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    converter, kde, typer = setup
    monkeypatch.setattr(ntrcn.converter, "ECHO_GRACE_S", 0)
    press(converter, e.KEY_G, e.KEY_PAUSE)
    press(converter, e.KEY_PAUSE)
    assert kde.index == 0
    assert typer.log[-2:] == [("erase", 1), ("type", [e.KEY_G])]


def test_word_typed_after_manual_switch_uses_its_own_layout(setup: Any) -> None:
    converter, kde, typer = setup
    kde.set(1)  # user typed the word in RU ...
    press(converter, e.KEY_G)
    kde.set(0)  # ... then switched to EN by hand before pressing the hotkey
    press(converter, e.KEY_PAUSE)
    assert kde.index == 0
    assert typer.log == [("erase", 1), ("type", [e.KEY_G])]


def test_pause_with_empty_buffer_does_nothing(setup: Any) -> None:
    converter, kde, typer = setup
    press(converter, e.KEY_PAUSE)
    assert typer.log == [] and kde.index == 0


def test_keys_right_after_conversion_are_ignored_as_echo(setup: Any) -> None:
    converter, _kde, _typer = setup
    press(converter, e.KEY_G, e.KEY_PAUSE)
    press(converter, e.KEY_BACKSPACE)
    assert len(converter.buffer) == 1


def test_on_convert_fires_before_retyping_and_only_then(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ntrcn.converter, "ECHO_GRACE_S", 0)
    typer = FakeTyper()
    converter = Converter(
        FakeKde(),  # type: ignore[arg-type]
        typer,  # type: ignore[arg-type]
        on_convert=lambda: typer.log.append("sound"),
    )
    press(converter, e.KEY_PAUSE)  # empty buffer: nothing to convert, no sound
    assert typer.log == []
    press(converter, e.KEY_G, e.KEY_PAUSE)
    assert typer.log == ["sound", ("erase", 1), ("type", [e.KEY_G])]


def test_shortcut_with_modifiers_still_finds_the_typed_text(setup: Any) -> None:
    # Ctrl+Alt+X resets the buffer as a shortcut a moment before KDE reports it.
    converter, kde, typer = setup
    press(converter, e.KEY_G)
    converter.on_key_press(e.KEY_X, {e.KEY_LEFTCTRL, e.KEY_LEFTALT})
    converter.fix_typed()
    assert kde.index == 1
    assert typer.log == [("erase", 1), ("type", [e.KEY_G])]


def test_shift_pause_retypes_selection(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    converter, kde, typer = setup
    monkeypatch.setattr(ntrcn.converter, "read_primary_selection", lambda: "ghb")
    press(converter, e.KEY_PAUSE, held={e.KEY_LEFTSHIFT})
    assert kde.index == 1
    assert typer.log == [("type", [e.KEY_G, e.KEY_H, e.KEY_B])]


WORDS = {"us": {"hello", "a"}, "ru": {"привет", "мир"}, "ua": {"світ"}}


def speller(layout: str) -> Callable[[str], bool]:
    return lambda word: word.lower() in WORDS[layout]


def with_dictionaries(
    names: tuple[str, ...] = ("us", "ru"),
) -> tuple[Converter, FakeKde, FakeTyper]:
    kde, typer = FakeKde(names), FakeTyper()
    converter = Converter(kde, typer, speller=speller)  # type: ignore[arg-type]
    return converter, kde, typer


PHRASE = [
    e.KEY_G,
    e.KEY_H,
    e.KEY_B,
    e.KEY_D,
    e.KEY_T,
    e.KEY_N,
    e.KEY_SPACE,
    e.KEY_V,
    e.KEY_B,
    e.KEY_H,
]


def test_whole_mistyped_phrase_is_retyped() -> None:
    converter, kde, typer = with_dictionaries()
    press(converter, *PHRASE, e.KEY_PAUSE)
    assert kde.index == 1
    assert typer.log == [("erase", 10), ("type", PHRASE)]


def test_correct_words_before_are_kept() -> None:
    converter, _kde, typer = with_dictionaries()
    hello = [e.KEY_H, e.KEY_E, e.KEY_L, e.KEY_L, e.KEY_O, e.KEY_SPACE]
    press(converter, *hello, *PHRASE[:6], e.KEY_PAUSE)
    assert typer.log == [("erase", 6), ("type", PHRASE[:6])]


def test_hotkey_again_cycles_the_same_phrase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ntrcn.converter, "ECHO_GRACE_S", 0)
    converter, kde, typer = with_dictionaries()
    press(converter, *PHRASE, e.KEY_PAUSE)
    press(converter, e.KEY_PAUSE)
    assert kde.index == 0
    assert typer.log[-2:] == [("erase", 10), ("type", PHRASE)]


def test_typing_after_conversion_starts_over(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ntrcn.converter, "ECHO_GRACE_S", 0)
    converter, _kde, typer = with_dictionaries()
    press(converter, *PHRASE, e.KEY_PAUSE)
    press(converter, e.KEY_SPACE, e.KEY_H, e.KEY_E, e.KEY_L, e.KEY_L, e.KEY_O, e.KEY_PAUSE)
    # "hello" was typed in RU now ("руддщ"), so only it goes back to EN.
    assert typer.log[-2:] == [("erase", 5), ("type", [e.KEY_H, e.KEY_E, e.KEY_L, e.KEY_L, e.KEY_O])]


def test_dictionary_picks_the_target_among_several_layouts() -> None:
    converter, kde, _typer = with_dictionaries(("us", "ua", "ru"))
    press(converter, *PHRASE, e.KEY_PAUSE)
    assert kde.layouts[kde.index].name == "ru"  # not "ua", the next one


def test_without_dictionaries_the_next_layout_and_last_word(setup: Any) -> None:
    converter, kde, typer = setup
    press(converter, *PHRASE, e.KEY_PAUSE)
    assert kde.index == 1
    assert typer.log == [("erase", 3), ("type", PHRASE[7:])]


def test_typed_text_never_reaches_the_log(
    setup: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    converter, _kde, _typer = setup
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(ntrcn.converter, "read_primary_selection", lambda: "ghbdtn")
    press(converter, e.KEY_PAUSE, held={e.KEY_LEFTSHIFT})
    assert caplog.records
    assert "ghbdtn" not in caplog.text and "привет" not in caplog.text


def test_change_case_retypes_and_reselects(setup: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    converter, kde, typer = setup
    monkeypatch.setattr(ntrcn.converter, "read_primary_selection", lambda: "ghb")
    converter.change_case()
    assert kde.index == 0  # the current layout has the letters
    assert typer.log == [("type", [e.KEY_G, e.KEY_H, e.KEY_B]), ("select", 3)]
    assert all(stroke.shift for stroke in typer.strokes)  # "GHB"


def test_change_case_switches_to_a_layout_that_has_the_letters(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    converter, kde, typer = setup
    monkeypatch.setattr(ntrcn.converter, "read_primary_selection", lambda: "привет")
    converter.change_case()
    assert kde.index == 1
    assert typer.log[-1] == ("select", 6)


def test_change_case_ignores_text_without_letters(
    setup: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    converter, _kde, typer = setup
    monkeypatch.setattr(ntrcn.converter, "read_primary_selection", lambda: "123")
    converter.change_case()
    assert typer.log == []
