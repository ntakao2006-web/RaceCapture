// OBDハーネス導通ライブ確認プローブ (Arduino Nano, 受動)
//
// 配線:
//   Nano A0 -> OBD 6番  (CANH のはず)
//   Nano A1 -> OBD 14番 (CANL のはず)
//   Nano GND -> OBD 4/5番 (MCP2562FDのGNDと共通)
//   ※Nanoからは何も駆動しない。measure only。
//
// ESP32側 can_selftest を「連続送信モード」で走らせた状態で計測する。
// 正常なら:
//   CANH(A0): 約2.5Vを中心に、ドミナントで上(~3.5V)へ振れる
//   CANL(A1): 約2.5Vを中心に、ドミナントで下(~1.5V)へ振れる
// 6番と14番が入れ替わっていれば、振れる向きが逆になる。
// まったく振れなければ 断線 or GND非共通 or ESP32が送信していない。

#include <Arduino.h>

const uint8_t PIN_CANH = A0;
const uint8_t PIN_CANL = A1;

static inline long to_mv(int raw) { return (long)raw * 5000L / 1023L; }

void setup() {
  Serial.begin(115200);
  analogReference(DEFAULT); // AVcc = 5V 基準
  delay(300);
  Serial.println();
  Serial.println(F("=== OBD harness live probe (passive, Nano) ==="));
  Serial.println(F("A0=OBD6(CANH?)  A1=OBD14(CANL?)  GND=OBD4/5"));
  Serial.println(F("ESP32(can_selftest)を連続送信モードにしてから読んでください。"));
  Serial.println(F("正常: CANH=中心~2.5Vで上へ / CANL=中心~2.5Vで下へ"));
  Serial.println();
}

void loop() {
  const uint16_t N = 3500;
  int hMin = 1023, hMax = 0, lMin = 1023, lMax = 0;
  long hSum = 0, lSum = 0;

  for (uint16_t i = 0; i < N; i++) {
    int h = analogRead(PIN_CANH);
    int l = analogRead(PIN_CANL);
    if (h < hMin) hMin = h;
    if (h > hMax) hMax = h;
    if (l < lMin) lMin = l;
    if (l > lMax) lMax = l;
    hSum += h;
    lSum += l;
  }
  long hAvg = hSum / N, lAvg = lSum / N;

  long hMinV = to_mv(hMin), hAvgV = to_mv(hAvg), hMaxV = to_mv(hMax);
  long lMinV = to_mv(lMin), lAvgV = to_mv(lAvg), lMaxV = to_mv(lMax);

  Serial.print(F("CANH(A0) min=")); Serial.print(hMinV);
  Serial.print(F(" avg="));         Serial.print(hAvgV);
  Serial.print(F(" max="));         Serial.print(hMaxV);
  Serial.print(F("mV | CANL(A1) min=")); Serial.print(lMinV);
  Serial.print(F(" avg="));         Serial.print(lAvgV);
  Serial.print(F(" max="));         Serial.print(lMaxV);
  Serial.println(F("mV"));

  // レセッシブ待機は両線とも約2.5V。バスが busy だと平均はドミナント側に寄るので
  // 平均ではなく「待機電圧に近い端(min or max)がどちら向きに離れるか」で判定する。
  //   CANH: 待機≒min付近、ドミナントで上へ  -> max が min から十分上
  //   CANL: 待機≒max付近、ドミナントで下へ  -> min が max から十分下
  const long IDLE_LO = 2000, IDLE_HI = 2950;   // レセッシブ待機とみなす窓 (mV)
  const long SW = 500;                         // 有効な振れ幅 (mV)

  bool aRises = (hMinV >= IDLE_LO && hMinV <= IDLE_HI) && (hMaxV - hMinV > SW);
  bool aFalls = (hMaxV >= IDLE_LO && hMaxV <= IDLE_HI) && (hMaxV - hMinV > SW);
  bool bRises = (lMinV >= IDLE_LO && lMinV <= IDLE_HI) && (lMaxV - lMinV > SW);
  bool bFalls = (lMaxV >= IDLE_LO && lMaxV <= IDLE_HI) && (lMaxV - lMinV > SW);
  bool aFlat  = (hMaxV - hMinV) < 150;
  bool bFlat  = (lMaxV - lMinV) < 150;

  if (aRises && bFalls) {
    Serial.println(F("  => OK: A0(OBD6)=CANH が上へ / A1(OBD14)=CANL が下へ。配線・極性 正常。"));
  } else if (aFalls && bRises) {
    Serial.println(F("  => SWAP: A0 が下へ / A1 が上へ。OBD 6番と14番が入れ替わっている。"));
  } else if (aFlat || bFlat) {
    Serial.print(F("  => CHECK: "));
    if (aFlat) Serial.print(F("A0 振れなし(断線/GND落ち疑い) "));
    if (bFlat) Serial.print(F("A1 振れなし(断線/GND落ち疑い) "));
    Serial.println();
  } else {
    Serial.println(F("  => UNCLEAR: 上の生値で判断。"));
  }
  Serial.println();
}
