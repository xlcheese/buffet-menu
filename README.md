# Buffet menu

**Is it in Edit or Tools?** The Buffet menu shows every menu of an application at once, side by side,
from one button in the header bar. Everything is laid out in front of you, like a buffet: two clicks to
any command, and no more opening one menu after another to find it.

![The Buffet menu, with the menus of Xed](screenshots/buffet-menu.png)

It's an experiment for GTK3 applications in the Linux Mint XApp style. It keeps what makes a menu bar
easy to use (File, Edit, View…, keyboard shortcuts next to the items, access keys) and takes no more room
than a header bar's hamburger menu.

## Try the Buffet Menu Challenge

Which is quicker: a normal menu bar, or the Buffet menu? The challenge times you finding 12 commands in
the menus of Xed, Linux Mint's text editor: one round with the menu bar, one with the Buffet menu, in a
random order. It takes about 2 minutes, with the mouse only.

![The Buffet Menu Challenge](screenshots/challenge.png)

1. Download `buffet_challenge.py` and `buffet_menu_test.py` into the same folder (or the whole project:
   **Code → Download ZIP**).
2. In a terminal, in that folder:
   ```bash
   python3 buffet_challenge.py
   ```
3. At the end, click **Copy results** and paste them where you were asked to share them.

The menus don't do anything: they're only for finding. Nothing is saved, nothing is installed, and
nothing is sent anywhere. It doesn't need administrator rights. You can read the code first.

**Requirements:** Linux, with Python 3, GTK 3 and PyGObject. These come with Linux Mint, Ubuntu and most
GTK desktops (on Fedora: `python3-gobject`). On a Wayland session (Ubuntu's or Fedora's GNOME, for
example), start it with `GDK_BACKEND=x11 python3 buffet_challenge.py`, so that the Buffet menu can place
its pop-up.

## The test window

`buffet_menu_test.py` is a window with Xed's menus as a Buffet menu, to try it out freely:

```bash
python3 buffet_menu_test.py            # the Buffet menu, as set in Edit → Preferences
python3 buffet_menu_test.py --classic  # the same menus as a normal menu bar
```

Open the menu with the button at the top right, or with F10. Alt+F, Alt+E… open it at a menu, and the
arrow keys move across the columns. The status line shows how long it took to choose an item.

**Edit → Preferences** sets how the menu looks:

- **Menu layout:** one row, then equal rows (7 menus become 4 + 3); one row, then fill each row; two
  rows; or a fixed number of menus per row. Shorter rows line up on the right, near the button.
- **Row width:** as wide as the application's window, or the screen.
- **When there's no room below the title bar:** move the menu up (above the title bar, or over it), or
  change the rows to fit.
- **Rows:** lined up, or stacked up (each menu right under the one above it: a shorter menu).
- **Keyboard shortcuts:** next to each item, in a tooltip, or hidden.

![The preferences](screenshots/preferences.png)

When the menus are too tall for the screen, the menu scrolls.

## Other applications (experimental)

`buffet_remote.py` shows the menus of other GTK3 applications as a Buffet menu, without changing them. It
uses `appmenu-gtk-module`, the GTK module that global menu panels use, to read their menu bar:

```bash
sudo apt install appmenu-gtk3-module
python3 buffet_remote.py --registrar &   # hides the menu bars of the applications started with the module
GTK_MODULES=appmenu-gtk-module xed &     # start an application with the module
python3 buffet_remote.py                 # show the active window's menus: give this a keyboard shortcut
```

It has been tried with Xed, GIMP 3, Inkscape 1.x, Code::Blocks and Xcalculator, on X11. Other
applications with a GTK3 menu bar should work too.
Inkscape doesn't send its keyboard shortcuts with its menus, so they don't show. `buffet_remote.py --dump`
prints what the active window sends.

## License

GPL-3.0. See [LICENSE](LICENSE).
