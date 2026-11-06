// NODE_PATH=<directory containing playwright> node web/tests/signup-modal.cjs
const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{for(const width of [1440,390,320]){
  const page=await browser.newPage({viewport:{width,height:900},isMobile:width<760,hasTouch:width<760});
  let authenticated=false,acceptSignup=false;const requests=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://localhost/**',route=>{
   const url=new URL(route.request().url());let body;
   if(url.pathname==='/api/v1/auth/session/')body={authenticated,username:authenticated?'tester':null,csrf:'test',onboarding_completed:false};
   else if(url.pathname==='/api/v1/auth/signup/'){
    requests.push(route.request().postDataJSON());assert.equal(route.request().headers()['x-csrftoken'],'test');
    if(!acceptSignup)return route.fulfill({status:400,json:{detail:'아이디를 확인하세요.',errors:{username:['이미 사용 중인 아이디입니다.']}}});
    authenticated=true;body={authenticated:true};
   }else if(url.pathname==='/api/v1/agent/status/')body={links:[]};
   else if(url.pathname==='/api/v1/onboarding/')body={mac_connected:false,completed:false};
   if(body!==undefined)return route.fulfill({json:body});
   if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
  });
  await page.goto('http://localhost/#intro');await page.locator('.header-signup').waitFor();
  const open=()=>page.waitForFunction(()=>document.getElementById('signup-modal').open);
  await page.locator('.header-signup').click();await open();
  assert.equal(new URL(page.url()).hash,'#intro');
  assert.equal(await page.locator('#signup-username').evaluate(e=>e===document.activeElement),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  assert.equal(await page.locator('#signup-modal').evaluate(e=>e.scrollWidth>e.clientWidth),false);
  await page.locator('#signup-password').fill('temporary-password');await page.keyboard.press('Escape');
  await page.waitForFunction(()=>!document.getElementById('signup-modal').open&&document.getElementById('signup-password').value==='');
  assert.equal(await page.locator('.header-signup').evaluate(e=>e===document.activeElement),true);
  await page.locator('.header-signup').click();await open();await page.locator('#signup-modal .login-modal-close').click();
  await page.locator('.header-signup').click();await open();await page.mouse.click(2,2);
  await page.waitForFunction(()=>!document.getElementById('signup-modal').open);
  // Switch between dialogs without changing the backdrop page or releasing its scroll lock.
  await page.locator('.header-login').click();await page.locator('#agent-login [data-page=signup]').click();await open();
  assert.equal(await page.locator('#login-modal').evaluate(e=>e.open),false);
  await page.locator('#signup-modal [data-login]').click();
  await page.waitForFunction(()=>document.getElementById('login-modal').open);
  assert.equal(await page.locator('#signup-modal').evaluate(e=>e.open),false);
  assert.equal(await page.evaluate(()=>document.body.style.overflow),'hidden');
  await page.locator('#agent-login [data-page=signup]').click();await open();
  await page.locator('#signup-username').fill('tester');await page.locator('#signup-password').fill('valid-password-123');
  await page.locator('#signup-password-confirm').fill('different-password');
  await page.locator('#signup-form button[type=submit]').click();
  await page.waitForFunction(()=>document.getElementById('signup-password_confirm-error').textContent.includes('일치'));
  assert.equal(requests.length,0);
  await page.locator('#signup-password-confirm').fill('valid-password-123');await page.locator('#signup-form button[type=submit]').click();
  await page.waitForFunction(()=>document.getElementById('signup-username-error').textContent.includes('이미'));
  assert.equal(await page.locator('#signup-modal').evaluate(e=>e.open),true);
  acceptSignup=true;await page.locator('#signup-username').fill('newtester');await page.locator('#signup-form button[type=submit]').click();
  await page.waitForFunction(()=>location.hash==='#onboarding'&&!document.getElementById('signup-modal').open);
  await page.waitForFunction(()=>document.body.style.overflow==='');assert.equal(requests.length,2);
  assert.equal(await page.locator('#signup-password').inputValue(),'');
  // A direct signup URL also opens a dialog, and closing it leaves the introduction.
  authenticated=false;await page.goto('http://localhost/#signup');await page.reload();await open();
  assert.equal(new URL(page.url()).hash,'#intro');
  assert.deepEqual(errors,[]);console.log('PASS signup modal, close/focus, auth switching, validation, CSRF, onboarding, direct URL:',width);
  await page.close();
 }}finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
