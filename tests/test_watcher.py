from evdev import ecodes as e

from ntrcn.watcher import PALM_GRACE_S, is_click


def test_mouse_buttons_are_clicks_even_while_typing() -> None:
    assert is_click(e.BTN_LEFT, event_time=10.0, last_key_time=10.0)
    assert is_click(e.BTN_RIGHT, event_time=10.0, last_key_time=10.0)


def test_touch_right_after_a_key_is_a_palm() -> None:
    assert not is_click(e.BTN_TOUCH, event_time=10.1, last_key_time=10.0)


def test_touch_after_a_pause_in_typing_is_a_tap() -> None:
    assert is_click(e.BTN_TOUCH, event_time=10.0 + PALM_GRACE_S, last_key_time=10.0)
