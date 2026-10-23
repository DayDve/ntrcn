from pathlib import Path

import pytest

from ntrcn import autostart


@pytest.fixture(autouse=True)
def autostart_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "autostart" / "app.desktop"
    monkeypatch.setattr(autostart, "AUTOSTART_FILE", path)
    return path


def test_enable_writes_entry_with_own_command(
    autostart_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autostart, "_command", lambda: "/opt/ntrcn --x")
    autostart.set_enabled(True)
    entry = autostart_file.read_text()
    assert autostart.is_enabled()
    assert entry == (
        "[Desktop Entry]\nType=Application\nName=ntrcn\n"
        "Exec=/opt/ntrcn --x\nIcon=org.daydve.ntrcn\n"
    )


def test_disable_removes_entry() -> None:
    autostart.set_enabled(True)
    autostart.set_enabled(False)
    assert not autostart.is_enabled()
    autostart.set_enabled(False)  # already off: no error


def test_entry_hidden_in_plasma_settings_is_off(autostart_file: Path) -> None:
    autostart.set_enabled(True)
    autostart_file.write_text(autostart_file.read_text() + "Hidden=true\n")
    assert not autostart.is_enabled()
    autostart.set_enabled(True)  # switching it on again overwrites the hidden entry
    assert autostart.is_enabled()
