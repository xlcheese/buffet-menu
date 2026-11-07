/* The Buffet menu's header bar, for applications that have a menu bar and no header bar of their own.
 *
 * A GTK 3 module, loaded by Buffet Menu's launcher into the applications given the Buffet menu. Just before
 * an application's main window is first shown, it gives the window a header bar: the window's title, its
 * buttons, and the Buffet button, which asks Buffet Menu to show the window's menus. The window keeps where
 * the header bar and the button are in the _BUFFET_MENU_HEADER property, for Buffet Menu to put the menu
 * under them. Some applications, such as Inkscape and GIMP, add their menu bar to the window after that:
 * the window gets its header bar then. It also keeps the keyboard shortcuts that the application registered
 * with GTK in the _BUFFET_MENU_ACCELS property: a menu that GTK publishes itself (Inkscape's, for example)
 * doesn't include them. A window with a header bar of its own and a menu bar that's only published (gedit's) gets
 * the Buffet button in its header bar. While Buffet Menu is running, the application's menu bars are hidden (see
 * set_service_running()). And it tells Buffet Menu when the application's first main window has a header bar of
 * its own, or no menu bar: the application can't have the Buffet menu.
 *
 * Build: gcc -shared -fPIC -O2 -o libbuffet-headerbar.so buffet-headerbar.c $(pkg-config --cflags --libs gtk+-3.0)
 */

#include <gtk/gtk.h>
#include <gdk/gdkx.h>

#define SERVICE "io.github.xlcheese.BuffetMenu"
#define SERVICE_PATH "/io/github/xlcheese/BuffetMenu"
#define HEADER_PROPERTY "_BUFFET_MENU_HEADER"
#define ACCELS_PROPERTY "_BUFFET_MENU_ACCELS"
#define LABEL_ACCELS_PROPERTY "_BUFFET_MENU_LABEL_ACCELS"
#define APP_PROPERTY "_BUFFET_MENU_APP"
/* Buffet Menu sets it to "1" while the window's Buffet menu is open, "0" when it closes */
#define OPEN_PROPERTY "_BUFFET_MENU_OPEN"
#define ICON_NAME "buffet-menu-symbolic"

static void (*original_realize) (GtkWidget *widget);
/* Whether Buffet Menu is running: the application's menu bars are hidden while it is */
static gboolean service_running = FALSE;
/* The application's menu entry, as Buffet Menu's launcher passed it on (BUFFET_MENU_APP): kept on its windows, for
 * Buffet Menu to use its settings. (Buffet Menu used to read it from the environment the application was started
 * with, but some applications overwrite that, with setproctitle: Linux Mint's Update Manager) */
static gchar *app_id = NULL;

static void
find_menu_bar (GtkWidget *widget, gpointer found)
{
  if (*(gboolean *) found)
    return;
  if (GTK_IS_MENU_BAR (widget))
    *(gboolean *) found = TRUE;
  else if (GTK_IS_CONTAINER (widget))
    gtk_container_forall (GTK_CONTAINER (widget), find_menu_bar, found);
}

/* A normal window, not a dialog */
static gboolean
is_main_window (GtkWindow *window)
{
  return !GTK_IS_DIALOG (window) && gtk_window_get_window_type (window) == GTK_WINDOW_TOPLEVEL &&
         gtk_window_get_type_hint (window) == GDK_WINDOW_TYPE_HINT_NORMAL &&
         gtk_window_get_transient_for (window) == NULL && gtk_window_get_decorated (window);
}

/* Whether a window has a menu bar: its own, or the application's */
static gboolean
has_menu_bar (GtkWindow *window)
{
  gboolean found = FALSE;

  gtk_container_forall (GTK_CONTAINER (window), find_menu_bar, &found);
  /* Or the application's menu bar, that GTK shows in its windows, or publishes instead with appmenu-gtk-module
   * (Inkscape's, for example) */
  if (!found && GTK_IS_APPLICATION_WINDOW (window) && gtk_window_get_application (window) != NULL)
    found = gtk_application_get_menubar (gtk_window_get_application (window)) != NULL &&
            gtk_application_window_get_show_menubar (GTK_APPLICATION_WINDOW (window));
  return found;
}

