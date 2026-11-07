#!/usr/bin/python3
"""Buffet Menu: every menu of your applications at once.

A small service that shows the menus of the applications you choose as a Buffet menu, from the Buffet button
in their header bar or a keyboard shortcut, and its settings window. The applications themselves don't change: they
start with appmenu-gtk-module, which publishes their menu bar on D-Bus, and the service hides it.

    python3 buffet_menu.py            starts the service if it isn't running, and opens the settings
    python3 buffet_menu.py --service  starts the service only, as at login
    python3 buffet_menu.py --show     shows the Buffet menu of the active window
    python3 buffet_menu.py --quit     stops the service: the applications' menu bars come back

Needs: sudo apt install appmenu-gtk3-module gir1.2-keybinder-3.0
"""

import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffet  # noqa: E402  (sets up the GTK versions)
from i18n import _, ngettext, translations  # noqa: E402
import buffet_remote as remote  # noqa: E402

import gi  # noqa: E402
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

try:
    gi.require_version("Keybinder", "3.0")
    from gi.repository import Keybinder
except (ValueError, ImportError):
    Keybinder = None

APP_ID = "io.github.xlcheese.BuffetMenu"
CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "buffet-menu")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "buffet-menu")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
LAUNCHER = os.path.join(DATA_DIR, "buffet-launch")
APPLICATIONS_DIR = os.path.join(GLib.get_user_data_dir(), "applications")
OWN_DESKTOP_FILE = os.path.join(APPLICATIONS_DIR, APP_ID + ".desktop")
AUTOSTART_FILE = os.path.join(GLib.get_user_config_dir(), "autostart", APP_ID + ".desktop")
# The icons, in the user's icon theme so that applications and menus find them by name: the Buffet button's in
# the header bars (a symbolic icon, recoloured to match the theme), and Buffet Menu's own (a cafeteria tray)
ICON_NAME = "buffet-menu-symbolic"
APP_ICON_NAME = "buffet-menu"
ICONS_DIR = os.path.join(GLib.get_user_data_dir(), "icons", "hicolor")
ICON_FILE = os.path.join(ICONS_DIR, "scalable", "apps", ICON_NAME + ".svg")
# Where each icon of the icons folder goes, in the user's icons: (file, size folder, name)
ICON_FILES = (("buffet-menu.svg", "scalable", APP_ICON_NAME),
              # Drawn for 16 px, where the other would blur
              ("buffet-menu-16.svg", "16x16", APP_ICON_NAME))
# Marks the applications' menu entries that Buffet Menu wrote, so that it only ever removes its own
MARK = "X-Buffet-Menu"
DEFAULT_SHORTCUT = "<Control><Alt>n"
# How many windows' menus are kept loaded, to show them without waiting
LOADED_WINDOWS = 8
# How many windows' Buffet menus are kept built after they close, to show again at once
BUILT_MENUS = 4
# BUFFET_MENU_DEBUG=1 prints how long each menu took to show
DEBUG = bool(os.environ.get("BUFFET_MENU_DEBUG"))
# Buffet Menu's own module, built with build.sh: a header bar with the Buffet button, in the applications' windows
HEADER_BAR_MODULE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libbuffet-headerbar.so")
MODULE_FILES = ("/usr/lib/*/gtk-3.0/modules/libappmenu-gtk-module.so", "/usr/lib*/gtk-3.0/modules/libappmenu-gtk-module.so")
INSTALL_COMMAND = "sudo apt install appmenu-gtk3-module gir1.2-keybinder-3.0"

# Starts an application with the Buffet menu: the module publishes its menu bar, and BUFFET_MENU_APP tells
# the service which application it is, to use its settings
LAUNCHER_SCRIPT = """#!/bin/sh
# Written by Buffet Menu: starts an application with the Buffet menu
BUFFET_MENU_APP="$1"
shift
export BUFFET_MENU_APP
# Buffet Menu's module puts it back as it was, for the programs the application starts
export BUFFET_MENU_GTK_MODULES="${{GTK_MODULES-}}"
export GTK_MODULES="${{GTK_MODULES:+$GTK_MODULES:}}{modules}"
exec "$@"
"""


# Settings: the service's, and those of each application's Buffet menu

def load_settings():
    settings = {"shortcut": DEFAULT_SHORTCUT, "apps": {}}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as source:
            settings.update(json.load(source))
    except (OSError, ValueError):
        pass
    # The icon in the panel and the Header bar switch, which earlier versions had
    settings.pop("panel-icon", None)
    settings.pop("header-bar", None)
    return settings


def save_settings(settings):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as target:
        json.dump(settings, target, indent=1)


def app_settings(settings, app):
    """The settings of an application's Buffet menu, as the test window's preferences have them, with the
    number of menus it has (once its menu has been opened)."""
    entry = settings["apps"].setdefault(app, {})
    for key, value in buffet.DEFAULT_SETTINGS.items():
        entry.setdefault(key, value)
    entry.setdefault("menus", None)
    entry.setdefault("no-menu-bar", False)
    entry.setdefault("own-header-bar", False)
    return entry


