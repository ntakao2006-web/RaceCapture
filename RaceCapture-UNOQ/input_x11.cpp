#include <X11/Xlib.h>
#include <X11/extensions/XTest.h>
#include <cstdlib>
#include <unistd.h>

int main(int argc, char** argv) {
    if (argc < 3) return 1;
    Display* display = XOpenDisplay(nullptr);
    if (!display) return 2;
    const int x = std::atoi(argv[1]), y = std::atoi(argv[2]);
    const int button = argc > 3 ? std::atoi(argv[3]) : 1;
    const int count = argc > 4 ? std::atoi(argv[4]) : 1;
    XTestFakeMotionEvent(display, -1, x, y, CurrentTime);
    for (int i=0; i<count; ++i) {
        XTestFakeButtonEvent(display, button, True, CurrentTime);
        XTestFakeButtonEvent(display, button, False, CurrentTime);
    }
    XFlush(display);
    usleep(250000);
    XCloseDisplay(display);
    return 0;
}
