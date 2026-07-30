#include <cmath>
#include <cstdio>
#include <cstring>
#include <unistd.h>
#include <ArduinoJson.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "sdkconfig.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "nvs_flash.h"

// 1-4-2: ESP32-S3はネイティブUSB OTGペリフェラルを持つため、TinyUSB CDC ACM
// (JTAGを含まないCDC専用ディスクリプタ)経由でRCP通信する。C3にはこのペリフェラルが
// 無く、1-6-5で確認済みの通りUSB Serial/JTAG(シリアル+JTAG複合ディスクリプタ)の
// ままで良い(スマホ版アプリとの接続は元々C3ではスコープ外、1-4でS3へ移行済み)。
#if CONFIG_IDF_TARGET_ESP32S3
#include "tinyusb.h"
#include "tusb_cdc_acm.h"
#include "freertos/stream_buffer.h"
// 1-2-3: SDカード(SDMMC 4bit)書き込み用。C3はSDMMCホストペリフェラルを
// 搭載していないため、SD保存機能自体がS3限定(1-2-1のARCHITECTURE.md参照)。
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include "driver/sdmmc_host.h"
#include "driver/gpio.h"
#else
#include "driver/usb_serial_jtag.h"
#endif

extern "C" {
#include "minmea.h"
}

// 1-1-1: Hello Taskレベルの疎通確認用タスク
static void helloTask(void *pvParameters)
{
    for (;;) {
        printf("[helloTask] alive\n");
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

// 1-1-2: タスク間通信用キューのPush/Pop確認用タスク
static QueueHandle_t queueTestHandle = nullptr;

static void queuePushTask(void *pvParameters)
{
    uint32_t counter = 0;
    for (;;) {
        counter++;
        if (xQueueSend(queueTestHandle, &counter, portMAX_DELAY) == pdPASS) {
            printf("[queuePushTask] pushed: %lu\n", static_cast<unsigned long>(counter));
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}

static void queuePopTask(void *pvParameters)
{
    uint32_t received = 0;
    for (;;) {
        if (xQueueReceive(queueTestHandle, &received, portMAX_DELAY) == pdPASS) {
            printf("[queuePopTask] popped: %lu\n", static_cast<unsigned long>(received));
        }
    }
}

// 1-1-3: タスクA（受信役）の雛形。ダミーのカウンタ値を生成し、一定間隔でキューにPushするだけ
// Push先は1-1-4で実装するタスクC（USB/シリアル送信役）を想定した専用キュー
static QueueHandle_t taskAToTaskCQueueHandle = nullptr;

// 1-2-2: タスクA→タスクB間のリングバッファ用データ型。SDログの1行(CSV化)に対応する
// 1サンプル分のレコード。GPS/IMU/CAN(OBD2)いずれも実センサーは未調達(Phase1-5/Phase2で
// 対応予定)のため、現時点では全フィールドをダミー値で埋める前提。フィールド追加時は
// 既存フィールドの並び・意味を変えず末尾に追加すること(SD上のCSV列順が変わるため)。
struct SensorLogRecord {
    uint32_t timestampMs; // 起動からの経過ms (esp_timer_get_time()/1000)

    // GPS (Phase1-5で実センサー化)
    double lat;
    double lon;
    float speedKph;

    // IMU 6軸: 加速度3軸 + 角速度3軸 (Phase1-5で実センサー化)
    float accelX, accelY, accelZ;
    float gyroX, gyroY, gyroZ;

    // CAN/OBD2由来 (Phase2で実装)
    float rpm;
    float waterTempC;
    float oilPressKpa;
};

// 1-2-2: タスクA→タスクB間のリングバッファ本体。FreeRTOSキューで実装する
// (1-1-2/1-1-3の既存キューと実装方式を揃える)。
//
// サイズ決定の根拠：
// - ログレートを仮に50Hz(20ms/レコード)と想定
// - SDカード書き込みはウェアレベリング等で数百ms単位のレイテンシスパイクが
//   起こることがあるため、そのブロック中もタスクAがレコードを生成し続けても
//   取りこぼさないよう、1.28秒分(64レコード)のバッファを確保する
// - 1レコード=sizeof(SensorLogRecord)（約64バイト）×64個 ≒ 4KB程度で、
//   ESP32のRAM容量に対して十分小さい
constexpr int kSensorLogQueueLength = 64;
static QueueHandle_t taskAToTaskBQueueHandle = nullptr;

// 5-3-1: taskA/rcpSendSampleが共有するGPSシミュレーション。従来は半径0.0001度
// (約11m)のsin/cos円軌道だったが、5-3-2(スタート/フィニッシュ交差判定)・
// 5-3-3(周回検出確認)の検証には現実のコースに近いサイズ・形状の移動軌跡が
// 必要なため、ウェイポイント列(コース1周分)を線形補間して周回する方式に置き換える。
// 基準点(35.830000, 139.410000)は既存ダミー値の中心と同じにしてある。
struct SimTrackOffset {
    double northM; // 基準点からの北方向オフセット(m)
    double eastM;  // 基準点からの東方向オフセット(m)
};

// P0(スタート/フィニッシュ)を起点に時計回りで1周し、最後にP0へ戻る閉じたループ。
// 直線+ゆるいカーブを模した6区間、1周長は約1.4km。
static constexpr SimTrackOffset kSimTrackOffsets[] = {
    {0,    0},
    {400,  0},
    {500,  150},
    {400,  300},
    {0,    300},
    {-100, 150},
    {0,    0},
};
constexpr size_t kSimTrackPointCount = sizeof(kSimTrackOffsets) / sizeof(kSimTrackOffsets[0]);

constexpr double kSimTrackBaseLat = 35.830000;
constexpr double kSimTrackBaseLon = 139.410000;
constexpr double kMetersPerDegLat = 111000.0; // 緯度1度あたりの距離(概算)

static double g_simTrackMetersPerDegLon = 0.0; // 基準緯度でのcos補正込み、simTrackInit()で計算
static double g_simTrackSegmentLen[kSimTrackPointCount - 1];
static double g_simTrackCumLen[kSimTrackPointCount]; // [0]=0, [末尾]=1周の総距離(m)
static bool g_simTrackInited = false;

constexpr double kSimTrackSpeedMps = 27.78; // シミュレーション走行速度、約100km/h一定

static void simTrackInit()
{
    g_simTrackMetersPerDegLon = kMetersPerDegLat * cos(kSimTrackBaseLat * M_PI / 180.0);
    g_simTrackCumLen[0] = 0.0;
    for (size_t i = 0; i + 1 < kSimTrackPointCount; i++) {
        double dNorth = kSimTrackOffsets[i + 1].northM - kSimTrackOffsets[i].northM;
        double dEast = kSimTrackOffsets[i + 1].eastM - kSimTrackOffsets[i].eastM;
        g_simTrackSegmentLen[i] = sqrt(dNorth * dNorth + dEast * dEast);
        g_simTrackCumLen[i + 1] = g_simTrackCumLen[i] + g_simTrackSegmentLen[i];
    }
    g_simTrackInited = true;
}

// 経過秒(elapsedSec)から、コースを一定速度(kSimTrackSpeedMps)で周回し続けた場合の
// 現在GPS位置(lat, lon)を求める。ウェイポイント間は距離に応じて線形補間する。
static void simTrackGetPosition(double elapsedSec, double *outLat, double *outLon)
{
    if (!g_simTrackInited) {
        simTrackInit();
    }
    double totalLen = g_simTrackCumLen[kSimTrackPointCount - 1];
    double lapTimeSec = totalLen / kSimTrackSpeedMps;
    double distIntoLap = fmod(elapsedSec, lapTimeSec) * kSimTrackSpeedMps;
    if (distIntoLap < 0.0) {
        distIntoLap += totalLen;
    }

    size_t seg = 0;
    while (seg + 2 < kSimTrackPointCount && g_simTrackCumLen[seg + 1] < distIntoLap) {
        seg++;
    }
    double segLen = g_simTrackSegmentLen[seg];
    double ratio = (segLen > 0.0) ? (distIntoLap - g_simTrackCumLen[seg]) / segLen : 0.0;

    const SimTrackOffset &a = kSimTrackOffsets[seg];
    const SimTrackOffset &b = kSimTrackOffsets[seg + 1];
    double northM = a.northM + (b.northM - a.northM) * ratio;
    double eastM = a.eastM + (b.eastM - a.eastM) * ratio;

    *outLat = kSimTrackBaseLat + northM / kMetersPerDegLat;
    *outLon = kSimTrackBaseLon + eastM / g_simTrackMetersPerDegLon;
}

// 5-3-2: lapDetectorUpdateの実体はTrackCfg構造体定義後(下記)にあるため、
// taskAで使う都合上、前方宣言しておく(trackCfgSaveToNvsと同じ事情)。
// 5-4-1: outCrossedStartFinishを追加。lapCompleted(戻り値、2周目以降のみtrue)とは別に、
// 「ジオフェンスを外→内へ横切った瞬間」自体(初回通過も含む)をlapRecorderUpdateへ
// 伝える必要があるため(下記lapRecorderUpdateのコメント参照)。
static bool lapDetectorUpdate(double lat, double lon, double elapsedSec,
                               double *outLapTimeSec, uint32_t *outLapNumber,
                               bool *outCrossedStartFinish);

// 5-4-1: lapRecorderUpdateの実体はg_lapDetector/gpsDistanceMeters定義後(下記)にあるため、
// taskAで使う都合上、前方宣言しておく。
static void lapRecorderUpdate(double lat, double lon, double elapsedSec,
                               bool crossedStartFinish, bool lapCompleted, double lapTimeSec);

static void taskA(void *pvParameters)
{
    uint32_t dummyCounter = 0;
    for (;;) {
        dummyCounter++;
        // タイムアウト0: 1-1-4でPop側(タスクC)が実装されるまでの間、
        // キューが満杯でもタスクAがブロックしないようにする
        if (xQueueSend(taskAToTaskCQueueHandle, &dummyCounter, 0) == pdPASS) {
            printf("[taskA] pushed dummy value: %lu\n", static_cast<unsigned long>(dummyCounter));
        } else {
            printf("[taskA] queue full, dropped: %lu\n", static_cast<unsigned long>(dummyCounter));
        }

        // 1-2-2: SD保存用レコードのダミー値を生成し、タスクB向けキューへPush。
        // 実センサー(GPS/IMU/CAN)未調達のため、taskCのrcpSendSample()と同様の
        // sin波ベースの緩やかな変動値で埋める。Pop側(タスクB)は1-2-3で実装するため、
        // それまではキューが満杯になり続ける("dropped"ログが出る)のは想定内の挙動。
        // GPS(lat/lon)は5-3-1でsimTrackGetPosition()のコース周回シミュレーションに
        // 置き換え済み(taskC側のrcpSendSample()と同じ軌道を共有する)。
        double t = static_cast<double>(esp_timer_get_time()) / 1000000.0;
        SensorLogRecord rec;
        rec.timestampMs = static_cast<uint32_t>(esp_timer_get_time() / 1000);
        simTrackGetPosition(t, &rec.lat, &rec.lon);

        // 5-3-2: 今回のGPS位置(rec.lat/lon)と前回のGPS位置を結ぶ移動線分が
        // スタート/フィニッシュのジオフェンスを外→内へ横切った瞬間(ラップ切り替わり)
        // を検出する。実際にシミュレーションデータで正しく発火するかの確認は5-3-3。
        double lapTimeSec = 0.0;
        uint32_t lapNumber = 0;
        bool crossedStartFinish = false;
        bool lapCompleted = lapDetectorUpdate(rec.lat, rec.lon, t, &lapTimeSec, &lapNumber,
                                               &crossedStartFinish);
        if (lapCompleted) {
            printf("[taskA] lap %lu completed: %.3f s\n",
                   static_cast<unsigned long>(lapNumber), lapTimeSec);
        }
        // 5-4-1: ベストラップのGPS軌跡(累積走行距離→経過時間)記録。5-4-2の予測タイム
        // 計算で、現在位置の走行距離に対応するベストラップ経過時間を補間するために使う。
        lapRecorderUpdate(rec.lat, rec.lon, t, crossedStartFinish, lapCompleted, lapTimeSec);

        rec.speedKph = static_cast<float>(60 + 40 * sin(t / 5));
        rec.accelX = static_cast<float>(0.1 * sin(t * 2));
        rec.accelY = static_cast<float>(0.1 * cos(t * 2));
        rec.accelZ = 1.0f;
        rec.gyroX = static_cast<float>(0.05 * sin(t * 3));
        rec.gyroY = static_cast<float>(0.05 * cos(t * 3));
        rec.gyroZ = static_cast<float>(0.05 * sin(t * 1.5));
        rec.rpm = static_cast<float>(3000 + 2000 * sin(t / 3));
        rec.waterTempC = static_cast<float>(82 + 5 * sin(t / 7));
        rec.oilPressKpa = static_cast<float>(280 + 30 * sin(t / 4));
        if (xQueueSend(taskAToTaskBQueueHandle, &rec, 0) != pdPASS) {
            printf("[taskA] sensor log queue full, dropped record at t=%lu\n",
                   static_cast<unsigned long>(rec.timestampMs));
        }

        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

// 1-3-1: USB CDCシリアル(ネイティブUSB、USB Serial/JTAGペリフェラル)経由の
// RCP受信パーサ。1バイトずつ受信し、`\r`を1メッセージの区切りとして
// JSON文字列を切り出す。1-3-7でタスクC本体へ統合済み。
static const char *kRcpTag = "rcp_rx";
constexpr size_t kRcpReadChunkSize = 256;
// 5-1-3: 512だと公式アプリのWrite操作が一括送信するsetLapCfg(9チャンネル分の
// nm/ut/min/max/prec/sr全部入り)だけでオーバーフローし、後続のsetTrackCfgまで
// 巻き添えで壊れて`JSON parse failed`になる不具合を実機で確認したため、
// 余裕を持たせて2048に拡大した。
constexpr size_t kRcpLineBufSize = 2048;

// 1-4-2: USB送受信層。C3(USB Serial/JTAG)とS3(TinyUSB CDC ACM)で実装を分け、
// 上位のRCPメッセージ処理(rcpHandleMessage等)からは意識せず使えるようにする。
#if CONFIG_IDF_TARGET_ESP32S3

// TinyUSB CDCは受信がコールバックベースのため、コールバック内でtinyusb_cdcacm_read()
// した内容をこのストリームバッファへ積み、taskC側は既存同様ポーリングで取り出す。
static StreamBufferHandle_t g_usbRxStream = nullptr;

static void rcpCdcRxCallback(int itf, cdcacm_event_t *event)
{
    uint8_t buf[64];
    size_t rxSize = 0;
    esp_err_t err = tinyusb_cdcacm_read(static_cast<tinyusb_cdcacm_itf_t>(itf), buf, sizeof(buf), &rxSize);
    if (err == ESP_OK && rxSize > 0) {
        xStreamBufferSend(g_usbRxStream, buf, rxSize, 0);
    }
}

static void rcpUsbInit()
{
    g_usbRxStream = xStreamBufferCreate(kRcpLineBufSize * 2, 1);

    // descriptor類はすべてNULL/デフォルトのままKconfig(TINYUSB_DESC_*)の値を使う。
    // JTAGを含まないCDC専用の単一インターフェース構成になり、1-6-5で問題になった
    // 「USB Serial/JTAGの複合ディスクリプタをスマホ版アプリが拒否する」件を回避する狙い。
    tinyusb_config_t tusbCfg = {};
    ESP_ERROR_CHECK(tinyusb_driver_install(&tusbCfg));

    tinyusb_config_cdcacm_t cdcCfg = {};
    cdcCfg.usb_dev = TINYUSB_USBDEV_0;
    cdcCfg.cdc_port = TINYUSB_CDC_ACM_0;
    cdcCfg.callback_rx = &rcpCdcRxCallback;
    ESP_ERROR_CHECK(tusb_cdc_acm_init(&cdcCfg));
}

static void rcpUsbWriteBytes(const uint8_t *buf, size_t len)
{
    // tinyusb_cdcacm_write_queue()はTX FIFO(既定512バイト、CONFIG_TINYUSB_CDC_TX_BUFSIZE)の
    // 空き容量を超える分を黙って切り捨てる(戻り値は実際にキューされたバイト数)。
    // C3のusb_serial_jtag_write_bytesと同様の欠落を避けるため、キューできた分だけ
    // flushして空きを作りながら全バイト書き切るまでループする。
    size_t written = 0;
    while (written < len) {
        size_t queued = tinyusb_cdcacm_write_queue(TINYUSB_CDC_ACM_0, buf + written, len - written);
        if (queued == 0) {
            tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, portMAX_DELAY);
            continue;
        }
        written += queued;
    }
    tinyusb_cdcacm_write_flush(TINYUSB_CDC_ACM_0, portMAX_DELAY);
}

static int rcpUsbReadBytes(uint8_t *buf, size_t maxLen, TickType_t timeout)
{
    return static_cast<int>(xStreamBufferReceive(g_usbRxStream, buf, maxLen, timeout));
}

#else // C3: USB Serial/JTAG

static void rcpUsbInit()
{
    // CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAGが有効な場合、
    // コンソール初期化時に既にドライバがインストール済みのことがあるため、
    // ESP_ERR_INVALID_STATEはそのまま読み書き可能とみなして無視する。
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    esp_err_t err = usb_serial_jtag_driver_install(&cfg);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_ERROR_CHECK(err);
    }
}

static void rcpUsbWriteBytes(const uint8_t *buf, size_t len)
{
    // USB Serial/JTAGのTXリングバッファ(デフォルト256バイト)より大きいサイズを
    // 一度にusb_serial_jtag_write_bytesへ渡すと、内部のxRingbufferSendが
    // 「要求サイズがバッファ全体に収まらない」と判定し、portMAX_DELAYで待っても
    // 入る余地がないため即座に失敗する(getMeta等、256バイトを超える応答で発生確認)。
    // そのためバッファ容量より確実に小さいチャンク単位に分割して送信する。
    constexpr size_t kUsbJtagWriteChunkSize = 128;
    size_t written = 0;
    while (written < len) {
        size_t chunk = len - written;
        if (chunk > kUsbJtagWriteChunkSize) {
            chunk = kUsbJtagWriteChunkSize;
        }
        int w = usb_serial_jtag_write_bytes(buf + written, chunk, portMAX_DELAY);
        if (w <= 0) {
            ESP_LOGW(kRcpTag, "usb_serial_jtag_write_bytes stalled (wrote %u/%u)",
                     (unsigned)written, (unsigned)len);
            break;
        }
        written += static_cast<size_t>(w);
    }
}

static int rcpUsbReadBytes(uint8_t *buf, size_t maxLen, TickType_t timeout)
{
    return usb_serial_jtag_read_bytes(buf, maxLen, timeout);
}

#endif

// 1-3-2: `{"ver":{...}}`応答の送信。行末は`\r\n`(HANDOFF.md参照：公式アプリの
// 受信パーサは`\n`区切りで見ているため、モック→アプリ方向は`\r\n`で問題ない)。
static void rcpSendJsonLine(JsonDocument &doc)
{
    char buf[kRcpLineBufSize];
    size_t n = serializeJson(doc, buf, sizeof(buf) - 2);
    buf[n++] = '\r';
    buf[n++] = '\n';
    rcpUsbWriteBytes(reinterpret_cast<const uint8_t *>(buf), n);
}

static void rcpSendVer()
{
    JsonDocument doc;
    JsonObject ver = doc["ver"].to<JsonObject>();
    ver["name"] = "RCPMK3";
#if CONFIG_IDF_TARGET_ESP32S3
    // 1-4-2: 公式アプリ画面でC3実機とS3実機を見分けられるよう、ターゲットごとに
    // 表示文字列を分ける(以前はC3固有の文字列がS3ビルドでもそのまま出ていた)。
    ver["fname"] = "RaceCapture/Pro MK3 (esp32-s3 proto fw)";
    ver["serial"] = "S3PROTO01";
    ver["git_info"] = "esp32-s3-proto-build";
#else
    ver["fname"] = "RaceCapture/Pro MK3 (esp32-c3 proto fw)";
    ver["serial"] = "C3PROTO01";
    ver["git_info"] = "esp32-c3-proto-build";
#endif
    ver["major"] = 2;
    ver["minor"] = 16;
    ver["bugfix"] = 1;
    ver["release_type"] = "release";
    rcpSendJsonLine(doc);
}

// 1-7-1: getAnalogCfg/setAnalogCfg用のセンサー較正設定。0-8(rcp_mock_device.py)
// で公式アプリとの読み書き疎通を確認済みのJSON形式(reference/RaceCapture-Pro_firmware
// 由来のフィールド構成)に合わせる。まずはRAM上に保持し、永続化(NVS)は1-7-2で追加する。
constexpr int kAnalogChannelCount = 1; // 0-8同様、疎通確認用に1chのみ有効化
constexpr int kApiSuccess = 1; // reference/RaceCapture-Pro_firmware/include/api/api.h より(0ではなく1が成功)

struct AnalogChannelCfg {
    char nm[16];
    char ut[16];
    double min;
    double max;
    int sr;
    int prec;
    int scalMod;
    double scaling;
    double offset;
    double alpha;
    double cal;
    double mapRaw[5];
    double mapScal[5];
};

static AnalogChannelCfg g_analogCfg[kAnalogChannelCount];

static void analogCfgSetDefault(AnalogChannelCfg &cfg, int index)
{
    snprintf(cfg.nm, sizeof(cfg.nm), "Analog%d", index);
    snprintf(cfg.ut, sizeof(cfg.ut), "Volts");
    cfg.min = 0.0;
    cfg.max = 5.0;
    cfg.sr = 10;
    cfg.prec = 2;
    cfg.scalMod = 0;
    cfg.scaling = 1.0;
    cfg.offset = 0.0;
    cfg.alpha = 0.0;
    cfg.cal = 0.0;
    const double defaultPoints[5] = {0, 1.25, 2.5, 3.75, 5};
    for (int i = 0; i < 5; i++) {
        cfg.mapRaw[i] = defaultPoints[i];
        cfg.mapScal[i] = defaultPoints[i];
    }
}

// 1-7-2: NVS上での較正値の保存先。1ch分の構造体をそのままblobとして書き込む
// (POD構造体でポインタを含まないため安全)。
static const char *kAnalogCfgNvsNamespace = "analogcfg";

static void analogCfgLoadFromNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kAnalogCfgNvsNamespace, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        // 初回起動等でnamespace未作成の場合はデフォルト値のまま使う
        return;
    }
    for (int i = 0; i < kAnalogChannelCount; i++) {
        char key[8];
        snprintf(key, sizeof(key), "ch%d", i);
        AnalogChannelCfg loaded;
        size_t required = sizeof(loaded);
        esp_err_t rerr = nvs_get_blob(handle, key, &loaded, &required);
        if (rerr == ESP_OK && required == sizeof(loaded)) {
            g_analogCfg[i] = loaded;
        }
    }
    nvs_close(handle);
}

// 1-7-2: 現在のg_analogCfg全chをNVSへ書き込む。flashCfg受信時(Writeボタン相当)に呼ぶ。
static void analogCfgSaveToNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kAnalogCfgNvsNamespace, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_open (RW) failed: %s", esp_err_to_name(err));
        return;
    }
    for (int i = 0; i < kAnalogChannelCount; i++) {
        char key[8];
        snprintf(key, sizeof(key), "ch%d", i);
        nvs_set_blob(handle, key, &g_analogCfg[i], sizeof(g_analogCfg[i]));
    }
    esp_err_t cerr = nvs_commit(handle);
    if (cerr != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_commit failed: %s", esp_err_to_name(cerr));
    }
    nvs_close(handle);
}

