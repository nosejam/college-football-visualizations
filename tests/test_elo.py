import gzip
import hashlib
import json
import math
import unittest
from pathlib import Path
from cfb.elo import MODEL,simulate,update
from cfb.imperialism import football_week,timestamp

ROOT=Path(__file__).resolve().parents[1]

class EloTests(unittest.TestCase):
    def test_known_updates_and_upset_weight(self):
        self.assertEqual(update(1500,1500,21,7),(1516,1484))
        self.assertEqual(update(1500,1500,7,21),(1484,1516))
        self.assertEqual(update(1500,1500,10,10),(1500,1500))
        favorite,underdog=update(1700,1300,7,21)
        self.assertAlmostEqual(favorite,1700-32*10/11)
        self.assertAlmostEqual(underdog,1300+32*10/11)
        self.assertEqual(favorite+underdog,3000)
        self.assertEqual(update(1500,1500,100,0),update(1500,1500,1,0))
        # A draw between unequal teams moves the ratings toward one another.
        self.assertLess(update(1700,1300,0,0)[0],1700)

    def test_season_reset_order_and_future_isolation(self):
        games=[dict(game_id=2,date='2026-09-12T18:00:00Z',home_id=1,away_id=3,home_points=7,away_points=21),
               dict(game_id=1,date='2026-09-05T18:00:00Z',home_id=1,away_id=2,home_points=21,away_points=7)]
        frames=[dict(week=None),dict(week=1),dict(week=2)]
        result=simulate(games,2026,frames,[1,2,3,4])
        self.assertEqual([g['game_id'] for g in result['games']],[1,2])
        self.assertEqual(result['frames'][0]['ratings'],[1500]*4)
        self.assertEqual(result['frames'][1]['ratings'],[1516,1484,1500,1500])
        changed=[{**g,'home_points':99,'away_points':0} if g['game_id']==2 else g for g in games]
        self.assertEqual(simulate(changed,2026,frames,[1,2,3,4])['frames'][:2],result['frames'][:2])
        self.assertEqual(result['frames'][-1]['ratings'][-1],1500)
        with self.assertRaises(ValueError):simulate(games+games,2026,frames)

    def test_saved_history_and_every_week_snapshot(self):
        source=ROOT/'data/imperialism_games.json.gz'
        games=json.loads(gzip.decompress(source.read_bytes()))
        timeline=json.loads((ROOT/'data/imperialism.json').read_text())
        data=json.loads(gzip.decompress((ROOT/'data/team_elo.json.gz').read_bytes()))
        self.assertEqual(data['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        self.assertEqual(data['model'],MODEL)
        self.assertEqual(data['as_of'],timeline['as_of'])
        self.assertEqual(set(data['seasons']),set(games))
        catalog={t['team_id'] for t in json.loads((ROOT/'data/teams.json').read_text())}
        for year,season in data['seasons'].items():
            self.assertTrue(catalog<=set(season['team_ids']))
            self.assertEqual(len(season['frames']),len(timeline['seasons'][year]['frames']))
            ordered=sorted(games[year],key=lambda g:(timestamp(g['date']),g['game_id']))
            self.assertEqual([g['game_id'] for g in ordered],[g['game_id'] for g in season['games']])
            ratings=dict.fromkeys(season['team_ids'],1500.0);cursor=0
            for frame,actual in zip(timeline['seasons'][year]['frames'],season['frames']):
                self.assertEqual(frame['week'],actual['week'])
                while frame['week'] is not None and cursor<len(ordered) and football_week(int(year),ordered[cursor]['date'])<=frame['week']:
                    game=ordered[cursor];record=season['games'][cursor];h,a=game['home_id'],game['away_id']
                    self.assertEqual(record['home_id'],h);self.assertEqual(record['away_id'],a)
                    for i,ident in enumerate([h,a]):self.assertAlmostEqual(record['before'][i],ratings[ident],delta=.00051)
                    expected=1/(1+10**((ratings[a]-ratings[h])/400))
                    observed=.5 if game['home_points']==game['away_points'] else float(game['home_points']>game['away_points'])
                    change=32*(observed-expected);ratings[h]+=change;ratings[a]-=change
                    for i,ident in enumerate([h,a]):self.assertAlmostEqual(record['after'][i],ratings[ident],delta=.00051)
                    cursor+=1
                self.assertEqual(actual['ratings'],[round(ratings[i],3) for i in season['team_ids']])
                self.assertTrue(all(math.isfinite(r) for r in actual['ratings']))
            self.assertEqual(cursor,len(ordered))
            self.assertAlmostEqual(sum(ratings.values()),1500*len(ratings),places=6)

if __name__=='__main__':unittest.main()
