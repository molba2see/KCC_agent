/* Mac first run: no user-facing account, token or terminal configuration. */
(async()=>{
 if(!["localhost","127.0.0.1"].includes(location.hostname))return;
 const panel=document.createElement('div');panel.className='note-block';panel.id='local-onboarding';
 document.querySelector('#connection .page-heading').after(panel);
 const request=async(path,body,extra={})=>{
  const headers={'Content-Type':'application/json',...extra};
  if(body){
   await window.MoaAuthReady;
   const token=document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1];
   if(!token)throw new Error('로그인 보안 쿠키를 읽을 수 없습니다. 페이지를 새로고침해 주세요.');
   headers['X-CSRFToken']=decodeURIComponent(token);
  }
  const r=await fetch('/api/v1/local/'+path,{method:body?'POST':'GET',credentials:'same-origin',headers,body:body?JSON.stringify(body):undefined});
  const data=await r.json();if(!r.ok)throw new Error(data.detail||'연결 실패');return data;
 };
 const key=location.hash.startsWith('#local-key=')?decodeURIComponent(location.hash.slice(11)):'';
 if(key){
  history.replaceState(null,'','#connection');page('connection');
  try{await request('unlock/',{},{'X-Moa-Local-Key':key});location.reload();return;}
  catch(e){panel.textContent='모아 시작 파일을 다시 열어 주세요. '+e.message;return;}
 }
 if(location.hash.startsWith('#cloud-pair=')){
  let pairing;
  try{pairing=JSON.parse(decodeURIComponent(location.hash.slice(12)));}catch{}
  history.replaceState(null,'','#connection');page('connection');
  if(!pairing||typeof pairing.origin!=='string'||typeof pairing.pairing_secret!=='string'){
   panel.textContent='연결 링크가 올바르지 않습니다. AWS에서 다시 연결하세요.';return;
  }
  const heading=document.createElement('h2');heading.textContent='이 Mac을 AWS 모아에 연결할까요?';panel.append(heading);
  const explanation=document.createElement('p');explanation.textContent='연결 주소: '+pairing.origin+' · 연결하면 이 Mac의 모아 파일 목록과 분류 상태가 AWS 계정에 표시됩니다. AWS에서 승인한 파일 명령을 이 Mac이 실행합니다.';panel.append(explanation);
  const button=document.createElement('button');button.className='primary';button.textContent='이 Mac 연결 승인';panel.append(button);
  const cancel=document.createElement('button');cancel.className='ghost';cancel.textContent='취소';panel.append(cancel);
  const feedback=document.createElement('p');feedback.setAttribute('role','status');panel.append(feedback);
  cancel.onclick=()=>{pairing=null;location.reload()};
  button.onclick=async()=>{
   button.disabled=true;cancel.disabled=true;
   try{await request('cloud/connect/',pairing);pairing=null;location.reload();}
   catch(err){feedback.textContent=err.message;button.disabled=false;cancel.disabled=false;}
  };
  return;
 }
 let deferredInstall;
 window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredInstall=e;const b=document.getElementById('install-webapp');if(b)b.textContent='모아 앱 설치'});
 async function show(){
  try{
   const s=await request('setup/');
   document.getElementById('agent-logout').hidden=true;document.getElementById('agent-account').textContent='이 Mac에서 사용 중';
   panel.innerHTML=`<h2>${s.shortcut_ready?'iCloud Drive 연결됨':s.configured?'KCC-inbox 연결 업데이트':'모아 시작하기'}</h2><p>1. iCloud Drive를 켜고 아래 연결 버튼을 눌러 주세요.</p><p>2. iCloud Drive의 <b>KCC-inbox</b>에 새 파일을 넣으면 이 Mac에서 분류합니다. 원본은 남겨두고 작업 사본을 처리합니다.</p><p>${window.MoaDesktop?"3. 다음부터 Dock의 모아 아이콘으로 여세요.":"3. Safari에서 <b>파일 → Dock에 추가</b>를 선택하면 모아를 앱처럼 열 수 있습니다."}</p><div class="actions"><button class="primary" id="connect-icloud">${s.shortcut_ready?'연결 다시 확인':s.configured?'KCC-inbox로 변경':'iCloud Drive 연결'}</button><button class="ghost" id="install-webapp">Dock에 추가 안내</button></div><p id="icloud-setup-status" role="status">${s.available?(s.shortcut_ready?'새 파일을 기다리고 있습니다. Mac이 켜져 있을 때 처리됩니다.':s.configured?'기존 연결을 KCC-inbox로 바꾸려면 위 버튼을 누르세요. 기존 파일은 그대로 둡니다.':'연결하면 iCloud Drive에 KCC-inbox를 만듭니다.'):'시스템 설정 → Apple 계정 → iCloud → Drive를 켜 주세요.'}</p>`;
   if(s.cloud_origin){
    panel.innerHTML='<h2>'+ (s.shortcut_ready?'Mac 연결이 끝났어요':s.configured?'KCC-inbox 연결 업데이트':'Mac의 공유 폴더를 만들어요')+'</h2><p>'+(s.shortcut_ready?'이 창을 닫고 Dock의 모아 AWS를 눌러 주세요. 열려 있던 모아 화면에서 다음 단계가 자동으로 표시됩니다.':'iPhone과 함께 사용할 KCC-inbox 폴더를 준비합니다.')+'</p><div class="setup-path">iCloud Drive / KCC-inbox</div><div class="actions"><button class="primary" id="connect-icloud">'+(s.shortcut_ready?'공유 폴더 다시 확인':s.configured?'KCC-inbox로 변경':'공유 폴더 만들기')+'</button><button id="install-webapp" hidden></button></div><p id="icloud-setup-status" role="status">'+(s.available?'아래 버튼을 누르면 폴더가 준비됩니다.':'먼저 Mac 시스템 설정 → Apple 계정 → iCloud → Drive를 켜 주세요.')+'</p>';

    const note=document.createElement('p');note.textContent=s.shortcut_ready?'모아 웹앱에 다시 로그인할 필요는 없습니다. 기존 모아 앱으로 돌아가세요.':s.configured?'KCC-inbox로 변경한 뒤 기존 모아 앱으로 돌아가세요. 기존 파일은 그대로 둡니다.':'아래 버튼으로 공유 폴더를 만들어 주세요.';panel.append(note);
    const back=document.createElement('a');back.className='ghost';back.textContent='브라우저에서 모아 열기';back.href=s.cloud_origin+'/#onboarding';back.rel='noreferrer';panel.append(back);
    const disconnect=document.createElement('button');disconnect.className='ghost';disconnect.textContent='AWS 연결 해제';panel.append(disconnect);
    disconnect.onclick=async()=>{if(!confirm('이 Mac의 AWS 연결과 서버에 저장된 상태·명령 기록을 삭제할까요? iCloud 파일은 유지됩니다.'))return;disconnect.disabled=true;try{await request('cloud/disconnect/',{});location.reload()}catch(err){alert(err.message);disconnect.disabled=false}};
   }
   document.getElementById('connect-icloud').onclick=async e=>{e.target.disabled=true;try{await request('setup/',{});await show();}catch(err){document.getElementById('icloud-setup-status').textContent=err.message;}finally{e.target.disabled=false;}};
   document.getElementById('install-webapp').hidden=!!window.MoaDesktop;
   document.getElementById('install-webapp').onclick=async()=>{if(deferredInstall){await deferredInstall.prompt();deferredInstall=null;}else alert('Safari: 파일 → Dock에 추가 → 이름을 모아로 지정 → 추가. 이후 Dock의 모아 아이콘으로 여세요.');};
  }catch{panel.innerHTML='<h2>Mac에서 간편하게 시작</h2><p>처음 한 번 저장소의 <b>모아 시작.command</b>를 열어 설치하고, iCloud Drive를 연결하세요. 이후 Safari의 <b>파일 → Dock에 추가</b>로 앱처럼 사용할 수 있습니다.</p>';}
 }
 await show();
})();
