"""A tray icon over D-Bus: StatusNotifierItem with a com.canonical.dbusmenu menu.

Qt's QSystemTrayIcon cannot set a tooltip subtitle or react to the mouse wheel, so ntrcn
speaks the protocols that KDE's own tray items use.
"""

from __future__ import annotations

import logging
import os
import sys
from array import array
from collections.abc import Callable
from typing import Any, NamedTuple

import dbus
import dbus.service
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QIcon, QImage

logger = logging.getLogger(__name__)

WATCHER = "org.kde.StatusNotifierWatcher"
_ITEM_INTERFACE = "org.kde.StatusNotifierItem"
_MENU_INTERFACE = "com.canonical.dbusmenu"
_PROPERTIES = "org.freedesktop.DBus.Properties"
_ITEM_PATH = "/StatusNotifierItem"
_MENU_PATH = "/MenuBar"
_ICON_SIZE = 64
_MENU_ICON_SIZE = 22


class MenuItem(NamedTuple):
    """One menu entry; an entry without a label is a separator."""

    label: str = ""
    action: Callable[[], None] | None = None
    icon_name: str = ""
    icon: QIcon | None = None
    checked: bool | None = None  # radio item when not None


def _pixmap(image: QImage) -> dbus.Struct:
    """Image as the protocol's (width, height, ARGB32 in network byte order)."""
    argb = image.convertToFormat(QImage.Format.Format_ARGB32)
    pixels = array("I", bytes(argb.constBits()))
    if sys.byteorder == "little":
        pixels.byteswap()
    return dbus.Struct(
        (argb.width(), argb.height(), dbus.ByteArray(pixels.tobytes())), signature="iiay"
    )


def _png(icon: QIcon) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    icon.pixmap(_MENU_ICON_SIZE, _MENU_ICON_SIZE).save(buffer, "PNG")
    return bytes(buffer.data().data())


def _menu_properties(item: MenuItem) -> dict[str, Any]:
    if not item.label:
        return {"type": "separator"}
    props: dict[str, Any] = {"label": item.label}
    if item.icon is not None:
        props["icon-data"] = dbus.ByteArray(_png(item.icon))
    elif item.icon_name:
        props["icon-name"] = item.icon_name
    if item.checked is not None:
        props["toggle-type"] = "radio"
        props["toggle-state"] = dbus.Int32(1 if item.checked else 0)
    return props


