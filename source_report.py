"""Readable source rankings and measured access status; separate access from importance."""
import csv,io,json
from collections import Counter
from html import escape
from pathlib import Path
from poll_sources import load_registry
LABELS={'readable':'公开页面 / RSS 可读','document':'公开 PDF','partial_paid':'检测到订阅提示','partial_login':'检测到登录提示','login_required':'要求认证','payment_required':'要求支付','blocked':'拒绝 / 限流 / 验证','needs_browser':'需浏览器复查','error':'本次访问失败','unconfigured':'缺少具体公开入口'}
IMPORTANCE={5:'5 · 核心',4:'4 · 高',3:'3 · 中',2:'2 · 补充',1:'1 · 背景 / 工具'}

def report_rows(root,topic):
    registry=load_registry(root,topic)
    polls=sorted((Path(root)/'research'/'polls').glob(f'????-??-??-{topic}.json'))+sorted((Path(root)/'research'/'source-audits').glob(f'????-??-??-{topic}.json'))
    observed={}
    for path in polls:
        poll=json.loads(path.read_text())
        for r in poll['results']:
            if r.get('checked_at','') >= observed.get(r['source_id'],{}).get('checked_at',''):
                observed[r['source_id']]=r
    notes_path=Path(root)/'sources'/'access-notes.json'
    notes=json.loads(notes_path.read_text()) if notes_path.exists() else {}
    ranks={}
    for d in registry['domains']:
        for n,r in enumerate(d['top20'],1):ranks.setdefault(r['source_id'],[]).append((d['name'],n,r['reason']))
    rows=[]
    for s in registry['sources']:
        hits=ranks.get(s['id'],[]);rank=min((x[1] for x in hits),default=99)
        priority=5 if rank<=5 else 4 if rank<=15 else 3 if rank<=20 else 1 if s['mode']=='reference' else 2
        obs=observed.get(s['id'],{});note=notes.get(s['id'],{})
        rows.append({**s,'priority':priority,'importance':IMPORTANCE[priority],'domains':'、'.join(x[0] for x in hits) or '补充来源','ranks':hits,'status':obs.get('status','unchecked'),'status_label':LABELS.get(obs.get('status'),'尚未检查'),'checked_at':obs.get('checked_at',''),'detail':obs.get('detail',''),'access':note.get('access','仅核验公开入口；文章全文权限逐篇核实'),'access_evidence':note.get('evidence','')})
    return registry,rows

