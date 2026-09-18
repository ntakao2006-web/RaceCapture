#include "state.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "nvs.h"
#include <cstdio>
#include <new>

namespace logger {
const char *resetReasonName() {
    switch (esp_reset_reason()) {
    case ESP_RST_POWERON: return "power_on";
    case ESP_RST_EXT: return "external_pin";
    case ESP_RST_SW: return "software";
    case ESP_RST_PANIC: return "panic";
    case ESP_RST_INT_WDT: return "interrupt_watchdog";
    case ESP_RST_TASK_WDT: return "task_watchdog";
    case ESP_RST_WDT: return "watchdog";
    case ESP_RST_DEEPSLEEP: return "deep_sleep";
    case ESP_RST_BROWNOUT: return "brownout";
    case ESP_RST_SDIO: return "sdio";
    case ESP_RST_USB: return "usb";
    case ESP_RST_JTAG: return "jtag";
    case ESP_RST_EFUSE: return "efuse";
    case ESP_RST_PWR_GLITCH: return "power_glitch";
    case ESP_RST_CPU_LOCKUP: return "cpu_lockup";
    default: return "unknown";
    }
}
SemaphoreHandle_t state_mutex = nullptr;
SemaphoreHandle_t sd_mutex = nullptr;
std::array<Channel, MAX_CHANNELS> channels{};
size_t channel_count = 0;
uint32_t schema_revision = 1;
Config config{};
VehicleAcquisition vehicle_acquisition{};
LevelCalibration level_calibration{};
Statistics stats;
GnssDiagnostics gnss_diagnostics;
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
    static const Def defs[] = {{"RPM", "rpm", 0, 16000, 0, 100},
                               {"Speed", "km/h", 0, 400, 2, 100},
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
                               {"Throttle", "%", 0, 100, 2, 10},
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
                               {"GPSTow", "ms", 0, 604800000, 0, GNSS_RATE_HZ},
                               {"GPSUTC", "s", 0, 4102444800, 6, GNSS_RATE_HZ},
                               {"GPSTAcc", "ns", 0, 1e9, 0, GNSS_RATE_HZ},
                               {"PPSAge", "ms", 0, 3000, 2, GNSS_RATE_HZ},
                               {"GNSSAcq", "", 0, 255, 0, 1},
                               {"GNSSTrack", "", 0, 255, 0, 1},
                               {"GNSSCNoMax", "dBHz", 0, 255, 0, 1},
                               {"GNSSCNoTop4", "dBHz", 0, 255, 1, 1},
                               {"RFNoise", "", 0, 65535, 0, 1},
                               {"RFAGC", "%", 0, 100, 2, 1},
                               {"RFJam", "", 0, 3, 0, 1},
                               {"RFCW", "", 0, 255, 0, 1},
                               {"GNSSRetry", "", 0, 1000000, 0, 1},
                               {"GNSSAge", "ms", 0, 1000000, 1, 10},
                               {"GNSSBad", "", 0, 1000000, 0, 1},
                               {"LevelRoll", "deg", -180, 180, 2, 100},
                               {"LevelPitch", "deg", -180, 180, 2, 100},
                               {"LongAccel", "G", -8, 8, 4, 100},
                               {"LatAccel", "G", -8, 8, 4, 100},
                               {"VertAccel", "G", -8, 8, 4, 100},
                               {"GPSVAcc", "m", 0, 10000, 2, 10},
                               {"SteeringAngle", "deg", -500, 500, 1, 50},
                               {"WheelSpeedFL", "km/h", -100, 555.35, 2, 100},
                               {"WheelSpeedFR", "km/h", -100, 555.35, 2, 100},
                               {"WheelSpeedRL", "km/h", -100, 555.35, 2, 100},
                               {"WheelSpeedRR", "km/h", -100, 555.35, 2, 100},
                               {"AccelPedal", "%", 0, 100, 2, 100},
                               {"AccelPedalBackup", "%", 0, 100, 2, 100},
                               {"BrakePedal", "", 0, 1, 0, 100},
                               {"ACRequest", "", 0, 1, 0, 100},
                               {"ClutchDisengaged", "", 0, 1, 0, 40},
                               {"WaterTempBackup", "C", -40, 215, 1, 10},
                               {"FuelLevelRaw", "%", 0, 100, 2, 10},
                               {"ParkingBrake", "", 0, 1, 0, 10},
                               {"FuelLevel", "%", 0, 100, 2, 10}};
    static_assert(std::size(defs) == BASE_CHANNELS, "Channel enum and metadata differ");
    for (auto &d : defs)
        addChannel(d.name, d.unit, d.lo, d.hi, d.prec, d.rate);
    for (unsigned i = ACCEL_X; i <= GRAVITY_Z; ++i)
        channels[i].stale_ms = 200;
    channels[STEERING_ANGLE].stale_ms = 250;
    for (unsigned i=WHEEL_FL; i<=FUEL_LEVEL; ++i) channels[i].stale_ms = 500;
    void *memory = heap_caps_malloc(sizeof(LapEngine), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    ESP_ERROR_CHECK(memory && state_mutex ? ESP_OK : ESP_ERR_NO_MEM);
    laps = new (memory) LapEngine;
}
bool validConfig(const Config &c) {
    if (!memchr(c.telemetry_device_id, 0, sizeof(c.telemetry_device_id)))
        return false;
    if (c.version != 1 || (c.gnss_hz != 8 && c.gnss_hz != 10 && c.gnss_hz != 15 &&
        c.gnss_hz != 18 && c.gnss_hz != 20 && c.gnss_hz != 25) || c.broadcast_hz < 1 ||
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
    VehicleAcquisition acquisition{};
    n = sizeof(acquisition);
    if (nvs_get_blob(h, "vehicle_acq", &acquisition, &n) == ESP_OK &&
        n == sizeof(acquisition) && validAcquisition(acquisition))
        vehicle_acquisition = acquisition;
    // Preserve the other legacy NVS fields without rewriting NVS. GNSS rate is
    // selected by the firmware profile, never inherited from the old 25 Hz build.
    config.gnss_hz = GNSS_RATE_HZ;
    n = sizeof(script_text);
    if (nvs_get_str(h, "script", script_text, &n) != ESP_OK)
        script_text[0] = 0;
    LevelCalibration saved_level{};
    n = sizeof(saved_level);
    if (nvs_get_blob(h, "level_cal", &saved_level, &n) == ESP_OK && n == sizeof(saved_level) &&
        validLevelCalibration(saved_level))
        level_calibration = saved_level;
    nvs_close(h);
    laps->reset(config.track);
    loadBestLap();
    for (const auto &m : config.mappings)
        if (m.enabled)
            channels[m.channel].stale_ms = m.stale_ms;
    return loaded;
}
bool saveLevelCalibration(const LevelCalibration &candidate) {
    if (!validLevelCalibration(candidate)) return false;
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READWRITE, &h) != ESP_OK)
        return false;
    bool ok = nvs_set_blob(h, "level_cal", &candidate, sizeof(candidate)) == ESP_OK &&
              nvs_commit(h) == ESP_OK;
    nvs_close(h);
    if (ok) {
        Guard lock(state_mutex);
        level_calibration = candidate;
        stats.rotate = true; // next CSV metadata and corrected values use one formula.
    }
    return ok;
}
bool saveVehicleAcquisition(const VehicleAcquisition &candidate) {
    if (!validAcquisition(candidate)) return false;
    // A stop takes effect even if NVS fails. The caller reports persistence failure.
    if (!candidate.obd_enabled) {
        Guard lock(state_mutex);
        vehicle_acquisition = candidate;
        ++stats.acquisition_revision;
    }
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READWRITE, &h) != ESP_OK) return false;
    const bool ok = nvs_set_blob(h, "vehicle_acq", &candidate, sizeof(candidate)) == ESP_OK &&
                    nvs_commit(h) == ESP_OK;
    nvs_close(h);
    if (ok) {
        Guard lock(state_mutex);
        vehicle_acquisition = candidate;
        for (auto id : {RPM, SPEED, WATER_TEMP, OIL_TEMP, THROTTLE, ENGINE_LOAD, INTAKE_TEMP,
                        BATT_VOLT, STEERING_ANGLE}) channels[id].available = false;
        stats.rotate = true;
        ++stats.acquisition_revision;
    }
    return ok;
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
