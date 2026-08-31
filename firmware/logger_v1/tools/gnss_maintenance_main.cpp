// TEMPORARY image: explicit UART bridge for the documented GNSS service procedure.
// Not part of the normal logger build. No NVS/SD/OTP writes happen autonomously.
// COM8: ? => banner; B<baud> => set GNSS UART baud; T<UBX hex> => send one frame.
// R<hex> lines contain raw GNSS RX bytes. The host is responsible for UBX validation.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static void output(const char *s) { uart_write_bytes(UART_NUM_0, s, strlen(s)); }
static int nibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}
static void command(char *s) {
    if (!strcmp(s, "?")) {
        output("GNSS_SERVICE_V1 NO_AUTOMATIC_WRITES\n");
        return;
    }
    if (*s == 'B') {
        char *end = nullptr;
        long rate = strtol(s + 1, &end, 10);
        if (*end || (rate != 9600 && rate != 38400 && rate != 57600 && rate != 115200)) {
            output("ERR BAUD\n");
            return;
        }
        uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(1000));
        uart_flush_input(UART_NUM_1);
        if (uart_set_baudrate(UART_NUM_1, rate) == ESP_OK) output("OK B\n");
        else output("ERR B\n");
        return;
    }
    if (*s == 'T') {
        size_t n = strlen(s + 1);
        uint8_t data[264];
        if (n < 16 || n % 2 || n > sizeof(data) * 2) {
            output("ERR LENGTH\n");
            return;
        }
        for (size_t i = 0; i < n / 2; ++i) {
            int hi = nibble(s[1 + i * 2]), lo = nibble(s[2 + i * 2]);
            if (hi < 0 || lo < 0) { output("ERR HEX\n"); return; }
            data[i] = uint8_t(hi * 16 + lo);
        }
        size_t bytes = n / 2;
        uint8_t a = 0, b = 0;
        for (size_t i = 2; i < bytes - 2; ++i) { a += data[i]; b += a; }
        if (data[0] != 0xb5 || data[1] != 0x62 ||
            size_t(data[4] + 256U * data[5]) + 8 != bytes ||
            a != data[bytes - 2] || b != data[bytes - 1]) {
            output("ERR UBX\n"); return;
        }
        if (uart_write_bytes(UART_NUM_1, data, bytes) == int(bytes) &&
            uart_wait_tx_done(UART_NUM_1, pdMS_TO_TICKS(1000)) == ESP_OK)
            output("OK T\n");
        else output("ERR T NO_RETRY\n");
        return;
    }
    output("ERR COMMAND\n");
}
extern "C" void app_main(void) {
    esp_log_level_set("*", ESP_LOG_NONE);
    uart_config_t c = {};
    c.baud_rate = 115200;
    c.data_bits = UART_DATA_8_BITS;
    c.parity = UART_PARITY_DISABLE;
    c.stop_bits = UART_STOP_BITS_1;
    c.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
    c.source_clk = UART_SCLK_DEFAULT;
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 2048, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &c));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_0, 43, 44, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    ESP_ERROR_CHECK(uart_driver_install(UART_NUM_1, 8192, 0, 0, nullptr, 0));
    ESP_ERROR_CHECK(uart_param_config(UART_NUM_1, &c));
    ESP_ERROR_CHECK(uart_set_pin(UART_NUM_1, 16, 15, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
    // Keep reset and SAFEBOOT/TIMEPULSE-related signals high impedance.
    gpio_set_direction(GPIO_NUM_9, GPIO_MODE_INPUT);
    gpio_set_direction(GPIO_NUM_8, GPIO_MODE_INPUT);
    output("GNSS_SERVICE_V1 NO_AUTOMATIC_WRITES\n");
    char line[530];
    size_t used = 0;
    bool discard = false;
    while (true) {
        uint8_t data[128];
        int n = uart_read_bytes(UART_NUM_0, data, sizeof(data), 0);
        for (int i = 0; i < n; ++i) {
            if (data[i] == '\r' || data[i] == '\n') {
                if (used && !discard) { line[used] = 0; command(line); }
                used = 0; discard = false;
            } else if (used < sizeof(line) - 1 && !discard) line[used++] = data[i];
            else discard = true;
        }
        n = uart_read_bytes(UART_NUM_1, data, sizeof(data), pdMS_TO_TICKS(1));
        if (n > 0) {
            static const char hex[] = "0123456789ABCDEF";
            char out[260] = {'R'};
            for (int i = 0; i < n; ++i) {
                out[1 + 2 * i] = hex[data[i] >> 4];
                out[2 + 2 * i] = hex[data[i] & 15];
            }
            out[1 + 2 * n] = '\n';
            uart_write_bytes(UART_NUM_0, out, 2 + 2 * n);
        }
        vTaskDelay(pdMS_TO_TICKS(1));
    }
}
