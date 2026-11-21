(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const region=$('foodRegion'), search=$('foodSearch');
  const count=$('foodCount'), cards=$('foodCards'), status=$('foodStatus');
  const naver=$('naverFind'), querySummary=$('naverSummary');
  const chips=[...document.querySelectorAll('[data-food-filter]')];
  let places=[],meta={},filter='전체',loadError='';
  const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const CATEGORY={한식:'category-korean',양식:'category-western',카페:'category-cafe'};
  const KEYWORDS={'전체':'맛집','한식':'한식 맛집','양식':'파스타 양식 맛집','카페':'카페 디저트','바다뷰':'바다뷰 카페','기념일':'기념일 레스토랑'};
  const naverUrl=q=>'https://map.naver.com/p/search/'+encodeURIComponent(q.trim());
  function searchQuery(){
    const area=region.value==='전국'?'':region.value;
    const word=search.value.trim().slice(0,100);
    // 검색어를 입력했다면 그 단어를 우선 사용하고, 비어 있을 때는 종류별 추천 검색어.
    return [area,word||(KEYWORDS[filter]||'맛집')].filter(Boolean).join(' ').trim()||'전국 맛집';
  }
  function placeUrl(item){return naverUrl([item.city,item.name,item.address].filter(Boolean).join(' '));}
  function sourceUrl(item){
    try{
      const url=new URL(item.sourceUrl);
      return url.protocol==='https:'&&(
        url.hostname==='english.visitkorea.or.kr'||url.hostname==='korean.visitkorea.or.kr'
      )?url.href:'';
    }catch(e){return '';}
  }
  function card(item){
    const badges=[item.district,item.type].filter(Boolean);
    const link=placeUrl(item),source=sourceUrl(item);
    const tags=badges.map((x,i)=>'<span class="food-tag'+(i?' secondary':'')+'">'+escape(x)+'</span>').join('');
    return '<article class="food-card">'+
      '<div class="food-art '+(CATEGORY[item.type]||'')+'" aria-hidden="true"><span>'+escape(item.emoji||'🍽️')+'</span></div>'+
      '<div class="food-info">'+
        '<div class="food-tags">'+tags+'</div>'+
        '<h3>'+escape(item.name)+'</h3>'+
        '<p>📍 '+escape(item.address)+'</p>'+
        '<p class="food-note">'+escape(item.note||'방문 전 네이버 지도에서 상세 확인')+'</p>'+
        '<div class="food-actions"><a class="primary" href="'+escape(link)+'" target="_blank" rel="noopener noreferrer" aria-label="'+escape(item.name)+' 네이버 지도에서 보기">네이버 지도 ↗</a>'+
        (source?'<a href="'+escape(source)+'" target="_blank" rel="noopener noreferrer">관광 정보 ↗</a>':'')+
        '</div></div></article>';
  }
  function matches(item){
    if(region.value!=='전국'&&item.city!==region.value)return false;
    if(filter!=='전체'&&filter!==item.type&&!(item.tags||[]).includes(filter))return false;
    const q=search.value.trim().toLocaleLowerCase('ko-KR');
    if(!q)return true;
    const text=[item.name,item.city,item.district,item.type,item.address,item.note,...(item.tags||[])]
      .join(' ').toLocaleLowerCase('ko-KR');
    // 공백으로 구분한 검색 단어가 모두 포함되는 후보만 표시한다.
    return q.split(/\s+/).every(x=>text.includes(x));
  }
  function render(){
    const q=searchQuery();
    const items=places.filter(matches);
    count.textContent='('+items.length+'곳)';
    cards.innerHTML=items.length?items.map(card).join(''):
      '<div class="food-empty"><strong>조건에 맞는 우리두리 추천 후보가 아직 없어.</strong><div>네이버 지도에서 '+escape(q)+' 검색 결과를 바로 확인할 수 있어.</div></div>';
    naver.href=naverUrl(q);
    naver.setAttribute('aria-label','네이버 지도에서 '+q+' 검색하기');
    querySummary.textContent='네이버 지도에서 ‘'+q+'’ 검색';
    status.textContent=loadError||('우리두리 직접 선정 '+places.length+'곳 · 자료 확인 '+(meta.updated||'미확인')+' · 네이버 실시간 리뷰·영업정보는 지도에서 확인');
  }
  chips.forEach(btn=>btn.addEventListener('click',()=>{
    filter=btn.dataset.foodFilter;
    chips.forEach(x=>{
      const selected=x===btn;x.classList.toggle('active',selected);
      x.setAttribute('aria-pressed',String(selected));
    });
    render();
  }));
  search.addEventListener('input',render);
  region.addEventListener('change',render);
  $('foodSearchForm').addEventListener('submit',event=>{
    event.preventDefault();
    window.open(naver.href,'_blank','noopener,noreferrer');
  });
  document.querySelectorAll('[data-example-region]').forEach(button=>button.addEventListener('click',()=>{
    region.value=button.dataset.exampleRegion;
    search.value=button.dataset.exampleQuery;
    filter='전체';
    chips.forEach(x=>{const on=x.dataset.foodFilter==='전체';x.classList.toggle('active',on);x.setAttribute('aria-pressed',String(on));});
    render();
    search.focus();
    window.scrollTo({top:0,behavior:'smooth'});
  }));
  async function load(){
    try{
      const response=await fetch('./food.json',{cache:'no-store'});
      if(!response.ok)throw Error('HTTP '+response.status);
      const data=await response.json();
      if(!Array.isArray(data.places))throw Error('등록 데이터 형식 오류');
      const seen=new Set();
      places=data.places.filter(item=>{
        if(!item||typeof item.id!=='string'||typeof item.name!=='string'
           ||typeof item.address!=='string'||typeof item.city!=='string'
           ||!item.name.trim()||!item.address.trim()||seen.has(item.id))return false;
        seen.add(item.id);
        return true;
      });
      meta=data;
    }catch(error){
      loadError='추천 목록을 불러오지 못했어. 네이버 지도 검색은 계속 사용할 수 있어.';
    }
    render();
  }
  load();
})();
