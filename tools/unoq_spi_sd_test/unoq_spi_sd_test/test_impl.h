// UNO Q 試験ファーム（STM32U585側）：内部SPI受信とシールドSDの書き込み速度を測る
// 目的は unoq_video_to_shield_sd_study.md 6章の実測。**ロガーのファームではない**（試験後に元のファームへ戻す）。
//
// ・SPI3スレーブ（PG9=SCK, PG10=MISO, PB5=MOSI, PG12=NSS）で Linux の spidev0.0 から受信し、
//   GPDMA1 ch7 で 64KB の環状バッファ（32KB×2ブロックをLLIで環状につないだもの）へ流し込む。受信データは32bitの連番として検査する
// ・シールドのSD（SPI2: PB13/PB14/PB15, CS=A4）をハードウェアSPI2で駆動し、複数セクタ連続書き込み（CMD25）の速度を測る
// ・書き込み先はFAT32パーティション中央の「FAT上で未使用のクラスタ」だけ。書く前に該当範囲のFATが全部0であることを確認する
//   （既存のファイル・FAT・ディレクトリには一切書き込まない）
//
// Bridge: spitest.stat → 状態JSON / spitest.cmd(文字列) → 0
//   "reset"           受信カウンタを0に戻す
//   "sdinit"          SDを初期化し、空き領域を確保する
//   "bench <MB>"      合成データで連続書き込み速度を測る
//   "e2e <MB>"        SPI3で受信したデータをそのままSDへ書く（受信→SDの通し試験）
// spitest.rd → SDへ書き終えたバイト数（下位32bit）。Linux側のフロー制御（spi_fc.py）が使う
#include <stm32u585xx.h>
#include <zephyr/kernel.h>
// Linux とつなぐ LPUART1 は RTS/CTS フロー制御が前提（ロガー本体 ecologger_v2.ino と同じ初期化。無いと Linux 側が送ってこない）
static void bridgeSerialInit() {
    unsigned key = irq_lock(); uint32_t cr1 = LPUART1->CR1;
    LPUART1->CR1 = cr1 & ~USART_CR1_UE;
    LPUART1->CR3 |= USART_CR3_RTSE | USART_CR3_CTSE;
    LPUART1->CR1 = cr1 | USART_CR1_FIFOEN; irq_unlock(key);
}
#define LOGGER_BRIDGE_SERIAL_INIT_HOOK bridgeSerialInit
#include <Arduino_RouterBridge.h>
#include <Arduino.h>

// ---------------------------------------------------------------- 共有状態
K_MUTEX_DEFINE(lock);
static String queued = "", result = "boot";
static volatile uint32_t completed = 0;

// ---------------------------------------------------------------- SPI3 + GPDMA 受信
// 1ブロックの転送数(BNDT)は16bit＝最大65535なので、32KBブロック4つをLLIで環状につなぐ
#define BLK 32768u
#define NBLK 2u  // 4（128KB）にすると LLEXT ヒープ（128KB）に収まらずスケッチが読み込まれない（2026-10-09 実機）
#define RING (BLK * NBLK)
static uint8_t ring[RING] __aligned(32);
static volatile uint32_t lli[NBLK][3] __aligned(16);  // 各ノード: CBR1, CDAR, CLLR（最後は先頭へ戻る）
static DMA_Channel_TypeDef *const ch = GPDMA1_Channel7;
static volatile uint64_t wrAbs = 0, rdAbs = 0;    // 受信済み・消費済みバイト数（通算）
static uint32_t lastMod = 0;
static volatile uint32_t ovr = 0, wordErr = 0, words = 0, lapped = 0;
static uint32_t expect = 0; static bool synced = false;
static volatile uint32_t firstRxMs = 0, lastRxMs = 0;
static volatile bool e2eActive = false;

static void gpioAF(GPIO_TypeDef *g, int pin, int af, int speed) {
    g->MODER = (g->MODER & ~(3u << (pin * 2))) | (2u << (pin * 2));
    g->OSPEEDR = (g->OSPEEDR & ~(3u << (pin * 2))) | ((uint32_t)speed << (pin * 2));
    g->PUPDR &= ~(3u << (pin * 2));
    volatile uint32_t *afr = &g->AFR[pin >> 3];
    *afr = (*afr & ~(15u << ((pin & 7) * 4))) | ((uint32_t)af << ((pin & 7) * 4));
}

