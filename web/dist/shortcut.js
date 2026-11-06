/* The QR contains only the public setup URL; no account or pairing token. */
(()=>{
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
