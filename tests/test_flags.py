from pathlib import Path

import pytest

import ntrcn.flags as flags


@pytest.fixture(autouse=True)
def flags_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(flags, "USER_FLAGS_DIR", tmp_path / "flags")
    return tmp_path / "flags"


def test_no_custom_flag_by_default() -> None:
    assert flags.custom_flag("de") is None


def test_set_replaces_previous_picture(tmp_path: Path, flags_dir: Path) -> None:
    svg, png = tmp_path / "a.svg", tmp_path / "B.PNG"
    svg.write_text("<svg/>")
    png.write_bytes(b"png")
    flags.set_custom_flag("De", svg)
    assert flags.custom_flag("de") == flags_dir / "de.svg"
    flags.set_custom_flag("de", png)
    assert flags.custom_flag("de") == flags_dir / "de.png"
    assert not (flags_dir / "de.svg").exists()


def test_remove_goes_back_to_bundled(tmp_path: Path) -> None:
    svg = tmp_path / "a.svg"
    svg.write_text("<svg/>")
    flags.set_custom_flag("de", svg)
    flags.remove_custom_flag("de")
    assert flags.custom_flag("de") is None


def test_only_svg_and_png(tmp_path: Path) -> None:
    jpg = tmp_path / "a.jpg"
    jpg.write_bytes(b"jpg")
    with pytest.raises(ValueError):
        flags.set_custom_flag("de", jpg)
