#include <cstdint>

#include "driver/gpio.h"
#include "esp_err.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

namespace {

constexpr gpio_num_t HC595_SER = GPIO_NUM_40;
constexpr gpio_num_t HC595_CLK = GPIO_NUM_39;
constexpr gpio_num_t HC595_LATCH = GPIO_NUM_45;
constexpr TickType_t STEP_TIME = pdMS_TO_TICKS(120);

void write_hc595(uint8_t value)
{
    for (int bit = 7; bit >= 0; --bit) {
        gpio_set_level(HC595_SER, (value >> bit) & 1U);
        gpio_set_level(HC595_CLK, 1);
        gpio_set_level(HC595_CLK, 0);
    }
    gpio_set_level(HC595_LATCH, 1);
    gpio_set_level(HC595_LATCH, 0);
}

}  // namespace

extern "C" void app_main(void)
{
    gpio_config_t outputs = {};
    outputs.pin_bit_mask = (1ULL << HC595_SER) |
                           (1ULL << HC595_CLK) |
                           (1ULL << HC595_LATCH);
    outputs.mode = GPIO_MODE_OUTPUT;
    outputs.pull_up_en = GPIO_PULLUP_DISABLE;
    outputs.pull_down_en = GPIO_PULLDOWN_DISABLE;
    outputs.intr_type = GPIO_INTR_DISABLE;
    ESP_ERROR_CHECK(gpio_config(&outputs));

    gpio_set_level(HC595_SER, 0);
    gpio_set_level(HC595_CLK, 0);
    gpio_set_level(HC595_LATCH, 0);
    write_hc595(0);
    ESP_LOGI("knight_rider", "74HC595 continuous test started: SER=40 CLK=39 LATCH=45");

    while (true) {
        for (int position = 0; position < 8; ++position) {
            write_hc595(static_cast<uint8_t>(1U << position));
            vTaskDelay(STEP_TIME);
        }
        for (int position = 6; position >= 1; --position) {
            write_hc595(static_cast<uint8_t>(1U << position));
            vTaskDelay(STEP_TIME);
        }
    }
}
