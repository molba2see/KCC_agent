// NODE_PATH=<directory containing playwright> node web/tests/guest-workspace.cjs
const {chromium}=require('playwright');const path=require('node:path');const fs=require('node:fs');const crypto=require('node:crypto');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});const errors=[],staleRequests=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{localStorage.setItem('moa-operations-demo-v2',JSON.stringify({folders:[{name:'캡스톤 자료'}],files:[{name:'공모전_신청서.pdf'}]}))});
  await page.route('http://localhost/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:false,csrf:'test'}});
   if(url.pathname.startsWith('/api/'))return route.fulfill({json:{links:[]}});
   const file=path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1));
   if(/\.(js|css)$/.test(url.pathname)){
    if(!url.searchParams.get('v')){staleRequests.push(url.pathname);return route.fulfill({contentType:'text/javascript',body:'throw Error("unversioned cached release loaded")'});}
    assert.equal(url.searchParams.get('v'),crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').slice(0,12));
   }
   return route.fulfill({path:file});
  });
  await page.goto('http://localhost/#home');await page.locator('.header-login').waitFor();
  for(let round=0;round<3;round++)for(const name of ['intro','home','files','folders','review','trash','connection','settings','home']){
   if(width<760){await page.locator('#menu-toggle').click();await page.locator('#mobile-menu [data-page="'+name+'"]').click();}
   else await page.locator('.desktop-nav [data-page="'+name+'"]').click();
   for(const id of ['stat-today','stat-pending','stat-folders','nav-pending'])assert.equal(await page.locator('#'+id).textContent(),'0',name);
   assert.equal(await page.locator('[data-asset]').count(),0);
   assert.equal(await page.locator('.status-word').textContent(),'연결 확인');
   assert.equal(await page.locator('#all-files').innerText().then(s=>s.includes('공모전_신청서')),false);
  }
  // This is the compatibility decision used by the old navigation renderer.
  await page.evaluate(()=>{if(window.MoaLive?.enabled)window.MoaLive.render();else document.getElementById('stat-folders').textContent='3'});
  assert.equal(await page.locator('#stat-folders').textContent(),'0');
  assert.equal(await page.evaluate(()=>localStorage.getItem('moa-operations-demo-v2')),null);
  assert.equal(await page.locator('#workspace-mode,#reset-demo').count(),0);
  assert.deepEqual(staleRequests,[]);assert.deepEqual(errors,[]);
  console.log('PASS guest zero state across repeated navigation, old storage/renderer, versioned cache:',width);await page.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