class _Menu(dbus.service.Object):  # type: ignore[misc]
    """com.canonical.dbusmenu: a flat menu, ids 1..n, root 0."""

    def __init__(self, bus: dbus.Bus) -> None:
        super().__init__(bus, _MENU_PATH)
        self.items: list[MenuItem] = []
        self.revision = 1

    def set_items(self, items: list[MenuItem]) -> None:
        self.items = items
        self.revision += 1
        self.LayoutUpdated(dbus.UInt32(self.revision), dbus.Int32(0))

    def _layout(self, item_id: int) -> dbus.Struct:
        if item_id == 0:
            children = [
                dbus.Struct(self._layout(i), signature="ia{sv}av", variant_level=1)
                for i in range(1, len(self.items) + 1)
            ]
            props = {"children-display": "submenu"}
            return dbus.Struct(
                (0, dbus.Dictionary(props, signature="sv"), dbus.Array(children, signature="v")),
                signature="ia{sv}av",
            )
        props = _menu_properties(self.items[item_id - 1])
        return dbus.Struct(
            (
                item_id,
                dbus.Dictionary(props, signature="sv"),
                dbus.Array([], signature="v"),
            ),
            signature="ia{sv}av",
        )

    @dbus.service.method(_MENU_INTERFACE, in_signature="iias", out_signature="u(ia{sv}av)")  # type: ignore[untyped-decorator]
    def GetLayout(self, parent: int, _depth: int, _names: list[str]) -> tuple[int, Any]:  # noqa: N802
        return dbus.UInt32(self.revision), self._layout(parent if parent else 0)

    @dbus.service.method(_MENU_INTERFACE, in_signature="aias", out_signature="a(ia{sv})")  # type: ignore[untyped-decorator]
    def GetGroupProperties(self, ids: list[int], _names: list[str]) -> list[Any]:  # noqa: N802
        return [
            dbus.Struct(
                (i, dbus.Dictionary(_menu_properties(self.items[i - 1]), signature="sv")),
                signature="ia{sv}",
            )
            for i in ids
            if 0 < i <= len(self.items)
        ]

    @dbus.service.method(_MENU_INTERFACE, in_signature="is", out_signature="v")  # type: ignore[untyped-decorator]
    def GetProperty(self, item_id: int, name: str) -> Any:  # noqa: N802
        return _menu_properties(self.items[item_id - 1]).get(name, "")

    @dbus.service.method(_MENU_INTERFACE, in_signature="isvu")  # type: ignore[untyped-decorator]
    def Event(self, item_id: int, event: str, _data: Any, _time: int) -> None:  # noqa: N802
        if event == "clicked" and 0 < item_id <= len(self.items):
            action = self.items[item_id - 1].action
            if action is not None:
                action()

    @dbus.service.method(_MENU_INTERFACE, in_signature="a(isvu)", out_signature="ai")  # type: ignore[untyped-decorator]
    def EventGroup(self, events: list[Any]) -> Any:  # noqa: N802
        for item_id, event, data, time in events:
            self.Event(item_id, event, data, time)
        return dbus.Array([], signature="i")

    @dbus.service.method(_MENU_INTERFACE, in_signature="i", out_signature="b")  # type: ignore[untyped-decorator]
    def AboutToShow(self, _item_id: int) -> bool:  # noqa: N802
        return False

    @dbus.service.method(_MENU_INTERFACE, in_signature="ai", out_signature="aiai")  # type: ignore[untyped-decorator]
    def AboutToShowGroup(self, _ids: list[int]) -> tuple[list[int], list[int]]:  # noqa: N802
        return dbus.Array([], signature="i"), dbus.Array([], signature="i")

    @dbus.service.signal(_MENU_INTERFACE, signature="ui")  # type: ignore[untyped-decorator]
    def LayoutUpdated(self, revision: int, parent: int) -> None:  # noqa: N802
        """The menu changed."""

    @dbus.service.method(_PROPERTIES, in_signature="ss", out_signature="v")  # type: ignore[untyped-decorator]
    def Get(self, _interface: str, name: str) -> Any:  # noqa: N802
        return self.GetAll(_MENU_INTERFACE)[name]

    @dbus.service.method(_PROPERTIES, in_signature="s", out_signature="a{sv}")  # type: ignore[untyped-decorator]
    def GetAll(self, _interface: str) -> Any:  # noqa: N802
        return dbus.Dictionary(
            {
                "Version": dbus.UInt32(3),
                "TextDirection": "ltr",
                "Status": "normal",
                "IconThemePath": dbus.Array([], signature="s"),
            },
            signature="sv",
        )


class _Item(dbus.service.Object):  # type: ignore[misc]
    """org.kde.StatusNotifierItem."""

    def __init__(self, bus: dbus.Bus, owner: StatusNotifierItem) -> None:
        super().__init__(bus, _ITEM_PATH)
        self._owner = owner

    @dbus.service.method(_ITEM_INTERFACE, in_signature="ii")  # type: ignore[untyped-decorator]
    def Activate(self, _x: int, _y: int) -> None:  # noqa: N802
        self._owner.on_activate()

    @dbus.service.method(_ITEM_INTERFACE, in_signature="ii")  # type: ignore[untyped-decorator]
    def SecondaryActivate(self, _x: int, _y: int) -> None:  # noqa: N802
        """Middle click: nothing to do."""

    @dbus.service.method(_ITEM_INTERFACE, in_signature="ii")  # type: ignore[untyped-decorator]
    def ContextMenu(self, _x: int, _y: int) -> None:  # noqa: N802
        """The menu is served through dbusmenu instead."""

    @dbus.service.method(_ITEM_INTERFACE, in_signature="is")  # type: ignore[untyped-decorator]
    def Scroll(self, delta: int, orientation: str) -> None:  # noqa: N802
        if orientation == "vertical" and delta:
            self._owner.on_scroll(1 if delta < 0 else -1)

    @dbus.service.signal(_ITEM_INTERFACE)  # type: ignore[untyped-decorator]
    def NewIcon(self) -> None:  # noqa: N802
        """The icon changed."""

    @dbus.service.signal(_ITEM_INTERFACE)  # type: ignore[untyped-decorator]
    def NewToolTip(self) -> None:  # noqa: N802
        """The tooltip changed."""

    @dbus.service.method(_PROPERTIES, in_signature="ss", out_signature="v")  # type: ignore[untyped-decorator]
    def Get(self, _interface: str, name: str) -> Any:  # noqa: N802
        return self.GetAll(_ITEM_INTERFACE)[name]

    @dbus.service.method(_PROPERTIES, in_signature="s", out_signature="a{sv}")  # type: ignore[untyped-decorator]
    def GetAll(self, _interface: str) -> Any:  # noqa: N802
        owner = self._owner
        no_icon = dbus.Array([], signature="(iiay)")
        icon = dbus.Array([owner.icon], signature="(iiay)") if owner.icon else no_icon
        tooltip = dbus.Struct(("", no_icon, owner.title, owner.subtitle), signature="sa(iiay)ss")
        return dbus.Dictionary(
            {
                "Category": "Hardware",
                "Id": owner.item_id,
                "Title": owner.item_id,
                "Status": "Active",
                "WindowId": dbus.Int32(0),
                "IconName": "",
                "IconPixmap": icon,
                "ToolTip": tooltip,
                "ItemIsMenu": False,
                "Menu": dbus.ObjectPath(_MENU_PATH),
            },
            signature="sv",
        )


