import pytest
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap

from ntrcn.sni import MenuItem, _menu_properties, _pixmap


def test_pixmap_is_argb_in_network_byte_order() -> None:
    image = QImage(1, 1, QImage.Format.Format_ARGB32)
    image.setPixelColor(0, 0, QColor(0x11, 0x22, 0x33, 0xFF))
    width, height, data = _pixmap(image)
    assert (width, height) == (1, 1)
    assert bytes(data) == bytes([0xFF, 0x11, 0x22, 0x33])


def test_separator() -> None:
    assert _menu_properties(MenuItem()) == {"type": "separator"}


def test_radio_item_with_icon_name() -> None:
    props = _menu_properties(MenuItem("Russian", icon_name="flag", checked=True))
    assert props["label"] == "Russian"
    assert props["icon-name"] == "flag"
    assert props["toggle-type"] == "radio" and props["toggle-state"] == 1


@pytest.mark.usefixtures("qt_app")
def test_icon_is_sent_as_png() -> None:
    pixmap = QPixmap(8, 8)
    pixmap.fill(QColor("red"))
    props = _menu_properties(MenuItem("A", icon=QIcon(pixmap)))
    assert bytes(props["icon-data"]).startswith(b"\x89PNG")
