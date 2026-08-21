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
// 6-4-2: Lua用メモリアロケータをESP-IDFのヒープAPIへ差し替えるために使う。
#include "esp_heap_caps.h"

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

// 1-5-1: IMU(秋月AE-LSM6DSV16X、LSM6DSV16Xチップ)用I2Cドライバに使う、
// ESP-IDFネイティブの新I2Cマスタードライバ。C3/S3共通(SDMMCと異なりC3でも
// I2Cペリフェラルは使えるため、S3限定にしない)。GPIO_NUM_*定数用にdriver/gpio.hも
// 併せてincludeする(S3側は既にsdmmc用でincludeしているが、C3側は未includeのため)。
#include "driver/gpio.h"
#include "driver/i2c_master.h"
// 6-5-1: 車載CAN(内蔵TWAI)受信用。C3/S3ともTWAIペリフェラルを搭載しているため
// board条件分岐なしで共通include。レガシー`driver/twai.h`は非推奨化されているため
// 新ドライバのヘッダーを使う。
#include "esp_twai.h"
#include "esp_twai_onchip.h"

extern "C" {
#include "minmea.h"
}

// 6-4-1: Luaスクリプティング機構(Phase6)用の標準Lua本体。プラットフォーム非依存の
// ANSI C部分(`reference/RaceCapture-Pro_firmware/lib/lua/src`相当)を`firmware/lib/lua/`へ
// vendoringし、PlatformIOのLibrary Dependency Finderに拾わせるためここでincludeする
// (lib/minmea等の既存vendoringと同じパターン)。専用FreeRTOSタスクでの定期実行(6-4-3)は
// 未実装で、現時点は起動時の自己診断(下記luaAllocSelfTest)まで。
extern "C" {
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"
}

// 6-4-2: Lua用メモリアロケータ。lauxlib.cの既定実装(l_alloc、標準malloc/free/realloc)を
// ESP-IDFのヒープAPI(heap_caps_*)へ差し替える。ud/osizeは未使用(公式実装のl_alloc同様、
// 引数の型を変えずに済ませるため)。heap_caps_realloc()はptr==NULLをmalloc相当として、
// nsize==0はfreeとして扱うわけではない(0バイトreallocは未定義動作になりうる)ため、
// nsize==0のケースだけ明示的にheap_caps_free()へ分岐する(標準realloc実装の慣例と同じ)。
static const char *kLuaTag = "lua";

static void *luaEspAlloc(void *ud, void *ptr, size_t osize, size_t nsize)
{
    (void)ud;
    (void)osize;
    if (nsize == 0) {
        heap_caps_free(ptr);
        return nullptr;
    }
    return heap_caps_realloc(ptr, nsize, MALLOC_CAP_DEFAULT);
}

// luaEspAlloc()が実際にVM生成・標準ライブラリのオープン(この過程で多数のアロケーションが
// 発生する)・スクリプト実行に耐えることを起動時に確認する自己診断(1-1-1のhelloTask等と同じ
// 「まず動かして確かめる」パターン)。専用FreeRTOSタスクでの周期実行は6-4-3(下記luaTask)。
static void luaAllocSelfTest()
{
    lua_State *L = lua_newstate(luaEspAlloc, nullptr);
    if (L == nullptr) {
        ESP_LOGE(kLuaTag, "lua_newstate failed (out of memory?)");
        return;
    }
    luaL_openlibs(L);
    if (luaL_dostring(L, "return 1 + 41") == 0 && lua_isnumber(L, -1)
        && lua_tointeger(L, -1) == 42) {
        printf("lua OK: custom allocator + base libs working (1+41=%d)\n",
               static_cast<int>(lua_tointeger(L, -1)));
    } else {
        ESP_LOGE(kLuaTag, "self-test failed: %s", lua_tostring(L, -1));
    }
    lua_close(L);
}

// 6-4-3/6-4-4: Luaスクリプトを周期実行する専用タスク用の暫定スクリプト。6-6(setScriptCfg/
// getScriptCfgの実データ化、NVS保存)が未実装のため、公式のgetScript()相当(ユーザーが
// 書き込んだスクリプト本文を返す)の代わりにハードコードされたプレースホルダを使う。
// 6-6実装時にNVSから読んだ文字列へ差し替える。
static const char *kLuaPlaceholderScript =
    "tickCount = 0\n"
    "function onTick()\n"
    "  tickCount = tickCount + 1\n"
    "end\n";

// 公式luaTask.cの`LUA_PERIODIC_FUNCTION`("onTick")呼び出し間隔と同じ既定値(1Hz)。
constexpr TickType_t kLuaOnTickIntervalMs = 1000;

