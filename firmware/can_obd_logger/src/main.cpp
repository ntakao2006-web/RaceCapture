// 生CANロガー + OBD2 PIDポーラー (実車OBD2直結用 / Phase2-2-1)
//
// can_logger の受信ロギング中核(受信タスク→リングバッファ→出力タスク)をそのまま流用し、
// 「OBD2 mode 01 のPIDリクエストを定期送信するタスク」を1本追加したもの。
// 応答フレーム(0x7E8..0x7EF)は他の生CANフレームと全く同じ経路・同じ
// esp_timer_get_time() のµsタイムスタンプで記録されるため、
// 生CAN候補バイトと基準値(車速・回転数等)の時間軸が原理的に一致する(2-4-5の狙い)。
//
// ============================================================
//  ★★ 警告: このファームウェアは CAN バスへ送信する ★★
// ============================================================
//  TWAI_MODE_NORMAL で動作するため、
//    (1) OBD2リクエスト(0x7E0 または 0x7DF)を能動的に送信する
//    (2) バス上の全フレームに対してACK(ドミナント)を返す
//  これは市販OBD2スキャンツール(2-0で使用したELM327)と同じ振る舞いであり、
//  車両に対して異常な操作ではない。ただし「完全受動」ではない。
//
//  ・完全受動での観測が必要なとき(2-4-3の操作差分検出など)は
//    firmware/can_logger (LISTEN_ONLY・送信不能) を使うこと。
//  ・firmware/can_selftest の NO_ACK送信 / blastモードは実車へ絶対に繋がない。
// ============================================================
//
// 出力形式は can_logger と完全互換(PC側 can_capture_logger.py の変更不要):
//   フレーム行 : t_us,id_hex,ext,rtr,dlc,data_hex
//                ※自分が送信したリクエストも同形式で記録する(ID 0x7E0/0x7DF)。
//                  TWAIは自己受信しないため、送信時刻はポーラータスクが自分で書く。
//   ステータス行: '#' 始まり (key=value 形式。can_capture_logger.py はトークン解析なので
//                 OBD用フィールドを追加しても互換)
//
// 実行時コマンド(USBシリアルへ1文字送るだけ。任意・失敗しても記録は継続):
//   'p' … PIDポーリング停止(完全受動の観測に切替。ただしACKは返る)
//   'r' … PIDポーリング再開
//
// 配線(can_logger / can_selftest / 2-1-2 と同一):
//   GPIO21 (XIAO D6) -> MCP2562FD TXD(pin1)   … 本ファームでは実TX
//   GPIO20 (XIAO D7) <- MCP2562FD RXD(pin4)
//   MCP2562FD: VDD=5V, VIO=3.3V, VSS/STBY=GND, CANH(7)->OBD6, CANL(6)->OBD14, GND->OBD4/5
//   ※実車では卓上終端の120Ωを外すこと(車両バスは両端終端済み)。

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <atomic>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/ringbuf.h"
#include "driver/gpio.h"
#include "driver/twai.h"
#include "driver/usb_serial_jtag.h"
#include "esp_timer.h"
#include "esp_err.h"

// ---- 配線・バス設定 ----
#define CAN_TX_GPIO       GPIO_NUM_21    // -> MCP2562FD TXD (can_logger と違い実TXとして使う)
#define CAN_RX_GPIO       GPIO_NUM_20    // <- MCP2562FD RXD
#define CAN_TIMING        TWAI_TIMING_CONFIG_500KBITS()  // NCロードスターOBD2=500k(2-0で確定)
#define RX_QUEUE_LEN      256
#define TX_QUEUE_LEN      5
#define LINE_RB_BYTES     (48 * 1024)
#define LOG_LINE_MAX      96

