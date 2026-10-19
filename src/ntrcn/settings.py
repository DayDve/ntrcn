"""Settings window. Every change is applied and saved immediately."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from evdev import ecodes as e
from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QHideEvent, QIcon, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ntrcn import __version__, autostart
from ntrcn.appicon import app_icon
from ntrcn.config import APP_ICON_THEMES, SOUND_MODES, TEXT_THEMES, TRAY_INDICATORS, Config
from ntrcn.diagnostics import run_checks
from ntrcn.download import DictionaryDownloader
from ntrcn.flags import (
    USER_FLAGS_DIR,
    custom_flag,
    layout_icon,
    remove_custom_flag,
    set_custom_flag,
)
from ntrcn.keys import CHAR_KEYS, key_name
from ntrcn.layouts import Layout
from ntrcn.sound import MAX_SECONDS, chosen_sound, play
from ntrcn.spelling import forget_dictionaries

REPO_URL = "https://github.com/DayDve/ntrcn"
# Keys that are needed for typing and editing, so they cannot be the hotkey.
_TYPING_KEYS = CHAR_KEYS | {e.KEY_BACKSPACE, e.KEY_ENTER, e.KEY_TAB}
_FLAG_ICON_SIZE = QSize(32, 32)
_SIDEBAR_ICON_SIZE = QSize(48, 48)
_SIDEBAR_ITEM_SIZE = QSize(116, 84)
_PAGE_WIDTH = 560

KeyCapture = Callable[[Callable[[int], None] | None], None]


def _open_flags_folder() -> None:
    USER_FLAGS_DIR.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(USER_FLAGS_DIR)))


def _key_title(name: str) -> str:
    return name.replace("_", " ").title()


def _page(title: str, *items: QWidget | QLayout) -> QScrollArea:
    """A page in the Plasma style: a title and the content in a centred column."""
    heading = QLabel(title)
    font = heading.font()
    font.setPointSizeF(font.pointSizeF() * 1.4)
    heading.setFont(font)
    column = QVBoxLayout()
    column.setSpacing(12)
    column.addWidget(heading)
    for item in items:
        if isinstance(item, QLayout):
            column.addLayout(item)
        else:
            column.addWidget(item)
    column.addStretch()
    body = QWidget()
    body.setMaximumWidth(_PAGE_WIDTH)
    body.setLayout(column)
    page = QWidget()
    centred = QHBoxLayout(page)  # the column grows up to _PAGE_WIDTH, the rest goes to margins
    centred.addStretch(1)
    centred.addWidget(body, 100)
    centred.addStretch(1)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(page)
    return scroll


def _form() -> QFormLayout:
    """A form with labels aligned to the right, against their fields."""
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    return form


def _section(title: str) -> QLabel:
    """A bold section title, used instead of a framed group box."""
    label = QLabel(f"<b>{title}</b>")
    label.setContentsMargins(0, 8, 0, 0)
    return label


def _note(text: str) -> QLabel:
    """Explanatory text in the theme's dimmed text colour."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setEnabled(False)
    return label


def _clear(layout: QLayout) -> None:
    """Remove and delete everything in a layout, including nested layouts."""
    while (item := layout.takeAt(0)) is not None:
        if (widget := item.widget()) is not None:
            widget.deleteLater()
        elif (inner := item.layout()) is not None:
            _clear(inner)


def _left(*widgets: QWidget) -> QHBoxLayout:
    """Put widgets in a row aligned to the left."""
    row = QHBoxLayout()
    for widget in widgets:
        row.addWidget(widget)
    row.addStretch()
    return row


