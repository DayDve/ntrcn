import pytest

from ntrcn.shortcuts import _keys, keys_text


@pytest.mark.usefixtures("qt_app")
@pytest.mark.parametrize("sequence", ["Pause", "Shift+Pause", "Ctrl+Alt+X"])
def test_keys_round_trip(sequence: str) -> None:
    keys = _keys(sequence)
    assert len(keys) == 1 and len(keys[0][0]) == 4  # one sequence of four combined keys
    assert keys_text(keys) == sequence


@pytest.mark.usefixtures("qt_app")
def test_no_keys_is_empty_text() -> None:
    assert keys_text([]) == ""
