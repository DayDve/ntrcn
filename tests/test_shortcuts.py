from typing import Any

import pytest

from ntrcn.shortcuts import GlobalShortcuts, Shortcut, _keys, keys_text


@pytest.mark.usefixtures("qt_app")
@pytest.mark.parametrize("sequence", ["Pause", "Shift+Pause", "Ctrl+Alt+X"])
def test_keys_round_trip(sequence: str) -> None:
    keys = _keys(sequence)
    assert len(keys) == 1 and len(keys[0][0]) == 4  # one sequence of four combined keys
    assert keys_text(keys) == sequence


@pytest.mark.usefixtures("qt_app")
def test_no_keys_is_empty_text() -> None:
    assert keys_text([]) == ""


class FakeKGlobalAccel:
    """kglobalaccel with one inactive action left over from an earlier version."""

    def __init__(self) -> None:
        self.names = ["old-action", "fix-typed"]
        self.unregistered: list[str] = []

    def get_object(self, _service: str, _path: str) -> "FakeKGlobalAccel":
        return self

    def get_dbus_method(self, member: str, _interface: str | None = None) -> Any:
        methods = {
            "doRegister": lambda action: None,
            "setShortcutKeys": lambda action, keys, flags: None,
            "getComponent": lambda component: "/component/ntrcn",
            "unregister": lambda component, name: self.unregistered.append(name),
        }
        return methods[member]

    def shortcutNames(self, dbus_interface: str) -> list[str]:  # noqa: N802 - D-Bus name
        return self.names

    def add_signal_receiver(self, *args: Any) -> None:
        pass


@pytest.mark.usefixtures("qt_app")
def test_inactive_actions_of_earlier_versions_are_removed() -> None:
    kga = FakeKGlobalAccel()
    GlobalShortcuts(kga, [Shortcut("fix-typed", "Fix", "Pause")], lambda action: None)  # type: ignore[arg-type]
    assert kga.unregistered == ["old-action"]