// ---- OBD2設定 ----
#define OBD_REQ_ID_PHYS   0x7E0          // 物理アドレス(ECU#1)。複数ECU同時応答を避けられるので既定。
#define OBD_REQ_ID_FUNC   0x7DF          // 機能アドレス(ブロードキャスト)。応答が無いとき自動で切替。
#define OBD_RESP_ID_LO    0x7E8          // 応答IDレンジ 0x7E8..0x7EF
#define OBD_RESP_ID_HI    0x7EF
#define OBD_PAD_BYTE      0x55           // ISO-TP パディング。応答が無い場合 0x00 も試す価値あり。
#define OBD_TIMEOUT_US    60000          // 1リクエストの応答待ち上限(60ms)
#define OBD_FALLBACK_FAIL 30             // 連続失敗がこの数に達したらリクエストIDを切替(応答ゼロのときのみ)
// ポーラータスクの刻み。**必ず1以上のtick数で指定すること**。
// FreeRTOSのtickは10ms(100Hz)なので pdMS_TO_TICKS(5) は 0 tick になり、
// vTaskDelay(0) はブロックせずIDLEタスクへCPUを渡さない → タスクWDTが発火する。
// 1 tick = 10ms あればリクエスト間隔の分解能としては十分(最速でも100req/s)。
#define OBD_POLL_TICKS    1

// PIDテーブル。period_ms ごとに1回リクエストする。
// 高レート群は 2-4-5 の相関検証の基準値として使うもの(→ 対応が疑われる生CAN IDを併記)。
// PIDの対応可否は 2-0-4 の実測(OBD2_SURVEY.md「対応PID一覧」)に基づく。
typedef struct {
    uint8_t     pid;
    uint16_t    period_ms;
    const char *name;
} obd_pid_t;

static const obd_pid_t PID_TABLE[] = {
    // --- 高レート群(相関検証の主役) ---
    {0x0C,  100, "rpm"},        // エンジン回転数      -> 0x201 候補
    {0x0D,  100, "speed"},      // 車速                -> 0x201 / 0x4B0(4輪ホイールスピード) 候補
    {0x11,  100, "throttle"},   // スロットル開度      -> 0x200 / 0x215 候補
    {0x49,  100, "accel_d"},    // アクセルペダル位置D -> 0x201 候補
    {0x04,  200, "load"},       // エンジン負荷計算値  -> 0x240 候補
    // --- 低レート群 ---
    {0x05, 1000, "coolant"},    // 水温 -> 0x240 byte1 (2-0-17で一致確認済み。答え合わせ用)
    {0x0E, 1000, "timing"},     // 点火時期進角 -> 0x240 候補
    {0x0F, 1000, "iat"},        // 吸気温       -> 0x240 候補
    {0x0B, 1000, "map"},        // 吸気管絶対圧
    {0x10, 1000, "maf"},        // MAF空気流量
    {0x45, 1000, "rel_thr"},    // 相対スロットル開度
    {0x4A, 1000, "accel_e"},    // アクセルペダル位置E
    {0x42, 2000, "batt"},       // バッテリー(モジュール)電圧
    {0x33, 5000, "baro"},       // 大気圧
    // --- 車種によっては未対応の追加群 ---
    // 応答しないPIDは s_pid_fail のバックオフで自動的に間隔が最大64倍まで伸びるため、
    // 対応していない車両で回しても上の群のポーリングレートはほぼ食わない。
    // 下記は 2-0-6 のレクサスUX(2022年式)実測(OBD2_SURVEY.md)で応答が確認できたもの。
    {0x5C, 1000, "oil_temp"},   // エンジン油温。UXは対応、NCロードスターは非対応
    {0x47, 1000, "abs_thr_b"},  // 絶対スロットル位置B
    {0x4C, 1000, "cmd_thr"},    // 指令スロットルアクチュエータ制御
    {0x43, 1000, "abs_load"},   // 絶対負荷値
    {0x44, 2000, "equiv_ratio"},// 燃料/空気当量比の指令値
    {0x34, 2000, "o2_wr"},      // O2センサー1 広域AFR(当量比/電流)
    {0x1F, 5000, "run_time"},   // 始動後経過時間。ECU側の経過秒とログの時間軸の突き合わせ用
};
#define PID_COUNT (sizeof(PID_TABLE) / sizeof(PID_TABLE[0]))

static RingbufHandle_t s_rb;
static std::atomic<uint32_t> s_total{0};        // 受信総数
static std::atomic<uint32_t> s_window{0};       // 直近1秒の受信数
static std::atomic<uint32_t> s_drop_rb{0};      // ringbuf満杯で捨てた行数

