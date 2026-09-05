// GSI raster tiles and route use the same Web Mercator world coordinates.
export const tileSize=256,maxLatitude=85.0511287798066;
export function mercator(lat,lon){
  if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)return null;
  const r=Math.max(-maxLatitude,Math.min(maxLatitude,lat))*Math.PI/180;
  return{x:(lon+180)/360,y:(1-Math.log(Math.tan(Math.PI/4+r/2))/Math.PI)/2};
}
export function routeSegments(points){
  const end=points.at(-1);if(!end)return[];
  // Never join real and demo journeys, or two different vehicle profiles.
  let begin=points.length-1;
  while(begin>0&&points[begin-1]?.demo===end.demo&&points[begin-1]?.vehicle===end.vehicle)begin--;
  const segments=[];let segment=[],previous=null;
  const finish=()=>{if(segment.length)segments.push(segment);segment=[];previous=null};
  for(const p of points.slice(begin)){
    const d=p?.d,q=mercator(d?.Lat,d?.Lon);
    if(!q||!Number.isFinite(p.t)||(d.GPSFix!==undefined&&!(d.GPSFix>=2))){finish();continue}
    if(previous&&(p.t<=previous.t||p.t-previous.t>15000))finish();
    const anchor=segment.at(-1)?.x??segments[0]?.[0]?.x??q.x;
    q.x+=Math.round(anchor-q.x); // unwrap the antimeridian locally
    segment.push({...q,t:p.t});previous=p;
  }
  finish();return segments;
}
export function fitRoute(segments,width,height){
  const pts=segments.flat();if(!pts.length||width<=0||height<=0)return null;
  const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y),loX=Math.min(...xs),hiX=Math.max(...xs),loY=Math.min(...ys),hiY=Math.max(...ys);
  const zoom=Math.max(2,Math.min(18,Math.floor(Math.log2(Math.min(Math.max(1,width-64)/(256*Math.max(hiX-loX,1e-9)),Math.max(1,height-64)/(256*Math.max(hiY-loY,1e-9)))))));
  return{x:(loX+hiX)/2,y:(loY+hiY)/2,zoom};
}
export function visibleTiles(view,width,height){
  const n=2**view.zoom,left=view.x*n-width/512,top=view.y*n-height/512,result=[];
  for(let y=Math.max(0,Math.floor(top));y<=Math.min(n-1,Math.floor(top+height/256));y++)
    for(let x=Math.floor(left);x<=Math.floor(left+width/256);x++){
      const wrapped=((x%n)+n)%n;
      result.push({key:`${view.zoom}/${wrapped}/${y}`,x:(x-left)*256,y:(y-top)*256});
    }
  return result;
}
export class GsiRouteMap{
  constructor(canvas,label){
    this.canvas=canvas;this.ctx=canvas.getContext("2d");this.label=label;this.points=[];this.tiles=new Map();this.pending=0;this.auto=true;this.view=null;
    canvas.addEventListener("pointerdown",e=>{if(!this.view)return;canvas.setPointerCapture(e.pointerId);this.drag={x:e.clientX,y:e.clientY,view:{...this.view}}});
    canvas.addEventListener("pointermove",e=>{if(!this.drag)return;const s=256*2**this.view.zoom;this.auto=false;this.view={...this.drag.view,x:this.drag.view.x-(e.clientX-this.drag.x)/s,y:Math.max(0,Math.min(1,this.drag.view.y-(e.clientY-this.drag.y)/s))};this.schedule()});
    const stop=()=>this.drag=null;canvas.addEventListener("pointerup",stop);canvas.addEventListener("pointercancel",stop);canvas.addEventListener("lostpointercapture",stop);
  }
  setPoints(points){this.points=points;this.schedule()}
  fit(){this.auto=true;this.schedule()}
  zoom(delta){if(!this.view)return;this.auto=false;this.view.zoom=Math.max(2,Math.min(18,this.view.zoom+delta));this.schedule()}
  schedule(){if(this.scheduled)return;this.scheduled=true;requestAnimationFrame(()=>{this.scheduled=false;this.draw()})}
  load(key){
    const cached=this.tiles.get(key);
    if(cached){cached.used=Date.now();if(!cached.error||Date.now()-cached.error<30000)return cached}
    if(this.pending>=6)return null;
    while(this.tiles.size>=96){const old=[...this.tiles].filter(([,v])=>!v.loading).sort((a,b)=>a[1].used-b[1].used)[0];if(!old)break;this.tiles.delete(old[0])}
    const tile={image:new Image(),loading:true,used:Date.now(),error:0};this.tiles.set(key,tile);this.pending++;
    let finished=false;
    const finish=failed=>{if(finished)return;finished=true;clearTimeout(timeout);tile.loading=false;if(failed){tile.error=Date.now();tile.image.src=""}this.pending--;this.schedule()};
    const timeout=setTimeout(()=>finish(true),15000);
    tile.image.onload=()=>finish(false);
    tile.image.onerror=()=>finish(true);
    tile.image.referrerPolicy="no-referrer"; // Never send the private sharing URL to the tile service.
    tile.image.src=`https://cyberjapandata.gsi.go.jp/xyz/pale/${key}.png`;
    return tile;
  }
  draw(){
    const c=this.canvas,ctx=this.ctx,w=c.clientWidth,h=c.clientHeight;if(!w||!h)return;
    const ratio=Math.min(devicePixelRatio||1,3);c.width=Math.round(w*ratio);c.height=Math.round(h*ratio);ctx.setTransform(ratio,0,0,ratio,0,0);
    ctx.fillStyle="#e9e8e3";ctx.fillRect(0,0,w,h);
    const segments=routeSegments(this.points);if(!segments.length){this.label.textContent="有効な位置を待っています";return}
    if(this.auto||!this.view)this.view=fitRoute(segments,w,h);
    const v=this.view,s=256*2**v.zoom;let loaded=0,failed=0;
    const tiles=visibleTiles(v,w,h);
    for(const t of tiles){const tile=this.load(t.key);if(tile&&!tile.loading&&!tile.error){ctx.drawImage(tile.image,t.x,t.y,256,256);loaded++}else if(tile?.error)failed++}
    const xy=p=>({x:(p.x-v.x)*s+w/2,y:(p.y-v.y)*s+h/2});
    for(const segment of segments){ctx.beginPath();segment.map(xy).forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.lineJoin="round";ctx.lineCap="round";ctx.lineWidth=6;ctx.strokeStyle="white";ctx.stroke();ctx.lineWidth=3;ctx.strokeStyle="#d91422";ctx.stroke()}
    const last=xy(segments.at(-1).at(-1));ctx.fillStyle="#d91422";ctx.strokeStyle="white";ctx.lineWidth=3;ctx.beginPath();ctx.arc(last.x,last.y,6,0,Math.PI*2);ctx.fill();ctx.stroke();
    this.label.textContent=failed?"地図の一部を取得できません · 経路は表示継続":loaded<tiles.length?"地理院地図 読込中":`地理院地図 · Z${v.zoom} · ドラッグで移動`;
  }
}
