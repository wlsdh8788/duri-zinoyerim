#!/usr/bin/env python3
"""KOPIS 기반 우리두리 '인기 상업 뮤지컬' 별도 데이터 자동 갱신.

선정: 공연명 사전 + KOPIS 상세 장르 '뮤지컬' + 상세 출연진 명단에 등록된 인물.
KOPIS는 공연별 유명도/상업성 인증을 제공하지 않으므로 편집 기준으로 분류한다.
비밀키는 GitHub Actions 환경변수로만 전달하며 공개 JSON에는 절대 포함하지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, date
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import json
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
KOPIS_BASE = "https://kopis.or.kr/openApi/restful/pblprfr/"
TICKET_HOSTS = {
    "ticket.interpark.com", "tickets.interpark.com", "nol.interpark.com",
    "nol.yanolja.com", "www.ticketlink.co.kr", "ticketlink.co.kr",
    "ticket.yes24.com", "ticket.melon.com", "melonticket.com",
    "www.playdb.co.kr", "ticket.11st.co.kr",
}
BAD_TITLE = re.compile(r"어린이|아동|유아|유치원|학예회|학생|동아리|발표회|갈라|쇼케이스|리딩|체험|키즈|콘서트")

def normalize(value: str) -> str:
    text = str(value or "")
    for _ in range(3):
        text = unescape(text)
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[^가-힣a-z0-9]", "", text)

def title_matches(title: str, titles: list[str], exclusions: list[str]) -> bool:
    raw = str(title or "")
    normal = normalize(raw)
    if not normal or any(normalize(x) in normal for x in exclusions if x):
        return False
    # 짧고 지나치게 넓은 작품명은 매칭하지 않는다.
    return any(len(normalize(name)) >= 3 and normalize(name) in normal for name in titles)

def recognized_actors(cast: str, actors: list[str]) -> list[str]:
    names = set(re.split(r"\s*[,;/·、\n]\s*|\s+및\s+", str(cast or "")))
    results = []
    for actor in actors:
        candidate = actor.strip()
        # 역할·괄호 표기가 있어도 확인하되, 2글자 이름이 다른 이름의 일부인 경우는 배제.
        if len(candidate) >= 3 and (
            candidate in names or any(
                n == candidate or n.startswith(candidate + "(") or n.startswith(candidate + " (")
                for n in names
            )
        ) and candidate not in results:
            results.append(candidate)
        elif len(candidate) == 2 and (
            candidate in names or any(
                n == candidate or n.startswith(candidate + "(") or n.startswith(candidate + " (")
                for n in names
            )
        ) and candidate not in results:
            results.append(candidate)
    return results

def ticket_url_from_detail(root: ET.Element) -> str:
    for item in root.findall(".//relates/relate"):
        name = "".join(item.findtext("relatenm", "")).strip().lower()
        url = unescape(item.findtext("relateurl", "") or "").strip()
        try:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname not in TICKET_HOSTS:
                continue
            if any(word in name for word in ("예매", "티켓", "인터파크", "yes24", "놀티켓", "멜론", "티켓링크")):
                return url
        except ValueError:
            continue
    return ""

def read_details(key: str, mt20id: str, timeout=13) -> ET.Element:
    if not re.fullmatch(r"PF\d+", mt20id):
        raise ValueError("Invalid KOPIS performance ID")
    url = KOPIS_BASE + quote(mt20id) + "?service=" + quote(key, safe="")
    request = Request(url, headers={
        "User-Agent": "UriDuriMusicals/1.0", "Accept": "application/xml, text/xml"
    })
    with urlopen(request, timeout=timeout) as response:
        xml = response.read(800_000)
    root = ET.fromstring(xml)
    if root.find(".//errmsg") is not None:
        raise ValueError("KOPIS detail returned error")
    db = root.find(".//db")
    if db is None:
        raise ValueError("KOPIS detail missing db")
    return db

def is_musical(genre: str) -> bool:
    return "뮤지컬" in str(genre or "")

def valid_poster(value: str) -> str:
    url = str(value or "").strip()
    if url.startswith("http://") and "kopis.or.kr" in url:
        url = "https://" + url[7:]
    return url if url.startswith("https://") else ""

def build_musical(event: dict, detail: ET.Element, actors: list[str]) -> dict | None:
    genre = detail.findtext("genrenm", "").strip()
    if not is_musical(genre):
        return None
    cast = unescape(detail.findtext("prfcast", "") or "").strip()
    featured = recognized_actors(cast, actors)
    if not featured:
        return None
    title = unescape(detail.findtext("prfnm", "") or event.get("title", ""))
    id_ = str(event["id"])
    poster = valid_poster(detail.findtext("poster", "") or event.get("posterUrl", ""))
    place = (detail.findtext("fcltynm", "") or event.get("place", "")).strip()
    return {
        "id": id_, "title": title, "start": event.get("start"), "end": event.get("end"),
        "province": event.get("province", ""), "city": event.get("city", ""),
        "place": place, "address": event.get("address", ""),
        "posterUrl": poster, "featuredCast": featured[:8],
        "castSummary": cast[:250], "genre": genre,
        "ticketUrl": ticket_url_from_detail(detail),
        "sourceUrl": "https://kopis.or.kr/mob/db/pblprfrView.do?mt20Id=" + quote(id_[6:]),
        "sourceName": "KOPIS 공연예술통합전산망",
        "verifiedOn": datetime.now(KST).date().isoformat(),
        "selection": "대표 작품과 KOPIS 등록 출연진 기준",
    }

def update():
    cfg = json.loads((ROOT / "musical_criteria.json").read_text(encoding="utf-8"))
    output = ROOT / "musicals.json"
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"performances":[]}
    old_by_id = {m["id"]: m for m in existing.get("performances", []) if isinstance(m, dict) and m.get("id")}
    events = json.loads((ROOT / "events.json").read_text(encoding="utf-8")).get("events", [])
    now = datetime.now(KST)
    today = now.date().isoformat()
    pool = [
        e for e in events
        if isinstance(e, dict) and str(e.get("id", "")).startswith("kopis-PF")
        and e.get("end", "") >= today
        and title_matches(e.get("title", ""), cfg["known_titles"], cfg["exclude_title_contains"])
    ]
    pool.sort(key=lambda e: (e.get("start", ""), e.get("title", "")))
    # API 호출 과다 방지를 위해 검증할 작품 수 제한 (목록 누락 가능성은 상태에 표시)
    cap = 60
    to_check = pool[:cap]
    key = os.getenv("KOPIS_SERVICE_KEY", "").strip()
    if not key:
        print("인기 뮤지컬: KOPIS_SERVICE_KEY 없음. 기존 결과를 보존함.")
        return

    found = []
    checked = 0
    reused = 0
    excluded = 0
    failed = 0
    for event in to_check:
        id_ = event["id"]
        old = old_by_id.get(id_)
        if old and old.get("verifiedOn") == today and old.get("start") == event.get("start") and old.get("end") == event.get("end"):
            found.append(old)
            reused += 1
            continue
        checked += 1
        try:
            db = read_details(key, id_[6:])
            result = build_musical(event, db, cfg["featured_cast"])
            if result:
                found.append(result)
            else:
                excluded += 1
        except Exception as exc:
            failed += 1
            # HTTPError 문자열엔 인증키가 들어갈 수 있으므로 예외 본문/URL은 절대 출력 안 함
            print("musicals: 상세 조회 실패 " + id_ + " (" + type(exc).__name__ + ")", file=sys.stderr)
            if old:
                found.append(old)
        time.sleep(0.05)
    # 일부 API가 빈 값을 반환해도 기존 확인 작품은 공연 종료일까지 보존.
    already = {m["id"] for m in found}
    for id_, item in old_by_id.items():
        if item.get("end", "") >= today and id_ not in already and not any(e.get("id") == id_ for e in pool):
            # KOPIS 목록 자체가 누락된 경우에는 기존 확인 공연을 보존
            found.append(item)
    found.sort(key=lambda m: (m.get("start",""), m.get("title","")))
    status = {
        "candidates":len(pool), "checked":checked, "reused":reused, "selected":len(found),
        "not_selected":excluded, "failures":failed, "limited":len(pool)>cap,
    }
    output.write_text(json.dumps({
        "version":1,"updated":now.strftime("%Y-%m-%d %H:%M KST"),
        "auto_update":True,
        "selection_note":"KOPIS에서 뮤지컬 장르 확인 + 사전 지정 대형 작품 + 지정 배우 출연 확인. 배우별 회차 출연은 별도 확인 필요.",
        "stats":status,"performances":found,
    }, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    print("인기 뮤지컬 자동 갱신:", json.dumps(status, ensure_ascii=False))

if __name__ == "__main__":
    update()
