from pathlib import Path
import shutil
src=Path('/home/arduino/ecologger_v2');dst=Path('/home/arduino/hardware-check-20261003/ecologger_bench')
shutil.copytree(src,dst,dirs_exist_ok=True)
(dst/'ecologger_v2.ino').rename(dst/'ecologger_bench.ino')
shutil.copy('/home/arduino/hardware-check-20261003/can_bench.h',dst/'can_bench.h')
p=dst/'logger_impl.h';s=p.read_text();s=s.replace('static void execute(String c){','\n#include "can_bench.h"\nstatic void execute(String c){if(c.startsWith("BENCH")){benchBegin(strtoul(c.c_str()+5,nullptr,10));completed++;return;}if(c=="END"){benchEnd();completed++;return;}')
s=s.replace('can1Poll();can2Poll();static uint32_t st=0;','can1Poll();can2Poll();benchTick();static uint32_t st=0;');p.write_text(s)
p=dst/'build.sh';s=p.read_text().replace('BUILD="$ROOT/ecologger_v2_build"','BUILD="$ROOT/hardware-check-20261003/bench_build"').replace('"$ROOT/ecologger_v2"','"$ROOT/hardware-check-20261003/ecologger_bench"').replace('ecologger_v2.ino.elf','ecologger_bench.ino.elf');p.write_text(s)