// OBD状態
static std::atomic<uint32_t> s_obd_sent{0};
static std::atomic<uint32_t> s_obd_resp{0};
static std::atomic<uint32_t> s_obd_timeout{0};
static std::atomic<uint32_t> s_obd_txerr{0};
static std::atomic<int>      s_inflight_pid{-1};    // 応答待ち中のPID。-1=待ちなし
static std::atomic<int>      s_inflight_idx{-1};    // 同じくPID_TABLE上の添字
static std::atomic<int64_t>  s_inflight_since{0};
static std::atomic<uint32_t> s_req_id{OBD_REQ_ID_PHYS};
static std::atomic<bool>     s_paused{false};

// 直近デコード値(現地での目視サニティチェック用。'-1'は未取得)
static std::atomic<int> s_v_rpm{-1};
static std::atomic<int> s_v_speed{-1};
static std::atomic<int> s_v_coolant{-1000};
static std::atomic<int> s_v_throttle{-1};

static int64_t s_last_sent_us[PID_COUNT];

// PIDごとの連続失敗回数(タイムアウト/否定応答)。
// 応答しないPIDが混ざっていても、そのPIDだけ間隔を指数的に伸ばして
// 応答するPIDのポーリングレートを守るためのバックオフに使う。
// 成功したら0に戻すので、一時的なバス不調からは自動で復帰する。
static std::atomic<uint8_t> s_pid_fail[PID_COUNT];
#define PID_FAIL_BACKOFF_MAX 6   // 最大 2^6 = 64倍まで間隔を伸ばす

// 1行をリングバッファへ流す。rx_task / obd_task / ctrl_task から呼ばれる(xRingbufferSendはスレッドセーフ)。
static void emit_line(const char *buf, int len)
{
    if (xRingbufferSend(s_rb, buf, len, 0) != pdTRUE) {
        s_drop_rb.fetch_add(1, std::memory_order_relaxed);  // PC側が詰まった等。取りこぼしを可視化。
    }
}

static void emit_frame_line(int64_t t, uint32_t id, bool extd, bool rtr,
                            int dlc, const uint8_t *data)
{
    char line[LOG_LINE_MAX];
    int n = snprintf(line, sizeof(line), "%lld,%03X,%d,%d,%d,",
                     (long long)t, (unsigned)id, extd ? 1 : 0, rtr ? 1 : 0, dlc);
    int dl = rtr ? 0 : dlc;
    for (int i = 0; i < dl && n < (int)sizeof(line) - 3; i++) {
        n += snprintf(line + n, sizeof(line) - n, "%02X", data[i]);
    }
    if (n < (int)sizeof(line) - 1) {
        line[n++] = '\n';
    }
    emit_line(line, n);
}

// OBD2応答(mode 01)を最小限デコードしてステータス行表示用に保持する。
// ※本格的な物理値変換はPC側(can_obd_extract.py)で行う。ここは現地確認用。
static void obd_decode_for_display(uint8_t pid, const uint8_t *d, int nbytes)
{
    if (nbytes < 1) return;
    switch (pid) {
        case 0x0C:  // RPM = ((A*256)+B)/4
            if (nbytes >= 2) s_v_rpm.store((((int)d[0] << 8) | d[1]) / 4, std::memory_order_relaxed);
            break;
        case 0x0D:  // 車速 = A [km/h]
            s_v_speed.store((int)d[0], std::memory_order_relaxed);
            break;
        case 0x05:  // 水温 = A - 40 [degC]
            s_v_coolant.store((int)d[0] - 40, std::memory_order_relaxed);
            break;
        case 0x11:  // スロットル = A*100/255 [%]
            s_v_throttle.store((int)d[0] * 100 / 255, std::memory_order_relaxed);
            break;
        default:
            break;
    }
}

