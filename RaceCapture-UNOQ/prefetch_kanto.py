"""One-shot Wi-Fi-only GSI z14 air-photo pack; resume-safe, bounded and rate-limited."""
import concurrent.futures,http.client,json,math,shutil,socket,ssl,threading,time
from pathlib import Path
import gi
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf

ROOT=Path('/home/arduino/ecocapture-v2-data/maps/gsi/seamlessphoto')
BOUNDS=(138.35,34.85,140.95,37.20) # mainland Kanto; border tiles include adjacent areas
HOST='cyberjapandata.gsi.go.jp'
LOCAL=threading.local()
class WifiHTTPS(http.client.HTTPSConnection):
    def connect(self):
        sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            sock.settimeout(20)
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_BINDTODEVICE,b'wlan0\0')
            sock.connect((HOST,443))
            self.sock=self._context.wrap_socket(sock,server_hostname=HOST)
        except BaseException:
            sock.close();raise
def tile(lon,lat,z):
    n=2**z
    return int((lon+180)/360*n),int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
def positions(z):
    west,south,east,north=BOUNDS
    x0,y0=tile(west,north,z);x1,y1=tile(east,south,z)
    return [(z,x,y) for y in range(y0,y1+1) for x in range(x0,x1+1)]
def path(z,x,y):return ROOT/str(z)/str(x)/(str(y)+'.jpg')
def fetch(item):
    z,x,y=item;p=path(z,x,y)
    if p.exists():
        try:
            im=GdkPixbuf.Pixbuf.new_from_file(str(p));assert im.get_width()==256 and im.get_height()==256
            return 'cached',p.stat().st_size
        except Exception:pass
    if shutil.disk_usage(ROOT).free<2*1024**3:raise RuntimeError('Less than 2 GiB free; stopped')
    p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.part')
    url=f'/xyz/seamlessphoto/{z}/{x}/{y}.jpg'
    for attempt in range(4):
        start=time.monotonic()
        # Strict interface binding. It fails rather than falling back to LTE.
        status=0;body=b''
        try:
            if not getattr(LOCAL,'connection',None):LOCAL.connection=WifiHTTPS(HOST,timeout=20,context=ssl.create_default_context())
            LOCAL.connection.request('GET',url,headers={'User-Agent':'EcoCapture-offline-pack/1.0'})
            response=LOCAL.connection.getresponse();status=response.status;body=response.read(2*1024*1024)
        except Exception:
            if getattr(LOCAL,'connection',None):LOCAL.connection.close()
            LOCAL.connection=None
        time.sleep(max(0,.2-(time.monotonic()-start)))
        if status==200:
            try:
                temp.write_bytes(body)
                im=GdkPixbuf.Pixbuf.new_from_file(str(temp));assert im.get_width()==256 and im.get_height()==256
                temp.replace(p);return 'downloaded',p.stat().st_size
            except Exception:pass
        if status==404:
            temp.unlink(missing_ok=True);return 'unavailable',0
        time.sleep(min(30,2**attempt*2))
    temp.unlink(missing_ok=True)
    return 'failed',0
def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    todo=positions(14);state={'bounds':BOUNDS,'source_zoom':14,'total':len(todo),'done':0,'bytes':0,'downloaded':0,'cached':0,'unavailable':0,'failed':0,'state':'downloading','interface':'wlan0'}
    def save():
        p=ROOT/'pack-status.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(state));t.replace(p)
    print(json.dumps(state),flush=True);save()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result,size in pool.map(fetch,todo):
            state[result]+=1;state['done']+=1;state['bytes']+=size
            if state['done']%100==0:save();print(json.dumps(state),flush=True)
    if state['failed']:
        state['state']='incomplete';save();raise SystemExit('Retry required; failed downloads retained in status')
    state['state']='building_overviews';save()
    for z in range(13,1,-1):
        for _,x,y in positions(z):
            p=path(z,x,y);p.parent.mkdir(parents=True,exist_ok=True)
            canvas=GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB,False,8,512,512);canvas.fill(0x242b2eff);found=False
            for dx in range(2):
                for dy in range(2):
                    child=path(z+1,x*2+dx,y*2+dy)
                    if child.exists():
                        im=GdkPixbuf.Pixbuf.new_from_file(str(child));im.copy_area(0,0,256,256,canvas,dx*256,dy*256);found=True
            if found:
                temp=p.with_suffix('.part');canvas.scale_simple(256,256,GdkPixbuf.InterpType.BILINEAR).savev(str(temp),'jpeg',['quality'],['85']);temp.replace(p)
    state['state']='complete';state['stored_bytes']=sum(p.stat().st_size for p in ROOT.rglob('*.jpg'));save();print(json.dumps(state),flush=True)
if __name__=='__main__':main()
