/* The QR contains only the public setup URL; no account or pairing token. */
(()=>{
  const guide=document.getElementById('shortcut-guide');
  if(guide)guide.innerHTML=`<article class="setup-screen"><span class="chip">1 / 3 · 단축어 추가</span><h2>알림 보기를 추가하고 저장 폴더를 골라요.</h2>${window.MoaSetupGuides.shortcut}<a class="ghost" href="#shortcut-backtap">다음 · 뒷면 탭 설정 보기 ↓</a></article><article id="shortcut-backtap" class="setup-screen"><span class="chip">2 / 3 · 뒷면 탭 설정</span><h2>이중 탭에 알림 보기를 지정해요.</h2>${window.MoaSetupGuides.backTap}<a class="ghost" href="#shortcut-capture">다음 · 캡처 테스트 보기 ↓</a></article><article id="shortcut-capture" class="setup-screen"><span class="chip">3 / 3 · 전송 테스트</span><h2>Mac에서 테스트를 시작한 뒤 캡처해요.</h2><p>Mac 화면에서 <b>단축어와 저장 폴더를 확인했어요 → 설정했어요 · 전송 테스트 시작</b>까지 누른 뒤 진행하세요. 그 전에 만든 파일은 새 파일 테스트에 포함되지 않아요.</p>${window.MoaSetupGuides.capture}<p>새 이미지가 보이면 Mac 화면의 <b>KCC-inbox에 새 이미지가 보여요</b>를 누르세요. Mac으로 수신되면 모아에서 완료할 수 있어요.</p><p>Mac이 켜져 있고 Helper가 연결된 상태여야 해요. iPhone에 모아 앱이나 별도 에이전트를 설치할 필요는 없어요.</p><button class="ghost" data-page="onboarding">이 기기에서 모아 연결 가이드 열기</button></article>`;
  guide?.addEventListener('click',e=>{const anchor=e.target.closest('a[href^="#shortcut-"]');if(!anchor)return;e.preventDefault();const section=document.getElementById(anchor.hash.slice(1));section?.scrollIntoView({block:'start',behavior:'smooth'});const heading=section?.querySelector('h2');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true})}});
  const target=new URL('/#iphone-shortcut',location.origin).href;
  const panel=document.getElementById('shortcut-qr');
  const link=document.getElementById('shortcut-qr-link');
  if(link)link.href=target;
  if(!panel||typeof qrcode!=='function')return;
  try{
    const code=qrcode(0,'M');
    code.addData(target);
    code.make();
    panel.innerHTML=code.createSvgTag({cellSize:5,margin:4,scalable:true});
    panel.querySelector('svg')?.setAttribute('role','img');
  }catch{panel.textContent='QR을 표시할 수 없습니다. 아래 링크를 iPhone에서 열어 주세요.'}
})();
