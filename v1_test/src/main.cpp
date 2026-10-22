#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <sys/statvfs.h>
#include <unistd.h>

#include <ArduinoJson.h>
#include "driver/gpio.h"
#include "driver/i2c.h"
#include "driver/sdmmc_host.h"
#include "driver/spi_master.h"
#include "driver/temperature_sensor.h"
#include "driver/twai.h"
#include "driver/uart.h"
#include "esp_chip_info.h"
#include "esp_err.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_private/esp_clk.h"
#include "esp_rom_sys.h"
#include "esp_timer.h"
#include "esp_vfs_fat.h"
#include "freertos/FreeRTOS.h"
#include "freertos/stream_buffer.h"
#include "freertos/task.h"
#include "sdmmc_cmd.h"
#include "tinyusb.h"
#include "tusb_cdc_acm.h"

namespace {

static const char *TAG = "logger_v1_test";

constexpr gpio_num_t LED_SER = GPIO_NUM_40;
constexpr gpio_num_t LED_CLK = GPIO_NUM_39;
constexpr gpio_num_t LED_LATCH = GPIO_NUM_45;
constexpr gpio_num_t SD_CLK = GPIO_NUM_11;
constexpr gpio_num_t SD_CMD = GPIO_NUM_10;
constexpr gpio_num_t SD_D0 = GPIO_NUM_12;
constexpr gpio_num_t SD_D1 = GPIO_NUM_13;
constexpr gpio_num_t SD_D2 = GPIO_NUM_14;
constexpr gpio_num_t SD_D3 = GPIO_NUM_21;
constexpr gpio_num_t GNSS_RX = GPIO_NUM_15;
constexpr gpio_num_t GNSS_TX = GPIO_NUM_16;
constexpr gpio_num_t GNSS_RESET_N = GPIO_NUM_9;
constexpr gpio_num_t GNSS_TIMEPULSE = GPIO_NUM_8;
constexpr gpio_num_t IMU_RESET_N = GPIO_NUM_7;
constexpr gpio_num_t IMU_I2C_SDA = GPIO_NUM_17;  // Module pin 3 SDA/T
constexpr gpio_num_t IMU_I2C_SCL = GPIO_NUM_18;  // Module pin 4 SCL/R
constexpr i2c_port_t IMU_I2C_PORT = I2C_NUM_0;
constexpr uint32_t IMU_I2C_HZ = 100000;
constexpr gpio_num_t CAN1_RX = GPIO_NUM_1;
constexpr gpio_num_t CAN1_TX = GPIO_NUM_2;
constexpr gpio_num_t CAN2_RESET = GPIO_NUM_4;
constexpr gpio_num_t CAN2_SCK = GPIO_NUM_39;
constexpr gpio_num_t CAN2_MOSI = GPIO_NUM_40;
constexpr gpio_num_t CAN2_MISO = GPIO_NUM_41;
constexpr gpio_num_t CAN2_CS = GPIO_NUM_42;
constexpr gpio_num_t OTG_VBUS_SENSE = GPIO_NUM_6;
constexpr gpio_num_t OTG_OC_N = GPIO_NUM_38;
constexpr gpio_num_t OTG_ROLE = GPIO_NUM_48;

constexpr size_t SD_TEST_BYTES = 8U * 1024U * 1024U;
constexpr size_t SD_CHUNK_BYTES = 32U * 1024U;
constexpr float STRESS_CUTOFF_C = 85.0F;
constexpr int GNSS_BAUD_RATES[] = {9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600};

struct Diagnostics {
    bool psram = false;
    bool imu = false;
    bool can1 = false;
    bool can2 = false;
    bool can_external = false;
    bool gnss = false;
    bool gnss_fix = false;
    bool gnss_rx = false;
    bool sd = false;
    bool sd_40mhz = false;
    float temp_c = NAN;
    float max_temp_c = NAN;
    float sd_write_mib_s = 0;
    float sd_read_mib_s = 0;
    uint32_t cpu_mhz = 0;
    uint32_t gnss_bytes = 0;
    uint32_t gnss_baud = 0;
    uint8_t gnss_fix_type = 0;
    uint8_t gnss_num_sv = 0;
    double gnss_latitude = 0;
    double gnss_longitude = 0;
    float gnss_speed_mps = 0;
    uint8_t imu_address = 0;
    uint8_t imu_calibration = 0;
    uint8_t imu_system_status = 0;
    uint8_t imu_system_error = 0;
    uint8_t imu_sda_idle = 0;
    uint8_t imu_scl_idle = 0;
    float imu_yaw_deg = 0;
    float imu_pitch_deg = 0;
    float imu_roll_deg = 0;
    float imu_accel_x = 0;
    float imu_accel_y = 0;
    float imu_accel_z = 0;
    float imu_gyro_x = 0;
    float imu_gyro_y = 0;
    float imu_gyro_z = 0;
    float imu_temp_c = 0;
    char gnss_version[64] = "no response";
};

Diagnostics diag;
temperature_sensor_handle_t temp_sensor = nullptr;
volatile bool stress_enabled = true;
volatile uint32_t stress_sink[2] = {};
bool gnss_tx_net_safe = true;
TaskHandle_t led_task_handle = nullptr;
uint8_t imu_i2c_address = 0;

constexpr uint8_t BNO055_CHIP_ID_REG = 0x00;
constexpr uint8_t BNO055_CHIP_ID = 0xA0;
constexpr uint8_t BNO055_ACCEL_DATA_X_LSB_REG = 0x08;
constexpr uint8_t BNO055_GYRO_DATA_X_LSB_REG = 0x14;
constexpr uint8_t BNO055_EULER_H_LSB_REG = 0x1A;
constexpr uint8_t BNO055_TEMP_REG = 0x34;
constexpr uint8_t BNO055_CALIB_STAT_REG = 0x35;
constexpr uint8_t BNO055_SYS_STATUS_REG = 0x39;
constexpr uint8_t BNO055_OPR_MODE_REG = 0x3D;

int16_t signed_le16(const uint8_t *bytes)
{
    return static_cast<int16_t>(static_cast<uint16_t>(bytes[0]) |
                                (static_cast<uint16_t>(bytes[1]) << 8));
}

bool imu_probe_address(uint8_t address)
{
    i2c_cmd_handle_t command = i2c_cmd_link_create();
    if (!command) return false;
    i2c_master_start(command);
    i2c_master_write_byte(command, static_cast<uint8_t>((address << 1) | I2C_MASTER_WRITE), true);
    i2c_master_stop(command);
    const esp_err_t result = i2c_master_cmd_begin(IMU_I2C_PORT, command, pdMS_TO_TICKS(50));
    i2c_cmd_link_delete(command);
    return result == ESP_OK;
}

bool imu_read_registers(uint8_t reg, uint8_t *data, size_t length)
{
    if (!length || length > 128) return false;
    if (!imu_i2c_address) return false;
    for (unsigned attempt = 0; attempt < 3; ++attempt) {
        if (i2c_master_write_read_device(IMU_I2C_PORT, imu_i2c_address,
                                         &reg, 1, data, length,
                                         pdMS_TO_TICKS(100)) == ESP_OK) return true;
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    return false;
}

bool imu_write_register(uint8_t reg, uint8_t value)
{
    const uint8_t bytes[] = {reg, value};
    return imu_i2c_address != 0 &&
           i2c_master_write_to_device(IMU_I2C_PORT, imu_i2c_address,
                                      bytes, sizeof(bytes),
                                      pdMS_TO_TICKS(100)) == ESP_OK;
}

void imu_task(void *)
{
    // The mode register changes quickly, but the first complete fused sample
    // can lag behind it. Keep the acquisition loop out of that transition.
    vTaskDelay(pdMS_TO_TICKS(200));
    uint32_t sample_count = 0;
    uint32_t consecutive_errors = 0;
    while (true) {
        uint8_t accel[6] = {};
        uint8_t gyro[6] = {};
        uint8_t euler[6] = {};
        uint8_t temp = 0;
        uint8_t calibration = 0;
        uint8_t system[2] = {};
        const bool ok =
            imu_read_registers(BNO055_ACCEL_DATA_X_LSB_REG, accel, sizeof(accel)) &&
            imu_read_registers(BNO055_GYRO_DATA_X_LSB_REG, gyro, sizeof(gyro)) &&
            imu_read_registers(BNO055_EULER_H_LSB_REG, euler, sizeof(euler)) &&
            imu_read_registers(BNO055_TEMP_REG, &temp, 1) &&
            imu_read_registers(BNO055_CALIB_STAT_REG, &calibration, 1) &&
            imu_read_registers(BNO055_SYS_STATUS_REG, system, sizeof(system));

        if (ok) {
            diag.imu_accel_x = signed_le16(&accel[0]) / 100.0F;
            diag.imu_accel_y = signed_le16(&accel[2]) / 100.0F;
            diag.imu_accel_z = signed_le16(&accel[4]) / 100.0F;
            diag.imu_gyro_x = signed_le16(&gyro[0]) / 16.0F;
            diag.imu_gyro_y = signed_le16(&gyro[2]) / 16.0F;
            diag.imu_gyro_z = signed_le16(&gyro[4]) / 16.0F;
            diag.imu_yaw_deg = signed_le16(&euler[0]) / 16.0F;
            diag.imu_roll_deg = signed_le16(&euler[2]) / 16.0F;
            diag.imu_pitch_deg = signed_le16(&euler[4]) / 16.0F;
            diag.imu_temp_c = static_cast<int8_t>(temp);
            diag.imu_calibration = calibration;
            diag.imu_system_status = system[0];
            // Bosch specifies SYS_ERR as valid only when SYS_STATUS is 0x01
            // (System Error). In the normal 0x05 fusion-running state the
            // byte may retain a stale value and must not be reported as an
            // active fault.
            diag.imu_system_error = system[0] == 0x01 ? system[1] : 0;
            diag.imu = true;
            consecutive_errors = 0;
            if ((++sample_count % 100U) == 0U) {
                ESP_LOGI(TAG,
                         "IMU I2C chip=0x%02X Euler(H/R/P)=%.1f/%.1f/%.1f deg "
                         "Accel=%.2f/%.2f/%.2f m/s2 Gyro=%.1f/%.1f/%.1f dps "
                         "temp=%.0fC calib=0x%02X sys=%u err=%u",
                         diag.imu_address, diag.imu_yaw_deg, diag.imu_roll_deg,
                         diag.imu_pitch_deg, diag.imu_accel_x, diag.imu_accel_y,
                         diag.imu_accel_z, diag.imu_gyro_x, diag.imu_gyro_y,
                         diag.imu_gyro_z, diag.imu_temp_c, diag.imu_calibration,
                         diag.imu_system_status, diag.imu_system_error);
            }
        } else {
            diag.imu = false;
            if (++consecutive_errors == 1U || (consecutive_errors % 100U) == 0U) {
                ESP_LOGE(TAG, "BNO055 I2C read failed (%lu consecutive)",
                         static_cast<unsigned long>(consecutive_errors));
            }
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

bool init_imu()
{
    gpio_config_t reset = {};
    reset.pin_bit_mask = 1ULL << IMU_RESET_N;
    reset.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&reset));
    gpio_set_level(IMU_RESET_N, 0);
    vTaskDelay(pdMS_TO_TICKS(20));

    i2c_config_t config = {};
    config.mode = I2C_MODE_MASTER;
    config.sda_io_num = IMU_I2C_SDA;
    config.scl_io_num = IMU_I2C_SCL;
    config.sda_pullup_en = GPIO_PULLUP_ENABLE;
    config.scl_pullup_en = GPIO_PULLUP_ENABLE;
    config.master.clk_speed = IMU_I2C_HZ;
    config.clk_flags = 0;
    if (i2c_param_config(IMU_I2C_PORT, &config) != ESP_OK ||
        i2c_driver_install(IMU_I2C_PORT, I2C_MODE_MASTER, 0, 0, 0) != ESP_OK) {
        ESP_LOGE(TAG, "BNO055 I2C initialization failed");
        return false;
    }

    gpio_set_level(IMU_RESET_N, 1);
    vTaskDelay(pdMS_TO_TICKS(800));

    diag.imu_sda_idle = gpio_get_level(IMU_I2C_SDA);
    diag.imu_scl_idle = gpio_get_level(IMU_I2C_SCL);
    for (const uint8_t address : {static_cast<uint8_t>(0x28), static_cast<uint8_t>(0x29)}) {
        if (imu_probe_address(address)) {
            imu_i2c_address = address;
            break;
        }
    }
    if (!imu_i2c_address) {
        ESP_LOGE(TAG, "BNO055 I2C no ACK at 0x28/0x29 (SDA=GPIO%d level=%u, SCL=GPIO%d level=%u)",
                 IMU_I2C_SDA, diag.imu_sda_idle, IMU_I2C_SCL, diag.imu_scl_idle);
        return false;
    }
    ESP_LOGI(TAG, "BNO055 I2C ACK at 0x%02X (100 kHz)", imu_i2c_address);

    uint8_t chip_id = 0;
    bool chip_ok = false;
    for (unsigned attempt = 1; attempt <= 5; ++attempt) {
        chip_id = 0;
        if (imu_read_registers(BNO055_CHIP_ID_REG, &chip_id, 1) &&
            chip_id == BNO055_CHIP_ID) {
            chip_ok = true;
            break;
        }
        ESP_LOGW(TAG, "BNO055 I2C chip-ID attempt %u/5 failed (got 0x%02X)", attempt, chip_id);
        vTaskDelay(pdMS_TO_TICKS(200));
    }
    if (!chip_ok) {
        ESP_LOGE(TAG,
                 "BNO055 I2C no valid chip ID (got 0x%02X, SDA=GPIO%d level=%u, SCL=GPIO%d level=%u)",
                 chip_id, IMU_I2C_SDA, diag.imu_sda_idle, IMU_I2C_SCL, diag.imu_scl_idle);
        return false;
    }
    diag.imu_address = chip_id;
    ESP_LOGI(TAG, "BNO055 I2C PASS: address 0x%02X, chip ID 0x%02X (SDA=%d SCL=%d)",
             imu_i2c_address, chip_id, IMU_I2C_SDA, IMU_I2C_SCL);

    // A hardware reset already leaves the BNO055 in page 0, normal power,
    // CONFIG mode and metric/degree units. Avoid redundant writes here: they
    // can obscure the exact source if the device reports a register-map write
    // error. Only the requested fusion mode needs to change.
    uint8_t mode_before = 0xFF;
    if (!imu_read_registers(BNO055_OPR_MODE_REG, &mode_before, 1)) return false;
    ESP_LOGI(TAG, "BNO055 mode after hardware reset: 0x%02X", mode_before);
    if (mode_before != 0x00) {
        if (!imu_write_register(BNO055_OPR_MODE_REG, 0x00)) return false;
        vTaskDelay(pdMS_TO_TICKS(25));
    }
    if (!imu_write_register(BNO055_OPR_MODE_REG, 0x0C)) return false;
    vTaskDelay(pdMS_TO_TICKS(50));

    uint8_t mode_after = 0;
    uint8_t system[2] = {};
    if (!imu_read_registers(BNO055_OPR_MODE_REG, &mode_after, 1) ||
        !imu_read_registers(BNO055_SYS_STATUS_REG, system, sizeof(system))) return false;
    ESP_LOGI(TAG, "BNO055 NDOF readback: mode=0x%02X sys=%u raw_err=%u",
             mode_after, system[0], system[1]);
    if (mode_after != 0x0C || system[0] == 0x01) {
        diag.imu_system_status = system[0];
        diag.imu_system_error = system[1];
        ESP_LOGE(TAG, "BNO055 initialization status invalid: mode=0x%02X sys=%u err=%u",
                 mode_after, system[0], system[1]);
        return false;
    }

    diag.imu = true;
    xTaskCreate(imu_task, "bno055", 4096, nullptr, 2, nullptr);
    return true;
}

void hc595_write(uint8_t value)
{
    for (int bit = 7; bit >= 0; --bit) {
        gpio_set_level(LED_SER, (value >> bit) & 1U);
        gpio_set_level(LED_CLK, 1);
        gpio_set_level(LED_CLK, 0);
    }
    gpio_set_level(LED_LATCH, 1);
    gpio_set_level(LED_LATCH, 0);
}

void led_task(void *)
{
    gpio_config_t config = {};
    config.pin_bit_mask = (1ULL << LED_SER) | (1ULL << LED_CLK) | (1ULL << LED_LATCH);
    config.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&config));
    ESP_LOGI(TAG, "74HC595 walking-one LED test started (SER=%d CLK=%d LATCH=%d)",
             LED_SER, LED_CLK, LED_LATCH);
    while (true) {
        for (int i = 0; i < 8; ++i) {
            hc595_write(static_cast<uint8_t>(1U << i));
            vTaskDelay(pdMS_TO_TICKS(120));
        }
        for (int i = 6; i >= 1; --i) {
            hc595_write(static_cast<uint8_t>(1U << i));
            vTaskDelay(pdMS_TO_TICKS(120));
        }
    }
}

void start_led_task()
{
    if (!led_task_handle) {
        ESP_ERROR_CHECK(xTaskCreate(led_task, "knight_rider", 2048, nullptr, 2,
                                    &led_task_handle) == pdPASS ? ESP_OK : ESP_FAIL);
    }
}

void stop_led_task_for_can()
{
    if (!led_task_handle) return;
    vTaskSuspend(led_task_handle);
    hc595_write(0);
    vTaskDelete(led_task_handle);
    led_task_handle = nullptr;
    ESP_ERROR_CHECK(gpio_reset_pin(LED_SER));
    ESP_ERROR_CHECK(gpio_reset_pin(LED_CLK));
    ESP_ERROR_CHECK(gpio_reset_pin(LED_LATCH));
    ESP_LOGI(TAG, "74HC595 paused briefly while CAN2 owns shared GPIO39/40");
}

void stress_task(void *argument)
{
    const uintptr_t core = reinterpret_cast<uintptr_t>(argument);
    uint32_t x = 0x9E3779B9U ^ static_cast<uint32_t>(core * 0x13579BDFU);
    uint32_t accumulator = 0;
    while (stress_enabled) {
        for (uint32_t i = 0; i < 262144U; ++i) {
            x ^= x << 13;
            x ^= x >> 17;
            x ^= x << 5;
            accumulator = ((accumulator << 7) | (accumulator >> 25)) + (x ^ i);
        }
        stress_sink[core] = accumulator;
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    vTaskDelete(nullptr);
}

void temperature_task(void *)
{
    while (true) {
        float value = NAN;
        if (temperature_sensor_get_celsius(temp_sensor, &value) == ESP_OK) {
            diag.temp_c = value;
            if (std::isnan(diag.max_temp_c) || value > diag.max_temp_c) diag.max_temp_c = value;
            if (value >= STRESS_CUTOFF_C && stress_enabled) {
                stress_enabled = false;
                ESP_LOGE(TAG, "temperature %.1f C reached %.1f C cutoff; stress stopped",
                         value, STRESS_CUTOFF_C);
            }
        }
        ESP_LOGI(TAG, "health cpu=%luMHz temp=%.1fC max=%.1fC stress=%s OTG(vbus=%d role=%d oc_n=%d)",
                 static_cast<unsigned long>(diag.cpu_mhz), diag.temp_c, diag.max_temp_c,
                 stress_enabled ? "ON" : "OFF", gpio_get_level(OTG_VBUS_SENSE),
                 gpio_get_level(OTG_ROLE), gpio_get_level(OTG_OC_N));
        vTaskDelay(pdMS_TO_TICKS(5000));
    }
}

// Native USB CDC carries only RaceCapture JSON; UART0 carries diagnostics.
constexpr size_t RCP_LINE_BYTES = 8192;
StreamBufferHandle_t usb_rx_stream = nullptr;

void cdc_rx_callback(int interface_number, cdcacm_event_t *)
{
    uint8_t buffer[128];
    size_t received = 0;
    if (tinyusb_cdcacm_read(static_cast<tinyusb_cdcacm_itf_t>(interface_number),
                            buffer, sizeof(buffer), &received) == ESP_OK && received) {
        xStreamBufferSend(usb_rx_stream, buffer, received, 0);
    }
}

void usb_write_all(const uint8_t *data, size_t length)
{
    size_t written = 0;
    while (written < length) {
        size_t queued = tinyusb_cdcacm_write_queue(TINYUSB_CDC_ACM_0,
                                                    data + written, length - written);
        if (!queued) {
            tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, pdMS_TO_TICKS(1000));
            continue;
        }
        written += queued;
    }
    tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, pdMS_TO_TICKS(1000));
}

