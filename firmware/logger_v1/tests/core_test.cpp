#include "../src/core.h"
#include <cassert>
#include <iostream>
#include <vector>
using namespace logger;
static bool near(double a, double b, double e = 1e-6) { return std::abs(a - b) < e; }
static std::vector<uint8_t> ubx(uint8_t cls, uint8_t id, const std::vector<uint8_t> &p) {
    std::vector<uint8_t> bytes{0xb5, 0x62, cls, id, uint8_t(p.size()), uint8_t(p.size() >> 8)};
    bytes.insert(bytes.end(), p.begin(), p.end());
    uint8_t a = 0, b = 0;
    for (size_t i = 2; i < bytes.size(); ++i) {
        a += bytes[i];
        b += a;
    }
    bytes.push_back(a);
    bytes.push_back(b);
    return bytes;
}
static void testBits() {
    CanFrame f;
    f.dlc = 8;
    f.data[0] = 0xFE;
    f.data[1] = 0xFF;
    double out = 0;
    assert(extract(f, 0, 16, true, true, 0.5, 3, out) && out == 2);
    assert(extract(f, 0, 16, false, false, 1, 0, out) && out == 65279);
    memset(f.data, 0xff, 8);
    assert(extract(f, 0, 32, true, true, 1, 0, out) && out == -1);
    assert(extract(f, 31, 32, false, false, 1, 0, out) && out == 4294967295.0);
    assert(!extract(f, 33, 32, true, false, 1, 0, out));
    assert(!extract(f, 0, 0, true, false, 1, 0, out));
    f.rtr = true;
    assert(!extract(f, 0, 8, true, false, 1, 0, out));
    f.rtr = false;
    f.dlc = 2;
    assert(!extract(f, 8, 16, true, false, 1, 0, out));
    assert(!extract(f, 0, 8, true, false, NAN, 0, out));
    // Exhaust all offsets and widths against an independent 64-bit reference.
    f.dlc = 8;
    uint64_t raw = 0x8070605040302010ULL;
    memcpy(f.data, &raw, 8);
    for (unsigned bit = 0; bit < 64; ++bit)
        for (unsigned width = 1; width <= 32 && bit + width <= 64; ++width)
            assert(extract(f, bit, width, true, false, 1, 0, out) &&
                   out == double((raw >> bit) & ((1ULL << width) - 1)));
}
static void testUbx() {
    UbxParser p;
    auto bytes = ubx(1, 7, {0, 1, 2, 0xb5, 0x62, 255});
    unsigned count = 0;
    for (uint8_t c : bytes)
        count += p.feed(c);
    assert(count == 1 && p.length() == 6 && p.payload[5] == 255);
    bytes.back() ^= 1;
    for (uint8_t c : bytes)
        assert(!p.feed(c));
    assert(p.errors == 1);
    bytes = ubx(5, 1, {});
    for (uint8_t c : bytes)
        count += p.feed(c);
    assert(count == 2 && p.length() == 0);
    const uint8_t bad[] = {0xb5, 0x62, 1, 2, 0xff, 0xff};
    for (uint8_t c : bad)
        assert(!p.feed(c));
    bytes = ubx(1, 7, std::vector<uint8_t>(92, 0));
    for (uint8_t c : bytes)
        count += p.feed(c);
    assert(count == 3);
    // Fragment boundaries do not affect parsing.
    for (unsigned chunk = 1; chunk < bytes.size(); ++chunk) {
        p.reset();
        unsigned got = 0;
        for (size_t i = 0; i < bytes.size(); i += chunk)
            for (size_t j = i; j < std::min(i + chunk, bytes.size()); ++j)
                got += p.feed(bytes[j]);
        assert(got == 1);
    }
}
static void testPvt() {
    std::vector<uint8_t> b(92);
    b[4] = 0xea;
    b[5] = 7;
    b[6] = 8;
    b[7] = 31;
    b[8] = 12;
    b[11] = 7;
    b[20] = 3;
    b[21] = 1;
    b[23] = 9;
    put32(b.data() + 24, 1391234567);
    put32(b.data() + 28, 351234567);
    put32(b.data() + 36, 93740);
    put32(b.data() + 40, 2090);
    put32(b.data() + 44, 12340);
    put32(b.data() + 60, 12345);
    Pvt p;
    assert(decodePvt(b.data(), b.size(), p) && p.fix_ok && p.utc_valid);
    assert(near(p.lat, 35.1234567) && near(p.lon, 139.1234567) && near(p.speed, 12.345));
    assert(near(p.altitude, 93.74) && near(p.hacc, 2.09) && near(p.vacc, 12.34));
    assert(p.utc_us == 1788177600000000LL);
    put32(b.data() + 16, uint32_t(-123456789));
    assert(decodePvt(b.data(), 92, p) && p.utc_us == 1788177599876544LL);
    b[78] = 1;
    assert(decodePvt(b.data(), 92, p) && !p.fix_ok);
    b[78] = 0;
    b[6] = 2;
    b[7] = 30;
    assert(decodePvt(b.data(), 92, p) && !p.utc_valid);
    assert(validDate(2024, 2, 29) && !validDate(2025, 2, 29));
    assert(!decodePvt(b.data(), 91, p));
    assert(daysFromCivil(1970, 1, 1) == 0);
}
static void testImu() {
    uint8_t b[0x33] = {};
    b[0] = 0xe2;
    b[1] = 0xff; // -0.30 m/s2, not a software bias
    b[4] = 0xd5;
    b[5] = 3;
    b[0x26] = 0xe2;
    b[0x27] = 0xff;
    b[0x20] = 1;
    b[0x31] = 5;
    b[0x32] = 7;
    b[0x2d] = 0xff;
    auto s = decodeImu(b, sizeof(b));
    assert(s.valid && near(s.accel[0], -.3) && near(s.accel[2], 9.81));
    assert(near(s.gravity[0], -.3) && near(s.linear[0], .01) && s.error == 0 &&
           s.calibration == 255);
    b[0x31] = 1;
    s = decodeImu(b, sizeof(b));
    assert(!s.valid && s.error == 7);
    // Regress the captured fault: I2C succeeds while SYS_STATUS=1, SYS_ERR=5.
    b[0x32] = 5;
    s = decodeImu(b, sizeof(b));
    assert(!s.valid && s.error == 5);
    ImuHealth health;
    for (unsigned i = 0; i < 9; ++i)
        assert(!health.observe(true, s.valid));
    assert(health.observe(true, s.valid));
    assert(!health.observe(true, true));
    // A good sample clears intermittent failures; both error types count.
    for (unsigned i = 0; i < 9; ++i)
        assert(!health.observe(false, false));
    assert(!health.observe(true, true));
    for (unsigned i = 0; i < 9; ++i)
        assert(!health.observe(i % 2 == 0, false));
    assert(health.observe(true, false));
    // Stale SYS_ERR must not trigger resets when the sensor reports running.
    b[0x31] = 5;
    s = decodeImu(b, sizeof(b));
    for (unsigned i = 0; i < 100; ++i)
        assert(!health.observe(true, s.valid));
    LevelCalibration c;
    c.enabled = 1;
    c.roll_zero_deg = 12.5;
    c.pitch_zero_deg = -3;
    c.matrix = {0, 1, 0, -1, 0, 0, 0, 0, 1};
    assert(validLevelCalibration(c));
    double input[3] = {1, 2, 3};
    auto corrected = correctedAcceleration(c, input);
    assert(near(corrected[0], 2) && near(corrected[1], -1) && near(corrected[2], 3));
    LevelCalibration identity;
    corrected = correctedAcceleration(identity, input);
    assert(near(corrected[0], 1) && near(corrected[1], 2) && near(corrected[2], 3));
    assert(near(wrap180(181), -179) && near(wrap180(-181), 179));
    c.matrix[0] = .5;
    assert(!validLevelCalibration(c));
}
static void testAfr() {
    AfrGate g;
    assert(!g.update(1000000, true, 3000, true));
    assert(!g.update(2999999, true, 3000, true));
    assert(g.update(3000000, true, 3000, true));
    assert(!g.update(4000000, true, 0, true));
    assert(!g.update(5000000, true, 3000, true));
    assert(g.update(7000000, true, 3000, true));
    assert(!g.update(8000000, false, 3000, true));
    assert(!g.update(9000000, true, 3000, true));
    assert(!g.update(11000000, true, 3000, false));
    assert(g.update(12000000, true, 3000, true));
    assert(!fresh(1000, 0, 10));
    assert(fresh(11000, 1000, 10));
    assert(!fresh(11001, 1000, 10));
}
static void testLaps() {
    LapEngine l;
    Track tr;
    tr.id = 1;
    tr.radius_m = 5;
    tr.lat = 35;
    tr.lon = 139;
    tr.min_lap_s = 10;
    l.reset(tr);
    // 100 m radius circle, SF at its eastmost point; fixed 100 s laps.
    double t = 100;
    for (unsigned i = 0; i < 6500; ++i, t += .05) {
        double angle = 2 * PI * (t - 100) / 100;
        double x = 100 * (std::cos(angle) - 1), y = 100 * std::sin(angle);
        l.update(tr.lat + y / M_PER_DEG, tr.lon + x / (M_PER_DEG * std::cos(tr.lat * PI / 180)), t,
                 6.283, 1, true);
    }
    assert(l.completed >= 2 && l.best_s > 99 && l.best_s < 101 && l.best_count > 100 &&
           l.delta_valid);
    l.update(35, 139, t + 10, 6.283, 1, true);
    assert(!l.delta_valid);
    Track second = tr;
    second.id = 2;
    l.reset(second);
    assert(l.completed == 0 && l.best_count == 0 && l.best_s == 0);
    tr.radius_m = NAN;
    assert(!tr.valid());
}
int main() {
    testBits();
    testUbx();
    testPvt();
    testImu();
    testAfr();
    testLaps();
    std::cout << "All core tests passed\n";
}
