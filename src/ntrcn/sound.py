"""Sound played when a conversion starts."""

from __future__ import annotations

import shutil
import subprocess
import threading
from pathlib import Path

#: The sound of a hand sweeping over the keys: erasing, then typing.
KEYBOARD_SOUND = Path(__file__).with_name("sounds") / "keyboard.wav"
#: A sound file of the user's choice is cut off after this many seconds.
MAX_SECONDS = 2


def chosen_sound(mode: str, custom_file: str) -> Path | None:
    """Return the sound for a ``config.SOUND_MODES`` key, or ``None`` for no sound."""
    if mode == "on":
        return KEYBOARD_SOUND
    if mode == "custom" and custom_file:
        return Path(custom_file)
    return None


def play(sound: Path) -> None:
    """Start playing a sound file right away, stopping it after MAX_SECONDS."""
    player = shutil.which("pw-play") or shutil.which("paplay")
    if player is None or not sound.is_file():
        return
    process = subprocess.Popen(
        [player, str(sound)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    stop = threading.Timer(MAX_SECONDS, process.kill)
    stop.daemon = True
    stop.start()