/* An application's main window: a normal window with a menu bar, not a dialog, and without a header bar */
static gboolean
wants_header_bar (GtkWindow *window)
{
  return gtk_window_get_titlebar (window) == NULL && is_main_window (window) &&
         has_menu_bar (window);
}

/* The menu bars: hidden while Buffet Menu is running, and shown again when it stops. appmenu-gtk-module, which
 * publishes them when they're set up, shrinks them to nothing while the gtk-shell-shows-menubar setting is on,
 * as for a global menu, and so does GTK for a GtkApplication's menu bar (Inkscape's). The setting is kept on
 * while Buffet Menu runs: appmenu-gtk-module itself only turns it on while com.canonical.AppMenu.Registrar is
 * owned, which Buffet Menu used to do, but other applications watch that name too, and hide their menu bars for
 * a global menu that Buffet Menu can't show (LibreOffice, Qt applications). A menu bar hidden outright wouldn't
 * be set up, nor published. */
static void
keep_setting (GtkSettings *settings, GParamSpec *pspec, gpointer data)
{
  gboolean shows;

  g_object_get (settings, "gtk-shell-shows-menubar", &shows, NULL);
  if (shows != service_running)
    g_object_set (settings, "gtk-shell-shows-menubar", service_running, NULL);
}

static void
set_service_running (gboolean running)
{
  static gboolean watching = FALSE;
  GtkSettings *settings = gtk_settings_get_default ();

  service_running = running;
  if (settings == NULL)
    return;
  if (!watching)
    {
      watching = TRUE;
      /* appmenu-gtk-module turns it off when it finds no registrar */
      g_signal_connect (settings, "notify::gtk-shell-shows-menubar", G_CALLBACK (keep_setting), NULL);
    }
  keep_setting (settings, NULL, NULL);
}

static void
on_service_appeared (GDBusConnection *connection, const gchar *name, const gchar *owner, gpointer data)
{
  set_service_running (TRUE);
}

static void
on_service_vanished (GDBusConnection *connection, const gchar *name, gpointer data)
{
  set_service_running (FALSE);
}

/* Activates one of Buffet Menu's actions for a window: show-window or load-window, with its X11 id */
static void
ask_service (GtkWidget *widget, const gchar *action)
{
  GdkWindow *window = gtk_widget_get_window (gtk_widget_get_toplevel (widget));
  GDBusConnection *bus;
  GVariantBuilder parameter;

  if (window == NULL || !GDK_IS_X11_WINDOW (window))
    return;
  bus = g_bus_get_sync (G_BUS_TYPE_SESSION, NULL, NULL);
  if (bus == NULL)
    return;
  g_variant_builder_init (&parameter, G_VARIANT_TYPE ("av"));
  g_variant_builder_add (&parameter, "v", g_variant_new_uint32 (gdk_x11_window_get_xid (window)));
  g_dbus_connection_call (bus, SERVICE, SERVICE_PATH, "org.gtk.Actions", "Activate",
                          g_variant_new ("(sava{sv})", action, &parameter, NULL),
                          NULL, G_DBUS_CALL_FLAGS_NONE, -1, NULL, NULL, NULL);
  g_object_unref (bus);
}

/* The Buffet button stays pressed while the window's Buffet menu is open, as a menu button does. Buffet Menu shows
 * the menu, in its own process: it says when it's open with the window's _BUFFET_MENU_OPEN property */
static void on_buffet_toggled (GtkToggleButton *button, gpointer data);

static gboolean
menu_is_open (GtkWidget *widget)
{
  GdkWindow *window = gtk_widget_get_window (gtk_widget_get_toplevel (widget));
  GdkAtom type;
  gint format, length;
  guchar *data = NULL;
  gboolean open = FALSE;

  if (window != NULL &&
      gdk_property_get (window, gdk_atom_intern_static_string (OPEN_PROPERTY),
                        gdk_atom_intern_static_string ("UTF8_STRING"), 0, 4, FALSE, &type, &format, &length, &data))
    {
      open = length > 0 && data[0] == '1';
      g_free (data);
    }
  return open;
}