void send_json(JsonDocument &document, bool uart_transport)
{
    char *output = static_cast<char *>(malloc(RCP_LINE_BYTES));
    if (!output) {
        ESP_LOGE(TAG, "RaceCapture response allocation failed");
        return;
    }
    size_t length = serializeJson(document, output, RCP_LINE_BYTES - 2);
    if (length >= RCP_LINE_BYTES - 2) {
        ESP_LOGE(TAG, "RaceCapture JSON response exceeded %u-byte buffer",
                 static_cast<unsigned>(RCP_LINE_BYTES));
        free(output);
        return;
    }
    output[length++] = '\r';
    output[length++] = '\n';
    if (uart_transport) uart_write_bytes(UART_NUM_0, output, length);
    else usb_write_all(reinterpret_cast<const uint8_t *>(output), length);
    free(output);
}

struct Channel { const char *name; const char *unit; float min; float max; int prec; int rate; };
constexpr Channel CHANNELS[] = {
    {"RPM", "rpm", 0, 10000, 0, 10}, {"Speed", "mph", 0, 200, 1, 10},
    {"WaterTemp", "F", 0, 300, 0, 5}, {"OilPress", "psi", 0, 150, 1, 5},
    {"Lat", "deg", -90, 90, 6, 10}, {"Lon", "deg", -180, 180, 6, 10},
    {"CpuTemp", "C", -40, 125, 1, 5}, {"CpuMHz", "MHz", 0, 240, 0, 1},
    {"SDWrite", "MiB/s", 0, 50, 2, 1}, {"SDRead", "MiB/s", 0, 50, 2, 1},
    {"GNSSLink", "bool", 0, 1, 0, 1}, {"CAN1Self", "bool", 0, 1, 0, 1},
    {"CAN2Loop", "bool", 0, 1, 0, 1}, {"CANWire", "bool", 0, 1, 0, 1},
    {"SDPass", "bool", 0, 1, 0, 1},
    {"IMULink", "bool", 0, 1, 0, 10}, {"Yaw", "deg", -360, 360, 1, 10},
    {"Pitch", "deg", -180, 180, 1, 10}, {"Roll", "deg", -180, 180, 1, 10},
    {"AccelX", "m/s2", -200, 200, 2, 10}, {"AccelY", "m/s2", -200, 200, 2, 10},
    {"AccelZ", "m/s2", -200, 200, 2, 10}, {"GyroX", "deg/s", -2000, 2000, 1, 10},
    {"GyroY", "deg/s", -2000, 2000, 1, 10}, {"GyroZ", "deg/s", -2000, 2000, 1, 10},
    {"IMUTemp", "C", -40, 125, 0, 1}, {"IMUCal", "raw", 0, 255, 0, 1},
    {"IMUChip", "raw", 0, 255, 0, 1}, {"IMUSDA", "bool", 0, 1, 0, 1},
    {"IMUSCL", "bool", 0, 1, 0, 1}, {"IMUErr", "raw", 0, 255, 0, 1},
};

