#!/usr/bin/python3
"""Buffet menu for another application's window: a proof of concept.

Shows the menus of the active window as a buffet menu, under its title bar, and runs the item you
choose in that application. The application itself doesn't change: its GTK menu bar is published on
D-Bus by appmenu-gtk-module, the GTK module that global menu panels use.

    sudo apt install appmenu-gtk3-module
    python3 buffet_remote.py --registrar &      first: hide the menu bars of applications started with the module
    GTK_MODULES=appmenu-gtk-module xed &        start Xed with the module
    python3 buffet_remote.py                    show the active window's menus (give this a keyboard shortcut)
    python3 buffet_remote.py --window 0x3a00007 or of a given window, by its X11 id as xprop shows it
    sleep 3; python3 buffet_remote.py --dump    print what the active window sends: its menus, with their shortcuts

The layout and keyboard shortcut settings are the ones set in buffet_menu_test.py (Edit → Preferences).
"""

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffet_menu_test as buffet  # noqa: E402  (sets up the GTK versions)

import gi  # noqa: E402
gi.require_version("GdkX11", "3.0")
from gi.repository import Gdk, GdkX11, Gio, GLib  # noqa: E402

# How long to wait for the application to send its whole menu, in seconds
LOAD_TIMEOUT = 2.0
# How long to wait for the changes to a menu that has been loaded before, in seconds
REFRESH_TIME = 0.05
# appmenu-gtk-module hides an application's menu bar while a program owns this name on D-Bus, and shows it
# again when the name is let go. It doesn't need anything else from that program.
REGISTRAR_NAME = "com.canonical.AppMenu.Registrar"
# Where the header bar module keeps the position of a window's header bar and Buffet button
HEADER_PROPERTY = "_BUFFET_MENU_HEADER"


def run_registrar():
    """Keeps the menu bars of the applications started with the module hidden, until stopped."""
    loop = GLib.MainLoop()

    def on_name_lost(_connection, _name):
        print("Another program already hides the menu bars (or D-Bus isn't available)", file=sys.stderr)
        loop.quit()

    Gio.bus_own_name(Gio.BusType.SESSION, REGISTRAR_NAME, Gio.BusNameOwnerFlags.NONE, None, None, on_name_lost)
    loop.run()


def active_window():
    # For example: _NET_ACTIVE_WINDOW(WINDOW): window id # 0x3a00007
    words = xprop("-root", "_NET_ACTIVE_WINDOW").split()
    return int(words[-1], 16) if words and words[-1].startswith("0x") and int(words[-1], 16) else None


def window_property(xid, name):
    """A text property of an X11 window, or None."""
    output = xprop("-id", str(xid), name)
    # For example: _GTK_UNIQUE_BUS_NAME(UTF8_STRING) = ":1.42"
    value = output.split("=", 1)[1].strip() if "=" in output else ""
    return value[1:-1] if value.startswith('"') else None


def xprop(*args):
    try:
        return subprocess.run(["xprop", *args], capture_output=True, text=True).stdout
    except FileNotFoundError:
        sys.exit("buffet_remote.py needs xprop: sudo apt install x11-utils")


def spin(seconds):
    """Lets D-Bus messages arrive for a while."""
    context = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        context.iteration(False)
        time.sleep(0.005)


def action_name(name):
    """An action's name without its group, as in "unity.-Copy"."""
    return name.split(".", 1)[1] if "." in name else name


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

    def __init__(self, bus_name, path):
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION)
        self.model = Gio.DBusMenuModel.get(self.connection, bus_name, path)
        self.actions = Gio.DBusActionGroup.get(self.connection, bus_name, path)
        self.submenus = []   # kept, so that D-Bus keeps sending their items
        self.found = []      # the submenus found while opening them, to keep from then on
        self.opened = []     # the submenus told that they're open
        self.choices = {}    # an item's path, as the buffet menu reports it: (action, target)

    def load(self):
        """Fetches the whole menu. The module only fills a submenu once it's told that it's opening, so
        this opens each one in turn, until the menu stops growing."""
        self.actions.list_actions()
        end = time.monotonic() + LOAD_TIMEOUT
        last, steady = -1, 0
        while time.monotonic() < end and steady < 3:
            count = self.open_all()
            spin(0.1)
            steady = steady + 1 if count == last else 0
            last = count
        self.close_all()

    def refresh(self):
        """Brings a menu loaded before up to date. D-Bus has kept it so, but some applications only change a
        submenu when it opens, like Xed's list of open documents: each one opens again, briefly."""
        self.open_all()
        spin(REFRESH_TIME)
        self.close_all()

    def open_all(self):
        """Tells each submenu that it's opening, keeping the submenus found. Returns how many items there are."""
        self.found = []
        count = self.open_submenus(self.model)
        self.submenus = self.found
        return count

    def close_all(self):
        for name in self.opened:
            self.actions.change_action_state(name, GLib.Variant("b", False))
        self.opened = []

    def open_submenus(self, model):
        count = model.get_n_items()
        for index in range(model.get_n_items()):
            opener = attribute(model, index, "submenu-action")
            if opener and action_name(opener) not in self.opened and self.actions.has_action(action_name(opener)):
                self.opened.append(action_name(opener))
                self.actions.change_action_state(action_name(opener), GLib.Variant("b", True))
            links = model.iterate_item_links(index)
            while links.next():
                submenu = links.get_value()
                self.found.append(submenu)
                count += self.open_submenus(submenu)
        return count

    def menus(self):
        """The application's menus, as (title, entries), in the form of buffet_menu_test.XED_MENUS."""
        return [(title, self.entries(submenu, [buffet.plain(title)])) for title, submenu in self.top(self.model)]

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
            name = action_name(attribute(model, index, "action") or "")
            target = model.get_item_attribute_value(index, "target", None)
            accel = attribute(model, index, "accel") or attribute(model, index, "x-canonical-accel")
            state = self.actions.get_action_state(name) if name and self.actions.has_action(name) else None
            if state is not None and target is None and state.get_type_string() == "b":
                entries.append(("check", label, accel, state.get_boolean()))
            elif state is not None and target is not None:
                # One of a group of radio items, such as the open documents
                entries.append(("file", buffet.plain(label), accel, state.equal(target)))
            else:
                entries.append(("item", label, accel))
            self.choices[" → ".join(path + [buffet.plain(label)])] = (name, target)
        return tidy(entries)

    def choose(self, path):
        """Runs the item in the application, as if it had been chosen in its own menu."""
        name, target = self.choices.get(path, (None, None))
        if name:
            self.actions.activate_action(name, target)
            self.connection.flush_sync(None)


class WindowBuffet(buffet.BuffetMenu):
    """A buffet menu under the title bar of another application's window."""

    def __init__(self, xid, menus, on_chosen, on_closed):
        self.window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), xid)
        self.on_closed = on_closed
        # Where the window's header bar and Buffet button are, if Buffet Menu's header bar module gave it one:
        # "x y width height" of each, in the window
        header = window_property(xid, HEADER_PROPERTY)
        self.header_position = [int(number) for number in header.split()] if header and len(header.split()) == 8 else None
        super().__init__(None, None, menus, on_chosen, lambda: None)

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
    bus_name = window_property(xid, "_GTK_UNIQUE_BUS_NAME") if xid else None
    path = window_property(xid, "_GTK_MENUBAR_OBJECT_PATH") if xid else None
    if not bus_name or not path:
        sys.exit("This window doesn't publish its menus: start the application with GTK_MODULES=appmenu-gtk-module")
    remote = RemoteMenu(bus_name, path)
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
