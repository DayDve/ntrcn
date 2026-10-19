from pathlib import Path
from typing import Any

import pytest

from ntrcn import sound


def test_keyboard_sound_ships_with_ntrcn() -> None:
    assert sound.KEYBOARD_SOUND.is_file()


@pytest.mark.parametrize(
    ("mode", "custom", "expected"),
    [
        ("off", "/x.oga", None),
        ("on", "", sound.KEYBOARD_SOUND),
        ("custom", "/x.oga", Path("/x.oga")),
        ("custom", "", None),
    ],
)
def test_chosen_sound(mode: str, custom: str, expected: Path | None) -> None:
    assert sound.chosen_sound(mode, custom) == expected


def test_sound_starts_at_once_and_is_cut_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / "rhapsody.ogg"
    file.write_bytes(b"x")
    started: list[list[str]] = []
    timers: list[tuple[float, Any]] = []

    class Process:
        def __init__(self, args: list[str], **_kwargs: Any) -> None:
            started.append(args)

        def kill(self) -> None:
            pass

    class Timer:
        def __init__(self, seconds: float, action: Any) -> None:
            timers.append((seconds, action))
            self.daemon = False

        def start(self) -> None:
            pass

    monkeypatch.setattr(sound.shutil, "which", lambda _name: "/usr/bin/pw-play")
    monkeypatch.setattr(sound.subprocess, "Popen", Process)
    monkeypatch.setattr(sound.threading, "Timer", Timer)
    sound.play(file)
    assert started == [["/usr/bin/pw-play", str(file)]]
    assert timers[0][0] == sound.MAX_SECONDS


def test_missing_file_is_not_played(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sound.subprocess, "Popen", None)  # would fail if used
    sound.play(tmp_path / "missing.oga")
