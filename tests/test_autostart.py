from pathlib import Path

import pytest

from ntrcn import autostart


@pytest.fixture(autouse=True)
def autostart_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "autostart" / "app.desktop"
    monkeypatch.setattr(autostart, "AUTOSTART_FILE", path)
    return path


def test_enable_copies_desktop_file_with_own_command(
    autostart_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(autostart, "_command", lambda: "/opt/ntrcn --x")
    autostart.set_enabled(True)
    entry = autostart_file.read_text()
    assert autostart.is_enabled()
    assert "Exec=/opt/ntrcn --x\n" in entry
    assert "Name=ntrcn" in entry
    assert "Desktop Action" not in entry and "Actions=" not in entry
    assert entry.count("Exec=") == 1


def test_disable_removes_entry() -> None:
    autostart.set_enabled(True)
    autostart.set_enabled(False)
    assert not autostart.is_enabled()
    autostart.set_enabled(False)  # already off: no error
