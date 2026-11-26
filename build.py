#!/usr/bin/env python3
"""Collect a topic's public RSS/Atom streams and build its static Pages site."""

import argparse
import concurrent.futures
from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
FEED_LIMIT = 8 * 1024 * 1024
READ_TIMEOUT = 20
USER_AGENT = "TopicFeedPages/1.0 (public RSS/Atom reader)"
ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\Z")
XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
ATOM = "http://www.w3.org/2005/Atom"
TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


class PlainText(HTMLParser):
    """Keep visible text from publisher-provided HTML, never its markup."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.hidden += 1
        if tag in {"p", "br", "li", "div", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "li", "div", "h1", "h2", "h3"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value, limit, *, markup=False):
    if not isinstance(value, str):
        return ""
    if markup:
        parser = PlainText()
        parser.feed(value)
        parser.close()
        value = "".join(parser.parts)
    text = " ".join(value.split())
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]", "", text)
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def web_url(value):
    if not isinstance(value, str) or not value or re.search(r"[\x00-\x20\\]", value):
        return ""
    try:
        parts = urlsplit(value)
        if (parts.scheme.lower() not in {"http", "https"} or not parts.hostname
                or parts.username is not None or parts.password is not None):
            return ""
        _ = parts.port  # Reject malformed ports.
    except ValueError:
        return ""
    return value


def canonical_url(value):
    if not web_url(value):
        return ""
    parts = urlsplit(value)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    keep = [(k, v) for k, v in pairs
            if not (k.lower().startswith("utm_") or k.lower() in TRACKING_PARAMETERS)]
    # Preserve original parameter spelling/order for unmodified (e.g. signed) URLs.
    query = parts.query if len(keep) == len(pairs) else urlencode(keep)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))


def utc_date(value):
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        value = value.strip()
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            stamp = parsedate_to_datetime(value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except (ValueError, TypeError, OverflowError):
        return ""


def normalized_item(raw, *, markup=False):
    if not isinstance(raw, dict):
        raise ValueError("item must be an object")
    record = {
        "title": plain(raw.get("title"), 400, markup=markup),
        "url": canonical_url(raw.get("url")),
        "date": utc_date(raw.get("date")),
        "source": plain(raw.get("source"), 150),
        "source_id": raw.get("source_id"),
        "summary": plain(raw.get("summary", ""), 400, markup=markup),
    }
    if not all(record[key] for key in ("title", "url", "date", "source")):
        raise ValueError("item needs a title, HTTP(S) URL, date and source")
    if not isinstance(record["source_id"], str) or not ID.fullmatch(record["source_id"]):
        raise ValueError("item has an invalid source_id")
    return record


def has_keyword(text, keywords):
    body = text.casefold()
    for raw_word in keywords:
        word = raw_word.casefold()
        # Whole words for short ASCII terms such as RSI, allow Chinese substrings.
        if word.isascii() and word.isalpha() and len(word) <= 4:
            if re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", body):
                return True
        elif word in body:
            return True
    return False


def local_name(node):
    return node.tag.rsplit("}", 1)[-1].lower()


def first_text(node, names):
    for name in names:
        for child in node:
            if local_name(child) == name:
                value = "".join(child.itertext()).strip()
                if value:
                    return value
    return ""


def parse_feed(data, source, keywords):
    if len(data) > FEED_LIMIT or b"<!DOCTYPE" in data.replace(b"\0", b"").upper():
        raise ValueError("oversize feed or unsupported document type")
    root = ET.fromstring(data)
    kind = local_name(root)
    if kind == "rss":
        parent = next((n for n in root if local_name(n) == "channel"), None)
        if parent is None:
            raise ValueError("RSS is missing its channel")
    elif kind in {"feed", "rdf"}:
        parent = root
    else:
        raise ValueError("response is not RSS or Atom")
    entries = [n for n in parent if local_name(n) == ("entry" if kind == "feed" else "item")]
    parsed, invalid, filtered = [], 0, 0
    base = urljoin(source["feed"], root.get(XML_BASE, ""))
    if parent is not root:
        base = urljoin(base, parent.get(XML_BASE, ""))
    for entry in entries:
        entry_base = urljoin(base, entry.get(XML_BASE, ""))
        link = ""
        if kind == "feed":
            for child in entry:
                if local_name(child) == "link" and child.get("rel", "alternate") == "alternate":
                    if child.get("href") and child.get("type", "text/html") in {"text/html", "application/xhtml+xml"}:
                        link = urljoin(urljoin(entry_base, child.get(XML_BASE, "")), child.get("href"))
                        break
            if not link:
                link = web_url(first_text(entry, ["id"]))
        else:
            link = first_text(entry, ["link"])
            if not link:
                link = web_url(first_text(entry, ["guid"]))
        summary = first_text(entry, ["summary", "description"])
        try:
            item = normalized_item({
                "title": first_text(entry, ["title"]), "url": urljoin(entry_base, link) if link else "",
                "date": first_text(entry, ["published", "pubdate", "date", "updated"]),
                "summary": summary,
                "source": source["name"], "source_id": source["id"],
            }, markup=True)
        except ValueError:
            invalid += 1
            continue
        if keywords and source.get("filter", True):
            excerpt = item["title"] + " " + plain(summary, 32000, markup=True)
            if not has_keyword(excerpt, keywords):
                # A publisher's full text is searchable but is never syndicated.
                full_text = first_text(entry, ["encoded", "content"])
                if not has_keyword(plain(full_text, 32000, markup=True), keywords):
                    filtered += 1
                    continue
        parsed.append(item)
    if entries and len(entries) == invalid:
        raise ValueError("all entries lack a usable title, public link or date")
    return parsed, f"匹配 {len(parsed)} 条，过滤 {filtered} 条，无效 {invalid} 条"


def download(url):
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*;q=0.2"})
    with urlopen(request, timeout=READ_TIMEOUT) as response:
        if not web_url(response.geturl()):
            raise ValueError("invalid redirect")
        data = response.read(FEED_LIMIT + 1)
    return data


def read_json(path, default=None):
    if default is not None and not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def records(path):
    raw = read_json(path, [])
    if not isinstance(raw, list):
        raise ValueError(f"{path.name}: expected an array of items")
    result = []
    for i, entry in enumerate(raw, 1):
        try:
            result.append(normalized_item(entry))
        except ValueError as exc:
            raise ValueError(f"{path.name}, row {i}: {exc}") from exc
    return result


def load_config(root, topic):
    if not ID.fullmatch(topic):
        raise ValueError("invalid topic ID")
    cfg = read_json(root / "topics" / f"{topic}.json")
    if not isinstance(cfg, dict) or cfg.get("id") != topic or not plain(cfg.get("title"), 400) or not plain(cfg.get("description"), 2000):
        raise ValueError("topic ID, title and description are required")
    if not isinstance(cfg.get("sources"), list) or not isinstance(cfg.get("keywords", []), list):
        raise ValueError("sources and keywords must be arrays")
    if any(not isinstance(w, str) or not w.strip() for w in cfg.get("keywords", [])):
        raise ValueError("keywords must be nonempty strings")
    seen = set()
    for source in cfg["sources"]:
        if not isinstance(source, dict):
            raise ValueError("each source must be an object")
        sid = source.get("id", "")
        if not isinstance(sid, str) or not ID.fullmatch(sid) or sid in seen:
            raise ValueError(f"invalid or repeated source ID: {sid}")
        if not plain(source.get("name"), 150) or not web_url(source.get("feed")) or not web_url(source.get("url")):
            raise ValueError(f"{sid}: needs a name, homepage URL and feed URL")
        if "filter" in source and not isinstance(source["filter"], bool):
            raise ValueError(f"{sid}: filter must be boolean")
        seen.add(sid)
    return cfg


def fetch_one(source, keywords, fetch):
    status = {"id": source["id"], "name": source["name"], "status": "ok", "detail": ""}
    try:
        items, status["detail"] = parse_feed(fetch(source["feed"]), source, keywords)
    except Exception as exc:
        # One broken upstream must not discard other sources or their history.
        status.update(status="error", detail=plain(f"{type(exc).__name__}: {exc}", 240))
        items = []
    return items, status


def merge_items(previous, incoming, curated):
    by_url = {item["url"]: item for item in previous}
    for item in incoming:
        old = by_url.get(item["url"])
        if old is None or (old["source_id"] == item["source_id"] and item["date"] >= old["date"]):
            by_url[item["url"]] = item
    # Curated rows take precedence regardless of concurrent feed response order.
    for item in curated:
        by_url[item["url"]] = item
    # Publishers sometimes alternate /article and /article/. Only collapse that
    # difference when titles also agree; keep query strings and published URLs.
    curated_urls = {item["url"] for item in curated}
    by_article = {}
    for item in by_url.values():
        parts = urlsplit(item["url"])
        path_key = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/") or "/", parts.query, ""))
        key = (path_key, item["title"].casefold())
        old = by_article.get(key)
        if (old is None or item["url"] in curated_urls or
                (old["url"] not in curated_urls and item["date"] > old["date"])):
            by_article[key] = item
    return sorted(by_article.values(), key=lambda it: (it["date"], it["url"]), reverse=True)


def xml_file(root, path):
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def write_syndication(out, config, items, site_url):
    ET.register_namespace("atom", ATOM)
    channel_root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(channel_root, "channel")
    for key, text in (("title", config["title"]), ("link", site_url), ("description", config["description"])):
        ET.SubElement(channel, key).text = text
    ET.SubElement(channel, f"{{{ATOM}}}link", rel="self", type="application/rss+xml", href=urljoin(site_url, "feed.xml"))
    for item in items[:200]:
        entry = ET.SubElement(channel, "item")
        ET.SubElement(entry, "title").text = item["title"]
        ET.SubElement(entry, "link").text = item["url"]
        ET.SubElement(entry, "guid", isPermaLink="true").text = item["url"]
        date = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
        ET.SubElement(entry, "pubDate").text = format_datetime(date, usegmt=True)
        # RSS readers may intentionally render a description as HTML.
        if item["summary"]:
            ET.SubElement(entry, "description").text = escape(item["summary"], quote=False)
        ET.SubElement(entry, "category").text = item["source"]
    xml_file(channel_root, out / "feed.xml")
    opml = ET.Element("opml", version="2.0")
    ET.SubElement(ET.SubElement(opml, "head"), "title").text = config["title"]
    body = ET.SubElement(opml, "body")
    for src in config["sources"]:
        ET.SubElement(body, "outline", type="rss", text=src["name"], title=src["name"], xmlUrl=src["feed"], htmlUrl=src["url"])
    xml_file(opml, out / "feeds.opml")


def json_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = tempfile.NamedTemporaryFile(dir=path.parent, delete=False)
    try:
        with temp:
            temp.write(data)
        os.chmod(temp.name, 0o644)
        os.replace(temp.name, path)
    finally:
        Path(temp.name).unlink(missing_ok=True)


def publish(stage, out, archive, items):
    """Replace generated files only; restore prior versions if a write fails."""
    targets = {out / p.relative_to(stage): p for p in sorted(stage.rglob("*")) if p.is_file()}
    committed = []
    with tempfile.TemporaryDirectory(dir=stage.parent) as backup:
        try:
            for index, (target, source) in enumerate(targets.items()):
                previous = None
                if target.exists():
                    previous = Path(backup) / str(index)
                    shutil.copyfile(target, previous)
                atomic_write(target, source.read_bytes())
                committed.append((target, previous))
            atomic_write(archive, json_text(items).encode("utf-8"))
        except OSError:
            for target, previous in reversed(committed):
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    atomic_write(target, previous.read_bytes())
            raise


def default_site_url():
    if os.environ.get("GITHUB_PAGES_URL"):
        return os.environ["GITHUB_PAGES_URL"]
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" in repository:
        owner, repo = repository.split("/", 1)
        prefix = "" if repo.lower() == f"{owner.lower()}.github.io" else f"{repo}/"
        return f"https://{owner.lower()}.github.io/{prefix}"
    return "http://localhost:8000/"


@contextmanager
def build_lock(root):
    """Serialize local builds as well as overlapping runners using the same checkout."""
    import fcntl
    (root / "state").mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root / "state", os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def build(root, topic, offline, site_url, out, fetch=download, renderer=None):
    cfg = load_config(root, topic)
    if not web_url(site_url) or urlsplit(site_url).query or urlsplit(site_url).fragment:
        raise ValueError("site URL must be an absolute HTTP(S) directory URL")
    site_url = site_url.rstrip("/") + "/"
    cfg = {**cfg, "site_url": site_url}
    catalog = read_json(root / cfg["catalog"]) if cfg.get("catalog") else []
    if not isinstance(catalog, list) or any(not isinstance(row, dict) for row in catalog):
        raise ValueError("catalog must be an array of objects")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with build_lock(root):
        archive = root / "state" / f"{topic}.json"
        previous = records(archive)
        curated = records(root / "editorial" / f"{topic}.json")
        status, incoming = [], []
        if offline:
            status = [{"id": s["id"], "name": s["name"], "status": "offline", "detail": "离线构建，未请求上游"} for s in cfg["sources"]]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                jobs = [pool.submit(fetch_one, s, cfg.get("keywords", []), fetch) for s in cfg["sources"]]
                for job in jobs:
                    found, result = job.result()
                    incoming.extend(found)
                    status.append(result)
                    print(f"{result['id']}: {result['status']} — {result['detail']}", file=sys.stderr)
            if status and not any(s["status"] == "ok" for s in status):
                raise ValueError("no live source succeeded; previous site and archive retained")
            if not status and not (previous or curated):
                raise ValueError("topic has no configured feeds or archived/editorial articles")
        items = merge_items(previous, incoming, curated)
        if renderer is None:
            from render_site import render_site
            renderer = render_site
        with tempfile.TemporaryDirectory(prefix=".topic-site-", dir=out.parent) as staging:
            stage = Path(staging)
            write_syndication(stage, cfg, items, site_url)
            (stage / "status.json").write_text(json_text(status), encoding="utf-8")
            renderer(cfg, items, catalog, status, stage)
            if not (stage / "index.html").is_file():
                raise ValueError("renderer did not produce index.html")
            publish(stage, out, archive, items)
        added = len(set(i["url"] for i in items) - set(i["url"] for i in previous))
        return {"topic": topic, "items": len(items), "added": added, "offline": offline,
                "sources_ok": sum(s["status"] == "ok" for s in status),
                "sources_error": sum(s["status"] == "error" for s in status),
                "feed": urljoin(site_url, "feed.xml")}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--topic", default="rsi", help="ID of a topic JSON file")
    cli.add_argument("--offline", action="store_true", help="use only the archive and curated files")
    cli.add_argument("--site-url", default=default_site_url(), help="public HTTP(S) Pages root, including project subpath")
    cli.add_argument("--out", type=Path, default=ROOT / "public")
    args = cli.parse_args()
    try:
        report = build(ROOT, args.topic, args.offline, args.site_url, args.out)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
