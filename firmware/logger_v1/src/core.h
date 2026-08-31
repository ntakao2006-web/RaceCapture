#pragma once
// Hardware-independent arithmetic and parsers; exercised by
// tests/core_test.cpp.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>

namespace logger {
constexpr size_t MAX_CHANNELS = 128;
constexpr double GRAVITY = 9.80665;
constexpr double M_PER_DEG = 111319.490793;
constexpr double PI = 3.141592653589793;

inline uint16_t u16(const uint8_t *p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
inline int16_t i16(const uint8_t *p) { return static_cast<int16_t>(u16(p)); }
inline uint32_t u32(const uint8_t *p) {
    return uint32_t(p[0]) | (uint32_t(p[1]) << 8) | (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}
inline int32_t i32(const uint8_t *p) { return static_cast<int32_t>(u32(p)); }
inline void put32(uint8_t *p, uint32_t v) {
    for (int i = 0; i < 4; ++i)
        p[i] = uint8_t(v >> (8 * i));
}
inline bool fresh(uint64_t now, uint64_t then, uint32_t timeout_ms) {
    return then != 0 && now >= then &&
           (timeout_ms == 0 || now - then <= uint64_t(timeout_ms) * 1000);
}

struct CanFrame {
    uint64_t us = 0;
    uint32_t id = 0;
    uint8_t bus = 0, dlc = 0;
    bool extended = false, rtr = false, tx = false;
    uint8_t data[8] = {};
};

// bit=0 means LSB of byte0 for little endian; MSB of byte0 for big endian.
// This is a linear network bit offset, NOT a DBC Motorola sawtooth bit number.
inline bool extract(const CanFrame &f, unsigned bit, unsigned width, bool little, bool is_signed,
                    double scale, double offset, double &value) {
    if (f.rtr || f.dlc > 8 || width == 0 || width > 32 || bit + width > f.dlc * 8U ||
        !std::isfinite(scale) || !std::isfinite(offset))
        return false;
    uint32_t raw = 0;
    for (unsigned n = 0; n < width; ++n) {
        unsigned b = bit + n;
        unsigned v = (f.data[b / 8] >> (little ? b % 8 : 7 - b % 8)) & 1;
        if (little)
            raw |= uint32_t(v) << n;
        else
            raw = (raw << 1) | v;
    }
    double numeric = raw;
    if (is_signed && (raw & (uint32_t(1) << (width - 1))))
        numeric -= std::ldexp(1.0, width);
    value = numeric * scale + offset;
    return std::isfinite(value);
}

struct ImuSample {
    double accel[3]{}, gyro[3]{}, euler[3]{}, linear[3]{}, gravity[3]{}, quaternion[4]{};
    int8_t temperature = 0;
    uint8_t calibration = 0, status = 0, error = 0;
    bool valid = false;
};
// Register burst 0x08..0x3A, default UNIT_SEL=0 (m/s2, dps, degrees).
inline ImuSample decodeImu(const uint8_t *p, size_t n) {
    ImuSample s;
    if (n < 0x33)
        return s;
    for (unsigned i = 0; i < 3; ++i) {
        s.accel[i] = i16(p + 2 * i) / 100.0;
        s.gyro[i] = i16(p + 0x0c + 2 * i) / 16.0;
        s.euler[i] = i16(p + 0x12 + 2 * i) / 16.0; // heading, roll, pitch
        s.linear[i] = i16(p + 0x20 + 2 * i) / 100.0;
        s.gravity[i] = i16(p + 0x26 + 2 * i) / 100.0;
    }
    for (unsigned i = 0; i < 4; ++i)
        s.quaternion[i] = i16(p + 0x18 + 2 * i) / 16384.0;
    s.temperature = static_cast<int8_t>(p[0x2c]);
    s.calibration = p[0x2d];
    s.status = p[0x31];
    s.error = s.status == 1 ? p[0x32] : 0;
    s.valid = s.status == 5;
    return s;
}

// Gregorian UTC conversion, independent of libc time_t width and PC timezone.
inline int64_t daysFromCivil(int y, unsigned m, unsigned d) {
    y -= m <= 2;
    const int era = (y >= 0 ? y : y - 399) / 400;
    const unsigned yoe = unsigned(y - era * 400);
    const unsigned doy = (153 * (m > 2 ? m - 3 : m + 9) + 2) / 5 + d - 1;
    return int64_t(era) * 146097 + yoe * 365 + yoe / 4 - yoe / 100 + doy - 719468;
}
inline bool validDate(int y, unsigned m, unsigned d) {
    constexpr unsigned md[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (y < 2020 || y > 2099 || m < 1 || m > 12 || d < 1)
        return false;
    const bool leap = (y % 4 == 0 && (y % 100 != 0 || y % 400 == 0));
    return d <= md[m - 1] + unsigned(m == 2 && leap);
}
struct Pvt {
    uint32_t tow_ms = 0, time_accuracy_ns = 0;
    int64_t utc_us = 0;
    double lat = 0, lon = 0, altitude = 0, speed = 0, heading = 0, hacc = 0, sacc = 0;
    uint8_t fix = 0, satellites = 0;
    bool fix_ok = false, utc_valid = false;
};
inline bool decodePvt(const uint8_t *p, size_t n, Pvt &s) {
    if (n != 92)
        return false;
    s = Pvt{};
    s.tow_ms = u32(p);
    s.time_accuracy_ns = u32(p + 12);
    s.fix = p[20];
    s.satellites = p[23];
    s.lon = i32(p + 24) * 1e-7;
    s.lat = i32(p + 28) * 1e-7;
    s.altitude = i32(p + 36) / 1000.0;
    s.hacc = u32(p + 40) / 1000.0;
    s.speed = i32(p + 60) / 1000.0;
    s.heading = i32(p + 64) * 1e-5;
    s.sacc = u32(p + 68) / 1000.0;
    s.fix_ok = (p[21] & 1) && (s.fix == 2 || s.fix == 3 || s.fix == 4) && std::abs(s.lat) <= 90 &&
               std::abs(s.lon) <= 180 && !(p[78] & 1);
    int year = u16(p + 4);
    unsigned month = p[6], day = p[7];
    s.utc_valid =
        (p[11] & 7) == 7 && validDate(year, month, day) && p[8] < 24 && p[9] < 60 && p[10] < 60;
    if (s.utc_valid)
        s.utc_us =
            (daysFromCivil(year, month, day) * 86400 + p[8] * 3600 + p[9] * 60 + p[10]) * 1000000 +
            i32(p + 16) / 1000;
    return true;
}

// Bounded streaming UBX parser: fragmented UART reads and bad checksums are
// normal.
class UbxParser {
    unsigned pos_ = 0, length_ = 0;
    uint8_t a_ = 0, b_ = 0;

  public:
    uint8_t cls = 0, id = 0;
    std::array<uint8_t, 1024> payload{};
    uint32_t errors = 0;
    size_t length() const { return length_; }
    void reset() {
        pos_ = 0;
        length_ = 0;
        a_ = b_ = 0;
    }
    bool feed(uint8_t c) {
        if (pos_ == 0) {
            if (c == 0xb5)
                pos_ = 1;
            return false;
        }
        if (pos_ == 1) {
            pos_ = c == 0x62 ? 2 : (c == 0xb5 ? 1 : 0);
            a_ = b_ = 0;
            return false;
        }
        if (pos_ == 2)
            cls = c;
        else if (pos_ == 3)
            id = c;
        else if (pos_ == 4)
            length_ = c;
        else if (pos_ == 5) {
            length_ |= unsigned(c) << 8;
            if (length_ > payload.size()) {
                ++errors;
                reset();
                return false;
            }
        } else if (pos_ < length_ + 6)
            payload[pos_ - 6] = c;
        else if (pos_ == length_ + 6) {
            if (c != a_) {
                ++errors;
                reset();
            } else
                ++pos_;
            return false;
        } else {
            bool ok = c == b_;
            if (!ok)
                ++errors;
            pos_ = 0;
            return ok; // preserve the complete payload until next feed
        }
        a_ = uint8_t(a_ + c);
        b_ = uint8_t(b_ + a_);
        ++pos_;
        return false;
    }
};

class AfrGate {
    uint64_t running_since_ = 0;

  public:
    bool update(uint64_t now, bool rpm_valid, double rpm, bool afr_valid) {
        if (!rpm_valid || !std::isfinite(rpm) || rpm < 50) {
            running_since_ = 0;
            return false;
        }
        if (running_since_ == 0)
            running_since_ = now;
        return afr_valid && now >= running_since_ && now - running_since_ >= 2000000;
    }
};

struct Track {
    int32_t id = -1;
    double lat = 0, lon = 0, radius_m = 20, min_lap_s = 10;
    bool valid() const {
        return id >= 0 && std::isfinite(lat) && std::isfinite(lon) && std::abs(lat) <= 90 &&
               std::abs(lon) <= 180 && radius_m >= 5 && radius_m <= 200 && min_lap_s >= 10 &&
               min_lap_s <= 3600;
    }
    bool operator==(const Track &b) const {
        return id == b.id && lat == b.lat && lon == b.lon && radius_m == b.radius_m &&
               min_lap_s == b.min_lap_s;
    }
};
inline double distance(double lat1, double lon1, double lat2, double lon2) {
    double dy = (lat2 - lat1) * M_PER_DEG;
    double dx = (lon2 - lon1) * M_PER_DEG * std::cos((lat1 + lat2) * PI / 360);
    return std::hypot(dx, dy);
}
struct LapPoint {
    float metres = 0, seconds = 0;
};
class LapEngine {
  public:
    static constexpr size_t CAPACITY = 4096;
    Track track{};
    std::array<LapPoint, CAPACITY> current{}, best{};
    size_t count = 0, best_count = 0;
    double last_s = 0, best_s = 0, metres = 0, elapsed_s = 0, delta_s = 0;
    uint32_t completed = 0, current_lap = 0;
    bool delta_valid = false, best_changed = false;

  private:
    bool prev_ = false, armed_ = false, lap_valid_ = false;
    double lat_ = 0, lon_ = 0, time_ = 0, start_ = 0;

  public:
    void reset(const Track &t) {
        track = t;
        count = best_count = 0;
        last_s = best_s = metres = elapsed_s = delta_s = 0;
        completed = current_lap = 0;
        delta_valid = best_changed = false;
        prev_ = armed_ = lap_valid_ = false;
        lat_ = lon_ = time_ = start_ = 0;
    }
    void invalidate() {
        prev_ = false;
        armed_ = false;
        lap_valid_ = false;
        delta_valid = false;
    }
    bool inValidLap() const { return current_lap > 0 && lap_valid_; }
    void update(double lat, double lon, double time, double speed, double accuracy, bool valid) {
        if (!track.valid() || !valid || !std::isfinite(time) || !std::isfinite(lat) ||
            !std::isfinite(lon) || !std::isfinite(accuracy) || !std::isfinite(speed) ||
            accuracy > 15 || accuracy < 0) {
            invalidate();
            return;
        }
        double gate = distance(lat, lon, track.lat, track.lon);
        if (!prev_) {
            lat_ = lat;
            lon_ = lon;
            time_ = time;
            prev_ = true;
            armed_ = gate > track.radius_m * 1.3;
            return;
        }
        double dt = time - time_, step = distance(lat_, lon_, lat, lon);
        if (dt <= 0)
            return;
        if (dt > 1.5 || step > std::max(15.0, 120 * dt)) {
            invalidate();
            return;
        }
        if (current_lap) {
            metres += step;
            elapsed_s = time - start_;
            if (count == 0 || metres - current[count - 1].metres >= 2 ||
                elapsed_s - current[count - 1].seconds >= 0.5) {
                if (count < CAPACITY)
                    current[count++] = {float(metres), float(elapsed_s)};
                else
                    lap_valid_ = false;
            }
        }
        double dx = (lon - lon_) * std::cos(track.lat * PI / 180) * M_PER_DEG,
               dy = (lat - lat_) * M_PER_DEG;
        double px = (track.lon - lon_) * std::cos(track.lat * PI / 180) * M_PER_DEG,
               py = (track.lat - lat_) * M_PER_DEG;
        double len = dx * dx + dy * dy,
               t = len > 0 ? std::clamp((px * dx + py * dy) / len, 0.0, 1.0) : 0;
        bool crossing =
            armed_ && speed > 2 && std::hypot(px - t * dx, py - t * dy) <= track.radius_m;
        if (crossing) {
            double crossed = time_ + dt * t, lap_s = crossed - start_;
            armed_ = false;
            if (!current_lap || lap_s >= track.min_lap_s) {
                if (current_lap && lap_valid_ && metres >= 50) {
                    // Trim the final sample to the interpolated gate time/distance.
                    const double finish_metres = metres - step * (1 - t);
                    while (count > 1 && current[count - 1].seconds >= lap_s)
                        --count;
                    if (count < CAPACITY)
                        current[count++] = {float(finish_metres), float(lap_s)};
                    else
                        current[count - 1] = {float(finish_metres), float(lap_s)};
                    last_s = lap_s;
                    ++completed;
                    if (best_s == 0 || lap_s < best_s) {
                        best = current;
                        best_count = count;
                        best_s = lap_s;
                        best_changed = true;
                    }
                }
                ++current_lap;
                start_ = crossed;
                metres = step * (1 - t);
                elapsed_s = time - crossed;
                count = 1;
                current[0] = {0, 0};
                lap_valid_ = true;
            }
        } else if (gate > track.radius_m * 1.3)
            armed_ = true;
        delta_valid = false;
        if (lap_valid_ && best_count > 1 && metres <= best[best_count - 1].metres) {
            for (size_t i = 1; i < best_count; ++i)
                if (best[i].metres >= metres) {
                    double d = best[i].metres - best[i - 1].metres;
                    if (d > 0) {
                        double ref =
                            best[i - 1].seconds + (metres - best[i - 1].metres) / d *
                                                      (best[i].seconds - best[i - 1].seconds);
                        delta_s = elapsed_s - ref;
                        delta_valid = true;
                    }
                    break;
                }
        }
        lat_ = lat;
        lon_ = lon;
        time_ = time;
    }
};
} // namespace logger
