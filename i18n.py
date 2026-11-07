"""Translations (gettext): _() for text people see, ngettext() for text with a number in it ("1 menu", "3 menus").

The translations are in po/, one file per language. build.sh compiles them into locale/ beside the scripts; once
installed, they're in the system's /usr/share/locale.
"""

import gettext
import locale
import os

TEXT_DOMAIN = "buffet-menu"
SOURCE_LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale")
# None: the system's own place for them
LOCALE_DIR = SOURCE_LOCALE_DIR if os.path.isdir(SOURCE_LOCALE_DIR) else None

try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error:
    pass
translation = gettext.translation(TEXT_DOMAIN, LOCALE_DIR, fallback=True)
_ = translation.gettext
ngettext = translation.ngettext


def translations(text):
    """A text in each language it's translated into, as {language: translation}: for a menu entry's Name[fr]=."""
    found = {}
    folder = LOCALE_DIR or "/usr/share/locale"
    try:
        languages = sorted(os.listdir(folder))
    except OSError:
        return found
    for language in languages:
        if os.path.exists(os.path.join(folder, language, "LC_MESSAGES", TEXT_DOMAIN + ".mo")):
            translated = gettext.translation(TEXT_DOMAIN, folder, languages=[language], fallback=True).gettext(text)
            if translated != text:
                found[language] = translated
    return found
