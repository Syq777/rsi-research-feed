from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
import poll_sources as p

DAY=date(2026,11,26)
class SourcePollingTests(unittest.TestCase):
    def registry(self,root):
        sources=[{'id':f's{i}','name':f'Lab {i}','url':f'https://lab{i}.example/','poll_url':f'https://lab{i}.example/','mode':'html'} for i in range(20)]
        sources.append({'id':'background','name':'Book','url':'https://book.example/','poll_url':'https://book.example/','mode':'reference'})
        obj={'topic':'test','sources':sources,'domains':[{'id':'engineering','name':'Engineering','top20':[{'source_id':f's{i}','reason':'Relevant primary source'} for i in range(20)]}]}
        (root/'sources').mkdir();(root/'sources/test.json').write_text(json.dumps(obj))
        return obj
    def fetch(self,url):
        return 200,url,'text/html',('<title>Lab articles</title><p>'+('Public research results. '*40)+'</p><a href="/new-research">New agent research result</a>').encode()
    def test_complete_pool_attempted_even_after_ten_successes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.registry(root);calls=[]
            def fetch(url):
                calls.append(url)
                if 'lab15.' in url:raise HTTPError(url,403,'Forbidden',{},None)
                return self.fetch(url)
            _,poll=p.run_poll(root,'test',DAY,fetch=fetch)
            self.assertEqual(len(calls),20)
            self.assertEqual(len(poll['results']),20)
            self.assertEqual(poll['results'][15]['status'],'blocked')
            self.assertNotIn('payment',poll['results'][15]['status'])
            calls.clear();p.run_poll(root,'test',DAY,True,fetch)
            self.assertEqual(len(calls),21)
    def test_coverage_blocks_missing_source_stale_review_and_duplicate_candidates(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.registry(root);path,poll=p.run_poll(root,'test',DAY,fetch=self.fetch)
            review={'poll_sha256':p.fingerprint(poll),'source_reviews':[{'source_id':f's{i}','decision':'no_relevant','note':'Listing screened; no claim of reading full articles.'} for i in range(20)],'candidates':[{'url':f'https://candidate.example/{i}','decision':'exclude','reason':'Outside current scope','evidence_level':'listing'} for i in range(30)]}
            self.assertEqual(p.validate_coverage(root,'test',DAY,review)['candidates_compared'],30)
            review['source_reviews'].pop()
            with self.assertRaisesRegex(ValueError,'every daily source'):p.validate_coverage(root,'test',DAY,review)
            review['source_reviews'].append({'source_id':'s19','decision':'unavailable','note':'Temporary issue'})
            review['candidates'][0]['decision']='shortlist'
            with self.assertRaisesRegex(ValueError,'original content'):p.validate_coverage(root,'test',DAY,review)
            review['candidates'][0]['decision']='exclude';review['candidates'][1]['url']=review['candidates'][0]['url']
            with self.assertRaisesRegex(ValueError,'distinct'):p.validate_coverage(root,'test',DAY,review)
            review['poll_sha256']='old'
            with self.assertRaisesRegex(ValueError,'current complete poll'):p.validate_coverage(root,'test',DAY,review)
            review['poll_sha256']=p.fingerprint(poll)
            poll['results'].pop();path.write_text(json.dumps(poll))
            with self.assertRaisesRegex(ValueError,'incomplete'):p.validate_coverage(root,'test',DAY,review)
    def test_feed_parser_and_empty_html_are_not_equated(self):
        source={'id':'feed','name':'Lab','url':'https://lab.example/','poll_url':'https://lab.example/rss','mode':'feed'}
        xml=b'<rss><channel><item><title>Research update</title><link>https://lab.example/new</link><pubDate>Thu, 26 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>'
        row=p.inspect_source(source,lambda u:(200,u,'application/rss+xml',xml))
        self.assertEqual(row['status'],'readable');self.assertEqual(len(row['links']),1)
        row=p.inspect_source({**source,'mode':'html'},lambda u:(200,u,'text/html',b'<div id="app"></div>'))
        self.assertEqual(row['status'],'needs_browser')
if __name__=='__main__':unittest.main()