static void rx_task(void *arg)
{
    for (;;) {
        twai_message_t m;
        if (twai_receive(&m, portMAX_DELAY) != ESP_OK) {
            continue;
        }
        int64_t t = esp_timer_get_time();

        s_total.fetch_add(1, std::memory_order_relaxed);
        s_window.fetch_add(1, std::memory_order_relaxed);
        emit_frame_line(t, m.identifier, m.extd, m.rtr, (int)m.data_length_code, m.data);

        // --- OBD2応答の照合(単一フレーム応答のみ。mode 01 の1PID要求は必ず1フレームに収まる) ---
        if (!m.extd && !m.rtr &&
            m.identifier >= OBD_RESP_ID_LO && m.identifier <= OBD_RESP_ID_HI &&
            m.data_length_code >= 3) {

            if (m.data[1] == 0x41) {
                // 肯定応答: [0]=長さ(PCI) [1]=0x41(=0x40+mode01) [2]=PID [3..]=データ
                uint8_t pid = m.data[2];
                int nbytes = (int)m.data[0] - 2;         // 長さからmode/PIDの2バイトを引く
                if (nbytes < 0) nbytes = 0;
                if (nbytes > (int)m.data_length_code - 3) nbytes = (int)m.data_length_code - 3;
                obd_decode_for_display(pid, &m.data[3], nbytes);

                if (s_inflight_pid.load(std::memory_order_relaxed) == (int)pid) {
                    int idx = s_inflight_idx.load(std::memory_order_relaxed);
                    if (idx >= 0 && idx < (int)PID_COUNT) {
                        s_pid_fail[idx].store(0, std::memory_order_relaxed);  // 応答した → バックオフ解除
                    }
                    s_inflight_pid.store(-1, std::memory_order_relaxed);
                }
                s_obd_resp.fetch_add(1, std::memory_order_relaxed);

            } else if (m.data[1] == 0x7F && m.data[2] == 0x01) {
                // 否定応答: [1]=0x7F [2]=拒否したサービス(0x01) [3]=NRC
                // PIDは含まれないが、同時に1リクエストしか投げていないので現在の待ちを解除してよい。
                // 60msのタイムアウトを待たずに次へ進めるのが狙い(スケジュールの巻き添えを防ぐ)。
                int idx = s_inflight_idx.load(std::memory_order_relaxed);
                if (idx >= 0 && idx < (int)PID_COUNT) {
                    uint8_t f = s_pid_fail[idx].load(std::memory_order_relaxed);
                    if (f < PID_FAIL_BACKOFF_MAX) s_pid_fail[idx].store(f + 1, std::memory_order_relaxed);
                }
                s_inflight_pid.store(-1, std::memory_order_relaxed);
                s_obd_timeout.fetch_add(1, std::memory_order_relaxed);
            }
        }
    }
}

