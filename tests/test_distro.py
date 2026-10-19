from pathlib import Path

import pytest

from ntrcn.distro import dictionary_package, distro_family, install_hint


@pytest.mark.parametrize(
    ("os_release", "family"),
    [
        ("ID=ubuntu\nID_LIKE=debian\n", "debian"),
        ('ID=linuxmint\nID_LIKE="ubuntu debian"\n', "debian"),
        ("ID=debian\n", "debian"),
        ("ID=fedora\n", "fedora"),
        ('ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n', "suse"),
        ("ID=manjaro\nID_LIKE=arch\n", "arch"),
        ("ID=gentoo\n", None),
    ],
)
def test_distro_family(tmp_path: Path, os_release: str, family: str | None) -> None:
    path = tmp_path / "os-release"
    path.write_text(os_release)
    assert distro_family(path) == family


def test_missing_os_release(tmp_path: Path) -> None:
    assert distro_family(tmp_path / "none") is None


@pytest.mark.parametrize(
    ("language", "family", "package"),
    [
        ("ru", "debian", "hunspell-ru"),
        ("en", "debian", "hunspell-en-us"),
        ("de", "debian", "hunspell-de-de"),
        ("uk", "fedora", "hunspell-uk"),
        ("uk", "suse", "myspell-uk_UA"),
        ("be", "suse", "myspell-be_BY"),
        ("en", "arch", "hunspell-en_us"),
        ("fr", "arch", "hunspell-fr-classical"),
        ("pl", "arch", "hunspell-pl"),
    ],
)
def test_dictionary_package(language: str, family: str, package: str) -> None:
    assert dictionary_package(language, family) == package


def test_install_hints() -> None:
    assert install_hint("uk", "debian") == "sudo apt install hunspell-uk"
    assert install_hint("uk", "suse") == "sudo zypper install myspell-uk_UA"
    assert "AUR" in install_hint("uk", "arch")
    assert "hunspell" in install_hint("uk", None)
