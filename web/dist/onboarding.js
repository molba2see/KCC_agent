/* One task at a time. Server progress remains the source of truth. */
(()=>{
 const root=document.getElementById('onboarding-content');
 const standalone=window.matchMedia('(display-mode: standalone)').matches;
 let dockReady=standalone;
 // Earlier versions saved this across accounts, hiding setup after an account reset.
 try{localStorage.removeItem('moa-dock-guide')}catch{}
 let authenticated=false;
 const phone=/iPhone|iPad|iPod|Android/i.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 root.innerHTML=`<div id="onboarding-login" class="note-block" hidden><h2>먼저 모아에 로그인해 주세요</h2><button class="primary" data-page="signup">회원가입</button><button class="ghost" data-login>로그인</button></div>
 <div id="onboarding-guide" class="setup-wizard" hidden>
 <ol class="setup-progress" aria-label="연결 순서"><li data-stage="dock">1 Dock에 추가</li><li data-stage="mac">2 Mac 연결</li><li data-stage="iphone">3 iPhone</li><li data-stage="done">4 수신 확인</li></ol>
 <p id="onboarding-status" role="status"></p>
 <article id="setup-dock" class="setup-screen" hidden><span class="chip">먼저 Mac Safari에서</span><h2>모아를 Dock에 추가해요.</h2><p>다음부터 Dock의 모아 아이콘으로 바로 열 수 있어요.</p><ol class="setup-instructions"><li>Mac의 <b>Safari</b>에서 이 사이트를 여세요.</li><li>화면 맨 위 메뉴에서 <b>파일 → Dock에 추가</b>를 누르세요.</li><li>이름을 <b>모아 AWS</b>로 정하고 <b>추가</b>를 누르세요.</li><li>Dock에 생긴 <b>모아 AWS</b> 아이콘을 눌러 여세요.</li></ol><div class="setup-path">Safari → 파일 → Dock에 추가 → 모아 AWS</div><p>열린 앱에서 회원가입하거나 기존 모아 계정으로 로그인한 뒤 연결을 진행하세요.</p><button id="setup-dock-done" class="primary">이미 Dock에 추가했어요 · 다음</button><details><summary>Dock에 추가 메뉴가 없어요</summary><p>이 기능은 macOS Sonoma 14 이상의 Safari에서 사용할 수 있습니다. Chrome 등 다른 브라우저라면 Safari에서 이 사이트를 다시 열어 주세요.</p><p><a href="https://support.apple.com/ko-kr/104996" target="_blank" rel="noopener noreferrer">Apple의 Dock 추가 안내 ↗</a></p><button id="setup-dock-skip" class="ghost">지금은 브라우저에서 계속</button></details></article>
 <article id="setup-welcome" class="setup-screen" hidden><span class="chip">처음 한 번만 설정해요</span><h2>iPhone 파일을<br>Mac에서 정리할 준비예요.</h2><p>iPhone에서 파일을 <b>KCC-inbox</b>에 넣으면,<br>Mac이 받아서 이 사이트에 보여줍니다.</p><div class="setup-flow" aria-label="파일이 전달되는 순서"><span>iPhone</span><b>→</b><span>iCloud 폴더</span><b>→</b><span>Mac · 모아</span></div><p><b>Mac과 iPhone을 옆에 두세요.</b><br>먼저 Mac을 연결한 뒤 iPhone 폴더를 확인할게요.</p><button id="setup-begin" class="primary">iPhone 파일 연결 시작하기</button></article>
 <article id="setup-mac" class="setup-screen" hidden><span class="chip">Mac 연결 · 1 / 3</span><h2>먼저 Helper 앱을 열어요.</h2><p>Mac에서 받은 파일을 모아에 전달하는 연결 앱이에요. 이 화면은 그대로 두고 진행하세요.</p><a id="setup-download-helper" class="primary" href="/downloads/moa-mac-helper.zip" download>모아 연결 앱 다운로드</a><ol class="setup-instructions"><li>Finder의 <b>다운로드</b>에서 <b>moa-mac-helper.zip</b>을 두 번 눌러 압축을 푸세요.</li><li>압축을 푼 <b>Moa Helper</b> 앱을 두 번 눌러 여세요.</li><li>앱이 차단되면 다음 화면의 <b>그래도 열기</b> 안내를 따라 주세요.</li></ol><div class="setup-actions"><button id="setup-helper-blocked" class="primary">앱이 차단됐어요 · 실행 허용하기</button><button id="setup-helper-ready" class="ghost">앱이 열렸어요 · 연결하기</button></div><details><summary>이미 Helper 앱을 설치했어요</summary><p>Finder에서 <b>응용 프로그램 → Moa Helper</b>를 열어 주세요. 사용자 홈 폴더의 Applications에 있을 수도 있어요. 준비가 끝나면 ‘앱이 열렸어요’를 누르세요.</p></details></article>
 <article id="setup-mac-security" class="setup-screen" hidden><span class="chip">Mac 연결 · 2 / 3</span><h2>설정에서 ‘그래도 열기’를 눌러요.</h2>${window.MoaSetupGuides.macSecurity}<div class="setup-actions"><button id="setup-security-done" class="primary">Helper 준비가 끝났어요 · 다음</button><button class="ghost" data-setup-back="mac">다운로드 안내로 돌아가기</button></div></article>
 <article id="setup-mac-connect" class="setup-screen" hidden><span class="chip">Mac 연결 · 3 / 3</span><h2>정리할 폴더를 고르고 연결해요.</h2><ol class="setup-instructions"><li>아래 <b>설치한 앱으로 Mac 연결하기</b>를 누르고 앱 열기 확인 창에서 허용하세요.</li><li>Helper 창에서 연결할 모아 주소를 확인하고 <b>폴더 선택하기</b>를 누르세요.</li><li><b>폴더 추가</b>로 정리할 폴더를 담은 뒤 <b>선택 완료 · 지침 만들기</b>를 누르세요.</li><li>첫 실행에는 필요한 프로그램과 모델을 준비하므로 시간이 걸릴 수 있어요. Helper 창을 닫지 말고 기다리세요.</li></ol><button id="onboarding-connect-mac" class="primary">설치한 앱으로 Mac 연결하기</button><div id="onboarding-pair-link"></div><p id="setup-mac-wait" role="status">Helper에서 지침 준비를 마치면 다운로드·스크린샷 일괄 정리로 이어집니다. 원본은 유지하고 기타 파일은 새 분류안을 확인받아요.</p><div class="setup-actions"><button class="ghost" data-setup-back="mac-security">앱 실행 허용 안내 다시 보기</button></div><details><summary>연결 앱이 열리지 않아요</summary><p>Finder에서 Moa Helper를 직접 열어 준비가 끝났는지 확인하세요. 준비가 끝나면 이 화면에서 연결 버튼을 다시 누르세요. 연결 요청은 5분 후 만료되므로 설치나 권한 확인에 시간이 걸렸다면 새로 눌러 주세요.</p></details></article>
 <article id="setup-cleanup" class="setup-screen" hidden><span class="chip">Mac의 첫 일괄 정리</span><h2>기존 파일부터 정리해 볼게요.</h2><p>선택한 폴더 지침으로 다운로드와 스크린샷을 분류합니다. 기타 파일의 제안을 확인하거나 보류한 뒤 iPhone 연결을 이어가세요.</p><div id="onboarding-cleanup"></div><button id="setup-cleanup-done" class="primary" disabled>일괄 정리 제안을 확인해 주세요</button><button id="setup-cleanup-later" class="ghost">분류 대기에서 나중에 확인 · iPhone 먼저 연결</button></article>
 <article id="setup-phone-first" class="setup-screen" hidden><span class="chip">먼저 Mac이 필요해요</span><h2>Mac에서 이 주소를 열어 주세요.</h2><p>Mac Safari에서 같은 모아 계정으로 로그인하면 연결을 시작할 수 있어요. iPhone은 옆에 두세요.</p><p id="setup-site-address" class="setup-path"></p><button id="onboarding-copy-link" class="primary">주소 복사하기</button><p>Mac이 연결되면 이 화면에서도 다음 단계가 표시됩니다.</p></article>
 <article id="setup-iphone" class="setup-screen" hidden><span class="chip">iPhone 설정 · 1 / 3</span><h2>같은 폴더가 보이는지 확인해요.</h2><p><b>Mac 화면은 그대로 두세요.</b><br>iPhone에서 모아에 다시 로그인할 필요는 없어요.</p><ol class="setup-instructions"><li>iPhone의 <b>설정 → Apple 계정</b>에서 Mac과 같은 계정인지 확인하세요. <b>iCloud → Drive → 이 iPhone 동기화</b>를 켜세요.</li><li>iPhone의 <b>파일</b> 앱을 여세요.</li><li><b>둘러보기 → iCloud Drive</b>를 누르세요.</li><li><b>KCC-inbox</b> 폴더를 여세요.</li></ol><div class="setup-path">iCloud Drive / KCC-inbox</div><button id="onboarding-confirm-iphone" class="primary">KCC-inbox 폴더가 보여요</button><details><summary>KCC-inbox가 보이지 않아요</summary><p>iPhone 설정 → Apple 계정 → iCloud → Drive에서 <b>이 iPhone 동기화</b>를 켜세요. Mac과 iPhone이 <b>같은 Apple 계정</b>에 로그인되어 있어야 합니다.</p><p>Mac의 Finder에서도 iCloud Drive 안에 KCC-inbox가 보이는지 확인하세요. 동기화에는 시간이 걸릴 수 있습니다.</p><a href="https://support.apple.com/ko-kr/118443" target="_blank" rel="noopener noreferrer">Apple 설정 안내 ↗</a></details></article>
 <article id="setup-shortcut" class="setup-screen" hidden><span class="chip">iPhone 설정 · 2 / 3</span><h2>캡처 단축어를 추가해요.</h2><div class="shortcut-qr-panel"><h3>iPhone 카메라로 QR을 스캔하세요</h3><p>iPhone에서 같은 안내가 열려요. 로그인은 필요 없어요. Mac 화면은 그대로 두세요.</p><div id="shortcut-qr" aria-label="iPhone 단축어 설치 안내 QR 코드"></div><a id="shortcut-qr-link" href="#iphone-shortcut" target="_blank" rel="noopener noreferrer">iPhone 설치 안내 링크 열기 ↗</a></div>${window.MoaSetupGuides.shortcut}<div class="setup-actions"><button id="setup-shortcut-done" class="primary">단축어와 저장 폴더를 확인했어요 · 다음</button><button class="ghost" data-setup-back="iphone">iCloud 폴더 확인으로 돌아가기</button></div></article>
 <article id="setup-backtap" class="setup-screen" hidden><span class="chip">iPhone 설정 · 3 / 3</span><h2>뒷면 두 번 탭에 연결해요.</h2>${window.MoaSetupGuides.backTap}<div class="setup-actions"><button id="setup-backtap-done" class="primary">설정했어요 · 전송 테스트 시작</button><button class="ghost" data-setup-back="shortcut">단축어 설정 다시 보기</button></div><p>뒷면 탭을 사용할 수 없다면 단축어를 직접 실행할 준비를 마친 뒤 전송 테스트를 시작하세요.</p></article>
 <article id="setup-send" class="setup-screen" hidden><span class="chip">iPhone에서 한 번만 테스트해요</span><h2>두 번 탭하고 파일을 확인해요.</h2><p>지금부터 새로 저장한 파일이 Mac에 도착하는지 확인할게요. Mac을 켜두세요.</p>${window.MoaSetupGuides.capture}<div class="setup-path">iCloud Drive / KCC-inbox</div><div class="setup-actions"><button id="setup-saved" class="primary">KCC-inbox에 새 이미지가 보여요</button><button class="ghost" data-setup-back="backtap">뒷면 탭 설정 다시 보기</button></div></article>
 <article id="setup-wait" class="setup-screen" hidden><span id="onboarding-receipt-badge" class="chip">파일을 기다리고 있어요</span><h2 id="setup-receipt-title">Mac으로 파일이 오는 중이에요.</h2><p id="onboarding-receipt">Mac을 켜두세요. 파일이 도착하면 자동으로 알려드릴게요.</p><button id="onboarding-complete" class="primary" disabled>파일 수신을 기다리는 중…</button><details><summary>계속 기다려도 파일이 안 보여요</summary><ul><li>iPhone에서 저장한 위치가 iCloud Drive / KCC-inbox인지 확인하세요.</li><li>Mac의 Finder에서 같은 파일이 보이는지 확인하세요.</li><li>Mac이 잠들지 않았는지, 모아 연결 프로그램이 실행 중인지 확인하세요.</li><li>두 기기의 인터넷 연결과 iCloud 저장 공간을 확인하세요.</li></ul><button id="onboarding-start-test" class="ghost">다른 사진으로 다시 테스트</button></details></article>
 <article id="setup-done" class="setup-screen" hidden><span class="chip">준비 끝</span><h2>이제 뒷면 탭으로 캡처하면 돼요.</h2><div class="setup-path">iCloud Drive / KCC-inbox</div><p>iPhone에서 여기에 저장한 파일을<br>Mac이 받아서 모아에 보여줍니다.</p><button id="setup-open-files" class="primary">내 파일 보러 가기</button></article>
 </div>`;
 const status=document.getElementById('onboarding-status');let state=null,screen=null,busy=false,loading=false,cleanupSignature='';
 document.getElementById('setup-site-address').textContent=location.origin+'/#onboarding';
 async function api(path,body){
  const session=await fetch('/api/v1/auth/session/',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json());
  const response=await fetch('/api/v1/'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','X-CSRFToken':session.csrf}:{},body:body?JSON.stringify(body):undefined});
  const data=await response.json();if(!response.ok)throw Error(data.detail||'연결 상태를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.');return data;
 }
 function show(next){
  const changed=screen!==next;screen=next;
  root.querySelectorAll('.setup-screen').forEach(x=>x.hidden=x.id!=='setup-'+screen);
  const stage=screen==='dock'?'dock':['welcome','mac','mac-security','mac-connect','cleanup','phone-first'].includes(screen)?'mac':['iphone','shortcut','backtap','send'].includes(screen)?'iphone':'done';
  document.querySelectorAll('[data-stage]').forEach(x=>{x.classList.toggle('current',x.dataset.stage===stage);if(x.dataset.stage===stage)x.setAttribute('aria-current','step');else x.removeAttribute('aria-current')});
  if(changed&&document.getElementById('onboarding').classList.contains('active')){const heading=document.querySelector('#setup-'+screen+' h2');heading.tabIndex=-1;heading.focus({preventScroll:true});document.getElementById('onboarding').scrollIntoView({block:'start'});}
 }
 function render(s){
  state=s;document.getElementById('onboarding-login').hidden=true;document.getElementById('onboarding-guide').hidden=false;
  if(!dockReady&&!phone)show('dock');
  else if(s.completed)show('done');
  else if(!screen||screen==='dock')show(s.test_started?(s.file_received?'wait':'send'):s.mac_connected?(s.cleanup&&!s.cleanup_confirmed?'cleanup':s.iphone_icloud_confirmed?'shortcut':'iphone'):'welcome');
  else if(['mac','mac-security','mac-connect','phone-first'].includes(screen)&&s.mac_connected)show(s.cleanup&&!s.cleanup_confirmed?'cleanup':'iphone');
  else if(screen==='welcome')show('welcome');
  if(s.file_received&&screen==='send')show('wait');
  const cleanup=document.getElementById('onboarding-cleanup');
  const signature=JSON.stringify([s.cleanup,s.cleanup_link_id,s.cleanup_busy,s.mac_connected]);
  if(signature!==cleanupSignature){cleanup.innerHTML=window.MoaCleanup?.html(s.cleanup,s.cleanup_link_id,s.cleanup_busy,s.mac_connected)||'';cleanupSignature=signature;}
  const cleanupReady=s.mac_connected&&s.cleanup&&!['scanning','generating'].includes(s.cleanup.status)&&!s.cleanup.pending_groups&&!(s.cleanup.groups||[]).some(group=>group.status==='pending');
  const cleanupDone=document.getElementById('setup-cleanup-done');cleanupDone.disabled=busy||!cleanupReady;document.getElementById('setup-cleanup-later').disabled=busy||!s.mac_connected;cleanupDone.textContent=cleanupReady?'확인했어요 · iPhone 연결하기':'일괄 정리 제안을 확인해 주세요';
  document.getElementById('onboarding-confirm-iphone').disabled=busy||!s.mac_connected;
  document.getElementById('setup-backtap-done').disabled=busy||!s.mac_connected;
  const ready=s.file_received&&s.mac_connected;
  document.getElementById('onboarding-receipt-badge').textContent=ready?'파일이 도착했어요':'파일을 기다리고 있어요';
  document.getElementById('setup-receipt-title').textContent=ready?'연결이 잘 됐어요!':s.mac_connected?'Mac으로 파일이 오는 중이에요.':'Mac 연결을 다시 기다리고 있어요.';
  document.getElementById('onboarding-receipt').textContent=ready?'받은 파일: '+s.received_filename:s.mac_connected?'Mac을 켜두세요. 파일이 도착하면 자동으로 알려드릴게요.':'Mac이 켜져 있는지, 모아 연결 프로그램이 실행 중인지 확인해 주세요.';
  const complete=document.getElementById('onboarding-complete');complete.disabled=busy||!ready;complete.textContent=ready?'좋아요, 설정 마치기':'파일 수신을 기다리는 중…';
  document.getElementById('onboarding-start-test').disabled=busy||!s.mac_connected;
 }
 async function load(){if(loading||busy)return;loading=true;try{const session=await fetch('/api/v1/auth/session/',{credentials:'same-origin',cache:'no-store'}).then(r=>r.json());authenticated=session.authenticated;if(!authenticated){state=null;document.getElementById('onboarding-guide').hidden=dockReady||phone;document.getElementById('onboarding-login').hidden=!(dockReady||phone);if(!dockReady&&!phone)show('dock');return;}render(await api('onboarding/'));}catch(e){document.getElementById('onboarding-guide').hidden=false;status.textContent=e.message}finally{loading=false}}
 async function action(name){busy=true;if(state)render(state);status.textContent='';try{
  if(name==='confirm_cleanup'||name==='defer_cleanup'){render(await api('onboarding/',{action:name}));show('iphone');}
  else if(name==='confirm_iphone'){render(await api('onboarding/',{action:name}));show('shortcut');}
  else{render(await api('onboarding/',{action:name}));if(name==='start_test')show('send');}
 }catch(e){status.textContent=e.message}finally{busy=false;if(state)render(state)}}
 function dockContinue(){dockReady=true;screen=null;status.textContent='';if(authenticated&&state)render(state);else load()}
 document.getElementById('setup-dock-done').onclick=dockContinue;
 document.getElementById('setup-dock-skip').onclick=dockContinue;
 document.getElementById('setup-begin').onclick=()=>show(state?.mac_connected?(state.cleanup&&!state.cleanup_confirmed?'cleanup':'iphone'):phone?'phone-first':'mac');
 document.getElementById('setup-cleanup-later').onclick=()=>action('defer_cleanup');
 document.getElementById('setup-cleanup-done').onclick=()=>action('confirm_cleanup');
 document.getElementById('onboarding-confirm-iphone').onclick=()=>action('confirm_iphone');
 document.getElementById('setup-helper-blocked').onclick=()=>show('mac-security');
 document.getElementById('setup-helper-ready').onclick=()=>show('mac-connect');
 document.getElementById('setup-security-done').onclick=()=>show('mac-connect');
 document.getElementById('setup-shortcut-done').onclick=()=>show('backtap');
 document.getElementById('setup-backtap-done').onclick=()=>action('start_test');
 root.addEventListener('click',e=>{const back=e.target.closest('[data-setup-back]');if(back)show(back.dataset.setupBack)});
 document.getElementById('setup-saved').onclick=()=>{show('wait');load()};
 document.getElementById('onboarding-start-test').onclick=()=>action('start_test');
 document.getElementById('onboarding-complete').onclick=()=>action('complete');
 document.getElementById('setup-open-files').onclick=()=>page('files');
 document.getElementById('onboarding-connect-mac').onclick=async e=>{
  if(phone){show('phone-first');return;}
  const button=e.currentTarget;button.disabled=true;status.textContent='';
  try{
   const ticket=await api('agent/pairing/',{});const link=document.createElement('a');link.className='primary';link.textContent='연결 앱 다시 열기';
   link.href='moa-helper://connect?ticket='+encodeURIComponent(ticket.pairing_secret);
   document.getElementById('onboarding-pair-link').replaceChildren(link);
   document.getElementById('setup-mac-wait').textContent='Helper 창에서 연결을 승인하고 폴더를 골라 주세요. 준비가 끝나면 자동으로 다음 단계로 넘어갑니다. 앱이 차단되면 아래 실행 허용 안내로 돌아가세요.';
   window.location.href=link.href;
   setTimeout(()=>{link.removeAttribute('href');link.textContent='연결 요청이 만료됐어요. 위 버튼을 다시 눌러 주세요.'},300000);
  }catch(e){status.textContent=e.message}finally{button.disabled=false}
 };
 document.getElementById('onboarding-copy-link').onclick=async()=>{try{await navigator.clipboard.writeText(location.origin+'/#onboarding');status.textContent='주소를 복사했어요. Mac Safari에서 열어 주세요.'}catch{status.textContent='Mac에서 열 주소: '+location.origin+'/#onboarding'}};
 document.addEventListener('moa-cleanup-command',()=>{if(document.getElementById('onboarding').classList.contains('active'))load()});
 document.addEventListener('moa-session',()=>{if(document.getElementById('onboarding').classList.contains('active'))load()});
 document.addEventListener('moa-page',()=>{if(document.getElementById('onboarding').classList.contains('active'))load()});
 document.addEventListener('click',e=>{if(e.target.closest('[data-page="onboarding"]'))load()});
 setInterval(()=>{if(document.getElementById('onboarding').classList.contains('active'))load()},5000);
 if(document.getElementById('onboarding').classList.contains('active'))load();
})();
