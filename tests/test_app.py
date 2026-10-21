from pathlib import Path

import ntrcn
from ntrcn.app import _parse_args

DESKTOP_FILE = Path(ntrcn.__file__).with_name(f"{ntrcn.APP_ID}.desktop")


def test_settings_flag() -> None:
    assert _parse_args(["--settings"]).settings
    assert not _parse_args([]).settings


def test_menu_entry_has_a_settings_action() -> None:
    entry = DESKTOP_FILE.read_text()
    assert "Actions=settings;" in entry
    assert "Exec=ntrcn --settings" in entry
