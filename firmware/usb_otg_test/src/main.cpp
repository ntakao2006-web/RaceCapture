// RaceCapture USB OTGシリアル受信 動作確認用ファームウェア(使い捨て検証コード)
//
// 目的: スマホ版RaceCaptureアプリが、USB OTG経由でこのESP32C3をシリアルデバイスとして
// 認識し、テレメトリーを表示できるかどうかを確認する。
//
// RaceCaptureアプリは能動的にコマンドを送ってくる側であり、こちらが正しいJSONで
// 応答を返さないと「接続失敗」と判断される(HANDOFF.md参照)。そのため、PCで
// 既に検証済みのrcp_mock_device.pyの応答ロジックを、ネイティブUSB(USB Serial/JTAG)
// 経由でそのまま移植する。
//
// 推奨テスト手順:
//   1. まずPCにUSB-C接続し、公式RaceCaptureアプリ(Windows版)を割り当てられた
//      COMポートに向けて起動する。rcp_mock_device.pyの代わりにこのファームウェアが
//      応答できているか(=プロトコル実装が正しいか)をPC上で先に確認できる。
//   2. PC側で問題なければ、同じ書き込み済みのボードをスマホにUSB-C接続し直し、
//      スマホ版RaceCaptureアプリで同様にテレメトリーが表示されるか確認する。
//      ここで失敗する場合は、プロトコルではなくAndroid側のUSBデバイス認識が原因と切り分けられる。
//
// ログ設計:
//   デバッグログ(ESP_LOG)はUART0のみに出す(sdkconfig.defaultsでネイティブUSBへの
//   セカンダリコンソール出力を無効化済み)。ネイティブUSBポートはRaceCaptureアプリとの
//   JSON会話専用チャンネルとして汚さずに使う。
//   XIAO ESP32C3にはユーザー制御可能なオンボードLEDが無いため、スマホ接続中の
//   生存確認はできない。代わりにNVSへ受信コマンド数・最後に受けたコマンド名・
//   起動回数を記録し、後でPCに繋ぎ直した際に何が起きていたか復元できるようにする。

#include <cstdint>
#include <cstring>
#include <cmath>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_err.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "driver/usb_serial_jtag.h"

#include <ArduinoJson.h>

static const char *TAG = "rcp_usb_test";

namespace {

constexpr size_t kReadChunkSize = 256;
constexpr size_t kLineBufSize = 512;

// --- NVS診断カウンタ ---------------------------------------------------
// スマホ接続中はPC側でログを見られないため、後で再度PCに繋いだ時に
// 「何が起きていたか」を追えるようにするための最小限の記録。
nvs_handle_t g_nvsHandle = 0;
uint32_t g_cmdCount = 0;
char g_lastCmd[24] = {0};

// 直前セッション(前回起動〜今回リセットされるまで)の記録。
// スマホに繋いで結果が思わしくなかった場合、PCに繋ぎ直して"getDiag"を
// 送ればこの内容をネイティブUSB経由で読み出せる(=UART0の外部アダプタが無くても診断できる)。
uint32_t g_prevBootCount = 0;
uint32_t g_prevCmdCount = 0;
uint32_t g_prevByteCount = 0;
char g_prevLastCmd[24] = {0};

// 生の受信バイト数(行として完成したかどうかに関わらずカウント)。
// 「改行コード設定が違うだけで1バイトも届いていないように見える」ケースを
// 「本当に1バイトも届いていない」ケースと区別するために用意する。
uint32_t g_byteCount = 0;

void diagInit()
{
    esp_err_t err = nvs_open("rcp_diag", NVS_READWRITE, &g_nvsHandle);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "NVS open failed (%s), diagnostics disabled", esp_err_to_name(err));
        g_nvsHandle = 0;
        return;
    }

    size_t prevLastCmdLen = sizeof(g_prevLastCmd);
    nvs_get_u32(g_nvsHandle, "boot_count", &g_prevBootCount);
    nvs_get_u32(g_nvsHandle, "cmd_count", &g_prevCmdCount);
    nvs_get_u32(g_nvsHandle, "byte_count", &g_prevByteCount);
    nvs_get_str(g_nvsHandle, "last_cmd", g_prevLastCmd, &prevLastCmdLen);

    ESP_LOGI(TAG, "=== previous session (before this boot) ===");
    ESP_LOGI(TAG, "boot_count=%lu total_cmds_received=%lu total_bytes_received=%lu last_cmd=\"%s\"",
             (unsigned long)g_prevBootCount, (unsigned long)g_prevCmdCount,
             (unsigned long)g_prevByteCount, g_prevLastCmd);
    ESP_LOGI(TAG, "============================================");

    uint32_t newBoot = g_prevBootCount + 1;
    nvs_set_u32(g_nvsHandle, "boot_count", newBoot);
    nvs_set_u32(g_nvsHandle, "cmd_count", 0);
    nvs_set_u32(g_nvsHandle, "byte_count", 0);
    nvs_set_str(g_nvsHandle, "last_cmd", "");
    nvs_commit(g_nvsHandle);
}