static void spi3Start() {
    RCC->AHB1ENR |= RCC_AHB1ENR_GPDMA1EN;
    RCC->APB3ENR |= RCC_APB3ENR_SPI3EN;
    RCC->AHB2ENR1 |= RCC_AHB2ENR1_GPIOBEN | RCC_AHB2ENR1_GPIOGEN;
    (void)RCC->APB3ENR;
    gpioAF(GPIOG, 9, 6, 2); gpioAF(GPIOG, 10, 6, 2); gpioAF(GPIOB, 5, 6, 2); gpioAF(GPIOG, 12, 6, 2);
    GPIOG->PUPDR |= 1u << (12 * 2);  // NSS は Linux が離している間はHigh

    // GPDMA1 ch7: SPI3_RX(要求10) → ring、ブロック = RING バイト、LLIで自分自身へ戻して永久に回す
    ch->CCR = DMA_CCR_RESET; while (ch->CCR & DMA_CCR_EN) {}
    ch->CFCR = 0x7F00;
    ch->CTR1 = DMA_CTR1_DINC;          // 送り元(RXDR)は8bit固定、送り先は8bitで増分
    ch->CTR2 = 10u << DMA_CTR2_REQSEL_Pos;
    ch->CBR1 = BLK;
    ch->CSAR = (uint32_t)&SPI3->RXDR;
    ch->CDAR = (uint32_t)ring;
    // ノード i は「ブロック i+1 の設定」を持つ。現在ブロック0を実行中なので CLLR はノード0（＝ブロック1）を指す
    for (uint32_t i = 0; i < NBLK; i++) {
        uint32_t nb = (i + 1) % NBLK, next = (uint32_t)lli[(i + 1) % NBLK];
        lli[i][0] = BLK; lli[i][1] = (uint32_t)ring + nb * BLK;
        lli[i][2] = DMA_CLLR_UB1 | DMA_CLLR_UDA | DMA_CLLR_ULL | (next & 0xFFFC);
    }
    if (((uint32_t)lli[0] ^ (uint32_t)lli[NBLK - 1]) & 0xFFFF0000) { result = "LLI_CROSSES_64K"; return; }
    ch->CLBAR = (uint32_t)lli[0] & 0xFFFF0000;
    ch->CLLR = DMA_CLLR_UB1 | DMA_CLLR_UDA | DMA_CLLR_ULL | ((uint32_t)lli[0] & 0xFFFC);
    ch->CCR = (2u << DMA_CCR_PRIO_Pos) | DMA_CCR_EN;

    // SPI3 スレーブ受信のみ、8bit、モード0、NSSはハードウェア
    SPI3->CR1 = 0;
    SPI3->CFG1 = (7u << SPI_CFG1_DSIZE_Pos) | SPI_CFG1_RXDMAEN;
    SPI3->CFG2 = (2u << SPI_CFG2_COMM_Pos);  // MASTER=0（スレーブ）、COMM=受信専用、SSM=0
    SPI3->CR2 = 0;                           // TSIZE=0：終わりなく受ける
    SPI3->IFCR = 0xFFFF;
    SPI3->CR1 = SPI_CR1_SPE;
    lastMod = 0; wrAbs = rdAbs = 0;
}

// DMAの進み具合から受信済みバイト数（通算）を更新する。1周（約26ms@2.5MB/s）より短い間隔で呼ぶこと
static uint64_t pollWr() {
    uint32_t mod = (ch->CDAR - (uint32_t)ring) % RING;  // 送り先アドレス＝次に書く位置
    uint64_t w = wrAbs;
    if (mod < lastMod) w += RING;
    w = (w & ~(uint64_t)(RING - 1)) | mod;
    if (w < wrAbs) w += RING;
    lastMod = mod;
    if (w != wrAbs) { lastRxMs = millis(); if (!firstRxMs) firstRxMs = lastRxMs; }
    wrAbs = w;
    if (SPI3->SR & SPI_SR_OVR) { ovr++; SPI3->IFCR = SPI_IFCR_OVRC; }
    return w;
}

