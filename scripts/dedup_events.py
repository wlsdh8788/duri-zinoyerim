#!/usr/bin/env python3
"""공개 사이트용 중복 행사 정리.

원본 events.json은 변경하지 않는다. API 장애 시 제공처별 이전 자료를
보존하기 위해서다. 행사명·기간·시도·공연장이 모두 일치하면 한 건으로
표시하고, 시군구/주소가 더 구체적인 자료를 우선한다.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import unicodedata
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALIASES = {
    '서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구',
    '인천광역시': '인천', '광주광역시': '광주', '대전광역시': '대전',
    '울산광역시': '울산', '세종특별자치시': '세종', '경기도': '경기',
    '강원특별자치도': '강원', '강원도': '강원',
    '충청북도': '충북', '충청남도': '충남',
    '전북특별자치도': '전북', '전라북도': '전북', '전라남도': '전남',
    '경상북도': '경북', '경상남도': '경남',
    '제주특별자치도': '제주', '제주도': '제주',
}
PROVINCES = set(ALIASES.values())
ALIASES.update({province: province for province in PROVINCES})


def normalized(value: object) -> str:
    text = unicodedata.normalize('NFKC', str(value or '')).casefold()
    return re.sub(r'[^가-힣a-z0-9]', '', text)


def province_of(event: dict) -> str:
    name = str(event.get('province') or '').strip()
    if name in PROVINCES:
        return name
    if name in ALIASES:
        return ALIASES[name]
    address = str(event.get('address') or '').strip()
    for alias in sorted(ALIASES, key=len, reverse=True):
        if address == alias or address.startswith(alias + ' '):
            return ALIASES[alias]
    return name


def city_of(event: dict, province: str) -> str:
    city = str(event.get('city') or '').strip()
    address = str(event.get('address') or '').strip()
    # 주소에 구체적인 시·군·구가 있으면 광역 단위 placeholder보다 우선한다.
    for alias, canonical in sorted(ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if canonical != province:
            continue
        if address.startswith(alias + ' '):
            remainder = address[len(alias):].strip()
            match = re.match(r'^([가-힣]+(?:시|군|구))(?=\s|$)', remainder)
            if match and match.group(1) not in {'광역시', '특별시', '자치시'}:
                return match.group(1)
            break
    if (not city or city in {'전체', province, province + ' 전체', '시군구 미확인',
                              '지역 미상', '지역 확인 필요'} or
            city.endswith(' 전체') or '미확인' in city or '미상' in city):
        return ''
    if city.startswith(province + ' '):
        city = city[len(province):].strip()
    return city


def place_of(event: dict) -> str:
    place = str(event.get('place') or '').strip()
    generic = {'미정', '공연장 미정', '행사장 미정', '장소 미정', '상세 확인 필요', '미확인'}
    if place in generic or place.endswith(' 전체'):
        return ''
    return normalized(place)


def dedup_key(event: dict) -> tuple | None:
    title = normalized(event.get('title'))
    start = str(event.get('start') or '')
    end = str(event.get('end') or '')
    province = province_of(event)
    place = place_of(event)
    # 동명이인 행사 및 다른 공연장·날짜의 회차를 잘못 합치지 않기 위한 보수적 조건.
    if not all((title, start, end, province, place)) or len(place) < 5:
        return None
    return title, start, end, province, place


def score(e: dict) -> tuple:
    province = province_of(e)
    city = city_of(e, province)
    address = str(e.get('address') or '')
    poster = str(e.get('posterUrl') or e.get('imageUrl') or '')
    return (
        int(bool(city)),
        int(len(normalized(address)) >= 8),
        int(bool(poster.startswith('https://'))),
        int(bool(str(e.get('sourceUrl') or '').startswith('https://'))),
        len(normalized(e.get('place'))),
    )


def clean(events: list) -> tuple[list[dict], int]:
    groups: OrderedDict[tuple, list[dict]] = OrderedDict()
    for i, item in enumerate(events):
        if not isinstance(item, dict):
            continue
        key = dedup_key(item)
        groups.setdefault(key if key is not None else ('__unique__', i), []).append(item)

    cleaned = []
    removed = 0
    for members in groups.values():
        ordered = sorted(members, key=score, reverse=True)
        best = copy.deepcopy(ordered[0])
        province = province_of(best)
        if province:
            best['province'] = province
        city = city_of(best, province)
        best['city'] = city or '시군구 미확인'
        ids = []
        for e in members:
            ids.extend([str(e.get('id') or '')] + [str(x) for x in e.get('relatedIds', [])])
            if not best.get('posterUrl') and e.get('posterUrl'):
                best['posterUrl'] = e['posterUrl']
                best['imageType'] = e.get('imageType') or best.get('imageType')
        best['relatedIds'] = list(dict.fromkeys(i for i in ids if i and i != str(best.get('id'))))
        # 원본 파일은 보존하고 공개용 데이터에서만 병합한다.
        cleaned.append(best)
        removed += len(members) - 1
    return cleaned, removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=str(ROOT / 'events.json'))
    parser.add_argument('--output', default=str(ROOT / 'events_public.json'))
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding='utf-8'))
    events = payload.get('events')
    if not isinstance(events, list):
        raise SystemExit('events 필드가 배열이 아님: 데이터 파일 확인 필요')
    result, removed = clean(events)
    payload['events'] = result
    payload['deduplication'] = {'raw_count': len(events), 'public_count': len(result), 'removed': removed}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'공개용 중복 정리: {len(events)}건 → {len(result)}건 (중복 {removed}건 제거, 원본 유지)')


if __name__ == '__main__':
    main()