def missing_packages():
    """What Buffet Menu needs that isn't installed, in words."""
    missing = []
    if not os.path.exists(HEADER_BAR_MODULE):
        missing.append(_("Buffet Menu's own module, for the header bar: run ./build.sh in Buffet Menu's folder "
                         "(it needs build-essential and libgtk-3-dev)"))
    if not any(glob.glob(pattern) for pattern in MODULE_FILES):
        missing.append(_("appmenu-gtk3-module (to read the applications' menus)"))
    if Keybinder is None:
        missing.append(_("gir1.2-keybinder-3.0 (for the keyboard shortcut)"))
    return missing


# The applications' menu entries

def can_use_buffet(info):
    """Whether an application can have the Buffet menu: not a sandboxed one, which the module can't reach."""
    if not info.get_id() or info.get_id() == APP_ID + ".desktop" or not info.get_commandline():
        return False
    if info.get_boolean("Terminal") or info.has_key("X-Flatpak") or info.has_key("X-SnapInstanceName"):
        return False
    command = info.get_commandline()
    return not (command.startswith(("flatpak ", "/usr/bin/flatpak ")) or "/snap/" in command)


# Which toolkit a program uses, from the libraries it's linked to, or for a script, the GTK version it asks for
TOOLKIT_LIBRARIES = (("gtk4", "libgtk-4.so"), ("gtk3", "libgtk-3.so"), ("gtk2", "libgtk-x11-2.0.so"), ("qt", "libQt"))
GTK_VERSION = re.compile(r"""require_version\(\s*['"]Gtk['"]\s*,\s*['"](\d)""")
PYTHON_IMPORT = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_]\w*)", re.MULTILINE)
SCRIPT_PATH = re.compile(r"(/(?:usr|opt)/[\w.+/-]+)")
ADMIN_COMMANDS = re.compile(r"\b(pkexec|gksu|gksudo|sudo)\b")
# A program's toolkit, kept while Buffet Menu runs: by its path, size and change time
toolkits = {}


def library_toolkit(path):
    try:
        libraries = subprocess.run(["ldd", path], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return next((toolkit for toolkit, library in TOOLKIT_LIBRARIES if library in libraries), None)


def python_toolkit(path, text):
    """The GTK version a Python program asks for: in its script, the files beside it, or its packages."""
    found = GTK_VERSION.search(text)
    if found:
        return f"gtk{found.group(1)}"
    places = []
    # A program in its own folder (/usr/lib/linuxmint/mintUpdate, for example): the modules beside it
    if not os.path.dirname(path) in ("/usr/bin", "/usr/local/bin", "/bin", "/usr/sbin"):
        places.append(os.path.dirname(path))
    # The packages it imports
    for name in dict.fromkeys(PYTHON_IMPORT.findall(text)):
        for folder in sys.path[1:] + ["/usr/lib/python3/dist-packages"]:
            if os.path.isdir(os.path.join(folder, name)):
                places.append(os.path.join(folder, name))
                break
    count = 0
    for place in places:
        for folder, _folders, names in os.walk(place):
            for name in names:
                if not name.endswith(".py") or count > 400:
                    continue
                count += 1
                try:
                    with open(os.path.join(folder, name), encoding="utf-8", errors="replace") as source:
                        found = GTK_VERSION.search(source.read())
                except OSError:
                    continue
                if found:
                    return f"gtk{found.group(1)}"
    return None


def program_toolkit(path, depth=0):
    """"gtk3", "gtk4", "gtk2" or "qt", "admin" for a program that runs as the administrator, or None."""
    try:
        with open(path, "rb") as source:
            start = source.read(65536)
    except OSError:
        return None
    # LibreOffice loads its GTK 3 support (when it's installed: libreoffice-gtk3) as a plugin, beside its program
    if os.path.exists(os.path.join(os.path.dirname(path), "libvclplug_gtk3lo.so")):
        return "gtk3"
    if start.startswith(b"\x7fELF"):
        return library_toolkit(path)
    if not start.startswith(b"#!") or depth > 2:
        return None
    text = start.decode("utf-8", errors="replace")
    if "python" in text.split("\n", 1)[0] or path.endswith(".py") or "gi.repository" in text:
        toolkit = python_toolkit(path, text)
        if toolkit:
            return toolkit
    # A shell script that starts its program as the administrator (Synaptic). A Python program may use pkexec for
    # some of its work (Update Manager), and isn't one
    elif ADMIN_COMMANDS.search(text):
        return "admin"
    # A shell script that starts the real program (gparted, LibreOffice…)
    for other in dict.fromkeys(SCRIPT_PATH.findall(text)):
        if os.path.isfile(other) and os.access(other, os.X_OK) and os.path.realpath(other) != os.path.realpath(path):
            toolkit = program_toolkit(other, depth + 1)
            if toolkit:
                return toolkit
    return None


INTERPRETERS = re.compile(r"^(python[\d.]*|gjs|sh|bash|dash|env)$")


def app_program(info):
    """The program an application's menu entry starts: for "python3 something.py", the script."""
    try:
        _ok, words = GLib.shell_parse_argv(info.get_commandline())
    except GLib.Error:
        return None
    words = [word for word in words if not word.startswith("%")]
    while words and (INTERPRETERS.match(os.path.basename(words[0])) or "=" in words[0] or words[0].startswith("-")):
        if len(words) == 1:
            break
        words = words[1:]
    return shutil.which(words[0]) if words else None


def app_toolkit(info):
    program = app_program(info)
    if program is None:
        return None
    program = os.path.realpath(program)
    try:
        details = os.stat(program)
    except OSError:
        return None
    key = (program, details.st_size, details.st_mtime)
    if key not in toolkits:
        toolkits[key] = program_toolkit(program)
    return toolkits[key]


def is_buffet_entry(path):
    keyfile = GLib.KeyFile()
    try:
        keyfile.load_from_file(path, GLib.KeyFileFlags.NONE)
        return keyfile.get_boolean("Desktop Entry", MARK)
    except GLib.Error:
        return False


def buffet_apps():
    """The applications that have the Buffet menu, by the id of their menu entry."""
    return sorted(os.path.basename(path) for path in glob.glob(os.path.join(APPLICATIONS_DIR, "*.desktop"))
                  if is_buffet_entry(path))


def key_value(keyfile, group, key):
    """A value of a menu entry, or None if it hasn't got one."""
    try:
        return keyfile.get_string(group, key)
    except GLib.Error:
        return None


def write_launcher():
    """The launcher, with Buffet Menu's module if it's built: it gives the applications their header bar with the
    Buffet button, and hides their menu bars while Buffet Menu runs."""
    modules = ["appmenu-gtk-module"]
    if os.path.exists(HEADER_BAR_MODULE):
        modules.insert(0, HEADER_BAR_MODULE)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAUNCHER, "w", encoding="utf-8") as target:
        target.write(LAUNCHER_SCRIPT.format(modules=":".join(modules)))
    os.chmod(LAUNCHER, 0o755)