// 受信データを32bit連番として検査する（e2e中はSD書き込み側が消費する）
static void checkUpTo(uint64_t w) {
    if (w - rdAbs > RING) { lapped++; rdAbs = w - RING / 2; rdAbs &= ~3ull; synced = false; }
    while (w - rdAbs >= 4) {
        uint32_t off = rdAbs % RING, v;
        memcpy(&v, ring + off, 4);
        if (!synced) { expect = v; synced = true; }
        if (v != expect) { wordErr++; expect = v; }
        expect++; words++; rdAbs += 4;
    }
}

K_THREAD_STACK_DEFINE(rxStack, 2048);
static struct k_thread rxThread;
static void rxWorker(void *, void *, void *) {
    while (true) {
        if (!e2eActive) checkUpTo(pollWr());  // 通し試験中は書き込み側が pollWr を呼ぶ
        k_usleep(500);
    }
}

// ---------------------------------------------------------------- SD（SPI2）
// 初期化だけはロガー本体と同じくGPIOを直接叩く低速モードで行い、その後ハードウェアSPI2へ切り替える
#define CS_PIN A4
static bool sdHC = false, sdOk = false;
static uint32_t partStart = 0, partSize = 0, regionLba = 0, regionSectors = 0, regionNext = 0;
static uint32_t spi2Hz = 0;
static uint8_t blk[512] __aligned(4);

static uint8_t bb(uint8_t v) {  // ビットバンギング（PB15=MOSI, PB13=SCK, PB14=MISO）
    uint8_t r = 0;
    for (int i = 7; i >= 0; i--) {
        GPIOB->BSRR = (v & (1 << i)) ? (1u << 15) : (1u << 31); k_busy_wait(2);
        GPIOB->BSRR = 1u << 13; k_busy_wait(2);
        r = (r << 1) | ((GPIOB->IDR >> 14) & 1);
        GPIOB->BSRR = 1u << 29;
    }
    return r;
}
static int bbCmd(uint8_t cmd, uint32_t arg, uint8_t crc) {
    digitalWrite(CS_PIN, HIGH); bb(0xFF); digitalWrite(CS_PIN, LOW);
    bb(0x40 | cmd); for (int i = 3; i >= 0; i--) bb(arg >> (8 * i)); bb(crc);
    for (int i = 0; i < 32; i++) { uint8_t r = bb(0xFF); if (!(r & 0x80)) return r; }
    return 255;
}
static void bbDone() { digitalWrite(CS_PIN, HIGH); bb(0xFF); }

// ハードウェアSPI2：32bit（4バイト）単位で全二重に流す。TXDRへの32bit書き込みで8bitフレーム4個を詰める
static uint8_t rxq[4]; static int rxn = 0;
static volatile uint32_t spiTimeouts = 0;
static void spi2Words(const uint32_t *tx, uint32_t *rx, int n) {
    int sent = 0, got = 0;
    uint32_t t0 = k_cycle_get_32(), lim = CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC / 10;  // 100ms で諦める（SPI2が止まっても固まらない）
    while (got < n) {
        if (k_cycle_get_32() - t0 > lim) { spiTimeouts++; return; }
        if (sent < n && sent - got < 3 && (SPI2->SR & SPI_SR_TXP)) *(volatile uint32_t *)&SPI2->TXDR = tx ? tx[sent++] : (sent++, 0xFFFFFFFFu);
        if (SPI2->SR & SPI_SR_RXP) { uint32_t v = *(volatile uint32_t *)&SPI2->RXDR; if (rx) rx[got] = v; got++; }
    }
}
static uint8_t hb() {  // 1バイト受け取る（足りなければ0xFFを4バイト送って補充）
    if (!rxn) { uint32_t v; spi2Words(nullptr, &v, 1); memcpy(rxq, &v, 4); rxn = 4; }
    uint8_t b = rxq[4 - rxn]; rxn--; return b;
}
static void hbFlush() { rxn = 0; }
static int hCmd(uint8_t cmd, uint32_t arg) {
    digitalWrite(CS_PIN, LOW); hbFlush();
    uint32_t w[2]; uint8_t *b = (uint8_t *)w;
    b[0] = 0xFF; b[1] = 0x40 | cmd; b[2] = arg >> 24; b[3] = arg >> 16; b[4] = arg >> 8; b[5] = arg; b[6] = 0x01; b[7] = 0xFF;
    uint32_t back[2]; spi2Words(w, back, 2);
    uint8_t first = ((uint8_t *)back)[7];  // CRC直後の1バイト目に応答が来ることがある
    if (!(first & 0x80)) return first;
    for (int i = 0; i < 64; i++) { uint8_t r = hb(); if (!(r & 0x80)) return r; }
    return 255;
}
static void hDone() { digitalWrite(CS_PIN, HIGH); spi2Words(nullptr, nullptr, 1); hbFlush(); }
static bool hRead(uint32_t lba, uint8_t *buf) {
    bool ok = false;
    if (hCmd(17, sdHC ? lba : lba * 512) == 0) {
        uint32_t end = millis() + 500; uint8_t t;
        do { t = hb(); } while (t == 0xFF && millis() < end);
        if (t == 0xFE) { for (int i = 0; i < 512; i++) buf[i] = hb(); hb(); hb(); ok = true; }
    }
    hDone(); return ok;
}
static bool waitReady(uint32_t ms) {  // ビジー（0x00）が明けて0xFFが返るまで待つ
    uint32_t end = millis() + ms;
    while (millis() < end) { uint32_t v; spi2Words(nullptr, &v, 1); if ((v >> 24) == 0xFF) { hbFlush(); return true; } k_yield(); }  // 待つ間はBridgeへ譲る
    return false;
}

