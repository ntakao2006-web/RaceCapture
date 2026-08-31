#include "driver/gpio.h"
#include "driver/i2c.h"
#include "driver/uart.h"
#include "esp_log.h"
#include "nvs.h"
#include "state.h"

namespace logger {
static const char *TAG = "sensors";
static uint8_t imu_address = 0;
static portMUX_TYPE pps_lock = portMUX_INITIALIZER_UNLOCKED;
static uint64_t pps_us = 0;
static void IRAM_ATTR ppsInterrupt(void *) {
    uint64_t t = esp_timer_get_time();
    portENTER_CRITICAL_ISR(&pps_lock);
    pps_us = t;
    portEXIT_CRITICAL_ISR(&pps_lock);
}
static bool imuRead(uint8_t reg, uint8_t *data, size_t n) {
    if (!imu_address)
        return false;
    for (unsigned attempt = 0; attempt < 3; ++attempt) {
        if (i2c_master_write_read_device(I2C_NUM_0, imu_address, &reg, 1, data, n,
                                         pdMS_TO_TICKS(100)) == ESP_OK)
            return true;
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    return false;
}
static bool imuWrite(uint8_t reg, const uint8_t *data, size_t n) {
    uint8_t buf[24] = {reg};
    if (n > sizeof(buf) - 1)
        return false;
    memcpy(buf + 1, data, n);
    return imu_address && i2c_master_write_to_device(I2C_NUM_0, imu_address, buf, n + 1,
                                                     pdMS_TO_TICKS(100)) == ESP_OK;
}
static bool imuByte(uint8_t reg, uint8_t value) { return imuWrite(reg, &value, 1); }
static bool initImu() {
    gpio_set_level(GPIO_NUM_7, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(GPIO_NUM_7, 1);
    vTaskDelay(pdMS_TO_TICKS(800));
    uint8_t id = 0;
    imu_address = 0x28;
    if (!imuRead(0, &id, 1) || id != 0xa0) {
        imu_address = 0x29;
        if (!imuRead(0, &id, 1) || id != 0xa0) {
            ESP_LOGW(TAG, "BNO055 chip ID unavailable: 0x%02x SDA=%d SCL=%d", id,
                     gpio_get_level(GPIO_NUM_17), gpio_get_level(GPIO_NUM_18));
            return false;
        }
    }
    uint8_t mode = 0xff;
    if (!imuRead(0x3d, &mode, 1))
        return false;
    ESP_LOGI(TAG, "BNO055 address 0x%02x, post-reset mode 0x%02x", imu_address, mode);
    if (mode != 0) {
        if (!imuByte(0x3d, 0))
            return false;
        vTaskDelay(pdMS_TO_TICKS(25));
    }
    uint8_t offsets[22];
    size_t n = sizeof(offsets);
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READONLY, &h) == ESP_OK) {
        if (nvs_get_blob(h, "imu_offsets", offsets, &n) == ESP_OK && n == sizeof(offsets)) {
            if (!imuWrite(0x55, offsets, sizeof(offsets))) {
                nvs_close(h);
                return false;
            }
            ESP_LOGI(TAG, "BNO055 calibration offsets restored");
        }
        nvs_close(h);
    }
    if (!imuByte(0x3d, 0x0c))
        return false;
    vTaskDelay(pdMS_TO_TICKS(200));
    return imuRead(0x3d, &mode, 1) && mode == 0x0c;
}
static bool persistImu() {
    uint8_t cal = 0;
    if (!imuRead(0x35, &cal, 1) || cal != 255)
        return false;
    if (!imuByte(0x3d, 0))
        return false;
    vTaskDelay(pdMS_TO_TICKS(25));
    uint8_t bytes[22];
    bool ok = imuRead(0x55, bytes, sizeof(bytes));
    bool resumed = imuByte(0x3d, 0x0c);
    vTaskDelay(pdMS_TO_TICKS(20));
    if (!ok || !resumed)
        return false;
    nvs_handle_t h;
    if (nvs_open_from_partition("loggercfg", "logger_v1", NVS_READWRITE, &h) != ESP_OK)
        return false;
    ok = nvs_set_blob(h, "imu_offsets", bytes, sizeof(bytes)) == ESP_OK && nvs_commit(h) == ESP_OK;
    nvs_close(h);
    ESP_LOGI(TAG, "BNO055 complete calibration save: %s", ok ? "OK" : "FAIL");
    return ok;
}
static void imuTask(void *) {
    i2c_config_t cfg = {};
    cfg.mode = I2C_MODE_MASTER;
    cfg.sda_io_num = GPIO_NUM_17;
    cfg.scl_io_num = GPIO_NUM_18;
    cfg.sda_pullup_en = GPIO_PULLUP_ENABLE;
    cfg.scl_pullup_en = GPIO_PULLUP_ENABLE;
    cfg.master.clk_speed = 100000;
    ESP_ERROR_CHECK(i2c_param_config(I2C_NUM_0, &cfg));
    ESP_ERROR_CHECK(i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0));
    gpio_set_direction(GPIO_NUM_7, GPIO_MODE_OUTPUT);
    bool ready = false, saved = false;
    uint32_t consecutive = 0;
    TickType_t last = xTaskGetTickCount();
    while (true) {
        if (!ready) {
            ready = initImu();
            last = xTaskGetTickCount();
            if (!ready) {
                ++stats.imu_errors;
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
        }
        uint8_t bytes[0x33];
        bool ok = imuRead(0x08, bytes, sizeof(bytes));
        uint64_t t = nowUs();
        if (ok) {
            ImuSample s = decodeImu(bytes, sizeof(bytes));
            {
                Guard lock(state_mutex);
                for (unsigned i = 0; i < 3; ++i) {
                    putChannel(ACCEL_X + i, s.accel[i], t, s.valid);
                    putChannel(GYRO_X + i, s.gyro[i], t, s.valid);
                    putChannel(LINEAR_X + i, s.linear[i] / GRAVITY, t, s.valid);
                    putChannel(GRAVITY_X + i, s.gravity[i], t, s.valid);
                }
                putChannel(YAW, s.euler[0], t, s.valid);
                putChannel(ROLL, s.euler[1], t, s.valid);
                putChannel(PITCH, s.euler[2], t, s.valid);
                putChannel(IMU_TEMP, s.temperature, t);
                putChannel(IMU_CAL, s.calibration, t);
                putChannel(IMU_ERR, s.error, t);
                putChannel(IMU_LINK, s.valid ? 1 : 0, t);
            }
            ++stats.imu_samples;
            consecutive = 0;
            bool requested = stats.save_imu.exchange(false);
            if ((requested || (!saved && t > 20000000 && s.calibration == 255)) &&
                s.calibration == 255) {
                saved = persistImu();
                last = xTaskGetTickCount();
            }
        } else {
            ++stats.imu_errors;
            {
                Guard lock(state_mutex);
                putChannel(IMU_LINK, 0, t);
            }
            if (++consecutive >= 10) {
                ready = false;
                consecutive = 0;
            }
        }
        if (xTaskGetTickCount() - last > pdMS_TO_TICKS(10))
            last = xTaskGetTickCount();
        vTaskDelayUntil(&last, pdMS_TO_TICKS(10));
    }
}
static bool sendUbx(uint8_t cls, uint8_t id, const uint8_t *payload, size_t n) {
    if (n > 256)
        return false;
    uint8_t frame[264] = {0xb5, 0x62, cls, id, uint8_t(n), uint8_t(n >> 8)};
    if (n)
        memcpy(frame + 6, payload, n);
    uint8_t a = 0, b = 0;
    for (size_t i = 2; i < n + 6; ++i) {
        a = uint8_t(a + frame[i]);
        b = uint8_t(b + a);
    }
    frame[n + 6] = a;
    frame[n + 7] = b;
    return uart_write_bytes(UART_NUM_1, frame, n + 8) == int(n + 8);
}
static bool waitUbx(UbxParser &parser, uint8_t cls, uint8_t id, uint32_t timeout_ms) {
    uint64_t end = nowUs() + uint64_t(timeout_ms) * 1000;
    while (nowUs() < end) {
        uint8_t bytes[128];
        int n = uart_read_bytes(UART_NUM_1, bytes, sizeof(bytes), pdMS_TO_TICKS(20));
        for (int i = 0; i < n; ++i)
            if (parser.feed(bytes[i]) && parser.cls == cls && parser.id == id)
                return true;
    }
    return false;
}
static bool highPerformanceClock(UbxParser &parser) {
    // Read-only verification sequence from MAX-M10M-00B Integration Manual R03, table 8.
    // Never send UBX-CFG-PMS/OTP programming messages here.
    uint8_t query[20] = {0, 4, 0, 0};
    const uint32_t keys[] = {0x40a40001, 0x40a40003, 0x40a40005, 0x40a4000a};
    for (unsigned i = 0; i < 4; ++i)
        put32(query + 4 + 4 * i, keys[i]);
    sendUbx(6, 0x8b, query, sizeof(query));
    if (!waitUbx(parser, 6, 0x8b, 1000) || parser.length() != 36)
        return false;
    for (unsigned i = 0; i < 4; ++i)
        if (u32(parser.payload.data() + 4 + 8 * i) != keys[i] ||
            u32(parser.payload.data() + 8 + 8 * i) != (i == 3 ? 96000000U : 192000000U))
            return false;
    return true;
}
static bool configureGnss(UbxParser &parser, unsigned hz) {
    // RAM-only changes; the MAX-M10M board intentionally has no backup battery.
    uint8_t rate[128] = {0, 1, 0, 0};
    size_t len = 4;
    auto key = [&](uint32_t id, uint32_t value, unsigned size) {
        put32(rate + len, id);
        len += 4;
        for (unsigned i = 0; i < size; ++i)
            rate[len++] = uint8_t(value >> (8 * i));
    };
    // MAX-M10M datasheet single-GNSS maximum: GPS (including QZSS/SBAS).
    key(0x1031001f, 1, 1);
    key(0x10310021, 0, 1);
    key(0x10310022, 0, 1);
    key(0x10310025, 0, 1);
    key(0x10310024, 1, 1);
    key(0x10310020, 1, 1);
    sendUbx(6, 0x8a, rate, len);
    if (!waitUbx(parser, 5, 1, 1000) || parser.length() != 2 || parser.payload[0] != 6 ||
        parser.payload[1] != 0x8a)
        return false;
    vTaskDelay(pdMS_TO_TICKS(600)); // constellation changes restart the GNSS engine
    len = 4;
    key(0x10740001, 1, 1); // UART1 UBX output
    key(0x10740002, 0, 1); // disable NMEA output (bandwidth)
    key(0x20910007, 1, 1); // NAV-PVT every navigation solution
    key(0x30210001, (1000 + hz - 1) / hz, 2);
    key(0x30210002, 1, 2); // 56 ms for 18 Hz; 40 ms for 25 Hz
    key(0x20110021, 4, 1); // automotive dynamic platform
    sendUbx(6, 0x8a, rate, len);
    if (!waitUbx(parser, 5, 1, 1000) || parser.length() != 2 || parser.payload[0] != 6 ||
        parser.payload[1] != 0x8a)
        return false;
    return true;
}
static void gnssTask(void *) {
    uart_config_t cfg = {};
    cfg.baud_rate = 9600;
    cfg.data_bits = UART_DATA_8_BITS;
    cfg.parity = UART_PARITY_DISABLE;
    cfg.stop_bits = UART_STOP_BITS_1;
    cfg.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    cfg.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 8192, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &cfg));
    ESP_ERROR_CHECK(
        uart_set_pin(UART_NUM_1, GPIO_NUM_16, GPIO_NUM_15, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    gpio_set_direction(GPIO_NUM_9,
                       GPIO_MODE_INPUT); // never drive TIMEPULSE/SAFEBOOT during startup
    gpio_config_t pps = {};
    pps.pin_bit_mask = 1ULL << 8;
    pps.mode = GPIO_MODE_INPUT;
    pps.intr_type = GPIO_INTR_POSEDGE;
    gpio_config(&pps);
    gpio_install_isr_service(0);
    gpio_isr_handler_add(GPIO_NUM_8, ppsInterrupt, nullptr);
    UbxParser parser;
    uint64_t last_pvt = 0;
    uint32_t previous_tow = UINT32_MAX;
    bool configured = false;
    while (true) {
        if (!configured) {
            bool found = false;
            for (int baud : {9600, 115200, 38400, 57600}) {
                uart_set_baudrate(UART_NUM_1, baud);
                uart_flush_input(UART_NUM_1);
                parser.reset();
                sendUbx(0x0a, 4, nullptr, 0);
                if (waitUbx(parser, 0x0a, 4, 600) && parser.length() >= 40) {
                    found = true;
                    ESP_LOGI(TAG, "MAX-M10M found at %d baud", baud);
                    ESP_LOGI(TAG, "GNSS SW %.30s HW %.10s",
                             reinterpret_cast<char *>(parser.payload.data()),
                             reinterpret_cast<char *>(parser.payload.data() + 30));
                    break;
                }
            }
            if (!found) {
                ++stats.gnss_errors;
                vTaskDelay(pdMS_TO_TICKS(1000));
                continue;
            }
            uint8_t baud_payload[12] = {0, 1, 0, 0};
            put32(baud_payload + 4, 0x40520001);
            put32(baud_payload + 8, 115200);
            sendUbx(6, 0x8a, baud_payload, sizeof(baud_payload));
            uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(100));
            vTaskDelay(pdMS_TO_TICKS(100));
            uart_set_baudrate(UART_NUM_1, 115200);
            uart_flush_input(UART_NUM_1);
            parser.reset();
            const unsigned hz = highPerformanceClock(parser) ? 25 : 18;
            {
                Guard lock(state_mutex);
                config.gnss_hz = hz;
                for (unsigned id : {LAT, LON, GPS_SPEED, ALTITUDE, GPS_HACC, GPS_SATS, GPS_FIX,
                                    UTC_VALID, GPS_TOW, GPS_UTC, GPS_TACC, PPS_AGE})
                    channels[id].rate = hz;
                ++schema_revision;
            }
            configured = configureGnss(parser, hz);
            last_pvt = nowUs();
            if (!configured) {
                ++stats.gnss_errors;
                continue;
            }
            ESP_LOGI(TAG, "GNSS continuous NAV-PVT requested %u Hz", hz);
        }
        uint8_t bytes[256];
        int n = uart_read_bytes(UART_NUM_1, bytes, sizeof(bytes), pdMS_TO_TICKS(20));
        for (int i = 0; i < n; ++i)
            if (parser.feed(bytes[i]) && parser.cls == 1 && parser.id == 7) {
                Pvt p;
                if (!decodePvt(parser.payload.data(), parser.length(), p))
                    continue;
                uint64_t t = nowUs();
                last_pvt = t;
                if (p.tow_ms == previous_tow)
                    continue;
                previous_tow = p.tow_ms;
                ++stats.gps_samples;
                uint64_t pulse;
                portENTER_CRITICAL(&pps_lock);
                pulse = pps_us;
                portEXIT_CRITICAL(&pps_lock);
                Guard lock(state_mutex);
                putChannel(GNSS_LINK, 1, t);
                putChannel(GPS_FIX, p.fix_ok ? p.fix : 0, t);
                putChannel(GPS_SATS, p.satellites, t);
                putChannel(LAT, p.lat, t, p.fix_ok);
                putChannel(LON, p.lon, t, p.fix_ok);
                putChannel(GPS_SPEED, p.speed * 3.6, t, p.fix_ok);
                putChannel(ALTITUDE, p.altitude, t, p.fix_ok);
                putChannel(GPS_HACC, p.hacc, t, p.fix_ok);
                // CAN speed takes precedence only while it is fresh; otherwise use
                // GNSS.
                bool can_speed = config.nc_profile;
                for (const auto &mapping : config.mappings)
                    if (mapping.enabled && mapping.channel == SPEED)
                        can_speed = true;
                if (!can_speed)
                    putChannel(SPEED, p.speed * 3.6, t, p.fix_ok);
                putChannel(UTC_VALID, p.utc_valid ? 1 : 0, t);
                putChannel(GPS_TOW, p.tow_ms, t);
                putChannel(GPS_UTC, p.utc_us / 1e6, t, p.utc_valid);
                putChannel(GPS_TACC, p.time_accuracy_ns, t, p.utc_valid);
                putChannel(PPS_AGE, pulse && t >= pulse ? (t - pulse) / 1000.0 : 0, t,
                           pulse && t >= pulse && t - pulse < 2000000);
                if (p.utc_valid) {
                    uint64_t frac = uint64_t((p.utc_us % 1000000 + 1000000) % 1000000);
                    // When PPS corresponds to this UTC second, remove UART delivery
                    // latency.
                    if (pulse && t >= pulse + frac && t - pulse - frac < 300000)
                        utc_offset = p.utc_us - int64_t(pulse + frac);
                    else
                        utc_offset =
                            p.utc_us -
                            int64_t(t); // coarse fallback; raw PVT timestamp is still exact
                    utc_updated = t;
                }
                bool reset = stats.reset_laps.exchange(false);
                if (!(laps->track == config.track) || reset) {
                    laps->reset(config.track);
                    if (reset)
                        laps->best_changed = true;
                }
                laps->update(p.lat, p.lon, p.utc_valid ? p.utc_us / 1e6 : t / 1e6, p.speed, p.hacc,
                             p.fix_ok);
            }
        if (nowUs() - last_pvt > 3000000) {
            configured = false;
            ++stats.gnss_errors;
            Guard lock(state_mutex);
            putChannel(GNSS_LINK, 0, nowUs());
            laps->invalidate();
        }
    }
}
void startSensors() {
    ESP_ERROR_CHECK(
        xTaskCreate(imuTask, "imu", 6144, nullptr, 5, nullptr) == pdPASS ? ESP_OK : ESP_ERR_NO_MEM);
    ESP_ERROR_CHECK(xTaskCreate(gnssTask, "gnss", 8192, nullptr, 5, nullptr) == pdPASS
                        ? ESP_OK
                        : ESP_ERR_NO_MEM);
}
} // namespace logger
