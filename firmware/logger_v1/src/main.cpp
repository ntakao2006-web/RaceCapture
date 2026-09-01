#include "driver/temperature_sensor.h"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "state.h"

namespace logger {
static void samplingTask(void *) {
    TickType_t wake = xTaskGetTickCount();
    AfrGate afr_gate;
    uint32_t imu_prev = 0, gps_prev = 0;
    uint64_t rate_time = nowUs();
    temperature_sensor_handle_t temp = nullptr;
    temperature_sensor_config_t tc = TEMPERATURE_SENSOR_CONFIG_DEFAULT(20, 100);
    if (temperature_sensor_install(&tc, &temp) == ESP_OK)
        temperature_sensor_enable(temp);
    while (true) {
        {
            Guard lock(state_mutex);
            uint64_t now = nowUs();
            auto &r = channels[RPM], &a = channels[AFR_RAW];
            bool afr_valid =
                afr_gate.update(now, r.available && fresh(now, r.updated_us, r.stale_ms), r.value,
                                a.available && fresh(now, a.updated_us, a.stale_ms));
            putChannel(AFR, a.value, now, afr_valid);
            putChannel(AFR_VALID, afr_valid ? 1 : 0, now);
            putChannel(SESSION_TIME, now / 60000000.0, now);
            bool track_valid = laps->track.valid();
            putChannel(LAP_COUNT, laps->completed, now, track_valid);
            putChannel(CURRENT_LAP, laps->current_lap, now, track_valid);
            putChannel(LAP_TIME, laps->last_s / 60, now, track_valid && laps->completed > 0);
            putChannel(ELAPSED_TIME, laps->elapsed_s / 60, now, track_valid && laps->inValidLap());
            putChannel(DISTANCE, laps->metres / 1000, now, track_valid && laps->inValidLap());
            putChannel(PRED_TIME, laps->delta_s / 60, now, laps->delta_valid);
            if (now - rate_time >= 1000000) {
                uint32_t ic = stats.imu_samples, gc = stats.gps_samples;
                double duration = (now - rate_time) / 1e6;
                putChannel(IMU_HZ, (ic - imu_prev) / duration, now);
                putChannel(GPS_HZ, (gc - gps_prev) / duration, now);
                imu_prev = ic;
                gps_prev = gc;
                rate_time = now;
                float c;
                if (temp && temperature_sensor_get_celsius(temp, &c) == ESP_OK)
                    putChannel(CPU_TEMP, c, now);
            }
            putChannel(SD_OK, stats.sd_ok ? 1 : 0, now);
            putChannel(LOG_DROPS, stats.log_drop, now);
            putChannel(CAN1_RX, stats.can1_rx, now);
            putChannel(CAN2_RX, stats.can2_rx, now);
            putChannel(CAN_DROPS, stats.can_drop, now);
            putChannel(LUA_OK, stats.lua_ok ? 1 : 0, now);
            putChannel(GNSS_RETRY, stats.gnss_retries, now);
            putChannel(GNSS_BAD, stats.gnss_parse_errors, now);
            putChannel(GNSS_AGE, gnss_diagnostics.pvt_us ?
                       (now - gnss_diagnostics.pvt_us) / 1000.0 : 0, now,
                       gnss_diagnostics.pvt_us != 0);
            bool imu_ok =
                channels[ACCEL_X].available && fresh(now, channels[ACCEL_X].updated_us, 200);
            bool gps_ok = channels[LAT].available && fresh(now, channels[LAT].updated_us, 1500);
            bool error =
                (!stats.sd_ok && !stats.sd_ready) || !imu_ok || !stats.can1_ok || !stats.can2_ok || !stats.lua_ok;
            // SYS is a steady power/running indicator. Other LEDs retain their
            // status-specific solid/blinking behavior below.
            uint8_t bits = 1;
            if (error)
                bits |= 2;
            if (stats.sd_ok && stats.logging)
                bits |= 4;
            if (gps_ok || ((now / 500000) & 1))
                bits |= 8;
            if (stats.usb_connected)
                bits |= 16;
            if (stats.can1_rx || stats.can2_rx)
                bits |= 128;
            stats.led_bits = bits;
        }
        Snapshot s = takeSnapshot();
        {
            Guard capture(capture_mutex);
            if (stats.logging && xQueueSend(log_queue, &s, 0) != pdTRUE)
                ++stats.log_drop;
        }
        if (xTaskGetTickCount() - wake > pdMS_TO_TICKS(10)) {
            ++stats.sample_late;
            wake = xTaskGetTickCount();
        }
        vTaskDelayUntil(&wake, pdMS_TO_TICKS(10));
    }
}
void startSampling() {
    ESP_ERROR_CHECK(xTaskCreate(samplingTask, "samples_100Hz", 6144, nullptr, 5, nullptr) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
}
} // namespace logger
extern "C" void app_main(void) {
    // Never erase NVS automatically: configuration and IMU/lap calibration belong
    // to the user.
    esp_err_t nvs = nvs_flash_init_partition("loggercfg");
    if (nvs != ESP_OK)
        ESP_LOGE("logger_v1", "NVS init failed: %s", esp_err_to_name(nvs));
    logger::stateInit();
    logger::loadSettings();
    logger::startStorage();
    logger::startProtocol();
    logger::startCan();
    logger::startSensors();
    logger::startLua();
    logger::startSampling();
    ESP_LOGI("logger_v1", "Production integration booted; real sensors only; "
                          "vehicle CAN listen-only");
}