static void obd_task(void *arg)
{
    char line[LOG_LINE_MAX];
    uint32_t consec_fail = 0;

    // 起動直後は受信だけ先に流したいので少し待つ(バスが生きているかを先に確認できる)。
    vTaskDelay(pdMS_TO_TICKS(1000));

    for (;;) {
        vTaskDelay(OBD_POLL_TICKS);
        if (s_paused.load(std::memory_order_relaxed)) continue;

        int64_t now = esp_timer_get_time();

        // 応答待ち中ならタイムアウトまで次を送らない(自動スロットリングも兼ねる)。
        int inflight = s_inflight_pid.load(std::memory_order_relaxed);
        if (inflight >= 0) {
            if (now - s_inflight_since.load(std::memory_order_relaxed) < OBD_TIMEOUT_US) {
                continue;
            }
            int idx = s_inflight_idx.load(std::memory_order_relaxed);
            if (idx >= 0 && idx < (int)PID_COUNT) {
                uint8_t f = s_pid_fail[idx].load(std::memory_order_relaxed);
                if (f < PID_FAIL_BACKOFF_MAX) s_pid_fail[idx].store(f + 1, std::memory_order_relaxed);
            }
            s_inflight_pid.store(-1, std::memory_order_relaxed);
            s_obd_timeout.fetch_add(1, std::memory_order_relaxed);
            consec_fail++;

            // 一度も応答が無いままなら、物理アドレス <-> 機能アドレスを切替えて再挑戦。
            // (実車1回きりの調査で「アドレスの選択ミスで全滅」を避けるための保険)
            if (consec_fail >= OBD_FALLBACK_FAIL &&
                s_obd_resp.load(std::memory_order_relaxed) == 0) {
                uint32_t cur = s_req_id.load(std::memory_order_relaxed);
                uint32_t next = (cur == OBD_REQ_ID_PHYS) ? OBD_REQ_ID_FUNC : OBD_REQ_ID_PHYS;
                s_req_id.store(next, std::memory_order_relaxed);
                consec_fail = 0;
                int n = snprintf(line, sizeof(line),
                                 "# obd no response on 0x%03X -> switching to 0x%03X\n",
                                 (unsigned)cur, (unsigned)next);
                emit_line(line, n);
            }
        }

        // 期限を最も過ぎているPIDを1つ選ぶ。
        // 応答しないPIDは s_pid_fail に応じて間隔を 2^fail 倍に伸ばし、
        // 応答するPIDのレートを食い潰さないようにする。
        int best = -1;
        int64_t best_overdue = 0;
        for (int i = 0; i < (int)PID_COUNT; i++) {
            int64_t period = (int64_t)PID_TABLE[i].period_ms * 1000;
            // バックオフは「バスは生きているが、そのPIDだけ未対応」の場合のための機能。
            // 一度も応答が無いうち(=アドレス選択ミス等でそもそも通信できていない疑い)は
            // 適用しない。適用すると送信間隔が伸びて 0x7E0->0x7DF の自動切替判断まで
            // 数分かかってしまい、1回きりの実車調査を潰しかねないため。
            if (s_obd_resp.load(std::memory_order_relaxed) > 0) {
                period <<= s_pid_fail[i].load(std::memory_order_relaxed);
            }
            int64_t overdue = (now - s_last_sent_us[i]) - period;
            if (overdue >= 0 && (best < 0 || overdue > best_overdue)) {
                best = i;
                best_overdue = overdue;
            }
        }
        if (best < 0) continue;

        twai_message_t req = {};
        req.identifier = s_req_id.load(std::memory_order_relaxed);
        req.extd = 0;
        req.rtr = 0;
        req.data_length_code = 8;                 // ISO 15765-4 はDLC8固定(残りはパディング)
        req.data[0] = 0x02;                       // PCI: 単一フレーム、以降2バイト有効
        req.data[1] = 0x01;                       // mode 01 (現在値)
        req.data[2] = PID_TABLE[best].pid;
        for (int i = 3; i < 8; i++) req.data[i] = OBD_PAD_BYTE;
#ifdef BENCH_LOOPBACK
        req.self = 1;   // 卓上検証: 自分の送信を自分で受信する
#endif

        // 送信キューが詰まらないよう待ちは短く。失敗しても記録は継続する。
        if (twai_transmit(&req, pdMS_TO_TICKS(20)) == ESP_OK) {
            int64_t t = esp_timer_get_time();
            s_last_sent_us[best] = t;
            s_obd_sent.fetch_add(1, std::memory_order_relaxed);
            s_inflight_idx.store(best, std::memory_order_relaxed);
            s_inflight_pid.store((int)PID_TABLE[best].pid, std::memory_order_relaxed);
            s_inflight_since.store(t, std::memory_order_relaxed);
            // TWAIは自己受信しないので、送信フレームはここで自分でログへ残す
            // (リクエスト→応答のECU応答時間もこれで測れる)。
            emit_frame_line(t, req.identifier, false, false, 8, req.data);
        } else {
            s_last_sent_us[best] = now;           // 詰まっているPIDで回り続けないよう前進させる
            s_obd_txerr.fetch_add(1, std::memory_order_relaxed);
            consec_fail++;
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
                st.state == TWAI_STATE_RUNNING     ? "RUNNING" :
                st.state == TWAI_STATE_BUS_OFF     ? "BUS_OFF" :
                st.state == TWAI_STATE_RECOVERING  ? "RECOVERING" : "STOPPED";

            printf("# stat t=%lld total=%u rate=%u/s drop_rb=%u "
                   "rx_missed=%u rx_overrun=%u buserr=%u tec=%d rec=%d state=%s alerts=0x%x\n",
                   (long long)now,
                   (unsigned)s_total.load(std::memory_order_relaxed), (unsigned)win,
                   (unsigned)s_drop_rb.load(std::memory_order_relaxed),
                   (unsigned)st.rx_missed_count, (unsigned)st.rx_overrun_count,
                   (unsigned)st.bus_error_count,
                   (int)st.tx_error_counter, (int)st.rx_error_counter,
                   state, (unsigned)alerts);

            int rpm = s_v_rpm.load(std::memory_order_relaxed);
            int spd = s_v_speed.load(std::memory_order_relaxed);
            int clt = s_v_coolant.load(std::memory_order_relaxed);
            int thr = s_v_throttle.load(std::memory_order_relaxed);
            printf("# obd req=0x%03X poll=%s sent=%u resp=%u timeout=%u txerr=%u "
                   "rpm=%d speed=%d coolant=%d throttle=%d\n",
                   (unsigned)s_req_id.load(std::memory_order_relaxed),
                   s_paused.load(std::memory_order_relaxed) ? "PAUSED" : "on",
                   (unsigned)s_obd_sent.load(std::memory_order_relaxed),
                   (unsigned)s_obd_resp.load(std::memory_order_relaxed),
                   (unsigned)s_obd_timeout.load(std::memory_order_relaxed),
                   (unsigned)s_obd_txerr.load(std::memory_order_relaxed),
                   rpm, spd, clt, thr);
            fflush(stdout);

            // --- バスオフ自動復帰 ---
            // 実車では稀だが、OBDコネクタの一時的な接触不良等で落ちたときに
            // 手を出さずに復帰させる(1回きりの実車調査を無駄にしないため)。
            if (st.state == TWAI_STATE_BUS_OFF) {
                printf("# WARN bus-off detected -> initiating recovery\n");
                fflush(stdout);
                twai_initiate_recovery();
            } else if (alerts & TWAI_ALERT_BUS_RECOVERED) {
                twai_start();
                printf("# bus recovered -> twai_start()\n");
                fflush(stdout);
            }

            t_next += 1000000;
            // 長時間まったく受信が無くても statライン境界がズレないよう追従
            while (t_next <= now) t_next += 1000000;
        }
        // 高負荷が続いてもIDLEタスクへ確実にCPUを渡す(WDT保護)。1 tick = 10ms。
        // 48KBのリングバッファがこの間のバーストを吸収する。
        vTaskDelay(1);
    }
}

