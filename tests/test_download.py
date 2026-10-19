from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer, QUrl

from ntrcn.download import DictionaryDownloader, save_dictionary, source_path


@pytest.mark.parametrize(
    ("language", "path"),
    [("ru", "ru_RU/ru_RU"), ("uk", "uk_UA/uk_UA"), ("en", "en/en_US"), ("be", "be_BY/be-official")],
)
def test_source_path(language: str, path: str) -> None:
    assert source_path(language) == path


def test_save_names_files_by_locale(tmp_path: Path) -> None:
    dic = save_dictionary("be", {".aff": b"SET UTF-8\n", ".dic": "1\nслова\n".encode()}, tmp_path)
    assert dic == tmp_path / "be_BY.dic"
    assert (tmp_path / "be_BY.aff").read_bytes() == b"SET UTF-8\n"
    assert not list(tmp_path.glob("*.part"))


def run_download(base: Path, target: Path, language: str) -> str | None:
    """Download from a local folder through file:// URLs and wait for the result."""
    results: list[str | None] = []
    loop = QEventLoop()
    downloader = DictionaryDownloader(QUrl.fromLocalFile(str(base)).toString() + "/", target)
    downloader.download(language, lambda error: (results.append(error), loop.quit()))
    QTimer.singleShot(5000, loop.quit)
    loop.exec()
    assert results, "download did not finish"
    return results[0]


@pytest.mark.usefixtures("qt_app")
def test_download_from_repository_layout(tmp_path: Path) -> None:
    source = tmp_path / "repo" / "uk_UA"
    source.mkdir(parents=True)
    (source / "uk_UA.aff").write_text("SET UTF-8\n")
    (source / "uk_UA.dic").write_text("1\nпривіт\n")
    assert run_download(tmp_path / "repo", tmp_path / "out", "uk") is None
    assert (tmp_path / "out" / "uk_UA.dic").read_text() == "1\nпривіт\n"


@pytest.mark.usefixtures("qt_app")
def test_missing_dictionary_reports_error(tmp_path: Path) -> None:
    (tmp_path / "repo").mkdir()
    error = run_download(tmp_path / "repo", tmp_path / "out", "uk")
    assert error
    assert not (tmp_path / "out" / "uk_UA.dic").exists()


@pytest.mark.usefixtures("qt_app")
def test_html_instead_of_dictionary_is_an_error(tmp_path: Path) -> None:
    source = tmp_path / "repo" / "uk_UA"
    source.mkdir(parents=True)
    (source / "uk_UA.aff").write_text("<!doctype html><p>Not found</p>")
    assert run_download(tmp_path / "repo", tmp_path / "out", "uk")