static void
set_button_pressed (GtkWidget *button, gboolean pressed)
{
  g_signal_handlers_block_by_func (button, on_buffet_toggled, NULL);
  gtk_toggle_button_set_active (GTK_TOGGLE_BUTTON (button), pressed);
  g_signal_handlers_unblock_by_func (button, on_buffet_toggled, NULL);
}

/* A moment after a click: if no menu opened (Buffet Menu isn't running, say), the button comes back up */
static gboolean
check_menu_opened (gpointer button)
{
  set_button_pressed (button, menu_is_open (button));
  g_object_unref (button);
  return G_SOURCE_REMOVE;
}

static void
on_buffet_toggled (GtkToggleButton *button, gpointer data)
{
  if (!gtk_toggle_button_get_active (button))
    {
      /* Clicked while its menu is open: the menu closes itself on a click outside it */
      set_button_pressed (GTK_WIDGET (button), menu_is_open (GTK_WIDGET (button)));
      return;
    }
  ask_service (GTK_WIDGET (button), "show-window");
  g_timeout_add (500, check_menu_opened, g_object_ref (button));
}

static gboolean
on_property_changed (GtkWidget *window, GdkEventProperty *event, GtkWidget *button)
{
  if (event->atom == gdk_atom_intern_static_string (OPEN_PROPERTY))
    set_button_pressed (button, menu_is_open (button));
  return FALSE;
}

/* The application's keyboard shortcuts, as "action=shortcut|action=shortcut…", with the actions' detailed names */
static void
publish_accels (GtkWidget *widget)
{
  GtkApplication *application = gtk_window_get_application (GTK_WINDOW (widget));
  GdkWindow *window = gtk_widget_get_window (widget);
  gchar **actions, **accels;
  GString *text;
  guint i;

  if (application == NULL || window == NULL)
    return;
  text = g_string_new (NULL);
  actions = gtk_application_list_action_descriptions (application);
  for (i = 0; actions[i] != NULL; i++)
    {
      accels = gtk_application_get_accels_for_action (application, actions[i]);
      if (accels[0] != NULL)
        g_string_append_printf (text, "%s%s=%s", text->len ? "|" : "", actions[i], accels[0]);
      g_strfreev (accels);
    }
  g_strfreev (actions);
  gdk_property_change (window, gdk_atom_intern_static_string (ACCELS_PROPERTY),
                       gdk_atom_intern_static_string ("UTF8_STRING"), 8, GDK_PROP_MODE_REPLACE,
                       (const guchar *) text->str, text->len);
  g_string_free (text, TRUE);
}

/* The shortcuts shown in the menu bar's items, by their labels: "File\x1fSave\t<Primary>s", one a line. Some
 * applications only show them there, and appmenu-gtk-module doesn't publish them (LibreOffice) */
typedef struct
{
  GString *text;
  GPtrArray *path;
} Collected;

static void
collect_label_accels (GtkWidget *widget, gpointer data)
{
  Collected *collected = data;
  GtkWidget *child, *submenu;
  const gchar *label;
  guint key = 0, i;
  GdkModifierType mods = 0;
  gchar *accel;

  if (!GTK_IS_MENU_ITEM (widget))
    {
      if (GTK_IS_CONTAINER (widget))
        gtk_container_forall (GTK_CONTAINER (widget), collect_label_accels, data);
      return;
    }
  label = gtk_menu_item_get_label (GTK_MENU_ITEM (widget));
  if (label == NULL || *label == '\0')
    return;
  g_ptr_array_add (collected->path, (gpointer) label);
  child = gtk_bin_get_child (GTK_BIN (widget));
  if (GTK_IS_ACCEL_LABEL (child))
    gtk_accel_label_get_accel (GTK_ACCEL_LABEL (child), &key, &mods);
  if (key != 0)
    {
      for (i = 0; i < collected->path->len; i++)
        g_string_append_printf (collected->text, "%s%s", i ? "\x1f" : "", (gchar *) collected->path->pdata[i]);
      accel = gtk_accelerator_name (key, mods);
      g_string_append_printf (collected->text, "\t%s\n", accel);
      g_free (accel);
    }
  submenu = gtk_menu_item_get_submenu (GTK_MENU_ITEM (widget));
  if (submenu != NULL)
    gtk_container_forall (GTK_CONTAINER (submenu), collect_label_accels, data);
  g_ptr_array_remove_index (collected->path, collected->path->len - 1);
}