void add_meta(JsonArray array)
{
    for (const auto &channel : CHANNELS) {
        JsonObject object = array.add<JsonObject>();
        object["nm"] = channel.name; object["ut"] = channel.unit;
        object["min"] = channel.min; object["max"] = channel.max;
        object["prec"] = channel.prec; object["sr"] = channel.rate;
    }
}

void send_version(bool uart_transport)
{
    JsonDocument doc;
    JsonObject version = doc["ver"].to<JsonObject>();
    version["name"] = "RCPMK3";
    version["fname"] = "logger_v1 diagnostics + simulated telemetry";
    version["major"] = 2; version["minor"] = 16; version["bugfix"] = 1;
    version["serial"] = "LOGGER-V1-TEST";
    version["git_info"] = "v1_test-sim-telemetry";
    version["release_type"] = "release";
    send_json(doc, uart_transport);
}

void send_capabilities(bool uart_transport)
{
    JsonDocument doc;
    JsonObject cap = doc["capabilities"].to<JsonObject>();
    cap["flags"].to<JsonArray>();
    JsonObject channels = cap["channels"].to<JsonObject>();
    channels["analog"] = 0; channels["imu"] = 1; channels["gpio"] = 0;
    channels["timer"] = 0; channels["pwm"] = 0; channels["can"] = 0;
    channels["obd2"] = 0; channels["canChan"] = 0;
    JsonObject rates = cap["sampleRates"].to<JsonObject>();
    rates["gps"] = 10; rates["sensor"] = 1000;
    JsonObject db = cap["db"].to<JsonObject>(); db["tracks"] = 0; db["sectors"] = 0;
    send_json(doc, uart_transport);
}

void send_status(bool uart_transport)
{
    JsonDocument doc;
    JsonObject status = doc["status"].to<JsonObject>();
    JsonObject sys = status["system"].to<JsonObject>();
    sys["model"] = "logger_v1 diagnostics + simulated telemetry";
    sys["ver_major"] = 2; sys["ver_minor"] = 16; sys["ver_bugfix"] = 1;
    sys["uptime"] = static_cast<int64_t>(esp_timer_get_time() / 1000000LL);
    JsonObject gps = status["GPS"].to<JsonObject>();
    gps["init"] = diag.gnss ? 3 : 0; gps["qual"] = diag.gnss_fix ? diag.gnss_fix_type : 0;
    gps["lat"] = diag.gnss_latitude; gps["lon"] = diag.gnss_longitude;
    gps["sats"] = diag.gnss_num_sv; gps["DOP"] = 0;
    JsonObject logging = status["logging"].to<JsonObject>(); logging["status"] = 0; logging["dur"] = 0;
    JsonObject track = status["track"].to<JsonObject>();
    track["status"] = 0; track["valid"] = false; track["trackId"] = 0;
    track["inLap"] = 0; track["armed"] = 0;
    send_json(doc, uart_transport);
}

void send_sample(bool with_meta, bool uart_transport)
{
    const double seconds = static_cast<double>(esp_timer_get_time()) / 1000000.0;
    const int rpm = static_cast<int>(3000.0 + 2000.0 * sin(seconds / 3.0));
    const double speed = 60.0 + 40.0 * sin(seconds / 5.0);
    const int water_temp = static_cast<int>(180.0 + 10.0 * sin(seconds / 7.0));
    const double oil_press = 40.0 + 5.0 * sin(seconds / 4.0);
    const double latitude = diag.gnss_fix ? diag.gnss_latitude : 0.0;
    const double longitude = diag.gnss_fix ? diag.gnss_longitude : 0.0;

    JsonDocument doc;
    JsonObject sample = doc["s"].to<JsonObject>();
    sample["t"] = static_cast<uint32_t>(esp_timer_get_time() / 100000ULL);
    JsonArray data = sample["d"].to<JsonArray>();
    data.add(rpm); data.add(speed); data.add(water_temp); data.add(oil_press);
    data.add(latitude); data.add(longitude);
    data.add(diag.temp_c); data.add(diag.cpu_mhz); data.add(diag.sd_write_mib_s);
    data.add(diag.sd_read_mib_s); data.add(diag.gnss ? 1 : 0); data.add(diag.can1 ? 1 : 0);
    data.add(diag.can2 ? 1 : 0); data.add(diag.can_external ? 1 : 0); data.add(diag.sd ? 1 : 0);
    data.add(diag.imu ? 1 : 0); data.add(diag.imu_yaw_deg); data.add(diag.imu_pitch_deg);
    data.add(diag.imu_roll_deg); data.add(diag.imu_accel_x); data.add(diag.imu_accel_y);
    data.add(diag.imu_accel_z); data.add(diag.imu_gyro_x); data.add(diag.imu_gyro_y);
    data.add(diag.imu_gyro_z); data.add(diag.imu_temp_c); data.add(diag.imu_calibration);
    data.add(diag.imu_address); data.add(diag.imu_sda_idle); data.add(diag.imu_scl_idle);
    data.add(diag.imu_system_error);
    data.add((1U << std::size(CHANNELS)) - 1U);
    if (with_meta) add_meta(sample["meta"].to<JsonArray>());
    send_json(doc, uart_transport);
}

void send_empty(const char *key, bool uart_transport)
{
    JsonDocument doc;
    doc[key].to<JsonObject>();
    send_json(doc, uart_transport);
}

void handle_rcp(JsonDocument &doc, bool uart_transport)
{
    JsonObject root = doc.as<JsonObject>();
    if (root.isNull() || root.begin() == root.end()) return;
    auto entry = root.begin();
    const char *command = entry->key().c_str();
    JsonVariant value = entry->value();
    ESP_LOGI(TAG, "RCP command: %s", command);
    if (!strcmp(command, "getVer")) send_version(uart_transport);
    else if (!strcmp(command, "getCapabilities")) send_capabilities(uart_transport);
    else if (!strcmp(command, "getMeta")) {
        JsonDocument out; add_meta(out["meta"].to<JsonArray>()); send_json(out, uart_transport);
    }
    else if (!strcmp(command, "getStatus")) send_status(uart_transport);
    else if (!strcmp(command, "s"))
        send_sample(value.is<JsonObject>() && value["meta"].as<bool>(), uart_transport);
    else if (!strcmp(command, "log")) {
        JsonDocument out; out[value.as<bool>() ? "logStart" : "logEnd"] = 1;
        send_json(out, uart_transport);
    }
    else if (!strcmp(command, "getLapCfg")) send_empty("lapCfg", uart_transport);
    else if (!strcmp(command, "getTrackCfg")) send_empty("trackCfg", uart_transport);
    else if (!strcmp(command, "getCanCfg")) send_empty("canCfg", uart_transport);
    else if (!strcmp(command, "getObd2Cfg")) send_empty("obd2Cfg", uart_transport);
    else if (!strcmp(command, "getConnCfg")) send_empty("connCfg", uart_transport);
    else if (!strcmp(command, "getImuCfg")) send_empty("imuCfg", uart_transport);
}

void rcp_task(void *)
{
    static char line[RCP_LINE_BYTES];
    size_t used = 0;
    uint8_t bytes[256];
    while (true) {
        size_t count = xStreamBufferReceive(usb_rx_stream, bytes, sizeof(bytes), pdMS_TO_TICKS(100));
        for (size_t i = 0; i < count; ++i) {
            char byte = static_cast<char>(bytes[i]);
            if (byte == '\r' || byte == '\n') {
                if (used) {
                    JsonDocument document;
                    DeserializationError error = deserializeJson(document, line, used);
                    if (error) ESP_LOGW(TAG, "RCP JSON error: %s", error.c_str());
                    else handle_rcp(document, false);
                    used = 0;
                }
            } else if (used < sizeof(line) - 1) line[used++] = byte;
            else { used = 0; ESP_LOGW(TAG, "RCP input overflow"); }
        }
    }
}

void uart_rcp_task(void *)
{
    static char line[RCP_LINE_BYTES];
    size_t used = 0;
    uint8_t bytes[256];
    while (true) {
        const int count = uart_read_bytes(UART_NUM_0, bytes, sizeof(bytes), pdMS_TO_TICKS(100));
        for (int i = 0; i < count; ++i) {
            const char byte = static_cast<char>(bytes[i]);
            if (byte == '\r' || byte == '\n') {
                if (used) {
                    JsonDocument document;
                    const DeserializationError error = deserializeJson(document, line, used);
                    if (!error) handle_rcp(document, true);
                    used = 0;
                }
            } else if (used < sizeof(line) - 1) line[used++] = byte;
            else used = 0;
        }
    }
}

void init_uart_rcp()
{
    uart_config_t config = {};
    config.baud_rate = 115200;
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_0, GPIO_NUM_43, GPIO_NUM_44,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    if (!uart_is_driver_installed(UART_NUM_0)) {
        ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 4096, 0, 0, nullptr, 0));
    }
    xTaskCreate(uart_rcp_task, "rcp_a105", 8192, nullptr, 4, nullptr);
    ESP_LOGI(TAG, "A105 UART0/COM8 also ready for RaceCapture App at 115200 baud");
}

void init_usb_rcp()
{
    usb_rx_stream = xStreamBufferCreate(RCP_LINE_BYTES * 2, 1);
    ESP_ERROR_CHECK(usb_rx_stream ? ESP_OK : ESP_ERR_NO_MEM);
    tinyusb_config_t usb = {};
    ESP_ERROR_CHECK(tinyusb_driver_install(&usb));
    tinyusb_config_cdcacm_t cdc = {};
    cdc.usb_dev = TINYUSB_USBDEV_0; cdc.cdc_port = TINYUSB_CDC_ACM_0;
    cdc.callback_rx = cdc_rx_callback;
    ESP_ERROR_CHECK(tusb_cdc_acm_init(&cdc));
    xTaskCreate(rcp_task, "rcp_usb", 8192, nullptr, 4, nullptr);
    ESP_LOGI(TAG, "native USB CDC ready for RaceCapture App");
}

uint8_t ubx_checksum_a(const uint8_t *data, size_t length, uint8_t *checksum_b)
{
    uint8_t a = 0, b = 0;
    for (size_t i = 0; i < length; ++i) { a = static_cast<uint8_t>(a + data[i]); b = static_cast<uint8_t>(b + a); }
    *checksum_b = b;
    return a;
}

