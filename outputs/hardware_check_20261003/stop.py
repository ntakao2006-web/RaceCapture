import asyncio,sys,json
sys.path.insert(0,'/app')
from telemetry_bridge import TelemetryBridge
async def main():
 b=TelemetryBridge();print(await b.command('LOG0'));print(await b.call('logger.status'));await b.close()
asyncio.run(main())
