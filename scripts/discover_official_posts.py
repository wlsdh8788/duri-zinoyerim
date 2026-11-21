#!/usr/bin/env python3
"""우리두리 공식 행사 게시물 탐색 (3차).
NAVER API HUB 키가 있으면 웹문서를 검색하고, 없으면 등록된 공식 홈페이지를 검사.
공식 페이지의 행사명·연도와 이미지의 포스터 표시가 맞을 때만 교체한다.
"""
import json, os, re, socket, sys
from collections import deque
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlencode
from urllib.request import Request, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parents[1]
SEARCH_URL='https://naverapihub.apigw.ntruss.com/search/v1/webkr'
POSTER=re.compile(r'포스터|홍보\s*(?:물|이미지)|poster',re.I)
NOT_POSTER=re.compile(r'logo|favicon|sprite|icon|로고|banner-ad',re.I)
YEAR=re.compile(r'(?<!\d)20\d{2}(?!\d)')
IMAGE=re.compile(r'\.(?:png|jpe?g|webp)(?:\?|$)',re.I)

def norm(x):
    x=unescape(re.sub(r'<[^>]*>','',str(x or ''))).lower()
    x=re.sub(r'20\d{2}(?:년)?|제\d+회','',x)
    return re.sub(r'[^가-힣a-z0-9]','',x)

def safe(url):
    try:
        p=urlsplit(url)
        h=(p.hostname or '').lower()
        if p.scheme!='https' or not h or p.username or p.password or p.port not in (None,443):
            return False
        if not re.fullmatch('[a-z0-9.-]+',h) or h.endswith(('.local','.internal')) or h=='localhost':
            return False
        try:
            socket.inet_pton(socket.AF_INET,h)
            return False
        except OSError:
            return True
    except (ValueError,TypeError):
        return False

def official(url,hosts):
    if not safe(url): return False
    h=urlsplit(url).hostname.lower()
    return h.endswith(('.go.kr','.gov.kr')) or any(h==x or h.endswith('.'+x) for x in hosts)

