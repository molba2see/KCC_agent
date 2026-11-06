/* Both account dialogs reuse the existing forms and their session/CSRF handlers. */
(()=>{
 const login=document.getElementById('agent-login');
 const signup=document.querySelector('#signup .signup-card');
 if(!login||!signup)return;
 const prompt=document.createElement('div');prompt.className='login-prompt note-block';
 prompt.innerHTML='<p>로그인하면 연결된 Mac과 파일 상태를 확인할 수 있어요.</p><button class="primary" data-login>로그인</button>';
 login.before(prompt);
 const signupPrompt=document.createElement('div');signupPrompt.className='note-block';
 signupPrompt.innerHTML='<p>모아 계정을 만들고 Mac과 iPhone을 연결하세요.</p><button class="primary" data-page="signup">회원가입</button>';
 signup.before(signupPrompt);
 function create(kind,content){
  const modal=document.createElement('dialog');modal.id=kind+'-modal';modal.className='login-modal'+(kind==='signup'?' signup-modal':'');
  modal.setAttribute('aria-labelledby',kind+'-modal-title');modal.setAttribute('aria-describedby',kind+'-modal-description');
  modal.innerHTML=`<button class="login-modal-close" type="button" aria-label="${kind==='signup'?'회원가입':'로그인'} 팝업 닫기">×</button>`;
  document.body.append(modal);modal.append(content);
  content.querySelector('h2').id=kind+'-modal-title';content.querySelector('p').id=kind+'-modal-description';
  modal.querySelector('.login-modal-close').onclick=()=>modal.close();
  let backdropDown=false;
  modal.addEventListener('pointerdown',e=>{backdropDown=e.target===modal});
  modal.addEventListener('click',e=>{if(backdropDown&&e.target===modal)modal.close();backdropDown=false});
  modal.addEventListener('close',()=>{
   if(modal.open)return;
   content.querySelectorAll('input[type="password"]').forEach(input=>input.value='');
   content.querySelectorAll('.field-error, #agent-login-error').forEach(error=>error.textContent='');
   content.querySelectorAll('[aria-invalid]').forEach(input=>input.removeAttribute('aria-invalid'));
   if(active!==modal)return;
   active=null;document.body.style.overflow=scrollStyle;
   if(previousFocus?.isConnected&&previousFocus.getClientRects().length)previousFocus.focus({preventScroll:true});
  });
  return modal;
 }
 let active=null,previousFocus=null,scrollStyle='';
 const dialogs={login:create('login',login),signup:create('signup',signup)};
 login.querySelector('h2').textContent='다시 만나 반가워요';
 login.querySelector('p').textContent='모아에 로그인하고 파일 정리를 이어가세요.';
 const username=login.querySelector('[name="username"]');username.autocapitalize='none';username.spellcheck=false;
 function open(kind){
  const modal=dialogs[kind];if(login.hidden||modal.open)return;
  if(!active){previousFocus=document.activeElement;scrollStyle=document.body.style.overflow;document.body.style.overflow='hidden';}
  else active.close();
  window.closeMenu?.();active=modal;modal.showModal();modal.scrollTop=0;
  modal.querySelector('input[name="username"]').focus({preventScroll:true});
 }
 function close(){if(active?.open)active.close()}
 document.addEventListener('click',e=>{
  const signupTrigger=e.target.closest('[data-page="signup"], [data-signup]');
  const loginTrigger=e.target.closest('[data-login],.header-login');
  if(signupTrigger||loginTrigger){e.preventDefault();e.stopImmediatePropagation();open(signupTrigger?'signup':'login');}
 },true);
 document.addEventListener('moa-page',()=>{
  close();
  if(location.hash==='#signup'){page('intro');open('signup');}
 });
 function sync(){prompt.hidden=login.hidden;signupPrompt.hidden=login.hidden;if(login.hidden)close()}
 new MutationObserver(sync).observe(login,{attributes:true,attributeFilter:['hidden']});sync();
 // Preserve direct signup links while using the service introduction as the backdrop.
 if(location.hash==='#signup'){page('intro');open('signup');}
})();
