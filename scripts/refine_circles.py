"""Spend additional solver time on unique unproven full-FBS reference graphs."""
import gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cfb.circles import certify_cycle
from cfb.imperialism import football_week

if __name__=='__main__':
    path=ROOT/'data/circles_reference.json';data=json.loads(path.read_text())
    timeline=json.loads((ROOT/'data/imperialism.json').read_text())
    games=json.loads(gzip.decompress((ROOT/'data/imperialism_games.json.gz').read_bytes()))
    seen={}
    for year,frames in data['seasons'].items():
        roster=set(timeline['seasons'][year]['roster'])
        for frame in frames:
            if frame['longest']['exact']:continue
            key=frame['fingerprint']
            if key not in seen:
                edges=set()
                for g in games[year]:
                    if football_week(int(year),g['date'])>frame['week'] or g['home_id'] not in roster or g['away_id'] not in roster or g['home_points']==g['away_points']:continue
                    edges.add((g['home_id'],g['away_id']) if g['home_points']>g['away_points'] else (g['away_id'],g['home_id']))
                old=frame['longest'];seen[key]=certify_cycle(roster,edges,old['cycle'],old['upper_bound'],time_limit=30)
                print(year,frame['week'],len(seen[key]['cycle']),seen[key]['upper_bound'],seen[key]['exact'],flush=True)
            frame['longest']=seen[key]
        path.write_text(json.dumps(data,separators=(',',':'))+'\n')
