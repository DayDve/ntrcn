from ntrcn.app import _parse_args
from ntrcn.autostart import DESKTOP_FILE


def test_settings_flag() -> None:
    assert _parse_args(["--settings"]).settings
    assert not _parse_args([]).settings


def test_menu_entry_has_a_settings_action() -> None:
    entry = DESKTOP_FILE.read_text()
    assert "Actions=settings;" in entry
    assert "Exec=ntrcn --settings" in entry
