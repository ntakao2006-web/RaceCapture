#include "driver/uart.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "esp_log.h"
#include "freertos/stream_buffer.h"
#include "state.h"
#include "tinyusb.h"
#include "tusb.h"
#include "tusb_cdc_acm.h"
#include <ArduinoJson.h>
#include <string>
#include <dirent.h>
#include <sys/stat.h>

namespace logger {
static constexpr size_t LINE_BYTES = 65536;
static StreamBufferHandle_t usb_rx;
static SemaphoreHandle_t protocol_mutex;
static SemaphoreHandle_t uart_output_mutex;
static vprintf_like_t original_log = vprintf;
static int atomicLog(const char *format, va_list args) {
    Guard lock(uart_output_mutex);
    return original_log(format, args);
}
struct Transport {
    bool uart = false, stream = false, discard = false;
    size_t used = 0;
    uint32_t schema = 0;
    uint64_t next_sample = 0;
    char *input = nullptr, *output = nullptr, *script = nullptr;
    Channel *metadata = nullptr;
    unsigned script_page = 0;
    size_t script_used = 0;
    bool script_active = false;
};
static void metadata(JsonObject o, const Channel &c) {
    o["nm"] = c.name;
    o["ut"] = c.unit;
    o["min"] = c.min;
    o["max"] = c.max;
    o["prec"] = c.precision;
    o["sr"] = c.rate;
}
static void metadataArray(JsonArray a) {
    Guard lock(state_mutex);
    for (size_t i = 0; i < channel_count; ++i)
        metadata(a.add<JsonObject>(), channels[i]);
}
static bool send(JsonDocument &doc, Transport &t) {
    size_t n = measureJson(doc);
    if (n > LINE_BYTES - 3 || doc.overflowed()) {
        ++stats.usb_drop;
        return false;
    }
    n = serializeJson(doc, t.output, LINE_BYTES - 3);
    t.output[n++] = '\r';
    t.output[n++] = '\n';
    if (t.uart) {
        Guard lock(uart_output_mutex);
        return uart_write_bytes(UART_NUM_0, t.output, n) == int(n);
    }
    if (!tud_cdc_connected())
        return false;
    uint64_t deadline = nowUs() + 250000;
    size_t sent = 0;
    while (sent < n && nowUs() < deadline && tud_cdc_connected()) {
        sent += tinyusb_cdcacm_write_queue(TINYUSB_CDC_ACM_0,
                                           reinterpret_cast<uint8_t *>(t.output) + sent, n - sent);
        tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, pdMS_TO_TICKS(10));
        if (sent < n)
            vTaskDelay(pdMS_TO_TICKS(1));
    }
    if (sent != n) {
        ++stats.usb_drop;
        return false;
    }
    return true;
}
static void result(JsonDocument &out, const char *cmd, bool ok, const char *error = nullptr) {
    auto r = out[cmd].to<JsonObject>();
    r["rc"] = ok ? 1 : -1;
    if (error)
        r["error"] = error;
}
static void sample(JsonDocument &out, Transport &t, bool meta) {
    Snapshot s = takeSnapshot(t.metadata);
    auto o = out["s"].to<JsonObject>();
    o["t"] = uint32_t(s.us / 1000);
    o["monotonic_us"] = s.us;
    o["utc_us"] = s.utc_us;
    o["schema"] = s.revision;
    auto a = o["d"].to<JsonArray>();
    for (size_t i = 0; i < s.count; ++i)
        if (s.has(i)) {
            // ArduinoJson's default float output has limited significant digits;
            // preserve UTC microseconds and exactly match each SD column's precision.
            char number[96];
            int n =
                snprintf(number, sizeof(number), "%.*f", int(t.metadata[i].precision), s.values[i]);
            if (n < 0 || size_t(n) >= sizeof(number))
                snprintf(number, sizeof(number), "%.17g", s.values[i]);
            a.add(serialized(std::string(number)));
        }
    for (size_t i = 0; i < (s.count + 31) / 32; ++i)
        a.add(s.valid[i]);
    if (meta || s.revision != t.schema) {
        auto a = o["meta"].to<JsonArray>();
        for (size_t i = 0; i < s.count; ++i)
            metadata(a.add<JsonObject>(), t.metadata[i]);
        t.schema = s.revision;
    }
}
static void trackConfig(JsonObject o) {
    Guard lock(state_mutex);
    const auto &c = config.track;
    o["rad"] = c.radius_m / M_PER_DEG;
    auto tr = o["track"].to<JsonObject>();
    tr["id"] = c.id;
    tr["type"] = 0;
    auto sf = tr["sf"].to<JsonArray>();
    sf.add(c.lat);
    sf.add(c.lon);
    tr["sec"].to<JsonArray>();
    o["minLapSeconds"] = c.min_lap_s;
}
static void loggerConfig(JsonObject o) {
    Guard lock(state_mutex);
    o["ncProfile"] = config.nc_profile;
    o["hubBroadcast"] = config.hub_broadcast;
    o["broadcastBase"] = config.broadcast_base;
    o["broadcastHz"] = config.broadcast_hz;
    o["gnssHz"] = config.gnss_hz;
    auto a = o["mappings"].to<JsonArray>();
    for (const auto &m : config.mappings)
        if (m.enabled) {
            auto x = a.add<JsonObject>();
            x["bus"] = m.bus;
            x["id"] = m.id;
            x["extended"] = m.extended;
            x["bit"] = m.bit;
            x["width"] = m.width;
            x["little"] = m.little;
            x["signed"] = m.signed_value;
            x["scale"] = m.scale;
            x["offset"] = m.offset;
            x["channel"] = channels[m.channel].name;
            x["staleMs"] = m.stale_ms;
        }
}
static bool setLogger(JsonVariant v) {
    Config c;
    {
        Guard lock(state_mutex);
        c = config;
    }
    if (!v.is<JsonObject>())
        return false;
    if (!v["ncProfile"].isNull())
        c.nc_profile = v["ncProfile"].as<bool>();
    if (!v["hubBroadcast"].isNull())
        c.hub_broadcast = v["hubBroadcast"].as<bool>();
    if (!v["broadcastBase"].isNull()) {
        int x = v["broadcastBase"];
        if (x < 0 || x > 0x7ff)
            return false;
        c.broadcast_base = x;
    }
    if (!v["broadcastHz"].isNull()) {
        int x = v["broadcastHz"];
        if (x < 1 || x > 5)
            return false;
        c.broadcast_hz = x;
    }
    // GNSS rate is selected from verified hardware capability at boot, not
    // arbitrary app input.
    if (!v["mappings"].isNull()) {
        if (!v["mappings"].is<JsonArray>() || v["mappings"].size() > c.mappings.size())
            return false;
        c.mappings = {};
        size_t i = 0;
        for (JsonObject x : v["mappings"].as<JsonArray>()) {
            int bus = x["bus"] | 2, bit = x["bit"] | 0, width = x["width"] | 16;
            if (bus < 1 || bus > 2 || bit < 0 || bit > 63 || width < 1 || width > 32 ||
                !x["channel"].is<const char *>())
                return false;
            int channel;
            {
                Guard lock(state_mutex);
                channel = findChannel(x["channel"].as<const char *>());
            }
            if (channel < 0 || channel >= BASE_CHANNELS)
                return false;
            // Only CAN-derived input channels can be overwritten, never
            // GNSS/IMU/status.
            if (!(channel == RPM || channel == SPEED || channel == WATER_TEMP ||
                  channel == OIL_PRESS || (channel >= THROTTLE && channel <= AFR_RAW) ||
                  channel == CAN_GPIO || channel == WHEEL_HZ))
                return false;
            auto &m = c.mappings[i++];
            m.enabled = true;
            m.bus = bus;
            m.channel = channel;
            m.bit = bit;
            m.width = width;
            m.id = x["id"] | 0U;
            m.extended = x["extended"] | false;
            m.little = x["little"] | true;
            m.signed_value = x["signed"] | false;
            m.scale = x["scale"] | 1.0;
            m.offset = x["offset"] | 0.0;
            m.stale_ms = x["staleMs"] | 1000U;
        }
    }
    if (!validConfig(c))
        return false;
    {
        Guard lock(state_mutex);
        config = c;
        for (const auto &m : c.mappings)
            if (m.enabled)
                channels[m.channel].stale_ms = m.stale_ms;
    }
    return true;
}
static void status(JsonObject s) {
    Snapshot snap = takeSnapshot();
    auto sy = s["system"].to<JsonObject>();
    sy["model"] = "logger_v1";
    sy["uptime"] = snap.us / 1000000;
    sy["ver_major"] = 2;
    sy["ver_minor"] = 16;
    sy["ver_bugfix"] = 1;
    sy["heap"] = esp_get_free_heap_size();
    auto gps = s["GPS"].to<JsonObject>();
    gps["init"] = snap.has(GNSS_LINK) && snap.values[GNSS_LINK] > 0 ? 3 : 0;
    gps["qual"] = snap.has(GPS_FIX) ? snap.values[GPS_FIX] : 0;
    gps["sats"] = snap.values[GPS_SATS];
    gps["lat"] = snap.values[LAT];
    gps["lon"] = snap.values[LON];
    gps["hAcc"] = snap.values[GPS_HACC];
    gps["hz"] = snap.values[GPS_HZ];
    gps["utcValid"] = snap.has(UTC_VALID) && snap.values[UTC_VALID] > 0;
    auto log = s["logging"].to<JsonObject>();
    log["status"] = stats.logging && stats.sd_ok ? 1 : 0;
    log["dur"] = snap.us / 1000000;
    log["rows"] = stats.rows.load();
    log["rawRows"] = stats.raw_rows.load();
    log["syncs"] = stats.syncs.load();
    log["drops"] = stats.log_drop.load();
    log["errors"] = stats.sd_errors.load();
    {
        Guard lock(state_mutex);
        log["file"] = session_path;
        s["luaError"] = lua_error;
        auto tr = s["track"].to<JsonObject>();
        tr["valid"] = config.track.valid();
        tr["trackId"] = config.track.id;
        tr["status"] = laps->current_lap ? 1 : 0;
        tr["inLap"] = laps->current_lap;
        tr["bestSeconds"] = laps->best_s;
    }
    auto ca = s["CAN"].to<JsonObject>();
    ca["vehicleListenOnly"] = stats.vehicle_listen_only.load();
    ca["vehicleRx"] = stats.can1_rx.load();
    ca["hubRx"] = stats.can2_rx.load();
    ca["vehicleOK"] = stats.can1_ok.load();
    ca["hubOK"] = stats.can2_ok.load();
    ca["vehicleErrors"] = stats.can1_errors.load();
    ca["hubErrors"] = stats.can2_errors.load();
    ca["hubTx"] = stats.hub_tx.load();
    ca["hubTxErrors"] = stats.hub_tx_errors.load();
    ca["drops"] = stats.can_drop.load();
    ca["benchStatus"] = stats.bench_status.load();
    ca["benchVehicleRx"] = stats.bench_vehicle_rx.load();
    ca["benchHubRx"] = stats.bench_hub_rx.load();
    s["imuSamples"] = stats.imu_samples.load();
    s["imuErrors"] = stats.imu_errors.load();
    s["gnssSamples"] = stats.gps_samples.load();
    s["gnssErrors"] = stats.gnss_errors.load();
    s["luaOK"] = stats.lua_ok.load();
    s["luaDrops"] = stats.lua_drop.load();
    s["usbDrops"] = stats.usb_drop.load();
    s["sampleLate"] = stats.sample_late.load();
}
static void listLogs(JsonDocument &out, JsonVariant v) {
    auto o = out["logs"].to<JsonObject>();
    auto a = o["files"].to<JsonArray>();
    unsigned offset = v["offset"] | 0U;
    if (offset > 100000 || !stats.sd_ok) {
        o["error"] = "SD unavailable or invalid offset";
        return;
    }
    Guard lock(sd_mutex);
    DIR *dir = opendir("/sdcard/logs");
    if (!dir) {
        o["error"] = "Cannot open logs";
        return;
    }
    unsigned seen = 0, count = 0;
    bool more = false;
    while (auto *entry = readdir(dir)) {
        if (entry->d_name[0] == '.')
            continue;
        if (seen++ < offset)
            continue;
        if (count++ >= 32) {
            more = true;
            break;
        }
        char path[256];
        snprintf(path, sizeof(path), "/sdcard/logs/%.220s", entry->d_name);
        struct stat info = {};
        auto f = a.add<JsonObject>();
        f["name"] = entry->d_name;
        if (stat(path, &info) == 0)
            f["bytes"] = uint64_t(info.st_size);
    }
    closedir(dir);
    if (more)
        o["next"] = offset + 32;
    else
        o["next"] = nullptr;
}
static void readLog(JsonDocument &out, JsonVariant v) {
    auto o = out["logData"].to<JsonObject>();
    const char *name = v["name"] | "";
    if (!*name || strlen(name) > 96 || !stats.sd_ok) {
        o["error"] = "SD unavailable or invalid name";
        return;
    }
    for (const char *p = name; *p; ++p)
        if (!(isalnum(static_cast<unsigned char>(*p)) || *p == '_' || *p == '.')) {
            o["error"] = "Invalid name";
            return;
        }
    if (strstr(name, "..")) {
        o["error"] = "Invalid name";
        return;
    }
    uint32_t offset = v["offset"] | 0U;
    char path[128];
    snprintf(path, sizeof(path), "/sdcard/logs/%s", name);
    Guard lock(sd_mutex);
    // Read only closed segments; rotateLog closes the current segment without stopping capture.
    {
        Guard state(state_mutex);
        std::string active = session_path;
        if (active == path ||
            (active.size() > 4 && active.substr(0, active.size() - 4) + "_can.csv" == path)) {
            o["error"] = "Rotate the active log before reading";
            return;
        }
    }
    FILE *f = fopen(path, "r");
    if (!f) {
        o["error"] = "Cannot open file";
        return;
    }
    struct stat info = {};
    if (fstat(fileno(f), &info) || offset > uint64_t(info.st_size) || fseek(f, offset, SEEK_SET)) {
        fclose(f);
        o["error"] = "Invalid offset";
        return;
    }
    char data[2049];
    size_t n = fread(data, 1, sizeof(data) - 1, f);
    bool error = ferror(f);
    fclose(f);
    data[n] = 0;
    if (error) {
        o["error"] = "SD read failed";
        return;
    }
    o["name"] = name;
    o["offset"] = offset;
    o["next"] = offset + n;
    o["size"] = uint64_t(info.st_size);
    o["eof"] = offset + n >= uint64_t(info.st_size);
    o["data"] = data;
}
static void handle(JsonDocument &in, Transport &t) {
    JsonDocument out;
    JsonObject root = in.as<JsonObject>();
    if (root.size() != 1)
        return;
    auto entry = root.begin();
    const char *cmd = entry->key().c_str();
    JsonVariant v = entry->value();
    Guard serial(protocol_mutex);
    if (!strcmp(cmd, "getVer")) {
        auto o = out["ver"].to<JsonObject>();
        o["name"] = "RCPMK3";
        o["fname"] = "logger_v1 real-sensor SD logger";
        o["major"] = 2;
        o["minor"] = 16;
        o["bugfix"] = 1;
        o["serial"] = "LOGGER-V1-TEST";
        o["git_info"] = "cf1c711-logger-v1-integration";
        o["release_type"] = "development";
    } else if (!strcmp(cmd, "getCapabilities")) {
        auto o = out["capabilities"].to<JsonObject>();
        o["flags"].to<JsonArray>();
        auto c = o["channels"].to<JsonObject>();
        for (const char *n : {"analog", "gpio", "timer", "pwm", "obd2", "canChan"})
            c[n] = 0;
        c["imu"] = 6;
        c["can"] = 2;
        {
            Guard lock(state_mutex);
            o["sampleRates"]["gps"] = config.gnss_hz;
        }
        o["sampleRates"]["sensor"] = 100;
        o["db"]["tracks"] = 0;
        o["db"]["sectors"] = 0;
    } else if (!strcmp(cmd, "listLogs"))
        listLogs(out, v);
    else if (!strcmp(cmd, "readLog"))
        readLog(out, v);
    else if (!strcmp(cmd, "testCanLoop")) {
        bool ok;
        {
            Guard lock(state_mutex);
            ok = !config.hub_broadcast && stats.can2_ok && stats.bench_status != 1;
        }
        ok = ok && !strcmp(v["confirm"] | "", "DESK_CAN1_CAN2_LOOP");
        if (ok)
            stats.bench_request = true;
        result(out, cmd, ok,
               ok ? "Queued: desk only; two test frames, CAN1 ACK enabled for at most one second"
                  : "Requires desk loop confirmation and broadcast disabled");
    } else if (!strcmp(cmd, "getMeta"))
        metadataArray(out["meta"].to<JsonArray>());
    else if (!strcmp(cmd, "getStatus"))
        status(out["status"].to<JsonObject>());
    else if (!strcmp(cmd, "s"))
        sample(out, t, v["meta"] | false);
    else if (!strcmp(cmd, "log")) {
        t.stream = v.is<JsonObject>() ? (v["en"] | true) : v.as<bool>();
        out[t.stream ? "logStart" : "logEnd"] = 1;
        t.schema = 0;
    } else if (!strcmp(cmd, "getLoggerCfg"))
        loggerConfig(out["loggerCfg"].to<JsonObject>());
    else if (!strcmp(cmd, "setLoggerCfg"))
        result(out, cmd, setLogger(v), "Use getLoggerCfg for supported fields; flashCfg persists");
    else if (!strcmp(cmd, "getTrackCfg"))
        trackConfig(out["trackCfg"].to<JsonObject>());
    else if (!strcmp(cmd, "setTrackCfg")) {
        if (v["trackCfg"].is<JsonObject>())
            v = v["trackCfg"];
        Track tr;
        {
            Guard lock(state_mutex);
            tr = config.track;
        }
        if (v["track"]["id"].is<int>())
            tr.id = v["track"]["id"];
        if (v["track"]["sf"].is<JsonArray>() && v["track"]["sf"].size() == 2) {
            tr.lat = v["track"]["sf"][0];
            tr.lon = v["track"]["sf"][1];
        }
        if (!v["rad"].isNull())
            tr.radius_m = v["rad"].as<double>() * M_PER_DEG;
        if (!v["minLapSeconds"].isNull())
            tr.min_lap_s = v["minLapSeconds"];
        bool ok = v.is<JsonObject>() && (tr.id == -1 || tr.valid()) &&
                  (v["track"]["sec"].isNull() || v["track"]["sec"].size() == 0);
        if (ok) {
            Guard lock(state_mutex);
            config.track = tr;
            stats.reset_laps = true;
        }
        result(out, cmd, ok,
               ok ? nullptr : "Invalid track; sectors require an explicit course definition");
    } else if (!strcmp(cmd, "getGpsCfg")) {
        auto o = out["gpsCfg"].to<JsonObject>();
        {
            Guard lock(state_mutex);
            o["sr"] = config.gnss_hz;
        }
        for (const char *key : {"pos", "speed", "dist", "alt", "sats", "qual"})
            o[key] = 1;
        o["dop"] = 0; // NAV-PVT exposes horizontal accuracy, not a fabricated DOP.
    } else if (!strcmp(cmd, "getAnalogCfg"))
        out["analogCfg"].to<JsonObject>();
    else if (!strcmp(cmd, "getTimerCfg"))
        out["timerCfg"].to<JsonObject>();
    else if (!strcmp(cmd, "getGpioCfg"))
        out["gpioCfg"].to<JsonObject>();
    else if (!strcmp(cmd, "getPwmCfg"))
        out["pwmCfg"].to<JsonObject>();
    else if (!strcmp(cmd, "getTrackDb")) {
        out["trackDb"]["tracks"].to<JsonArray>();
        out["trackDb"]["page"] = nullptr;
    } else if (!strcmp(cmd, "getCanCfg")) {
        auto o = out["canCfg"].to<JsonObject>();
        o["en"] = 1;
        auto a = o["baud"].to<JsonArray>();
        a.add(500000);
        a.add(500000);
    } else if (!strcmp(cmd, "setCanCfg")) {
        if (v["canCfg"].is<JsonObject>())
            v = v["canCfg"];
        bool ok = (v["en"] | 1) == 1 && v["baud"].size() == 2 && v["baud"][0] == 500000 &&
                  v["baud"][1] == 500000;
        result(out, cmd, ok,
               ok ? nullptr : "Board uses two enabled 500k buses; CAN1 remains listen-only");
    } else if (!strcmp(cmd, "getImuCfg")) {
        auto o = out["imuCfg"].to<JsonObject>();
        Guard lock(state_mutex);
        const unsigned ids[] = {LINEAR_X, LINEAR_Y, LINEAR_Z, GYRO_X, GYRO_Y, GYRO_Z};
        for (unsigned i = 0; i < 6; ++i) {
            char k[2] = {char('0' + i), 0};
            auto channel = o[k].to<JsonObject>();
            metadata(channel, channels[ids[i]]);
            channel["mode"] = 1;
            channel["chan"] = i;
            channel["zeroVal"] = 0;
            channel["alpha"] = 1;
        }
    } else if (!strcmp(cmd, "getLapCfg")) {
        auto o = out["lapCfg"].to<JsonObject>();
        Guard lock(state_mutex);
        const unsigned ids[] = {LAP_COUNT, LAP_TIME, PRED_TIME, ELAPSED_TIME, CURRENT_LAP};
        const char *names[] = {"lapCount", "lapTime", "predTime", "elapsedTime", "currentLap"};
        for (unsigned i = 0; i < 5; ++i)
            metadata(o[names[i]].to<JsonObject>(), channels[ids[i]]);
    } else if (!strcmp(cmd, "getObd2Cfg")) {
        out["obd2Cfg"]["en"] = 0;
        out["obd2Cfg"]["pids"].to<JsonArray>();
    } else if (!strcmp(cmd, "getConnCfg")) {
        auto o = out["connCfg"].to<JsonObject>();
        o["btCfg"]["btEn"] = 0;
        o["btCfg"]["name"] = "";
        o["btCfg"]["pass"] = "";
        o["cellCfg"]["cellEn"] = 0;
        o["cellCfg"]["apnHost"] = "";
        o["cellCfg"]["apnUser"] = "";
        o["cellCfg"]["apnPass"] = "";
        o["telCfg"]["bgStream"] = 0;
        o["telCfg"]["host"] = "";
        Guard lock(state_mutex);
        o["telCfg"]["deviceId"] = config.telemetry_device_id;
    } else if (!strcmp(cmd, "setConnCfg")) {
        if (v["connCfg"].is<JsonObject>())
            v = v["connCfg"];
        const char *id = v["telCfg"]["deviceId"] | "";
        bool ok = strlen(id) < sizeof(config.telemetry_device_id) &&
                  !(v["btCfg"]["btEn"] | false) && !(v["cellCfg"]["cellEn"] | false);
        if (ok) {
            Guard lock(state_mutex);
            strcpy(config.telemetry_device_id, id);
        }
        result(out, cmd, ok, ok ? nullptr : "Bluetooth/cellular unsupported or device ID too long");
    } else if (!strcmp(cmd, "getScriptCfg")) {
        Guard lock(state_mutex);
        out["scriptCfg"]["page"] = nullptr;
        out["scriptCfg"]["data"] = script_text;
    } else if (!strcmp(cmd, "setScriptCfg")) {
        int page = v["page"] | -1, mode = v["mode"] | 0;
        const char *data = v["data"] | "";
        size_t size = strlen(data);
        if (page == 0) {
            t.script_used = 0;
            t.script_page = 0;
            t.script_active = true;
        }
        bool ok = t.script_active && page == int(t.script_page) && (mode == 1 || mode == 2) &&
                  size <= 256 && t.script_used + size < sizeof(script_text);
        if (ok) {
            memcpy(t.script + t.script_used, data, size);
            t.script_used += size;
            t.script[t.script_used] = 0;
            ++t.script_page;
            if (mode == 2) {
                ok = saveScript(t.script);
                t.script_active = false;
            }
        } else
            t.script_active = false;
        result(out, cmd, ok, ok ? nullptr : "Script transfer rejected: page/length/mode");
    } else if (!strcmp(cmd, "runScript")) {
        stats.reload_lua = true;
        result(out, cmd, true);
    } else if (!strcmp(cmd, "flashCfg"))
        result(out, cmd, saveSettings());
    else if (!strcmp(cmd, "saveImuCalibration")) {
        Snapshot s = takeSnapshot();
        bool ok = s.has(IMU_CAL) && s.values[IMU_CAL] == 255;
        if (ok)
            stats.save_imu = true;
        result(out, cmd, ok,
               ok ? "Queued; verify boot log and next startup"
                  : "BNO055 must be fully calibrated (255)");
    } else if (!strcmp(cmd, "resetLap")) {
        stats.reset_laps = true;
        result(out, cmd, true);
    } else if (!strcmp(cmd, "setLogging")) {
        stats.logging = v.as<bool>();
        result(out, cmd, true);
    } else if (!strcmp(cmd, "rotateLog")) {
        stats.rotate = true;
        result(out, cmd, true);
    } else
        result(out, cmd, false, "Unsupported command; no changes made");
    send(out, t);
}
static void receive(Transport &t, const uint8_t *data, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        char c = char(data[i]);
        if (c == '\r' || c == '\n') {
            if (t.used && !t.discard) {
                JsonDocument doc;
                auto error =
                    deserializeJson(doc, t.input, t.used, DeserializationOption::NestingLimit(12));
                if (!error)
                    handle(doc, t);
                else {
                    JsonDocument out;
                    result(out, "error", false, "Malformed JSON");
                    send(out, t);
                }
            }
            t.used = 0;
            t.discard = false;
        } else if (t.used < LINE_BYTES - 1 && !t.discard)
            t.input[t.used++] = c;
        else {
            t.discard = true;
            t.used = 0;
        }
    }
}
static void task(void *arg) {
    Transport t;
    t.uart = arg != nullptr;
    t.input =
        static_cast<char *>(heap_caps_malloc(LINE_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    t.output =
        static_cast<char *>(heap_caps_malloc(LINE_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    t.script = static_cast<char *>(
        heap_caps_malloc(sizeof(script_text), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    t.metadata = static_cast<Channel *>(
        heap_caps_malloc(sizeof(Channel) * MAX_CHANNELS, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    ESP_ERROR_CHECK(t.input && t.output && t.script && t.metadata ? ESP_OK : ESP_ERR_NO_MEM);
    while (true) {
        uint8_t b[256];
        int n = t.uart ? uart_read_bytes(UART_NUM_0, b, sizeof(b), pdMS_TO_TICKS(10))
                       : int(xStreamBufferReceive(usb_rx, b, sizeof(b), pdMS_TO_TICKS(10)));
        if (n > 0)
            receive(t, b, n);
        if (!t.uart) {
            stats.usb_connected = tud_cdc_connected();
            if (!stats.usb_connected) {
                t.stream = false;
                t.used = 0;
                t.schema = 0;
            }
        }
        if (t.stream && nowUs() >= t.next_sample) {
            t.next_sample = nowUs() + 100000;
            JsonDocument out;
            sample(out, t, false);
            if (!send(out, t))
                t.stream = false;
        }
    }
}
static void cdcRx(int itf, cdcacm_event_t *) {
    uint8_t b[512];
    size_t n = 0;
    while (tinyusb_cdcacm_read(static_cast<tinyusb_cdcacm_itf_t>(itf), b, sizeof(b), &n) ==
               ESP_OK &&
           n)
        if (xStreamBufferSend(usb_rx, b, n, 0) != n)
            ++stats.usb_drop;
}
void startProtocol() {
    protocol_mutex = xSemaphoreCreateMutex();
    uart_output_mutex = xSemaphoreCreateMutex();
    usb_rx = xStreamBufferCreate(8192, 1);
    ESP_ERROR_CHECK(protocol_mutex && usb_rx && uart_output_mutex ? ESP_OK : ESP_ERR_NO_MEM);
    original_log = esp_log_set_vprintf(atomicLog);
    tinyusb_config_t usb = {};
    // The logger can remain powered while the PC cable is absent.
    usb.self_powered = true;
    usb.vbus_monitor_io = 6;
    static const uint8_t descriptor[] = {
        TUD_CONFIG_DESCRIPTOR(1, 2, 0, TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN,
                              TUSB_DESC_CONFIG_ATT_SELF_POWERED, 100),
        TUD_CDC_DESCRIPTOR(0, 4, 0x81, 8, 0x02, 0x82, 64)};
    usb.configuration_descriptor = descriptor;
    ESP_ERROR_CHECK(tinyusb_driver_install(&usb));
    tinyusb_config_cdcacm_t cdc = {};
    cdc.usb_dev = TINYUSB_USBDEV_0;
    cdc.cdc_port = TINYUSB_CDC_ACM_0;
    cdc.callback_rx = cdcRx;
    ESP_ERROR_CHECK(tusb_cdc_acm_init(&cdc));
    uart_config_t u = {};
    u.baud_rate = 115200;
    u.data_bits = UART_DATA_8_BITS;
    u.parity = UART_PARITY_DISABLE;
    u.stop_bits = UART_STOP_BITS_1;
    u.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    u.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &u));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_0, 43, 44, -1, -1));
    if (!uart_is_driver_installed(UART_NUM_0))
        ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 8192, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(xTaskCreate(task, "rcp_usb", 12288, nullptr, 3, nullptr) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(xTaskCreate(task, "rcp_uart", 12288, reinterpret_cast<void *>(1), 3, nullptr) ==
                            pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
}
} // namespace logger