// 6-4-4: 公式の実行契約(luaTask.cのload_script()/lua_invocation())を再現する。スクリプト
// 本体(kLuaPlaceholderScript、6-6実装後はNVS由来の文字列)は起動時に一度だけluaL_dostring()
// で実行し、以降は`onTick`関数(グローバル)が定義されていればタスクループ周期ごとに呼び出す
// のみとする。`onTick`未定義は公式同様エラー扱いしない(RaceCapture-Pro Issue #707参照、
// 「onTickを持たないスクリプトは合法」という判断を踏襲)。
static void luaTask(void *pvParameters)
{
    lua_State *L = lua_newstate(luaEspAlloc, nullptr);
    if (L == nullptr) {
        ESP_LOGE(kLuaTag, "luaTask: lua_newstate failed, task exiting");
        vTaskDelete(nullptr);
        return;
    }
    luaL_openlibs(L);

    // スクリプト本体は起動時に一度だけ実行(onTick関数の定義はこの実行の副作用として行われる)。
    if (luaL_dostring(L, kLuaPlaceholderScript) != 0) {
        ESP_LOGE(kLuaTag, "luaTask: script load failed: %s", lua_tostring(L, -1));
        lua_pop(L, 1);
    }

    for (;;) {
        lua_getglobal(L, "onTick");
        if (lua_isnil(L, -1)) {
            // onTick未定義は許容(公式同様エラーにしない)。スタックを戻すだけ。
            lua_pop(L, 1);
        } else if (lua_pcall(L, 0, 0, 0) != 0) {
            ESP_LOGW(kLuaTag, "luaTask: onTick error: %s", lua_tostring(L, -1));
            lua_pop(L, 1);
        }
        vTaskDelay(pdMS_TO_TICKS(kLuaOnTickIntervalMs));
    }
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

// 1-5-1: IMU(秋月AE-LSM6DSV16X、LSM6DSV16Xチップ)用ドライバ。ESP-IDFネイティブの
// 新I2Cマスタードライバ(driver/i2c_master.h)で実装する。レジスタマップ・初期化ビット
// パターン・スケール係数は秋月電子の動作確認用Arduinoサンプル
// (other/check_AE-LSM6DSV16X_extracted/check_AE-LSM6DSV16X/check_AE-LSM6DSV16X.ino)の
// 実測値をそのまま踏襲する。配線・実機は1-5-3で対応するため、本タスクではビルド確認までとし、
// I2C通信が失敗する間は呼び出し側(taskA、1-5-2)がフォールバックできるよう戻り値で成否を返す。
static const char *kImuTag = "imu";

// 基板のJ2/J3ジャンパ設定でアドレスが変わるため、起動時に両方へ順にプローブする
constexpr uint8_t kImuAddrGnd = 0x6A; // J3(「6A」刻印近く)側を短絡した場合
constexpr uint8_t kImuAddrVcc = 0x6B; // J2(「6B」刻印近く)側を短絡した場合
constexpr uint8_t kImuProbeAddrs[] = {kImuAddrGnd, kImuAddrVcc};

constexpr uint8_t kImuRegWhoAmI = 0x0F;
constexpr uint8_t kImuRegCtrl1 = 0x10;
constexpr uint8_t kImuRegCtrl2 = 0x11;
constexpr uint8_t kImuRegCtrl6 = 0x15;
constexpr uint8_t kImuRegCtrl8 = 0x17;
constexpr uint8_t kImuRegOutXLG = 0x22;
constexpr uint8_t kImuWhoAmIExpected = 0x70;

// スケール係数(Arduinoサンプル実測値。CTRL6=0b00000100/CTRL8=0b10000010の設定に対応)
constexpr float kImuGyroScaleDpsPerLsb = 0.07f;
constexpr float kImuAccelScaleGPerLsb = 0.000244f;

// 配線は1-5-3で確定するため、ここではSDMMC(S3: GPIO9-14使用中、4章「SDカード
// インターフェースの設計方針」参照)と衝突しない空きGPIOを暫定値として選定。
// 1-5-3の実配線時に配線しやすいピンへ変更してよい。
#if CONFIG_IDF_TARGET_ESP32S3
constexpr gpio_num_t kImuSdaPin = GPIO_NUM_2;
constexpr gpio_num_t kImuSclPin = GPIO_NUM_1;
#else
// Seeed XIAO ESP32C3のQwiicコネクタ標準ピン
constexpr gpio_num_t kImuSdaPin = GPIO_NUM_6;
constexpr gpio_num_t kImuSclPin = GPIO_NUM_7;
#endif

static i2c_master_bus_handle_t g_imuI2cBus = nullptr;
static i2c_master_dev_handle_t g_imuI2cDev = nullptr;
static bool g_imuAvailable = false;

static bool imuWriteReg(uint8_t reg, uint8_t val)
{
    uint8_t buf[2] = {reg, val};
    return i2c_master_transmit(g_imuI2cDev, buf, sizeof(buf), pdMS_TO_TICKS(100)) == ESP_OK;
}

static bool imuReadRegs(uint8_t startReg, uint8_t *buf, size_t len)
{
    return i2c_master_transmit_receive(g_imuI2cDev, &startReg, 1, buf, len, pdMS_TO_TICKS(100)) == ESP_OK;
}

// I2Cバス初期化・0x6A/0x6Bへの順次プローブ・WHO_AM_I確認・初期化レジスタ書き込みを行う。
// 配線が無い間は必ずプローブ失敗でfalseを返し、taskA側は直近値保持のフォールバックへ回る。
static bool imuInit()
{
    i2c_master_bus_config_t busConfig = {};
    busConfig.i2c_port = I2C_NUM_0;
    busConfig.sda_io_num = kImuSdaPin;
    busConfig.scl_io_num = kImuSclPin;
    busConfig.clk_source = I2C_CLK_SRC_DEFAULT;
    busConfig.glitch_ignore_cnt = 7;
    busConfig.flags.enable_internal_pullup = false;

    esp_err_t err = i2c_new_master_bus(&busConfig, &g_imuI2cBus);
    if (err != ESP_OK) {
        ESP_LOGW(kImuTag, "i2c_new_master_bus failed: %s", esp_err_to_name(err));
        return false;
    }

    // バス生成直後は信号線の安定待ちが必要。またブレッドボード配線の浮遊容量分、
    // プローブのタイムアウトは短すぎるとACKを取りこぼす(1-5-3実機切り分けで判明)。
    vTaskDelay(pdMS_TO_TICKS(50));

    uint8_t foundAddr = 0;
    for (uint8_t addr : kImuProbeAddrs) {
        if (i2c_master_probe(g_imuI2cBus, addr, pdMS_TO_TICKS(200)) == ESP_OK) {
            foundAddr = addr;
            break;
        }
    }
    if (foundAddr == 0) {
        ESP_LOGW(kImuTag, "LSM6DSV16X not found on I2C bus (checked 0x%02X/0x%02X, SDA=%d/SCL=%d)",
                 kImuAddrGnd, kImuAddrVcc, static_cast<int>(kImuSdaPin), static_cast<int>(kImuSclPin));
        i2c_del_master_bus(g_imuI2cBus);
        g_imuI2cBus = nullptr;
        return false;
    }

    i2c_device_config_t devConfig = {};
    devConfig.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    devConfig.device_address = foundAddr;
    devConfig.scl_speed_hz = 400000;

    err = i2c_master_bus_add_device(g_imuI2cBus, &devConfig, &g_imuI2cDev);
    if (err != ESP_OK) {
        ESP_LOGW(kImuTag, "i2c_master_bus_add_device failed: %s", esp_err_to_name(err));
        return false;
    }

    uint8_t who = 0;
    if (!imuReadRegs(kImuRegWhoAmI, &who, 1) || who != kImuWhoAmIExpected) {
        ESP_LOGW(kImuTag, "WHO_AM_I mismatch: got 0x%02X, expected 0x%02X", who, kImuWhoAmIExpected);
        return false;
    }

    bool ok = imuWriteReg(kImuRegCtrl1, 0b00001001)
              && imuWriteReg(kImuRegCtrl2, 0b00001001)
              && imuWriteReg(kImuRegCtrl6, 0b00000100)
              && imuWriteReg(kImuRegCtrl8, 0b10000010);
    if (!ok) {
        ESP_LOGW(kImuTag, "init register write failed");
        return false;
    }
    vTaskDelay(pdMS_TO_TICKS(10));

    ESP_LOGI(kImuTag, "LSM6DSV16X initialized (addr=0x%02X, SDA=%d, SCL=%d)",
             foundAddr, static_cast<int>(kImuSdaPin), static_cast<int>(kImuSclPin));
    return true;
}

// OUTX_L_Gから12バイト一括読み取り(ジャイロ3軸+加速度3軸、リトルエンディアン16bit)、
// スケール変換して物理量(dps/G)で返す。読み取り失敗時はfalseを返し、呼び出し側(taskA)は
// 直近値を保持する。
static bool imuReadSensor(float *gx, float *gy, float *gz, float *ax, float *ay, float *az)
{
    uint8_t buf[12];
    if (!imuReadRegs(kImuRegOutXLG, buf, sizeof(buf))) {
        return false;
    }
    int16_t raw[6];
    for (int i = 0; i < 6; i++) {
        raw[i] = static_cast<int16_t>((buf[i * 2 + 1] << 8) | buf[i * 2]);
    }
    *gx = raw[0] * kImuGyroScaleDpsPerLsb;
    *gy = raw[1] * kImuGyroScaleDpsPerLsb;
    *gz = raw[2] * kImuGyroScaleDpsPerLsb;
    *ax = raw[3] * kImuAccelScaleGPerLsb;
    *ay = raw[4] * kImuAccelScaleGPerLsb;
    *az = raw[5] * kImuAccelScaleGPerLsb;
    return true;
}

// 6-5-1: 車載CAN(内蔵TWAI)用TX/RXピン。友人による最終基板配線(logger_v1.net)はまだ
// GPIO番号レベルまで確定していないため、kImuSdaPin/kImuSclPinと同じ考え方で、
// SDMMC/IMU I2Cと衝突しない空きGPIOを暫定値として選定した。実配線確定時に見直す。
// 現時点では外部トランシーバ(MCP2562FD-E/P)が実機に未接続のため、ドライバの
// インストール自体はハードウェア無しでも成功する見込みだが、実際のフレーム受信確認は
// トランシーバ接続後の実機検証が必要(6-5-1時点ではビルド確認までが対象)。
//
// 補足(実装時に判明)：本プロジェクトのESP-IDFはレガシーTWAIドライバ(`driver/twai.h`、
// `twai_receive()`によるポーリング型)が非推奨化されており(`-Werror`によりビルド停止)、
// 新ドライバ(`esp_twai.h`/`esp_twai_onchip.h`)を使う必要があった。新ドライバは
// イベントコールバック方式(`twai_node_register_event_callbacks()`の`on_rx_done`が
// ISRコンテキストで呼ばれ、その中で`twai_node_receive_from_isr()`によりフレームを
// 取り出す)のため、専用の受信タスク(ポーリングループ)は不要になった。
constexpr gpio_num_t kCanTxPin = GPIO_NUM_4;
constexpr gpio_num_t kCanRxPin = GPIO_NUM_5;
static const char *kCanTag = "can_rx";

// 6-5-1: 生CANフレーム(車載CAN)を保持する構造体。デコードはせず、ID・DLC・データバイト列を
// そのまま保持する(Lua側(6-5-2以降)で未デコードのIDも自由にデコードできるようにする方針、
// ARCHITECTURE.md Phase6参照)。
struct CanFrame {
    uint32_t id;
    uint8_t dlc;
    uint8_t data[TWAI_FRAME_MAX_LEN];
    bool extended; // 標準(11bit)/拡張(29bit)ID
};

// 6-5-1: 生CANフレームの共有バッファ。既存のtaskAToTaskCQueueHandle等と同じくFreeRTOS
// キューをリングバッファとして使う。ISRコンテキスト(on_rx_doneコールバック)から
// xQueueSendFromISR()で書き込み、タスクコンテキストからcanRxPop()で読み出す。
// 車載CAN(500kbpsの車両バスを全量受信する側)はTWAIのハードウェア受信フィルタが1系統のみ
// (ESP-IDF sdkconfigのCONFIG_SOC_TWAI_MASK_FILTER_NUM=1で確認済み)という制約があるため、
// フィルタは標準(11bit)ID全域を通す設定にし、ID単位の絞り込みはLua側(6-5-2以降)の
// ソフトウェアフィルタに委ねる。満杯時はxQueueSendFromISRが失敗し最新フレームを1つ捨てる
// (古いフレームを押し出す設計ではない、consumer側の読み出し頻度に委ねる)。
//
// 既知の制約：フィルタが1系統のみのハードウェア制約により、標準(11bit)ID全域を受信対象と
// する設定と拡張(29bit)ID全域を受信対象とする設定を同時には持てない。本プロジェクトの
// 対象車両はOBD2診断通信が標準IDである想定が高いため標準ID側を採用したが、実車で拡張ID
// 主体と判明した場合はここを見直す必要がある。
constexpr size_t kCanRxQueueLen = 64;
static QueueHandle_t g_canRxQueueHandle = nullptr;
static twai_node_handle_t g_canNodeHandle = nullptr;

// on_rx_doneコールバック用の作業バッファ。ISR内で毎回ヒープ確保はできないため
// ファイルスコープの固定バッファを使い回す(この用途では受信を1フレームずつ即座に
// キューへ転記するため、複数フレーム分を同時に保持する必要はない)。
static uint8_t g_canRxIsrBuffer[TWAI_FRAME_MAX_LEN];

// 6-5-1: on_rx_doneイベントコールバック(ISRコンテキストで呼ばれる、ブロッキングAPI呼び出し
// 禁止)。受信済みフレームが無くなるまでtwai_node_receive_from_isr()をループして取り出し、
// デコードせずそのまま共有キューへ転記する。
static bool canOnRxDone(twai_node_handle_t handle, const twai_rx_done_event_data_t *edata, void *user_ctx)
{
    BaseType_t higherPriorityTaskWoken = pdFALSE;

    twai_frame_t rxFrame = {};
    rxFrame.buffer = g_canRxIsrBuffer;
    rxFrame.buffer_len = sizeof(g_canRxIsrBuffer);

    while (twai_node_receive_from_isr(handle, &rxFrame) == ESP_OK) {
        CanFrame frame = {};
        frame.id = rxFrame.header.id;
        frame.dlc = static_cast<uint8_t>(rxFrame.header.dlc);
        frame.extended = rxFrame.header.ide != 0;
        size_t len = twaifd_dlc2len(rxFrame.header.dlc);
        if (len > sizeof(frame.data)) {
            len = sizeof(frame.data); // クラシックTWAI(FD無効)のため実際は最大8バイトのはず
        }
        memcpy(frame.data, g_canRxIsrBuffer, len);
        xQueueSendFromISR(g_canRxQueueHandle, &frame, &higherPriorityTaskWoken);

        // 次のフレーム用にバッファを再設定(twai_node_receive_from_isrがbuffer/buffer_lenを
        // 上書きしている可能性があるため、ループのたびに明示的にリセットする)
        rxFrame.buffer = g_canRxIsrBuffer;
        rxFrame.buffer_len = sizeof(g_canRxIsrBuffer);
    }

    return higherPriorityTaskWoken == pdTRUE;
}

// 車載CANはlisten-onlyのまま維持し送信は行わない方針(ARCHITECTURE.md「送信先の物理バス
// について」参照、純正ECU側への影響を避けるため)。500kbps固定は`hardware_interface_spec.md`
// 「車載CANは500kbpsで流れる車両バス」の記載に基づく。
static bool canRxInit()
{
    twai_onchip_node_config_t nodeConfig = {};
    nodeConfig.io_cfg.tx = kCanTxPin;
    nodeConfig.io_cfg.rx = kCanRxPin;
    nodeConfig.io_cfg.quanta_clk_out = GPIO_NUM_NC;
    nodeConfig.io_cfg.bus_off_indicator = GPIO_NUM_NC;
    nodeConfig.bit_timing.bitrate = 500000;
    nodeConfig.tx_queue_depth = 1; // listen-onlyのため送信キューはほぼ使わないが0不可のため最小値
    nodeConfig.flags.enable_listen_only = 1;

    esp_err_t newErr = twai_new_node_onchip(&nodeConfig, &g_canNodeHandle);
    if (newErr != ESP_OK) {
        ESP_LOGW(kCanTag, "twai_new_node_onchip failed: %s", esp_err_to_name(newErr));
        return false;
    }

    // フィルタは標準ID全域を通す設定(mask=0で「全ビットdon't care」= 全ID一致)。
    // 上記コメントの既知の制約(フィルタ1系統のみ)により拡張IDは対象外。
    twai_mask_filter_config_t filterConfig = {};
    filterConfig.id = 0;
    filterConfig.mask = 0;
    filterConfig.is_ext = false;
    esp_err_t filterErr = twai_node_config_mask_filter(g_canNodeHandle, 0, &filterConfig);
    if (filterErr != ESP_OK) {
        ESP_LOGW(kCanTag, "twai_node_config_mask_filter failed: %s", esp_err_to_name(filterErr));
        twai_node_delete(g_canNodeHandle);
        g_canNodeHandle = nullptr;
        return false;
    }

    twai_event_callbacks_t callbacks = {};
    callbacks.on_rx_done = canOnRxDone;
    esp_err_t cbErr = twai_node_register_event_callbacks(g_canNodeHandle, &callbacks, nullptr);
    if (cbErr != ESP_OK) {
        ESP_LOGW(kCanTag, "twai_node_register_event_callbacks failed: %s", esp_err_to_name(cbErr));
        twai_node_delete(g_canNodeHandle);
        g_canNodeHandle = nullptr;
        return false;
    }

    esp_err_t enableErr = twai_node_enable(g_canNodeHandle);
    if (enableErr != ESP_OK) {
        ESP_LOGW(kCanTag, "twai_node_enable failed: %s", esp_err_to_name(enableErr));
        twai_node_delete(g_canNodeHandle);
        g_canNodeHandle = nullptr;
        return false;
    }
    return true;
}

// 6-5-1: 共有バッファからの読み出しAPI(6-5-2でLuaのrxCAN相当バインディングから呼ばれる
// 想定)。非ブロッキング。フレームが無ければfalseを返す。
[[maybe_unused]] static bool canRxPop(CanFrame *outFrame)
{
    return xQueueReceive(g_canRxQueueHandle, outFrame, 0) == pdPASS;
}

// 1-5-2: taskAで更新される最新IMU値。taskC(RCPストリーム、rcpSendSample)からも
// 参照するためファイルスコープに保持する(既存のg_trackCfg等と同様、taskA/taskC間の
// 排他制御は行わない、既存踏襲)。配線が無い/通信失敗の間は直近値を保持し続け、
// 初期値は静止・水平置き相当(Z軸のみ1G)とする。
// 注意：これらはセンサー座標系の生値(kImuChannels/SensorLogRecordが送出する値)。
// 取り付け角度補正後の車体座標系の値はg_bodyAccel*/g_bodyGyro*(1-5-5)を使うこと。
static float g_imuAccelX = 0.0f;
static float g_imuAccelY = 0.0f;
static float g_imuAccelZ = 1.0f;
static float g_imuGyroX = 0.0f;
static float g_imuGyroY = 0.0f;
static float g_imuGyroZ = 0.0f;

// 1-5-5: 3x3回転行列。センサー座標系→車体座標系への取り付け角度補正に使う。
struct Mat3 {
    float m[3][3];
};

static const Mat3 kIdentityMat3 = {{{1, 0, 0}, {0, 1, 0}, {0, 0, 1}}};

static void mat3Apply(const Mat3 &r, float x, float y, float z, float *xOut, float *yOut, float *zOut)
{
    *xOut = r.m[0][0] * x + r.m[0][1] * y + r.m[0][2] * z;
    *yOut = r.m[1][0] * x + r.m[1][1] * y + r.m[1][2] * z;
    *zOut = r.m[2][0] * x + r.m[2][1] * y + r.m[2][2] * z;
}

// ベクトルaをベクトルbへ回す回転行列をロドリゲスの回転公式で求める(a/bとも非ゼロベクトル、
// 内部で正規化する)。1-5-5の起動時キャリブレーションで、静止時に測定した重力ベクトル(a)を
// 車体座標系の上方向(b=(0,0,1)、水平置き時のg_imuAccelZ初期値+1Gと整合)へ合わせる補正行列を
// 求めるために使う。Pythonでの再実装検算(恒等/90度/180度/45度傾斜の各ケース)で妥当性を確認済み。
static Mat3 mat3RotationBetweenVectors(float ax, float ay, float az, float bx, float by, float bz)
{
    float aNorm = sqrtf(ax * ax + ay * ay + az * az);
    float bNorm = sqrtf(bx * bx + by * by + bz * bz);
    ax /= aNorm; ay /= aNorm; az /= aNorm;
    bx /= bNorm; by /= bNorm; bz /= bNorm;

    float vx = ay * bz - az * by;
    float vy = az * bx - ax * bz;
    float vz = ax * by - ay * bx;
    float c = ax * bx + ay * by + az * bz;
    float s2 = vx * vx + vy * vy + vz * vz;

    if (s2 < 1e-12f) {
        if (c > 0.0f) {
            return kIdentityMat3; // 既に一致している(水平置き)
        }
        // 反平行(180度反転した取り付け)：aに垂直な任意軸を選び180度回転する
        float ux = (fabsf(ax) < 0.9f) ? 1.0f : 0.0f;
        float uy = (fabsf(ax) < 0.9f) ? 0.0f : 1.0f;
        float uz = 0.0f;
        float d = ux * ax + uy * ay + uz * az;
        ux -= d * ax; uy -= d * ay; uz -= d * az;
        float uNorm = sqrtf(ux * ux + uy * uy + uz * uz);
        ux /= uNorm; uy /= uNorm; uz /= uNorm;
        Mat3 r;
        r.m[0][0] = 2 * ux * ux - 1; r.m[0][1] = 2 * ux * uy;     r.m[0][2] = 2 * ux * uz;
        r.m[1][0] = 2 * ux * uy;     r.m[1][1] = 2 * uy * uy - 1; r.m[1][2] = 2 * uy * uz;
        r.m[2][0] = 2 * ux * uz;     r.m[2][1] = 2 * uy * uz;     r.m[2][2] = 2 * uz * uz - 1;
        return r;
    }

    float vSkew[3][3] = {
        {0, -vz, vy},
        {vz, 0, -vx},
        {-vy, vx, 0},
    };
    float k = (1.0f - c) / s2;
    Mat3 r;
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            float vSkewSq = 0.0f;
            for (int n = 0; n < 3; n++) {
                vSkewSq += vSkew[i][n] * vSkew[n][j];
            }
            r.m[i][j] = (i == j ? 1.0f : 0.0f) + vSkew[i][j] + vSkewSq * k;
        }
    }
    return r;
}

