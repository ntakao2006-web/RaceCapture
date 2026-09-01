#include "../src/gnss_health.h"
#include <cassert>
#include <cmath>
#include <iostream>
using namespace logger;

int main() {
    // A stream of repeated packets must not hide a stopped navigation engine.
    GnssProgress progress;
    progress.reset(100);
    assert(progress.observe(604799960, 200));
    assert(!progress.observe(604799960, 3000000));
    assert(!progress.stalled(3000200));
    assert(progress.stalled(3000201));
    assert(progress.observe(0, 3000202)); // GPS week rollover is real progress.
    // No-fix data remains useful progress; do not reset repeatedly under a roof.
    for (unsigned i = 1; i < 1000; ++i) {
        assert(progress.observe(i * 40, 3000202 + i * 40000));
        assert(!progress.stalled(3000202 + i * 40000));
    }
    progress.reset(50000000);
    assert(progress.observe(39960, 50000001)); // First epoch after reconfiguration.

    uint8_t sat[8 + 5 * 12]{};
    sat[4] = 1; sat[5] = 5;
    const uint8_t cn[] = {24, 42, 0, 30, 38};
    const uint8_t flags[] = {1, 5 | 8, 0, 2, 4 | 8};
    const uint8_t systems[] = {0,2,3,5,6};
    for (unsigned i = 0; i < 5; ++i) {
        sat[8 + i * 12] = systems[i];
        sat[10 + i * 12] = cn[i];
        sat[16 + i * 12] = flags[i];
    }
    SatelliteHealth s;
    assert(decodeSatelliteHealth(sat, sizeof(sat), s));
    assert(s.reported == 5 && s.acquired == 3 && s.tracked == 2 && s.used == 2);
    assert(s.used_by_gnss[2]==1 && s.used_by_gnss[6]==1 && s.used_by_gnss[0]==0);
    assert(s.acquired_by_gnss[5]==1 && s.acquired_by_gnss[3]==0);
    assert(s.max_cno == 42 && std::abs(s.top4_cno - 33.5) < 1e-9);
    assert(!decodeSatelliteHealth(sat, sizeof(sat) - 1, s));
    assert(s.max_cno == 42); // Failed frames cannot replace valid state.
    sat[4] = 2;
    assert(!decodeSatelliteHealth(sat, sizeof(sat), s));
    sat[4] = 1; sat[5] = 0;
    assert(decodeSatelliteHealth(sat, 8, s) && s.max_cno == 0 && s.top4_cno == 0);
    sat[5] = 1;
    assert(decodeSatelliteHealth(sat, 20, s) && s.top4_cno == 24);

    uint8_t rf[4 + 2 * 24]{};
    rf[1] = 2; rf[4] = 1; // First block is not L1.
    rf[28] = 0; rf[29] = 2; rf[30] = 1; rf[31] = 2;
    rf[40] = 0x34; rf[41] = 0x12;
    rf[42] = 0xff; rf[43] = 0x1f; rf[44] = 200;
    RadioHealth r;
    assert(decodeRadioHealth(rf, sizeof(rf), r));
    assert(r.jamming == 2 && r.antenna_status == 1 && r.antenna_power == 2);
    assert(r.noise == 0x1234 && r.agc == 8191 && r.cw == 200);
    assert(!decodeRadioHealth(rf, sizeof(rf) - 1, r));
    rf[28] = 2;
    assert(!decodeRadioHealth(rf, sizeof(rf), r));
    rf[0] = 1;
    assert(!decodeRadioHealth(rf, sizeof(rf), r));
    std::cout << "GNSS health tests passed\n";
}