def enable(app):
    """Gives an application the Buffet menu: a copy of its menu entry in the user's applications, that
    starts it through the launcher. The applications menu, panel launchers and the file manager use it from then on."""
    if not os.path.exists(LAUNCHER):
        write_launcher()
    info = Gio.DesktopAppInfo.new(app)
    source = info.get_filename()
    target = os.path.join(APPLICATIONS_DIR, app)
    keyfile = GLib.KeyFile()
    keyfile.load_from_file(source, GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    if os.path.abspath(source) == os.path.abspath(target):
        # The user's own entry: kept, to put back when the Buffet menu is removed
        os.makedirs(BACKUP_DIR, exist_ok=True)
        shutil.copy2(source, os.path.join(BACKUP_DIR, app))
    groups, _length = keyfile.get_groups()
    for group in groups:
        command = key_value(keyfile, group, "Exec")
        if command and (group == "Desktop Entry" or group.startswith("Desktop Action ")):
            keyfile.set_string(group, "Exec", f"{shlex.quote(LAUNCHER)} {app} {command}")
    # A D-Bus activated application would be started without its Exec line, so without the launcher
    if key_value(keyfile, "Desktop Entry", "DBusActivatable") is not None:
        keyfile.set_boolean("Desktop Entry", "DBusActivatable", False)
    keyfile.set_boolean("Desktop Entry", MARK, True)
    os.makedirs(APPLICATIONS_DIR, exist_ok=True)
    keyfile.save_to_file(target)


def disable(app):
    """Takes the Buffet menu away from an application: its menu entry is as it was before."""
    target = os.path.join(APPLICATIONS_DIR, app)
    if not is_buffet_entry(target):
        return
    backup = os.path.join(BACKUP_DIR, app)
    if os.path.exists(backup):
        shutil.move(backup, target)
    else:
        os.remove(target)


def window_app(xid):
    """Which application a window belongs to: the id of its menu entry, as the launcher passed it on, or else
    its window class. The header bar module keeps it on the window; without it, it's in the environment the
    application was started with (unless the application overwrote that)."""
    app = remote.window_property(xid, "_BUFFET_MENU_APP")
    if app:
        return app
    pid = remote.window_number(xid, "_NET_WM_PID")
    if pid:
        try:
            with open(f"/proc/{pid}/environ", "rb") as source:
                for variable in source.read().split(b"\0"):
                    if variable.startswith(b"BUFFET_MENU_APP="):
                        return variable.split(b"=", 1)[1].decode()
        except OSError:
            pass
    # The instance and the class, each ended by a zero byte
    names = (remote.x11.get(xid, "WM_CLASS") or b"").split(b"\0")
    window_class = names[1].decode(errors="replace") if len(names) > 1 else ""
    return f"class:{window_class}" if window_class else "class:unknown"


def app_name(app):
    if app.startswith("class:"):
        return app.split(":", 1)[1]
    info = Gio.DesktopAppInfo.new(app)
    return info.get_display_name() if info else app


def write_own_entries():
    """Buffet Menu's own menu entry, so that it appears among the applications, and its icon."""
    os.makedirs(os.path.dirname(ICON_FILE), exist_ok=True)
    with open(ICON_FILE, "w", encoding="utf-8") as target:
        target.write(buffet.ICON_SVG)
    icons = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    for source, size, name in ICON_FILES:
        if os.path.exists(os.path.join(icons, source)):
            target = os.path.join(ICONS_DIR, size, "apps", name + ".svg")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(os.path.join(icons, source), target)
    # The folder's change time tells the icon themes of the applications menu and other programs to look again
    os.utime(ICONS_DIR)
    Gtk.IconTheme.get_default().rescan_if_needed()
    os.makedirs(APPLICATIONS_DIR, exist_ok=True)
    icon = APP_ICON_NAME if os.path.exists(os.path.join(icons, "buffet-menu.svg")) else ICON_NAME
    command = f"{shlex.quote(sys.executable)} {shlex.quote(os.path.abspath(__file__))}"
    with open(OWN_DESKTOP_FILE, "w", encoding="utf-8") as target:
        comment = "Every menu of your applications at once"
        target.write("[Desktop Entry]\nType=Application\nName=Buffet Menu\n"
                     f"Comment={comment}\n" +
                     "".join(f"Comment[{language}]={text}\n" for language, text in translations(comment).items()) +
                     f"Exec={command}\nIcon={icon}\nCategories=Settings;DesktopSettings;\n")


def set_autostart(enabled):
    if not enabled:
        if os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)
        return
    os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
    command = f"{shlex.quote(sys.executable)} {shlex.quote(os.path.abspath(__file__))} --service"
    with open(AUTOSTART_FILE, "w", encoding="utf-8") as target:
        target.write("[Desktop Entry]\nType=Application\nName=Buffet Menu\n"
                     "Comment=Shows the menus of your applications as a Buffet menu\n"
                     f"Exec={command}\nX-GNOME-Autostart-enabled=true\nNoDisplay=true\n")


