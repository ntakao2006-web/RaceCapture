// SDカード(SDMMC 4bit)配線確認用の検証コード。
// ESP-IDF公式サンプル(examples/storage/sd_card/sdmmc)のapp_mainを土台に、
// 実配線したピン(GPIO12=CLK/GPIO11=CMD/GPIO13=D0/GPIO14=D1/GPIO9=D2/GPIO10=D3、
// ARCHITECTURE.md「SDカードインターフェースの設計方針」参照)を直接指定し、
// マウント→ファイル書き込み→読み込み→アンマウントまでを確認する。
// 外付け10kΩプルアップの実配線を検証したいため、内部プルアップは有効にしない。

#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "esp_log.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdmmc_host.h"
#include "driver/gpio.h"
#include "esp_cpu.h"

static const char *TAG = "sd_card_test";
#define MOUNT_POINT "/sdcard"

// 配線・プルアップの切り分け診断(ESP-IDF公式sd_card_pin_check相当を簡略移植):
// 各信号線を一度Lowに落とし、外付けプルアップだけでどれだけ速くHighへ戻るかを
// CPUサイクル数で計測する。10000サイクル(160MHz動作で約62us)に達してもHighに
// 戻らなければタイムアウト=そのラインのプルアップが機能していない疑い。
static uint32_t cycles_until_high(gpio_num_t pin, uint32_t timeout_cycles)
{
    uint32_t start = esp_cpu_get_cycle_count();
    while (gpio_get_level(pin) == 0 && esp_cpu_get_cycle_count() - start < timeout_cycles) {
        ;
    }
    return esp_cpu_get_cycle_count() - start;
}

static void diagnose_pins(void)
{
    static const char *names[] = {"CLK", "CMD", "D0", "D1", "D2", "D3"};
    static const gpio_num_t pins[] = {GPIO_NUM_12, GPIO_NUM_11, GPIO_NUM_13, GPIO_NUM_14, GPIO_NUM_9, GPIO_NUM_10};
    const uint32_t timeout_cycles = 10000;

    for (int i = 0; i < 6; i++) {
        gpio_config_t io_conf = {};
        io_conf.intr_type = GPIO_INTR_DISABLE;
        io_conf.mode = GPIO_MODE_INPUT_OUTPUT_OD;
        io_conf.pin_bit_mask = 1ULL << pins[i];
        io_conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
        io_conf.pull_up_en = GPIO_PULLUP_DISABLE;
        gpio_config(&io_conf);
    }

    printf("\n**** PIN recovery time (外付けプルアップのみ、内部プルアップ無効) ****\n\n");
    for (int i = 0; i < 6; i++) {
        gpio_set_level(pins[i], 0);
        usleep(100);
        gpio_set_level(pins[i], 1);
        uint32_t cycles = cycles_until_high(pins[i], timeout_cycles);
        printf("PIN %2d %3s  %lu cycles%s\n", (unsigned)pins[i], names[i], (unsigned long)cycles,
               cycles >= timeout_cycles ? "  <-- TIMEOUT (プルアップ未接続/断線の疑い)" : "");
    }
    printf("\n");
}

extern "C" void app_main(void)
{
    diagnose_pins();

    esp_vfs_fat_sdmmc_mount_config_t mount_config = {};
    mount_config.format_if_mount_failed = false;
    mount_config.max_files = 5;
    mount_config.allocation_unit_size = 16 * 1024;
    sdmmc_card_t *card;
    const char mount_point[] = MOUNT_POINT;

    ESP_LOGI(TAG, "Initializing SD card (SDMMC 4bit)");

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();

    sdmmc_slot_config_t slot_config = SDMMC_SLOT_CONFIG_DEFAULT();
    slot_config.width = 4;
    slot_config.clk = GPIO_NUM_12;
    slot_config.cmd = GPIO_NUM_11;
    slot_config.d0 = GPIO_NUM_13;
    slot_config.d1 = GPIO_NUM_14;
    slot_config.d2 = GPIO_NUM_9;
    slot_config.d3 = GPIO_NUM_10;

    ESP_LOGI(TAG, "Mounting filesystem");
    esp_err_t ret = esp_vfs_fat_sdmmc_mount(mount_point, &host, &slot_config, &mount_config, &card);
    if (ret != ESP_OK) {
        if (ret == ESP_FAIL) {
            ESP_LOGE(TAG, "Failed to mount filesystem");
        } else {
            ESP_LOGE(TAG, "Failed to initialize the card (%s). Check wiring / pullups.", esp_err_to_name(ret));
        }
        return;
    }
    ESP_LOGI(TAG, "Filesystem mounted");
    sdmmc_card_print_info(stdout, card);

    const char *file_path = MOUNT_POINT "/hello.txt";
    ESP_LOGI(TAG, "Writing %s", file_path);
    FILE *f = fopen(file_path, "w");
    if (f == NULL) {
        ESP_LOGE(TAG, "Failed to open file for writing");
        return;
    }
    fprintf(f, "Hello %s!\n", card->cid.name);
    fclose(f);
    ESP_LOGI(TAG, "File written");

    ESP_LOGI(TAG, "Reading %s", file_path);
    f = fopen(file_path, "r");
    if (f == NULL) {
        ESP_LOGE(TAG, "Failed to open file for reading");
        return;
    }
    char line[64];
    fgets(line, sizeof(line), f);
    fclose(f);
    char *pos = strchr(line, '\n');
    if (pos) {
        *pos = '\0';
    }
    ESP_LOGI(TAG, "Read from file: '%s'", line);

    esp_vfs_fat_sdcard_unmount(mount_point, card);
    ESP_LOGI(TAG, "Card unmounted. SD wiring check: PASS");
}