// 1-5-5: 起動時自動キャリブレーション(取り付け角度補正)の状態機械。
// 起動直後の一定時間、加速度サンプルを集めて分散を見る。分散が小さければ「静止」と
// みなし、その間の平均加速度ベクトル(センサー座標系での重力方向)から、センサー座標系→
// 車体座標系への回転行列(g_imuAlignRotation)を確定する。取り付け角度を変えた場合は
// 再起動するだけで再キャリブレーションされる(ユーザー方針確認済み、1-5-9参照)。
enum class ImuCalibState : uint8_t { kCollecting, kDone };
static ImuCalibState g_imuCalibState = ImuCalibState::kCollecting;
static Mat3 g_imuAlignRotation = kIdentityMat3;

// taskAの周期(100ms)基準で3秒間サンプルを集める。分散閾値は静止時の想定ノイズ(std〜0.1G
// 程度)を踏まえた仮値で、1-5-6の実機確認時に現物合わせでチューニングする前提(このタスクは
// 配線が無い状態でのロジック実装・ビルド確認までがスコープのため)。
constexpr int kImuCalibSampleCount = 30;
constexpr float kImuCalibVarianceThresholdG2 = 0.01f;
static int g_imuCalibSamples = 0;
static float g_imuCalibSumX = 0.0f, g_imuCalibSumY = 0.0f, g_imuCalibSumZ = 0.0f;
static float g_imuCalibSumSqX = 0.0f, g_imuCalibSumSqY = 0.0f, g_imuCalibSumSqZ = 0.0f;

