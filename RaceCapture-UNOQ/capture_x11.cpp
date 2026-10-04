#include <gtk/gtk.h>

int main(int argc, char** argv) {
    gtk_init(&argc, &argv);
    GdkWindow* root = gdk_get_default_root_window();
    if (!root) return 1;
    const int width = gdk_window_get_width(root);
    const int height = gdk_window_get_height(root);
    GdkPixbuf* image = gdk_pixbuf_get_from_window(root, 0, 0, width, height);
    if (!image) return 2;
    GError* error = nullptr;
    const char* path = argc > 1 ? argv[1] : "/tmp/ecocapture-screen.png";
    const gboolean ok = gdk_pixbuf_save(image, path, "png", &error, nullptr);
    if (error) g_error_free(error);
    g_object_unref(image);
    return ok ? 0 : 3;
}
