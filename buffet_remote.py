#!/usr/bin/python3
"""Buffet menu for another application's window: a proof of concept.

Shows the menus of the active window as a buffet menu, under its title bar, and runs the item you
choose in that application. The application itself doesn't change: its GTK menu bar is published on
D-Bus by appmenu-gtk-module, the GTK module that global menu panels use.

    sudo apt install appmenu-gtk3-module
    python3 buffet_remote.py --registrar &      first: hide the menu bars of applications started with the module
    GTK_MODULES=appmenu-gtk-module xed &        start Xed with the module
    python3 buffet_remote.py                    show the active window's menus (give this a keyboard shortcut)
    python3 buffet_remote.py --window 0x3a00007 or of a given window, by its X11 id (as xprop or wmctrl -l show it)
    sleep 3; python3 buffet_remote.py --dump    print what the active window sends: its menus, with their shortcuts

The layout and keyboard shortcut settings are the ones set in buffet_menu_test.py (Edit → Preferences).
"""

import argparse
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffet_menu_test as buffet  # noqa: E402  (sets up the GTK versions)

import gi  # noqa: E402
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11, Gio, GLib  # noqa: E402

# How long to wait for the application to send its whole menu, in seconds
LOAD_TIMEOUT = 2.0
# How long to wait, at most, for the application to answer, in seconds
REFRESH_TIME = 0.1
# A menu is converted again after this long anyway, even if the application sent no change, in seconds
CONVERTED_TIME = 30
# appmenu-gtk-module hides an application's menu bar while a program owns this name on D-Bus, and shows it
# again when the name is let go. It doesn't need anything else from that program.
REGISTRAR_NAME = "com.canonical.AppMenu.Registrar"
# Where the header bar module keeps the position of a window's header bar and Buffet button
HEADER_PROPERTY = "_BUFFET_MENU_HEADER"
# Where it keeps the keyboard shortcuts the application registered with GTK, as "action=shortcut|…"
ACCELS_PROPERTY = "_BUFFET_MENU_ACCELS"
# And those its menu bar's items show, by their labels: "File\x1fSave\t<Primary>s", one a line
LABEL_ACCELS_PROPERTY = "_BUFFET_MENU_LABEL_ACCELS"


def run_registrar():
    """Keeps the menu bars of the applications started with the module hidden, until stopped."""
    loop = GLib.MainLoop()

    def on_name_lost(_connection, _name):
        print("Another program already hides the menu bars (or D-Bus isn't available)", file=sys.stderr)
        loop.quit()

    Gio.bus_own_name(Gio.BusType.SESSION, REGISTRAR_NAME, Gio.BusNameOwnerFlags.NONE, None, None, on_name_lost)
    loop.run()


class X11:
    """Reads the properties of X11 windows with libX11, in this process: much quicker than starting xprop."""

    def __init__(self):
        self.lib = ctypes.cdll.LoadLibrary("libX11.so.6")
        self.lib.XOpenDisplay.restype = ctypes.c_void_p
        self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.lib.XInternAtom.restype = ctypes.c_ulong
        self.lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        self.lib.XDefaultRootWindow.restype = ctypes.c_ulong
        self.lib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.lib.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int,
            ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p)]
        self.lib.XFree.argtypes = [ctypes.c_void_p]
        # A window that has just closed would otherwise end the program, with libX11's own error handler
        self.on_error = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(lambda _display, _error: 0)
        self.lib.XSetErrorHandler(self.on_error)
        self.display = self.lib.XOpenDisplay(None)
        self.root = self.lib.XDefaultRootWindow(self.display) if self.display else 0
        self.atoms = {}

    def atom(self, name):
        if name not in self.atoms:
            self.atoms[name] = self.lib.XInternAtom(self.display, name.encode(), False)
        return self.atoms[name]

    def get(self, window, name):
        """A property's value: bytes for text, a list of numbers for numbers and windows, or None."""
        if not self.display or not window:
            return None
        kind, size, count, after = ctypes.c_ulong(), ctypes.c_int(), ctypes.c_ulong(), ctypes.c_ulong()
        data = ctypes.c_void_p()
        # AnyPropertyType is 0; up to 64 KiB
        if self.lib.XGetWindowProperty(self.display, window, self.atom(name), 0, 16384, False, 0, ctypes.byref(kind),
                                       ctypes.byref(size), ctypes.byref(count), ctypes.byref(after),
                                       ctypes.byref(data)) != 0 or not data.value:
            return None
        try:
            if size.value == 8:
                return ctypes.string_at(data.value, count.value)
            if size.value == 32:
                # Each one is a C long, whatever its size on this computer
                return list((ctypes.c_long * count.value).from_address(data.value))
            return None
        finally:
            self.lib.XFree(data)