def render_sources(root,topic,out):
    out=Path(out);registry,rows=report_rows(root,topic);byid={r['id']:r for r in rows}
    headings=['名称','内容领域','重要性','本次抓取','登录 / 付费','检查时间','日常策略','地址','本次证据']
    values=lambda r:[r['name'],r['domains'],r['importance'],r['status_label'],r['access'],r['checked_at'],('待补入口' if r['mode']=='manual' else '每日轮询' if r['mode']!='reference' else '背景 / 工具，不作日更源'),r['url'],r['detail']]
    buf=io.StringIO();writer=csv.writer(buf);writer.writerow(headings)
    for r in sorted(rows,key=lambda r:(-r['priority'],r['name'])):writer.writerow(values(r))
    (out/'sources.csv').write_text('\ufeff'+buf.getvalue(),encoding='utf-8')
    md=['# RSI 信息源：重要性与访问实测','',registry['ranking_note'],'','重要性指 RSI 日常阅读与监测优先级，不是机构学术排名。可读仅指当前公开页面或 RSS，不保证已提取到文章列表或所有文章全文免费。','', '| '+' | '.join(headings)+' |','| '+' | '.join(['---']*len(headings))+' |']
    for r in sorted(rows,key=lambda r:(-r['priority'],r['name'])):md.append('| '+' | '.join(str(x).replace('|','/').replace('\n',' ') for x in values(r))+' |')
    (out/'sources.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    def row(r,rank=None):
        name=escape(r['name']);link=f'<a href="{escape(r["url"],quote=True)}">{name}</a>' if r['url'] else name
        group='readable' if r['status'] in ('readable','document') else 'limited' if r['status'] in ('partial_paid','partial_login','login_required','payment_required') else 'failed'
        return f'<tr data-access="{group}"><td>{str(rank)+". " if rank else ""}{link}<small>{escape(r["domains"])}</small></td><td>{escape(r["importance"])}</td><td>{escape(r["status_label"])}<small>{escape(r["detail"])}</small></td><td>{escape(r["access"])}</td><td>{"待补入口" if r["mode"]=="manual" else "每日轮询" if r["mode"]!="reference" else "背景 / 工具"}</td></tr>'
    def table(items):return '<div class="table-scroll"><table><thead><tr><th>信息源</th><th>重要性</th><th>本次读取</th><th>登录与付费</th><th>检查方式</th></tr></thead><tbody>'+''.join(items)+'</tbody></table></div>'
    domains=''.join(f'<details><summary>{escape(d["name"])} · Top 20</summary>'+table(row(byid[r['source_id']],n) for n,r in enumerate(d['top20'],1))+'</details>' for d in registry['domains'])
    counts=Counter(r['status_label'] for r in rows);summary='；'.join(f'{k} {v}' for k,v in counts.items())
    day=max((r['checked_at'] for r in rows),default='')[:10]
    html='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>信息源实测与 Top 20 · RSI 十条</title><style>body{margin:0;background:#f7f6f1;color:#202823;font:16px/1.7 system-ui,"PingFang SC",sans-serif}.wrap{max-width:1200px;margin:auto;padding:28px 24px}h1{font-size:32px}a{color:#315847;text-underline-offset:3px}p{max-width:72em}.notice{background:#e9eee6;padding:18px 22px}details{border-bottom:1px solid #d5d8cf}summary{cursor:pointer;padding:18px 0;font-weight:650}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:780px}th,td{text-align:left;vertical-align:top;padding:14px 12px;border-bottom:1px solid #d5d8cf;font-size:14px}th{white-space:nowrap}small{display:block;color:#59645d;font-size:13px;margin-top:6px}td:first-child{width:25%}td:nth-child(2){white-space:nowrap}input,select{font:inherit;padding:10px;min-height:44px;max-width:100%;margin:8px 8px 8px 0}input{width:26em}a:focus-visible,summary:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #315847;outline-offset:3px}[hidden]{display:none}nav{display:flex;gap:24px;flex-wrap:wrap}</style></head><body><main class="wrap"><nav><a href="index.html">回到每日十条</a><a href="sources.csv">下载完整表格 CSV</a><a href="sources.md">下载 Markdown 表</a></nav>'''
    html+=f'<h1>先看过这些来源，再挑十条</h1><p>六个领域，每个领域 20 个重点源，共 {len({r["source_id"] for d in registry["domains"] for r in d["top20"]})} 个去重入口。其余动态源也纳入每天轮询，不因找到十篇就结束。</p><p class="notice">实测日期 {day}。{escape(summary)}。<br>“可读”表示本次拿到公开页面、RSS 或文件；页面可读不等于已提取到文章列表，不代表每篇全文都能读取。403、限流和超时不等于必须付费。重要性与可访问性分开记录。</p><p>重要性：5 核心，4 高，3 中，2 补充，1 背景或工具。排名依据主题相关性、一手信息、持续产出和信息增量，是编辑选择。经典论文、书籍和管理工具仍在全表中，但不作为每天产出新文章的来源。</p>'
    html+=domains+f'<h2>完整访问表 · {len(rows)} 项</h2><label for="search">搜索名称或领域</label><br><input id="search" type="search" placeholder="例如 Anthropic、观点访谈"><label for="access">本次读取</label> <select id="access"><option value="">全部</option><option value="readable">可读入口</option><option value="limited">登录 / 订阅提示</option><option value="failed">受限 / 失败 / 未配置</option></select><p role="status" id="count"></p><section id="all">'+table(row(r) for r in sorted(rows,key=lambda r:(-r['priority'],r['name'])))+'</section>'
    html+='''<script>const q=document.getElementById('search'),a=document.getElementById('access'),rows=[...document.querySelectorAll('#all tbody tr')];function filter(){let n=0;rows.forEach(r=>{r.hidden=!(r.textContent.toLowerCase().includes(q.value.trim().toLowerCase())&&(!a.value||r.dataset.access===a.value));if(!r.hidden)n++});document.getElementById('count').textContent=`显示 ${n} 项`}q.addEventListener('input',filter);a.addEventListener('change',filter);filter();</script></main></body></html>'''
    (out/'sources.html').write_text(html,encoding='utf-8')