static void analogCfgInitAll()
{
    for (int i = 0; i < kAnalogChannelCount; i++) {
        analogCfgSetDefault(g_analogCfg[i], i);
    }
    // NVSに保存済みの値があれば、デフォルトの上から読み込んで上書きする
    analogCfgLoadFromNvs();
}

static void analogCfgToJson(const AnalogChannelCfg &cfg, JsonObject obj)
{
    obj["nm"] = cfg.nm;
    obj["ut"] = cfg.ut;
    obj["min"] = cfg.min;
    obj["max"] = cfg.max;
    obj["sr"] = cfg.sr;
    obj["prec"] = cfg.prec;
    obj["scalMod"] = cfg.scalMod;
    obj["scaling"] = cfg.scaling;
    obj["offset"] = cfg.offset;
    obj["alpha"] = cfg.alpha;
    obj["cal"] = cfg.cal;
    JsonObject map = obj["map"].to<JsonObject>();
    JsonArray raw = map["raw"].to<JsonArray>();
    JsonArray scal = map["scal"].to<JsonArray>();
    for (int i = 0; i < 5; i++) {
        raw.add(cfg.mapRaw[i]);
        scal.add(cfg.mapScal[i]);
    }
}

// 1-7-3: `{"getAnalogCfg":null}`(全ch)または`{"getAnalogCfg":<index>}`(単一ch)への応答。
static void rcpSendGetAnalogCfg(JsonVariantConst indexArg)
{
    JsonDocument doc;
    JsonObject result = doc["analogCfg"].to<JsonObject>();
    if (indexArg.isNull()) {
        for (int i = 0; i < kAnalogChannelCount; i++) {
            char key[4];
            snprintf(key, sizeof(key), "%d", i);
            JsonObject chObj = result[key].to<JsonObject>();
            analogCfgToJson(g_analogCfg[i], chObj);
        }
    } else {
        int idx = indexArg.as<int>();
        if (idx >= 0 && idx < kAnalogChannelCount) {
            char key[4];
            snprintf(key, sizeof(key), "%d", idx);
            JsonObject chObj = result[key].to<JsonObject>();
            analogCfgToJson(g_analogCfg[idx], chObj);
        }
    }
    rcpSendJsonLine(doc);
}

