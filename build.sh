#!/bin/sh
# Builds Buffet Menu's header bar module, and its translations if the gettext tools are installed.
# Needs: sudo apt install build-essential libgtk-3-dev gettext
cd "$(dirname "$0")" || exit 1
gcc -shared -fPIC -O2 -o libbuffet-headerbar.so buffet-headerbar.c $(pkg-config --cflags --libs gtk+-3.0) &&
    echo "Built libbuffet-headerbar.so" || exit 1
if command -v msgfmt > /dev/null; then
    for language in $(grep -v "^\s*#" po/LINGUAS); do
        mkdir -p "locale/$language/LC_MESSAGES"
        msgfmt --check --output-file="locale/$language/LC_MESSAGES/buffet-menu.mo" "po/$language.po" || exit 1
    done
    echo "Built the translations: $(grep -v "^\s*#" po/LINGUAS | tr '\n' ' ')"
else
    echo "Translations not built: sudo apt install gettext"
fi
