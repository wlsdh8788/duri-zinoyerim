(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const input=$('foodSearch');
  const sort=$('foodSort');
  const cards=$('foodCards');
  const categoryTitle=$('foodCategoryTitle');
  const count=$('foodCount');
  const status=$('foodStatus');
  const naver=$('naverFind');
  const naverSummary=$('naverSummary');
  const categories=[...document.querySelectorAll('[data-food-filter]')];
  const STORAGE_KEY='uriduri_food_personal_scores_v1';
  const CATEGORY_NAMES={'전체':'강릉 전체 맛집','한식':'강릉 한식','피자':'강릉 피자','햄버거':'강릉 햄버거','돈까스':'강릉 돈까스','회':'강릉 횟집','양식':'강릉 양식','카페':'강릉 카페'};
  const CATEGORY_QUERIES={'전체':'맛집','한식':'한식 맛집','피자':'피자 맛집','햄버거':'수제버거','돈까스':'돈까스','회':'횟집','양식':'파스타 맛집','카페':'카페'};
  let places=[],meta={},selectedCategory='전체',personal={},loadError='';
  const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const naverUrl=query=>'https://map.naver.com/p/search/'+encodeURIComponent(query.trim());
  function readRatings(){
    try{
      const stored=JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}');
      if(!stored||typeof stored!=='object'||Array.isArray(stored))return {};
      return Object.fromEntries(Object.entries(stored).filter(([,v])=>Number.isInteger(v)&&v>=1&&v<=5));
    }catch(err){return {};}
  }
  function saveRatings(){
    try{localStorage.setItem(STORAGE_KEY,JSON.stringify(personal));}catch(err){}
  }
  personal=readRatings();
  function myRating(id){return Number(personal[id])||0;}
  function searchPhrase(){
    const q=input.value.trim().slice(0,100);
    return ['강릉',q||(CATEGORY_QUERIES[selectedCategory]||'맛집')].filter(Boolean).join(' ');
  }
  function chooseCategory(value){
    selectedCategory=value;
    for(const btn of categories){
      const selected=btn.dataset.foodFilter===value;
      btn.classList.toggle('active',selected);
      btn.setAttribute('aria-pressed',String(selected));
    }
    render();
  }
  function filterPlace(item){
    if(item.city!=='강릉')return false;
    if(selectedCategory!=='전체'&&item.category!==selectedCategory)return false;
    const q=input.value.trim().toLocaleLowerCase('ko-KR');
    if(!q)return true;
    const parts=q.split(/\s+/).filter(Boolean);
    const haystack=[item.name,item.category,item.district,item.address,item.menu,item.note,...(item.tags||[])]
      .join(' ').toLocaleLowerCase('ko-KR');
    return parts.every(x=>haystack.includes(x));
  }
  function sortedPlaces(items){
    const data=items.map((row,i)=>({row,i}));
    if(sort.value==='name'){
      data.sort((a,b)=>a.row.name.localeCompare(b.row.name,'ko'));
    }else if(sort.value==='my-rating'){
      data.sort((a,b)=>myRating(b.row.id)-myRating(a.row.id)||a.row.name.localeCompare(b.row.name,'ko'));
    }
    return data.map(x=>x.row);
  }
  function card(item){
    const url=naverUrl('강릉 '+item.name);
    const name=escape(item.name),menu=escape(item.menu||item.category||'식당');
    const location=escape([item.district,item.address].filter(Boolean).join(' · '));
    const emoji=escape(item.emoji||'🍽️');
    const num=myRating(item.id);
    const stars=num?'★'.repeat(num)+'☆'.repeat(5-num):'☆☆☆☆☆';
    const select='<label class="food-personal-rating"><span aria-hidden="true" class="food-stars">'+stars+'</span>'+
      '<span class="visually-hidden">'+name+' 나의 별점</span>'+
      '<select data-food-rate="'+escape(item.id)+'" aria-label="'+name+' 나의 별점">'+
      '<option value="0"'+(!num?' selected':'')+'>내 별점 미등록</option>'+
      [1,2,3,4,5].map(n=>'<option value="'+n+'"'+(num===n?' selected':'')+'>'+n+'점</option>').join('')+
      '</select></label>';
    return '<article class="food-item" data-restaurant-id="'+escape(item.id)+'">'+
      '<div class="food-thumb" aria-hidden="true">'+emoji+'</div>'+
      '<div class="food-item-body">'+
        '<div class="food-item-category">'+escape(item.category)+' <span>·</span> '+escape(item.district||'강릉')+'</div>'+
        '<h3>'+name+'</h3>'+
        '<p class="food-item-menu">'+menu+'</p>'+
        '<p class="food-item-address">'+location+'</p>'+
        '<div class="food-item-actions">'+select+
        '<a href="'+escape(url)+'" class="food-map-link" target="_blank" rel="noopener noreferrer" aria-label="'+name+' 네이버 지도에서 확인">네이버 지도 ↗</a>'+
        '</div>'+
      '</div></article>';
  }
  function render(){
    const filtered=sortedPlaces(places.filter(filterPlace));
    const counts=places.filter(x=>x.city==='강릉'&&(selectedCategory==='전체'||x.category===selectedCategory));
    const q=searchPhrase();
    categoryTitle.textContent=CATEGORY_NAMES[selectedCategory]||'강릉 맛집';
    count.textContent=filtered.length+'곳';
    cards.innerHTML=filtered.length?filtered.map(card).join(''):
      '<div class="food-empty">해당 조건에 등록된 강릉 식당이 없어.<br>다른 음식 종류를 선택하거나 네이버 지도에서 직접 검색해 봐.</div>';
    const rated=places.filter(item=>myRating(item.id)>0).length;
    status.textContent=loadError||(
      input.value.trim()?'검색 결과 '+filtered.length+'곳 · 등록 '+counts.length+'곳':
      '강릉 식당 '+filtered.length+'곳 · 내 별점 등록 '+rated+'곳'
    );
    naver.href=naverUrl(q);
    naver.setAttribute('aria-label','네이버 지도에서 '+q+' 검색하기');
    naverSummary.textContent='네이버 지도에서 ‘'+q+'’ 더 찾아보기';
  }
  categories.forEach(btn=>btn.addEventListener('click',()=>chooseCategory(btn.dataset.foodFilter)));
  input.addEventListener('input',render);
  sort.addEventListener('change',render);
  $('foodSearchForm').addEventListener('submit',event=>{
    event.preventDefault();
    render();
  });
  cards.addEventListener('change',event=>{
    const select=event.target.closest('select[data-food-rate]');
    if(!select)return;
    const id=select.dataset.foodRate;
    if(!places.some(item=>item.id===id))return;
    const number=Number(select.value);
    if(Number.isInteger(number)&&number>=1&&number<=5)personal[id]=number;
    else delete personal[id];
    saveRatings();
    render();
  });
  async function load(){
    try{
      const res=await fetch('./food.json',{cache:'no-store'});
      if(!res.ok)throw Error('HTTP '+res.status);
      const data=await res.json();
      if(!Array.isArray(data.places))throw Error('Invalid restaurant list');
      const seen=new Set();
      places=data.places.filter(item=>{
        if(!item||typeof item.id!=='string'||typeof item.name!=='string'
          ||typeof item.city!=='string'||typeof item.category!=='string'
          ||typeof item.address!=='string'||!item.name.trim()||seen.has(item.id))return false;
        seen.add(item.id);
        return item.city==='강릉';
      });
      meta=data;
    }catch(err){
      loadError='식당 데이터를 불러오지 못했어. 네이버 지도 검색은 사용할 수 있어.';
    }
    render();
  }
  load();
})();
