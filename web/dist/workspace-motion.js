/* Reveal workspace content on navigation and when asynchronous data arrives. */
(()=>{
 const preference=matchMedia('(prefers-reduced-motion: reduce)');
 const selector=[
  '.page-heading > *','.stats > button','.section-heading','.toolbar',
  '.file-row','.empty','.callout','.folder-summary-row','.folder-list > button',
  '.folder-detail > *','.review-card','.journal-row','.note-block',
  '.agent-login','.agent-toolbar','.agent-state','.settings-list > label',
  '#folders > p','#agent-live > button','#onboarding-content > *','#shortcut-guide > *'
 ].join(',');
 let active=null,intersection=null,mutations=null,seen=new Set();
 const running=new Set();
 function stop(){
  intersection?.disconnect();mutations?.disconnect();
  for(const animation of running)animation.cancel();
  running.clear();
 }
 function start(){
  stop();active=document.querySelector('.page.active');seen=new Set();
  if(!active||active.id==='intro'||preference.matches||!window.IntersectionObserver||!Element.prototype.animate)return;
  const prepared=new Map();
  intersection=new IntersectionObserver(entries=>{
   const visible=entries.filter(entry=>entry.isIntersecting).sort((a,b)=>
    a.target.compareDocumentPosition(b.target)&Node.DOCUMENT_POSITION_FOLLOWING?-1:1);
   visible.forEach((entry,index)=>{
    intersection.unobserve(entry.target);
    const animation=prepared.get(entry.target);if(!animation)return;
    animation.effect.updateTiming({delay:Math.min(index,5)*90});animation.play();
   });
  },{threshold:.04});
  function collect(){
   for(const element of active.querySelectorAll(selector)){
    if(element.closest('[hidden]')||element.parentElement.closest(selector)||!element.getClientRects().length||prepared.has(element))continue;
    const key=element.id||element.className+'|'+element.textContent.trim();
    if(seen.has(key))continue;seen.add(key);
    const animation=element.animate([
     {opacity:0,transform:'translateY(18px)'},{opacity:1,transform:'translateY(0)'}
    ],{duration:650,easing:'cubic-bezier(.2,.7,.2,1)',fill:'both'});
    animation.pause();animation.currentTime=0;prepared.set(element,animation);running.add(animation);
    animation.onfinish=()=>{running.delete(animation);animation.cancel()};
    animation.oncancel=()=>running.delete(animation);
    intersection.observe(element);
   }
   // Polling can replace nodes during a reveal; release the detached animations.
   for(const [element,animation] of prepared){
    if(!element.isConnected){intersection.unobserve(element);animation.cancel();prepared.delete(element)}
   }
  }
  mutations=new MutationObserver(collect);
  mutations.observe(active,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
  collect();
 }
 document.addEventListener('moa-page',start);
 preference.addEventListener('change',start);
 start();
})();
