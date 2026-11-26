from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from balance import history_stats,load_plan,week_id
from digest import select_items,DEFAULTS
from test_digest import candidate

DAY=date(2026,11,26)
class WeeklyBalanceTests(unittest.TestCase):
    def choose(self,rows,prior=(),**changes):
        return select_items(rows,DAY,{**DEFAULTS,'size':1,**changes},prior)[0]
    def test_recent_concentration_changes_a_close_choice(self):
        recent=[{'date':'2026-11-25','items':[candidate(i+100,'engineering',domain='engineering') for i in range(20)]}]
        rows=[candidate(1,'engineering',domain='engineering',score=4.1),candidate(2,'assessment',domain='safety',score=4)]
        self.assertEqual(self.choose(rows,recent)['domain'],'safety')
    def test_weekly_focus_can_change_without_daily_fixed_slots(self):
        rows=[candidate(1,'engineering',domain='engineering'),candidate(2,'assessment',domain='safety')]
        self.assertEqual(self.choose(rows,focus_domains=['engineering'])['domain'],'engineering')
        self.assertEqual(self.choose(rows,focus_domains=['safety'])['domain'],'safety')
    def test_diversity_does_not_rescue_low_quality(self):
        recent=[{'date':'2026-11-25','items':[candidate(100,'engineering',domain='engineering')]}]
        rows=[candidate(1,'engineering',domain='engineering',score=5),candidate(2,'assessment',domain='safety',score=3)]
        self.assertEqual(self.choose(rows,recent,focus_domains=['safety'])['domain'],'engineering')
    def test_history_windows_and_week_plan_expiry(self):
        history=history_stats([{'date':'2026-11-26','items':[candidate(1)]},{'date':'2026-11-25','items':[candidate(2)]},{'date':'2026-11-01','items':[candidate(3,'engineering')]},{'date':'2026-10-01','items':[candidate(4)]}],DAY)
        self.assertEqual(history['items_7d'],1)
        self.assertEqual(sum(history['domains_28d'].values()),2)
        inclusive=history_stats([{'date':'2026-11-26','items':[candidate(1)]},{'date':'2026-11-20','items':[candidate(2)]},{'date':'2026-11-19','items':[candidate(3)]}],DAY,True)
        self.assertEqual(inclusive['items_7d'],2)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'weeks').mkdir();(root/'weeks/2026-W48-rsi.json').write_text(json.dumps({'week':'2026-W48','focus_domains':['engineering'],'reason':'Recent engineering evidence'}))
            self.assertEqual(load_plan(root,'rsi',DAY,True)['focus_domains'],['engineering'])
            with self.assertRaisesRegex(ValueError,'this week'):load_plan(root,'rsi',date(2026,11,30),True)
if __name__=='__main__':unittest.main()