void diagRecordCommand(const char *cmdName)
{
    g_cmdCount++;
    strncpy(g_lastCmd, cmdName, sizeof(g_lastCmd) - 1);
    g_lastCmd[sizeof(g_lastCmd) - 1] = '\0';

    if (g_nvsHandle == 0) {
        return;
    }
    // 短時間の手動テスト用途なので、フラッシュ書き込み回数の節約より
    // 「電源を抜かれた瞬間の値を正確に残す」ことを優先し、毎回commitする。
    nvs_set_u32(g_nvsHandle, "cmd_count", g_cmdCount);
    nvs_set_str(g_nvsHandle, "last_cmd", g_lastCmd);
    nvs_commit(g_nvsHandle);
}

void diagRecordBytes(size_t n)
{
    g_byteCount += static_cast<uint32_t>(n);
    if (g_nvsHandle == 0) {
        return;
    }
    nvs_set_u32(g_nvsHandle, "byte_count", g_byteCount);
    nvs_commit(g_nvsHandle);
}

// --- ネイティブUSB(USB Serial/JTAG)への送信 -----------------------------

void sendJsonLine(JsonDocument &doc)
{
    char buf[kLineBufSize];
    size_t n = serializeJson(doc, buf, sizeof(buf) - 2);
    buf[n++] = '\r';
    buf[n++] = '\n';

    // usb_serial_jtag_write_bytes()は1回の呼び出しで書き切れるバイト数に上限があり
    // (内部リングバッファサイズ相当、実測で約256バイト程度)、それを超える量を一度に
    // 渡すと超過分が黙って失われる。timeout(portMAX_DELAY)は「空きができるまで待つ」
    // だけで「全部書き切るまでループする」わけではないため、戻り値を見ながら
    // 自前でループして送り切る必要がある。
    size_t written = 0;
    while (written < n) {
        int w = usb_serial_jtag_write_bytes(reinterpret_cast<const uint8_t *>(buf) + written,
                                             n - written, portMAX_DELAY);
        if (w <= 0) {
            ESP_LOGW(TAG, "usb_serial_jtag_write_bytes stalled (wrote %u/%u)",
                     (unsigned)written, (unsigned)n);
            break;
        }
        written += static_cast<size_t>(w);
    }
}

// --- rcp_mock_device.pyと同じダミーチャンネル定義 -----------------------

struct ChannelDef {
    const char *nm;
    const char *ut;
    int min;
    int max;
    int prec;
    int sr;
};

constexpr ChannelDef kChannels[] = {
    {"RPM", "rpm", 0, 10000, 0, 10},
    {"Speed", "mph", 0, 200, 1, 10},
    {"WaterTemp", "F", 0, 300, 0, 5},
    {"OilPress", "psi", 0, 150, 1, 5},
    {"Lat", "deg", -90, 90, 6, 10},
    {"Lon", "deg", -180, 180, 6, 10},
};
constexpr size_t kChannelCount = sizeof(kChannels) / sizeof(kChannels[0]);

void addChannelsMeta(JsonArray metaArr)
{
    for (const auto &ch : kChannels) {
        JsonObject o = metaArr.add<JsonObject>();
        o["nm"] = ch.nm;
        o["ut"] = ch.ut;
        o["min"] = ch.min;
        o["max"] = ch.max;
        o["prec"] = ch.prec;
        o["sr"] = ch.sr;
    }
}

uint32_t g_tick = 0;

void sendVer()
{
    JsonDocument doc;
    JsonObject ver = doc["ver"].to<JsonObject>();
    ver["name"] = "RCPMK3";
    ver["fname"] = "RaceCapture/Pro MK3 (usb otg test fw)";
    ver["major"] = 2;
    ver["minor"] = 16;
    ver["bugfix"] = 1;
    ver["serial"] = "USBTEST01";
    ver["git_info"] = "usb-otg-test-build";
    ver["release_type"] = "release";
    sendJsonLine(doc);
}

