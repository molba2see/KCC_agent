// NODE_PATH=<directory containing playwright> node web/tests/onboarding-guide.cjs
const {chromium}=require('playwright');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{
  for(const width of [1440,390,320]){
   const page=await browser.newPage({viewport:{width,height:900},isMobile:width<760,hasTouch:width<760});
   const errors=[],actions=[];let authenticated=true;
   let state={mac_connected:false,iphone_icloud_confirmed:false,test_started:false,file_received:false,completed:false};
   page.on('pageerror',e=>errors.push(e.message));
   await page.route('http://localhost/**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated,username:'tester',csrf:'test',onboarding_completed:false}});
    if(url.pathname==='/api/v1/onboarding/'){
     if(route.request().method()==='POST'){
      assert.equal(route.request().headers()['x-csrftoken'],'test');
      const {action}=route.request().postDataJSON();actions.push(action);
      if(action==='confirm_iphone')state.iphone_icloud_confirmed=true;
      if(action==='start_test'){state.test_started=true;state.file_received=false;}
      if(action==='complete')state.completed=true;
     }
     return route.fulfill({json:state});
    }
    if(url.pathname==='/api/v1/agent/status/')return route.fulfill({json:{links:[]}});
    if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
    return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
   });
   const visible=async id=>{await page.locator('#'+id).waitFor({state:'visible'});assert.equal(await page.locator('#onboarding-content .setup-screen:visible').count(),1);};
   const noOverflow=async()=>assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.goto('http://localhost/#onboarding');
   await visible('setup-dock');await page.locator('#setup-dock-done').click();await visible('setup-welcome');
   await page.locator('#setup-begin').click();await visible('setup-mac');
   await page.locator('#setup-helper-blocked').click();await visible('setup-mac-security');await noOverflow();
   assert.match(await page.locator('#setup-mac-security').innerText(),/그래도 열기/);
   await page.locator('#setup-security-done').click();await visible('setup-mac-connect');
   await page.locator('#setup-mac-connect [data-setup-back]').click();await visible('setup-mac-security');
   await page.locator('#setup-security-done').click();
   state.mac_connected=true;await page.evaluate(()=>document.dispatchEvent(new Event('moa-page')));await visible('setup-iphone');
   await page.locator('#onboarding-confirm-iphone').click();await visible('setup-shortcut');await noOverflow();
   assert.deepEqual(actions,['confirm_iphone']); // Setup must finish before the receipt baseline starts.
   const qr=await page.locator('#shortcut-qr-link').getAttribute('href');assert.equal(qr,'http://localhost/#iphone-shortcut');
   await page.locator('#setup-shortcut-done').click();await visible('setup-backtap');await noOverflow();
   assert.deepEqual(actions,['confirm_iphone']);
   await page.locator('#setup-backtap-done').click();await visible('setup-send');
   assert.deepEqual(actions,['confirm_iphone','start_test']);
   await page.locator('#setup-saved').click();await visible('setup-wait');
   assert.equal(await page.locator('#onboarding-complete').isDisabled(),true);
   state.file_received=true;state.received_filename='테스트.png';
   await page.evaluate(()=>document.dispatchEvent(new Event('moa-page')));
   await page.locator('#onboarding-complete').waitFor({state:'visible'});
   await page.waitForFunction(()=>!document.getElementById('onboarding-complete').disabled);
   await page.locator('#onboarding-complete').click();await visible('setup-done');
   assert.deepEqual(actions,['confirm_iphone','start_test','complete']);
   // QR page is public and remains visible after onboarding polling.
   authenticated=false;await page.goto('http://localhost/#iphone-shortcut');await page.reload();
   assert.equal(await page.locator('#shortcut-guide .setup-screen:visible').count(),3);
   await noOverflow();await page.locator('#shortcut-guide a[href="#shortcut-backtap"]').click();
   assert.equal(await page.locator('#shortcut-backtap').isVisible(),true);
   await page.evaluate(()=>document.dispatchEvent(new Event('moa-session')));
   assert.equal(await page.locator('#shortcut-guide .setup-screen:visible').count(),3);
   assert.deepEqual(errors,[]);
   if(width===390){await page.evaluate(()=>scrollTo({top:0,left:0,behavior:'instant'}));await page.screenshot({path:'/tmp/moa-onboarding-qa/iphone-guide-viewport.png',animations:'disabled'});}
   console.log('PASS guided setup, back navigation, deferred test, receipt, public QR, no overflow:',width);
   await page.close();
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