x11 = X11()


def active_window():
    value = x11.get(x11.root, "_NET_ACTIVE_WINDOW")
    return value[0] if value and value[0] else None


def window_property(xid, name):
    """A text property of an X11 window, or None."""
    value = x11.get(xid, name)
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else None


def window_number(xid, name):
    """A number property of an X11 window, such as _NET_WM_PID, or None."""
    value = x11.get(xid, name)
    return value[0] if isinstance(value, list) and value else None


def window_menu(xid):
    """Where a window's menu is on D-Bus: (bus name, menu path, application path, window path), or None. The
    application's and window's paths are where GTK publishes their actions, for a menu it publishes itself."""
    if not xid:
        return None
    bus_name = window_property(xid, "_GTK_UNIQUE_BUS_NAME")
    path = window_property(xid, "_GTK_MENUBAR_OBJECT_PATH")
    if not bus_name or not path:
        return None
    return (bus_name, path, window_property(xid, "_GTK_APPLICATION_OBJECT_PATH"),
            window_property(xid, "_GTK_WINDOW_OBJECT_PATH"))


def window_accels(xid):
    """The keyboard shortcuts of a window's application that its published menu doesn't include, as the header bar
    module keeps them: by their actions' detailed names, for a menu that GTK publishes itself (Inkscape's), and by
    their items' paths ("File → Save"), for those only shown in the menu bar's items (LibreOffice's)."""
    text = window_property(xid, ACCELS_PROPERTY) or ""
    accels = {}
    for pair in text.split("|"):
        action, _equals, accel = pair.rpartition("=")
        if action and accel:
            accels[action] = accel
    for line in (window_property(xid, LABEL_ACCELS_PROPERTY) or "").splitlines():
        path, _tab, accel = line.rpartition("\t")
        if path and accel:
            accels.setdefault(item_path([buffet.plain(label) for label in path.split("\x1f")]), accel)
    return accels


def item_path(labels):
    """The key of a menu item, by its labels (without access keys) from its menu's title."""
    return "path:" + " → ".join(labels)


def spin(seconds):
    """Lets D-Bus messages arrive for a while."""
    context = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        context.iteration(False)
        time.sleep(0.005)


def split_action(name):
    """An action's group and name: "unity.-Copy" is in the group the module publishes, "app.quit" and
    "win.close" in the application's and the window's, when GTK publishes the menu itself."""
    return tuple(name.split(".", 1)) if "." in name else ("unity", name)


def attribute(model, index, name):
    value = model.get_item_attribute_value(index, name, None)
    return value.unpack() if value is not None else None


def tidy(entries):
    """Removes separators at the ends and next to each other."""
    tidied = []
    for entry in entries:
        if entry[0] == "sep" and (not tidied or tidied[-1][0] == "sep"):
            continue
        tidied.append(entry)
    while tidied and tidied[-1][0] == "sep":
        tidied.pop()
    return tidied