// 1-7-1: setAnalogCfgで送られてきたフィールドだけを既存設定へ部分マージする
// (実機/rcp_mock_device.py同様、送られてこなかったフィールドは変更しない)。
static void analogCfgApplyFields(AnalogChannelCfg &cfg, JsonObjectConst fields)
{
    if (fields["nm"].is<const char *>()) {
        strncpy(cfg.nm, fields["nm"].as<const char *>(), sizeof(cfg.nm) - 1);
        cfg.nm[sizeof(cfg.nm) - 1] = '\0';
    }
    if (fields["ut"].is<const char *>()) {
        strncpy(cfg.ut, fields["ut"].as<const char *>(), sizeof(cfg.ut) - 1);
        cfg.ut[sizeof(cfg.ut) - 1] = '\0';
    }
    if (!fields["min"].isNull()) cfg.min = fields["min"].as<double>();
    if (!fields["max"].isNull()) cfg.max = fields["max"].as<double>();
    if (!fields["sr"].isNull()) cfg.sr = fields["sr"].as<int>();
    if (!fields["prec"].isNull()) cfg.prec = fields["prec"].as<int>();
    if (!fields["scalMod"].isNull()) cfg.scalMod = fields["scalMod"].as<int>();
    if (!fields["scaling"].isNull()) cfg.scaling = fields["scaling"].as<double>();
    if (!fields["offset"].isNull()) cfg.offset = fields["offset"].as<double>();
    if (!fields["alpha"].isNull()) cfg.alpha = fields["alpha"].as<double>();
    if (!fields["cal"].isNull()) cfg.cal = fields["cal"].as<double>();
    JsonObjectConst map = fields["map"];
    if (!map.isNull()) {
        JsonArrayConst raw = map["raw"];
        if (!raw.isNull()) {
            int i = 0;
            for (JsonVariantConst v : raw) {
                if (i >= 5) break;
                cfg.mapRaw[i++] = v.as<double>();
            }
        }
        JsonArrayConst scal = map["scal"];
        if (!scal.isNull()) {
            int i = 0;
            for (JsonVariantConst v : scal) {
                if (i >= 5) break;
                cfg.mapScal[i++] = v.as<double>();
            }
        }
    }
}

// 1-7-1: `{"setAnalogCfg":{"<index>":{フィールドの部分更新}, ...}}`受信時にRAM上へ保存する。
static void rcpHandleSetAnalogCfg(JsonObjectConst payload)
{
    if (!payload.isNull()) {
        for (JsonPairConst kv : payload) {
            int idx = atoi(kv.key().c_str());
            if (idx < 0 || idx >= kAnalogChannelCount) continue;
            JsonObjectConst fields = kv.value().as<JsonObjectConst>();
            if (fields.isNull()) continue;
            analogCfgApplyFields(g_analogCfg[idx], fields);
        }
    }
    JsonDocument doc;
    JsonObject result = doc["setAnalogCfg"].to<JsonObject>();
    result["rc"] = kApiSuccess;
    rcpSendJsonLine(doc);
}

// 5-2-2: trackCfgSaveToNvsの実体はTrackCfg構造体定義後(下記)にあるため、
// ここで使う都合上、前方宣言しておく。
static void trackCfgSaveToNvs();
// 1-4-7: connCfgSaveToNvsも同様に、ConnCfg構造体定義後(下記)にあるため前方宣言しておく。
static void connCfgSaveToNvs();

// setAnalogCfg後にWriteボタン相当でアプリが送ってくる。応答がないと公式アプリが
// "Timeout waiting for 'flashCfg'"でWriteをエラー扱いにする(0-8で実機確認済み)。
// 1-7-2: このタイミングで現在のRAM上の値をNVSへ書き込み、再起動後も保持されるようにする。
// 5-2-2: setTrackCfg(5-1-3)もこのタイミングで書き込まれたRAM値をNVSへコミットする
// (公式アプリのWrite操作はタブに関わらず一括送信されるため、AnalogCfgと同じ
// flashCfgタイミングで両方永続化するのが自然)。
static void rcpSendFlashCfgAck()
{
    analogCfgSaveToNvs();
    trackCfgSaveToNvs();
    connCfgSaveToNvs();

    JsonDocument doc;
    JsonObject result = doc["flashCfg"].to<JsonObject>();
    result["rc"] = kApiSuccess;
    rcpSendJsonLine(doc);
}

// 5-1-3: getLapCfg/getTrackCfgの現状(空応答)を実データ保持へ変更する構造。
// 5-1-1で設計、5-1-2で公式アプリ(reference/RaceCapture_App、ryandoherty fork)の
// TrackConfig/Track送受信仕様と一致確認済み。保存先(NVS/SD)は5-2で決定するため、
// 5-1-3時点ではRAM保持のみとし、autoDetect/type/セクター/stage用st-finは
// 非対応(常に固定値・空)のまま扱う。
constexpr float kDefaultTrackRadius = 0.0001f; // reference/RaceCapture-Pro_firmware の DEFAULT_TRACK_TARGET_RADIUS

struct TrackCfg {
    float radius = kDefaultTrackRadius;
    int32_t trackId = -1;
    // 5-3-2: 実GPS/公式アプリ未接続でもラップ検出のシミュレーション確認ができるよう、
    // デフォルト値をkSimTrackOffsetsのスタート/フィニッシュ地点(kSimTrackBaseLat/Lon)
    // に合わせる(5-3-1の申し送り事項への対応)。setTrackCfg+flashCfgで書き込まれれば
    // 従来通りその値で上書きされる。
    float startFinishLat = static_cast<float>(kSimTrackBaseLat);
    float startFinishLon = static_cast<float>(kSimTrackBaseLon);
};

