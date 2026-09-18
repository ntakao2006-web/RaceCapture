#include "../src/ncec.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <fstream>
#include <sstream>
#include <map>
using namespace logger;
int main(int argc, char **argv) {
    NcDecoder decoder; std::map<NcSignal,double> values;
    auto emit=[&](NcSignal s,double v){values[s]=v;};
    uint8_t wheels[]={0x27,0x10,0x2a,0xf8,0x2e,0xe0,0x32,0xc8};
    decoder.decode(0x4b0,wheels,8,1,emit);
    assert(values[NcWheelFL]==0 && values[NcWheelFR]==10 && values[NcWheelRL]==20 && values[NcWheelRR]==30);
    values.clear(); decoder.decode(0x4b0,wheels,7,2,emit); assert(values.empty());
    uint8_t d[]={0,0,0,0,0,0,1,0xff};
    decoder.decode(0x200,d,8,3,emit); assert(values[NcBrake]==1 && std::abs(values[NcPedal]-85.352)<1e-6);
    d[6]=0; decoder.decode(0x200,d,8,4,emit); assert(values[NcBrake]==0);
    d[6]=255;d[7]=0x40;decoder.decode(0x215,d,8,5,emit); assert(values[NcAc]==1 && values[NcPedalBackup]==values[NcPedal]);
    d[1]=4;decoder.decode(0x231,d,2,6,emit);assert(values[NcClutch]==0);
    d[1]=6;decoder.decode(0x231,d,2,7,emit);assert(values[NcClutch]==1);
    d[0]=8;decoder.decode(0x39a,d,1,8,emit);assert(values[NcParking]==1);
    d[1]=137;d[3]=31;d[4]=122;decoder.decode(0x240,d,5,9,emit);
    assert(values[NcWater]==97 && values[NcIntake]==82 && std::abs(values[NcThrottle]-11.8658)<1e-6);
    d[3]=0;decoder.decode(0x240,d,5,10,emit);assert(values[NcThrottle]==0);
    d[0]=0;decoder.decode(0x430,d,1,100,emit);
    d[0]=255;decoder.decode(0x430,d,1,100100,emit);assert(std::abs(values[NcFuel]-50)<1e-9);
    decoder.decode(0x430,d,1,3000100,emit);assert(std::abs(values[NcFuel]-100)<1e-9);
    d[0]=0;decoder.decode(0x430,d,1,1,emit);assert(values[NcFuel]==0);
    for(int i=0;i<10000;++i)decoder.decode(0x430,d,1,2+i,emit);
    assert(values[NcFuel]==0);
    if(argc>1) {
        std::ifstream input(argv[1]); std::string line;std::getline(input,line);unsigned count=0;
        while(std::getline(input,line)) {
            std::stringstream ss(line);std::string col[8];for(auto &c:col)std::getline(ss,c,',');
            if(col[7].size()<16)continue;
            uint8_t bytes[8];for(int i=0;i<8;++i)bytes[i]=std::stoul(col[7].substr(i*2,2),nullptr,16);
            decoder.decode(std::stoul(col[3],nullptr,16),bytes,std::stoul(col[6]),std::stoull(col[0]),emit);++count;
        }
        assert(count>1000 && values[NcWheelFL]==0 && values[NcWheelRR]==0);
        assert(values[NcFuelRaw]>40 && values[NcFuelRaw]<42);
        assert(values[NcClutch]==0 && values[NcAc]==1);
        std::cout<<"Real SD excerpt replay: "<<count<<" frames passed\n";
    }
    std::cout<<"NCEC decode, bounds, fuel smoothing and recovery passed\n";
}
