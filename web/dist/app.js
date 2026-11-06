/* Application navigation and filters for the connected Mac workspace. */
const $=selector=>document.querySelector(selector);
let fileFilter='all';
// Drop only obsolete sample data; account sessions and connection settings are untouched.
try{for(const key of ['moa-operations-demo-v2','moa-draft-v1'])localStorage.removeItem(key)}catch{}
function page(name){if(!document.getElementById(name)?.classList.contains('page'))return;closeMenu();document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id===name));document.querySelectorAll('[data-page]').forEach(x=>x.classList.toggle('active',x.dataset.page===name));history.replaceState(null,'','#'+name);window.scrollTo({top:0,behavior:'instant'});render();document.dispatchEvent(new Event('moa-page'))}
function closeMenu(){ $('#mobile-menu').hidden=true;$('#menu-backdrop').hidden=true;$('#menu-toggle').setAttribute('aria-expanded','false');$('#menu-toggle').setAttribute('aria-label','메뉴 열기')}
$('#menu-toggle').addEventListener('click',()=>{const open=$('#mobile-menu').hidden;$('#mobile-menu').hidden=!open;$('#menu-backdrop').hidden=!open;$('#menu-toggle').setAttribute('aria-expanded',String(open));$('#menu-toggle').setAttribute('aria-label',open?'메뉴 닫기':'메뉴 열기')});$('#menu-backdrop').addEventListener('click',closeMenu);
document.addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(b)page(b.dataset.page)});
function render(){window.MoaLive?.render()}
$('#file-search').addEventListener('input',render);
$('#file-filter').addEventListener('click',e=>{
 const button=e.target.closest('[data-filter]');if(!button)return;
 fileFilter=button.dataset.filter;
 $('#file-filter').querySelectorAll('button').forEach(item=>item.classList.toggle('active',item===button));
 render();
});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeMenu()});
if(location.hash&&document.getElementById(location.hash.slice(1))?.classList.contains('page'))page(location.hash.slice(1));
// A pointer spotlight follows only the service-introduction card's border.
const introHero=document.querySelector('#intro .intro-hero');
const precisePointer=window.matchMedia('(hover: hover) and (pointer: fine)');
introHero?.addEventListener('pointermove',event=>{
 if(!precisePointer.matches||event.pointerType!=='mouse')return;
 const bounds=introHero.getBoundingClientRect();
 introHero.style.setProperty('--pointer-x',`${event.clientX-bounds.left}px`);
 introHero.style.setProperty('--pointer-y',`${event.clientY-bounds.top}px`);
 introHero.classList.add('has-pointer');
});
introHero?.addEventListener('pointerleave',()=>introHero.classList.remove('has-pointer'));
