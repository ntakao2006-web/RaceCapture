// Build with GTK/libcurl, then run under xvfb-run; no logger or real touch writes.
#include <gtk/gtk.h>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <atomic>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <tuple>
#include <vector>
#include <cassert>
#define private public
#define main ecocapture_program_main
#include "ecocapture_native.cpp"
#undef main
#undef private

int main(int argc,char** argv) {
    gtk_init(&argc,&argv);
    App app;
    gtk_widget_show_all(app.window_);
    gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"gnss");
    while(gtk_events_pending())gtk_main_iteration();
    app.map_initialized_=true;app.map_center_lon_=139;app.map_center_lat_=35;
    app.map_zoom_=16;
    auto original=App::map_project(139,35,16);
    app.map_center_from_world(original.first,original.second);
    assert(std::abs(app.map_center_lon_-139)<1e-9);
    assert(std::abs(app.map_center_lat_-35)<1e-9);
    guint32 stamp=1000;
    auto touch=[&](GdkEventType type,unsigned id,double x,double y){
        GdkEvent* e=gdk_event_new(type);
        e->touch.window=GDK_WINDOW(g_object_ref(gtk_widget_get_window(app.map_area_)));
        e->touch.time=stamp+=20;e->touch.x=x;e->touch.y=y;
        e->touch.emulating_pointer=(id!=2);
        e->touch.sequence=reinterpret_cast<GdkEventSequence*>(static_cast<uintptr_t>(id));
        GdkDevice* pointer=gdk_seat_get_pointer(gdk_display_get_default_seat(gdk_display_get_default()));
        gdk_event_set_device(e,pointer);gdk_event_set_source_device(e,pointer);
        gtk_event_controller_handle_event(GTK_EVENT_CONTROLLER(app.map_drag_),e);
        gtk_event_controller_handle_event(GTK_EVENT_CONTROLLER(app.map_pinch_),e);
        gdk_event_free(e);
    };
    touch(GDK_TOUCH_BEGIN,1,300,120);touch(GDK_TOUCH_BEGIN,2,400,120);
    touch(GDK_TOUCH_UPDATE,1,240,120);touch(GDK_TOUCH_UPDATE,2,460,120);
    assert(app.map_zoom_==17);assert(!app.map_follow_);
    assert(std::abs(app.map_center_lon_-139)<0.1);
    touch(GDK_TOUCH_END,1,240,120);touch(GDK_TOUCH_END,2,460,120);
    const double before=app.map_center_lon_;
    touch(GDK_TOUCH_BEGIN,3,300,120);touch(GDK_TOUCH_UPDATE,3,400,120);touch(GDK_TOUCH_END,3,400,120);
    std::cerr<<"pan before="<<std::setprecision(12)<<before<<" after="<<app.map_center_lon_
             <<" drag_origin="<<app.drag_x_<<" pinch_recognized="<<gtk_gesture_is_recognized(app.map_pinch_)<<"\n";
    assert(app.map_center_lon_<before);
    std::cout<<"PASS: two-contact pinch zoom, single-contact pan, manual follow state\n";
    gtk_widget_destroy(app.window_);
}
