"""Render a portable, buildless research feed using only Python's standard library."""

from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlsplit


def _text(value):
    return escape(str(value or ""), quote=True)


def _web_url(value):
    url = str(value or "").strip()
    if not url or any(ord(char) < 32 for char in url) or "\\" in url:
        return ""
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() in {"https", "http"} and parts.hostname and not parts.username and not parts.password:
            return url
    except ValueError:
        pass
    return ""


def _external(label, url):
    url = _web_url(url)
    if not url:
        return _text(label)
    return f'<a href="{_text(url)}" target="_blank" rel="noopener noreferrer">{_text(label)}<span class="ext" aria-hidden="true">↗</span></a>'


def _date(value):
    value = str(value or "")
    try:
        day = datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return ""
    return f'<time datetime="{day.isoformat()}">{day:%Y.%m.%d}</time>'


STYLE = """
:root{color-scheme:light;--page:#f7f6f1;--paper:#fcfbf7;--ink:#202823;--muted:#59645d;--line:#ced2c7;--strong:#9da79b;--accent:#9b3f22;--pale:#e9ecdf;--serif:"Source Han Serif SC","Noto Serif CJK SC","Songti SC","STSong",Georgia,serif;--sans:Inter,"Noto Sans CJK SC","PingFang SC","Microsoft YaHei",sans-serif;--mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Consolas,monospace}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:1rem}body{margin:0;background:var(--page);color:var(--ink);font:15px/1.65 var(--sans);-webkit-font-smoothing:antialiased}a{color:inherit;text-decoration:none}a:hover{text-decoration:underline;text-underline-offset:.2em}button,input,select{font:inherit;color:inherit}button,select{cursor:pointer}button{border:0}h1,h2,h3,p{margin:0}a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid #287b66;outline-offset:3px}button:disabled{cursor:default}::selection{background:#d9e4bc}
.wrap{width:min(1180px,calc(100% - 72px));margin-inline:auto}.skip{position:absolute;left:1rem;top:-5rem;padding:.5rem 1rem;background:white;z-index:10}.skip:focus{top:1rem}
header{border-bottom:1px solid var(--line)}.top{min-height:70px;display:flex;align-items:center;justify-content:space-between;gap:24px}.brand,.rss{display:inline-flex;align-items:center;justify-content:center;gap:10px;font-weight:700}.brand{font-size:16px;letter-spacing:.04em}.mark{display:inline-block;position:relative;width:26px;height:26px;background:var(--accent);border-radius:5px;flex:none}.mark:before,.mark:after{content:"";position:absolute;left:5px;bottom:5px;border:solid #fff7e8;border-width:2px 2px 0 0;border-radius:0 100% 0 0;width:12px;height:12px}.mark:after{width:7px;height:7px}.mark i{width:3px;height:3px;position:absolute;bottom:5px;left:5px;background:#fff7e8;border-radius:50%}
nav{display:flex;align-items:center;gap:26px}.navlink{font-size:13px;color:var(--muted)}.rss,.action{font-size:13px;font-weight:650;padding:8px 15px;border:1px solid var(--ink);border-radius:4px;background:var(--ink);color:white;text-decoration:none}.rss:hover,.action:hover{background:#3f5144;text-decoration:none}.rss b{font:18px/1 var(--mono)}.mast{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:end;gap:24px;padding:65px 0 42px;border-bottom:2px solid var(--ink)}
h1{font:700 clamp(42px,5.7vw,76px)/1.15 var(--serif);letter-spacing:-.045em;overflow-wrap:anywhere}.intro{max-width:720px;margin-top:17px;color:var(--muted);line-height:1.8}.stats{display:flex;gap:25px;padding-bottom:4px}.stat{border-left:1px solid var(--line);padding-left:18px}.stat dt{color:var(--muted);font-size:12px}.stat dd{margin:1px 0 0;font:500 30px/1.25 var(--mono);letter-spacing:-.09em}
.section{margin-top:36px}.sectionhead{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.sectionhead h2,.status-heading{font:700 clamp(23px,2.5vw,31px)/1.35 var(--serif);letter-spacing:-.025em}.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.search,.select{display:block;height:39px;border:1px solid var(--strong);border-radius:4px;background:var(--paper);padding:6px 12px;font-size:13px}.search{width:min(240px,100%)}.select{max-width:100%}.js-only{display:none!important}.enhanced .js-only{display:revert!important}.enhanced .controls.js-only{display:flex!important}
.articlegrid{display:grid;grid-template-columns:minmax(0,1fr) minmax(210px,27%);gap:clamp(30px,5vw,75px);align-items:start}.stories,.filterlist,.status-list{list-style:none;margin:0;padding:0}.story{border-top:1px solid var(--line);padding:20px 0 22px}.story:first-child{border-top:2px solid var(--ink)}.meta{display:flex;gap:11px;align-items:center;font-size:12px;color:var(--accent);font-weight:650}.meta time{font:12px/1.5 var(--mono);color:var(--muted)}.meta time:after{content:"";display:inline-block;margin-left:11px;width:10px;border-top:1px solid var(--strong);vertical-align:middle}
.story h3{font:650 clamp(20px,2.15vw,29px)/1.46 var(--serif);letter-spacing:-.02em;margin:6px 0 4px;overflow-wrap:anywhere}.story p,.resource p{color:var(--muted);overflow-wrap:anywhere}.story p{font-size:14px;line-height:1.85}.ext{font:normal .67em/1 var(--sans);color:var(--accent);margin-left:.33em;vertical-align:.17em}.story a:hover,.resource a:hover{color:var(--accent)}.sidebar{border:1px solid var(--line);border-top:3px solid #465a43;border-radius:2px;background:var(--pale);padding:19px 18px}.sidebar h3{font:700 16px/1.5 var(--serif);margin-bottom:10px}.filterlist li+li{border-top:1px solid #d2d8c9}.sourcebtn{font-size:13px;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 0;width:100%;text-align:left;border:0;background:transparent}.sourcebtn:hover,.sourcebtn[aria-pressed=true]{color:var(--accent)}.sourcebtn[aria-pressed=true]{font-weight:700}.count{font:12px/1.6 var(--mono);color:var(--muted);white-space:nowrap}.sidebar p,.notice{color:var(--muted);font-size:13px}
.archive{margin-top:42px;padding-top:25px;border-top:2px solid var(--ink)}.archive .sectionhead{align-items:start}.catalog-tools{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin:5px 0 12px}.subtle-link{font-size:13px;color:var(--accent);text-decoration:underline;text-underline-offset:.25em}.group{border-top:1px solid var(--line)}.group:last-child{border-bottom:1px solid var(--line)}summary{cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}.group>summary,.status-box>summary{display:flex;align-items:center;gap:12px;padding:14px 0}.group>summary:before,.status-box>summary:before{content:"+";color:var(--accent);font:18px/1 var(--mono);width:16px;text-align:center}.group[open]>summary:before,.status-box[open]>summary:before{content:"−"}.group-label{font-weight:650}.group .count{margin-left:auto}.resources{list-style:none;padding:0 0 15px 28px;margin:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 24px}.resource{padding:11px 0;border-top:1px dotted var(--line);overflow-wrap:anywhere}.resource h3{font-size:15px;line-height:1.45}.resource p{font-size:13px;line-height:1.65;margin-top:2px}.topic{display:block;color:var(--accent);font-size:11px;margin-bottom:2px}
.status-box{margin:32px 0;border-top:1px solid var(--strong);border-bottom:1px solid var(--line)}.status-heading{font-size:19px}.status-row{display:grid;grid-template-columns:minmax(140px,1fr) minmax(90px,.45fr) minmax(0,2.3fr);gap:16px;border-top:1px dotted var(--line);padding:11px 0;font-size:13px;overflow-wrap:anywhere}.status-row b{font-weight:600}.status-row span:last-child{color:var(--muted)}.empty{padding:24px 0;color:var(--muted);font-size:14px}.sr-only{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
footer{margin-top:24px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}.foot{display:flex;justify-content:space-between;align-items:baseline;gap:14px;padding-block:22px}.foot p{overflow-wrap:anywhere}.foot-links{display:flex;gap:18px}.foot-links a{white-space:nowrap}
dialog{background:var(--paper);color:var(--ink);border:1px solid var(--strong);border-radius:8px;max-width:min(460px,calc(100% - 28px));width:100%;padding:25px;box-shadow:0 12px 60px #16201b32}dialog::backdrop{background:#18241ccc}dialog h2{font:700 24px/1.3 var(--serif)}dialog p{margin:12px 0;color:var(--muted);font-size:14px}.dialogtop{display:flex;align-items:center;justify-content:space-between;gap:14px}.close{font:22px var(--sans);background:transparent;padding:2px 8px}.url{width:100%;padding:9px;border:1px solid var(--strong);background:white;font:13px var(--mono);border-radius:3px}.dialog-actions{display:flex;align-items:center;gap:16px;margin-top:14px}[hidden]{display:none!important}.enhanced .js-only[hidden]{display:none!important}
@media(max-width:800px){.wrap{width:calc(100% - 42px)}.mast{padding:42px 0 32px;grid-template-columns:1fr}.stats{gap:20px}.stat:first-child{border:0;padding-left:0}.stat{display:flex;align-items:baseline;gap:8px}.stat dd{font-size:23px}.articlegrid{grid-template-columns:minmax(0,1fr) 205px;gap:22px}nav{gap:15px}}
@media(max-width:640px){.wrap{width:calc(100% - 32px)}.top{min-height:59px;gap:10px}.brand{font-size:14px;gap:7px}nav{gap:12px}.rss{padding:5px 9px}.navlink{font-size:12px}.nav-status{display:none}.mast{gap:17px}.section{margin-top:24px}.sectionhead{align-items:flex-start;flex-wrap:wrap;gap:10px}.articlegrid{display:flex;flex-direction:column-reverse;gap:12px;align-items:stretch}.sidebar{padding:8px 12px}.sidebar h3{font-size:13px;margin-bottom:2px}.filterlist{display:flex;flex-wrap:wrap;gap:0 12px}.filterlist li+li{border-top:0}.sourcebtn{font-size:12px;padding:4px 0;gap:4px}.resources{grid-template-columns:1fr;gap:0;padding-left:14px}.status-row{grid-template-columns:1fr auto;gap:3px 10px}.status-row span:last-child{grid-column:1/-1}.catalog-tools{align-items:flex-start}.controls{width:100%}.controls .search{flex:1 1 145px;min-width:0}.select{flex:0 1 auto;max-width:55%}.story{padding:15px 0}.archive{margin-top:28px}.notice{font-size:12px}.foot{align-items:flex-start}}
@media(max-width:355px){.navlink{display:none}.stats{gap:10px}.stat{padding-left:10px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


SCRIPT = """
(() => {
  'use strict';
  const get = id => document.getElementById(id);
  const fold = text => text.normalize('NFKC').toLocaleLowerCase().trim();
  const articleInput = get('article-search');
  const stories = Array.from(document.querySelectorAll('.story'));
  const sourceButtons = Array.from(document.querySelectorAll('.sourcebtn'));
  let source = '';
  function applyArticles() {
    const query = fold(articleInput.value);
    let visible = 0;
    stories.forEach(row => {
      row.hidden = Boolean((source && row.dataset.source !== source) || (query && !fold(row.textContent).includes(query)));
      if (!row.hidden) visible++;
    });
    sourceButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.source === source)));
    get('article-empty').hidden = visible !== 0 || stories.length === 0;
    get('article-count').textContent = '显示 ' + visible + ' 篇文章';
  }
  articleInput.addEventListener('input', applyArticles);
  sourceButtons.forEach(button => button.addEventListener('click', () => { source = button.dataset.source; applyArticles(); }));
  const groupSelect = get('group-select'), directoryInput = get('catalog-search');
  const groups = Array.from(document.querySelectorAll('.group'));
  function applyCatalog() {
    const query = fold(directoryInput.value), selected = groupSelect.value;
    let visible = 0;
    groups.forEach(group => {
      const groupMatch = !selected || group.dataset.group === selected;
      const nameMatch = fold(group.dataset.group).includes(query);
      let count = 0;
      group.querySelectorAll('.resource').forEach(row => {
        row.hidden = !(groupMatch && (nameMatch || fold(row.textContent).includes(query)));
        if (!row.hidden) count++;
      });
      group.hidden = count === 0;
      group.querySelector('.count').textContent = count + ' 项';
      group.open = Boolean((query || selected) && count);
      visible += count;
    });
    get('catalog-count').textContent = '显示 ' + visible + ' 个目录条目';
    get('catalog-empty').hidden = visible !== 0 || groups.length === 0;
  }
  directoryInput.addEventListener('input', applyCatalog);
  groupSelect.addEventListener('change', applyCatalog);
  document.querySelector('a[href="#fetch-log"]').addEventListener('click', () => { get('fetch-log').open = true; });
  const dialog = get('subscribe-dialog');
  const online = ['https:', 'http:'].includes(location.protocol);
  document.querySelectorAll('[data-subscribe]').forEach(link => link.addEventListener('click', event => {
    if (typeof dialog.showModal !== 'function') return;
    event.preventDefault();
    get('published-controls').hidden = !online;
    get('dialog-title').textContent = '订阅地址';
    get('subscribe-hint').textContent = online ? '复制地址后，在 RSS 阅读器中添加订阅。' : '当前是本地预览。网站发布后，可将站点目录下的 feed.xml 地址添加到 RSS 阅读器。';
    if (online) get('feed-url').value = new URL('feed.xml', location.href).href;
    get('copy-message').textContent = '';
    dialog.showModal();
  }));
  document.querySelectorAll('[data-opml]').forEach(link => link.addEventListener('click', event => {
    if (online || typeof dialog.showModal !== 'function') return;
    event.preventDefault();
    get('published-controls').hidden = true;
    get('dialog-title').textContent = '导出上游订阅';
    get('subscribe-hint').textContent = '当前是本地预览。完整站点的 feeds.opml 可导入阅读器，订阅各上游来源。';
    get('copy-message').textContent = '';
    dialog.showModal();
  }));
  get('dialog-close').addEventListener('click', () => dialog.close());
  get('copy-feed').addEventListener('click', async () => {
    const input = get('feed-url');
    try {
      await navigator.clipboard.writeText(input.value);
      get('copy-message').textContent = '已复制订阅地址。';
    } catch {
      input.focus(); input.select();
      get('copy-message').textContent = '已选中订阅地址，请复制。';
    }
  });
  document.documentElement.classList.add('enhanced');
})();
"""


def _stories(items):
    rows = []
    for item in items:
        source = item.get("source", "")
        key = item.get("source_id") or source
        description = _text(item.get("summary"))
        rows.append(
            f'<li class="story" data-source="{_text(key)}"><article>'
            f'<div class="meta">{_date(item.get("date"))}<span>{_text(source)}</span></div>'
            f'<h3>{_external(item.get("title"), item.get("url"))}</h3>'
            f'{("<p>" + description + "</p>") if description else ""}</article></li>'
        )
    return "".join(rows)


def _source_sidebar(items):
    counts = Counter(item.get("source_id") or item.get("source", "") for item in items)
    names = {item.get("source_id") or item.get("source", ""): item.get("source", "") for item in items}
    if not counts:
        return ""
    sources = [("", "全部来源", len(items))] + [(key, names[key], n) for key, n in counts.most_common()]
    rows = "".join(
        f'<li><button type="button" class="sourcebtn" data-source="{_text(key)}" aria-pressed="{str(not key).lower()}">'
        f'<span>{_text(label)}</span><span class="count">{n}</span></button></li>'
        for key, label, n in sources
    )
    return f'<aside class="sidebar js-only" aria-label="按文章来源筛选"><h3>文章来源</h3><ul class="filterlist">{rows}</ul></aside>'


def _catalog(catalog):
    by_group = defaultdict(list)
    for row in catalog:
        by_group[row.get("group") or "其他"].append(row)
    options, groups = [], []
    for group, records in by_group.items():
        options.append(f'<option value="{_text(group)}">{_text(group)}</option>')
        entries = []
        for record in records:
            topic = _text(record.get("topic"))
            entries.append(
                f'<li class="resource"><span class="topic">{topic}</span>'
                f'<h3>{_external(record.get("name"), record.get("url"))}</h3>'
                f'<p>{_text(record.get("note"))}</p></li>'
            )
        groups.append(
            f'<details class="group" data-group="{_text(group)}"><summary>'
            f'<span class="group-label">{_text(group)}</span><span class="count">{len(records)} 项</span>'
            f'</summary><ul class="resources">{"".join(entries)}</ul></details>'
        )
    return "".join(options), "".join(groups)


STATUS_LABELS = {
    "ok": "已读取", "success": "已读取", "unchanged": "无变化",
    "error": "读取失败", "failed": "读取失败", "offline": "离线构建",
    "skipped": "已跳过", "cached": "使用存档", "empty": "无条目",
}


def _statuses(status):
    rows = []
    for entry in status:
        state = str(entry.get("status", ""))
        rows.append(
            f'<li class="status-row"><b>{_text(entry.get("name") or entry.get("id"))}</b>'
            f'<span>{_text(STATUS_LABELS.get(state.lower(), state))}</span>'
            f'<span>{_text(entry.get("detail"))}</span></li>'
        )
    return '<ul class="status-list">' + "".join(rows) + '</ul>' if rows else '<p class="empty">本次没有抓取记录。</p>'


def render_archive(config, items, catalog, status, out):
    """Write a static, escaped single-file UI; links work under a Pages project path."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    title = _text(config.get("title"))
    description = _text(config.get("description"))
    sources = config.get("sources") or []
    options, directory = _catalog(catalog)
    story_empty = '<p class="empty">暂时没有收录文章。</p>' if not items else ""
    directory_empty = '<p class="empty">暂时没有目录条目。</p>' if not catalog else ""
    html = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><meta name="description" content="{description}">
