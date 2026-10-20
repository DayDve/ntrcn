import os
from collections.abc import Iterator

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Tests check the untranslated (English) strings, whatever the language of the machine.
os.environ["LANGUAGE"] = "C"
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qt_app() -> Iterator[QApplication]:
    """One QApplication for all tests that need Qt objects or its event loop."""
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    yield app
