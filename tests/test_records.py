import csv
import gzip
import hashlib
import json
import unittest
from collections import Counter

from cfb import ROOT, load_season_records, load_teams
from scripts.build_records import record

class RecordTests(unittest.TestCase):
    def test_coverage_and_joins(self):
        records=load_season_records()
        self.assertEqual(Counter(r['season'] for r in records),dict(zip(range(2016,2026),[128,130,130,130,130,130,131,133,134,136])))
        self.assertEqual(len(records),len({(r['season'],r['team_id']) for r in records}))
        catalog={t['team_id']:t for t in load_teams()}
        for r in records:
            self.assertEqual(r['games'],r['wins']+r['losses']+r['ties'])
            self.assertGreaterEqual(min(r['wins'],r['losses'],r['ties']),0)
            self.assertEqual(r['school'],catalog[r['team_id']]['school'])
            self.assertEqual(r['logo'],catalog[r['team_id']]['logo'])
            self.assertTrue((ROOT/r['logo']).is_file())
            if 'fbs' in catalog[r['team_id']]['logos']:
                self.assertEqual(r['logo_source'],'fbs')
            if r['games']:
                self.assertAlmostEqual(r['win_pct'],(r['wins']+r['ties']/2)/r['games'],places=6)
            else: self.assertIsNone(r['win_pct'])
        with (ROOT/'data/season_records.csv').open() as f:
            csv_rows=list(csv.DictReader(f))
        self.assertEqual([(int(r['season']),int(r['team_id']),int(r['wins']),int(r['losses'])) for r in csv_rows],
                         [(r['season'],r['team_id'],r['wins'],r['losses']) for r in records])

    def test_postseason_and_covid(self):
        for name,year,w,l in [('Clemson',2016,14,1),('Alabama',2020,13,0),('Ohio State',2024,14,2),('Indiana',2025,16,0),('New Mexico State',2020,1,1)]:
            row,=load_season_records(name,year)
            self.assertEqual((row['wins'],row['losses']),(w,l))
        for team in ['Connecticut','Old Dominion']:
            row,=load_season_records(team,2020)
            self.assertEqual(row['status'],'did_not_play')
            self.assertEqual(row['games'],0)
        self.assertEqual(load_season_records('UAB',2016),[])
        self.assertEqual(load_season_records('James Madison',2021),[])

    def test_record_type_ignores_repeated_stat_names(self):
        stats=[dict(name='wins',type='wins',value=12),dict(name='overall',type='total',summary='12-2'),
               dict(name='wins',type='awayrecord_wins',value=5)]
        self.assertEqual(record(stats,'total'),[12,2,0])
        self.assertIsNone(record(stats,'vsconf'))

    def test_sources_audit_and_totals(self):
        manifest=json.loads((ROOT/'data/sources/records/manifest.json').read_text())
        self.assertEqual(len(manifest),20)
        for source in manifest:
            data=gzip.decompress((ROOT/source['file']).read_bytes())
            self.assertEqual(hashlib.sha256(data).hexdigest(),source['sha256'])
        coverage=json.loads((ROOT/'data/records_coverage.json').read_text())
        self.assertEqual(coverage['missing_records'],[])
        # Full schedules independently reproduce every FBS record for 2023–2025.
        self.assertFalse([d for d in coverage['standings_schedule_differences'] if d['season']>=2023])
        for total in json.loads((ROOT/'data/decade_records.json').read_text()):
            rows=load_season_records(total['team_id'])
            for key in ['wins','losses','ties','games']:
                self.assertEqual(total[key],sum(r[key] for r in rows))
            self.assertEqual(total['seasons_played'],sum(r['games']>0 for r in rows))

if __name__=='__main__': unittest.main()
