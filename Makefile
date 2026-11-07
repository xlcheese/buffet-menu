# Buffet Menu: build the header bar module and the translations, and install the program.
#
#   make           build libbuffet-headerbar.so, compile po/*.po into locale/, and write the menu entry
#   make pot       update po/buffet-menu.pot from the source (after changing any text), and the .po files with it
#   make install   copy everything into $(DESTDIR)$(PREFIX); debian/rules runs this
#   make clean     remove what make built

APP_ID  = io.github.xlcheese.BuffetMenu
DOMAIN  = buffet-menu
VERSION = $(shell sed -n '1s/.*(\(.*\)).*/\1/p' debian/changelog)
PREFIX ?= /usr
LIBDIR  = $(PREFIX)/lib/buffet-menu

# The program: not the test window and the challenge (buffet_menu_test.py, buffet_challenge.py), shared on their own
SOURCES = buffet_menu.py buffet.py buffet_remote.py i18n.py
MODULE  = libbuffet-headerbar.so
DESKTOP = build/$(APP_ID).desktop
LOCALE  = locale
LANGUAGES = $(shell grep -v "^\s*#" po/LINGUAS)
MO_FILES  = $(foreach lang,$(LANGUAGES),$(LOCALE)/$(lang)/LC_MESSAGES/$(DOMAIN).mo)
# the menu entry's words that are translated (its Name, Buffet Menu, is not)
DESKTOP_KEYWORDS = --keyword= --keyword=Comment --keyword=Keywords

CFLAGS ?= -O2

all: $(MODULE) $(MO_FILES) $(DESKTOP)

$(MODULE): buffet-headerbar.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -shared -fPIC -o $@ $< $(LDFLAGS) $(shell pkg-config --cflags --libs gtk+-3.0)

$(LOCALE)/%/LC_MESSAGES/$(DOMAIN).mo: po/%.po
	mkdir -p $(dir $@)
	msgfmt --check --output-file=$@ $<

$(DESKTOP): data/$(APP_ID).desktop.in $(wildcard po/*.po)
	mkdir -p $(dir $@)
	msgfmt --desktop $(DESKTOP_KEYWORDS) --template=$< -d po --output-file=$@

POT_HEADER = --package-name="Buffet Menu" --package-version=$(VERSION) --copyright-holder="Wesley Hayslip" \
	--msgid-bugs-address=https://github.com/xlcheese/buffet-menu/issues

pot:
	xgettext --language=Python --from-code=UTF-8 --keyword=_ --keyword=ngettext:1,2 --add-comments=Translators \
		$(POT_HEADER) --output=po/$(DOMAIN).pot $(SOURCES)
	xgettext --language=C --from-code=UTF-8 --keyword=_ --add-comments=Translators --join-existing \
		$(POT_HEADER) --output=po/$(DOMAIN).pot buffet-headerbar.c
	xgettext --language=Desktop $(DESKTOP_KEYWORDS) --add-comments=Translators --join-existing \
		$(POT_HEADER) --output=po/$(DOMAIN).pot data/$(APP_ID).desktop.in
	for po in $(wildcard po/*.po); do msgmerge --quiet --update --backup=none $$po po/$(DOMAIN).pot; done

install: all
	install -Dm755 data/buffet-menu $(DESTDIR)$(PREFIX)/bin/buffet-menu
	install -d $(DESTDIR)$(LIBDIR)
	install -m644 $(SOURCES) $(DESTDIR)$(LIBDIR)/
	chmod 755 $(DESTDIR)$(LIBDIR)/buffet_menu.py
	install -m644 $(MODULE) $(DESTDIR)$(LIBDIR)/
	install -Dm644 $(DESKTOP) $(DESTDIR)$(PREFIX)/share/applications/$(APP_ID).desktop
	install -Dm644 icons/buffet-menu.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/buffet-menu.svg
	install -Dm644 icons/buffet-menu-16.svg $(DESTDIR)$(PREFIX)/share/icons/hicolor/16x16/apps/buffet-menu.svg
	install -Dm644 icons/buffet-menu-symbolic.svg \
		$(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps/buffet-menu-symbolic.svg
	for lang in $(LANGUAGES); do \
		install -Dm644 $(LOCALE)/$$lang/LC_MESSAGES/$(DOMAIN).mo \
			$(DESTDIR)$(PREFIX)/share/locale/$$lang/LC_MESSAGES/$(DOMAIN).mo; \
	done

clean:
	rm -rf $(LOCALE) $(MODULE) build

.PHONY: all pot install clean