bool find_mon_ver(const uint8_t *data, size_t length, char *version, size_t version_size)
{
    for (size_t i = 0; i + 8 <= length; ++i) {
        if (data[i] != 0xB5 || data[i + 1] != 0x62 || data[i + 2] != 0x0A || data[i + 3] != 0x04) continue;
        size_t payload = data[i + 4] | (static_cast<size_t>(data[i + 5]) << 8);
        // UBX-MON-VER contains 30 bytes of SW version and 10 bytes of HW
        // version before any extension strings.  Reject a zero-length copy of
        // our poll packet; that indicates a physical TXD/RXD echo, not a GNSS
        // response.
        if (payload < 40 || payload > 1024 || i + payload + 8 > length) continue;
        uint8_t b = 0, a = ubx_checksum_a(&data[i + 2], payload + 4, &b);
        if (data[i + payload + 6] != a || data[i + payload + 7] != b) continue;
        size_t copy = std::min(payload, version_size - 1);
        for (size_t j = 0; j < copy; ++j) version[j] = std::isprint(data[i + 6 + j]) ? data[i + 6 + j] : ' ';
        version[copy] = '\0';
        return true;
    }
    return false;
}

uint32_t read_le_u32(const uint8_t *data)
{
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
}

bool find_nav_pvt(const uint8_t *data, size_t length)
{
    for (size_t i = 0; i + 100 <= length; ++i) {
        if (data[i] != 0xB5 || data[i + 1] != 0x62 ||
            data[i + 2] != 0x01 || data[i + 3] != 0x07) continue;
        const size_t payload_length = data[i + 4] |
                                      (static_cast<size_t>(data[i + 5]) << 8);
        if (payload_length < 92 || i + payload_length + 8 > length) continue;
        uint8_t checksum_b = 0;
        const uint8_t checksum_a = ubx_checksum_a(&data[i + 2], payload_length + 4,
                                                   &checksum_b);
        if (data[i + payload_length + 6] != checksum_a ||
            data[i + payload_length + 7] != checksum_b) continue;

        const uint8_t *payload = &data[i + 6];
        diag.gnss_fix_type = payload[20];
        diag.gnss_num_sv = payload[23];
        const bool fix_ok = (payload[21] & 0x01U) != 0 && diag.gnss_fix_type >= 2;
        const int32_t longitude = static_cast<int32_t>(read_le_u32(&payload[24]));
        const int32_t latitude = static_cast<int32_t>(read_le_u32(&payload[28]));
        const int32_t ground_speed = static_cast<int32_t>(read_le_u32(&payload[60]));
        diag.gnss_longitude = static_cast<double>(longitude) * 1e-7;
        diag.gnss_latitude = static_cast<double>(latitude) * 1e-7;
        diag.gnss_speed_mps = static_cast<float>(ground_speed) / 1000.0F;
        diag.gnss_fix = fix_ok;
        return true;
    }
    return false;
}

bool test_gnss_minimal_first()
{
    // First-touch test: do not drive RESET_N or TIMEPULSE. Find the configured
    // baud rate without disturbing a healthy receiver, then request MON-VER.
    uart_config_t config = {};
    config.baud_rate = GNSS_BAUD_RATES[0];
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 4096, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, GNSS_TX, GNSS_RX,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_set_line_inverse(UART_NUM_1, 0));

    constexpr uint8_t poll[] = {0xB5, 0x62, 0x0A, 0x04, 0, 0, 0x0E, 0x34};
    bool pass = false;
    for (int baud : GNSS_BAUD_RATES) {
        uart_set_baudrate(UART_NUM_1, baud);
        uart_flush_input(UART_NUM_1);
        uint8_t drain[256];
        size_t passive_total = 0;
        const int64_t passive_deadline = esp_timer_get_time() + 750000LL;
        while (esp_timer_get_time() < passive_deadline) {
            const int count = uart_read_bytes(UART_NUM_1, drain, sizeof(drain),
                                              pdMS_TO_TICKS(50));
            if (count > 0) passive_total += static_cast<size_t>(count);
        }
        uart_flush_input(UART_NUM_1);
        uart_write_bytes(UART_NUM_1, poll, sizeof(poll));
        uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(200));
        uint8_t response[2048] = {};
        size_t total = 0;
        const int64_t poll_deadline = esp_timer_get_time() + 1200000LL;
        while (esp_timer_get_time() < poll_deadline && total < sizeof(response)) {
            const int count = uart_read_bytes(UART_NUM_1, response + total,
                                              sizeof(response) - total,
                                              pdMS_TO_TICKS(50));
            if (count > 0) total += static_cast<size_t>(count);
            if (find_mon_ver(response, total, diag.gnss_version,
                             sizeof(diag.gnss_version))) break;
        }
        diag.gnss_bytes += passive_total + total;
        diag.gnss_rx = diag.gnss_rx || passive_total || total;
        pass = find_mon_ver(response, total, diag.gnss_version,
                            sizeof(diag.gnss_version));
        ESP_LOGI(TAG, "GNSS untouched %d baud: passive=%u poll-rx=%u MON-VER=%s",
                 baud, static_cast<unsigned>(passive_total),
                 static_cast<unsigned>(total), pass ? "PASS" : "no");
        if (pass) {
            diag.gnss_baud = static_cast<uint32_t>(baud);
            break;
        }
    }
    uart_driver_delete(UART_NUM_1);
    ESP_LOGI(TAG, "GNSS minimal MON-VER: %s (baud=%lu total rx=%lu)",
             pass ? "PASS" : "FAIL", static_cast<unsigned long>(diag.gnss_baud),
             static_cast<unsigned long>(diag.gnss_bytes));
    return pass;
}

bool test_gnss_fix(uint32_t timeout_seconds)
{
    if (!diag.gnss_baud) return false;
    uart_config_t config = {};
    config.baud_rate = static_cast<int>(diag.gnss_baud);
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 8192, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, GNSS_TX, GNSS_RX,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_set_line_inverse(UART_NUM_1, 0));

    constexpr uint8_t nav_pvt_poll[] = {0xB5, 0x62, 0x01, 0x07, 0, 0, 0x08, 0x19};
    const int64_t deadline = esp_timer_get_time() +
                             static_cast<int64_t>(timeout_seconds) * 1000000LL;
    uint32_t last_report_second = UINT32_MAX;
    while (esp_timer_get_time() < deadline && !diag.gnss_fix) {
        uart_flush_input(UART_NUM_1);
        uart_write_bytes(UART_NUM_1, nav_pvt_poll, sizeof(nav_pvt_poll));
        uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(200));
        uint8_t response[2048] = {};
        size_t total = 0;
        const int64_t reply_deadline = esp_timer_get_time() + 900000LL;
        bool pvt_received = false;
        while (esp_timer_get_time() < reply_deadline && total < sizeof(response)) {
            const int count = uart_read_bytes(UART_NUM_1, response + total,
                                              sizeof(response) - total,
                                              pdMS_TO_TICKS(50));
            if (count > 0) total += static_cast<size_t>(count);
            if (find_nav_pvt(response, total)) {
                pvt_received = true;
                break;
            }
        }
        diag.gnss_bytes += total;
        const uint32_t elapsed = timeout_seconds - static_cast<uint32_t>(
            std::max<int64_t>(0, deadline - esp_timer_get_time()) / 1000000LL);
        if (pvt_received && (diag.gnss_fix || elapsed / 5 != last_report_second / 5)) {
            ESP_LOGI(TAG, "GNSS NAV-PVT: fix=%u ok=%s SV=%u lat=%.7f lon=%.7f",
                     diag.gnss_fix_type, diag.gnss_fix ? "yes" : "no",
                     diag.gnss_num_sv, diag.gnss_latitude, diag.gnss_longitude);
            last_report_second = elapsed;
        }
    }
    uart_driver_delete(UART_NUM_1);
    ESP_LOGI(TAG, "GNSS outdoor antenna position fix within %lu s: %s (fix=%u SV=%u)",
             static_cast<unsigned long>(timeout_seconds), diag.gnss_fix ? "PASS" : "TIMEOUT",
             diag.gnss_fix_type, diag.gnss_num_sv);
    return diag.gnss_fix;
}

bool test_gnss_uart_harness()
{
    uart_config_t config = {};
    config.baud_rate = 9600;
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 2048, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &config));
    ESP_ERROR_CHECK(uart_set_loop_back(UART_NUM_1, true));

    constexpr uint8_t pattern[] = {0xB5, 0x62, 0x0A, 0x04, 0x00, 0x00, 0x0E, 0x34,
                                   0x55, 0xAA, 0x00, 0xFF, 0x12, 0x34, 0x56, 0x78};
    bool internal_pass = true;
    for (int baud : GNSS_BAUD_RATES) {
        uart_set_baudrate(UART_NUM_1, baud);
        uart_flush_input(UART_NUM_1);
        uart_write_bytes(UART_NUM_1, pattern, sizeof(pattern));
        uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(200));
        uint8_t received[sizeof(pattern)] = {};
        int count = uart_read_bytes(UART_NUM_1, received, sizeof(received), pdMS_TO_TICKS(250));
        bool baud_pass = count == static_cast<int>(sizeof(pattern)) &&
                         memcmp(received, pattern, sizeof(pattern)) == 0;
        internal_pass = internal_pass && baud_pass;
        ESP_LOGI(TAG, "GNSS UART1 internal loopback %d baud: %s (%d byte(s))",
                 baud, baud_pass ? "PASS" : "FAIL", count);
    }
    ESP_ERROR_CHECK(uart_set_loop_back(UART_NUM_1, false));
    uart_driver_delete(UART_NUM_1);

    // uart_driver_delete() leaves the GPIO matrix route intact. Return the pad
    // to plain GPIO first, otherwise gpio_set_level() does not own the output.
    ESP_ERROR_CHECK(gpio_reset_pin(GNSS_TX));
    ESP_ERROR_CHECK(gpio_set_direction(GNSS_TX, GPIO_MODE_INPUT_OUTPUT));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_TX, GPIO_FLOATING));
    gpio_set_level(GNSS_TX, 0);
    esp_rom_delay_us(1000);
    int physical_low = gpio_get_level(GNSS_TX);
    gpio_set_level(GNSS_TX, 1);
    esp_rom_delay_us(1000);
    int physical_high = gpio_get_level(GNSS_TX);
    bool static_run_pass = physical_low == 0 && physical_high == 1;
    ESP_LOGI(TAG, "GNSS GPIO16 static pad drive/read while module running: %s (low=%d high=%d)",
             static_run_pass ? "PASS" : "FAIL", physical_low, physical_high);

    gpio_config_t reset = {};
    reset.pin_bit_mask = 1ULL << GNSS_RESET_N;
    reset.mode = GPIO_MODE_INPUT_OUTPUT_OD;
    ESP_ERROR_CHECK(gpio_config(&reset));
    gpio_set_level(GNSS_RESET_N, 0);
    vTaskDelay(pdMS_TO_TICKS(20));
    gpio_set_level(GNSS_TX, 0);
    esp_rom_delay_us(1000);
    int reset_low = gpio_get_level(GNSS_TX);
    gpio_set_level(GNSS_TX, 1);
    esp_rom_delay_us(1000);
    int reset_high = gpio_get_level(GNSS_TX);
    bool static_reset_pass = reset_low == 0 && reset_high == 1;
    gnss_tx_net_safe = static_run_pass && static_reset_pass;
    ESP_LOGI(TAG, "GNSS GPIO16 static pad drive/read while RESET_N Low: %s (low=%d high=%d)",
             static_reset_pass ? "PASS" : "FAIL", reset_low, reset_high);

    // Control measurement using the adjacent ESP32 GPIO15 while every MAX-M10M
    // PIO is an input during reset. This proves the GPIO reset/drive/read method.
    ESP_ERROR_CHECK(gpio_reset_pin(GNSS_RX));
    ESP_ERROR_CHECK(gpio_set_direction(GNSS_RX, GPIO_MODE_INPUT_OUTPUT));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_RX, GPIO_FLOATING));
    gpio_set_level(GNSS_RX, 0);
    esp_rom_delay_us(1000);
    int control_low = gpio_get_level(GNSS_RX);
    gpio_set_level(GNSS_RX, 1);
    esp_rom_delay_us(1000);
    int control_high = gpio_get_level(GNSS_RX);
    bool control_pass = control_low == 0 && control_high == 1;
    ESP_LOGI(TAG, "GNSS GPIO15 control drive/read while RESET_N Low: %s (low=%d high=%d)",
             control_pass ? "PASS" : "FAIL", control_low, control_high);
    ESP_ERROR_CHECK(gpio_set_direction(GNSS_RX, GPIO_MODE_INPUT));
    gpio_set_level(GNSS_RESET_N, 1);
    vTaskDelay(pdMS_TO_TICKS(1000));

    bool physical_pass = false;
    if (gnss_tx_net_safe) {
        // Route RX to the real GPIO16 TX net. This confirms the UART peripheral,
        // GPIO matrix, output pad and GNSS RXD PCB net can carry the exact bytes.
        ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 2048, 0, 0, nullptr, 0));
        ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &config));
        ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, GNSS_TX, GNSS_TX,
                                     UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
        ESP_ERROR_CHECK(gpio_set_direction(GNSS_TX, GPIO_MODE_INPUT_OUTPUT));
        uart_flush_input(UART_NUM_1);
        uart_write_bytes(UART_NUM_1, pattern, sizeof(pattern));
        uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(200));
        uint8_t physical_rx[sizeof(pattern)] = {};
        int physical_count = uart_read_bytes(UART_NUM_1, physical_rx, sizeof(physical_rx),
                                             pdMS_TO_TICKS(250));
        physical_pass = physical_count == static_cast<int>(sizeof(pattern)) &&
                        memcmp(physical_rx, pattern, sizeof(pattern)) == 0;
        uart_driver_delete(UART_NUM_1);
        ESP_LOGI(TAG, "GNSS GPIO16 physical TX-net loopback: %s (%d byte(s))",
                 physical_pass ? "PASS" : "FAIL", physical_count);
    } else {
        ESP_LOGE(TAG, "GNSS GPIO16 physical TX-net loopback SKIPPED: line cannot be driven High");
    }
    return internal_pass && static_run_pass && static_reset_pass && control_pass && physical_pass;
}