static void
collect_menu_bars (GtkWidget *widget, gpointer data)
{
  if (GTK_IS_MENU_BAR (widget))
    gtk_container_forall (GTK_CONTAINER (widget), collect_label_accels, data);
  else if (GTK_IS_CONTAINER (widget))
    gtk_container_forall (GTK_CONTAINER (widget), collect_menu_bars, data);
}

static void
publish_label_accels (GtkWidget *widget)
{
  GdkWindow *window = gtk_widget_get_window (widget);
  Collected collected = { g_string_new (NULL), g_ptr_array_new () };
  gchar *published;

  if (window != NULL)
    {
      gtk_container_forall (GTK_CONTAINER (widget), collect_menu_bars, &collected);
      /* Only when they've changed: Buffet Menu converts the menus again when they do. (Kept with the window's X11
       * window, which is a new one when the window gets its header bar after it was first shown) */
      published = g_object_get_data (G_OBJECT (window), "buffet-label-accels");
      if (g_strcmp0 (published, collected.text->str) != 0)
        {
          gdk_property_change (window, gdk_atom_intern_static_string (LABEL_ACCELS_PROPERTY),
                               gdk_atom_intern_static_string ("UTF8_STRING"), 8, GDK_PROP_MODE_REPLACE,
                               (const guchar *) collected.text->str, collected.text->len);
          g_object_set_data_full (G_OBJECT (window), "buffet-label-accels", g_strdup (collected.text->str), g_free);
        }
    }
  g_string_free (collected.text, TRUE);
  g_ptr_array_free (collected.path, TRUE);
}

/* Menu items added or taken away: the menus' shortcuts are published again, once that's done (LibreOffice fills its
 * submenus when they first open) */
static guint publish_later_source = 0;

static gboolean
publish_label_accels_later (gpointer data)
{
  GList *windows = gtk_window_list_toplevels (), *window;

  publish_later_source = 0;
  for (window = windows; window != NULL; window = window->next)
    if (gtk_widget_get_realized (window->data) && is_main_window (window->data))
      publish_label_accels (window->data);
  g_list_free (windows);
  return G_SOURCE_REMOVE;
}

/* Once the window is on screen and has published its menus: Buffet Menu loads them, for the first click */
static gboolean
load_menus (gpointer window)
{
  publish_accels (GTK_WIDGET (window));
  publish_label_accels (GTK_WIDGET (window));
  ask_service (GTK_WIDGET (window), "load-window");
  g_object_unref (window);
  return G_SOURCE_REMOVE;
}

static void
on_window_mapped (GtkWidget *window, gpointer data)
{
  g_signal_handlers_disconnect_by_func (window, on_window_mapped, data);
  /* A moment for the application to publish its menus */
  g_timeout_add (250, load_menus, g_object_ref (window));
}

/* The application's first main window, a few seconds after it appeared (an application can add its menu bar
 * late): if it has a header bar of its own, or no menu bar, Buffet Menu is told that the application can't have
 * the Buffet menu */
static gboolean
check_first_window (gpointer data)
{
  GtkWindow *window = data;

  if (gtk_widget_get_mapped (GTK_WIDGET (window)) &&
      g_object_get_data (G_OBJECT (window), "buffet-header") == NULL && !has_menu_bar (window))
    ask_service (GTK_WIDGET (window), gtk_window_get_titlebar (window) != NULL ? "own-header-bar" : "no-menu-bar");
  g_object_unref (window);
  return G_SOURCE_REMOVE;
}

static void
on_first_window_mapped (GtkWidget *window, gpointer data)
{
  g_signal_handlers_disconnect_by_func (window, on_first_window_mapped, data);
  g_timeout_add_seconds (3, check_first_window, g_object_ref (window));
}

