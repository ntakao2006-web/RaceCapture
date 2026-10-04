#include "../rpc_frame.h"
#include <cassert>
#include <vector>
#include <cstdio>
int main(){
 const std::vector<uint8_t> take={0x94,0,42,0xab,'l','o','g','g','e','r','.','t','a','k','e',0x90};
 for(size_t i=0;i<take.size();i++)assert(loggerRpcFrame(take.data(),i)==0);
 assert(loggerRpcFrame(take.data(),take.size())==(int)take.size());
 auto joined=take;joined.insert(joined.end(),take.begin(),take.end());
 assert(loggerRpcFrame(joined.data(),joined.size())==(int)take.size());
 const uint8_t nested[]={0x94,0,43,0xa1,'x',0x92,0x81,0xa1,'a',0x92,0xc0,0xc3,0xcc,128};
 for(size_t i=0;i<sizeof(nested);i++)assert(loggerRpcFrame(nested,i)==0);
 assert(loggerRpcFrame(nested,sizeof(nested))==sizeof(nested));
 const uint8_t oversized[]={0xdb,0xff,0xff,0xff,0xff};
 assert(loggerRpcFrame(oversized,sizeof(oversized))==-1);
 const uint8_t bad[]={0xc1};assert(loggerRpcFrame(bad,1)==-1);
 const uint8_t ext[]={0xc7,2,7,1,2};
 for(size_t i=0;i<sizeof(ext);i++)assert(loggerRpcFrame(ext,i)==0);
 assert(loggerRpcFrame(ext,sizeof(ext))==sizeof(ext));
 puts("PASS: complete, fragmented, concatenated, nested, invalid and oversized frames");
}
