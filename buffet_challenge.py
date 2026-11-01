#!/usr/bin/python3
"""The Buffet Menu Challenge.

Two rounds of 12 commands to find and click with the mouse, in Xed's menus: one round with Xed's normal
menu bar, one with the buffet menu, in a random order. Each command is timed from clicking Start to
clicking the command. At the end, the results are ready to copy into a post.

    python3 buffet_challenge.py

It needs buffet_menu_test.py in the same folder. Nothing is saved or sent anywhere.
"""

import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buffet_menu_test as buffet  # noqa: E402  (sets up the GTK versions)

from gi.repository import Gdk, GLib, Gtk  # noqa: E402

# The commands to find: (what the player is told, the item as the menus report it)
TASKS = [
    ("Save As…", "File → Save As..."),
    ("Copy", "Edit → Copy"),
    ("Sort lines", "Edit → Sort lines"),
    ("Insert Date and Time…", "Edit → Insert Date and Time..."),
    ("Overview Map", "View → Overview Map"),
    ("Larger Text", "View → Larger Text"),
    ("Replace", "Search → Replace"),
    ("Go to Line…", "Search → Go to Line..."),
    ("Document Statistics", "Tools → Document Statistics"),
    ("Move to New Window", "Documents → Move to New Window"),
    ("Keyboard Shortcuts", "Help → Keyboard Shortcuts"),
    ("README.md, one of the recent files", "File → Recents → 2. README.md"),
]
MENU_BAR = "Menu bar"
BUFFET = "Buffet menu"
WINDOW_SIZE = (1000, 650)

WELCOME = f"""Welcome to the Buffet Menu Challenge!

Which is quicker for finding a command: a normal menu bar, or the buffet menu, which shows every
menu at once? Let's find out, with the menus of Xed, Linux Mint's text editor.

There are two rounds of {len(TASKS)} commands: one with Xed's normal menu bar, and one with the buffet
menu, in a random order. The commands are the same in both rounds, in a different order.

Before you start: size this window the way you normally use Xed, maximised or the size you usually
keep it. The second round opens at the same size.

For each command:
  1. Click Start.
  2. Find the command in the menus and click it, as quickly as you can.

Use the mouse only. You're told the command's name, not which menu it's in. If you click the
wrong one, it counts as a miss: keep looking, the clock keeps running.

At the end, you'll get your results to copy and post. Nothing is saved or sent anywhere.
"""

CSS = b"""
.challenge-task {
    font-size: 150%;
}
"""


def seconds(value):
    return f"{value:.1f} s"


def times(count):
    return {1: "once", 2: "twice"}.get(count, f"{count} times")


