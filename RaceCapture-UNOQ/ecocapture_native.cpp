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

using json = nlohmann::json;

namespace {
constexpr int kBarHeight = 64;
const char* kApi = "http://127.0.0.1:8080";

struct HttpResult { long code = 0; std::string body; std::string error; };

size_t append_body(char* data, size_t size, size_t count, void* output) {
    static_cast<std::string*>(output)->append(data, size * count);
    return size * count;
}

HttpResult request(const std::string& path, const char* post = nullptr) {
    HttpResult out;
    CURL* curl = curl_easy_init();
    if (!curl) { out.error = "通信の初期化に失敗"; return out; }
    char err[CURL_ERROR_SIZE] = {};
    std::string url = std::string(kApi) + path;
    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, append_body);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &out.body);
    long timeout = (path.rfind("/api/device/",0)==0 || path=="/api/podium/check") ? 50000L : 10000L;
    if(path.rfind("/api/sd/logs/",0)==0) timeout=300000L;
    if(path.rfind("/api/log/",0)==0) timeout=60000L;
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, timeout);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 400L);
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, err);
    struct curl_slist* headers = nullptr;
    if (post) {
        headers = curl_slist_append(headers, "Content-Type: application/json");
        headers = curl_slist_append(headers, "X-EcoCapture: 1");
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, post);
    }
    CURLcode result = curl_easy_perform(curl);
    if (result != CURLE_OK) out.error = *err ? err : curl_easy_strerror(result);
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &out.code);
    if (headers) curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return out;
}

HttpResult request_reuse(CURL* curl, const std::string& path) {
    HttpResult out; if(!curl){out.error="通信の初期化に失敗";return out;} char err[CURL_ERROR_SIZE]={}; std::string url=std::string(kApi)+path;
    curl_easy_reset(curl); curl_easy_setopt(curl,CURLOPT_URL,url.c_str());curl_easy_setopt(curl,CURLOPT_WRITEFUNCTION,append_body);curl_easy_setopt(curl,CURLOPT_WRITEDATA,&out.body);curl_easy_setopt(curl,CURLOPT_TIMEOUT_MS,1500L);curl_easy_setopt(curl,CURLOPT_CONNECTTIMEOUT_MS,300L);curl_easy_setopt(curl,CURLOPT_NOSIGNAL,1L);curl_easy_setopt(curl,CURLOPT_ERRORBUFFER,err);
    CURLcode result=curl_easy_perform(curl);if(result!=CURLE_OK)out.error=*err?err:curl_easy_strerror(result);curl_easy_getinfo(curl,CURLINFO_RESPONSE_CODE,&out.code);return out;
}

HttpResult request_url(const std::string& url) {
    HttpResult out; CURL* curl=curl_easy_init(); if(!curl){out.error="通信の初期化に失敗";return out;}curl_easy_setopt(curl,CURLOPT_URL,url.c_str());curl_easy_setopt(curl,CURLOPT_WRITEFUNCTION,append_body);curl_easy_setopt(curl,CURLOPT_WRITEDATA,&out.body);curl_easy_setopt(curl,CURLOPT_TIMEOUT_MS,5000L);curl_easy_setopt(curl,CURLOPT_CONNECTTIMEOUT_MS,1000L);curl_easy_setopt(curl,CURLOPT_NOSIGNAL,1L);CURLcode code=curl_easy_perform(curl);if(code!=CURLE_OK)out.error=curl_easy_strerror(code);curl_easy_getinfo(curl,CURLINFO_RESPONSE_CODE,&out.code);curl_easy_cleanup(curl);return out;
}

std::string number(const json& values, const char* key, int precision, const char* unit) {
    auto it = values.find(key);
    if (it == values.end() || it->is_null() || !it->is_number()) return "--";
    std::ostringstream s;
    s << std::fixed << std::setprecision(precision) << it->get<double>();
    if (*unit) s << " " << unit;
    return s.str();
}

std::string integer(const json& value, const char* unit = "") {
    if (value.is_null() || !value.is_number()) return "--";
    std::ostringstream s;
    s << std::llround(value.get<double>());
    if (*unit) s << " " << unit;
    return s.str();
}

std::string human_bytes(long long value) {
    std::ostringstream s;
    if (value >= 1024LL * 1024 * 1024) s << std::fixed << std::setprecision(1) << value / (1024.0 * 1024 * 1024) << " GB";
    else if (value >= 1024LL * 1024) s << std::fixed << std::setprecision(1) << value / (1024.0 * 1024) << " MB";
    else if (value >= 1024) s << std::fixed << std::setprecision(1) << value / 1024.0 << " KB";
    else s << value << " B";
    return s.str();
}

std::string text_value(const json& object, const char* key, const std::string& fallback = "--") {
    auto it = object.find(key);
    return it != object.end() && it->is_string() ? it->get<std::string>() : fallback;
}

GtkWidget* label(const char* text, const char* css = nullptr) {
    GtkWidget* w = gtk_label_new(text);
    gtk_label_set_xalign(GTK_LABEL(w), 0.0f);
    if (css) gtk_style_context_add_class(gtk_widget_get_style_context(w), css);
    return w;
}

GtkWidget* wrapped_label(const char* text, const char* css = nullptr) {
    GtkWidget* w=label(text,css);gtk_label_set_line_wrap(GTK_LABEL(w),TRUE);gtk_label_set_line_wrap_mode(GTK_LABEL(w),PANGO_WRAP_WORD_CHAR);gtk_label_set_max_width_chars(GTK_LABEL(w),100);gtk_widget_set_hexpand(w,TRUE);return w;
}

class App {
public:
    App() {
        window_ = gtk_window_new(GTK_WINDOW_TOPLEVEL);
        gtk_window_set_title(GTK_WINDOW(window_), "EcoCapture Native");
        gtk_window_set_wmclass(GTK_WINDOW(window_), "ecocapture-native", "ecocapture-native");
        gtk_window_set_decorated(GTK_WINDOW(window_), FALSE);
        gtk_window_move(GTK_WINDOW(window_), 0, kBarHeight);
        gtk_window_set_default_size(GTK_WINDOW(window_), 1280, 736);
        gtk_window_maximize(GTK_WINDOW(window_));
        g_signal_connect(window_, "destroy", G_CALLBACK(on_destroy), this);
        build_css();

        GtkWidget* root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
        GtkWidget* header = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
        gtk_style_context_add_class(gtk_widget_get_style_context(header), "header");
        title_ = label("EcoCapture   WEB / 0.2", "title");
        rec_ = label("EcoLogger V2    接続待ち", "connection");
        gtk_box_pack_start(GTK_BOX(header), title_, TRUE, TRUE, 18);
        gtk_box_pack_end(GTK_BOX(header), rec_, FALSE, FALSE, 18);
        gtk_box_pack_start(GTK_BOX(root), header, FALSE, FALSE, 0);
        GtkWidget* shell=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,0);
        sidebar_=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
        gtk_widget_set_size_request(sidebar_,228,-1);
        gtk_style_context_add_class(gtk_widget_get_style_context(sidebar_),"sidebar");
        GtkWidget* workspace=label("WORKSPACE","eyebrow");
        gtk_box_pack_start(GTK_BOX(sidebar_),workspace,FALSE,FALSE,12);
        stack_=gtk_stack_new();
        gtk_stack_set_transition_type(GTK_STACK(stack_),GTK_STACK_TRANSITION_TYPE_CROSSFADE);
        add_dashboard();
        add_sensors();
        add_gnss();
        add_imu();
        add_logs();
        add_settings();
        GtkWidget* source=label("DATA SOURCE\n\nSTM32 → Linux → UNO Q\n\n実機センサ / タッチ操作","side-info");
        gtk_box_pack_end(GTK_BOX(sidebar_),source,FALSE,FALSE,18);
        gtk_box_pack_start(GTK_BOX(shell),sidebar_,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(shell),stack_,TRUE,TRUE,0);
        gtk_box_pack_start(GTK_BOX(root),shell,TRUE,TRUE,0);
        gtk_container_add(GTK_CONTAINER(window_), root);
    }

    ~App() { stop(); for(auto& tile:map_tiles_)g_object_unref(tile.second); }
    void show() {
        gtk_widget_show_all(window_);
        worker_ = std::thread([this] { worker_loop(); });
        metadata_worker_ = std::thread([this] { metadata_loop(); });
        // Offline maps only: do not download tiles over the vehicle LTE link.
    }