# The service

class BuffetMenuApp(Gtk.Application):
    """The service: it keeps the Buffet menu applications' menu bars hidden, and shows their menus."""

    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.settings = None
        self.menu = None
        self.built = {}    # the Buffet menus shown before, by window: xid → (menus, WindowBuffet), the latest last
        self.published = None   # the menus of the window whose Buffet menu is open (a RemoteMenu)
        self.window = None
        self.shortcut = None
        self.registrar = None
        self.loaded = {}   # the menus loaded before, by window: (bus name, path) → RemoteMenu, the latest last

    def do_startup(self):
        Gtk.Application.do_startup(self)
        buffet.set_up_style()
        self.settings = load_settings()
        write_own_entries()
        # Set up and forgotten: Buffet Menu starts at login, unless that's been turned off in its window. Without it,
        # the applications' menu bars come back after a restart, until Buffet Menu is started again
        if not self.settings.get("start-at-login-chosen"):
            set_autostart(True)
            self.settings["start-at-login-chosen"] = True
            save_settings(self.settings)
        # The settings window's icon (in the window list and Alt+Tab)
        Gtk.Window.set_default_icon_name(APP_ICON_NAME)
        write_launcher()
        # The Buffet button of the header bar module asks for a window's menus with this action
        show_window = Gio.SimpleAction.new("show-window", GLib.VariantType.new("u"))
        show_window.connect("activate", lambda _action, xid: self.show_menu(False, xid.get_uint32()))
        self.add_action(show_window)
        # It also asks for them to be loaded as soon as the window appears, so that the first click is quick
        load_window = Gio.SimpleAction.new("load-window", GLib.VariantType.new("u"))
        load_window.connect("activate", lambda _action, xid: GLib.idle_add(self.load_window, xid.get_uint32()))
        self.add_action(load_window)
        # And it tells when an application turns out to have a header bar of its own, or no menu bar
        for name in ("own-header-bar", "no-menu-bar"):
            action = Gio.SimpleAction.new(name, GLib.VariantType.new("u"))
            action.connect("activate", lambda _action, xid, reason=name: GLib.idle_add(self.cannot_have, xid.get_uint32(),
                                                                                         reason))
            self.add_action(action)
        # Keeps running when the settings window closes
        self.hold()
        # Buffet Menu's module hides the applications' menu bars while Buffet Menu runs. Without it (not built),
        # appmenu-gtk-module hides them while a program owns this name, which Buffet Menu does then. Other
        # applications hide their menu bars too while it's owned, for a global menu (LibreOffice, Qt applications)
        if not os.path.exists(HEADER_BAR_MODULE):
            self.registrar = Gio.bus_own_name(Gio.BusType.SESSION, remote.REGISTRAR_NAME,
                                              Gio.BusNameOwnerFlags.NONE, None, None, None)
        if Keybinder is not None:
            Keybinder.init()
            self.bind_shortcut(self.settings["shortcut"])
        # The windows already open, if Buffet Menu was started after them: their menus are loaded too
        GLib.timeout_add(500, self.load_open_windows)

    def do_shutdown(self):
        if self.registrar:
            Gio.bus_unown_name(self.registrar)
        Gtk.Application.do_shutdown(self)

    def do_command_line(self, command_line):
        arguments = command_line.get_arguments()[1:]
        if "--quit" in arguments:
            self.quit()
        elif "--show" in arguments:
            GLib.idle_add(self.show_menu, True)
        elif "--service" not in arguments:
            self.show_settings()
        return 0

    # The keyboard shortcut

    def bind_shortcut(self, shortcut):
        if Keybinder is None:
            return False
        if self.shortcut:
            Keybinder.unbind_all(self.shortcut)
            self.shortcut = None
        if shortcut and Keybinder.bind(shortcut, lambda _keys: self.show_menu(True)):
            self.shortcut = shortcut
            return True
        return False

    # Showing an application's menus

    def show_menu(self, keyboard, xid=None):
        if self.menu is not None:
            return False
        started = time.monotonic()
        xid = xid or remote.active_window()
        published = remote.window_menu(xid)
        if published is None:
            self.notify(_("This window doesn't have the Buffet menu"),
                        _("Add its application in Buffet Menu's settings, then close and reopen it."))
            return False
        app = window_app(xid)
        entry = app_settings(self.settings, app)
        menus_published, menus = self.menus_of(published, remote.window_accels(xid))
        if not menus:
            entry["no-menu-bar"] = True
            self.changed()
            self.notify(_("{application} has no menu bar").format(application=app_name(app)),
                        _("Its menus can't be shown as a Buffet menu."))
            return False
        if entry["menus"] != len(menus) or entry["no-menu-bar"] or entry["own-header-bar"]:
            entry["menus"] = len(menus)
            entry["no-menu-bar"] = False
            entry["own-header-bar"] = False
            self.changed()
        loaded = time.monotonic()

        self.published = menus_published
        built_menus, menu = self.built.pop(xid, (None, None))
        kept = menu is not None and built_menus == menus
        if kept:
            # The same menus as last time: shown again, as built then
            menu.update_position()
        else:
            if menu is not None:
                self.destroy_menu(menu)
            menu = self.build_menu(xid, menus)
        self.configure(menu, entry)
        menu.set_disabled(menus_published.disabled_paths())
        self.menu = menu
        built = time.monotonic()
        self.menu.open(keyboard=keyboard)
        if DEBUG:
            done = time.monotonic()
            print(f"{app}: menu shown in {done - started:.2f} s (menus {loaded - started:.2f} s, "
                  f"{'kept' if kept else 'built'} {built - loaded:.2f} s, opened {done - built:.2f} s)", flush=True)
        return False

    def build_menu(self, xid, menus):
        menu = remote.WindowBuffet(xid, menus, lambda chosen, _accel: self.published.choose(chosen),
                                   self.on_menu_closed)
        menu.built_menus = menus
        return menu

    def configure(self, menu, entry):
        """Gives a window's Buffet menu its application's settings."""

        def on_layout_chosen(layout):
            # The layout the menu picked for itself, the first time it opened: kept, as if chosen in its settings
            entry["layout"] = layout
            self.changed()

        menu.set_layout(entry["layout"], entry["per-row"])
        menu.set_width(entry["width"])
        menu.set_rows(entry["rows"])
        menu.set_no_room(entry["no-room"])
        menu.set_shortcuts(entry["shortcuts"])
        menu.set_shortcut(self.settings["shortcut"])
        menu.on_layout_chosen = on_layout_chosen

    def keep(self, menu):
        """Keeps a window's Buffet menu built, to show again, for the last few windows."""
        self.built[menu.xid] = (menu.built_menus, menu)
        while len(self.built) > BUILT_MENUS:
            self.destroy_menu(self.built.pop(next(iter(self.built)))[1])

    def menus_of(self, where, accels):
        """A window's menus, from where they're published on D-Bus (see buffet_remote.window_menu()): loaded
        before and brought up to date, or else loaded now."""
        published = self.loaded.pop(where, None)
        if published is not None:
            published.accels = accels
            published.refresh()
            menus = published.menus()
        if published is None or not menus:
            published = remote.RemoteMenu(*where)
            published.accels = accels
            published.load()
            menus = published.menus()
        self.loaded[where] = published
        # The windows used last, a few of them
        while len(self.loaded) > LOADED_WINDOWS:
            del self.loaded[next(iter(self.loaded))]
        return published, menus

    def cannot_have(self, xid, reason):
        """An application that can't have the Buffet menu: it's taken off the list, and not offered again."""
        app = window_app(xid)
        if app.startswith("class:"):
            return False
        entry = app_settings(self.settings, app)
        # One whose menus were shown before has a menu bar: a window of it without one is another kind of window
        if entry["menus"]:
            return False
        entry[reason] = True
        disable(app)
        self.changed()
        why = _("It has a header bar of its own.") if reason == "own-header-bar" else _("It has no menu bar.")
        self.notify(_("{application} can't have the Buffet menu").format(application=app_name(app)),
                    why + " " + _("It was taken off Buffet Menu's list, and will be as before when you reopen it."))
        return False

    def load_open_windows(self):
        """Loads the menus of the windows open now that have the Buffet menu, one at a time, the window on top
        last, so that it's kept."""
        windows = [xid for xid in remote.x11.get(remote.x11.root, "_NET_CLIENT_LIST_STACKING") or []
                   if not window_app(xid).startswith("class:") and remote.window_menu(xid) is not None]
        windows = windows[-LOADED_WINDOWS:]

        def load_next():
            if windows:
                self.load_window(windows.pop(0))
            return bool(windows)

        GLib.idle_add(load_next)
        return False

    def load_window(self, xid):
        """Loads a window's menus and builds its Buffet menu, without showing it: its first opening is then as
        quick as the others."""
        where = remote.window_menu(xid)
        if where is None or where in self.loaded or self.menu is not None:
            return False
        started = time.monotonic()
        _published, menus = self.menus_of(where, remote.window_accels(xid))
        app = window_app(xid)
        if not menus or app.startswith("class:") or xid in self.built:
            return False
        menu = self.build_menu(xid, menus)
        self.configure(menu, app_settings(self.settings, app))
        menu.prepare()
        self.keep(menu)
        if DEBUG:
            print(f"{app}: menu loaded and built in {time.monotonic() - started:.2f} s", flush=True)
        return False

    def on_menu_closed(self):
        menu, self.menu = self.menu, None
        self.keep(menu)

    @staticmethod
    def destroy_menu(menu):

        def destroy():
            for popup in [menu.popup] + menu.sub_popups:
                popup.destroy()
            return False

        GLib.idle_add(destroy)

    def notify(self, title, body):
        notification = Gio.Notification.new(title)
        notification.set_body(body)
        self.send_notification("buffet-menu", notification)

    def changed(self):
        save_settings(self.settings)
        if self.window is not None:
            self.window.refresh()

    def show_settings(self):
        if self.window is None:
            self.window = SettingsWindow(self)
            self.window.connect("destroy", lambda _window: setattr(self, "window", None))
        self.window.present()


