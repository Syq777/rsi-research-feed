from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import build
import digest

DAY = date(2026, 11, 26)


def candidate(i, kind='research', **changes):
    return {'title': f'Article {i}', 'url': f'https://lab.example/articles/{i}',
            'date': '2026-11-25', 'source': f'Lab {i % 4}', 'source_id': f'lab-{i % 4}',
            'headline': f'中文标题 {i}', 'summary': '根据原文核实的具体内容。',
            'why_read': '帮助理解反馈如何影响改进。', 'kind': kind,
            'score': 4, 'reviewed_at': DAY.isoformat(), 'event_id': f'event-{i}', **changes}


class DigestTests(unittest.TestCase):
    def select(self, rows, **policy):
        return digest.select_items(rows, DAY, {**digest.DEFAULTS, **policy})

    def test_diversity_and_actual_paper_ceiling(self):
        rows = [candidate(i, 'paper', score=5) for i in range(20)]
        rows += [candidate(i, kind) for i, kind in enumerate(
            ['research'] * 4 + ['engineering'] * 3 + ['assessment'] * 3, 20)]
        chosen = self.select(rows)
        self.assertEqual(len(chosen), 10)
        self.assertLessEqual(sum(x['kind'] == 'paper' for x in chosen), 4)
        self.assertNotEqual(chosen[0]['kind'], 'paper')
        self.assertGreaterEqual(len({x['kind'] for x in chosen}), 3)
        sparse = self.select([candidate(0, 'paper'), candidate(1, 'paper'), candidate(2)])
        self.assertLessEqual(sum(x['kind'] == 'paper' for x in sparse) / len(sparse), .4)
        self.assertEqual(self.select([candidate(i, 'paper') for i in range(5)]), [])

    def test_nonpaper_slots_reallocated_without_forcing_missing_kinds(self):
        chosen = self.select([candidate(i, 'engineering') for i in range(12)])
        self.assertEqual(len(chosen), 10)
        self.assertTrue(all(row['kind'] == 'engineering' for row in chosen))

    def test_old_unreviewed_future_and_low_quality_do_not_fill_slots(self):
        rows = [candidate(0, date='2024-01-01'), candidate(1, reviewed_at='2026-11-25'),
                candidate(2, date='2026-11-27'), candidate(3, score=1), candidate(4)]
        self.assertEqual([x['event_id'] for x in self.select(rows)], ['event-4'])

    def test_event_and_recent_issue_deduplication(self):
        rows = [candidate(0), candidate(1, event_id='event-0'), candidate(2), candidate(3)]
        prior = [{'date': '2026-11-25', 'items': [candidate(2)]}]
        selected = digest.select_items(rows, DAY, digest.DEFAULTS, prior)
        self.assertEqual(len(selected), 2)
        self.assertEqual(len({x['event_id'] for x in selected}), 2)
        self.assertNotIn('event-2', {x['event_id'] for x in selected})

    def test_end_to_end_brief_rss_archive_and_no_fake_next_day(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            def put(name, value):
                p = root / name; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            put('site.json', {'topic': 'rsi'})
            put('topics/rsi.json', {'id': 'rsi', 'title': '阅读精选', 'description': '简短介绍',
                                   'sources': [], 'keywords': [], 'daily_brief': {'size': 10}})
            put('editorial/rsi.json', [candidate(i) for i in range(10)])
            path, issue = digest.make_edition(root, DAY, '今天看什么，以及为什么。')
            before = path.read_bytes()
            report = build.build(root, 'rsi', True, 'https://reader.example/topic/', root/'public')
            self.assertEqual(report['brief_items'], 10)
            html = (root/'public/index.html').read_text()
            self.assertIn('为什么读', html)
            self.assertNotIn('目录条目', html)
            self.assertTrue((root/'public/archive.html').exists())
            self.assertTrue((root/'public/issues/2026-11-26.html').exists())
            rss = ET.parse(root/'public/feed.xml')
            self.assertEqual(len(rss.findall('.//item')), 10)
            self.assertIn('中文标题', rss.findtext('.//item/title'))
            self.assertIn('为什么读', rss.findtext('.//item/description'))
            with self.assertRaisesRegex(ValueError, 'previous edition retained'):
                digest.make_edition(root, DAY + timedelta(days=1), '不能伪装今天已经更新')
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(digest.load_editions(root, 'rsi')), 1)

    def test_incomplete_editorial_cannot_be_published(self):
        with self.assertRaisesRegex(ValueError, 'why_read'):
            self.select([candidate(1, why_read='')])

    def test_rss_uses_issue_timezone_and_keeps_original_publication_date(self):
        edition = {'date': DAY.isoformat(), 'timezone': 'America/New_York', 'items': [candidate(1)]}
        item = digest.feed_items([edition])[0]
        self.assertEqual(item['date'], '2026-11-26T05:00:00+00:00')
        self.assertIn('原文发布：2026-11-25', item['summary'])


if __name__ == '__main__':
    unittest.main()