class SettingsDialog(QDialog):
    """Settings window: sections on the left, the chosen one on the right."""

    def __init__(
        self,
        config: Config,
        layouts: Callable[[], list[Layout]],
        on_change: Callable[[Config], None],
        capture_key: KeyCapture,
    ) -> None:
        """Build the window.

        Args:
            config: Current settings.
            layouts: Returns the layouts currently configured in Plasma.
            on_change: Receives the new settings after every change.
            capture_key: Routes the next physical key press to the given callback
                (or stops doing so when given ``None``), to pick a hotkey.
        """
        super().__init__()
        self._config = config
        self._layouts = layouts
        self._on_change = on_change
        self._capture_key = capture_key
        self._downloader = DictionaryDownloader()
        self.setWindowTitle("Настройки ntrcn")
        self.setWindowIcon(app_icon())
        self.resize(860, 560)

        pages = QStackedWidget()
        # Large icons with the title below, like the settings of KDE applications.
        sidebar = QListWidget()
        sidebar.setViewMode(QListWidget.ViewMode.IconMode)
        sidebar.setFlow(QListWidget.Flow.TopToBottom)
        sidebar.setMovement(QListWidget.Movement.Static)
        sidebar.setWrapping(False)
        sidebar.setIconSize(_SIDEBAR_ICON_SIZE)
        sidebar.setGridSize(_SIDEBAR_ITEM_SIZE)
        sidebar.setFixedWidth(_SIDEBAR_ITEM_SIZE.width())
        sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar.setFrameShape(QFrame.Shape.NoFrame)
        for icon, title, page in (
            ("preferences-desktop-keyboard", "Основные", self._general_page()),
            ("preferences-desktop-plasma", "Индикатор", self._indicator_page()),
            ("preferences-smart-status", "Диагностика", self._diagnostics_page()),
            ("help-about", "О программе", self._about_page()),
        ):
            item = QListWidgetItem(QIcon.fromTheme(icon), title, sidebar)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setSizeHint(_SIDEBAR_ITEM_SIZE)  # equal cells keep icons centred
            pages.addWidget(page)
        sidebar.currentRowChanged.connect(pages.setCurrentIndex)
        sidebar.setCurrentRow(0)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar)
        layout.addWidget(separator)
        layout.addWidget(pages, 1)

    def _change(self, **changes: object) -> None:
        self._config = replace(self._config, **changes)  # type: ignore[arg-type]
        self._on_change(self._config)

    def _choice(self, options: dict[str, str], setting: str) -> QComboBox:
        """A list of ``options`` (key -> title) bound to the setting with that name."""
        box = QComboBox()
        for key, title in options.items():
            box.addItem(title, key)
        box.setCurrentIndex(max(box.findData(getattr(self._config, setting)), 0))
        box.currentIndexChanged.connect(lambda _: self._change(**{setting: box.currentData()}))
        return box

    # --- General ---------------------------------------------------------------------

    def _general_page(self) -> QWidget:
        self._word_hotkey = QLabel()
        self._selection_hotkey = QLabel()
        self._hotkey_button = QPushButton()
        self._hotkey_button.clicked.connect(self._start_hotkey_capture)
        self._hotkey_error = QLabel()
        self._hotkey_error.setStyleSheet("color: #da4453")
        self._show_hotkey()
        self._sound = self._choice(SOUND_MODES, "sound")
        self._sound_file = QPushButton(QIcon.fromTheme("document-open"), "")
        self._sound_file.clicked.connect(self._choose_sound_file)
        self._listen = QPushButton(QIcon.fromTheme("media-playback-start"), "")
        self._listen.setToolTip("Прослушать")
        self._listen.clicked.connect(self._play_sound)
        self._sound_note = _note(f"Звук длиннее {MAX_SECONDS} секунд обрывается.")
        self._sound_note.setWordWrap(False)
        self._sound.currentIndexChanged.connect(self._show_sound_controls)
        self._show_sound_controls()
        start = QCheckBox("Запускать при входе в систему")
        start.setChecked(autostart.is_enabled())
        start.toggled.connect(autostart.set_enabled)

        form = _form()
        form.addRow("Исправить набранное:", self._word_hotkey)
        form.addRow("Исправить выделенное:", self._selection_hotkey)
        form.addRow("", self._hotkey_button)
        form.addRow("", self._hotkey_error)
        form.addRow("Звук при исправлении:", _left(self._sound, self._sound_file, self._listen))
        form.addRow("", self._sound_note)
        form.addRow("Автозапуск:", start)
        return _page("Основные", form)

    def _show_hotkey(self) -> None:
        title = _key_title(self._config.hotkey)
        self._word_hotkey.setText(f"<b>{title}</b>")
        self._selection_hotkey.setText(f"<b>Shift+{title}</b>")
        self._hotkey_button.setText("Изменить клавишу…")
        self._hotkey_button.setEnabled(True)

    def _start_hotkey_capture(self) -> None:
        self._hotkey_error.clear()
        self._hotkey_button.setText("Нажмите клавишу… (Esc — отмена)")
        self._hotkey_button.setEnabled(False)
        self._capture_key(self._on_key_captured)

    def _on_key_captured(self, code: int) -> None:
        if code in _TYPING_KEYS:
            self._hotkey_error.setText(
                f"{_key_title(key_name(code))} нужна для набора текста, выберите другую"
            )
        elif code != e.KEY_ESC:  # Esc cancels
            self._change(hotkey=key_name(code))
        self._show_hotkey()

    def _show_sound_controls(self) -> None:
        custom = self._config.sound == "custom"
        self._sound_file.setVisible(custom)
        self._sound_note.setVisible(custom)
        self._sound_file.setText(Path(self._config.sound_file).name or "Выбрать файл…")
        self._listen.setEnabled(
            chosen_sound(self._config.sound, self._config.sound_file) is not None
        )

    def _choose_sound_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Звук при исправлении", str(Path.home()), "Звуки (*.oga *.ogg *.wav *.flac)"
        )
        if path:
            self._change(sound_file=path)
            self._show_sound_controls()
            self._play_sound()

    def _play_sound(self) -> None:
        sound = chosen_sound(self._config.sound, self._config.sound_file)
        if sound:
            play(sound)

    # --- Indicator -------------------------------------------------------------------

    def _indicator_page(self) -> QWidget:
        indicator = self._choice(TRAY_INDICATORS, "tray_indicator")
        text_theme = self._choice(TEXT_THEMES, "text_theme")
        app_icon_theme = self._choice(APP_ICON_THEMES, "app_icon_theme")
        self._indicator_form = form = _form()
        form.addRow("Индикатор в системном трее:", indicator)
        form.addRow("Тема значка:", text_theme)
        form.addRow("Тема значка:", app_icon_theme)
        hint = _note(
            "Без индикатора настройки открываются повторным запуском ntrcn из меню приложений "
            "или пунктом «Настройки» в контекстном меню его ярлыка."
        )

        def show_relevant_rows() -> None:
            kind = indicator.currentData()
            form.setRowVisible(text_theme, kind in ("text", "flag_text"))
            form.setRowVisible(app_icon_theme, kind == "app_icon")
            hint.setVisible(kind == "none")

        indicator.currentIndexChanged.connect(show_relevant_rows)
        show_relevant_rows()

        self._flags_form = _form()
        custom = _note(
            "Картинка раскладки — файл <code>&lt;раскладка&gt;.svg</code> или "
            "<code>.png</code> в папке флагов, например <code>de.png</code>. "
            "Файлы оттуда подхватываются сразу."
        )
        open_folder = QPushButton(QIcon.fromTheme("folder-open"), "Открыть папку с флагами")
        open_folder.clicked.connect(_open_flags_folder)
        return _page(
            "Индикатор",
            form,
            hint,
            _section("Флаги раскладок"),
            self._flags_form,
            custom,
            _left(open_folder),
        )

    def _fill_flag_choices(self) -> None:
        """(Re)build one row per layout; layouts and pictures may change while ntrcn runs."""
        while self._flags_form.rowCount():
            self._flags_form.removeRow(0)
        for layout in self._layouts():
            preview = QLabel()
            preview.setPixmap(
                layout_icon(layout.name, layout.label, "flag").pixmap(_FLAG_ICON_SIZE)
            )
            choose = QPushButton(QIcon.fromTheme("document-open"), "Выбрать картинку…")
            choose.clicked.connect(lambda _=False, name=layout.name: self._choose_flag(name))
            reset = QPushButton(QIcon.fromTheme("edit-undo"), "Сбросить")
            reset.setEnabled(custom_flag(layout.name) is not None)
            reset.clicked.connect(lambda _=False, name=layout.name: self._reset_flag(name))
            self._flags_form.addRow(
                f"{layout.label} ({layout.name}):", _left(preview, choose, reset)
            )

    def _choose_flag(self, layout_name: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Картинка для раскладки {layout_name}",
            str(Path.home()),
            "Картинки (*.svg *.png)",
        )
        if path:
            set_custom_flag(layout_name, Path(path))
            self._fill_flag_choices()

    def _reset_flag(self, layout_name: str) -> None:
        remove_custom_flag(layout_name)
        self._fill_flag_choices()

    # --- Diagnostics -----------------------------------------------------------------

    def _diagnostics_page(self) -> QWidget:
        self._checks = QVBoxLayout()
        self._checks.setSpacing(8)
        self._download_error = QLabel()
        self._download_error.setStyleSheet("color: #da4453")
        self._download_error.setWordWrap(True)
        again = QPushButton(QIcon.fromTheme("view-refresh"), "Проверить снова")
        again.clicked.connect(self._recheck)
        return _page("Диагностика", self._checks, self._download_error, _left(again))

    def _recheck(self) -> None:
        """Check again, picking up dictionaries installed meanwhile."""
        forget_dictionaries()
        self._run_checks()

    def _run_checks(self) -> None:
        _clear(self._checks)
        for check in run_checks(self._layouts()):
            mark = QLabel()
            mark.setPixmap(QIcon.fromTheme("data-success" if check.ok else "data-error").pixmap(16))
            hint = "" if check.ok else f"<br><small>{check.hint}</small>"
            label = QLabel(f"{check.title}{hint}")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row = QHBoxLayout()
            row.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(label, 1)
            self._checks.addLayout(row)
            if check.download:
                button = QPushButton(QIcon.fromTheme("download"), "Скачать словарь")
                button.clicked.connect(
                    lambda _=False, lang=check.download, b=button: self._download(lang, b)
                )
                self._checks.addLayout(_left(button))

    def _download(self, language: str, button: QPushButton) -> None:
        self._download_error.clear()
        button.setEnabled(False)
        button.setText("Скачивание…")
        self._downloader.download(language, self._on_downloaded)

    def _on_downloaded(self, error: str | None) -> None:
        if error:
            self._download_error.setText(error)
        self._recheck()

    # --- About -----------------------------------------------------------------------

    def _about_page(self) -> QWidget:
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(96))
        name = QLabel(
            f"<span style='font-size: 20pt; font-weight: 600'>ntrcn</span><br>Версия {__version__}"
        )
        header = _left(icon, name)
        header.setSpacing(16)
        description = QLabel(
            "Исправляет текст, набранный не в той раскладке, в KDE Plasma 6 на Wayland."
        )
        description.setWordWrap(True)
        form = _form()
        for title, html in (
            ("Сайт:", f"<a href='{REPO_URL}'>{REPO_URL.removeprefix('https://')}</a>"),
            ("Лицензия:", "MIT"),
            ("Флаги:", "<a href='https://vlags.com'>vlags.com</a>"),
            (
                "Словари:",
                "<a href='https://github.com/LibreOffice/dictionaries'>LibreOffice</a>",
            ),
        ):
            value = QLabel(html)
            value.setOpenExternalLinks(True)
            form.addRow(title, value)
        return _page("О программе", header, description, form)

    # --- Window events ---------------------------------------------------------------

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt override
        """Refresh what may have changed while the window was hidden."""
        self._fill_flag_choices()
        self._run_checks()
        super().showEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802 - Qt override
        """Stop waiting for a hotkey when the window goes away."""
        self._capture_key(None)
        self._show_hotkey()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        """Only hide: the window is reused next time."""
        event.ignore()
        self.hide()
