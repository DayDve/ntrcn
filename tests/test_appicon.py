import pytest

from ntrcn.appicon import THEMED_ICONS, app_icon


def test_an_icon_file_per_theme() -> None:
    assert set(THEMED_ICONS) == {"color", "light", "dark"}
    assert all(path.is_file() for path in THEMED_ICONS.values())


@pytest.mark.usefixtures("qt_app")
@pytest.mark.parametrize("theme", ["color", "light", "dark"])
def test_icons_load(theme: str) -> None:
    assert not app_icon(theme).isNull()
