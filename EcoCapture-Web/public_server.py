"""Read-only viewer. Only receives sanitized telemetry; no config, logs, Bridge or admin socket mounts."""
import json
import os
import time
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

SNAPSHOT=Path(os.environ.get('ECOCAPTURE_PUBLIC_DATA','/telemetry'))/'telemetry.json'
app=FastAPI(title='EcoCapture Web Viewer',docs_url=None,redoc_url=None,openapi_url=None)


def snapshot():
    try:
        result=json.loads(SNAPSHOT.read_text())
        age=time.monotonic()-result.pop('_exported_monotonic',0)
        if age<0 or age>3:
            result['sample']=None;result['status']['connected']=False;result['status']['receive_hz']=0
            result['status']['logging']['active']=None
        return result
    except (OSError,ValueError,KeyError):
        return {'type':'telemetry','status':{'device':'EcoLogger V2','connected':False,'receive_hz':0,'logging':{'active':None}},'sample':None}


@app.middleware('http')
async def readonly(request:Request,call_next):
    if request.method not in ('GET','HEAD'):
        return JSONResponse({'detail':'閲覧専用です'},status_code=403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://cyberjapandata.gsi.go.jp; connect-src 'self'; frame-ancestors 'none'"
    return response


@app.get('/api/telemetry')
def telemetry():return snapshot()


app.mount('/',StaticFiles(directory=Path(__file__).parent/'public',html=True),name='viewer')
