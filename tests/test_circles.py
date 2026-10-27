import gzip
import hashlib
import json
import unittest
import importlib.util
from pathlib import Path
from cfb.circles import canonical,shortest_cycle,strongly_connected,valid_cycle
from cfb.imperialism import football_week
ROOT=Path(__file__).resolve().parents[1]

class CirclesTests(unittest.TestCase):
    def test_direction_and_simple_cycle_rules(self):
        edges=[(1,2),(2,3),(3,1),(2,1)]
        self.assertEqual(shortest_cycle([1,2,3],edges),[1,2,3])
        self.assertEqual(len(shortest_cycle([1,2,3],edges,minimum=2)),2)
        self.assertTrue(valid_cycle([1,2,3],edges))
        self.assertFalse(valid_cycle([1,3,2],edges))
        self.assertFalse(valid_cycle([1,2,1],edges))
        self.assertEqual(shortest_cycle([1,2,3,4],edges,required=4),[])
        self.assertEqual(canonical([3,1,2]),[1,2,3])
        self.assertEqual(strongly_connected([1,2,3,4],edges),[[1,2,3],[4]])

    def test_all_cached_circles_use_real_available_wins(self):
        source=ROOT/'data/imperialism_games.json.gz'
        games=json.loads(gzip.decompress(source.read_bytes()))
        data=json.loads((ROOT/'data/imperialism.json').read_text())
        cache=json.loads((ROOT/'data/circles_reference.json').read_text())
        self.assertEqual(cache['source_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
        for year,season in data['seasons'].items():
            roster=set(season['roster']);frames=cache['seasons'][year]
            self.assertEqual(len(frames),len(season['frames']))
            for i,frame in enumerate(frames):
                edges=set()
                for g in games[year]:
                    if frame['week'] is None or football_week(int(year),g['date'])>frame['week']:continue
                    if g['home_id'] not in roster or g['away_id'] not in roster or g['home_points']==g['away_points']:continue
                    edges.add((g['home_id'],g['away_id']) if g['home_points']>g['away_points'] else (g['away_id'],g['home_id']))
                self.assertEqual(frame['week'],season['frames'][i]['week'])
                self.assertEqual(frame['fingerprint'],hashlib.sha256(json.dumps(sorted(edges)).encode()).hexdigest())
                self.assertEqual(len(frame['shortest']),len(shortest_cycle(roster,edges)))
                self.assertEqual(len(frame['shortest_with_pairs']),len(shortest_cycle(roster,edges,minimum=2)))
                longest=frame['longest'];self.assertGreaterEqual(longest['upper_bound'],len(longest['cycle']))
                if longest['exact']:self.assertEqual(longest['upper_bound'],len(longest['cycle']))
                for field,minimum in [('shortest',3),('shortest_with_pairs',2)]:
                    if frame[field]:self.assertTrue(valid_cycle(frame[field],edges,minimum))
                if longest['cycle']:self.assertTrue(valid_cycle(longest['cycle'],edges))
                else:self.assertEqual(frame['shortest'],[])
        self.assertTrue(next(f for f in cache['seasons']['2026'] if f['week']==7)['longest']['exact'])
        self.assertEqual(len(next(f for f in cache['seasons']['2026'] if f['week']==7)['longest']['cycle']),61)

    @unittest.skipUnless(importlib.util.find_spec('scipy'), 'Optional SciPy solver is not installed')
    def test_connected_integer_solver(self):
        from cfb.circles import longest_cycle,certify_cycle
        articulation=[(1,2),(2,3),(3,1),(1,4),(4,5),(5,1)]
        solved=certify_cycle([1,2,3,4,5],articulation,[1,2,3],5,time_limit=3)
        self.assertEqual(len(solved['cycle']),3)
        self.assertTrue(solved['exact'])
        merged=[(1,2),(2,3),(3,1),(4,5),(5,6),(6,4),(3,4),(6,1)]
        for solved in [longest_cycle(range(1,7),merged,time_limit=3),certify_cycle(range(1,7),merged,[1,2,3],6,time_limit=3)]:
            self.assertEqual(len(solved['cycle']),6)
            self.assertTrue(solved['exact'])
            self.assertTrue(valid_cycle(solved['cycle'],merged))

    def test_supplemental_identity_sources(self):
        manifest=json.loads((ROOT/'data/sources/circles/team_manifest.json').read_text())
        self.assertEqual({t['team_id'] for t in manifest},{292,2341,2698})
        for team in manifest:self.assertEqual(hashlib.sha256((ROOT/team['file']).read_bytes()).hexdigest(),team['sha256'])

if __name__=='__main__':unittest.main()
