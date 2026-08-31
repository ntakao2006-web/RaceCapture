#include "state.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "nvs.h"
#include <cstdio>
#include <new>

namespace logger {
SemaphoreHandle_t state_mutex = nullptr;
SemaphoreHandle_t sd_mutex = nullptr;
std::array<Channel, MAX_CHANNELS> channels{};
size_t channel_count = 0;
uint32_t schema_revision = 1;
Config config{};
Statistics stats;
QueueHandle_t log_queue = nullptr, can_log_queue = nullptr, lua_can_queue = nullptr;
int64_t utc_offset = 0;
uint64_t utc_updated = 0;
char session_path[128]{};
char script_text[16385]{};
uint32_t script_revision = 1;
char lua_error[160]{};
LapEngine *laps = nullptr;

void putChannel(size_t id, double value, uint64_t now, bool valid) {
    if (id >= channel_count)
        return;
    auto &c = channels[id];
    c.value = value;
    c.updated_us = now;
    c.available = valid && std::isfinite(value);
}
int findChannel(const char *name) {
    for (size_t i = 0; i < channel_count; ++i)
        if (!strcmp(channels[i].name, name))
            return int(i);
    return -1;
}
int addChannel(const char *name, const char *unit, double min, double max, unsigned precision,
               unsigned rate) {
    if (!name || !*name || strlen(name) >= sizeof(Channel::name) || !unit ||
        strlen(unit) >= sizeof(Channel::unit) || precision > 7 || rate < 1 || rate > 100 ||
        !std::isfinite(min) || !std::isfinite(max) || min > max)
        return -1;
    // Keep CSV headers and CAN-side names unambiguous.
    for (const char *p = name; *p; ++p)
        if (!((*p >= 'A' && *p <= 'Z') || (*p >= 'a' && *p <= 'z') || (*p >= '0' && *p <= '9') ||
              *p == '_'))
            return -1;
    int existing = findChannel(name);
    if (existing >= 0) {
        const auto &c = channels[existing];
        return c.custom && !strcmp(c.unit, unit) && c.min == min && c.max == max &&
                       c.precision == precision && c.rate == rate
                   ? existing
                   : -1;
    }
    if (channel_count >= MAX_CHANNELS)
        return -1;
    auto &c = channels[channel_count];
    c = Channel{};
    snprintf(c.name, sizeof(c.name), "%s", name);
    snprintf(c.unit, sizeof(c.unit), "%s", unit);
    c.min = min;
    c.max = max;
    c.precision = uint8_t(precision);
    c.rate = uint16_t(rate);
    c.stale_ms = std::max(1000U, 3000U / rate);
    c.custom = channel_count >= BASE_CHANNELS;
    ++schema_revision;
    return int(channel_count++);
}
Snapshot takeSnapshot(Channel *metadata) {
    Snapshot s;
    Guard lock(state_mutex);
    // Timestamp after taking the lock: a sensor can publish while we wait.
    // A pre-lock timestamp would misclassify that fresh sample as future data.
    s.us = nowUs();
    s.count = uint16_t(channel_count);
    if (metadata)
        memcpy(metadata, channels.data(), channel_count * sizeof(Channel));
    s.revision = schema_revision;
    if (fresh(s.us, utc_updated, 2000))
        s.utc_us = int64_t(s.us) + utc_offset;
    for (size_t i = 0; i < channel_count; ++i) {
        auto &c = channels[i];
        s.values[i] = c.value;
        if (c.available && fresh(s.us, c.updated_us, c.stale_ms))
            s.valid[i / 32] |= uint32_t(1) << (i % 32);
    }
    return s;
}
void stateInit() {
    state_mutex = xSemaphoreCreateMutex();
    config = Config{};
    struct Def {
        const char *name, *unit;
        double lo, hi;
        unsigned prec, rate;
    };
    static const Def defs[] = {{"RPM", "rpm", 0, 16000, 0, 50},
                               {"Speed", "km/h", 0, 400, 2, 50},
                               {"WaterTemp", "C", -40, 200, 1, 10},
                               {"OilPress", "kPa", 0, 2000, 1, 50},
                               {"Lat", "deg", -90, 90, 7, 10},
                               {"Lon", "deg", -180, 180, 7, 10},
                               {"GPSSpeed", "km/h", 0, 400, 2, 10},
                               {"Altitude", "m", -1000, 10000, 2, 10},
                               {"GPSHAcc", "m", 0, 1000, 2, 10},
                               {"GPSSats", "", 0, 64, 0, 10},
                               {"GPSFix", "", 0, 5, 0, 10},
                               {"GNSSHz", "Hz", 0, 25, 1, 1},
                               {"UTCValid", "", 0, 1, 0, 10},
                               {"AccelX", "m/s2", -40, 40, 3, 100},
                               {"AccelY", "m/s2", -40, 40, 3, 100},
                               {"AccelZ", "m/s2", -40, 40, 3, 100},
                               {"GyroX", "dps", -2000, 2000, 2, 100},
                               {"GyroY", "dps", -2000, 2000, 2, 100},
                               {"GyroZ", "dps", -2000, 2000, 2, 100},
                               {"Yaw", "deg", 0, 360, 2, 100},
                               {"Pitch", "deg", -180, 180, 2, 100},
                               {"Roll", "deg", -180, 180, 2, 100},
                               {"GForceX", "G", -4, 4, 4, 100},
                               {"GForceY", "G", -4, 4, 4, 100},
                               {"GForceZ", "G", -4, 4, 4, 100},
                               {"GravityX", "m/s2", -12, 12, 3, 100},
                               {"GravityY", "m/s2", -12, 12, 3, 100},
                               {"GravityZ", "m/s2", -12, 12, 3, 100},
                               {"IMUTemp", "C", -40, 125, 0, 10},
                               {"IMUCal", "", 0, 255, 0, 10},
                               {"IMULink", "", 0, 1, 0, 10},
                               {"IMUErr", "", 0, 255, 0, 10},
                               {"IMUHz", "Hz", 0, 100, 1, 1},
                               {"GNSSLink", "", 0, 1, 0, 10},
                               {"LapCount", "", 0, 10000, 0, 10},
                               {"LapTime", "Min", 0, 60, 4, 10},
                               {"PredTime", "Min", -60, 60, 4, 10},
                               {"ElapsedTime", "Min", 0, 60, 4, 10},
                               {"CurrentLap", "", 0, 10000, 0, 10},
                               {"Distance", "km", 0, 100, 4, 10},
                               {"SessionTime", "Min", 0, 100000, 4, 10},
                               {"Throttle", "%", 0, 100, 2, 50},
                               {"EngineLoad", "%", 0, 100, 2, 20},
                               {"IntakeTemp", "C", -40, 200, 1, 10},
                               {"BatteryVolt", "V", 0, 30, 3, 5},
                               {"OilTemp", "C", -40, 250, 2, 10},
                               {"CHT", "C", -40, 500, 2, 10},
                               {"EGT", "C", -40, 1400, 2, 10},
                               {"AFRRaw", "AFR", 0, 100, 3, 50},
                               {"AFR", "AFR", 0, 100, 3, 50},
                               {"AFRValid", "", 0, 1, 0, 50},
                               {"CANGPIO", "", 0, 65535, 0, 100},
                               {"WheelHz", "Hz", 0, 10000, 2, 100},
                               {"CpuTemp", "C", -40, 125, 1, 1},
                               {"SDPass", "", 0, 1, 0, 1},
                               {"LogDrops", "", 0, 1000000, 0, 1},
                               {"CAN1Rx", "", 0, 1000000000, 0, 1},
                               {"CAN2Rx", "", 0, 1000000000, 0, 1},
                               {"CANDrops", "", 0, 1000000, 0, 1},
                               {"LuaOK", "", 0, 1, 0, 1},
                               {"GPSTow", "ms", 0, 604800000, 0, 25},
                               {"GPSUTC", "s", 0, 4102444800, 6, 25},
                               {"GPSTAcc", "ns", 0, 1e9, 0, 25},
                               {"PPSAge", "ms", 0, 3000, 2, 25}};
    static_assert(std::size(defs) == BASE_CHANNELS, "Channel enum and metadata differ");
    for (auto &d : defs)
        addChannel(d.name, d.unit, d.lo, d.hi, d.prec, d.rate);
    for (unsigned i = ACCEL_X; i <= GRAVITY_Z; ++i)
        channels[i].stale_ms = 200;
    void *memory = heap_caps_malloc(sizeof(LapEngine), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    ESP_ERROR_CHECK(memory && state_mutex ? ESP_OK : ESP_ERR_NO_MEM);
    laps = new (memory) LapEngine;
}
bool validConfig(const Config &c) {
    if (!memchr(c.telemetry_device_id, 0, sizeof(c.telemetry_device_id)))
        return false;
    if (c.version != 1 || (c.gnss_hz != 18 && c.gnss_hz != 25) || c.broadcast_hz < 1 ||
        c.broadcast_hz > 5 || c.broadcast_base + MAX_CHANNELS - 1 > 0x7ff ||
        (c.track.id != -1 && !c.track.valid()))
        return false;
    for (const auto &m : c.mappings)
        if (m.enabled &&
            (m.bus < 1 || m.bus > 2 || m.channel >= BASE_CHANNELS || m.width < 1 || m.width > 32 ||
             m.bit + m.width > 64 || m.id > (m.extended ? 0x1fffffffU : 0x7ffU) ||
             m.stale_ms < 10 || m.stale_ms > 60000 || !std::isfinite(m.scale) ||
             !std::isfinite(m.offset)))
            return false;
    return true;
}
bool loadSettings() {
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READONLY, &h) != ESP_OK)
        return false;
    Config saved{};
    size_t n = sizeof(saved);
    bool loaded =
        nvs_get_blob(h, "config", &saved, &n) == ESP_OK && n == sizeof(saved) && saved.version == 1;
    loaded = loaded && validConfig(saved);
    if (loaded)
        config = saved;
    n = sizeof(script_text);
    if (nvs_get_str(h, "script", script_text, &n) != ESP_OK)
        script_text[0] = 0;
    nvs_close(h);
    laps->reset(config.track);
    loadBestLap();
    for (const auto &m : config.mappings)
        if (m.enabled)
            channels[m.channel].stale_ms = m.stale_ms;
    return loaded;
}
bool saveSettings() {
    Config copy;
    {
        Guard lock(state_mutex);
        copy = config;
    }
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READWRITE, &h) != ESP_OK)
        return false;
    bool ok = nvs_set_blob(h, "config", &copy, sizeof(copy)) == ESP_OK && nvs_commit(h) == ESP_OK;
    nvs_close(h);
    return ok;
}
bool saveScript(const char *text) {
    if (strlen(text) >= sizeof(script_text))
        return false;
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READWRITE, &h) != ESP_OK)
        return false;
    bool ok = nvs_set_str(h, "script", text) == ESP_OK && nvs_commit(h) == ESP_OK;
    nvs_close(h);
    if (ok) {
        Guard lock(state_mutex);
        strcpy(script_text, text);
        ++script_revision;
        stats.reload_lua = true;
    }
    return ok;
}
} // namespace logger