# The settings window

def program_name(info):
    """The name of the program an application's menu entry starts, past Buffet Menu's launcher: nemo for Files."""
    try:
        _ok, words = GLib.shell_parse_argv(info.get_commandline() or "")
    except GLib.Error:
        return ""
    if words and words[0] == LAUNCHER:
        words = words[2:]
    return os.path.basename(words[0]) if words else ""


class AppRow(Gtk.ListBoxRow):
    """An application in one of the two lists: its icon and name, and in the Buffet menu list, its status and
    the button to its settings."""

    def __init__(self, app, info, status=None, on_settings=None):
        super().__init__()
        self.app = app
        self.name = info.get_display_name() if info else app
        # What the search box finds it by: its name, and as the applications menu does, its program (nemo for
        # Files), its menu entry's keywords, generic name ("File Manager") and description
        words = [self.name, app.removesuffix(".desktop")]
        if info:
            words += [program_name(info), info.get_generic_name() or "", info.get_description() or ""]
            words += info.get_keywords() if isinstance(info, Gio.DesktopAppInfo) else []
        self.search_text = " ".join(word.lower() for word in words if word)
        box = Gtk.Box(spacing=10, margin=6)
        icon = Gtk.Image.new_from_gicon(info.get_icon(), Gtk.IconSize.DND) if info and info.get_icon() else \
            Gtk.Image.new_from_icon_name("application-x-executable", Gtk.IconSize.DND)
        box.pack_start(icon, False, False, 0)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        text.pack_start(Gtk.Label(label=self.name, xalign=0), False, False, 0)
        if status:
            status_label = Gtk.Label(label=status, xalign=0, wrap=True, max_width_chars=40)
            status_label.get_style_context().add_class("dim-label")
            text.pack_start(status_label, False, False, 0)
        box.pack_start(text, True, True, 0)
        if on_settings:
            gear = Gtk.Button(relief=Gtk.ReliefStyle.NONE, valign=Gtk.Align.CENTER,
                              tooltip_text=_("Settings of the Buffet menu of {application}").format(
                                  application=self.name))
            gear.set_image(Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON))
            gear.connect("clicked", lambda _button: on_settings(app, self.name))
            box.pack_end(gear, False, False, 0)
        self.add(box)


