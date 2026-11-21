(function(){
'use strict';
const tab=document.getElementById('soccerTab'),panel=document.getElementById('footballSection'),browse=document.querySelector('section.discovery'),results=document.getElementById('eventResults');
const cards=document.getElementById('footballCards'),status=document.getElementById('footballStatus'),search=document.getElementById('footballSearch'),period=document.getElementById('footballWhen'),place=document.getElementById('footballPlace');
let games=[],team='all',loaded=false,meta={};
const esc=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const kick=m=>new Date(m.date+'T'+(m.time||'00:00')+':00+09:00');
const fmt=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'numeric',day:'numeric',weekday:'short'});
const fmtOpen=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'numeric',day:'numeric',hour:'numeric',minute:'2-digit'});
const safeLink=url=>{
  try{
    const p=new URL(url),h=p.hostname.toLowerCase();
    return p.protocol==='https:'&&['gangwon-fc.com','kleague.com','kfa.or.kr','playkfa.com','nol.yanolja.com','nol.interpark.com'].some(x=>h===x||h.endsWith('.'+x))?p.href:'#';
  }catch(e){return '#';}
};
function localType(m){
 if(m.teamGroup==='gangwon'&&m.home==='강원FC'){
   if(m.localHome==='강릉'||/강릉|하이원/.test(m.venue||''))return 'gangneung';
   if(m.localHome==='춘천'||/춘천|송암/.test(m.venue||''))return 'chuncheon';
 }
 if(m.teamGroup==='national'&&m.domesticNational)return 'korea';
 return '';
}
function ticketLink(m){
 const direct=safeLink(m.ticketInfoUrl);
 if(direct!=='#')return direct;
 if(m.teamGroup==='gangwon'&&m.home==='강원FC')return 'https://nol.yanolja.com/ticket/genre/sports/gangwonfc';
 if(m.teamGroup==='national'&&m.domesticNational)return 'https://www.playkfa.com/';
 return '#';
}
function ticketDetails(m,now){
 const raw=String(m.ticketOpenAt||'');
 const verified=m.ticketStatus==='announced'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\+09:00$/.test(raw)&&safeLink(m.ticketAnnouncementUrl)!=='#';
 if(verified){
  const when=new Date(raw);
  const prefix=when>now?'예매 오픈 예정':'예매 시작일';
  const presale=/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\+09:00$/.test(m.ticketPresaleAt||'')?'<div class="football-ticket-date">⭐ 선예매: '+esc(fmtOpen.format(new Date(m.ticketPresaleAt)))+'</div>':'';
  return presale+'<div class="football-ticket-date">🎫 '+prefix+': '+esc(fmtOpen.format(when))+'</div>';
 }
 // 원정팀으로 출전하는 경기는 예매 오픈일 미확인 문구를 표시하지 않는다.
 if((m.teamGroup==='gangwon'&&m.away==='강원FC')||(m.teamGroup==='national'&&m.away==='대한민국'))return '';
 return '<div class="football-ticket-date football-ticket-unknown">예매 오픈일 미확인</div>';
}
function render(){
 const q=search.value.trim().toLocaleLowerCase('ko-KR'),now=new Date(),loc=place.value;
 const matches=games.filter(m=>{
  if(team!=='all'&&m.teamGroup!==team)return false;
  if(period.value==='upcoming'&&kick(m)<now)return false;
  if(period.value==='past'&&kick(m)>=now)return false;
  if(loc!=='all'&&localType(m)!==loc)return false;
  if(q&&![m.home,m.away,m.competition,m.venue].join(' ').toLocaleLowerCase('ko-KR').includes(q))return false;
  return true;
 }).sort((a,b)=>{
   const t=period.value==='past'?-1:1;
   if(t===1&&loc==='all'){
     const rank=m=>({'gangneung':0,'chuncheon':1,'korea':2})[localType(m)]??3;
     if(rank(a)!==rank(b))return rank(a)-rank(b);
   }
   return t*(kick(a)-kick(b));
 });
 document.getElementById('footballCount').textContent='('+matches.length+'건)';
 cards.innerHTML=matches.length?matches.slice(0,60).map(m=>{
  const local=localType(m),kind=local==='gangneung'?'🟠 강릉 홈경기':local==='chuncheon'?'🟠 춘천 홈경기':local==='korea'?'🇰🇷 국내 A매치':'';
  const ticket=ticketLink(m),notice=safeLink(m.ticketAnnouncementUrl);
  const dateText=esc(fmt.format(kick(m)))+' · '+esc(m.time||'시간 미정')+' KST';
  const venueText=m.venue?' · '+esc(m.venue):' · 경기장 미확인';
  const links=(ticket==='#'?'':'<a class="football-link football-ticket" href="'+esc(ticket)+'" target="_blank" rel="noopener noreferrer">공식 예매처 확인 ↗</a>')
    +(notice==='#'?'':'<a class="football-link" href="'+esc(notice)+'" target="_blank" rel="noopener noreferrer">예매 공지 ↗</a>');
  return '<article class="football-match">'+
   '<div class="football-top"><strong>'+esc(m.competition||'축구 경기')+'</strong><span>'+(kick(m)<now?'지난 경기':'경기 예정')+'</span></div>'+
   (kind?'<div class="football-home-tag">'+kind+'</div>':'')+
   '<div class="football-vs"><span class="home">'+esc(m.home)+'</span><span class="vs">VS</span><span class="away">'+esc(m.away)+'</span></div>'+
   '<div class="football-place">🗓 '+dateText+venueText+'</div>'+
   ticketDetails(m,now)+'<div class="football-actions">'+links+'</div></article>';
 }).join(''):'<div class="football-empty">조건에 맞는 경기 일정이 없어.<br>팀·지역·기간을 바꾸거나 공식 일정에서 확인해 줘.</div>';
 const gw=meta.source_status?.gangwon||'unknown';
 const teamStatus=gw==='updated'?'강원FC 일정 자동 확인':gw==='no_new_verified_games'?'강원FC 공식 사이트 확인·새 경기 없음':'강원FC 자동 확인 결과 미검증';
 const national='국가대표 신규 일정 수동 확인';
 status.textContent='일정 기준 '+(meta.updated||'미확인')+' · '+teamStatus+' · '+national+' · '+games.length+'건';
}
async function load(){
 if(loaded)return;loaded=true;
 try{
  const r=await fetch('./sports.json?nocache='+Date.now(),{cache:'no-store'});
  if(!r.ok)throw Error('HTTP '+r.status);
  meta=await r.json();if(!Array.isArray(meta.matches))throw Error('경기 자료 없음');
  games=meta.matches.filter(m=>m&&/^\d{4}-\d{2}-\d{2}$/.test(m.date||'')&&/^\d{2}:\d{2}$/.test(m.time||'')&&m.home&&m.away&&['gangwon','national'].includes(m.teamGroup));
 }catch(e){loaded=false;status.textContent='경기 자료 로드 오류. 아래 공식 사이트에서 확인해 줘.';}
 render();
}
tab.addEventListener('click',()=>{
 document.querySelectorAll('[data-section]').forEach(b=>{b.classList.remove('active');b.setAttribute('aria-pressed','false')});
 tab.classList.add('active');tab.setAttribute('aria-pressed','true');
 browse.hidden=true;results.hidden=true;panel.hidden=false;load();
});
document.querySelectorAll('[data-section]').forEach(b=>b.addEventListener('click',()=>{
 tab.classList.remove('active');tab.setAttribute('aria-pressed','false');
 browse.hidden=false;results.hidden=false;panel.hidden=true;
}));
document.querySelectorAll('[data-soccer-filter]').forEach(b=>b.addEventListener('click',()=>{
 team=b.dataset.soccerFilter;
 document.querySelectorAll('[data-soccer-filter]').forEach(x=>{const on=b===x;x.classList.toggle('active',on);x.setAttribute('aria-pressed',String(on))});
 render();
}));
search.addEventListener('input',render);
period.addEventListener('change',render);
place.addEventListener('change',render);
})();
