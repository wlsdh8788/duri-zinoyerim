(function(){
'use strict';
const tab=document.getElementById('soccerTab'),panel=document.getElementById('footballSection'),browse=document.querySelector('section.discovery'),results=document.getElementById('eventResults');
const cards=document.getElementById('footballCards'),status=document.getElementById('footballStatus'),search=document.getElementById('footballSearch'),period=document.getElementById('footballWhen');
let games=[],team='all',loaded=false;
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const kick=m=>new Date(m.date+'T'+m.time+':00+09:00');
const fmt=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'numeric',day:'numeric',weekday:'short'});
const source=u=>{try{const p=new URL(u),h=p.hostname;return p.protocol==='https:'&&(h==='kleague.com'||h.endsWith('.kleague.com')||h==='kfa.or.kr'||h.endsWith('.kfa.or.kr'))?p.href:'#';}catch(e){return '#';}};
function render(){
 const q=search.value.trim().toLocaleLowerCase('ko-KR'),now=new Date();
 const filtered=games.filter(m=>(team==='all'||m.teamGroup===team)&&(period.value!=='upcoming'||kick(m)>=now)&&(period.value!=='past'||kick(m)<now)&&(!q||[m.home,m.away,m.competition,m.venue].join(' ').toLocaleLowerCase('ko-KR').includes(q))).sort((a,b)=>(period.value==='past'?-1:1)*(kick(a)-kick(b)));
 document.getElementById('footballCount').textContent='('+filtered.length+'건)';
 cards.innerHTML=filtered.length?filtered.slice(0,60).map(m=>{
   const url=source(m.sourceUrl);
   return '<article class="football-match"><div class="football-top"><strong>'+esc(m.competition||'축구 경기')+'</strong><span>'+(kick(m)<now?'지난 경기':'경기 예정')+'</span></div>'
    +'<div class="football-vs"><span class="home">'+esc(m.home)+'</span><span class="vs">VS</span><span class="away">'+esc(m.away)+'</span></div>'
    +'<div class="football-place">🗓 '+esc(fmt.format(kick(m)))+' · '+esc(m.time)+' KST'+(m.venue?' · '+esc(m.venue):'')+'</div>'
    +(url==='#'?'':'<a class="football-link" href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">공식 경기 일정 확인 ↗</a>')+'</article>';
 }).join(''):'<div class="football-empty">해당 조건에 등록된 경기 일정이 없어.<br>팀이나 기간을 바꾸거나 공식 일정에서 확인해 줘.</div>';
}
async function load(){
 if(loaded)return;loaded=true;
 try{
  const r=await fetch('./sports.json?nocache='+Date.now(),{cache:'no-store'});
  if(!r.ok)throw Error('HTTP '+r.status);
  const data=await r.json();if(!Array.isArray(data.matches))throw Error('경기 자료 없음');
  games=data.matches.filter(m=>m&&/^\d{4}-\d{2}-\d{2}$/.test(m.date||'')&&/^\d{2}:\d{2}$/.test(m.time||'')&&m.home&&m.away&&['gangwon','national'].includes(m.teamGroup));
  status.textContent='일정 기준 '+(data.updated||'미확인')+' · '+(data.auto_update?'자동 연동':'공식 확인 후 등록')+' · '+games.length+'건';
 }catch(e){loaded=false;status.textContent='경기 자료를 불러오지 못했어. 공식 일정 링크를 이용해 줘.';}
 render();
}
tab.addEventListener('click',()=>{
 document.querySelectorAll('[data-section]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-pressed','false');});
 tab.classList.add('active');tab.setAttribute('aria-pressed','true');
 browse.hidden=true;results.hidden=true;panel.hidden=false;load();
});
document.querySelectorAll('[data-section]').forEach(b=>b.addEventListener('click',()=>{tab.classList.remove('active');tab.setAttribute('aria-pressed','false');browse.hidden=false;results.hidden=false;panel.hidden=true;}));
document.querySelectorAll('[data-soccer-filter]').forEach(b=>b.addEventListener('click',()=>{team=b.dataset.soccerFilter;document.querySelectorAll('[data-soccer-filter]').forEach(x=>{const on=b===x;x.classList.toggle('active',on);x.setAttribute('aria-pressed',String(on));});render();}));
search.addEventListener('input',render);period.addEventListener('change',render);
})();
