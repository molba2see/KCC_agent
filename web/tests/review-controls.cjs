// NODE_PATH=<directory containing playwright> node web/tests/review-controls.cjs
const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});try{
 for(const width of [1440,390,320]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});const errors=[],commands=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const link={id:'mac',label:'My Mac',connected:true,commands:[],snapshot:{catalog:[{id:'recommended',name:'경제학개론',desc:'과목 자료'},{id:'chosen',name:'프로젝트 기획 자료'}],assets:[{id:'file',name:'수업_강의자료.pdf',why:['과목 폴더를 확인해 주세요.'],run:{status:'waiting_user',question:'어느 폴더의 자료인가요?',candidates:['recommended']}}]}};
  await page.route('http://localhost/**',route=>{const u=new URL(route.request().url());if(u.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:true,username:'tester',csrf:'test',onboarding_completed:true}});if(u.pathname==='/api/v1/agent/status/')return route.fulfill({json:{links:[link]}});if(u.pathname==='/api/v1/agent/commands/'){commands.push(route.request().postDataJSON());return route.fulfill({json:{id:'cmd'}})}if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});return route.fulfill({path:path.join(__dirname,'../dist',u.pathname==='/'?'index.html':u.pathname.slice(1))})});
  await page.goto('http://localhost/#review');const card=page.locator('#review-list [data-asset=file]');await card.waitFor();
  assert.equal(await card.locator('[data-review-method=existing]').getAttribute('aria-pressed'),'true');
  await card.locator('.agent-project').selectOption('chosen');assert.equal(commands.length,0);
  await card.locator('[data-review-method=keep]').click();assert.equal(await card.locator('[data-method-panel=keep]').isVisible(),true);assert.equal(await card.locator('[data-method-panel=existing]').isVisible(),false);assert.equal(commands.length,0);
  await card.locator('[data-review-method=existing]').click();assert.equal(await card.locator('.agent-project').inputValue(),'chosen');
  if(width!==320)await page.screenshot({path:`/tmp/moa-onboarding-qa/review-controls-${width}.png`});
  await Promise.all([page.waitForResponse(response=>response.url().endsWith('/api/v1/agent/commands/')),card.locator('[data-agent-action=answer]').click()]);assert.deepEqual(commands[0],{link_id:'mac',action:'answer',asset_id:'file',project_id:'chosen'});
  link.snapshot.assets[0].why=['자동 갱신된 상태입니다.'];await page.evaluate(()=>document.querySelector('.desktop-nav [data-page=review]').click());await card.getByText('자동 갱신된 상태입니다.').waitFor();assert.equal(await card.locator('.agent-project').inputValue(),'chosen');
  await card.locator('.agent-project').selectOption('__new_folder__');assert.equal(await card.locator('[data-method-panel=new]').isVisible(),true);
  assert.equal(await card.locator('[data-new-folder]').isVisible(),true);assert.equal(await card.locator('[data-new-folder]').isDisabled(),false);
  await card.locator('[data-review-method=keep]').click();await Promise.all([page.waitForResponse(response=>response.url().endsWith('/api/v1/agent/commands/')),card.locator('[data-agent-action=keep]').click()]);assert.equal(commands.at(-1).action,'keep');
  link.connected=false;await page.evaluate(()=>document.querySelector('.desktop-nav [data-page=review]').click());await page.waitForFunction(()=>document.querySelector('#review-list [data-review-method=existing]').disabled);assert.equal(await card.locator('[data-agent-action=keep]').isDisabled(),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);console.log('PASS review methods, destination selection/persistence, answer/keep commands, new folder, offline state, responsive layout:',width);await page.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
