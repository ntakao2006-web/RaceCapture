// MCP2562FD 配線セルフテスト (TWAI 自己受信モード)
//
// 車載CANに繋がず、卓上で XIAO ESP32C3 + MCP2562FD-E/P + 120ohm だけで実行する。
// TWAI を NO_ACK モードにし、self フラグ付きフレームを送信すると、
// 他ノードが居なくても自分の送信を自分で受信できる。
// フレームがCANH/CANL(120ohm終端)を physically 一周して返ってくれば、
//   - GPIO21/GPIO20 の割当
//   - TXD(1)/RXD(4) の配線
//   - VDD/VIO/GND/STBY の給電
//   - MCP2562FD 本体
//   - 120ohm 終端
//   - 500kbit タイミング設定
// が全て正常、と判定できる。
//
// 結線表(このプロジェクトの前提):
//   TWAI TX = GPIO21 (XIAO D6) -> MCP2562FD TXD (pin 1)
//   TWAI RX = GPIO20 (XIAO D7) -> MCP2562FD RXD (pin 4)

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/twai.h"
#include "esp_err.h"

#define CAN_TX_GPIO   GPIO_NUM_21
#define CAN_RX_GPIO   GPIO_NUM_20

#define ITERATIONS    20

static void run_batch(void)
{
    int pass = 0, fail = 0;
    uint8_t last_state_ok = 1;

    for (uint32_t seq = 0; seq < ITERATIONS; seq++) {
        twai_message_t tx = {};
        tx.identifier = 0x123;
        tx.data_length_code = 8;
        tx.self = 1;                                  // 自己受信要求
        for (int i = 0; i < 8; i++) tx.data[i] = (uint8_t)(seq + i);

        esp_err_t te = twai_transmit(&tx, pdMS_TO_TICKS(1000));

        twai_message_t rx = {};
        esp_err_t re = twai_receive(&rx, pdMS_TO_TICKS(1000));

        twai_status_info_t st = {};
        twai_get_status_info(&st);

        bool match = (re == ESP_OK) &&
                     (rx.identifier == 0x123) &&
                     (rx.data_length_code == 8) &&
                     (rx.data[0] == (uint8_t)seq);

        if (match) {
            pass++;
            printf("[%2d] TX=%-11s RX=OK   d0=0x%02X  TEC=%d REC=%d  => MATCH\n",
                   (int)seq, esp_err_to_name(te), rx.data[0],
                   (int)st.tx_error_counter, (int)st.rx_error_counter);
        } else {
            fail++;
            last_state_ok = 0;
            printf("[%2d] TX=%-11s RX=%-11s  TEC=%d REC=%d state=%d  => NG\n",
                   (int)seq, esp_err_to_name(te), esp_err_to_name(re),
                   (int)st.tx_error_counter, (int)st.rx_error_counter, (int)st.state);
        }
        vTaskDelay(pdMS_TO_TICKS(250));
    }

    printf("\n---- batch result: PASS=%d / NG=%d ----\n", pass, fail);
    if (fail == 0) {
        printf("[OK] 配線OK。TX/RX/トランシーバ/120ohm/500k設定すべて正常。\n");
        printf("     次: firmware側を listen-only に切替えて実車OBDへ。車では120ohmを外す。\n");
    } else if (pass == 0) {
        printf("[NG] 全滅。疑う順:\n");
        printf("     (1) TXD<->RXD の配線が逆  (2) GPIO番号違い(21/20)\n");
        printf("     (3) VIO/VDD/GND/STBY の未接続  (4) 120ohm 未接続  (5) トランシーバ不良\n");
    } else {
        printf("[NG] 断続的に失敗。接触不良/はんだ不良/120ohm やジャンパの接触を疑う。\n");
    }
    (void)last_state_ok;
    printf("--------------------------------------\n\n");
}

extern "C" void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(1500));
    printf("\n\n==================================================\n");
    printf(" MCP2562FD wiring self-test (TWAI self-reception)\n");
    printf(" TWAI TX=GPIO%d  RX=GPIO%d   500kbit   mode=NO_ACK\n",
           (int)CAN_TX_GPIO, (int)CAN_RX_GPIO);
    printf(" 前提: 車載CAN未接続 / CANH-CANL 間に 120ohm あり\n");
    printf("==================================================\n\n");

    twai_general_config_t g_config =
        TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_GPIO, CAN_RX_GPIO, TWAI_MODE_NO_ACK);
    twai_timing_config_t t_config = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    esp_err_t err = twai_driver_install(&g_config, &t_config, &f_config);
    if (err != ESP_OK) {
        printf("[NG] twai_driver_install failed: %s\n", esp_err_to_name(err));
        printf("     -> GPIO番号が他機能と衝突している可能性。\n");
        return;
    }
    err = twai_start();
    if (err != ESP_OK) {
        printf("[NG] twai_start failed: %s\n", esp_err_to_name(err));
        twai_driver_uninstall();
        return;
    }
    printf("[OK] TWAI driver install / start 完了 (mode=NO_ACK, 500kbit)\n\n");

    // 書き込み直後にログを取り逃しても次サイクルで拾えるよう、無限ループで繰り返す。
    for (;;) {
        run_batch();
        vTaskDelay(pdMS_TO_TICKS(3000));
    }
}
