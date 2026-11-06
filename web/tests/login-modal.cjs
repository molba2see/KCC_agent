// NODE_PATH=<directory containing playwright> node web/tests/login-modal.cjs
const {chromium}=require('playwright');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{
  let page;let authenticated=false,acceptLogin=false;
  const errors=[],requests=[];
  async function createPage(width){
   const page=await browser.newPage({viewport:{width,height:900},isMobile:width<760,hasTouch:width<760});
   page.on('pageerror',e=>errors.push(e.message));
  await page.route('http://localhost/**',async route=>{
   const url=new URL(route.request().url());let body;
   if(url.pathname==='/api/v1/auth/session/')body={authenticated,username:authenticated?'tester':null,display_name:'테스터',onboarding_completed:true,csrf:'test'};
   else if(url.pathname==='/api/v1/agent/status/')body={links:[]};
   else if(url.pathname==='/api/v1/auth/login/'){
    requests.push(route.request().postDataJSON());
    assert.equal(route.request().headers()['x-csrftoken'],'test');
    if(!acceptLogin)return route.fulfill({status:400,json:{detail:'아이디 또는 비밀번호를 확인하세요.'}});
    authenticated=true;body={authenticated:true,username:'tester'};
   }else if(url.pathname==='/api/v1/auth/logout/'){authenticated=false;body={};}
   if(body!==undefined)return route.fulfill({json:body});
   if(url.pathname.startsWith('/api/'))return route.fulfill({status:404,json:{}});
   return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
  });
   return page;
  }
  for(const width of [1440,390,320]){
   if(page)await page.close();
   page=await createPage(width);await page.goto('http://localhost/');
   await page.locator('.header-login').waitFor();const hash=new URL(page.url()).hash;
   await page.locator('.header-login').click();await page.waitForFunction(()=>document.getElementById('login-modal').open);
   assert.equal(new URL(page.url()).hash,hash);
   assert.equal(await page.locator('#agent-login-form [name=username]').evaluate(e=>e===document.activeElement),true);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await page.locator('#agent-login-form [name=password]').fill('temporary');
   await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.getElementById('login-modal').open);
   await page.waitForFunction(()=>document.querySelector('#agent-login-form [name=password]').value==='');
   assert.equal(await page.locator('.header-login').evaluate(e=>e===document.activeElement),true);
   await page.locator('.header-login').click();await page.locator('#login-modal .login-modal-close').click();
   await page.locator('.header-login').click();await page.mouse.click(2,2);
   assert.equal(await page.locator('#login-modal').evaluate(e=>e.open),false);
   console.log('PASS modal, current page, focus, Escape, close and backdrop',width);
  }
  await page.locator('.header-login').click();
  await page.locator('#agent-login-form [name=username]').fill('tester');
  await page.locator('#agent-login-form [name=password]').fill('wrong-password');
  await page.locator('#agent-login-form button').click();
  await page.waitForFunction(()=>document.getElementById('agent-login-error').textContent.includes('확인'));
  assert.equal(await page.locator('#login-modal').evaluate(e=>e.open),true);
  acceptLogin=true;await page.locator('#agent-login-form [name=password]').fill('correct-password');
  await page.locator('#agent-login-form button').click();
  await page.locator('.header-account-toggle').waitFor();await page.waitForFunction(()=>!document.getElementById('login-modal').open);
  assert.equal(requests.length,2);await page.waitForFunction(()=>document.body.style.overflow==='');
  await page.locator('.header-account-toggle').click();await page.locator('.account-manage').click();
  await page.locator('#agent-logout').click();await page.locator('.header-login').waitFor();
  const signupHash=new URL(page.url()).hash;await page.locator('.header-signup').click();await page.locator('#signup-modal [data-login]').click();
  assert.equal(await page.locator('#login-modal').evaluate(e=>e.open),true);
  assert.equal(new URL(page.url()).hash,signupHash);
  await page.locator('#agent-login [data-page=signup]').click();
  assert.equal(await page.locator('#login-modal').evaluate(e=>e.open),false);
  assert.deepEqual(errors,[]);
  console.log('PASS login error, CSRF, successful login, session header, logout, signup links; no browser errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