size_t sniff_gnss_uart_pin(gpio_num_t candidate_rx, bool inverted)
{
    // Receive-only probe: never route UART TX, so a possible TX/RX swap cannot
    // cause output-to-output contention between ESP32 and MAX-M10M.
    gpio_config_t input = {};
    input.pin_bit_mask = (1ULL << GNSS_RX) | (1ULL << GNSS_TX) | (1ULL << GNSS_TIMEPULSE);
    input.mode = GPIO_MODE_INPUT;
    input.pull_up_en = GPIO_PULLUP_ENABLE;
    ESP_ERROR_CHECK(gpio_config(&input));

    uart_config_t config = {};
    config.baud_rate = 9600;
    config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE;
    config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 2048, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, UART_PIN_NO_CHANGE, candidate_rx,
                                 UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_set_line_inverse(UART_NUM_1, inverted ? UART_SIGNAL_RXD_INV : 0));

    gpio_config_t reset_config = {};
    reset_config.pin_bit_mask = 1ULL << GNSS_RESET_N;
    reset_config.mode = GPIO_MODE_INPUT_OUTPUT_OD;
    ESP_ERROR_CHECK(gpio_config(&reset_config));
    gpio_set_level(GNSS_RESET_N, 0);
    vTaskDelay(pdMS_TO_TICKS(100));
    gpio_set_level(GNSS_RESET_N, 1);
    vTaskDelay(pdMS_TO_TICKS(1000));

    uint8_t discard[256];
    size_t total = 0;
    for (int baud : GNSS_BAUD_RATES) {
        uart_set_baudrate(UART_NUM_1, baud);
        uart_flush_input(UART_NUM_1);
        int64_t deadline = esp_timer_get_time() + 1100000LL;
        size_t baud_bytes = 0;
        while (esp_timer_get_time() < deadline) {
            int count = uart_read_bytes(UART_NUM_1, discard, sizeof(discard), pdMS_TO_TICKS(100));
            if (count > 0) baud_bytes += static_cast<size_t>(count);
        }
        total += baud_bytes;
        ESP_LOGI(TAG, "GNSS receive-only sniff GPIO%d %s at %d baud: %u byte(s)",
                 candidate_rx, inverted ? "inverted" : "normal", baud,
                 static_cast<unsigned>(baud_bytes));
    }
    uart_driver_delete(UART_NUM_1);
    return total;
}

void test_gnss_pin_swap_safely()
{
    size_t gpio15_normal = sniff_gnss_uart_pin(GNSS_RX, false);
    size_t gpio16_normal = sniff_gnss_uart_pin(GNSS_TX, false);
    size_t gpio15_inverted = sniff_gnss_uart_pin(GNSS_RX, true);
    size_t gpio16_inverted = sniff_gnss_uart_pin(GNSS_TX, true);
    if (gpio15_normal) {
        ESP_LOGI(TAG, "GNSS pin direction check: normal activity on expected RX GPIO15 (%u bytes)",
                 static_cast<unsigned>(gpio15_normal));
    } else if (gpio16_normal) {
        ESP_LOGE(TAG, "GNSS pin direction check: normal UART activity only on GPIO16 (%u bytes); physical TX/RX may be swapped",
                 static_cast<unsigned>(gpio16_normal));
    } else if (gpio15_inverted || gpio16_inverted) {
        ESP_LOGE(TAG, "GNSS polarity check: activity found only with inverted RX (GPIO15=%u GPIO16=%u)",
                 static_cast<unsigned>(gpio15_inverted), static_cast<unsigned>(gpio16_inverted));
    } else {
        ESP_LOGE(TAG, "GNSS pin direction check: no normal or inverted startup UART activity on GPIO15 or GPIO16");
    }
}

int majority_gpio_level(gpio_num_t pin)
{
    int high = 0;
    for (int i = 0; i < 32; ++i) {
        high += gpio_get_level(pin);
        esp_rom_delay_us(100);
    }
    return high >= 16;
}

void characterize_gnss_pins()
{
    gpio_config_t reset = {};
    reset.pin_bit_mask = 1ULL << GNSS_RESET_N;
    reset.mode = GPIO_MODE_INPUT_OUTPUT_OD;
    ESP_ERROR_CHECK(gpio_config(&reset));
    gpio_set_level(GNSS_RESET_N, 1);
    vTaskDelay(pdMS_TO_TICKS(50));

    ESP_ERROR_CHECK(gpio_set_direction(GNSS_RX, GPIO_MODE_INPUT));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_RX, GPIO_PULLUP_ONLY));
    vTaskDelay(pdMS_TO_TICKS(20));
    int run_pullup = majority_gpio_level(GNSS_RX);
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_RX, GPIO_PULLDOWN_ONLY));
    vTaskDelay(pdMS_TO_TICKS(20));
    int run_pulldown = majority_gpio_level(GNSS_RX);

    gpio_set_level(GNSS_RESET_N, 0);
    vTaskDelay(pdMS_TO_TICKS(100));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_RX, GPIO_PULLUP_ONLY));
    vTaskDelay(pdMS_TO_TICKS(20));
    int reset_pullup = majority_gpio_level(GNSS_RX);
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_RX, GPIO_PULLDOWN_ONLY));
    vTaskDelay(pdMS_TO_TICKS(20));
    int reset_pulldown = majority_gpio_level(GNSS_RX);
    gpio_set_level(GNSS_RESET_N, 1);
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_RX, GPIO_PULLUP_ONLY));
    ESP_LOGI(TAG, "GNSS TXD drive test: run pull-up=%d pull-down=%d; reset pull-up=%d pull-down=%d",
             run_pullup, run_pulldown, reset_pullup, reset_pulldown);
    if (run_pullup == 1 && run_pulldown == 0) {
        ESP_LOGE(TAG, "GNSS TXD appears high-impedance while RESET_N is High (not an actively driven UART idle)");
    }

    ESP_ERROR_CHECK(gpio_set_direction(GNSS_TIMEPULSE, GPIO_MODE_INPUT));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_TIMEPULSE, GPIO_PULLUP_ONLY));
    int previous = gpio_get_level(GNSS_TIMEPULSE);
    unsigned edges = 0;
    int64_t deadline = esp_timer_get_time() + 4000000LL;
    while (esp_timer_get_time() < deadline) {
        int current = gpio_get_level(GNSS_TIMEPULSE);
        if (current != previous) {
            ++edges;
            previous = current;
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
    ESP_LOGI(TAG, "GNSS TIMEPULSE GPIO8 edges in 4 s: %u (final level=%d)", edges, previous);
}

bool test_gnss()
{
    uart_config_t config = {};
    config.baud_rate = 9600; config.data_bits = UART_DATA_8_BITS;
    config.parity = UART_PARITY_DISABLE; config.stop_bits = UART_STOP_BITS_1;
    config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE; config.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 4096, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &config));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, GNSS_TX, GNSS_RX, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_set_line_inverse(UART_NUM_1, 0));
    // If MAX-M10M releases TXD during reset, this pull-up makes an open net read High.
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_RX, GPIO_PULLUP_ONLY));
    // TIMEPULSE is internally connected to SAFEBOOT_N through 1 kOhm in MAX-M10M.
    // Drive it High only across reset release to positively exclude an accidental
    // safeboot selection, then immediately release it before TIMEPULSE can become
    // an output. This is diagnostic behavior, not intended for production firmware.
    ESP_ERROR_CHECK(gpio_set_level(GNSS_TIMEPULSE, 1));
    ESP_ERROR_CHECK(gpio_set_direction(GNSS_TIMEPULSE, GPIO_MODE_OUTPUT));

    // Verify the board pull-up, then issue a clean active-low hardware reset.
    gpio_config_t reset_config = {};
    reset_config.pin_bit_mask = 1ULL << GNSS_RESET_N;
    reset_config.mode = GPIO_MODE_INPUT_OUTPUT_OD;
    ESP_ERROR_CHECK(gpio_config(&reset_config));
    gpio_set_level(GNSS_RESET_N, 1);
    vTaskDelay(pdMS_TO_TICKS(20));
    ESP_LOGI(TAG, "GNSS electrical levels before reset: RESET_N=%d TXD/ESP_RX=%d",
             gpio_get_level(GNSS_RESET_N), gpio_get_level(GNSS_RX));
    gpio_set_level(GNSS_RESET_N, 0);
    vTaskDelay(pdMS_TO_TICKS(100));
    ESP_LOGI(TAG, "GNSS electrical levels during reset: RESET_N=%d TXD/ESP_RX=%d (TIMEPULSE forced High)",
             gpio_get_level(GNSS_RESET_N), gpio_get_level(GNSS_RX));
    gpio_set_level(GNSS_RESET_N, 1);
    esp_rom_delay_us(2000);
    ESP_ERROR_CHECK(gpio_set_direction(GNSS_TIMEPULSE, GPIO_MODE_INPUT));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_TIMEPULSE, GPIO_PULLUP_ONLY));
    vTaskDelay(pdMS_TO_TICKS(998));
    ESP_LOGI(TAG, "GNSS electrical levels after reset: RESET_N=%d TXD/ESP_RX=%d",
             gpio_get_level(GNSS_RESET_N), gpio_get_level(GNSS_RX));

    constexpr uint8_t poll[] = {0xB5, 0x62, 0x0A, 0x04, 0, 0, 0x0E, 0x34};
    uint8_t response[2048];
    constexpr char pubx_poll[] = "$PUBX,00*33\r\n";
    for (int baud : GNSS_BAUD_RATES) {
        uart_set_baudrate(UART_NUM_1, baud); uart_flush_input(UART_NUM_1);
        uart_write_bytes(UART_NUM_1, poll, sizeof(poll)); uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(200));
        uart_write_bytes(UART_NUM_1, pubx_poll, sizeof(pubx_poll) - 1);
        uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(200));
        size_t total = 0;
        int64_t deadline = esp_timer_get_time() + 1800000LL;
        while (esp_timer_get_time() < deadline && total < sizeof(response)) {
            int count = uart_read_bytes(UART_NUM_1, response + total, sizeof(response) - total, pdMS_TO_TICKS(100));
            if (count > 0) total += static_cast<size_t>(count);
        }
        diag.gnss_bytes += total; diag.gnss_rx = diag.gnss_rx || total;
        if (find_mon_ver(response, total, diag.gnss_version, sizeof(diag.gnss_version))) {
            diag.gnss = true;
            ESP_LOGI(TAG, "GNSS PASS baud=%d MON-VER='%s' rx=%u", baud, diag.gnss_version, static_cast<unsigned>(total));
            uart_driver_delete(UART_NUM_1);
            return true;
        }
        ESP_LOGW(TAG, "GNSS no valid MON-VER at %d baud (rx=%u)", baud, static_cast<unsigned>(total));
    }
    uart_driver_delete(UART_NUM_1);
    ESP_LOGE(TAG, "GNSS FAIL: no UBX MON-VER response (total rx=%lu)", static_cast<unsigned long>(diag.gnss_bytes));
    return false;
}

