import hashlib
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class PredictorSourcesTests(unittest.TestCase):
    def test_current_rules_and_schedule_coverage(self):
        coverage=json.loads((ROOT/'data/predictor_coverage.json').read_text())
        rules=json.loads((ROOT/'data/sources/predictor/rules_2026.json').read_text())
        self.assertEqual(coverage['rules'],rules)
        self.assertEqual(rules['field_size'],12)
        self.assertEqual(set(rules['power_automatic']),{'ACC','Big Ten','Big 12','SEC'})
        self.assertEqual(len(rules['group_automatic']),6)
        self.assertFalse(rules['group_bid_requires_championship'])
        self.assertTrue(rules['notre_dame_top_12_guarantee'])
        self.assertFalse(rules['conference_flag_overrides']['401862844']['conference'])
        self.assertEqual(set(rules['sun_belt_east'])&set(rules['sun_belt_west']),set())
        self.assertEqual(len(rules['sun_belt_east'])+len(rules['sun_belt_west']),14)
        self.assertEqual(coverage['fbs_teams'],138)
        self.assertEqual(sum(coverage['conferences'].values()),138)
        path=ROOT/f'data/sources/imperialism/schedules_{coverage["season"]}.parquet'
        self.assertEqual(coverage['schedule_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())

if __name__=='__main__':unittest.main()
