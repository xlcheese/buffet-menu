#!/bin/sh
# Builds Buffet Menu's header bar module. Needs: sudo apt install build-essential libgtk-3-dev
cd "$(dirname "$0")" && gcc -shared -fPIC -O2 -o libbuffet-headerbar.so buffet-headerbar.c $(pkg-config --cflags --libs gtk+-3.0) && echo "Built libbuffet-headerbar.so"