private:
    GtkWidget *window_ = nullptr, *stack_ = nullptr, *sidebar_ = nullptr, *title_ = nullptr, *rec_ = nullptr;
    GtkWidget *diag_ = nullptr,*can_live_=nullptr,*calibration_info_=nullptr, *logs_ = nullptr, *logs_box_=nullptr, *sd_logs_ = nullptr, *sd_logs_box_=nullptr, *solve_summary_=nullptr,*solve_area_=nullptr, *storage_free_ = nullptr, *action_ = nullptr, *settings_action_ = nullptr, *settings_ = nullptr, *dash_rec_ = nullptr,*dash_seq_=nullptr,*throttle_bar_=nullptr;
    std::string logs_snapshot_,sd_logs_snapshot_;
    GtkWidget *config_name_ = nullptr, *config_profile_ = nullptr, *config_bitrate_ = nullptr, *config_auto_ = nullptr, *g_area_ = nullptr, *trend_area_=nullptr, *map_area_=nullptr,*map_follow_button_=nullptr;
    GtkWidget *signal_list_=nullptr;
    GtkWidget *ncec_input_ = nullptr, *ncec_result_ = nullptr,*ncec_download_=nullptr, *wifi_networks_=nullptr, *wifi_ssid_ = nullptr, *wifi_password_ = nullptr, *wifi_security_ = nullptr, *device_status_ = nullptr,*sharing_status_=nullptr,*sharing_copy_=nullptr;
    GtkWidget *podium_apn_=nullptr,*podium_user_=nullptr,*podium_password_=nullptr,*podium_key_=nullptr,*podium_host_=nullptr,*podium_port_=nullptr,*podium_hardware_=nullptr,*podium_enabled_=nullptr,*podium_channels_box_=nullptr,*system_info_=nullptr;
    json podium_cache_;
    GtkWidget *podium_toggle_=nullptr,*sensor_grid_=nullptr;
    bool podium_pending_=false,podium_on_=false;
    std::map<std::string,GtkWidget*> sensor_values_;
    GtkWidget *record_toggle_=nullptr,*record_message_=nullptr,*podium_message_=nullptr,*podium_live_=nullptr;
    bool recording_active_=false,record_pending_=false;
    json config_cache_;
    std::string signals_snapshot_;
    std::string ncec_csv_;
    std::string sharing_url_;
    double g_lat_ = 0.0, g_long_ = 0.0;
    std::vector<std::tuple<double,double,double>> track_;
    std::vector<std::pair<double,double>> trend_;
    std::vector<std::pair<double,double>> solve_track_;
    double map_center_lon_=0,map_center_lat_=0,current_lon_=0,current_lat_=0;int map_zoom_=16;bool map_follow_=true,map_initialized_=false;
    GtkGesture *map_pinch_=nullptr,*map_drag_=nullptr;
    int pinch_zoom_=16;
    double pinch_anchor_lon_=0,pinch_anchor_lat_=0,drag_x_=0,drag_y_=0;
    std::atomic<double> tile_lon_{0},tile_lat_{0};
    std::atomic<int> tile_zoom_{16};
    std::atomic<bool> tile_ready_{false};
    std::mutex metadata_mutex_;
    json pending_metadata_=json::object();
    std::map<std::string,GdkPixbuf*> map_tiles_;
    std::map<std::string, std::vector<GtkWidget*>> values_;
    std::map<std::string,std::string> wifi_security_by_ssid_;
    std::map<std::string,GtkWidget*> podium_channel_boxes_;
    std::vector<GtkWidget*> nav_;
    std::atomic<bool> running_{true};
    std::thread worker_,metadata_worker_,map_worker_;

    static void on_destroy(GtkWidget*, gpointer self) {
        static_cast<App*>(self)->stop();
        gtk_main_quit();
    }

    void stop() {
        if (!running_.exchange(false)) return;
        if (worker_.joinable()) worker_.join();
        if (metadata_worker_.joinable()) metadata_worker_.join();
        if (map_worker_.joinable()) map_worker_.join();
    }

    void build_css() {
        GtkCssProvider* css = gtk_css_provider_new();
        const char* data =
            "window { background:#f4f4f4; color:#181818; font-family:'Noto Sans CJK JP'; }"
            ".header { background:#ffffff; min-height:66px; border-bottom:1px solid #d9d9d9; }"
            ".title { font-size:24px; font-weight:bold; color:#181818; } .connection { font-size:14px; color:#5f5f5f; }"
            ".sidebar { background:#ffffff; border-right:1px solid #d9d9d9; padding:18px; }"
            ".eyebrow { font-size:12px; font-weight:bold; letter-spacing:2px; color:#686868; }"
            ".side-info { font-size:13px; color:#555555; }"
            "button.nav { background:#ffffff; color:#181818; border:0; border-radius:2px; padding:13px 10px; font-size:14px; font-weight:bold; }"
            "button.nav.active { background:#181818; color:#ffffff; }"
            ".page { padding:18px 28px; } .page-title { font-size:30px; font-weight:bold; color:#181818; }"
            ".card { background:#ffffff; border:1px solid #d9d9d9; border-radius:0; margin:6px; padding:12px; }"
            ".metric-name { font-size:14px; color:#686868; } .metric-value { font-size:29px; font-weight:500; color:#181818; }"
            ".speed-card { background:#171717; padding:18px 24px; margin:6px; } .speed-card label { color:#ffffff; }"
            ".speed-name { font-size:12px; letter-spacing:1px; } .speed-value { font-size:70px; font-weight:600; }"
            ".rpm-card { background:#ffffff; border:1px solid #d9d9d9; padding:18px 24px; margin:6px; }"
            ".rpm-value { font-size:60px; font-weight:500; color:#181818; }"
            ".map { background:#232a2c; color:#ffffff; border:1px solid #d9d9d9; padding:0; } .map label { color:#ffffff; font-size:18px; } .page.map-page { padding:8px 12px; }"
            ".section { font-size:16px; font-weight:bold; color:#181818; margin:8px; }"
            ".body { font-size:15px; color:#333333; padding:12px; }"
            ".mono { font-family:monospace; font-size:13px; }"
            "button { font-size:16px; font-weight:bold; color:#181818; background:#ffffff; border:1px solid #aaaaaa; border-radius:3px; padding:10px 18px; margin:5px; }"
            "button.compact { font-size:13px; padding:6px 9px; margin:2px; }"
            "button.primary { background:#171717; color:#ffffff; } button.stop { background:#ffffff; color:#181818; }"
            ".action { font-size:14px; color:#b82428; padding:6px; }";
        gtk_css_provider_load_from_data(css, data, -1, nullptr);
        gtk_style_context_add_provider_for_screen(gdk_screen_get_default(), GTK_STYLE_PROVIDER(css), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
        g_object_unref(css);
    }

    void add_page(GtkWidget* page, const char* name, const char* button_text,bool scrolling=true) {
        gtk_style_context_add_class(gtk_widget_get_style_context(page),"page");
        GtkWidget* scroll=gtk_scrolled_window_new(nullptr,nullptr);
        gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll),GTK_POLICY_NEVER,GTK_POLICY_AUTOMATIC);
        gtk_scrolled_window_set_overlay_scrolling(GTK_SCROLLED_WINDOW(scroll),FALSE);
        gtk_scrolled_window_set_kinetic_scrolling(GTK_SCROLLED_WINDOW(scroll),TRUE);
        if(scrolling){gtk_container_add(GTK_CONTAINER(scroll),page);gtk_stack_add_named(GTK_STACK(stack_),scroll,name);}
        else{gtk_widget_destroy(scroll);gtk_stack_add_named(GTK_STACK(stack_),page,name);}
        GtkWidget* b=gtk_button_new_with_label(button_text);
        gtk_style_context_add_class(gtk_widget_get_style_context(b),"nav");
        g_object_set_data_full(G_OBJECT(b),"page",g_strdup(name),g_free);
        g_signal_connect(b,"clicked",G_CALLBACK(+[](GtkButton* button,gpointer data){
            App* self=static_cast<App*>(data); const char* page=static_cast<const char*>(g_object_get_data(G_OBJECT(button),"page"));
            gtk_stack_set_visible_child_name(GTK_STACK(self->stack_),page);
            for(GtkWidget* n:self->nav_) gtk_style_context_remove_class(gtk_widget_get_style_context(n),"active");
            gtk_style_context_add_class(gtk_widget_get_style_context(GTK_WIDGET(button)),"active");
        }),this);
        nav_.push_back(b); gtk_box_pack_start(GTK_BOX(sidebar_),b,FALSE,FALSE,0);
        if(nav_.size()==1) gtk_style_context_add_class(gtk_widget_get_style_context(b),"active");
    }

    GtkWidget* metric(const std::string& key, const char* name) {
        GtkWidget* box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
        gtk_style_context_add_class(gtk_widget_get_style_context(box), "card");
        GtkWidget* n = label(name, "metric-name");
        GtkWidget* v = label("--", "metric-value");
        gtk_label_set_xalign(GTK_LABEL(v), 0.5f);
        gtk_label_set_xalign(GTK_LABEL(n), 0.5f);
        gtk_box_pack_start(GTK_BOX(box), n, FALSE, FALSE, 0);
        gtk_box_pack_start(GTK_BOX(box), v, TRUE, TRUE, 0);
        values_[key].push_back(v);
        return box;
    }

    GtkWidget* reading(const std::string& key, const char* name, const char* unit) {
        GtkWidget* row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
        gtk_box_pack_start(GTK_BOX(row),label(name,"metric-name"),TRUE,TRUE,0);
        GtkWidget* value=label("--","body"); values_[key].push_back(value);
        gtk_box_pack_end(GTK_BOX(row),label(unit,"metric-name"),FALSE,FALSE,0);
        gtk_box_pack_end(GTK_BOX(row),value,FALSE,FALSE,0);
        return row;
    }

    void add_dashboard() {
        GtkWidget* page=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
        GtkWidget* heading=label("LIVE TELEMETRY\nDashboard","page-title");
        gtk_box_pack_start(GTK_BOX(page),heading,FALSE,FALSE,4);
        GtkWidget* hero=gtk_grid_new(); gtk_grid_set_column_homogeneous(GTK_GRID(hero),TRUE);
        gtk_widget_set_size_request(hero,-1,218);
        GtkWidget* speed=gtk_box_new(GTK_ORIENTATION_VERTICAL,4); gtk_style_context_add_class(gtk_widget_get_style_context(speed),"speed-card");
        GtkWidget* sn=label("GNSS SPEED                                      km/h","speed-name");
        GtkWidget* sv=label("--","speed-value"); values_["GPSSpeed"].push_back(sv);
        GtkWidget* sb=label("SPEED                                      SEQ --","speed-name");dash_seq_=sb;
        gtk_box_pack_start(GTK_BOX(speed),sn,FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(speed),sv,TRUE,TRUE,0); gtk_box_pack_start(GTK_BOX(speed),sb,FALSE,FALSE,0);
        GtkWidget* rpm=gtk_box_new(GTK_ORIENTATION_VERTICAL,4); gtk_style_context_add_class(gtk_widget_get_style_context(rpm),"rpm-card");
        gtk_box_pack_start(GTK_BOX(rpm),label("ENGINE SPEED                                      rpm","metric-name"),FALSE,FALSE,0);
        GtkWidget* rv=label("--","rpm-value"); values_["RPM"].push_back(rv); gtk_box_pack_start(GTK_BOX(rpm),rv,TRUE,TRUE,0);
        GtkWidget* bar=gtk_progress_bar_new();throttle_bar_=bar; gtk_progress_bar_set_fraction(GTK_PROGRESS_BAR(bar),0); gtk_box_pack_start(GTK_BOX(rpm),bar,FALSE,FALSE,4);
        GtkWidget* throttle=label("スロットル -- %","metric-name"); values_["dash.Throttle"].push_back(throttle); gtk_box_pack_start(GTK_BOX(rpm),throttle,FALSE,FALSE,0);
        gtk_grid_attach(GTK_GRID(hero),speed,0,0,3,1); gtk_grid_attach(GTK_GRID(hero),rpm,3,0,2,1);
        gtk_box_pack_start(GTK_BOX(page),hero,FALSE,FALSE,0);
        GtkWidget* metrics=gtk_grid_new(); gtk_grid_set_column_homogeneous(GTK_GRID(metrics),TRUE);
        gtk_widget_set_size_request(metrics,-1,96);
        const std::pair<const char*,const char*> cards[]={{"LongAccel","前後加速度"},{"LatAccel","左右加速度"},{"BatteryVolt","バッテリー"},{"Distance","累積距離"}};
        for(int i=0;i<4;i++) gtk_grid_attach(GTK_GRID(metrics),metric(cards[i].first,cards[i].second),i,0,1,1);
        gtk_box_pack_start(GTK_BOX(page),metrics,FALSE,FALSE,0);
        GtkWidget* trend=gtk_box_new(GTK_ORIENTATION_VERTICAL,2); gtk_style_context_add_class(gtk_widget_get_style_context(trend),"card");
        gtk_widget_set_size_request(trend,-1,200);
        GtkWidget* trend_title=label("GPS速度の推移  ·  直近60秒 / km/h","section");
        trend_area_=gtk_drawing_area_new(); g_signal_connect(trend_area_,"draw",G_CALLBACK(draw_trend),this);
        gtk_box_pack_start(GTK_BOX(trend),trend_title,FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(trend),trend_area_,TRUE,TRUE,0);
        gtk_box_pack_start(GTK_BOX(page),trend,FALSE,FALSE,0);
        GtkWidget* record=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);
        GtkWidget* status=label("○ STANDBY     00:00:00     0 samples","body"); dash_rec_=status;
        record_toggle_=gtk_button_new_with_label("● 記録開始");
        gtk_widget_set_size_request(record_toggle_,190,64);
        GtkCssProvider* record_css=gtk_css_provider_new();
        gtk_css_provider_load_from_data(record_css,"button {background-image:none;background-color:#171717;color:white;font-weight:bold;} button.recording {background-color:#c92828;} button:disabled {opacity:0.65;}",-1,nullptr);
        gtk_style_context_add_provider(gtk_widget_get_style_context(record_toggle_),GTK_STYLE_PROVIDER(record_css),GTK_STYLE_PROVIDER_PRIORITY_APPLICATION+1);g_object_unref(record_css);
        g_signal_connect(record_toggle_,"clicked",G_CALLBACK(record_toggle),this);
        gtk_box_pack_start(GTK_BOX(record),status,TRUE,TRUE,0);gtk_box_pack_end(GTK_BOX(record),record_toggle_,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(page),record,FALSE,FALSE,0);
        record_message_=wrapped_label("停止中 · ボタンを押すとSDと本体への記録を開始します","body");gtk_box_pack_start(GTK_BOX(page),record_message_,FALSE,FALSE,0);
        gtk_box_reorder_child(GTK_BOX(page),record,1);gtk_box_reorder_child(GTK_BOX(page),record_message_,2);
        add_page(page,"dashboard","01    Dashboard");
    }

    void add_sensors(){
        GtkWidget* page=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
        gtk_box_pack_start(GTK_BOX(page),label("LIVE VALUES\nセンサ値一覧","page-title"),FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(page),label("GNSS・IMU・車両CANの現在値 · 未受信の値は —","metric-name"),FALSE,FALSE,0);
        sensor_grid_=gtk_grid_new();gtk_grid_set_column_homogeneous(GTK_GRID(sensor_grid_),TRUE);
        gtk_grid_set_column_spacing(GTK_GRID(sensor_grid_),12);gtk_grid_set_row_spacing(GTK_GRID(sensor_grid_),6);
        gtk_box_pack_start(GTK_BOX(page),sensor_grid_,FALSE,FALSE,0);
        add_page(page,"sensors","02    センサ値一覧");
    }

    void add_gnss() {
        GtkWidget* page=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
        gtk_style_context_add_class(gtk_widget_get_style_context(page),"map-page");
        gtk_box_pack_start(GTK_BOX(page),label("GNSS / Maps","section"),FALSE,FALSE,0);
        GtkWidget* toolbar=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4);
        auto map_button=[&](const char* title,const char* action){GtkWidget* b=gtk_button_new_with_label(title);g_object_set_data_full(G_OBJECT(b),"action",g_strdup(action),g_free);g_signal_connect(b,"clicked",G_CALLBACK(map_action),this);gtk_box_pack_start(GTK_BOX(toolbar),b,FALSE,FALSE,0);return b;};
        map_button("＋","zoom-in");map_button("−","zoom-out");map_button("全体表示","fit");map_button("現在地","current");map_follow_button_=map_button("追従 ON","follow");map_button("軌跡をクリア","clear");
        gtk_box_pack_start(GTK_BOX(page),toolbar,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(page),label("オフライン航空写真 · 関東広域版 · 追加通信なし","metric-name"),FALSE,FALSE,0);
        GtkWidget* map=gtk_box_new(GTK_ORIENTATION_VERTICAL,4); gtk_style_context_add_class(gtk_widget_get_style_context(map),"map");
        gtk_widget_set_vexpand(map,TRUE);map_area_=gtk_drawing_area_new();gtk_widget_set_size_request(map_area_, -1,250);g_signal_connect(map_area_,"draw",G_CALLBACK(draw_map),this);gtk_box_pack_start(GTK_BOX(map),map_area_,TRUE,TRUE,0);
        gtk_widget_add_events(map_area_,GDK_TOUCH_MASK|GDK_BUTTON_PRESS_MASK|GDK_BUTTON_RELEASE_MASK|GDK_POINTER_MOTION_MASK);
        map_drag_=gtk_gesture_drag_new(map_area_);
        map_pinch_=gtk_gesture_zoom_new(map_area_);
        gtk_gesture_group(map_drag_,map_pinch_);
        gtk_event_controller_set_propagation_phase(GTK_EVENT_CONTROLLER(map_drag_),GTK_PHASE_CAPTURE);
        gtk_event_controller_set_propagation_phase(GTK_EVENT_CONTROLLER(map_pinch_),GTK_PHASE_CAPTURE);
        g_signal_connect(map_drag_,"drag-begin",G_CALLBACK(map_drag_begin),this);
        g_signal_connect(map_drag_,"drag-update",G_CALLBACK(map_drag_update),this);
        g_signal_connect(map_pinch_,"begin",G_CALLBACK(map_pinch_begin),this);
        g_signal_connect(map_pinch_,"scale-changed",G_CALLBACK(map_pinch_scale),this);
        gtk_box_pack_start(GTK_BOX(page),map,TRUE,TRUE,0);
        GtkWidget* credit=gtk_label_new(nullptr);gtk_label_set_markup(GTK_LABEL(credit),"出典：<a href=\"https://maps.gsi.go.jp/development/ichiran.html\">国土地理院・地理院タイル</a>（全国最新写真）");gtk_box_pack_start(GTK_BOX(page),credit,FALSE,FALSE,0);
        map_center_lon_=139.65;map_center_lat_=36.0;map_zoom_=14;map_initialized_=true;
        add_page(page,"gnss","03    GNSS / Maps",false);
    }

    void add_imu() {
        GtkWidget* outer=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
        gtk_box_pack_start(GTK_BOX(outer),label("MOTION & CHANNELS\nIMU / Indicate","page-title"),FALSE,FALSE,4);
        GtkWidget* split=gtk_grid_new(); gtk_grid_set_column_homogeneous(GTK_GRID(split),TRUE);
        GtkWidget* readings=gtk_box_new(GTK_ORIENTATION_VERTICAL,2); gtk_style_context_add_class(gtk_widget_get_style_context(readings),"card");
        gtk_box_pack_start(GTK_BOX(readings),label("加速度","section"),FALSE,FALSE,0);
        for(auto r:{std::tuple<const char*,const char*,const char*>("imu.AccelX","加速度 X","m/s²"),{"imu.AccelY","加速度 Y","m/s²"},{"imu.AccelZ","加速度 Z","m/s²"},{"imu.LongAccel","前後加速度","g"},{"imu.LatAccel","左右加速度","g"},{"imu.VertAccel","上下加速度","g"}}) gtk_box_pack_start(GTK_BOX(readings),reading(std::get<0>(r),std::get<1>(r),std::get<2>(r)),FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(readings),label("角速度・姿勢","section"),FALSE,FALSE,0);
        for(auto r:{std::tuple<const char*,const char*,const char*>("imu.GyroX","角速度 X","°/s"),{"imu.GyroY","角速度 Y","°/s"},{"imu.GyroZ","角速度 Z","°/s"},{"imu.Roll","ロール","°"},{"imu.Pitch","ピッチ","°"}}) gtk_box_pack_start(GTK_BOX(readings),reading(std::get<0>(r),std::get<1>(r),std::get<2>(r)),FALSE,FALSE,0);
        GtkWidget* gpanel=gtk_box_new(GTK_ORIENTATION_VERTICAL,4); gtk_style_context_add_class(gtk_widget_get_style_context(gpanel),"card");
        gtk_box_pack_start(GTK_BOX(gpanel),label("G表示","section"),FALSE,FALSE,0); g_area_=gtk_drawing_area_new(); gtk_widget_set_size_request(g_area_,300,300); g_signal_connect(g_area_,"draw",G_CALLBACK(draw_g),this); gtk_box_pack_start(GTK_BOX(gpanel),g_area_,TRUE,TRUE,0); gtk_box_pack_start(GTK_BOX(gpanel),label("横：左右加速度 / 縦：前後加速度 / 外周：1 g","metric-name"),FALSE,FALSE,0);
        gtk_grid_attach(GTK_GRID(split),readings,0,0,3,1); gtk_grid_attach(GTK_GRID(split),gpanel,3,0,2,1);
        gtk_box_pack_start(GTK_BOX(outer),split,TRUE,TRUE,0);
        GtkWidget* diagnostics_panel=gtk_box_new(GTK_ORIENTATION_VERTICAL,2); gtk_style_context_add_class(gtk_widget_get_style_context(diagnostics_panel),"card");
        gtk_box_pack_start(GTK_BOX(diagnostics_panel),label("受信状態                                      実機Bridge経路","section"),FALSE,FALSE,0);
        diag_ = label("取得中...", "body");
        gtk_label_set_line_wrap(GTK_LABEL(diag_), TRUE);
        gtk_box_pack_start(GTK_BOX(diagnostics_panel),diag_,FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(outer),diagnostics_panel,FALSE,FALSE,0);
        add_page(outer,"imu","04    IMU / Indicate");
    }

    static gboolean draw_g(GtkWidget* widget, cairo_t* cr, gpointer data) {
        App* self=static_cast<App*>(data); GtkAllocation a; gtk_widget_get_allocation(widget,&a); double cx=a.width/2.0,cy=a.height/2.0,r=std::max(30.0,std::min(a.width,a.height)/2.0-28.0);
        cairo_set_line_width(cr,1.0); cairo_set_source_rgb(cr,.78,.78,.78);
        for(double scale:{.5,1.0}) { cairo_arc(cr,cx,cy,r*scale,0,2*M_PI); cairo_stroke(cr); }
        cairo_move_to(cr,cx-r,cy);cairo_line_to(cr,cx+r,cy);cairo_move_to(cr,cx,cy-r);cairo_line_to(cr,cx,cy+r);cairo_stroke(cr);
        double x=cx+std::max(-1.0,std::min(1.0,self->g_lat_))*r, y=cy-std::max(-1.0,std::min(1.0,self->g_long_))*r; cairo_set_source_rgb(cr,.72,.14,.16);cairo_arc(cr,x,y,7,0,2*M_PI);cairo_fill(cr); return FALSE;
    }

    static gboolean draw_trend(GtkWidget* widget,cairo_t* cr,gpointer data){
        App* s=static_cast<App*>(data);GtkAllocation a;gtk_widget_get_allocation(widget,&a);
        double left=48,top=14,width=std::max(1,a.width-68),height=std::max(1,a.height-44);
        double now=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
        double peak=0;for(auto [t,v]:s->trend_)if(now-t<=60&&std::isfinite(v))peak=std::max(peak,v);
        double maximum=std::max(20.0,std::ceil(peak/20.0)*20.0);
        cairo_select_font_face(cr,"sans",CAIRO_FONT_SLANT_NORMAL,CAIRO_FONT_WEIGHT_NORMAL);cairo_set_font_size(cr,13);
        for(int i=0;i<=4;i++){
            double y=top+height*(1-i/4.0);cairo_set_source_rgb(cr,.82,.85,.87);cairo_set_line_width(cr,1);
            cairo_move_to(cr,left,y);cairo_line_to(cr,left+width,y);cairo_stroke(cr);
            cairo_set_source_rgb(cr,.25,.3,.34);cairo_move_to(cr,4,y+4);cairo_show_text(cr,std::to_string((int)(maximum*i/4)).c_str());
        }
        for(int i=0;i<=4;i++){
            double x=left+width*i/4;cairo_set_source_rgb(cr,.9,.91,.92);cairo_move_to(cr,x,top);cairo_line_to(cr,x,top+height);cairo_stroke(cr);
            std::string caption=i==4?"0 s":std::to_string(-60+15*i)+" s";
            cairo_set_source_rgb(cr,.25,.3,.34);cairo_move_to(cr,x-(i==4?20:12),top+height+22);cairo_show_text(cr,caption.c_str());
        }
        cairo_save(cr);cairo_rectangle(cr,left,top,width,height);cairo_clip(cr);
        cairo_set_source_rgb(cr,.0,.43,.64);cairo_set_line_width(cr,3);cairo_set_line_join(cr,CAIRO_LINE_JOIN_ROUND);
        bool first=true;double previous=0;
        for(auto [t,v]:s->trend_){if(now-t>60||!std::isfinite(v)){first=true;continue;}
            double x=left+width*(1-(now-t)/60),y=top+height*(1-std::clamp(v/maximum,0.0,1.0));
            if(first||t-previous>1)cairo_move_to(cr,x,y);else cairo_line_to(cr,x,y);first=false;previous=t;
        }cairo_stroke(cr);cairo_restore(cr);return FALSE;
    }
    static std::pair<double,double> map_project(double lon,double lat,int zoom){double n=std::pow(2.0,zoom),clamped=std::max(-85.05112878,std::min(85.05112878,lat));double x=(lon+180.0)/360.0*n,y=(1.0-std::log(std::tan(clamped*M_PI/180.0)+1.0/std::cos(clamped*M_PI/180.0))/M_PI)/2.0*n;return{x,y};}
    void map_center_from_world(double x,double y) {
        double n=std::pow(2.0,map_zoom_);
        map_center_lon_=std::fmod(std::fmod(x/n*360.0,360.0)+360.0,360.0)-180.0;
        map_center_lat_=std::atan(std::sinh(M_PI*(1-2*std::max(0.0,std::min(n,y))/n)))*180/M_PI;
    }
    void map_redraw() {
        if(map_initialized_){tile_lon_=map_center_lon_;tile_lat_=map_center_lat_;tile_zoom_=map_zoom_;tile_ready_=true;}
        if(map_area_)gtk_widget_queue_draw(map_area_);
    }
    void map_manual() {
        map_follow_=false;
        gtk_button_set_label(GTK_BUTTON(map_follow_button_),"追従 OFF");
    }
    static void map_drag_begin(GtkGestureDrag* gesture,gdouble,gdouble,gpointer data) {
        App* s=static_cast<App*>(data);if(!s->map_initialized_)return;
        auto p=map_project(s->map_center_lon_,s->map_center_lat_,s->map_zoom_);
        s->drag_x_=p.first;s->drag_y_=p.second;s->map_manual();
        gtk_gesture_set_state(GTK_GESTURE(gesture),GTK_EVENT_SEQUENCE_CLAIMED);
    }
    static void map_drag_update(GtkGestureDrag*,gdouble x,gdouble y,gpointer data) {
        App* s=static_cast<App*>(data);if(!s->map_initialized_||gtk_gesture_is_recognized(s->map_pinch_))return;
        s->map_center_from_world(s->drag_x_-x/256.0,s->drag_y_-y/256.0);s->map_redraw();
    }
    static void map_pinch_begin(GtkGesture* gesture,GdkEventSequence*,gpointer data) {
        App* s=static_cast<App*>(data);if(!s->map_initialized_)return;
        s->pinch_zoom_=s->map_zoom_;s->map_manual();
        double x=0,y=0;gtk_gesture_get_bounding_box_center(gesture,&x,&y);
        GtkAllocation a;gtk_widget_get_allocation(s->map_area_,&a);
        auto p=map_project(s->map_center_lon_,s->map_center_lat_,s->map_zoom_);
        double n=std::pow(2.0,s->map_zoom_),wx=p.first+(x-a.width/2.0)/256,wy=p.second+(y-a.height/2.0)/256;
        s->pinch_anchor_lon_=wx/n*360-180;
        s->pinch_anchor_lat_=std::atan(std::sinh(M_PI*(1-2*wy/n)))*180/M_PI;
        gtk_gesture_set_state(gesture,GTK_EVENT_SEQUENCE_CLAIMED);
    }
    static void map_pinch_scale(GtkGestureZoom* gesture,gdouble scale,gpointer data) {
        App* s=static_cast<App*>(data);if(!s->map_initialized_||!std::isfinite(scale)||scale<=0)return;
        s->map_zoom_=std::max(2,std::min(19,s->pinch_zoom_+static_cast<int>(std::lround(std::log2(scale)))));
        double x=0,y=0;gtk_gesture_get_bounding_box_center(GTK_GESTURE(gesture),&x,&y);
        GtkAllocation a;gtk_widget_get_allocation(s->map_area_,&a);
        auto anchor=map_project(s->pinch_anchor_lon_,s->pinch_anchor_lat_,s->map_zoom_);
        s->map_center_from_world(anchor.first-(x-a.width/2.0)/256,anchor.second-(y-a.height/2.0)/256);
        s->map_redraw();
    }
    GdkPixbuf* offline_tile(int z,int x,int y){
        const std::string key=std::to_string(z)+"/"+std::to_string(x)+"/"+std::to_string(y);
        auto found=map_tiles_.find(key);if(found!=map_tiles_.end())return found->second;
        GdkPixbuf* result=nullptr;
        for(int source=z;source>=2;--source){
            int factor=1<<(z-source),sx=x/factor,sy=y/factor;
            std::string path="/home/arduino/ecocapture-v2-data/maps/gsi/seamlessphoto/"+std::to_string(source)+"/"+std::to_string(sx)+"/"+std::to_string(sy)+".jpg";
            GError* error=nullptr;auto original=gdk_pixbuf_new_from_file(path.c_str(),&error);if(error)g_error_free(error);if(!original)continue;
            // Render a crop of a stored parent tile at higher zoom, never fetch online.
            int width=gdk_pixbuf_get_width(original),height=gdk_pixbuf_get_height(original);
            int cropw=std::max(1,width/factor),croph=std::max(1,height/factor);
            int left=std::min(width-cropw,(x%factor)*width/factor),top=std::min(height-croph,(y%factor)*height/factor);
            auto crop=gdk_pixbuf_new_subpixbuf(original,left,top,cropw,croph);
            result=gdk_pixbuf_scale_simple(crop,256,256,GDK_INTERP_BILINEAR);g_object_unref(crop);g_object_unref(original);break;
        }
        if(result){while(map_tiles_.size()>=160){auto old=map_tiles_.begin();g_object_unref(old->second);map_tiles_.erase(old);}map_tiles_[key]=result;}
        return result;
    }
    static void map_action(GtkButton* button,gpointer data){App* s=static_cast<App*>(data);std::string action=static_cast<const char*>(g_object_get_data(G_OBJECT(button),"action"));if(action=="zoom-in")s->map_zoom_=std::min(19,s->map_zoom_+1);else if(action=="zoom-out")s->map_zoom_=std::max(2,s->map_zoom_-1);else if(action=="follow"){s->map_follow_=!s->map_follow_;gtk_button_set_label(GTK_BUTTON(s->map_follow_button_),s->map_follow_?"追従 ON":"追従 OFF");}else if(action=="current"&&s->map_initialized_){s->map_center_lon_=s->current_lon_;s->map_center_lat_=s->current_lat_;}else if(action=="clear")s->track_.clear();else if(action=="fit"&&!s->track_.empty()){double minlon=180,maxlon=-180,minlat=90,maxlat=-90;for(auto [lon,lat,t]:s->track_){minlon=std::min(minlon,lon);maxlon=std::max(maxlon,lon);minlat=std::min(minlat,lat);maxlat=std::max(maxlat,lat);}s->map_center_lon_=(minlon+maxlon)/2;s->map_center_lat_=(minlat+maxlat)/2;double span=std::max((maxlon-minlon)*std::cos(s->map_center_lat_*M_PI/180),maxlat-minlat);s->map_zoom_=span>0?std::max(2,std::min(19,static_cast<int>(std::floor(std::log2(180.0/span))))):18;s->map_follow_=false;gtk_button_set_label(GTK_BUTTON(s->map_follow_button_),"追従 OFF");}s->map_redraw();}
    static gboolean draw_map(GtkWidget* widget,cairo_t* cr,gpointer data){App* s=static_cast<App*>(data);GtkAllocation a;gtk_widget_get_allocation(widget,&a);cairo_set_source_rgb(cr,.14,.17,.18);cairo_paint(cr);if(!s->map_initialized_)return FALSE;auto center=map_project(s->map_center_lon_,s->map_center_lat_,s->map_zoom_);int n=1<<s->map_zoom_;int x0=static_cast<int>(std::floor(center.first-a.width/512.0)),x1=static_cast<int>(std::floor(center.first+a.width/512.0)),y0=std::max(0,static_cast<int>(std::floor(center.second-a.height/512.0))),y1=std::min(n-1,static_cast<int>(std::floor(center.second+a.height/512.0)));for(int y=y0;y<=y1;++y)for(int rawx=x0;rawx<=x1;++rawx){int x=(rawx%n+n)%n;std::string key=std::to_string(s->map_zoom_)+"/"+std::to_string(x)+"/"+std::to_string(y);double left=a.width/2.0+(rawx-center.first)*256,top=a.height/2.0+(y-center.second)*256;GdkPixbuf* pix=s->offline_tile(s->map_zoom_,x,y);if(pix){gdk_cairo_set_source_pixbuf(cr,pix,left,top);cairo_rectangle(cr,left,top,257,257);cairo_fill(cr);}else{cairo_set_source_rgb(cr,.25,.29,.3);cairo_rectangle(cr,left,top,256,256);cairo_stroke(cr);}}
        auto path=[&](){bool first=true;double last=0;for(auto [lon,lat,t]:s->track_){auto p=map_project(lon,lat,s->map_zoom_);double x=a.width/2+(p.first-center.first)*256,y=a.height/2+(p.second-center.second)*256;if(first||t-last>1.0)cairo_move_to(cr,x,y);else cairo_line_to(cr,x,y);first=false;last=t;}};if(!s->track_.empty()){path();cairo_set_source_rgb(cr,1,1,1);cairo_set_line_width(cr,5);cairo_stroke(cr);path();cairo_set_source_rgb(cr,.9,.13,.17);cairo_set_line_width(cr,2.5);cairo_stroke(cr);}auto current=map_project(s->current_lon_,s->current_lat_,s->map_zoom_);double px=a.width/2+(current.first-center.first)*256,py=a.height/2+(current.second-center.second)*256;cairo_set_source_rgb(cr,1,1,1);cairo_arc(cr,px,py,8,0,2*M_PI);cairo_fill(cr);cairo_set_source_rgb(cr,.9,.13,.17);cairo_arc(cr,px,py,6,0,2*M_PI);cairo_fill(cr);cairo_set_source_rgba(cr,1,1,1,.93);cairo_rectangle(cr,a.width-53,10,43,30);cairo_fill(cr);cairo_set_source_rgb(cr,.12,.12,.12);cairo_select_font_face(cr,"Sans",CAIRO_FONT_SLANT_NORMAL,CAIRO_FONT_WEIGHT_BOLD);cairo_set_font_size(cr,13);cairo_move_to(cr,a.width-46,30);cairo_show_text(cr,"N ↑");return FALSE;}
    static gboolean draw_solve(GtkWidget* widget,cairo_t* cr,gpointer data){App* s=static_cast<App*>(data);GtkAllocation a;gtk_widget_get_allocation(widget,&a);cairo_set_source_rgb(cr,.96,.96,.96);cairo_paint(cr);if(s->solve_track_.size()<2)return FALSE;double lon0=s->solve_track_[0].first,lat0=s->solve_track_[0].second,minx=0,maxx=0,miny=0,maxy=0;std::vector<std::pair<double,double>> points;for(auto p:s->solve_track_){double x=(p.first-lon0)*111320*std::cos(lat0*M_PI/180),y=(p.second-lat0)*111320;points.push_back({x,y});minx=std::min(minx,x);maxx=std::max(maxx,x);miny=std::min(miny,y);maxy=std::max(maxy,y);}double scale=std::min((a.width-40)/std::max(10.0,maxx-minx),(a.height-30)/std::max(10.0,maxy-miny));cairo_set_source_rgb(cr,.1,.1,.1);cairo_set_line_width(cr,2);bool first=true;for(auto p:points){double x=a.width/2+(p.first-(minx+maxx)/2)*scale,y=a.height/2-(p.second-(miny+maxy)/2)*scale;if(first)cairo_move_to(cr,x,y);else cairo_line_to(cr,x,y);first=false;}cairo_stroke(cr);return FALSE;}

    static GtkWidget* field_entry(GtkWidget* row,const char* key,const std::string& value,int width=9) {
        GtkWidget* w=gtk_entry_new(); gtk_entry_set_text(GTK_ENTRY(w),value.c_str()); gtk_entry_set_width_chars(GTK_ENTRY(w),width); g_object_set_data(G_OBJECT(row),key,w); return w;
    }
    static GtkWidget* field_combo(GtkWidget* row,const char* key,const std::vector<std::pair<std::string,std::string>>& values,const std::string& active) {
        GtkWidget* w=gtk_combo_box_text_new(); for(const auto& v:values) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(w),v.first.c_str(),v.second.c_str()); gtk_combo_box_set_active_id(GTK_COMBO_BOX(w),active.c_str()); g_object_set_data(G_OBJECT(row),key,w); return w;
    }
    void add_signal_row(const json& s=json::object()) {
        if(!signal_list_) return;
        GtkWidget* row=gtk_grid_new(); g_object_set_data_full(G_OBJECT(row),"signal-json",g_strdup(s.dump().c_str()),g_free); gtk_style_context_add_class(gtk_widget_get_style_context(row),"card"); gtk_grid_set_column_spacing(GTK_GRID(row),7);gtk_grid_set_row_spacing(GTK_GRID(row),4);
        auto put=[&](const char* title,GtkWidget* w,int col,int r){GtkWidget* box=gtk_box_new(GTK_ORIENTATION_VERTICAL,1);gtk_box_pack_start(GTK_BOX(box),label(title,"metric-name"),FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(box),w,FALSE,FALSE,0);gtk_grid_attach(GTK_GRID(row),box,col,r,1,1);};
        put("CAN",field_combo(row,"channel",{{"1","CAN1"},{"2","CAN2"}},std::to_string(s.value("channel",1))),0,0);
        put("信号名",field_entry(row,"name",text_value(s,"name",""),13),1,0); put("単位",field_entry(row,"unit",text_value(s,"unit",""),7),2,0);
        std::ostringstream id; id<<std::hex<<std::uppercase<<s.value("can_id",256); put("CAN ID (16進)",field_entry(row,"can_id",id.str(),9),3,0);
        put("ID種別",field_combo(row,"extended",{{"false","標準11bit"},{"true","拡張29bit"}},s.value("extended",false)?"true":"false"),4,0);
        put("開始byte",field_entry(row,"byte_offset",std::to_string(s.value("byte_offset",0)),5),0,1);
        put("型",field_combo(row,"data_type",{{"uint8","uint8"},{"int8","int8"},{"uint16","uint16"},{"int16","int16"},{"uint32","uint32"},{"int32","int32"}},text_value(s,"data_type","uint16")),1,1);
        put("Endian",field_combo(row,"endian",{{"little","little"},{"big","big"}},text_value(s,"endian","little")),2,1);
        put("倍率",field_entry(row,"scale",std::to_string(s.value("scale",1.0)),7),3,1); put("加算",field_entry(row,"offset",std::to_string(s.value("offset",0.0)),7),4,1);
        std::string mask=s.contains("bit_mask")&&!s["bit_mask"].is_null()?std::to_string(s["bit_mask"].get<int>()):""; put("bit mask",field_entry(row,"bit_mask",mask,6),5,1);
        GtkWidget* remove=gtk_button_new_with_label("信号を削除");g_signal_connect(remove,"clicked",G_CALLBACK(+[](GtkButton* b,gpointer){gtk_widget_destroy(GTK_WIDGET(g_object_get_data(G_OBJECT(b),"row")));}),nullptr);g_object_set_data(G_OBJECT(remove),"row",row);gtk_grid_attach(GTK_GRID(row),remove,5,0,1,1);
        gtk_box_pack_start(GTK_BOX(signal_list_),row,FALSE,FALSE,0);gtk_widget_show_all(row);
    }
    static void add_signal(GtkButton*,gpointer data){App* s=static_cast<App*>(data);GList* children=gtk_container_get_children(GTK_CONTAINER(s->signal_list_));int n=g_list_length(children);g_list_free(children);if(n<64)s->add_signal_row();else gtk_label_set_text(GTK_LABEL(s->settings_action_),"信号は64個までです");}
    json collect_signals() {
        json result=json::array(); GList* children=gtk_container_get_children(GTK_CONTAINER(signal_list_));
        for(GList* it=children;it;it=it->next){GtkWidget* row=GTK_WIDGET(it->data);auto entry=[&](const char* k){return std::string(gtk_entry_get_text(GTK_ENTRY(g_object_get_data(G_OBJECT(row),k))));};auto combo=[&](const char* k){const char* v=gtk_combo_box_get_active_id(GTK_COMBO_BOX(g_object_get_data(G_OBJECT(row),k)));return std::string(v?v:"");};try{json s={{"channel",std::stoi(combo("channel"))},{"name",entry("name")},{"unit",entry("unit")},{"can_id",std::stoi(entry("can_id"),nullptr,16)},{"extended",combo("extended")=="true"},{"byte_offset",std::stoi(entry("byte_offset"))},{"data_type",combo("data_type")},{"endian",combo("endian")},{"scale",std::stod(entry("scale"))},{"offset",std::stod(entry("offset"))}};std::string mask=entry("bit_mask");s["bit_mask"]=mask.empty()?json(nullptr):json(std::stoi(mask));const char* saved=static_cast<const char*>(g_object_get_data(G_OBJECT(row),"signal-json"));if(saved){json prior=json::parse(saved);for(const char* field:{"conversion","pullup_ohm","ntc_points"})if(prior.contains(field))s[field]=prior[field];}result.push_back(s);}catch(...){}}
        g_list_free(children); return result;
    }

    void set_action_text(const std::string& value){if(action_)gtk_label_set_text(GTK_LABEL(action_),value.c_str());}
    static std::string encoded(const std::string& value){CURL* c=curl_easy_init();if(!c)return value;char* escaped=curl_easy_escape(c,value.c_str(),static_cast<int>(value.size()));std::string out=escaped?escaped:value;if(escaped)curl_free(escaped);curl_easy_cleanup(c);return out;}
    static void log_button(GtkButton* button,gpointer data){App* s=static_cast<App*>(data);std::string action=static_cast<const char*>(g_object_get_data(G_OBJECT(button),"action"));std::string name=static_cast<const char*>(g_object_get_data(G_OBJECT(button),"name"));if(action=="delete"){GtkWidget* dialog=gtk_message_dialog_new(GTK_WINDOW(s->window_),GTK_DIALOG_MODAL,GTK_MESSAGE_WARNING,GTK_BUTTONS_OK_CANCEL,"%s を削除しますか？",name.c_str());int response=gtk_dialog_run(GTK_DIALOG(dialog));gtk_widget_destroy(dialog);if(response!=GTK_RESPONSE_OK)return;}s->set_action_text("処理中…");std::thread([s,action,name]{std::string path="/api/logs/"+encoded(name),message;HttpResult r;if(action=="sd")r=request(path+"/sd","{}");else if(action=="delete"){CURL* c=curl_easy_init();if(c){std::string url=std::string(kApi)+path;curl_easy_setopt(c,CURLOPT_URL,url.c_str());curl_easy_setopt(c,CURLOPT_CUSTOMREQUEST,"DELETE");curl_easy_setopt(c,CURLOPT_WRITEFUNCTION,append_body);curl_easy_setopt(c,CURLOPT_WRITEDATA,&r.body);curl_easy_perform(c);curl_easy_getinfo(c,CURLINFO_RESPONSE_CODE,&r.code);curl_easy_cleanup(c);}}else{std::string suffix=action=="meta"?"/metadata":action=="can"?"/can":"/download";r=request(path+suffix);}
            if(r.code>=200&&r.code<300){if(action=="sd")message="SDへのコピーを開始しました";else if(action=="delete")message="ログを削除しました";else if(action=="solve"){std::istringstream in(r.body);std::string line;std::getline(in,line);std::vector<std::string> head;std::stringstream hs(line);while(std::getline(hs,line,','))head.push_back(line);auto index=[&](const char* key){for(size_t i=0;i<head.size();++i)if(head[i]==key)return static_cast<int>(i);return -1;};int speed=index("GPSSpeed"),distance=index("Distance"),stamp=index("timestamp_ms");double max_speed=0,sum=0,first_d=0,last_d=0,first_t=0,last_t=0;long count=0;bool first=true;while(std::getline(in,line)){std::vector<std::string> row;std::stringstream rs(line);std::string part;while(std::getline(rs,part,','))row.push_back(part);try{if(speed>=0&&speed<(int)row.size()&&!row[speed].empty()){double v=std::stod(row[speed]);max_speed=std::max(max_speed,v);sum+=v;count++;}if(distance>=0&&distance<(int)row.size()&&!row[distance].empty()){double d=std::stod(row[distance]);if(first)first_d=d;last_d=d;}if(stamp>=0&&stamp<(int)row.size()&&!row[stamp].empty()){double t=std::stod(row[stamp]);if(first)first_t=t;last_t=t;}first=false;}catch(...){}}std::ostringstream report;report<<name<<" / サンプル "<<count<<" / 最高速度 "<<std::fixed<<std::setprecision(1)<<max_speed<<" km/h / 平均速度 "<<(count?sum/count:0)<<" km/h / 距離 "<<std::setprecision(2)<<std::max(0.0,last_d-first_d)<<" km / 時間 "<<std::setprecision(1)<<std::max(0.0,(last_t-first_t)/1000)<<" 秒";message=report.str();}else{std::filesystem::create_directories("/home/arduino/Downloads");std::string filename=name+(action=="meta"?".meta.json":action=="can"?".can.jsonl":"");std::ofstream out("/home/arduino/Downloads/"+filename,std::ios::binary);out.write(r.body.data(),r.body.size());message="Downloads に保存しました: "+filename;}}else message="操作に失敗しました (HTTP "+std::to_string(r.code)+")";char* copy=g_strdup(message.c_str());g_idle_add([](gpointer p)->gboolean{auto x=static_cast<std::pair<App*,char*>*>(p);x->first->set_action_text(x->second);if(std::string(x->second).find(" / サンプル ")!=std::string::npos&&x->first->solve_summary_)gtk_label_set_text(GTK_LABEL(x->first->solve_summary_),x->second);g_free(x->second);delete x;return G_SOURCE_REMOVE;},new std::pair<App*,char*>(s,copy));}).detach();}
    GtkWidget* make_log_button(const char* title,const char* action,const std::string& name){GtkWidget* b=gtk_button_new_with_label(title);gtk_style_context_add_class(gtk_widget_get_style_context(b),"compact");g_object_set_data_full(G_OBJECT(b),"action",g_strdup(action),g_free);g_object_set_data_full(G_OBJECT(b),"name",g_strdup(name.c_str()),g_free);g_signal_connect(b,"clicked",G_CALLBACK(log_button),this);return b;}
    static void sd_download(GtkButton* button,gpointer data){App* s=static_cast<App*>(data);int index=GPOINTER_TO_INT(g_object_get_data(G_OBJECT(button),"index"));s->set_action_text("SDログを取得中…");std::thread([s,index]{HttpResult r=request("/api/sd/logs/"+std::to_string(index)+"/download");std::ostringstream name;name<<"EL"<<std::setw(6)<<std::setfill('0')<<index<<".BIN";std::string message;if(r.code==200&&r.error.empty()){std::filesystem::create_directories("/home/arduino/Downloads");std::ofstream out("/home/arduino/Downloads/"+name.str(),std::ios::binary);out.write(r.body.data(),r.body.size());out.close();message=out?"Downloads に保存しました: "+name.str():"SDログの保存に失敗しました";}else message="SDログを取得できませんでした";char* copy=g_strdup(message.c_str());g_idle_add([](gpointer p)->gboolean{auto x=static_cast<std::pair<App*,char*>*>(p);x->first->set_action_text(x->second);g_free(x->second);delete x;return G_SOURCE_REMOVE;},new std::pair<App*,char*>(s,copy));}).detach();}

    static void sd_solve(GtkButton* button,gpointer data){
        App* s=static_cast<App*>(data);int index=GPOINTER_TO_INT(g_object_get_data(G_OBJECT(button),"index"));
        s->set_action_text("SDログを読み取り・解析中…");
        std::thread([s,index]{auto r=request("/api/sd/logs/"+std::to_string(index)+"/summary");
            struct Result{App* app;std::string message;std::vector<std::pair<double,double>> track;};
            auto result=new Result{s,"SDログを解析できませんでした",{}};
            try{if(r.code==200){auto j=json::parse(r.body);std::ostringstream out;out<<"EL"<<std::setw(6)<<std::setfill('0')<<index<<".BIN / IMU "<<j.value("imu",0)<<" / CAN "<<j.value("can",0)<<" / 最高速度 "<<std::fixed<<std::setprecision(1)<<j.value("max_speed",0.0)<<" km/h / 時間 "<<j.value("seconds",0.0)<<" 秒";result->message=out.str();for(const auto& p:j["track"])result->track.emplace_back(p[0].get<double>(),p[1].get<double>());}}catch(...){}
            g_idle_add([](gpointer p)->gboolean{std::unique_ptr<Result> x(static_cast<Result*>(p));x->app->set_action_text(x->message);gtk_label_set_text(GTK_LABEL(x->app->solve_summary_),x->message.c_str());x->app->solve_track_=std::move(x->track);gtk_widget_queue_draw(x->app->solve_area_);return G_SOURCE_REMOVE;},result);
        }).detach();
    }

    void add_logs() {
        GtkWidget* box=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
        gtk_box_pack_start(GTK_BOX(box),label("RECORDINGS\nLogging / Solve","page-title"),FALSE,FALSE,0);
        storage_free_=wrapped_label("保存先：SDカード · 本体の直近バックアップは自動管理","body");
        gtk_box_pack_start(GTK_BOX(box),storage_free_,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(box),wrapped_label("記録の開始・停止はDashboardで操作します。停止後、SD一覧は自動更新されます。","metric-name"),FALSE,FALSE,0);
        action_=wrapped_label("","action");gtk_box_pack_start(GTK_BOX(box),action_,FALSE,FALSE,0);
        sd_logs_box_=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
        sd_logs_=label("SDログ一覧を取得中…","body");
        gtk_box_pack_start(GTK_BOX(sd_logs_box_),sd_logs_,FALSE,FALSE,0);
        // One page-level scroll container: no nested fixed-height log list.
        gtk_box_pack_start(GTK_BOX(box),sd_logs_box_,FALSE,FALSE,0);
        GtkWidget* solved=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);
        gtk_style_context_add_class(gtk_widget_get_style_context(solved),"card");
        gtk_box_pack_start(GTK_BOX(solved),label("SD走行データ解析","section"),FALSE,FALSE,0);
        solve_summary_=wrapped_label("SDログの「解析」を選択してください。","body");
        gtk_box_pack_start(GTK_BOX(solved),solve_summary_,FALSE,FALSE,0);
        solve_area_=gtk_drawing_area_new();gtk_widget_set_size_request(solve_area_,-1,150);
        g_signal_connect(solve_area_,"draw",G_CALLBACK(draw_solve),this);
        gtk_box_pack_start(GTK_BOX(solved),solve_area_,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(box),solved,FALSE,FALSE,0);
        add_page(box,"logs","05    Logging / Solve");
    }

    void add_settings() {
        GtkWidget* page=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
        gtk_box_pack_start(GTK_BOX(page),label("DEVICE CONFIGURATION\nSettings / CAN","page-title"),FALSE,FALSE,4);
        GtkWidget* tabs=gtk_box_new(GTK_ORIENTATION_VERTICAL,0),*settings_stack=gtk_stack_new(),*settings_switcher=gtk_stack_switcher_new(), *can_box=gtk_box_new(GTK_ORIENTATION_VERTICAL,6), *device_box=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);
        gtk_stack_set_homogeneous(GTK_STACK(settings_stack),FALSE);gtk_stack_set_vhomogeneous(GTK_STACK(settings_stack),FALSE);gtk_stack_set_transition_type(GTK_STACK(settings_stack),GTK_STACK_TRANSITION_TYPE_NONE);gtk_stack_switcher_set_stack(GTK_STACK_SWITCHER(settings_switcher),GTK_STACK(settings_stack));gtk_widget_set_halign(settings_switcher,GTK_ALIGN_START);gtk_box_pack_start(GTK_BOX(tabs),settings_switcher,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(tabs),settings_stack,FALSE,FALSE,0);
        GtkWidget* ncec_panel=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);gtk_style_context_add_class(gtk_widget_get_style_context(ncec_panel),"card");GtkWidget* ncec_head=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6),*ncec=gtk_button_new_with_label("NCECの信号定義を読み込む");gtk_box_pack_start(GTK_BOX(ncec_head),label("NCEC 2005 MT / NOPRO","section"),TRUE,TRUE,0);gtk_box_pack_end(GTK_BOX(ncec_head),ncec,FALSE,FALSE,0);g_signal_connect(ncec,"clicked",G_CALLBACK(load_ncec),this);gtk_box_pack_start(GTK_BOX(ncec_panel),ncec_head,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(ncec_panel),wrapped_label("500 kbps・標準ID。確定済み12信号を設定へ読み込みます。編集中の信号定義は置き換わり、下の保存ボタンで確定します。\n輪速は前A・前B・後A・後B（左右未確定）。油温・油圧・舵角・ブレーキ圧は含めません。回転数表示は8000rpmまで、式の実測検証は3439rpmまでです。\nCAN1・CAN2を受信専用で収集します。信号が届かない項目は空欄になります。","body"),FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(can_box),ncec_panel,FALSE,FALSE,0);
        GtkWidget* panel=gtk_box_new(GTK_ORIENTATION_VERTICAL,6); gtk_style_context_add_class(gtk_widget_get_style_context(panel),"card");
        gtk_box_pack_start(GTK_BOX(panel),label("基本設定","section"),FALSE,FALSE,0);
        GtkWidget* form=gtk_grid_new(); gtk_grid_set_column_spacing(GTK_GRID(form),14); gtk_grid_set_row_spacing(GTK_GRID(form),8);
        gtk_grid_attach(GTK_GRID(form),label("機器名","metric-name"),0,0,1,1); config_name_=gtk_entry_new(); gtk_grid_attach(GTK_GRID(form),config_name_,1,0,1,1);
        gtk_grid_attach(GTK_GRID(form),label("表示プロファイル","metric-name"),2,0,1,1); config_profile_=gtk_combo_box_text_new();
        for(auto p:{std::pair<const char*,const char*>("no-can","車載CAN接続なし"),{"demo-vehicle","車両表示"},{"ncec-2005-mt","NCEC 2005 MT / NOPRO"}}) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(config_profile_),p.first,p.second);
        gtk_grid_attach(GTK_GRID(form),config_profile_,3,0,1,1);
        config_bitrate_=gtk_combo_box_text_new();
        for(auto p:{std::pair<const char*,const char*>("125000","125 kbit/s"),{"250000","250 kbit/s"},{"500000","500 kbit/s"},{"1000000","1 Mbit/s"}}) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(config_bitrate_),p.first,p.second);
        config_auto_=gtk_check_button_new_with_label("Web起動時にCSVを自動記録（SDは電源投入時に記録）"); gtk_grid_attach(GTK_GRID(form),config_auto_,0,1,4,1);
        gtk_box_pack_start(GTK_BOX(panel),form,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(can_box),panel,FALSE,FALSE,0);
        GtkWidget* can_panel=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);gtk_style_context_add_class(gtk_widget_get_style_context(can_panel),"card");
        GtkWidget* signal_head=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6); settings_=label("CAN信号定義を取得中...", "section"); GtkWidget* add_signal_button=gtk_button_new_with_label("信号を追加");g_signal_connect(add_signal_button,"clicked",G_CALLBACK(add_signal),this);gtk_box_pack_start(GTK_BOX(signal_head),settings_,TRUE,TRUE,0);gtk_box_pack_end(GTK_BOX(signal_head),add_signal_button,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(can_panel),signal_head,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(can_panel),label("保存したビットレートを両CANに適用します。標準・拡張ID、符号、倍率に対応。送信は行いません。","metric-name"),FALSE,FALSE,0);GtkWidget* bitrate_row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);gtk_box_pack_start(GTK_BOX(bitrate_row),label("ビットレート","metric-name"),FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(bitrate_row),config_bitrate_,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(can_panel),bitrate_row,FALSE,FALSE,0);
        signal_list_=gtk_box_new(GTK_ORIENTATION_VERTICAL,2);gtk_box_pack_start(GTK_BOX(can_panel),signal_list_,FALSE,FALSE,0);
        can_live_=wrapped_label("CANライブ値を受信待ち","body");gtk_box_pack_start(GTK_BOX(can_panel),can_live_,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(can_box),can_panel,FALSE,FALSE,0);
        GtkWidget* actions=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,6); GtkWidget* save=gtk_button_new_with_label("UNO Qに設定を保存");gtk_style_context_add_class(gtk_widget_get_style_context(save),"primary"); g_signal_connect(save,"clicked",G_CALLBACK(save_config),this);gtk_box_pack_start(GTK_BOX(actions),save,FALSE,FALSE,0);settings_action_=label("","action");gtk_box_pack_start(GTK_BOX(actions),settings_action_,TRUE,TRUE,0);gtk_box_pack_start(GTK_BOX(can_box),actions,FALSE,FALSE,0);
        GtkWidget* decode=gtk_box_new(GTK_ORIENTATION_VERTICAL,5); gtk_style_context_add_class(gtk_widget_get_style_context(decode),"card"); gtk_box_pack_start(GTK_BOX(decode),label("NCEC CANデータ解析","section"),FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(decode),wrapped_label("1行に「時刻ms CAN-ID(16進) データ(16進)」。時刻順、1回500フレームまで。解析のみで車両への送信は行いません。","metric-name"),FALSE,FALSE,0); ncec_input_=gtk_text_view_new(); gtk_widget_set_size_request(ncec_input_,-1,100); gtk_box_pack_start(GTK_BOX(decode),ncec_input_,FALSE,FALSE,0); GtkWidget* decode_actions=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4),*decode_button=gtk_button_new_with_label("解析");ncec_download_=gtk_button_new_with_label("CSVを保存");gtk_widget_set_sensitive(ncec_download_,FALSE);g_signal_connect(decode_button,"clicked",G_CALLBACK(decode_ncec),this);g_signal_connect(ncec_download_,"clicked",G_CALLBACK(download_ncec),this);gtk_box_pack_start(GTK_BOX(decode_actions),decode_button,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(decode_actions),ncec_download_,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(decode),decode_actions,FALSE,FALSE,0); ncec_result_=label("","body");gtk_label_set_selectable(GTK_LABEL(ncec_result_),TRUE); gtk_box_pack_start(GTK_BOX(decode),ncec_result_,FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(can_box),decode,FALSE,FALSE,0);
        GtkWidget* recording=gtk_box_new(GTK_ORIENTATION_VERTICAL,4);gtk_style_context_add_class(gtk_widget_get_style_context(recording),"card");gtk_box_pack_start(GTK_BOX(recording),label("記録について","section"),FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(recording),wrapped_label("IMUは約100 Hz、GNSSは10 Hzで実測します。起動するとSTM32がSDへ自動記録し、UNO Q側は内蔵eMMCへCSVを保存します。Linuxとの通信が切れてもSD記録は続きます。記録停止後にCSVをSDへコピーできます。\n加速度の方向はIMUモジュールの軸です。車体への取付方向とIMU校正は実車設置後に確認してください。LTEは初期状態で電源OFFです。","body"),FALSE,FALSE,0);calibration_info_=label("IMU校正：受信待ち","body");gtk_box_pack_start(GTK_BOX(recording),calibration_info_,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(can_box),recording,FALSE,FALSE,0);
        GtkWidget* device=gtk_box_new(GTK_ORIENTATION_VERTICAL,6); gtk_style_context_add_class(gtk_widget_get_style_context(device),"card"); gtk_box_pack_start(GTK_BOX(device),label("Wi-Fi接続","section"),FALSE,FALSE,0);
        GtkWidget* wf=gtk_grid_new(); gtk_grid_set_column_spacing(GTK_GRID(wf),10);gtk_grid_set_row_spacing(GTK_GRID(wf),5);
        gtk_grid_attach(GTK_GRID(wf),label("周囲のWi-Fi","metric-name"),0,0,1,1);wifi_networks_=gtk_combo_box_text_new();gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(wifi_networks_),"","ネットワークを選択");gtk_combo_box_set_active(GTK_COMBO_BOX(wifi_networks_),0);g_signal_connect(wifi_networks_,"changed",G_CALLBACK(wifi_selected),this);gtk_grid_attach(GTK_GRID(wf),wifi_networks_,1,0,2,1);GtkWidget* scan=gtk_button_new_with_label("再検索");g_signal_connect(scan,"clicked",G_CALLBACK(wifi_scan),this);gtk_grid_attach(GTK_GRID(wf),scan,3,0,1,1);
        gtk_grid_attach(GTK_GRID(wf),label("SSID","metric-name"),0,1,1,1); wifi_ssid_=gtk_entry_new(); gtk_grid_attach(GTK_GRID(wf),wifi_ssid_,1,1,1,1); gtk_grid_attach(GTK_GRID(wf),label("認証","metric-name"),2,1,1,1); wifi_security_=gtk_combo_box_text_new(); gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(wifi_security_),"wpa-psk","WPA / WPA2 Personal"); gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(wifi_security_),"sae","WPA3 Personal"); gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(wifi_security_),"open","パスワードなし"); gtk_combo_box_set_active(GTK_COMBO_BOX(wifi_security_),0); gtk_grid_attach(GTK_GRID(wf),wifi_security_,3,1,1,1); gtk_grid_attach(GTK_GRID(wf),label("Wi-Fiパスワード","metric-name"),0,2,1,1); wifi_password_=gtk_entry_new(); gtk_entry_set_visibility(GTK_ENTRY(wifi_password_),FALSE); gtk_grid_attach(GTK_GRID(wf),wifi_password_,1,2,1,1); GtkWidget* wc=gtk_button_new_with_label("接続して保存"),*wd=gtk_button_new_with_label("Wi-Fiを切断"); g_signal_connect(wc,"clicked",G_CALLBACK(wifi_connect),this); g_signal_connect(wd,"clicked",G_CALLBACK(wifi_disconnect),this); gtk_grid_attach(GTK_GRID(wf),wc,2,2,1,1); gtk_grid_attach(GTK_GRID(wf),wd,3,2,1,1); gtk_box_pack_start(GTK_BOX(device),wf,FALSE,FALSE,0);
        GtkWidget* share_card=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);gtk_style_context_add_class(gtk_widget_get_style_context(share_card),"card");gtk_box_pack_start(GTK_BOX(share_card),label("インターネット公開","section"),FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(share_card),wrapped_label("公開すると、リンクを知る人が走行値と位置を閲覧できます。Wi-Fi設定・機器管理・ログ操作は公開画面から利用できません。","body"),FALSE,FALSE,0); GtkWidget* share=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4),*share_on=gtk_button_new_with_label("閲覧用サイトを公開"),*share_off=gtk_button_new_with_label("公開を停止");sharing_copy_=gtk_button_new_with_label("公開URLをコピー");gtk_widget_set_sensitive(sharing_copy_,FALSE); g_object_set_data(G_OBJECT(share_on),"enabled",GINT_TO_POINTER(1)); g_object_set_data(G_OBJECT(share_off),"enabled",GINT_TO_POINTER(0)); g_signal_connect(share_on,"clicked",G_CALLBACK(sharing),this); g_signal_connect(share_off,"clicked",G_CALLBACK(sharing),this);g_signal_connect(sharing_copy_,"clicked",G_CALLBACK(copy_sharing),this); gtk_box_pack_start(GTK_BOX(share),share_on,FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(share),share_off,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(share),sharing_copy_,FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(share_card),share,FALSE,FALSE,0);sharing_status_=label("公開停止","metric-name");gtk_box_pack_start(GTK_BOX(share_card),sharing_status_,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(share_card),wrapped_label("Cloudflare Quick Tunnelを使用します。UNO Qがオンラインの間に利用でき、公開処理の再起動でURLが変わります。","metric-name"),FALSE,FALSE,0);
        GtkWidget* podium_card=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);gtk_style_context_add_class(gtk_widget_get_style_context(podium_card),"card");gtk_box_pack_start(GTK_BOX(podium_card),label("LTE / Podium センサ共有                                      目標 10 Hz","section"),FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(podium_card),label("LTEモジュールで位置・IMU・選択した車両信号を共有します。ローカル記録は別に続きます。","metric-name"),FALSE,FALSE,0);
        GtkWidget* pf=gtk_grid_new(); gtk_grid_set_column_spacing(GTK_GRID(pf),10); gtk_grid_set_row_spacing(GTK_GRID(pf),6);
        auto add_entry=[&](const char* name,GtkWidget** target,int col,int row,bool secret=false){gtk_grid_attach(GTK_GRID(pf),label(name,"metric-name"),col,row,1,1);*target=gtk_entry_new();if(secret)gtk_entry_set_visibility(GTK_ENTRY(*target),FALSE);gtk_grid_attach(GTK_GRID(pf),*target,col+1,row,1,1);};
        add_entry("APN",&podium_apn_,0,0); add_entry("APNユーザー名",&podium_user_,2,0); add_entry("APNパスワード",&podium_password_,0,1,true); add_entry("Podium送信キー",&podium_key_,2,1,true); add_entry("送信先",&podium_host_,0,2); add_entry("ポート",&podium_port_,2,2);
        gtk_box_pack_start(GTK_BOX(podium_card),pf,FALSE,FALSE,0); podium_hardware_=gtk_check_button_new_with_label("SIMとLTEアンテナを接続済み"); podium_enabled_=gtk_check_button_new_with_label("電源投入後もLTE送信を開始する"); gtk_box_pack_start(GTK_BOX(podium_card),podium_hardware_,FALSE,FALSE,0); gtk_box_pack_start(GTK_BOX(podium_card),podium_enabled_,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(podium_card),label("送信するセンサ値","metric-name"),FALSE,FALSE,0);podium_channels_box_=gtk_flow_box_new();gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(podium_channels_box_),GTK_SELECTION_NONE);gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(podium_channels_box_),4);gtk_box_pack_start(GTK_BOX(podium_card),podium_channels_box_,FALSE,FALSE,0);
        GtkWidget* pa=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4),*podium_save=gtk_button_new_with_label("LTE設定を保存"),*podium_off=gtk_button_new_with_label("送信OFF"),*podium_check=gtk_button_new_with_label("LTEを点検（電波OFF）"); gtk_style_context_add_class(gtk_widget_get_style_context(podium_save),"primary"); g_signal_connect(podium_save,"clicked",G_CALLBACK(podium_save_config),this);g_signal_connect(podium_off,"clicked",G_CALLBACK(podium_stop),this);g_signal_connect(podium_check,"clicked",G_CALLBACK(podium_check_action),this);gtk_box_pack_start(GTK_BOX(pa),podium_save,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(pa),podium_off,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(pa),podium_check,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(podium_card),pa,FALSE,FALSE,0);
        device_status_=label("状態を取得中...","body"); gtk_box_pack_start(GTK_BOX(podium_card),device_status_,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(podium_card),wrapped_label("送信キーはこの画面に再表示されません。Podiumの接続方式は暗号化なしのTCPです。SDのコピー・読出し中はLTEを休止します。","metric-name"),FALSE,FALSE,0);
        GtkWidget* task_card=gtk_box_new(GTK_ORIENTATION_VERTICAL,6);gtk_style_context_add_class(gtk_widget_get_style_context(task_card),"card");gtk_box_pack_start(GTK_BOX(task_card),label("タスクマネージャ                                      3秒間隔 / この画面を開いている間だけ更新","section"),FALSE,FALSE,0);system_info_=label("CPU・メモリ・温度・ストレージを取得中...","body");gtk_style_context_add_class(gtk_widget_get_style_context(system_info_),"mono");gtk_box_pack_start(GTK_BOX(task_card),system_info_,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(task_card),label("負荷の高い上位15件。プロセスCPUは1コアを100%とし、全体CPUは全コア合計を100%とします。","metric-name"),FALSE,FALSE,0);
        GtkWidget* podium_page=gtk_box_new(GTK_ORIENTATION_VERTICAL,8);
        gtk_box_pack_start(GTK_BOX(podium_page),label("LIVE TELEMETRY\nPodium 管理","page-title"),FALSE,FALSE,4);
        GtkWidget* live_actions=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,8);podium_toggle_=gtk_button_new_with_label("● 配信開始");
        gtk_style_context_add_class(gtk_widget_get_style_context(podium_toggle_),"record-toggle");
        gtk_widget_set_size_request(podium_toggle_,190,64);
        GtkCssProvider* live_css=gtk_css_provider_new();
        gtk_css_provider_load_from_data(live_css,"button {background-image:none;background-color:#171717;color:white;font-weight:bold;} button.recording {background-color:#c92828;} button:disabled {opacity:0.65;}",-1,nullptr);
        gtk_style_context_add_provider(gtk_widget_get_style_context(podium_toggle_),GTK_STYLE_PROVIDER(live_css),GTK_STYLE_PROVIDER_PRIORITY_APPLICATION+1);g_object_unref(live_css);
        gtk_widget_set_no_show_all(podium_off,TRUE);gtk_widget_hide(podium_off);
        g_signal_connect(podium_toggle_,"clicked",G_CALLBACK(podium_toggle),this);
        gtk_box_pack_start(GTK_BOX(live_actions),podium_toggle_,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(podium_page),live_actions,FALSE,FALSE,0);
        podium_live_=label("配信状態を確認中…","body");gtk_box_pack_start(GTK_BOX(podium_page),podium_live_,FALSE,FALSE,0);
        podium_message_=wrapped_label("キーを入力して配信開始。保存済みなら空欄のまま開始できます。","body");gtk_box_pack_start(GTK_BOX(podium_page),podium_message_,FALSE,FALSE,0);
        gtk_box_pack_start(GTK_BOX(podium_page),podium_card,FALSE,FALSE,0);
        gtk_editable_set_editable(GTK_EDITABLE(podium_host_),FALSE);gtk_editable_set_editable(GTK_EDITABLE(podium_port_),FALSE);
        gtk_box_pack_start(GTK_BOX(device_box),label("USB ADMINISTRATION\nUNO Q / 管理","page-title"),FALSE,FALSE,8);gtk_box_pack_start(GTK_BOX(device_box),device,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(device_box),share_card,FALSE,FALSE,0);gtk_box_pack_start(GTK_BOX(device_box),task_card,FALSE,FALSE,0);
        gtk_stack_add_titled(GTK_STACK(settings_stack),can_box,"settings-can","基本設定 / CAN");gtk_stack_add_titled(GTK_STACK(settings_stack),device_box,"device","UNO Q");
        gtk_box_pack_start(GTK_BOX(page),tabs,FALSE,FALSE,0); add_page(page,"settings","06    Settings / CAN");
        add_page(podium_page,"podium","07    Podium 管理");
    }

    struct NcecResult{App* app;std::string text,csv;};
    static void decode_ncec(GtkButton*, gpointer data) { App* self=static_cast<App*>(data); GtkTextBuffer* b=gtk_text_view_get_buffer(GTK_TEXT_VIEW(self->ncec_input_)); GtkTextIter a,z; gtk_text_buffer_get_bounds(b,&a,&z); gchar* t=gtk_text_buffer_get_text(b,&a,&z,FALSE); json body={{"text",t}}; g_free(t);gtk_widget_set_sensitive(self->ncec_download_,FALSE);std::thread([self,body]{HttpResult r=request("/api/can/ncec/decode",body.dump().c_str());auto* out=new NcecResult{self};try{json j=json::parse(r.body),labels=j.value("labels",json::object());std::ostringstream view,csv;view<<j.value("rows",json::array()).size()<<"フレーム / カウンタ異常 "<<j.value("counter_anomalies",0)<<"件\n\n時刻ms    CAN ID    信号    値\n";csv<<"timestamp_ms,can_id,signal,value\r\n";for(const auto& frame:j.value("rows",json::array())){json values=frame.value("values",json::object());for(auto it=values.begin();it!=values.end();++it){std::string shown=text_value(labels,it.key().c_str(),it.key());view<<frame.value("timestamp_ms",0)<<"    "<<frame.value("can_id",0)<<"    "<<shown<<"    "<<it.value()<<"\n";csv<<frame.value("timestamp_ms",0)<<","<<frame.value("can_id",0)<<","<<it.key()<<","<<it.value()<<"\r\n";}}out->text=view.str();out->csv=csv.str();}catch(...){out->text="解析できませんでした";}g_idle_add([](gpointer p)->gboolean{std::unique_ptr<NcecResult>x(static_cast<NcecResult*>(p));x->app->ncec_csv_=x->csv;gtk_label_set_text(GTK_LABEL(x->app->ncec_result_),x->text.c_str());gtk_widget_set_sensitive(x->app->ncec_download_,!x->csv.empty());return G_SOURCE_REMOVE;},out);}).detach(); }
    static void download_ncec(GtkButton*,gpointer data){App* s=static_cast<App*>(data);if(s->ncec_csv_.empty())return;std::filesystem::create_directories("/home/arduino/Downloads");std::ofstream out("/home/arduino/Downloads/ncec-decoded.csv",std::ios::binary);out.write(s->ncec_csv_.data(),s->ncec_csv_.size());gtk_label_set_text(GTK_LABEL(s->settings_action_),"Downloads に ncec-decoded.csv を保存しました");}
    static void wifi_selected(GtkComboBox* box,gpointer data){App* s=static_cast<App*>(data);const char* id=gtk_combo_box_get_active_id(box);if(!id||!*id)return;gtk_entry_set_text(GTK_ENTRY(s->wifi_ssid_),id);std::string security=s->wifi_security_by_ssid_[id];const char* mode=security.find("WPA3")!=std::string::npos&&security.find("WPA2")==std::string::npos?"sae":(!security.empty()&&security!="--"?"wpa-psk":"open");gtk_combo_box_set_active_id(GTK_COMBO_BOX(s->wifi_security_),mode);}
    static void wifi_scan(GtkButton*,gpointer data){App* s=static_cast<App*>(data);gtk_label_set_text(GTK_LABEL(s->settings_action_),"周囲のWi-Fiを検索しています…");std::thread([s]{HttpResult r=request("/api/device/wifi/scan","{}");json* result=new json;try{if(r.code==200)*result=json::parse(r.body);}catch(...){}g_idle_add([](gpointer p)->gboolean{auto x=static_cast<std::pair<App*,json*>*>(p);App* s=x->first;gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(s->wifi_networks_));gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->wifi_networks_),"","ネットワークを選択");s->wifi_security_by_ssid_.clear();for(const auto& n:*x->second){std::string ssid=text_value(n,"ssid","");if(ssid.empty())continue;std::string security=text_value(n,"security","");std::ostringstream title;title<<ssid<<"（"<<n.value("signal",0)<<"% / "<<(security.empty()?"オープン":security)<<"）";gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(s->wifi_networks_),ssid.c_str(),title.str().c_str());s->wifi_security_by_ssid_[ssid]=security;}gtk_combo_box_set_active(GTK_COMBO_BOX(s->wifi_networks_),0);gtk_label_set_text(GTK_LABEL(s->settings_action_),x->second->empty()?"Wi-Fiが見つかりませんでした":"Wi-Fiを選び、パスワードを入力してください");delete x->second;delete x;return G_SOURCE_REMOVE;},new std::pair<App*,json*>(s,result));}).detach();}
    static void wifi_connect(GtkButton*, gpointer data) { App* self=static_cast<App*>(data); const char* sec=gtk_combo_box_get_active_id(GTK_COMBO_BOX(self->wifi_security_)); json j={{"ssid",gtk_entry_get_text(GTK_ENTRY(self->wifi_ssid_))},{"password",gtk_entry_get_text(GTK_ENTRY(self->wifi_password_))},{"security",sec?sec:"wpa-psk"}}; self->post_json("/api/device/wifi/connect",j,"Wi-Fiを接続して保存しました"); gtk_entry_set_text(GTK_ENTRY(self->wifi_password_),""); }
    static void wifi_disconnect(GtkButton*, gpointer data) { static_cast<App*>(data)->post_json("/api/device/wifi/disconnect",json::object(),"Wi-Fiを切断しました"); }
    static void sharing(GtkButton* b, gpointer data) { static_cast<App*>(data)->post_json("/api/device/sharing",{{"enabled",GPOINTER_TO_INT(g_object_get_data(G_OBJECT(b),"enabled"))!=0}},"公開設定を変更しました"); }
    static void copy_sharing(GtkButton*,gpointer data){App* s=static_cast<App*>(data);if(s->sharing_url_.empty())return;GtkClipboard* clipboard=gtk_clipboard_get(GDK_SELECTION_CLIPBOARD);gtk_clipboard_set_text(clipboard,s->sharing_url_.c_str(),-1);gtk_label_set_text(GTK_LABEL(s->settings_action_),"公開URLをコピーしました");}
    static void podium_stop(GtkButton*, gpointer data) { static_cast<App*>(data)->post_json("/api/podium",{{"enabled",false}},"LTE送信を停止しました"); }
    static void podium_toggle(GtkButton*,gpointer data){
        App* s=static_cast<App*>(data);if(s->podium_pending_)return;
        s->podium_pending_=true;gtk_widget_set_sensitive(s->podium_toggle_,FALSE);
        gtk_button_set_label(GTK_BUTTON(s->podium_toggle_),"切替を確認中…");
        json payload={{"enabled",!s->podium_on_}};
        std::string key=gtk_entry_get_text(GTK_ENTRY(s->podium_key_));if(!s->podium_on_&&!key.empty())payload["device_id"]=key;
        std::thread([s,payload]{auto r=request("/api/podium",payload.dump().c_str());
            struct Result{App* app;bool ok;std::string message;json state;};
            auto result=new Result{s,r.code>=200&&r.code<300&&r.error.empty(),"操作に失敗しました",json()};
            try{auto j=json::parse(r.body);if(result->ok){result->state=j;result->message=payload["enabled"].get<bool>()?"配信を有効にしました。接続状態を確認してください。":"配信を停止しました";}else result->message=text_value(j,"detail",result->message);}catch(...){}
            g_idle_add([](gpointer p)->gboolean{std::unique_ptr<Result>x(static_cast<Result*>(p));App* a=x->app;a->podium_pending_=false;if(x->ok){a->podium_on_=x->state.value("config",json::object()).value("enabled",false);gtk_entry_set_text(GTK_ENTRY(a->podium_key_),"");}a->update_podium_toggle();gtk_label_set_text(GTK_LABEL(a->podium_message_),x->message.c_str());return G_SOURCE_REMOVE;},result);
        }).detach();
    }
    void update_podium_toggle(){
        if(!podium_toggle_||podium_pending_)return;
        gtk_widget_set_sensitive(podium_toggle_,TRUE);gtk_button_set_label(GTK_BUTTON(podium_toggle_),podium_on_?"■ 配信停止":"● 配信開始");
        auto c=gtk_widget_get_style_context(podium_toggle_);if(podium_on_)gtk_style_context_add_class(c,"recording");else gtk_style_context_remove_class(c,"recording");
    }
    static void podium_start(GtkButton*, gpointer data) { App* s=static_cast<App*>(data);json j={{"enabled",true}};std::string key=gtk_entry_get_text(GTK_ENTRY(s->podium_key_));if(!key.empty())j["device_id"]=key;s->post_json("/api/podium",j,"配信開始を受け付けました。接続状態を確認してください。");gtk_entry_set_text(GTK_ENTRY(s->podium_key_),""); }
    static void podium_check_action(GtkButton*, gpointer data) { App* s=static_cast<App*>(data);gtk_label_set_text(GTK_LABEL(s->settings_action_),"LTEの電源と通信を点検しています…");std::thread([s]{HttpResult r=request("/api/podium/check","{}");std::string message;if(r.code==200)try{json j=json::parse(r.body);message=text_value(j,"model","LTE")+" / AT応答 "+(j.value("at",false)?"OK":"NG")+" / 電波OFF "+(j.value("rf_off",false)?"OK":"NG")+" / UART制御 "+(j.value("flow_control",false)?"OK":"NG")+" / TCP "+(j.value("tcp_commands",false)?"コマンド一覧で確認":"SIM接続後に確認")+" / 最後に電源OFF "+(j.value("power_off",false)?"OK":"未確認");}catch(...){message="LTE点検結果を読めませんでした";}else message="LTE点検に失敗しました";char* copy=g_strdup(message.c_str());g_idle_add([](gpointer p)->gboolean{auto x=static_cast<std::pair<App*,char*>*>(p);gtk_label_set_text(GTK_LABEL(x->first->settings_action_),x->second);g_free(x->second);delete x;return G_SOURCE_REMOVE;},new std::pair<App*,char*>(s,copy));}).detach(); }
    static void podium_save_config(GtkButton*, gpointer data) { App* s=static_cast<App*>(data); json j=s->podium_cache_.is_object()?s->podium_cache_:json::object(); j.erase("key_configured");j.erase("password_configured");j.erase("error"); j["apn"]=gtk_entry_get_text(GTK_ENTRY(s->podium_apn_));j["username"]=gtk_entry_get_text(GTK_ENTRY(s->podium_user_));j["password"]=gtk_entry_get_text(GTK_ENTRY(s->podium_password_));j["device_id"]=gtk_entry_get_text(GTK_ENTRY(s->podium_key_));j["host"]=gtk_entry_get_text(GTK_ENTRY(s->podium_host_));try{j["port"]=std::stoi(gtk_entry_get_text(GTK_ENTRY(s->podium_port_)));}catch(...){j["port"]=8080;}j["hardware_ready"]=gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(s->podium_hardware_));j["enabled"]=gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(s->podium_enabled_));j["channels"]=json::array();for(const auto& item:s->podium_channel_boxes_)if(gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(item.second)))j["channels"].push_back(item.first);s->post_json("/api/podium",j,"LTE設定を保存しました");gtk_entry_set_text(GTK_ENTRY(s->podium_password_),"");gtk_entry_set_text(GTK_ENTRY(s->podium_key_),""); }

    static void save_config(GtkButton*, gpointer data) {
        App* self=static_cast<App*>(data); if(!self->config_cache_.is_object()) return;
        self->config_cache_["device_name"]=gtk_entry_get_text(GTK_ENTRY(self->config_name_));
        const char* profile=gtk_combo_box_get_active_id(GTK_COMBO_BOX(self->config_profile_)); if(profile) self->config_cache_["profile"]=profile;
        const char* bitrate=gtk_combo_box_get_active_id(GTK_COMBO_BOX(self->config_bitrate_)); if(bitrate) self->config_cache_["can_bitrate"]=std::stoi(bitrate);
        self->config_cache_["auto_record"]=gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(self->config_auto_));
        self->config_cache_["signals"]=self->collect_signals();
        self->post_json("/api/config",self->config_cache_,"設定を保存しました");
    }

    static void load_ncec(GtkButton*, gpointer data) {
        App* self=static_cast<App*>(data); json base=self->config_cache_;gtk_label_set_text(GTK_LABEL(self->settings_action_),"NCEC定義を読み込んでいます…");
        std::thread([self,base]{ HttpResult p=request("/api/can/ncec");json* merged=new json(base);if(p.code==200)try{json preset=json::parse(p.body);for(const char* key:{"profile","can_bitrate","signals"})if(preset.contains(key))(*merged)[key]=preset[key];}catch(...){}g_idle_add([](gpointer value)->gboolean{auto x=static_cast<std::pair<App*,json*>*>(value);App* s=x->first;if(x->second->contains("signals")){s->config_cache_=*x->second;gtk_combo_box_set_active_id(GTK_COMBO_BOX(s->config_profile_),text_value(*x->second,"profile","ncec-2005-mt").c_str());std::string bitrate=std::to_string(x->second->value("can_bitrate",500000));gtk_combo_box_set_active_id(GTK_COMBO_BOX(s->config_bitrate_),bitrate.c_str());GList* rows=gtk_container_get_children(GTK_CONTAINER(s->signal_list_));for(GList* it=rows;it;it=it->next)gtk_widget_destroy(GTK_WIDGET(it->data));g_list_free(rows);json signals=x->second->value("signals",json::array());for(const auto& signal:signals)s->add_signal_row(signal);s->signals_snapshot_=signals.dump();gtk_label_set_text(GTK_LABEL(s->settings_), ("CAN信号定義  "+std::to_string(signals.size())+"件").c_str());gtk_label_set_text(GTK_LABEL(s->settings_action_),"NCEC定義を読み込みました。保存すると確定します。");}else gtk_label_set_text(GTK_LABEL(s->settings_action_),"NCEC定義を読み込めませんでした");delete x->second;delete x;return G_SOURCE_REMOVE;},new std::pair<App*,json*>(self,merged));}).detach();
    }

    void post_json(const std::string& path, const json& payload, const std::string& success) {
        std::thread([this,path,payload,success]{ std::string body=payload.dump(); HttpResult r=request(path,body.c_str()); std::string msg=(r.code>=200&&r.code<300)?success:"操作に失敗しました"; char* copy=g_strdup(msg.c_str());
            g_idle_add([](gpointer p)->gboolean{auto x=static_cast<std::pair<App*,char*>*>(p); if(x->first->podium_message_)gtk_label_set_text(GTK_LABEL(x->first->podium_message_),x->second); if(x->first->action_)gtk_label_set_text(GTK_LABEL(x->first->action_),x->second); if(x->first->settings_action_)gtk_label_set_text(GTK_LABEL(x->first->settings_action_),x->second); g_free(x->second);delete x;return G_SOURCE_REMOVE;},new std::pair<App*,char*>(this,copy)); }).detach();
    }

    static void record_start(GtkButton*, gpointer self) { static_cast<App*>(self)->record_request(true); }
    static void record_stop(GtkButton*, gpointer self) { static_cast<App*>(self)->record_request(false); }
    static void record_toggle(GtkButton*, gpointer self) { App* s=static_cast<App*>(self);s->record_request(!s->recording_active_); }
    void record_request(bool start) {
        if(record_pending_)return;
        record_pending_=true;gtk_widget_set_sensitive(record_toggle_,FALSE);
        gtk_button_set_label(GTK_BUTTON(record_toggle_),start?"開始を確認中…":"SD保存を確認中…");
        gtk_label_set_text(GTK_LABEL(record_message_),start?"SD記録の開始を待っています":"SDに保存しています。電源を切らないでください。");
        std::thread([this,start]{HttpResult r=request(start?"/api/log/start":"/api/log/stop","{}");
            bool ok=r.error.empty()&&r.code>=200&&r.code<300;std::string message=ok?(start?"記録中 · 再度押すと停止・保存します":"停止しました · SDへの保存完了"):"操作を確認できません。現在の記録状態を確認してください。";
            if(!ok)try{json j=json::parse(r.body);if(j.contains("detail")&&j["detail"].is_string())message=j["detail"].get<std::string>();}catch(...){}
            struct Result{App* app;std::string message;};
            g_idle_add([](gpointer p)->gboolean{std::unique_ptr<Result>x(static_cast<Result*>(p));x->app->record_pending_=false;gtk_label_set_text(GTK_LABEL(x->app->record_message_),x->message.c_str());x->app->set_action_text(x->message);return G_SOURCE_REMOVE;},new Result{this,message});
        }).detach();
    }
    static void refresh_logs(GtkButton*,gpointer self){App* s=static_cast<App*>(self);s->logs_snapshot_.clear();s->sd_logs_snapshot_.clear();s->set_action_text("一覧を更新しています…");}

    void post_action(const char* path, const char* message) {
        gtk_label_set_text(GTK_LABEL(action_), message);
        std::thread([this, path=std::string(path)] {
            HttpResult r = request(path, "{}");
            std::string msg = (r.error.empty() && r.code >= 200 && r.code < 300) ? "操作を受け付けました" : "操作に失敗しました: " + (r.error.empty() ? std::to_string(r.code) : r.error);
            char* copy = g_strdup(msg.c_str());
            g_idle_add([](gpointer p)->gboolean { auto pair=static_cast<std::pair<App*,char*>*>(p); if (pair->first->running_) gtk_label_set_text(GTK_LABEL(pair->first->action_), pair->second); g_free(pair->second); delete pair; return G_SOURCE_REMOVE; }, new std::pair<App*,char*>(this, copy));
        }).detach();
    }

    struct Update { App* app; json telemetry, status, logs, sdlogs, config, system, wifi, sharing, podium; std::string error; };

    void metadata_loop() {
        while(running_) {
            for(auto item:{std::pair<const char*,const char*>("logs","/api/logs"),{"sdlogs","/api/sd/logs"},{"config","/api/config"},{"system","/api/device/system"},{"wifi","/api/device/wifi"},{"sharing","/api/device/sharing"},{"podium","/api/podium"}}) {
                if(!running_)return;
                HttpResult r=request(item.second);
                if(r.code==200&&r.error.empty())try{
                    json value=json::parse(r.body);
                    std::lock_guard<std::mutex> lock(metadata_mutex_);pending_metadata_[item.first]=std::move(value);
                }catch(...){}
            }
            for(int i=0;i<40&&running_;++i)std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
    void map_tile_loop() {
        int previous_x=-1,previous_y=-1,previous_z=-1;
        auto retry=std::chrono::steady_clock::now();
        while(running_) {
            if(tile_ready_) {
                double lon=tile_lon_.load(),lat=tile_lat_.load();int zoom=tile_zoom_.load();
                auto p=map_project(lon,lat,zoom);int x=std::floor(p.first),y=std::floor(p.second);
                if(x!=previous_x||y!=previous_y||zoom!=previous_z||std::chrono::steady_clock::now()>=retry) {
                    previous_x=x;previous_y=y;previous_z=zoom;
                    retry=std::chrono::steady_clock::now()+std::chrono::seconds(10);
                    g_idle_add([](gpointer data)->gboolean{App* s=static_cast<App*>(data);if(s->running_&&s->map_area_)gtk_widget_queue_draw(s->map_area_);return G_SOURCE_REMOVE;},this);
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
    void worker_loop() {
        CURL* ws=nullptr;
        std::string ws_text;
        auto connect_ws=[&]()->bool {
            if(ws) curl_easy_cleanup(ws);
            ws=curl_easy_init(); if(!ws) return false;
            curl_easy_setopt(ws,CURLOPT_URL,"ws://127.0.0.1:8080/ws");
            curl_easy_setopt(ws,CURLOPT_CONNECT_ONLY,2L);
            curl_easy_setopt(ws,CURLOPT_CONNECTTIMEOUT_MS,500L);
            curl_easy_setopt(ws,CURLOPT_NOSIGNAL,1L);
            CURLcode code=curl_easy_perform(ws);
            if(code!=CURLE_OK){curl_easy_cleanup(ws);ws=nullptr;return false;}
            ws_text.clear(); return true;
        };
        connect_ws();
        while (running_) {
            auto* update = new Update{this};
            bool got=false;
            if(!ws) connect_ws();
            if(ws) {
                char buffer[65536]; size_t received=0; const struct curl_ws_frame* meta=nullptr;
                CURLcode code=curl_ws_recv(ws,buffer,sizeof(buffer),&received,&meta);
                if(code==CURLE_OK) {
                    if(received) ws_text.append(buffer,received);
                    if(meta && meta->bytesleft==0 && !(meta->flags&CURLWS_CONT)) {
                        try { json frame=json::parse(ws_text); update->telemetry=frame; update->status=frame.value("status",json::object()); got=true; }
                        catch(...) { update->error="データ形式エラー"; }
                        ws_text.clear();
                    }
                } else if(code!=CURLE_AGAIN) { curl_easy_cleanup(ws); ws=nullptr; update->error="ライブ表示を再接続中"; }
            }
            if(!got && update->error.empty()) { delete update; std::this_thread::sleep_for(std::chrono::milliseconds(10)); continue; }
            {
                std::lock_guard<std::mutex> lock(metadata_mutex_);
                for(auto item:{std::pair<const char*,json*>("logs",&update->logs),{"sdlogs",&update->sdlogs},{"config",&update->config},{"system",&update->system},{"wifi",&update->wifi},{"sharing",&update->sharing},{"podium",&update->podium}})
                    if(pending_metadata_.contains(item.first))*item.second=std::move(pending_metadata_[item.first]);
                pending_metadata_.clear();
            }
            g_idle_add(apply_update, update);
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        if(ws) curl_easy_cleanup(ws);
    }

    static gboolean apply_update(gpointer data) {
        std::unique_ptr<Update> u(static_cast<Update*>(data));
        if (!u->app->running_) return G_SOURCE_REMOVE;
        try {
            u->app->render(*u);
        } catch (const std::exception& error) {
            // API fields can briefly be null while LoggerV2 is starting.  Keep the
            // last good screen instead of letting systemd restart the whole UI.
            gtk_label_set_text(GTK_LABEL(u->app->rec_),
                (std::string("EcoLogger V2    データ更新待ち: ") + error.what()).c_str());
        }
        return G_SOURCE_REMOVE;
    }

    void set(const char* key, const std::string& text) {
        auto it=values_.find(key); if(it!=values_.end()) for(GtkWidget* w:it->second) gtk_label_set_text(GTK_LABEL(w), text.c_str());
    }

    void render(const Update& u) {
        if (!u.error.empty()) {
            gtk_label_set_text(GTK_LABEL(rec_), ("EcoLogger V2    未接続: " + u.error).c_str());
            set("OilTemp", "通信途絶");
            auto oil=sensor_values_.find("OilTemp");
            if(oil!=sensor_values_.end())gtk_label_set_text(GTK_LABEL(oil->second),"通信途絶");
            return;
        }
        const json telemetry = u.telemetry.is_object() ? u.telemetry : json::object();
        const json sample = telemetry.contains("sample") && telemetry["sample"].is_object()
            ? telemetry["sample"] : json::object();
        json v = sample.contains("values") && sample["values"].is_object()
            ? sample["values"] : json::object();
        json decoded=sample.value("can_signals",json::object());
        for(auto it=decoded.begin();it!=decoded.end();++it)v[it.key()]=it.value();
        json states=sample.value("can_states",json::object());
        auto signal_text=[&](const std::string& name,int digits,const std::string& unit){
            if(states.contains(name)){
                if(!u.status.value("connected",false))return std::string("通信途絶");
                if(states[name].value("code",4)!=0)return text_value(states[name],"label","通信途絶");
            }
            return number(v,name.c_str(),digits,unit.c_str());
        };

        if(sensor_grid_&&!u.podium.is_null())for(const auto& ch:u.podium.value("channels",json::array())){
            std::string key=text_value(ch,"name","");if(key.empty()||sensor_values_.count(key))continue;
            int n=static_cast<int>(sensor_values_.size());GtkWidget* title=wrapped_label(text_value(ch,"label",key).c_str(),"body"),*value=label("—","body");
            g_object_set_data_full(G_OBJECT(value),"unit",g_strdup(text_value(ch,"unit","").c_str()),g_free);
            gtk_grid_attach(GTK_GRID(sensor_grid_),title,(n%2)*2,n/2,1,1);gtk_grid_attach(GTK_GRID(sensor_grid_),value,(n%2)*2+1,n/2,1,1);sensor_values_[key]=value;
        }
        for(auto& item:sensor_values_){auto unit=static_cast<const char*>(g_object_get_data(G_OBJECT(item.second),"unit"));gtk_label_set_text(GTK_LABEL(item.second),signal_text(item.first,(item.first=="Lat"||item.first=="Lon")?6:2,unit?unit:"").c_str());}
        if(sensor_grid_)gtk_widget_show_all(sensor_grid_);
        set("Speed", number(v,"Speed",0,"km/h")); set("RPM", number(v,"RPM",0,"rpm"));
        set("Throttle", number(v,"Throttle",1,"%")); set("WaterTemp", number(v,"WaterTemp",1,"°C"));
        set("dash.Throttle", "スロットル " + number(v,"Throttle",1,"%"));
        if(throttle_bar_){double maximum=config_cache_.is_object()&&config_cache_.value("profile",std::string("no-can"))=="ncec-2005-mt"?8000.0:6000.0;gtk_progress_bar_set_fraction(GTK_PROGRESS_BAR(throttle_bar_),v.contains("RPM")&&v["RPM"].is_number()?std::max(0.0,std::min(1.0,v["RPM"].get<double>()/maximum)):0.0);}
        if(dash_seq_){std::string seq=sample.contains("seq")&&sample["seq"].is_number_integer()?std::to_string(sample["seq"].get<long long>()):"--";gtk_label_set_text(GTK_LABEL(dash_seq_),("SPEED                                      SEQ "+seq).c_str());}
        set("OilTemp", signal_text("OilTemp",1,"°C")); set("BatteryVolt", number(v,"BatteryVolt",2,"V"));
        set("GPSSpeed", number(v,"GPSSpeed",1,"km/h")); set("GPSFix", integer(v.value("GPSFix",json())));
        set("GPSSats", integer(v.value("GPSSats",json()))); set("Distance", number(v,"Distance",2,"km"));
        set("LongAccel", number(v,"LongAccel",2,"G")); set("LatAccel", number(v,"LatAccel",2,"G"));
        const double now_s=std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
        if(v.contains("GPSSpeed")&&v["GPSSpeed"].is_number()) {
            trend_.push_back({now_s,v["GPSSpeed"].get<double>()});
            while(!trend_.empty()&&now_s-trend_.front().first>60.0) trend_.erase(trend_.begin());
            if(trend_area_) gtk_widget_queue_draw(trend_area_);
        }
        if(v.contains("Lon")&&v["Lon"].is_number()&&v.contains("Lat")&&v["Lat"].is_number()) {
            const double lon=v["Lon"].get<double>(),lat=v["Lat"].get<double>();
            if(std::isfinite(lon)&&std::isfinite(lat)&&(std::abs(lon)>0.000001||std::abs(lat)>0.000001)) {
                current_lon_=lon;current_lat_=lat;if(!map_initialized_){map_center_lon_=lon;map_center_lat_=lat;map_initialized_=true;}if(map_follow_){map_center_lon_=lon;map_center_lat_=lat;}
                if(track_.empty()||std::get<0>(track_.back())!=lon||std::get<1>(track_.back())!=lat) track_.push_back({lon,lat,now_s});
                while(!track_.empty()&&now_s-std::get<2>(track_.front())>300.0) track_.erase(track_.begin());
                map_redraw();
            }
        }
        if(v.contains("LatAccel")&&v["LatAccel"].is_number()) g_lat_=v["LatAccel"].get<double>(); if(v.contains("LongAccel")&&v["LongAccel"].is_number()) g_long_=v["LongAccel"].get<double>(); if(g_area_) gtk_widget_queue_draw(g_area_);
        set("AccelX", number(v,"AccelX",2,"m/s²")); set("AccelY", number(v,"AccelY",2,"m/s²")); set("AccelZ", number(v,"AccelZ",2,"m/s²"));
        set("GyroX", number(v,"GyroX",1,"°/s")); set("GyroY", number(v,"GyroY",1,"°/s")); set("GyroZ", number(v,"GyroZ",1,"°/s"));
        set("Roll", number(v,"Roll",1,"°")); set("Pitch", number(v,"Pitch",1,"°"));
        for(const char* key:{"AccelX","AccelY","AccelZ","LongAccel","LatAccel","VertAccel","GyroX","GyroY","GyroZ","Roll","Pitch"}) set((std::string("imu.")+key).c_str(),number(v,key,2,""));
        set("gnss.Lat",number(v,"Lat",6,"°")); set("gnss.Lon",number(v,"Lon",6,"°"));
        set("gnss.GPSSpeed",number(v,"GPSSpeed",1,"km/h")); set("gnss.Altitude",number(v,"Altitude",1,"m"));
        set("gnss.Yaw",number(v,"Yaw",1,"°")); set("gnss.GPSFix",integer(v.value("GPSFix",json())));
        set("gnss.GPSSats",integer(v.value("GPSSats",json()))); set("gnss.GNSSHz",number(v,"GNSSHz",1,"Hz"));
        set("IMUTemp", number(sample,"imu_temperature_C",1,"°C"));
        json cal=sample.contains("imu_calibration")&&sample["imu_calibration"].is_object()?sample["imu_calibration"]:json::object();
        set("CalSystem", integer(cal.value("system",json())," / 3")); set("CalGyro", integer(cal.value("gyro",json())," / 3")); set("CalAccel", integer(cal.value("accel",json())," / 3"));
        if(calibration_info_){std::ostringstream ci;ci<<"IMU校正（0〜3）：system "<<integer(cal.value("system",json()))<<" / gyro "<<integer(cal.value("gyro",json()))<<" / accel "<<integer(cal.value("accel",json()))<<" / mag "<<integer(cal.value("mag",json()));gtk_label_set_text(GTK_LABEL(calibration_info_),ci.str().c_str());}
        if(can_live_&&config_cache_.is_object()){std::ostringstream live;json decoded=sample.value("can_signals",json::object());for(const auto& signal:config_cache_.value("signals",json::array())){std::string name=text_value(signal,"name","");live<<name<<"  ";live<<signal_text(name,2,text_value(signal,"unit",""))<<"    ";}gtk_label_set_text(GTK_LABEL(can_live_),live.str().empty()?"CANライブ値：信号定義なし":live.str().c_str());}

        const json st = u.status.is_object() ? u.status : json::object();
        double hz=st.value("receive_hz",0.0);
        bool connected=st.value("connected",false);
        std::ostringstream head; head << "EcoLogger V2    " << (connected?"● MCU受信中":"MCU通信待ち") << "    " << std::fixed << std::setprecision(1) << hz << " Hz";
        gtk_label_set_text(GTK_LABEL(rec_),head.str().c_str());
        json logging=st.contains("logging")&&st["logging"].is_object()?st["logging"]:json::object();
        json hardware=st.contains("hardware")&&st["hardware"].is_object()?st["hardware"]:json::object();
        bool sd_active=hardware.value("sd_logging",0) != 0;
        bool active=logging.value("active",false) || sd_active;
        recording_active_=active;
        if(record_toggle_&&!record_pending_){gtk_widget_set_sensitive(record_toggle_,connected);gtk_button_set_label(GTK_BUTTON(record_toggle_),active?"■ 記録停止":"● 記録開始");GtkStyleContext* c=gtk_widget_get_style_context(record_toggle_);if(active)gtk_style_context_add_class(c,"recording");else gtk_style_context_remove_class(c,"recording");}
        std::string filename=text_value(logging,"name","");
        if (filename.empty() && hardware.contains("sd_file")) {
            std::ostringstream f; f << "EL" << std::setw(6) << std::setfill('0') << hardware.value("sd_file",0) << ".BIN"; filename=f.str();
        }
        if(dash_rec_) {
            long long seconds=static_cast<long long>(logging.value("elapsed_s",0.0));
            std::ostringstream rs; rs << (logging.value("active",false)?"● REC":"○ STANDBY") << "     " << std::setw(2) << std::setfill('0') << seconds/3600 << ":" << std::setw(2) << (seconds/60)%60 << ":" << std::setw(2) << seconds%60 << "     " << logging.value("rows",0LL) << " samples";
            gtk_label_set_text(GTK_LABEL(dash_rec_),rs.str().c_str());
        }

        std::ostringstream d;
        d << "LoggerV2: " << (connected?"正常":"未接続") << "    受信: " << std::fixed << std::setprecision(1) << hz << " Hz\n\n";
        json sensors=st.contains("sensors")&&st["sensors"].is_object()?st["sensors"]:json::object();
        for (const auto& item : {std::pair<const char*,const char*>("can","CAN"),{"imu","IMU"},{"gnss","GNSS"}}) d << item.second << ": " << text_value(sensors,item.first) << "\n";
        d << "\nSD: " << (hardware.value("sd_ready",0)?"使用可能":"未準備") << "    記録: " << (sd_active?"実行中":"停止")
          << "\nファイル: " << filename << "    書込量: " << human_bytes(hardware.value("sd_bytes",0LL))
          << "\nエラー: " << hardware.value("sd_errors",0) << "    取こぼし: " << hardware.value("sd_queue_dropped",0) << "\n";
        json podium=st.contains("podium")&&st["podium"].is_object()?st["podium"]:json::object();
        if(podium_live_){std::string live=text_value(podium,"message","配信停止中")+" · 送信 "+std::to_string(podium.value("frames",0))+" 件";gtk_label_set_text(GTK_LABEL(podium_live_),live.c_str());}
        d << "\nLTE: " << (hardware.value("lte_power",0)?"ON":"OFF") << "    Podium: " << (podium.value("enabled",false)?"ON":"OFF");
        gtk_label_set_text(GTK_LABEL(diag_), d.str().c_str());

        if (!u.logs.is_null()) {
            json list=u.logs.is_array()?u.logs:u.logs.value("logs",json::array());
            std::string snapshot=list.dump();if(snapshot!=logs_snapshot_&&logs_box_){GList* rows=gtk_container_get_children(GTK_CONTAINER(logs_box_));for(GList* it=rows;it;it=it->next)gtk_widget_destroy(GTK_WIDGET(it->data));g_list_free(rows);logs_=nullptr;GtkWidget* head=label(("eMMCログ  "+std::to_string(list.size())+"件").c_str(),"section");gtk_box_pack_start(GTK_BOX(logs_box_),head,FALSE,FALSE,0);for(const auto& entry:list){std::string name=entry.is_string()?entry.get<std::string>():text_value(entry,"name",text_value(entry,"filename","ログ"));bool active=entry.is_object()&&entry.value("active",false);GtkWidget* row=gtk_box_new(GTK_ORIENTATION_VERTICAL,1);std::string caption=name+"    "+(entry.is_object()?human_bytes(entry.value("size",0LL)):"")+(active?"    記録中":"    保存済み");gtk_box_pack_start(GTK_BOX(row),label(caption.c_str(),"body"),FALSE,FALSE,0);if(!active){GtkWidget* actions=gtk_flow_box_new();gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(actions),GTK_SELECTION_NONE);gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(actions),6);for(auto item:{std::pair<const char*,const char*>("CSV","download"),{"メタデータ","meta"},{"解析","solve"},{"CAN生データ","can"},{"SDへコピー","sd"},{"削除","delete"}})gtk_flow_box_insert(GTK_FLOW_BOX(actions),make_log_button(item.first,item.second,name),-1);gtk_box_pack_start(GTK_BOX(row),actions,FALSE,FALSE,0);}gtk_box_pack_start(GTK_BOX(logs_box_),row,FALSE,FALSE,0);}gtk_widget_show_all(logs_box_);logs_snapshot_=snapshot;}
        }
        if(storage_free_) gtk_label_set_text(GTK_LABEL(storage_free_),active?"SD記録中 · Dashboardで停止すると一覧を自動更新します":"保存先：SDカード · 本体の直近3件はバックアップとして自動管理");
        if(sd_logs_box_)gtk_widget_set_sensitive(sd_logs_box_,!active);
        if(!u.sdlogs.is_null()&&sd_logs_box_){
            std::string snapshot=u.sdlogs.dump();if(snapshot!=sd_logs_snapshot_){
                GList* rows=gtk_container_get_children(GTK_CONTAINER(sd_logs_box_));for(GList* it=rows;it;it=it->next)gtk_widget_destroy(GTK_WIDGET(it->data));g_list_free(rows);sd_logs_=nullptr;
                if(u.sdlogs.empty())gtk_box_pack_start(GTK_BOX(sd_logs_box_),label("SDに保存済みの記録はありません","body"),FALSE,FALSE,0);
                for(const auto& f:u.sdlogs){
                    int index=f.value("index",0);std::ostringstream name;name<<"EL"<<std::setw(6)<<std::setfill('0')<<index<<".BIN  —  "<<human_bytes(f.value("size",0LL));
                    GtkWidget* row=gtk_box_new(GTK_ORIENTATION_HORIZONTAL,4);gtk_box_pack_start(GTK_BOX(row),label(name.str().c_str(),"body"),TRUE,TRUE,0);
                    if(f.value("active",false))gtk_box_pack_start(GTK_BOX(row),label("記録中","metric-name"),FALSE,FALSE,0);
                    else{for(bool solve:{true,false}){GtkWidget* b=gtk_button_new_with_label(solve?"解析":"ダウンロード");g_object_set_data(G_OBJECT(b),"index",GINT_TO_POINTER(index));g_signal_connect(b,"clicked",solve?G_CALLBACK(sd_solve):G_CALLBACK(sd_download),this);gtk_box_pack_start(GTK_BOX(row),b,FALSE,FALSE,0);}}
                    gtk_box_pack_start(GTK_BOX(sd_logs_box_),row,FALSE,FALSE,0);
                }
                gtk_widget_show_all(sd_logs_box_);sd_logs_snapshot_=snapshot;
            }
        }
        if (!u.config.is_null()) {
            if(config_cache_.is_null()) {
                gtk_entry_set_text(GTK_ENTRY(config_name_),text_value(u.config,"device_name","").c_str());
                gtk_combo_box_set_active_id(GTK_COMBO_BOX(config_profile_),text_value(u.config,"profile","no-can").c_str());
                std::string bitrate=std::to_string(u.config.value("can_bitrate",500000)); gtk_combo_box_set_active_id(GTK_COMBO_BOX(config_bitrate_),bitrate.c_str());
                gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(config_auto_),u.config.value("auto_record",false));
            }
            config_cache_=u.config;
            json signals=u.config.value("signals",json::array()); std::string snapshot=signals.dump();
            if(snapshot!=signals_snapshot_&&signal_list_) { GList* rows=gtk_container_get_children(GTK_CONTAINER(signal_list_));for(GList* it=rows;it;it=it->next)gtk_widget_destroy(GTK_WIDGET(it->data));g_list_free(rows);for(const auto& signal:signals)add_signal_row(signal);signals_snapshot_=snapshot; }
            gtk_label_set_text(GTK_LABEL(settings_),("CAN信号定義  "+std::to_string(signals.size())+"件").c_str());
        }
        if(!u.podium.is_null()) {
            json pc=u.podium.value("config",json::object()); podium_cache_=pc;
            if(!podium_pending_){podium_on_=pc.value("enabled",false);update_podium_toggle();}
            if(podium_apn_ && !gtk_widget_has_focus(podium_apn_)) gtk_entry_set_text(GTK_ENTRY(podium_apn_),text_value(pc,"apn","").c_str());
            if(podium_user_ && !gtk_widget_has_focus(podium_user_)) gtk_entry_set_text(GTK_ENTRY(podium_user_),text_value(pc,"username","").c_str());
            if(podium_host_ && !gtk_widget_has_focus(podium_host_)) gtk_entry_set_text(GTK_ENTRY(podium_host_),text_value(pc,"host","telemetry.podium.live").c_str());
            if(podium_port_ && !gtk_widget_has_focus(podium_port_)) gtk_entry_set_text(GTK_ENTRY(podium_port_),std::to_string(pc.value("port",8080)).c_str());
            if(podium_password_) gtk_entry_set_placeholder_text(GTK_ENTRY(podium_password_),pc.value("password_configured",false)?"保存済み / 空欄で変更しない":"APNパスワード（必要な場合）");
            if(podium_key_) gtk_entry_set_placeholder_text(GTK_ENTRY(podium_key_),pc.value("key_configured",false)?"保存済み / 空欄で変更しない":"Podiumの送信キー");
            if(podium_channel_boxes_.empty()&&podium_channels_box_) for(const auto& ch:u.podium.value("channels",json::array())){std::string name=text_value(ch,"name","");if(name.empty())continue;std::string title=text_value(ch,"label",name)+" ("+name+")";GtkWidget* box=gtk_check_button_new_with_label(title.c_str());podium_channel_boxes_[name]=box;gtk_flow_box_insert(GTK_FLOW_BOX(podium_channels_box_),box,-1);} 
            for(auto& item:podium_channel_boxes_){bool selected=false;for(const auto& ch:pc.value("channels",json::array()))if(ch.is_string()&&ch.get<std::string>()==item.first){selected=true;break;}gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(item.second),selected);}if(podium_channels_box_)gtk_widget_show_all(podium_channels_box_);
            if(podium_hardware_) gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(podium_hardware_),pc.value("hardware_ready",false)); if(podium_enabled_) gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(podium_enabled_),pc.value("enabled",false));
        }
        if(device_status_) {
            std::ostringstream ds; if(!u.wifi.is_null()) { ds << (u.wifi.value("addresses",json::array()).empty()?"Wi-Fi未接続":"Wi-Fi接続中: "+text_value(u.wifi,"connection")); for(const auto& a:u.wifi.value("addresses",json::array())) if(a.is_string()) ds << "  " << a.get<std::string>(); }
            json ps=!u.podium.is_null()?u.podium.value("status",json::object()):st.value("podium",json::object()); ds << "\nLTE / Podium: " << text_value(ps,"message","送信OFF") << "  送信 " << ps.value("frames",0) << "件 / 再接続 " << ps.value("reconnects",0) << "回"; gtk_label_set_text(GTK_LABEL(device_status_),ds.str().c_str());
        }
        if(u.sharing.is_object()&&sharing_status_){sharing_url_=text_value(u.sharing,"url","");std::string state=!u.sharing.value("enabled",false)?"公開停止":sharing_url_.empty()?"公開URLを準備中…":"公開中: "+sharing_url_;gtk_label_set_text(GTK_LABEL(sharing_status_),state.c_str());if(sharing_copy_)gtk_widget_set_sensitive(sharing_copy_,!sharing_url_.empty());}
        if(!u.system.is_null() && system_info_) {
            std::ostringstream si; double total=u.system.value("memory_total",0.0),used=u.system.value("memory_used",0.0); si << "CPU " << std::fixed << std::setprecision(1) << u.system.value("cpu_percent",0.0) << "%    メモリ " << (total?used/total*100:0) << "%    温度 " << u.system.value("temperature_c",0.0) << "°C    空きストレージ " << u.system.value("disk_free",0.0)/1073741824.0 << " GiB\n";
            si << u.system.value("cpu_cores",0) << " コア / メモリ " << human_bytes(static_cast<long long>(used)) << " / " << human_bytes(static_cast<long long>(total)) << " / 稼働 " << u.system.value("uptime_s",0) << "秒 / " << u.system.value("process_count",0) << " プロセス\n\nPID    プロセス                         CPU %    メモリ MiB\n";
            for(const auto& p:u.system.value("processes",json::array())) si << std::setw(6) << p.value("pid",0) << "  " << std::setw(30) << std::left << text_value(p,"name") << std::right << std::setw(7) << p.value("cpu_percent",0.0) << std::setw(12) << p.value("rss_bytes",0.0)/1048576.0 << "\n";
            gtk_label_set_text(GTK_LABEL(system_info_),si.str().c_str());
        }
    }
};
}

int main(int argc, char** argv) {
    curl_global_init(CURL_GLOBAL_DEFAULT);
    if (argc > 1 && std::string(argv[1]) == "--self-test") {
        auto r=request("/api/telemetry");
        try { auto j=json::parse(r.body); std::cout << "ok sample=" << j.contains("sample") << " http=" << r.code << "\n"; }
        catch (...) { std::cerr << "failed " << r.error << " http=" << r.code << "\n"; return 1; }
        return r.code==200?0:1;
    }
    gtk_init(&argc,&argv);
    App app; app.show(); gtk_main();
    curl_global_cleanup();
    return 0;
}
