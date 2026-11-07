/* Live workspace uses the authenticated Mac snapshot and command queue. */
(()=>{
if(location.protocol==='http:'&&!['localhost','127.0.0.1'].includes(location.hostname)){location.replace('https:'+location.href.slice(location.protocol.length));return}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const basename=s=>String(s||'').split('/').pop();
let csrf='',authenticated=false,latest=[],loadError='',liveFolder='';
const reviewChoices=new Map();
async function api(path,body){const response=await fetch('/api/v1/'+path,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRFToken':csrf}:{},body:body?JSON.stringify(body):undefined});const result=await response.json().catch(()=>({detail:'서버 응답을 읽을 수 없습니다.'}));if(!response.ok){const error=new Error(result.detail||result.error||`HTTP ${response.status}`);error.fields=result.errors||{};throw error;}return result}
async function session(){try{const s=await api('auth/session/');csrf=s.csrf;authenticated=s.authenticated;window.MoaSession={authenticated:s.authenticated,username:s.username,display_name:s.display_name};document.dispatchEvent(new CustomEvent("moa-session",{detail:window.MoaSession}));document.getElementById('agent-login').hidden=authenticated;document.getElementById('signup-form').hidden=authenticated;document.getElementById('signup-already').hidden=!authenticated;document.getElementById('agent-live').hidden=!authenticated;document.getElementById('agent-account').textContent=s.username?`${s.display_name||s.username}`:' ';renderWorkspace();if(authenticated&&!s.onboarding_completed&&!location.hash&&!['localhost','127.0.0.1'].includes(location.hostname))page('onboarding');if(authenticated)await refresh();else{latest=[];reviewChoices.clear();renderWorkspace()}}catch(e){loadError='서버 연결 실패: '+e.message;renderWorkspace();document.getElementById('agent-login-error').textContent=e.message}}
const needsReview=a=>!a.archived&&!a.keep;
const group=(link,html)=>`<section data-link="${esc(link.id)}"><h3>${esc(link.label)} · ${link.connected?'연결됨':'연결 끊김 · 마지막 수신 상태'}</h3>${html}</section>`;
function renderWorkspace(){
 const links=authenticated?latest:[],entries=links.flatMap(l=>(l.snapshot?.assets||[]).map(a=>({a,l}))),folders=links.flatMap(l=>(l.snapshot?.catalog||[]).map(p=>({...p,key:l.id+':'+p.id,l}))),pending=entries.filter(({a})=>needsReview(a));
 const blank=`<div class="empty">${esc(loadError||(!authenticated?'연결 화면에서 로그인하면 실제 파일이 표시됩니다.':links.length?'수신된 항목이 없습니다.':'Mac 에이전트와 브리지를 실행해 주세요.'))}<button class="ghost" data-page="connection">연결 확인</button></div>`;
 const pendingCount=links.reduce((sum,link)=>sum+(link.snapshot?.counts?.pending??(link.snapshot?.assets||[]).filter(needsReview).length),0);
 const movedCount=links.reduce((sum,link)=>sum+(link.snapshot?.counts?.moved??(link.snapshot?.assets||[]).filter(asset=>asset.archived).length),0);
 const put=(id,html)=>document.getElementById(id).innerHTML=html||blank;
 document.getElementById('nav-pending').textContent=pendingCount;document.getElementById('stat-pending').textContent=pendingCount;document.getElementById('stat-folders').textContent=folders.length;
 document.getElementById('stat-today').textContent=movedCount;
 document.querySelector('#stat-today').previousElementSibling.textContent='이동한 파일';document.querySelector('#stat-today').nextElementSibling.textContent='현재 에이전트 상태 기준';
 document.querySelector('.status-word').textContent=!authenticated?'연결 확인':links.some(l=>l.connected)?'연결됨':'연결 대기';
 document.getElementById('review-count').textContent=`${pendingCount}개 대기`;
 if(!authenticated){
  for(const id of ['files-cleanup','folders-cleanup']){const target=document.getElementById(id);if(target)target.innerHTML='';}
  for(const id of ['recent-files','pending-summary','folder-summary','all-files','review-list','folder-list','folder-detail','scheduled-list','deleted-list','journal-list'])put(id,blank);
  return;
 }
 const cleanupHTML=links.length?links.map(link=>window.MoaCleanup?.html(link.snapshot?.cleanup,link.id,(link.commands||[]).some(command=>['pending','running'].includes(command.status)),link.connected)||'').join(''):(window.MoaCleanup?.html(null)||'');
 for(const id of ['files-cleanup','folders-cleanup']){const target=document.getElementById(id);if(target)target.innerHTML=cleanupHTML;}
 const row=({a,l})=>group(l,assetHTML(a,l));
 put('recent-files',entries.slice(0,5).map(row).join(''));
 put('pending-summary',authenticated?`<strong>${pendingCount}개 파일에 확인이 필요합니다.</strong><p>답변 후 생성된 이동 계획을 승인하세요.</p><button class="primary" data-page="review">분류 대기 보기</button>`:blank);
 put('folder-summary',folders.map(p=>`<div class="folder-summary-row"><b>${esc(p.name)}</b><span>${p.l.snapshot?.counts?.folders?.[p.id]??entries.filter(({a,l})=>l.id===p.l.id&&a.project===p.id).length}개</span></div>`).join(''));
 const q=document.getElementById('file-search').value.trim().toLowerCase();
 const limited=links.filter(link=>link.snapshot?.assets_truncated);
 const limitNote=limited.length?`<div class="empty">전체 ${links.reduce((sum,link)=>sum+(link.snapshot?.counts?.files??link.snapshot.assets.length),0)}개 중 최근 ${entries.length}개를 표시합니다. 검색은 현재 표시한 파일 안에서 진행해요.</div>`:'';
 put('all-files',limitNote+entries.filter(({a,l})=>(fileFilter==='all'||(fileFilter==='other'?needsReview(a):!needsReview(a)))&&(!q||`${a.name} ${(l.snapshot.catalog||[]).find(p=>p.id===a.project)?.name||''}`.toLowerCase().includes(q))).map(row).join(''));
 put('review-list',cleanupHTML+pending.filter(({a,l})=>!(l.snapshot?.cleanup?.groups||[]).some(group=>group.status==='pending'&&group.files?.some(file=>file.id===a.id))).map(row).join(''));
 put('folder-list',folders.map(p=>`<button data-live-folder="${esc(p.key)}" class="${liveFolder===p.key?'active':''}">${esc(p.name)} · ${esc(p.l.label)}</button>`).join(''));
 const folder=folders.find(p=>p.key===liveFolder)||folders[0];
 put('folder-detail',folder?`<h2>${esc(folder.name)}</h2><p>${esc(folder.desc||'프로젝트 설명 없음')}</p><p>프로젝트 지침 수정은 Mac에서 _project.md를 편집해 주세요.</p>${entries.filter(({a,l})=>l.id===folder.l.id&&a.project===folder.id).map(row).join('')}`:'');
 put('scheduled-list',entries.filter(({a})=>!a.archived&&a.plan?.action==='archive').map(row).join('')||'<div class="empty">보관 승인 대기 파일이 없습니다. 보관은 삭제가 아닙니다.</div>');
 put('deleted-list',links.map(l=>group(l,(l.snapshot?.trashed||[]).map(t=>`<div class="journal-row"><span>${esc(t.name)}</span><button class="ghost" data-trash-index="${Number(t.i)}">복구 요청</button></div>`).join(''))).join(''));
 put('journal-list',links.map(l=>group(l,(l.commands||[]).map(c=>`<div class="journal-row">${esc(c.action)} · ${esc(c.status)} · ${esc(new Date(c.created_at).toLocaleString('ko-KR'))}${c.status==='failed'?' · '+esc(c.result?.result||'실행 실패'):''}</div>`).join(''))).join(''));
}
// Older cached navigation scripts use enabled to choose their renderer.
// Always delegate them to the live workspace instead of their sample-data fallback.
window.MoaLive={get enabled(){return true},render:renderWorkspace,selectFolder(id){liveFolder=id;renderWorkspace()}};
document.getElementById('folder-list').addEventListener('click',e=>{const b=e.target.closest('[data-live-folder]');if(b){liveFolder=b.dataset.liveFolder;renderWorkspace()}});
function assetHTML(a,link){
 const busy=(link.commands||[]).some(command=>['pending','running'].includes(command.status));
 const run=a.run||{},plan=a.plan||{},name=basename(a.name||a.original||a.path)||a.id;
 const reasons=(a.why||[]).slice(0,4).map(reason=>`<p>${esc(reason)}</p>`).join('');
 const disabled=busy||!link.connected?'disabled':'';
 const waiting=run.status==='waiting_user'&&!a.archived&&!a.keep;
 const canApprove=['file','archive'].includes(plan.action)&&!a.archived;
 return `<article class="agent-asset" data-asset="${esc(a.id)}"><div class="review-card-header"><h3><button class="file-preview-trigger" type="button" data-preview-link="${esc(link.id)}" data-preview-asset="${esc(a.id)}" data-preview-name="${esc(name)}" aria-label="${esc(name)} 미리보기">${esc(name)} ↗</button></h3><span class="chip ${run.status==='waiting_user'?'other':''}">${esc(a.archived?'이동됨':run.status==='waiting_user'?'질문 대기':plan.action==='file'?'승인 대기':plan.action||'판단 중')}</span></div>${reasons||(!run.question?'<p>판단 근거를 기다리는 중입니다.</p>':'')}${plan.target?`<p>계획: ${esc(plan.action)} → ${esc(basename(plan.target))}</p>`:''}${run.question?`<p class="review-question"><b>질문</b> ${esc(run.question)}</p>`:''}${waiting?reviewControlsHTML(a,link,busy):''}<div class="actions asset-footer">${canApprove?`<button class="primary" ${disabled} data-agent-action="approve">계획 승인</button>`:''}${!waiting&&!a.archived&&!a.keep?`<button class="ghost" ${disabled} data-agent-action="keep">그대로 두기</button>`:''}${a.archived?`<button class="ghost" ${disabled} data-agent-action="undo">이동 되돌리기</button>`:''}</div></article>`;
}
function reviewControlsHTML(a,link,busy){
 const choices=[...(link.snapshot.catalog||[])].sort((left,right)=>Number((a.run.candidates||[]).includes(right.id))-Number((a.run.candidates||[]).includes(left.id)));
 const key=link.id+':'+a.id;
 const draft=reviewChoices.get(key)||{};
 const selected=choices.some(project=>project.id===draft.project)?draft.project:choices[0]?.id;
 const method=draft.method==='keep'||draft.method==='new'?draft.method:choices.length?'existing':'new';
 const disabled=busy||!link.connected?'disabled':'';
 const folderIcon='<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M3 10h18" stroke="currentColor" stroke-width="1.6"/></svg>';
 const options=choices.map(project=>`<option value="${esc(project.id)}" ${project.id===selected?'selected':''}>${esc(project.name)}</option>`).join('');
 return `<div class="review-decision"><span class="review-field-label">처리 방법</span><div class="review-methods" role="group" aria-label="처리 방법">${[['existing','폴더에 정리'],['new','새 폴더'],['keep','그대로 두기']].map(([value,label])=>`<button type="button" data-review-method="${value}" aria-pressed="${method===value}" ${disabled||value==='existing'&&!choices.length?'disabled':''}>${value==='existing'?folderIcon:value==='new'?'<span aria-hidden="true">＋</span>':'<span aria-hidden="true">−</span>'}<span>${label}</span></button>`).join('')}</div>
 <div data-method-panel="existing" ${method!=='existing'?'hidden':''}><label class="review-destination"><span class="review-field-label">대상 폴더</span><span class="review-select-shell"><span class="review-folder-icon">${folderIcon}</span><select class="agent-project" aria-label="대상 폴더" ${disabled}>${options}<option value="__new_folder__">＋ 새 폴더 만들기…</option></select><svg class="review-select-chevron" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m6 8 4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></span></label><div class="review-decision-footer"><p>폴더를 알려 주면 이동 계획을 준비해요.</p><button class="primary" ${disabled||!choices.length?'disabled':''} data-agent-action="answer">이 폴더로 답변 <span aria-hidden="true">↗</span></button></div></div>
 <div data-method-panel="new" ${method!=='new'?'hidden':''}><div class="review-method-note"><span class="review-folder-icon">${folderIcon}</span><div><strong>새로운 정리 공간이 필요한가요?</strong><p>Mac에서 폴더를 만든 뒤 목록에서 골라 주세요.</p></div></div><div class="review-decision-footer"><p>기존 폴더와 정리 지침은 유지돼요.</p><button class="primary" ${disabled} data-new-folder>새 폴더 만들기 <span aria-hidden="true">＋</span></button></div></div>
 <div data-method-panel="keep" ${method!=='keep'?'hidden':''}><div class="review-method-note"><div><strong>현재 위치에 그대로 둘게요.</strong><p>파일을 옮기지 않고 분류 대기에서 제외합니다.</p></div></div><div class="review-decision-footer"><p>Mac에 유지 요청을 보내요.</p><button class="primary" ${disabled} data-agent-action="keep">그대로 두기</button></div></div>
 <span class="review-create-status" data-folder-create-status role="status"></span></div>`;
}
function setReviewMethod(card,method){
 const link=card.closest('[data-link]');if(!link)return;
 const select=card.querySelector('.agent-project');
 if(method==='existing'&&select.value==='__new_folder__')select.value=[...select.options].find(option=>option.value!=='__new_folder__')?.value||'';
 reviewChoices.set(link.dataset.link+':'+card.dataset.asset,{method,project:select.value});
 card.querySelectorAll('[data-review-method]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.reviewMethod===method)));
 card.querySelectorAll('[data-method-panel]').forEach(panel=>panel.hidden=panel.dataset.methodPanel!==method);
}
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-review-method]');if(!button||button.disabled)return;
 setReviewMethod(button.closest('[data-asset]'),button.dataset.reviewMethod);
});
document.addEventListener('change',event=>{
 if(!event.target.matches('.agent-project'))return;
 const card=event.target.closest('[data-asset]');
 setReviewMethod(card,event.target.value==='__new_folder__'?'new':'existing');
});
function linkHTML(link){const s=link.snapshot||{},assets=s.assets||[],trash=s.trashed||[],commands=link.commands||[];return `<section class="agent-state" data-link="${esc(link.id)}"><div class="review-card-header"><h2>${esc(link.label)}</h2><span class="agent-status ${link.connected?'online':''}">${link.connected?'연결됨':'연결 대기'}${link.last_seen_at?' · 마지막 동기화 '+esc(new Date(link.last_seen_at).toLocaleString('ko-KR')):''}</span></div><p>${link.connected?'Mac 에이전트 상태를 표시합니다. 승인한 계획만 실행기로 전달됩니다.':'Mac 에이전트와 브리지 프로그램을 실행하면 여기에 상태가 나타납니다.'}</p><div class="agent-assets">${assets.length?assets.map(a=>assetHTML(a,link)).join(''):'<div class="empty">전송된 파일 상태가 없습니다.</div>'}</div>${trash.length?`<div class="agent-trash"><h3>Mac 휴지통으로 이동한 설치 파일</h3>${trash.map(t=>`<div class="journal-row"><span>${esc(basename(t.name||t.path||t.trash))}</span><button class="ghost" data-trash-index="${Number(t.i)}">복구 요청</button></div>`).join('')}</div>`:''}${commands.length?`<div class="agent-trash"><h3>최근 명령</h3>${commands.slice(0,5).map(c=>`<div class="agent-command ${c.status==='failed'?'failed':''}">${esc(c.action)} · ${esc(c.status)}${c.status==='failed'?' · '+esc(c.result?.result||'실행 실패'):''}</div>`).join('')}</div>`:''}</section>`}
async function refresh(){if(!authenticated)return;try{const r=await api('agent/status/');if(!authenticated)return;const changed=JSON.stringify(latest)!==JSON.stringify(r.links||[])||!!loadError;latest=r.links||[];loadError='';if(changed)renderWorkspace();document.getElementById('agent-links').innerHTML=latest.length?latest.map(linkHTML).join(''):'<div class="empty">연결된 Mac이 없습니다. 위의 이 Mac 연결 버튼으로 연결을 시작하세요.</div>'}catch(e){latest=[];loadError='연결 상태를 읽지 못했습니다: '+e.message;renderWorkspace();document.getElementById('agent-links').innerHTML=`<div class="empty">연결 상태를 읽지 못했습니다: ${esc(e.message)}</div>`}}
document.getElementById('agent-login-form').addEventListener('submit',async e=>{e.preventDefault();const data=new FormData(e.target);try{await api('auth/login/',{username:data.get('username'),password:data.get('password')});e.target.reset();document.getElementById('agent-login-error').textContent='';await session();const state=await api('auth/session/');if(!state.onboarding_completed&&!['localhost','127.0.0.1'].includes(location.hostname))page('onboarding')}catch(err){document.getElementById('agent-login-error').textContent=err.message}});
document.getElementById('signup-form').addEventListener('submit',async e=>{
 e.preventDefault();const form=e.target,button=form.querySelector('button[type=submit]'),message=document.getElementById('signup-error');
 message.textContent='';form.querySelectorAll('.field-error').forEach(x=>x.textContent='');form.querySelectorAll('input').forEach(x=>x.removeAttribute('aria-invalid'));
 const data=Object.fromEntries(new FormData(form));
 if(data.password!==data.password_confirm){document.getElementById('signup-password_confirm-error').textContent='비밀번호가 일치하지 않습니다.';form.elements.password_confirm.setAttribute('aria-invalid','true');form.elements.password_confirm.focus();return;}
 button.disabled=true;button.textContent='계정을 만들고 있습니다…';
 try{const fresh=await api('auth/session/');csrf=fresh.csrf;await api('auth/signup/',data);form.reset();await session();page('onboarding');}
 catch(err){message.textContent=err.message;for(const [field,details] of Object.entries(err.fields||{})){const output=document.getElementById('signup-'+field+'-error');if(output)output.textContent=Array.isArray(details)?details.join(' '):String(details);form.elements.namedItem(field)?.setAttribute('aria-invalid','true');}const invalid=form.querySelector('[aria-invalid=true]');if(invalid)invalid.focus();else message.focus();}
 finally{button.disabled=false;button.textContent='가입하고 Mac 연결하기';}
});
document.getElementById('agent-logout').addEventListener('click',async()=>{try{await api('auth/logout/',{});authenticated=false;latest=[];await session()}catch(e){alert(e.message)}});
document.addEventListener('click',async e=>{const b=e.target.closest('[data-agent-action],[data-trash-index]');if(!b)return;const section=b.closest('[data-link]'),link=latest.find(x=>x.id===section.dataset.link);if(!link?.connected){alert('Mac 브리지가 연결된 뒤 요청해 주세요.');return}const card=b.closest('[data-asset]'),asset=card&&link.snapshot.assets.find(x=>x.id===card.dataset.asset),action=b.dataset.agentAction||'restore_trashed';let body={link_id:link.id,action},message='';if(action==='restore_trashed'){body.trash_index=Number(b.dataset.trashIndex);message='Mac 휴지통의 파일을 원래 자리로 복구하시겠습니까?'}else{body.asset_id=asset.id;const name=basename(asset.name||asset.original||asset.path);if(action==='answer'){body.project_id=card.querySelector('.agent-project').value;if(body.project_id==='__new_folder__'){await window.MoaFolders.open(card.querySelector('[data-folder-create-status]'),true);return;}const project=link.snapshot.catalog.find(x=>x.id===body.project_id);message=`${name}의 프로젝트를 ${project?.name||body.project_id}(으)로 답변하시겠습니까? 이 답변은 Mac의 _project.md 지침을 수정할 수 있지만 파일 이동은 별도 승인입니다.`}else if(action==='approve'){message=`${name}을(를) ${basename(asset.plan.target)}(으)로 실제 이동하시겠습니까? 에이전트가 현재 계획과 해시를 다시 확인합니다.`}else if(action==='undo'){message=`${name}의 실제 파일 이동을 되돌리시겠습니까?`}else message=`${name}을(를) 현재 위치에 그대로 두시겠습니까?`}
if(b.disabled||!confirm(message))return;b.disabled=true;try{await api('agent/commands/',body);await refresh();alert('요청을 등록했습니다. Mac 브리지가 실행하면 결과가 표시됩니다.')}catch(err){alert(err.message)}finally{b.disabled=false}});
document.addEventListener('click',e=>{if(e.target.closest('[data-page]'))setTimeout(()=>{if(authenticated)refresh()},0)});
document.addEventListener('moa-cleanup-command',()=>{if(authenticated)refresh()});
renderWorkspace();window.MoaAuthReady=session();setInterval(()=>{if(authenticated)refresh()},5000);
})();
