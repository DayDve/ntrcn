"""Downloading hunspell dictionaries from the LibreOffice dictionaries repository."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from ntrcn.spelling import USER_DICTIONARY_DIR, locale_name

logger = logging.getLogger(__name__)

BASE_URL = "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/"
# Dictionaries that do not follow the repository's usual <ll_CC>/<ll_CC> layout.
_IRREGULAR_PATHS = {
    "en": "en/en_US",
    "de": "de/de_DE_frami",
    "es": "es/es_ES",
    "be": "be_BY/be-official",
    "fr": "fr_FR/dictionaries/fr",
}
SUFFIXES = (".aff", ".dic")

#: Called with ``None`` on success or with an error message.
DoneCallback = Callable[[str | None], None]


def source_path(language: str) -> str:
    """Return the repository path of a dictionary without the file extension."""
    name = locale_name(language)
    return _IRREGULAR_PATHS.get(language, f"{name}/{name}")


def save_dictionary(language: str, files: dict[str, bytes], directory: Path) -> Path:
    """Write the downloaded ``.aff`` and ``.dic`` as ``<ll_CC>`` and return the ``.dic``."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / locale_name(language)
    for suffix in SUFFIXES:
        temporary = target.with_suffix(suffix + ".part")
        temporary.write_bytes(files[suffix])
        temporary.replace(target.with_suffix(suffix))
    return target.with_suffix(".dic")


class DictionaryDownloader:
    """Fetches dictionaries in the background with Qt networking."""

    def __init__(self, base_url: str = BASE_URL, directory: Path = USER_DICTIONARY_DIR) -> None:
        """Prepare to download from ``base_url`` into ``directory``."""
        self._base_url = base_url
        self._directory = directory
        self._network = QNetworkAccessManager()
        # Qt deletes every reply after it finished. Replies are handled through the
        # manager's signal: slots that capture the reply itself crash PySide.
        self._network.setAutoDeleteReplies(True)
        self._network.finished.connect(self._received)
        # URL being fetched -> (language, files fetched so far, callback).
        self._pending: dict[str, tuple[str, dict[str, bytes], DoneCallback]] = {}

    def download(self, language: str, on_done: DoneCallback) -> None:
        """Download the dictionary of ``language``; ``on_done`` is called when finished."""
        self._fetch(language, {}, on_done)

    def _fetch(self, language: str, files: dict[str, bytes], on_done: DoneCallback) -> None:
        suffix = SUFFIXES[len(files)]
        url = QUrl(self._base_url + source_path(language) + suffix)
        self._pending[url.toString()] = (language, files, on_done)
        self._network.get(QNetworkRequest(url))

    def _received(self, reply: QNetworkReply) -> None:
        language, files, on_done = self._pending.pop(reply.url().toString())
        data = bytes(reply.readAll().data())
        if reply.error() != QNetworkReply.NetworkError.NoError:
            logger.warning("Downloading %s failed: %s", reply.url().toString(), reply.errorString())
            on_done(f"Не удалось скачать словарь: {reply.errorString()}")
            return
        if not data or data.lstrip().startswith(b"<"):  # an HTML page instead of a dictionary
            on_done("Не удалось скачать словарь: сервер вернул не словарь")
            return
        files[SUFFIXES[len(files)]] = data
        if len(files) < len(SUFFIXES):
            self._fetch(language, files, on_done)
            return
        try:
            path = save_dictionary(language, files, self._directory)
        except OSError as err:
            on_done(f"Не удалось сохранить словарь: {err}")
            return
        logger.info("Downloaded the %s dictionary to %s", language, path)
        on_done(None)
