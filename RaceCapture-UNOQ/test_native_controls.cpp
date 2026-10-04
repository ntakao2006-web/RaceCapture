// Real API integration test under Xvfb; deliberately records a short session.
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

template<class Predicate> bool wait_until(Predicate ready,int seconds=60){
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(seconds);
    while(std::chrono::steady_clock::now()<end){while(gtk_events_pending())gtk_main_iteration();if(ready())return true;g_usleep(20000);}return false;
}
void snapshot(App& app,const char* path){
    GdkWindow* w=gtk_widget_get_window(app.window_);
    GdkPixbuf* p=gdk_pixbuf_get_from_window(w,0,0,gdk_window_get_width(w),gdk_window_get_height(w));
    assert(p);gdk_pixbuf_save(p,path,"png",nullptr,nullptr);g_object_unref(p);
}
int main(int argc,char** argv){
    gtk_init(&argc,&argv);curl_global_init(CURL_GLOBAL_DEFAULT);
    auto before=json::parse(request("/api/status").body);
    if(before["logging"]["active"].get<bool>()||before["hardware"]["sd_logging"].get<int>())return 2;
    App app;app.show();
    assert(wait_until([&]{return !app.podium_cache_.empty();}));
    gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"dashboard");
    if(argc>1&&std::string(argv[1])=="--maps"){
        assert(app.sensor_values_.size()>=20);
        gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"sensors");
        auto until=std::chrono::steady_clock::now()+std::chrono::seconds(1);
        wait_until([&]{return std::chrono::steady_clock::now()>=until;},3);
        snapshot(app,"/home/arduino/recovery-20261004/sensors-page.png");
        auto map_page=gtk_stack_get_child_by_name(GTK_STACK(app.stack_),"gnss");
        assert(!GTK_IS_SCROLLED_WINDOW(map_page));
        gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"gnss");
        app.map_follow_=false;app.map_center_lon_=139.5;app.map_center_lat_=37.15;app.map_zoom_=14;app.map_redraw();
        until=std::chrono::steady_clock::now()+std::chrono::seconds(1);
        wait_until([&]{return std::chrono::steady_clock::now()>=until;},3);
        GtkAllocation allocation;gtk_widget_get_allocation(app.map_area_,&allocation);std::cout<<"map height="<<allocation.height<<std::endl;
        snapshot(app,"/home/arduino/recovery-20261004/maps-page.png");
        assert(allocation.height>=450);
        gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"podium");
        bool initial=app.podium_on_;
        if(initial)snapshot(app,"/home/arduino/recovery-20261004/podium-toggle-on.png");
        gtk_button_clicked(GTK_BUTTON(app.podium_toggle_));
        assert(wait_until([&]{return !app.podium_pending_&&app.podium_on_!=initial;}));
        assert(gtk_style_context_has_class(gtk_widget_get_style_context(app.podium_toggle_),"recording")==!initial);
        until=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        wait_until([&]{return std::chrono::steady_clock::now()>=until;},4);
        if(!initial)snapshot(app,"/home/arduino/recovery-20261004/podium-toggle-on.png");
        gtk_button_clicked(GTK_BUTTON(app.podium_toggle_));
        assert(wait_until([&]{return !app.podium_pending_&&app.podium_on_==initial;}));
        assert(gtk_style_context_has_class(gtk_widget_get_style_context(app.podium_toggle_),"recording")==initial);
        until=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        wait_until([&]{return std::chrono::steady_clock::now()>=until;},4);
        assert(json::parse(request("/api/podium").body)["config"]["enabled"].get<bool>()==initial);
        snapshot(app,"/home/arduino/recovery-20261004/podium-toggle.png");
        std::cout<<"PASS: sensors, map height "<<allocation.height<<", no page scroller, actual Podium toggle round trip\n";
        app.stop();return 0;
    }
    if(argc>1&&std::string(argv[1])=="--logs"){
        app.stop();while(gtk_events_pending())gtk_main_iteration();
        App::Update update{};update.app=&app;update.status=before;update.sdlogs=json::array();
        for(int i=1;i<=100;++i)update.sdlogs.push_back({{"index",i},{"size",1048576},{"active",false}});
        app.render(update);gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"logs");
        auto until=std::chrono::steady_clock::now()+std::chrono::seconds(1);
        wait_until([&]{return std::chrono::steady_clock::now()>=until;},3);
        auto scroll=GTK_SCROLLED_WINDOW(gtk_stack_get_child_by_name(GTK_STACK(app.stack_),"logs"));
        auto adj=gtk_scrolled_window_get_vadjustment(scroll);
        assert(gtk_adjustment_get_upper(adj)>gtk_adjustment_get_page_size(adj)*3);
        snapshot(app,"/home/arduino/recovery-20261004/logs-top.png");
        double bottom=gtk_adjustment_get_upper(adj)-gtk_adjustment_get_page_size(adj);
        gtk_adjustment_set_value(adj,bottom);
        while(gtk_events_pending())gtk_main_iteration();
        assert(std::abs(gtk_adjustment_get_value(adj)-bottom)<1);
        assert(app.logs_box_==nullptr);
        until=std::chrono::steady_clock::now()+std::chrono::seconds(1);
        wait_until([&]{return std::chrono::steady_clock::now()>=until;},3);
        snapshot(app,"/home/arduino/recovery-20261004/logs-bottom.png");
        std::cout<<"PASS: SD-only 100-row page scrolls to bottom; no eMMC list\n";return 0;
    }
    if(argc>1){
        auto ready=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        wait_until([&]{return std::chrono::steady_clock::now()>=ready;},4);
        snapshot(app,"/home/arduino/recovery-20261004/dashboard-stopped.png");
        gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"podium");
        App::podium_stop(nullptr,&app);
        assert(wait_until([&]{auto j=json::parse(request("/api/podium").body);return !j["config"]["enabled"].get<bool>()&&j["status"]["state"]=="off";}));
        App::podium_start(nullptr,&app);
        assert(wait_until([&]{auto j=json::parse(request("/api/podium").body);return j["config"]["enabled"].get<bool>()&&j["config"]["key_configured"].get<bool>();}));
        snapshot(app,"/home/arduino/recovery-20261004/podium-controls.png");
        std::cout<<"PASS: native Podium stop/start controls, saved key retained; stopped dashboard snapshot\n";
        app.stop();return 0;
    }
    gtk_button_clicked(GTK_BUTTON(app.record_toggle_));
    assert(wait_until([&]{return !app.record_pending_&&app.recording_active_&&gtk_style_context_has_class(gtk_widget_get_style_context(app.record_toggle_),"recording");}));
    assert(gtk_style_context_has_class(gtk_widget_get_style_context(app.record_toggle_),"recording"));
    snapshot(app,"/home/arduino/recovery-20261004/dashboard-recording.png");
    auto until=std::chrono::steady_clock::now()+std::chrono::seconds(3);
    wait_until([&]{return std::chrono::steady_clock::now()>=until;},5);
    gtk_button_clicked(GTK_BUTTON(app.record_toggle_));
    assert(wait_until([&]{return !app.record_pending_&&!app.recording_active_&&!gtk_style_context_has_class(gtk_widget_get_style_context(app.record_toggle_),"recording");}));
    std::string message=gtk_label_get_text(GTK_LABEL(app.record_message_));
    assert(message.find("保存完了")!=std::string::npos);
    assert(!gtk_style_context_has_class(gtk_widget_get_style_context(app.record_toggle_),"recording"));
    snapshot(app,"/home/arduino/recovery-20261004/dashboard-stopped.png");
    gtk_stack_set_visible_child_name(GTK_STACK(app.stack_),"podium");
    auto frame=std::chrono::steady_clock::now()+std::chrono::seconds(1);
    wait_until([&]{return std::chrono::steady_clock::now()>=frame;},3);
    snapshot(app,"/home/arduino/recovery-20261004/podium-controls.png");
    std::cout<<"PASS: actual dashboard button start/red, stop/black, SD save acknowledged, Podium page present\n";
    app.stop();
}
