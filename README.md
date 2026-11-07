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
3. **Before you start, size the window the way you normally use Xed**: maximised, or the size you
   usually keep it. The second round opens at the same size.
   You'll also be asked how often you use Xed: if you use it a lot, you know where its menu bar keeps
   things, and the results show that.
4. At the end, click **Copy results** and paste them where you were asked to share them.

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

## The Buffet Menu app

Buffet Menu gives your own applications the Buffet menu, without changing them. Choose the applications
in its window: they then open with a header bar and a Buffet button, which shows all of their menus at
once. **Ctrl+Alt+N** opens and closes it from the keyboard.

![The Buffet Menu app](screenshots/app.png)

### Install

On Linux Mint 22 (or Ubuntu 24.04), download `buffet-menu_0.1.0_amd64.deb` from the
[Releases](https://github.com/xlcheese/buffet-menu/releases) page, then:

```bash
sudo apt install ./buffet-menu_0.1.0_amd64.deb
```

apt installs what it needs with it (`appmenu-gtk3-module`, `gir1.2-keybinder-3.0`). Then:

1. Open **Buffet Menu** from the applications menu (it's in Preferences).
2. Choose an application on the left and click **+**.
3. Close the application and open it again from the menu: its menu bar is gone, and the Buffet button
   in its header bar shows all of its menus.

Buffet Menu starts at login from then on, and does its work quietly in the background: set it up, and
forget about it.

### Using it

- **Each application has its own settings:** click the gear next to it. The first time its Buffet menu
  opens, it picks one row for an application with up to 4 menus, two rows for more.
- **Keyboard shortcut and Start at login** are at the bottom of the window. Start at login is on from
  the start; without it, the applications' menu bars come back until Buffet Menu is started again.
- **The menu works like a menu bar's:** keyboard shortcuts next to the items, ticks and choices that
  follow the application, greyed-out items it has disabled, access keys with Alt, and the arrow keys.
- **To stop it:** `buffet-menu --quit` (the menu bars come back). **To remove it:** remove each
  application with **−** first, so that they're as they were, then `sudo apt remove buffet-menu`.

### What it works with

GTK 3 applications that have a menu bar, on X11 (Cinnamon, MATE and Xfce on Linux Mint). Tried with Xed,
Nemo, LibreOffice, Inkscape 1.x, Pluma, Mousepad, gedit, Code::Blocks, Update Manager and xl-Calculator.

- The list only offers GTK 3 applications. One that turns out to have a header bar of its own (and no
  menu bar behind it), or no menu bar, is taken off the list when it first opens. Tick **Show all
  applications** to see the others, and why they're left out.
- Not with GTK 2 applications (GIMP 2.10), GTK 4, Qt, Flatpak or Snap applications, or Wayland.
- The LibreOffice applications share one program: whichever opens first decides whether they all have
  the Buffet menu.
- Update Manager starts at login on its own: it has the Buffet menu once it's been reopened from the menu.
- Xed 3.6 (Linux Mint 22) doesn't tell GTK when it's maximized, so its maximize button stays as it is;
  Xed's next version fixes it.

### How it works

`+` puts a copy of the application's menu entry in `~/.local/share/applications`, which starts it with
`appmenu-gtk-module`, the module that global menu panels use to read an application's menu bar over
D-Bus, and with Buffet Menu's own module (`buffet-headerbar.c`). That one gives the main window its
header bar and Buffet button, and hides the menu bar while Buffet Menu runs; other applications keep
theirs. `−` deletes the copy, and the application is as it was.

### Run it from the source

```bash
sudo apt install appmenu-gtk3-module gir1.2-keybinder-3.0 build-essential libgtk-3-dev gettext git
git clone https://github.com/xlcheese/buffet-menu.git
cd buffet-menu
./build.sh                  # the header bar module and the translations
python3 buffet_menu.py      # its window; python3 buffet_menu.py --quit stops it
```

`git pull` and `./build.sh` bring it up to date. The files:

| File | What it is |
|---|---|
| `buffet_menu.py` | The app: its window, and the service that shows the Buffet menus |
| `buffet.py` | The Buffet menu itself, and its settings |
| `buffet_remote.py` | Reads another application's menus over D-Bus |
| `buffet-headerbar.c` | The GTK module that gives the applications their header bar |
| `i18n.py`, `po/` | The translations |
| `debian/`, `Makefile` | The package: `dpkg-buildpackage -b`, or on GitHub, a version tag (see `.github/workflows/deb.yml`) |
| `buffet_challenge.py`, `buffet_menu_test.py` | The challenge and the test window, which stand on their own |

## Translate

Buffet Menu uses gettext. Spanish, French, German, and Brazilian Portuguese are included as drafts
that still need a review by native speakers: corrections are very welcome. `./build.sh` compiles them
(it needs `gettext`: `sudo apt install gettext`), and `make pot` updates `po/buffet-menu.pot` after any
text in the program changes.

To start a new language, for example Italian:

```
msginit -i po/buffet-menu.pot -l it -o po/it.po
```

then translate the `msgstr` lines in `po/it.po` (with Poedit, or any text editor), add `it` to
`po/LINGUAS`, and run `./build.sh`. To try it: `LANGUAGE=it python3 buffet_menu.py`. Text in braces, such
as `{application}`, stays as it is, and an underscore marks the letter of an access key (`_Hide`).

## License

GPL-3.0. See [LICENSE](LICENSE).
