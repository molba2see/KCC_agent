/* First-run proposals are data; the Mac applies them only after explicit confirmation. */
(()=>{
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function destination(group){return group.destination_path||[group.destination,group.name].filter(Boolean).join(' / ')}
 function fileMap(file,group,linkId){
  const folder=file.destination||destination(group);
  return `<li class="cleanup-file-map-row"><div class="cleanup-file-from"><span class="cleanup-map-label">파일</span><button class="file-preview-trigger" type="button" data-preview-link="${esc(linkId)}" data-preview-asset="${esc(file.id)}" data-preview-name="${esc(file.name)}">${esc(file.name)} ↗</button><small>가져온 위치: ${esc(file.source||'모아 작업 사본')}${file.source_name&&file.source_name!==file.name?` · 원본 이름: ${esc(file.source_name)}`:''}</small></div><span class="cleanup-map-arrow" aria-hidden="true">→</span><div class="cleanup-file-to"><span class="cleanup-map-label">정리될 위치</span><span>${esc(folder)} / <b>${esc(file.target_name||file.name)}</b></span></div></li>`;
 }
 function proposal(group,linkId,disabled){
  const files=group.files||[],folder=destination(group);
  return `<article class="cleanup-group" data-proposal-kind="${group.new_folder?'new':'existing'}"><div class="cleanup-group-title"><h3>${esc(group.name)}</h3><span class="intro-tag ${group.new_folder?'peach':'mint'}">${group.new_folder?'새로 만들 폴더':'기존 폴더'}</span></div><p class="cleanup-folder-purpose"><b>묶은 이유</b> ${esc(group.purpose)}</p><div class="cleanup-folder-plan"><span class="cleanup-map-label">${group.new_folder?'새 폴더를 만들 위치':'이동할 기존 폴더'}</span><strong>${esc(folder)}</strong><p>${group.new_folder?'아직 없는 폴더입니다. 승인하면 폴더와 정리 지침을 만든 뒤 아래 파일을 정리합니다.':'아래 파일을 이 폴더로 정리합니다. 기존 폴더와 지침은 유지합니다.'}</p></div><h4 class="cleanup-preview-title">${files.length}개 파일 이동 미리보기</h4><ul class="cleanup-file-map">${files.slice(0,8).map(file=>fileMap(file,group,linkId)).join('')}</ul>${files.length>8?`<details class="cleanup-more-files"><summary>나머지 ${files.length-8}개 파일의 이동 위치 보기</summary><ul class="cleanup-file-map">${files.slice(8).map(file=>fileMap(file,group,linkId)).join('')}</ul></details>`:''}<div class="cleanup-actions"><span>${files.length}개 파일 · 원본 유지</span><button class="ghost" data-cleanup-action="cleanup_dismiss" data-cleanup-group="${esc(group.id)}" ${disabled}>이번에는 보류</button><button class="primary" data-cleanup-action="cleanup_confirm" data-cleanup-group="${esc(group.id)}" data-cleanup-name="${esc(group.name)}" data-cleanup-destination="${esc(folder)}" data-cleanup-new="${group.new_folder?'true':'false'}" data-cleanup-count="${files.length}" ${disabled}>${group.new_folder?'새 폴더 만들고 정리':'이 폴더로 정리'}</button></div></article>`;
 }
 function html(cleanup,linkId,busy=false,connected=true){
  if(!cleanup)return `<section class="cleanup-panel"><h2>다운로드 · 스크린샷 자동 분류</h2><p>Mac을 연결하면 기존 파일을 자동으로 분석하고 폴더별 정리 제안을 보여드려요. 파일 이동은 확인 후 실행합니다.</p><a class="ghost" href="/downloads/moa-mac-helper.zip" download>최신 Mac 연결 앱 다운로드</a><button class="ghost" data-page="connection">Mac 연결 확인</button></section>`;
  const running=['scanning','generating'].includes(cleanup.status);
  const pending=(cleanup.groups||[]).filter(group=>group.status==='pending');
  const disabled=running||busy||!connected?'disabled':'';
  const phase=cleanup.status==='scanning'?'기존 파일을 분류하고 있어요':cleanup.status==='generating'?'폴더별 정리 제안을 만들고 있어요':cleanup.status==='failed'?'일괄 정리 준비를 확인해 주세요':pending.length?'이렇게 정리하면 어떨까요?':cleanup.deferred_count?'개별 확인이 필요한 파일이 있어요':'일괄 분석을 마쳤어요';
  return `<section class="cleanup-panel" data-cleanup-link="${esc(linkId)}"><div class="cleanup-heading"><div><span class="eyebrow">다운로드 · 스크린샷 정리</span><h2>${phase}</h2></div><span class="chip">${Number(cleanup.pending_groups??pending.length)}개 제안</span></div><p>다운로드와 스크린샷 폴더의 파일을 자동으로 분석하고, 기존 폴더 또는 새 폴더로 묶어 제안합니다. 분류된 파일도 확인받은 뒤 정리하며 원본은 유지해요.</p><div class="cleanup-stats"><span><b>${Number(cleanup.processed)||0}</b>개 확인</span><span><b>${Number(cleanup.classified)||0}</b>개 기존 폴더 후보</span><span><b>${Number(cleanup.remaining)||0}</b>개 확인 대기</span></div>${running?`<progress aria-label="일괄 정리 진행 중"></progress><p class="cleanup-status">${cleanup.status==='generating'?`로컬 모델이 파일 내용을 대조하고 있어요. ${Number(cleanup.model_processed)||0}개 재분류 확인 중`:'다운로드와 스크린샷 저장 폴더의 문서·이미지를 확인하고 있어요.'}</p>`:''}${cleanup.deferred_count?`<p class="cleanup-status">${Number(cleanup.deferred_count)}개 파일은 분류 근거가 부족해 개별 분류 대기에 남겼습니다. 다른 제안은 계속 확인할 수 있어요.</p>`:''}${cleanup.detail?`<p class="cleanup-status">${esc(cleanup.detail)}</p>`:''}
  ${cleanup.pending_groups>pending.length?`<p class="cleanup-status">${cleanup.pending_groups}개 제안 중 ${pending.length}개를 표시해요. 확인하면 다음 묶음이 이어집니다.</p>`:''}<div class="cleanup-proposal-summary" aria-label="표시된 정리 제안"><span>기존 폴더 제안 <b>${pending.filter(group=>!group.new_folder).length}</b>개</span><span>새 폴더 제안 <b>${pending.filter(group=>group.new_folder).length}</b>개</span></div><div class="cleanup-groups">${pending.map(group=>proposal(group,linkId,disabled)).join('')}</div>${!running?`<button class="ghost" data-cleanup-action="cleanup_scan" ${busy||!connected?'disabled':''}>다운로드 · 스크린샷 다시 분석</button>`:''}${cleanup.status==='failed'?`<button class="ghost" data-cleanup-action="cleanup_retry" ${busy||!connected?'disabled':''}>다시 제안받기</button>`:''}${!running&&!pending.length?'<p class="cleanup-status">분류가 남은 파일은 분류 대기에서 하나씩 폴더를 지정할 수 있어요.</p>':''}<p class="cleanup-action-status" role="status"></p></section>`;
 }
 window.MoaCleanup={html};
 document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-cleanup-action]');if(!button||button.disabled)return;
  const panel=button.closest('[data-cleanup-link]'),status=panel.querySelector('.cleanup-action-status');
  if(button.dataset.cleanupAction==='cleanup_confirm'&&!confirm(`${button.dataset.cleanupNew==='true'?'새 폴더를 만들고 정리할까요?':'이 폴더로 정리할까요?'}\n정리 위치: ${button.dataset.cleanupDestination||button.dataset.cleanupName}\n대상: ${button.dataset.cleanupCount}개 파일\n${button.dataset.cleanupNew==='true'?'새 폴더와 정리 지침을 만듭니다. ':''}작업 사본을 이동하며 원본은 유지합니다.`))return;
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