static TrackCfg g_trackCfg;

// 5-3-2: スタート/フィニッシュ通過(ラップ切り替わり)検出。GPS移動軌跡を
// 「直近2サンプル間の線分」として扱い、その線分がg_trackCfgのジオフェンス
// (startFinishLat/Lon中心、半径radius)を外側→内側へ横切った瞬間を検出する。
// radiusは5-1-2確認の通り度単位(公式GeoPoint.withinCircleと同じ、緯度経度差の
// 二乗和で比較しメートル換算はしない)。設計メモ(5-3/5-4向け)の「①スタート/
// フィニッシュ・セクター判定」に基づき、線分上でジオフェンス中心に最も近い点の
// パラメータt(0〜1)を求め、そのtで前回/今回のGPS時刻を線形補間することで、
// サンプル間隔(taskAは100ms間隔)より高精度な通過時刻を算出する。
struct LapDetectorState {
    bool hasPrev = false;
    double prevLat = 0.0;
    double prevLon = 0.0;
    double prevTimeSec = 0.0;
    bool wasInsideGate = false;
    uint32_t lapCount = 0;       // ジオフェンスを外→内へ横切った通算回数
    double lapStartTimeSec = 0.0; // 直近の横切り時刻(次ラップの起点)
};

static LapDetectorState g_lapDetector;

// 5-5-2: `s`応答のLapTimeチャンネル(直近完了ラップのタイム、秒)用。lapDetectorUpdate
// 内でラップ完了を検出した際に更新する値はこれまでtaskAのローカル変数(lapTimeSec)止まり
// だったため、taskC(rcpSendSample)からも参照できるようグローバル化した。1周も完了して
// いない間は0.0のまま。
static double g_lastLapTimeSec = 0.0;

// 線分(aLat,aLon)-(bLat,bLon)上で点(pLat,pLon)に最も近い点のパラメータt(0〜1、
// 線分の外に出ないよう0〜1にクランプ)を求める。
static double segmentClosestPointT(double aLat, double aLon, double bLat, double bLon,
                                    double pLat, double pLon)
{
    double dLat = bLat - aLat;
    double dLon = bLon - aLon;
    double lenSq = dLat * dLat + dLon * dLon;
    if (lenSq <= 0.0) {
        return 0.0;
    }
    double t = ((pLat - aLat) * dLat + (pLon - aLon) * dLon) / lenSq;
    if (t < 0.0) {
        t = 0.0;
    } else if (t > 1.0) {
        t = 1.0;
    }
    return t;
}

// 新しいGPSサンプル(lat, lon, elapsedSec)を渡し、直近サンプルとの移動線分が
// スタート/フィニッシュのジオフェンスへ外側から内側へ入った瞬間(1周完了)を検出する。
// ジオフェンス内に留まっている間の連続トリガーを避けるため、外→内のエッジのみを
// 検出する(一度内に入ったら外に出るまで再トリガーしない)。初回の横切り(電源投入後
// 最初にスタート地点へ到達した時点)はラップ完了とはみなさず、2回目以降の横切りを
// 「1周完了」として扱う。検出時はtrueを返し、outLapTimeSecへ直前の横切りからの
// 補間後経過時間(ラップタイム)、outLapNumberへ何周目が完了したかを書き込む。
static bool lapDetectorUpdate(double lat, double lon, double elapsedSec,
                               double *outLapTimeSec, uint32_t *outLapNumber,
                               bool *outCrossedStartFinish)
{
    bool lapCompleted = false;
    if (outCrossedStartFinish != nullptr) {
        *outCrossedStartFinish = false;
    }

    if (g_lapDetector.hasPrev) {
        double t = segmentClosestPointT(g_lapDetector.prevLat, g_lapDetector.prevLon, lat, lon,
                                         g_trackCfg.startFinishLat, g_trackCfg.startFinishLon);
        double closestLat = g_lapDetector.prevLat + (lat - g_lapDetector.prevLat) * t;
        double closestLon = g_lapDetector.prevLon + (lon - g_lapDetector.prevLon) * t;
        double dLat = closestLat - g_trackCfg.startFinishLat;
        double dLon = closestLon - g_trackCfg.startFinishLon;
        double distSq = dLat * dLat + dLon * dLon;
        double radius = static_cast<double>(g_trackCfg.radius);
        bool isInsideNow = distSq <= (radius * radius);

        if (isInsideNow && !g_lapDetector.wasInsideGate) {
            double crossTimeSec = g_lapDetector.prevTimeSec
                + (elapsedSec - g_lapDetector.prevTimeSec) * t;
            if (outCrossedStartFinish != nullptr) {
                *outCrossedStartFinish = true;
            }
            if (g_lapDetector.lapCount > 0) {
                lapCompleted = true;
                double completedLapTimeSec = crossTimeSec - g_lapDetector.lapStartTimeSec;
                if (outLapTimeSec != nullptr) {
                    *outLapTimeSec = completedLapTimeSec;
                }
                if (outLapNumber != nullptr) {
                    *outLapNumber = g_lapDetector.lapCount;
                }
                g_lastLapTimeSec = completedLapTimeSec;
            }
            g_lapDetector.lapStartTimeSec = crossTimeSec;
            g_lapDetector.lapCount++;
        }
        g_lapDetector.wasInsideGate = isInsideNow;
    }

    g_lapDetector.prevLat = lat;
    g_lapDetector.prevLon = lon;
    g_lapDetector.prevTimeSec = elapsedSec;
    g_lapDetector.hasPrev = true;
    return lapCompleted;
}

// 5-4-1: 予測タイム計算(5-4-2)向けに、ベストラップの「累積走行距離(m)→経過時間(秒)」
// 対応表を記録する仕組み。設計メモ(5-3・5-4向け)の③「予測タイム」の前段に対応する。
//
// GPSサンプル(taskAは100ms周期)ごとに、現在ラップ開始(直近のスタート/フィニッシュ
// ジオフェンス通過)からの累積走行距離と経過時間をペアで記録し続け、次にジオフェンスを
// 通過した瞬間、直前まで記録していたラップがベストラップ(lapCompletedかつ最速)であれば
// 確定バッファ(g_bestLapSamples)へコピーする。
//
// リセット契機は「ラップ完了(lapCompleted、2周目以降)」ではなく「ジオフェンス通過
// (crossedStartFinish、初回通過も含む)」である点に注意。初回通過(電源投入後、最初に
// スタート地点へ到達した瞬間)はラップ完了とはみなされない(lapDetectorUpdate参照)が、
// そこが1周目の走行距離・経過時間の起点になるため、記録側は初回通過でもリセットする
// 必要がある。そうしないと1周目のサンプルに電源投入からの経過時間が混入してしまう。
constexpr size_t kMaxLapSamples = 2048; // 100ms周期で約204秒(3.4分)分。長めの周回コースも見込んだ余裕

struct LapDistanceSample {
    float distanceM; // 現在ラップ開始からの累積走行距離(m)
    float timeSec;   // 同じく現在ラップ開始からの経過時間(秒)
};

static LapDistanceSample g_currentLapSamples[kMaxLapSamples];
static size_t g_currentLapSampleCount = 0;
static double g_currentLapDistanceM = 0.0;
static bool g_currentLapHasPrevPos = false;
static double g_currentLapPrevLat = 0.0;
static double g_currentLapPrevLon = 0.0;

static LapDistanceSample g_bestLapSamples[kMaxLapSamples];
static size_t g_bestLapSampleCount = 0;
static double g_bestLapTimeSec = -1.0; // 未確定時-1

// 2点間の距離(m)を、緯度経度差からの平面近似(equirectangular近似)で求める。
// simTrackGetPosition()と同じ考え方(緯度1度=111000m、経度1度は緯度でcos補正)だが、
// 実GPS軌跡は基準点を持たないため、2点の中間緯度でcos補正するその場計算にしている。
static double gpsDistanceMeters(double lat1, double lon1, double lat2, double lon2)
{
    double dLat = (lat2 - lat1) * kMetersPerDegLat;
    double midLat = (lat1 + lat2) * 0.5;
    double metersPerDegLon = kMetersPerDegLat * cos(midLat * M_PI / 180.0);
    double dLon = (lon2 - lon1) * metersPerDegLon;
    return sqrt(dLat * dLat + dLon * dLon);
}

