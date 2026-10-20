// 生CANリードオンリーロガー (実車OBD2直結用)
//
// 車両CANバスへ一切フレームを注入しない。受信専用。
// 受信フレームを「マイクロ秒タイムスタンプ付きの1行テキスト」でUSBシリアルへ流す。
// PC側は `pio device monitor` 等でファイルに落とすだけ(記録ツール本体は2-4-2)。
//
// ===== bus injection を防ぐ 3重の安全策 =====
//  1. TWAI を TWAI_MODE_LISTEN_ONLY で起動。
//     LISTEN_ONLY はハード的に「ドミナントを出さない/ACKを返さない/
//     エラーアクティブフラグを出さない/再送しない」ことが保証される受動モード。
//  2. TWAI の TX 信号は、トランシーバに繋がっていないダミーGPIO(GPIO10)へ割り当てる。
//     実配線(GPIO21→トランシーバTXD)には TWAI の信号が一切出ない。
//  3. その GPIO21 を単純GPIO出力の HIGH(=レセッシブ)で保持し、
//     トランシーバTXDが絶対にドミナントへ引かれないようにする。
//  → 仮にモード設定を書き換えても、2.と3.で物理的に注入不可。
//
// 配線(can_selftest / 2-1-2 と同じ):
//   GPIO20 (XIAO D7) <- MCP2562FD RXD(pin4)     … TWAI RX
//   GPIO21 (XIAO D6) -> MCP2562FD TXD(pin1)     … 本モードでは HIGH 固定(TWAI非接続)
//   MCP2562FD: VDD=5V, VIO=3.3V, VSS/STBY=GND, CANH(7)->OBD6, CANL(6)->OBD14, GND->OBD4/5
//   ※実車では卓上終端の120Ωを外すこと(車両バスは両端終端済み)。
//
// ===== MPP_SOC=1 (env esp32-c3-mpp-soc, ER-12) =====
//  電動二輪クラスのMPP充電器のCAN計測コネクタ(DIN 41524: 1=CAN Hi, 2=CAN Low, 3=GND)から
//  ID 0x402 の先頭2バイト(ビッグエンディアン・unsigned・0.01%)をSOCとして表示する。
//  生フレームの行は出さず、0x402だけを "SOC ..." の1行にする。
//  MPPを載せると充電が始まるため、載せた直後に最初に受けた値を "FIRST" として目立たせる
//  (電源投入後の最初の値、または0x402が SOC_GAP_US 以上途切れた後の最初の値)。
//  手順: 基板の終端120Ωを外す → USBでPCにつなぎ受信待機 → 充電器へ接続 → MPPを載せる。

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <atomic>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/ringbuf.h"
#include "driver/gpio.h"
#include "driver/twai.h"
#include "esp_timer.h"
#include "esp_err.h"

// ---- 設定 ----
#define CAN_RX_GPIO       GPIO_NUM_20    // <- MCP2562FD RXD
#define CAN_TXD_WIRE_GPIO GPIO_NUM_21    // -> MCP2562FD TXD、HIGH固定
#define CAN_TX_DECOY_GPIO GPIO_NUM_10    // TWAI TX のダミー割当先(トランシーバ非接続)
// ビットレートはビルドフラグ -D CAN_BITRATE_KBPS=<125|250|500|1000> で切替可能。
// 既定は500k（乗用車のHS-CAN/OBD2の標準値。NCロードスターで2-0確定、MAZDA2も同一想定）。
// 500kで1フレームも受信できない場合の切り分け用に250k等を用意している。
#ifndef CAN_BITRATE_KBPS
#define CAN_BITRATE_KBPS 500
#endif
#if   CAN_BITRATE_KBPS == 1000
#define CAN_TIMING        TWAI_TIMING_CONFIG_1MBITS()
#elif CAN_BITRATE_KBPS == 500
#define CAN_TIMING        TWAI_TIMING_CONFIG_500KBITS()
#elif CAN_BITRATE_KBPS == 250
#define CAN_TIMING        TWAI_TIMING_CONFIG_250KBITS()
#elif CAN_BITRATE_KBPS == 125
#define CAN_TIMING        TWAI_TIMING_CONFIG_125KBITS()
#else
#error "CAN_BITRATE_KBPS must be one of 125/250/500/1000"
#endif
#define RX_QUEUE_LEN      256
#define LINE_RB_BYTES     (48 * 1024)
#define LOG_LINE_MAX      80

static RingbufHandle_t s_rb;
static std::atomic<uint32_t> s_total{0};     // 受信総数
static std::atomic<uint32_t> s_window{0};    // 直近1秒の受信数
static std::atomic<uint32_t> s_drop_rb{0};   // ringbuf満杯で捨てた行数

