#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include "gnss_health.h"

namespace logger {
// Provisional boot profile, not a measured optimum. Bench selections are RAM-only.
inline constexpr unsigned GNSS_RATE_HZ = 10;
struct GnssProfile {
    const char *id;
    const char *systems;
    uint16_t period_ms;
    uint8_t nominal_hz;
    bool galileo, b1i, b1c, glonass;
    uint8_t standard_max_hz, high_max_hz;
};
inline constexpr std::array<GnssProfile, 8> GNSS_PROFILES{{
    {"four_10", "GPS+Galileo+BeiDou B1C+GLONASS",100,10,true,false,true,true,4,10},
    {"b1c_15", "GPS+Galileo+BeiDou B1C",67,15,true,false,true,false,8,16},
    {"glo_15", "GPS+Galileo+GLONASS",67,15,true,false,false,true,6,16},
    {"dual_20", "GPS+Galileo",50,20,true,false,false,false,10,20},
    {"gps_25", "GPS",40,25,false,false,false,false,18,25},
    {"four_8", "GPS+Galileo+BeiDou B1C+GLONASS",125,8,true,false,true,true,4,10},
    {"b1i_10", "GPS+Galileo+BeiDou B1I",100,10,true,true,false,false,3,12},
    {"dual_10", "GPS+Galileo",100,10,true,false,false,false,10,20}
}};
inline constexpr unsigned GNSS_DEFAULT_PROFILE = 0, GNSS_FALLBACK_PROFILE = 7;
inline bool gnssProfileSupported(unsigned index, bool high) {
    if (index >= GNSS_PROFILES.size()) return false;
    const auto &p = GNSS_PROFILES[index];
    return !(p.b1i && (p.b1c || p.glonass)) &&
           uint32_t(p.period_ms) * (high ? p.high_max_hz : p.standard_max_hz) >= 1000;
}
struct GnssSetting { uint32_t key, value; unsigned bytes; };
// UBX-22038241 R03 2.1.3: B1I cannot coexist with B1C or GLONASS.
// UBX-22028884 R04 table 2: 4 GNSS at 10 Hz requires high-performance clock.
inline std::array<GnssSetting, 13> gnssSignals(const GnssProfile &p) {
    return {{{0x1031001f,1,1}, {0x10310001,1,1}, // GPS L1 C/A
             {0x10310021,p.galileo,1}, {0x10310007,p.galileo,1}, // Galileo E1
             {0x10310022,p.b1i||p.b1c,1}, {0x1031000d,p.b1i,1}, {0x1031000f,p.b1c,1},
             {0x10310025,p.glonass,1}, {0x10310018,p.glonass,1}, // GLONASS L1OF
             {0x10310024,1,1}, {0x10310012,1,1}, // QZSS L1 C/A
             {0x10310020,1,1}, {0x10310005,1,1}}}; // SBAS L1 C/A
}
inline constexpr std::array<GnssSetting, 6> GNSS_RATE_SETTINGS{{
    {0x10740001,1,1}, {0x10740002,0,1}, {0x20910007,1,1}, // UBX only, every PVT
    {0x30210001,1000/GNSS_RATE_HZ,2}, {0x30210002,1,2}, {0x20110021,4,1}}};
inline std::array<GnssSetting, 6> gnssRateSettings(const GnssProfile &p) {
    auto settings = GNSS_RATE_SETTINGS;
    settings[3].value = p.period_ms;
    return settings;
}

// Exact RAM VALGET readback; key order is not assumed. Reject wrong, missing,
// duplicated and truncated values rather than reporting an unverified profile.
inline bool matchesGnssSettings(const uint8_t *p, size_t n,
                                const GnssSetting *settings, size_t count) {
    if (n < 4 || p[0] != 1 || p[1] != 0 || count > 32) return false;
    uint32_t seen = 0;
    size_t pos = 4;
    while (pos < n) {
        if (n-pos < 4) return false;
        uint32_t id = gnssU32(p+pos); pos += 4;
        size_t i = 0;
        while (i < count && settings[i].key != id) ++i;
        if (i == count || (seen & (uint32_t(1)<<i)) || n-pos < settings[i].bytes) return false;
        uint32_t value = 0;
        for (unsigned j=0;j<settings[i].bytes;++j) value |= uint32_t(p[pos++]) << (8*j);
        if (value != settings[i].value) return false;
        seen |= uint32_t(1)<<i;
    }
    return seen == (count == 32 ? UINT32_MAX : (uint32_t(1)<<count)-1);
}
} // namespace logger