class StatusNotifierItem:
    """A tray item: icon, two-line tooltip, menu, click and wheel handlers."""

    def __init__(
        self,
        bus: dbus.Bus,
        item_id: str,
        on_activate: Callable[[], None],
        on_scroll: Callable[[int], None],
    ) -> None:
        """Prepare the item; :meth:`show` puts it into the tray.

        Args:
            bus: Session bus with the GLib main loop.
            item_id: Application id shown to the tray.
            on_activate: Left click.
            on_scroll: Mouse wheel, called with +1 (down) or -1 (up).
        """
        self._bus = bus
        self.item_id = item_id
        self.on_activate = on_activate
        self.on_scroll = on_scroll
        self.icon: dbus.Struct | None = None
        self.title = ""
        self.subtitle = ""
        self._service: dbus.service.BusName | None = None
        self._item: _Item | None = None
        self._menu: _Menu | None = None
        self._menu_items: list[MenuItem] = []
        # Plasma restarting the tray drops registrations; register again then.
        bus.add_signal_receiver(
            self._on_watcher_changed,
            "NameOwnerChanged",
            "org.freedesktop.DBus",
            arg0=WATCHER,
        )

    @property
    def visible(self) -> bool:
        """Tell whether the item is in the tray."""
        return self._item is not None

    def show(self) -> None:
        """Publish the item and register it with the tray."""
        if self._item is not None:
            return
        name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._service = dbus.service.BusName(name, self._bus)
        self._item = _Item(self._bus, self)
        self._menu = _Menu(self._bus)
        self._menu.set_items(self._menu_items)
        self._register()

    def hide(self) -> None:
        """Remove the item from the tray."""
        if self._item is None:
            return
        self._item.remove_from_connection()
        if self._menu is not None:
            self._menu.remove_from_connection()
        self._item = self._menu = None
        self._service = None  # releases the bus name

    def set_icon(self, icon: QIcon) -> None:
        """Show ``icon`` in the tray."""
        self.icon = _pixmap(icon.pixmap(_ICON_SIZE, _ICON_SIZE).toImage())
        if self._item is not None:
            self._item.NewIcon()

    def set_tooltip(self, title: str, subtitle: str) -> None:
        """Set the tooltip: a bold title and a line below it."""
        self.title, self.subtitle = title, subtitle
        if self._item is not None:
            self._item.NewToolTip()

    def set_menu(self, items: list[MenuItem]) -> None:
        """Replace the menu."""
        self._menu_items = items
        if self._menu is not None:
            self._menu.set_items(items)

    def _register(self) -> None:
        if self._service is None:
            return
        try:
            watcher = self._bus.get_object(WATCHER, "/StatusNotifierWatcher")
            watcher.RegisterStatusNotifierItem(self._service.get_name(), dbus_interface=WATCHER)
        except dbus.DBusException as err:
            logger.warning("No system tray to show the indicator in: %s", err)

    def _on_watcher_changed(self, _name: str, _old: str, new: str) -> None:
        if new:
            self._register()


def tray_available(bus: dbus.Bus) -> bool:
    """Tell whether a system tray is running."""
    return bool(bus.name_has_owner(WATCHER))
