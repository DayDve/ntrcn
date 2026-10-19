from pathlib import Path

import pytest

from ntrcn import diagnostics
from ntrcn.layouts import Layout

UA = Layout("ua", "", "UK")


def test_dictionary_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "find_dictionary", lambda _lang, _layout: Path("/x.dic"))
    check = diagnostics._dictionary_check(UA, "debian")
    assert check.ok and "uk" in check.title and check.download is None


def test_missing_dictionary_tells_the_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "find_dictionary", lambda _lang, _layout: None)
    check = diagnostics._dictionary_check(UA, "debian")
    assert not check.ok
    assert check.download == "uk"
    assert "sudo apt install hunspell-uk" in check.hint


def test_layout_without_language(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diagnostics, "layout_language", lambda _layout: None)
    assert not diagnostics._dictionary_check(UA, "debian").ok


def test_udev_rule_ships_with_the_package() -> None:
    assert 'KERNEL=="uinput"' in diagnostics.UDEV_RULE_FILE.read_text()