class SettingsWindow(Gtk.ApplicationWindow):
    """Which applications have the Buffet menu, each with its settings, and the service's settings."""

    def __init__(self, app):
        super().__init__(application=app, title=_("Buffet Menu"))
        self.app = app
        self.set_default_size(860, 600)
        header = Gtk.HeaderBar(title=_("Buffet Menu"), subtitle=_("Every menu of your applications at once"),
                               show_close_button=True)
        self.set_titlebar(header)

        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=18)
        self.add(page)
        missing = missing_packages()
        if missing:
            bar = Gtk.InfoBar(message_type=Gtk.MessageType.WARNING)
            text = Gtk.Label(xalign=0, wrap=True, selectable=True)
            text.set_markup("<b>" + GLib.markup_escape_text(_("Buffet Menu needs some packages that aren't installed:")) +
                            "</b>\n" + "\n".join(f"  • {GLib.markup_escape_text(item)}" for item in missing) + "\n" +
                            GLib.markup_escape_text(_("Install them with:")) +
                            f"  <tt>{GLib.markup_escape_text(INSTALL_COMMAND)}</tt>")
            bar.get_content_area().add(text)
            page.pack_start(bar, False, False, 0)

        lists = Gtk.Box(spacing=12)
        page.pack_start(lists, True, True, 0)

        # The applications that can have the Buffet menu
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left.pack_start(self.heading(_("Applications")), False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text=_("Search"))
        self.search.connect("search-changed", lambda _entry: self.available.invalidate_filter())
        left.pack_start(self.search, False, False, 0)
        self.available = Gtk.ListBox(activate_on_single_click=False)
        self.available.set_filter_func(self.matches_search)
        self.available.connect("row-activated", lambda _list, _row: self.add_selected())
        left.pack_start(self.framed(self.available), True, True, 0)
        self.show_all_apps = Gtk.CheckButton(label=_("Show all applications"),
                                             tooltip_text=_("Also those that can't have the Buffet menu, as far as "
                                                            "Buffet Menu can tell: GTK 2, GTK 4 or Qt ones, for example"))
        self.show_all_apps.connect("toggled", lambda _button: self.refresh())
        left.pack_start(self.show_all_apps, False, False, 0)
        lists.pack_start(left, True, True, 0)

        # + and −
        buttons = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        for icon, tooltip, action in (("list-add-symbolic", _("Give the Buffet menu to this application"),
                                       self.add_selected),
                                      ("list-remove-symbolic", _("Take the Buffet menu away from this application"),
                                       self.remove_selected)):
            button = Gtk.Button(tooltip_text=tooltip)
            button.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))
            button.connect("clicked", lambda _button, act=action: act())
            buttons.pack_start(button, False, False, 0)
        lists.pack_start(buttons, False, False, 0)

        # The applications that have it
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        right.pack_start(self.heading(_("With the Buffet menu")), False, False, 0)
        self.chosen = Gtk.ListBox()
        right.pack_start(self.framed(self.chosen), True, True, 0)
        note = Gtk.Label(label=_("Close and reopen an application after adding or removing it."), xalign=0, wrap=True)
        note.get_style_context().add_class("dim-label")
        right.pack_start(note, False, False, 0)
        lists.pack_start(right, True, True, 0)

        # The service's settings
        page.pack_start(Gtk.Separator(), False, False, 0)
        grid = Gtk.Grid(column_spacing=12, row_spacing=8)
        page.pack_start(grid, False, False, 0)
        self.shortcut_button = Gtk.Button(halign=Gtk.Align.START)
        self.shortcut_button.connect("clicked", self.on_change_shortcut)
        self.set_shortcut_label()
        self.shortcut_button.set_sensitive(Keybinder is not None)
        login = Gtk.Switch(active=os.path.exists(AUTOSTART_FILE), halign=Gtk.Align.START)
        login.connect("notify::active", self.on_start_at_login)
        rows = ((_("Keyboard shortcut"), self.shortcut_button, _("Shows the Buffet menu of the active window")),
                (_("Start at login"), login, _("Without it, the menu bars come back until Buffet Menu is started")))
        for row, (label, widget, note_text) in enumerate(rows):
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            grid.attach(widget, 1, row, 1, 1)
            hint = Gtk.Label(label=note_text, xalign=0)
            hint.get_style_context().add_class("dim-label")
            grid.attach(hint, 2, row, 1, 1)

        self.capturing = False
        self.connect("key-press-event", self.on_key_press)
        self.preferences = {}
        self.refresh()
        self.show_all()

    @staticmethod
    def heading(text):
        label = Gtk.Label(xalign=0)
        label.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")
        return label

    @staticmethod
    def framed(list_box):
        scrolled = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled.add(list_box)
        frame = Gtk.Frame()
        frame.add(scrolled)
        return frame

    def matches_search(self, row):
        # Every word typed, anywhere in what the row is found by: "file man" finds Files
        return all(word in row.search_text for word in self.search.get_text().lower().split())

    def refresh(self):
        """Fills the two lists again, from the menu entries and the settings."""
        chosen = buffet_apps()
        for list_box in (self.available, self.chosen):
            for row in list_box.get_children():
                list_box.remove(row)
        infos = sorted((info for info in Gio.AppInfo.get_all() if info.should_show() and can_use_buffet(info)),
                       key=lambda info: info.get_display_name().lower())
        show_all = self.show_all_apps.get_active()
        for info in infos:
            if info.get_id() in chosen:
                continue
            why_not = self.why_not(info)
            if why_not is None or show_all:
                self.available.add(AppRow(info.get_id(), info, why_not))
        for app in sorted(chosen, key=lambda app: app_name(app).lower()):
            self.chosen.add(AppRow(app, Gio.DesktopAppInfo.new(app), self.status(app), self.show_app_settings))
        self.available.show_all()
        self.chosen.show_all()

    def why_not(self, info):
        """Why an application can't have the Buffet menu, or None if it can: a GTK 3 one, with a menu bar."""
        entry = self.app.settings["apps"].get(info.get_id(), {})
        if entry.get("own-header-bar"):
            return _("Has a header bar of its own")
        if entry.get("no-menu-bar"):
            return _("Has no menu bar")
        toolkit = app_toolkit(info)
        return {"gtk3": None, "gtk4": _("A GTK 4 application"), "gtk2": _("A GTK 2 application"),
                "qt": _("A Qt application"), "admin": _("Runs as the administrator")}.get(
                    toolkit, _("Not a GTK 3 application"))

    def status(self, app):
        entry = self.app.settings["apps"].get(app, {})
        if entry.get("no-menu-bar"):
            return _("No menu bar found: this application can't have the Buffet menu")
        if entry.get("menus"):
            return ngettext("{count} menu", "{count} menus", entry["menus"]).format(count=entry["menus"])
        if os.path.exists(HEADER_BAR_MODULE):
            return _("Not opened yet: reopen it, then click its Buffet button")
        shortcut = Gtk.accelerator_get_label(*Gtk.accelerator_parse(self.app.settings["shortcut"]))
        return _("Not opened yet: reopen it, then press {shortcut} in it").format(shortcut=shortcut)

    def add_selected(self):
        row = self.available.get_selected_row()
        if row is not None:
            # Chosen anyway (with Show all applications): it's given another try
            entry = self.app.settings["apps"].get(row.app, {})
            entry.pop("own-header-bar", None)
            entry.pop("no-menu-bar", None)
            save_settings(self.app.settings)
            enable(row.app)
            self.refresh()

    def remove_selected(self):
        row = self.chosen.get_selected_row()
        if row is not None:
            disable(row.app)
            self.refresh()

    def show_app_settings(self, app, name):
        entry = app_settings(self.app.settings, app)
        dialog = self.preferences.get(app)
        if dialog is None:
            dialog = buffet.PreferencesDialog(self, entry, entry["menus"] or 12, lambda: save_settings(self.app.settings),
                                              title=_("Buffet menu of {application}").format(application=name))
            self.preferences[app] = dialog
        dialog.present()

    def on_start_at_login(self, switch, _param):
        set_autostart(switch.get_active())
        # Chosen: kept as it is from now on (see BuffetMenuApp.do_startup())
        self.app.settings["start-at-login-chosen"] = True
        save_settings(self.app.settings)

    # The keyboard shortcut: click the button, then press the keys

    def set_shortcut_label(self):
        shortcut = self.app.settings["shortcut"]
        self.shortcut_button.set_label(Gtk.accelerator_get_label(*Gtk.accelerator_parse(shortcut)) if shortcut
                                       else _("None"))

    def on_change_shortcut(self, _button):
        self.capturing = True
        self.shortcut_button.set_label(_("Press the keys… (Esc to cancel)"))

    def on_key_press(self, _window, event):
        if not self.capturing:
            return False
        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        if event.keyval == Gdk.KEY_Escape:
            self.capturing = False
            self.set_shortcut_label()
        elif Gtk.accelerator_valid(event.keyval, mods) and mods:
            shortcut = Gtk.accelerator_name(event.keyval, mods)
            if self.app.bind_shortcut(shortcut):
                self.app.settings["shortcut"] = shortcut
                save_settings(self.app.settings)
            else:
                # Taken by something else: keep the old one
                self.app.bind_shortcut(self.app.settings["shortcut"])
                self.app.notify(_("That shortcut is taken"), _("Choose another one for Buffet Menu."))
            self.capturing = False
            self.set_shortcut_label()
        return True


if __name__ == "__main__":
    sys.exit(BuffetMenuApp().run(sys.argv))
