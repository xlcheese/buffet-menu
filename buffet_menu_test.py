#!/usr/bin/python3
"""Buffet menu test window.

A dummy window with Xed's menus (Xed with its standard plugins), shown either as a
buffet menu that opens from a header bar button, or as a classic menu bar so the
two can be compared. The menu items do nothing: the window only reports which
item was chosen and how long it took from opening the menu.

    python3 buffet_menu_test.py              buffet menu, laid out as set in Edit → Preferences
    python3 buffet_menu_test.py --columns 4  buffet menu, 4 menus per row, whatever the preferences say
    python3 buffet_menu_test.py --classic    classic title bar and menu bar
"""

import argparse
import json
import os
import time

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango

HERE = os.path.dirname(os.path.abspath(__file__))

# A copy of icons/buffet-menu-symbolic.svg, used when the script is run on its own without the icons folder
ICON_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg height="16px" viewBox="0 0 16 16" width="16px" xmlns="http://www.w3.org/2000/svg">
    <g fill="#2e3436">
        <!-- left column: heading, then three items -->
        <path d="m 0 2 h 7 v 2 h -7 z m 0 0"/>
        <path d="m 1 7 h 5 v 1 h -5 z m 0 0"/>
        <path d="m 1 10 h 5 v 1 h -5 z m 0 0"/>
        <path d="m 1 13 h 5 v 1 h -5 z m 0 0"/>
        <!-- right column: heading, then three items -->
        <path d="m 9 2 h 7 v 2 h -7 z m 0 0"/>
        <path d="m 10 7 h 5 v 1 h -5 z m 0 0"/>
        <path d="m 10 10 h 5 v 1 h -5 z m 0 0"/>
        <path d="m 10 13 h 5 v 1 h -5 z m 0 0"/>
    </g>
</svg>
"""

# Xed's menus, from xed/resources/ui/xed-ui.xml and xed/xed-ui.h, plus the items
# that Xed's standard plugins add (sort, time, joinlines, textsize, spell, docinfo).
# Each entry is one of:
#   ("item", label, accelerator)
#   ("check", label, accelerator, active)
#   ("file", name, accelerator, active)   a file name: no access key, and a radio item if active is not None
#   ("sub", label, [entries])
#   ("sep",)
FAVORITES = [("file", "notes.txt", None, None), ("file", "todo.md", None, None), ("file", "budget.csv", None, None)]
RECENTS = [("file", "1. buffet_menu_test.py", None, None), ("file", "2. README.md", None, None),
           ("file", "3. xed-ui.xml", None, None), ("file", "4. changelog", None, None)]

XED_MENUS = [
    ("_File", [
        ("item", "_New", "<Control>n"),
        ("item", "_Open...", "<Control>o"),
        ("sep",),
        ("item", "_Save", "<Control>s"),
        ("item", "Save _As...", "<Shift><Control>s"),
        ("item", "Revert", None),
        ("sep",),
        ("item", "Print Previe_w", "<Control><Shift>p"),
        ("item", "_Print...", "<Control>p"),
        ("sep",),
        ("sub", "Favorites", FAVORITES),
        ("sub", "Recents", RECENTS),
        ("sep",),
        ("item", "_Close", "<Control>w"),
        ("item", "_Quit", "<Control>q"),
    ]),
    ("_Edit", [
        ("item", "_Undo", "<Control>z"),
        ("item", "_Redo", "<Control>y"),
        ("sep",),
        ("item", "C_ut", "<Control>x"),
        ("item", "_Copy", "<Control>c"),
        ("item", "_Paste", "<Control>v"),
        ("item", "_Delete", None),
        ("item", "_Duplicate", "<Control><Shift>d"),
        ("sep",),
        ("item", "Select _All", "<Control>a"),
        ("sep",),
        ("item", "_Toggle Comment", "<Control>slash"),
        ("item", "Toggle Comment _Block", "<Shift><Control>question"),
        ("sep",),
        ("item", "In_sert Date and Time...", "F5"),
        ("sep",),
        ("item", "S_ort lines", "F10"),
        ("sep",),
        ("item", "Pr_eferences", None),
    ]),
    ("_View", [
        ("check", "_Toolbar", None, True),
        ("check", "_Menubar", None, True),
        ("check", "_Statusbar", None, True),
        ("check", "Side _Pane", "F9", False),
        ("check", "_Bottom Pane", "<Control>F9", False),
        ("check", "_Overview Map", "F12", False),
        ("sep",),
        ("check", "Fullscreen", "F11", False),
        ("sep",),
        ("check", "_Word wrap", "<Control>r", True),
        ("sep",),
        ("item", "_Join Lines", "<Control>j"),
        ("item", "_Larger Text", "<Control>equal"),
        ("item", "S_maller Text", "<Control>minus"),
        ("item", "_Normal size", "<Control>0"),
        ("sep",),
        ("item", "_Highlight Mode", "<Shift><Control>h"),
    ]),
    ("_Search", [
        ("item", "_Find", "<Control>f"),
        ("item", "Find Ne_xt", "<Control>g"),
        ("item", "Find Pre_vious", "<Shift><Control>g"),
        ("sep",),
        ("item", "_Replace", "<Control>h"),
        ("sep",),
        ("item", "Go to _Line...", "<Control>i"),
    ]),
    ("_Tools", [
        ("item", "_Check Spelling...", "<Shift>F7"),
        ("item", "Set _Language...", None),
        ("check", "_Autocheck Spelling", None, False),
        ("sep",),
        ("item", "_Document Statistics", None),
    ]),
    ("_Documents", [
        ("item", "_Save All", "<Shift><Control>l"),
        ("item", "_Close All", "<Shift><Control>w"),
        ("sep",),
        ("item", "_Previous Document", "<Alt><Control>Page_Up"),
        ("item", "_Next Document", "<Alt><Control>Page_Down"),
        ("sep",),
        ("item", "_Move to New Window", None),
        ("sep",),
        ("file", "notes.txt", "<Alt>1", True),
        ("file", "todo.md", "<Alt>2", False),
        ("file", "buffet_menu_test.py", "<Alt>3", False),
    ]),
    ("_Help", [
        ("item", "_Contents", "F1"),
        ("item", "_Keyboard Shortcuts", None),
        ("item", "_About", None),
    ]),
]

SAMPLE_TEXT = """This window only tests menus. Nothing in the menus does anything.

Try finding these items, then compare with --classic:
  • Edit → Sort lines
  • View → Overview Map
  • Documents → Move to New Window
  • File → Recents → README.md
  • Tools → Document Statistics

Keyboard: F10 opens the menu. Alt+F, Alt+E, Alt+V, Alt+S, Alt+T, Alt+D and Alt+H
open it at that menu. Arrow keys move around, Enter chooses, Esc closes.

