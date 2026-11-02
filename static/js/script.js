if(document.getElementById('dressFile')){
const dressFile=document.getElementById('dressFile'),dress=document.getElementById('dress'),
  man=document.getElementById('mannequin'),hint=document.getElementById('hint'),
  result=document.getElementById('result'),sizes=document.getElementById('sizes');
let scale=1,sizeName='M';
function update(){
  man.dataset.size=sizeName;
  const d=scale-1;
  const label=Math.abs(d)<.05?'Perfect fit':d<0?'Relaxed, flowing fit':'Fitted, close to the body';
  result.textContent='Size '+sizeName+' · '+(dress.hidden?'upload a dress to preview':label);
}
dressFile.addEventListener('change',()=>{
  const f=dressFile.files[0];if(!f)return;
  dress.src=URL.createObjectURL(f);dress.hidden=false;hint.hidden=true;update();
});
sizes.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  sizes.querySelectorAll('button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');scale=+b.dataset.s;sizeName=b.textContent;update();
});
update();
}

document.querySelectorAll('#title .word').forEach(w=>{
  const t=w.textContent;w.textContent='';w.setAttribute('aria-hidden','true');
  [...t].forEach(c=>{const s=document.createElement('span');s.className='ch';s.textContent=c;w.appendChild(s)});
});
const btn=document.getElementById('menuBtn'),ov=document.getElementById('overlay');
function toggle(open){ov.classList.toggle('open',open);document.body.classList.toggle('menu-open',open);ov.setAttribute('aria-hidden',!open);btn.textContent=open?'Close':'Menu';btn.setAttribute('aria-expanded',open)}
btn.onclick=()=>toggle(!ov.classList.contains('open'));
addEventListener('keydown',e=>{if(e.key==='Escape')toggle(false)});
addEventListener('resize',()=>{if(innerWidth>900)toggle(false)});
ov.querySelectorAll('a').forEach(a=>a.onclick=()=>toggle(false));
const io=new IntersectionObserver(es=>es.forEach(e=>{if(!e.isIntersecting)return;e.target.classList.add('in');
  e.target.querySelectorAll('[data-n]').forEach(b=>{const t=+b.dataset.n,s=performance.now();
    (function f(n){const p=Math.min((n-s)/1500,1);b.textContent=Math.round(t*p);if(p<1)requestAnimationFrame(f)})(s)});
  io.unobserve(e.target)}),{threshold:.25});
document.querySelectorAll('.reveal').forEach(el=>io.observe(el));
const vid=document.querySelector('video');
if(vid){
vid.addEventListener('ended',()=>{vid.currentTime=0;vid.pause()});
vid.play().catch(()=>{});
}

const page=document.body.dataset.page||location.pathname.split('/').pop().replace('.html','')||'index';
document.querySelectorAll('.links a[data-page]').forEach(a=>{
  if(a.dataset.page===page||(page===''&&a.dataset.page==='index')){a.classList.remove('glass');a.classList.add('active')}
});

document.querySelectorAll('.ov-nav a[data-page]').forEach(a=>{if(a.dataset.page===page)a.classList.add('here')});

const cForm=document.getElementById('contactForm');
if(cForm)cForm.addEventListener('submit',e=>{
  e.preventDefault();
  const msg='Hello Omafrans Couture, my name is '+document.getElementById('cName').value.trim()+
    ' (size '+document.getElementById('cSize').value+'). '+document.getElementById('cMsg').value.trim();
  const whatsappUrl=document.body.dataset.whatsappUrl;
  if(!whatsappUrl)throw new Error('WhatsApp contact URL is missing from this page.');
  window.open(whatsappUrl+'?text='+encodeURIComponent(msg),'_blank','noopener');
});

const track=document.getElementById('revTrack');
if(track){
  const step=()=>track.querySelector('.rev-card').offsetWidth+20;
  document.getElementById('revPrev').onclick=()=>track.scrollBy({left:-step(),behavior:'smooth'});
  document.getElementById('revNext').onclick=()=>track.scrollBy({left:step(),behavior:'smooth'});
  let down=false,sx=0,sl=0;
  track.addEventListener('pointerdown',e=>{if(e.pointerType!=='mouse')return;down=true;sx=e.clientX;sl=track.scrollLeft;track.classList.add('dragging')});
  addEventListener('pointermove',e=>{if(down)track.scrollLeft=sl-(e.clientX-sx)});
  addEventListener('pointerup',()=>{down=false;track.classList.remove('dragging')});
}

const grid=document.getElementById('grid'),filters=document.getElementById('filters');
if(grid&&filters)filters.addEventListener('click',e=>{
  const button=e.target.closest('button');if(!button)return;
  filters.querySelectorAll('button').forEach(item=>item.classList.remove('on'));
  button.classList.add('on');
  grid.querySelectorAll('.card[data-category]').forEach(card=>{
    card.hidden=button.dataset.c!=='all'&&card.dataset.category!==button.dataset.c;
  });
});

