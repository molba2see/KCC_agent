const {chromium}=require('playwright');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  for(const width of [1440,390]){
   const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});
   const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.route('http://localhost/**',route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:false,csrf:'test'}});
    if(url.pathname.startsWith('/api/'))return route.fulfill({json:{links:[]}});
    return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
   });
   await page.goto('http://localhost/#home');
   for(const name of ['home','files','folders','review','trash','connection','settings']){
    await page.evaluate(name=>window.page(name),name);
    await page.waitForFunction(name=>document.querySelector('#'+name+' .page-heading > div').getAnimations().some(a=>a.playState==='running'),name);
    const heading=page.locator('#'+name+' .page-heading > div');
    assert(await heading.evaluate(e=>Number(getComputedStyle(e).opacity))<1);
    await page.waitForTimeout(1200);
    assert.equal(await heading.evaluate(e=>getComputedStyle(e).opacity),'1');
   }
   await page.evaluate(()=>window.page('home'));
   await page.waitForFunction(()=>document.querySelector('.stats button').getAnimations().some(a=>a.playState==='running'));
   const delays=await page.locator('.stats button').evaluateAll(items=>items.map(e=>e.getAnimations()[0].effect.getTiming().delay));
   assert(new Set(delays).size>=3,'Dashboard cards should be staggered');
   await page.evaluate(()=>window.page('files'));
   await page.evaluate(()=>document.getElementById('all-files').innerHTML='<div class="file-row">Async file</div>');
   await page.waitForFunction(()=>document.querySelector('#all-files .file-row').getAnimations().some(a=>a.playState==='running'));
   await page.waitForTimeout(1200);
   await page.evaluate(()=>document.getElementById('all-files').innerHTML='<div class="file-row">Async file</div>');
   await page.waitForTimeout(100);
   assert.equal(await page.locator('#all-files .file-row').evaluate(e=>e.getAnimations().length),0,'Polling must not replay unchanged rows');
   await page.emulateMedia({reducedMotion:'reduce'});
   await page.evaluate(()=>window.page('home'));
   assert.equal(await page.locator('#home .page-heading > div').evaluate(e=>e.getAnimations().length),0);
   assert.equal(await page.locator('#home .page-heading > div').evaluate(e=>getComputedStyle(e).opacity),'1');
   assert.deepEqual(errors,[]);
   console.log('PASS workspace navigation, stagger, async data, polling and reduced motion',width);
   await page.close();
  }
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