// 1-5-3実機切り分け時、静止90分間の実測でジャイロZ軸バイアスが0.137dps
// (積分すると約8.2度/分のドリフトに相当)と判明。加速度と同じ静止ウィンドウで
// ジャイロのゼロ点オフセットも同時に求め、車体座標系へ変換する前に差し引く。
static float g_imuGyroBiasSumX = 0.0f, g_imuGyroBiasSumY = 0.0f, g_imuGyroBiasSumZ = 0.0f;
static float g_imuGyroBiasX = 0.0f, g_imuGyroBiasY = 0.0f, g_imuGyroBiasZ = 0.0f;

// サンプルを1つ蓄積し、規定数に達したら分散を判定してg_imuAlignRotationを確定する。
// 分散が閾値を超えていても(振動等で「静止」と確信が持てなくても)規定サンプル数に達した
// 時点の平均値でいったん確定させ、姿勢推定が永久に始まらない状態を避ける(警告ログのみ出す)。
static void imuCalibrationUpdate(float ax, float ay, float az, float gx, float gy, float gz)
{
    if (g_imuCalibState == ImuCalibState::kDone) {
        return;
    }
    g_imuCalibSamples++;
    g_imuCalibSumX += ax; g_imuCalibSumY += ay; g_imuCalibSumZ += az;
    g_imuCalibSumSqX += ax * ax; g_imuCalibSumSqY += ay * ay; g_imuCalibSumSqZ += az * az;
    g_imuGyroBiasSumX += gx; g_imuGyroBiasSumY += gy; g_imuGyroBiasSumZ += gz;

    if (g_imuCalibSamples < kImuCalibSampleCount) {
        return;
    }

    float n = static_cast<float>(g_imuCalibSamples);
    float meanX = g_imuCalibSumX / n, meanY = g_imuCalibSumY / n, meanZ = g_imuCalibSumZ / n;
    float varX = g_imuCalibSumSqX / n - meanX * meanX;
    float varY = g_imuCalibSumSqY / n - meanY * meanY;
    float varZ = g_imuCalibSumSqZ / n - meanZ * meanZ;
    float totalVar = varX + varY + varZ;

    if (totalVar > kImuCalibVarianceThresholdG2) {
        ESP_LOGW(kImuTag, "calibration variance too high (%.4f G^2), using average anyway", totalVar);
    }

    g_imuAlignRotation = mat3RotationBetweenVectors(meanX, meanY, meanZ, 0.0f, 0.0f, 1.0f);
    g_imuGyroBiasX = g_imuGyroBiasSumX / n;
    g_imuGyroBiasY = g_imuGyroBiasSumY / n;
    g_imuGyroBiasZ = g_imuGyroBiasSumZ / n;
    g_imuCalibState = ImuCalibState::kDone;
    ESP_LOGI(kImuTag, "alignment calibration done: gravity=(%.3f,%.3f,%.3f)G", meanX, meanY, meanZ);
    ESP_LOGI(kImuTag, "gyro bias(dps): (%.3f,%.3f,%.3f)", g_imuGyroBiasX, g_imuGyroBiasY, g_imuGyroBiasZ);
}