// 5-4-2: g_bestLapSamples(距離→経過時間の対応表、distanceMについて単調増加)から、
// 現在の走行距離distanceMに対応するベストラップ経過時間を線形補間で求める。
// distanceMが対応表の範囲外(ベストラップより手前/先まで走行)の場合は外挿せず、
// 端の値(先頭/末尾のtimeSec)にクランプする。
static double bestLapTimeAtDistance(double distanceM)
{
    size_t last = g_bestLapSampleCount - 1;
    if (distanceM <= g_bestLapSamples[0].distanceM) {
        return g_bestLapSamples[0].timeSec;
    }
    if (distanceM >= g_bestLapSamples[last].distanceM) {
        return g_bestLapSamples[last].timeSec;
    }
    size_t lo = 0, hi = last;
    while (lo + 1 < hi) {
        size_t mid = (lo + hi) / 2;
        if (g_bestLapSamples[mid].distanceM <= distanceM) {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    double d0 = g_bestLapSamples[lo].distanceM;
    double d1 = g_bestLapSamples[hi].distanceM;
    double t0 = g_bestLapSamples[lo].timeSec;
    double t1 = g_bestLapSamples[hi].timeSec;
    double ratio = (d1 > d0) ? (distanceM - d0) / (d1 - d0) : 0.0;
    return t0 + (t1 - t0) * ratio;
}

// 5-4-2: 予測タイム(デルタ) = 現在ラップの経過時間 - ベストラップが同じ走行距離に
// 達した時点の経過時間。正の値=ベストラップより遅れている、負の値=進んでいる。
// ベストラップがまだ確定していない(g_bestLapSampleCount==0)間はg_predDeltaValidを
// falseのままにし、呼び出し側(5-5でのRCPストリーム送信等)が無効値と判別できるようにする。
static bool g_predDeltaValid = false;
static double g_predDeltaSec = 0.0;

static void predTimeUpdate(double currentDistanceM, double currentTimeSec)
{
    if (g_bestLapSampleCount == 0) {
        g_predDeltaValid = false;
        return;
    }
    double bestTimeAtDist = bestLapTimeAtDistance(currentDistanceM);
    g_predDeltaSec = currentTimeSec - bestTimeAtDist;
    g_predDeltaValid = true;

    // 5-4-3: シミュレーションデータでの妥当性確認用ログ。100ms周期そのままだと
    // 出力過多になるため、約1秒間隔(10サンプルに1回)に間引いて出力する。
    static uint32_t sPredLogCounter = 0;
    if ((sPredLogCounter++ % 10) == 0) {
        printf("[predTime] dist=%.1fm delta=%+.3fs\n", currentDistanceM, g_predDeltaSec);
    }
}

static void lapRecorderUpdate(double lat, double lon, double elapsedSec,
                               bool crossedStartFinish, bool lapCompleted, double lapTimeSec)
{
    if (crossedStartFinish) {
        // 直前まで記録していたラップが完了(2周目以降)かつベスト更新なら確定させる。
        if (lapCompleted && (g_bestLapTimeSec < 0.0 || lapTimeSec < g_bestLapTimeSec)) {
            memcpy(g_bestLapSamples, g_currentLapSamples,
                   sizeof(LapDistanceSample) * g_currentLapSampleCount);
            g_bestLapSampleCount = g_currentLapSampleCount;
            g_bestLapTimeSec = lapTimeSec;
            printf("[lapRecorder] new best lap: %.3f s (%u samples)\n",
                   lapTimeSec, static_cast<unsigned>(g_bestLapSampleCount));
        }
        // 新しいラップの記録を開始(距離・サンプル数をリセット)。
        g_currentLapSampleCount = 0;
        g_currentLapDistanceM = 0.0;
        g_currentLapHasPrevPos = false;
    }

    if (g_currentLapHasPrevPos) {
        g_currentLapDistanceM += gpsDistanceMeters(g_currentLapPrevLat, g_currentLapPrevLon, lat, lon);
    }
    g_currentLapPrevLat = lat;
    g_currentLapPrevLon = lon;
    g_currentLapHasPrevPos = true;

    if (g_currentLapSampleCount < kMaxLapSamples) {
        // g_lapDetector.lapStartTimeSecはlapDetectorUpdate内で既に更新済み(このタイミング
        // では今回横切った場合は今回のcrossTimeSec、横切っていなければ直近のラップ開始時刻)
        // のため、そのまま「現在ラップ開始からの経過時間」の基準として使える。
        double timeSinceLapStart = elapsedSec - g_lapDetector.lapStartTimeSec;
        g_currentLapSamples[g_currentLapSampleCount].distanceM =
            static_cast<float>(g_currentLapDistanceM);
        g_currentLapSamples[g_currentLapSampleCount].timeSec =
            static_cast<float>(timeSinceLapStart);
        g_currentLapSampleCount++;

        // 5-4-2: 今回のサンプル(現在ラップ開始からの走行距離・経過時間)を使い、
        // ベストラップとの予測タイム(デルタ)を更新する。
        predTimeUpdate(g_currentLapDistanceM, timeSinceLapStart);
    }
}

// 5-2-2: NVS上でのトラック設定の保存先。AnalogCfg(1-7-2、analogCfgLoadFromNvs/
// analogCfgSaveToNvs)と同じnvs_set_blob/nvs_get_blobパターンをそのまま踏襲する
// (TrackCfgもポインタを含まないPOD構造体のためblob化に問題ない)。5-2-1の結論
// (案B: NVS保存)の通り、現在アクティブな1トラック分のみを単一namespace・単一
// blobとして保存する(複数トラック切り替えが必要になった場合はキーを追加する形で拡張)。
static const char *kTrackCfgNvsNamespace = "trackcfg";
static const char *kTrackCfgNvsKey = "track0";

static void trackCfgLoadFromNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kTrackCfgNvsNamespace, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        // 初回起動等でnamespace未作成の場合は構造体のデフォルト値のまま使う
        return;
    }
    TrackCfg loaded;
    size_t required = sizeof(loaded);
    esp_err_t rerr = nvs_get_blob(handle, kTrackCfgNvsKey, &loaded, &required);
    if (rerr == ESP_OK && required == sizeof(loaded)) {
        g_trackCfg = loaded;
    }
    nvs_close(handle);
}

// flashCfg受信時(Writeボタン相当、rcpSendFlashCfgAck参照)に呼ぶ。
static void trackCfgSaveToNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kTrackCfgNvsNamespace, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_open (RW) failed: %s", esp_err_to_name(err));
        return;
    }
    nvs_set_blob(handle, kTrackCfgNvsKey, &g_trackCfg, sizeof(g_trackCfg));
    esp_err_t cerr = nvs_commit(handle);
    if (cerr != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_commit failed: %s", esp_err_to_name(cerr));
    }
    nvs_close(handle);
}

// 5-1-3: `{"trackCfg":{...}}`応答。5-1-2確認の通り、公式アプリのTrack.fromJsonは
// "sec"キーが存在しないとlen()呼び出しで例外になるため、セクター未対応でも
// 空配列[]を必ず含める。setTrackCfgで受信した値をそのまま返せるかが本タスクの
// 動作確認手段となるため、getTrackCfgもここで実データ応答に変更する。
static void rcpSendTrackCfg()
{
    JsonDocument doc;
    JsonObject result = doc["trackCfg"].to<JsonObject>();
    result["rad"] = g_trackCfg.radius;
    result["autoDetect"] = 0;
    JsonObject track = result["track"].to<JsonObject>();
    track["id"] = g_trackCfg.trackId;
    track["type"] = 0; // circuit固定(5-1-1設計の通りstage/セクターは非対応)
    track["sec"].to<JsonArray>();
    JsonArray sf = track["sf"].to<JsonArray>();
    sf.add(g_trackCfg.startFinishLat);
    sf.add(g_trackCfg.startFinishLon);
    rcpSendJsonLine(doc);
}

// 5-1-3: `{"setTrackCfg":{"rad":...,"track":{"id":...,"sf":[lat,lon]}}}`受信時に
// RAM上のg_trackCfgへ保存する。5-1-1設計の通りrad/track.id/sfのみ反映し、
// autoDetect/type/セクターは無視する(circuit以外のstage用st/finにも非対応)。
//
// 実機確認で判明した重要な差異：5-1-2で参照した非公式フォーク(ryandoherty/
// RaceCapture_App)のソースでは"setTrackCfg"直下に"rad"/"track"が来る想定だったが、
// 手元の実機公式アプリ(Windows版)は実際には
// `{"setTrackCfg":{"trackCfg":{"rad":...,"track":{...}}}}`と、さらに"trackCfg"
// キーで一段ラップして送ってくることをシリアルログで確認した(HANDOFF.md記載の
// 「参照リポジトリは補助情報止まり、一次情報源は実機観測」という方針通りの結果)。
// このネストを考慮せず"rad"/"track"を直接見ると常にnullで、Writeしても
// 値が一切反映されない不具合になっていたため、"trackCfg"キーがあればその中身を
// 使うようにした。
static void rcpHandleSetTrackCfg(JsonObjectConst payload)
{
    if (!payload.isNull()) {
        JsonObjectConst nested = payload["trackCfg"];
        JsonObjectConst fields = nested.isNull() ? payload : nested;

        if (!fields["rad"].isNull()) {
            g_trackCfg.radius = fields["rad"].as<float>();
        }
        JsonObjectConst track = fields["track"];
        if (!track.isNull()) {
            if (!track["id"].isNull()) {
                g_trackCfg.trackId = track["id"].as<int32_t>();
            }
            JsonArrayConst sf = track["sf"];
            if (!sf.isNull() && sf.size() >= 2) {
                g_trackCfg.startFinishLat = sf[0].as<float>();
                g_trackCfg.startFinishLon = sf[1].as<float>();
            }
        }
    }
    JsonDocument doc;
    JsonObject result = doc["setTrackCfg"].to<JsonObject>();
    result["rc"] = kApiSuccess;
    rcpSendJsonLine(doc);
}

// 1-4-7: getConnCfg/setConnCfgの現状(空応答スタブ)を実データ保持へ変更する構造。
// 1-4-6で判明した「Podium Connectのストリーミングキーが接続の度に再入力を要求される」
// 問題への対応。公式ファームウェア(reference/RaceCapture-Pro_firmware/src/logger/loggerApi.c
// のapi_getConnectivityConfig/api_setConnectivityConfig)ではbtCfg/cellCfg/telCfgの3つに
// 分かれるが、本プロジェクトはUSB接続のみでBluetooth/Cellularハードウェアを持たないため、
// bt/cellは常に無効固定とし、telCfg.deviceId(Podiumのストリーミングキーに相当)のみを
// TrackCfg(5-2-2)と同じnvs_set_blob/nvs_get_blobパターンでNVS永続化する。
struct ConnCfg {
    char telemetryDeviceId[64] = "";
};

static ConnCfg g_connCfg;

static const char *kConnCfgNvsNamespace = "conncfg";
static const char *kConnCfgNvsKey = "conn0";

static void connCfgLoadFromNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kConnCfgNvsNamespace, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        // 初回起動等でnamespace未作成の場合は構造体のデフォルト値(空文字列)のまま使う
        return;
    }
    ConnCfg loaded;
    size_t required = sizeof(loaded);
    esp_err_t rerr = nvs_get_blob(handle, kConnCfgNvsKey, &loaded, &required);
    if (rerr == ESP_OK && required == sizeof(loaded)) {
        g_connCfg = loaded;
    }
    nvs_close(handle);
}

// flashCfg受信時(Writeボタン相当、rcpSendFlashCfgAck参照)に呼ぶ。
static void connCfgSaveToNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kConnCfgNvsNamespace, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_open (RW) failed: %s", esp_err_to_name(err));
        return;
    }
    nvs_set_blob(handle, kConnCfgNvsKey, &g_connCfg, sizeof(g_connCfg));
    esp_err_t cerr = nvs_commit(handle);
    if (cerr != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_commit failed: %s", esp_err_to_name(cerr));
    }
    nvs_close(handle);
}

static void rcpSendConnCfg()
{
    JsonDocument doc;
    JsonObject result = doc["connCfg"].to<JsonObject>();

    JsonObject bt = result["btCfg"].to<JsonObject>();
    bt["btEn"] = 0;
    bt["name"] = "";
    bt["pass"] = "";

    JsonObject cell = result["cellCfg"].to<JsonObject>();
    cell["cellEn"] = 0;
    cell["apnHost"] = "";
    cell["apnUser"] = "";
    cell["apnPass"] = "";

    JsonObject tel = result["telCfg"].to<JsonObject>();
    tel["bgStream"] = 0;
    tel["deviceId"] = g_connCfg.telemetryDeviceId;
    tel["host"] = "";

    rcpSendJsonLine(doc);
}

