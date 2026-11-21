#!/usr/bin/env python3
"""우리두리 축구 일정 갱신.

- 구단이 공개한 강원FC 경기 페이지를 하루 한 차례 읽어 정확히 파싱된 경기만 병합
- 대한축구협회 공개 일정은 구조가 검증된 항목만 병합 (없을 때 기존 자료 유지)
- API 오류나 공란은 기존 sports.json 자료를 삭제하지 않음
- 확인되지 않은 티켓 오픈 시각이나 예매 가능 상태를 추측하지 않음
"""
from __future__ import annotations
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone, date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
CLUB_SCHEDULE = "https://gangwon-fc.com/match/schedule?league=all"
KFA_SCHEDULE = "https://www.kfa.or.kr/live/live.php?act=match_schedule"
CLUB_TICKETS = "https://nol.yanolja.com/ticket/genre/sports/gangwonfc"
KFA_TICKETS = "https://www.playkfa.com"
DATE_LINE = re.compile(r"^(\d{1,2})/(\d{1,2})\s*\(([월화수목금토일])\)\s*(\d{2}:\d{2})$")
HEADER = re.compile(r"^(20\d{2})\s+(0?[1-9]|1[0-2])$")
COMPETITION = re.compile(r"K리그|K LEAGUE|ACL|AFC|코리아컵|챔피언스", re.I)
CLUB_ALIASES = ("강원", "강원FC", "강원 FC")
KOREA = ("대한민국", "한국", "남자 국가대표팀")

class TextCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if not self.hidden and tag == "img":
            a = dict(attrs)
            alt = a.get("alt", "").strip()
            # 구단의 경기별 상대팀 이미지에 기록된 팀명을 활용
            if alt and len(alt) < 32:
                self.tokens.append(alt)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            value = " ".join(unescape(data).split())
            if value:
                self.tokens.append(value)

def collect_tokens(html):
    parser = TextCollector()
    parser.feed(html)
    return parser.tokens

def club_team(value):
    name = re.sub(r"\s+", " ", str(value).strip())
    if name in CLUB_ALIASES:
        return "강원FC"
    if name in ("키치 SC", "킷치 SC"):
        return "킷치 SC"
    if name in ("대전", "대전하나시티즌"):
        return "대전하나시티즌"
    if name in ("인천", "인천유나이티드", "인천 유나이티드"):
        return "인천 유나이티드"
    return name

def classify(match):
    """실제 개최 장소가 확인된 경우에만 근거리 홈경기를 분류."""
    venue = str(match.get("venue") or "")
    home = str(match.get("home") or "")
    away = str(match.get("away") or "")
    team = match.get("teamGroup")
    match["isHome"] = team == "gangwon" and home == "강원FC"
    match["localHome"] = ""
    match["domesticNational"] = False
    if match["isHome"]:
        if any(word in venue for word in ("강릉", "하이원")):
            match["localHome"] = "강릉"
        elif any(word in venue for word in ("춘천", "송암")):
            match["localHome"] = "춘천"
    if team == "national":
        korean_venue = any(v in venue for v in (
            "서울", "수원", "천안", "용인", "대전", "인천", "부산", "울산",
            "대구", "광주", "전주", "강릉", "춘천", "고양", "화성", "안양", "김천"
        ))
        match["domesticNational"] = bool(korean_venue and (home in KOREA or away in KOREA))
    # 공식 예매처 진입점과 예매 개시 여부는 구분하여 표시
    match["ticketInfoUrl"] = CLUB_TICKETS if match["isHome"] else (KFA_TICKETS if match["domesticNational"] else "")
    match["ticketStatus"] = "unconfirmed"
    match["ticketOpenAt"] = ""
    return match

def parse_gangwon_tokens(tokens, today=None):
    today = today or datetime.now(KST).date()
    found = []
    year, month = None, None
    for i, token in enumerate(tokens):
        header = HEADER.match(token)
        if header:
            year, month = int(header[1]), int(header[2])
            continue
        hit = DATE_LINE.match(token)
        if not hit:
            continue
        mm, dd, weekday, when = int(hit[1]), int(hit[2]), hit[3], hit[4]
        # 헤더의 년/월이 일치해야 다른 페이지/알림의 날짜가 섞이지 않음
        if year is None or month != mm:
            continue
        try:
            d = date(year, mm, dd)
        except ValueError:
            continue
        if not (today - timedelta(days=45) <= d <= today + timedelta(days=150)):
            continue
        # 다음 날짜까지의 블록으로 제한
        block = []
        for next_item in tokens[i + 1:i + 24]:
            if DATE_LINE.match(next_item) or HEADER.match(next_item):
                break
            block.append(next_item)
        if "VS" not in block:
            continue
        j = block.index("VS")
        if j < 2 or j + 1 >= len(block):
            continue
        # 일반적으로: 경기장 / 홈팀 이미지+이름 / VS / 원정팀 이미지+이름 / 대회
        venue = block[0].strip()
        before = [club_team(x) for x in block[1:j] if x.strip()]
        after = [club_team(x) for x in block[j + 1:j + 5] if x.strip() and not COMPETITION.search(x)]
        if not before or not after:
            continue
        home, away = before[-1], after[0]
        if "강원FC" not in (home, away):
            continue
        if not re.fullmatch(r"\d{2}:\d{2}", when):
            continue
        competition = next((x for x in block[j + 1:] if COMPETITION.search(x)), "대회 확인 필요")
        obj = {
            "id": f"gw-official-{d:%Y%m%d}-{re.sub('[^a-z0-9가-힣]', '', away if home == '강원FC' else home)}",
            "teamGroup": "gangwon", "competition": competition,
            "date": d.isoformat(), "time": when,
            "home": home, "away": away, "venue": venue,
            "sourceName": "강원FC 공식 경기일정", "sourceUrl": CLUB_SCHEDULE,
        }
        found.append(classify(obj))
    unique = {(m["date"], m["home"], m["away"]): m for m in found}
    return list(unique.values())