<link rel="alternate" type="application/rss+xml" title="{title} RSS" href="feed.xml">
<style>{STYLE}</style></head><body id="top">
<a class="skip" href="#articles">跳到文章</a>
<header><div class="wrap top"><a class="brand" href="#top"><span class="mark" aria-hidden="true"><i></i></span>主题订阅</a>
<nav aria-label="主导航"><a class="navlink" href="#articles">文章</a><a class="navlink" href="#catalog">信息源</a>
<a class="navlink nav-status" href="#fetch-log">抓取记录</a><a class="rss" data-subscribe href="feed.xml">订阅 RSS <b aria-hidden="true">↗</b></a></nav></div></header>
<main class="wrap"><section class="mast" aria-labelledby="site-title"><div><h1 id="site-title">{title}</h1>
<p class="intro">{description}</p></div><dl class="stats"><div class="stat"><dt>收录文章</dt><dd>{len(items)}</dd></div>
<div class="stat"><dt>上游订阅</dt><dd>{len(sources)}</dd></div><div class="stat"><dt>目录条目</dt><dd>{len(catalog)}</dd></div></dl></section>
<section class="section" id="articles" aria-labelledby="articles-title"><div class="sectionhead"><h2 id="articles-title">最新文章</h2>
<div class="controls js-only"><input id="article-search" class="search" type="search" aria-label="搜索文章" placeholder="搜索文章、摘要或来源"></div></div>
<div class="articlegrid"><div><ul class="stories">{_stories(items)}</ul>{story_empty}
<p class="empty" id="article-empty" hidden>没有符合条件的文章。</p><span class="sr-only" role="status" id="article-count"></span></div>
{_source_sidebar(items)}</div></section>
<section class="archive" id="catalog" aria-labelledby="catalog-title"><div class="sectionhead"><h2 id="catalog-title">信息源目录</h2>
<a class="subtle-link" data-opml href="feeds.opml">导出上游订阅 OPML</a></div>
<p class="notice">目录包含网页、栏目和订阅源。可自动抓取的上游订阅见抓取记录。</p>
<div class="catalog-tools"><div class="controls js-only"><input id="catalog-search" class="search" type="search" aria-label="搜索目录" placeholder="搜索名称、方向或说明">
<select id="group-select" class="select" aria-label="按分类筛选"><option value="">全部分类</option>{options}</select></div>
<span role="status" class="count js-only" id="catalog-count">共 {len(catalog)} 个目录条目</span></div>
{directory}{directory_empty}<p class="empty" id="catalog-empty" hidden>没有符合条件的目录条目。</p></section>
<details class="status-box" id="fetch-log"><summary><span class="status-heading">抓取记录</span></summary>{_statuses(status)}</details></main>
<footer><div class="wrap foot"><p>{title}</p><div class="foot-links"><a href="#top">回到顶部 ↑</a></div></div></footer>
<dialog id="subscribe-dialog" aria-labelledby="dialog-title"><div class="dialogtop"><h2 id="dialog-title">订阅地址</h2>
<button class="close" id="dialog-close" type="button" aria-label="关闭">×</button></div><p id="subscribe-hint"></p>
<div id="published-controls"><input readonly id="feed-url" class="url" aria-label="RSS 地址">
<div class="dialog-actions"><button type="button" class="action" id="copy-feed">复制地址</button><a class="subtle-link" href="feed.xml">打开 RSS 文件</a></div></div>
<p role="status" id="copy-message"></p></dialog><script>{SCRIPT}</script></body></html>'''
    (out / "index.html").write_text(html, encoding="utf-8")


BRIEF_STYLE = '''
:root{--page:#f7f6f1;--ink:#202823;--muted:#59645d;--line:#d5d8cf;--accent:#9b3f22;--green:#315847;--sans:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;--serif:"Songti SC","Noto Serif CJK SC",Georgia,serif}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:1rem}body{margin:0;background:var(--page);color:var(--ink);font:.9375rem/1.65 var(--sans);-webkit-font-smoothing:antialiased}a{color:inherit;text-underline-offset:.22em}a:hover{color:var(--accent)}button,input{font:inherit}button{cursor:pointer}a:focus-visible,button:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid var(--green);outline-offset:3px}[hidden]{display:none!important}::selection{background:#dce6cb}
.wrap{width:min(1320px,calc(100% - 48px));margin-inline:auto}.skip{position:absolute;top:-10rem;left:1rem;padding:.7rem;background:white;z-index:10}.skip:focus{top:1rem}.top{display:flex;align-items:center;justify-content:space-between;gap:20px;min-height:48px;border-bottom:1px solid var(--line)}.brand{font-weight:700;text-decoration:none;letter-spacing:.04em}.top nav{display:flex;gap:22px;align-items:center}.top nav a{font-size:.8125rem;min-height:40px;display:flex;align-items:center}.subscribe{color:var(--green)}
.issue-layout{display:grid;grid-template-columns:224px minmax(0,1fr);gap:28px;align-items:start}.issue-sidebar{position:sticky;top:16px;max-height:calc(100vh - 32px);overflow-y:auto;scrollbar-width:thin;padding:20px 4px 20px 0}.issue-nav-title{margin:0 0 10px;font-size:.8125rem;font-weight:650;color:var(--muted)}.issue-nav-title span{margin-inline-start:8px;font-weight:400}.issue-switcher>summary{display:none;cursor:pointer;min-height:44px;padding:9px 0;font-weight:650}.issue-list{list-style:none;margin:0;padding:0;display:grid;gap:4px}.issue-link{display:block;padding:10px 12px;border-inline-start:3px solid transparent;border-radius:0 4px 4px 0;text-decoration:none;overflow-wrap:anywhere}.issue-link:hover{background:#edf0e8;color:var(--ink)}.issue-link[aria-current=page]{background:#e9eee6;border-color:var(--green)}.issue-link[data-pending]{border-color:var(--accent);background:#f0ece2}.issue-link-meta{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:.75rem;font-variant-numeric:tabular-nums}.current-label{color:var(--green);font-weight:650}.issue-link-title{display:block;margin-top:3px;font:650 .9375rem/1.5 var(--serif);text-wrap:balance;word-break:keep-all;overflow-wrap:anywhere}.switcher-date{font-size:.8125rem;font-weight:400;color:var(--muted);margin-inline-start:12px}
.issue-content{min-width:0}.mast{padding:17px 0 12px}.eyebrow{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}h1{font:700 clamp(1.5rem,2.3vw,2rem)/1.35 var(--serif);letter-spacing:-.02em;margin:0;overflow-wrap:anywhere;text-wrap:balance}.issue-overview{display:flex;align-items:baseline;justify-content:space-between;gap:6px 18px;flex-wrap:wrap;margin-top:8px}.intro{margin:0;color:var(--muted);font-size:.875rem}.issue-meta{display:flex;gap:6px 14px;flex-wrap:wrap;font-size:.75rem;color:var(--muted);font-variant-numeric:tabular-nums}
.lead{display:flex;align-items:baseline;gap:12px;padding:10px 14px;background:#e9eee6;border-left:2px solid var(--green);margin-bottom:12px}.lead h2{flex:none;font-size:.8125rem;font-weight:650;color:var(--green);margin:0}.lead p{margin:0;max-width:72em;font-size:.875rem;line-height:1.65}.filters{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 2px}.filters button{padding:4px 10px;min-height:32px;background:transparent;border:1px solid var(--line);border-radius:4px;color:var(--muted);font-size:.8125rem}.filters button[aria-pressed=true]{background:var(--ink);border-color:var(--ink);color:white}.filters button:hover{border-color:var(--muted)}.js-only{display:none}.enhanced .js-only{display:flex}
ol.reading-list{padding:0;margin:0;list-style:none;counter-reset:reading}.reading{display:grid;grid-template-columns:22px minmax(0,1fr);gap:12px;padding:14px 0;border-bottom:1px solid var(--line);counter-increment:reading}.reading:before{content:counter(reading,decimal-leading-zero);padding-top:1px;color:var(--muted);font-size:.75rem;font-variant-numeric:tabular-nums}.reading article{min-width:0}.reading-meta{display:flex;align-items:center;gap:6px 12px;flex-wrap:wrap;font-size:.75rem;color:var(--muted)}.kind{font-weight:650;color:var(--green)}.reading h2{font:700 clamp(1.0625rem,1.5vw,1.25rem)/1.45 var(--serif);margin:4px 0 6px;overflow-wrap:anywhere;text-wrap:pretty}.reading h2 a{text-decoration:none}.reading h2 a:hover{text-decoration:underline}.summary{font-size:.9375rem;line-height:1.65;max-width:66em;margin:0}.why{display:flex;gap:10px;max-width:70em;margin:7px 0 0;color:var(--green);font-size:.875rem;line-height:1.6}.why strong{flex:none;font-weight:650}.ext{font-size:.65em;color:var(--muted);margin-left:.4em;vertical-align:.1em}.original{margin-top:4px;max-width:70em;color:var(--muted);font-size:.75rem;overflow-wrap:anywhere}.original summary{cursor:pointer;min-height:24px;display:list-item}.original p{margin:4px 0 0}
.past{margin-top:22px}.past summary{font-weight:650;cursor:pointer;padding-block:8px;min-height:40px}.edition-note{color:var(--muted);font-size:.8125rem;margin-top:12px}.subscribe-box{margin-top:16px;padding-top:18px;border-top:1px solid var(--line)}.subscribe-box label{display:block;font-size:.8125rem;margin-bottom:6px}.copy-row{display:flex;gap:10px;align-items:stretch}.copy-row input{min-width:0;flex:1;padding:8px 10px;background:#fff;border:1px solid var(--line);border-radius:4px;font-size:1rem}.copy-row button{background:var(--green);color:white;border:0;border-radius:4px;padding:8px 16px;min-height:40px}.copy-status{min-height:1.6em;margin:6px 0}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.empty{padding:24px 0}footer{padding:24px 0;margin-top:20px;color:var(--muted);font-size:.8125rem}footer p{margin:8px 0}footer nav{display:flex;gap:18px;flex-wrap:wrap}
@media(prefers-reduced-motion:no-preference){.issue-content{transition:opacity 180ms ease-out,transform 220ms ease-out}.issue-content.is-exiting{opacity:0;transform:translateY(-4px);transition-duration:110ms}.issue-content.is-entering{opacity:0;transform:translateY(7px)}.issue-link{transition:background-color 140ms ease-out,border-color 140ms ease-out}.filters button,.copy-row button{transition:background-color 140ms ease-out,border-color 140ms ease-out,color 140ms ease-out,scale 120ms ease-out}.filters button:active,.copy-row button:active{scale:.96}.reading h2 a{transition:color 120ms ease-out}.original[open] p{animation:detail-in 150ms ease-out}@keyframes detail-in{from{opacity:0;transform:translateY(-2px)}to{opacity:1;transform:translateY(0)}}}
@media(max-width:820px){.issue-layout{grid-template-columns:minmax(0,1fr);gap:0}.issue-sidebar{position:static;max-height:none;overflow:visible;padding:6px 0 0}.issue-nav-title{display:none}.issue-switcher{border-bottom:1px solid var(--line)}.issue-switcher>summary{display:list-item}.issue-switcher[open]{padding-bottom:10px}.issue-list{grid-template-columns:repeat(2,minmax(0,1fr));gap:4px}.mast{padding-top:14px}.issue-overview{display:block}.issue-meta{margin-top:6px}}
@media(max-width:600px){.wrap{width:calc(100% - 28px)}.top{min-height:50px;gap:10px;flex-wrap:wrap;padding-block:4px}.top nav{gap:12px}.top nav a{min-height:40px}.issue-list{grid-template-columns:minmax(0,1fr)}h1{font-size:1.5rem}.intro{font-size:.8125rem}.lead{display:block;padding:9px 12px}.lead h2{margin-bottom:3px}.lead p{font-size:.8125rem}.filters button{min-height:40px;padding-inline:10px}.reading{grid-template-columns:18px minmax(0,1fr);gap:8px;padding:13px 0}.reading h2{font-size:1.125rem}.summary{font-size:.9375rem;line-height:1.7}.why{display:block;font-size:.8125rem}.why strong{margin-inline-end:8px}.original summary{min-height:32px}.copy-row{flex-wrap:wrap}.copy-row input{flex-basis:100%}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
'''

BRIEF_SCRIPT = '''
(() => {
  'use strict';
  const issueSwitcher = document.getElementById('issue-switcher');
  const compact = window.matchMedia('(max-width: 820px)');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const adaptIssues = () => { issueSwitcher.open = !compact.matches; };
  adaptIssues();
  compact.addEventListener('change', adaptIssues);
  document.querySelector('a[href="#issues"]').addEventListener('click', () => {
    issueSwitcher.open = true;
  });

  // Keep root and nested issue links correct after changing the URL in place.
  function resolveLinks(root, base) {
    root.querySelectorAll('a[href], link[rel="alternate"][href]').forEach(link => {
      const href = link.getAttribute('href');
      if (href && !href.startsWith('#')) link.href = new URL(href, base).href;
    });
  }
  resolveLinks(document, location.href);
  let renderedURL = location.href, requestID = 0, controller;
  const status = document.getElementById('navigation-status');
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

  async function navigateIssue(url, push = true) {
    const id = ++requestID;
    controller?.abort();
    const old = document.getElementById('issue-content');
    old.classList.remove('is-exiting', 'is-entering');
    document.querySelectorAll('.issue-link[data-pending]').forEach(link => delete link.dataset.pending);
    if (url === renderedURL && location.href === renderedURL) {
      old.removeAttribute('aria-busy'); status.textContent = ''; return;
    }
    const request = controller = new AbortController();
    const timeout = setTimeout(() => request.abort(), 12000);
    old.setAttribute('aria-busy', 'true');
    const pending = [...document.querySelectorAll('.issue-link')].find(link => link.href === url);
    if (pending) pending.dataset.pending = 'true';
    status.textContent = '正在载入这一期';
    try {
      const response = await fetch(url, {signal: request.signal});
      if (!response.ok) throw new Error('Issue unavailable');
      const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
      const content = doc.getElementById('issue-content');
      const list = doc.querySelector('.issue-list');
      if (!content || !list) throw new Error('Incomplete issue');
      resolveLinks(doc, url);
      if (id !== requestID) return;
      if (!reducedMotion.matches) {
        old.classList.add('is-exiting');
        await delay(115);
      }
      if (id !== requestID) return;
      const next = document.importNode(content, true);
      if (!reducedMotion.matches) next.classList.add('is-entering');
      old.replaceWith(next);
      document.querySelector('.issue-list').replaceWith(document.importNode(list, true));
      document.querySelector('.switcher-date').textContent = doc.querySelector('.switcher-date').textContent;
      document.title = doc.title;
      if (push) history.pushState({issueReader: true}, '', url);
      renderedURL = url;
      if (compact.matches) issueSwitcher.open = false;
      next.focus({preventScroll: true});
      window.scrollTo({top: 0, behavior: 'instant'});
      // Commit the starting state before transitioning to fully visible content.
      next.getBoundingClientRect();
      requestAnimationFrame(() => next.classList.remove('is-entering'));
      status.textContent = '已切换到 ' + doc.querySelector('h1').textContent;
    } catch (error) {
      if (id === requestID) location.assign(url);
    } finally {
      clearTimeout(timeout);
      if (id === requestID) {
        document.getElementById('issue-content').removeAttribute('aria-busy');
        document.querySelectorAll('.issue-link[data-pending]').forEach(link => delete link.dataset.pending);
      }
    }
  }

  document.addEventListener('click', async event => {
    const link = event.target.closest('.issue-link');
    if (link && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
        && new URL(link.href).origin === location.origin) {
      event.preventDefault();
      navigateIssue(link.getAttribute('aria-current') === 'page' ? renderedURL : link.href);
      return;
    }
    const filter = event.target.closest('[data-filter]');
    if (filter) {
      let count = 0;
      document.querySelectorAll('.reading').forEach(row => {
        row.hidden = Boolean(filter.dataset.filter && row.dataset.kind !== filter.dataset.filter);
        if (!row.hidden) count++;
      });
      document.querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button === filter)));
      document.getElementById('filter-status').textContent = `显示 ${count} 条精选`;
    }
    if (event.target.closest('#copy-rss')) {
      const input = document.getElementById('rss-url');
      const message = document.getElementById('copy-status');
      try { await navigator.clipboard.writeText(input.value); message.textContent = '订阅地址已复制'; }
      catch { input.focus(); input.select(); message.textContent = '请复制选中的地址'; }
    }
  });
  window.addEventListener('popstate', () => navigateIssue(location.href, false));
  document.documentElement.classList.add('enhanced');
})();
'''


def _issue_navigation(editions, day, prefix):
    links = []
    for edition in editions[:60]:
        date = edition['date']
        name = edition.get('name') or f'{len(edition["items"])} 条精选'
        # The site name and item count already have their own place in the navigation.
        theme = name.split('｜', 1)[-1].strip()
        theme_html = _text(theme).replace('，', '，<wbr>')
        current = ' aria-current="page"' if date == day else ''
        label = '<span class="current-label">正在读</span>' if date == day else ''
        links.append(f'<li><a class="issue-link" href="{prefix}issues/{_text(date)}.html"{current}>'
                     f'<span class="issue-link-meta">{_date(date)}{label}</span>'
                     f'<span class="issue-link-title">{theme_html}</span>'
                     '</a></li>')
    listing = f'<ol class="issue-list">{"".join(links)}</ol>' if links else '<p class="edition-note">第一期正在整理。</p>'
    return (f'<aside class="issue-sidebar" id="issues" aria-label="每期主题">'
            f'<h2 class="issue-nav-title">每期主题<span>{len(links)} 期</span></h2>'
            f'<details class="issue-switcher" id="issue-switcher" open><summary>每期主题'
            f'<span class="switcher-date">{_text(day.replace("-", "."))}</span></summary>'
            f'<nav aria-label="选择一期阅读">{listing}</nav></details></aside>')


def render_brief(config, edition, editions, out, prefix=''):
    from digest import KINDS
    from urllib.parse import urljoin
    import math
    title = config.get('title', '每日精选')
    items = edition['items'] if edition else []
    mix = Counter(row['kind'] for row in items)
    day = edition['date'] if edition else ''
    issue_name = edition.get('name', '每天几分钟，看懂值得关注的进展。') if edition else '第一期正在整理'
    keywords = ' · '.join(edition.get('keywords', [])) if edition else ''
    coverage = edition.get('coverage') if edition else None
    weekly = edition.get('weekly_focus', {}) if edition else {}
    from balance import DOMAINS
    weekly_names = '、'.join(DOMAINS.get(d, d) for d in weekly.get('focus_domains', []))
    weekly_html = f'<p class="edition-note">本周多看一点：{_text(weekly_names)}。{_text(weekly.get("reason", ""))}</p>' if weekly_names else ''
    source_table_link = f'<a href="{prefix}sources.html">信息源 Top 20 与访问表</a>' if config.get('source_registry') else ''
    coverage_html = ''
    if coverage:
        coverage_html = f'<p class="edition-note">本期比较了 {coverage["candidates_compared"]} 篇候选，其中 {coverage.get("candidates_read", 0)} 篇读过原文或摘要；其余为列表初筛。来源表登记 {coverage["sources_total"]} 项，本轮尝试读取 {coverage["sources_attempted"]} 项，其中 {coverage["sources_readable"]} 项取得公开页面或 RSS；失败与受限项另列。<a href="{prefix}sources.html">查看信息源与访问实测</a></p>'
    words = sum(len(row['headline'] + row['summary'] + row['why_read']) for row in items)
    minutes = max(1, math.ceil(words / 350))
    filters = ''.join(f'<button type="button" data-filter="{kind}" aria-pressed="false">{_text(KINDS[kind])} {count}</button>' for kind, count in mix.items())
    cards = []
    for row in items:
        cards.append(f'''<li class="reading" data-kind="{row['kind']}"><article>
<div class="reading-meta"><span class="kind">{_text(KINDS[row['kind']])}</span><span>{_text(row['source'])}</span><span>原文 {_date(row['date'])}</span></div>
<h2>{_external(row['headline'], row['url'])}</h2>
<p class="summary">{_text(row['summary'])}</p>
<p class="why"><strong>为什么读</strong><span>{_text(row['why_read'])}</span></p>
<details class="original"><summary>查看原文标题</summary><p>{_external(row['title'], row['url'])}</p></details>
</article></li>''')
    issue_navigation = _issue_navigation(editions, day, prefix)
    date_meta = f'<time datetime="{day}">{day.replace("-", ".")}</time>' if day else '第一期正在整理'
    lead = f'<section class="lead" aria-labelledby="lead-title"><h2 id="lead-title">本期看点</h2><p>{_text(edition["lead"])}</p></section>' if edition else '<p class="empty">第一期精选正在整理。发布后会出现在这里，也可以通过 RSS 阅读。</p>'
    feed_url = urljoin(config['site_url'], 'feed.xml')
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_text(issue_name)}{(' · ' + day) if day else ''}</title><meta name="description" content="{_text(config['description'])}"><link rel="alternate" type="application/rss+xml" href="{prefix}feed.xml" title="{_text(title)}"><style>{BRIEF_STYLE}</style></head>
<body><a class="skip" href="#issue-content">跳到本期内容</a><header class="wrap top"><a class="brand" href="{prefix}index.html">{_text(title)}</a><nav aria-label="主导航"><a href="#issues">每期主题</a><a class="subscribe" href="#subscribe">订阅 RSS</a></nav></header>
<p id="navigation-status" class="sr-only" role="status"></p><div class="wrap issue-layout">{issue_navigation}<main class="issue-content" id="issue-content" tabindex="-1"><section class="mast" aria-labelledby="title"><p class="eyebrow">{_text(config.get("brief_tagline", config["title"]))}</p><h1 id="title">{_text(issue_name)}</h1><div class="issue-overview"><p class="intro">{_text(keywords or config['description'])}</p><div class="issue-meta"><span>精选日期 {date_meta}</span><span>{len(items)} 条精选</span><span>约 {minutes} 分钟读完本页</span></div></div></section>
{lead}<section id="reading" aria-label="本期精选"><div class="filters js-only" role="group" aria-label="按内容类型筛选"><button type="button" data-filter="" aria-pressed="true">全部 {len(items)}</button>{filters}</div><p id="filter-status" class="sr-only" role="status"></p><ol class="reading-list">{''.join(cards)}</ol></section>
<details class="past"><summary>这 {len(items)} 条怎么选出来的</summary><p class="edition-note">先轮询完整来源池，再比较候选；找到十篇不会结束检索。每天参考过去七天读过的领域、形式和来源，适当补充缺少的视角；每周结合近四周的覆盖与新进展调整重点，不固定每天的分类名额。论文最多四成，质量优先，不凑数。</p>{weekly_html}{coverage_html}</details>
<section class="subscribe-box" id="subscribe" aria-label="订阅每日精选"><label for="rss-url">把这个地址加入你的 RSS 阅读器</label><div class="copy-row"><input id="rss-url" readonly value="{_text(feed_url)}"><button id="copy-rss" type="button">复制地址</button></div><p class="copy-status" id="copy-status" role="status"></p></section></main></div>
<footer class="wrap"><nav aria-label="更多资料">{source_table_link}<a href="{prefix}archive.html#catalog">原始目录</a><a href="{prefix}archive.html">全部候选资料</a><a href="{prefix}feed.xml">打开 RSS</a></nav><p>精选日期与原文发布日期分别标注；没有新一期时，保留最近一期。</p></footer><script>{BRIEF_SCRIPT}</script></body></html>'''
    Path(out).write_text(html, encoding='utf-8')


def render_site(config, items, catalog, status, out):
    out = Path(out)
    render_archive(config, items, catalog, status, out)
    if 'editions' not in config:
        return
    archive = (out / 'index.html').read_text(encoding='utf-8')
    archive = archive.replace('<nav aria-label="主导航">', '<nav aria-label="主导航"><a class="navlink" href="index.html">每日精选</a>')
    (out / 'archive.html').write_text(archive, encoding='utf-8')
    editions = config['editions']
    render_brief(config, editions[0] if editions else None, editions, out / 'index.html')
    (out / 'issues').mkdir(exist_ok=True)
    for edition in editions[:60]:
        render_brief(config, edition, editions, out / 'issues' / f'{edition["date"]}.html', '../')
