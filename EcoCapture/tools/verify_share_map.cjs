// Local browser regression: synthetic Firebase responses, real public GSI tiles.
// No Firebase writes and no user settings/location are read.
const {chromium}=require(process.argv[2]||'playwright');
const http=require('http'),fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=path.resolve(__dirname,'../cloud/public'),output=path.resolve(__dirname,'../artifacts/share-map-036');
fs.mkdirSync(output,{recursive:true});
const server=http.createServer((req,res)=>{
  const file=path.join(root,new URL(req.url,'http://localhost').pathname==='/'?'index.html':new URL(req.url,'http://localhost').pathname);
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return}
  fs.readFile(file,(err,body)=>{if(err){res.writeHead(404).end();return}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(body)});
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1100,height:1000}}),errors=[],tileRequests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.url().includes('cyberjapandata.gsi.go.jp'))tileRequests.push({url:r.url(),referrer:r.headers().referer})});
  const now=Date.now(),points=Array.from({length:45},(_,i)=>({t:now-(44-i)*1000,vehicle:'ux250h',demo:true,
    d:{Lat:36.1517+.001*Math.sin(i/12),Lon:139.9196+.001*Math.cos(i/12),GPSFix:3,GPSSpeed:34,RPM:0,SteeringAngle:-8.1,WaterTemp:88,OilTemp:83}}));
  await page.route('**/*.firebasedatabase.app/**',route=>{
    const url=route.request().url();
    if(url.includes('/latest.json'))return route.fulfill({contentType:'text/event-stream',body:'event: put\ndata: '+JSON.stringify({path:'/',data:points.at(-1)})+'\n\n'});
    return route.fulfill({contentType:'application/json',body:JSON.stringify(url.includes('/meta.json')?{vehicle:'lx',demo:false}:Object.fromEntries(points.map(p=>[p.t,p])))});
  });
  const base=process.argv[3]||`http://127.0.0.1:${server.address().port}`;
  await page.goto(`${base}/?id=${'f'.repeat(32)}`);
  await page.waitForFunction(()=>document.getElementById('vehicle').textContent.includes('DEMO · レクサス UX250h'));
  await page.waitForFunction(()=>document.getElementById('map-status').textContent.includes(' · Z'),{},{timeout:45000});
  assert.equal(await page.locator('#rpm').textContent(),'0');assert.equal(await page.locator('#steering').textContent(),'-8.1');
  assert.ok(tileRequests.length>0&&tileRequests.every(r=>!r.referrer),'private ID must not reach tile service');
  await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
  await page.locator('#map-in').click();await page.locator('#map-out').click();await page.locator('#map-fit').click();
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(1000);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile must not overflow');
  await page.screenshot({path:path.join(output,'mobile.png'),fullPage:true});
  // Tile failure still leaves route canvas and a visible diagnostic.
  await page.route('**/cyberjapandata.gsi.go.jp/**',r=>r.abort());
  for(let i=0;i<3;i++)await page.locator('#map-out').click();
  await page.waitForFunction(()=>document.getElementById('map-status').textContent.includes('取得できません'));
  assert.equal(errors.length,0,errors.join('\n'));
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({passed:true,base,errors,tilesRequested:tileRequests.length,realGsiTiles:true,syntheticFirebase:true,noFirebaseWrites:true},null,2));
  console.log('PASS shared viewer: actual GSI tiles, demo/zero/steering, responsive layout, privacy, tile failure');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>server.close());
