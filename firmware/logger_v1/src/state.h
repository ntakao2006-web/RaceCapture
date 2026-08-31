#pragma once
#include "core.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include <atomic>

namespace logger {
enum ChannelId {
    RPM,
    SPEED,
    WATER_TEMP,
    OIL_PRESS,
    LAT,
    LON,
    GPS_SPEED,
    ALTITUDE,
    GPS_HACC,
    GPS_SATS,
    GPS_FIX,
    GPS_HZ,
    UTC_VALID,
    ACCEL_X,
    ACCEL_Y,
    ACCEL_Z,
    GYRO_X,
    GYRO_Y,
    GYRO_Z,
    YAW,
    PITCH,
    ROLL,
    LINEAR_X,
    LINEAR_Y,
    LINEAR_Z,
    GRAVITY_X,
    GRAVITY_Y,
    GRAVITY_Z,
    IMU_TEMP,
    IMU_CAL,
    IMU_LINK,
    IMU_ERR,
    IMU_HZ,
    GNSS_LINK,
    LAP_COUNT,
    LAP_TIME,
    PRED_TIME,
    ELAPSED_TIME,
    CURRENT_LAP,
    DISTANCE,
    SESSION_TIME,
    THROTTLE,
    ENGINE_LOAD,
    INTAKE_TEMP,
    BATT_VOLT,
    OIL_TEMP,
    CHT,
    EGT,
    AFR_RAW,
    AFR,
    AFR_VALID,
    CAN_GPIO,
    WHEEL_HZ,
    CPU_TEMP,
    SD_OK,
    LOG_DROPS,
    CAN1_RX,
    CAN2_RX,
    CAN_DROPS,
    LUA_OK,
    GPS_TOW,
    GPS_UTC,
    GPS_TACC,
    PPS_AGE,
    BASE_CHANNELS
};
struct Channel {
    char name[24]{};
    char unit[12]{};
    double min = 0, max = 0, value = 0;
    uint64_t updated_us = 0;
    uint32_t stale_ms = 1000;
    uint16_t rate = 100;
    uint8_t precision = 3;
    bool available = false, custom = false;
};
struct Snapshot {
    uint64_t us = 0;
    int64_t utc_us = 0;
    uint32_t revision = 0;
    uint16_t count = 0;
    std::array<double, MAX_CHANNELS> values{};
    std::array<uint32_t, (MAX_CHANNELS + 31) / 32> valid{};
    bool has(size_t i) const { return i < count && (valid[i / 32] & (uint32_t(1) << (i % 32))); }
};
struct CanMapping {
    bool enabled = false, little = true, signed_value = false, extended = false;
    uint8_t bus = 2, bit = 0, width = 16;
    uint16_t channel = OIL_TEMP;
    uint32_t id = 0, stale_ms = 1000;
    double scale = 1, offset = 0;
};
struct Config {
    uint32_t version = 1;
    bool nc_profile = false;
    bool hub_broadcast = false;
    uint16_t broadcast_base = 0x600;
    uint8_t broadcast_hz = 5;
    // 25 Hz requires irreversible high-performance OTP configuration; never burn
    // implicitly.
    uint8_t gnss_hz = 18;
    char telemetry_device_id[64]{};
    Track track{};
    std::array<CanMapping, 24> mappings{};
};
struct Statistics {
    std::atomic<uint32_t> can1_rx{0}, can2_rx{0}, can1_errors{0}, can2_errors{0};
    std::atomic<uint32_t> can_drop{0}, log_drop{0}, lua_drop{0}, usb_drop{0}, imu_errors{0},
        gnss_errors{0};
    std::atomic<uint32_t> rows{0}, raw_rows{0}, syncs{0}, sd_errors{0}, hub_tx{0}, hub_tx_errors{0};
    std::atomic<uint32_t> imu_samples{0}, gps_samples{0}, lua_errors{0}, sample_late{0};
    std::atomic<bool> sd_ok{false}, can1_ok{false}, can2_ok{false}, lua_ok{true},
        usb_connected{false};
    std::atomic<bool> logging{true}, rotate{false}, save_imu{false}, reload_lua{false};
    std::atomic<bool> reset_laps{false};
    std::atomic<uint32_t> led_bits{0};
    std::atomic<bool> bench_request{false};
    std::atomic<uint32_t> bench_status{0}, bench_vehicle_rx{0}, bench_hub_rx{0};
    std::atomic<bool> vehicle_listen_only{true};
};
class Guard {
    SemaphoreHandle_t mutex_;

  public:
    explicit Guard(SemaphoreHandle_t m) : mutex_(m) { xSemaphoreTake(mutex_, portMAX_DELAY); }
    ~Guard() { xSemaphoreGive(mutex_); }
    Guard(const Guard &) = delete;
};
extern SemaphoreHandle_t state_mutex;
extern SemaphoreHandle_t sd_mutex;
extern std::array<Channel, MAX_CHANNELS> channels;
extern size_t channel_count;
extern uint32_t schema_revision;
extern Config config;
extern Statistics stats;
extern QueueHandle_t log_queue, can_log_queue, lua_can_queue;
extern int64_t utc_offset;
extern uint64_t utc_updated;
extern char session_path[128];
extern char script_text[16385];
extern uint32_t script_revision;
extern char lua_error[160];
extern LapEngine *laps;
inline uint64_t nowUs() { return uint64_t(esp_timer_get_time()); }
void stateInit();
void putChannel(size_t id, double value, uint64_t now,
                bool valid = true); // caller holds state_mutex
int findChannel(const char *name);  // caller holds state_mutex
int addChannel(const char *name, const char *unit, double min, double max, unsigned precision,
               unsigned rate);
Snapshot takeSnapshot(Channel *metadata = nullptr);
bool loadSettings();
bool saveSettings();
bool saveScript(const char *text);
bool validConfig(const Config &candidate);
void loadBestLap();
void persistBestLap();
void onCan(const CanFrame &frame);
void startSensors();
void startCan();
void startStorage();
void startProtocol();
void startLua();
void startSampling();
} // namespace logger
