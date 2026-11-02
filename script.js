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

const page=location.pathname.split('/').pop().replace('.html','')||'index';
document.querySelectorAll('.links a[data-page]').forEach(a=>{
  if(a.dataset.page===page||(page===''&&a.dataset.page==='index')){a.classList.remove('glass');a.classList.add('active')}
});

document.querySelectorAll('.ov-nav a[data-page]').forEach(a=>{if(a.dataset.page===page)a.classList.add('here')});

const cForm=document.getElementById('contactForm');
if(cForm)cForm.addEventListener('submit',e=>{
  e.preventDefault();
  const msg='Hello Omafrans Couture, my name is '+document.getElementById('cName').value.trim()+
    ' (size '+document.getElementById('cSize').value+'). '+document.getElementById('cMsg').value.trim();
  window.open('https://wa.me/2349166901393?text='+encodeURIComponent(msg),'_blank','noopener');
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

const dresses=[
  {name:'Aurora Gown',cat:'Gowns',tone:'t1'},
  {name:'Midnight Wrap',cat:'Occasion',tone:'t2'},
  {name:'Velvet Rose',cat:'Gowns',tone:'t3'},
  {name:'Sahara Day Dress',cat:'Day wear',tone:'t4'},
  {name:'Ivory Elegance',cat:'Occasion',tone:'t5'},
  {name:'Emerald Flow',cat:'Gowns',tone:'t6'},
  {name:'Linen Breeze',cat:'Day wear',tone:'t7'},
  {name:'Plum Couture',cat:'Occasion',tone:'t8'},
  {name:'Golden Hour',cat:'Gowns',tone:'t9'},
  {name:'City Chic',cat:'Day wear',tone:'t10'},
  {name:'Royal Navy',cat:'Occasion',tone:'t11'},
  {name:'Blush Silk',cat:'Day wear',tone:'t12'}
];
const grid=document.getElementById('grid');
if(grid){
  const limit=+grid.dataset.limit||dresses.length;
  const render=cat=>{
    const list=dresses.filter(d=>cat==='all'||d.cat===cat).slice(0,limit);
    grid.textContent='';
    list.forEach(d=>{
      const card=document.createElement('article');card.className='card reveal';
      const fig=document.createElement('div');fig.className='card-img '+d.tone;
      const img=document.createElement('img');img.src='about.png';img.alt=d.name;img.loading='lazy';fig.appendChild(img);
      const body=document.createElement('div');body.className='card-body';
      const h=document.createElement('h3');h.textContent=d.name;
      const s=document.createElement('span');s.textContent=d.cat;
      const a=document.createElement('a');a.href='index.html#dressing-room';a.textContent='Try it on';
      body.append(h,s,a);card.append(fig,body);grid.appendChild(card);io.observe(card);
    });
  };
  render('all');
  const filters=document.getElementById('filters');
  if(filters)filters.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    filters.querySelectorAll('button').forEach(x=>x.classList.remove('on'));
    b.classList.add('on');render(b.dataset.c);
  });
}

if(document.getElementById('roomFile')){
const room={dress:document.getElementById('roomDress'),figure:document.getElementById('figure'),fitBox:document.getElementById('fitBox'),canvas:document.getElementById('canvas'),color:'none',fabric:'contrast(1.05) brightness(1)',size:1,zoom:1,x:0,y:0};
const sizeMap={XS:.84,S:.92,M:1,L:1.08,XL:1.17,'2XL':1.27};
function paint(){
  room.dress.style.filter=(room.color==='none'?'':room.color+' ')+room.fabric;
  room.figure.style.transform='translate('+room.x+'px,'+room.y+'px) scale('+room.zoom+')';
  room.fitBox.style.transform='scaleX('+room.size+')';
}
function pick(group,btn,fn){
  group.querySelectorAll('button').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');fn(btn);
}
document.getElementById('roomFile').addEventListener('change',e=>{
  const f=e.target.files[0];if(!f)return;
  const u=URL.createObjectURL(f);
  room.dress.src=u;document.getElementById('roomThumb').src=u;room.x=room.y=0;paint();
});
document.getElementById('fabrics').addEventListener('click',e=>{
  const b=e.target.closest('button');if(b)pick(e.currentTarget,b,()=>{room.fabric=b.dataset.f;paint()});
});
document.getElementById('palettes').addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  document.querySelectorAll('#palettes button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');room.color=b.dataset.f;paint();
});
document.getElementById('palNav').addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b)return;
  pick(e.currentTarget,b,()=>document.querySelectorAll('.pal').forEach(p=>p.hidden=p.dataset.p!==b.dataset.p));
});
document.getElementById('roomSizes').addEventListener('click',e=>{
  const b=e.target.closest('button');if(b)pick(e.currentTarget,b,()=>{room.size=sizeMap[b.textContent];
    document.getElementById('sizeInfo').textContent='Size '+b.textContent+' · '+b.dataset.m.replace(/ · /g,' · ')+' cm';paint()});
});
document.getElementById('zoomIn').onclick=()=>{room.zoom=Math.min(room.zoom+.15,2);paint()};
document.getElementById('zoomOut').onclick=()=>{room.zoom=Math.max(room.zoom-.15,.5);paint()};
document.getElementById('roomReset').onclick=()=>{room.zoom=1;room.x=room.y=0;room.color='none';room.fabric='contrast(1.05) brightness(1)';
  document.querySelectorAll('#palettes button,#fabrics button').forEach(b=>b.classList.remove('on'));
  document.querySelector('#palettes .pal button').classList.add('on');document.querySelector('#fabrics button').classList.add('on');paint()};
document.getElementById('toolColor').onclick=()=>document.querySelector('.dock').scrollIntoView({behavior:'smooth',block:'nearest'});
let drag=null;
room.canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX-room.x,y:e.clientY-room.y};room.canvas.setPointerCapture(e.pointerId);room.canvas.classList.add('grab')});
room.canvas.addEventListener('pointermove',e=>{if(!drag)return;room.x=e.clientX-drag.x;room.y=e.clientY-drag.y;paint()});
['pointerup','pointercancel'].forEach(t=>room.canvas.addEventListener(t,()=>{drag=null;room.canvas.classList.remove('grab')}));
paint();
}