// 1-5-5で確定した回転補正を適用した後の車体座標系IMU値(taskAで更新)。
// 相補フィルタ(1-5-4)の入力はこちらを使う。g_imuAccel*/g_imuGyro*(センサー座標系の生値、
// SD/RCPログ用)とは別に保持し、既存のログ出力の意味を変えない。
static float g_bodyAccelX = 0.0f, g_bodyAccelY = 0.0f, g_bodyAccelZ = 1.0f;
static float g_bodyGyroX = 0.0f, g_bodyGyroY = 0.0f, g_bodyGyroZ = 0.0f;

// 1-5-4: 相補フィルタによるRoll/Pitch姿勢推定(単位: 度)。taskC(rcpSendSample)からも
// 参照するためファイルスコープに保持する(既存のg_imuAccel*等と同様、排他制御はしない)。
static float g_attitudeRollDeg = 0.0f;
static float g_attitudePitchDeg = 0.0f;
static bool g_attitudeInitialized = false;
static double g_attitudeLastUpdateTimeSec = 0.0;

// alpha(ジャイロ積分を信頼する度合い)は0.95〜0.98を想定した仮値。実機での妥当性確認・
// チューニングは1-5-6/1-5-8の申し送り事項(時定数チューニング手順)で扱う。
constexpr float kAttitudeComplementaryAlpha = 0.96f;

// 加速度3軸(車体座標系、G単位)から重力ベクトルの向きをRoll/Pitch角度(度)に変換する。
// Python再実装検算(静止水平収束・90dps/2秒回転追従・ジャイロバイアスドリフト抑制の
// 各ケース)で妥当性を確認済み。
static void imuAccelToRollPitchDeg(float ax, float ay, float az, float *rollDeg, float *pitchDeg)
{
    *rollDeg = atan2f(ay, az) * (180.0f / static_cast<float>(M_PI));
    *pitchDeg = atan2f(-ax, sqrtf(ay * ay + az * az)) * (180.0f / static_cast<float>(M_PI));
}

// ジャイロ角速度(dps)の積分値を加速度由来の角度で緩やかに補正する相補フィルタ。
// Yaw(ジャイロ積分のみ、磁力計での長期ドリフト補正)は1-5-8で別途対応する。
static void attitudeComplementaryFilterUpdate(float gx, float gy, float ax, float ay, float az, float dtSec)
{
    float accelRollDeg, accelPitchDeg;
    imuAccelToRollPitchDeg(ax, ay, az, &accelRollDeg, &accelPitchDeg);

    g_attitudeRollDeg = kAttitudeComplementaryAlpha * (g_attitudeRollDeg + gx * dtSec)
                         + (1.0f - kAttitudeComplementaryAlpha) * accelRollDeg;
    g_attitudePitchDeg = kAttitudeComplementaryAlpha * (g_attitudePitchDeg + gy * dtSec)
                          + (1.0f - kAttitudeComplementaryAlpha) * accelPitchDeg;
}

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

        // 1-5-2: IMUダミー値(sin波)を実読み取りに置き換え。配線がまだ無い/通信失敗の間は
        // g_imuAccel*/g_imuGyro*の直近値(未接続時は初期値のZ軸1G)を保持し続けるフォールバック。
        if (g_imuAvailable) {
            float gx, gy, gz, ax, ay, az;
            if (imuReadSensor(&gx, &gy, &gz, &ax, &ay, &az)) {
                g_imuAccelX = ax;
                g_imuAccelY = ay;
                g_imuAccelZ = az;
                g_imuGyroX = gx;
                g_imuGyroY = gy;
                g_imuGyroZ = gz;
            }
        }
        rec.accelX = g_imuAccelX;
        rec.accelY = g_imuAccelY;
        rec.accelZ = g_imuAccelZ;
        rec.gyroX = g_imuGyroX;
        rec.gyroY = g_imuGyroY;
        rec.gyroZ = g_imuGyroZ;

        // 1-5-5: 起動時キャリブレーション用に、センサー座標系の生の加速度をサンプル蓄積する
        // (キャリブレーション完了後は内部で何もしない)。完了済みならg_imuAlignRotationで
        // センサー座標系→車体座標系へ変換し、1-5-4の相補フィルタへ渡す。
        imuCalibrationUpdate(g_imuAccelX, g_imuAccelY, g_imuAccelZ,
                             g_imuGyroX, g_imuGyroY, g_imuGyroZ);
        if (g_imuCalibState == ImuCalibState::kDone) {
            mat3Apply(g_imuAlignRotation, g_imuAccelX, g_imuAccelY, g_imuAccelZ,
                      &g_bodyAccelX, &g_bodyAccelY, &g_bodyAccelZ);
            mat3Apply(g_imuAlignRotation,
                      g_imuGyroX - g_imuGyroBiasX, g_imuGyroY - g_imuGyroBiasY, g_imuGyroZ - g_imuGyroBiasZ,
                      &g_bodyGyroX, &g_bodyGyroY, &g_bodyGyroZ);

            if (!g_attitudeInitialized) {
                // 初回はdt不定(前回時刻が無い)のため、積分をスキップして基準時刻だけ記録する
                g_attitudeLastUpdateTimeSec = t;
                g_attitudeInitialized = true;
            } else {
                float dtSec = static_cast<float>(t - g_attitudeLastUpdateTimeSec);
                g_attitudeLastUpdateTimeSec = t;
                attitudeComplementaryFilterUpdate(g_bodyGyroX, g_bodyGyroY,
                                                   g_bodyAccelX, g_bodyAccelY, g_bodyAccelZ, dtSec);
            }
        }

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

// 5-8-3: ジオフェンスの二重発火やピットレーン等がスタート/フィニッシュ付近を通る
// コース形状で、実際には数秒しかない「ラップ」が誤検出されるとベストラップとして
// 恒久的に記録されてしまう(以降のPredTimeが壊れる)ため、明らかに短すぎるラップは
// ベスト更新の対象外とする下限値。市販車のミニサーキットでも1周十数秒はまず無いため、
// 十分安全側の値として10秒を採用。
constexpr double kMinValidLapTimeSec = 10.0;

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

// 5-8-1: このベストラップがどのトラックで記録されたものかを保持する。trackIdだけでなく
// スタート/フィニッシュ座標も合わせて保持するのは、公式アプリ側でtrackIdが未割当(-1)の
// まま手動設定されたトラックが複数ありうる想定のため(trackId単独では別トラック同士を
// 区別できないケースへの保険)。g_trackCfgの対応フィールドと三つ組で比較する。
static int32_t g_bestLapTrackId = -1;
static float g_bestLapStartFinishLat = 0.0f;
static float g_bestLapStartFinishLon = 0.0f;

// ベストラップ統計のNVS永続化。電源断でg_bestLapSamplesが消えると再起動直後は
// 毎回ベストラップ未確定の状態に戻り、予測タイム(PredTime)がしばらく機能しない
// ため、AnalogCfg(1-7-2)/TrackCfg(5-2-2)と同じnvs_set_blob/nvs_get_blobパターン
// で永続化する。g_bestLapSamples全体(kMaxLapSamples=2048要素、最大16KB)を丸ごと
// 保存するとNVSパーティション(デフォルトpartitions_singleapp.csvで24KB)を圧迫する
// ため、実際に使用中のg_bestLapSampleCount分だけを可変長で保存する。
// 保存タイミングはAnalogCfg/TrackCfgと異なりflashCfg(Writeボタン)ではなく、
// ベストラップが更新された瞬間(lapRecorderUpdate内)に自動保存する。ベストラップは
// ユーザーが明示的に設定する値ではなく走行中に自動更新される記録のため、Write操作
// を待たずに確定した時点で保存するのが自然と判断した。
static const char *kBestLapNvsNamespace = "bestlap";
static const char *kBestLapSamplesNvsKey = "samples";
static const char *kBestLapTimeNvsKey = "time";
static const char *kBestLapTrackIdNvsKey = "trackid";
static const char *kBestLapSfLatNvsKey = "sflat";
static const char *kBestLapSfLonNvsKey = "sflon";

