import pytest

from ntrcn.convert import (
    NEWLINE,
    detect_source,
    next_case,
    next_layout,
    plan_retype,
    plan_typing,
    retyped_text,
    wrong_fragment,
)
from ntrcn.keymap import layout_chars


@pytest.fixture(scope="module")
def us_ru() -> list:
    return [layout_chars("us"), layout_chars("ru")]


def test_next_layout_wraps() -> None:
    assert next_layout(0, 2) == 1
    assert next_layout(1, 2) == 0
    assert next_layout(2, 3) == 0


def test_layout_chars_us_and_ru() -> None:
    us, ru = layout_chars("us"), layout_chars("ru")
    assert "".join(sorted(set(us.values()) & set("qwerty"))) == "eqrtwy"
    assert "й" in ru.values() and "Ё" in ru.values()


def test_unknown_layout_raises() -> None:
    with pytest.raises(ValueError):
        layout_chars("no-such-layout")


@pytest.mark.parametrize(
    ("text", "source"),
    [("ghbdtn", 0), ("привет", 1), ("Ghbdtn, vbh!", 0), ("руддщ", 1)],
)
def test_detect_source(us_ru: list, text: str, source: int) -> None:
    assert detect_source(text, us_ru) == source


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ghbdtn", "привет"),
        ("Ghbdtn vbh", "Привет мир"),
        ("ghbdtn? z nen", "привет, я тут"),
        ("руддщ", "hello"),
        ("Ntrcn\nyf ldt cnhjrb", "Текст\nна две строки"),
    ],
)
def test_plan_retype_round_trip(us_ru: list, text: str, expected: str) -> None:
    plan = plan_retype(text, us_ru)
    assert plan is not None
    assert retyped_text(plan.strokes, us_ru[plan.target]) == expected


def test_newline_is_shift_enter(us_ru: list) -> None:
    plan = plan_retype("a\nb", us_ru)
    assert plan is not None and plan.strokes[1] == NEWLINE


def test_chars_only_in_target_are_kept(us_ru: list) -> None:
    plan = plan_retype("ghbdtn мир", us_ru)
    assert plan is not None
    assert retyped_text(plan.strokes, us_ru[plan.target]) == "привет мир"


def test_untypable_text_is_rejected(us_ru: list) -> None:
    assert plan_retype("ghbdtn 🙂", us_ru) is None


def test_needs_two_layouts(us_ru: list) -> None:
    assert plan_retype("ghbdtn", us_ru[:1]) is None
    assert plan_retype("", us_ru) is None


ENGLISH = {"hello", "a", "z", "kubectl2"}
RUSSIAN = {"привет", "мир", "я", "тут", "а"}


def fragment(*pairs: tuple[str, str]) -> tuple[int, int]:
    return wrong_fragment(pairs, ENGLISH.__contains__, RUSSIAN.__contains__)


def test_whole_phrase_in_wrong_layout() -> None:
    assert fragment(("ghbdtn", "привет"), ("vbh", "мир")) == (2, 2)


def test_stops_at_a_right_word() -> None:
    assert fragment(("hello", "руддщ"), ("ghbdtn", "привет")) == (1, 1)


def test_unknown_leading_words_are_left_out() -> None:
    assert fragment(("kubectl", "лгиусед"), ("ghbdtn", "привет"), ("vbh", "мир")) == (2, 2)


def test_unknown_words_inside_are_kept() -> None:
    assert fragment(("ghbdtn", "привет"), ("ntcn", "тест"), ("vbh", "мир")) == (3, 2)


def test_punctuation_and_words_known_in_both() -> None:
    # "z" is a letter in English and "я" a word in Russian: neither right nor wrong.
    assert fragment(("ghbdtn?", "привет,"), ("z", "я"), ("nen", "тут")) == (3, 2)


def test_last_word_is_converted_even_if_dictionaries_disagree() -> None:
    assert fragment(("hello", "руддщ")) == (1, 0)
    assert fragment(("123", "123")) == (1, 0)


def test_without_dictionaries_only_last_word() -> None:
    pairs = (("ghbdtn", "привет"), ("vbh", "мир"))
    assert wrong_fragment(pairs, None, None) == (1, 0)


def test_selection_target_chosen_by_dictionaries() -> None:
    us_ua_ru = [layout_chars("us"), layout_chars("ua"), layout_chars("ru")]
    russian = RUSSIAN.__contains__
    # Without dictionaries the next layout (ua) is taken; Russian knows the word.
    assert plan_retype("ghbdtn", us_ua_ru).target == 1  # type: ignore[union-attr]
    plan = plan_retype("ghbdtn", us_ua_ru, [ENGLISH.__contains__, None, russian])
    assert plan is not None and plan.target == 2
    assert retyped_text(plan.strokes, us_ua_ru[2]) == "привет"


def test_selection_source_chosen_by_dictionaries(us_ru: list) -> None:
    plan = plan_retype("руддщ", us_ru, [ENGLISH.__contains__, RUSSIAN.__contains__])
    assert plan is not None and (plan.source, plan.target) == (1, 0)
    assert retyped_text(plan.strokes, us_ru[0]) == "hello"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("привет мир", "ПРИВЕТ МИР"),
        ("ПРИВЕТ МИР", "Привет Мир"),
        ("Привет Мир", "привет мир"),
        ("пРИВЕТ", "привет"),  # mixed case starts the cycle over
        ("a", "A"),
        ("A", "a"),  # upper and title are the same: no getting stuck
        ("don't stop", "DON'T STOP"),
    ],
)
def test_next_case_cycles(text: str, expected: str) -> None:
    assert next_case(text) == expected


def test_next_case_without_letters_is_unchanged() -> None:
    assert next_case("123 !") == "123 !"


def test_plan_typing_in_one_layout(us_ru: list) -> None:
    strokes = plan_typing("Привет", us_ru[1])
    assert strokes is not None and retyped_text(strokes, us_ru[1]) == "Привет"
    assert plan_typing("Привет", us_ru[0]) is None
