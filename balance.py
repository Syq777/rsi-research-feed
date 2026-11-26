"""Rolling reading diversity and evidence-based weekly editorial focus."""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path

DOMAINS={'methods':'研究方法','engineering':'工程与开源','science':'自动科研','safety':'评测安全','industry':'产业动态','perspectives':'观点访谈'}
LEGACY={'paper':'methods','research':'science','engineering':'engineering','assessment':'safety','perspective':'perspectives','podcast':'perspectives'}

def week_id(day):
    year,week,_=day.isocalendar();return f'{year}-W{week:02d}'

def domain_for(item):return item.get('domain') or LEGACY.get(item.get('kind'),'methods')

def history_stats(editions,day,include_today=False):
    kinds,sources,domains,month_domains=Counter(),Counter(),Counter(),Counter()
    weeks={};issues=0
    for edition in editions:
        published=date.fromisoformat(edition['date']);age=(day-published).days
        if not (0 if include_today else 1)<=age<=(27 if include_today else 28):continue
        weekly=weeks.setdefault(week_id(published),Counter())
        for item in edition['items']:
            domain=domain_for(item);weekly[domain]+=1;month_domains[domain]+=1
            if age<=(6 if include_today else 7):
                kinds[item['kind']]+=1;domains[domain]+=1;sources[item['source_id']]+=1
        if age<=(6 if include_today else 7):issues+=1
    return {'issues_7d':issues,'items_7d':sum(kinds.values()),'kinds_7d':dict(kinds),'domains_7d':dict(domains),'sources_7d':dict(sources),'domains_28d':dict(month_domains),'weeks':{k:dict(v) for k,v in sorted(weeks.items())}}

def load_plan(root,topic,day,required=False):
    path=Path(root)/'weeks'/f'{week_id(day)}-{topic}.json'
    if not path.exists():
        if required:raise ValueError(f'write this week\'s evidence-based focus first: {path}')
        return {'week':week_id(day),'focus_domains':[],'reason':'按候选质量与近期阅读分布选择。'}
    plan=json.loads(path.read_text())
    focus=plan.get('focus_domains',[])
    if plan.get('week')!=week_id(day) or not isinstance(focus,list) or len(focus)>2 or len(focus)!=len(set(focus)) or not set(focus)<=set(DOMAINS) or not plan.get('reason'):
        raise ValueError('weekly plan needs the current ISO week, at most two distinct domains, and an evidence-based reason')
    return plan

def adjustment(item,selected,history,policy):
    domain=domain_for(item);n=max(1,history['items_7d']);m=max(1,len(selected))
    kinds=Counter(r['kind'] for r in selected);domains=Counter(domain_for(r) for r in selected);sources=Counter(r['source_id'] for r in selected)
    value=.35 if domain in policy.get('focus_domains',[]) else 0
    value-=.35*history['kinds_7d'].get(item['kind'],0)/n
    value-=.45*history['domains_7d'].get(domain,0)/n
    value-=.25*history['sources_7d'].get(item['source_id'],0)/n
    month=history['domains_28d'];value-=.15*month.get(domain,0)/max(1,sum(month.values()))
    value-=.25*kinds[item['kind']]/m+.3*domains[domain]/m+.12*sources[item['source_id']]
    if item['kind']=='paper':
        share=(history['kinds_7d'].get('paper',0)+kinds['paper'])/max(1,history['items_7d']+len(selected))
        value-=.8*max(0,share-policy['paper_target'])
    # Diversity breaks close calls; it cannot rescue clearly weak material.
    return max(-.65,min(.65,value))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--date',type=date.fromisoformat,required=True);a=p.parse_args()
    from digest import load_editions
    topic=json.loads((a.root/'site.json').read_text())['topic']
    print(json.dumps({'as_of':a.date.isoformat(),'domain_labels':DOMAINS,'history':history_stats(load_editions(a.root,topic),a.date,True),'current_plan':load_plan(a.root,topic,a.date)},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