class RemoteMenu:
    """The menu bar of another application's window, as published on D-Bus by appmenu-gtk-module."""

    def __init__(self, bus_name, path, application_path=None, window_path=None):
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION)
        self.bus_name = bus_name
        # Where the application answers on its main thread, in turn with what it was asked before
        self.actions_path = application_path or path
        self.model = Gio.DBusMenuModel.get(self.connection, bus_name, path)
        # The actions of the menu items, by group: those the module publishes with the menu, and the
        # application's and the window's, for a menu that GTK publishes itself (Inkscape's, for example)
        self.groups = {"unity": Gio.DBusActionGroup.get(self.connection, bus_name, path)}
        for group, group_path in (("app", application_path), ("win", window_path)):
            if group_path:
                self.groups[group] = Gio.DBusActionGroup.get(self.connection, bus_name, group_path)
        self.submenus = []   # kept, so that D-Bus keeps sending their items
        self.found = []      # the submenus found while opening them, to keep from then on
        self.opened = []     # the submenus told that they're open
        self.choices = {}    # an item's path, as the buffet menu reports it: (action group, action, target)
        self.accels = {}     # shortcuts the menu doesn't include, by the actions' detailed names (window_accels())
        # The menus as last converted by menus(), with the shortcuts they were converted with and when. They're
        # converted again when the application changes its menu or its actions, which it tells as it does
        self.converted = None
        self.converted_accels = None
        self.converted_at = 0
        self.changed = True
        self.watched = set()   # the models whose changes are watched, by id
        self.openers = set()   # the submenus' actions, whose changes are Buffet Menu's own: (group, name)
        for group in self.groups.values():
            # (Whether an action is enabled isn't part of the menus: see disabled_paths())
            for signal in ("action-added", "action-removed"):
                group.connect(signal, self.on_changed)
            group.connect("action-state-changed", self.on_state_changed)
        self.watch(self.model)

    def watch(self, model):
        if id(model) not in self.watched:
            self.watched.add(id(model))
            model.connect("items-changed", self.on_changed)

    def on_changed(self, *_args):
        self.changed = True

    def on_state_changed(self, group, name, _state):
        # Opening and closing the submenus changes their actions' states: that's not a change to the menu
        if (group, name) not in self.openers:
            self.changed = True

    def load(self):
        """Fetches the whole menu. The module only fills a submenu once it's told that it's opening, so
        this opens each one in turn, until the menu stops growing."""
        for group in self.groups.values():
            group.list_actions()
        self.wait_for_application()
        started = time.monotonic()
        last, steady = -1, 0
        # Until the menu has stopped growing: twice the same number of items, once the application has answered.
        # An empty menu is given half a second to arrive.
        while time.monotonic() < started + LOAD_TIMEOUT and \
                (steady < 2 or (last == 0 and time.monotonic() < started + 0.5)):
            count = self.open_all()
            self.wait_for_application()
            if count == last:
                steady += 1
            else:
                steady = 0
                # The application may fill a submenu a little later: a moment for it, while it's still growing
                spin(0.01)
            last = count
        self.close_all()

    def refresh(self):
        """Brings a menu loaded before up to date. D-Bus has kept it so, but some applications only change a
        submenu when it opens, like Xed's list of open documents: each one opens again, briefly."""
        self.open_all()
        self.wait_for_application()
        self.close_all()

    def wait_for_application(self):
        """Waits until the application has answered what it was sent: it answers in turn, so its changes to the
        menu have arrived when it answers a question asked after them."""
        answered = []
        self.connection.call(self.bus_name, self.actions_path, "org.gtk.Actions", "List", None, None,
                             Gio.DBusCallFlags.NONE, int(REFRESH_TIME * 1000), None,
                             lambda _connection, _result: answered.append(True))
        context = GLib.MainContext.default()
        end = time.monotonic() + REFRESH_TIME
        while not answered and time.monotonic() < end:
            if not context.iteration(False):
                time.sleep(0.001)
        while context.pending():
            context.iteration(False)

    def open_all(self):
        """Tells each submenu that it's opening, keeping the submenus found. Returns how many items there are."""
        self.found = []
        count = self.open_submenus(self.model)
        self.submenus = self.found
        return count

    def close_all(self):
        for group, name in self.opened:
            group.change_action_state(name, GLib.Variant("b", False))
        self.opened = []

    def open_submenus(self, model):
        count = model.get_n_items()
        for index in range(model.get_n_items()):
            opener = attribute(model, index, "submenu-action")
            group, name = self.action(opener) if opener else (None, None)
            if group is not None and (group, name) not in self.opened:
                self.openers.add((group, name))
                self.opened.append((group, name))
                group.change_action_state(name, GLib.Variant("b", True))
            links = model.iterate_item_links(index)
            while links.next():
                submenu = links.get_value()
                self.watch(submenu)
                self.found.append(submenu)
                count += self.open_submenus(submenu)
        return count

    def menus(self):
        """The application's menus, as (title, entries), in the form of buffet_menu_test.XED_MENUS: as converted
        last time, unless they've changed since."""
        if self.changed or self.converted is None or self.converted_accels != self.accels or \
                time.monotonic() - self.converted_at > CONVERTED_TIME:
            self.changed = False
            self.choices = {}
            self.converted = [(title, self.entries(submenu, [buffet.plain(title)]))
                              for title, submenu in self.top(self.model)]
            self.converted_accels = dict(self.accels)
            self.converted_at = time.monotonic()
        return self.converted

    def top(self, model):
        found = []
        for index in range(model.get_n_items()):
            section = model.get_item_link(index, "section")
            submenu = model.get_item_link(index, "submenu")
            if section is not None:
                found += self.top(section)
            elif submenu is not None and attribute(model, index, "label"):
                found.append((attribute(model, index, "label"), submenu))
        return found

    def entries(self, model, path):
        entries = []
        for index in range(model.get_n_items()):
            section = model.get_item_link(index, "section")
            if section is not None:
                # Each section is a group of items, between separators
                entries += [("sep",)] + self.entries(section, path) + [("sep",)]
                continue
            label = attribute(model, index, "label") or ""
            submenu = model.get_item_link(index, "submenu")
            if submenu is not None:
                entries.append(("sub", label, self.entries(submenu, path + [buffet.plain(label)])))
                continue
            full_name = attribute(model, index, "action") or ""
            group, name = self.action(full_name)
            target = model.get_item_attribute_value(index, "target", None)
            accel = attribute(model, index, "accel") or attribute(model, index, "x-canonical-accel") or \
                (self.accels.get(Gio.Action.print_detailed_name(full_name, target)) if full_name else None) or \
                self.accels.get(item_path(path + [buffet.plain(label)]))
            state = group.get_action_state(name) if group is not None else None
            if state is not None and target is None and state.get_type_string() == "b":
                entries.append(("check", label, accel, state.get_boolean()))
            elif state is not None and target is not None:
                # One of a group of radio items, such as the open documents
                entries.append(("file", buffet.plain(label), accel, state.equal(target)))
            else:
                entries.append(("item", label, accel))
            self.choices[" → ".join(path + [buffet.plain(label)])] = (group, name, target)
        return tidy(entries)

    def disabled_paths(self):
        """The items whose actions the application has disabled, by their paths, as the buffet menu reports them:
        asked each time the menu opens, as they change all the time (Paste, Undo…)."""
        return [path for path, (group, name, _target) in self.choices.items()
                if group is not None and not group.get_action_enabled(name)]

    def action(self, full_name):
        """The action group and name of a menu item's action, or (None, None) if there's no such action."""
        prefix, name = split_action(full_name)
        group = self.groups.get(prefix)
        return (group, name) if name and group is not None and group.has_action(name) else (None, None)

    def choose(self, path):
        """Runs the item in the application, as if it had been chosen in its own menu."""
        group, name, target = self.choices.get(path, (None, None, None))
        if group is not None:
            group.activate_action(name, target)
            self.connection.flush_sync(None)


