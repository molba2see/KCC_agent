/* First-run proposals are data; the Mac applies them only after explicit confirmation. */
(()=>{
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function html(cleanup,linkId,busy=false,connected=true){
  if(!cleanup)return '';
  const running=['scanning','generating'].includes(cleanup.status);
  const pending=(cleanup.groups||[]).filter(group=>group.status==='pending');
  const disabled=running||busy||!connected?'disabled':'';
  const phase=cleanup.status==='scanning'?'기존 파일을 분류하고 있어요':cleanup.status==='generating'?'기타 파일을 다시 묶어 보고 있어요':cleanup.status==='failed'?'일괄 정리 준비를 확인해 주세요':pending.length?'이렇게 정리하면 어떨까요?':'일괄 분류를 확인했어요';
  return `<section class="cleanup-panel" data-cleanup-link="${esc(linkId)}"><div class="cleanup-heading"><div><span class="eyebrow">첫 파일 정리</span><h2>${phase}</h2></div><span class="chip">${Number(cleanup.pending_groups??pending.length)}개 제안</span></div><p>선택한 폴더 지침으로 먼저 분류하고, 남은 파일은 목적에 맞게 다시 제안합니다. 원본은 유지하며 제안한 정리는 확인 후 실행해요.</p><div class="cleanup-stats"><span><b>${Number(cleanup.processed)||0}</b>개 확인</span><span><b>${Number(cleanup.classified)||0}</b>개 기존 폴더 분류</span><span><b>${Number(cleanup.remaining)||0}</b>개 기타 확인</span></div>${running?`<progress aria-label="일괄 정리 진행 중"></progress><p class="cleanup-status">${cleanup.status==='generating'?`로컬 모델이 파일 내용을 대조하고 있어요. ${Number(cleanup.model_processed)||0}개 재분류 확인 중`:'다운로드와 스크린샷 저장 폴더의 문서·이미지를 확인하고 있어요.'}</p>`:''}${cleanup.detail?`<p class="cleanup-status">${esc(cleanup.detail)}</p>`:''}
  ${cleanup.pending_groups>pending.length?`<p class="cleanup-status">${cleanup.pending_groups}개 제안 중 ${pending.length}개를 표시해요. 확인하면 다음 묶음이 이어집니다.</p>`:''}<div class="cleanup-groups">${pending.map(group=>`<article class="cleanup-group"><div class="cleanup-group-title"><h3>${esc(group.name)}</h3><span class="intro-tag ${group.new_folder?'peach':'mint'}">${group.new_folder?'새 폴더 제안':'기존 폴더 제안'}</span></div><p>${esc(group.purpose)}</p><p class="cleanup-destination">${esc(group.destination)} / <b>${esc(group.name)}</b></p><ul class="cleanup-files">${(group.files||[]).slice(0,8).map(file=>`<li><button class="file-preview-trigger" type="button" data-preview-link="${esc(linkId)}" data-preview-asset="${esc(file.id)}" data-preview-name="${esc(file.name)}">${esc(file.name)} ↗</button></li>`).join('')}</ul>${group.files?.length>8?`<details><summary>나머지 ${group.files.length-8}개 파일 보기</summary><ul class="cleanup-files">${group.files.slice(8).map(file=>`<li><button class="file-preview-trigger" type="button" data-preview-link="${esc(linkId)}" data-preview-asset="${esc(file.id)}" data-preview-name="${esc(file.name)}">${esc(file.name)} ↗</button></li>`).join('')}</ul></details>`:''}<div class="cleanup-actions"><span>${group.files?.length||0}개 파일 · ${group.new_folder?'확인하면 폴더와 지침도 만들어요':'선택한 폴더로 정리해요'}</span><button class="ghost" data-cleanup-action="cleanup_dismiss" data-cleanup-group="${esc(group.id)}" ${disabled}>이번에는 보류</button><button class="primary" data-cleanup-action="cleanup_confirm" data-cleanup-group="${esc(group.id)}" data-cleanup-name="${esc(group.name)}" data-cleanup-count="${group.files?.length||0}" ${disabled}>이 분류로 정리</button></div></article>`).join('')}</div>${cleanup.status==='failed'?`<button class="ghost" data-cleanup-action="cleanup_retry" ${busy||!connected?'disabled':''}>다시 제안받기</button>`:''}${!running&&!pending.length?'<p class="cleanup-status">분류가 남은 파일은 분류 대기에서 하나씩 폴더를 지정할 수 있어요.</p>':''}<p class="cleanup-action-status" role="status"></p></section>`;
 }
 window.MoaCleanup={html};
 document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-cleanup-action]');if(!button||button.disabled)return;
  const panel=button.closest('[data-cleanup-link]'),status=panel.querySelector('.cleanup-action-status');
  if(button.dataset.cleanupAction==='cleanup_confirm'&&!confirm(`${button.dataset.cleanupName} 폴더에 ${button.dataset.cleanupCount}개 파일을 정리할까요? 새 폴더 제안은 폴더와 정리 지침을 만든 뒤 작업 사본을 옮깁니다. 원본은 유지됩니다.`))return;
  button.disabled=true;status.textContent='Mac에 요청을 보내고 있어요…';
  try{
   const session=await fetch('/api/v1/auth/session/',{credentials:'same-origin',cache:'no-store'}).then(response=>response.json());
   const response=await fetch('/api/v1/agent/commands/',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':session.csrf},body:JSON.stringify({link_id:panel.dataset.cleanupLink,action:button.dataset.cleanupAction,group_id:button.dataset.cleanupGroup})});
   const result=await response.json();if(!response.ok)throw Error(result.detail||'요청을 보내지 못했어요.');
   status.textContent='Mac에서 처리한 결과가 잠시 뒤 표시됩니다.';
   document.dispatchEvent(new Event('moa-cleanup-command'));
  }catch(error){status.textContent=error.message;button.disabled=false;}
 });
 window.MoaLive?.render();
})();
