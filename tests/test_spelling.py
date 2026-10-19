from pathlib import Path

import pytest

from ntrcn import spelling

REGISTRY = """<xkbConfigRegistry><layoutList>
<layout><configItem><name>ua</name><languageList><iso639Id>ukr</iso639Id></languageList>
</configItem></layout>
<layout><configItem><name>us</name><languageList><iso639Id>eng</iso639Id></languageList>
</configItem></layout>
<layout><configItem><name>custom</name></configItem></layout>
</layoutList></xkbConfigRegistry>"""


@pytest.fixture
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "evdev.xml"
    path.write_text(REGISTRY)
    monkeypatch.setattr(spelling, "XKB_REGISTRY", path)
    spelling._layout_languages.cache_clear()
    yield
    spelling._layout_languages.cache_clear()


@pytest.fixture
def dic_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "hunspell"
    directory.mkdir()
    monkeypatch.setattr(spelling, "DICTIONARY_DIRS", (directory,))
    return directory


def add_dictionary(directory: Path, name: str) -> Path:
    (directory / f"{name}.aff").write_text("SET UTF-8\n")
    dic = directory / f"{name}.dic"
    dic.write_text("0\n")
    return dic


@pytest.mark.usefixtures("registry")
def test_layout_language_from_xkb_registry() -> None:
    assert spelling.layout_language("ua") == "uk"
    assert spelling.layout_language("us") == "en"
    assert spelling.layout_language("custom") is None
    assert spelling.layout_language("unknown") is None


def test_prefers_layout_country(dic_dir: Path) -> None:
    add_dictionary(dic_dir, "en_GB")
    us = add_dictionary(dic_dir, "en_US")
    assert spelling.find_dictionary("en", "us") == us
    assert spelling.find_dictionary("en", "gb") == dic_dir / "en_GB.dic"


def test_falls_back_to_any_variant_of_language(dic_dir: Path) -> None:
    ua = add_dictionary(dic_dir, "uk_UA")
    assert spelling.find_dictionary("uk", "ua") == ua
    assert spelling.find_dictionary("de", "de") is None


def test_needs_aff_next_to_dic(dic_dir: Path) -> None:
    (dic_dir / "ru_RU.dic").write_text("0\n")
    assert spelling.find_dictionary("ru", "ru") is None


def test_real_dictionary_if_installed() -> None:
    dic = Path("/usr/share/hunspell/ru_RU.dic")
    if not dic.is_file():
        pytest.skip("hunspell-ru is not installed")
    dictionary = spelling.Dictionary(dic)
    assert dictionary.knows("Привет")
    assert not dictionary.knows("руддщ")
    assert not dictionary.knows("hello")


def test_layout_title_falls_back_to_the_short_name() -> None:
    from ntrcn.layouts import Layout

    assert Layout("epo", "", "EO").title == "EO"
    assert Layout("us", "", "EN", "English (US)").title  # translated or as is
