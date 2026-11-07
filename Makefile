# Buffet Menu: build the header bar module and the translations.
#
#   make           build libbuffet-headerbar.so and compile po/*.po into locale/
#   make pot       update po/buffet-menu.pot from the source (after changing any text), and the .po files with it
#   make clean     remove what make built

DOMAIN  = buffet-menu
VERSION = 0.1.0
SOURCES = buffet_menu.py buffet.py buffet_remote.py
MODULE  = libbuffet-headerbar.so
LOCALE  = locale
LANGUAGES = $(shell grep -v "^\s*#" po/LINGUAS)
MO_FILES  = $(foreach lang,$(LANGUAGES),$(LOCALE)/$(lang)/LC_MESSAGES/$(DOMAIN).mo)

all: $(MODULE) $(MO_FILES)

$(MODULE): buffet-headerbar.c
	gcc -shared -fPIC -O2 -o $@ $< $(shell pkg-config --cflags --libs gtk+-3.0)

$(LOCALE)/%/LC_MESSAGES/$(DOMAIN).mo: po/%.po
	mkdir -p $(dir $@)
	msgfmt --check --output-file=$@ $<

POT_HEADER = --package-name="Buffet Menu" --package-version=$(VERSION) --copyright-holder="Wesley Hayslip" \
	--msgid-bugs-address=https://github.com/xlcheese/buffet-menu/issues

pot:
	xgettext --language=Python --from-code=UTF-8 --keyword=_ --keyword=ngettext:1,2 --add-comments=Translators \
		$(POT_HEADER) --output=po/$(DOMAIN).pot $(SOURCES)
	xgettext --language=C --from-code=UTF-8 --keyword=_ --add-comments=Translators --join-existing \
		$(POT_HEADER) --output=po/$(DOMAIN).pot buffet-headerbar.c
	for po in $(wildcard po/*.po); do msgmerge --quiet --update --backup=none $$po po/$(DOMAIN).pot; done

clean:
	rm -rf $(LOCALE) $(MODULE)

.PHONY: all pot clean
