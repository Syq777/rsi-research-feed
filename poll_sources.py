"""Poll the complete registered source pool; never stop after finding ten articles."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from build import atomic_write,json_text,plain,parse_feed

class Listing(HTMLParser):
    def __init__(self,base):
        super().__init__();self.base=base;self.hidden=0;self.text=[];self.links=[];self.anchor=None;self.label=[];self.title=[];self.in_title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style','template','noscript'):self.hidden+=1
        if tag=='title':self.in_title=True
        if tag=='a':self.anchor=urljoin(self.base,a.get('href',''));self.label=[]
    def handle_endtag(self,tag):
        if tag in ('script','style','template','noscript'):self.hidden=max(0,self.hidden-1)
        if tag=='title':self.in_title=False
        if tag=='a' and self.anchor:
            label=plain(' '.join(self.label),300)
            if len(label)>=10 and urlsplit(self.anchor).scheme in ('http','https'):
                self.links.append({'title':label,'url':self.anchor.split('#')[0]})
            self.anchor=None
    def handle_data(self,data):
        if self.hidden:return
        self.text.append(data)
        if self.in_title:self.title.append(data)
        if self.anchor:self.label.append(data)

def fingerprint(obj):return hashlib.sha256(json_text(obj).encode()).hexdigest()

def load_registry(root,topic):
    obj=json.loads((Path(root)/'sources'/f'{topic}.json').read_text())
    ids=[r['id'] for r in obj['sources']]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate source IDs')
    for d in obj['domains']:
        ranked=[r['source_id'] for r in d['top20']]
        if len(ranked)!=20 or len(set(ranked))!=20 or not set(ranked)<=set(ids):raise ValueError('each domain needs 20 distinct registered sources')
    return obj

def fetch_url(url):
    req=Request(url,headers={'User-Agent':'ResearchReadingList/2.0 (public source availability check)','Accept':'text/html,application/rss+xml,application/atom+xml,application/xml;q=0.9,*/*;q=0.5'})
    with urlopen(req,timeout=12) as response:
        data=response.read(8*1024*1024+1)
        if len(data)>8*1024*1024:raise ValueError('response exceeds 8 MiB; needs a narrower listing')
        return response.status,response.geturl(),response.headers.get('Content-Type',''),data

def inspect_source(source,fetch=fetch_url):
    row={'source_id':source['id'],'name':source['name'],'requested_url':source['poll_url'],'checked_at':datetime.now(timezone.utc).isoformat(),'links':[]}
    if not source['poll_url']:
        return {**row,'status':'unconfigured','detail':'无固定公开地址；需补充具体入口或人工线索'}
    try:
        code,final,ctype,data=fetch(source['poll_url'])
        row.update(http_status=code,final_url=final,content_type=ctype,sha256=hashlib.sha256(data).hexdigest())
        if source['mode']=='feed' or 'xml' in ctype:
            items,_=parse_feed(data,{'id':source['id'],'name':source['name'],'url':source['url'],'feed':source['poll_url'],'filter':False},[])
            if not items:raise ValueError('feed parsed but has no usable entries')
            return {**row,'status':'readable','detail':f'RSS/Atom 可解析，{len(items)} 条；原文访问仍需逐篇核对','links':[{'title':x['title'],'url':x['url'],'date':x['date']} for x in items]}
        if 'pdf' in ctype:
            return {**row,'status':'document','detail':'公开 PDF 可下载；固定背景资料，不是日更内容源'}
        parser=Listing(final);parser.feed(data.decode('utf-8','replace'))
        visible=plain(' '.join(parser.text),200000);title=plain(' '.join(parser.title),200)
        row.update(page_title=title,visible_chars=len(visible))
        unique={x['url']:x for x in parser.links}
        row['links']=list(unique.values())
        lower=visible.lower()
        if re.search(r'just a moment|access denied|security verification|verify you are human|captcha',title.lower()) or (len(visible)<3000 and re.search(r'verify you are human|enable javascript and cookies|checking your browser',lower)):
            return {**row,'status':'blocked','detail':'访问验证或反爬页面；未读到有效列表','links':[]}
        pay=re.search(r'subscribe to (continue|read|unlock)|paid subscribers|subscriber.only|订阅后阅读|付费阅读|订阅会员',lower)
        login=re.search(r'sign in to (continue|view|read)|log in to (continue|view|read)|登录后查看|登录后阅读',lower)
        if pay:return {**row,'status':'partial_paid','detail':'可见页出现付费/订阅提示；公开列表可作线索，不能保证全文可读'}
        if login:return {**row,'status':'partial_login','detail':'页面出现登录阅读提示；公开内容与登录后内容需区分'}
        if len(visible)<500 or not row['links']:
            return {**row,'status':'needs_browser','detail':'HTTP 可达，但未取得足够正文或内容链接；可能依赖 JavaScript，不能视作已读'}
        return {**row,'status':'readable','detail':f'公开页面可读，提取 {len(row["links"])} 个链接；不等于全部全文免费'}
    except HTTPError as exc:
        code=exc.code
        exc.close()
        return {**row,'http_status':code,'status':'login_required' if code==401 else 'payment_required' if code==402 else 'blocked' if code in (403,429) else 'error','detail':f'HTTP {code}；'+('服务器要求认证' if code==401 else '服务器返回支付要求' if code==402 else '拒绝或限制自动请求，未确认是否需要登录/付费' if code in (403,429) else '本次未取得内容')}
    except Exception as exc:
        return {**row,'status':'error','detail':f'{type(exc).__name__}: {str(exc)[:180]}'}

def run_poll(root,topic,day,audit_all=False,fetch=fetch_url):
    root=Path(root);registry=load_registry(root,topic)
    targets=[r for r in registry['sources'] if audit_all or r['mode'] in ('html','feed','manual')]
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(lambda row:inspect_source(row,fetch),targets))
    obj={'topic':topic,'date':day.isoformat(),'registry_sha256':fingerprint(registry),'scope':'all_entries' if audit_all else 'daily_sources','finished_at':datetime.now(timezone.utc).isoformat(),'expected_ids':[r['id'] for r in targets],'results':results}
    path=root/'research'/'polls'/f'{day.isoformat()}-{topic}.json';path.parent.mkdir(parents=True,exist_ok=True)
    atomic_write(path,json_text(obj).encode())
    if audit_all:
        audit=root/'research'/'source-audits'/path.name
        audit.parent.mkdir(parents=True,exist_ok=True)
        atomic_write(audit,json_text(obj).encode())
    return path,obj

def validate_coverage(root,topic,day,review):
    registry=load_registry(root,topic)
    path=Path(root)/'research'/'polls'/f'{day.isoformat()}-{topic}.json'
    poll=json.loads(path.read_text())
    active={r['id'] for r in registry['sources'] if r['mode'] in ('html','feed','manual')}
    seen=[r['source_id'] for r in poll['results']]
    if poll['date']!=day.isoformat() or poll['registry_sha256']!=fingerprint(registry) or not active<=set(seen) or len(seen)!=len(set(seen)):
        raise ValueError('poll is incomplete, duplicated, outdated, or for a different registry')
    if review.get('poll_sha256')!=fingerprint(poll):raise ValueError('review must refer to the current complete poll')
    decisions=review.get('source_reviews',[])
    reviewed=[r['source_id'] for r in decisions]
    if not active<=set(reviewed) or len(reviewed)!=len(set(reviewed)) or any(not r.get('note') or r.get('decision') not in ('candidates','no_relevant','unavailable') for r in decisions):
        raise ValueError('every daily source needs an explicit editorial review or access limitation')
    candidates=review.get('candidates',[])
    if len(candidates)<30 and not review.get('shortfall_reason'):raise ValueError('compare 30 candidates, or document the actual shortage after full coverage')
    if len({c.get('url') for c in candidates})!=len(candidates) or any(not c.get('url') or not c.get('reason') or c.get('decision') not in ('shortlist','exclude') for c in candidates):raise ValueError('each distinct compared candidate needs a decision and reason')
    if any(c.get('evidence_level') not in ('full_text','abstract','transcript') for c in candidates if c['decision']=='shortlist'):
        raise ValueError('shortlisted candidates require original content, not just a listing')
    return {'sources_attempted':sum(r['status']!='unconfigured' for r in poll['results']), 'sources_readable':sum(r['status']=='readable' for r in poll['results']), 'sources_total':len(poll['results']), 'candidates_compared':len(candidates),'candidates_read':sum(c.get('evidence_level')!='listing' for c in candidates),'poll':str(path.relative_to(root))}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--topic',default='rsi');p.add_argument('--date',required=True,type=date.fromisoformat);p.add_argument('--audit-all',action='store_true');a=p.parse_args()
    path,obj=run_poll(a.root,a.topic,a.date,a.audit_all)
    print(json.dumps({'path':str(path),'entries':len(obj['results']),'status':dict(Counter(r['status'] for r in obj['results']))},ensure_ascii=False))
if __name__=='__main__':main()
