// Exercise the actual HTML parser and plot commands without a browser or network.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(require('node:path').join(__dirname,'../tools/sd_viewer.html'),'utf8');
let drawingCalls=0;
const context2d=new Proxy({}, {get:(_,key)=> (...args)=>{for(const a of args)if(typeof a==='number')assert(Number.isFinite(a),key+' received nonfinite coordinate');drawingCalls++;},set:()=>true});
const nodes=new Map();
function element(){return {hidden:false,textContent:'',value:'',max:0,clientWidth:600,clientHeight:340,children:[],replaceChildren(){this.children=[]},append(x){this.children.push(x)},getContext(){return context2d}}}
const sandbox={Blob,TextDecoder,console,window:{devicePixelRatio:1,addEventListener(){}},document:{getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id)},createElement:element}};
vm.createContext(sandbox);vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],sandbox);
async function loadText(text,name='test.csv',sidecars=[]){const f=new Blob([text]);f.name=name;sandbox.testFiles=[f,...sidecars];vm.runInContext("selectedFiles=testFiles; document.getElementById('sessions').value=testFiles[0].name",sandbox);await vm.runInContext('load()',sandbox)}
(async()=>{
 await loadText('monotonic_us,utc_us,Lat,Lon,GPSSpeed,GPSFix,GPSTow,LogDrops,AccelX\n1000000,,35,139,0,3,1000,0,\n1010000,,35.000001,139.000001,1,3,1000,0,-0.2\n1020000,,,,,0,1040,0,\nbroken,row\n');
 assert.equal(vm.runInContext('stats.count',sandbox),3);assert.equal(vm.runInContext('stats.position',sandbox),2);assert.equal(vm.runInContext('stats.malformed',sandbox),1);
 assert.equal(vm.runInContext("get(rows[0],'AccelX')",sandbox),null);assert(nodes.get('message').textContent.includes('未確定'));assert(drawingCalls>0);
 nodes.get('channel').value='AccelX';vm.runInContext('draw()',sandbox);assert(nodes.get('unit').textContent.includes('AccelX'));
 const csvPath=process.argv[2];if(csvPath){await loadText(fs.readFileSync(csvPath,'utf8'));assert.equal(vm.runInContext('stats.count',sandbox),6063);assert.equal(vm.runInContext('stats.malformed',sandbox),0);assert.equal(vm.runInContext('headers.length',sandbox),66);assert(nodes.get('message').textContent.includes('推定起動日時'))}
 let large='monotonic_us,utc_us,Lat,Lon,GPSSpeed,GPSFix,GPSTow,LogDrops\n';for(let i=0;i<90000;i++)large+=`${i*10000+1},,35,139,0,3,${Math.floor(i/4)*40},0\n`;
 await loadText(large);assert.equal(vm.runInContext('stats.count',sandbox),90000);assert(vm.runInContext('rows.length',sandbox)<=40001);assert.equal(vm.runInContext('stats.gpsUpdates',sandbox),22500);
 console.log('Viewer parser and plot-command tests passed: missing data, malformed rows, real CSV, 90000-row decimation.');
})().catch(e=>{console.error(e);process.exitCode=1});
