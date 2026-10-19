from collections.abc import Callable
from pathlib import Path

import pytest
from evdev import ecodes as e
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

from ntrcn import settings
from ntrcn.config import Config
from ntrcn.diagnostics import Check
from ntrcn.settings import SettingsDialog

KeyCallback = Callable[[int], None]


@pytest.fixture
def dialog(qt_app: QApplication) -> tuple[SettingsDialog, list[Config], list[KeyCallback | None]]:
    changes: list[Config] = []
    captures: list[KeyCallback | None] = []
    window = SettingsDialog(Config(), lambda: [], changes.append, captures.append)
    return window, changes, captures


def capture(dialog: SettingsDialog, captures: list[KeyCallback | None], code: int) -> None:
    dialog._start_hotkey_capture()
    callback = captures[-1]
    assert callback is not None
    callback(code)


def test_hotkey_is_changed_by_a_key_press(dialog: tuple) -> None:
    window, changes, captures = dialog
    capture(window, captures, e.KEY_F13)
    assert changes[-1].hotkey == "F13"
    assert "F13" in window._word_hotkey.text()


def test_escape_cancels(dialog: tuple) -> None:
    window, changes, captures = dialog
    capture(window, captures, e.KEY_ESC)
    assert changes == []


def test_typing_keys_are_refused(dialog: tuple) -> None:
    window, changes, captures = dialog
    capture(window, captures, e.KEY_A)
    assert changes == []
    assert window._hotkey_error.text()


class FakeDownloader:
    def __init__(self, error: str | None) -> None:
        self.error = error
        self.languages: list[str] = []

    def download(self, language: str, on_done: Callable[[str | None], None]) -> None:
        self.languages.append(language)
        on_done(self.error)


def buttons(window: SettingsDialog) -> list[QPushButton]:
    return [b for b in window.findChildren(QPushButton) if b.text() == "Скачать словарь"]


@pytest.mark.parametrize("error", [None, "нет сети"])
def test_download_button_fetches_and_rechecks(
    dialog: tuple, monkeypatch: pytest.MonkeyPatch, error: str | None
) -> None:
    window, _changes, _captures = dialog
    checks = [Check("Словарь uk", False, "hint", download="uk"), Check("Клавиатура", True, "")]
    monkeypatch.setattr(settings, "run_checks", lambda _layouts: checks)
    forgotten: list[bool] = []
    monkeypatch.setattr(settings, "forget_dictionaries", lambda: forgotten.append(True))
    window._downloader = FakeDownloader(error)
    window._run_checks()
    assert len(buttons(window)) == 1
    buttons(window)[0].click()
    assert window._downloader.languages == ["uk"]
    assert forgotten == [True]
    assert window._download_error.text() == (error or "")


@pytest.mark.parametrize(
    ("indicator", "text_theme_shown", "app_icon_theme_shown"),
    [("flag", False, False), ("text", True, False), ("app_icon", False, True)],
)
def test_theme_lists_follow_the_indicator(
    dialog: tuple, indicator: str, text_theme_shown: bool, app_icon_theme_shown: bool
) -> None:
    window, changes, _captures = dialog
    indicator_box, text_theme, app_icon_theme = window.findChildren(QComboBox)[:3]
    indicator_box.setCurrentIndex(indicator_box.findData("none"))
    indicator_box.setCurrentIndex(indicator_box.findData(indicator))
    assert changes[-1].tray_indicator == indicator
    assert window._indicator_form.isRowVisible(text_theme) == text_theme_shown
    assert window._indicator_form.isRowVisible(app_icon_theme) == app_icon_theme_shown


def test_theme_choice_is_saved(dialog: tuple) -> None:
    window, changes, _captures = dialog
    app_icon_theme = window.findChildren(QComboBox)[2]
    app_icon_theme.setCurrentIndex(app_icon_theme.findData("color"))
    assert changes[-1].app_icon_theme == "color"


def test_sound_file_button_only_for_own_sound(
    dialog: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    window, changes, _captures = dialog
    played: list[Path] = []
    monkeypatch.setattr(settings, "play", played.append)
    assert not window._sound_file.isVisibleTo(window)
    assert not window._listen.isEnabled()  # off by default

    window._sound.setCurrentIndex(window._sound.findData("on"))
    assert changes[-1].sound == "on" and window._listen.isEnabled()

    window._sound.setCurrentIndex(window._sound.findData("custom"))
    assert window._sound_file.isVisibleTo(window)
    assert not window._listen.isEnabled()  # no file yet
    monkeypatch.setattr(
        settings.QFileDialog, "getOpenFileName", lambda *_a: ("/music/tick.ogg", "")
    )
    window._sound_file.click()
    assert changes[-1].sound_file == "/music/tick.ogg"
    assert window._sound_file.text() == "tick.ogg"
    assert played == [Path("/music/tick.ogg")]
