#pragma once
#include <array>
#include <cstdint>
#include <algorithm>

namespace logger {
// NCEC 2005 MT / NOPRO, supplied measurements dated 2026-09-12.
// Indices are independent of persistent ChannelId values.
enum NcSignal { NcRpm, NcSpeed, NcWater, NcThrottle, NcIntake,
    NcWheelFL, NcWheelFR, NcWheelRL, NcWheelRR, NcPedal, NcPedalBackup,
    NcBrake, NcAc, NcClutch, NcWaterBackup, NcFuelRaw, NcParking, NcFuel };
class NcDecoder {
    struct FuelPoint { uint64_t us; double value; };
    std::array<FuelPoint, 32> fuel{};
    unsigned begin = 0, count = 0;
    uint64_t last = 0;
public:
    void reset() { begin = count = 0; last = 0; }
    template<class Emit>
    void decode(uint32_t id, const uint8_t *d, unsigned length, uint64_t us, Emit emit) {
        auto be = [&](unsigned i) { return unsigned(d[i]) * 256 + d[i+1]; };
        switch (id) {
        case 0x201:
            if (length < 6) return;
            emit(NcRpm, be(0) / 4.0); emit(NcSpeed, be(4) / 100.0 - 100); break;
        case 0x4b0:
            if (length < 8) return;
            for (unsigned i=0; i<4; ++i) emit(NcSignal(NcWheelFL+i), be(i*2)/100.0-100);
            break;
        case 0x200:
            if (length < 8) return;
            emit(NcPedal, d[7]*0.2144+30.68); emit(NcBrake, double(bool(d[6]&1))); break;
        case 0x215:
            if (length < 8) return;
            emit(NcPedalBackup, d[6]*0.2144+30.68); emit(NcAc, double(bool(d[7]&0x40))); break;
        case 0x231:
            if (length < 2) return;
            emit(NcClutch, double(bool(d[1]&2))); break;
        case 0x240:
            if (length < 5) return;
            emit(NcWater, int(d[1])-40);
            emit(NcThrottle, std::clamp(d[3]*0.3938-0.342, 0.0, 100.0));
            emit(NcIntake, int(d[4])-40); break;
        case 0x420:
            if (length < 1) return;
            emit(NcWaterBackup, int(d[0])-40); break;
        case 0x39a:
            if (length < 1) return;
            emit(NcParking, double(bool(d[0]&8))); break;
        case 0x430: {
            if (length < 1) return;
            if (count && (us <= last || us-last > 1000000)) reset();
            last = us;
            while (count && us-fuel[begin].us > 2000000) { begin=(begin+1)%fuel.size(); --count; }
            if (count == fuel.size()) { begin=(begin+1)%fuel.size(); --count; }
            const double raw=d[0]/2.55;
            fuel[(begin+count)%fuel.size()]={us,raw}; ++count;
            double sum=0; for(unsigned i=0;i<count;++i) sum+=fuel[(begin+i)%fuel.size()].value;
            emit(NcFuelRaw,raw); emit(NcFuel,sum/count); break;
        }
        default: break;
        }
    }
};
}
