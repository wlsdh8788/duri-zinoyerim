(function(){
'use strict';
const tab=document.getElementById('musicalTab');
const section=document.getElementById('musicalSection');
const soccer=document.getElementById('soccerTab');
const football=document.getElementById('footballSection');
const discovery=document.querySelector('section.discovery');
const results=document.getElementById('eventResults');
const cards=document.getElementById('musicalCards');
const state=document.getElementById('musicalStatus');
const query=document.getElementById('musicalSearch');
const area=document.getElementById('musicalRegion');
const count=document.getElementById('musicalCount');
const more=document.getElementById('musicalMore');
let filter='all', rows=[], meta={}, shown=12, loaded=false;
const safe=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const pretty=d=>String(d||'').replace(/^(\d{4})-(\d{2})-(\d{2})$/,(_,y,m,day)=>y+'. '+Number(m)+'. '+Number(day)+'.');
const url=s=>{try{const u=new URL(s);return u.protocol==='https:'?u.href:'#';}catch(e){return '#';}};
const ticketUrl=s=>{
 try{
  const u=new URL(s),h=u.hostname.toLowerCase();
  const hosts=['ticket.interpark.com','tickets.interpark.com','nol.interpark.com','nol.yanolja.com','ticketlink.co.kr','ticket.yes24.com','ticket.melon.com','melonticket.com','ticket.11st.co.kr'];
  return u.protocol==='https:'&&hosts.some(x=>h===x||h.endsWith('.'+x))?u.href:'#';
 }catch(e){return '#';}
};
function rowHtml(m,current){
 const active=m.start<=current && m.end>=current;
 const image=url(m.posterUrl);
 const poster=image==='#'?'<div class="musical-blank" aria-hidden="true">🎭</div>':
  '<img loading="lazy" decoding="async" referrerpolicy="no-referrer" src="'+safe(image)+'" alt="'+safe(m.title)+' 포스터" onerror="this.style.display=&#39;none&#39;;this.parentElement.classList.add(&#39;musical-broken&#39;)">';
 const actors=(m.featuredCast||[]).slice(0,5).join(' · ');
 const detail=url(m.sourceUrl),ticket=ticketUrl(m.ticketUrl);
 const links=(detail!=='#'?'<a href="'+safe(detail)+'" target="_blank" rel="noopener noreferrer">공연 정보 ↗</a>':'')
 +(ticket!=='#'?'<a class="musical-ticket" href="'+safe(ticket)+'" target="_blank" rel="noopener noreferrer">공식 예매처 ↗</a>':'');
 return '<article class="musical-card">'+
  '<div class="musical-poster">'+poster+'</div>'+
  '<div class="musical-info">'+
   '<div class="musical-tags"><span class="musical-tag">'+(active?'공연 중':'개막 예정')+'</span><span class="musical-tag subtle">'+safe(m.city||m.province||'전국')+'</span></div>'+
   '<h3>'+safe(m.title)+'</h3>'+
   '<p class="musical-dates">🗓 '+safe(pretty(m.start))+' ~ '+safe(pretty(m.end))+'</p>'+
   '<p class="musical-place">📍 '+safe(m.place||'공연장 확인 필요')+'</p>'+
   '<p class="musical-actors"><strong>주요 출연진</strong> '+safe(actors)+'</p>'+
   '<div class="musical-links">'+links+'</div>'+
  '</div></article>';
}
function render(){
 const current=today(),q=query.value.trim().toLocaleLowerCase('ko-KR'),region=area.value;
 const data=rows.filter(m=>{
  if(m.end<current)return false;
  if(filter==='playing'&&!(m.start<=current&&m.end>=current))return false;
  if(filter==='upcoming'&&m.start<=current)return false;
  if(region==='capital'&&!['서울','경기','인천'].includes(m.province))return false;
  if(region==='other'&&['서울','경기','인천'].includes(m.province))return false;
  if(q&&![m.title,m.place,m.city,(m.featuredCast||[]).join(' ')]
      .join(' ').toLocaleLowerCase('ko-KR').includes(q))return false;
  return true;
 }).sort((a,b)=>{
  const an=a.start<=current?0:1,bn=b.start<=current?0:1;
  return an-bn || a.start.localeCompare(b.start) || a.title.localeCompare(b.title,'ko');
 });
 if(count)count.textContent='('+data.length+'건)';
 cards.innerHTML=data.length?data.slice(0,shown).map(x=>rowHtml(x,current)).join(''):
 '<div class="musical-empty">조건에 맞는 대형 뮤지컬이 아직 없어.<br>검색이나 지역을 바꾸거나 다음 KOPIS 갱신 후 확인해 줘.</div>';
 more.hidden=data.length<=shown;
 const updated=meta.updated||'미확인';
 const stateLabel=meta.auto_update?'KOPIS 출연진 검증 자료':'KOPIS 자동 갱신 대기';
 state.textContent='기준 '+updated+' · '+stateLabel+' · '+rows.length+'작품 등록';
}
async function load(){
 if(loaded)return;loaded=true;
 try{
  const response=await fetch('./musicals.json?nocache='+Date.now(),{cache:'no-store'});
  if(!response.ok)throw Error('HTTP '+response.status);
  const data=await response.json();
  if(!Array.isArray(data.performances))throw Error('작품 목록 없음');
  meta=data;rows=data.performances.filter(m=>m&&m.id&&m.title&&/^\d{4}-\d{2}-\d{2}$/.test(m.start||'')
   &&/^\d{4}-\d{2}-\d{2}$/.test(m.end||'')&&m.end>=m.start&&Array.isArray(m.featuredCast)&&m.featuredCast.length>0);
 }catch(err){loaded=false;state.textContent='뮤지컬 정보 로드 실패 · GitHub Actions 배포 여부를 확인해 줘.';}
 render();
}
function hide(){
 tab.classList.remove('active');tab.setAttribute('aria-pressed','false');section.hidden=true;
}
tab.addEventListener('click',()=>{
 document.querySelectorAll('[data-section]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-pressed','false')});
 soccer.classList.remove('active');soccer.setAttribute('aria-pressed','false');
 discovery.hidden=true;results.hidden=true;football.hidden=true;section.hidden=false;
 tab.classList.add('active');tab.setAttribute('aria-pressed','true');
 load();
});
soccer.addEventListener('click',hide);
document.querySelectorAll('[data-section]').forEach(b=>b.addEventListener('click',hide));
document.querySelectorAll('[data-musical-filter]').forEach(button=>button.addEventListener('click',()=>{
 filter=button.dataset.musicalFilter;shown=12;
 document.querySelectorAll('[data-musical-filter]').forEach(b=>{
  const active=b===button;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));
 });
 render();
}));
query.addEventListener('input',()=>{shown=12;render()});
area.addEventListener('change',()=>{shown=12;render()});
more.addEventListener('click',()=>{shown+=12;render()});
})();