/* Keeps where the header bar and the Buffet button are in the window, as "x y width height" for each */
static void
on_header_allocated (GtkWidget *header, GdkRectangle *allocation, GtkWidget *button)
{
  GtkWidget *toplevel = gtk_widget_get_toplevel (header);
  GdkWindow *window = gtk_widget_get_window (toplevel);
  gint header_x, header_y, button_x, button_y;
  gchar *text;

  if (window == NULL ||
      !gtk_widget_translate_coordinates (header, toplevel, 0, 0, &header_x, &header_y) ||
      !gtk_widget_translate_coordinates (button, toplevel, 0, 0, &button_x, &button_y))
    return;
  text = g_strdup_printf ("%d %d %d %d %d %d %d %d", header_x, header_y, allocation->width, allocation->height,
                          button_x, button_y, gtk_widget_get_allocated_width (button),
                          gtk_widget_get_allocated_height (button));
  gdk_property_change (window, gdk_atom_intern_static_string (HEADER_PROPERTY),
                       gdk_atom_intern_static_string ("UTF8_STRING"), 8, GDK_PROP_MODE_REPLACE,
                       (const guchar *) text, strlen (text));
  g_free (text);
}

/* The window's title in the header bar. GTK copies the header bar's title to the window: only a different
 * title is copied back, or each would keep updating the other */
static void
on_title_changed (GtkWindow *window, GParamSpec *pspec, GtkHeaderBar *header)
{
  const gchar *title = gtk_window_get_title (window);

  if (g_strcmp0 (title, gtk_header_bar_get_title (header)) != 0)
    gtk_header_bar_set_title (header, title);
}

/* Buffet Menu's icon, which it puts in the user's icons. Some applications use an icon theme of their own that
 * doesn't look there (Inkscape): the icon's folder is added to where their icon theme looks */
static void
find_icon (GtkWidget *widget)
{
  GtkIconTheme *theme = gtk_icon_theme_get_for_screen (gtk_widget_get_screen (widget));
  gchar *folder;

  if (gtk_icon_theme_has_icon (theme, ICON_NAME))
    return;
  folder = g_build_filename (g_get_user_data_dir (), "icons", "hicolor", "scalable", "apps", NULL);
  gtk_icon_theme_append_search_path (theme, folder);
  g_free (folder);
}

/* The Buffet button, at the end of a header bar */
static void
add_buffet_button (GtkWindow *window, GtkWidget *header)
{
  GtkWidget *button;

  find_icon (GTK_WIDGET (window));
  button = gtk_toggle_button_new ();
  gtk_button_set_image (GTK_BUTTON (button), gtk_image_new_from_icon_name (ICON_NAME, GTK_ICON_SIZE_BUTTON));

  gtk_widget_set_tooltip_text (button, "Menu");
  gtk_widget_set_valign (button, GTK_ALIGN_CENTER);
  g_signal_connect (button, "toggled", G_CALLBACK (on_buffet_toggled), NULL);
  /* Buffet Menu says when the window's menu opens and closes, with a property of the window */
  gtk_widget_add_events (GTK_WIDGET (window), GDK_PROPERTY_CHANGE_MASK);
  if (gtk_widget_get_window (GTK_WIDGET (window)) != NULL)
    gdk_window_set_events (gtk_widget_get_window (GTK_WIDGET (window)),
                           gdk_window_get_events (gtk_widget_get_window (GTK_WIDGET (window))) |
                           GDK_PROPERTY_CHANGE_MASK);
  g_signal_connect (window, "property-notify-event", G_CALLBACK (on_property_changed), button);
  gtk_header_bar_pack_end (GTK_HEADER_BAR (header), button);
  gtk_widget_show (button);
  g_signal_connect_after (header, "size-allocate", G_CALLBACK (on_header_allocated), button);
  g_object_set_data (G_OBJECT (window), "buffet-header", header);
}

