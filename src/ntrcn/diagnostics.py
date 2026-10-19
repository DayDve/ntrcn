"""Checks that the system lets ntrcn read keys, type, read the selection and spell-check."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import NamedTuple

import evdev
from evdev import ecodes as e

from ntrcn.distro import distro_family, install_command, install_hint
from ntrcn.layouts import Layout
from ntrcn.spelling import find_dictionary, layout_language

UDEV_RULE_FILE = Path(__file__).with_name("70-ntrcn-uinput.rules")


class Check(NamedTuple):
    """Result of one check, with a hint on how to fix a failure."""

    title: str
    ok: bool
    hint: str
    #: Language whose missing dictionary can be downloaded to fix this.
    download: str | None = None


def _readable_keyboards() -> int:
    count = 0
    for path in evdev.list_devices():  # lists only devices the user may open
        try:
            device = evdev.InputDevice(path)
        except OSError:
            continue
        count += e.KEY_A in device.capabilities().get(e.EV_KEY, [])
        device.close()
    return count


def _dictionary_check(layout: Layout, family: str | None) -> Check:
    title = f"Словарь для {layout.label} ({layout.name})"
    language = layout_language(layout.name)
    if language is None:
        return Check(title, False, "Язык раскладки неизвестен: исправляется только последнее слово")
    found = find_dictionary(language, layout.name) is not None
    hint = (
        "Без словаря исправляется только последнее слово. "
        f"Скачайте его или установите пакетом: {install_hint(language, family)}"
    )
    return Check(f"{title}: {language}", found, hint, download=None if found else language)


def run_checks(layouts: list[Layout]) -> list[Check]:
    """Run all checks for the layouts configured in Plasma."""
    family = distro_family()
    wl_clipboard = install_command("wl-clipboard", family) or "установите пакет wl-clipboard"
    return [
        Check(
            "Чтение клавиатур",
            _readable_keyboards() > 0,
            "Добавьте себя в группу input и перезайдите: sudo usermod -aG input $USER",
        ),
        Check(
            "Виртуальная клавиатура (/dev/uinput)",
            os.access("/dev/uinput", os.W_OK),
            f"Разрешите доступ правилом udev: sudo install -m 644 {UDEV_RULE_FILE} "
            "/etc/udev/rules.d/ && sudo udevadm trigger /dev/uinput",
        ),
        Check("Чтение выделения (wl-paste)", shutil.which("wl-paste") is not None, wl_clipboard),
        Check(
            f"Раскладки Plasma: {len(layouts)}",
            len(layouts) >= 2,
            "Добавьте вторую раскладку в Параметрах системы → Клавиатура → Раскладки",
        ),
        *(_dictionary_check(layout, family) for layout in layouts),
    ]