#ifndef MPP_SOC
#define MPP_SOC 0
#endif
#if MPP_SOC
#define SOC_CAN_ID        0x402
#define SOC_GAP_US        3000000        // これ以上途切れたらMPPを載せ直したとみなす
static std::atomic<uint32_t> s_soc_count{0}; // 0x402の受信数

// 0x402 を1行にする。rx_taskからのみ呼ぶ(状態はこのタスク内だけで持つ)。
static int format_soc_line(char *line, size_t size, int64_t t, const twai_message_t &m)
{
    static int64_t  last_us  = 0;
    static int64_t  first_us = 0;
    static unsigned first_raw = 0;

    unsigned raw = ((unsigned)m.data[0] << 8) | m.data[1];   // 0.01%単位
    bool first = (last_us == 0) || (t - last_us > SOC_GAP_US);
    last_us = t;
    s_soc_count.fetch_add(1, std::memory_order_relaxed);

    if (first) {
        first_us  = t;
        first_raw = raw;
        return snprintf(line, size,
                        "\n########## FIRST SOC = %u.%02u %% ##########\n",
                        raw / 100, raw % 100);
    }
    int diff = (int)raw - (int)first_raw;
    return snprintf(line, size, "SOC %u.%02u %%  (first %u.%02u, %c%d.%02u, %llds)\n",
                    raw / 100, raw % 100, first_raw / 100, first_raw % 100,
                    diff < 0 ? '-' : '+', abs(diff) / 100, abs(diff) % 100,
                    (long long)((t - first_us) / 1000000));
}
#endif

static void rx_task(void *arg)
{
    char line[LOG_LINE_MAX];
    for (;;) {
        twai_message_t m;
        // LISTEN_ONLY: 送信は一切しない。受信のみ無限待ち。
        if (twai_receive(&m, portMAX_DELAY) != ESP_OK) {
            continue;
        }
        int64_t t = esp_timer_get_time();

#if MPP_SOC
        s_total.fetch_add(1, std::memory_order_relaxed);
        s_window.fetch_add(1, std::memory_order_relaxed);
        if (m.extd || m.rtr || m.identifier != SOC_CAN_ID || m.data_length_code < 2) {
            continue;
        }
        int sn = format_soc_line(line, sizeof(line), t, m);
        if (xRingbufferSend(s_rb, line, sn, 0) != pdTRUE) {
            s_drop_rb.fetch_add(1, std::memory_order_relaxed);
        }
        continue;
#endif

        // 形式: t_us,id_hex,ext,rtr,dlc,data_hex
        int n = snprintf(line, sizeof(line), "%lld,%03X,%d,%d,%d,",
                         (long long)t, (unsigned)m.identifier,
                         m.extd ? 1 : 0, m.rtr ? 1 : 0,
                         (int)m.data_length_code);
        int dl = m.rtr ? 0 : (int)m.data_length_code;
        for (int i = 0; i < dl && n < (int)sizeof(line) - 3; i++) {
            n += snprintf(line + n, sizeof(line) - n, "%02X", m.data[i]);
        }
        if (n < (int)sizeof(line) - 1) {
            line[n++] = '\n';
        }

        s_total.fetch_add(1, std::memory_order_relaxed);
        s_window.fetch_add(1, std::memory_order_relaxed);
        if (xRingbufferSend(s_rb, line, n, 0) != pdTRUE) {
            s_drop_rb.fetch_add(1, std::memory_order_relaxed);  // PC側が詰まった等。取りこぼしを可視化。
        }
    }
}