// Dressing room logic is handled by dressing-room.js (loaded after Three.js)
if(false && document.getElementById('roomFile')){
const room={
  file:null,dress:null,thumb:null,figure:null,fitBox:null,canvas:null,output:null,sizeButtons:null,
  sizeName:'M',size:1,color:'none',colorName:'Original',fabric:'',fabricName:'',zoom:1,
  rotateY:0,rotateX:0,sourceUrl:'',hasPreview:false
};
const roomStatus=document.getElementById('roomStatus');
const generateButton=document.getElementById('generateLook');
const contactButton=document.getElementById('roomContact');
const sizeMap={XS:.84,S:.92,M:1,L:1.08,XL:1.17,'2XL':1.27};
const sizeMeasure=()=>document.querySelector('#roomSizes button.on')?.dataset.m||'';
const notes=()=>document.getElementById('designNotes').value.trim();
const setRoomStatus=message=>{roomStatus.textContent=message};
function invalidatePreview(){
  room.hasPreview=false;
  contactButton.disabled=true;
  generateButton.textContent='Generate preview';
  if(room.sourceUrl){
    room.output.hidden=false;
    room.figure.hidden=true;
    drawPreview();
  }
  setRoomStatus('Design updated. Generate a new preview before contacting us.');
}
function paint(){
  room.dress.style.filter=(room.color==='none'?'':room.color+' ')+room.fabric;
  room.figure.style.transform='translate('+room.x+'px,'+room.y+'px) scale('+room.zoom+') rotateY('+room.rotateY+'deg) rotateX('+room.rotateX+'deg)';
  room.fitBox.style.transform='scaleX('+room.size+')';
  if(room.sourceUrl){
    drawPreview();
    room.output.style.transform='rotateY('+room.rotateY+'deg) rotateX('+room.rotateX+'deg)';
  }
}
function pick(group,btn,fn){
  group.querySelectorAll('button').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  fn(btn);
}
function loadDress(file){
  if(!file)return;
  if(!file.type.startsWith('image/')){
    setRoomStatus('Choose an image file to preview this design.');
    room.file.value='';
    return;
  }
  if(file.size>12*1024*1024){
    setRoomStatus('Choose an image smaller than 12 MB.');
    room.file.value='';
    return;
  }
  const nextUrl=URL.createObjectURL(file);
  const image=new Image();
  image.onload=()=>{
    if(room.sourceUrl)URL.revokeObjectURL(room.sourceUrl);
    room.sourceUrl=nextUrl;
    room.dress.src=nextUrl;
    room.thumb.src=nextUrl;
    room.dress.hidden=false;
    room.figure.hidden=true;
    room.output.hidden=false;
    room.x=room.y=0;
    invalidatePreview();
    paint();
    generateButton.disabled=false;
    setRoomStatus('Dress loaded. Adjust the fit, then generate your preview.');
  };
  image.onerror=()=>{
    URL.revokeObjectURL(nextUrl);
    room.file.value='';
    setRoomStatus('This image could not be opened. Try another image.');
  };
  image.src=nextUrl;
}
function drawImageContain(ctx,image,x,y,width,height){
  const ratio=Math.min(width/image.naturalWidth,height/image.naturalHeight);
  const drawWidth=image.naturalWidth*ratio;
  const drawHeight=image.naturalHeight*ratio;
  ctx.drawImage(image,x+(width-drawWidth)/2,y+(height-drawHeight)/2,drawWidth,drawHeight);
}
function drawPreview(){
  const canvas=room.output;
  const ctx=canvas.getContext('2d');
  const width=canvas.width,height=canvas.height;
  const angle=room.rotateY*Math.PI/180;
  ctx.clearRect(0,0,width,height);
  const wall=ctx.createLinearGradient(0,0,0,height);
  wall.addColorStop(0,'#342842');
  wall.addColorStop(.68,'#17121e');
  wall.addColorStop(1,'#100d15');
  ctx.fillStyle=wall;
  ctx.fillRect(0,0,width,height);
  const glow=ctx.createRadialGradient(width*.5,height*.38,20,width*.5,height*.4,width*.62);
  glow.addColorStop(0,'rgba(215,190,154,.25)');
  glow.addColorStop(1,'rgba(20,14,24,0)');
  ctx.fillStyle=glow;
  ctx.fillRect(0,0,width,height);
  ctx.strokeStyle='rgba(255,255,255,.07)';
  ctx.lineWidth=2;
  for(let x=45;x<width;x+=90){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,height*.8);ctx.stroke()}
  ctx.fillStyle='rgba(5,4,8,.55)';
  ctx.beginPath();
  ctx.moveTo(0,height*.82);ctx.lineTo(width,height*.82);ctx.lineTo(width,height);ctx.lineTo(0,height);ctx.closePath();ctx.fill();
  ctx.strokeStyle='rgba(212,255,0,.12)';
  ctx.beginPath();ctx.moveTo(0,height*.82);ctx.lineTo(width,height*.82);ctx.stroke();
  ctx.save();
  ctx.translate(width/2,height*.53);
  ctx.scale(Math.max(.28,Math.cos(angle))*room.size*room.zoom,1);
  ctx.translate(-width/2,-height*.53);
  const bodyPath=new Path2D('M112 56V70C134 74 150 80 154 94L148 152L138 156C136 168 134 178 134 190C140 204 148 212 148 226L142 340L138 450H118L114 340H86L82 450H62L58 340L52 226C52 212 60 204 66 190C66 178 64 168 62 156L52 152L46 94C50 80 66 74 88 70V56Z');
  ctx.save();
  ctx.translate(width*.25,height*.12);
  ctx.scale(1.65,1.45);
  ctx.fillStyle='rgba(236,226,214,.88)';
  ctx.strokeStyle='rgba(255,255,255,.65)';
  ctx.lineWidth=1.5;
  ctx.beginPath();ctx.arc(100,34,22,0,Math.PI*2);ctx.fill();
  ctx.fill(bodyPath);ctx.stroke(bodyPath);
  if(room.dress.complete&&room.dress.naturalWidth){
    const garmentPath=new Path2D('M63 88C72 78 84 73 100 72C116 73 128 78 137 88L151 151L127 164L148 344H52L73 164L49 151Z');
    ctx.save();
    ctx.clip(garmentPath);
    ctx.filter=(room.color==='none'?'':room.color+' ')+room.fabric;
    drawImageContain(ctx,room.dress,32,82,136,260);
    ctx.restore();
    const fabricShade=ctx.createLinearGradient(46,0,158,0);
    fabricShade.addColorStop(0,'rgba(0,0,0,.25)');
    fabricShade.addColorStop(.24,'rgba(255,255,255,.08)');
    fabricShade.addColorStop(.55,'rgba(255,255,255,.16)');
    fabricShade.addColorStop(1,'rgba(0,0,0,.32)');
    ctx.fillStyle=fabricShade;ctx.fill(garmentPath);
    ctx.strokeStyle='rgba(255,255,255,.48)';ctx.lineWidth=1.4;ctx.stroke(garmentPath);
  }
  ctx.restore();
  ctx.restore();
  const shade=ctx.createLinearGradient(0,0,width,0);
  shade.addColorStop(0,'rgba(0,0,0,.3)');
  shade.addColorStop(.5,'rgba(0,0,0,0)');
  shade.addColorStop(1,'rgba(0,0,0,.3)');
  ctx.fillStyle=shade;ctx.fillRect(0,0,width,height);
  ctx.fillStyle='#d4ff00';
  ctx.font='700 18px Arial, sans-serif';
  ctx.fillText('OMAFRANS COUTURE · FITTING PREVIEW',32,height-100);
  ctx.fillStyle='rgba(255,255,255,.8)';
  ctx.font='16px Arial, sans-serif';
  ctx.fillText('Size '+room.sizeName+' · '+room.fabricName+' · '+room.colorName,32,height-68);
  if(notes()){
    ctx.fillStyle='rgba(255,255,255,.68)';
    ctx.font='14px Arial, sans-serif';
    const note='Notes: '+notes().slice(0,72);
    ctx.fillText(note,32,height-38);
  }
}
room.file.addEventListener('change',e=>loadDress(e.target.files[0]));
document.getElementById('fabrics').addEventListener('click',e=>{
  const button=e.target.closest('button');
  if(button)pick(e.currentTarget,button,()=>{
    room.fabric=button.dataset.f;
    room.fabricName=button.textContent.trim();
    invalidatePreview();paint();
  });
});
document.getElementById('palettes').addEventListener('click',e=>{
  const button=e.target.closest('button');
  if(!button)return;
  document.querySelectorAll('#palettes button').forEach(item=>item.classList.remove('on'));
  button.classList.add('on');
  room.color=button.dataset.f;
  room.colorName=button.getAttribute('aria-label');
  invalidatePreview();paint();
});
document.getElementById('palNav').addEventListener('click',e=>{
  const button=e.target.closest('button');
  if(!button)return;
  pick(e.currentTarget,button,()=>document.querySelectorAll('.pal').forEach(palette=>palette.hidden=palette.dataset.p!==button.dataset.p));
});
room.sizeButtons.addEventListener('click',e=>{
  const button=e.target.closest('button');
  if(!button)return;
  pick(e.currentTarget,button,()=>{
    room.size=sizeMap[button.textContent.trim()];
    room.sizeName=button.textContent.trim();
    document.getElementById('sizeInfo').textContent='Size '+room.sizeName+' · '+button.dataset.m+' cm';
    invalidatePreview();paint();
  });
});
document.getElementById('designNotes').addEventListener('input',()=>{
  invalidatePreview();
});
generateButton.addEventListener('click',()=>{
  if(!room.dress.src||!room.sourceUrl){
    setRoomStatus('Upload a dress photo before generating a preview.');
    room.file.focus();
    return;
  }
  if(!room.dress.complete||!room.dress.naturalWidth){
    setRoomStatus('The dress image is still loading. Try again in a moment.');
    return;
  }
  room.figure.hidden=true;
  room.output.hidden=false;
  room.hasPreview=true;
  contactButton.disabled=false;
  generateButton.textContent='Regenerate preview';
  drawPreview();
  setRoomStatus('Preview ready. This is a visual simulation, not an AI-generated fitting.');
});
document.getElementById('zoomIn').onclick=()=>{room.zoom=Math.min(room.zoom+.15,2);paint()};
document.getElementById('zoomOut').onclick=()=>{room.zoom=Math.max(room.zoom-.15,.5);paint()};
document.getElementById('roomReset').onclick=()=>{
  room.zoom=1;room.x=room.y=0;room.rotateX=room.rotateY=0;room.color='none';room.colorName='Original';room.fabric='contrast(1.05) brightness(1)';room.fabricName='Premium Gabardine';
  document.querySelectorAll('#palettes button,#fabrics button').forEach(button=>button.classList.remove('on'));
  document.querySelector('#palettes .pal button').classList.add('on');
  document.querySelector('#fabrics button').classList.add('on');
  invalidatePreview();paint();
};
document.getElementById('toolColor').onclick=()=>document.querySelector('.dock').scrollIntoView({behavior:'smooth',block:'nearest'});
let drag=null;
room.canvas.addEventListener('pointerdown',e=>{
  if(e.target.closest('button'))return;
  drag={x:e.clientX,y:e.clientY,rotateY:room.rotateY,rotateX:room.rotateX};
  room.canvas.setPointerCapture(e.pointerId);
  room.canvas.classList.add('grab');
});
room.canvas.addEventListener('pointermove',e=>{
  if(!drag)return;
  room.rotateY=Math.max(-65,Math.min(65,drag.rotateY+(e.clientX-drag.x)*.45));
  room.rotateX=Math.max(-8,Math.min(8,drag.rotateX-(e.clientY-drag.y)*.08));
  room.figure.style.transform='translate('+room.x+'px,'+room.y+'px) scale('+room.zoom+') rotateY('+room.rotateY+'deg) rotateX('+room.rotateX+'deg)';
  room.output.style.transform='rotateY('+room.rotateY+'deg) rotateX('+room.rotateX+'deg)';
  if(room.sourceUrl)drawPreview();
});
['pointerup','pointercancel','lostpointercapture'].forEach(type=>room.canvas.addEventListener(type,()=>{
  drag=null;room.canvas.classList.remove('grab');
}));
contactButton.addEventListener('click',async()=>{
  if(!room.hasPreview)return;
  const message='Hello Omafrans Couture, I would love you to sew this dress for me.\nSize: '+room.sizeName+' ('+sizeMeasure()+' cm).\nFabric: '+room.fabricName+'. Colour: '+room.colorName+'.'+(notes()?'\nDesign notes: '+notes():'')+'\nI created a dressing-room preview.';
  const contactUrl=document.body.dataset.whatsappUrl;
  if(!contactUrl)throw new Error('WhatsApp contact URL is missing from this page.');
  const blob=await new Promise(resolve=>room.output.toBlob(resolve,'image/png'));
  if(!blob){
    setRoomStatus('Could not export the preview image. Please regenerate and try again.');
    return;
  }
  const imageFile=new File([blob],'omafrans-fitting-preview.png',{type:'image/png'});
  if(navigator.canShare&&navigator.canShare({files:[imageFile]})&&navigator.share){
    try{
      await navigator.share({files:[imageFile],title:'Omafrans Couture fitting preview',text:message});
      setRoomStatus('Choose WhatsApp in the share menu to send your preview.');
      return;
    }catch(error){
      if(error.name==='AbortError')return;
      console.error('Image sharing failed:',error);
    }
  }
  const downloadUrl=URL.createObjectURL(blob);
  const download=document.createElement('a');
  download.href=downloadUrl;download.download=imageFile.name;download.click();
  setTimeout(()=>URL.revokeObjectURL(downloadUrl),1000);
  window.open(contactUrl+'?text='+encodeURIComponent(message),'_blank','noopener');
  setRoomStatus('Preview downloaded. Attach omafrans-fitting-preview.png in the WhatsApp chat.');
});
paint();
}