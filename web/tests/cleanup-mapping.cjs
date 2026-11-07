const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});const errors=[],commands=[],dialogs=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>{dialogs.push(d.message());return d.accept()});
  const newPath='iCloud Drive / 모아 / 제주여행 준비',existingPath='내 Mac (~) / Documents / 경제학';
  const groups=[{id:'existing',name:'경제학',purpose:'경제학 강의자료입니다.',status:'pending',new_folder:false,destination_path:existingPath,files:[{id:'a',name:'강의자료.pdf',source:'내 Mac (~) / Downloads',destination:existingPath,target_name:'강의자료.pdf'}]},
   {id:'new',name:'제주여행 준비',purpose:'항공권과 숙소 예약을 함께 보관합니다.',status:'pending',new_folder:true,destination_path:newPath,files:Array.from({length:9},(_,i)=>({id:'n'+i,name:i===0?'예약 <script>window.injected=true</script>.txt':'숙소 예약 확인서 '+i+'.pdf',source:'다운로드',source_name:i===0?'booking.txt':undefined,destination:newPath}))}];
  const link={id:'mac',label:'Mac',connected:true,commands:[],snapshot:{assets:[],catalog:[],cleanup:{status:'review',pending_groups:2,groups}}};
  await page.route('http://localhost/**',route=>{const u=new URL(route.request().url());
   if(u.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:true,username:'tester',csrf:'test',onboarding_completed:true}});
   if(u.pathname==='/api/v1/agent/status/')return route.fulfill({json:{links:[link]}});
   if(u.pathname==='/api/v1/agent/commands/'){commands.push(route.request().postDataJSON());return route.fulfill({json:{id:'command'}})}
   if(u.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.fulfill({path:path.join(__dirname,'../dist',u.pathname==='/'?'index.html':u.pathname.slice(1))});
  });
  await page.goto('http://localhost/#review');await page.locator('#review [data-proposal-kind=new]').waitFor();
  for(const name of ['files','folders','review']){
   await page.evaluate(name=>window.page(name),name);
   const panel=page.locator('#'+name);
   assert.match(await panel.locator('[data-proposal-kind=existing] .cleanup-file-to').innerText(),/Documents \/ 경제학 \/ 강의자료.pdf/);
   assert.match(await panel.locator('[data-proposal-kind=new] .cleanup-folder-plan').innerText(),/아직 없는 폴더/);
   assert.match(await panel.locator('[data-proposal-kind=new] .cleanup-folder-plan').innerText(),/iCloud Drive \/ 모아 \/ 제주여행 준비/);
   await panel.locator('[data-proposal-kind=new] summary').click();
   assert.equal(await panel.locator('[data-proposal-kind=new] .cleanup-file-map-row:visible').count(),9);
   assert.equal(await page.evaluate(()=>window.injected),undefined);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  }
  assert.equal(commands.length,0,'Viewing mappings must not approve or create a folder');
  if(width===390)await page.screenshot({path:'/tmp/moa-onboarding-qa/cleanup-mapping-mobile.png'});
  await page.locator('#review [data-cleanup-group=new][data-cleanup-action=cleanup_confirm]').click();
  await page.waitForFunction(()=>document.querySelector('#review .cleanup-action-status').textContent.includes('처리'));
  assert.deepEqual(commands[0],{link_id:'mac',action:'cleanup_confirm',group_id:'new'});
  assert(dialogs[0].includes(newPath));assert(dialogs[0].includes('\n정리 위치:'));assert(dialogs[0].includes('새 폴더'));
  assert.deepEqual(errors,[]);console.log('PASS explicit file-to-folder mapping, new-folder plan, all-file disclosure, safe text and confirm destination',width);await page.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