// `{"setConnCfg":{"connCfg":{"telCfg":{"deviceId":...}}}}`受信時にg_connCfgへ保存する。
// setTrackCfg(5-1-3)の実機確認と同じく、公式アプリ(Windows版)が"connCfg"キーで一段
// ラップして送ってくる可能性を考慮し、ラップの有無どちらでも受理できるようにする。
static void rcpHandleSetConnCfg(JsonObjectConst payload)
{
    if (!payload.isNull()) {
        JsonObjectConst nested = payload["connCfg"];
        JsonObjectConst fields = nested.isNull() ? payload : nested;

        JsonObjectConst tel = fields["telCfg"];
        if (!tel.isNull()) {
            const char *deviceId = tel["deviceId"];
            if (deviceId != nullptr) {
                snprintf(g_connCfg.telemetryDeviceId, sizeof(g_connCfg.telemetryDeviceId),
                         "%s", deviceId);
            }
        }
    }
    JsonDocument doc;
    JsonObject result = doc["setConnCfg"].to<JsonObject>();
    result["rc"] = kApiSuccess;
    rcpSendJsonLine(doc);
}

// 1-3-3: `{"capabilities":{...}}`応答。HANDOFF.md記載の通り、flagsを空リストに
// し、channels.*とdb.tracks/sectorsを全て0にすることで、has_gps等の条件付き
// 追加コマンド(getAnalogCfg等)が一切トリガーされないようにする。1-7でanalogのみ
// 疎通確認するため analog だけ非0にし、他は最小限の接続シーケンスのまま全て0にする。
static void rcpSendCapabilities()
{
    JsonDocument doc;
    JsonObject cap = doc["capabilities"].to<JsonObject>();
    cap["flags"].to<JsonArray>();
    JsonObject channels = cap["channels"].to<JsonObject>();
    channels["analog"] = kAnalogChannelCount;
    channels["imu"] = 0;
    channels["gpio"] = 0;
    channels["timer"] = 0;
    channels["pwm"] = 0;
    channels["can"] = 0;
    channels["obd2"] = 0;
    channels["canChan"] = 0;
    JsonObject sampleRates = cap["sampleRates"].to<JsonObject>();
    sampleRates["gps"] = 50;
    sampleRates["sensor"] = 1000;
    JsonObject db = cap["db"].to<JsonObject>();
    db["tracks"] = 0;
    db["sectors"] = 0;
    rcpSendJsonLine(doc);
}

// 1-3-3: 残り5つの接続必須コマンドへの空応答。HANDOFF.md記載の通り、各設定
// オブジェクトは中身が空`{}`で問題ない(アプリ側のfromJsonはdict.get()ベース)。
static void rcpSendEmptyObjectResponse(const char *key)
{
    JsonDocument doc;
    doc[key].to<JsonObject>();
    rcpSendJsonLine(doc);
}

// 1-7-4: 公式アプリの「Write」操作は、開いているタブに関わらずlapCfg等の
// 未実装set系コマンドも一括で書き込もうとする。応答がないとその他の設定
// (setAnalogCfg等)も含めて"Timeout waiting for 'setXxxCfg'"でWrite全体が
// エラー扱いになるため、getXxxCfgと同じ5コマンド分をスタブ実装しておく
// (中身を保存する必要はなく、成功応答を返すだけでよい)。
static void rcpSendSetCfgAck(const char *key)
{
    JsonDocument doc;
    JsonObject result = doc[key].to<JsonObject>();
    result["rc"] = kApiSuccess;
    rcpSendJsonLine(doc);
}

// 1-3-5: `getMeta`応答用のダミーチャンネル定義。`rcp_mock_device.py`のCHANNELSと
// 同じ内容(nm/ut/min/max/prec/sr)。1-3-6で"s"応答のmeta同送にもこの定義を流用する。
struct RcpChannelMeta {
    const char *nm;
    const char *ut;
    int min;
    int max;
    int prec;
    int sr;
};

static const RcpChannelMeta kDummyChannels[] = {
    {"RPM",       "rpm", 0,    10000, 0, 10},
    {"Speed",     "mph", 0,    200,   1, 10},
    {"WaterTemp", "F",   0,    300,   0, 5},
    {"OilPress",  "psi", 0,    150,   1, 5},
    {"Lat",       "deg", -90,  90,    6, 10},
    {"Lon",       "deg", -180, 180,   6, 10},
};

// 5-5-1: Phase5(5-1〜5-4)で実装したラップタイム・予測タイム計算の結果を公式アプリへ
// 表示するためのチャンネル定義。5-1-1設計結果で洗い出した公式lapCfgの9チャンネル分
// (nm/ut/prec/sr)を、`reference/RaceCapture-Pro_firmware`の実機応答例
// (test/json_api_files/getMeta_response.json)に合わせてそのまま採用する。
// Sector/SectorTimeは本プロジェクトでは複数セクター判定を実装しない方針(5-1-1参照)
// のため値は常に0を送るのみになるが、公式アプリ側のUI要素(チャンネル選択リスト等)との
// 互換性を優先し、メタデータ自体は他の8チャンネルと同様に定義しておく。
// 値の実送信(sコマンドへの反映)は5-5-2でrcpSendSample()に実装した。
static const RcpChannelMeta kLapChannels[] = {
    {"LapCount",    "",    0, 0, 0, 10},
    {"LapTime",     "Min", 0, 0, 4, 10},
    {"Sector",      "",    0, 0, 0, 10},
    {"SectorTime",  "Min", 0, 0, 4, 10},
    {"PredTime",    "Min", 0, 0, 4, 5},
    {"ElapsedTime", "Min", 0, 0, 4, 10},
    {"CurrentLap",  "",    0, 0, 0, 10},
    {"Distance",    "mi",  0, 0, 4, 10},
    {"SessionTime", "Min", 0, 0, 4, 10},
};

// 1-3-5: `{"meta":[{"nm":..,"ut":..,"min":..,"max":..,"prec":..,"sr":..}, ...]}`応答。
// アプリ側は一度受け取るとキャッシュするため、以後の再送は不要(HANDOFF.md参照)。
// 5-5-1でkLapChannels(ラップタイム・予測タイム関連)を追加送出するようになった。
static void rcpSendMeta()
{
    JsonDocument doc;
    JsonArray meta = doc["meta"].to<JsonArray>();
    for (const auto &ch : kDummyChannels) {
        JsonObject obj = meta.add<JsonObject>();
        obj["nm"] = ch.nm;
        obj["ut"] = ch.ut;
        obj["min"] = ch.min;
        obj["max"] = ch.max;
        obj["prec"] = ch.prec;
        obj["sr"] = ch.sr;
    }
    for (const auto &ch : kLapChannels) {
        JsonObject obj = meta.add<JsonObject>();
        obj["nm"] = ch.nm;
        obj["ut"] = ch.ut;
        obj["min"] = ch.min;
        obj["max"] = ch.max;
        obj["prec"] = ch.prec;
        obj["sr"] = ch.sr;
    }
    rcpSendJsonLine(doc);
}

// 1-3-6: `s`応答用の数値を指定小数桁数に丸める（JSON表現を短く保つため）。
static double roundToPrec(double v, int prec)
{
    double scale = pow(10, prec);
    return round(v * scale) / scale;
}

// 1-3-6: `{"s":{"t":<tick>,"d":[v1,...,vN,<bitmask>]}}`応答。
// rcp_mock_device.pyのsample_values()と同じ考え方(sin波で緩やかに変動する
// ダミー値)をESP32上で再現し、kDummyChannelsの6チャンネル分を毎回送る。
// Lat/Lonは5-3-1でsimTrackGetPosition()によるコース周回シミュレーションに
// 置き換えた(taskAのSensorLogRecordと同じ軌道を共有する)。
//
// 5-5-2: kLapChannels(9ch)の値をここに追加した。taskA側で更新されるg_lapDetector/
// g_currentLapDistanceM/g_predDelta*/g_lastLapTimeSecをそのまま読む(taskA/taskC間の
// 排他制御は既存のg_trackCfg等と同様に行わない、既存踏襲)。kLapChannelsのnm/ut(5-5-1、
// 公式getMeta_response.json準拠)に合わせ、LapTime/PredTime/ElapsedTime/SessionTimeは
// 秒→分、Distanceはメートル→マイルへ変換して送る点に注意。
static void rcpSendSample()
{
    static uint32_t tick = 0;
    double t = static_cast<double>(esp_timer_get_time()) / 1000000.0;
    double simLat, simLon;
    simTrackGetPosition(t, &simLat, &simLon);

    JsonDocument doc;
    JsonObject s = doc["s"].to<JsonObject>();
    s["t"] = tick;
    JsonArray d = s["d"].to<JsonArray>();
    d.add(static_cast<int>(3000 + 2000 * sin(t / 3)));           // RPM
    d.add(roundToPrec(60 + 40 * sin(t / 5), 1));                 // Speed
    d.add(static_cast<int>(180 + 10 * sin(t / 7)));              // WaterTemp
    d.add(roundToPrec(40 + 5 * sin(t / 4), 1));                  // OilPress
    d.add(roundToPrec(simLat, 6));                                // Lat
    d.add(roundToPrec(simLon, 6));                                // Lon

    // g_lapDetector.lapCountはスタート/フィニッシュを外→内へ横切った通算回数=現在
    // 走行中のラップ番号(公式のCurrentLap相当)。公式のLapCountは「完了したラップ数」
    // (reference/RaceCapture-Pro_firmwareのgetLapCount/lapstats_current_lapの違いを
    // 参照)を指すため、1周も完了していない間は0になるようcurrentLapから1引いてクランプする。
    uint32_t currentLap = g_lapDetector.lapCount;
    int completedLaps = (currentLap > 0) ? static_cast<int>(currentLap - 1) : 0;

    // 現在ラップ開始からの経過時間。lapRecorderUpdate内のtimeSinceLapStartと同じ考え方
    // だが、taskC(このrcpSendSample)は自前のtで計算する必要があるためここで求め直す。
    double elapsedLapTimeSec = t - g_lapDetector.lapStartTimeSec;
    if (elapsedLapTimeSec < 0.0) {
        elapsedLapTimeSec = 0.0;
    }

    double predDeltaMin = g_predDeltaValid ? (g_predDeltaSec / 60.0) : 0.0;
    constexpr double kMilesPerMeter = 0.000621371;

    d.add(completedLaps);                                             // LapCount
    d.add(roundToPrec(g_lastLapTimeSec / 60.0, 4));                   // LapTime (Min)
    d.add(0);                                                         // Sector (非対応、常に0)
    d.add(0.0);                                                       // SectorTime (非対応、常に0)
    d.add(roundToPrec(predDeltaMin, 4));                              // PredTime (Min)
    d.add(roundToPrec(elapsedLapTimeSec / 60.0, 4));                  // ElapsedTime (Min)
    d.add(static_cast<int>(currentLap));                              // CurrentLap
    d.add(roundToPrec(g_currentLapDistanceM * kMilesPerMeter, 4));    // Distance (mi)
    d.add(roundToPrec(t / 60.0, 4));                                  // SessionTime (Min)

    d.add((1 << 15) - 1); // bitmask: kDummyChannels(6ch)+kLapChannels(9ch)全15chとも有効
    rcpSendJsonLine(doc);
    tick++;
}

