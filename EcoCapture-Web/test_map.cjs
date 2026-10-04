// Geometry and interaction contract tests, without a browser or third-party tile requests.
const assert=require('node:assert/strict');
const {Camera,project,unproject}=require('./web/map-view.js');
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-6,`${a} != ${b}`);
for(const [lon,lat] of [[135,35],[0,0],[-179,70],[179,-70]]){const p=unproject(...project(lon,lat));close(p[0],lon);close(p[1],lat);}
const camera=new Camera();camera.resize(900,600);const pos=[135.001,35.001];
const point=camera.screen(...pos);camera.zoomAt(2,...point);camera.screen(...pos).forEach((v,i)=>close(v,point[i]));
const before=camera.screen(...pos);camera.pan(93,-47);const after=camera.screen(...pos);close(after[0]-before[0],93);close(after[1]-before[1],-47);
camera.fit([[179.999,35],[-179.999,35.001]]);assert.ok(camera.zoom>14,'dateline fit should use the short arc');
camera.fit([[135,35],[135.004,35.003]]);for(const p of [[135,35],[135.004,35.003]]){const [x,y]=camera.screen(...p);assert.ok(x>=49&&x<=851&&y>=49&&y<=551);}
camera.zoomAt(100);assert.equal(camera.zoom,22);camera.zoomAt(-100);assert.equal(camera.zoom,2);

const vm=require('node:vm'),fs=require('node:fs');
const nodes=new Map(),frames=[],requests=[];
const context=new Proxy({}, {get:(t,k)=>t[k]||(()=>{}),set:(t,k,v)=>(t[k]=v,true)});
function node(id){if(!nodes.has(id))nodes.set(id,{clientWidth:800,clientHeight:500,width:0,height:0,events:{},classList:{add(){},remove(){}},setAttribute(){},focus(){},setPointerCapture(){},getBoundingClientRect:()=>({left:0,top:0}),getContext:()=>context,addEventListener(name,fn){this.events[name]=fn;}});return nodes.get(id);}
class FakeImage{set src(url){if(url)requests.push(url);}get src(){return '';}}
const sandbox={window:{devicePixelRatio:1},document:{getElementById:node},Image:FakeImage,ResizeObserver:class{observe(){}},requestAnimationFrame:f=>frames.push(f),performance:{now:()=>1000},Date,Map,Set,Math};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'web/map-view.js'),'utf8'),sandbox);
const view=new sandbox.window.EcoMap();
view.update([[135,35,1],[135.0001,35.0001,1.05]],[135.0001,35.0001]);frames.shift()();
assert.ok(requests.length>0);assert.ok(requests.every(x=>x.startsWith('https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/')));
view.zoom(.5,100,200);assert.equal(view.follow,false);const manualCenter=[...view.camera.center];
view.update([[135.01,35.01,2]],[135.01,35.01]);assert.deepEqual([...view.camera.center],manualCenter,'incoming data must not move a manually positioned map');
const event=(x,y,button=1)=>({target:{closest:()=>null},button,pointerId:1,clientX:x,clientY:y,preventDefault(){}});
const initial=view.camera.screen(135,35);node('map-shell').events.pointerdown(event(100,100));node('map-shell').events.pointermove(event(180,150));
const moved=view.camera.screen(135,35);close(moved[0]-initial[0],80);close(moved[1]-initial[1],50);
node('map-shell').events.pointerup(event(180,150));assert.equal(view.pointers.size,0);
view.locate();const located=view.camera.screen(...view.current);close(located[0],400);close(located[1],250);
view.camera.zoom=22;view.paint();assert.ok(requests.every(x=>Number(x.split('/')[5])<=18),'overzoom must not request nonexistent zoom 19+ tiles');
view.update([],null);assert.equal(node('map-current').disabled,true);assert.equal(node('map-fit').disabled,true);
console.log('PASS: projection, cursor anchor, pan, fit, antimeridian, zoom bounds, GSI tile source, manual-view retention, middle drag, recenter, overzoom, stale location');
