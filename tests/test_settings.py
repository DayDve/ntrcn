from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton

from ntrcn import settings
from ntrcn.config import Config
from ntrcn.diagnostics import Check
from ntrcn.settings import SettingsDialog

SHORTCUTS = {"fix-typed": "Pause", "fix-selection": "", "change-case": "Ctrl+Pause"}


@pytest.fixture
def dialog(qt_app: QApplication) -> tuple[SettingsDialog, list[Config], None]:
    changes: list[Config] = []
    window = SettingsDialog(Config(), lambda: [], changes.append, SHORTCUTS.get)
    return window, changes, None


def test_shortcuts_come_from_kde(dialog: tuple) -> None:
    window, _changes, _ = dialog
    window._show_shortcuts()
    assert "Pause" in window._shortcut_labels["fix-typed"].text()
    assert "Not set" in window._shortcut_labels["fix-selection"].text()
    assert "Ctrl+Pause" in window._shortcut_labels["change-case"].text()
    texts = [button.text() for button in window.findChildren(QPushButton)]
    assert "Configure Shortcuts…" in texts  # opens System Settings; not clicked in tests


class FakeDownloader:
    def __init__(self, error: str | None) -> None:
        self.error = error
        self.languages: list[str] = []

    def download(self, language: str, on_done: Callable[[str | None], None]) -> None:
        self.languages.append(language)
        on_done(self.error)


def buttons(window: SettingsDialog) -> list[QPushButton]:
    return [b for b in window.findChildren(QPushButton) if b.text() == "Download Dictionary"]


@pytest.mark.parametrize("error", [None, "no network"])
def test_download_button_fetches_and_rechecks(
    dialog: tuple, monkeypatch: pytest.MonkeyPatch, error: str | None
) -> None:
    window, _changes, _captures = dialog
    checks = [Check("Dictionary uk", False, "hint", download="uk"), Check("Keyboard", True, "")]
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


def test_translations_are_used(monkeypatch: pytest.MonkeyPatch) -> None:
    import gettext

    from ntrcn import i18n

    class Russian(gettext.NullTranslations):
        def gettext(self, message: str) -> str:
            return {"Keyboard Layout": "Раскладка клавиатуры"}.get(message, message)

    monkeypatch.setattr(i18n, "_translation", Russian())
    assert i18n._("Keyboard Layout") == "Раскладка клавиатуры"
    assert i18n._("Quit") == "Quit"
