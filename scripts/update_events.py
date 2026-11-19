#!/usr/bin/env python3
"""강원도 행사정보 자동 수집. Python 표준 라이브러리만 사용한다.

API 키는 환경변수 KTO_SERVICE_KEY / KOPIS_SERVICE_KEY로만 전달한다.
데이터가 실패하면 기존 이벤트를 유지하고 상태를 기록한다.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
CITIES=['강릉','동해','속초','양양','삼척','평창','춘천','원주','홍천','횡성','태백','정선','영월','인제','고성','철원','화천','양구']
SEOUL_TZ=timezone(timedelta(hours=9))
TODAY=datetime.now(SEOUL_TZ).date()
BEGIN=TODAY-timedelta(days=80)  # 이미 진행 중인 행사 조회
END=TODAY+timedelta(days=120)


def get_bytes(url, params, timeout=25):
    query=urlencode(params)
    req=Request(url+'?'+query,headers={'User-Agent':'GangwonDateCalendar/1.0 (public event info aggregator)','Accept':'application/json, application/xml, text/xml'})
    with urlopen(req,timeout=timeout) as resp:
        return resp.read()


def city_of(value):
    s=(value or '').replace('강원특별자치도','').replace('강원도','')
    for c in CITIES:
        if re.search(r'(?<![가-힣])'+re.escape(c)+r'(?:시|군)?(?![가-힣])',s): return c
    for c in CITIES:
        if c in s: return c
    return None


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
    city=city_of(addr+' '+str(raw.get('city') or '')) or ('강원 전체' if raw.get('province_wide') else None)
    start,end=iso_date(raw.get('start')),iso_date(raw.get('end'))
    if not title or not city or not start or not end or end<start or end<TODAY.isoformat() or start>END.isoformat():return None
    category=classify(title,category)
    emoji,theme=VISUAL.get(category,('🎉','sea'))
    place=str(raw.get('place') or '').strip() or addr or city
    source_url=str(raw.get('url') or '')
    if not source_url.startswith(('http://','https://')):source_url='https://www.google.com/search?q='+quote(title+' '+city)
    return {'id':f'{code}-{str(raw.get("id") or "").strip()}' if raw.get('id') else f'{code}-{title[:20]}-{start}',
            'title':title,'city':city,'category':category,'start':start,'end':end,
            'place':place,'address':addr,'price':'요금 확인 필요','priceType':'unknown','emoji':emoji,'theme':theme,
            'intro':f'{city}에서 열리는 {category} 정보. 상세 일정과 예약 여부는 공식 출처에서 확인해 줘.',
            'highlight':'주말 데이트 후보','status':'자동 수집 · 방문 전 재확인','sourceLabel':provider,
            'sourceUrl':source_url,'mapQuery':f'{city} {place}','note':'외부 데이터 자동 수집. 상세 프로그램과 변경사항은 출처 확인',
            'collectionMethod':provider+' API','lastVerified':TODAY.isoformat()}


def fetch_tourapi(key):
    url='https://apis.data.go.kr/B551011/KorService2/searchFestival2'
    rows=[];page=1
    # avoid accidentally fetching all Korea: areaCode=32 is Gangwon TourAPI code
    while page<=20:
        params={'serviceKey':key,'MobileOS':'ETC','MobileApp':'OurGangwonDate','_type':'json',
                'eventStartDate':BEGIN.strftime('%Y%m%d'),'eventEndDate':END.strftime('%Y%m%d'),
                'areaCode':'32','numOfRows':100,'pageNo':page,'arrange':'A'}
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
                'url':'https://korean.visitkorea.or.kr/search/search_list.do?keyword='+quote(str(x.get('title') or ''))},
                category='축제',provider='한국관광공사',code='tourapi')
            if item:rows.append(item)
        if page*100>=int(body.get('totalCount') or 0) or not batch:break
        page+=1
    return rows


def fetch_kopis(key):
    # KOPIS 시도 코드: 강원 51 (2026 API 공통코드 기준)
    rows=[];page=1
    while page<=30:
        params={'service':key,'stdate':TODAY.strftime('%Y%m%d'),'eddate':END.strftime('%Y%m%d'),
                'cpage':page,'rows':100,'signgucode':'51'}
        data=get_bytes('https://kopis.or.kr/openApi/restful/pblprfr',params)
        root=ET.fromstring(data)
        if root.find('.//errmsg') is not None or root.find('.//error') is not None:
            raise RuntimeError('KOPIS error '+''.join(root.itertext())[:150])
        batch=root.findall('.//db')
        for e in batch:
            get=lambda k: (e.findtext(k) or '').strip()
            code=get('mt20id');title=get('prfnm');place=get('fcltynm');city=city_of(get('adres')+' '+get('area')+' '+place)
            # 일부 공연 API에는 시군구 주소가 없을 수 있음. 강원 전체로 표시하고 출처로 확인.
            item=build({'id':code,'title':title,'city':city or '강원 전체','address':get('adres') or ((city or '강원 전체')+' '+place),
                'start':get('prfpdfrom'),'end':get('prfpdto'),'place':place,'province_wide':True,
                'url':'https://kopis.or.kr/mob/db/pblprfrView.do?mt20Id='+quote(code)},
                category='공연',provider='KOPIS',code='kopis')
            if item:rows.append(item)
        if len(batch)<100:break
        page+=1
    return rows


def signature(e):
    # Manual data wins against API data of the same named event and starting date.
    title=unicodedata.normalize('NFKC',e.get('title','')).lower()
    title=re.sub(r'^(?:제\d+회\s*)|\b20\d{2}\b','',title)
    title=re.sub(r'[^가-힣a-z0-9]','',title)
    return (title,e.get('start'),e.get('city'))


def read_list(path):
    obj=json.loads(path.read_text(encoding='utf-8'))
    return obj if isinstance(obj,list) else obj.get('events',[])


def update():
    manually=read_list(ROOT/'manual_events.json')
    previous=json.loads((ROOT/'events.json').read_text(encoding='utf-8')) if (ROOT/'events.json').exists() else {'events':[]}
    old_by_source={'tourapi':[e for e in previous.get('events',[]) if str(e.get('id','')).startswith('tourapi-')],
                   'kopis':[e for e in previous.get('events',[]) if str(e.get('id','')).startswith('kopis-')]}
    all_rows=list(manually)
    stats={'manual':len(manually)}
    success=0
    for src,env,fn in [('tourapi','KTO_SERVICE_KEY',fetch_tourapi),('kopis','KOPIS_SERVICE_KEY',fetch_kopis)]:
        key=os.getenv(env,'').strip()
        if not key:
            stats[src]='미설정'
            all_rows.extend(old_by_source[src]);continue
        try:
            rows=fn(key);success+=1
            stats[src]=len(rows)
            all_rows.extend(rows)
            print(f'{src}: {len(rows)}건 수집')
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