// USBシリアルからの1文字コマンド。あくまで補助機能で、
// 動かなくてもロギング本体には一切影響しないよう独立・低優先度・エラー無視で実装する。
static void ctrl_task(void *arg)
{
    // ESP32-C3のUSB Serial/JTAGでは、VFS経由の read(STDIN_FILENO) ではホストからの
    // 1バイトを受け取れない。受信FIFOが誰にも掃かれないため、**PC側の write が
    // 永久にブロックする**（2026-09-05に実測。pyserialで write timeout）。
    // 無人キャプチャ中にホストが止まるのは致命的なので、専用ドライバを入れて直接読む。
    // stdout(printf)の経路は変えない(usb_serial_jtag_vfs_use_driver()は呼ばない)ため、
    // 高レートのログ出力の挙動は従来どおり。
    usb_serial_jtag_driver_config_t ucfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    bool drv = (usb_serial_jtag_driver_install(&ucfg) == ESP_OK);
    if (!drv) {
        // 入らなくてもロギング本体には影響しないので、旧経路のまま続行する。
        int flags = fcntl(STDIN_FILENO, F_GETFL, 0);
        if (flags >= 0) {
            fcntl(STDIN_FILENO, F_SETFL, flags | O_NONBLOCK);
        }
        printf("# WARN usb_serial_jtag driver install failed; runtime keys may not work\n");
        fflush(stdout);
    }
    char line[LOG_LINE_MAX];
    for (;;) {
        char c;
        int r;
        if (drv) {
            r = usb_serial_jtag_read_bytes(&c, 1, pdMS_TO_TICKS(100));
        } else {
            vTaskDelay(pdMS_TO_TICKS(100));
            r = read(STDIN_FILENO, &c, 1);
        }
        if (r != 1) continue;
        if (c == 'p' || c == 'P') {
            s_paused.store(true, std::memory_order_relaxed);
            s_inflight_pid.store(-1, std::memory_order_relaxed);
            int n = snprintf(line, sizeof(line), "# obd polling PAUSED (passive; ACK is still sent)\n");
            emit_line(line, n);
        } else if (c == 'r' || c == 'R') {
            s_paused.store(false, std::memory_order_relaxed);
            int n = snprintf(line, sizeof(line), "# obd polling RESUMED\n");
            emit_line(line, n);
        }
    }
}

