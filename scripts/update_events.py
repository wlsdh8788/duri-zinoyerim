#!/usr/bin/env python3
"""전국 행사정보 자동 수집. Python 표준 라이브러리만 사용한다.

API 키는 환경변수 KTO_SERVICE_KEY / KOPIS_SERVICE_KEY로만 전달한다.
데이터가 실패하면 기존 이벤트를 유지하고 상태를 기록한다.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, quote, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
# TourAPI 주소에 사용되는 공식 시도명과 약칭을 한 화면용 표기로 정규화한다.
PROVINCE_ALIASES = {
    '서울특별시':'서울', '서울':'서울', '부산광역시':'부산', '부산':'부산',
    '대구광역시':'대구', '대구':'대구', '인천광역시':'인천', '인천':'인천',
    '광주광역시':'광주', '광주':'광주', '대전광역시':'대전', '대전':'대전',
    '울산광역시':'울산', '울산':'울산', '세종특별자치시':'세종', '세종':'세종',
    '경기도':'경기', '경기':'경기',
    '강원특별자치도':'강원', '강원도':'강원', '강원':'강원',
    '충청북도':'충북', '충북':'충북', '충청남도':'충남', '충남':'충남',
    '전북특별자치도':'전북', '전라북도':'전북', '전북':'전북',
    '전라남도':'전남', '전남':'전남',
    '경상북도':'경북', '경북':'경북', '경상남도':'경남', '경남':'경남',
    '제주특별자치도':'제주', '제주도':'제주', '제주':'제주',
}
ALIASES_ORDERED = sorted(PROVINCE_ALIASES.items(), key=lambda x: -len(x[0]))
GANGWON_CITIES = ['강릉','동해','속초','양양','삼척','평창','춘천','원주','홍천','횡성','태백','정선','영월','인제','고성','철원','화천','양구']

SEOUL_TZ=timezone(timedelta(hours=9))
TODAY=datetime.now(SEOUL_TZ).date()
BEGIN=TODAY-timedelta(days=80)  # 이미 진행 중인 행사 조회
END=TODAY+timedelta(days=120)


def get_bytes(url, params, timeout=25):
    query=urlencode(params)
    req=Request(url+'?'+query,headers={'User-Agent':'GangwonDateCalendar/1.0 (public event info aggregator)','Accept':'application/json, application/xml, text/xml'})
    with urlopen(req,timeout=timeout) as resp:
        return resp.read()


def location_of(address, area_hint=''):
    """공식 주소에서 시도/시군구 추출. 확신할 수 없는 행사는 지역 미상으로 구분."""
    s = ' '.join(str(address or '').split())
    hint = ' '.join(str(area_hint or '').split())
    province, remainder = None, s
    for alias, name in ALIASES_ORDERED:
        if s == alias or s.startswith(alias + ' '):
            province, remainder = name, s[len(alias):].strip()
            break
    if not province:
        for alias, name in ALIASES_ORDERED:
            if hint == alias or hint.startswith(alias + ' '):
                province = name
                remainder = s if s and not any(s.startswith(a) for a in PROVINCE_ALIASES) else ''
                break
    if not province:
        for city in GANGWON_CITIES:
            if s.startswith(city + '시 ') or s.startswith(city + '군 ') or s == city:
                return '강원', city
        return None, None
    if province == '세종':
        return '세종', '세종'
    token = remainder.split(' ')[0].strip() if remainder else ''
    # KOPIS가 시도명만 제공할 때 시설명 등을 시군구로 오인하지 않기 위한 방어
    if token and not re.fullmatch(r'[가-힣A-Za-z0-9·-]+(?:시|군|구)', token):
        token = ''
    if province == '강원' and token.endswith(('시','군')):
        token = token[:-1]
    return province, token or province + ' 전체'

def iso_date(value):
    digits=re.sub(r'[^0-9]','',str(value or ''))
    if len(digits)<8:return None
    try:return date.fromisoformat(digits[:4]+'-'+digits[4:6]+'-'+digits[6:8]).isoformat()
    except ValueError:return None


def classify(title, default='축제'):
    title=title or ''
    if any(w in title for w in ('팝업','팝-업','POP-UP','팝업스토어')):return '팝업'
    if any(w in title for w in ('야경','빛축제','빛 축제','불꽃','일루미네이션','점등','라이트쇼')):return '야경'
    if any(w in title for w in ('전시','미술','기획전','사진전','아트페어','박람회')):return '전시'
    if any(w in title for w in ('체험','낚시','딸기','눈썰매','스키','공방')):return '체험'
    if any(w in title for w in ('콘서트','공연','음악회','연극','뮤지컬','리사이틀')):return '공연'
    return default


VISUAL={'축제':('🎉','sea'),'공연':('🎵','music'),'전시':('🖼️','music'),'팝업':('🛍️','christmas'),'체험':('🎿','winter'),'야경':('🌙','christmas')}

def build(raw, category='축제', provider='한국관광공사', code=''):
    title=re.sub(r'<[^>]*>','',str(raw.get('title') or '')).strip()
    addr=str(raw.get('address') or '').strip()
    province, city = location_of(addr, raw.get('area_hint') or raw.get('province') or raw.get('city') or '')
    if not province and raw.get('province_wide'):
        province, city = location_of('', raw.get('area_hint') or '')
    start,end=iso_date(raw.get('start')),iso_date(raw.get('end'))
    if not title or not province or not city or not start or not end or end<start or end<TODAY.isoformat() or start>END.isoformat():return None
    category=classify(title,category)
    emoji,theme=VISUAL.get(category,('🎉','sea'))
    place=str(raw.get('place') or '').strip() or addr or city
    poster=str(raw.get('poster') or raw.get('image') or '').strip()
    if poster.startswith('http://') and ('kopis.or.kr' in poster or 'visitkorea.or.kr' in poster or 'culture.go.kr' in poster):poster='https://'+poster[7:]
    if not poster.startswith('https://'): poster=''
    source_url=str(raw.get('url') or '')
    if not source_url.startswith(('http://','https://')):source_url='https://www.google.com/search?q='+quote(title+' '+city)
    return {'id':f'{code}-{str(raw.get("id") or "").strip()}' if raw.get('id') else f'{code}-{title[:20]}-{start}',
            'title':title,'province':province,'city':city,'category':category,'start':start,'end':end,
            'place':place,'address':addr,'price':'요금 확인 필요','priceType':'unknown','emoji':emoji,'theme':theme,
            'intro':f'{province} {city}에서 열리는 {category} 정보. 상세 일정과 예약 여부는 공식 출처에서 확인해 줘.',
            'highlight':'주말 데이트 후보','status':'자동 수집 · 방문 전 재확인','sourceLabel':provider,
            'sourceUrl':source_url,'mapQuery':f'{province} {city} {place}','note':'외부 데이터 자동 수집. 상세 프로그램과 변경사항은 출처 확인',
            'collectionMethod':provider+' API','lastVerified':TODAY.isoformat(),
            'posterUrl':poster,'imageType':raw.get('imageType') or ('공식 이미지' if poster else '이미지 없음'),
            'isPermanent':bool(raw.get('isPermanent') or re.search(r'상설\s*(전시|공연|운영|체험)|상시\s*(운영|개방)',title)),
            'isLongRunning':(date.fromisoformat(end)-date.fromisoformat(start)).days+1>=60}


def fetch_tourapi(key):
    url='https://apis.data.go.kr/B551011/KorService2/searchFestival2'
    rows=[];page=1
    # 지역코드를 지정하지 않아 전국 행사 검색. pageNo로 끝까지 페이지 이동.
    while page<=50:
        params={'serviceKey':key,'MobileOS':'ETC','MobileApp':'OurGangwonDate','_type':'json',
                'eventStartDate':BEGIN.strftime('%Y%m%d'),'eventEndDate':END.strftime('%Y%m%d'),
                'numOfRows':100,'pageNo':page,'arrange':'A'}
        payload=json.loads(get_bytes(url,params).decode('utf-8'))
        response=payload.get('response') or {}
        header=response.get('header') or {}
        if str(header.get('resultCode')) not in ('0000','0'):
            raise RuntimeError('TourAPI '+str(header.get('resultMsg') or header))
        body=response.get('body') or {}
        batch=((body.get('items') or {}).get('item') or [])
        if isinstance(batch,dict):batch=[batch]
        for x in batch:
            item=build({'id':x.get('contentid'),'title':x.get('title'),'address':x.get('addr1'),
                'start':x.get('eventstartdate'),'end':x.get('eventenddate'),'place':x.get('addr1'),
                'url':'https://korean.visitkorea.or.kr/search/search_list.do?keyword='+quote(str(x.get('title') or '')),
                'image':x.get('firstimage') or x.get('firstimage2'),'imageType':'관광공사 제공 대표 이미지'},
                category='축제',provider='한국관광공사',code='tourapi')
            if item:rows.append(item)
        total_count=int(body.get('totalCount') or 0)
        if page*100>=total_count or not batch:break
        if page == 50:
            print(f'주의: 관광공사 전국 조회가 5,000건을 초과해 일부 미수집 (총 {total_count}건)', file=sys.stderr)
        page+=1
    return rows


def fetch_kopis(key):
    """KOPIS: 요청 날짜 구간 최대 31일 준수, 공식 포스터와 장르를 보존."""
    rows=[]; seen=set()
    from_day=TODAY-timedelta(days=30)
    # KOPIS 목록 API 날짜 최대 31일: 30일 이내 조각으로 조회
    while from_day<=END:
        to_day=min(from_day+timedelta(days=29),END)
        page=1
        while page<=30:
            params={'service':key,'stdate':from_day.strftime('%Y%m%d'),
                    'eddate':to_day.strftime('%Y%m%d'),'cpage':page,'rows':100}
            root=ET.fromstring(get_bytes('https://kopis.or.kr/openApi/restful/pblprfr',params))
            error=root.find('.//errmsg')
            if error is None:error=root.find('.//error')
            if error is not None:raise RuntimeError('KOPIS error '+''.join(root.itertext())[:150])
            batch=root.findall('.//db')
            for e in batch:
                get=lambda k: (e.findtext(k) or '').strip()
                code=get('mt20id')
                if not code or code in seen:continue
                seen.add(code)
                title=get('prfnm'); place=get('fcltynm'); area=get('area'); address=get('adres')
                item=build({'id':code,'title':title,'area_hint':area,'address':address or area,
                    'start':get('prfpdfrom'),'end':get('prfpdto'),'place':place,'province_wide':True,
                    'poster':get('poster'),'imageType':'KOPIS 공연 포스터',
                    'url':'https://kopis.or.kr/mob/db/pblprfrView.do?mt20Id='+quote(code)},
                    category='공연',provider='KOPIS',code='kopis')
                if item:rows.append(item)
            if len(batch)<100:break
            page+=1
        if page>30:print('주의: KOPIS 조회 구간당 최대 3000건 제한 도달', file=sys.stderr)
        from_day=to_day+timedelta(days=1)
    return rows

def fetch_culture(key):
    """문화포털 공연·전시: 공공데이터포털 현행 period2 API.

    공식 페이지 입력값은 PageNo, numOfrows (대소문자 구분)이고
    serviceTp=A는 공연/전시를 뜻한다. 인증키는 환경변수로만 전달한다.
    """
    rows = []
    page = 1
    last_ids = None
    url = 'https://apis.data.go.kr/B553457/cultureinfo/period2'
    # 공공데이터포털 인증키가 Encoding 형태여도 한 번만 인코딩되게 변환.
    key = unquote(key.strip())
    while page <= 50:
        params = {
            'serviceKey': key,
            'PageNo': page,
            'numOfrows': 100,
            'from': BEGIN.strftime('%Y%m%d'),
            'to': END.strftime('%Y%m%d'),
            'serviceTp': 'A',
        }
        try:
            raw = get_bytes(url, params, timeout=30)
        except HTTPError as exc:
            # HTTPError 문자열에는 API키가 포함된 전체 URL이 있을 수 있으므로 출력 금지.
            body = exc.read(500).decode('utf-8', errors='replace')
            body = body.replace(key, '[REDACTED]').replace(quote(key, safe=''), '[REDACTED]')
            raise RuntimeError(f'문화포털 HTTP {exc.code}: {body[:200]}') from None
        root = ET.fromstring(raw)
        rc = (root.findtext('.//resultCode') or root.findtext('.//returnReasonCode') or '').strip()
        if rc and rc not in ('00', '0000', '0'):
            msg = (root.findtext('.//resultMsg') or root.findtext('.//returnAuthMsg') or '').strip()
            raise RuntimeError(f'문화포털 응답 오류 코드 {rc}: {msg[:160]}')

        # 문화포털 데이터는 버전에 따라 perforList, item 등으로 올 수 있음.
        batch = root.findall('.//perforList')
        if not batch: batch = root.findall('.//item')
        if not batch: batch = root.findall('.//list')
        if not batch:
            if page == 1 and ('error' in root.tag.lower() or 'response' not in root.tag.lower()):
                summary=' '.join(''.join(root.itertext()).split())[:180]
                raise RuntimeError('문화포털 빈/오류 응답: '+summary)
            break

        page_ids = []
        for e in batch:
            fields = {child.tag.split('}')[-1].lower(): (child.text or '').strip() for child in e}
            def get(*names):
                return next((fields.get(n.lower(), '') for n in names if fields.get(n.lower())), '')
            seq = get('seq', 'contentId', 'id')
            page_ids.append(seq or get('title'))
            realm = get('realmName', 'serviceName', 'realm', 'genre', 'category')
            if any(word in realm for word in ('전시', '미술', '사진', '공예', '디자인')):
                category = '전시'
            elif any(word in realm for word in ('공연', '콘서트', '연극', '뮤지컬', '음악', '오페라', '무용', '발레', '국악')):
                category = '공연'
            else:
                continue  # 불명확한 자료는 임의로 분류하지 않음

            area = get('area', 'sido', 'region')
            sigungu = get('sigungu', 'city')
            address = get('placeAddr', 'placeAddress', 'address', 'addr')
            if not address:
                address = ' '.join(x for x in (area, sigungu) if x)
            event = build({
                'id': seq,
                'title': get('title', 'name'),
                'address': address,
                'area_hint': area,
                'start': get('startDate', 'startDt', 'fromDate'),
                'end': get('endDate', 'endDt', 'toDate'),
                'place': get('place', 'placeName', 'location'),
                'poster': get('thumbnail', 'imgUrl', 'imageUrl', 'image', 'poster'),
                'imageType': '문화포털 제공 포스터/이미지',
                'url': get('url', 'detailUrl', 'homepage') or 'https://www.culture.go.kr/',
            }, category=category, provider='문화포털', code='culture')
            if event:
                rows.append(event)

        # API가 페이지 번호를 무시하고 첫 페이지만 반복하는 경우 무한수집 방지
        if page_ids == last_ids:
            print('주의: 문화포털이 동일한 페이지를 반복 반환해 수집 종료', file=sys.stderr)
            break
        last_ids = page_ids
        if len(batch) < 100:
            break
        page += 1
    if page > 50:
        print('주의: 문화포털 최대 5,000건 제한 도달', file=sys.stderr)
    return rows

def signature(e):
    # Manual data wins against API data of the same named event and starting date.
    title=unicodedata.normalize('NFKC',e.get('title','')).lower()
    title=re.sub(r'^(?:제\d+회\s*)|\b20\d{2}\b','',title)
    title=re.sub(r'[^가-힣a-z0-9]','',title)
    return (title,e.get('start'),e.get('province') or location_of(e.get('address'))[0],e.get('city'))


def read_list(path):
    obj=json.loads(path.read_text(encoding='utf-8'))
    return obj if isinstance(obj,list) else obj.get('events',[])


def update():
    manually=read_list(ROOT/'manual_events.json')
    previous=json.loads((ROOT/'events.json').read_text(encoding='utf-8')) if (ROOT/'events.json').exists() else {'events':[]}
    old_by_source={'tourapi':[e for e in previous.get('events',[]) if str(e.get('id','')).startswith('tourapi-')],
                   'kopis':[e for e in previous.get('events',[]) if str(e.get('id','')).startswith('kopis-')],
                   'culture':[e for e in previous.get('events',[]) if str(e.get('id','')).startswith('culture-')]}
    all_rows=list(manually)
    stats={'manual':len(manually)}
    success=0
    for src,env,fn in [('tourapi','KTO_SERVICE_KEY',fetch_tourapi),('kopis','KOPIS_SERVICE_KEY',fetch_kopis),('culture','CULTURE_SERVICE_KEY',fetch_culture)]:
        key=os.getenv(env,'').strip()
        if not key:
            stats[src]='미설정'
            all_rows.extend(old_by_source[src]);continue
        try:
            rows=fn(key);success+=1
            stats[src]=len(rows)
            all_rows.extend(rows)
            print(f'{src}: {len(rows)}건 수집 · 사진 {sum(bool(r.get("posterUrl")) for r in rows)}건 · 시도 {len(set(r.get("province") for r in rows))}곳')
        except Exception as exc:
            stats[src]='오류 · 기존 데이터 사용'
            all_rows.extend(old_by_source[src]);print(f'{src}: {exc}',file=sys.stderr)
    if not success:
        print('경고: API 연결에 성공한 출처가 없음. 기존 데이터는 유지되며 자동 업데이트 활성화 표시는 하지 않음.',file=sys.stderr)
    seen_ids=set();seen_signatures=set();dedup=[]
    for e in all_rows:
        if not isinstance(e,dict) or not e.get('id') or not e.get('title'):continue
        if e.get('end','')<TODAY.isoformat():continue
        sig=signature(e)
        if e['id'] in seen_ids or sig in seen_signatures:continue
        seen_ids.add(e['id']);seen_signatures.add(sig)
        dedup.append(e)
    dedup.sort(key=lambda e:(e.get('start',''),e.get('city',''),e.get('title','')))
    out={'updated':datetime.now(SEOUL_TZ).strftime('%Y-%m-%d %H:%M KST') if success else previous.get('updated','미확인'),
         'auto_update':bool(success),'events':dedup,'sources':stats}
    new_text=json.dumps(out,ensure_ascii=False,indent=2)+'\n'
    (ROOT/'events.json').write_text(new_text,encoding='utf-8')
    print(f'합계 {len(dedup)}건; {stats}')
    if not success and os.getenv('GITHUB_ACTIONS')=='true':
        raise RuntimeError('수집에 성공한 API 없음. GitHub Settings > Secrets에서 KTO_SERVICE_KEY 또는 KOPIS_SERVICE_KEY 설정 필요')


if __name__=='__main__':update()