bool test_can1()
{
    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(CAN1_TX, CAN1_RX, TWAI_MODE_NO_ACK);
    general.tx_queue_len = 4; general.rx_queue_len = 4;
    twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    esp_err_t error = twai_driver_install(&general, &timing, &filter);
    if (error != ESP_OK) { ESP_LOGE(TAG, "CAN1 install FAIL: %s", esp_err_to_name(error)); return false; }
    error = twai_start();
    if (error != ESP_OK) { ESP_LOGE(TAG, "CAN1 start FAIL: %s", esp_err_to_name(error)); twai_driver_uninstall(); return false; }

    twai_message_t tx = {};
    tx.identifier = 0x321; tx.data_length_code = 8;
    tx.flags = TWAI_MSG_FLAG_SELF | TWAI_MSG_FLAG_SS;
    constexpr uint8_t expected[8] = {0x4C, 0x4F, 0x47, 0x47, 0x45, 0x52, 0x31, 0x21};
    memcpy(tx.data, expected, sizeof(expected));
    twai_message_t rx = {};
    esp_err_t tx_error = twai_transmit(&tx, pdMS_TO_TICKS(1000));
    esp_err_t rx_error = tx_error == ESP_OK ? twai_receive(&rx, pdMS_TO_TICKS(1000)) : tx_error;
    bool pass = tx_error == ESP_OK && rx_error == ESP_OK && rx.identifier == tx.identifier &&
                rx.data_length_code == tx.data_length_code && !memcmp(rx.data, expected, sizeof(expected));
    twai_status_info_t status = {};
    twai_get_status_info(&status); twai_stop(); twai_driver_uninstall();
    diag.can1 = pass;
    if (pass) ESP_LOGI(TAG, "CAN1 PASS: TWAI/ATA6561 self reception at 500 kbit/s, id=0x321");
    else ESP_LOGE(TAG, "CAN1 FAIL: tx=%s rx=%s txerr=%lu rxerr=%lu buserr=%lu",
                  esp_err_to_name(tx_error), esp_err_to_name(rx_error),
                  static_cast<unsigned long>(status.tx_error_counter),
                  static_cast<unsigned long>(status.rx_error_counter),
                  static_cast<unsigned long>(status.bus_error_count));
    return pass;
}

constexpr uint8_t MCP_RESET = 0xC0;
constexpr uint8_t MCP_READ = 0x03;
constexpr uint8_t MCP_WRITE = 0x02;
constexpr uint8_t MCP_RTS_TX0 = 0x81;
constexpr uint8_t MCP_CANSTAT = 0x0E;
constexpr uint8_t MCP_CANCTRL = 0x0F;
constexpr uint8_t MCP_CNF3 = 0x28;
constexpr uint8_t MCP_CANINTF = 0x2C;
constexpr uint8_t MCP_EFLG = 0x2D;
constexpr uint8_t MCP_TEC = 0x1C;
constexpr uint8_t MCP_REC = 0x1D;
constexpr uint8_t MCP_TXB0CTRL = 0x30;
constexpr uint8_t MCP_TXB0SIDH = 0x31;
constexpr uint8_t MCP_RXB0CTRL = 0x60;
constexpr uint8_t MCP_RXB0SIDH = 0x61;

bool mcp_transaction(spi_device_handle_t device, const uint8_t *tx, uint8_t *rx, size_t length)
{
    spi_transaction_t transaction = {};
    transaction.length = length * 8; transaction.tx_buffer = tx; transaction.rx_buffer = rx;
    return spi_device_polling_transmit(device, &transaction) == ESP_OK;
}

uint8_t mcp_read(spi_device_handle_t device, uint8_t address)
{
    uint8_t tx[3] = {MCP_READ, address, 0}, rx[3] = {};
    return mcp_transaction(device, tx, rx, sizeof(tx)) ? rx[2] : 0xFF;
}

bool mcp_read_many(spi_device_handle_t device, uint8_t address, uint8_t *data, size_t count)
{
    uint8_t tx[32] = {MCP_READ, address}, rx[32] = {};
    if (count + 2 > sizeof(tx) || !mcp_transaction(device, tx, rx, count + 2)) return false;
    memcpy(data, &rx[2], count); return true;
}

bool mcp_write_many(spi_device_handle_t device, uint8_t address, const uint8_t *data, size_t count)
{
    uint8_t tx[32] = {MCP_WRITE, address};
    if (count + 2 > sizeof(tx)) return false;
    memcpy(&tx[2], data, count); return mcp_transaction(device, tx, nullptr, count + 2);
}

bool mcp_write(spi_device_handle_t device, uint8_t address, uint8_t value)
{
    return mcp_write_many(device, address, &value, 1);
}

bool mcp_set_mode(spi_device_handle_t device, uint8_t mode)
{
    uint8_t control = static_cast<uint8_t>((mcp_read(device, MCP_CANCTRL) & 0x1F) | (mode & 0xE0));
    if (!mcp_write(device, MCP_CANCTRL, control)) return false;
    for (int i = 0; i < 50; ++i) {
        if ((mcp_read(device, MCP_CANSTAT) & 0xE0) == (mode & 0xE0)) return true;
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    return false;
}

bool test_can2()
{
    gpio_config_t reset = {};
    reset.pin_bit_mask = 1ULL << CAN2_RESET; reset.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&reset));
    gpio_set_level(CAN2_RESET, 0); vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(CAN2_RESET, 1); vTaskDelay(pdMS_TO_TICKS(20));

    spi_bus_config_t bus = {};
    bus.mosi_io_num = CAN2_MOSI; bus.miso_io_num = CAN2_MISO; bus.sclk_io_num = CAN2_SCK;
    bus.quadwp_io_num = -1; bus.quadhd_io_num = -1;
    bus.data4_io_num = -1; bus.data5_io_num = -1; bus.data6_io_num = -1; bus.data7_io_num = -1;
    bus.max_transfer_sz = 64;
    esp_err_t error = spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_DISABLED);
    if (error != ESP_OK) { ESP_LOGE(TAG, "CAN2 SPI init FAIL: %s", esp_err_to_name(error)); return false; }

    spi_device_interface_config_t device_config = {};
    device_config.mode = 0; device_config.clock_speed_hz = 1000000;
    device_config.spics_io_num = CAN2_CS; device_config.queue_size = 1;
    spi_device_handle_t device = nullptr;
    error = spi_bus_add_device(SPI2_HOST, &device_config, &device);
    if (error != ESP_OK) { ESP_LOGE(TAG, "CAN2 SPI device FAIL: %s", esp_err_to_name(error)); spi_bus_free(SPI2_HOST); return false; }

    uint8_t command = MCP_RESET;
    mcp_transaction(device, &command, nullptr, 1); vTaskDelay(pdMS_TO_TICKS(10));
    uint8_t initial_status = mcp_read(device, MCP_CANSTAT);
    uint8_t initial_control = mcp_read(device, MCP_CANCTRL);
    bool pass = initial_status != 0 && initial_status != 0xFF && (initial_status & 0xE0) == 0x80;
    // CNF3, CNF2, CNF1: 20 MHz, 500 kbit/s, 20 TQ/bit, 80% sample point.
    // BRP=0, SJW=3 TQ, PRSEG=8 TQ, PHSEG1=7 TQ, PHSEG2=4 TQ.
    constexpr uint8_t timing[3] = {0x03, 0xB7, 0x80};
    pass = pass && mcp_write_many(device, MCP_CNF3, timing, sizeof(timing));
    pass = pass && mcp_write(device, MCP_RXB0CTRL, 0x60);
    pass = pass && mcp_write(device, MCP_CANINTF, 0);
    pass = pass && mcp_set_mode(device, 0x40); // internal loopback

    constexpr uint16_t identifier = 0x456;
    constexpr uint8_t expected[8] = {0x43, 0x41, 0x4E, 0x32, 0x4C, 0x4F, 0x4F, 0x50};
    uint8_t tx_buffer[13] = {};
    tx_buffer[0] = identifier >> 3; tx_buffer[1] = (identifier & 7) << 5;
    tx_buffer[4] = 8; memcpy(&tx_buffer[5], expected, sizeof(expected));
    pass = pass && mcp_write_many(device, MCP_TXB0SIDH, tx_buffer, sizeof(tx_buffer));
    command = MCP_RTS_TX0; pass = pass && mcp_transaction(device, &command, nullptr, 1);
    bool received = false;
    for (int i = 0; i < 100; ++i) {
        if (mcp_read(device, MCP_CANINTF) & 1) { received = true; break; }
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    uint8_t rx_buffer[13] = {};
    pass = pass && received && mcp_read_many(device, MCP_RXB0SIDH, rx_buffer, sizeof(rx_buffer));
    uint16_t rx_identifier = static_cast<uint16_t>(rx_buffer[0] << 3) | (rx_buffer[1] >> 5);
    pass = pass && rx_identifier == identifier && (rx_buffer[4] & 0x0F) == 8 &&
           !memcmp(&rx_buffer[5], expected, sizeof(expected));

    mcp_set_mode(device, 0x80);
    spi_bus_remove_device(device); spi_bus_free(SPI2_HOST);
    diag.can2 = pass;
    if (pass) ESP_LOGI(TAG, "CAN2 PASS: MCP25625 SPI/config/internal loopback at 500 kbit/s, id=0x456");
    else ESP_LOGE(TAG, "CAN2 FAIL: CANSTAT=0x%02X CANCTRL=0x%02X received=%d rxid=0x%03X dlc=%u",
                  initial_status, initial_control, received, rx_identifier, rx_buffer[4] & 0x0F);
    return pass;
}