/* BUFFET_MENU_DEBUG=1: what GTK makes of the window's state, and the icon of the header bar's maximize button */
static void
find_maximize_icon (GtkWidget *widget, gpointer icon)
{
  GtkWidget *image;

  if (GTK_IS_BUTTON (widget) && gtk_style_context_has_class (gtk_widget_get_style_context (widget), "maximize"))
    {
      image = gtk_bin_get_child (GTK_BIN (widget));
      if (GTK_IS_IMAGE (image))
        gtk_image_get_icon_name (GTK_IMAGE (image), (const gchar **) icon, NULL);
    }
  else if (GTK_IS_CONTAINER (widget))
    gtk_container_forall (GTK_CONTAINER (widget), find_maximize_icon, icon);
}

static gboolean
debug_state (GtkWidget *widget, GdkEventWindowState *event, GtkWidget *header)
{
  const gchar *icon = NULL;

  find_maximize_icon (header, &icon);
  g_message ("Buffet Menu: %s: window state %#x (changed %#x), maximized for GTK: %s, maximize button: %s",
             G_OBJECT_TYPE_NAME (widget), event->new_window_state, event->changed_mask,
             gtk_window_is_maximized (GTK_WINDOW (widget)) ? "yes" : "no", icon ? icon : "none");
  return FALSE;
}

static void
add_header_bar (GtkWindow *window)
{
  GtkWidget *header = gtk_header_bar_new ();

  gtk_header_bar_set_show_close_button (GTK_HEADER_BAR (header), TRUE);
  gtk_header_bar_set_title (GTK_HEADER_BAR (header), gtk_window_get_title (window));
  g_signal_connect (window, "notify::title", G_CALLBACK (on_title_changed), header);
  gtk_widget_show_all (header);
  add_buffet_button (window, header);
  gtk_window_set_titlebar (window, header);
  if (g_getenv ("BUFFET_MENU_DEBUG") != NULL)
    g_signal_connect_after (window, "window-state-event", G_CALLBACK (debug_state), header);
}

/* The last header bar in a widget: the one on the right, in a title bar made of several (gedit's) */
static void
find_header_bar (GtkWidget *widget, gpointer found)
{
  if (GTK_IS_HEADER_BAR (widget))
    *(GtkWidget **) found = widget;
  else if (GTK_IS_CONTAINER (widget))
    gtk_container_forall (GTK_CONTAINER (widget), find_header_bar, found);
}

/* A window with a header bar of its own, and a menu bar that's only published (gedit's, for example): its
 * header bar gets the Buffet button */
static GtkWidget *
own_header_bar (GtkWindow *window)
{
  GtkWidget *titlebar = gtk_window_get_titlebar (window), *header = NULL;

  if (titlebar == NULL || g_object_get_data (G_OBJECT (window), "buffet-header") != NULL ||
      !is_main_window (window) || !has_menu_bar (window))
    return NULL;
  find_header_bar (titlebar, &header);
  return header;
}

/* A window's realize, with the header bar first: GTK only takes a header bar before the window is realized */
static void
buffet_realize (GtkWidget *widget)
{
  static gboolean first_window = TRUE;
  GtkWidget *header;

  if (wants_header_bar (GTK_WINDOW (widget)))
    add_header_bar (GTK_WINDOW (widget));
  else if ((header = own_header_bar (GTK_WINDOW (widget))) != NULL)
    add_buffet_button (GTK_WINDOW (widget), header);
  original_realize (widget);
  if (app_id != NULL && gtk_widget_get_window (widget) != NULL)
    gdk_property_change (gtk_widget_get_window (widget), gdk_atom_intern_static_string (APP_PROPERTY),
                         gdk_atom_intern_static_string ("UTF8_STRING"), 8, GDK_PROP_MODE_REPLACE,
                         (const guchar *) app_id, strlen (app_id));
  /* A main window: once it's on screen, its shortcuts are kept, and Buffet Menu loads its menus */
  if (g_object_get_data (G_OBJECT (widget), "buffet-header") != NULL || GTK_IS_APPLICATION_WINDOW (widget))
    g_signal_connect (widget, "map", G_CALLBACK (on_window_mapped), NULL);
  if (first_window && is_main_window (GTK_WINDOW (widget)))
    {
      first_window = FALSE;
      g_signal_connect (widget, "map", G_CALLBACK (on_first_window_mapped), NULL);
    }
}