Edit → Preferences sets how the menus are laid out (fitted to the window, in one row,
or a fixed number of menus per row) and whether the keyboard shortcuts are shown next to
the items, in a tooltip, or not at all.
"""

# How the buffet menu puts its menus in rows. Rows are as wide as the window, or the screen (see WIDTH_WINDOW).
LAYOUT_EQUAL = "equal"     # one row, or else as few rows as fit, with as many menus in each: 7 menus are 4 + 3
LAYOUT_FILL = "fill"       # one row, or else as many menus in each row as fit: 7 menus may be 6 + 1
LAYOUT_TWO_ROWS = "two"    # two rows, with as many menus in each: more rows only if two don't fit
LAYOUT_FIXED = "fixed"     # a set number of menus per row
# Until a layout is chosen, the first time the menu opens picks LAYOUT_EQUAL for an application with up to this
# many menus, else LAYOUT_TWO_ROWS, and keeps it
STARTING_ONE_ROW_MENUS = 4
# What the buffet menu does when it doesn't fit below the header bar
NO_ROOM_MOVE = "move"      # keeps its rows as they are, and goes above the header bar, or over it
NO_ROOM_ROWS = "rows"      # stays below the header bar, with fewer, wider rows, as long as some fit there
# How the menus of a row line up
ROWS_LINED = "lined"       # each row of menus starts at the same height, with a line between the rows
ROWS_STACKED = "stacked"   # each menu right under the one above it: a shorter menu
# How wide the rows of the buffet menu can be
WIDTH_WINDOW = "window"    # as wide as the application's window
WIDTH_SCREEN = "screen"    # as wide as the screen
# How the buffet menu shows the keyboard shortcuts of its items
SHORTCUTS_SHOW = "show"         # next to each item, as in other menus
SHORTCUTS_TOOLTIP = "tooltip"   # in a tooltip when pointing at an item: narrower menus
SHORTCUTS_HIDE = "hide"         # not at all: the narrowest menus
DEFAULT_SETTINGS = {"layout": None, "per-row": 4, "width": WIDTH_WINDOW, "no-room": NO_ROOM_MOVE,
                    "rows": ROWS_LINED, "shortcuts": SHORTCUTS_SHOW}
# A real application would keep these in GSettings. The test window keeps them in a small file.
SETTINGS_FILE = os.path.join(GLib.get_user_config_dir(), "buffet-menu-test", "settings.json")


def load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as source:
            settings.update(json.load(source))
    except (OSError, ValueError):
        pass
    # Choices of earlier versions of the test window
    if settings["layout"] == "row":
        settings["layout"], settings["width"] = LAYOUT_EQUAL, WIDTH_SCREEN
    if settings["layout"] not in (LAYOUT_EQUAL, LAYOUT_FILL, LAYOUT_TWO_ROWS, LAYOUT_FIXED):
        settings["layout"] = None
    if settings["width"] not in (WIDTH_WINDOW, WIDTH_SCREEN):
        settings["width"] = WIDTH_WINDOW
    if settings["no-room"] not in (NO_ROOM_MOVE, NO_ROOM_ROWS):
        settings["no-room"] = NO_ROOM_MOVE
    if settings["rows"] not in (ROWS_LINED, ROWS_STACKED):
        settings["rows"] = ROWS_LINED
    settings.pop("too-big", None)
    return settings


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as target:
        json.dump(settings, target)

# A check box or radio button in a menu item: a 16 px indicator with 2 px before it and 6 px after it, as in Mint-Y
TOGGLE_SIZE, TOGGLE_BEFORE, TOGGLE_AFTER = 16, 2, 6
TOGGLE_WIDTH = TOGGLE_BEFORE + TOGGLE_SIZE + TOGGLE_AFTER

CSS = b"""
menu.buffet {
    margin: 0;
}
menu.buffet menuitem {
    padding-left: 14px;
    padding-right: 14px;
}
menu.buffet .buffet-heading {
    padding: 6px 14px 4px 14px;
    font-weight: bold;
}
"""

# Themes can set the colour of the menu titles with: @define-color buffet_heading_color #000000;
HEADING_COLOR = "buffet_heading_color"
# Room for the menu's own padding and borders, around its columns
MENU_FRAME = 16
# Room for the Buffet icon at the top of the menu, when it covers the header bar
COVER_BAR_ROOM = 48
# How the buffet menu is shown when it's open
MODE_FULL = "full"          # all the menus, in rows of columns
MODE_SCROLL = "scroll"      # all the menus, in a pop-up that scrolls
# The titles are 2 px larger than the menu items (1.5 pt at 96 dpi)
HEADING_GROWTH_PX = 2


def plain(label):
    """The label without its access key underscore. A double underscore stands for a real one."""
    return label.replace("__", "\0").replace("_", "").replace("\0", "_")


class MenuBuilder:
    """Turns the menu description into GTK menu items, for the classic menu bar. Reports choices to a callback."""

    def __init__(self, on_chosen, accel_group):
        self.on_chosen = on_chosen
        self.accel_group = accel_group

    def item(self, entry, path):
        kind = entry[0]
        if kind == "sep":
            return Gtk.SeparatorMenuItem()
        label = entry[1]
        if kind == "check":
            item = Gtk.CheckMenuItem.new_with_mnemonic(label)
            item.set_active(entry[3])
        elif kind == "file" and entry[3] is not None:
            item = Gtk.CheckMenuItem(label=label, draw_as_radio=True, active=entry[3])
        elif kind == "file":
            item = Gtk.MenuItem(label=label)
        else:
            item = Gtk.MenuItem.new_with_mnemonic(label)
        name = label if kind == "file" else plain(label)
        if kind == "sub":
            submenu = Gtk.Menu()
            for sub_entry in entry[2]:
                submenu.append(self.item(sub_entry, path + [name]))
            item.set_submenu(submenu)
            return item
        accel = entry[2]
        if accel:
            # A real shortcut, as in Xed: pressing it chooses the item
            key, mods = Gtk.accelerator_parse(accel)
            item.add_accelerator("activate", self.accel_group, key, mods, Gtk.AccelFlags.VISIBLE)
        item.connect("activate", lambda _item: self.on_chosen(" → ".join(path + [name]), accel))
        return item

    def menu(self, entries, path):
        menu = Gtk.Menu()
        for entry in entries:
            menu.append(self.item(entry, path))
        return menu


# The buffet menu is drawn with its own widgets rather than a Gtk.Menu, which makes all its columns
# as wide as the widest one. These widgets carry the names of the parts of a GTK menu (menu, menuitem,
# accelerator, check, radio), so that the theme styles them like any other menu.

class MenuNode(Gtk.Box):
    __gtype_name__ = "BuffetMenuNode"


class ItemNode(Gtk.Box):
    __gtype_name__ = "BuffetItemNode"


class AcceleratorNode(Gtk.Label):
    __gtype_name__ = "BuffetAcceleratorNode"


class CheckNode(Gtk.DrawingArea):
    """The check box of a menu item, drawn by the theme."""
    __gtype_name__ = "BuffetCheckNode"
    render = staticmethod(Gtk.render_check)

    def __init__(self, active):
        super().__init__(width_request=TOGGLE_SIZE, height_request=TOGGLE_SIZE, valign=Gtk.Align.CENTER,
                         margin_start=TOGGLE_BEFORE, margin_end=TOGGLE_AFTER)
        self.set_active(active)

    def set_active(self, active):
        self.active = active
        if active:
            self.set_state_flags(Gtk.StateFlags.CHECKED, False)
        else:
            self.unset_state_flags(Gtk.StateFlags.CHECKED)

    def do_draw(self, cr):
        self.render(self.get_style_context(), cr, 0, 0, self.get_allocated_width(), self.get_allocated_height())
        return False


class RadioNode(CheckNode):
    """The radio button of a menu item, drawn by the theme."""
    __gtype_name__ = "BuffetRadioNode"
    render = staticmethod(Gtk.render_option)


MenuNode.set_css_name("menu")
ItemNode.set_css_name("menuitem")
AcceleratorNode.set_css_name("accelerator")
CheckNode.set_css_name("check")
RadioNode.set_css_name("radio")


class BuffetItem(Gtk.EventBox):
    """One item of the buffet menu, or of one of its submenus."""
    __gtype_name__ = "BuffetItem"

    def __init__(self, entry, path, column, toggle_space):
        super().__init__(visible_window=False)
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        kind, label = entry[0], entry[1]
        self.column = column
        self.entries = entry[2] if kind == "sub" else None
        self.accel = None if kind == "sub" else entry[2]
        self.path = path + [label if kind == "file" else plain(label)]
        self.node = ItemNode(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.node)

        self.accel_node = None
        self.toggle = None
        if kind == "check":
            self.toggle = CheckNode(entry[3])
        elif kind == "file" and entry[3] is not None:
            self.toggle = RadioNode(entry[3])
        if self.toggle:
            self.node.pack_start(self.toggle, False, False, 0)
        elif toggle_space:
            self.node.pack_start(Gtk.Box(width_request=TOGGLE_WIDTH), False, False, 0)

        self.label = Gtk.Label(label=label, use_underline=kind != "file", xalign=0)
        self.node.pack_start(self.label, True, True, 0)
        if self.accel:
            accel_label = Gtk.accelerator_get_label(*Gtk.accelerator_parse(self.accel))
            self.accel_label = accel_label
            self.accel_node = AcceleratorNode(label=accel_label, margin_start=24, no_show_all=True)
            self.node.pack_end(self.accel_node, False, False, 0)
        if self.entries:
            arrow = Gtk.Image.new_from_icon_name("pan-end-symbolic", Gtk.IconSize.MENU)
            self.node.pack_end(arrow, False, False, 0)
            arrow.set_margin_start(10)

    def show_shortcut(self, shortcuts):
        """Shows the item's keyboard shortcut next to it, in its tooltip, or not at all."""
        if self.accel_node is None:
            return
        self.accel_node.set_visible(shortcuts == SHORTCUTS_SHOW)
        self.set_tooltip_text(f"Shortcut: {self.accel_label}" if shortcuts == SHORTCUTS_TOOLTIP else None)

    def set_selected(self, selected):
        if selected:
            self.node.set_state_flags(Gtk.StateFlags.PRELIGHT, False)
        else:
            self.node.unset_state_flags(Gtk.StateFlags.PRELIGHT)

    def matches(self, keyval):
        """Whether this item's access key (the underlined letter) is this key."""
        mnemonic = self.label.get_mnemonic_keyval()
        return mnemonic != Gdk.KEY_VoidSymbol and Gdk.keyval_to_lower(mnemonic) == Gdk.keyval_to_lower(keyval)


