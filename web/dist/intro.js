/* Accessible, local navigation within the service-introduction page. */
(()=>{
 const tabs=[...document.querySelectorAll('.intro-segments [role="tab"]')];
 if(!tabs.length)return;
 const intro=document.getElementById('intro');
 const segments=document.querySelector('.intro-segments');
 const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
 let observer=null;
 const running=new Set();
 const revealSelector=[
  '.intro-hero > .eyebrow','.intro-hero > h1','.intro-hero > p','.intro-hero > .actions',
  '.intro-section-heading > *','.intro-section > .section-heading','.intro-card',
  '.intro-principles > div','.intro-principles dl > div','.intro-evidence > div',
  '.intro-table thead','.intro-table tbody > tr','.intro-quote','.intro-pipeline > li','.intro-howto > li',
  '.intro-learning > div','.intro-note','.intro-cta','.intro-sources'
 ].join(',');
 function stopMotion(){observer?.disconnect();for(const animation of running)animation.cancel();running.clear()}
 function revealPanel(){
  stopMotion();
  if(reducedMotion.matches||!intro.classList.contains('active')||!('IntersectionObserver' in window)||!Element.prototype.animate)return;
  const panel=intro.querySelector('.intro-panel:not([hidden])');if(!panel)return;
  // Animate each content block once, without stacking parent and child fades.
  const elements=[...panel.querySelectorAll(revealSelector)].filter(element=>!element.parentElement.closest(revealSelector));
  observer=new IntersectionObserver(entries=>{
   const visible=entries.filter(entry=>entry.isIntersecting).sort((a,b)=>elements.indexOf(a.target)-elements.indexOf(b.target));
   visible.forEach((entry,index)=>{
    if(reducedMotion.matches||!intro.classList.contains('active')||entry.target.closest('.intro-panel').hidden)return;
    observer.unobserve(entry.target);
    // Elements stay readable by default; only visible content is animated.
    const animation=entry.target.animate([
     {opacity:0,translate:'0 18px'},
     {opacity:1,translate:'0 0'}
    ],{duration:680,delay:Math.min(index,6)*90,easing:'cubic-bezier(.2,.7,.2,1)',fill:'backwards'});
    running.add(animation);animation.onfinish=()=>running.delete(animation);animation.oncancel=()=>running.delete(animation);
   });
  },{threshold:0.06,rootMargin:'0px 0px -24px 0px'});
  elements.forEach(element=>observer.observe(element));
 }
 let activeTab=tabs.find(tab=>tab.getAttribute('aria-selected')==='true');
 function select(tab){
  if(tab===activeTab)return;
  activeTab=tab;segments.style.setProperty('--intro-tab-index',tabs.indexOf(tab));
  for(const item of tabs){
   const selected=item===tab;
   item.setAttribute('aria-selected',String(selected));item.tabIndex=selected?0:-1;
   document.getElementById(item.getAttribute('aria-controls')).hidden=!selected;
  }
  const top=document.getElementById('intro').getBoundingClientRect().top;
  const offset=parseFloat(getComputedStyle(document.querySelector('.intro-segments')).top)||0;
  if(top<offset)window.scrollTo({top:window.scrollY+top-offset,behavior:'instant'});
  revealPanel();
 }
 tabs.forEach((tab,index)=>{
  tab.addEventListener('click',()=>select(tab));
  tab.addEventListener('keydown',event=>{
   let next;
   if(event.key==='ArrowRight')next=(index+1)%tabs.length;
   else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
   else if(event.key==='Home')next=0;
   else if(event.key==='End')next=tabs.length-1;
   else return;
   event.preventDefault();select(tabs[next]);tabs[next].focus({preventScroll:true});
  });
 });
 document.addEventListener('moa-page',revealPanel);
 reducedMotion.addEventListener('change',revealPanel);
 revealPanel();
})();
