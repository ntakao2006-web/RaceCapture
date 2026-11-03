import asyncio
import json
import time
import unittest
from rcp_bridge import Source, build_meta, channel, client

class Samples(unittest.TestCase):
    def test_defi_voltage_channels_and_state(self):
        config={'signals':[{'name':'OilTemp','unit':'°C','conversion':'sensorhub_oiltemp'},
            {'name':'PressVolt','unit':'V','conversion':'defi_volt','scale':5/4095,'offset':0.0}]}
        meta={c['nm']:c for c in build_meta(config,[{'name':'RPM','unit':'rpm'}])}
        self.assertEqual([n for n in meta if 'Oil' in n or 'Press' in n],['OilTemp','OilTempState','OilTempOpen','PressVolt','PressVoltState'])
        self.assertEqual((meta['PressVolt']['min'],meta['PressVolt']['max'],meta['PressVolt']['prec'],meta['PressVolt']['ut']),(0.0,5.0,3,'V'))
        self.assertEqual((meta['PressVoltState']['min'],meta['PressVoltState']['max'],meta['PressVoltState']['prec']),(0,4,0))
        # Near a rail the voltage is still sent, with its state.
        s=Source();s.updated=time.monotonic();s.meta=[meta['PressVolt'],meta['PressVoltState']]
        s.frame={'status':{'connected':True},'sample':{'can_signals':{'PressVolt':0.0,'PressVoltState':1}}}
        self.assertEqual(s.sample()['s']['d'],[0.0,1,3])
        s.frame['sample']['can_signals']={'PressVolt':None,'PressVoltState':4}
        self.assertEqual(s.sample()['s']['d'],[4,2])
    def test_open_sensor_masks_temperature_but_keeps_fault_channels(self):
        s=Source();s.updated=time.monotonic()
        s.meta=[channel('OilTemp'),channel('OilTempState'),channel('OilTempOpen')]
        s.frame={'status':{'connected':True},'sample':{'mcu_ms':42,'can_signals':{'OilTemp':None,'OilTempState':1,'OilTempOpen':1}}}
        self.assertEqual(s.sample()['s']['d'],[1,1,6])
    def test_sparse_masks_cross_32_channels(self):
        s=Source();s.meta=[channel('c'+str(i)) for i in range(65)]
        s.frame={'status':{'connected':True},'sample':{'mcu_ms':42,'values':{'c0':1,'c32':2,'c64':3,'c2':None,'c3':float('nan')}}}
        s.updated=time.monotonic()
        self.assertEqual(s.sample()['s'],{'t':42,'d':[1,2,3,1,1,1]})
    def test_stale_source_never_replays_valid_values(self):
        s=Source();s.meta=[channel('RPM')]
        s.frame={'status':{'connected':True},'sample':{'values':{'RPM':1234}}}
        self.assertEqual(s.sample()['s']['d'],[0])
        s.updated=time.monotonic();s.frame['status']['connected']=False
        self.assertEqual(s.sample()['s']['d'],[0])
    def test_lap_timer_and_utc_channels(self):
        s=Source();s.updated=time.monotonic()
        s.meta=[channel(n) for n in ('LapCount','LapTime','BestLap','ElapsedTime','SessionTime','Utc')]
        s.frame={'status':{'connected':True},'sample':{'host_utc':'2026-11-08T01:30:00+00:00',
            'gnss_utc':'2026-11-08T01:30:01Z','lap':{'LapCount':3,'LapTime':1.75,'BestLap':1.7,
            'ElapsedTime':None,'RaceTime':12.5}}}
        # ElapsedTime is missing before the first crossing; Utc prefers the GNSS time.
        self.assertEqual(s.sample()['s']['d'],[3,1.75,1.7,12.5,1794101401000.0,0b110111])
        self.assertEqual(channel('SessionTime')['prec'],4)
    def test_no_fix_is_missing_not_zero_position(self):
        s=Source();s.updated=time.monotonic();s.meta=[channel('Lat'),channel('GPSFix')]
        s.frame={'status':{'connected':True},'sample':{'values':{'Lat':None,'GPSFix':0}}}
        self.assertEqual(s.sample()['s']['d'],[0,2])
        self.assertEqual(s.status()['status']['GPS']['lat'],0)
        self.assertEqual(s.status()['status']['GPS']['qual'],0)

class Protocol(unittest.IsolatedAsyncioTestCase):
    async def test_real_socket_cr_lf_and_unsupported_write(self):
        source=Source()
        server=await asyncio.start_server(lambda r,w:client(r,w,source),'127.0.0.1',0)
        async with server:
            r,w=await asyncio.open_connection('127.0.0.1',server.sockets[0].getsockname()[1])
            w.write(b'{"getVer":{}}\r{"flashCfg":{}}\r\n{"setTelemetry":{"rate":-1}}\n');await w.drain()
            self.assertIn('real sensors',json.loads(await r.readline())['ver']['fname'])
            self.assertEqual(json.loads(await r.readline())['flashCfg']['rc'],-1)
            self.assertEqual(json.loads(await r.readline())['setTelemetry']['rc'],-1)
            w.close();await w.wait_closed()

if __name__=='__main__':unittest.main()
