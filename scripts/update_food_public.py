#!/usr/bin/env python3
"""Build a Gangneung restaurant directory from official LOCALDATA licence records.

The official licence dataset is NOT a review or recommendation dataset.
Only basic store names, business-type labels and addresses are published.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse
import urllib.request

ORG_CODE = "4201000"  # 강원강릉시
BASE = "https://file.localdata.go.kr"
REFERER = BASE + "/file/general_restaurants/info"
SLUGS = ("general_restaurants", "rest_cafes")
OUTPUT = Path(__file__).resolve().parents[1] / "food-public.json"
CATEGORIES = ("한식", "피자", "햄버거", "돈까스", "회", "양식", "카페",
              "중식", "일식", "고기", "분식", "치킨", "기타")
ICONS = {"한식": "🍚", "피자": "🍕", "햄버거": "🍔", "돈까스": "🍛",
         "회": "🐟", "양식": "🍝", "카페": "☕", "중식": "🥟",
         "일식": "🍣", "고기": "🥩", "분식": "🍜", "치킨": "🍗", "기타": "🍽️"}


def category_for(name: str, kind: str) -> str:
    """Infer a browsing category; do not claim to have inspected actual menus."""
    n = name.lower().replace(" ", "")
    k = kind.replace(" ", "")
    if any(x in n for x in ("돈까스", "돈가스", "돈카츠", "돈카쓰", "돈까츠")):
        return "돈까스"
    if any(x in n for x in ("피자", "pizza")):
        return "피자"
    if any(x in n for x in ("버거", "burger")) or k == "패스트푸드" and "햄" in n:
        return "햄버거"
    if any(x in n for x in ("횟집", "회센터", "회센타", "물회", "참치회")) or k == "횟집":
        return "회"
    if (k in ("커피숍", "까페", "카페", "다방", "제과점영업")
            or any(x in n for x in ("카페", "cafe", "coffee", "커피", "로스터리", "베이커리", "제과"))):
        return "카페"
    if any(x in n for x in ("치킨", "통닭", "닭강정", "굽네", "교촌", "비비큐", "bbq")) or k == "통닭(치킨)":
        return "치킨"
    if (any(x in n for x in ("스시", "초밥", "라멘", "우동", "돈부리", "이자카야"))
            or k == "일식"):
        return "일식"
    if (any(x in n for x in ("짜장", "짬뽕", "마라탕", "마라샹궈", "탕수육", "중화"))
            or k == "중국식"):
        return "중식"
    if (any(x in n for x in ("떡볶이", "김밥", "분식", "순대"))
            or k in ("분식", "김밥(도시락)", "일반조리판매")):
        return "분식"
    if (any(x in n for x in ("삼겹살", "갈비", "한우", "곱창", "고깃집", "고기집", "숯불", "불고기"))
            or "식육" in k):
        return "고기"
    if (any(x in n for x in ("파스타", "스테이크", "브런치", "비스트로"))
            or k in ("경양식", "양식")):
        return "양식"
    if k == "한식" or any(x in n for x in ("순두부", "국밥", "장칼국수", "옹심이", "막국수", "백반")):
        return "한식"
    return "기타"


def district_for(address: str) -> str:
    found = re.search(r"\b(주문진읍|(?:[가-힣]{2,8})(?:면|동))\b", address.split("강릉시", 1)[-1])
    return found.group(1) if found else "강릉"


def is_open(row: dict) -> bool:
    states = " ".join(str(row.get(col, "") or "") for col in ("영업상태명", "상세영업상태명"))
    if any(word in states for word in ("폐업", "휴업", "취소", "말소", "정지")):
        return False
    return "영업" in states or "정상" in states


def convert_rows(rows, source: str):
    out = []
    for row in rows:
        name = (row.get("사업장명") or "").strip()
        address = (row.get("도로명주소") or row.get("지번주소") or "").strip()
        kind = (row.get("업태구분명") or "").strip()
        if not name or not address or "강릉시" not in address or not is_open(row):
            continue
        # Exclude transient festival stalls that are not normal restaurant destinations.
        if any(word in name for word in ("월화거리야시장", "단오제 임시", "임시영업")):
            continue
        category = category_for(name, kind)
        identity = name.replace(" ", "").lower() + "|" + re.sub(r"\s+", "", address)
        uid = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        out.append({
            "id": "permit-" + uid, "name": name, "city": "강릉",
            "district": district_for((row.get("지번주소") or "") + " " + address),
            "category": category, "address": address, "menu": "",
            "type": kind or "음식점", "emoji": ICONS[category],
            "tags": [kind] if kind else [],
            "sourceType": "official-permit", "sourceName": "행정안전부 지방행정 인허가데이터",
            "sourceUrl": "https://www.localdata.go.kr/",
            "verifiedAt": "", "rating": None
        })
    return out


def fetch_csv(slug: str):
    url = BASE + "/file/download/" + slug + "/info?" + urllib.parse.urlencode({"orgCode": ORG_CODE})
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; UriduriFoodBot/1.0)",
                      "Referer": REFERER, "Accept": "text/csv,*/*"})
    with urllib.request.urlopen(req, timeout=110) as response:
        payload = response.read(60 * 1024 * 1024)
        if response.read(1):
            raise ValueError("LOCALDATA response exceeds 60MB")
    decoded = payload.decode("cp949", errors="replace").lstrip("\ufeff")
    rows = list(csv.DictReader(io.StringIO(decoded)))
    if not rows or "사업장명" not in rows[0]:
        raise ValueError("LOCALDATA CSV header invalid for " + slug)
    return rows


def main() -> int:
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d")
    all_rows, errors, sources = [], [], []
    for slug in SLUGS:
        try:
            rows = fetch_csv(slug)
            all_rows.extend(convert_rows(rows, slug))
            sources.append(slug)
            print(f"{slug}: {len(rows)} raw entries", flush=True)
        except Exception as err:
            errors.append(slug + ": " + str(err))
            print(f"WARNING: {errors[-1]}", file=sys.stderr, flush=True)
    if not sources:
        if OUTPUT.exists():
            try:
                old = json.loads(OUTPUT.read_text(encoding="utf-8"))
                if old.get("places"):
                    print("Official feed unavailable; preserve last valid public data.")
                    return 0
            except (OSError, ValueError):
                pass
        # Maintain a deployable fallback while making the failure visible in metadata.
        all_rows = []
    unique = {}
    for item in all_rows:
        # Licence feeds can contain duplicated names for the same address.
        key = (re.sub(r"\s+", "", item["name"]).lower(),
               re.sub(r"\s+", "", item["address"]))
        unique.setdefault(key, item)
    entries = sorted(unique.values(), key=lambda x: (x["category"], x["name"], x["address"]))
    for item in entries:
        item["verifiedAt"] = today
    data = {
        "version": 1, "updated": today, "defaultRegion": "강릉",
        "source": "행정안전부 지방행정 인허가데이터(LOCALDATA), 강릉시",
        "sourceUrl": "https://www.localdata.go.kr/",
        "status": "ok" if sources else "unavailable",
        "note": "영업 인허가 정보이며 맛집 순위나 실제 당일 영업 여부를 보장하지 않습니다. 음식 분류는 업태·상호에 따른 추정입니다.",
        "errors": errors, "categories": list(CATEGORIES), "places": entries
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n",
                      encoding="utf-8")
    print(f"Saved {len(entries)} unique Gangneung permitted establishments to {OUTPUT.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
