"""Select and archive a dated reading brief from source-checked editorial notes.

RSS collection alone never creates a new issue or invents Chinese summaries.
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

KINDS = {'research': '研究观察', 'engineering': '工程实践', 'assessment': '评测解读',
         'perspective': '观点分析', 'podcast': '访谈播客', 'paper': '论文'}
DEFAULTS = {'size': 10, 'paper_target': .3, 'paper_max': .4, 'recent_days': 14,
            'max_age_days': 30, 'repeat_days': 7, 'max_per_source': 3,
            'min_score': 3, 'timezone': 'Asia/Shanghai'}


def url_key(url):
    from build import canonical_url
    p = urlsplit(canonical_url(url))
    return urlunsplit((p.scheme, p.netloc, p.path.rstrip('/') or '/', p.query, ''))


def checked_item(raw):
    from build import normalized_item, plain
    item = normalized_item(raw)
    for name, limit in [('headline', 100), ('summary', 260), ('why_read', 180), ('event_id', 160)]:
        value = raw.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f'brief item needs {name} (1–{limit} characters)')
        item[name] = plain(value, limit)
    if raw.get('kind') not in KINDS:
        raise ValueError('brief item needs a known kind')
    score = raw.get('score')
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not 1 <= score <= 5:
        raise ValueError('brief item needs a score from 1 to 5')
    item.update(kind=raw['kind'], score=score, reviewed_at=date.fromisoformat(raw['reviewed_at']).isoformat())
    return item


def policy_for(config):
    policy = {**DEFAULTS, **config.get('daily_brief', {})}
    if not 1 <= policy['size'] <= 20 or not 0 <= policy['paper_target'] <= policy['paper_max'] < .5:
        raise ValueError('brief size must be 1–20; paper target <= maximum < 50%')
    return policy


def select_items(candidates, day, policy, prior=()):
    used_urls, used_events = set(), set()
    for edition in prior:
        age = (day - date.fromisoformat(edition['date'])).days
        if 0 < age <= policy['repeat_days']:
            used_urls.update(url_key(row['url']) for row in edition['items'])
            used_events.update(row['event_id'] for row in edition['items'])
    eligible = []
    for raw in candidates:
        if not raw.get('headline'):
            continue  # Legacy curated notes remain in the archive, not in the brief.
        item = checked_item(raw)
        age = (day - date.fromisoformat(item['date'][:10])).days
        if (not 0 <= age <= policy['max_age_days'] or item['score'] < policy['min_score']
                or item['reviewed_at'] != day.isoformat() or url_key(item['url']) in used_urls
                or item['event_id'] in used_events):
            continue
        item['_rank'] = item['score'] - age * .035 - (.5 if age > policy['recent_days'] else 0)
        eligible.append(item)
    eligible.sort(key=lambda row: (-row['_rank'], row['url']))
    size = policy['size']
    quotas = {'paper': round(size * policy['paper_target']), 'engineering': round(size * .2),
              'assessment': round(size * .2), 'research': round(size * .2),
              'perspective': max(1, round(size * .1)), 'podcast': max(1, round(size * .1))}
    selected, sources, counts, events, urls = [], Counter(), Counter(), set(), set()
    def take(item):
        if (len(selected) >= size or sources[item['source_id']] >= policy['max_per_source']
                or item['event_id'] in events or url_key(item['url']) in urls):
            return False
        if item['kind'] == 'paper' and counts['paper'] >= math.floor(size * policy['paper_max']):
            return False
        selected.append(item); sources[item['source_id']] += 1; counts[item['kind']] += 1
        events.add(item['event_id']); urls.add(url_key(item['url'])); return True
    # A first pass keeps room for different kinds; unavailable slots are shared.
    for item in eligible:
        if counts[item['kind']] < quotas[item['kind']]:
            take(item)
    for item in eligible:
        if item['kind'] != 'paper':
            take(item)
    for item in eligible:
        take(item)
    # The ceiling applies to the actual issue length too, including sparse days.
    while selected and counts['paper'] / len(selected) > policy['paper_max']:
        worst = min((row for row in selected if row['kind'] == 'paper'), key=lambda row: row['_rank'])
        selected.remove(worst); counts['paper'] -= 1
    selected.sort(key=lambda row: (-row['_rank'], row['url']))
    # Never open with a wall of papers when a non-paper can introduce the subject.
    for i, item in enumerate(selected):
        if item['kind'] != 'paper':
            selected.insert(0, selected.pop(i)); break
    return [{k: v for k, v in row.items() if k != '_rank'} for row in selected]


def load_editions(root, topic):
    editions = []
    for path in sorted((Path(root) / 'editions' / topic).glob('????-??-??.json'), reverse=True):
        obj = json.loads(path.read_text(encoding='utf-8'))
        if obj.get('topic') != topic or obj.get('date') != path.stem:
            raise ValueError(f'invalid edition: {path.name}')
        date.fromisoformat(obj['date'])
        obj['items'] = [checked_item(item) for item in obj['items']]
        editions.append(obj)
    return editions


def make_edition(root, day, lead):
    from build import read_json, load_config, atomic_write, json_text, build_lock
    root = Path(root).resolve()
    topic = read_json(root / 'site.json')['topic']
    config = load_config(root, topic)
    if not config.get('daily_brief'):
        raise ValueError('enable daily_brief in the topic configuration first')
    if not lead.strip() or len(lead) > 240:
        raise ValueError('write a short issue introduction (1–240 characters)')
    with build_lock(root):
        previous = load_editions(root, topic)
        chosen = select_items(read_json(root / 'editorial' / f'{topic}.json'), day, policy_for(config), previous)
        if not chosen:
            raise ValueError('no fresh, reviewed mixed selection; previous edition retained')
        edition = {'topic': topic, 'date': day.isoformat(), 'timezone': policy_for(config)['timezone'],
                   'lead': lead, 'items': chosen}
        path = root / 'editions' / topic / f'{day.isoformat()}.json'
        atomic_write(path, json_text(edition).encode())
    return path, edition


def feed_items(editions):
    seen, items = set(), []
    for edition in editions:
        for row in edition['items']:
            key = url_key(row['url'])
            if key in seen:
                continue
            seen.add(key)
            items.append({**row, 'title': row['headline'],
                          'date': datetime.fromisoformat(edition['date']).replace(
                              tzinfo=ZoneInfo(edition.get('timezone', DEFAULTS['timezone']))
                          ).astimezone(timezone.utc).isoformat(),
                          'summary': f"{row['summary']}\n为什么读：{row['why_read']}\n原文发布：{row['date'][:10]} · {row['source']}"})
    return items


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--date', required=True, type=date.fromisoformat)
    p.add_argument('--lead', required=True, help='source-grounded Chinese introduction for this issue')
    args = p.parse_args()
    try:
        path, edition = make_edition(args.root, args.date, args.lead)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        p.exit(1, f'Brief not published: {exc}\n')
    print(json.dumps({'edition': str(path), 'items': len(edition['items']),
                      'mix': dict(Counter(row['kind'] for row in edition['items']))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
