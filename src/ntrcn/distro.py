"""Which Linux distribution family this is, and how to install a dictionary there."""

from __future__ import annotations

from pathlib import Path

from ntrcn.spelling import locale_name

OS_RELEASE = Path("/etc/os-release")

# os-release ID / ID_LIKE word -> family. Derivatives (Mint, neon, Manjaro...) list their
# parent in ID_LIKE.
_FAMILIES = {
    "debian": "debian",
    "ubuntu": "debian",
    "fedora": "fedora",
    "suse": "suse",
    "opensuse": "suse",
    "arch": "arch",
}
_INSTALL = {
    "debian": "sudo apt install {}",
    "fedora": "sudo dnf install {}",
    "suse": "sudo zypper install {}",
    "arch": "sudo pacman -S {}",
}
# Packages that do not follow the family's naming rule (checked against the repositories).
_DEBIAN_PACKAGES = {"en": "hunspell-en-us", "de": "hunspell-de-de"}
_ARCH_PACKAGES = {"en": "hunspell-en_us", "es": "hunspell-es_es", "fr": "hunspell-fr-classical"}
_ARCH_AUR_ONLY = {"uk", "be"}


def distro_family(os_release: Path = OS_RELEASE) -> str | None:
    """Return ``debian``, ``fedora``, ``suse``, ``arch`` or ``None`` for anything else."""
    try:
        lines = os_release.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    values = dict(line.split("=", 1) for line in lines if "=" in line)
    words = [values.get("ID", ""), *values.get("ID_LIKE", "").split()]
    for word in words:
        family = _FAMILIES.get(word.strip().strip('"'))
        if family:
            return family
    return None


def dictionary_package(language: str, family: str) -> str:
    """Return the name of the hunspell dictionary package for a language."""
    if family == "suse":
        return f"myspell-{locale_name(language)}"
    if family == "debian":
        return _DEBIAN_PACKAGES.get(language, f"hunspell-{language}")
    if family == "arch":
        return _ARCH_PACKAGES.get(language, f"hunspell-{language}")
    return f"hunspell-{language}"


def install_command(package: str, family: str | None) -> str | None:
    """Return the command that installs a package, or ``None`` on an unknown system."""
    return _INSTALL[family].format(package) if family else None


def install_hint(language: str, family: str | None) -> str:
    """Tell how to install the dictionary for a language on this system."""
    if family is None:
        return f"Установите словарь hunspell для языка «{language}» через менеджер пакетов"
    package = dictionary_package(language, family)
    if family == "arch" and language in _ARCH_AUR_ONLY:
        return f"Установите пакет {package} из AUR"
    return install_command(package, family) or package
