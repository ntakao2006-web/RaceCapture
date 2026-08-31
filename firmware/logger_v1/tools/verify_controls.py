"""Explicit desk test of scripts and recording control; restores the original script.

Adds one temporary metadata channel until the next reboot. Does not change CAN/track settings.
"""
import argparse
import json
import time
from pathlib import Path
from rcp_client import Client, decode_sample


def upload(client, text):
    # Our test text is ASCII; preserve arbitrary original UTF-8 scripts at byte boundaries.
    pages, page = [], ''
    for char in text:
        if len((page + char).encode('utf-8')) > 256:
            pages.append(page)
            page = ''
        page += char
    pages.append(page)
    for i, page in enumerate(pages):
        reply = client.query({'setScriptCfg': {'page': i, 'mode': 2 if i == len(pages)-1 else 1, 'data': page}})
        assert reply['setScriptCfg']['rc'] == 1, reply


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='COM10')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    client = Client(args.port)
    original = client.query({'getScriptCfg': None})['scriptCfg']['data']
    before = client.query({'getStatus': None})['status']
    was_logging = before['logging']['status'] == 1
    report = {'checks': {}}
    try:
        assert not original, 'Refusing to replace an existing user script in this desk test'
        script = 'local ch=addChannel("DeskCounter",50,0,0,100000,"count")\nlocal n=0\nfunction onTick() n=n+1; setChannel(ch,n) end\n'
        upload(client, script)
        time.sleep(1)
        a, meta = decode_sample(client.query({'s': {'meta': True}}), [])
        time.sleep(1)
        b, _ = decode_sample(client.query({'s': {'meta': True}}), meta)
        report['checks']['lua_counter_and_65th_channel'] = b.get('DeskCounter', 0) > a.get('DeskCounter', 0) > 0 and len(meta) == 65
        report['counter'] = [a.get('DeskCounter'), b.get('DeskCounter')]
        upload(client, 'function onTick() while true do end end\n')
        time.sleep(.5)
        failed = client.query({'getStatus': None})['status']
        time.sleep(1)
        continued = client.query({'getStatus': None})['status']
        report['checks']['lua_timeout_isolated'] = not failed['luaOK'] and 'deadline' in failed['luaError']
        report['checks']['sd_and_imu_continue_after_lua_fault'] = continued['logging']['rows'] > failed['logging']['rows'] + 90 and continued['imuSamples'] > failed['imuSamples'] + 90
        upload(client, original)
        time.sleep(.3)
        report['checks']['lua_recovers'] = client.query({'getStatus': None})['status']['luaOK']
        # Closing the PC port does not request a recording stop.
        count = client.query({'getStatus': None})['status']['logging']['rows']
        client.close()
        time.sleep(2)
        client = Client(args.port)
        after = client.query({'getStatus': None})['status']
        report['checks']['recording_without_pc_connection'] = after['logging']['rows'] >= count + 190
        client.query({'setLogging': False})
        time.sleep(.3)
        stopped = client.query({'getStatus': None})['status']['logging']
        time.sleep(.4)
        stopped2 = client.query({'getStatus': None})['status']['logging']
        report['checks']['recording_stop'] = stopped['status'] == 0 and stopped['rows'] == stopped2['rows']
        client.query({'setLogging': True})
        time.sleep(.4)
        resumed = client.query({'getStatus': None})['status']['logging']
        report['checks']['recording_resume'] = resumed['status'] == 1 and resumed['rows'] > stopped2['rows']
        report['checks']['config_save'] = client.query({'flashCfg': None})['flashCfg']['rc'] == 1
        report['config'] = client.query({'getLoggerCfg': None})['loggerCfg']
        report['after'] = client.query({'getStatus': None})['status']
        print(json.dumps(report, indent=2), flush=True)
        assert all(report['checks'].values()), 'Control verification failed'
    finally:
        try:
            upload(client, original)
            client.query({'setLogging': was_logging})
        finally:
            client.close()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