class BuffetColumn(Gtk.Box):
    """One menu of the buffet menu: its title and its items. A submenu is a column without a title."""
    __gtype_name__ = "BuffetColumn"

    def __init__(self, title, entries, path, buffet):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START)
        toggle_space = any(entry[0] == "check" or (entry[0] == "file" and entry[3] is not None)
                           for entry in entries)
        self.title = title
        if title:
            heading = Gtk.Label(label=plain(title), xalign=0)
            heading.get_style_context().add_class("buffet-heading")
            if toggle_space:
                heading.set_margin_start(TOGGLE_WIDTH)
            self.pack_start(heading, False, False, 0)
        self.items = []
        for entry in entries:
            if entry[0] == "sep":
                # Shorter than the column, so it doesn't run into the lines of the next column
                self.pack_start(Gtk.Separator(margin_start=3, margin_end=3), False, False, 0)
                continue
            item = BuffetItem(entry, path + ([plain(title)] if title else []), self, toggle_space)
            buffet.connect_item(item)
            self.pack_start(item, False, False, 0)
            self.items.append(item)

    def matches(self, keyval):
        """Whether this menu's access key (the underlined letter of its title) is this key."""
        if "_" not in self.title.replace("__", ""):
            return False
        letter = self.title.replace("__", "").split("_", 1)[1][0]
        return Gdk.keyval_to_lower(keyval) == Gdk.unicode_to_keyval(ord(letter.lower()))


class BuffetPopup(Gtk.Window):
    """The pop-up window that holds the buffet menu, or one of its submenus."""
    __gtype_name__ = "BuffetPopup"

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_type_hint(Gdk.WindowTypeHint.DROPDOWN_MENU)
        self.node = MenuNode(orientation=Gtk.Orientation.VERTICAL)
        self.node.get_style_context().add_class("buffet")
        self.add(self.node)

    def set_content(self, widget):
        for child in self.node.get_children():
            self.node.remove(child)
        self.node.add(widget)
        self.node.show_all()
        self.resize(1, 1)


def screen_rect(widget):
    """Where a widget is on the screen, as (x, y, width, height)."""
    toplevel = widget.get_toplevel()
    origin = toplevel.get_window().get_origin()
    x, y = widget.translate_coordinates(toplevel, 0, 0)
    return origin[-2] + x, origin[-1] + y, widget.get_allocated_width(), widget.get_allocated_height()


class Level:
    """An open submenu: the item it belongs to, its column, and its pop-up window."""

    def __init__(self, parent, column, popup):
        self.parent = parent
        self.column = column
        self.popup = popup


def scrolling(widget, max_width, max_height):
    """The widget itself if it fits in this size, or else the widget in a box that scrolls."""
    widget.show_all()
    width, height = widget.get_preferred_width()[1], widget.get_preferred_height()[1]
    if width <= max_width and height <= max_height:
        return widget
    # As big as the widget, up to the maximum. Its smallest size too: a pop-up that's already shown shrinks
    # to the smallest size of its contents.
    scrolled = Gtk.ScrolledWindow(min_content_width=min(width, max_width), min_content_height=min(height, max_height),
                                  max_content_width=max_width, max_content_height=max_height)
    scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    scrolled.add(widget)
    return scrolled


