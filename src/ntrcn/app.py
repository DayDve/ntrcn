"""The ntrcn session: wires input, conversion, tray and settings together."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
from collections.abc import Callable

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from evdev import ecodes as e
from PySide6.QtCore import QFileSystemWatcher, QLibraryInfo, QLocale, QTimer, QTranslator
from PySide6.QtWidgets import QApplication

from ntrcn import APP_ID, __version__
from ntrcn.appicon import app_icon
from ntrcn.config import Config, load_config, save_config
from ntrcn.converter import Converter
from ntrcn.flags import USER_FLAGS_DIR
from ntrcn.keys import key_code
from ntrcn.layouts import KdeLayouts
from ntrcn.settings import SettingsDialog
from ntrcn.sound import chosen_sound, play
from ntrcn.spelling import speller_for
from ntrcn.tray import Tray
from ntrcn.typer import Typer
from ntrcn.watcher import InputWatcher

logger = logging.getLogger(__name__)

BUS_NAME = APP_ID
OBJECT_PATH = "/" + APP_ID.replace(".", "/")


class _Service(dbus.service.Object):  # type: ignore[misc]
    """D-Bus object that lets a second ``ntrcn`` launch open the settings of the first."""

    def __init__(self, bus: dbus.Bus, show_settings: Callable[[], None]) -> None:
        super().__init__(bus, OBJECT_PATH)
        self._show_settings = show_settings

    @dbus.service.method(BUS_NAME)  # type: ignore[untyped-decorator]
    def ShowSettings(self) -> None:  # noqa: N802 - D-Bus method name
        self._show_settings()


class Session:
    """The running application: converter, tray, settings, and applying the config to them."""

    def __init__(self, bus: dbus.Bus, typer: Typer) -> None:
        """Start converting and show the tray icon."""
        self.config = load_config()
        kde = KdeLayouts(bus)
        self.tray = Tray(bus, kde.set, self.show_settings)
        self.watcher = InputWatcher()
        self.converter = Converter(
            kde,
            typer,
            held_keys=self.watcher.held_keys,
            on_layouts_changed=self.tray.update,
            on_convert=self._on_convert,
            speller=speller_for,
        )
        for layout in self.converter.layouts:  # load dictionaries now, not on the first hotkey
            speller_for(layout.name)
        self.watcher.key_pressed.connect(self.converter.on_key_press)
        self.watcher.clicked.connect(self.converter.buffer.reset)
        self._settings: SettingsDialog | None = None
        self._service = _Service(bus, self.show_settings)
        # Redraw the icon when flag pictures are added, replaced or removed.
        USER_FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        self._flags_watcher = QFileSystemWatcher([str(USER_FLAGS_DIR)])
        self._flags_watcher.directoryChanged.connect(lambda _path: self._apply())
        self._apply()

    def _apply(self) -> None:
        hotkey = key_code(self.config.hotkey)
        if hotkey is None:
            logger.warning("Unknown hotkey %r, using PAUSE", self.config.hotkey)
            hotkey = e.KEY_PAUSE
        self.converter.hotkey = hotkey
        self.tray.indicator = self.config.tray_indicator
        self.tray.text_theme = self.config.text_theme
        self.tray.app_icon_theme = self.config.app_icon_theme
        self.tray.update(self.converter.layouts, self.converter.current)

    def change_config(self, config: Config) -> None:
        """Save new settings and apply them right away."""
        self.config = config
        save_config(config)
        self._apply()

    def _on_convert(self) -> None:
        sound = chosen_sound(self.config.sound, self.config.sound_file)
        if sound:
            play(sound)

    def _capture_key(self, callback: Callable[[int], None] | None) -> None:
        self.converter.key_capture = callback

    def show_settings(self) -> None:
        """Open the settings window, or bring it to front."""
        if self._settings is None:
            self._settings = SettingsDialog(
                self.config,
                lambda: self.converter.layouts,
                self.change_config,
                self._capture_key,
            )
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()


def _become_main_instance(bus: dbus.Bus) -> bool:
    """Own the D-Bus name, or ask the running ntrcn to show its settings and return False."""
    for _attempt in range(3):
        reply = bus.request_name(BUS_NAME, dbus.bus.NAME_FLAG_DO_NOT_QUEUE)
        if reply == dbus.bus.REQUEST_NAME_REPLY_PRIMARY_OWNER:
            return True
        try:
            bus.get_object(BUS_NAME, OBJECT_PATH).ShowSettings(dbus_interface=BUS_NAME)
        except dbus.DBusException:
            logger.info("The running ntrcn has just quit, taking over")
            continue
        print("ntrcn is already running, opened its settings")
        return False
    raise SystemExit("ntrcn: another instance holds the D-Bus name and does not respond")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ntrcn",
        description="Retype text typed in the wrong keyboard layout (Pause) or the selection "
        "(Shift+Pause). For KDE Plasma 6 on Wayland. Settings are in the tray menu; "
        "starting ntrcn again while it runs opens them.",
    )
    parser.add_argument("--settings", action="store_true", help="open the settings window")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run ntrcn until the session ends or it is quit from the tray."""
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    if not _become_main_instance(bus):
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName("ntrcn")
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    # Translations of Qt's own strings such as the "Close" button.
    translator = QTranslator(app)
    if translator.load(
        QLocale(), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    ):
        app.installTranslator(translator)
    try:
        typer = Typer()
    except OSError as err:
        print(f"ntrcn: cannot create a virtual keyboard: {err}", file=sys.stderr)
        return 1
    session = Session(bus, typer)
    if args.settings:
        session.show_settings()

    # Let Python see Ctrl+C: Qt only yields to the interpreter between events.
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    heartbeat = QTimer(interval=200)
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start()

    logger.info("ntrcn %s started, hotkey %s", __version__, session.config.hotkey)
    try:
        return app.exec()
    finally:
        typer.close()