static void spi2Hw() {
    RCC->APB1ENR1 |= RCC_APB1ENR1_SPI2EN; (void)RCC->APB1ENR1;
    gpioAF(GPIOB, 13, 5, 3); gpioAF(GPIOB, 14, 5, 3); gpioAF(GPIOB, 15, 5, 3);
    // カーネルクロック（既定PCLK1）を 8 分周。PCLK1=160MHz なら 20MHz
    uint32_t hclk = CONFIG_SYS_CLOCK_HW_CYCLES_PER_SEC, pre = (RCC->CFGR2 >> RCC_CFGR2_PPRE1_Pos) & 7;
    uint32_t pclk1 = pre < 4 ? hclk : hclk >> (pre - 3);
    uint32_t mbr = 0; while ((pclk1 >> (mbr + 1)) > 20000000u && mbr < 7) mbr++;
    spi2Hz = pclk1 >> (mbr + 1);
    // SSI=1 を先に立てる。SSM=1・SSI=0 のままマスターにするとモードフォルト（MODF）でSPEとMASTERが自動で落ちる（2026-10-09 実機）
    SPI2->CR1 = SPI_CR1_SSI;
    SPI2->IFCR = 0xFFFF;
    SPI2->CFG1 = (mbr << SPI_CFG1_MBR_Pos) | (7u << SPI_CFG1_DSIZE_Pos) | (3u << SPI_CFG1_FTHLV_Pos);
    SPI2->CFG2 = SPI_CFG2_MASTER | SPI_CFG2_SSM | SPI_CFG2_AFCNTR;
    SPI2->CR2 = 0;
    SPI2->CR1 = SPI_CR1_SSI | SPI_CR1_SPE;
    SPI2->CR1 = SPI_CR1_SSI | SPI_CR1_SPE | SPI_CR1_CSTART;
}

static uint32_t u32(const uint8_t *p) { return p[0] | p[1] << 8 | p[2] << 16 | (uint32_t)p[3] << 24; }
static uint16_t u16(const uint8_t *p) { return p[0] | p[1] << 8; }