static void bestLapLoadFromNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kBestLapNvsNamespace, NVS_READONLY, &handle);
    if (err != ESP_OK) {
        // 初回起動等でnamespace未作成の場合はベストラップ未確定のまま(デフォルト値)
        return;
    }
    size_t required = sizeof(g_bestLapSamples);
    esp_err_t rerr = nvs_get_blob(handle, kBestLapSamplesNvsKey, g_bestLapSamples, &required);
    if (rerr == ESP_OK && required > 0 && (required % sizeof(LapDistanceSample)) == 0) {
        size_t loadedCount = required / sizeof(LapDistanceSample);
        double savedTime = -1.0;
        size_t timeSize = sizeof(savedTime);
        bool haveTime = nvs_get_blob(handle, kBestLapTimeNvsKey, &savedTime, &timeSize) == ESP_OK
            && timeSize == sizeof(savedTime);

        // 5-8-1: このタイミングでは呼び出し元(app_main)がtrackCfgLoadFromNvs()を先に
        // 実行済みのため、g_trackCfgは既に「今回起動時に有効なトラック」を指している。
        // 保存済みベストラップのtrackId(+sf座標)がこれと一致する場合のみ復元する。
        // 不一致(別トラックで記録されたベストラップ)なら復元せず未確定のままにする
        // (ARCHITECTURE.md 7章「ベストラップがトラックと紐付いていない」への対応)。
        // trackid/sfキーが無い場合(本対応より前に保存されたデータ)はデフォルト値
        // (-1, 0, 0)のまま扱われ、g_trackCfgもトラック未設定なら同じデフォルト値
        // なので従来通り復元される。
        int32_t savedTrackId = -1;
        size_t trackIdSize = sizeof(savedTrackId);
        nvs_get_blob(handle, kBestLapTrackIdNvsKey, &savedTrackId, &trackIdSize);
        float savedSfLat = 0.0f;
        size_t sfLatSize = sizeof(savedSfLat);
        nvs_get_blob(handle, kBestLapSfLatNvsKey, &savedSfLat, &sfLatSize);
        float savedSfLon = 0.0f;
        size_t sfLonSize = sizeof(savedSfLon);
        nvs_get_blob(handle, kBestLapSfLonNvsKey, &savedSfLon, &sfLonSize);

        bool matchesCurrentTrack = savedTrackId == g_trackCfg.trackId
            && savedSfLat == g_trackCfg.startFinishLat
            && savedSfLon == g_trackCfg.startFinishLon;

        if (haveTime && matchesCurrentTrack) {
            g_bestLapSampleCount = loadedCount;
            g_bestLapTimeSec = savedTime;
            g_bestLapTrackId = savedTrackId;
            g_bestLapStartFinishLat = savedSfLat;
            g_bestLapStartFinishLon = savedSfLon;
        }
    }
    nvs_close(handle);
}

