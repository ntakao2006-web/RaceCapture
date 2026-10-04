#include <Arduino_RouterBridge.h>
#include <zephyr/kernel.h>
#include <math.h>

// All values are synthetic. No CAN controller, sensor pin or SD is accessed.
K_MUTEX_DEFINE(sampleMutex);
String sample = "{}";
uint32_t sequence = 0;
uint32_t previousMs = 0;
double elapsedSeconds = 0;

String readSample() {
  k_mutex_lock(&sampleMutex, K_FOREVER);
  String result = sample;
  k_mutex_unlock(&sampleMutex);
  return result;
}

void generateSample(uint32_t now) {
  elapsedSeconds += (uint32_t)(now - previousMs) / 1000.0;
  previousMs = now;
  const double t = elapsedSeconds;
  const double speed = 38 + 12 * sin(t * 0.12);
  const double distance = 38 / 3.6 * t + 12 / 3.6 / 0.12 * (1 - cos(t * 0.12));
  const double angle = distance / 180;
  const double turns = angle / (2 * M_PI);
  const double heading = (1 - (turns - (uint32_t)turns)) * 360;
  const double lat = 35.0 + 180 * sin(angle) / 111320;
  const double lon = 135.0 + 180 * cos(angle) / (111320 * cos(35 * M_PI / 180));
  const double ax = 12 / 3.6 * 0.12 * cos(t * 0.12);
  const double ay = pow(speed / 3.6, 2) / 180;
  char payload[1300];
  snprintf(payload, sizeof(payload),
    "{\"schema\":1,\"source\":\"stm32-dummy\",\"demo\":true,\"seq\":%lu,\"mcu_ms\":%lu,"
    "\"values\":{\"Speed\":%.3f,\"GPSSpeed\":%.3f,\"RPM\":%.1f,\"Throttle\":%.2f,"
    "\"BatteryVolt\":%.3f,\"Lat\":%.7f,\"Lon\":%.7f,\"Altitude\":28.4,"
    "\"Yaw\":%.2f,\"GPSFix\":3,\"GPSSats\":16,\"GNSSHz\":50,"
    "\"AccelX\":%.4f,\"AccelY\":%.4f,\"AccelZ\":9.80665,"
    "\"GyroX\":0,\"GyroY\":0,\"GyroZ\":%.4f,\"Roll\":%.3f,\"Pitch\":%.3f,"
    "\"LongAccel\":%.4f,\"LatAccel\":%.4f,\"VertAccel\":0,\"Distance\":%.5f,\"WaterTemp\":%.2f}}",
    (unsigned long)++sequence, (unsigned long)now, speed, speed, 2400 + 900 * sin(t * 0.12),
    35 + 20 * sin(t * 0.12), 12.6 + 0.15 * sin(t / 10), lat, lon,
    heading >= 360 ? 0 : heading,
    ax, ay, -speed / 3.6 / 180 * 180 / M_PI, 4 * sin(t / 4), 2 * cos(t / 5),
    ax / 9.80665, ay / 9.80665, distance / 1000, 78 + 3 * sin(t / 20));
  k_mutex_lock(&sampleMutex, K_FOREVER);
  sample = payload;
  k_mutex_unlock(&sampleMutex);
}

void setup() {
  previousMs = millis();
  generateSample(previousMs);
  Bridge.begin();
  Bridge.provide("ecologger.read", readSample);
}

void loop() {
  uint32_t now = millis();
  if ((uint32_t)(now - previousMs) >= 20) generateSample(now);
  delay(1);
}