void sendCapabilities()
{
    JsonDocument doc;
    JsonObject cap = doc["capabilities"].to<JsonObject>();
    cap["flags"].to<JsonArray>();
    JsonObject ch = cap["channels"].to<JsonObject>();
    ch["analog"] = 0;
    ch["imu"] = 0;
    ch["gpio"] = 0;
    ch["timer"] = 0;
    ch["pwm"] = 0;
    ch["can"] = 0;
    ch["obd2"] = 0;
    ch["canChan"] = 0;
    JsonObject sr = cap["sampleRates"].to<JsonObject>();
    sr["gps"] = 50;
    sr["sensor"] = 1000;
    JsonObject db = cap["db"].to<JsonObject>();
    db["tracks"] = 0;
    db["sectors"] = 0;
    sendJsonLine(doc);
}

void sendMeta()
{
    JsonDocument doc;
    JsonArray metaArr = doc["meta"].to<JsonArray>();
    addChannelsMeta(metaArr);
    sendJsonLine(doc);
}

void sendStatus()
{
    JsonDocument doc;
    JsonObject status = doc["status"].to<JsonObject>();
    JsonObject sys = status["system"].to<JsonObject>();
    sys["model"] = "RaceCapture/Pro MK3 (usb otg test fw)";
    sys["ver_major"] = 2;
    sys["ver_minor"] = 16;
    sys["ver_bugfix"] = 1;
    sys["uptime"] = static_cast<int64_t>(esp_timer_get_time() / 1000000);
    JsonObject gps = status["GPS"].to<JsonObject>();
    gps["init"] = 3;
    gps["qual"] = 1;
    gps["lat"] = 35.83;
    gps["lon"] = 139.41;
    gps["sats"] = 8;
    gps["DOP"] = 100;
    JsonObject logging = status["logging"].to<JsonObject>();
    logging["status"] = 0;
    logging["dur"] = 0;
    JsonObject track = status["track"].to<JsonObject>();
    track["status"] = 0;
    track["valid"] = false;
    track["trackId"] = 0;
    track["inLap"] = 0;
    track["armed"] = 0;
    sendJsonLine(doc);
}

void sendEmptyObjResponse(const char *key)
{
    JsonDocument doc;
    doc[key].to<JsonObject>();
    sendJsonLine(doc);
}

// RCPプロトコル上のコマンドではなく、この検証ファームウェア専用の診断コマンド。
// 前回セッション(直前にリセットされるまでの接続、例えばスマホ接続テスト)で
// 何コマンド受信できたか・最後に何を受けたかを返す。
void sendDiag()
{
    JsonDocument doc;
    JsonObject diag = doc["diag"].to<JsonObject>();
    diag["prevBootCount"] = g_prevBootCount;
    diag["prevSessionCmdCount"] = g_prevCmdCount;
    diag["prevSessionByteCount"] = g_prevByteCount;
    diag["prevSessionLastCmd"] = g_prevLastCmd;
    diag["curSessionCmdCount"] = g_cmdCount;
    diag["curSessionByteCount"] = g_byteCount;
    sendJsonLine(doc);
}

void sendSample(bool withMeta)
{
    double t = static_cast<double>(esp_timer_get_time()) / 1e6;
    int rpm = static_cast<int>(3000 + 2000 * sin(t / 3));
    double speed = 60 + 40 * sin(t / 5);
    int waterTemp = static_cast<int>(180 + 10 * sin(t / 7));
    double oilPress = 40 + 5 * sin(t / 4);
    double lat = 35.830000 + 0.0001 * sin(t);
    double lon = 139.410000 + 0.0001 * cos(t);

    JsonDocument doc;
    JsonObject s = doc["s"].to<JsonObject>();
    s["t"] = g_tick;
    JsonArray d = s["d"].to<JsonArray>();
    d.add(rpm);
    d.add(speed);
    d.add(waterTemp);
    d.add(oilPress);
    d.add(lat);
    d.add(lon);
    d.add((1u << kChannelCount) - 1); // 全チャンネル有効ビットマスク
    if (withMeta) {
        JsonArray metaArr = s["meta"].to<JsonArray>();
        addChannelsMeta(metaArr);
    }
    sendJsonLine(doc);
    g_tick++;
}

