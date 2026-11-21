#!/usr/bin/env python3
"""우리두리: 기존 수집 자료의 포스터를 공식 TourAPI 상세 이미지로 보강.

- KOPIS/문화포털 이미지는 유지
- 관광공사 축제는 detailImage2에서 '포스터/홍보물'로 명시된 이미지 우선
- 수동 등록 축제는 searchKeyword2 + detailIntro2(날짜 검증)로 같은 행사 검색
- 발견하지 못하거나 공식 이미지가 불확실하면 기존 이미지를 유지
- API 인증키는 환경변수로만 사용. Python 표준 라이브러리만 필요.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, unquote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
API = 'https://apis.data.go.kr/B551011/KorService2/'
KST = timezone(timedelta(hours=9))
POSTER_WORDS = re.compile(r'(포스터|홍보물|홍보\s*이미지|행사\s*안내문|poster)', re.I)
YEAR_WORDS = re.compile(r'(?<!\d)20\d{2}(?!\d)')


def clean_name(value):
    text = str(value or '').casefold()
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'20\d{2}(?:년)?|제\d+회', '', text)
    return re.sub(r'[^가-힣a-z0-9]+', '', text)


def title_match(a, b):
    x, y = clean_name(a), clean_name(b)
    if len(x) < 4 or len(y) < 4:
        return False
    if x == y:
        return True
    shorter, longer = sorted((x, y), key=len)
    return (len(shorter) >= 6 and shorter in longer and len(shorter)/len(longer) >= .65) or SequenceMatcher(None, x, y).ratio() >= .82


def api_call(key, endpoint, args, timeout=12):
    params = {
        'serviceKey': unquote(key.strip()), 'MobileOS': 'ETC',
        'MobileApp': 'UriDuri', '_type': 'json', 'numOfRows': 30,
        'pageNo': 1,
    }
    params.update(args)
    req = Request(API + endpoint + '?' + urlencode(params), headers={
        'User-Agent': 'UriDuriPosterEnrichment/1.0',
        'Accept': 'application/json',
    })
    with urlopen(req, timeout=timeout) as resp:
        parsed = json.loads(resp.read(1_000_000).decode('utf-8'))
    response = parsed.get('response', {})
    header = response.get('header', {})
    if str(header.get('resultCode', '0000')) not in ('0000', '0'):
        raise RuntimeError(f'{endpoint} resultCode={str(header.get("resultCode"))[:8]}')
    body = response.get('body', {})
    items = body.get('items') or {}
    if not isinstance(items, dict):
        return []
    rows = items.get('item') or []
    return [rows] if isinstance(rows, dict) else rows if isinstance(rows, list) else []


def same_year(value, year):
    years = set(YEAR_WORDS.findall(str(value or '')))
    return not years or years == {str(year)}


def https_image(value):
    url = str(value or '').strip()
    if url.startswith('http://'):
        host = (urlsplit(url).hostname or '').lower()
        if host == 'visitkorea.or.kr' or host.endswith('.visitkorea.or.kr'):
            url = 'https://' + url[7:]
    if not url.startswith('https://'):
        return ''
    split = urlsplit(url)
    if not split.hostname or split.username or split.password:
        return ''
    return url


def select_poster(items, year):
    """이미지 이름에 포스터 명시가 있어야 함. 다른 연도 표기 있으면 제외."""
    found = []
    for row in items:
        imgname = str(row.get('imgname') or row.get('imageName') or '').strip()
        if not POSTER_WORDS.search(imgname) or not same_year(imgname, year):
            continue
        url = https_image(row.get('originimgurl') or row.get('originImgUrl') or '')
        if not url:
            continue
        has_year = str(year) in YEAR_WORDS.findall(imgname)
        found.append((2 if has_year else 1, url, imgname))
    return max(found, key=lambda r:r[0]) if found else None


def event_year(event):
    try:
        return int(str(event.get('start', ''))[:4])
    except (ValueError, TypeError):
        return 0


def matches_event_date(event, item):
    """TourAPI 행사 상세 일정이 직접 확인될 때에만 수동 항목과 연결."""
    a = str(item.get('eventstartdate') or '')
    b = str(item.get('eventenddate') or '')
    if len(a) != 8 or len(b) != 8:
        return False
    try:
        start = date.fromisoformat(a[:4]+'-'+a[4:6]+'-'+a[6:])
        end = date.fromisoformat(b[:4]+'-'+b[4:6]+'-'+b[6:])
        target_start = date.fromisoformat(event['start'])
        target_end = date.fromisoformat(event['end'])
    except (ValueError, KeyError):
        return False
    # 개최 시작/종료일이 3일 이내로 일치해야 함.
    return abs((start-target_start).days) <= 3 and abs((end-target_end).days) <= 3


def match_manual_tourapi(event, key, call):
    """수동 등록 축제에 대해 공식 TourAPI 콘텐츠 ID를 엄격히 탐색."""
    if event.get('category') not in ('축제', '체험', '야경'):
        return ''
    title = str(event.get('title', ''))
    keyword = re.sub(r'^\s*20\d{2}\s*', '', title).strip()
    if not keyword:
        return ''
    rows = call(key, 'searchKeyword2', {'keyword':keyword, 'contentTypeId':'15', 'numOfRows':20})
    city = str(event.get('city') or '').replace('시', '').replace('군', '').strip()
    choices = []
    for row in rows:
        if not title_match(title, row.get('title', '')):
            continue
        if not same_year(row.get('title'), event_year(event)):
            continue
        address = str(row.get('addr1') or '')
        if city and city not in address:
            continue
        content_id = str(row.get('contentid') or '')
        if content_id.isdigit():
            choices.append(content_id)
    for content_id in choices[:3]:
        info = call(key, 'detailIntro2', {'contentId':content_id, 'contentTypeId':15})
        if info and matches_event_date(event, info[0]):
            return content_id
    return ''


def eligible(event, today):
    # 당장 방문 후보인 행사 위주로 호출량 통제.
    try:
        start = date.fromisoformat(str(event.get('start', '')))
        end = date.fromisoformat(str(event.get('end', '')))
    except ValueError:
        return False
    return end >= today and start <= today + timedelta(days=120)


def enrich_data(data, key, max_events=100, call=api_call, today=None):
    now = today or datetime.now(KST).date()
    events = data.get('events', [])
    stats = {'candidate_events':0, 'checked':0, 'official_posters_added':0,
             'unchanged':0, 'year_unconfirmed_skipped':0, 'request_failures':0}
    if not key:
        stats['message'] = 'KTO_SERVICE_KEY 미등록: 원본 유지'
        return data, stats
    candidates = []
    for event in events:
        if not isinstance(event, dict) or not eligible(event, now):
            continue
        identifier = str(event.get('id', ''))
        kind = str(event.get('category', ''))
        source = str(event.get('sourceLabel', ''))
        # KOPIS·문화포털의 자체 포스터는 교체하지 않음.
        if identifier.startswith(('kopis-', 'culture-')) or source in ('KOPIS', '문화포털'):
            continue
        if kind not in ('축제', '체험', '야경') and not identifier.startswith('tourapi-'):
            continue
        candidates.append(event)
    candidates.sort(key=lambda e: (not str(e.get('id','')).startswith('mukho-'),
                                   e.get('start',''), e.get('title','')))
    stats['candidate_events'] = len(candidates)
    for event in candidates[:max_events]:
        stats['checked'] += 1
        identifier = str(event.get('id', ''))
        try:
            content_id = identifier.split('-', 1)[1] if re.fullmatch(r'tourapi-\d+', identifier) else ''
            if not content_id:
                content_id = match_manual_tourapi(event, key, call)
            if not content_id:
                stats['unchanged'] += 1
                continue
            items = call(key, 'detailImage2', {'contentId':content_id, 'imageYN':'Y', 'numOfRows':50})
            candidate = select_poster(items, event_year(event))
            if not candidate:
                stats['unchanged'] += 1
                continue
            strength, url, name = candidate
            if strength < 2:
                # 이미지 이름에 올해 연도가 없으면 과거 포스터인지 확인 불가능. 자동 교체 금지.
                stats['year_unconfirmed_skipped'] += 1
                stats['unchanged'] += 1
                continue
            if event.get('posterUrl') != url:
                event['posterUrl'] = url
                event['imageType'] = '관광공사 등록 포스터 · 이미지 제목의 개최연도 일치'
                event['posterSource'] = 'TourAPI/detailImage2'
                event['posterConfidence'] = 'year-matched'
                stats['official_posters_added'] += 1
            else:
                stats['unchanged'] += 1
        except (HTTPError, URLError, OSError, TimeoutError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            stats['request_failures'] += 1
            # 요청 URL/인증키 노출 방지, 예외 유형만 기록
            print('poster: 수집처 일시 오류: '+type(exc).__name__, file=sys.stderr)
        time.sleep(.03)
    return data, stats


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default=str(ROOT/'events.json'))
    p.add_argument('--output', default=None)
    p.add_argument('--max-events', type=int, default=100)
    args = p.parse_args()
    path = Path(args.input)
    result = Path(args.output) if args.output else path
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or not isinstance(obj.get('events'), list):
        raise SystemExit('events.json 형식이 올바르지 않음')
    data, stats = enrich_data(obj, os.getenv('KTO_SERVICE_KEY', ''), max(0, min(args.max_events, 150)))
    data['poster_enrichment'] = stats
    result.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('포스터 자동 확인:', json.dumps(stats, ensure_ascii=False))
    print('참고: 이미지 설명에 개최연도가 없는 포스터 후보는 과거 포스터일 수 있어 자동 교체하지 않음')


if __name__ == '__main__':
    main()
