const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const agent=fs.readFileSync(path.join(__dirname,'../dist/agent.js'),'utf8');
const markup={reviewChoices:new Map(),document:{addEventListener(){}},esc:String,basename:s=>String(s).split('/').pop()};
vm.createContext(markup);
vm.runInContext(agent.slice(agent.indexOf('function assetHTML('),agent.indexOf('function linkHTML(')),markup);
let html=markup.assetHTML({id:'file',name:'AWS.pdf',run:{status:'waiting_user',candidates:['old']}},{connected:true,snapshot:{catalog:[{id:'old',name:'Old'},{id:'new',name:'New folder'}]}});
assert.match(html,/value="new"/); // Newly added folders stay selectable despite stale model candidates.
assert.match(html,/value="__new_folder__"/);
assert.match(html,/data-new-folder/);
html=markup.assetHTML({id:'file',run:{status:'waiting_user'}},{connected:true,snapshot:{catalog:[]}});
assert.match(html,/data-agent-action="answer"/);
assert.match(html,/data-new-folder/); // First folder can be created even with no existing projects.
(async()=>{
 const status={textContent:''},button={},events={};let authenticated=true;
 const context={navigator:{userAgent:'Macintosh',platform:'MacIntel',maxTouchPoints:0},location:{href:'https://example.test'},fetch:async()=>({ok:true,json:async()=>({authenticated})}),document:{getElementById:id=>id==='folder-add'?button:status,querySelector:()=>null,addEventListener:(type,callback)=>events[type]=callback},window:{location:{href:''}}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../dist/folder-manager.js'),'utf8'),context);
 await context.window.MoaFolders.open(status,true);
 assert.equal(context.window.location.href,'moa-helper://folders?create=1');
 assert.match(status.textContent,/답변/);
 await button.onclick();
 assert.equal(context.window.location.href,'moa-helper://folders');
 authenticated=false;context.window.location.href='';
 await context.window.MoaFolders.open(status,true);
 assert.equal(context.window.location.href,'');
 assert.match(status.textContent,/로그인/);
 console.log('PASS new-folder reply with empty/stale candidates, persistent additions, create link, authentication');
})().catch(error=>{console.error(error);process.exitCode=1});
