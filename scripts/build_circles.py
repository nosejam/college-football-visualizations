"""Build the offline circles-of-suck explorer from the existing game snapshot."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb.imperialism import football_week


def build():
    source=ROOT/'data/imperialism_games.json.gz'
    games=json.loads(gzip.decompress(source.read_bytes()))
    timeline=json.loads((ROOT/'data/imperialism.json').read_text())
    catalog={t['team_id']:t for t in json.loads((ROOT/'data/teams.json').read_text())}
    supplemental=json.loads((ROOT/'data/sources/circles/team_manifest.json').read_text())
    for team in supplemental:
        catalog[team['team_id']]={**team,'logos':{},'logo':None}
    reference=json.loads((ROOT/'data/circles_reference.json').read_text())
    assert reference['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest(),'Recompute circle references after updating games'
    elo=json.loads(gzip.decompress((ROOT/'data/team_elo.json.gz').read_bytes()))
    assert elo['source_sha256']==reference['source_sha256'],'Rebuild Elo after updating games'
    all_ids=set();seasons={};coverage=[]
    for year,season in timeline['seasons'].items():
        roster=set(season['roster']);opponents=set(roster)
        for game in games[year]:
            if game['home_id'] in roster or game['away_id'] in roster:opponents.update([game['home_id'],game['away_id']])
        elo_season=elo['seasons'][year];elo_games={g['game_id']:g for g in elo_season['games']}
        included=[]
        for game in sorted(games[year],key=lambda r:(r['date'],r['game_id'])):
            if game['home_id'] not in opponents or game['away_id'] not in opponents or game['home_points']==game['away_points']:continue
            home=game['home_points']>game['away_points']
            rating=elo_games[game['game_id']];winner_index=0 if home else 1;loser_index=1-winner_index
            included.append(dict(id=game['game_id'],winner=game['home_id'] if home else game['away_id'],loser=game['away_id'] if home else game['home_id'],
                winner_points=max(game['home_points'],game['away_points']),loser_points=min(game['home_points'],game['away_points']),
                date=game['date'],week=football_week(int(year),game['date']),
                winner_elo_before=rating['before'][winner_index],winner_elo_after=rating['after'][winner_index],
                loser_elo_before=rating['before'][loser_index],loser_elo_after=rating['after'][loser_index]))
        all_ids.update(opponents)
        assert len(elo_season['frames'])==len(season['frames']),'Rebuild Elo frames'
        frames=[]
        dated=[(football_week(int(year),g['date']),g) for g in games[year]]
        for frame,ratings in zip(season['frames'],elo_season['frames']):
            assert frame['week']==ratings['week'],'Elo week mismatch'
            values=dict(zip(elo_season['team_ids'],ratings['ratings']))
            records={ident:dict(wins=0,losses=0,ties=0) for ident in opponents}
            for week,game in dated:
                if frame['week'] is None or week>frame['week']:continue
                for side,other in [('home','away'),('away','home')]:
                    ident=game[side+'_id']
                    if ident in records:
                        key='wins' if game[side+'_points']>game[other+'_points'] else 'losses' if game[side+'_points']<game[other+'_points'] else 'ties'
                        records[ident][key]+=1
            frames.append(dict(week=frame['week'],label=frame['label'],date=frame['date'],records=records,elo={ident:values[ident] for ident in sorted(opponents)}))
        assert len(reference['seasons'][year])==len(frames)
        seasons[year]=dict(roster=sorted(roster),games=included,frames=frames,reference=reference['seasons'][year])
        coverage.append(dict(season=int(year),fbs_teams=len(roster),teams_with_opponents=len(opponents),games=len(included),
            exact_longest_frames=sum(r['longest']['exact'] for r in reference['seasons'][year]),frames=len(frames)))
    assets=[]
    for ident in sorted(all_ids):
        t=catalog[ident]
        path=ROOT/t['logos']['fbs'] if 'fbs' in t['logos'] else ROOT/f'assets/imperialism/logos/{ident}.png'
        if not path.exists() and t.get('logo'):path=ROOT/t['logo']
        logo='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode() if path.exists() else None
        assets.append(dict(id=ident,school=t['school'],abbreviation=t.get('abbreviation') or t['school'],color=t.get('color') or '#4b5960',logo=logo))
    payload=dict(as_of=timeline['as_of'],teams=assets,seasons=seasons,elo_model=elo['model'])
    output=(ROOT/'maps/circles-template.html').read_text()
    for token,file in [('__D3_JS__','assets/vendor/d3-7.9.0.min.js'),('__ALG_JS__','maps/circles-algorithms.js'),
                       ('__WORKER_JS__','maps/circles-worker.js'),('__PAGE_JS__','maps/circles.js')]:
        output=output.replace(token,(ROOT/file).read_text())
    output=output.replace('__DATA__',json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    output=output.replace('__THEME_CSS__',(ROOT/'maps/theme.css').read_text()).replace('__THEME_JS__',(ROOT/'maps/theme.js').read_text())
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/circles-of-suck.html').write_text(output)
    (ROOT/'data/circles_coverage.json').write_text(json.dumps(dict(as_of=timeline['as_of'],seasons=coverage),indent=2)+'\n')
    print(f'Built build/circles-of-suck.html: {len(assets)} team identities, {len(seasons)} seasons')

if __name__=='__main__':build()