class Challenge:
    """The two rounds, and their results."""

    def __init__(self, app):
        self.app = app
        self.order = random.sample([MENU_BAR, BUFFET], 2)
        self.results = {}   # round: [(task, seconds, misses, menus opened)]
        self.window = None
        self.buffet_layout = "its starting layout"
        self.geometry = None   # where the first window was, so the second one is in the same place
        self.maximized = False
        self.show_round(0)

    def show_round(self, index):
        if self.window is not None:
            self.geometry = self.window.get_position() + self.window.get_size()
            self.maximized = self.window.is_maximized()
            self.window.destroy()
        self.window = ChallengeWindow(self, self.order[index], index)
        if self.maximized:
            self.window.maximize()
        elif self.geometry:
            x, y, width, height = self.geometry
            self.window.move(x, y)
            self.window.resize(width, height)
        self.window.show_all()

    def round_done(self, kind, results):
        self.results[kind] = results
        if len(self.results) < len(self.order):
            self.window.offer_next_round(self.order[len(self.results)])
        else:
            self.window.show_results(self.report())

    def report(self):
        """The results, as a table to paste in a post (Markdown, as Reddit shows it)."""
        lines = [f"**Buffet Menu Challenge**: {len(TASKS)} commands in Xed's menus, mouse only", "",
                 "| Round | Total | Average | Misses | Menus opened |", "|---|---|---|---|---|"]
        totals, opened = {}, {}
        for number, kind in enumerate(self.order, start=1):
            results = self.results[kind]
            totals[kind] = sum(time_taken for _task, time_taken, _misses, _opened in results)
            misses = sum(missed for _task, _time_taken, missed, _opened in results)
            opened[kind] = sum(menus for _task, _time_taken, _missed, menus in results)
            lines.append(f"| {kind} (round {number}) | {seconds(totals[kind])} | "
                         f"{seconds(totals[kind] / len(results))} | {misses} | {opened[kind]} |")
        difference = (totals[MENU_BAR] - totals[BUFFET]) / totals[MENU_BAR] * 100
        lines += ["", f"Buffet menu: {abs(difference):.0f}% {'faster' if difference >= 0 else 'slower'} "
                      f"than the menu bar", "",
                  f"To find {len(TASKS)} commands, the menu bar's menus were opened {times(opened[MENU_BAR])}, "
                  f"the buffet menu {times(opened[BUFFET])}", "",
                  f"| Command | {MENU_BAR} | {BUFFET} |", "|---|---|---|"]
        by_task = {kind: {task: (time_taken, missed) for task, time_taken, missed, _opened in self.results[kind]}
                 for kind in self.order}
        for task, _path in TASKS:
            cells = []
            for kind in (MENU_BAR, BUFFET):
                time_taken, missed = by_task[kind][task]
                cells.append(seconds(time_taken) + (f" ({missed} missed)" if missed else ""))
            lines.append(f"| {task} | {cells[0]} | {cells[1]} |")
        monitor = Gdk.Display.get_default().get_monitor_at_window(self.window.get_window())
        screen = monitor.get_geometry()
        width, height = self.window.get_size()
        window = "maximised" if self.window.is_maximized() else f"{width}×{height}"
        lines += ["", f"Screen {screen.width}×{screen.height}, window {window}, "
                      f"buffet menu in {self.buffet_layout}"]
        return "\n".join(lines)


