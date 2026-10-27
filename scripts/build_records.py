"""Build FBS season records from archived ESPN standings, audit against schedules."""
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb import load_teams
SOURCES=ROOT/'data/sources/records'

def entries(node, conference=None):
    if node.get('isConference'):
        conference=node['name']
    for entry in node.get('standings',{}).get('entries',[]):
        yield conference,entry
    for child in node.get('children',[]):
        yield from entries(child,conference)

def record(stats,kind):
    # name='wins' is repeated for home, away, conference, ranked opponents, etc.
    matches=[s for s in stats if s['type']==kind]
    if not matches:
        return None
    if len(matches)!=1:
        raise ValueError(f'Duplicate record type {kind}')
    summary=matches[0].get('summary',matches[0].get('displayValue',''))
    parts=[int(x) for x in summary.split('-')]
    if len(parts)==2: parts.append(0)
    if len(parts)!=3: raise ValueError(f'Invalid record {summary}')
    return parts

def schedule_records(year):
    results=defaultdict(Counter)
    fbs=set()
    seen=set()
    has_postseason=False
    with gzip.open(SOURCES/f'schedules_{year}.csv.gz','rt') as f:
        for g in csv.DictReader(f):
            assert int(g['season'])==year
            assert g['game_id'] not in seen, f'Duplicate game {g["game_id"]}'
            seen.add(g['game_id'])
            has_postseason |= g['season_type']=='postseason'
            for side in ['home','away']:
                if g[f'{side}_division']=='fbs': fbs.add(int(g[f'{side}_id']))
            if g['completed'].upper()!='TRUE': continue
            if g['home_points'] in ('','NA') or g['away_points'] in ('','NA'): continue
            hp,ap=float(g['home_points']),float(g['away_points'])
            for side,own,opponent in [('home',hp,ap),('away',ap,hp)]:
                ident=int(g[f'{side}_id'])
                outcome='wins' if own>opponent else 'losses' if own<opponent else 'ties'
                results[ident][outcome]+=1
    return results,fbs,has_postseason

def build():
    catalog={t['team_id']:t for t in load_teams()}
    adjustments=json.loads((SOURCES/'adjustments.json').read_text())
    rows=[]
    coverage=[]
    differences=[]
    missing=[]
    for year in range(2016,2026):
        with gzip.open(SOURCES/f'standings_{year}.json.gz','rt') as f: payload=json.load(f)
        assert payload['season']['year']==year
        schedule,fbs,has_postseason=schedule_records(year)
        ids=set()
        year_entries=list(entries(payload))
        present={int(e['team']['id']) for _,e in year_entries}
        for a in adjustments:
            if a['season']==year and a['team_id'] not in present:
                year_entries.append((a['conference'],dict(team=dict(id=a['team_id'],location=catalog[a['team_id']]['school']),stats=[])))
        for conference,e in year_entries:
            ident=int(e['team']['id'])
            assert ident not in ids, f'Duplicate standings team {year}/{ident}'
            ids.add(ident)
            overall=record(e['stats'],'total')
            adjustment=next((a for a in adjustments if a['season']==year and a['team_id']==ident),None)
            if adjustment:
                overall=[adjustment[k] for k in ['wins','losses','ties']]
            assert overall is not None
            wins,losses,ties=overall
            conf=record(e['stats'],'vsconf')
            t=catalog.get(ident)
            if t is None: raise ValueError(f'No catalog identity for {ident}: {e["team"]}')
            row=dict(season=year,team_id=ident,school=t['school'],source_school=e['team']['location'],
                     conference=conference or 'FBS Independents',classification='fbs',
                     status=adjustment['status'] if adjustment else 'played',
                     record_source='school_adjustment' if adjustment else 'espn_standings',
                     source_url=adjustment['source_url'] if adjustment else f'https://site.api.espn.com/apis/v2/sports/football/college-football/standings?season={year}',
                     wins=wins,losses=losses,ties=ties,
                     games=wins+losses+ties,win_pct=round((wins+ties/2)/(wins+losses+ties),6) if wins+losses+ties else None,
                     conference_wins=conf[0] if conf else None,conference_losses=conf[1] if conf else None,
                     conference_ties=conf[2] if conf else None,logo=t['logo'],logo_source='fbs' if 'fbs' in t['logos'] else 'cfbd')
            rows.append(row)
            counted=[schedule[ident][k] for k in ['wins','losses','ties']]
            if counted!=overall:
                differences.append(dict(season=year,team_id=ident,school=t['school'],record=overall,schedule=counted,
                    reason='Spring games absent from schedule archive' if adjustment else 'Schedule archive omits postseason' if not has_postseason else 'Unresolved'))
        if fbs-ids:
            missing.extend(dict(season=year,team_id=i,school=catalog.get(i,{}).get('school')) for i in sorted(fbs-ids))
        coverage.append(dict(season=year,teams=len(ids),schedule_fbs_teams=len(fbs),schedule_includes_postseason=has_postseason,
                             missing_from_standings=sorted(fbs-ids),missing_from_schedule=sorted(ids-fbs)))
    rows.sort(key=lambda r:(r['season'],r['team_id']))
    def save(name,obj): (ROOT/'data'/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
    save('season_records.json',rows)
    with (ROOT/'data/season_records.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    totals=[]
    for ident in sorted({r['team_id'] for r in rows}):
        seasons=[r for r in rows if r['team_id']==ident]
        first=seasons[0]
        w,l,t=(sum(r[k] for r in seasons) for k in ['wins','losses','ties'])
        totals.append(dict(team_id=ident,school=first['school'],seasons=len(seasons),seasons_played=sum(r['games']>0 for r in seasons),first_season=seasons[0]['season'],
                           last_season=seasons[-1]['season'],wins=w,losses=l,ties=t,games=w+l+t,
                           win_pct=round((w+t/2)/(w+l+t),6) if w+l+t else None,logo=first['logo']))
    save('decade_records.json',totals)
    with (ROOT/'data/decade_records.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(totals[0]));writer.writeheader();writer.writerows(totals)
    save('records_coverage.json',dict(scope='FBS membership in each season, 2016–2025; overall records include postseason',
          seasons=coverage,standings_schedule_differences=differences,missing_records=missing,
          teams_using_cfbd_logos=sorted({r['school'] for r in rows if r['logo_source']=='cfbd'})))
    print(f'{len(rows)} season records; {len(totals)} teams; {len(differences)} standings/schedule differences; {len(missing)} missing records')
    print(json.dumps(coverage,indent=2))

if __name__=='__main__': build()
