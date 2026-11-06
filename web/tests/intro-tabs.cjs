// NODE_PATH=<directory containing playwright> node web/tests/intro-tabs.cjs
const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});try{
 for(const width of [1440,390,320]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://localhost/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:false,csrf:'test'}});
   if(url.pathname.startsWith('/api/'))return route.fulfill({json:{links:[]}});
   return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
  });
  await page.goto('http://localhost/#intro');await page.locator('.header-signup').waitFor();
  if(width<760){
   assert.equal(await page.locator('.mobile-bar').isVisible(),false);
   const before=await page.locator('.intro-segments').boundingBox();
   await page.evaluate(()=>scrollTo(0,500));
   const after=await page.locator('.intro-segments').boundingBox();
   const header=await page.locator('.site-header').boundingBox();
   assert(Math.abs(before.y-after.y)<1,'Mobile segments must stay fixed while scrolling');
   assert(Math.abs(after.y-(header.y+header.height))<1,'Segments must meet the header without a gap');
   assert.equal(after.x,0);assert.equal(after.width,width);
   assert.equal(await page.locator('.intro-segments').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(250, 248, 245)');
   assert.equal(await page.locator('.site-header').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(250, 248, 245)');
   await page.evaluate(()=>scrollTo(0,0));
  }
  assert.deepEqual(await page.locator('.intro-segments [role=tab]').allTextContents(),['서비스 소개','문제 정의','기술 과정','서비스 사용법']);
  for(const key of ['overview','problem','technology','guide']){
   await page.locator('#intro-tab-'+key).click();
   assert.equal(await page.locator('#intro .intro-panel:visible').count(),1);
   assert.equal(await page.locator('#intro-panel-'+key).isVisible(),true);
   assert.equal(await page.locator('#intro-tab-'+key).getAttribute('aria-selected'),'true');
   await page.waitForFunction(key=>document.querySelector('#intro-panel-'+key+' h1').getAnimations().some(animation=>animation.playState==='running'),key);
   const motion=await page.locator('#intro-panel-'+key).evaluate(panel=>[...panel.querySelectorAll('*')].flatMap(element=>element.getAnimations().filter(animation=>animation.effect.getKeyframes().some(frame=>frame.opacity=== '0')).map(animation=>animation.effect.getTiming().delay)));
   assert(motion.length>=3,'Each tab should fade its visible content in sequence');
   assert(new Set(motion).size>=3,'Visible blocks should have staggered start times');
   assert.equal(new URL(page.url()).hash,'#intro');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   if(width!==320)await page.screenshot({path:`/tmp/moa-onboarding-qa/intro-${key}-${width}.png`,animations:'disabled'});
  }
  await page.keyboard.press('ArrowRight');assert.equal(await page.locator('#intro-tab-overview').evaluate(e=>e===document.activeElement),true);
  await page.keyboard.press('End');assert.equal(await page.locator('#intro-tab-guide').getAttribute('aria-selected'),'true');
  await page.keyboard.press('Home');assert.equal(await page.locator('#intro-tab-overview').getAttribute('aria-selected'),'true');
  await page.evaluate(()=>scrollTo({top:document.body.scrollHeight,left:0,behavior:'instant'}));
  await page.locator('#intro-tab-problem').click();
  assert((await page.locator('#intro-panel-problem h1').boundingBox()).y>70,'Changing tabs should reveal the new heading');
  await page.locator('#intro-tab-guide').click();await page.locator('#intro-panel-guide [data-page=signup]').click();
  await page.waitForFunction(()=>document.getElementById('signup-modal').open);
  assert.equal(new URL(page.url()).hash,'#intro');await page.keyboard.press('Escape');
  await page.evaluate(()=>page('home'));await page.evaluate(()=>page('intro'));
  assert.equal(await page.locator('#intro-panel-guide').isVisible(),true);
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.waitForFunction(()=>!document.querySelector('#intro-panel-guide h1').getAnimations().length);
  assert.equal(await page.locator('#intro-panel-guide h1').evaluate(element=>getComputedStyle(element).opacity),'1');
  assert.deepEqual(errors,[]);console.log('PASS public intro content, tabs, keyboard, scroll position, signup modal, responsive layout:',width);
  await page.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