static void sdInitCmd() {
    sdOk = false; regionSectors = 0;
    // 他の SPI2 デバイス（CAN2 = D10、LEDラッチ = D7）を非選択に固定
    pinMode(D10, OUTPUT); digitalWrite(D10, HIGH); pinMode(CS_PIN, OUTPUT); digitalWrite(CS_PIN, HIGH);
    RCC->AHB2ENR1 |= RCC_AHB2ENR1_GPIOBEN;
    GPIOB->MODER = (GPIOB->MODER & ~((3u << 26) | (3u << 28) | (3u << 30))) | (1u << 26) | (1u << 30);  // PB13,15出力 / PB14入力
    for (int i = 0; i < 12; i++) bb(0xFF);
    int r0 = bbCmd(0, 0, 0x95); bbDone();
    int r8 = bbCmd(8, 0x1AA, 0x87); uint8_t r7[4]; for (int i = 0; i < 4; i++) r7[i] = bb(0xFF); bbDone();
    int r = 255; uint32_t end = millis() + 3000;
    if (r0 == 1) do { bbCmd(55, 0, 1); bbDone(); r = bbCmd(41, 0x40000000, 1); bbDone(); if (!r) break; delay(10); } while (millis() < end);
    if (r) { result = "SD_INIT_FAIL r0=" + String(r0) + " r8=" + String(r8); return; }
    bbCmd(58, 0, 1); uint8_t ocr[4]; for (int i = 0; i < 4; i++) ocr[i] = bb(0xFF); bbDone();
    sdHC = ocr[0] & 0x40; (void)r7;
    spi2Hw();
    // MBR → FAT32 BPB → パーティション中央の未使用クラスタを確保
    if (!hRead(0, blk) || blk[510] != 0x55 || blk[511] != 0xAA) { result = "MBR_READ_FAIL"; return; }
    uint8_t type = blk[446 + 4]; partStart = u32(blk + 446 + 8); partSize = u32(blk + 446 + 12);
    if (type != 0x0B && type != 0x0C) { result = "NOT_FAT32 type=" + String(type); return; }
    if (!hRead(partStart, blk) || u16(blk + 11) != 512) { result = "BPB_READ_FAIL"; return; }
    uint32_t spc = blk[13], resv = u16(blk + 14), nfat = blk[16], fatSz = u32(blk + 36);
    uint32_t fatBase = partStart + resv, dataBase = fatBase + nfat * fatSz;
    uint32_t clusters = (partStart + partSize - dataBase) / spc;
    uint32_t want = (uint32_t)((512ull * 1024 * 1024) / (spc * 512));  // 512MB分
    // クラスタ番号 cn0 から want 個。cn0 はFAT1セクタ（128エントリ）の境目にそろえ、そのFATセクタを丸ごと検査する
    uint32_t cn0 = (clusters / 2) & ~127u;
    if (cn0 < 128 || cn0 + want > clusters + 2) { result = "SD_TOO_SMALL"; return; }
    for (uint32_t s = 0; s < (want + 127) / 128; s++) {
        if (!hRead(fatBase + cn0 / 128 + s, blk)) { result = "FAT_READ_FAIL"; return; }
        for (int i = 0; i < 512; i += 4) if (u32(blk + i) & 0x0FFFFFFF) { result = "REGION_NOT_FREE"; return; }
    }
    regionLba = dataBase + (cn0 - 2) * spc;
    regionSectors = want * spc; regionNext = regionLba;
    sdOk = true;
    char t[200];
    snprintf(t, sizeof t, "SD ok hc=%d spi2=%luHz part=%lu+%lu spc=%lu region=%lu..%lu(%luMB free in FAT)",
             sdHC, (unsigned long)spi2Hz, (unsigned long)partStart, (unsigned long)partSize, (unsigned long)spc,
             (unsigned long)regionLba, (unsigned long)(regionLba + regionSectors), (unsigned long)(regionSectors / 2048));
    result = t;
}

// 連続書き込み：CMD25 で開始し、src(i) が返す512バイトを nBlk 個書く
static uint32_t wrMaxBusyUs = 0, wrBlocks = 0, wrErr = 0;
static bool writeBlock(const uint8_t *data) {
    uint32_t pre = 0xFCFFFFFFu;  // FF FF FF FC（データトークン）
    spi2Words(&pre, nullptr, 1);
    spi2Words((const uint32_t *)data, nullptr, 128);
    uint32_t tail = 0xFFFFFFFFu, back;  // CRC(2B・無視される) + FF FF：3バイト目にデータ応答トークン
    spi2Words(&tail, &back, 1);
    uint8_t tok = (back >> 16) & 0xFF;
    if ((tok & 0x1F) != 0x05) { uint8_t t3 = back >> 24; if ((t3 & 0x1F) != 0x05) { wrErr++; return false; } }
    uint32_t t0 = micros();
    if (!waitReady(500)) { wrErr++; return false; }
    uint32_t us = micros() - t0; if (us > wrMaxBusyUs) wrMaxBusyUs = us;
    wrBlocks++; return true;
}
static bool beginMulti(uint32_t lba) { return hCmd(25, sdHC ? lba : lba * 512) == 0; }
static void endMulti() { uint32_t stop = 0xFFFFFDFFu; spi2Words(&stop, nullptr, 1); waitReady(1000); hDone(); }

