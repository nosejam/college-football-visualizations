import gzip
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from cfb.imperialism import football_week,simulate,timestamp,transfer

ROOT=Path(__file__).resolve().parents[1]

class ImperialismTests(unittest.TestCase):
    def test_conquests_and_landless_reentry(self):
        owners={1:1,2:2,3:3}
        self.assertEqual(transfer(owners,1,2),[2])
        self.assertEqual(owners,{1:1,2:1,3:3})
        self.assertEqual(transfer(owners,1,3),[3])
        self.assertEqual(transfer(owners,2,1),[1,2,3])
        self.assertEqual(owners,{1:2,2:2,3:2})
        self.assertEqual(transfer(owners,3,1),[]) # Losing team has no land.
        self.assertEqual(owners,{1:2,2:2,3:2})

    def test_kickoff_order_and_ties(self):
        def game(ident,date,home,away,hp,ap):
            return dict(game_id=ident,date=date,home_id=home,away_id=away,home_points=hp,away_points=ap,season_type='regular')
        games=[game(2,'2026-09-05T22:00:00+00:00',3,1,21,14),
               game(3,'2026-09-05T23:00:00+00:00',2,3,7,7),
               game(1,'2026-09-05T16:00:00+00:00',1,2,35,7)]
        frames=simulate([1,2,3],{1:10,2:20,3:30},games,2026)
        self.assertEqual(frames[0]['owners'],[1,2,3])
        self.assertEqual(frames[1]['owners'],[3,3,3])
        self.assertEqual([e['game_id'] for e in frames[1]['events']],[1,2])
        self.assertEqual([e['counties'] for e in frames[1]['events']],[20,30])

    def test_week_numbering(self):
        self.assertEqual(football_week(2019,'2019-08-24T16:00:00Z'),0)
        self.assertEqual(football_week(2019,'2019-08-31T16:00:00Z'),1)
        self.assertEqual(football_week(2025,'2025-08-23T16:00:00Z'),0)
        self.assertEqual(football_week(2025,'2025-08-30T16:00:00Z'),1)
        self.assertEqual(football_week(2026,'2026-10-17T16:00:00Z'),7)
        self.assertEqual(football_week(2026,'2026-09-08T02:00:00Z'),1) # Monday evening Eastern.
        self.assertEqual(football_week(2026,'2026-09-08T12:00:00Z'),2)
        self.assertGreater(football_week(2025,'2026-01-20T00:30:00Z'),16)

    def test_real_upset_chain(self):
        data=json.loads((ROOT/'data/imperialism.json').read_text())
        year=data['seasons']['2016'];geography=data['geographies'][year['geography']]
        i=geography['seeds'].index(2294) # Iowa home territory.
        frames={f['week']:f for f in year['frames']}
        self.assertEqual(frames[3]['owners'][i],2449) # NDSU beats Iowa.
        self.assertEqual(frames[7]['owners'][i],2571) # South Dakota State beats NDSU.
        self.assertEqual(year['frames'][-1]['owners'][i],256) # Ends with James Madison.

    def test_archived_replay_and_county_conservation(self):
        data=json.loads((ROOT/'data/imperialism.json').read_text())
        games=json.loads(gzip.decompress((ROOT/'data/imperialism_games.json.gz').read_bytes()))
        manifest=json.loads((ROOT/'data/sources/imperialism/manifest.json').read_text())
        self.assertEqual(set(data['seasons']),set(map(str,range(2016,2027))))
        self.assertEqual(len(data['county_ids']),3144)
        self.assertEqual(len(set(data['county_ids'])),3144)
        for year,season in data['seasons'].items():
            geo=data['geographies'][season['geography']]
            counts={int(seed):count for seed,count in geo['counts'].items()}
            self.assertEqual(sum(counts.values()),3144)
            self.assertEqual(Counter(geo['assignments']),counts)
            self.assertEqual(geo['seeds'],sorted(counts))
            replay=simulate(geo['seeds'],counts,games[year],int(year))
            self.assertEqual(replay,season['frames'])
            owner={seed:seed for seed in geo['seeds']}
            for frame in replay:
                for event in frame['events']:
                    captured=[seed for seed in geo['seeds'] if owner[seed]==event['loser']]
                    self.assertEqual(captured,event['territories'])
                    self.assertEqual(sum(counts[s] for s in captured),event['counties'])
                    for seed in captured:owner[seed]=event['winner']
                self.assertEqual([owner[seed] for seed in geo['seeds']],frame['owners'])
                self.assertEqual(sum(counts[seed] for seed in owner),3144)
            self.assertEqual(len({g['game_id'] for g in games[year]}),len(games[year]))
            for g in games[year]:self.assertLessEqual(timestamp(g['date']),timestamp(manifest['as_of']))
        # Starting membership changes by year, not a single modern roster.
        self.assertNotIn(5,data['seasons']['2016']['roster']) # UAB resumes in 2017.
        self.assertIn(70,data['seasons']['2017']['roster']) # Idaho leaves FBS in 2018.
        self.assertNotIn(70,data['seasons']['2018']['roster'])
        self.assertEqual(len(data['seasons']['2020']['roster']),130)
        self.assertEqual(len(data['seasons']['2026']['roster']),138)

    def test_source_integrity_and_record_audit(self):
        manifest=json.loads((ROOT/'data/sources/imperialism/manifest.json').read_text())
        self.assertEqual(len(manifest['sources']),11)
        for source in manifest['sources']:
            self.assertEqual(hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest(),source['sha256'])
        coverage=json.loads((ROOT/'data/imperialism_coverage.json').read_text())
        for year in coverage['seasons']:self.assertEqual(year['record_differences'],[])
        for logo in json.loads((ROOT/'data/sources/imperialism/logo_manifest.json').read_text()):
            self.assertNotIn('error',logo)
            self.assertEqual(hashlib.sha256((ROOT/logo['file']).read_bytes()).hexdigest(),logo['sha256'])

if __name__=='__main__':unittest.main()
