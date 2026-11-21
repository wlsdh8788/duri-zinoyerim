(function(){
'use strict';
const tab=document.getElementById('concertTab');
const section=document.getElementById('concertSection');
const cards=document.getElementById('concertCards');
const state=document.getElementById('concertStatus');
const search=document.getElementById('concertSearch');
const region=document.getElementById('concertRegion');
const count=document.getElementById('concertCount');
const more=document.getElementById('concertMore');
let rows=[],meta={},loaded=false,show=12,mode='all',loadError='';
const e=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const day=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const nice=d=>String(d||'').replace(/^(\d{4})-(\d{2})-(\d{2})$/,(_,y,m,x)=>y+'. '+Number(m)+'. '+Number(x)+'.');
function safeUrl(value,ticket=false){
 try{
  const u=new URL(value),h=u.hostname.toLowerCase();
  if(u.protocol!=='https:')return '#';
  if(!ticket)return u.href;
  const hosts=['ticket.interpark.com','tickets.interpark.com','nol.interpark.com','nol.yanolja.com','ticketlink.co.kr','ticket.yes24.com','ticket.melon.com','melonticket.com','ticket.11st.co.kr'];
  return hosts.some(x=>h===x||h.endsWith('.'+x))?u.href:'#';
 }catch(err){return '#';}
}
function card(m,current){
 const playing=m.start<=current&&m.end>=current;
 const poster=safeUrl(m.posterUrl);
 const image=poster==='#'?'<div class="concert-empty-poster">🎤</div>':
 '<img loading="lazy" decoding="async" referrerpolicy="no-referrer" src="'+e(poster)+'" alt="'+e(m.title)+' 포스터" onerror="this.hidden=true;this.parentElement.classList.add(&#39;concert-broken&#39;)">';
 const singers=(m.artists||[]).slice(0,5).join(' · ');
 const details=safeUrl(m.sourceUrl),ticket=safeUrl(m.ticketUrl,true);
 const links=(details==='#'?'':'<a href="'+e(details)+'" target="_blank" rel="noopener noreferrer">공연 정보 ↗</a>')
 +(ticket==='#'?'':'<a class="concert-book" href="'+e(ticket)+'" target="_blank" rel="noopener noreferrer">공식 예매처 ↗</a>');
 return '<article class="concert-card">'+
 '<div class="concert-poster">'+image+'</div><div class="concert-info">'+
 '<div class="concert-badges"><span class="concert-badge">'+(playing?'공연 중':'공연 예정')+'</span><span class="concert-badge region">'+e(m.province||'전국')+'</span></div>'+
 '<h3>'+e(m.title)+'</h3><p class="concert-dates">📅 '+e(nice(m.start))+' ~ '+e(nice(m.end))+'</p>'+
 '<p>📍 '+e(m.place||'공연장 확인 필요')+'</p>'+
 '<p class="concert-artists"><strong>출연 가수</strong> '+e(singers)+'</p>'+
 '<div class="concert-links">'+links+'</div>'+
 '</div></article>';
}
function render(){
 const current=day(),q=search.value.trim().toLocaleLowerCase('ko-KR'),area=region.value;
 const items=rows.filter(m=>{
  if(m.end<current)return false;
  if(mode==='playing'&&!(m.start<=current&&m.end>=current))return false;
  if(mode==='upcoming'&&m.start<=current)return false;
  if(area==='capital'&&!['서울','경기','인천'].includes(m.province))return false;
  if(area==='other'&&['서울','경기','인천'].includes(m.province))return false;
  return !q||[m.title,m.place,m.province,(m.artists||[]).join(' ')].join(' ').toLocaleLowerCase('ko-KR').includes(q);
 }).sort((a,b)=>{
  const aNow=a.start<=current?0:1,bNow=b.start<=current?0:1;
  return aNow-bNow||a.start.localeCompare(b.start)||a.title.localeCompare(b.title,'ko');
 });
 count.textContent='('+items.length+'건)';
 cards.innerHTML=items.length?items.slice(0,show).map(x=>card(x,current)).join(''):
  '<div class="concert-empty">조건에 맞는 유명 가수 콘서트가 아직 없어.<br>검색·지역을 변경하거나 다음 데이터 갱신 후 확인해 줘.</div>';
 more.hidden=items.length<=show;
 state.textContent=loadError||('기준 '+(meta.updated||'미확인')+' · '+(meta.auto_update?'KOPIS 대중음악 자동 수집':'자동 수집 대기')+' · '+rows.length+'건');
}
async function load(){
 if(loaded)return;loaded=true;
 try{
  const res=await fetch('./concerts.json?nocache='+Date.now(),{cache:'no-store'});
  if(!res.ok)throw Error('HTTP '+res.status);
  meta=await res.json();
  if(!Array.isArray(meta.performances))throw Error('잘못된 콘서트 목록');
  rows=meta.performances.filter(x=>x&&x.id&&x.title&&/^\d{4}-\d{2}-\d{2}$/.test(x.start||'')
   &&/^\d{4}-\d{2}-\d{2}$/.test(x.end||'')&&x.end>=x.start&&Array.isArray(x.artists)&&x.artists.length>0);
 }catch(err){
  loaded=false;loadError='콘서트 목록을 불러오지 못했어. GitHub Actions 배포 상태를 확인해 줘.';
 }
 render();
}
function hide(){
 tab.classList.remove('active');tab.setAttribute('aria-pressed','false');section.hidden=true;
}
tab.addEventListener('click',()=>{
 document.querySelectorAll('[data-section]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-pressed','false');});
 for(const name of ['soccerTab','musicalTab']){
  const btn=document.getElementById(name);btn.classList.remove('active');btn.setAttribute('aria-pressed','false');
 }
 document.querySelector('section.discovery').hidden=true;
 document.getElementById('eventResults').hidden=true;
 document.getElementById('footballSection').hidden=true;
 document.getElementById('musicalSection').hidden=true;
 tab.classList.add('active');tab.setAttribute('aria-pressed','true');section.hidden=false;
 load();
});
document.querySelectorAll('[data-section]').forEach(b=>b.addEventListener('click',hide));
for(const id of ['soccerTab','musicalTab'])document.getElementById(id).addEventListener('click',hide);
document.querySelectorAll('[data-concert-filter]').forEach(button=>button.addEventListener('click',()=>{
 mode=button.dataset.concertFilter;show=12;
 document.querySelectorAll('[data-concert-filter]').forEach(b=>{
  const active=b===button;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));
 });
 render();
}));
search.addEventListener('input',()=>{show=12;render()});
region.addEventListener('change',()=>{show=12;render()});
more.addEventListener('click',()=>{show+=12;render()});
})();