// 1-4-8: `{"getStatus":null}`への応答。コマンドディスパッチャに分岐が無く無視されて
// いたため、公式アプリ(StatusPump)が接続直後から恒常的にタイムアウトし続けていた
// 不具合(1-4-6副産物2)への対応。JSON構造は公式ファームウェア(reference/RaceCapture-Pro_firmware/
// src/logger/loggerApi.cのapi_getStatus)に合わせる。cell/bt等ハードウェア非搭載の項目は省略、
// GPS位置はrcpSendSample同様simTrackGetPosition()のシミュレーション軌跡を使う。
static void rcpSendStatus()
{
    double t = static_cast<double>(esp_timer_get_time()) / 1000000.0;
    double simLat, simLon;
    simTrackGetPosition(t, &simLat, &simLon);

    JsonDocument doc;
    JsonObject status = doc["status"].to<JsonObject>();

    JsonObject system = status["system"].to<JsonObject>();
    system["model"] = "RCPMK3";
    system["ver_major"] = 2;
    system["ver_minor"] = 16;
    system["ver_bugfix"] = 1;
    system["uptime"] = static_cast<uint32_t>(t);

    JsonObject gps = status["GPS"].to<JsonObject>();
    gps["init"] = 1;
    gps["qual"] = 1;
    gps["lat"] = roundToPrec(simLat, 6);
    gps["lon"] = roundToPrec(simLon, 6);
    gps["sats"] = 8;
    gps["DOP"] = 1;

    // "記録は絶対に止めない"方針上、taskBのSDロギングは起動直後から常時動作する
    // 設計のため固定値でよい(taskB側のg_sdMounted変数はtaskC定義より後方のため参照しない)。
    JsonObject logging = status["logging"].to<JsonObject>();
    logging["status"] = 1;
    logging["dur"] = static_cast<uint32_t>(t);

    JsonObject track = status["track"].to<JsonObject>();
    track["status"] = 1;
    track["valid"] = true;
    track["trackId"] = g_trackCfg.trackId;
    track["inLap"] = (g_lapDetector.lapCount > 0) ? 1 : 0;
    track["armed"] = 0;

    rcpSendJsonLine(doc);
}

// 1-3-2: 受信した1メッセージ分のJSON文字列を解釈し、既知のコマンドに応答する。
static void rcpHandleMessage(const char *line)
{
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, line);
    if (err) {
        ESP_LOGW(kRcpTag, "JSON parse failed: %s (line=\"%s\")", err.c_str(), line);
        return;
    }

    JsonObject obj = doc.as<JsonObject>();
    if (obj.isNull()) {
        return;
    }

    // rcp_mock_device.py同様、各コマンドは単一キーのオブジェクトなので先頭のキーだけ見る
    const char *cmdName = nullptr;
    for (JsonPair kv : obj) {
        cmdName = kv.key().c_str();
        break;
    }
    if (cmdName == nullptr) {
        return;
    }

    if (strcmp(cmdName, "getVer") == 0) {
        rcpSendVer();
    } else if (strcmp(cmdName, "getCapabilities") == 0) {
        rcpSendCapabilities();
    } else if (strcmp(cmdName, "getLapCfg") == 0) {
        rcpSendEmptyObjectResponse("lapCfg");
    } else if (strcmp(cmdName, "getTrackCfg") == 0) {
        rcpSendTrackCfg();
    } else if (strcmp(cmdName, "getCanCfg") == 0) {
        rcpSendEmptyObjectResponse("canCfg");
    } else if (strcmp(cmdName, "getObd2Cfg") == 0) {
        rcpSendEmptyObjectResponse("obd2Cfg");
    } else if (strcmp(cmdName, "getConnCfg") == 0) {
        rcpSendConnCfg();
    } else if (strcmp(cmdName, "setLapCfg") == 0) {
        rcpSendSetCfgAck("setLapCfg");
    } else if (strcmp(cmdName, "setTrackCfg") == 0) {
        rcpHandleSetTrackCfg(obj["setTrackCfg"].as<JsonObjectConst>());
    } else if (strcmp(cmdName, "setCanCfg") == 0) {
        rcpSendSetCfgAck("setCanCfg");
    } else if (strcmp(cmdName, "setObd2Cfg") == 0) {
        rcpSendSetCfgAck("setObd2Cfg");
    } else if (strcmp(cmdName, "setConnCfg") == 0) {
        rcpHandleSetConnCfg(obj["setConnCfg"].as<JsonObjectConst>());
    } else if (strcmp(cmdName, "getStatus") == 0) {
        rcpSendStatus();
    } else if (strcmp(cmdName, "getMeta") == 0) {
        rcpSendMeta();
    } else if (strcmp(cmdName, "getAnalogCfg") == 0) {
        rcpSendGetAnalogCfg(obj["getAnalogCfg"]);
    } else if (strcmp(cmdName, "setAnalogCfg") == 0) {
        rcpHandleSetAnalogCfg(obj["setAnalogCfg"].as<JsonObjectConst>());
    } else if (strcmp(cmdName, "flashCfg") == 0) {
        rcpSendFlashCfgAck();
    } else if (strcmp(cmdName, "s") == 0) {
        rcpSendSample();
    } else {
        ESP_LOGW(kRcpTag, "unknown/unimplemented command, ignoring: %s", cmdName);
    }
}

// 1-1-4/1-3-7: タスクC（USB/シリアル送信役）。1-1-4時点ではタスクAのダミー値を
// キューからPopしてログ出力するだけだったが、1-3-7で1-3のRCP受信・応答処理を
// このタスクへ統合した。1ループの中で、(1)タスクAのキューを非ブロッキングでPop
// してログ出力、(2)USB CDC経由のRCPメッセージ受信・応答、の両方を行う。
static void taskC(void *pvParameters)
{
    rcpUsbInit();

    static char lineBuf[kRcpLineBufSize];
    size_t lineLen = 0;
    uint8_t readBuf[kRcpReadChunkSize];

    for (;;) {
        // (1) 1-1-4由来：タスクAが積んだダミー値を非ブロッキングでPopしてログ出力
        uint32_t received = 0;
        if (xQueueReceive(taskAToTaskCQueueHandle, &received, 0) == pdPASS) {
            printf("[taskC] sent to serial: %lu\n", static_cast<unsigned long>(received));
        }

        // (2) 1-3-1由来：RCP受信パーサ。100msタイムアウトでブロックすることで
        // タスクCのCPU占有を防ぎつつ、上記(1)のPopも一定間隔で回す
        int n = rcpUsbReadBytes(readBuf, sizeof(readBuf), pdMS_TO_TICKS(100));
        for (int i = 0; i < n; i++) {
            char c = static_cast<char>(readBuf[i]);
            if (c == '\r') {
                if (lineLen > 0) {
                    lineBuf[lineLen] = '\0';
                    printf("[taskC] rcp message: %s\n", lineBuf);
                    rcpHandleMessage(lineBuf);
                    lineLen = 0;
                }
            } else if (c == '\n') {
                // `\r\n`終端の場合に空メッセージを作らないよう、\nは常に読み捨てる
                // (仕様上は`\r`のみ終端だが、手動テスト時の端末が\r\nを送るケースへの保険)
            } else if (lineLen < kRcpLineBufSize - 1) {
                lineBuf[lineLen++] = c;
            } else {
                ESP_LOGW(kRcpTag, "line buffer overflow, discarding");
                lineLen = 0;
            }
        }
    }
}

// 1-2-3: タスクB（SD書き込み役）。1-2-1で実配線確認済みのピン配置
// (CLK=GPIO12/CMD=GPIO11/D0=GPIO13/D1=GPIO14/D2=GPIO9/D3=GPIO10、SDMMC 4bit)で
// SDカードをマウントし、taskAToTaskBQueueHandleからPopした1-2-2の
// SensorLogRecordをCSV形式で書き込む。C3はSDMMCホストペリフェラル非搭載のため
// SD保存自体がS3限定(1-1-6の優先度検証用ダミー処理をC3側にそのまま残す)。
#if CONFIG_IDF_TARGET_ESP32S3
static const char *kSdTag = "sd_log";
#define SD_MOUNT_POINT "/sdcard"
static const char kSdLogFilePath[] = SD_MOUNT_POINT "/log.csv";
static bool g_sdMounted = false;

static bool sdCardMount()
{
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {};
    mount_config.format_if_mount_failed = false;
    mount_config.max_files = 2;
    mount_config.allocation_unit_size = 16 * 1024;

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    sdmmc_slot_config_t slot_config = SDMMC_SLOT_CONFIG_DEFAULT();
    slot_config.width = 4;
    slot_config.clk = GPIO_NUM_12;
    slot_config.cmd = GPIO_NUM_11;
    slot_config.d0 = GPIO_NUM_13;
    slot_config.d1 = GPIO_NUM_14;
    slot_config.d2 = GPIO_NUM_9;
    slot_config.d3 = GPIO_NUM_10;

    sdmmc_card_t *card = nullptr;
    esp_err_t ret = esp_vfs_fat_sdmmc_mount(SD_MOUNT_POINT, &host, &slot_config, &mount_config, &card);
    if (ret != ESP_OK) {
        ESP_LOGE(kSdTag, "SD mount failed (%s). Check wiring/pullups.", esp_err_to_name(ret));
        return false;
    }
    ESP_LOGI(kSdTag, "SD mounted at " SD_MOUNT_POINT);
    sdmmc_card_print_info(stdout, card);
    return true;
}

static const char kSdCsvHeader[] =
    "timestampMs,lat,lon,speedKph,accelX,accelY,accelZ,gyroX,gyroY,gyroZ,rpm,waterTempC,oilPressKpa\n";

