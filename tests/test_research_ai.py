import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

# Supports both a sibling test file and tests/ in a generated repository.
for path in Path(__file__).resolve().parents[:2]:
    if (path / 'research_ai.py').is_file():
        sys.path.insert(0, str(path))
        break
import research_ai as worker


class ResearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / 'topics').mkdir()
        (self.root / 'editorial').mkdir()
        self.home = 'https://publisher.org/blog/'
        self.known = 'https://publisher.org/s/article'
        self.new = 'https://publisher.org/s/new'
        self.env = {'OPENAI_API_KEY': 'test-only', 'RESEARCH_MODEL': 'fixture'}
        self.today = dt.date(2026, 3, 24)
        (self.root / 'site.json').write_text(json.dumps({'topic': 'harness'}))
        (self.root / 'topics/harness.json').write_text(json.dumps({'id': 'harness', 'title': '公开主题', 'keywords': ['harness'], 'sources': [{'url': self.home}]}))
        (self.root / 'editorial/harness.json').write_text(json.dumps([{'url': self.known, 'title': '已核查的文章', 'date': '2026-03-01', 'summary':'不属于查询的内部测试标记'}]))

    def result(self, candidates, citations=(), sources=()):
        annotations = [{'type': 'url_citation', 'url': url, 'title': title} for url, title in citations]
        return {'status': 'completed', 'output': [
            {'type': 'web_search_call', 'status': 'completed', 'action': {'type': 'search', 'sources': list(sources)}},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps({'candidates': candidates}), 'annotations': annotations}]}]}

    def run_with(self, result):
        search = Mock(return_value=result)
        path = worker.run(self.root, self.env, search, self.today)
        return path, search

    def test_enabled_only_when_both_variables_are_supplied(self):
        search = Mock(side_effect=AssertionError('must stay offline'))
        for env in ({}, {'OPENAI_API_KEY': 'x'}, {'RESEARCH_MODEL': 'x'}):
            self.assertIsNone(worker.run(self.root, env, search, self.today))
        self.assertFalse((self.root / 'research').exists())

    def test_report_uses_tool_urls_and_archive_dates(self):
        untrusted = 'https://publisher.org/made-up'
        rows = [{'url': url, 'question': '如何复现实验？', 'date': '2999-01-01'} for url in (self.new, self.known, untrusted, self.new)]
        original = (self.root / 'editorial/harness.json').read_bytes()
        target, search = self.run_with(self.result(rows, [(self.new, 'Fresh [field]'), (self.known, '错误元数据')]))
        self.assertEqual(target, self.root / 'research/harness/2026-03-24.md')
        report = target.read_text()
        self.assertEqual(report.count(self.new), 1)
        self.assertIn('Fresh \\[field\\]', report)
        self.assertIn('发布日期：待核实', report)
        self.assertIn('已核查的文章', report)
        self.assertIn('2026-03-01', report)
        self.assertNotIn(untrusted, report)
        self.assertNotIn('2999', report)
        self.assertNotIn('错误元数据', report)
        self.assertEqual((self.root / 'editorial/harness.json').read_bytes(), original)
        self.assertFalse((self.root / 'state').exists())
        key, payload = search.call_args.args
        self.assertEqual(key, 'test-only')
        self.assertEqual(payload['model'], 'fixture')
        self.assertIn('web_search_call.action.sources', payload['include'])
        self.assertEqual(payload['tools'][0]['filters']['allowed_domains'], ['publisher.org'])
        self.assertNotIn('不属于查询的内部测试标记', json.dumps(payload, ensure_ascii=False))

    def test_action_source_works_even_without_title_and_has_no_untrusted_link(self):
        target, _ = self.run_with(self.result([{'url': self.new, 'question': 'visit https://untrusted.io?'}], sources=[{'url': self.new}]))
        self.assertIn('标题待核实', target.read_text()); self.assertNotIn('untrusted.io', target.read_text())

    def test_stays_within_public_source_domains(self):
        for url in ('https://publisher.org.evil.com/a', 'javascript:alert(1)', 'https://name:pass@publisher.org/x', 'https://publisher.org/x?token=ABC', 'https://127.0.0.1/a', 'https://server.local/x'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.run_with(self.result([{'url': url}], [(url, '候选')]))
        self.assertFalse(worker.in_scope('https://github.com/other/repo/releases/1', ['https://github.com/org/repo/releases']))
        self.assertTrue(worker.in_scope('https://github.com/org/repo/releases/tag/v1', ['https://github.com/org/repo/releases']))

    def test_refuses_nonsearch_output_and_preserves_good_report(self):
        report, _ = self.run_with(self.result([{'url': self.new}], [(self.new, 'New')]))
        original = report.read_text()
        self.run_with(self.result([]))
        self.assertEqual(report.read_text(), original)
        result = self.result([{'url': self.new}]); result['output'].pop(0)
        with self.assertRaises(ValueError):
            self.run_with(result)
        self.assertEqual(report.read_text(), original)

    def test_no_match_report_separated_from_feed(self):
        target, _ = self.run_with(self.result([]))
        self.assertIn('没有得到', target.read_text()); self.assertFalse((self.root / 'feed.xml').exists())

    def test_bad_topic_does_not_read_outside_repo(self):
        (self.root / 'site.json').write_text('{"topic":"../../invalid"}')
        with self.assertRaises(ValueError):
            self.run_with(self.result([]))


if __name__ == '__main__':
    unittest.main()