class WindowBuffet(buffet.BuffetMenu):
    """A buffet menu under the title bar of another application's window."""

    def __init__(self, xid, menus, on_chosen, on_closed):
        self.xid = xid
        self.window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), xid)
        self.on_closed = on_closed
        self.header_position = None
        self.update_position()
        super().__init__(None, None, menus, on_chosen, lambda: None)

    def update_position(self):
        """Where the window's header bar and Buffet button are, if Buffet Menu's header bar module gave it one:
        "x y width height" of each, in the window. They move when the window is resized."""
        header = window_property(self.xid, HEADER_PROPERTY)
        self.header_position = [int(number) for number in header.split()] if header and len(header.split()) == 8 else None

    def header_rect(self):
        if self.header_position:
            _result, x, y = self.window.get_origin()
            header_x, header_y, width, height = self.header_position[:4]
            return x + header_x, y + header_y, width, height
        # The title bar: the part of the window's frame above its contents
        frame = self.window.get_frame_extents()
        top = self.window.get_origin()[-1]
        return frame.x, frame.y, frame.width, max(0, top - frame.y)

    def button_rect(self):
        if self.header_position:
            _result, x, y = self.window.get_origin()
            button_x, button_y, width, height = self.header_position[4:]
            return x + button_x, y + button_y, width, height
        # There's no button: as if there were one in the title bar, to the left of the window's buttons
        x, y, width, height = self.header_rect()
        return x + width - 150, y, height, height

    def set_button_active(self, active):
        if not active:
            self.on_closed()

    def workarea(self):
        return Gdk.Display.get_default().get_monitor_at_window(self.window).get_workarea()


