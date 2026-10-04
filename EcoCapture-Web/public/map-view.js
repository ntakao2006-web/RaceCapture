'use strict';
// Web Mercator camera shared by GSI XYZ imagery and telemetry.
const MapCamera = (() => {
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  function project(lon,lat){const s=Math.sin(clamp(lat,-85.05112878,85.05112878)*Math.PI/180);return [(lon+180)/360,.5-Math.log((1+s)/(1-s))/(4*Math.PI)];}
  function unproject(x,y){return [x*360-180,Math.atan(Math.sinh(Math.PI*(1-2*y)))*180/Math.PI];}
  function delta(x,center){let d=x-center;return d-Math.round(d);}
  class Camera {
    constructor(){this.center=project(135,35);this.zoom=16;this.width=800;this.height=500;}
    resize(w,h){this.width=w;this.height=h;}
    screen(lon,lat){const p=project(lon,lat),s=256*2**this.zoom;return [this.width/2+delta(p[0],this.center[0])*s,this.height/2+(p[1]-this.center[1])*s];}
    zoomAt(amount,x=this.width/2,y=this.height/2){const before=256*2**this.zoom,z=clamp(this.zoom+amount,2,22),after=256*2**z;this.center[0]+=(x-this.width/2)*(1/before-1/after);this.center[1]+=(y-this.height/2)*(1/before-1/after);this.zoom=z;this.normalize();}
    pan(dx,dy){const s=256*2**this.zoom;this.center[0]-=dx/s;this.center[1]-=dy/s;this.normalize();}
    normalize(){this.center[0]=(this.center[0]%1+1)%1;this.center[1]=clamp(this.center[1],0,1);}
    fit(points){if(!points.length)return;const ref=project(...points[0])[0],p=points.map(a=>{const v=project(...a);return [ref+delta(v[0],ref),v[1]];});let x0=Infinity,x1=-Infinity,y0=Infinity,y1=-Infinity;for(const a of p){x0=Math.min(x0,a[0]);x1=Math.max(x1,a[0]);y0=Math.min(y0,a[1]);y1=Math.max(y1,a[1]);}this.center=[(x0+x1)/2,(y0+y1)/2];this.zoom=clamp(Math.log2(Math.min(Math.max(1,this.width-100)/Math.max(1e-8,x1-x0),Math.max(1,this.height-100)/Math.max(1e-8,y1-y0))/256),2,19);this.normalize();}
  }
  return {Camera,project,unproject};
})();
if(typeof module!=='undefined')module.exports=MapCamera;