bool test_can_external()
{
    ESP_LOGI(TAG, "CAN external test: J4(CAN2) <-> J5(CAN1), 500 kbit/s, 32 frames each direction");

    gpio_config_t reset = {};
    reset.pin_bit_mask = 1ULL << CAN2_RESET;
    reset.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&reset));
    gpio_set_level(CAN2_RESET, 0);
    vTaskDelay(pdMS_TO_TICKS(10));
    gpio_set_level(CAN2_RESET, 1);
    vTaskDelay(pdMS_TO_TICKS(20));

    spi_bus_config_t bus = {};
    bus.mosi_io_num = CAN2_MOSI;
    bus.miso_io_num = CAN2_MISO;
    bus.sclk_io_num = CAN2_SCK;
    bus.quadwp_io_num = -1;
    bus.quadhd_io_num = -1;
    bus.data4_io_num = -1;
    bus.data5_io_num = -1;
    bus.data6_io_num = -1;
    bus.data7_io_num = -1;
    bus.max_transfer_sz = 64;
    esp_err_t error = spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_DISABLED);
    if (error != ESP_OK) {
        ESP_LOGE(TAG, "CAN external SPI init FAIL: %s", esp_err_to_name(error));
        return false;
    }

    spi_device_interface_config_t device_config = {};
    device_config.mode = 0;
    device_config.clock_speed_hz = 1000000;
    device_config.spics_io_num = CAN2_CS;
    device_config.queue_size = 1;
    spi_device_handle_t device = nullptr;
    error = spi_bus_add_device(SPI2_HOST, &device_config, &device);
    if (error != ESP_OK) {
        ESP_LOGE(TAG, "CAN external SPI device FAIL: %s", esp_err_to_name(error));
        spi_bus_free(SPI2_HOST);
        return false;
    }

    uint8_t command = MCP_RESET;
    bool pass = mcp_transaction(device, &command, nullptr, 1);
    vTaskDelay(pdMS_TO_TICKS(10));
    // CNF3, CNF2, CNF1: 20 MHz, 500 kbit/s, 20 TQ/bit, 80% sample point.
    constexpr uint8_t timing[3] = {0x03, 0xB7, 0x80};
    pass = pass && (mcp_read(device, MCP_CANSTAT) & 0xE0) == 0x80;
    pass = pass && mcp_write_many(device, MCP_CNF3, timing, sizeof(timing));
    pass = pass && mcp_write(device, MCP_RXB0CTRL, 0x60); // receive any valid frame
    pass = pass && mcp_write(device, MCP_CANINTF, 0);
    pass = pass && mcp_set_mode(device, 0x00); // normal mode, external transceiver active

    twai_general_config_t general = TWAI_GENERAL_CONFIG_DEFAULT(CAN1_TX, CAN1_RX, TWAI_MODE_NORMAL);
    general.tx_queue_len = 4;
    general.rx_queue_len = 8;
    twai_timing_config_t twai_timing = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    bool twai_installed = false;
    bool twai_started = false;
    if (pass) {
        error = twai_driver_install(&general, &twai_timing, &filter);
        twai_installed = error == ESP_OK;
        pass = twai_installed;
    }
    if (pass) {
        error = twai_start();
        twai_started = error == ESP_OK;
        pass = twai_started;
    }

    unsigned can1_to_can2 = 0;
    unsigned can2_to_can1 = 0;
    for (unsigned sequence = 0; pass && sequence < 32; ++sequence) {
        uint8_t expected[8] = {0x31, 0x3E, 0x32, 0x21,
                               static_cast<uint8_t>(sequence),
                               static_cast<uint8_t>(sequence ^ 0xA5),
                               static_cast<uint8_t>(sequence + 0x37),
                               static_cast<uint8_t>(~sequence)};
        twai_message_t tx = {};
        tx.identifier = 0x500 + sequence;
        tx.data_length_code = 8;
        tx.flags = TWAI_MSG_FLAG_SS;
        memcpy(tx.data, expected, sizeof(expected));
        mcp_write(device, MCP_CANINTF, 0);
        error = twai_transmit(&tx, pdMS_TO_TICKS(250));
        bool received = false;
        for (int poll = 0; error == ESP_OK && poll < 100; ++poll) {
            if (mcp_read(device, MCP_CANINTF) & 0x01) {
                received = true;
                break;
            }
            vTaskDelay(pdMS_TO_TICKS(2));
        }
        uint8_t rx_buffer[13] = {};
        bool read_ok = received && mcp_read_many(device, MCP_RXB0SIDH, rx_buffer, sizeof(rx_buffer));
        uint16_t rx_identifier = static_cast<uint16_t>(rx_buffer[0] << 3) | (rx_buffer[1] >> 5);
        pass = error == ESP_OK && read_ok && rx_identifier == tx.identifier &&
               (rx_buffer[4] & 0x0F) == 8 && !memcmp(&rx_buffer[5], expected, sizeof(expected));
        if (pass) ++can1_to_can2;
    }

    if (twai_started) twai_clear_receive_queue();
    for (unsigned sequence = 0; pass && sequence < 32; ++sequence) {
        constexpr uint8_t prefix[4] = {0x32, 0x3E, 0x31, 0x21};
        uint8_t expected[8] = {prefix[0], prefix[1], prefix[2], prefix[3],
                               static_cast<uint8_t>(sequence),
                               static_cast<uint8_t>(sequence ^ 0x5A),
                               static_cast<uint8_t>(sequence + 0x73),
                               static_cast<uint8_t>(~sequence)};
        uint16_t identifier = static_cast<uint16_t>(0x580 + sequence);
        uint8_t tx_buffer[13] = {};
        tx_buffer[0] = identifier >> 3;
        tx_buffer[1] = (identifier & 7) << 5;
        tx_buffer[4] = 8;
        memcpy(&tx_buffer[5], expected, sizeof(expected));
        mcp_write(device, MCP_CANINTF, 0);
        pass = mcp_write_many(device, MCP_TXB0SIDH, tx_buffer, sizeof(tx_buffer));
        command = MCP_RTS_TX0;
        pass = pass && mcp_transaction(device, &command, nullptr, 1);
        twai_message_t rx = {};
        error = pass ? twai_receive(&rx, pdMS_TO_TICKS(250)) : ESP_FAIL;
        pass = error == ESP_OK && rx.identifier == identifier && rx.data_length_code == 8 &&
               !memcmp(rx.data, expected, sizeof(expected));
        for (int poll = 0; pass && poll < 100 && (mcp_read(device, MCP_TXB0CTRL) & 0x08); ++poll) {
            vTaskDelay(pdMS_TO_TICKS(2));
        }
        pass = pass && !(mcp_read(device, MCP_TXB0CTRL) & 0x08);
        if (pass) ++can2_to_can1;
    }

    twai_status_info_t status = {};
    if (twai_started) twai_get_status_info(&status);
    uint8_t mcp_eflg = mcp_read(device, MCP_EFLG);
    uint8_t mcp_tec = mcp_read(device, MCP_TEC);
    uint8_t mcp_rec = mcp_read(device, MCP_REC);
    pass = pass && can1_to_can2 == 32 && can2_to_can1 == 32 &&
           status.tx_error_counter == 0 && status.rx_error_counter == 0 &&
           status.bus_error_count == 0 && mcp_eflg == 0 && mcp_tec == 0 && mcp_rec == 0;

    if (twai_started) twai_stop();
    if (twai_installed) twai_driver_uninstall();
    mcp_set_mode(device, 0x80);
    spi_bus_remove_device(device);
    spi_bus_free(SPI2_HOST);

    diag.can_external = pass;
    if (pass) {
        ESP_LOGI(TAG, "CAN EXTERNAL PASS: CAN1->CAN2=%u/32 CAN2->CAN1=%u/32; all error counters zero",
                 can1_to_can2, can2_to_can1);
    } else {
        ESP_LOGE(TAG, "CAN EXTERNAL FAIL: CAN1->CAN2=%u/32 CAN2->CAN1=%u/32 TWAI(tx=%lu rx=%lu bus=%lu) MCP(EFLG=0x%02X TEC=%u REC=%u)",
                 can1_to_can2, can2_to_can1,
                 static_cast<unsigned long>(status.tx_error_counter),
                 static_cast<unsigned long>(status.rx_error_counter),
                 static_cast<unsigned long>(status.bus_error_count), mcp_eflg, mcp_tec, mcp_rec);
    }
    return pass;
}

uint8_t pattern_byte(size_t offset)
{
    uint32_t value = static_cast<uint32_t>(offset);
    value ^= value >> 7; value *= 0x45D9F3BU; value ^= value >> 16;
    return static_cast<uint8_t>(value);
}

bool run_sd_file_test(sdmmc_card_t *card)
{
    const char *path = "/sdcard/logger_v1_v1_test.bin";
    unlink(path);
    uint8_t *buffer = static_cast<uint8_t *>(heap_caps_malloc(SD_CHUNK_BYTES, MALLOC_CAP_8BIT));
    if (!buffer) { ESP_LOGE(TAG, "SD FAIL: no test buffer memory"); return false; }
    FILE *file = fopen(path, "wb");
    if (!file) { ESP_LOGE(TAG, "SD FAIL: write open errno=%d", errno); free(buffer); return false; }

    bool pass = true;
    int64_t write_start = esp_timer_get_time();
    for (size_t offset = 0; offset < SD_TEST_BYTES && pass; offset += SD_CHUNK_BYTES) {
        for (size_t i = 0; i < SD_CHUNK_BYTES; ++i) buffer[i] = pattern_byte(offset + i);
        pass = fwrite(buffer, 1, SD_CHUNK_BYTES, file) == SD_CHUNK_BYTES;
    }
    fflush(file); fsync(fileno(file)); fclose(file);
    int64_t write_us = esp_timer_get_time() - write_start;

    file = pass ? fopen(path, "rb") : nullptr;
    if (!file) {
        ESP_LOGE(TAG, "SD FAIL: read open/write stage errno=%d", errno);
        unlink(path); free(buffer); return false;
    }
    size_t bad_offset = 0;
    int64_t read_start = esp_timer_get_time();
    for (size_t offset = 0; offset < SD_TEST_BYTES && pass; offset += SD_CHUNK_BYTES) {
        if (fread(buffer, 1, SD_CHUNK_BYTES, file) != SD_CHUNK_BYTES) { pass = false; bad_offset = offset; break; }
        for (size_t i = 0; i < SD_CHUNK_BYTES; ++i) {
            if (buffer[i] != pattern_byte(offset + i)) { pass = false; bad_offset = offset + i; break; }
        }
    }
    fclose(file);
    int64_t read_us = esp_timer_get_time() - read_start;
    unlink(path); free(buffer);
    diag.sd_write_mib_s = 8.0F * 1000000.0F / static_cast<float>(write_us);
    diag.sd_read_mib_s = 8.0F * 1000000.0F / static_cast<float>(read_us);
    if (pass) ESP_LOGI(TAG, "SD PASS: 8 MiB write/read/verify/delete; write=%.2f MiB/s read=%.2f MiB/s",
                       diag.sd_write_mib_s, diag.sd_read_mib_s);
    else ESP_LOGE(TAG, "SD FAIL: read/data mismatch at byte %u", static_cast<unsigned>(bad_offset));
    return pass;
}

