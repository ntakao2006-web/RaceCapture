"""SIM7070 AT socket transport over the existing, serialized RouterBridge.

No PPP or Linux internet route. 18-byte RPC chunks fit the MCU's 64-byte RX ring.
AT text and Podium keys are never logged or exposed in status.
"""
import asyncio
import json
import re
import time

class LTEUART:
    def __init__(self,bridge):self.bridge=bridge;self.overflow=None
    async def power(self,on):
        if await self.bridge.call('logger.ltex',['P1' if on else 'P0'])!=0:raise OSError('LTE power command rejected')
        if not on:
            until=time.monotonic()+2
            while json.loads(await self.bridge.call('logger.lter'))['power']:
                if time.monotonic()>until:raise TimeoutError('LTE power off timeout')
                await asyncio.sleep(.01)
    async def read(self):
        status=json.loads(await self.bridge.call('logger.lter'))
        if self.overflow is None:self.overflow=status['overflows']
        if status['overflows']!=self.overflow:raise OSError('LTE receive overflow')
        return bytes.fromhex(status['rx'])
    async def write(self,data):
        for at in range(0,len(data),18):
            chunk=data[at:at+18].hex();until=time.monotonic()+5
            while True:
                rc=await self.bridge.call('logger.ltex',[chunk])
                if rc==0:break
                if rc!=-1 or time.monotonic()>until:raise OSError('LTE UART transmit rejected')
                await asyncio.sleep(.005)

