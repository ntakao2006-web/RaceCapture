// [130950]6軸IMUセンサーモジュール AE-LSM6DSV16X
// https://akizukidenshi.com/catalog/g/g130950/
// 本プログラムは上記モジュールを簡易的に動作確認するプログラムです。
//
// ======== 注意！ ========
// 本モジュールは5V系のマイコンボード（Arduino Unoなど）ではお使いいただけません！
// Raspberry Pi PicoやEPS32など3.3V系のマイコンボードに付属のQwiicケーブルを使い以下のように繋いでください。
//  黒 : GND
//  赤 : 3.3V (5V不可)
//  青 : SDA
//  黄 : SCL
// 本サンプルプログラムはI2Cで通信するため、J2（「6B」刻印近く）もしくはJ3（「6A」刻印近く）のジャンパーパターンをハンダで短絡させてください。
// また、プルアップ抵抗を外部で用意しない場合は、J1もハンダで短絡させてください。
// 
// (株）秋月電子通商 2025-12-22

#include <Arduino.h>
#include <Wire.h>

// 使用するシリアルやI2Cポートに応じて変更してください。
auto& mySerial = Serial;
auto& myWire = Wire;

constexpr uint8_t LSM6_ADDR_GND = 0x6A;
constexpr uint8_t LSM6_ADDR_VCC = 0x6B;
uint8_t lsm6_addr = 0;

constexpr uint8_t REG_WHO_AM_I = 0x0F;
constexpr uint8_t REG_CTRL1 = 0x10;
constexpr uint8_t REG_CTRL2 = 0x11;
constexpr uint8_t REG_CTRL6 = 0x15;
constexpr uint8_t REG_CTRL8 = 0x17;
constexpr uint8_t REG_OUTX_L_G = 0x22;

void writeReg(uint8_t reg, uint8_t val) {
  myWire.beginTransmission(lsm6_addr);
  myWire.write(reg);
  myWire.write(val);
  myWire.endTransmission();
}

void readRegs(uint8_t startReg, uint8_t* buf, uint8_t len) {
  myWire.beginTransmission(lsm6_addr);
  myWire.write(startReg);
  myWire.endTransmission(false);
  myWire.requestFrom(lsm6_addr, len);
  for (uint8_t i = 0; i < len; i++) { buf[i] = myWire.read(); }
}

bool lsm6_init() {
  // デバイス固有IDチェック
  uint8_t who;
  readRegs(REG_WHO_AM_I, &who, 1);
  mySerial.print("WHO_AM_I = 0x");
  mySerial.println(who, HEX);
  if (who != 0x70) { return false; }

  // 初期設定
  writeReg(REG_CTRL1, 0b00001001);
  writeReg(REG_CTRL2, 0b00001001);
  writeReg(REG_CTRL6, 0b00000100);
  writeReg(REG_CTRL8, 0b10000010);
  delay(10);

  return true;
}

void readSensor(float& gx, float& gy, float& gz, float& ax, float& ay, float& az) {
  uint8_t buf[12];
  int16_t buf2[6];
  readRegs(REG_OUTX_L_G, buf, 12);
  for (int i = 0; i < 6; i++) { buf2[i] = (buf[i * 2 + 1] << 8 | buf[i * 2]); }
  gx = static_cast<float>(buf2[0]) * 0.07;
  gy = static_cast<float>(buf2[1]) * 0.07;
  gz = static_cast<float>(buf2[2]) * 0.07;
  ax = static_cast<float>(buf2[3]) * 0.000244;
  ay = static_cast<float>(buf2[4]) * 0.000244;
  az = static_cast<float>(buf2[5]) * 0.000244;
}

void setup() {
  myWire.begin();
  mySerial.begin(115200);
  while (!mySerial);
  delay(100);

  mySerial.println("\n\nStart!");

  myWire.beginTransmission(LSM6_ADDR_GND);
  if (myWire.endTransmission() == 0) {
    mySerial.print("LSM6DSV16X found.\naddress: 0x");
    mySerial.println(LSM6_ADDR_GND, 16);
    lsm6_addr = LSM6_ADDR_GND;
  }

  myWire.beginTransmission(LSM6_ADDR_VCC);
  if (myWire.endTransmission() == 0) {
    mySerial.print("LSM6DSV16X found.\naddress: 0x");
    mySerial.println(LSM6_ADDR_VCC, 16);
    lsm6_addr = LSM6_ADDR_VCC;
  }

  if (lsm6_addr == 0) {
    mySerial.print("LSM6DSV16X not found.");
    while (1);
  }

  if (!lsm6_init()) {
    mySerial.println("LSM6DSV16X init error!");
    while (1);
  }

  mySerial.println("LSM6DSV16X initialized.");
}

void loop() {
  float ax, ay, az, gx, gy, gz;
  readSensor(gx, gy, gz, ax, ay, az);

  mySerial.print(ax);
  mySerial.print(", ");
  mySerial.print(ay);
  mySerial.print(", ");
  mySerial.print(az);
  mySerial.print(", ");
  mySerial.print(gx);
  mySerial.print(", ");
  mySerial.print(gy);
  mySerial.print(", ");
  mySerial.println(gz);

  delay(100);
}