bool mount_and_test_sd(int frequency_khz)
{
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {};
    mount_config.format_if_mount_failed = false; mount_config.max_files = 4;
    mount_config.allocation_unit_size = 16 * 1024;
    sdmmc_host_t host = SDMMC_HOST_DEFAULT(); host.max_freq_khz = frequency_khz;
    sdmmc_slot_config_t slot = SDMMC_SLOT_CONFIG_DEFAULT();
    slot.width = 4; slot.clk = SD_CLK; slot.cmd = SD_CMD;
    slot.d0 = SD_D0; slot.d1 = SD_D1; slot.d2 = SD_D2; slot.d3 = SD_D3;
    sdmmc_card_t *card = nullptr;
    esp_err_t error = esp_vfs_fat_sdmmc_mount("/sdcard", &host, &slot, &mount_config, &card);
    if (error != ESP_OK) {
        ESP_LOGW(TAG, "SD mount FAIL at max %d kHz: %s", frequency_khz, esp_err_to_name(error));
        return false;
    }
    sdmmc_card_print_info(stdout, card);
    struct statvfs filesystem = {};
    if (!statvfs("/sdcard", &filesystem)) {
        uint64_t free_mib = static_cast<uint64_t>(filesystem.f_bavail) * filesystem.f_frsize / (1024ULL * 1024ULL);
        ESP_LOGI(TAG, "SD free space: %llu MiB", static_cast<unsigned long long>(free_mib));
    }
    bool pass = run_sd_file_test(card);
    esp_vfs_fat_sdcard_unmount("/sdcard", card);
    return pass;
}

bool test_sd()
{
    ESP_LOGI(TAG, "SD current-net pins CLK=%d CMD=%d D0=%d D1=%d D2=%d D3=%d",
             SD_CLK, SD_CMD, SD_D0, SD_D1, SD_D2, SD_D3);
    if (mount_and_test_sd(SDMMC_FREQ_HIGHSPEED)) {
        diag.sd = true; diag.sd_40mhz = true; return true;
    }
    ESP_LOGW(TAG, "SD retry at 20 MHz to distinguish high-speed SI from card/contact/wiring");
    if (mount_and_test_sd(SDMMC_FREQ_DEFAULT)) {
        diag.sd = true; diag.sd_40mhz = false;
        ESP_LOGW(TAG, "SD passes at 20 MHz only; 40 MHz signal integrity is not verified");
        return true;
    }
    ESP_LOGE(TAG, "SD FAIL at 40 and 20 MHz (card absent, contact, pull-up, or wiring)");
    return false;
}

bool test_psram()
{
    const size_t total = heap_caps_get_total_size(MALLOC_CAP_SPIRAM);
    const size_t free_before = heap_caps_get_free_size(MALLOC_CAP_SPIRAM);
    const size_t largest = heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM);
    ESP_LOGI(TAG, "PSRAM: total=%u free=%u largest=%u byte(s)",
             static_cast<unsigned>(total), static_cast<unsigned>(free_before),
             static_cast<unsigned>(largest));

    if (total < 7U * 1024U * 1024U || largest < 6U * 1024U * 1024U) {
        ESP_LOGE(TAG, "PSRAM capacity/allocation FAIL (expected fitted 8 MiB N16R8 module)");
        return false;
    }

    const size_t reserve = 64U * 1024U;
    const size_t test_bytes = largest > reserve ? largest - reserve : largest;
    uint32_t *memory = static_cast<uint32_t *>(
        heap_caps_malloc(test_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!memory) {
        ESP_LOGE(TAG, "PSRAM full-range allocation FAIL (%u byte(s))",
                 static_cast<unsigned>(test_bytes));
        return false;
    }

    const size_t words = test_bytes / sizeof(uint32_t);
    for (size_t i = 0; i < words; ++i) {
        memory[i] = 0xA5A55A5AU ^ static_cast<uint32_t>(i * 2654435761U);
    }
    size_t errors = 0;
    for (size_t i = 0; i < words; ++i) {
        const uint32_t expected = 0xA5A55A5AU ^ static_cast<uint32_t>(i * 2654435761U);
        if (memory[i] != expected) {
            if (errors < 4) {
                ESP_LOGE(TAG, "PSRAM mismatch word %u: got 0x%08lX expected 0x%08lX",
                         static_cast<unsigned>(i), static_cast<unsigned long>(memory[i]),
                         static_cast<unsigned long>(expected));
            }
            ++errors;
        }
    }
    heap_caps_free(memory);
    diag.psram = errors == 0;
    ESP_LOGI(TAG, "PSRAM write/read/verify %u byte(s): %s (%u error(s))",
             static_cast<unsigned>(words * sizeof(uint32_t)),
             diag.psram ? "PASS" : "FAIL", static_cast<unsigned>(errors));
    return diag.psram;
}

void init_health()
{
    diag.cpu_mhz = esp_clk_cpu_freq() / 1000000;
    temperature_sensor_config_t temp_config = TEMPERATURE_SENSOR_CONFIG_DEFAULT(20, 100);
    ESP_ERROR_CHECK(temperature_sensor_install(&temp_config, &temp_sensor));
    ESP_ERROR_CHECK(temperature_sensor_enable(temp_sensor));
    gpio_config_t inputs = {};
    inputs.pin_bit_mask = (1ULL << OTG_VBUS_SENSE) | (1ULL << OTG_OC_N) | (1ULL << OTG_ROLE);
    inputs.mode = GPIO_MODE_INPUT;
    ESP_ERROR_CHECK(gpio_config(&inputs));
    xTaskCreatePinnedToCore(stress_task, "stress0", 3072, reinterpret_cast<void *>(0), 1, nullptr, 0);
    xTaskCreatePinnedToCore(stress_task, "stress1", 3072, reinterpret_cast<void *>(1), 1, nullptr, 1);
    xTaskCreate(temperature_task, "temperature", 3072, nullptr, 2, nullptr);
}

}  // namespace

extern "C" void app_main(void)
{
    esp_chip_info_t chip = {};
    esp_chip_info(&chip);
    ESP_LOGI(TAG, "logger_v1 full board test boot");
    ESP_LOGI(TAG, "ESP-IDF %s; cores=%u rev=%u; CPU config/actual=%d/%d MHz",
             esp_get_idf_version(), chip.cores, chip.revision,
             CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ, esp_clk_cpu_freq() / 1000000);

    // Give immediate visual proof of life on every power-up. CAN2 later borrows
    // GPIO39/40 briefly, then the Knight Rider automatically resumes.
    start_led_task();
    vTaskDelay(pdMS_TO_TICKS(300));
    init_health();
    init_usb_rcp();
    init_uart_rcp();

    bool psram = test_psram();

    // Run the heat-sensitive nearby peripherals early. CAN2 shares GPIO39/40
    // with the 74HC595, so pause LEDs only for the CAN2 bus tests.
    bool imu = init_imu();
    bool can1 = test_can1();
    stop_led_task_for_can();
    bool can2 = test_can2();
    bool can_external = test_can_external();
    start_led_task();

    ESP_ERROR_CHECK(gpio_reset_pin(GNSS_TX));
    ESP_ERROR_CHECK(gpio_set_direction(GNSS_TX, GPIO_MODE_INPUT));
    ESP_ERROR_CHECK(gpio_set_pull_mode(GNSS_TX, GPIO_PULLUP_ONLY));
    vTaskDelay(pdMS_TO_TICKS(20));
    bool weak_pullup_high = gpio_get_level(GNSS_TX) == 1;
    bool gnss_minimal = weak_pullup_high ? test_gnss_minimal_first() : false;
    if (!weak_pullup_high) {
        ESP_LOGE(TAG, "GNSS minimal active poll SKIPPED: GPIO16 remains Low with weak pull-up");
    }
    if (!gnss_minimal) {
        bool gnss_harness = test_gnss_uart_harness();
        ESP_LOGI(TAG, "GNSS software/UART harness: %s", gnss_harness ? "PASS" : "FAIL");
    } else {
        ESP_LOGI(TAG, "GNSS MON-VER responded; failure-only GPIO drive harness skipped");
    }
    bool gnss = gnss_minimal;
    if (!gnss_minimal) {
        characterize_gnss_pins();
        test_gnss_pin_swap_safely();
        gnss = gnss_tx_net_safe ? test_gnss() : false;
        if (!gnss_tx_net_safe) {
            ESP_LOGE(TAG, "GNSS active baud sweep SKIPPED to protect GPIO16 from a suspected Low clamp");
        }
    }
    diag.gnss = gnss;
    const bool gnss_fix = gnss ? test_gnss_fix(120) : false;
    bool sd = test_sd();

    ESP_LOGI(TAG, "================ BOARD TEST SUMMARY ================");
    ESP_LOGI(TAG, "CPU: %lu MHz, dual-core stress ON, temp %.1f C (cutoff %.1f C)",
             static_cast<unsigned long>(diag.cpu_mhz), diag.temp_c, STRESS_CUTOFF_C);
    ESP_LOGI(TAG, "PSRAM 8 MiB octal 80 MHz write/read/verify: %s", psram ? "PASS" : "FAIL");
    ESP_LOGI(TAG, "GNSS UART/MON-VER: %s (%s)", gnss ? "PASS" : "FAIL", diag.gnss_version);
    ESP_LOGI(TAG, "GNSS antenna/NAV-PVT position fix: %s (fix=%u SV=%u lat=%.7f lon=%.7f)",
             gnss_fix ? "PASS" : "TIMEOUT", diag.gnss_fix_type, diag.gnss_num_sv,
             diag.gnss_latitude, diag.gnss_longitude);
    ESP_LOGI(TAG, "IMU BNO055 I2C/RaceCapture telemetry: %s (addr 0x%02X chip 0x%02X)",
             imu ? "PASS" : "FAIL", imu_i2c_address, diag.imu_address);
    ESP_LOGI(TAG, "CAN1 TWAI/transceiver self reception: %s", can1 ? "PASS" : "FAIL");
    ESP_LOGI(TAG, "CAN2 MCP25625 SPI/internal loopback: %s", can2 ? "PASS" : "FAIL");
    ESP_LOGI(TAG, "CAN1 <-> CAN2 external physical bus: %s", can_external ? "PASS" : "FAIL");
    ESP_LOGI(TAG, "SDMMC write/read/verify: %s%s", sd ? "PASS" : "FAIL",
             sd ? (diag.sd_40mhz ? " at 40 MHz" : " at 20 MHz only") : "");
    ESP_LOGI(TAG, "74HC595 Knight Rider: PASS at boot; RUNNING again after CAN2 SPI release");
    ESP_LOGI(TAG, "RaceCapture: READY on native USB CDC and A105 UART0/COM8");
    ESP_LOGI(TAG, "====================================================");
}
