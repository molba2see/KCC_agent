/* Per-Mac settings and expiry use the same authenticated command relay as filing. */
(()=>{
 const settings=document.getElementById('workspace-settings'),expiry=document.getElementById('expiry-list');
 if(!settings||!expiry)return;
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const date=value=>Number.isFinite(Number(value))?new Date(Number(value)*1000).toLocaleString('ko-KR'):'—';
 let links=[],authenticated=false,selected='',dirty=false,rendered='',baseRevision=null,feedback='';
 const pending=new Map();
 const dialog=document.createElement('dialog');dialog.className='expiry-dialog';
 dialog.innerHTML='<button type="button" class="login-modal-close" aria-label="삭제 예약 닫기">×</button><h2 id="expiry-dialog-title">삭제 예약</h2><p class="expiry-dialog-name"></p><p>선택한 기한에 휴지통으로 이동합니다. 휘발성 자료는 모아에 등록된 작업 파일을 처리하며, 다운로드 원본은 유지합니다.</p><form><label class="expiry-date-label">휴지통으로 옮길 시간<input name="due_at" type="datetime-local" required></label><p role="status"></p><button class="primary" type="submit">이 시간으로 예약</button></form>';
 dialog.setAttribute('aria-labelledby','expiry-dialog-title');document.body.append(dialog);
 let operation=null;
 dialog.querySelector('.login-modal-close').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{operation=null});
 function busy(link){return (link?.commands||[]).some(command=>['pending','running'].includes(command.status))}
 function enabled(link,capability){return link?.connected&&link.snapshot?.agent_available!==false&&!busy(link)&&link.snapshot?.capabilities?.includes(capability)}
 async function send(linkId,action,extra={}){
  const response=await fetch('/api/v1/auth/session/',{credentials:'same-origin',cache:'no-store'});const session=await response.json();
  const reply=await fetch('/api/v1/agent/commands/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':session.csrf},body:JSON.stringify({link_id:linkId,action,...extra})});
  const data=await reply.json();if(!reply.ok)throw Error(data.detail||'요청을 보내지 못했습니다.');
  document.dispatchEvent(new Event('moa-cleanup-command'));return data;
 }
 const modeOptions=(value,volatile=false)=> (volatile?[['review','기한 제안 후 승인'],['auto','자동으로 기한 예약'],['off','사용 안 함']]:[['auto','바로 자동 정리'],['review','승인 후 정리']]).map(([key,label])=>`<option value="${key}" ${value===key?'selected':''}>${label}</option>`).join('');
 function renderSettings(){
  if(!authenticated){settings.innerHTML='<div class="note-block">로그인하면 연결된 Mac의 처리 방식을 설정할 수 있어요. <button class="ghost" data-login>로그인</button></div>';rendered='';return}
  if(!links.length){settings.innerHTML='<div class="note-block">먼저 Mac을 연결해 주세요. <button class="ghost" data-page="connection">Mac 연결</button></div>';rendered='';return}
  if(!links.some(link=>link.id===selected)){selected=links[0].id;dirty=false;rendered=''}
  const link=links.find(link=>link.id===selected),preferences=link.snapshot?.preferences;
  const pendingInfo=pending.get(link.id),pendingId=pendingInfo?.id,command=(link.commands||[]).find(item=>item.id===pendingId);
  if(pendingId&&command?.status==='failed'){feedback='적용 실패: '+String(command.result?.result||'Mac 상태를 확인해 주세요.');pending.delete(link.id)}
  if(pendingId&&command?.status==='done'&&preferences?.revision>pendingInfo.revision){dirty=false;rendered='';feedback='Mac에 설정을 적용했습니다. 새 파일부터 선택한 방식으로 처리합니다.';pending.delete(link.id)}
  const signature=JSON.stringify([link.id,preferences?.revision,link.snapshot?.capabilities,links.map(item=>[item.id,item.label])]);
  if(!dirty&&signature!==rendered){
   const selector=`<label class="policy-mac">설정할 Mac<select id="policy-mac">${links.map(item=>`<option value="${esc(item.id)}" ${selected===item.id?'selected':''}>${esc(item.label)}</option>`).join('')}</select></label>`;
   if(!preferences||!link.snapshot?.capabilities?.includes('preferences')){
    settings.innerHTML=selector+'<div class="note-block">이 Mac의 연결 앱을 업데이트하면 처리 정책과 삭제 기한을 설정할 수 있어요. <a class="ghost" href="/downloads/moa-mac-helper.zip" download>최신 연결 앱 다운로드</a></div>';rendered=signature;return;
   }
   baseRevision=preferences.revision;
   settings.innerHTML=selector+`<form id="policy-form"><fieldset><legend>새 파일 정리 방식</legend><p>근거가 충분한 파일에 적용합니다. 애매한 파일과 온보딩의 기존 파일은 자동 모드에서도 확인을 기다립니다.</p><div class="settings-list">${[['download_mode','인터넷 다운로드'],['screenshot_mode','Mac 스크린샷'],['icloud_mode','iPhone · iCloud 파일']].map(([name,label])=>`<label><span><b>${label}</b><small>새로 수신한 지원 문서·이미지</small></span><select name="${name}">${modeOptions(preferences[name])}</select></label>`).join('')}</div></fieldset><fieldset><legend>설치파일 정리</legend><p>.dmg · .pkg 및 이름으로 확인되는 일부 설치파일을 처음 발견한 뒤 기한이 지나면 휴지통으로 옮깁니다.</p><div class="settings-list"><label><span><b>설치파일 만료 정리</b><small>끄면 예약 실행을 일시 중지합니다.</small></span><select name="installers_enabled"><option value="on" ${preferences.installers_enabled?'selected':''}>켜기</option><option value="off" ${!preferences.installers_enabled?'selected':''}>끄기</option></select></label><label><span><b>보관 기간</b><small>기간 변경 시 현재 시각부터 새 기한을 계산합니다.</small></span><span><input name="installer_days" type="number" min="1" max="365" required value="${Number(preferences.installer_days)}"> 일</span></label></div></fieldset><fieldset><legend>휘발성 자료</legend><p>파일 이름의 ‘공지·임시·일회용’ 같은 단서로 기한을 제안합니다. 문맥 판단이 틀릴 수 있으므로 기본은 승인 방식입니다. 등록된 작업 파일을 처리하며 원본은 유지합니다.</p><div class="settings-list"><label><span><b>처리 방식</b><small>기한과 대상은 삭제 관리에서 확인·변경·취소할 수 있어요.</small></span><select name="volatile_mode">${modeOptions(preferences.volatile_mode,true)}</select></label><label><span><b>기본 보관 기간</b></span><span><input name="volatile_days" type="number" min="1" max="365" required value="${Number(preferences.volatile_days)}"> 일</span></label></div></fieldset><button class="primary" type="submit">이 Mac에 설정 저장</button><p class="policy-status" role="status"></p></form>`;
   rendered=signature;
  }
  settings.querySelectorAll('#policy-form input,#policy-form select,#policy-form button').forEach(element=>element.disabled=!enabled(link,'preferences')||pending.has(link.id));
  const status=settings.querySelector('.policy-status');if(status)status.textContent=!link.connected?'Mac 연결이 끊겼습니다. 다시 연결되면 저장할 수 있어요.':link.snapshot?.agent_available===false?'Mac은 연결되어 있으며 파일을 분석 중입니다. 완료 후 저장할 수 있어요.':pending.has(link.id)?'Mac에 설정을 적용하고 있어요…':feedback;
 }
 function renderExpiry(){
  if(!authenticated){expiry.innerHTML='<div class="empty">로그인하면 연결된 Mac의 삭제 예약을 확인할 수 있어요.</div>';return}
  const html=links.map(link=>{
   const state=link.snapshot?.expiry;if(!state)return `<div class="empty">${esc(link.label)}: 최신 연결 앱에서 삭제 예약을 사용할 수 있어요.</div>`;
   const blocked=!enabled(link,'expiry')?'disabled':'';
   const labels={pending:'승인 대기',scheduled:'예약됨',paused:'일시 중지',blocked:'확인 필요',changed:'파일 변경',moving:'이동 중'};
   return `<section data-expiry-link="${esc(link.id)}"><h3>${esc(link.label)} · ${Number(state.total)||0}개 예정</h3>${state.total>state.entries.length?`<p>전체 ${Number(state.total)}개 중 기한이 가까운 ${state.entries.length}개를 표시합니다.</p>`:''}${state.entries.map(entry=>`<article class="expiry-row" data-expiry-entry="${esc(entry.id)}"><div class="review-card-header"><h3>${entry.asset_id?`<button class="file-preview-trigger" data-preview-asset="${esc(entry.asset_id)}" data-preview-link="${esc(link.id)}" data-preview-name="${esc(entry.name)}">${esc(entry.name)} ↗</button>`:esc(entry.name)}</h3><span class="chip">${labels[entry.status]||esc(entry.status)}</span></div><p>${entry.kind==='installer'?'설치파일':entry.kind==='volatile'?'휘발성 자료 제안':'직접 예약'} · 예정: <time datetime="${new Date(entry.due_at*1000).toISOString()}">${esc(date(entry.due_at))}</time></p>${entry.error?`<p>${esc(entry.error)}</p>`:''}<div class="actions">${entry.status==='pending'?`<button class="primary" data-expiry-action="expiry_confirm" ${blocked}>예약 승인</button>`:''}${!['moving','changed'].includes(entry.status)?`<button class="ghost" data-expiry-action="expiry_change" ${blocked}>시간 변경</button>`:''}${entry.status!=='moving'?`<button class="ghost" data-expiry-action="expiry_cancel" ${blocked}>예약 취소</button>`:''}</div></article>`).join('')||'<div class="empty">예약된 파일이 없습니다. 설치파일은 발견 시 기한을 만들고, 다른 파일은 파일 카드에서 직접 예약할 수 있어요.</div>'}</section>`;
  }).join('');
  expiry.innerHTML=html||'<div class="empty">Mac을 연결하면 삭제 기한을 확인할 수 있어요.</div>';
 }
 document.addEventListener('moa-workspace',event=>{
  links=event.detail.links;authenticated=event.detail.authenticated;
  if(!authenticated){selected='';dirty=false;pending.clear();feedback='';dialog.close()}
  renderSettings();renderExpiry();
 });
 settings.addEventListener('change',event=>{
  if(event.target.id==='policy-mac'){selected=event.target.value;dirty=false;rendered='';feedback='';renderSettings()}
  else if(event.target.closest('#policy-form'))dirty=true;
 });
 settings.addEventListener('input',event=>{if(event.target.closest('#policy-form'))dirty=true});
 settings.addEventListener('submit',async event=>{
  if(event.target.id!=='policy-form')return;event.preventDefault();
  const form=event.target,link=links.find(item=>item.id===selected);if(!enabled(link,'preferences'))return;
  const values=Object.fromEntries(new FormData(form));values.installers_enabled=values.installers_enabled==='on';
  values.installer_days=Number(values.installer_days);values.volatile_days=Number(values.volatile_days);
  if(values.volatile_mode==='auto'&&link.snapshot.preferences.volatile_mode!=='auto'&&!confirm('파일 이름으로 판단한 자료에 자동으로 기한을 예약합니다. 기한이 되면 등록된 작업 파일을 휴지통으로 옮깁니다. 계속할까요?'))return;
  form.querySelector('button[type=submit]').disabled=true;
  try{const revision=baseRevision;const command=await send(link.id,'preferences',{settings:values,revision});pending.set(link.id,{id:command.id,revision});feedback='Mac 적용을 기다리고 있습니다.'}catch(error){feedback=error.message}
  renderSettings();
 });
 function openSchedule(link,assetId,entry){
  operation={linkId:link.id,assetId,entryId:entry?.id};
  const asset=link.snapshot.assets?.find(item=>item.id===assetId);
  dialog.querySelector('.expiry-dialog-name').textContent=entry?.name||asset?.name||'파일';
  const future=new Date(entry?.due_at?Math.max(entry.due_at*1000,Date.now()+120000):Date.now()+(link.snapshot.preferences?.volatile_days||7)*86400000);
  dialog.querySelector('input').value=new Date(future.getTime()-future.getTimezoneOffset()*60000).toISOString().slice(0,16);
  dialog.querySelector('[role=status]').textContent='';dialog.showModal();
 }
 document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-expiry-action]');if(!button||button.disabled)return;
  const parent=button.closest('[data-expiry-link],[data-link]');
  const link=links.find(item=>item.id===(parent?.dataset.expiryLink||parent?.dataset.link));
  if(!enabled(link,'expiry')){alert('Mac 연결 상태와 연결 앱 버전을 확인해 주세요.');return}
  const action=button.dataset.expiryAction;
  const entry=link.snapshot.expiry?.entries.find(item=>item.id===button.closest('[data-expiry-entry]')?.dataset.expiryEntry);
  const assetId=button.closest('[data-asset]')?.dataset.asset;
  if(action==='expiry_schedule'||action==='expiry_change'){openSchedule(link,assetId,entry);return}
  if(!entry)return;
  if(action==='expiry_confirm'&&!confirm(`${entry.name}을(를) ${date(entry.due_at)} 이후 휴지통으로 옮기도록 예약할까요?`))return;
  button.disabled=true;
  try{await send(link.id,action,{entry_id:entry.id})}catch(error){alert(error.message);button.disabled=false}
 });
 dialog.querySelector('form').addEventListener('submit',async event=>{
  event.preventDefault();const current=operation;if(!current)return;
  const due_at=new Date(dialog.querySelector('input').value).getTime()/1000;
  if(!Number.isFinite(due_at)||due_at<Date.now()/1000+60){dialog.querySelector('[role=status]').textContent='1분 이후의 시간을 선택해 주세요.';return}
  const button=event.target.querySelector('button');button.disabled=true;
  try{await send(current.linkId,current.entryId?'expiry_change':'expiry_schedule',current.entryId?{entry_id:current.entryId,due_at}:{asset_id:current.assetId,due_at});dialog.close()}catch(error){dialog.querySelector('[role=status]').textContent=error.message}finally{button.disabled=false}
 });
})();
