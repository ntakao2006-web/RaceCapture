#pragma once
#include <stddef.h>
#include <stdint.h>

// Return a complete MessagePack object's size, 0 for incomplete, -1 for invalid.
// Do not invoke MsgPack::Unpacker on partial input: its feed() checks scalar
// boundaries, not whether all the children of an array/map have arrived.
inline int loggerRpcFrame(const uint8_t *p, size_t n, unsigned depth=0) {
    if(!n)return 0;
    if(depth>12)return -1;
    const unsigned c=p[0];
    size_t header=1,payload=0,children=0;
    unsigned lengthBytes=0;
    bool container=false,extension=false;
    if(c<=0x7f||c>=0xe0||c==0xc0||c==0xc2||c==0xc3)return 1;
    if((c&0xe0)==0xa0)payload=c&31;
    else if((c&0xf0)==0x90){children=c&15;container=true;}
    else if((c&0xf0)==0x80){children=2*(c&15);container=true;}
    else switch(c){
      case 0xc4:case 0xd9:lengthBytes=1;break;
      case 0xc5:case 0xda:lengthBytes=2;break;
      case 0xc6:case 0xdb:lengthBytes=4;break;
      case 0xc7:lengthBytes=1;extension=true;break;
      case 0xc8:lengthBytes=2;extension=true;break;
      case 0xc9:lengthBytes=4;extension=true;break;
      case 0xca:case 0xce:case 0xd2:payload=4;break;
      case 0xcb:case 0xcf:case 0xd3:payload=8;break;
      case 0xcc:case 0xd0:payload=1;break;
      case 0xcd:case 0xd1:payload=2;break;
      case 0xd4:payload=2;break;
      case 0xd5:payload=3;break;
      case 0xd6:payload=5;break;
      case 0xd7:payload=9;break;
      case 0xd8:payload=17;break;
      case 0xdc:case 0xde:lengthBytes=2;container=true;break;
      case 0xdd:case 0xdf:lengthBytes=4;container=true;break;
      default:return -1;
    }
    if(lengthBytes){
      if(n<1+lengthBytes)return 0;
      uint32_t length=0;
      for(unsigned i=0;i<lengthBytes;i++)length=(length<<8)|p[1+i];
      if(length>1024)return -1;
      header+=lengthBytes;
      if(container){children=length;if(c==0xde||c==0xdf)children*=2;}
      else payload=length+(extension?1:0);
    }
    if(header+payload>1024||children>1024)return -1;
    if(n<header+payload)return 0;
    size_t used=header+payload;
    for(size_t i=0;i<children;i++){
      int part=loggerRpcFrame(p+used,n-used,depth+1);
      if(part<=0)return part;
      used+=part;
      if(used>1024)return -1;
    }
    return (int)used;
}