static void bestLapSaveToNvs()
{
    nvs_handle_t handle;
    esp_err_t err = nvs_open(kBestLapNvsNamespace, NVS_READWRITE, &handle);
    if (err != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_open (RW) failed: %s", esp_err_to_name(err));
        return;
    }
    nvs_set_blob(handle, kBestLapSamplesNvsKey, g_bestLapSamples,
                 g_bestLapSampleCount * sizeof(LapDistanceSample));
    nvs_set_blob(handle, kBestLapTimeNvsKey, &g_bestLapTimeSec, sizeof(g_bestLapTimeSec));
    nvs_set_blob(handle, kBestLapTrackIdNvsKey, &g_bestLapTrackId, sizeof(g_bestLapTrackId));
    nvs_set_blob(handle, kBestLapSfLatNvsKey, &g_bestLapStartFinishLat, sizeof(g_bestLapStartFinishLat));
    nvs_set_blob(handle, kBestLapSfLonNvsKey, &g_bestLapStartFinishLon, sizeof(g_bestLapStartFinishLon));
    esp_err_t cerr = nvs_commit(handle);
    if (cerr != ESP_OK) {
        ESP_LOGW(kRcpTag, "nvs_commit failed: %s", esp_err_to_name(cerr));
    }
    nvs_close(handle);
}

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
        // 5-8-3: 異常に短いラップ(ジオフェンス二重発火・ピットレーン等)はベスト対象外。
        if (lapCompleted && lapTimeSec >= kMinValidLapTimeSec
            && (g_bestLapTimeSec < 0.0 || lapTimeSec < g_bestLapTimeSec)) {
            memcpy(g_bestLapSamples, g_currentLapSamples,
                   sizeof(LapDistanceSample) * g_currentLapSampleCount);
            g_bestLapSampleCount = g_currentLapSampleCount;
            g_bestLapTimeSec = lapTimeSec;
            // 5-8-1: 今回のベストラップがどのトラックのものか記録する。
            g_bestLapTrackId = g_trackCfg.trackId;
            g_bestLapStartFinishLat = g_trackCfg.startFinishLat;
            g_bestLapStartFinishLon = g_trackCfg.startFinishLon;
            bestLapSaveToNvs();
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
                int32_t newTrackId = track["id"].as<int32_t>();
                // 5-8-1: 走行中に別トラックへ切り替わった場合、保持中のベストラップ
                // (前トラック分)をRAM上で破棄する。放置すると新トラックの走行中も
                // 前トラックの軌跡と照合し続け、PredTimeが無意味な値になってしまう
                // (ARCHITECTURE.md 7章の指摘への対応)。NVS上のデータはあえてここでは
                // 書き換えない。flashCfg未実行のままrebootした場合はg_trackCfgも前
                // トラックへ戻るため、bestLapLoadFromNvs()の一致判定により結果的に
                // 正しく復元される。新トラックでのベストラップが確定した時点で
                // (lapRecorderUpdate内)NVSへ上書き保存される。
                if (newTrackId != g_trackCfg.trackId && g_bestLapSampleCount > 0) {
                    g_bestLapSampleCount = 0;
                    g_bestLapTimeSec = -1.0;
                    g_predDeltaValid = false;
                }
                g_trackCfg.trackId = newTrackId;
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

// 5-8-2: ベストラップ統計のリセット手段。ARCHITECTURE.md 7章「ベストラップをクリアする
// 手段が無く、ジオフェンス誤検出等で異常に短い『ラップ』がベスト登録されると再フラッシュ
// でしか復旧できない」への対応。方式は、公式ファームウェア(reference/RaceCapture-Pro_
// firmware/src/logger/loggerApi.c)のRCPコマンド`resetLapStats`(api_reset_lap_stats→
// lapstats_reset(true))と同じコマンド名で実装する(5-8-2申し送りの4候補「RCPコマンド経由・
// シリアルコマンド・setTrackCfg書き込み時の自動破棄・外部CAN経由の物理ボタン」のうち、
// 外部CAN経由は受信(RX)経路自体が未実装(Phase6-3はTXのみがスコープ)で採用不可、
// setTrackCfg時の自動破棄は既に5-8-1で対応済み・今回の「同じトラックのままベストラップ
// だけ手動で消したい」ケースをカバーしない、シリアルコマンドは独自プロトコルになり公式
// アプリ/ツールとの互換性が無いため、いずれも不採用とした)。
//
// ただし公式のlapstats_reset(true)はセッションタイム・ラップカウント・距離等セッション
// 全体を丸ごとリセットする広い操作だが、本プロジェクトで解決したい課題(7章記載)は
// 「異常なベストラップを手動でクリアしたい」のみのため、意図的にスコープを狭め、
// ベストラップ統計(g_bestLapSamples関連)のみをリセットする。コマンド名を公式と揃える
// ことで将来的な外部ツール・スクリプトからの呼び出し互換性は確保しつつ、本ファームウェア
// 独自の判断としてラップカウント進行中のセッション自体には影響を与えない設計とした。
static void resetLapStats()
{
    g_bestLapSampleCount = 0;
    g_bestLapTimeSec = -1.0;
    g_bestLapTrackId = -1;
    g_bestLapStartFinishLat = 0.0f;
    g_bestLapStartFinishLon = 0.0f;
    g_predDeltaValid = false;
    bestLapSaveToNvs();
    printf("[lapRecorder] best lap stats reset via resetLapStats\n");
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

// 6-1-1/6-1-2: RCPシリアル送信・CAN送信(6-3)・Luaバインディング(6-5)の3経路が共有する
// 共通チャンネルテーブル。設計の詳細はtask_phase6_breakdown.md「6-1-1設計結果」を参照。
// value取得は2通り：(a) sample!=nullptr の場合は既存グローバル変数等をラップした関数を
// 毎回呼び出す(既存チャンネルはすべてこちら)。(b) sample==nullptrの場合はvalueを直接
// 読み書きする(Lua addChannel(6-5-3)で動的追加されるチャンネル用、未実装)。
struct ChannelDef {
    const char *nm;
    const char *ut;
    int min, max, prec, sr;

    double (*sample)();
    double value;
};

constexpr size_t kMaxChannels = 64; // 既存23ch + Lua動的追加分の余裕
static ChannelDef g_channelTable[kMaxChannels];
static size_t g_channelCount = 0;
static const char *kChannelTag = "channel";

// テーブルへ新規チャンネルを1件登録する。起動時の初期化専用(実行中の動的追加はLua
// addChannel(6-5-3)実装時に別途扱う)。
static void channelRegister(const char *nm, const char *ut, int min, int max, int prec, int sr,
                             double (*sample)())
{
    if (g_channelCount >= kMaxChannels) {
        ESP_LOGE(kChannelTag, "channel table full, cannot register '%s'", nm);
        return;
    }
    ChannelDef &ch = g_channelTable[g_channelCount++];
    ch.nm = nm;
    ch.ut = ut;
    ch.min = min;
    ch.max = max;
    ch.prec = prec;
    ch.sr = sr;
    ch.sample = sample;
    ch.value = 0.0;
}

// 全sample()持ちチャンネルを1回ずつ呼び出し、valueキャッシュを最新化する。
// rcpSendSample()の冒頭等、値を使う直前に呼ぶ想定。
static void channelTableSync()
{
    for (size_t i = 0; i < g_channelCount; i++) {
        if (g_channelTable[i].sample != nullptr) {
            g_channelTable[i].value = g_channelTable[i].sample();
        }
    }
}

// 名前引き(Lua addChannel/getChannel/setChannel用、6-5-3で使用予定)。チャンネル数が
// 小規模(数十件)な組み込み用途のため線形探索で十分と判断した。
[[maybe_unused]] static int channelFindByName(const char *nm)
{
    for (size_t i = 0; i < g_channelCount; i++) {
        if (strcmp(g_channelTable[i].nm, nm) == 0) {
            return static_cast<int>(i);
        }
    }
    return -1;
}

static const RcpChannelMeta kDummyChannels[] = {
    {"RPM",       "rpm", 0,    10000, 0, 10},
    {"Speed",     "mph", 0,    200,   1, 10},
    {"WaterTemp", "F",   0,    300,   0, 5},
    {"OilPress",  "psi", 0,    150,   1, 5},
    {"Lat",       "deg", -90,  90,    6, 10},
    {"Lon",       "deg", -180, 180,   6, 10},
};

// 5-5-1/6-1-2: Phase5(5-1〜5-4)で実装したラップタイム・予測タイム計算の結果を公式アプリへ
// 表示するためのチャンネル定義。5-1-1設計結果で洗い出した公式lapCfgの9チャンネル分
// (nm/ut/prec/sr)を、`reference/RaceCapture-Pro_firmware`の実機応答例
// (test/json_api_files/getMeta_response.json)に合わせてそのまま採用する。
// Sector/SectorTimeは本プロジェクトでは複数セクター判定を実装しない方針(5-1-1参照)
// のため値は常に0を送るのみになるが、公式アプリ側のUI要素(チャンネル選択リスト等)との
// 互換性を優先し、メタデータ自体は他の8チャンネルと同様に定義しておく。
//
// 6-1-2でg_channelTable(ChannelDef)方式へ移行した。以前は静的配列(kLapChannels)として
// nm/ut/prec/sr等のメタデータのみ保持し、値はrcpSendSample()内に手書きしていたが、
// CAN送信(6-3)・Luaバインディング(6-5)が同じ値を必要とするため、sample関数でラップして
// テーブルへ登録する形に変更した(task_phase6_breakdown.md「6-1-1設計結果」参照)。
static double sampleLapCount()
{
    // g_lapDetector.lapCountはスタート/フィニッシュを外→内へ横切った通算回数=現在
    // 走行中のラップ番号(公式のCurrentLap相当)。公式のLapCountは「完了したラップ数」
    // を指すため、1周も完了していない間は0になるようcurrentLapから1引いてクランプする。
    uint32_t currentLap = g_lapDetector.lapCount;
    return (currentLap > 0) ? static_cast<double>(currentLap - 1) : 0.0;
}

static double sampleLapTime()
{
    return g_lastLapTimeSec / 60.0;
}

static double sampleSector()
{
    return 0.0; // 非対応、常に0
}

static double sampleSectorTime()
{
    return 0.0; // 非対応、常に0
}

static double samplePredTime()
{
    return g_predDeltaValid ? (g_predDeltaSec / 60.0) : 0.0;
}

static double sampleElapsedTime()
{
    // 現在ラップ開始からの経過時間。lapRecorderUpdate内のtimeSinceLapStartと同じ考え方だが、
    // ここは呼び出しごとに自前のtで計算する必要がある。
    double t = static_cast<double>(esp_timer_get_time()) / 1000000.0;
    double elapsedLapTimeSec = t - g_lapDetector.lapStartTimeSec;
    if (elapsedLapTimeSec < 0.0) {
        elapsedLapTimeSec = 0.0;
    }
    return elapsedLapTimeSec / 60.0;
}

static double sampleCurrentLap()
{
    return static_cast<double>(g_lapDetector.lapCount);
}

static double sampleDistance()
{
    constexpr double kMilesPerMeter = 0.000621371;
    return g_currentLapDistanceM * kMilesPerMeter;
}

static double sampleSessionTime()
{
    double t = static_cast<double>(esp_timer_get_time()) / 1000000.0;
    return t / 60.0;
}

// 起動時に一度だけ呼び、kLapChannels(9ch)相当をg_channelTableへ登録する。
// 残り3グループ(kDummyChannels/kImuChannels/kAttitudeChannels)の移行は別タスクで行うため
// (task_phase6_breakdown.md 6-1-2参照)、この時点ではテーブルにはこの9チャンネルのみが並ぶ。
static void channelTableInitLapChannels()
{
    channelRegister("LapCount",    "",    0, 0, 0, 10, sampleLapCount);
    channelRegister("LapTime",     "Min", 0, 0, 4, 10, sampleLapTime);
    channelRegister("Sector",      "",    0, 0, 0, 10, sampleSector);
    channelRegister("SectorTime",  "Min", 0, 0, 4, 10, sampleSectorTime);
    channelRegister("PredTime",    "Min", 0, 0, 4, 5,  samplePredTime);
    channelRegister("ElapsedTime", "Min", 0, 0, 4, 10, sampleElapsedTime);
    channelRegister("CurrentLap",  "",    0, 0, 0, 10, sampleCurrentLap);
    channelRegister("Distance",    "mi",  0, 0, 4, 10, sampleDistance);
    channelRegister("SessionTime", "Min", 0, 0, 4, 10, sampleSessionTime);
}

// 1-5-2: IMU(LSM6DSV16X)6軸分のチャンネル定義。Accel*は`reference/RaceCapture-Pro_firmware`
// の実機応答例(test/json_api_files/getMeta_response.json)のnm/ut/min/max/prec/srをそのまま
// 採用。公式ファームウェアはジャイロ生値ではなくYaw/Pitch/Roll(姿勢角、要姿勢推定)を送る仕様
// だが、ここではGyroX/Y/Zとして生の角速度をそのまま送る(公式互換ではなく独自チャンネル)。
// min/maxはLSM6DSV16Xの初期化設定(CTRL2=0b00001001)で選択したジャイロフルスケール
// (±2000dps)を踏まえた値。
// （1-5-2完了直後の訂正：本プロジェクトは姿勢推定を実装する方針であり、1-5-4/1-5-8で
// 　Roll/Pitch/Yawを別チャンネル(kAttitudeChannels)として追加する。詳細はtask_phase1_
// 　breakdown.md「方針追記」参照）
static const RcpChannelMeta kImuChannels[] = {
    {"AccelX", "G",   -3,    3,    2, 25},
    {"AccelY", "G",   -3,    3,    2, 25},
    {"AccelZ", "G",   -3,    3,    2, 25},
    {"GyroX",  "dps", -2000, 2000, 1, 25},
    {"GyroY",  "dps", -2000, 2000, 1, 25},
    {"GyroZ",  "dps", -2000, 2000, 1, 25},
};

// 1-5-4: 相補フィルタで推定したRoll/Pitch(単位: 度)。Yawは1-5-8(磁力計統合)まで未対応の
// ため、このチャンネル配列には含めない。
static const RcpChannelMeta kAttitudeChannels[] = {
    {"Roll",  "deg", -180, 180, 1, 25},
    {"Pitch", "deg", -90,  90,  1, 25},
};

// 1-3-5: `{"meta":[{"nm":..,"ut":..,"min":..,"max":..,"prec":..,"sr":..}, ...]}`応答。
// アプリ側は一度受け取るとキャッシュするため、以後の再送は不要(HANDOFF.md参照)。
// 5-5-1でkLapChannels(ラップタイム・予測タイム関連)、1-5-2でkImuChannels(IMU6軸)を
// 追加送出するようになった。
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
    // 6-1-2: kLapChannels(9ch)はg_channelTableへ移行済み
    for (size_t i = 0; i < g_channelCount; i++) {
        const ChannelDef &ch = g_channelTable[i];
        JsonObject obj = meta.add<JsonObject>();
        obj["nm"] = ch.nm;
        obj["ut"] = ch.ut;
        obj["min"] = ch.min;
        obj["max"] = ch.max;
        obj["prec"] = ch.prec;
        obj["sr"] = ch.sr;
    }
    for (const auto &ch : kImuChannels) {
        JsonObject obj = meta.add<JsonObject>();
        obj["nm"] = ch.nm;
        obj["ut"] = ch.ut;
        obj["min"] = ch.min;
        obj["max"] = ch.max;
        obj["prec"] = ch.prec;
        obj["sr"] = ch.sr;
    }
    for (const auto &ch : kAttitudeChannels) {
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

    // 6-1-2: kLapChannels(9ch、LapCount〜SessionTime)はg_channelTableへ移行済み。
    // sample()を一括実行して最新値へ同期してから使う(値の計算自体はsampleLapCount()等、
    // 各チャンネルのsample関数側へ移した)。JSON上の型(int/double)は元の実装同様、
    // prec==0のチャンネル(LapCount/Sector/CurrentLap)のみintで送る。
    channelTableSync();
    for (size_t i = 0; i < g_channelCount; i++) {
        const ChannelDef &ch = g_channelTable[i];
        if (ch.prec == 0) {
            d.add(static_cast<int>(ch.value));
        } else {
            d.add(roundToPrec(ch.value, ch.prec));
        }
    }

    // 1-5-2: taskAで更新される最新IMU値(g_imuAccel*/g_imuGyro*)をkImuChannels(6ch)分追加。
    // 配線が無い/通信失敗の間はtaskA側のフォールバックにより直近値(未接続時は初期値の
    // Z軸1G)がそのまま送られる。
    d.add(roundToPrec(g_imuAccelX, 2));                               // AccelX (G)
    d.add(roundToPrec(g_imuAccelY, 2));                               // AccelY (G)
    d.add(roundToPrec(g_imuAccelZ, 2));                               // AccelZ (G)
    d.add(roundToPrec(g_imuGyroX, 1));                                // GyroX (dps)
    d.add(roundToPrec(g_imuGyroY, 1));                                // GyroY (dps)
    d.add(roundToPrec(g_imuGyroZ, 1));                                // GyroZ (dps)

    // 1-5-4: taskAで更新される姿勢推定値(g_attitudeRollDeg/g_attitudePitchDeg)を
    // kAttitudeChannels(2ch)分追加。キャリブレーション未完了(起動直後3秒程度)の間は
    // 初期値0度のまま送られる。
    d.add(roundToPrec(g_attitudeRollDeg, 1));                         // Roll (deg)
    d.add(roundToPrec(g_attitudePitchDeg, 1));                        // Pitch (deg)

    d.add((1 << 23) - 1); // bitmask: kDummyChannels(6ch)+g_channelTable(9ch、旧kLapChannels)+kImuChannels(6ch)+kAttitudeChannels(2ch)全23chとも有効
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
    } else if (strcmp(cmdName, "resetLapStats") == 0) {
        // 5-8-2: 公式RCPコマンド名と一致させる(詳細はresetLapStats()定義部のコメント参照)。
        resetLapStats();
        rcpSendSetCfgAck("resetLapStats");
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
// 元々はCPUを一定時間占有するビジーループでタスクB=最優先の動作を確認していたが、
// このビジーループが最優先(+3)のままRCP処理タスクC(+1)を長時間ブロックし、
// 実機での`getLapCfg`等RCPコマンド応答タイムアウトの原因になっていたと判明(4-4-2調査)。
// 検証目的は1-1-6で既に達成済みのため、以後はCPUを占有しないダミー処理に変更する。
static void taskB(void *pvParameters)
{
    for (;;) {
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

    // 6-1-2: 共通チャンネルテーブルにkLapChannels(9ch)相当を登録する。他の初期化処理より
    // 前でよい(グローバル変数の読み取りはsample()呼び出し時=channelTableSync()時のみ発生)。
    channelTableInitLapChannels();

    // 1-7-1/1-7-2: analog較正設定をデフォルト値で初期化した上で、NVSに保存済みの値があれば読み込む
    analogCfgInitAll();

    // 5-2-2: g_trackCfgは構造体のデフォルトメンバ初期化子で初期値済みのため、
    // AnalogCfgのようなsetDefault呼び出しは不要。NVSに保存済みの値があれば上書きする。
    trackCfgLoadFromNvs();
    // 1-4-7: g_connCfgも同様にデフォルト初期化子(空文字列)済みのため、NVS保存済みの値があれば上書きする。
    connCfgLoadFromNvs();
    // ベストラップ統計もNVS保存済みの値があれば復元する(g_bestLapSampleCount==0のままなら未確定)。
    bestLapLoadFromNvs();

    // 1-5-1/1-5-2: IMU(LSM6DSV16X)初期化。配線・実機は1-5-3で対応するため、現時点では
    // 配線が無くプローブ失敗しても構わない(g_imuAvailable=falseのままtaskAがフォールバックする)。
    g_imuAvailable = imuInit();
    if (!g_imuAvailable) {
        ESP_LOGW(kImuTag, "IMU not available, taskA will keep using fallback values");
    }

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

    // 6-4-2: Luaの自前アロケータ(luaEspAlloc、ESP-IDFヒープAPI)が実際に機能することの
    // 起動時自己診断。専用FreeRTOSタスクでの周期実行は下記luaTask(6-4-3)。
    luaAllocSelfTest();

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

    // 6-5-1: 車載CAN(内蔵TWAI)受信バッファを準備
    g_canRxQueueHandle = xQueueCreate(kCanRxQueueLen, sizeof(CanFrame));

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

    // 6-4-3: Luaスクリプトタスク。既存タスク構成(taskB=+3/taskA=+2/taskC=+1)に一切影響
    // しないよう、アイドルタスクと同じ最低優先度(tskIDLE_PRIORITY)で動かす(時分割によって
    // アイドルタスクと共存はするが、taskA/B/Cを含む他の全タスクより後回しになる)。
    // スタックサイズはLuaパーサがスタックを多く消費する点(公式luaTask.cのコメント参照)を
    // 踏まえ、taskC同様8192バイトとした(実測に基づくチューニングは実機到着後の課題)。
    xTaskCreate(luaTask, "task_lua", 8192, nullptr, tskIDLE_PRIORITY, nullptr);

    // 6-5-1: 車載CAN(内蔵TWAI)受信の初期化。新ドライバはイベントコールバック方式のため
    // 専用タスクは不要(ISRコンテキストで自動的にg_canRxQueueHandleへ積まれる)。
    // トランシーバ未接続の現段階では失敗しうる想定内の状態のため、失敗してもapp_main自体は
    // 継続する(他の機能への影響なし、ハードウェア到着後にリブートすれば正常化する見込み)。
    if (!canRxInit()) {
        ESP_LOGW(kCanTag, "canRxInit failed (no CAN hardware attached?), continuing without CAN RX");
    }
}
