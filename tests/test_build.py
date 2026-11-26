import io
import json
from contextlib import redirect_stderr
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import build


SOURCE = {"id": "lab", "name": "示例实验室", "url": "https://lab.test/", "feed": "https://lab.test/feed"}
SECOND = {**SOURCE, "id": "review", "name": "Review", "feed": "https://review.test/feed"}
SITE_URL = "https://owner.github.io/project/"
RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>RSI: A &amp; B</title><link>https://lab.test/a?utm_source=news&amp;v=1#top</link>
<pubDate>Mon, 06 Jan 2025 12:00:00 -0500</pubDate>
<description><![CDATA[<p>Read <b>this</b>.</p><script>bad</script>]]></description></item>
<item><title>A version update</title><link>https://lab.test/other</link><pubDate>2025-01-05</pubDate></item>
<item><title>RSI item</title><link>javascript:bad</link><pubDate>2025-01-01</pubDate></item>
</channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://lab.test/posts/">
<entry xml:base="./2025/"><title>Recursive self-improvement</title>
<link rel="self" href="machine"/><link type="text/html" href="new"/>
<updated>2025-01-07T13:00:00+01:00</updated>
<summary type="html">&lt;p&gt;Coverage.&lt;/p&gt;</summary></entry></feed>"""


def article(url, title="Reviewed", source="ed"):
    return {"source_id": source, "source": source.upper(), "title": title, "url": url,
            "summary": "Use &amp; in <element>.", "date": "2025-01-08"}


class FeedTests(unittest.TestCase):
    def test_rss_filters_and_normalizes(self):
        items, detail = build.parse_feed(RSS, SOURCE, ["rsi"])
        self.assertEqual(len(items), 1)
        self.assertIn("过滤 1 条，无效 1 条", detail)
        self.assertEqual(items[0]["title"], "RSI: A & B")
        self.assertEqual(items[0]["summary"], "Read this.")
        self.assertEqual(items[0]["date"], "2025-01-06T17:00:00Z")
        self.assertEqual(items[0]["url"], "https://lab.test/a?v=1")
        unfiltered, _ = build.parse_feed(RSS, {**SOURCE, "filter": False}, ["unused"])
        self.assertEqual(len(unfiltered), 2)

    def test_atom_resolves_alternate_and_utc(self):
        items, _ = build.parse_feed(ATOM, SOURCE, ["self-improvement"])
        self.assertEqual(items[0]["url"], "https://lab.test/posts/2025/new")
        self.assertEqual(items[0]["date"], "2025-01-07T12:00:00Z")
        self.assertEqual(items[0]["summary"], "Coverage.")

    def test_nonfeeds_and_document_entities_rejected(self):
        for data in (b"<html/>", b"<!DOCTYPE test><rss/>", b"<rss/>"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                build.parse_feed(data, SOURCE, [])

    def test_content_can_match_without_being_syndicated(self):
        atom = ATOM.replace(b"Recursive self-improvement", b"A research update").replace(
            b'<summary type="html">&lt;p&gt;Coverage.&lt;/p&gt;</summary>',
            b'<content type="html">&lt;p&gt;Full text mentions RSI.&lt;/p&gt;</content>',
        )
        items, _ = build.parse_feed(atom, SOURCE, ["RSI"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["summary"], "")
        self.assertNotIn("Full text", str(items[0]))

    def test_duplicate_old_article_does_not_supersede_newer(self):
        first = build.normalized_item(article("https://x.test/link", "New", "lab"))
        stale = {**first, "title": "Old", "date": "2023-01-01T00:00:00Z"}
        self.assertEqual(build.merge_items([first], [stale], []), [first])

    def test_trailing_slash_duplicate_prefers_curated_without_changing_urls(self):
        feed = build.normalized_item(article("https://lab.test/article", "Same article", "lab"))
        curated = build.normalized_item(article("https://lab.test/article/", "Same article", "ed"))
        self.assertEqual(build.merge_items([feed, curated], [feed], [curated]), [curated])
        different_title = {**curated, "title": "Different page"}
        self.assertEqual(len(build.merge_items([], [feed, different_title], [])), 2)
        different_query = {**curated, "url": "https://lab.test/article/?version=2"}
        self.assertEqual(len(build.merge_items([], [feed, different_query], [])), 2)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "site"
        self.put("topics/rsi.json", {
            "id": "rsi", "title": "话题", "description": "Digest", "keywords": ["RSI", "self-improvement"],
            "sources": [SOURCE, SECOND], "catalog": "catalog/rsi.json",
        })
        self.put("catalog/rsi.json", [{"group": "论文", "topic": "聚合", "name": "入口", "url": "", "note": ""}])

    def put(self, path, value):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def read(self, path):
        return json.loads((self.root / path).read_text(encoding="utf-8"))

    def run_build(self, *, fetch, offline=False):
        with redirect_stderr(io.StringIO()):
            return build.build(self.root, "rsi", offline, SITE_URL, self.out, fetch=fetch)

    def snapshot(self):
        return {p.relative_to(self.root): p.read_bytes()
                for folder in (self.out, self.root / "state") for p in folder.rglob("*") if p.is_file()}

    def test_repeatable_collect_then_update_partial_failure_and_offline(self):
        self.put("editorial/rsi.json", [article("https://lab.test/a?v=1", "编辑稿")])
        def both(url):
            return RSS if url == SOURCE["feed"] else ATOM
        result = self.run_build(fetch=both)
        self.assertEqual((result["added"], result["sources_ok"]), (2, 2))
        self.assertEqual(self.run_build(fetch=both)["added"], 0)
        self.assertEqual(self.read("state/rsi.json")[0]["title"], "编辑稿")
        rss = ET.parse(self.out / "feed.xml")
        guids = [node.text for node in rss.findall(".//item/guid")]
        self.assertEqual(len(set(guids)), 2)
        self.assertEqual(rss.find(".//{http://www.w3.org/2005/Atom}link").get("href"), SITE_URL + "feed.xml")
        self.assertEqual(len(ET.parse(self.out / "feeds.opml").findall(".//outline")), 2)
        def partial(url):
            if url == SECOND["feed"]:
                raise TimeoutError("upstream timeout")
            return RSS
        result = self.run_build(fetch=partial)
        self.assertEqual((result["sources_error"], result["items"]), (1, 2))
        statuses = self.read("site/status.json")
        self.assertEqual([s["status"] for s in statuses], ["ok", "error"])
        self.assertIn("upstream timeout", statuses[1]["detail"])
        def no_requests(url):
            self.fail(f"offline made a request: {url}")
        self.run_build(fetch=no_requests, offline=True)
        before = self.snapshot()
        self.run_build(fetch=no_requests, offline=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual([s["status"] for s in self.read("site/status.json")], ["offline", "offline"])
        self.assertEqual(guids, [n.text for n in ET.parse(self.out / "feed.xml").findall(".//item/guid")])

    def test_all_failed_or_invalid_editorial_preserves_previous_site(self):
        self.run_build(fetch=lambda url: RSS)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "no live source succeeded"):
            self.run_build(fetch=lambda url: b"<html/>")
        self.assertEqual(before, self.snapshot())
        self.put("editorial/rsi.json", [article("javascript:void")])
        with self.assertRaisesRegex(ValueError, "row 1"):
            self.run_build(fetch=lambda url: RSS)
        self.assertEqual(before, self.snapshot())

    def test_failed_write_rolls_back_generated_files(self):
        self.run_build(fetch=lambda url: RSS)
        before = self.snapshot()
        self.put("editorial/rsi.json", [article("https://lab.test/new")])
        write = build.atomic_write
        def fail_archive(path, data):
            if path == self.root / "state" / "rsi.json":
                raise OSError("archive write failed")
            write(path, data)
        with patch("build.atomic_write", side_effect=fail_archive), self.assertRaises(OSError):
            self.run_build(fetch=lambda url: RSS)
        self.assertEqual(before, self.snapshot())

    def test_reads_a_real_http_feed_with_default_downloader(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "application/rss+xml")
                self.end_headers()
                self.wfile.write(RSS)

            def log_message(self, *args):
                pass
        # Exercise real HTTP without depending on the machine's reverse DNS.
        with patch("socket.getfqdn", return_value="localhost"), HTTPServer(("127.0.0.1", 0), Handler) as server:
            cfg = self.read("topics/rsi.json")
            cfg["sources"] = [{**SOURCE, "feed": f"http://127.0.0.1:{server.server_port}/feed"}]
            self.put("topics/rsi.json", cfg)
            thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
            thread.start()
            try:
                with redirect_stderr(io.StringIO()):
                    result = build.build(self.root, "rsi", False, SITE_URL, self.out)
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual((result["added"], result["sources_ok"]), (1, 1))
        self.assertTrue((self.out / "index.html").is_file())

    def test_editorial_only_or_history_only_build(self):
        cfg = self.read("topics/rsi.json")
        cfg["sources"] = []
        self.put("topics/rsi.json", cfg)
        with self.assertRaisesRegex(ValueError, "no configured feeds"):
            self.run_build(fetch=None)
        self.put("editorial/rsi.json", [article("https://lab.test/news")])
        result = self.run_build(fetch=None)
        self.assertEqual((result["added"], result["sources_ok"]), (1, 0))
        (self.root / "editorial" / "rsi.json").unlink()
        self.assertEqual(self.run_build(fetch=None)["added"], 0)
        self.assertEqual(self.read("state/rsi.json")[0]["summary"], "Use &amp; in <element>.")


if __name__ == "__main__":
    unittest.main()