class ChallengeWindow(Gtk.ApplicationWindow):
    """One round: Xed's menus as a menu bar or a buffet menu, and the command to find."""

    def __init__(self, challenge, kind, index):
        super().__init__(application=challenge.app, title="Buffet Menu Challenge")
        self.set_default_size(*WINDOW_SIZE)
        self.challenge = challenge
        self.kind = kind
        self.tasks = random.sample(TASKS, len(TASKS))
        self.task = -1
        self.started = None      # when Start was clicked for the current command, or None between commands
        self.misses = 0
        self.opened = 0          # how many times a menu was opened, looking for the current command
        self.results = []
        round_title = f"Round {index + 1} of 2: {kind}"

        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(layout)
        if kind == MENU_BAR:
            self.set_title(f"Buffet Menu Challenge: {round_title}")
            # The shortcuts are shown, as in Xed, but don't work: mouse only
            builder = buffet.MenuBuilder(self.on_chosen, Gtk.AccelGroup())
            self.menus = Gtk.MenuBar()
            for title, entries in buffet.XED_MENUS:
                item = Gtk.MenuItem.new_with_mnemonic(title)
                submenu = builder.menu(entries, [buffet.plain(title)])
                # Moving across the menu bar opens one menu after another: each one counts
                submenu.connect("show", self.on_menu_opened)
                item.set_submenu(submenu)
                self.menus.append(item)
            layout.pack_start(self.menus, False, False, 0)
        else:
            header = Gtk.HeaderBar(title="Buffet Menu Challenge", subtitle=round_title, show_close_button=True)
            self.menus = Gtk.ToggleButton(tooltip_text="Menu")
            self.menus.set_image(Gtk.Image.new_from_icon_name("buffet-menu-symbolic", Gtk.IconSize.BUTTON))
            header.pack_end(self.menus)
            self.set_titlebar(header)
            # The buffet menu as it starts, whatever the test window's preferences say
            self.buffet = buffet.BuffetMenu(self.menus, header, buffet.XED_MENUS, self.on_chosen, lambda: None)
            self.menus.connect("toggled", self.on_buffet_toggled)
        self.menus.set_sensitive(False)

        # The command to find, and the button that starts the clock, in the middle: as far from the menu bar
        # at the top left as from the buffet menu's button at the top right
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=24)
        self.prompt = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        self.prompt.get_style_context().add_class("challenge-task")
        self.progress = Gtk.Label()
        self.progress.get_style_context().add_class("dim-label")
        self.button = Gtk.Button(halign=Gtk.Align.CENTER)
        self.button.get_style_context().add_class("suggested-action")
        self.button.connect("clicked", self.on_button)
        panel.pack_start(self.prompt, False, False, 0)
        panel.pack_start(self.progress, False, False, 0)
        panel.pack_start(self.button, False, False, 0)
        layout.pack_start(panel, False, False, 0)

        self.text = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD, monospace=True,
                                 left_margin=12, right_margin=12, top_margin=12, bottom_margin=12)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.text)
        layout.pack_start(Gtk.Separator(), False, False, 0)
        layout.pack_start(scrolled, True, True, 0)

        if index == 0:
            self.text.get_buffer().set_text(WELCOME)
            self.prompt.set_markup(f"<b>{round_title}</b>")
            self.button.set_label("Start the challenge")
        else:
            self.text.get_buffer().set_text(f"{round_title}. The same commands as in round 1, in a different order.")
            self.prompt.set_markup(f"<b>{round_title}</b>")
            self.button.set_label("Start round 2")
        self.next_action = self.next_task

    # The round

    def on_button(self, _button):
        self.next_action()

    def next_task(self):
        """Shows the next command to find, with the button that starts the clock."""
        self.task += 1
        self.misses = 0
        self.opened = 0
        name, _path = self.tasks[self.task]
        self.prompt.set_markup(f"Find and click: <b>{GLib.markup_escape_text(name)}</b>")
        self.progress.set_text(f"{self.kind}: command {self.task + 1} of {len(self.tasks)}")
        self.button.set_label("Start")
        self.button.set_sensitive(True)
        self.next_action = self.start_task

    def start_task(self):
        self.started = time.monotonic()
        self.button.set_sensitive(False)
        self.button.set_label("Go!")
        self.menus.set_sensitive(True)

    def on_chosen(self, path, _accel):
        if self.started is None:
            return
        name, wanted = self.tasks[self.task]
        if path != wanted:
            self.misses += 1
            self.progress.set_text(f"Not that one: keep looking! ({self.misses} missed)")
            return
        self.results.append((name, time.monotonic() - self.started, self.misses, self.opened))
        self.started = None
        self.menus.set_sensitive(False)
        if self.task + 1 < len(self.tasks):
            self.next_task()
        else:
            self.challenge.round_done(self.kind, self.results)

    def on_menu_opened(self, _menu):
        if self.started is not None:
            self.opened += 1

    def on_buffet_toggled(self, button):
        if button.get_active():
            self.on_menu_opened(None)
            self.buffet.open()
            self.challenge.buffet_layout = f"{self.buffet.layout_name()} ({self.buffet.per_row} per row)"
        else:
            self.buffet.close()

    def offer_next_round(self, kind):
        total = sum(time_taken for _task, time_taken, _misses, _opened in self.results)
        misses = sum(missed for _task, _time_taken, missed, _opened in self.results)
        self.prompt.set_markup(f"<b>Round 1 done:</b> {seconds(total)}, {misses} missed")
        self.progress.set_text(f"Next: the same commands with the {kind.lower()}")
        self.button.set_label(f"On to round 2: {kind}")
        self.button.set_sensitive(True)
        self.next_action = lambda: self.challenge.show_round(1)

    def show_results(self, report):
        self.prompt.set_markup("<b>All done!</b> Here are your results")
        self.progress.set_text("Copy them into your post: Reddit shows the tables as tables")
        self.text.get_buffer().set_text(report)
        self.button.set_label("Copy results")
        self.button.set_sensitive(True)
        self.next_action = lambda: self.copy(report)

    def copy(self, report):
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(report, -1)
        self.button.set_label("Copied!")
        GLib.timeout_add_seconds(2, lambda: self.button.set_label("Copy results") and False)


class ChallengeApp(Gtk.Application):

    def __init__(self):
        super().__init__(application_id=None)

    def do_activate(self):
        buffet.set_up_style()
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.challenge = Challenge(self)


if __name__ == "__main__":
    ChallengeApp().run(None)
