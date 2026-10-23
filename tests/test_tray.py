from typing import Any

import pytest
from PySide6.QtGui import QIcon

import ntrcn.tray
from ntrcn.flags import layout_icon
from ntrcn.layouts import Layout
from ntrcn.tray import Tray

LAYOUTS = [Layout("us", "", "EN", "English (US)"), Layout("epo", "", "EO")]


class FakeItem:
    def __init__(self, _bus: Any, _id: str, on_activate: Any, on_scroll: Any) -> None:
        self.on_activate, self.on_scroll = on_activate, on_scroll
        self.visible = False
        self.tooltip: tuple[str, str] = ("", "")
        self.menu: list[Any] = []

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def set_icon(self, _icon: QIcon) -> None:
        pass

    def set_tooltip(self, title: str, subtitle: str) -> None:
        self.tooltip = (title, subtitle)

    def set_menu(self, items: list[Any]) -> None:
        self.menu = items


@pytest.fixture
def tray(monkeypatch: pytest.MonkeyPatch) -> tuple[Tray, list[int]]:
    monkeypatch.setattr(ntrcn.tray, "StatusNotifierItem", FakeItem)
    monkeypatch.setattr(ntrcn.tray, "tray_available", lambda _bus: True)
    selected: list[int] = []
    return Tray(None, selected.append, lambda: None), selected  # type: ignore[arg-type]


def colours(icon: QIcon) -> set[str]:
    image = icon.pixmap(64, 64).toImage()
    return {image.pixelColor(x, y).name() for x in range(64) for y in range(64)}


@pytest.mark.usefixtures("qt_app")
def test_text_is_drawn_in_the_theme_colour() -> None:
    assert "#fcfcfc" in colours(layout_icon("us", "ENG", "text", "light"))
    assert "#232629" in colours(layout_icon("us", "ENG", "text", "dark"))


@pytest.mark.usefixtures("qt_app")
def test_layout_without_flag_falls_back_to_text() -> None:
    assert "#fcfcfc" in colours(layout_icon("epo", "EO", "flag", "light"))


@pytest.mark.usefixtures("qt_app")
@pytest.mark.parametrize("indicator", ["flag", "text", "flag_text", "app_icon"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_every_indicator_has_an_icon(tray: tuple, indicator: str, theme: str) -> None:
    item, _selected = tray
    item.indicator, item.text_theme, item.app_icon_theme = indicator, theme, theme
    assert not item._indicator_icon(LAYOUTS[0]).isNull()


@pytest.mark.usefixtures("qt_app")
def test_tooltip_like_plasma_keyboard_widget(tray: tuple) -> None:
    item, _selected = tray
    item.update(LAYOUTS, 0)
    assert item._item.visible
    assert item._item.tooltip == ("Keyboard Layout", "English (US)")


@pytest.mark.usefixtures("qt_app")
def test_menu_lists_layouts_with_the_current_one_checked(tray: tuple) -> None:
    item, selected = tray
    item.update(LAYOUTS, 1)
    menu = item._item.menu
    assert [m.label for m in menu[:2]] == ["English (US)", "EO"]
    assert [m.checked for m in menu[:2]] == [False, True]
    menu[0].action()
    assert selected == [0]


@pytest.mark.usefixtures("qt_app")
def test_click_and_wheel_cycle_layouts(tray: tuple) -> None:
    item, selected = tray
    item.update(LAYOUTS, 1)
    item._item.on_activate()
    item._item.on_scroll(-1)
    assert selected == [0, 0]


@pytest.mark.usefixtures("qt_app")
def test_no_indicator_hides_the_item(tray: tuple) -> None:
    item, _selected = tray
    item.update(LAYOUTS, 0)
    item.indicator = "none"
    item.update(LAYOUTS, 0)
    assert not item._item.visible
