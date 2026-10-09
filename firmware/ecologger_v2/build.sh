#!/bin/sh
set -eu
export TMPDIR=/tmp
ROOT=/home/arduino
BUILD="$ROOT/ecologger_v2_build"
# RouterBridge 0.3.0 default 500-byte update stack overflows under real telemetry.
python3 - <<'PY'
from pathlib import Path
import re
import shutil
p=Path("/home/arduino/.arduino15/packages/arduino/hardware/zephyr/0.52.0/libraries/Arduino_RouterBridge/src/bridge.h")
s=p.read_text();s=re.sub(r"UPDATE_THREAD_STACK_SIZE\s+\d+", "UPDATE_THREAD_STACK_SIZE    8192", s)
if 'LOGGER_BRIDGE_SERIAL_INIT_HOOK();' not in s:
    s=s.replace('        serial_ptr->begin(baud);','        serial_ptr->begin(baud);\n#ifdef LOGGER_BRIDGE_SERIAL_INIT_HOOK\n        LOGGER_BRIDGE_SERIAL_INIT_HOOK();\n#endif')
p.write_text(s)
p=Path("/home/arduino/.arduino15/packages/arduino/hardware/zephyr/0.52.0/libraries/Arduino_RPClite/src/request.h")
s=p.read_text().replace("(DECODER_BUFFER_SIZE / 4)","DECODER_BUFFER_SIZE")
p.write_text(s)
# RPClite's incremental parser must not feed incomplete arrays to MsgPack.
root=Path('/home/arduino/.arduino15/packages/arduino/hardware/zephyr/0.52.0/libraries/Arduino_RPClite/src')
shutil.copy('/home/arduino/ecologger_v2/rpc_frame.h',root/'logger_rpc_frame.h')
p=root/'decoder.h';s=p.read_text()
if '#include "logger_rpc_frame.h"' not in s:
    s=s.replace('#include "MsgPack.h"','#include "MsgPack.h"\n#include "logger_rpc_frame.h"')
begin=s.index('    void parse_packet(){')
end=s.index('    bool packet_incoming()',begin)
s=s[:begin]+'''    void parse_packet(){
        if(packet_incoming())return;
        while(_bytes_stored){
            if(_raw_buffer[0]!=0x93 && _raw_buffer[0]!=0x94){
                consume(1);_discarded_packets++;continue;
            }
            int size=loggerRpcFrame(_raw_buffer,_bytes_stored);
            if(size==0 && !buffer_full())return;
            if(size<=0){consume(1);_discarded_packets++;continue;}
            MsgPack::Unpacker unpacker;
            size_t count=0;int type=NO_MSG;
            if(!unpacker.feed(_raw_buffer,size) || !unpackTypedArray(unpacker,count,type)
               || (type!=CALL_MSG && type!=RESP_MSG && type!=NOTIFY_MSG)
               || count!=(type==NOTIFY_MSG?NOTIFY_SIZE:REQUEST_SIZE)){
                consume(size);_discarded_packets++;continue;
            }
            _packet_type=type;_packet_size=size;return;
        }
    }

'''+s[end:]
p.write_text(s)
# Bound each MCU-to-Linux UART burst below the GENI DMA buffer size. The
# installed Linux driver can stop RX permanently on a zero-length DMA event.
# Flush + an inter-burst idle lets Linux finish the short DMA transfer before
# more bytes arrive, without reducing the 100 Hz acquisition rate.
p=root/'SerialTransport.h';s=p.read_text()
if '#include <zephyr/kernel.h>' not in s:
    s=s.replace('#include "transport.h"','#include "transport.h"\n#include <zephyr/kernel.h>')
old='''            _stream->write(data, size);
            return size;'''
new='''            size_t sent = 0;
            while(sent < size) {
                size_t chunk = size - sent;
                if(chunk > 127) chunk = 127;
                size_t written = _stream->write(data + sent, chunk);
                sent += written;
                _stream->flush();
                k_usleep(250);
                if(written != chunk) break;
            }
            return sent;'''
if old in s:s=s.replace(old,new)
elif new not in s:raise RuntimeError('Unexpected SerialTransport write implementation')
p.write_text(s)
PY
arduino-cli compile -b arduino:zephyr:unoq --libraries "$ROOT/ecologger_v2_libraries" --output-dir "$BUILD" "$ROOT/ecologger_v2"
"$ROOT/.arduino15/packages/zephyr/tools/arm-zephyr-eabi/0.16.8/bin/arm-zephyr-eabi-objcopy" -G setup -G loop "$BUILD/ecologger_v2.ino.elf" "$BUILD/logger_compact.elf"
"$ROOT/.arduino15/packages/zephyr/tools/arm-zephyr-eabi/0.16.8/bin/arm-zephyr-eabi-strip" --strip-unneeded "$BUILD/logger_compact.elf"
python3 "$ROOT/ecologger_v2/compact_symbols.py" "$ROOT/.arduino15/packages/zephyr/tools/arm-zephyr-eabi/0.16.8/bin/arm-zephyr-eabi-" "$BUILD/logger_compact.elf" "$BUILD/logger_short.elf"
mv "$BUILD/logger_short.elf" "$BUILD/logger_compact.elf"
"$ROOT/.arduino15/packages/arduino/tools/zephyr-sketch-tool/0.2.0/zephyr-sketch-tool" "$BUILD/logger_compact.elf"
SIZE=$(wc -c < "$BUILD/logger_compact.elf-zsk.bin")
test "$SIZE" -le 65536 || { echo "Installed sketch partition is 64 KiB; image is $SIZE bytes"; exit 1; }
python3 "$ROOT/ecologger_v2/audit_image.py" "$BUILD/logger_compact.elf-zsk.bin" --output "$BUILD/image-audit.json"
python3 "$ROOT/ecologger_v2/compare_sources.py" --output "$BUILD/source-manifest.json"
echo "Ready: $BUILD/logger_compact.elf-zsk.bin ($SIZE bytes)"
# Flash separately; do not interrupt voltage measurements or an SD write.
