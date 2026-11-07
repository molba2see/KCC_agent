/* Explicit, owner-scoped previews are requested from the connected Mac. */
(()=>{
 const dialog=document.createElement('dialog');dialog.className='file-preview';
 dialog.innerHTML='<button class="login-modal-close" type="button" aria-label="파일 미리보기 닫기">×</button><h2 id="file-preview-title"></h2><p class="file-preview-status" role="status"></p><div class="file-preview-content"></div>';
 dialog.setAttribute('aria-labelledby','file-preview-title');document.body.append(dialog);
 const status=dialog.querySelector('[role=status]'),content=dialog.querySelector('.file-preview-content');
 let generation=0,trigger=null;
 dialog.querySelector('button').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{generation++;content.replaceChildren();if(trigger?.isConnected)trigger.focus({preventScroll:true})});
 dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close()}});
 async function request(path,body,csrf){
  const response=await fetch('/api/v1/'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','X-CSRFToken':csrf}:{},body:body?JSON.stringify(body):undefined});
  const data=await response.json();if(!response.ok)throw Error(data.detail||'파일을 불러오지 못했습니다.');return data;
 }
 document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-preview-asset]');if(!button)return;
  trigger=button;const current=++generation;
  dialog.querySelector('h2').textContent=button.dataset.previewName||button.textContent.trim();
  content.replaceChildren();status.textContent='연결된 Mac에서 미리보기를 가져오고 있어요…';dialog.showModal();
  try{
   const state=await request('agent/status/');if(current!==generation)return;
   const link=state.links.find(link=>link.id===button.dataset.previewLink);
   if(!link?.connected)throw Error('Mac이 연결되어 있어야 파일 내용을 가져올 수 있어요.');
   if(!link.snapshot?.capabilities?.includes('preview')){
    const download=document.createElement('a');download.className='ghost';download.href='/downloads/moa-mac-helper.zip';download.download='moa-mac-helper.zip';download.textContent='최신 Mac 연결 앱 다운로드';content.append(download);
    throw Error('Mac 연결 앱 업데이트가 필요해요. 최신 앱을 설치하고 다시 열어 주세요.');
   }
   const session=await request('auth/session/');if(current!==generation)return;
   const command=await request('agent/commands/',{link_id:link.id,action:'preview',asset_id:button.dataset.previewAsset},session.csrf);
   const deadline=Date.now()+90000;
   while(current===generation&&Date.now()<deadline){
    await new Promise(resolve=>setTimeout(resolve,1500));if(current!==generation)return;
    const fresh=await request('agent/status/');if(current!==generation)return;
    const result=fresh.links.find(item=>item.id===link.id)?.commands?.find(item=>item.id===command.id);
    if(result?.status==='failed')throw Error(String(result.result?.result||'Mac에서 파일을 읽지 못했습니다.'));
    if(result?.status!=='done')continue;
    const preview=result.result?.result;
    if(preview?.kind==='text'&&typeof preview.text==='string'){
     const text=document.createElement('pre');text.textContent=preview.text||'추출할 수 있는 텍스트가 없습니다.';content.append(text);
     status.textContent=preview.truncated?'문서 일부를 표시합니다.':'문서에서 추출한 텍스트입니다.';
    }else if(preview?.kind==='image'&&preview.mime==='image/jpeg'&&typeof preview.data==='string'&&/^[A-Za-z0-9+/=]+$/.test(preview.data)){
     const image=document.createElement('img');image.alt=button.dataset.previewName||'파일 미리보기';image.src='data:image/jpeg;base64,'+preview.data;content.append(image);status.textContent='내용 확인용으로 축소한 이미지입니다.';
    }else throw Error('미리보기 응답을 읽을 수 없습니다.');
    return;
   }
   if(current===generation)throw Error('미리보기가 지연되고 있어요. Mac 연결 상태를 확인하고 다시 시도해 주세요.');
  }catch(error){if(current===generation)status.textContent=error.message}
 });
})();