def dump(menus, depth=0):
    """Prints the menus, one item a line, each with its shortcut if the application sent one."""
    for entry in menus:
        if len(entry) == 2:   # a menu, as (title, entries)
            print(f"{entry[0]}")
            dump(entry[1], 1)
        elif entry[0] == "sep":
            print("    " * depth + "----")
        elif entry[0] == "sub":
            print("    " * depth + f"{entry[1]}  >")
            dump(entry[2], depth + 1)
        else:
            print("    " * depth + f"{entry[1]:40} {entry[2] or '(no shortcut)'}")


def main():
    parser = argparse.ArgumentParser(description="Shows the menus of the active window as a buffet menu")
    parser.add_argument("--window", type=lambda text: int(text, 0), help="an X11 window id, instead of the active window")
    parser.add_argument("--dump", action="store_true",
                        help="print the window's menus, with their shortcuts, instead of showing them")
    parser.add_argument("--registrar", action="store_true",
                        help="keep running, so that applications started with the module hide their menu bars")
    args = parser.parse_args()
    if args.registrar:
        run_registrar()
        return

    xid = args.window or active_window()
    published = window_menu(xid)
    if published is None:
        sys.exit("This window doesn't publish its menus: start the application with GTK_MODULES=appmenu-gtk-module")
    remote = RemoteMenu(*published)
    remote.accels = window_accels(xid)
    remote.load()
    menus = remote.menus()
    if not menus:
        sys.exit("The application didn't send its menus")
    if args.dump:
        dump(menus)
        return

    buffet.set_up_style()
    settings = buffet.load_settings()
    loop = GLib.MainLoop()
    menu = WindowBuffet(xid, menus, lambda chosen, _accel: remote.choose(chosen), loop.quit)
    menu.set_layout(settings["layout"], settings["per-row"])
    menu.set_shortcuts(settings["shortcuts"])
    menu.set_width(settings["width"])
    menu.set_rows(settings["rows"])
    menu.set_no_room(settings["no-room"])

    def on_layout_chosen(layout):
        # The layout the menu picked for itself, the first time it opened: kept, as if chosen in the preferences
        settings["layout"] = layout
        buffet.save_settings(settings)

    menu.on_layout_chosen = on_layout_chosen
    menu.open(keyboard=True)
    loop.run()


if __name__ == "__main__":
    main()