def fetch_text(url):
    req = Request(url, headers={
        "User-Agent": "UriDuriPersonalSchedule/1.0 (+official match links)",
        "Accept": "text/html",
    })
    with urlopen(req, timeout=18) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        raw = resp.read(2_500_000)
        encoding = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(encoding, errors="replace")

def key(m):
    names = (str(m.get("home", "")).replace(" ", ""),
             str(m.get("away", "")).replace(" ", ""))
    return (m.get("teamGroup"), m.get("date"), names[0], names[1])

def merge(existing, discovered, now):
    out = []
    where = {}
    for row in existing:
        if not isinstance(row, dict):
            continue
        clone = dict(row)
        classify(clone)
        ident = key(clone)
        if ident in where:
            continue
        where[ident] = len(out)
        out.append(clone)
    changed = 0
    for fresh in discovered:
        ident = key(fresh)
        if ident in where:
            index = where[ident]
            old = out[index]
            # 기존 수동 등록 고유 id 및 확정 예매일 보존
            updated = dict(old)
            for field in ("competition", "time", "venue", "sourceName", "sourceUrl"):
                if fresh.get(field):
                    updated[field] = fresh[field]
            classify(updated)
            out[index] = updated
            if updated != old:
                changed += 1
        else:
            where[ident] = len(out)
            out.append(dict(fresh))
            changed += 1
    # 자료가 오래 남아도 과거 기록의 연도별 추적 가능하도록 보존
    out.sort(key=lambda x:(x.get("date", ""), x.get("time", ""), x.get("id", "")))
    return out, changed

def apply_ticket_overrides(matches, path):
    if not path.exists():
        return 0
    raw = json.loads(path.read_text(encoding="utf-8"))
    patches = raw.get("matches", {})
    if not isinstance(patches, dict):
        return 0
    count = 0
    for match in matches:
        patch = patches.get(match.get("id"))
        if not isinstance(patch, dict):
            continue
        opening = str(patch.get("ticketOpenAt", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\+09:00", opening):
            continue
        # 예매 시작일이 공식 공지된 경우에만 표시
        if not str(patch.get("announcementUrl", "")).startswith("https://"):
            continue
        match["ticketOpenAt"] = opening
        match["ticketStatus"] = "announced"
        match["ticketAnnouncementUrl"] = patch["announcementUrl"]
        count += 1
    return count

def main():
    destination = ROOT / "sports.json"
    document = json.loads(destination.read_text(encoding="utf-8"))
    current = datetime.now(KST).date()
    original = document.get("matches") or []
    pulled = []
    statuses = {}
    # 구단 공식 홈페이지가 공개한 일정(현재 페이지의 월)을 적은 빈도로 확인
    try:
        tokens = collect_tokens(fetch_text(CLUB_SCHEDULE))
        pulled = parse_gangwon_tokens(tokens, today=current)
        statuses["gangwon"] = ("updated" if pulled else "no_new_verified_games")
    except (OSError, HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as exc:
        statuses["gangwon"] = "fetch_error_" + type(exc).__name__
    # KFA 남자 A 경기 신규 발표: 공식 API 미연동. 기존 확인 자료 보존하고 공식 일정 링크 제공
    statuses["national"] = "official_api_not_connected"
    merged, changed = merge(original, pulled, current)
    ticket_count = apply_ticket_overrides(merged, ROOT / "sports_ticket_overrides.json")
    document["matches"] = merged
    document["updated"] = current.isoformat()
    document["last_checked"] = datetime.now(KST).isoformat(timespec="minutes")
    document["auto_update"] = bool(pulled)
    document["source_status"] = statuses
    document["message"] = ("강원FC 공식 경기일정 페이지 확인. 국가대표 새 경기 자동수집은 미연동; "
                           "예매 시작일은 공식 공지가 있는 경우에만 표시.")
    destination.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("축구 일정 자동 확인:", json.dumps({
        "gangwon_fixtures": len(pulled), "merged_changed": changed,
        "ticket_announcements": ticket_count,
        "source_status": statuses
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