static void benchCmd(uint32_t mb) {
    if (!sdOk) { result = "SD_NOT_READY"; return; }
    uint32_t n = mb * 2048; if (regionNext + n > regionLba + regionSectors) regionNext = regionLba;
    for (int i = 0; i < 512; i++) blk[i] = i;
    wrMaxBusyUs = wrBlocks = wrErr = 0;
    uint32_t t0 = millis();
    if (!beginMulti(regionNext)) { result = "CMD25_FAIL"; hDone(); return; }
    for (uint32_t i = 0; i < n; i++) { memcpy(blk, &i, 4); if (!writeBlock(blk)) break; }
    endMulti();
    uint32_t ms = millis() - t0; regionNext += n;
    char t[160];
    snprintf(t, sizeof t, "bench %luMB in %lums = %lu KB/s, blocks=%lu err=%lu max_busy=%luus",
             (unsigned long)mb, (unsigned long)ms, (unsigned long)(wrBlocks * 512ull / (ms ? ms : 1)),
             (unsigned long)wrBlocks, (unsigned long)wrErr, (unsigned long)wrMaxBusyUs);
    result = t;
}

// 通し試験：SPI3で受けたデータを512バイトずつSDへ。最初の受信を30秒待ち、受信が途切れて2秒で終了
static uint32_t e2eBlocks = 0, e2eGaps = 0, e2eLostBlocks = 0;
static void e2eCmd(uint32_t mb) {
    if (!sdOk) { result = "SD_NOT_READY"; return; }
    uint32_t n = mb * 2048; if (regionNext + n > regionLba + regionSectors) regionNext = regionLba;
    wrMaxBusyUs = wrBlocks = wrErr = 0; e2eBlocks = e2eGaps = e2eLostBlocks = 0;
    uint32_t lapped0 = lapped, nextWord = 0; bool haveWord = false;
    uint32_t busyHist[4] = {0, 0, 0, 0};  // SDのビジー時間の分布：<5ms, 5-20ms, 20-50ms, 50ms以上
    e2eActive = true; k_msleep(2);       // 受信スレッドが pollWr から手を離すのを待つ
    rdAbs = (pollWr() + 511) & ~511ull;  // 次のブロック境界から
    uint32_t idleSince = millis(), t0 = 0, tLast = 0;
    uint64_t maxLag = 0;
    if (!beginMulti(regionNext)) { e2eActive = false; result = "CMD25_FAIL"; hDone(); return; }
    while (e2eBlocks < n) {
        uint64_t w = pollWr();
        if (w - rdAbs > RING) { lapped++; rdAbs = (w - RING / 2) & ~511ull; }
        if (w - rdAbs > maxLag) maxLag = w - rdAbs;
        if (w - rdAbs >= 512) {
            if (!t0) t0 = millis();
            // 送り手の連番はブロック（128語）ごとに128進む。飛んでいたらバッファを追い越された（＝欠落）
            uint32_t w0; memcpy(&w0, ring + rdAbs % RING, 4);
            if (haveWord && w0 != nextWord) { e2eGaps++; e2eLostBlocks += (w0 - nextWord) / 128; }
            nextWord = w0 + 128; haveWord = true;
            uint32_t mb0 = wrMaxBusyUs; wrMaxBusyUs = 0;
            if (!writeBlock(ring + rdAbs % RING)) break;
            uint32_t b = wrMaxBusyUs; wrMaxBusyUs = b > mb0 ? b : mb0;
            busyHist[b < 5000 ? 0 : b < 20000 ? 1 : b < 50000 ? 2 : 3]++;
            rdAbs += 512; e2eBlocks++; idleSince = tLast = millis();
        } else if (millis() - idleSince > (t0 ? 2000u : 30000u)) break;  // 最初のデータは30秒待つ。始まった後は2秒途切れたら終了
        else k_usleep(100);
    }
    endMulti(); e2eActive = false; regionNext += e2eBlocks;
    uint32_t ms = tLast - t0;
    char t[300];
    snprintf(t, sizeof t, "e2e %lu blocks (%lu KB) in %lums = %lu KB/s, gaps=%lu lost=%luKB overflow=%lu max_lag=%luB err=%lu max_busy=%luus busy_hist(<5/<20/<50/>=50ms)=%lu/%lu/%lu/%lu",
             (unsigned long)e2eBlocks, (unsigned long)(e2eBlocks / 2), (unsigned long)ms,
             (unsigned long)(e2eBlocks * 512ull / (ms ? ms : 1)), (unsigned long)e2eGaps, (unsigned long)(e2eLostBlocks / 2),
             (unsigned long)(lapped - lapped0), (unsigned long)maxLag, (unsigned long)wrErr, (unsigned long)wrMaxBusyUs,
             (unsigned long)busyHist[0], (unsigned long)busyHist[1], (unsigned long)busyHist[2], (unsigned long)busyHist[3]);
    result = t;
}