class StrictRedirect(HTTPRedirectHandler):
    def __init__(self,hosts):
        super().__init__()
        self.hosts=hosts
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not official(newurl,self.hosts): raise ValueError('untrusted redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings=[]; self.words=[]; self.images=[]; self.links=[]; self.meta={}
        self.isheading=False; self.active=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('title','h1','h2','h3'): self.isheading=True
        if tag=='meta':
            k=(a.get('property') or a.get('name') or '').lower()
            if k and a.get('content'): self.meta[k]=a['content']
        if tag=='img':
            desc=' '.join(str(a.get(k,'')) for k in ('alt','title','class','id'))
            for u in (a.get('data-original'),a.get('data-src'),a.get('src')):
                if u: self.images.append((u,desc));break
            if a.get('srcset'):
                self.images.append((a['srcset'].split(',')[0].strip().split()[0],desc))
        if tag=='source' and a.get('srcset'):
            self.images.append((a['srcset'].split(',')[0].strip().split()[0],str(a.get('title',''))))
        if a.get('style'):
            for u in re.findall(r'url\(["\x27]?([^"\x27)]+)',a['style'],re.I):
                self.images.append((u,str(a.get('class',''))))
        if tag=='a': self.active=[a.get('href',''),'']
    def handle_endtag(self,tag):
        if tag in ('title','h1','h2','h3'): self.isheading=False
        if tag=='a' and self.active:
            self.links.append(tuple(self.active));self.active=None
    def handle_data(self,data):
        t=data.strip()
        if not t:return
        if len(self.words)<1500:self.words.append(t)
        if self.isheading:self.headings.append(t)
        if self.active:self.active[1]+=' '+t

def matches(page,event,hint=''):
    name=norm(event.get('title'))
    yr=str(event.get('start',''))[:4]
    title=' '.join([page.meta.get('og:title',''),*page.headings[:12],hint])
    body=' '.join(page.words[:600])
    yrs=set(YEAR.findall(title))
    return (len(name)>=5 and re.fullmatch(r'20\d{2}',yr) is not None
            and name in norm(title) and yr in title+' '+body and (not yrs or yr in yrs))

def poster_for(page,url,event):
    yr=str(event.get('start',''))[:4]
    items=list(page.images[:120])
    for key in ('og:image','twitter:image'):
        if page.meta.get(key):items.insert(0,(page.meta[key],key))
    items += [(u,t) for u,t in page.links[:100] if POSTER.search(t) and IMAGE.search(u)]
    found={}
    for src,label in items:
        image=urljoin(url,unescape(src))
        if not safe(image):continue
        # 수집처 외부의 임의 이미지 링크는 자동 등록하지 않음.
        if urlsplit(image).hostname.lower()!=urlsplit(url).hostname.lower():continue
        descr=label+' '+urlsplit(image).path
        years=set(YEAR.findall(descr))
        if NOT_POSTER.search(descr) or not POSTER.search(descr):continue
        if years and years!={yr}:continue
        score=2+(3 if yr in years else 0)+(1 if norm(event.get('title')) in norm(descr) else 0)
        found[image]=max(score,found.get(image,0))
    candidates=sorted(found.items(),key=lambda x:-x[1])
    if not candidates:return '',False
    if len(candidates)>1 and candidates[0][1]==candidates[1][1]:return '',True
    return candidates[0][0],False

def fetch_official(url,hosts):
    request=Request(url,headers={'User-Agent':'UriDuriOfficialPoster/3.0','Accept':'text/html'})
    with build_opener(StrictRedirect(hosts)).open(request,timeout=10) as resp:
        if not official(resp.geturl(),hosts):raise ValueError('outside official domain')
        if 'html' not in resp.headers.get('Content-Type','').lower():return None
        raw=resp.read(1800000)
        final=resp.geturl()
    page=Page();page.feed(raw.decode('utf-8',errors='replace'))
    return page,final

def search(event,client_id,client_secret):
    if not (client_id and client_secret):return []
    q=f"{event.get('title','')} {str(event.get('start',''))[:4]} 포스터 공식"
    url=SEARCH_URL+'?'+urlencode({'query':q,'display':5,'start':1,'format':'json'})
    request=Request(url,headers={'X-NCP-APIGW-API-KEY-ID':client_id,
                                 'X-NCP-APIGW-API-KEY':client_secret})
    with build_opener().open(request,timeout=10) as resp:
        data=json.loads(resp.read(500000).decode('utf-8'))
    return [(unescape(x.get('link','')),unescape(re.sub('<[^>]*>','',x.get('title',''))))
            for x in data.get('items',[]) if isinstance(x,dict)]

def discover(event,starts,hosts,client_id,client_secret,stat):
    queue=deque((x,'') for x in starts)
    try:
        results=search(event,client_id,client_secret)
        queue.extend(results)
        if client_id and client_secret:stat['search_requests']+=1
    except (OSError,ValueError,HTTPError,URLError,TimeoutError):
        stat['search_errors']+=1
    seen=set()
    while queue and len(seen)<7:
        url,hint=queue.popleft()
        if not official(url,hosts) or url in seen:continue
        seen.add(url)
        try:
            result=fetch_official(url,hosts)
            if not result:continue
            page,final=result
            stat['pages_read']+=1
        except (OSError,ValueError,HTTPError,URLError,TimeoutError):
            stat['page_errors']+=1
            continue
        if matches(page,event,hint):
            image,ambiguous=poster_for(page,final,event)
            if ambiguous:stat['ambiguous']+=1
            if image:return image,final
        core=norm(event.get('title'))
        for link,label in page.links[:180]:
            nxt=urljoin(final,unescape(link))
            if not official(nxt,hosts) or nxt in seen or IMAGE.search(nxt):continue
            if core in norm(label+' '+nxt) and len(queue)<20:
                queue.append((nxt,label))
    return '',''

def main():
    root=ROOT/'events.json'
    cfg=json.loads((ROOT/'official_poster_sources.json').read_text(encoding='utf-8'))
    data=json.loads(root.read_text(encoding='utf-8'))
    hosts=[str(h).lower() for h in cfg.get('official_hosts',[]) if re.fullmatch('[a-z0-9.-]+',str(h).lower())]
    srcs=cfg.get('sources',[])
    client_id=os.getenv('NAVER_APIHUB_CLIENT_ID','').strip()
    client_secret=os.getenv('NAVER_APIHUB_CLIENT_SECRET','').strip()
    today=datetime.now(timezone(timedelta(hours=9))).date()
    stat={'eligible':0,'pages_read':0,'search_requests':0,'search_errors':0,
          'page_errors':0,'ambiguous':0,'posters_added':0,'unchanged':0,
          'search_enabled':bool(client_id and client_secret)}
    events=[]
    for e in data.get('events',[]):
        if not isinstance(e,dict) or e.get('category') not in ('축제','체험','야경'):continue
        if e.get('posterConfidence') in ('year-matched','official-verified','official-post-verified'):continue
        try:
            start=date.fromisoformat(e['start']);end=date.fromisoformat(e['end'])
        except (KeyError,TypeError,ValueError):continue
        if end<today or start>today+timedelta(days=100):continue
        events.append(e)
    def has_known(e):
        return any(s.get('title_contains') and norm(s['title_contains']) in norm(e.get('title'))
                   and str(s.get('year'))==str(e.get('start',''))[:4] for s in srcs)
    events.sort(key=lambda e:(not has_known(e),e.get('start','')))
    for e in events[:30]:
        stat['eligible']+=1
        links=[e[k] for k in ('officialUrl','homepage','sourceUrl') if isinstance(e.get(k),str)]
        for s in srcs:
            if not s.get('title_contains') or norm(s['title_contains']) not in norm(e.get('title')):continue
            if str(s.get('year'))!=str(e.get('start',''))[:4]:continue
            if s.get('city') and norm(s['city']) not in norm(e.get('city','')):continue
            links.insert(0,s.get('url',''))
        img,source=discover(e,links,hosts,client_id,client_secret,stat)
        if img and img!=e.get('posterUrl'):
            e['posterUrl']=img
            e['posterSource']=source
            e['posterConfidence']='official-post-verified'
            e['imageType']='공식 게시물 행사명·연도·포스터 표기 일치'
            stat['posters_added']+=1
        else:stat['unchanged']+=1
    data['official_post_discovery']=stat
    root.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('공식 게시물 포스터 3차 확인:',json.dumps(stat,ensure_ascii=False))
    if not (client_id and client_secret):
        print('검색키 미연결: 등록된 공식 사이트 내부 탐색만 실행')

if __name__=='__main__':main()
