(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const input = $('foodSearch'), sort = $('foodSort'), area = $('foodArea');
  const cards = $('foodCards'), count = $('foodCount'), status = $('foodStatus');
  const categoryTitle = $('foodCategoryTitle'), naver = $('naverFind');
  const naverSummary = $('naverSummary'), more = $('foodLoadMore');
  const live = $('foodLive'), liveStatus = $('foodLiveStatus'), liveCards = $('foodLiveCards');
  const categories = [...document.querySelectorAll('[data-food-filter]')];
  const STORAGE_KEY = 'uriduri_food_personal_scores_v1';
  const CATEGORY_NAMES = {'전체':'강릉 전체 맛집','한식':'강릉 한식','피자':'강릉 피자','햄버거':'강릉 햄버거','돈까스':'강릉 돈까스','회':'강릉 횟집','양식':'강릉 양식','카페':'강릉 카페','중식':'강릉 중식','일식':'강릉 일식','고기':'강릉 고깃집','분식':'강릉 분식','치킨':'강릉 치킨','기타':'강릉 기타 음식점'};
  const CATEGORY_QUERIES = {'전체':'맛집','한식':'한식 맛집','피자':'피자','햄버거':'수제버거','돈까스':'돈까스','회':'횟집','양식':'파스타','카페':'카페','중식':'중국집','일식':'일식','고기':'고깃집','분식':'분식','치킨':'치킨','기타':'음식점'};
  const ICONS = {'한식':'🍚','피자':'🍕','햄버거':'🍔','돈까스':'🍛','회':'🐟','양식':'🍝','카페':'☕','중식':'🥟','일식':'🍣','고기':'🥩','분식':'🍜','치킨':'🍗','기타':'🍽️'};
  const PAGE_SIZE = 40;
  let places = [], selectedCategory = '전체', personal = {}, visible = PAGE_SIZE;
  let publicLoaded = false, loadError = '', liveTimer = 0, liveAbort = null, liveRevision = 0;
  const escape = s => String(s ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const naverUrl = query => 'https://map.naver.com/p/search/' + encodeURIComponent(query.trim());
  const norm = s => String(s || '').replace(/\s+/g,'').toLocaleLowerCase('ko-KR');
  const placeKey = item => norm(item.name) + '|' + norm(item.address);
  function readRatings() {
    try {
      const val = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return val && typeof val === 'object' && !Array.isArray(val)
        ? Object.fromEntries(Object.entries(val).filter(([,v]) => Number.isInteger(v) && v >= 1 && v <= 5)) : {};
    } catch { return {}; }
  }
  personal = readRatings();
  function myRating(id) { return Number(personal[id]) || 0; }
  function saveRatings() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(personal)); } catch {} }
  function searchPhrase() {
    const q = input.value.trim().slice(0, 80);
    const a = area.value;
    const region = a === '전체' ? '' : a;
    return ['강릉', region, q || CATEGORY_QUERIES[selectedCategory] || '맛집'].filter(Boolean).join(' ');
  }
  function chooseCategory(value) {
    selectedCategory = value;
    visible = PAGE_SIZE;
    for (const btn of categories) {
      const selected = btn.dataset.foodFilter === value;
      btn.classList.toggle('active', selected);
      btn.setAttribute('aria-pressed', String(selected));
    }
    render();
    scheduleLive();
  }
  function filterPlace(item) {
    if (item.city !== '강릉') return false;
    if (selectedCategory !== '전체' && item.category !== selectedCategory) return false;
    const region = area.value;
    if (region !== '전체' && ![item.district, item.address].join(' ').includes(region)) return false;
    const words = input.value.trim().toLocaleLowerCase('ko-KR').split(/\s+/).filter(Boolean);
    if (!words.length) return true;
    const haystack = [item.name,item.category,item.district,item.address,item.menu,item.type,item.note,...(item.tags || [])].join(' ').toLocaleLowerCase('ko-KR');
    return words.every(w => haystack.includes(w));
  }
  function sortedPlaces(items) {
    const result = [...items];
    if (sort.value === 'name') result.sort((a,b) => a.name.localeCompare(b.name,'ko'));
    else if (sort.value === 'my-rating') result.sort((a,b) => myRating(b.id)-myRating(a.id) || a.name.localeCompare(b.name,'ko'));
    else result.sort((a,b) => Number(b.sourceType !== 'official-permit')-Number(a.sourceType !== 'official-permit') || a.name.localeCompare(b.name,'ko'));
    return result;
  }
  function card(item) {
    const name = escape(item.name), num = myRating(item.id);
    const stars = num ? '★'.repeat(num) + '☆'.repeat(5-num) : '☆☆☆☆☆';
    const meta = item.sourceType === 'official-permit'
      ? '<span class="food-data-source">공공 인허가 목록</span>'
      : '<span class="food-data-source curated">추천 후보</span>';
    const select = '<label class="food-personal-rating"><span aria-hidden="true" class="food-stars">' + stars + '</span>' +
      '<span class="visually-hidden">' + name + ' 내 별점</span>' +
      '<select data-food-rate="' + escape(item.id) + '" aria-label="' + name + ' 내 별점">' +
      '<option value="0"' + (!num ? ' selected' : '') + '>내 별점 미등록</option>' +
      [1,2,3,4,5].map(n => '<option value="' + n + '"' + (num === n ? ' selected':'') + '>' + n + '점</option>').join('') +
      '</select></label>';
    const menu = item.menu || (item.type && item.type !== '기타' ? '업태: ' + item.type : '메뉴는 네이버 지도에서 확인');
    return '<article class="food-item" data-restaurant-id="' + escape(item.id) + '">' +
      '<div class="food-thumb" aria-hidden="true">' + escape(item.emoji || ICONS[item.category] || '🍽️') + '</div>' +
      '<div class="food-item-body">' +
        '<div class="food-item-category">' + escape(item.category) + ' <span>·</span> ' + escape(item.district || '강릉') + ' ' + meta + '</div>' +
        '<h3>' + name + '</h3>' +
        '<p class="food-item-menu">' + escape(menu) + '</p>' +
        '<p class="food-item-address">' + escape(item.address) + '</p>' +
        '<div class="food-item-actions">' + select +
          '<a class="food-map-link" href="' + escape(naverUrl('강릉 ' + item.name)) + '" target="_blank" rel="noopener noreferrer">네이버 지도 ↗</a>' +
        '</div></div></article>';
  }
  function render() {
    const filtered = sortedPlaces(places.filter(filterPlace));
    categoryTitle.textContent = CATEGORY_NAMES[selectedCategory] || '강릉 맛집';
    count.textContent = filtered.length.toLocaleString('ko-KR') + '곳';
    cards.innerHTML = filtered.length ? filtered.slice(0,visible).map(card).join('') :
      '<div class="food-empty">이 조건에 맞는 등록 식당이 없어. 검색어·카테고리를 바꾸거나 네이버 지도에서 더 찾아봐.</div>';
    more.hidden = filtered.length <= visible;
    more.textContent = '식당 더 보기 (' + Math.min(PAGE_SIZE, Math.max(0, filtered.length-visible)) + '곳)';
    const publicCount = places.filter(p => p.sourceType === 'official-permit').length;
    const prefix = publicLoaded ? '공공 인허가 ' + publicCount.toLocaleString('ko-KR') + '곳 포함' : '추천 후보 목록';
    status.textContent = loadError || (prefix + ' · 조건에 맞는 식당 ' + filtered.length.toLocaleString('ko-KR') + '곳 · 인허가 기준 영업 상태는 방문 전 확인');
    const q = searchPhrase();
    naver.href = naverUrl(q);
    naver.setAttribute('aria-label', '네이버 지도에서 ' + q + ' 검색');
    naverSummary.textContent = '네이버 지도에서 ‘' + q + '’ 더 찾아보기';
    for (const btn of categories) {
      const n = places.filter(p => p.city === '강릉' && (btn.dataset.foodFilter === '전체' || p.category === btn.dataset.foodFilter)).length;
      const counter = btn.querySelector('.food-category-count');
      if (counter) counter.textContent = n ? n.toLocaleString('ko-KR') : '';
    }
  }
  function scheduleLive() {
    if (liveTimer) clearTimeout(liveTimer);
    if (liveAbort) { liveAbort.abort(); liveAbort = null; }
    const rev = ++liveRevision;
    const endpoint = String(window.FOOD_NAVER_PROXY_URL || '').trim();
    if (!endpoint || !/^https:\/\//.test(endpoint)) {
      live.hidden = true; return;
    }
    live.hidden = false;
    liveCards.innerHTML = '';
    liveStatus.textContent = '네이버 최신 검색 결과 확인 중…';
    liveTimer = setTimeout(() => fetchLive(endpoint, rev), 500);
  }
  async function fetchLive(endpoint, rev) {
    const words = input.value.trim().slice(0,75);
    const query = [area.value === '전체' ? '' : area.value, words || CATEGORY_QUERIES[selectedCategory] || '맛집'].filter(Boolean).join(' ');
    const controller = new AbortController();
    liveAbort = controller;
    try {
      const url = new URL(endpoint);
      url.searchParams.set('q', query);
      const response = await fetch(url.toString(), {signal:controller.signal, cache:'no-store'});
      if (!response.ok) throw Error('HTTP ' + response.status);
      const data = await response.json();
      if (rev !== liveRevision) return;
      const items = Array.isArray(data.items) ? data.items.filter(x => x && x.name && (x.address||'').includes('강릉시')).slice(0,5) : [];
      liveStatus.textContent = items.length ? '네이버 지역검색 API · 최대 5곳 · 별점 미제공' : '네이버에서 일치하는 강릉 식당을 찾지 못했어.';
      liveCards.innerHTML = items.map(x => {
        const url = naverUrl('강릉 ' + x.name);
        return '<article class="food-live-item"><div><strong>' + escape(x.name) + '</strong><p>' + escape(x.category || '음식점') +
          ' · ' + escape(x.address || '강릉') + '</p></div><a class="food-map-link" href="' + escape(url) +
          '" target="_blank" rel="noopener noreferrer">네이버 지도 ↗</a></article>';
      }).join('');
    } catch (error) {
      if (rev !== liveRevision || error.name === 'AbortError') return;
      liveStatus.textContent = '실시간 검색이 일시적으로 불가능해. 아래 네이버 지도 검색을 이용해 줘.';
    } finally {
      if (liveAbort === controller) liveAbort = null;
    }
  }
  categories.forEach(btn => btn.addEventListener('click', () => chooseCategory(btn.dataset.foodFilter)));
  input.addEventListener('input', () => {visible=PAGE_SIZE;render();scheduleLive();});
  area.addEventListener('change', () => {visible=PAGE_SIZE;render();scheduleLive();});
  sort.addEventListener('change', render);
  more.addEventListener('click', () => {visible += PAGE_SIZE;render();});
  $('foodSearchForm').addEventListener('submit', event => {event.preventDefault();render();scheduleLive();});
  cards.addEventListener('change', event => {
    const el = event.target.closest('select[data-food-rate]');
    if (!el || !places.some(p => p.id === el.dataset.foodRate)) return;
    const n = Number(el.value);
    if (Number.isInteger(n) && n >= 1 && n <= 5) personal[el.dataset.foodRate] = n;
    else delete personal[el.dataset.foodRate];
    saveRatings();render();
  });
  async function loadJson(file) {
    const response = await fetch('./' + file, {cache:'no-store'});
    if (!response.ok) throw Error(file + ' HTTP ' + response.status);
    const result = await response.json();
    if (!result || !Array.isArray(result.places)) throw Error(file + ' list invalid');
    return result;
  }
  async function load() {
    const results = await Promise.allSettled([loadJson('food.json'),loadJson('food-public.json')]);
    const seenIds = new Set(), seenPlaces = new Set(), collected = [];
    results.forEach((r,index) => {
      if (r.status !== 'fulfilled') return;
      if (index === 1) publicLoaded = r.value.status === 'ok' && r.value.places.length > 0;
      for (const item of r.value.places) {
        if (!item || item.city !== '강릉' || !item.id || !item.name || !item.address || !item.category) continue;
        const identity = placeKey(item);
        if (seenIds.has(item.id) || seenPlaces.has(identity)) continue;
        seenIds.add(item.id);seenPlaces.add(identity);
        collected.push({...item, sourceType:index === 1 ? 'official-permit':'curated'});
      }
    });
    places = collected;
    if (!collected.length) loadError = '식당 목록을 불러오지 못했어. 네이버 지도 검색을 이용해 줘.';
    else if (results[1].status === 'rejected' || !publicLoaded) {
      loadError = '공공 데이터 갱신 전이야 · 현재 등록된 추천 후보 ' + collected.length + '곳';
    }
    render();scheduleLive();
  }
  load();
})();
