const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});const errors=[],commands=[];
  page.on('pageerror',error=>errors.push(error.message));page.on('dialog',dialog=>dialog.accept());
  const cleanup={status:'review',pending_groups:1,groups:[{id:'g',name:'수업',purpose:'강의 문서를 보관합니다.',status:'pending',new_folder:false,destination:'선택한 폴더',files:[{id:'a',name:'lecture.pdf'}]}]};
  const link={id:'mac',label:'Mac',connected:true,commands:[],snapshot:{capabilities:['cleanup_scan','preview'],assets:[],catalog:[],cleanup}};
  await page.route('http://localhost/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:true,username:'tester',csrf:'test',onboarding_completed:true}});
   if(url.pathname==='/api/v1/agent/status/')return route.fulfill({json:{links:[link]}});
   if(url.pathname==='/api/v1/agent/commands/'){
    const body=route.request().postDataJSON();commands.push(body);assert.equal(route.request().headers()['x-csrftoken'],'test');
    if(body.action==='cleanup_scan'){cleanup.status='scanning';cleanup.groups=[];cleanup.pending_groups=0;}
    else{cleanup.groups[0].status=body.action==='cleanup_confirm'?'approved':'dismissed';cleanup.pending_groups=0;}
    return route.fulfill({json:{id:'command'}});
   }
   if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
  });
  await page.goto('http://localhost/#files');
  for(const name of ['files','folders','review']){
   await page.evaluate(name=>window.page(name),name);
   await page.locator('#'+name+' [data-cleanup-group=g][data-cleanup-action=cleanup_confirm]').waitFor();
   assert.equal(await page.locator('#'+name+' [data-preview-asset=a]').count(),1);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  }
  assert.equal(commands.length,0,'Scanning proposals never approves or moves files automatically');
  await page.evaluate(()=>window.page('files'));
  await page.locator('#files [data-cleanup-action=cleanup_confirm]').click();
  await page.waitForFunction(()=>!document.querySelector('#files [data-cleanup-action=cleanup_confirm]'));
  assert.deepEqual(commands[0],{link_id:'mac',action:'cleanup_confirm',group_id:'g'});
  await page.evaluate(()=>window.page('folders'));
  await page.locator('#folders [data-cleanup-action=cleanup_scan]').click();
  await page.locator('#folders progress').waitFor();
  await page.evaluate(()=>window.page('review'));await page.locator('#review progress').waitFor();
  assert.equal(commands[1].action,'cleanup_scan');assert.deepEqual(errors,[]);
  console.log('PASS post-onboarding cleanup in files/folders/review, preview links, explicit confirmation and rescan',width);await page.close();
 }
}finally{await browser.close()}})().catch(error=>{console.error(error);process.exitCode=1});