static void out_task(void *arg)
{
    int64_t t_next = esp_timer_get_time() + 1000000;
    for (;;) {
        // データが来るまで最大50msブロック(この待ちでIDLEタスクが走りWDTが養われる)。
        // 1件取れたら、あとは空になるまで非ブロックで一気に吐く。
        size_t sz = 0;
        char *item = (char *)xRingbufferReceive(s_rb, &sz, pdMS_TO_TICKS(50));
        while (item) {
            fwrite(item, 1, sz, stdout);
            vRingbufferReturnItem(s_rb, item);
            sz = 0;
            item = (char *)xRingbufferReceive(s_rb, &sz, 0);
        }
        fflush(stdout);

        int64_t now = esp_timer_get_time();
        if (now >= t_next) {
            uint32_t win = s_window.exchange(0, std::memory_order_relaxed);

            twai_status_info_t st;
            twai_get_status_info(&st);
            uint32_t alerts = 0;
            twai_read_alerts(&alerts, 0);

            const char *state =
                st.state == TWAI_STATE_RUNNING    ? "RUNNING" :
                st.state == TWAI_STATE_BUS_OFF     ? "BUS_OFF" :
                st.state == TWAI_STATE_RECOVERING  ? "RECOVERING" : "STOPPED";

#if MPP_SOC
            // SOCの行を読みやすくするため、状態は5秒に1回だけ短く出す。
            // frames>0 で soc=0 なら、つながってはいるが0x402が来ていない(MPP未装着等)。
            static int stat_div = 0;
            if (++stat_div >= 5) {
                stat_div = 0;
                printf("# stat frames=%u soc=%u buserr=%u state=%s\n",
                       (unsigned)s_total.load(std::memory_order_relaxed),
                       (unsigned)s_soc_count.load(std::memory_order_relaxed),
                       (unsigned)st.bus_error_count, state);
            }
            (void)win; (void)alerts;
#else
            printf("# stat t=%lld total=%u rate=%u/s drop_rb=%u "
                   "rx_missed=%u rx_overrun=%u buserr=%u tec=%d rec=%d state=%s alerts=0x%x\n",
                   (long long)now,
                   (unsigned)s_total.load(std::memory_order_relaxed), (unsigned)win,
                   (unsigned)s_drop_rb.load(std::memory_order_relaxed),
                   (unsigned)st.rx_missed_count, (unsigned)st.rx_overrun_count,
                   (unsigned)st.bus_error_count,
                   (int)st.tx_error_counter, (int)st.rx_error_counter,
                   state, (unsigned)alerts);
#endif
            fflush(stdout);
            // 取りこぼしが起きた分を1回だけ経過表示に出す用途で total は累積のまま。
            t_next += 1000000;
            // 長時間まったく受信が無くても statライン境界がズレないよう追従
            while (t_next <= now) t_next += 1000000;
        }
        // 高負荷が続いてもIDLEタスクへ確実にCPUを渡す(WDT保護)。1 tick = 10ms。
        // 48KBのリングバッファがこの間のバーストを吸収する。
        vTaskDelay(1);
    }
}

extern "C" void app_main(void)
{
    // --- 安全策3: トランシーバTXDへ繋がるGPIO21をレセッシブ(HIGH)で固定 ---
    gpio_config_t txd_hold = {};
    txd_hold.pin_bit_mask = (1ULL << CAN_TXD_WIRE_GPIO);
    txd_hold.mode = GPIO_MODE_OUTPUT;
    txd_hold.pull_up_en = GPIO_PULLUP_ENABLE;
    txd_hold.pull_down_en = GPIO_PULLDOWN_DISABLE;
    txd_hold.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&txd_hold);
    gpio_set_level(CAN_TXD_WIRE_GPIO, 1);   // recessive

    vTaskDelay(pdMS_TO_TICKS(300));
    printf("\n\n");
    printf("# ===== CAN read-only logger (LISTEN_ONLY / no bus injection) =====\n");
    printf("# safety: mode=LISTEN_ONLY, TWAI-TX=decoy GPIO%d (not wired), "
           "GPIO%d held HIGH(recessive)\n",
           (int)CAN_TX_DECOY_GPIO, (int)CAN_TXD_WIRE_GPIO);
    printf("# bitrate=%dk, RX=GPIO%d\n", (int)CAN_BITRATE_KBPS, (int)CAN_RX_GPIO);
#if MPP_SOC
    printf("# MPP SOC mode: shows CAN ID 0x%03X bytes0-1 x 0.01%%. Use the FIRST value.\n",
           (unsigned)SOC_CAN_ID);
    printf("# remove the 120ohm terminator. then: charger CAN connector -> set MPP on charger\n");
#else
    printf("# line format: t_us,id_hex,ext,rtr,dlc,data_hex   (lines starting with '#' are status)\n");
#endif

    // --- 安全策1+2: LISTEN_ONLY + TX信号はダミーGPIOへ ---
    twai_general_config_t g =
        TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_DECOY_GPIO, CAN_RX_GPIO, TWAI_MODE_LISTEN_ONLY);
    g.rx_queue_len = RX_QUEUE_LEN;
    g.tx_queue_len = 0;                 // 送信キューは不要
    g.alerts_enabled = TWAI_ALERT_NONE;

    twai_timing_config_t t = CAN_TIMING;
    twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    ESP_ERROR_CHECK(twai_driver_install(&g, &t, &f));
    twai_reconfigure_alerts(
        TWAI_ALERT_RX_QUEUE_FULL | TWAI_ALERT_RX_FIFO_OVERRUN |
        TWAI_ALERT_BUS_ERROR | TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF,
        NULL);
    ESP_ERROR_CHECK(twai_start());
    printf("# TWAI started in LISTEN_ONLY. logging...\n");
    fflush(stdout);

    s_rb = xRingbufferCreate(LINE_RB_BYTES, RINGBUF_TYPE_NOSPLIT);
    if (!s_rb) {
        printf("# FATAL: ringbuffer alloc failed\n");
        return;
    }
    xTaskCreate(rx_task,  "can_rx",  4096, NULL, 6, NULL);
    xTaskCreate(out_task, "can_out", 6144, NULL, 5, NULL);
}
