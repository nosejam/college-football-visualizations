"""Build the offline 2026 Elo playoff predictor, including remaining schedules."""
import base64
import gzip
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb.imperialism import football_week,timestamp


def build():
    rules=json.loads((ROOT/'data/sources/predictor/rules_2026.json').read_text())
    year=rules['season'];source=ROOT/f'data/sources/imperialism/schedules_{year}.parquet'
    raw=pq.read_table(source).to_pylist()
    timeline=json.loads((ROOT/'data/imperialism.json').read_text())
    elo=json.loads(gzip.decompress((ROOT/'data/team_elo.json.gz').read_bytes()))
    completed=json.loads(gzip.decompress((ROOT/'data/imperialism_games.json.gz').read_bytes()))[str(year)]
    actual={g['game_id']:g for g in completed}
    roster=timeline['seasons'][str(year)]['roster'];roster_set=set(roster)
    catalog={t['team_id']:t for t in json.loads((ROOT/'data/teams.json').read_text())}
    teams={};games=[];seen=set()
    for row in sorted(raw,key=lambda r:(timestamp(r['start_date']),r['game_id'])):
        if row['game_id'] in seen:continue
        seen.add(row['game_id'])
        if row['season_type']!='regular' or row['status'] in ['STATUS_CANCELED','STATUS_CANCELLED']:continue
        for side in ['home','away']:
            ident=row[side+'_id']
            teams.setdefault(ident,dict(id=ident,school=catalog.get(ident,{}).get('school',row[side+'_team']),conference=row[side+'_conference'] if ident in roster_set else None,fbs=ident in roster_set,logo=None))
        g=actual.get(row['game_id'])
        conference_flag=rules.get('conference_flag_overrides',{}).get(str(row['game_id']),{}).get('conference',row['conference_game'])
        games.append(dict(id=row['game_id'],date=g['date'] if g else row['start_date'],week=football_week(year,g['date'] if g else row['start_date']),
                          home=row['home_id'],away=row['away_id'],conference=bool(conference_flag and row['home_conference']==row['away_conference'] and row['home_id'] in roster_set and row['away_id'] in roster_set),
                          after_selection=timestamp(row['start_date'])>=timestamp(rules['selection_cutoff']),
                          championship=timestamp(rules['regular_end'])<=timestamp(row['start_date'])<timestamp(rules['selection_cutoff']) and row['home_id'] in roster_set and row['away_id'] in roster_set and row['home_conference']==row['away_conference'],
                          score=[g['home_points'],g['away_points']] if g else None))
    for ident in roster:
        assert ident in teams,f'Missing schedule for {ident}'
        t=catalog[ident];logo=ROOT/t['logo']
        fallback=ROOT/f'assets/imperialism/logos/{ident}.png'
        if 'fbs' not in t['logos'] and fallback.exists():logo=fallback
        teams[ident]['logo']='data:image/png;base64,'+base64.b64encode(logo.read_bytes()).decode()
    frames=[];e=elo['seasons'][str(year)]
    for frame,rating in zip(timeline['seasons'][str(year)]['frames'],e['frames']):
        values=dict(zip(e['team_ids'],rating['ratings']))
        records={ident:dict(wins=0,losses=0,ties=0) for ident in roster}
        for g in completed:
            if frame['week'] is None or football_week(year,g['date'])>frame['week']:continue
            for side,other in [('home','away'),('away','home')]:
                ident=g[side+'_id']
                if ident in records:
                    records[ident]['wins' if g[side+'_points']>g[other+'_points'] else 'losses' if g[side+'_points']<g[other+'_points'] else 'ties']+=1
        frames.append(dict(week=frame['week'],label=frame['label'],date=frame['date'],records=records,elo={ident:values.get(ident,1500) for ident in teams}))
    payload=dict(year=year,as_of=timeline['as_of'],rules=rules,teams=list(teams.values()),roster=roster,games=games,frames=frames)
    output=(ROOT/'maps/predictor-template.html').read_text()
    for marker,file in [('__THEME_CSS__','maps/theme.css'),('__THEME_JS__','maps/theme.js'),('__MODEL_JS__','maps/predictor-model.js'),('__WORKER_JS__','maps/predictor-worker.js'),('__PAGE_JS__','maps/predictor.js')]:
        output=output.replace(marker,(ROOT/file).read_text())
    output=output.replace('__DATA__',json.dumps(payload,separators=(',',':')).replace('</','<\\/'))
    (ROOT/'build').mkdir(exist_ok=True);(ROOT/'build/playoff-predictor.html').write_text(output)
    report=dict(season=year,as_of=timeline['as_of'],fbs_teams=len(roster),games=len(games),conferences=dict(Counter(t['conference'] for t in teams.values() if t['fbs'])),schedule_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),rules=rules)
    (ROOT/'data/predictor_coverage.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Built build/playoff-predictor.html: {len(roster)} FBS teams, {len(games)} known scheduled games')

if __name__=='__main__':build()
