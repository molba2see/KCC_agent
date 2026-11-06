// NODE_PATH=<directory containing playwright> node web/tests/cleanup-onboarding.cjs
const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});const errors=[],commands=[],actions=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const cleanup={status:'scanning',processed:2,total:2,classified:0,remaining:2,groups:[]};
  const state={mac_connected:true,cleanup,cleanup_link_id:'mac',cleanup_busy:false,cleanup_confirmed:false,iphone_icloud_confirmed:false,test_started:false,file_received:false,completed:false};
  await page.route('http://localhost/**',route=>{const u=new URL(route.request().url());let body;
   if(u.pathname==='/api/v1/auth/session/')body={authenticated:true,username:'tester',csrf:'test',onboarding_completed:false};
   else if(u.pathname==='/api/v1/onboarding/'){
    if(route.request().method()==='POST'){const action=route.request().postDataJSON().action;actions.push(action);if(action==='confirm_cleanup'||action==='defer_cleanup')state.cleanup_confirmed=true;}
    body=state;
   }else if(u.pathname==='/api/v1/agent/status/')body={links:[{id:'mac',label:'Mac',connected:true,snapshot:{assets:[],catalog:[],cleanup}}]};
   else if(u.pathname==='/api/v1/agent/commands/'){
    const command=route.request().postDataJSON();commands.push(command);assert.equal(route.request().headers()['x-csrftoken'],'test');
    const group=cleanup.groups.find(group=>group.id===command.group_id);if(group)group.status=command.action==='cleanup_confirm'?'approved':'dismissed';body={id:'command'};
   }
   if(body!==undefined)return route.fulfill({json:body});if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});return route.fulfill({path:path.join(__dirname,'../dist',u.pathname==='/'?'index.html':u.pathname.slice(1))});
  });
  await page.goto('http://localhost/#onboarding');await page.locator('#setup-dock-done').click();await page.locator('#setup-cleanup').waitFor();
  assert.equal(await page.locator('#setup-cleanup-done').isDisabled(),true);assert.equal(commands.length,0);
  cleanup.status='review';cleanup.groups=[{id:'group-new',name:'회의 자료',purpose:'회의록과 일정 자료를 모읍니다.',status:'pending',new_folder:true,destination:'iCloud Drive / 모아',files:[{id:'a',name:'회의록.txt'}]},{id:'group-old',name:'수업',purpose:'수업의 강의 자료입니다.',status:'pending',new_folder:false,destination:'선택한 폴더',files:[{id:'b',name:'lecture.pdf'}]}];
  await page.evaluate(()=>document.dispatchEvent(new Event('moa-page')));await page.locator('#onboarding-cleanup [data-cleanup-action=cleanup_confirm]').first().waitFor();
  if(width===390)await page.screenshot({path:'/tmp/moa-onboarding-qa/cleanup-onboarding-mobile.png'});
  await page.locator('#onboarding-cleanup [data-cleanup-group=group-new][data-cleanup-action=cleanup_confirm]').click();
  await page.waitForFunction(()=>!document.querySelector('#onboarding-cleanup [data-cleanup-group="group-new"]'));
  assert.deepEqual(commands[0],{link_id:'mac',action:'cleanup_confirm',group_id:'group-new'});
  await page.locator('#onboarding-cleanup [data-cleanup-group=group-old][data-cleanup-action=cleanup_dismiss]').click();
  await page.waitForFunction(()=>!document.getElementById('setup-cleanup-done').disabled);await page.locator('#setup-cleanup-done').click();await page.locator('#setup-iphone').waitFor();
  assert.deepEqual(actions,['confirm_cleanup']);assert.equal(commands[1].action,'cleanup_dismiss');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);console.log('PASS first-run cleanup screen, no automatic confirmation, group approve/dismiss, iPhone continuation, responsive layout:',width);await page.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
