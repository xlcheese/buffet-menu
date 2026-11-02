/* The Buffet menu's header bar, for applications that have a menu bar and no header bar of their own.
 *
 * A GTK 3 module, loaded by Buffet Menu's launcher into the applications given the Buffet menu. Just before
 * an application's main window is first shown, it gives the window a header bar: the window's title, its
 * buttons, and the Buffet button, which asks Buffet Menu to show the window's menus. The window keeps where
 * the header bar and the button are in the _BUFFET_MENU_HEADER property, for Buffet Menu to put the menu
 * under them. Some applications, such as Inkscape and GIMP, add their menu bar to the window after that:
 * the window gets its header bar then.
 *
 * Build: gcc -shared -fPIC -O2 -o libbuffet-headerbar.so buffet-headerbar.c $(pkg-config --cflags --libs gtk+-3.0)
 */

#include <gtk/gtk.h>
#include <gdk/gdkx.h>

#define SERVICE "io.github.xlcheese.BuffetMenu"
#define SERVICE_PATH "/io/github/xlcheese/BuffetMenu"
#define HEADER_PROPERTY "_BUFFET_MENU_HEADER"

static void (*original_realize) (GtkWidget *widget);

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

/* An application's main window: a normal window with a menu bar, not a dialog, and without a header bar */
static gboolean
wants_header_bar (GtkWindow *window)
{
  gboolean found = FALSE;

  if (gtk_window_get_titlebar (window) != NULL || GTK_IS_DIALOG (window) ||
      gtk_window_get_window_type (window) != GTK_WINDOW_TOPLEVEL ||
      gtk_window_get_type_hint (window) != GDK_WINDOW_TYPE_HINT_NORMAL ||
      gtk_window_get_transient_for (window) != NULL || !gtk_window_get_decorated (window))
    return FALSE;
  gtk_container_forall (GTK_CONTAINER (window), find_menu_bar, &found);
  /* Or the application's menu bar, that GTK shows in its windows, or publishes instead with appmenu-gtk-module
   * (Inkscape's, for example) */
  if (!found && GTK_IS_APPLICATION_WINDOW (window) && gtk_window_get_application (window) != NULL)
    found = gtk_application_get_menubar (gtk_window_get_application (window)) != NULL &&
            gtk_application_window_get_show_menubar (GTK_APPLICATION_WINDOW (window));
  return found;
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

static void
on_buffet_clicked (GtkButton *button, gpointer data)
{
  ask_service (GTK_WIDGET (button), "show-window");
}

/* Once the window is on screen and has published its menus: Buffet Menu loads them, for the first click */
static gboolean
load_menus (gpointer window)
{
  ask_service (GTK_WIDGET (window), "load-window");
  g_object_unref (window);
  return G_SOURCE_REMOVE;
}

static void
on_window_mapped (GtkWidget *window, gpointer data)
{
  g_signal_handlers_disconnect_by_func (window, on_window_mapped, data);
  g_timeout_add_seconds (1, load_menus, g_object_ref (window));
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

static void
add_header_bar (GtkWindow *window)
{
  GtkWidget *header = gtk_header_bar_new ();
  GtkWidget *button = gtk_button_new_from_icon_name ("buffet-menu-symbolic", GTK_ICON_SIZE_BUTTON);

  gtk_header_bar_set_show_close_button (GTK_HEADER_BAR (header), TRUE);
  gtk_header_bar_set_title (GTK_HEADER_BAR (header), gtk_window_get_title (window));
  g_signal_connect (window, "notify::title", G_CALLBACK (on_title_changed), header);
  gtk_widget_set_tooltip_text (button, "Menu");
  g_signal_connect (button, "clicked", G_CALLBACK (on_buffet_clicked), NULL);
  gtk_header_bar_pack_end (GTK_HEADER_BAR (header), button);
  g_signal_connect_after (header, "size-allocate", G_CALLBACK (on_header_allocated), button);
  gtk_widget_show_all (header);
  gtk_window_set_titlebar (window, header);
  g_signal_connect (window, "map", G_CALLBACK (on_window_mapped), NULL);
}

/* A window's realize, with the header bar first: GTK only takes a header bar before the window is realized */
static void
buffet_realize (GtkWidget *widget)
{
  if (wants_header_bar (GTK_WINDOW (widget)))
    add_header_bar (GTK_WINDOW (widget));
  original_realize (widget);
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

G_MODULE_EXPORT void
gtk_module_init (gint *argc, gchar ***argv)
{
  GtkWidgetClass *klass = g_type_class_ref (GTK_TYPE_WINDOW);

  if (original_realize != NULL)
    return;
  original_realize = klass->realize;
  replace_realize (GTK_TYPE_WINDOW);
  g_signal_add_emission_hook (g_signal_lookup ("hierarchy-changed", GTK_TYPE_WIDGET), 0, on_hierarchy_changed,
                              NULL, NULL);
}