// ---------------------------------------------------------------- Bridge
static String stat() {
    char t[640];
    snprintf(t, sizeof t,
             "{\"rx_bytes\":%llu,\"words\":%lu,\"word_err\":%lu,\"ovr\":%lu,\"lapped\":%lu,\"rx_ms\":%lu,"
             "\"sr\":%lu,\"dma_csr\":%lu,\"spi2_sr\":%lu,\"spi2_to\":%lu,\"completed\":%lu,\"e2e\":%d,\"result\":\"%s\"}",
             (unsigned long long)wrAbs, (unsigned long)words, (unsigned long)wordErr, (unsigned long)ovr,
             (unsigned long)lapped, (unsigned long)(lastRxMs - firstRxMs), (unsigned long)SPI3->SR,
             (unsigned long)ch->CSR, (unsigned long)SPI2->SR, (unsigned long)spiTimeouts, (unsigned long)completed, e2eActive, result.c_str());
    return String(t);
}
// フロー制御用：消費済み（SDへ書き終えた）バイト数の下位32bit。Linuxは「送った量 − これ」が受け皿（RING）を超えないように送る
static int consumed() { return (int)(uint32_t)rdAbs; }
static int submit(String c) { k_mutex_lock(&lock, K_FOREVER); queued = c; k_mutex_unlock(&lock); return 0; }

K_THREAD_STACK_DEFINE(bridgeStack, 4096);
static struct k_thread bridgeThread;
static void bridgeWorker(void *, void *, void *) {
    Bridge.begin(921600);
    // 書き込み直後はルーターとの最初のやり取りを取りこぼすことがあるので、登録が通るまでやり直す
    bool a = false, b = false, c = false;
    while (!(a && b && c)) {
        if (!a) a = Bridge.provide("spitest.stat", stat);
        if (!b) b = Bridge.provide("spitest.cmd", submit);
        if (!c) c = Bridge.provide("spitest.rd", consumed);
        if (!(a && b && c)) k_msleep(1000);
    }
    result = "bridge ready";
}

void setup() {
    // ロガー本体と同じ待機時の出力状態（LTE・CAN・LED等を触らない）
    pinMode(D10, OUTPUT); digitalWrite(D10, HIGH);
    pinMode(A4, OUTPUT); digitalWrite(A4, HIGH);
    spi3Start();
    k_thread_create(&rxThread, rxStack, K_THREAD_STACK_SIZEOF(rxStack), rxWorker, nullptr, nullptr, nullptr, 2, 0, K_NO_WAIT);
    k_thread_create(&bridgeThread, bridgeStack, K_THREAD_STACK_SIZEOF(bridgeStack), bridgeWorker, nullptr, nullptr, nullptr, 5, 0, K_NO_WAIT);
}

void loop() {
    String c;
    k_mutex_lock(&lock, K_FOREVER); c = queued; queued = ""; k_mutex_unlock(&lock);
    if (c.length()) {
        if (c == "reset") { wordErr = words = ovr = lapped = 0; firstRxMs = lastRxMs = 0; synced = false; result = "reset"; }
        else if (c == "sdinit") sdInitCmd();
        else if (c.startsWith("bench ")) benchCmd(strtoul(c.c_str() + 6, nullptr, 10));
        else if (c.startsWith("e2e ")) e2eCmd(strtoul(c.c_str() + 4, nullptr, 10));
        else result = "unsupported";
        completed++;
    }
    delay(5);
}
