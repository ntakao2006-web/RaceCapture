#include <cmath>
#include <cstdio>
#include <cstring>
#include <ArduinoJson.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/usb_serial_jtag.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "nvs_flash.h"

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
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}

// 1-3-1: USB CDCシリアル(ネイティブUSB、USB Serial/JTAGペリフェラル)経由の
// RCP受信パーサ。1バイトずつ受信し、`\r`を1メッセージの区切りとして
// JSON文字列を切り出す。1-3-7でタスクC本体へ統合済み。
static const char *kRcpTag = "rcp_rx";
constexpr size_t kRcpReadChunkSize = 256;
constexpr size_t kRcpLineBufSize = 512;

// 1-3-2: `{"ver":{...}}`応答の送信。行末は`\r\n`(HANDOFF.md参照：公式アプリの
// 受信パーサは`\n`区切りで見ているため、モック→アプリ方向は`\r\n`で問題ない)。
static void rcpSendJsonLine(JsonDocument &doc)
{
    char buf[kRcpLineBufSize];
    size_t n = serializeJson(doc, buf, sizeof(buf) - 2);
    buf[n++] = '\r';
    buf[n++] = '\n';

    // USB Serial/JTAGのTXリングバッファ(デフォルト256バイト)より大きいサイズを
    // 一度にusb_serial_jtag_write_bytesへ渡すと、内部のxRingbufferSendが
    // 「要求サイズがバッファ全体に収まらない」と判定し、portMAX_DELAYで待っても
    // 入る余地がないため即座に失敗する(getMeta等、256バイトを超える応答で発生確認)。
    // そのためバッファ容量より確実に小さいチャンク単位に分割して送信する。
    constexpr size_t kUsbJtagWriteChunkSize = 128;
    size_t written = 0;
    while (written < n) {
        size_t chunk = n - written;
        if (chunk > kUsbJtagWriteChunkSize) {
            chunk = kUsbJtagWriteChunkSize;
        }
        int w = usb_serial_jtag_write_bytes(reinterpret_cast<const uint8_t *>(buf) + written,
                                             chunk, portMAX_DELAY);
        if (w <= 0) {
            ESP_LOGW(kRcpTag, "usb_serial_jtag_write_bytes stalled (wrote %u/%u)",
                     (unsigned)written, (unsigned)n);
            break;
        }
        written += static_cast<size_t>(w);
    }
}

static void rcpSendVer()
{
    JsonDocument doc;
    JsonObject ver = doc["ver"].to<JsonObject>();
    ver["name"] = "RCPMK3";
    ver["fname"] = "RaceCapture/Pro MK3 (esp32-c3 proto fw)";
    ver["major"] = 2;
    ver["minor"] = 16;
    ver["bugfix"] = 1;
    ver["serial"] = "C3PROTO01";
    ver["git_info"] = "esp32-c3-proto-build";
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

// setAnalogCfg後にWriteボタン相当でアプリが送ってくる。応答がないと公式アプリが
// "Timeout waiting for 'flashCfg'"でWriteをエラー扱いにする(0-8で実機確認済み)。
// 1-7-2: このタイミングで現在のRAM上の値をNVSへ書き込み、再起動後も保持されるようにする。
static void rcpSendFlashCfgAck()
{
    analogCfgSaveToNvs();

    JsonDocument doc;
    JsonObject result = doc["flashCfg"].to<JsonObject>();
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

// 1-3-5: `{"meta":[{"nm":..,"ut":..,"min":..,"max":..,"prec":..,"sr":..}, ...]}`応答。
// アプリ側は一度受け取るとキャッシュするため、以後の再送は不要(HANDOFF.md参照)。
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
static void rcpSendSample()
{
    static uint32_t tick = 0;
    double t = static_cast<double>(esp_timer_get_time()) / 1000000.0;

    JsonDocument doc;
    JsonObject s = doc["s"].to<JsonObject>();
    s["t"] = tick;
    JsonArray d = s["d"].to<JsonArray>();
    d.add(static_cast<int>(3000 + 2000 * sin(t / 3)));           // RPM
    d.add(roundToPrec(60 + 40 * sin(t / 5), 1));                 // Speed
    d.add(static_cast<int>(180 + 10 * sin(t / 7)));              // WaterTemp
    d.add(roundToPrec(40 + 5 * sin(t / 4), 1));                  // OilPress
    d.add(roundToPrec(35.830000 + 0.0001 * sin(t), 6));          // Lat
    d.add(roundToPrec(139.410000 + 0.0001 * cos(t), 6));         // Lon
    d.add((1 << 6) - 1); // bitmask: kDummyChannels全6chとも有効
    rcpSendJsonLine(doc);
    tick++;
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
        rcpSendEmptyObjectResponse("trackCfg");
    } else if (strcmp(cmdName, "getCanCfg") == 0) {
        rcpSendEmptyObjectResponse("canCfg");
    } else if (strcmp(cmdName, "getObd2Cfg") == 0) {
        rcpSendEmptyObjectResponse("obd2Cfg");
    } else if (strcmp(cmdName, "getConnCfg") == 0) {
        rcpSendEmptyObjectResponse("connCfg");
    } else if (strcmp(cmdName, "setLapCfg") == 0) {
        rcpSendSetCfgAck("setLapCfg");
    } else if (strcmp(cmdName, "setTrackCfg") == 0) {
        rcpSendSetCfgAck("setTrackCfg");
    } else if (strcmp(cmdName, "setCanCfg") == 0) {
        rcpSendSetCfgAck("setCanCfg");
    } else if (strcmp(cmdName, "setObd2Cfg") == 0) {
        rcpSendSetCfgAck("setObd2Cfg");
    } else if (strcmp(cmdName, "setConnCfg") == 0) {
        rcpSendSetCfgAck("setConnCfg");
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
    // CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAGが有効な場合、
    // コンソール初期化時に既にドライバがインストール済みのことがあるため、
    // ESP_ERR_INVALID_STATEはそのまま読み書き可能とみなして無視する。
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    esp_err_t err = usb_serial_jtag_driver_install(&cfg);
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_ERROR_CHECK(err);
    }

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
        int n = usb_serial_jtag_read_bytes(readBuf, sizeof(readBuf), pdMS_TO_TICKS(100));
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

// 1-1-6: タスクB（SD書き込み役）の優先度検証用プレースホルダー
// SDモジュール未調達のため実際のSD書き込みは1-2-3で実装する。ここでは
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

    // 1-1-6: ARCHITECTURE.md記載の優先度設計（タスクB=最優先／タスクA=高優先／
    // タスクC=低優先）を反映。タスクBはSD書き込み役の優先度検証用プレースホルダー。
    // タスクCは1-3-7でRCP受信・応答処理(usb_serial_jtag経由)を統合済みのため、
    // 単純な文字列出力より処理量が増える点を踏まえスタックを4096へ拡大。
    xTaskCreate(taskB, "task_b", 2048, nullptr, tskIDLE_PRIORITY + 3, nullptr); // 最優先
    xTaskCreate(taskA, "task_a", 2048, nullptr, tskIDLE_PRIORITY + 2, nullptr); // 高優先
    xTaskCreate(taskC, "task_c", 4096, nullptr, tskIDLE_PRIORITY + 1, nullptr); // 低優先（RCP受信・応答を統合）
}
