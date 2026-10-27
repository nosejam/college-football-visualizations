"""Precompute certified shortest/longest cycles for each cumulative FBS snapshot."""
import gzip
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb.circles import longest_cycle,shortest_cycle,valid_cycle
from cfb.imperialism import football_week


def main():
    source=ROOT/'data/imperialism_games.json.gz'
    games=json.loads(gzip.decompress(source.read_bytes()))
    timeline=json.loads((ROOT/'data/imperialism.json').read_text())
    path=ROOT/'data/circles_reference.json'
    existing=json.loads(path.read_text()) if path.exists() else {}
    result=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),minimum=3,seasons={})
    cached={f['fingerprint']:f for frames in existing.get('seasons',{}).values() for f in frames} if existing.get('minimum')==3 else {}
    memo={}
    for year,season in timeline['seasons'].items():
        roster=set(season['roster']);compiled=[]
        for index,frame in enumerate(season['frames']):
            edges=set()
            if frame['week'] is not None:
                for g in games[year]:
                    if football_week(int(year),g['date'])>frame['week']:continue
                    if g['home_id'] not in roster or g['away_id'] not in roster or g['home_points']==g['away_points']:continue
                    winner,loser=(g['home_id'],g['away_id']) if g['home_points']>g['away_points'] else (g['away_id'],g['home_id'])
                    edges.add((winner,loser))
            fingerprint=hashlib.sha256(json.dumps(sorted(edges)).encode()).hexdigest()
            old=existing.get('seasons',{}).get(year,[])
            prior=cached.get(fingerprint)
            if fingerprint in memo:
                entry={**memo[fingerprint],'week':frame['week']}
            elif prior is not None:
                entry={**prior,'week':frame['week']}
            else:
                longest=longest_cycle(roster,edges,time_limit=15,initial_cycle=prior['longest']['cycle'] if prior else None,initial_upper=prior['longest']['upper_bound'] if prior else None)
                entry=dict(week=frame['week'],fingerprint=fingerprint,shortest=shortest_cycle(roster,edges),
                           shortest_with_pairs=shortest_cycle(roster,edges,minimum=2),longest=longest)
            memo[fingerprint]=entry
            compiled.append(entry)
            result['seasons'][year]=compiled
            path.write_text(json.dumps(result,separators=(',',':'))+'\n')
            print(year,frame['label'],'largest',len(entry['longest']['cycle']),'upper',entry['longest']['upper_bound'],'exact',entry['longest']['exact'],flush=True)
        result['seasons'][year]=compiled
        # Checkpoint each season, so an interrupted long solve can resume.
        path.write_text(json.dumps(result,separators=(',',':'))+'\n')
    print('Unproven:',[(y,i) for y,frames in result['seasons'].items() for i,f in enumerate(frames) if not f['longest']['exact']],flush=True)

if __name__=='__main__':main()
