#!/usr/bin/env python3
"""우리두리 유명 가수 콘서트 자동 수집 (KOPIS 대중음악 CCCD).

단순 축제나 클래식·뮤지컬을 포함시키지 않는다. KOPIS 상세 장르가
대중음악이고 지정한 가수/그룹 이름이 제목이나 출연진에 실제로 존재할 때
별도 콘서트 목록에 추가한다. '유명'은 편집 기준이며 공식 인기순위가 아니다.
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
LIST_URL = "https://kopis.or.kr/openApi/restful/pblprfr"
DETAIL_URL = LIST_URL + "/"
VENUE_PROVINCES = {
    "서울특별시":"서울","경기도":"경기","인천광역시":"인천",
    "강원특별자치도":"강원","강원도":"강원",
    "부산광역시":"부산","대구광역시":"대구","광주광역시":"광주",
    "대전광역시":"대전","울산광역시":"울산","세종특별자치시":"세종",
    "경상북도":"경북","경상남도":"경남",
    "충청북도":"충북","충청남도":"충남",
    "전라북도":"전북","전북특별자치도":"전북","전라남도":"전남",
    "제주특별자치도":"제주",
}
TICKET_HOSTS = (
    "ticket.interpark.com","tickets.interpark.com","nol.interpark.com",
    "nol.yanolja.com","ticketlink.co.kr","ticket.yes24.com",
    "ticket.melon.com","melonticket.com","ticket.11st.co.kr",
)
PERFORMANCE_ID = re.compile(r"PF\d+")

def clean(value):
    text = unicodedata.normalize("NFKC",unescape(str(value or ""))).lower()
    return re.sub(r"[^가-힣a-z0-9]", "", text)

def matches_name(text, artist):
    """2글자 한글 이름이 다른 사람 이름 일부일 때 일치하지 않도록 한다."""
    source = unicodedata.normalize("NFKC",unescape(str(text or "")))
    name = unicodedata.normalize("NFKC",str(artist).strip())
    if len(name)<2:
        return False
    if re.fullmatch(r"[가-힣]{2,3}",name):
        return bool(re.search(r"(?<![가-힣])"+re.escape(name)+r"(?![가-힣])",source))
    key = clean(name)
    return len(key)>=3 and key in clean(source)

def names_in_text(text, artists):
    """최대 8명, 대소문자/별칭 중복 정리."""
    found=[]
    taken=set()
    for name in artists:
        key=clean(name)
        if key not in taken and matches_name(text,name):
            found.append(name)
            taken.add(key)
    return found[:8]

def exclude(title, phrases):
    s=clean(title)
    return any(clean(x) in s for x in phrases if clean(x))

def iso_date(value):
    parts=re.sub(r"[^0-9]","",str(value or ""))
    if len(parts)<8:return ""
    try:return date(int(parts[:4]),int(parts[4:6]),int(parts[6:8])).isoformat()
    except ValueError:return ""

def fetch_xml(url, timeout=18):
    req=Request(url,headers={"User-Agent":"UriDuriConcerts/1.0", "Accept":"application/xml,text/xml"})
    with urlopen(req,timeout=timeout) as response:
        return ET.fromstring(response.read(1_500_000))

def error_check(root):
    if root.find(".//errmsg") is not None or root.find(".//error") is not None:
        raise RuntimeError("KOPIS API 오류 응답")

def list_candidates(key,artists,exclusions):
    today=datetime.now(KST).date()
    first=today-timedelta(days=30)
    last=today+timedelta(days=120)
    results=[]
    seen=set()
    pages=0
    capped=False
    while first<=last:
        end=min(first+timedelta(days=29),last)
        for p in range(1,11):
            params={
                "service":key,"stdate":first.strftime("%Y%m%d"),
                "eddate":end.strftime("%Y%m%d"),"cpage":p,"rows":100,"shcate":"CCCD"
            }
            root=fetch_xml(LIST_URL+"?"+urlencode(params))
            error_check(root)
            batch=root.findall(".//db")
            pages+=1
            for row in batch:
                field=lambda name:(row.findtext(name) or "").strip()
                pfid=field("mt20id")
                if not PERFORMANCE_ID.fullmatch(pfid) or pfid in seen:
                    continue
                seen.add(pfid)
                title=unescape(field("prfnm"))
                if exclude(title,exclusions):
                    continue
                # 공연명만 일치하는 항목은 상세 장르 확인 후 선별.
                names=names_in_text(title,artists)
                if not names:
                    continue
                start=iso_date(field("prfpdfrom"))
                finish=iso_date(field("prfpdto"))
                if not start or not finish or finish<today.isoformat():
                    continue
                region=field("area")
                prov=VENUE_PROVINCES.get(region,region)
                results.append({
                    "id":"kopis-"+pfid,"title":title,"start":start,"end":finish,
                    "province":prov,"city":prov+" 전체" if prov else "",
                    "place":field("fcltynm"),"posterUrl":field("poster"),
                    "titleArtists":names,
                })
            if len(batch)<100:
                break
            if p==10:
                capped=True
        first=end+timedelta(days=1)
    return results,{"pages":pages,"capped":capped}

def detail_info(key,pfid):
    if not PERFORMANCE_ID.fullmatch(pfid):
        raise ValueError("Invalid KOPIS ID")
    root=fetch_xml(DETAIL_URL+quote(pfid)+"?"+urlencode({"service":key}),timeout=14)
    error_check(root)
    db=root.find(".//db")
    if db is None:
        raise ValueError("KOPIS 상세 항목 누락")
    return db

def poster_url(raw):
    value=str(raw or "").strip()
    if value.startswith("http://") and "kopis.or.kr" in value:
        value="https://"+value[7:]
    return value if value.startswith("https://") else ""

def ticket_url(detail):
    for link in detail.findall(".//relates/relate"):
        addr=unescape(link.findtext("relateurl") or "").strip()
        label=unescape(link.findtext("relatenm") or "")
        try:
            parsed=urlsplit(addr)
            host=(parsed.hostname or "").lower()
            if parsed.scheme=="https" and any(host==h or host.endswith("."+h) for h in TICKET_HOSTS):
                if any(x in label.lower() for x in ("예매","티켓","yes24","인터파크","멜론","놀","ticket")):
                    return addr
        except ValueError:
            continue
    return ""

def make_concert(event,detail,artists,exclusions):
    genre=unescape(detail.findtext("genrenm") or "")
    if "대중음악" not in genre:
        return None
    title=unescape(detail.findtext("prfnm") or event.get("title") or "")
    if exclude(title,exclusions):
        return None
    cast=unescape(detail.findtext("prfcast") or "")
    title_artists=names_in_text(title,artists)
    cast_artists=names_in_text(cast,artists)
    selected=[]
    for name in title_artists+cast_artists:
        if name not in selected:
            selected.append(name)
    if not selected:
        return None
    pfid=str(event["id"])[6:]
    start=iso_date(detail.findtext("prfpdfrom") or "") or event.get("start","")
    end=iso_date(detail.findtext("prfpdto") or "") or event.get("end","")
    return {
        "id":event["id"],"title":title,"start":start,"end":end,
        "province":event.get("province",""),"city":event.get("city",""),
        "place":(detail.findtext("fcltynm") or event.get("place") or "").strip(),
        "posterUrl":poster_url(detail.findtext("poster") or event.get("posterUrl")),
        "artists":selected[:8],
        "castSummary":cast[:260],"genre":genre,
        "ticketUrl":ticket_url(detail),
        "sourceUrl":"https://kopis.or.kr/mob/db/pblprfrView.do?mt20Id="+quote(pfid),
        "sourceName":"KOPIS 공연예술통합전산망",
        "verifiedOn":datetime.now(KST).date().isoformat(),
        "selection":"KOPIS 대중음악 + 지정 주요 가수·그룹 확인",
    }

def fallback_from_events(artists, exclusions):
    path=ROOT/"events.json"
    if not path.exists():return []
    obj=json.loads(path.read_text(encoding="utf-8"))
    today=datetime.now(KST).date().isoformat()
    return [
        {"id":x["id"],"title":x["title"],"start":x["start"],"end":x["end"],
         "province":x.get("province",""),"city":x.get("city",""),
         "place":x.get("place",""),"posterUrl":x.get("posterUrl","")}
        for x in obj.get("events",[])
        if isinstance(x,dict) and str(x.get("id","")).startswith("kopis-PF")
           and x.get("end","")>=today
           and names_in_text(x.get("title",""),artists)
           and not exclude(x.get("title",""),exclusions)
    ]

def update():
    config=json.loads((ROOT/"concert_criteria.json").read_text(encoding="utf-8"))
    output=ROOT/"concerts.json"
    previous=json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"performances":[]}
    old={p["id"]:p for p in previous.get("performances",[]) if isinstance(p,dict) and p.get("id")}
    key=os.getenv("KOPIS_SERVICE_KEY","").strip()
    if not key:
        print("유명가수 콘서트: KOPIS_SERVICE_KEY 없음, 기존 데이터 유지")
        return
    now=datetime.now(KST)
    today=now.date().isoformat()
    candidates=fallback_from_events(config["featured_artists"],config["exclude_title_contains"])
    byid={c["id"]:c for c in candidates}
    listing_stats={"pages":0,"capped":False}
    listing_status="ok"
    try:
        extra,listing_stats=list_candidates(key,config["featured_artists"],config["exclude_title_contains"])
        for item in extra:byid[item["id"]]=item
    except Exception as exc:
        listing_status="error_"+type(exc).__name__
        # 인증 URL이 예외 문자열에 포함될 수 있으므로 메시지 출력 금지
        print("concerts: 장르별 목록 실패 ("+type(exc).__name__+")",file=sys.stderr)
    pool=sorted(byid.values(),key=lambda x:(x.get("start",""),x.get("title","")))
    cap=65
    found=[]
    checked=0;reused=0;excluded=0;failures=0
    for event in pool[:cap]:
        old_item=old.get(event["id"])
        if old_item and old_item.get("verifiedOn")==today and old_item.get("start")==event.get("start") and old_item.get("end")==event.get("end"):
            found.append(old_item)
            reused+=1
            continue
        checked+=1
        try:
            details=detail_info(key,event["id"][6:])
            record=make_concert(event,details,config["featured_artists"],config["exclude_title_contains"])
            if record and record["end"]>=today:
                found.append(record)
            else:
                excluded+=1
        except Exception as exc:
            failures+=1
            print("concerts: 상세조회 실패 "+event["id"]+" ("+type(exc).__name__+")",file=sys.stderr)
            if old_item and old_item.get("end","")>=today:
                found.append(old_item)
        time.sleep(0.04)
    selected={item["id"] for item in found}
    # 공식 목록 검색이 일시 실패하면 마지막 성공 기록 보존.
    if listing_status!="ok":
        for pfid,row in old.items():
            if pfid not in selected and row.get("end","")>=today:
                found.append(row)
                selected.add(pfid)
    found.sort(key=lambda x:(x.get("start",""),x.get("title","")))
    stat={
        "candidates":len(pool),"checked":checked,"selected":len(found),
        "reused":reused,"excluded":excluded,"failures":failures,"limited":len(pool)>cap,
        "genre_listing":listing_status,**listing_stats,
    }
    output.write_text(json.dumps({
        "version":1,"updated":now.strftime("%Y-%m-%d %H:%M KST"),
        "auto_update":True,
        "selection_note":"유명가수는 사이트 편집 목록 기준. KOPIS 대중음악 장르·공연명 또는 출연진 확인. 예매·출연 변경은 공식 출처 재확인.",
        "stats":stat,"performances":found
    },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("유명가수 콘서트 자동 갱신:",json.dumps(stat,ensure_ascii=False))

if __name__=="__main__":
    update()
