#include "../src/vehicle_obd.h"
#include <cassert>
#include <iostream>
using namespace logger;
static CanFrame reply(uint64_t t, uint32_t id, uint8_t pid, uint32_t bits) {
    CanFrame f{}; f.bus=1; f.us=t; f.id=id; f.dlc=8; f.data[0]=6;
    f.data[1]=0x41; f.data[2]=pid;
    f.data[3]=bits>>24; f.data[4]=bits>>16; f.data[5]=bits>>8; f.data[6]=bits;
    return f;
}
int main() {
    static_assert(sizeof(VehicleAcquisition)==8);
    VehicleAcquisition c; assert(validAcquisition(c)&&!c.obd_enabled); c.version=2; assert(!validAcquisition(c));
    ObdPoller p; p.reset(0); CanFrame q; ObdValue v;
    assert(!p.next(999999,q)&&p.next(1000000,q));
    assert(q.id==0x7e0&&q.tx&&q.data[0]==2&&q.data[1]==1&&q.data[2]==0&&q.dlc==8);
    assert(!p.next(1100000,q));
    auto f=reply(1010000,0x7e9,0,0xffffffff); assert(!p.receive(f,v)&&p.responses==0);
    f.id=0x7e8; f.data[0]=7; assert(!p.receive(f,v)); f.data[0]=6;
    assert(!p.receive(f,v)&&p.response_id==0x7e8&&p.responses==1);
    assert(p.next(1100000,q)&&q.data[2]==0x20);
    assert(!p.receive(reply(1110000,0x7e8,0x20,1),v));
    assert(p.next(1200000,q)&&q.data[2]==0x40);
    assert(!p.receive(reply(1210000,0x7e8,0x40,(1U<<30)|(1U<<4)),v));
    assert(!p.discovering&&p.supported==255);
    assert(p.next(1300000,q)&&q.data[2]==0x0c);
    f=reply(1310000,0x7e8,0x0c,0); f.data[0]=4;
    assert(p.receive(f,v)&&v.pid==0x0c&&v.value==0); // EV mode is valid zero, not missing.
    f.data[3]=0x0c; f.data[4]=0x80; assert(decodeObd(f,v)&&v.value==800);
    f.data[0]=3; assert(!decodeObd(f,v)); f.data[0]=4; f.dlc=4; assert(!decodeObd(f,v));
    f.dlc=8; f.extended=true; assert(!decodeObd(f,v)); f.extended=false; f.rtr=true; assert(!decodeObd(f,v));
    // Sustained mock ECU: max 10 requests/s; each supported PID gets scheduled.
    uint64_t previous=1300000; unsigned seen=0;
    for(uint64_t t=1400000;t<15000000;t+=10000) if(p.next(t,q)) {
        assert(t-previous>=100000); previous=t;
        f=reply(t+1000,0x7e8,q.data[2],0); f.data[0]=(q.data[2]==0x0c||q.data[2]==0x42)?4:3;
        assert(p.receive(f,v));
        for(size_t i=0;i<p.pids.size();++i) if(q.data[2]==p.pids[i].id) seen|=1U<<i;
    }
    assert(seen==255);
    // Missing ECU: functional fallback, bounded retries and five-second quiet window.
    p.reset(0); unsigned requests=0; bool functional=false; uint64_t largest_gap=0; previous=0;
    for(uint64_t t=0;t<20000000;t+=10000) if(p.next(t,q)) {
        ++requests; largest_gap=std::max(largest_gap,t-previous); previous=t; functional|=q.id==0x7df;
    }
    assert(functional&&requests<20&&largest_gap>=5000000&&p.responses==0);
    // Functional discovery ignores an ECU which does not advertise RPM.
    p.reset(0);
    for(uint64_t t=0;t<4000000;t+=10000) if(p.next(t,q)&&q.id==0x7df) {
        assert(!p.receive(reply(t+1,0x7e9,0,1),v)&&p.response_id==0);
        assert(!p.receive(reply(t+2,0x7ea,0,1U<<20),v)&&p.response_id==0x7ea);
        assert(!p.discovering&&p.supported==1); break;
    }
    assert(p.response_id==0x7ea&&p.request_id==0x7df);
    // Unsupported PIDs must not be requested; reject late and negative responses.
    assert(p.next(5000000,q)&&q.data[2]==0x0c);
    f=reply(5250000,0x7ea,0x0c,0);f.data[0]=4;assert(!p.receive(f,v));
    assert(!p.next(5250000,q)&&p.timeouts==4);
    assert(p.next(6000000,q)&&q.data[2]==0x0c);
    f=reply(6010000,0x7ea,0x0c,0);f.data[0]=3;f.data[1]=0x7f;f.data[2]=1;f.data[3]=0x12;
    assert(!p.receive(f,v)&&p.negative==1);
    assert(!p.next(6100000,q));
    p.reset(0);assert(p.next(1000000,q));p.txFailed(1000010);
    assert(p.tx_errors==1&&!p.next(1500000,q));
    // Signed Toyota 0x025, both signs/fraction and invalid sentinel.
    f=CanFrame{}; f.bus=1; f.id=0x25; f.dlc=8; double angle;
    f.data[1]=10; f.data[4]=0x30; assert(decodeToyotaSteering(f,angle)&&std::abs(angle-15.3)<1e-9);
    f.data[0]=0xf; f.data[1]=0xf6; f.data[4]=0xd0; assert(decodeToyotaSteering(f,angle)&&std::abs(angle+15.3)<1e-9);
    f.data[4]=0x80; assert(!decodeToyotaSteering(f,angle));
    f.data[0]=f.data[1]=f.data[4]=0; assert(decodeToyotaSteering(f,angle)&&angle==0);
    f.dlc=7; assert(!decodeToyotaSteering(f,angle)); f.dlc=8; f.id=0x260; assert(!decodeToyotaSteering(f,angle));
    CanFrame allowed{}; allowed.bus=1;allowed.tx=true;allowed.id=0x7e0;allowed.dlc=8;allowed.data[0]=2;allowed.data[1]=1;allowed.data[2]=0x0c;
    assert(allowedObdRequest(allowed));
    for(unsigned mode=0;mode<256;++mode) { auto bad=allowed;bad.data[1]=mode;assert(allowedObdRequest(bad)==(mode==1)); }
    for(unsigned id=0;id<2048;++id) {auto bad=allowed;bad.id=id;assert(allowedObdRequest(bad)==(id==0x7df||(id>=0x7e0&&id<=0x7e7)));}
    for(unsigned pid=0;pid<256;++pid) { auto bad=allowed;bad.data[2]=pid;bool ok=pid==0||pid==0x20||pid==0x40||pid==0x0c||pid==0x0d||pid==0x11||pid==4||pid==5||pid==0x0f||pid==0x42||pid==0x5c;assert(allowedObdRequest(bad)==ok); }
    auto bad=allowed;bad.extended=true;assert(!allowedObdRequest(bad));bad=allowed;bad.rtr=true;assert(!allowedObdRequest(bad));bad=allowed;bad.data[7]=1;assert(!allowedObdRequest(bad));bad=allowed;bad.dlc=7;assert(!allowedObdRequest(bad));
    FanProbe probe;probe.reset(0);assert(!probe.next(1999999,q));assert(probe.next(2000000,q)&&allowedObdRequest(q)&&q.data[2]==0x11&&q.data[3]==3);
    f=CanFrame{};f.bus=1;f.id=0x7e8;f.dlc=8;f.us=2010000;f.data[0]=4;f.data[1]=0x62;f.data[2]=0x11;f.data[3]=3;f.data[4]=12;
    probe.receive(f);assert(probe.responses==1&&probe.raw[0]==12&&!probe.busy(f.us));
    assert(probe.next(4010000,q)&&allowedObdRequest(q)&&q.data[2]==9&&q.data[3]==0x67);
    auto unsafe=q;unsafe.data[3]=0x68;assert(!allowedObdRequest(unsafe));unsafe=q;unsafe.data[1]=0x2e;assert(!allowedObdRequest(unsafe));unsafe=q;unsafe.id=0x7df;assert(!allowedObdRequest(unsafe));
    assert(!probe.busy(4260000)&&probe.timeouts==1);assert(!probe.next(4260010,q));
    std::cout<<"PASS vehicle OBD scheduling, discovery, response lock, functional routing, zero RPM, timeouts, steering\n";
}
