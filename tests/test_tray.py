import pytest
from PySide6.QtGui import QIcon

from ntrcn.flags import layout_icon
from ntrcn.layouts import Layout
from ntrcn.tray import Tray

LAYOUTS = [Layout("us", "", "EN"), Layout("epo", "", "EO")]


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
def test_every_indicator_has_an_icon(indicator: str, theme: str) -> None:
    tray = Tray(lambda _i: None, lambda: None)
    tray.indicator, tray.text_theme, tray.app_icon_theme = indicator, theme, theme
    tray.update(LAYOUTS, 0)
    assert not tray._indicator_icon(LAYOUTS[0]).isNull()


@pytest.mark.usefixtures("qt_app")
def test_no_indicator_hides_the_icon() -> None:
    tray = Tray(lambda _i: None, lambda: None)
    tray.indicator = "none"
    tray.update(LAYOUTS, 0)
    assert not tray._icon.isVisible()