class SIM7070:
    def __init__(self,bridge=None,uart=None):
        self.uart=uart or LTEUART(bridge);self.buffer=bytearray();self.stream=bytearray();self.sent=0
        # Seconds spent in each connect phase, and the modem's network-mode settings
        # (power-on to telemetry took 2+ min on 2026-10-19; this shows where).
        self.timings={};self.modem={};self._phase_at=None
        self.phase='idle'
        self.operation='idle'
    @property
    def phase(self):return self._phase
    @phase.setter
    def phase(self,value):
        now=time.monotonic()
        if self._phase_at is not None:self.timings[self._phase]=round(self.timings.get(self._phase,0)+now-self._phase_at,1)
        self._phase=value;self._phase_at=now
    async def pump(self):
        self.buffer.extend(await self.uart.read())
        if len(self.buffer)>16384:raise OSError('Modem response too large')
        # An unsolicited socket/PDP closure is fatal even during another command.
        if b'+CASTATE: 0,0' in self.buffer or b'+APP PDP: 0,DEACTIVE' in self.buffer:
            raise ConnectionError('Cellular connection closed')
    async def wait(self,marker,timeout=5):
        until=time.monotonic()+timeout
        while True:
            if marker in self.buffer:return bytes(self.buffer)
            if b'\r\nERROR\r\n' in self.buffer or b'+CME ERROR:' in self.buffer:raise OSError('Modem rejected operation')
            if time.monotonic()>=until:raise TimeoutError('Modem response timeout')
            await self.pump();await asyncio.sleep(.01)
    async def command(self,text,timeout=5):
        self.operation=text.split('=')[0].split('?')[0]
        self.buffer.clear()
        await self.uart.write(text.encode('ascii')+b'\r')
        return await self.wait(b'\r\nOK\r\n',timeout)
    async def connect(self,config,endpoint=None):
        # endpoint=(host,port,tls) for the relay server; default is Podium itself.
        host,port,tls=endpoint or (config.host,config.port,False)
        self.phase='modem_initialization'
        await self.uart.power(True)
        await asyncio.sleep(3)
        # Autobaud synchronization; no persistent baud setting is changed here.
        for attempt in range(5):
            try:await self.command('AT');break
            except (OSError,TimeoutError):
                if attempt==4:raise
        await self.command('ATE0')
        for query in ('AT+CNMP?','AT+CMNB?'):
            # Which radio access technologies the modem searches.
            with __import__('contextlib').suppress(OSError,TimeoutError):
                match=re.search(rb'\+(CNMP|CMNB):\s*(\d+)',await self.command(query))
                if match:self.modem[match[1].decode().lower()]=int(match[2])
        await self.command('AT+IFC=2,2')
        await self.command('AT+CFUN=0',10)
        # Search LTE-M only (user decision 2026-10-20). As delivered the modem also
        # scans GSM and NB-IoT (CNMP 51, CMNB 3): Japan has no GSM, the SIM is used on
        # LTE-M only, and Germany's carriers have LTE-M, so those scans only delay
        # attach after a move. The modem keeps these settings; written only on change.
        for setting,value in (('cnmp',38),('cmnb',1)):
            if self.modem.get(setting)!=value:
                with __import__('contextlib').suppress(OSError,TimeoutError):
                    await self.command(f'AT+{setting.upper()}={value}')
                    self.modem[f'{setting}_set']=value
        await self.command(f'AT+CGDCONT=1,"IP","{config.apn}"')
        await self.command('AT+CFUN=1',15)
        # CFUN=1 returns before the SIM is ready on the real SIM7070G.
        until=time.monotonic()+20
        self.phase='sim_ready'
        while True:
            try:sim=await self.command('AT+CPIN?')
            except OSError:
                # During SIM startup this firmware reports plain ERROR.
                # Do not hide transport faults, PIN/PUK requirements, or CME errors.
                if b'\r\nERROR\r\n' not in self.buffer or time.monotonic()>until:raise
                await asyncio.sleep(.5)
                continue
            if re.search(rb'\+CPIN:\s*READY\b',sim):break
            if b'SIM PIN' in sim or b'SIM PUK' in sim:raise OSError('SIM locked')
            if time.monotonic()>until:raise OSError('SIM unavailable')
            await asyncio.sleep(.5)
        until=time.monotonic()+150
        self.phase='network_registration'
        while True:
            attached=await self.command('AT+CGATT?')
            if re.search(rb'\+CGATT:\s*1\b',attached):break
            if time.monotonic()>until:raise TimeoutError('Network registration timeout')
            await asyncio.sleep(1)
        # Firmware 1951B14 rejects these during RF/SIM initialization.
        await self.command('AT+CPSMS=0')
        self.phase='pdp_activation'
        await self.command('AT+CEDRXS=0')
        cnc=f'AT+CNCFG=0,1,"{config.apn}"'
        if config.username or config.password:cnc+=f',"{config.username}","{config.password}",1'
        await self.command(cnc)
        await self.command('AT+CNACT=0,1',30)
        until=time.monotonic()+30
        while True:
            pdp=await self.command('AT+CNACT?')
            if re.search(rb'\+CNACT:\s*0,1,"(?!0\.0\.0\.0)[^"]+"',pdp):break
            if time.monotonic()>until:raise TimeoutError('PDP activation timeout')
            await asyncio.sleep(1)
        if tls:
            # TLS runs inside the modem. These settings are the ones the team's
            # ecorun-talk uses against Tailscale Funnel (TLS 1.2, ECDHE-ECDSA-
            # AES128-GCM); the server certificate is not verified (no CA loaded).
            await self.command('AT+CSSLCFG="SSLVERSION",0,3')
            await self.command('AT+CSSLCFG="IGNORERTCTIME",0,1')
            await self.command(f'AT+CSSLCFG="SNI",0,"{host}"')
            await self.command('AT+CSSLCFG="CIPHERSUITE",0,0,0xC02B')
            await self.command('AT+CASSLCFG=0,"SSL",1')
            await self.command('AT+CASSLCFG=0,"CRINDEX",0')
        else:await self.command('AT+CASSLCFG=0,"SSL",0')
        self.phase='relay_connect' if endpoint else 'podium_tcp_connect'
        await self.command(f'AT+CAOPEN=0,0,"TCP","{host}",{port}',30)
        response=await self.wait(b'+CAOPEN:',30)
        # URC may follow the final OK or be fragmented across UART reads.
        until=time.monotonic()+30
        while not re.search(rb'\+CAOPEN:\s*0,\d+\r\n',response):
            if time.monotonic()>until:raise TimeoutError('Socket open response timeout')
            await self.pump();response=bytes(self.buffer);await asyncio.sleep(.01)
        if not re.search(rb'\+CAOPEN:\s*0,0\r\n',response):raise OSError('Socket open failed')
        self.phase='relay_handshake' if endpoint else 'podium_authentication'
    async def send(self,data):
        # One TCP stream message can span multiple CASENDs, including large meta.
        for at in range(0,len(data),1024):
            self.operation='AT+CASEND'
            part=data[at:at+1024]
            self.buffer.clear()
            await self.uart.write(f'AT+CASEND=0,{len(part)}\r'.encode('ascii'))
            await self.wait(b'>',10)
            self.buffer.clear();await self.uart.write(part)
            await self.wait(b'\r\nOK\r\n',15)
        self.sent+=1
        if self.sent%100==0:
            state=await self.command('AT+CASTATE?')
            if not re.search(rb'\+CASTATE:\s*0,1\b',state):raise ConnectionError('Socket no longer connected')
    async def receive(self,until):
        response=await self.command('AT+CARECV=0,512')
        # SIMCom V1.03 uses +CARECV: <length>,<raw payload>, not a line string.
        match=re.search(rb'\+CARECV:\s*(\d+),',response)
        if not match:return b''
        n=int(match[1])
        if n>512:raise ValueError('Invalid socket receive length')
        while len(self.buffer)<match.end()+n:
            if time.monotonic()>until:raise TimeoutError('Truncated socket payload')
            await self.pump()
        return bytes(self.buffer[match.end():match.end()+n])
    async def read_some(self,wait=0):
        # One AT+CARECV poll; `wait` only mirrors the socket transport's signature.
        data=bytes(self.stream)+await self.receive(time.monotonic()+20);self.stream.clear()
        return data
    async def readline(self):
        until=time.monotonic()+20
        while b'\n' not in self.stream:
            self.stream.extend(await self.receive(until))
            if len(self.stream)>4096:raise ValueError('Podium response too large')
            if time.monotonic()>until:raise TimeoutError('Podium auth response timeout')
            await asyncio.sleep(.05)
        end=self.stream.index(b'\n')+1
        result=bytes(self.stream[:end]);del self.stream[:end];return result
    async def close(self):
        # Also clears partial CASEND input and power-key state after cancellation.
        await self.uart.power(False)