void handleCommand(JsonDocument &doc)
{
    JsonObject obj = doc.as<JsonObject>();
    if (obj.isNull()) {
        return;
    }

    // rcp_mock_device.py同様、各コマンドは単一キーのオブジェクトなので先頭のキーだけ見る
    const char *cmdName = nullptr;
    JsonVariant cmdVal;
    for (JsonPair kv : obj) {
        cmdName = kv.key().c_str();
        cmdVal = kv.value();
        break;
    }
    if (cmdName == nullptr) {
        return;
    }

    diagRecordCommand(cmdName);
    ESP_LOGI(TAG, "recv cmd: %s", cmdName);

    if (strcmp(cmdName, "getVer") == 0) {
        sendVer();
    } else if (strcmp(cmdName, "getCapabilities") == 0) {
        sendCapabilities();
    } else if (strcmp(cmdName, "getMeta") == 0) {
        sendMeta();
    } else if (strcmp(cmdName, "getStatus") == 0) {
        sendStatus();
    } else if (strcmp(cmdName, "getLapCfg") == 0) {
        sendEmptyObjResponse("lapCfg");
    } else if (strcmp(cmdName, "getTrackCfg") == 0) {
        sendEmptyObjResponse("trackCfg");
    } else if (strcmp(cmdName, "getCanCfg") == 0) {
        sendEmptyObjResponse("canCfg");
    } else if (strcmp(cmdName, "getObd2Cfg") == 0) {
        sendEmptyObjResponse("obd2Cfg");
    } else if (strcmp(cmdName, "getConnCfg") == 0) {
        sendEmptyObjResponse("connCfg");
    } else if (strcmp(cmdName, "s") == 0) {
        bool wantMeta = cmdVal.is<JsonObject>() && cmdVal["meta"].as<bool>();
        sendSample(wantMeta);
    } else if (strcmp(cmdName, "log") == 0) {
        bool streaming = cmdVal.as<bool>();
        JsonDocument resp;
        resp[streaming ? "logStart" : "logEnd"] = 1;
        sendJsonLine(resp);
    } else if (strcmp(cmdName, "getDiag") == 0) {
        sendDiag();
    } else {
        ESP_LOGW(TAG, "unknown command, ignoring: %s", cmdName);
    }
}

// --- ネイティブUSBからの生の受信 + 行分割 -------------------------------

void rcpUsbTestTask(void *)
{
    // デフォルト(256B程度)のTXリングバッファだと、getMeta/getStatus等の
    // 300バイトを超える応答が1回で丸ごと拒否される(usb_serial_jtag_write_bytesは
    // リクエストサイズがバッファ容量を超えると即座に書き込み0で返り、ブロック再試行しても
    // 状況が変わらない)。kLineBufSizeを余裕を持って収められるサイズまで拡張する。
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    cfg.tx_buffer_size = kLineBufSize * 2;
    cfg.rx_buffer_size = kLineBufSize;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&cfg));

    static char lineBuf[kLineBufSize];
    size_t lineLen = 0;
    uint8_t readBuf[kReadChunkSize];

    const int64_t bootTime = esp_timer_get_time();
    bool everReceivedAnything = false;
    bool warnedNoData = false;

    for (;;) {
        int n = usb_serial_jtag_read_bytes(readBuf, sizeof(readBuf), pdMS_TO_TICKS(100));
        if (n > 0) {
            everReceivedAnything = true;
            diagRecordBytes(static_cast<size_t>(n));
            for (int i = 0; i < n; i++) {
                char c = static_cast<char>(readBuf[i]);
                if (c == '\r' || c == '\n') {
                    if (lineLen > 0) {
                        lineBuf[lineLen] = '\0';
                        JsonDocument doc;
                        DeserializationError err = deserializeJson(doc, lineBuf, lineLen);
                        if (err) {
                            ESP_LOGW(TAG, "JSON parse failed: %s (line=\"%s\")", err.c_str(), lineBuf);
                        } else {
                            handleCommand(doc);
                        }
                        lineLen = 0;
                    }
                } else if (lineLen < kLineBufSize - 1) {
                    lineBuf[lineLen++] = c;
                } else {
                    ESP_LOGW(TAG, "line buffer overflow, discarding");
                    lineLen = 0;
                }
            }
        } else if (!everReceivedAnything && !warnedNoData &&
                   (esp_timer_get_time() - bootTime) > 30 * 1000000LL) {
            // 30秒経ってもホストから1バイトも来ない場合、プロトコル以前に
            // デバイスとして認識されていない可能性が高い
            ESP_LOGW(TAG, "no data received from host within 30s - "
                          "device may not be recognized as a serial port by the host");
            warnedNoData = true;
        }
    }
}

} // namespace

extern "C" void app_main(void)
{
    esp_err_t nvsErr = nvs_flash_init();
    if (nvsErr == ESP_ERR_NVS_NO_FREE_PAGES || nvsErr == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        nvsErr = nvs_flash_init();
    }
    ESP_ERROR_CHECK(nvsErr);

    diagInit();

    ESP_LOGI(TAG, "RCP USB OTG test firmware boot OK");
    ESP_LOGI(TAG, "waiting for host (PC's RaceCapture app, or phone's RaceCapture app) "
                  "to talk over native USB...");

    xTaskCreate(rcpUsbTestTask, "rcp_usb_test", 8192, nullptr, tskIDLE_PRIORITY + 2, nullptr);
}
