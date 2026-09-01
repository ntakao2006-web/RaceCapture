#include "../src/gnss_config.h"
#include <algorithm>
#include <cassert>
#include <iostream>
#include <vector>
using namespace logger;

static std::vector<uint8_t> reply(const GnssSetting *items, size_t n) {
    std::vector<uint8_t> bytes{1,0,0,0};
    for (size_t i=0;i<n;++i) {
        for (unsigned j=0;j<4;++j) bytes.push_back(items[i].key>>(8*j));
        for (unsigned j=0;j<items[i].bytes;++j) bytes.push_back(items[i].value>>(8*j));
    }
    return bytes;
}
int main() {
    assert(GNSS_RATE_HZ==10);
    for (bool high : {false,true}) {
        auto signals=gnssSignals(GNSS_PROFILES[high ? GNSS_DEFAULT_PROFILE : GNSS_FALLBACK_PROFILE]);
        auto value=[&](uint32_t key) {
            auto item=std::find_if(signals.begin(),signals.end(),[&](auto s){return s.key==key;});
            assert(item!=signals.end());return item->value;
        };
        assert(value(0x1031001f)==1 && value(0x10310021)==1); // GPS + Galileo
        assert(value(0x10310022)==high && value(0x10310025)==high);
        assert(value(0x1031000d)==0 && value(0x1031000f)==high); // B1I / B1C exclusion
        assert(value(0x10310024)==1 && value(0x10310020)==1); // QZSS / SBAS
        auto bytes=reply(signals.data(),signals.size());
        assert(matchesGnssSettings(bytes.data(),bytes.size(),signals.data(),signals.size()));
        auto reversed=signals;std::reverse(reversed.begin(),reversed.end());
        bytes=reply(reversed.data(),reversed.size());
        assert(matchesGnssSettings(bytes.data(),bytes.size(),signals.data(),signals.size()));
        assert(!matchesGnssSettings(bytes.data(),bytes.size()-1,signals.data(),signals.size()));
        bytes.back()^=1;
        assert(!matchesGnssSettings(bytes.data(),bytes.size(),signals.data(),signals.size()));
        bytes=reply(signals.data(),signals.size()-1);
        assert(!matchesGnssSettings(bytes.data(),bytes.size(),signals.data(),signals.size()));
        auto duplicate=signals;duplicate[1]=duplicate[0];bytes=reply(duplicate.data(),duplicate.size());
        assert(!matchesGnssSettings(bytes.data(),bytes.size(),signals.data(),signals.size()));
        bytes=reply(signals.data(),signals.size());bytes[1]=1; // BBR is not RAM verification.
        assert(!matchesGnssSettings(bytes.data(),bytes.size(),signals.data(),signals.size()));
    }
    // Reference mixed-width reply: measurement period 100 ms and nav ratio 1.
    const GnssSetting rate[]={{0x30210001,100,2},{0x30210002,1,2}};
    const uint8_t frame[]={1,0,0,0,1,0,0x21,0x30,100,0,2,0,0x21,0x30,1,0};
    assert(matchesGnssSettings(frame,sizeof(frame),rate,2));
    auto old_rate=rate[0];old_rate.value=40;
    assert(!matchesGnssSettings(frame,sizeof(frame),&old_rate,1));
    assert(GNSS_RATE_SETTINGS[3].value==100 && GNSS_RATE_SETTINGS[4].value==1);
    for (unsigned i=0;i<GNSS_PROFILES.size();++i) {
        const auto &p=GNSS_PROFILES[i];
        assert(gnssProfileSupported(i,true));
        assert(gnssProfileSupported(i,false)==(i==GNSS_FALLBACK_PROFILE));
        assert(!(p.b1i && (p.b1c || p.glonass)));
        auto signals=gnssSignals(p);
        auto rates=gnssRateSettings(p);
        auto bytes=reply(rates.data(),rates.size());
        assert(rates[3].value==p.period_ms);
        assert(matchesGnssSettings(bytes.data(),bytes.size(),rates.data(),rates.size()));
        for (auto setting: signals) {
            if (setting.key==0x10310022) assert(setting.value==(p.b1i||p.b1c));
            if (setting.key==0x1031000d) assert(setting.value==p.b1i);
            if (setting.key==0x1031000f) assert(setting.value==p.b1c);
            if (setting.key==0x10310018) assert(setting.value==p.glonass);
        }
    }
    assert(!gnssProfileSupported(GNSS_PROFILES.size(),true));
    // Millisecond rounding stays BELOW 15 Hz and the manufacturer's 16 Hz maximum.
    assert(GNSS_PROFILES[1].period_ms==67 && 1000.0/GNSS_PROFILES[1].period_ms<15);
    std::cout<<"GNSS configuration tests passed\n";
}
