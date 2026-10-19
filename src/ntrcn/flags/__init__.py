"""Layout icons: the user's pictures or bundled flags (``sprite.svg``), text badges, or both."""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer

from ntrcn.config import CONFIG_DIR

SPRITE_FILE = Path(__file__).with_name("sprite.svg")
USER_FLAGS_DIR = CONFIG_DIR / "flags"
FLAG_SUFFIXES = (".svg", ".png")
_SVG_NS = "http://www.w3.org/2000/svg"
ICON_SIZE = 64
_LIGHT, _DARK = QColor("#fcfcfc"), QColor("#232629")


@cache
def _sprite() -> dict[str, bytes]:
    """Return each flag of the sprite as a standalone SVG document, keyed by country code."""
    ET.register_namespace("", _SVG_NS)
    root = ET.parse(SPRITE_FILE).getroot()
    viewbox = root.get("viewBox", "0 0 512 512")
    flags = {}
    for group in root.findall(f"{{{_SVG_NS}}}g"):
        inner = ET.tostring(group, encoding="unicode")
        svg = f'<svg xmlns="{_SVG_NS}" viewBox="{viewbox}">{inner}</svg>'
        flags[group.get("id", "").lower()] = svg.encode()
    return flags


def _custom_path(layout: str, suffix: str) -> Path:
    return USER_FLAGS_DIR / f"{layout.lower()}{suffix.lower()}"


def custom_flag(layout: str) -> Path | None:
    """Return the user's own picture for a layout from ``~/.config/ntrcn/flags``, if any."""
    paths = (_custom_path(layout, suffix) for suffix in FLAG_SUFFIXES)
    return next((path for path in paths if path.is_file()), None)


def set_custom_flag(layout: str, picture: Path) -> None:
    """Use a copy of ``picture`` (SVG or PNG) as the flag of ``layout``."""
    if picture.suffix.lower() not in FLAG_SUFFIXES:
        raise ValueError(f"Only SVG and PNG pictures are supported: {picture}")
    remove_custom_flag(layout)
    USER_FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(picture, _custom_path(layout, picture.suffix))


def remove_custom_flag(layout: str) -> None:
    """Go back to the bundled flag of ``layout``."""
    for suffix in FLAG_SUFFIXES:
        _custom_path(layout, suffix).unlink(missing_ok=True)


def _draw_text(painter: QPainter, rect: QRectF, label: str, color: QColor) -> None:
    """Draw ``label`` as large as fits into ``rect``."""
    font = QFont("sans-serif")
    font.setWeight(QFont.Weight.Bold)
    font.setPixelSize(max(1, int(rect.height() * 0.62)))
    width = QFontMetricsF(font).horizontalAdvance(label)
    if width > rect.width() * 0.92:
        font.setPixelSize(max(1, int(font.pixelSize() * rect.width() * 0.92 / width)))
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)


def _draw_badge(painter: QPainter, rect: QRectF, label: str, color: QColor) -> None:
    """Draw ``label`` on a dark rounded plate, readable over any flag."""
    plate = QColor(_DARK if color == _LIGHT else _LIGHT)
    plate.setAlpha(220)
    painter.setBrush(plate)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(rect, rect.height() * 0.2, rect.height() * 0.2)
    _draw_text(painter, rect, label, color)


def _draw_flag(painter: QPainter, rect: QRectF, flag: Path | bytes) -> None:
    """Draw a flag (a picture file or bundled SVG data) cropped into the rounded banner."""
    painter.save()
    clip = QPainterPath()
    clip.addRoundedRect(rect, 6, 6)
    painter.setClipPath(clip)
    if isinstance(flag, Path) and flag.suffix.lower() == ".png":
        image = QImage(str(flag))
        # Scale to cover the banner, cropping what sticks out.
        image = image.scaled(
            rect.size().toSize(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        target = QRectF(image.rect())
        target.moveCenter(rect.center())
        painter.drawImage(target, image)
    else:
        renderer = QSvgRenderer(QByteArray(flag.read_bytes() if isinstance(flag, Path) else flag))
        # Fit the picture's width to the banner and crop the middle (bundled flags are square).
        size = renderer.defaultSize()
        height = rect.width() * size.height() / size.width() if size.width() else rect.width()
        target = QRectF(rect.x(), rect.center().y() - height / 2, rect.width(), height)
        renderer.render(painter, target)
    painter.restore()


def layout_icon(layout: str, label: str, style: str = "flag", theme: str = "dark") -> QIcon:
    """Return the icon for a layout.

    Args:
        layout: XKB layout name such as ``de``. The flag is the user's picture from
            ``~/.config/ntrcn/flags/<layout>.svg|png`` or the bundled flag of the country
            with this code.
        label: Short layout name from Plasma, shown by the text styles and as fallback.
        style: ``flag``, ``text`` (just ``label``) or ``flag_text`` (flag with ``label``
            over it). Without any flag, ``text`` is used.
        theme: ``light`` or ``dark`` text, to match a dark or light panel.
    """
    text_color = _LIGHT if theme == "light" else _DARK
    flag: Path | bytes | None = None
    if style != "text":
        flag = custom_flag(layout) or _sprite().get(layout.lower())

    image = QImage(ICON_SIZE, ICON_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    banner = QRectF(2, ICON_SIZE * 0.14, ICON_SIZE - 4, ICON_SIZE * 0.72)
    if flag is None:
        _draw_text(painter, QRectF(image.rect()), label or layout, text_color)
    else:
        _draw_flag(painter, banner, flag)
        if style == "flag_text":
            corner = QRectF(ICON_SIZE * 0.36, ICON_SIZE * 0.44, ICON_SIZE * 0.64, ICON_SIZE * 0.56)
            _draw_badge(painter, corner, label or layout, text_color)
    painter.end()
    return QIcon(QPixmap.fromImage(image))
