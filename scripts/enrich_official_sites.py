#!/usr/bin/env python3
"""우리두리 공식 행사 사이트 포스터 보강 (2차).

공식 홈페이지에 공개된 이미지만 확인한다. 행사명/연도/포스터 단서가
확실하지 않으면 기존 이미지를 보존한다.
"""
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone, date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
POSTER = re.compile(r'포스터|홍보\s*(?:이미지|물)|poster', re.I)
YEAR = re.compile(r'(?<!\d)20\d{2}(?!\d)')
BAD = re.compile(r'logo|favicon|icon|sprite|프로필|profile|social|로고', re.I)

def norm(s):
    s = unescape(str(s or '')).lower()
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'20\d{2}(?:년)?|제\d+회', '', s)
    return re.sub(r'[^가-힣a-z0-9]', '', s)

def url_ok(u):
    p = urlsplit(str(u or ''))
    return bool(p.scheme == 'https' and p.hostname and not p.username and not p.password
                and p.hostname.lower() not in ('localhost',)
                and not p.hostname.lower().endswith(('.local', '.internal')))

def official(u, hosts):
    if not url_ok(u):
        return False
    h = urlsplit(u).hostname.lower()
    return h.endswith(('.go.kr', '.gov.kr')) or any(
        h == x.lower() or h.endswith('.' + x.lower()) for x in hosts)

class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings, self.texts, self.images, self.metas = [], [], [], {}
        self.heading = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('title', 'h1', 'h2'):
            self.heading = True
        if tag == 'meta':
            k = (a.get('property') or a.get('name') or '').lower()
            if k and a.get('content'):
                self.metas[k] = a['content']
        if tag == 'img':
            u = a.get('data-src') or a.get('data-original') or a.get('src') or ''
            self.images.append((u, ' '.join([a.get('alt', ''), a.get('title', ''), a.get('class', '')])))

    def handle_endtag(self, tag):
        if tag in ('title', 'h1', 'h2'):
            self.heading = False

    def handle_data(self, text):
        s = text.strip()
        if s:
            self.texts.append(s)
            if self.heading:
                self.headings.append(s)

def select_image(page_bytes, page_url, event):
    p = Images()
    p.feed(page_bytes.decode('utf-8', errors='replace'))
    title = str(event.get('title', ''))
    year = str(event.get('start', ''))[:4]
    page_title = ' '.join([p.metas.get('og:title', ''), p.metas.get('twitter:title', ''), *p.headings[:8]])
    page_text = ' '.join([page_title, p.metas.get('og:description', ''), *p.texts[:250]])
    target = norm(title)
    if len(target) < 5 or target not in norm(page_text[:3500]):
        return None
    if year not in page_text:
        return None
    candidates = []
    if p.metas.get('og:image'):
        candidates.append((p.metas['og:image'], 'og:image'))
    candidates += p.images[:120]
    found = []
    for u, label in candidates:
        candidate = urljoin(page_url, unescape(u))
        if not url_ok(candidate):
            continue
        desc = label + ' ' + urlsplit(candidate).path
        years = set(YEAR.findall(desc))
        if years and years != {year}:
            continue
        if BAD.search(desc) or not POSTER.search(desc):
            continue
        score = (3 if year in years else 0) + (2 if target in norm(desc) else 0)
        found.append((score, candidate))
    if not found:
        return None
    found.sort(reverse=True)
    # 같은 신뢰도의 후보가 둘이면 임의 선택하지 않는다.
    if len(found) > 1 and found[0][0] == found[1][0]:
        return None
    return found[0][1]

def main():
    file = ROOT / 'events.json'
    cfgfile = ROOT / 'official_poster_sources.json'
    data = json.loads(file.read_text(encoding='utf-8'))
    cfg = json.loads(cfgfile.read_text(encoding='utf-8')) if cfgfile.exists() else {}
    allowed = cfg.get('official_hosts', [])
    sources = cfg.get('sources', [])
    stats = {'candidate_events': 0, 'pages_checked': 0, 'official_posters_added': 0, 'unchanged': 0, 'request_failures': 0}
    today = datetime.now(KST).date()
    for event in data.get('events', []):
        if not isinstance(event, dict):
            continue
        if event.get('category') not in ('축제', '체험', '야경'):
            continue
        if event.get('posterConfidence') in ('year-matched', 'official-verified'):
            continue
        try:
            start = date.fromisoformat(event['start'])
            end = date.fromisoformat(event['end'])
        except (KeyError, ValueError, TypeError):
            continue
        if end < today or start > today + timedelta(days=120):
            continue
        stats['candidate_events'] += 1
        addresses = []
        for key in ('officialUrl', 'homepage', 'sourceUrl', 'url'):
            if event.get(key):
                addresses.append(event[key])
        for entry in sources:
            if not norm(entry.get('title_contains')) or norm(entry.get('title_contains')) not in norm(event.get('title')):
                continue
            if str(entry.get('year')) != str(start.year):
                continue
            if entry.get('city') and norm(entry['city']) not in norm(event.get('city', '')):
                continue
            addresses.append(entry.get('url', ''))
        visited = set()
        replaced = False
        for addr in addresses[:5]:
            if not official(addr, allowed) or addr in visited:
                continue
            visited.add(addr)
            try:
                req = Request(addr, headers={'User-Agent': 'Mozilla/5.0 UriDuri/2.0', 'Accept': 'text/html'})
                with urlopen(req, timeout=12) as response:
                    actual = response.geturl()
                    if not official(actual, allowed) or 'html' not in response.headers.get('Content-Type', ''):
                        continue
                    html = response.read(2_000_000)
                stats['pages_checked'] += 1
                image = select_image(html, actual, event)
                if not image:
                    continue
                if image != event.get('posterUrl'):
                    event['posterUrl'] = image
                    event['posterSource'] = actual
                    event['posterConfidence'] = 'official-verified'
                    event['imageType'] = '공식 행사 사이트 · 행사명/연도/포스터 이미지 표시 확인'
                    stats['official_posters_added'] += 1
                replaced = True
                break
            except (HTTPError, URLError, OSError, ValueError, TimeoutError) as ex:
                stats['request_failures'] += 1
                print('official-site: 접속 실패 ' + type(ex).__name__, file=sys.stderr)
            time.sleep(.1)
        if not replaced:
            stats['unchanged'] += 1
    data['official_site_poster_scan'] = stats
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('공식 사이트 포스터 2차 확인:', json.dumps(stats, ensure_ascii=False))
    print('참고: 포스터 설명/연도가 불확실하면 기존 이미지를 유지함')

if __name__ == '__main__':
    main()
