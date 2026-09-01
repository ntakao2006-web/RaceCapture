#pragma once
#include <array>
#include <cstddef>
#include <cstdint>

namespace logger {
// UBX-21035062 R03: NAV-SAT (1/35), MON-RF (0A/38). No config writes.
struct SatelliteHealth {
    uint32_t tow_ms = 0;
    unsigned reported = 0, acquired = 0, tracked = 0, used = 0;
    uint8_t max_cno = 0;
    double top4_cno = 0;
    std::array<unsigned, 7> acquired_by_gnss{}, used_by_gnss{};
};
struct RadioHealth {
    uint8_t jamming = 0, antenna_status = 0, antenna_power = 0, cw = 0;
    uint16_t noise = 0, agc = 0;
};
inline uint16_t gnssU16(const uint8_t *p) { return uint16_t(p[0]) | uint16_t(p[1]) << 8; }
inline uint32_t gnssU32(const uint8_t *p) {
    return uint32_t(gnssU16(p)) | uint32_t(gnssU16(p + 2)) << 16;
}
inline bool decodeSatelliteHealth(const uint8_t *p, size_t n, SatelliteHealth &out) {
    if (n < 8 || p[4] != 1 || n != 8 + size_t(p[5]) * 12)
        return false;
    SatelliteHealth result;
    result.tow_ms = gnssU32(p);
    result.reported = p[5];
    std::array<uint8_t, 4> best{};
    unsigned nonzero = 0;
    for (size_t i = 0; i < result.reported; ++i) {
        const uint8_t *s = p + 8 + i * 12;
        uint32_t flags = gnssU32(s + 8);
        unsigned quality = flags & 7;
        result.acquired += quality >= 2;
        result.tracked += quality >= 4;
        result.used += (flags & 8) != 0;
        if (s[0] < result.used_by_gnss.size()) {
            result.acquired_by_gnss[s[0]] += quality >= 2;
            result.used_by_gnss[s[0]] += (flags & 8) != 0;
        }
        uint8_t cno = s[2];
        if (cno) ++nonzero;
        if (cno > result.max_cno) result.max_cno = cno;
        for (auto &value : best)
            if (cno > value) {
                uint8_t old = value;
                value = cno;
                cno = old;
            }
    }
    unsigned count = nonzero < 4 ? nonzero : 4;
    for (uint8_t cno : best) result.top4_cno += cno;
    if (count) result.top4_cno /= count;
    out = result;
    return true;
}
inline bool decodeRadioHealth(const uint8_t *p, size_t n, RadioHealth &out) {
    if (n < 4 || p[0] != 0 || n != 4 + size_t(p[1]) * 24)
        return false;
    for (size_t i = 0; i < p[1]; ++i) {
        const uint8_t *b = p + 4 + 24 * i;
        if (b[0] != 0) continue; // L1 only; do not mislabel another RF band.
        out = RadioHealth{uint8_t(b[1] & 3), b[2], b[3], b[16],
                          gnssU16(b + 12), gnssU16(b + 14)};
        return true;
    }
    return false;
}
struct GnssProgress {
    uint32_t previous_tow = UINT32_MAX;
    uint64_t updated_us = 0;
    void reset(uint64_t now) { previous_tow = UINT32_MAX; updated_us = now; }
    bool observe(uint32_t tow, uint64_t now) {
        if (tow == previous_tow) return false;
        previous_tow = tow;
        updated_us = now;
        return true;
    }
    bool stalled(uint64_t now) const {
        return now >= updated_us && now - updated_us > 3000000;
    }
};
struct GnssDiagnostics {
    SatelliteHealth satellites;
    RadioHealth radio;
    uint64_t satellites_us = 0, radio_us = 0, pvt_us = 0;
    bool high_performance_clock = false, configuration_verified = false;
    unsigned profile_index = UINT32_MAX;
};
} // namespace logger