extern "C" void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(300));
    printf("\n\n");
    printf("# ===== CAN raw logger + OBD2 poller (TWAI_MODE_NORMAL) =====\n");
    printf("# *** WARNING: THIS FIRMWARE TRANSMITS ON THE CAN BUS ***\n");
    printf("#   - sends OBD2 mode-01 requests (ID 0x%03X, falls back to 0x%03X)\n",
           OBD_REQ_ID_PHYS, OBD_REQ_ID_FUNC);
    printf("#   - acknowledges (ACK) every frame on the bus\n");
    printf("#   For fully passive observation use firmware/can_logger (LISTEN_ONLY).\n");
    printf("# bitrate=500k, TX=GPIO%d, RX=GPIO%d\n", (int)CAN_TX_GPIO, (int)CAN_RX_GPIO);
    printf("# line format: t_us,id_hex,ext,rtr,dlc,data_hex   (lines starting with '#' are status)\n");
    printf("#   own requests are logged too (ID 0x7E0/0x7DF), responses arrive as 0x7E8..0x7EF\n");
    printf("# runtime keys: 'p'=pause polling, 'r'=resume\n");
    printf("# polling %d PIDs:", (int)PID_COUNT);
    for (int i = 0; i < (int)PID_COUNT; i++) {
        printf(" %02X(%s@%ums)", PID_TABLE[i].pid, PID_TABLE[i].name,
               (unsigned)PID_TABLE[i].period_ms);
    }
    printf("\n");
    fflush(stdout);

#ifdef BENCH_LOOPBACK
    // ★卓上検証専用★ CAN相手がいない机上で、送信〜自己受信〜ログ出力の全経路を実証するためのモード。
    // can_selftest と同じ TWAI_MODE_NO_ACK + メッセージselfフラグで、自分の送信フレームが
    // CANH/CANL(卓上終端120Ω)を一周して受信キューへ返る。
    // **実車には絶対に使わない**(NO_ACKはACKを返さないため、車両バス上では他ノードの
    // 通信をエラーフレームで妨害しうる)。実車用は既定env(NORMAL)側をビルドすること。
    twai_general_config_t g =
        TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_GPIO, CAN_RX_GPIO, TWAI_MODE_NO_ACK);
#else
    twai_general_config_t g =
        TWAI_GENERAL_CONFIG_DEFAULT(CAN_TX_GPIO, CAN_RX_GPIO, TWAI_MODE_NORMAL);
#endif
    g.rx_queue_len = RX_QUEUE_LEN;
    g.tx_queue_len = TX_QUEUE_LEN;
    g.alerts_enabled = TWAI_ALERT_NONE;

    twai_timing_config_t t = CAN_TIMING;
    twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    ESP_ERROR_CHECK(twai_driver_install(&g, &t, &f));
    twai_reconfigure_alerts(
        TWAI_ALERT_RX_QUEUE_FULL | TWAI_ALERT_RX_FIFO_OVERRUN |
        TWAI_ALERT_BUS_ERROR | TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF |
        TWAI_ALERT_BUS_RECOVERED | TWAI_ALERT_TX_FAILED,
        NULL);
    ESP_ERROR_CHECK(twai_start());
    printf("# TWAI started in NORMAL mode. logging + polling...\n");
    fflush(stdout);

    s_rb = xRingbufferCreate(LINE_RB_BYTES, RINGBUF_TYPE_NOSPLIT);
    if (!s_rb) {
        printf("# FATAL: ringbuffer alloc failed\n");
        return;
    }

    int64_t now = esp_timer_get_time();
    for (int i = 0; i < (int)PID_COUNT; i++) {
        // 起動直後に全PIDが同時に期限到来してバーストしないよう、初回だけ時間をずらす
        s_last_sent_us[i] = now - (int64_t)PID_TABLE[i].period_ms * 1000 + (int64_t)i * 20000;
    }

    xTaskCreate(rx_task,   "can_rx",   4096, NULL, 6, NULL);
    xTaskCreate(out_task,  "can_out",  6144, NULL, 5, NULL);
    xTaskCreate(obd_task,  "obd_poll", 4096, NULL, 4, NULL);
    xTaskCreate(ctrl_task, "obd_ctrl", 3072, NULL, 2, NULL);
}
