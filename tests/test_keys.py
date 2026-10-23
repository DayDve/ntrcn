from evdev import ecodes as e

from ntrcn.keys import KeyBuffer, Keystroke

SHIFT = {e.KEY_LEFTSHIFT}
CTRL = {e.KEY_LEFTCTRL}


def type_keys(buffer: KeyBuffer, codes: list[int], held: set[int] | None = None) -> None:
    for code in codes:
        buffer.press(code, held or set(), layout=0)


def codes(keys: list) -> list[int]:
    return [key.stroke.code for key in keys]


def test_last_word_with_trailing_spaces() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_SPACE, e.KEY_B, e.KEY_C, e.KEY_SPACE, e.KEY_SPACE])
    assert codes(buffer.tail(1)) == [e.KEY_B, e.KEY_C, e.KEY_SPACE, e.KEY_SPACE]


def test_punctuation_keys_belong_to_the_word() -> None:
    # In the Russian layout , . ; ' [ ] are letters, so they must not split words.
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_G, e.KEY_COMMA, e.KEY_SEMICOLON])
    assert codes(buffer.tail(1)) == [e.KEY_G, e.KEY_COMMA, e.KEY_SEMICOLON]


def test_shift_is_recorded() -> None:
    buffer = KeyBuffer()
    buffer.press(e.KEY_G, SHIFT, layout=0)
    buffer.press(e.KEY_H, set(), layout=0)
    assert [key.stroke for key in buffer.tail(1)] == [
        Keystroke(e.KEY_G, True),
        Keystroke(e.KEY_H, False),
    ]


def test_backspace_removes_last_key() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_B, e.KEY_BACKSPACE])
    assert codes(buffer.tail(1)) == [e.KEY_A]


def test_backspace_on_empty_buffer_is_harmless() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_BACKSPACE])
    assert len(buffer) == 0


def test_caret_movement_resets() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_LEFT, e.KEY_B])
    assert codes(buffer.tail(1)) == [e.KEY_B]


def test_shortcut_resets() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A])
    buffer.press(e.KEY_V, CTRL, layout=0)
    assert len(buffer) == 0


def test_modifiers_and_caps_lock_keep_buffer() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_LEFTSHIFT, e.KEY_CAPSLOCK, e.KEY_LEFTCTRL])
    assert codes(buffer.tail(1)) == [e.KEY_A]


def test_only_spaces_give_only_spaces() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_SPACE])
    assert codes(buffer.tail(1)) == [e.KEY_SPACE]


def test_layout_is_remembered_and_relabelled() -> None:
    buffer = KeyBuffer()
    buffer.press(e.KEY_A, set(), layout=0)
    buffer.press(e.KEY_B, set(), layout=0)
    buffer.relabel_tail(1, layout=1)
    assert [key.layout for key in buffer.tail(1)] == [0, 1]


def test_buffer_is_bounded() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A] * 1000)
    assert len(buffer) == 256


def test_tail_spans_several_words() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_SPACE, e.KEY_B, e.KEY_SPACE, e.KEY_SPACE, e.KEY_C])
    assert codes(buffer.tail(2)) == [e.KEY_B, e.KEY_SPACE, e.KEY_SPACE, e.KEY_C]
    assert len(buffer.tail(10)) == 6


def test_trailing_words_skip_spaces() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_B, e.KEY_SPACE, e.KEY_SPACE, e.KEY_C, e.KEY_SPACE])
    assert [codes(word) for word in buffer.trailing_words()] == [[e.KEY_A, e.KEY_B], [e.KEY_C]]


def test_trailing_words_stop_at_another_layout() -> None:
    buffer = KeyBuffer()
    buffer.press(e.KEY_A, set(), layout=1)
    buffer.press(e.KEY_SPACE, set(), layout=1)
    buffer.press(e.KEY_B, set(), layout=0)
    buffer.press(e.KEY_SPACE, set(), layout=1)  # spaces do not depend on the layout
    buffer.press(e.KEY_C, set(), layout=0)
    assert [codes(word) for word in buffer.trailing_words()] == [[e.KEY_B], [e.KEY_C]]


def test_trailing_words_of_empty_or_blank_buffer() -> None:
    buffer = KeyBuffer()
    assert buffer.trailing_words() == []
    type_keys(buffer, [e.KEY_SPACE])
    assert buffer.trailing_words() == []


def test_reset_by_a_key_can_be_undone_right_away() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_B])
    revision = buffer.revision
    buffer.press(e.KEY_PAUSE, set(), layout=0)
    assert len(buffer) == 0
    buffer.undo_reset()
    assert codes(buffer.tail(1)) == [e.KEY_A, e.KEY_B]
    assert buffer.revision == revision  # as if the key had not been pressed


def test_old_or_click_resets_are_not_undone() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A])
    buffer.press(e.KEY_ENTER, set(), layout=0)
    buffer.undo_reset(max_age=-1)  # too late
    assert len(buffer) == 0
    type_keys(buffer, [e.KEY_B])
    buffer.reset()  # a click
    buffer.undo_reset()
    assert len(buffer) == 0


def test_nothing_to_undo_once_typing_continued() -> None:
    buffer = KeyBuffer()
    type_keys(buffer, [e.KEY_A, e.KEY_ENTER, e.KEY_B])
    buffer.undo_reset()
    assert codes(buffer.tail(1)) == [e.KEY_B]
