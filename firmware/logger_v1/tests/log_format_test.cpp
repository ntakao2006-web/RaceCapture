#include "../src/log_format.h"
#include <cassert>
#include <cstring>
#include <iostream>
int main() {
    char s[96];
    logger::logBaseName(s,sizeof(s),0x1234abcd,0,0);
    assert(!strcmp(s,"L1234ABCD_0000"));
    logger::logBaseName(s,sizeof(s),0x1234abcd,12,1788174000000000LL);
    assert(!strcmp(s,"20260831_200000_JST_L1234ABCD_0012"));
    // JST date boundary and identifiers: distinct reboots never share a name
    // just because their clocks resolve to the same whole second.
    logger::logBaseName(s,sizeof(s),1,3,1577890800000000LL);
    assert(!strcmp(s,"20200102_000000_JST_L00000001_0003"));
    logger::logBaseName(s,sizeof(s),2,3,1577890800000000LL);
    assert(strstr(s,"L00000002_0003"));
    logger::logBaseName(s,sizeof(s),1,0,-100);
    assert(!strcmp(s,"L00000001_0000"));
    std::cout<<"log filename tests passed\n";
}