class BuffetMenu:
    """Every menu of an application at once, side by side in columns, in a pop-up under a header bar button.

    The columns are put in rows according to the layout (see LAYOUT_EQUAL) and how wide the rows can be (see
    WIDTH_WINDOW), lined up in rows or stacked up (see ROWS_LINED). The menu lines up with the right edge of the window, like other header bar menus, unless
    it's wider than the window: then it starts at the left edge of the window and sticks out past its right
    edge. When the menus can't all fit on the screen, the menu scrolls."""

    def __init__(self, button, header, menus, on_chosen, on_opened, layout=None, fixed_per_row=4):
        self.button = button
        self.header = header
        self.on_chosen = on_chosen
        self.on_opened = on_opened
        self.layout = layout
        self.fixed_per_row = fixed_per_row
        self.width = WIDTH_WINDOW
        self.rows = ROWS_LINED
        self.no_room = NO_ROOM_MOVE
        self.on_layout_chosen = None   # called with the layout when the menu picks one for itself
        self.per_row = len(menus)
        self.mode = MODE_FULL
        self.is_open = False
        self.access_keys = False
        self.selected = None
        self.pointer = None     # where the mouse pointer was last seen, on the screen
        self.levels = []        # the open submenus, from the outermost
        self.sub_popups = []    # a pop-up window for each depth of submenu, kept for the next time
        self.styled = False
        self.shortcuts = SHORTCUTS_SHOW
        self.columns = [BuffetColumn(title, entries, [], self) for title, entries in menus]
        self.places = {}   # column: (row, position in the row)

        self.popup = BuffetPopup()
        self.popup.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.popup.connect("button-press-event", self.on_press_outside)
        self.popup.connect("key-press-event", self.on_key_press)
        self.popup.connect("key-release-event", self.on_key_release)
        self.popup.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.popup.connect("button-release-event", self.on_release_elsewhere)

        # Shown only when the menu has to cover the header bar: the Buffet icon, where the header bar's one is
        # hidden under the menu, to close it
        self.cover_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, no_show_all=True)
        self.cover_button = Gtk.Button(tooltip_text="Close the menu", halign=Gtk.Align.START, margin_top=4,
                                       margin_bottom=4)
        self.cover_button.set_image(Gtk.Image.new_from_icon_name("buffet-menu-symbolic", Gtk.IconSize.BUTTON))
        self.cover_button.connect("clicked", lambda _button: self.close())
        self.cover_bar.pack_start(self.cover_button, False, False, 0)
        self.cover_bar.pack_start(Gtk.Separator(), False, False, 0)
        for child in self.cover_bar.get_children():
            child.show_all()

        # Start with one row, so that the columns are in the menu and get its style before they're measured
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.pack_start(self.cover_bar, False, False, 0)
        self.body = self.make_grid(len(self.columns))
        self.content.pack_start(self.body, False, False, 0)
        self.popup.set_content(self.content)

    def connect_item(self, item):
        item.show_shortcut(self.shortcuts)
        item.connect("enter-notify-event", self.on_item_enter)
        item.connect("leave-notify-event", self.on_item_leave)
        item.connect("button-press-event", lambda *_: True)
        item.connect("button-release-event", self.on_item_release)

    # Opening and closing

    def open(self, keyboard=False, column=None):
        if self.is_open:
            return
        self.is_open = True
        self.style_headings()
        self.lay_out()
        self.place()
        self.popup.show_all()
        self.show_access_keys(keyboard)
        self.set_button_active(True)
        # Like a GTK menu, take all the mouse and keyboard events while open, so a click elsewhere closes it
        window = self.popup.get_window()
        window.get_display().get_default_seat().grab(window, Gdk.SeatCapabilities.ALL, True, None,
                                                      Gtk.get_current_event(), None, None)
        self.popup.grab_add()
        self.pointer = tuple(window.get_display().get_default_seat().get_pointer().get_position()[1:])
        if keyboard:
            self.select((column or self.columns[0]).items[0])
        self.on_opened()

    def close(self):
        if not self.is_open:
            return
        self.is_open = False
        self.close_levels(0)
        self.select(None)
        self.popup.grab_remove()
        self.popup.get_window().get_display().get_default_seat().ungrab()
        self.popup.hide()
        self.set_button_active(False)

    def set_layout(self, layout, fixed_per_row):
        self.layout = layout
        self.fixed_per_row = fixed_per_row

    def set_width(self, width):
        """How wide the rows of menus can be: as wide as the window, or the screen (see WIDTH_WINDOW)."""
        self.width = width

    def set_no_room(self, no_room):
        """When the menu doesn't fit below the header bar: move it up, or change its rows (see NO_ROOM_MOVE)."""
        self.no_room = no_room

    def set_rows(self, rows):
        """Whether the menus of a row line up, or stack up under the menus above them (see ROWS_LINED)."""
        self.rows = rows

    def set_shortcuts(self, shortcuts):
        """Shows the keyboard shortcuts next to the items, in tooltips, or not at all (see SHORTCUTS_SHOW)."""
        self.shortcuts = shortcuts
        for column in self.columns:
            for item in column.items:
                item.show_shortcut(shortcuts)

    def lay_out(self):
        """Puts the menus in the pop-up, in rows of columns, as many to a row as the layout asks for. If they
        don't fit on the screen, they scroll."""
        if self.layout is None:
            # Not chosen yet: one row for an application with a few menus, two rows for more. Kept from now on.
            self.layout = LAYOUT_EQUAL if len(self.columns) <= STARTING_ONE_ROW_MENUS else LAYOUT_TWO_ROWS
            if self.on_layout_chosen:
                self.on_layout_chosen(self.layout)
        self.per_row = self.menus_per_row()
        width, height = self.grid_size(self.per_row)
        workarea = self.workarea()
        fits = width <= workarea.width - MENU_FRAME and height <= workarea.height - MENU_FRAME
        self.mode = MODE_FULL if fits else MODE_SCROLL
        grid = self.make_grid(self.per_row)
        if self.mode == MODE_SCROLL:
            # Room left for the Buffet icon at the top, in case the menu covers the header bar
            body = scrolling(grid, workarea.width - MENU_FRAME, workarea.height - MENU_FRAME - COVER_BAR_ROOM)
        else:
            body = grid
        self.content.remove(self.body)
        self.body = body
        self.content.pack_start(body, False, False, 0)
        body.show_all()

    def positions(self, per_row):
        """Where each menu goes in rows of this many, as (row, column of the grid). A last row with fewer menus
        lines up on the right, near the Buffet button."""
        count = len(self.columns)
        last_row = (count - 1) // per_row * per_row
        shift = per_row - (count - last_row)
        return [(index // per_row, index % per_row + (shift if index >= last_row else 0)) for index in range(count)]

    def make_grid(self, per_row):
        """The menus in rows of this many, lined up in rows or stacked up in the columns of the grid."""
        for column in self.columns:
            if column.get_parent():
                column.get_parent().remove(column)
        positions = self.positions(per_row)
        self.places = dict(zip(self.columns, positions))
        if self.rows == ROWS_STACKED:
            # Each menu right under the one above it
            grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            stacks = [Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.START) for _ in range(per_row)]
            for column, (_row, position) in zip(self.columns, positions):
                if stacks[position].get_children():
                    stacks[position].pack_start(Gtk.Separator(margin_start=3, margin_end=3), False, False, 0)
                stacks[position].pack_start(column, False, False, 0)
            for stack in stacks:
                grid.pack_start(stack, False, False, 0)
            return grid
        grid = Gtk.Grid()
        for row in range(1, positions[-1][0] + 1):
            grid.attach(Gtk.Separator(), 0, 2 * row - 1, per_row, 1)
        for column, (row, position) in zip(self.columns, positions):
            grid.attach(column, position, 2 * row, 1, 1)
        return grid

    def grid_size(self, per_row):
        """About how big the menus are in rows of this many: each column of the grid is as wide as the widest
        menu in it, and each row as tall as its tallest menu, or each column as tall as its stack of menus."""
        positions = self.positions(per_row)
        column_widths = [0] * per_row
        column_heights = [0] * per_row
        row_heights = [0] * (positions[-1][0] + 1)
        for column, (row, position) in zip(self.columns, positions):
            width, height = column.get_preferred_width()[1], column.get_preferred_height()[1]
            column_widths[position] = max(column_widths[position], width)
            column_heights[position] += height
            row_heights[row] = max(row_heights[row], height)
        return sum(column_widths), max(column_heights) if self.rows == ROWS_STACKED else sum(row_heights)

    def menus_per_row(self):
        """How many menus to put in each row, for the layout. To move the menu up when it doesn't fit below the
        header bar (see place()):
        1. its first choice that fits in the width (the window's or the screen's), below the header bar, or
           else above it
        2. or else its first choice that fits in the width and on the screen: over the header bar, with the
           Buffet icon at its top
        3. or else, when that's too tall for the screen, the fewest rows wider than the window that fit on it
        To change its rows instead, below the header bar, or else above it, or else over it: its first choice
        that fits in the width there, or else the fewest rows wider than the window that fit there.
        Either way, when the menus are too tall for the screen anyway, its first choice that fits in the width:
        the menu scrolls."""
        sizes = {}

        def size(per_row):
            if per_row not in sizes:
                sizes[per_row] = self.grid_size(per_row)
            return sizes[per_row]

        choices = self.layout_choices()
        workarea = self.workarea()
        _left, top, window_width, header_height = self.header_rect()
        screen_width = workarea.width - MENU_FRAME
        target = window_width if self.width == WIDTH_WINDOW else screen_width
        below = workarea.y + workarea.height - (top + header_height) - MENU_FRAME
        above = top - workarea.y - MENU_FRAME
        over = workarea.height - MENU_FRAME - COVER_BAR_ROOM

        def fitting(room):
            return [per_row for per_row in choices if size(per_row)[0] <= screen_width and size(per_row)[1] <= room]

        def narrowest(per_rows):
            return min(per_rows, key=lambda per_row: size(per_row)[0])

        if self.no_room == NO_ROOM_ROWS:
            for room in (below, above, over):
                in_width = [per_row for per_row in fitting(room) if size(per_row)[0] <= target]
                if in_width or fitting(room):
                    return in_width[0] if in_width else narrowest(fitting(room))
        else:
            for room in (below, above, over):
                in_width = [per_row for per_row in fitting(room) if size(per_row)[0] <= target]
                if in_width:
                    return in_width[0]
            for room in (below, above, over):
                if fitting(room):
                    return narrowest(fitting(room))
        for per_row in choices:
            if size(per_row)[0] <= target:
                return per_row
        on_screen = [per_row for per_row in choices if size(per_row)[0] <= screen_width]
        return min(on_screen or choices, key=lambda per_row: size(per_row)[0])

    def layout_choices(self):
        """The numbers of menus per row that the layout allows, from the one it prefers."""
        count = len(self.columns)
        if self.layout == LAYOUT_FIXED:
            return [max(1, min(self.fixed_per_row, count))]
        if self.layout == LAYOUT_FILL:
            # As many in each row as fit: the last row has the rest
            return list(range(count, 0, -1))
        # As few rows as fit, with as many menus in each, as evenly as possible: 7 menus in two rows are 4 + 3
        first_rows = 2 if self.layout == LAYOUT_TWO_ROWS and count > 1 else 1
        return sorted({-(-count // rows) for rows in range(first_rows, count + 1)}, reverse=True)

    def layout_name(self):
        """The layout, in words."""
        return {LAYOUT_EQUAL: "one row, then equal rows", LAYOUT_FILL: "one row, then fill each row",
                LAYOUT_TWO_ROWS: "two rows", LAYOUT_FIXED: "fixed", None: "not chosen yet"}[self.layout]

    def place(self):
        """Puts the pop-up below the header bar if it fits there, else above it, else over it with the Buffet
        icon at its top, where the header bar's icon is hidden. It lines up with the right edge of the window,
        or with its left edge if the menu is wider than the window, and stays on the screen."""
        left, top, width, height = self.header_rect()
        workarea = self.workarea()
        bottom = workarea.y + workarea.height
        self.cover_bar.hide()
        # Shrinks the pop-up to the menu, which may have become smaller since it was last shown
        self.popup.resize(1, 1)
        size = self.popup.get_preferred_size()[1]
        x = left + width - size.width if size.width <= width else left
        x = max(workarea.x, min(x, workarea.x + workarea.width - size.width))
        if top + height + size.height <= bottom:
            y = top + height
        elif size.height <= top - workarea.y:
            y = top - size.height
        else:
            # Under the header bar's button, so that the Buffet icon takes its place
            self.cover_button.set_margin_start(max(0, self.button_rect()[0] - x))
            self.cover_bar.show()
            size = self.popup.get_preferred_size()[1]
            y = max(workarea.y, bottom - size.height)
        self.popup.move(x, y)

    # Where the menu belongs. A program that shows the menu of another application's window replaces these.

    def header_rect(self):
        """Where the header bar is on the screen, as (x, y, width, height)."""
        return screen_rect(self.header)

    def button_rect(self):
        """Where the button that opens the menu is on the screen, as (x, y, width, height)."""
        return screen_rect(self.button)

    def set_button_active(self, active):
        self.button.set_active(active)

    def workarea(self):
        display = self.header.get_display()
        window = self.header.get_toplevel().get_window()
        monitor = display.get_monitor_at_window(window) if window else display.get_monitor(0)
        return monitor.get_workarea()

    def style_headings(self):
        """Makes the menu titles 2 px larger than the items, and darker on a light theme (lighter on a dark
        one), unless the theme sets their colour itself."""
        if self.styled:
            return
        self.styled = True
        style = self.columns[0].items[0].label.get_style_context()
        found, color = style.lookup_color(HEADING_COLOR)
        if not found:
            color = style.get_color(Gtk.StateFlags.NORMAL)
            lightness = 0.2126 * color.red + 0.7152 * color.green + 0.0722 * color.blue
            target = 0.0 if lightness < 0.5 else 1.0   # dark text on a light theme: go darker
            for part in ("red", "green", "blue"):
                value = getattr(color, part)
                setattr(color, part, value + (target - value) * 0.5)
        font = style.get_property("font", Gtk.StateFlags.NORMAL)
        size = font.get_size() / Pango.SCALE
        size = f"{size + HEADING_GROWTH_PX}px" if font.get_size_is_absolute() else \
               f"{size + HEADING_GROWTH_PX * 0.75:.1f}pt"
        css = f"menu.buffet .buffet-heading {{ color: {color.to_string()}; font-size: {size}; }}"
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

    # Submenus

    def depth(self, column):
        """How many submenus deep a column is: 0 for the menus themselves, 1 for their submenus..."""
        for index, level in enumerate(self.levels):
            if level.column is column:
                return index + 1
        return 0

    def is_parent(self, item):
        return any(level.parent is item for level in self.levels)

    def sub_popup(self, depth):
        """The pop-up window for submenus this deep. Each one goes in its own window group, so that the grab of
        the main pop-up doesn't take its pointer motion; its clicks still go to the main pop-up (see
        on_release_elsewhere())."""
        while len(self.sub_popups) <= depth:
            popup = BuffetPopup()
            Gtk.WindowGroup().add_window(popup)
            self.sub_popups.append(popup)
        return self.sub_popups[depth]

    def open_submenu(self, item, select_first=False):
        depth = self.depth(item.column)
        if not (len(self.levels) > depth and self.levels[depth].parent is item):
            self.close_levels(depth)
            if not item.entries:
                return
            column = BuffetColumn(None, item.entries, item.path, self)
            popup = self.sub_popup(depth)
            workarea = self.workarea()
            popup.set_content(scrolling(column, workarea.width, workarea.height - MENU_FRAME))
            size = popup.get_preferred_size()[1]
            x, y, width, height = screen_rect(item)
            right, bottom = workarea.x + workarea.width, workarea.y + workarea.height
            if x + width + size.width > right:
                # To the right of the item, or to its left if there's no room on the right
                x -= size.width
            else:
                x += width
            y = max(workarea.y, min(y, bottom - size.height))
            popup.move(x, y)
            popup.show_all()
            self.levels.append(Level(item, column, popup))
            self.show_access_keys(self.access_keys)
        if select_first and self.levels[depth].column.items:
            self.select(self.levels[depth].column.items[0])

    def close_levels(self, depth):
        """Closes the submenus this deep and deeper."""
        while len(self.levels) > depth:
            level = self.levels.pop()
            level.popup.hide()
            if self.selected is not None and self.selected.column is level.column:
                # Back to the item that the submenu belongs to
                self.selected = level.parent
            elif level.parent is not self.selected:
                level.parent.set_selected(False)

    def close_submenu(self):
        """Closes the innermost submenu."""
        if self.levels:
            self.close_levels(len(self.levels) - 1)

    # Choosing

    def select(self, item):
        if self.selected is not None and self.selected is not item and not self.is_parent(self.selected):
            self.selected.set_selected(False)
        self.selected = item
        if item is not None:
            item.set_selected(True)
            scroll_to(item)

    def activate(self, item):
        if item.entries:
            self.open_submenu(item, select_first=True)
            return
        if isinstance(item.toggle, RadioNode):
            for other in item.column.items:
                if isinstance(other.toggle, RadioNode):
                    other.toggle.set_active(other is item)
        elif item.toggle:
            item.toggle.set_active(not item.toggle.active)
        self.close()
        self.on_chosen(" → ".join(item.path), item.accel)

    # Mouse

    def on_item_enter(self, item, event):
        # Only when the pointer moves onto the item, not when the item moves under it as the menu scrolls or
        # changes, as in other menus
        pointer = (int(event.x_root), int(event.y_root))
        if pointer == self.pointer:
            return False
        self.pointer = pointer
        depth = self.depth(item.column)
        if len(self.levels) > depth and self.levels[depth].parent is not item:
            self.close_levels(depth)
        if item.entries:
            self.open_submenu(item)
        self.select(item)
        return False

    def on_item_leave(self, item, event):
        if event.detail != Gdk.NotifyType.INFERIOR and self.selected is item and not self.is_parent(item):
            self.select(None)
        return False

    def on_item_release(self, item, event):
        if event.button == Gdk.BUTTON_PRIMARY:
            self.activate(item)
        return True

    def on_press_outside(self, _popup, event):
        # Clicks elsewhere, and on the submenus, arrive here because of the grab
        popups = [self.popup] + [level.popup for level in self.levels]
        if not any(self.on_popup(popup, event.x_root, event.y_root) for popup in popups):
            self.close()
        return True

    def on_release_elsewhere(self, _popup, event):
        """Chooses the item under the mouse, for clicks that the grab sends here instead of to the item."""
        if event.button == Gdk.BUTTON_PRIMARY:
            items = [item for level in reversed(self.levels) for item in level.column.items]
            for item in items + self.main_items():
                if item.get_mapped():
                    x, y, width, height = screen_rect(item)
                    if x <= event.x_root < x + width and y <= event.y_root < y + height:
                        self.activate(item)
                        break
        return True

    def main_items(self):
        return [item for column in self.columns for item in column.items]

    @staticmethod
    def on_popup(popup, x_root, y_root):
        if not popup.get_visible():
            return False
        x, y = popup.get_position()
        return x <= x_root < x + popup.get_allocated_width() and y <= y_root < y + popup.get_allocated_height()

    # Keyboard

    def on_key_press(self, _popup, event):
        key = event.keyval
        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        if key in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
            self.show_access_keys(True)
        elif key == Gdk.KEY_F10:
            self.close()
        elif key == Gdk.KEY_Escape:
            if self.levels:
                self.close_submenu()
            else:
                self.close()
        elif key in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            self.move_vertically(-1)
        elif key in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            self.move_vertically(1)
        elif key in (Gdk.KEY_Left, Gdk.KEY_KP_Left):
            if self.levels:
                self.close_submenu()
            else:
                self.move_sideways(-1)
        elif key in (Gdk.KEY_Right, Gdk.KEY_KP_Right):
            if self.selected is not None and self.selected.entries:
                self.open_submenu(self.selected, select_first=True)
            elif not self.levels:
                self.move_sideways(1)
        elif key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            if self.selected is not None:
                self.activate(self.selected)
        elif mods == Gdk.ModifierType.MOD1_MASK:
            # Alt+letter: go to that menu
            for column in self.columns:
                if column.matches(key):
                    self.close_levels(0)
                    self.select(column.items[0])
                    break
        elif not mods:
            # A letter: choose the item with that access key in the current menu
            if self.levels:
                column = self.levels[-1].column
            elif self.selected is not None:
                column = self.selected.column
            else:
                column = self.columns[0]
            for item in column.items:
                if item.matches(key):
                    self.select(item)
                    self.activate(item)
                    break
        return True

    def on_key_release(self, _popup, _event):
        # GTK hides the access keys of a window when Alt is let go, but a menu opened with Alt+letter keeps them
        self.show_access_keys(self.access_keys)
        return True

    def show_access_keys(self, visible):
        """Underlines the access keys of the items, as when a menu is used from the keyboard."""
        self.access_keys = visible
        for popup in [self.popup] + self.sub_popups:
            popup.set_mnemonics_visible(visible)

    def move_vertically(self, step):
        if self.selected is None:
            self.select(self.columns[0].items[0])
            return
        column = self.selected.column
        index = column.items.index(self.selected) + step
        if 0 <= index < len(column.items):
            self.select(column.items[index])
            return
        if column in self.places:
            # Past the end of the menu: on to the menu above or below it, in the next row
            row, position = self.places[column]
            for other, place in self.places.items():
                if place == (row + step, position):
                    self.select(other.items[0 if step > 0 else -1])
                    return
        self.select(column.items[index % len(column.items)])

    def move_sideways(self, step):
        if self.selected is None:
            self.select(self.columns[0].items[0])
            return
        current = self.selected
        column = self.columns[(self.columns.index(current.column) + step) % len(self.columns)]
        # The item of the next menu that's nearest in height to the current one
        _x, y = current.translate_coordinates(self.popup, 0, current.get_allocated_height() // 2)
        self.select(min(column.items, key=lambda item: abs(
            item.translate_coordinates(self.popup, 0, item.get_allocated_height() // 2)[1] - y)))


def scroll_to(item):
    """Scrolls the menu that the item is in, if it scrolls, so that the item can be seen."""
    scrolled = item.get_ancestor(Gtk.ScrolledWindow)
    if scrolled is None or not item.get_mapped():
        return
    # Where the item is in the whole of what scrolls, not in the part of it that can be seen
    content = scrolled.get_child()
    if isinstance(content, Gtk.Viewport):
        content = content.get_child()
    coordinates = item.translate_coordinates(content, 0, 0)
    if coordinates is None:
        return
    x, y = coordinates
    for adjustment, start, length in ((scrolled.get_vadjustment(), y, item.get_allocated_height()),
                                      (scrolled.get_hadjustment(), x, item.get_allocated_width())):
        if start < adjustment.get_value():
            adjustment.set_value(start)
        elif start + length > adjustment.get_value() + adjustment.get_page_size():
            adjustment.set_value(start + length - adjustment.get_page_size())


class TestWindow(Gtk.ApplicationWindow):

    def __init__(self, app, classic, columns):
        super().__init__(application=app, title="Buffet Menu Test")
        self.set_default_size(800, 560)
        self.settings = load_settings()
        self.columns_option = columns
        self.preferences = None
        self.opened_at = None
        self.menu_open = False
        self.buffet = None
        self.classic = classic

        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(layout)

        if classic:
            accel_group = Gtk.AccelGroup()
            self.add_accel_group(accel_group)
            builder = MenuBuilder(self.on_chosen, accel_group)
            menubar = Gtk.MenuBar()
            for title, entries in XED_MENUS:
                top_item = Gtk.MenuItem.new_with_mnemonic(title)
                submenu = builder.menu(entries, [plain(title)])
                submenu.connect("show", self.on_menu_shown)
                top_item.set_submenu(submenu)
                menubar.append(top_item)
            menubar.connect("deactivate", self.on_menu_closed)
            layout.pack_start(menubar, False, False, 0)
        else:
            header = Gtk.HeaderBar(title="Buffet Menu Test", subtitle="Xed menus", show_close_button=True)
            self.menu_button = Gtk.ToggleButton(tooltip_text="Menu (F10)")
            self.menu_button.set_image(Gtk.Image.new_from_icon_name("buffet-menu-symbolic", Gtk.IconSize.BUTTON))
            header.pack_end(self.menu_button)
            self.set_titlebar(header)
            self.buffet = BuffetMenu(self.menu_button, header, XED_MENUS, self.on_chosen, self.on_buffet_opened)
            self.buffet.on_layout_chosen = self.on_layout_chosen
            self.apply_settings()
            self.menu_button.connect("toggled", self.on_button_toggled)
            self.connect("key-press-event", self.on_key_press)

        text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD, left_margin=12, top_margin=12, monospace=True)
        text.get_buffer().set_text(SAMPLE_TEXT)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(text)
        layout.pack_start(scrolled, True, True, 0)

        self.status = Gtk.Label(xalign=0, margin=6)
        self.status.set_text("Mode: classic menu bar" if classic else "Mode: buffet menu")
        layout.pack_start(Gtk.Separator(), False, False, 0)
        layout.pack_start(self.status, False, False, 0)

    def on_button_toggled(self, button):
        if button.get_active():
            self.buffet.open()
        else:
            self.buffet.close()

    def on_buffet_opened(self):
        self.opened_at = time.monotonic()
        shown = (f"{self.buffet.layout_name()}, {self.buffet.per_row} per row, {self.buffet.width} width, "
                 f"{self.buffet.rows}")
        if self.buffet.mode == MODE_SCROLL:
            shown += ", scrolling"
        self.status.set_text(f"Mode: buffet menu, {shown}")

    def apply_settings(self):
        if self.columns_option:
            # --columns on the command line wins over the preferences
            self.buffet.set_layout(LAYOUT_FIXED, self.columns_option)
        else:
            self.buffet.set_layout(self.settings["layout"], self.settings["per-row"])
        self.buffet.set_shortcuts(self.settings["shortcuts"])
        self.buffet.set_width(self.settings["width"])
        self.buffet.set_rows(self.settings["rows"])
        self.buffet.set_no_room(self.settings["no-room"])

    def on_layout_chosen(self, layout):
        # The layout the menu picked for itself, the first time it opened: kept, as if chosen in the preferences
        self.settings["layout"] = layout
        save_settings(self.settings)
    def show_preferences(self):
        if self.preferences is None:
            self.preferences = PreferencesDialog(self, self.settings, len(XED_MENUS), self.on_settings_changed)
        self.preferences.present()
        return False

    def on_settings_changed(self):
        save_settings(self.settings)
        self.apply_settings()

    def on_menu_shown(self, _menu):
        # In the menu bar, moving from one menu to the next shows another menu: keep the first time
        if not self.menu_open:
            self.menu_open = True
            self.opened_at = time.monotonic()

    def on_menu_closed(self, _menu):
        # GTK closes the menu before it activates the chosen item, so opened_at is kept for on_chosen
        self.menu_open = False

    def on_chosen(self, path, accel):
        seconds = f" in {time.monotonic() - self.opened_at:.1f} s" if self.opened_at else ""
        shortcut = f"   (shortcut: {Gtk.accelerator_get_label(*Gtk.accelerator_parse(accel))})" if accel else ""
        self.status.set_text(f"Chose {path}{seconds}{shortcut}")
        self.opened_at = None
        if path == "Edit → Preferences" and self.buffet is not None:
            GLib.idle_add(self.show_preferences)

    def on_key_press(self, _window, event):
        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        if event.keyval == Gdk.KEY_F10 and not mods:
            self.buffet.open(keyboard=True)
            return True
        if mods == Gdk.ModifierType.MOD1_MASK:
            for column in self.buffet.columns:
                if column.matches(event.keyval):
                    self.buffet.open(keyboard=True, column=column)
                    return True
        return False


class PreferencesDialog(Gtk.Dialog):
    """The buffet menu's settings, as they could appear in an application's preferences."""

    def __init__(self, parent, settings, menu_count, on_changed):
        super().__init__(title="Preferences", transient_for=parent, resizable=False)
        self.settings = settings
        self.on_changed = on_changed
        self.add_button("_Close", Gtk.ResponseType.CLOSE)
        self.connect("response", lambda dialog, _response: dialog.hide())
        self.connect("delete-event", lambda dialog, _event: dialog.hide_on_delete())
        columns = Gtk.Box(spacing=36, margin=18)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        columns.pack_start(left, False, False, 0)
        columns.pack_start(right, False, False, 0)
        self.get_content_area().add(columns)

        self.per_row = Gtk.SpinButton.new_with_range(1, menu_count, 1)
        self.per_row.set_value(settings["per-row"])
        self.per_row.set_sensitive(settings["layout"] == LAYOUT_FIXED)
        self.per_row.connect("value-changed", self.on_per_row_changed)
        fixed = Gtk.Box(spacing=6)
        fixed.pack_start(self.per_row, False, False, 0)
        fixed.pack_start(Gtk.Label(label="menus per row"), False, False, 0)
        self.add_choices(left, "Menu layout", "layout", (
            (LAYOUT_EQUAL, "One row, then _equal rows", None,
             "If one row doesn't fit, as few rows as fit, with as many menus in each"),
            (LAYOUT_FILL, "One row, then fi_ll each row", None,
             "If one row doesn't fit, as many menus in each row as fit"),
            (LAYOUT_TWO_ROWS, "T_wo rows", None, "More rows only if two don't fit"),
            (LAYOUT_FIXED, "_Fixed:", fixed, "Always the same number of menus in each row"),
        ))
        self.add_choices(left, "Row width", "width", (
            (WIDTH_WINDOW, "The application's win_dow", None,
             "The menu stays inside the window when it can"),
            (WIDTH_SCREEN, "The scree_n", None, "Wider rows, so fewer of them"),
        ))
        self.add_choices(right, "When there's no room below the title bar", "no-room", (
            (NO_ROOM_MOVE, "Move the _menu up", None, "Above the title bar, or over it,\nwith the rows as they are"),
            (NO_ROOM_ROWS, "Change the _rows to fit", None, "Below the title bar,\nwith fewer, wider rows"),
        ))
        self.add_choices(right, "Rows", "rows", (
            (ROWS_LINED, "Lined _up", None, "Each row starts at the same height,\nwith a line between rows"),
            (ROWS_STACKED, "Stac_ked up", None, "Each menu right under the one above it:\nshorter, but busier"),
        ))
        self.add_choices(right, "Keyboard shortcuts", "shortcuts", (
            (SHORTCUTS_SHOW, "_Show next to each item", None, "As in other menus"),
            (SHORTCUTS_TOOLTIP, "Show in a _tooltip", None,
             "Narrower menus: point at an item to see its shortcut"),
            (SHORTCUTS_HIDE, "_Hide", None, "The narrowest menus"),
        ))
        self.show_all()

    def add_choices(self, box, title, key, choices):
        """A titled group of radio buttons that sets one of the settings."""
        heading = Gtk.Label(xalign=0)
        heading.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
        if box.get_children():
            heading.set_margin_top(12)
        box.pack_start(heading, False, False, 0)
        group = None
        for value, label, extra, note in choices:
            button = Gtk.RadioButton.new_with_mnemonic_from_widget(group, label)
            group = group or button
            button.set_active(self.settings[key] == value)
            button.connect("toggled", self.on_choice_toggled, key, value)
            row = Gtk.Box(spacing=6)
            row.pack_start(button, False, False, 0)
            if extra:
                row.pack_start(extra, False, False, 0)
            box.pack_start(row, False, False, 0)
            note_label = Gtk.Label(label=note, xalign=0, margin_start=26, margin_bottom=6)
            note_label.get_style_context().add_class("dim-label")
            box.pack_start(note_label, False, False, 0)

    def on_choice_toggled(self, button, key, value):
        if not button.get_active():
            return
        self.settings[key] = value
        if key == "layout":
            self.per_row.set_sensitive(value == LAYOUT_FIXED)
        self.on_changed()

    def on_per_row_changed(self, spin):
        self.settings["per-row"] = spin.get_value_as_int()
        self.on_changed()


def set_up_style():
    """Makes the Buffet icon and the buffet menu's style available to the program's windows."""
    icons = os.path.join(HERE, "icons")
    if not os.path.exists(os.path.join(icons, "buffet-menu-symbolic.svg")):
        icons = os.path.join(GLib.get_user_cache_dir(), "buffet-menu-test")
        os.makedirs(icons, exist_ok=True)
        with open(os.path.join(icons, "buffet-menu-symbolic.svg"), "w", encoding="utf-8") as icon:
            icon.write(ICON_SVG)
    # A "-symbolic" icon is recoloured by GTK to match the theme's text colour
    Gtk.IconTheme.get_default().append_search_path(icons)
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class TestApp(Gtk.Application):

    def __init__(self, classic, columns):
        super().__init__(application_id=None)
        self.classic = classic
        self.columns = columns

    def do_activate(self):
        set_up_style()
        TestWindow(self, self.classic, self.columns).show_all()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Buffet menu test window with Xed's menus")
    parser.add_argument("--classic", action="store_true", help="use a classic title bar and menu bar")
    parser.add_argument("--columns", type=int,
                        help="menus per row in the buffet menu, instead of the layout set in the preferences")
    args = parser.parse_args()
    TestApp(args.classic, args.columns and max(1, args.columns)).run(None)