// 1-2-4: flushタイミング。1-2-3時点の「都度flush」はレコード(taskAの生成間隔100ms)ごとに
// SDカードへ物理書き込みが発生し、書き込み回数の増大(フラッシュメモリの摩耗)とスループット
// 低下を招く。時間ベースで間引き、経過時間の上限を明確にする(行数ベースだと、キューの
// 詰まり具合で実際のflush間隔が変動してしまうため)。
// 500msという値は、taskAの生成間隔(100ms)基準で最大5レコード分をまとめて書き込める
// 程度にSDカードへの書き込み頻度を下げつつ、「記録を絶対に止めない」方針(ARCHITECTURE.md
// 1章)との兼ね合いで電源断時に失われうるデータを最大500ms分に収める、というバランスで
// 選んだ値。1-2-5の電源断テストで、この間隔で問題ないか実データで検証する。
constexpr int64_t kSdFlushIntervalUs = 500 * 1000;

static void taskB(void *pvParameters)
{
    FILE *logFile = nullptr;
    if (g_sdMounted) {
        // 1-2-5の電源断テストで判明：直前の起動時に改行を書く前に電源が切れて
        // いると、末尾の行が改行なしで終わったまま残ることがある。その状態で
        // fopen(path, "a")して追記すると、新しいレコードが壊れた行の続きとして
        // 連結され、CSVの列数が合わない壊れた行になってしまう(実機テストで確認済み)。
        //
        // 末尾チェックを追記用ハンドル自体("a+")で行う実装を最初に試したが、
        // ESP-IDFのFATFS VFS層はO_APPENDが立ったハンドルの読み込み位置も常に
        // 末尾へ強制してしまうらしく、fseek()で1バイト前に戻してもfgetc()が
        // 常にEOFを返し、「改行で終わっていない」と誤判定して既に改行済みの
        // 行にも毎回余計な空行を追加してしまう不具合を実機テストで確認した。
        // そのため、末尾1バイトの確認は読み込み専用("r")の別ハンドルで行い、
        // 書き込み用ハンドルとは完全に分離する。
        FILE *checkFile = fopen(kSdLogFilePath, "r");
        if (checkFile != nullptr) {
            fseek(checkFile, 0, SEEK_END);
            long size = ftell(checkFile);
            if (size > 0) {
                fseek(checkFile, -1, SEEK_END);
                int lastChar = fgetc(checkFile);
                fclose(checkFile);
                if (lastChar != '\n') {
                    FILE *fixFile = fopen(kSdLogFilePath, "a");
                    if (fixFile != nullptr) {
                        fputc('\n', fixFile);
                        fflush(fixFile);
                        fsync(fileno(fixFile));
                        fclose(fixFile);
                    }
                }
            } else {
                fclose(checkFile);
            }
        }

        // 追記モード: 1-2-5の電源断テストで直前までのデータを残すため、
        // 起動の都度上書きはしない。ファイルが空(初回作成)ならヘッダーを書く。
        logFile = fopen(kSdLogFilePath, "a");
        if (logFile == nullptr) {
            ESP_LOGE(kSdTag, "failed to open %s for writing", kSdLogFilePath);
        } else {
            fseek(logFile, 0, SEEK_END);
            if (ftell(logFile) == 0) {
                fputs(kSdCsvHeader, logFile);
                fflush(logFile);
            }
        }
    }

    int64_t lastFlushUs = esp_timer_get_time();

    for (;;) {
        SensorLogRecord rec;
        if (xQueueReceive(taskAToTaskBQueueHandle, &rec, pdMS_TO_TICKS(200)) == pdPASS) {
            if (logFile != nullptr) {
                fprintf(logFile,
                        "%lu,%.6f,%.6f,%.2f,%.4f,%.4f,%.4f,%.4f,%.4f,%.4f,%.1f,%.1f,%.1f\n",
                        static_cast<unsigned long>(rec.timestampMs), rec.lat, rec.lon, rec.speedKph,
                        rec.accelX, rec.accelY, rec.accelZ, rec.gyroX, rec.gyroY, rec.gyroZ, rec.rpm,
                        rec.waterTempC, rec.oilPressKpa);
                printf("[taskB] wrote record t=%lu to SD\n", static_cast<unsigned long>(rec.timestampMs));
            } else {
                printf("[taskB] SD not mounted, dropped record t=%lu\n",
                       static_cast<unsigned long>(rec.timestampMs));
            }
        }

        // xQueueReceiveがタイムアウトした場合(キューが空でレコードが来なかった場合)でも
        // flush間隔の上限を守れるよう、Pop成否に関わらず毎ループ経過時間をチェックする。
        if (logFile != nullptr) {
            int64_t nowUs = esp_timer_get_time();
            if (nowUs - lastFlushUs >= kSdFlushIntervalUs) {
                // 実機検証で判明した重要な注意点：fflush()はCライブラリ側のバッファを
                // FATFSのf_write()まで渡すだけで、ディレクトリエントリ(ファイルサイズ含む)の
                // 実ディスクへのコミットは行われない(ESP-IDFのvfs_fat_write()はKconfig
                // CONFIG_FATFS_IMMEDIATE_FSYNC無効時、write毎のf_sync()を省略する実装のため)。
                // fflush()のみの状態でSDカードを抜くとファイルサイズが0バイトのまま
                // 残ることを実機で確認した。fsync()(内部でf_sync()を呼ぶ)を明示的に
                // 呼び、電源断時にもここまでの書き込みが読み出せる状態を保証する。
                fflush(logFile);
                fsync(fileno(logFile));
                lastFlushUs = nowUs;
            }
        }
    }
}
#else
// 1-1-6: タスクB（SD書き込み役）の優先度検証用プレースホルダー
// C3はSDMMCホストペリフェラル非搭載のためSD保存機能自体がスコープ外(1-2-3参照)。
// タスクB=最優先が狙い通り動くかを確認するため、CPUを一定時間占有する
// ダミー処理のみ行う（タスクA/Cとの実行順・詰まり具合を観察する用途）
static void taskB(void *pvParameters)
{
    for (;;) {
        volatile uint32_t dummyWork = 0;
        for (uint32_t i = 0; i < 100000; i++) {
            dummyWork += i;
        }
        printf("[taskB] busy-work cycle done (dummy=%lu)\n", static_cast<unsigned long>(dummyWork));
        vTaskDelay(pdMS_TO_TICKS(200));
    }
}
#endif

extern "C" void app_main(void)
{
    // 1-7-2: NVS初期化(ESP-IDF定型パターン: パーティション不整合時は一度消去して再初期化)
    esp_err_t nvsErr = nvs_flash_init();
    if (nvsErr == ESP_ERR_NVS_NO_FREE_PAGES || nvsErr == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        nvsErr = nvs_flash_init();
    }
    ESP_ERROR_CHECK(nvsErr);

    // 1-7-1/1-7-2: analog較正設定をデフォルト値で初期化した上で、NVSに保存済みの値があれば読み込む
    analogCfgInitAll();

    // 5-2-2: g_trackCfgは構造体のデフォルトメンバ初期化子で初期値済みのため、
    // AnalogCfgのようなsetDefault呼び出しは不要。NVSに保存済みの値があれば上書きする。
    trackCfgLoadFromNvs();
    // 1-4-7: g_connCfgも同様にデフォルト初期化子(空文字列)済みのため、NVS保存済みの値があれば上書きする。
    connCfgLoadFromNvs();

    // ArduinoJsonがArduino本体なしでビルド・動作することの確認用スタブ
    JsonDocument doc;
    doc["status"] = "RaceCapture logger firmware boot OK";

    char buf[128];
    serializeJson(doc, buf);
    printf("%s\n", buf);

    // minmeaのビルド確認用: サンプルGGA文をパース
    struct minmea_sentence_gga gga;
    if (minmea_parse_gga(&gga, "$GPGGA,092750.000,5321.6802,N,00630.3372,W,1,8,1.03,61.7,M,55.2,M,,*76")) {
        printf("minmea OK: satellites=%d\n", gga.satellites_tracked);
    }

    // 1-1-1: Hello Taskレベルの疎通確認用タスク
    xTaskCreate(helloTask, "hello_task", 2048, nullptr, tskIDLE_PRIORITY + 1, nullptr);

    // 1-1-2: キュー経由のPush/Pop確認
    queueTestHandle = xQueueCreate(10, sizeof(uint32_t));
    xTaskCreate(queuePushTask, "queue_push_task", 2048, nullptr, tskIDLE_PRIORITY + 1, nullptr);
    xTaskCreate(queuePopTask, "queue_pop_task", 2048, nullptr, tskIDLE_PRIORITY + 1, nullptr);

    // 1-1-3: タスクA→タスクC間のキューを準備
    taskAToTaskCQueueHandle = xQueueCreate(10, sizeof(uint32_t));

    // 1-2-2: タスクA→タスクB間のリングバッファ(SDログ用レコード)を準備
    taskAToTaskBQueueHandle = xQueueCreate(kSensorLogQueueLength, sizeof(SensorLogRecord));

#if CONFIG_IDF_TARGET_ESP32S3
    // 1-2-3: SDカード(SDMMC 4bit)をマウント。タスクB起動前に一度だけ実行する
    g_sdMounted = sdCardMount();
#endif

    // 1-1-6: ARCHITECTURE.md記載の優先度設計（タスクB=最優先／タスクA=高優先／
    // タスクC=低優先）を反映。タスクCは1-3-7でRCP受信・応答処理(usb_serial_jtag経由)を
    // 統合済みのため、単純な文字列出力より処理量が増える点を踏まえスタックを4096へ拡大。
    // タスクBは1-2-3でSD書き込み(fopen/fprintf等のFATFS処理)を実装したため、
    // S3ではC3のダミー処理版より多くのスタックを消費する想定で4096へ拡大。
#if CONFIG_IDF_TARGET_ESP32S3
    xTaskCreate(taskB, "task_b", 4096, nullptr, tskIDLE_PRIORITY + 3, nullptr); // 最優先（SD書き込み）
#else
    xTaskCreate(taskB, "task_b", 2048, nullptr, tskIDLE_PRIORITY + 3, nullptr); // 最優先
#endif
    xTaskCreate(taskA, "task_a", 2048, nullptr, tskIDLE_PRIORITY + 2, nullptr); // 高優先
    // 5-1-3: kRcpLineBufSizeを512→2048に拡大した結果、rcpSendJsonLine内の
    // ローカルバッファ(スタック確保)がJsonDocument等と合わせてtaskCのスタックを
    // 圧迫し、"stack overflow in task task_c"で実機がリセットする不具合を確認したため、
    // 4096→8192へ拡大した。
    xTaskCreate(taskC, "task_c", 8192, nullptr, tskIDLE_PRIORITY + 1, nullptr); // 低優先（RCP受信・応答を統合）
}
