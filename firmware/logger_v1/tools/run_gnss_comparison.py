"""Run equal warmup/measurement windows on the connected logger.

Requires the stack-corrected h firmware or later and A105 plus native USB.
Close RaceCapture and its guard first. No deletion, OTP, NVS or CAN writes.
The last tested profile remains active in RAM; SD recording continues.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from gnss_profile import select
from rcp_client import Client


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profiles',nargs='+',default=['four_10','b1c_15','glo_15'])
    p.add_argument('--port',default='COM8')
    p.add_argument('--download-port',default='COM10')
    p.add_argument('--warmup',type=float,default=120)
    p.add_argument('--seconds',type=float,default=180)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.warmup<0 or args.seconds<10: p.error('Invalid window length')
    args.output.mkdir(parents=True,exist_ok=False)
    for i,profile in enumerate(args.profiles):
        folder=args.output/f'{i+1:02d}_{profile}'
        folder.mkdir()
        client=Client(args.port); warmup=[]
        try:
            version=client.query({'getVer':None})['ver']['git_info']
            if version not in {'logger-v1-gnss-compare-20260901h',
                               'logger-v1-gnss-stream-20260901i'}:
                raise RuntimeError('Use the communication-stack-corrected comparison firmware')
            cfg=select(client,profile)
            print(json.dumps({'phase':'warmup','profile':profile,'configuration':cfg}),flush=True)
            start=time.monotonic(); next_print=start
            while time.monotonic()-start<args.warmup:
                diag=client.query({'getGnssDiagnostics':None})['getGnssDiagnostics']
                status=client.query({'getStatus':None})['status']
                row={'elapsed':time.monotonic()-start,'diagnostics':diag,'status':status}
                warmup.append(row)
                if time.monotonic()>=next_print:
                    print(json.dumps({'phase':'warmup','profile':profile,'elapsed':round(row['elapsed']),
                        'fix':status['GPS']['qual'],'sats':status['GPS']['sats'],
                        'systems':diag.get('satellites',{}).get('systems',[])}),flush=True)
                    next_print=time.monotonic()+30
                time.sleep(1)
        finally:
            client.close()
            (folder/'warmup.json').write_text(json.dumps(warmup,indent=2),encoding='utf-8')
        print(json.dumps({'phase':'measure','profile':profile,'seconds':args.seconds}),flush=True)
        with (folder/'measurement_console.txt').open('w',encoding='utf-8') as output:
            subprocess.run([sys.executable,'-X','utf8',str(Path(__file__).with_name('verify_gnss_health.py')),
                '--port',args.port,'--download-port',args.download_port,'--seconds',str(args.seconds),
                '--comparison-report','--output',str(folder)],stdout=output,stderr=subprocess.STDOUT,check=True)
        report=json.loads((folder/'verification.json').read_text())
        print(json.dumps({'phase':'complete','profile':profile,'checks':report['checks'],
                          'gnss':report['gnss'],'systems':report.get('satellite_systems_max_used')}),flush=True)


if __name__=='__main__':main()
