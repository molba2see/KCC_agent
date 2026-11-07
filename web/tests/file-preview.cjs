const {chromium}=require('playwright');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000},isMobile:width<760,hasTouch:width<760});
  const errors=[],requests=[];let mode='text';page.on('pageerror',e=>errors.push(e.message));
  const link={id:'mac',label:'Mac',connected:true,commands:[],snapshot:{capabilities:['preview'],assets:[{id:'a',name:'회의록.txt',run:{status:'waiting_user',question:'어느 폴더인가요?'},why:[]}],catalog:[]}};
  await page.route('http://localhost/**',route=>{
   const url=new URL(route.request().url());
   if(url.pathname==='/api/v1/auth/session/')return route.fulfill({json:{authenticated:true,username:'tester',csrf:'test',onboarding_completed:true}});
   if(url.pathname==='/api/v1/agent/status/')return route.fulfill({json:{links:[link]}});
   if(url.pathname==='/api/v1/agent/commands/'){
    const body=route.request().postDataJSON();requests.push(body);assert.equal(route.request().headers()['x-csrftoken'],'test');
    link.commands=[{id:'command',action:'preview',status:mode==='failure'?'failed':'done',result:{result:mode==='failure'?'파일이 삭제되었습니다.':mode==='text'?{kind:'text',text:'회의 <script>window.injected=true</script> 내용',truncated:true}:{kind:'image',mime:'image/jpeg',data:'/9j/2Q=='}}}];
    return route.fulfill({json:{id:'command'}});
   }
   if(url.pathname.startsWith('/api/'))return route.fulfill({json:{}});
   return route.fulfill({path:path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1))});
  });
  await page.goto('http://localhost/#review');await page.locator('#review-list [data-preview-asset=a]').click();
  await page.locator('.file-preview pre').waitFor();
  assert.match(await page.locator('.file-preview pre').textContent(),/<script>/);assert.equal(await page.evaluate(()=>window.injected),undefined);
  assert.deepEqual(requests[0],{link_id:'mac',action:'preview',asset_id:'a'});
  assert.equal(await page.locator('.file-preview').evaluate(e=>e.scrollWidth>e.clientWidth),false);
  await page.keyboard.press('Escape');assert.equal(await page.locator('.file-preview').isVisible(),false);
  mode='image';await page.locator('#review-list [data-preview-asset=a]').click();await page.locator('.file-preview img').waitFor();await page.keyboard.press('Escape');
  mode='failure';await page.locator('#review-list [data-preview-asset=a]').click();await page.waitForFunction(()=>document.querySelector('.file-preview-status').textContent.includes('삭제'));await page.keyboard.press('Escape');
  link.connected=false;await page.locator('#review-list [data-preview-asset=a]').click();await page.waitForFunction(()=>document.querySelector('.file-preview-status').textContent.includes('연결되어'));await page.keyboard.press('Escape');
  link.connected=true;link.snapshot.capabilities=[];await page.locator('#review-list [data-preview-asset=a]').click();await page.locator('.file-preview a[download]').waitFor();assert.equal(requests.length,3);
  assert.deepEqual(errors,[]);console.log('PASS review previews, escaped text, image, errors, offline and helper upgrade',width);await page.close();
 }
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
