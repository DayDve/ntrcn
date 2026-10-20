"""Checks that the system lets ntrcn read keys, type, read the selection and spell-check."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import NamedTuple

import evdev
from evdev import ecodes as e

from ntrcn.distro import distro_family, install_command, install_hint
from ntrcn.i18n import _
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
    title = _("Dictionary for {label} ({name})").format(label=layout.label, name=layout.name)
    language = layout_language(layout.name)
    if language is None:
        return Check(
            title, False, _("The layout's language is unknown: only the last word is fixed")
        )
    found = find_dictionary(language, layout.name) is not None
    hint = _(
        "Without a dictionary only the last word is fixed. Download it or install a package: {hint}"
    ).format(hint=install_hint(language, family))
    return Check(f"{title}: {language}", found, hint, download=None if found else language)


def run_checks(layouts: list[Layout]) -> list[Check]:
    """Run all checks for the layouts configured in Plasma."""
    family = distro_family()
    wl_clipboard = install_command("wl-clipboard", family) or _("Install the wl-clipboard package")
    return [
        Check(
            _("Reading keyboards"),
            _readable_keyboards() > 0,
            _("Add yourself to the input group and log in again: sudo usermod -aG input $USER"),
        ),
        Check(
            _("Virtual keyboard (/dev/uinput)"),
            os.access("/dev/uinput", os.W_OK),
            _(
                "Allow access with the udev rule: sudo install -m 644 {rule} "
                "/etc/udev/rules.d/ && sudo udevadm trigger /dev/uinput"
            ).format(rule=UDEV_RULE_FILE),
        ),
        Check(
            _("Reading the selection (wl-paste)"),
            shutil.which("wl-paste") is not None,
            wl_clipboard,
        ),
        Check(
            _("Plasma layouts: {count}").format(count=len(layouts)),
            len(layouts) >= 2,
            _("Add a second layout in System Settings → Keyboard → Layouts"),
        ),
        *(_dictionary_check(layout, family) for layout in layouts),
    ]
