from pathlib import Path
p=Path('/home/arduino/hardware-check-20261003/ecologger_bench/logger_impl.h')
s=p.read_text();assert '#include "can_bench.h"' not in s
s=s.replace('static void execute(String c){','\n#include "can_bench.h"\nstatic void execute(String c){if(c.startsWith("BENCH")){benchBegin(strtoul(c.c_str()+5,nullptr,10));completed++;return;}if(c=="END"){benchEnd();completed++;return;}')
s=s.replace('can1Poll();can2Poll();static uint32_t st=0;','can1Poll();can2Poll();benchTick();static uint32_t st=0;');p.write_text(s)
