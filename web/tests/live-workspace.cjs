// Run with: NODE_PATH=<directory containing playwright> node web/tests/live-workspace.cjs
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||"chrome"});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:900}}); const errors=[],commands=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 let authenticated=true,sessionCalls=0;
 const link={id:'mac-1',label:'My Mac',connected:true,commands:[],snapshot:{catalog:[{id:'p',name:'실제 프로젝트',desc:'프로젝트 설명'}],assets:[{id:'a',name:'실제파일.txt',project:'p',why:['실제 근거'],plan:{action:'file',target:'/project/실제파일.txt'},run:{status:'waiting_user',candidates:['p']}}],trashed:[{i:0,name:'설치파일.dmg'}]}};
 await page.route('http://localhost/**',async route=>{
 const url=new URL(route.request().url());let body;
 if(url.pathname==='/api/v1/auth/session/'){sessionCalls++;body={authenticated,csrf:'test',username:'tester'};}
 else if(url.pathname==='/api/v1/agent/status/')body={links:[link]};
 else if(url.pathname==='/api/v1/agent/commands/'){commands.push(route.request().postDataJSON());body={id:'command'};}
 else if(url.pathname==='/api/v1/auth/logout/'){authenticated=false;body={};}
 if(body!==undefined)return route.fulfill({json:body});
 if(url.pathname.startsWith('/api/'))return route.fulfill({status:404,json:{detail:'Not a local installation'}});
 const filename=path.join(__dirname,'../dist',url.pathname==='/'?'index.html':url.pathname.slice(1));
 return route.fulfill({path:filename});
 });
 await page.addInitScript(()=>{localStorage.setItem('moa-operations-demo-v2',JSON.stringify({files:[{name:'오래된시연파일.txt'}]}));localStorage.setItem('moa-draft-v1','legacy')});
 await page.goto('http://localhost/');
 await page.waitForFunction(()=>document.querySelector('#recent-files').textContent.includes('실제파일.txt'));
 assert.equal(sessionCalls,1,'Initial page load should request one CSRF session');
 assert.equal(await page.locator('#stat-folders').textContent(),'1');
 await page.locator('.desktop-nav [data-page="files"]').click();
 await page.locator('#file-search').fill('없는파일');assert.equal(await page.locator('#all-files [data-asset]').count(),0);
 await page.locator('#file-search').fill('실제 프로젝트');assert.equal(await page.locator('#all-files [data-asset]').count(),1);
 await page.locator('.desktop-nav [data-page="review"]').click();
 await page.locator('#review-list [data-agent-action="answer"]').click();
 await page.waitForTimeout(100);assert.deepEqual(commands[0],{link_id:'mac-1',action:'answer',asset_id:'a',project_id:'p'});
 await page.locator('#review-list [data-agent-action="approve"]').click();
 await page.waitForTimeout(100);assert.equal(commands[1].action,'approve');
 await page.locator('.desktop-nav [data-page="folders"]').click();assert.match(await page.locator('#folder-detail').textContent(),/실제파일/);
 await page.locator('.desktop-nav [data-page="trash"]').click();await page.locator('#deleted-list [data-trash-index]').click();
 await page.waitForTimeout(100);assert.equal(commands[2].action,'restore_trashed');
 assert.equal(await page.locator('#workspace-mode, #reset-demo').count(),0);
 assert.equal(await page.locator('#review-list [data-asset]').count(),1);
 assert.equal(await page.evaluate(()=>localStorage.getItem('moa-operations-demo-v2')),null);
 await page.locator('.desktop-nav [data-page="connection"]').click();await page.locator('#agent-logout').click();
 await page.waitForFunction(()=>!document.querySelector('#recent-files').textContent.includes('실제파일.txt'));
 assert.equal(await page.locator('#all-files [data-asset]').count(),0);
 for(const id of ['stat-today','stat-pending','stat-folders','nav-pending'])assert.equal(await page.locator('#'+id).textContent(),'0');
 assert.equal(await page.locator('.status-word').textContent(),'연결 확인');
 for(const id of ['recent-files','pending-summary','folder-summary','all-files','review-list','folder-list','folder-detail','scheduled-list','deleted-list','journal-list'])assert.equal(await page.locator('#'+id+' button[data-page=connection]').count(),1);
 assert.equal(await page.evaluate(()=>localStorage.getItem('moa-draft-v1')),null);
 assert.equal(await page.locator('body').innerText().then(text=>text.includes('오래된시연파일')),false);
 assert.deepEqual(errors,[]);console.log('PASS: live pages, search, project grouping, answer, approve, restore, live-only workspace, logout; no browser errors');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