if(typeof window!=='undefined'){
window.EcoMap = class {
  constructor(){
    this.root=document.getElementById('map-shell');this.canvas=document.getElementById('track-chart');this.camera=new MapCamera.Camera();this.points=[];this.current=null;this.follow=true;this.initialized=false;this.pointers=new Map();this.tiles=new Map();this.lastPaint=0;this.scheduled=false;this.gapSeconds=1;
    document.getElementById('map-zoom-in').onclick=()=>this.zoom(1);
    document.getElementById('map-zoom-out').onclick=()=>this.zoom(-1);
    document.getElementById('map-fit').onclick=()=>this.fit();
    document.getElementById('map-current').onclick=()=>this.locate();
    document.getElementById('map-follow').onclick=()=>{this.setFollow(!this.follow);if(this.follow)this.locate();};
    this.root.addEventListener('wheel',e=>{if(!e.deltaY)return;e.preventDefault();const r=this.root.getBoundingClientRect();this.zoom(e.deltaY<0?.5:-.5,e.clientX-r.left,e.clientY-r.top);},{passive:false});
    this.root.addEventListener('pointerdown',e=>{
      if(e.target.closest('a,button')||![0,1].includes(e.button))return;
      e.preventDefault();this.setFollow(false);this.root.focus({preventScroll:true});this.root.setPointerCapture(e.pointerId);this.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});this.root.classList.add('panning');
    });
    this.root.addEventListener('pointermove',e=>{
      const previous=this.pointers.get(e.pointerId);if(!previous)return;e.preventDefault();
      const old=[...this.pointers.values()];this.pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});const next=[...this.pointers.values()];
      if(next.length===1)this.camera.pan(e.clientX-previous.x,e.clientY-previous.y);
      else if(next.length===2){
        const dist=p=>Math.hypot(p[0].x-p[1].x,p[0].y-p[1].y),mid=p=>[(p[0].x+p[1].x)/2,(p[0].y+p[1].y)/2],a=mid(old),b=mid(next),r=this.root.getBoundingClientRect();
        if(dist(old)>2&&dist(next)>2)this.camera.zoomAt(Math.log2(dist(next)/dist(old)),a[0]-r.left,a[1]-r.top);
        this.camera.pan(b[0]-a[0],b[1]-a[1]);
      }this.schedule();
    });
    const end=e=>{this.pointers.delete(e.pointerId);if(!this.pointers.size)this.root.classList.remove('panning');};
    for(const event of ['pointerup','pointercancel','lostpointercapture'])this.root.addEventListener(event,end);
    this.root.addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault();});
    this.root.addEventListener('keydown',e=>{if(e.target!==this.root)return;const moves={ArrowLeft:[60,0],ArrowRight:[-60,0],ArrowUp:[0,60],ArrowDown:[0,-60]};if(e.key==='+'||e.key==='=')this.zoom(1);else if(e.key==='-')this.zoom(-1);else if(e.key==='Home')this.fit();else if(e.key.toLowerCase()==='f')this.locate();else if(moves[e.key]){this.setFollow(false);this.camera.pan(...moves[e.key]);this.schedule();}else return;e.preventDefault();});
    new ResizeObserver(()=>this.schedule()).observe(this.root);this.setFollow(true);
  }
  setFollow(value){this.follow=value;const b=document.getElementById('map-follow');b.setAttribute('aria-pressed',String(value));b.textContent=value?'追従 ON':'追従 OFF';}
  resize(){if(this.root.clientWidth)this.camera.resize(this.root.clientWidth,this.root.clientHeight);}
  zoom(amount,x,y){this.resize();this.setFollow(false);this.camera.zoomAt(amount,x,y);this.schedule();}
  fit(){this.resize();this.setFollow(false);this.camera.fit(this.points);this.schedule();}
  locate(){if(!this.current)return;this.camera.center=MapCamera.project(...this.current);this.schedule();}
  update(points,current){this.points=points;this.current=current;document.getElementById('map-current').disabled=!current;document.getElementById('map-fit').disabled=!points.length;if(!this.root.clientWidth)return;this.resize();if(!this.initialized&&current){this.camera.center=MapCamera.project(...current);this.initialized=true;}if(this.follow&&current)this.camera.center=MapCamera.project(...current);if(performance.now()-this.lastPaint>=100)this.schedule();}
  schedule(){if(this.scheduled)return;this.scheduled=true;requestAnimationFrame(()=>{this.scheduled=false;this.paint();});}
  tile(z,x,y){
    const key=`${z}/${x}/${y}`;let entry=this.tiles.get(key);
    if(entry&&entry.state==='error'&&Date.now()-entry.used>30000){this.tiles.delete(key);entry=null;}
    if(entry){if(entry.state!=='error')entry.used=Date.now();return entry;}
    // Only on-screen tiles are requested, no prefetch or full-area download.
    entry={image:new Image(),state:'loading',used:Date.now()};this.tiles.set(key,entry);
    entry.image.crossOrigin='anonymous';entry.image.referrerPolicy='no-referrer';
    entry.image.onload=()=>{entry.state='ready';this.schedule();};entry.image.onerror=()=>{entry.state='error';entry.used=Date.now();this.schedule();};
    entry.image.src=`https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/${key}.jpg`;
    return entry;
  }
  paint(){
    if(!this.root.clientWidth)return;this.lastPaint=performance.now();this.resize();
    const dpr=window.devicePixelRatio||1,w=this.camera.width,h=this.camera.height,c=this.canvas;
    if(c.width!==Math.round(w*dpr)||c.height!==Math.round(h*dpr)){c.width=Math.round(w*dpr);c.height=Math.round(h*dpr);}
    const ctx=c.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.fillStyle='#232a2c';ctx.fillRect(0,0,w,h);
    const z=Math.min(18,Math.floor(this.camera.zoom)),count=2**z,size=256*2**(this.camera.zoom-z),cx=this.camera.center[0]*count,cy=this.camera.center[1]*count;
    const x0=Math.floor(cx-w/2/size),x1=Math.floor(cx+w/2/size),y0=Math.max(0,Math.floor(cy-h/2/size)),y1=Math.min(count-1,Math.floor(cy+h/2/size));
    const visible=new Set();let loading=0,errors=0;
    for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){
      const tx=(x%count+count)%count,key=`${z}/${tx}/${y}`;visible.add(key);const t=this.tile(z,tx,y),left=w/2+(x-cx)*size,top=h/2+(y-cy)*size;
      if(t.state==='ready')ctx.drawImage(t.image,left,top,size+.5,size+.5);
      else{if(t.state==='error')errors++;else loading++;ctx.strokeStyle='#536063';ctx.strokeRect(left,top,size,size);}
    }
    if(this.tiles.size>128){for(const [key,entry] of [...this.tiles].sort((a,b)=>a[1].used-b[1].used)){if(this.tiles.size<=128)break;if(!visible.has(key)){entry.image.onload=null;entry.image.onerror=null;entry.image.src='';this.tiles.delete(key);}}}
    // A white casing keeps the route legible over both dark fields and pale roofs.
    const path=()=>{ctx.beginPath();this.points.forEach((p,i)=>{const [x,y]=this.camera.screen(...p);if(!i||p[2]-this.points[i-1][2]>this.gapSeconds)ctx.moveTo(x,y);else ctx.lineTo(x,y);});};
    path();ctx.strokeStyle='#fff';ctx.lineWidth=5;ctx.stroke();path();ctx.strokeStyle='#e5222b';ctx.lineWidth=2.5;ctx.stroke();
    if(this.current){const [x,y]=this.camera.screen(...this.current);ctx.fillStyle='#e5222b';ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.beginPath();ctx.arc(x,y,6,0,2*Math.PI);ctx.fill();ctx.stroke();}
    const lat=MapCamera.unproject(...this.camera.center)[1],mpp=40075016.686*Math.cos(lat*Math.PI/180)/(256*2**this.camera.zoom),target=mpp*100,base=10**Math.floor(Math.log10(target)),meters=([5,2,1].find(n=>n*base<=target)||1)*base;
    ctx.fillStyle='#ffffffec';ctx.fillRect(10,h-48,Math.max(100,meters/mpp+20),38);ctx.fillStyle='#222';ctx.font='13px Segoe UI';ctx.fillText(meters>=1000?`${meters/1000} km`:`${meters} m`,18,h-28);ctx.strokeStyle='#222';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(18,h-22);ctx.lineTo(18,h-17);ctx.lineTo(18+meters/mpp,h-17);ctx.lineTo(18+meters/mpp,h-22);ctx.stroke();
    ctx.fillStyle='#ffffffec';ctx.fillRect(w-46,10,36,29);ctx.fillStyle='#222';ctx.fillText('N ↑',w-40,30);
    document.getElementById('map-status').textContent=errors?'一部の航空写真を取得できません（未整備・通信エラー）':loading?'航空写真を読み込んでいます…':`地理院地図・航空写真${this.camera.zoom>18?'（拡大表示）':''}`;
  }
};
}