/* A menu bar added to a window that had none: the window gets its header bar now, once GTK is done adding */
static gboolean
add_header_bar_later (gpointer data)
{
  GtkWindow *window = data;
  GtkWidget *widget = data;
  gboolean visible, maximized;
  gint x, y;

  g_object_set_data (G_OBJECT (window), "buffet-pending", NULL);
  if (wants_header_bar (window))
    {
      /* GTK only takes a header bar on a window that isn't realized: one on screen goes away and comes back */
      visible = gtk_widget_get_visible (widget);
      maximized = gtk_window_is_maximized (window);
      gtk_window_get_position (window, &x, &y);
      if (gtk_widget_get_realized (widget))
        {
          gtk_widget_hide (widget);
          gtk_widget_unrealize (widget);
        }
      add_header_bar (window);
      if (visible)
        {
          gtk_window_move (window, x, y);
          if (maximized)
            gtk_window_maximize (window);
          gtk_widget_show (widget);
        }
    }
  g_object_unref (window);
  return G_SOURCE_REMOVE;
}

static gboolean
on_hierarchy_changed (GSignalInvocationHint *hint, guint count, const GValue *values, gpointer data)
{
  GtkWidget *widget = g_value_get_object (&values[0]);
  GtkWidget *toplevel;

  if (GTK_IS_MENU_ITEM (widget))
    {
      if (publish_later_source == 0)
        publish_later_source = g_timeout_add (100, publish_label_accels_later, NULL);
      return TRUE;
    }
  if (!GTK_IS_MENU_BAR (widget))
    return TRUE;
  toplevel = gtk_widget_get_toplevel (widget);
  if (GTK_IS_WINDOW (toplevel) && g_object_get_data (G_OBJECT (toplevel), "buffet-pending") == NULL &&
      wants_header_bar (GTK_WINDOW (toplevel)))
    {
      g_object_set_data (G_OBJECT (toplevel), "buffet-pending", GINT_TO_POINTER (TRUE));
      g_idle_add (add_header_bar_later, g_object_ref (toplevel));
    }
  return TRUE;
}

/* Uses buffet_realize for the kinds of window whose classes were set up before the module was loaded */
static void
replace_realize (GType type)
{
  GtkWidgetClass *klass = g_type_class_peek (type);
  GType *children;
  guint count, i;

  if (klass != NULL && klass->realize == original_realize)
    klass->realize = buffet_realize;
  children = g_type_children (type, &count);
  for (i = 0; i < count; i++)
    replace_realize (children[i]);
  g_free (children);
}

/* The environment as it was before Buffet Menu's launcher started the application: the programs the application
 * starts (a document opened from Nemo, for example) don't get the Buffet menu, nor its settings. Buffet Menu finds
 * out which application a window belongs to from the environment it was started with, which this doesn't change */
static void
restore_environment (void)
{
  const gchar *modules = g_getenv ("BUFFET_MENU_GTK_MODULES");

  if (g_getenv ("BUFFET_MENU_APP") == NULL)
    return;
  if (modules != NULL && *modules != '\0')
    g_setenv ("GTK_MODULES", modules, TRUE);
  else
    g_unsetenv ("GTK_MODULES");
  g_unsetenv ("BUFFET_MENU_GTK_MODULES");
  g_unsetenv ("BUFFET_MENU_APP");
}

G_MODULE_EXPORT void
gtk_module_init (gint *argc, gchar ***argv)
{
  GtkWidgetClass *klass = g_type_class_ref (GTK_TYPE_WINDOW);

  if (original_realize != NULL)
    return;
  original_realize = klass->realize;
  app_id = g_strdup (g_getenv ("BUFFET_MENU_APP"));
  restore_environment ();
  replace_realize (GTK_TYPE_WINDOW);
  g_bus_watch_name (G_BUS_TYPE_SESSION, SERVICE, G_BUS_NAME_WATCHER_FLAGS_NONE, on_service_appeared,
                    on_service_vanished, NULL, NULL);
  g_signal_add_emission_hook (g_signal_lookup ("hierarchy-changed", GTK_TYPE_WIDGET), 0, on_hierarchy_changed,
                              NULL, NULL);
}
