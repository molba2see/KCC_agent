const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});const errors=[],commands=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const preferences={revision:0,download_mode:'auto',screenshot_mode:'auto',icloud_mode:'auto',installers_enabled:true,installer_days:3,volatile_mode:'review',volatile_days:7};
  const link={id:'mac',label:'My Mac',connected:true,commands:[],snapshot:{preferences,capabilities:['preferences','expiry','preview'],assets:[{id:'a',name:'공지.txt',run:{status:'waiting_user',question:'폴더를 골라주세요.'}}],catalog:[],expiry:{total:1,entries:[{id:'e',asset_id:'a',name:'공지.txt',kind:'volatile',status:'pending',due_at:Date.now()/1000+7*86400}]}}};
  await page.route('http://localhost/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:true,username:'tester',csrf:'test',onboarding_completed:true}});
   if(url.pathname==='/api/v1/agent/status/')return route.fulfill({json:{links:[link]}});
   if(url.pathname==='/api/v1/agent/commands/'){
    const body=route.request().postDataJSON();commands.push(body);assert.equal(route.request().headers()['x-csrftoken'],'test');
    const command={id:'command-'+commands.length,action:body.action,status:body.action==='preferences'?'pending':'done',result:{ok:true,result:{}}};link.commands=[command];
    const entry=link.snapshot.expiry.entries.find(item=>item.id===body.entry_id);
    if(body.action==='expiry_confirm')entry.status='scheduled';
    if(body.action==='expiry_change'){entry.due_at=body.due_at;entry.status='scheduled';}
    if(body.action==='expiry_cancel'){link.snapshot.expiry.entries=[];link.snapshot.expiry.total=0;}
    if(body.action==='expiry_schedule'){link.snapshot.expiry.entries=[{id:'manual',asset_id:'a',name:'공지.txt',kind:'manual',status:'scheduled',due_at:body.due_at}];link.snapshot.expiry.total=1;}
    return route.fulfill({json:command});
   }
   if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
  });
  await page.goto('http://localhost/#settings');await page.locator('#policy-form').waitFor();
  assert.equal(await page.locator('[name=installer_days]').inputValue(),'3');
  await page.locator('[name=screenshot_mode]').selectOption('review');await page.locator('[name=installers_enabled]').selectOption('off');await page.locator('[name=volatile_days]').fill('10');
  await page.evaluate(()=>window.MoaLive.render());assert.equal(await page.locator('[name=volatile_days]').inputValue(),'10','Polling must preserve drafts');
  await page.locator('#policy-form button[type=submit]').click();await page.waitForFunction(()=>document.querySelector('.policy-status').textContent.includes('적용하고'));
  assert.deepEqual(commands[0],{link_id:'mac',action:'preferences',settings:{download_mode:'auto',screenshot_mode:'review',icloud_mode:'auto',installers_enabled:false,installer_days:3,volatile_mode:'review',volatile_days:10},revision:0});
  Object.assign(preferences,commands[0].settings,{revision:1});link.commands[0].status='done';await page.evaluate(()=>document.dispatchEvent(new Event('moa-cleanup-command')));
  await page.waitForFunction(()=>document.querySelector('.policy-status').textContent.includes('적용했습니다'));
  await page.reload();await page.locator('#policy-form').waitFor();assert.equal(await page.locator('[name=screenshot_mode]').inputValue(),'review');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(width===390)await page.waitForTimeout(1300);
  if(width===390)await page.screenshot({path:'/tmp/moa-onboarding-qa/settings-policy-mobile.png'});
  await page.evaluate(()=>window.page('trash'));await page.locator('[data-expiry-action=expiry_confirm]').click();
  await page.waitForFunction(()=>document.querySelector('#expiry-list .chip').textContent==='예약됨');
  await page.locator('[data-expiry-action=expiry_change]').click();await page.locator('.expiry-dialog').waitFor();
  await page.locator('.expiry-dialog button[type=submit]').click();await page.waitForFunction(()=>!document.querySelector('.expiry-dialog').open);
  assert.equal(commands[2].action,'expiry_change');assert.equal(typeof commands[2].due_at,'number');
  await page.locator('[data-expiry-action=expiry_cancel]').click();await page.waitForFunction(()=>!document.querySelector('[data-expiry-entry]'));
  await page.evaluate(()=>window.page('files'));await page.locator('#files [data-expiry-action=expiry_schedule]').click();await page.locator('.expiry-dialog button[type=submit]').click();await page.waitForFunction(()=>!document.querySelector('.expiry-dialog').open);
  assert.equal(commands[4].asset_id,'a');assert.equal(commands[4].action,'expiry_schedule');
  await page.evaluate(()=>window.page('trash'));assert.equal(await page.locator('[data-expiry-entry=manual]').count(),1);
  link.connected=false;await page.evaluate(()=>document.dispatchEvent(new Event('moa-cleanup-command')));await page.waitForFunction(()=>document.querySelector('[data-expiry-action=expiry_cancel]').disabled);
  await page.evaluate(()=>window.page('settings'));assert.equal(await page.locator('#policy-form button[type=submit]').isDisabled(),true);
  assert.deepEqual(errors,[]);console.log('PASS settings persistence/ack, dirty draft, expiry approve/change/cancel/schedule, offline and layout',width);await page.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
