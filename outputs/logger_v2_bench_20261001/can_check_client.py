import asyncio,json
from telemetry_bridge import TelemetryBridge
async def main():
 b=TelemetryBridge()
 print(await b.call('logger.command',['TEST']),flush=True)
 await asyncio.sleep(6)
 print(await b.call('logger.status'))
 await b.close()
asyncio.run(main())
