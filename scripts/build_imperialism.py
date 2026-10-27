"""Compile season-by-season land transfers and an offline interactive Plotly map."""
import base64
import datetime as dt
import gzip
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter,defaultdict
from pathlib import Path

import pyarrow.parquet as pq
from shapely.geometry import shape
from shapely.ops import unary_union,polylabel

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb import load_teams,load_school_locations
from cfb.imperialism import simulate,timestamp
from scripts.build_geography import haversine

SRC=ROOT/'data/sources/imperialism'

def load_games(year,as_of):
    rows=pq.read_table(SRC/f'schedules_{year}.parquet').to_pylist()
    roster={g[s+'_id'] for g in rows for s in ['home','away'] if g[s+'_division']=='fbs'}
    result={}
    for g in rows:
        if g['season_type'] not in ['regular','postseason','spring_regular','spring_postseason']:continue
        if not g['completed'] or g['home_points'] is None or g['away_points'] is None:continue
        if timestamp(g['start_date'])>as_of:continue
        # Canonical UTC format ensures correct kickoff ordering across source formats.
        date=timestamp(g['start_date']).astimezone(dt.timezone.utc).isoformat()
        game=dict(game_id=g['game_id'],date=date,home_id=g['home_id'],away_id=g['away_id'],
            home_points=g['home_points'],away_points=g['away_points'],season_type=g['season_type'])
        if game['game_id'] in result and result[game['game_id']]!=game:raise ValueError('Conflicting duplicate game')
        result[game['game_id']]=game
    return sorted(roster),list(result.values()),rows

def build():
    manifest=json.loads((SRC/'manifest.json').read_text())
    as_of=timestamp(manifest['as_of'])
    teams={t['team_id']:t for t in load_teams()}
    locations={t['team_id']:t for t in load_school_locations()}
    counties=json.loads((ROOT/'data/counties.geojson').read_text())
    original_geometries=[shape(f['geometry']) for f in counties['features']]
    schools_by_season={}
    records=json.loads((ROOT/'data/season_records.json').read_text())
    for row in records:schools_by_season.setdefault(row['season'],set()).add(row['team_id'])
    all_games={};seasons={};coverage=[];used_teams=set();roster_cache={}
    for year in range(2016,2027):
        derived,games,raw=load_games(year,as_of)
        ids=sorted(schools_by_season.get(year,set(derived)))
        assert set(derived)<=set(ids),f'Unexpected FBS roster for {year}'
        # Historical records retain canceled COVID-season members in the starting map.
        key=tuple(ids)
        if key not in roster_cache:
            assignments=[]
            for f in counties['features']:
                p=f['properties']
                winner=min(ids,key=lambda ident:(haversine(p['latitude'],p['longitude'],locations[ident]['latitude'],locations[ident]['longitude']),ident))
                assignments.append(winner)
            counts=Counter(assignments)
            seeds=sorted(counts)
            anchors=[]
            for ident in seeds:
                for region in ['conus','AK','HI']:
                    parts=[original_geometries[i] for i,owner in enumerate(assignments) if owner==ident and
                        ('AK' if counties['features'][i]['properties']['state']=='AK' else 'HI' if counties['features'][i]['properties']['state']=='HI' else 'conus')==region]
                    if not parts:continue
                    union=unary_union(parts)
                    polygons=[union] if union.geom_type=='Polygon' else list(union.geoms)
                    main=max(polygons,key=lambda p:p.area)
                    anchor=polylabel(main,tolerance=.003)
                    anchors.append(dict(seed=ident,part=region,longitude=anchor.x,latitude=anchor.y))
            roster_cache[key]=dict(roster=ids,seeds=seeds,assignments=assignments,anchors=anchors,counts=dict(counts))
        geography=roster_cache[key]
        frames=simulate(geography['seeds'],geography['counts'],games,year)
        used_teams.update(ids)
        raiders=set()
        for frame in frames:
            for event in frame['events']:
                used_teams.update([event['winner'],event['loser']])
                if event['winner'] not in ids:raiders.add(event['winner'])
        unknown=used_teams-set(teams)
        assert not unknown,f'Unmapped landholders: {unknown}'
        seasons[str(year)]=dict(geography=list(roster_cache).index(key),frames=frames,roster=ids)
        all_games[str(year)]=games
        # Independent record audit of FBS games, including postseason.
        counted=defaultdict(Counter)
        for g in games:
            for side,other in [('home','away'),('away','home')]:
                outcome='wins' if g[side+'_points']>g[other+'_points'] else 'losses' if g[side+'_points']<g[other+'_points'] else 'ties'
                counted[g[side+'_id']][outcome]+=1
        differences=[]
        for r in records:
            if r['season']==year and any(counted[r['team_id']][k]!=r[k] for k in ['wins','losses','ties']):
                differences.append(dict(team_id=r['team_id'],school=r['school'],standings=[r[k] for k in ['wins','losses','ties']],
                    schedule=[counted[r['team_id']][k] for k in ['wins','losses','ties']]))
        coverage.append(dict(season=year,fbs_teams=len(ids),games=len(games),frames=len(frames),last_result=max(g['date'] for g in games),
            transfers=sum(len(f['events']) for f in frames),raiders=sorted(raiders),record_differences=differences))
        print(year,'games',len(games),'transfers',coverage[-1]['transfers'],'raiders',len(raiders),'record differences',len(differences),flush=True)
    def save(name,obj,pretty=True):
        (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2 if pretty else None,separators=None if pretty else (',',':'))+'\n')
    save('data/imperialism_coverage.json',dict(as_of=manifest['as_of'],seasons=coverage))
    payload=dict(as_of=manifest['as_of'],seasons=seasons,geographies=list(roster_cache.values()),county_ids=[f['id'] for f in counties['features']])
    save('data/imperialism.json',payload,pretty=False)
    (ROOT/'data/imperialism_games.json.gz').write_bytes(gzip.compress(json.dumps(all_games,separators=(',',':')).encode(),mtime=0))
    # Keep only needed metadata and logos in the browser payload.
    browser_teams=[]
    for ident in sorted(used_teams):
        t=teams[ident]
        fallback=ROOT/f'assets/imperialism/logos/{ident}.png'
        logo=(ROOT/t['logos']['fbs']) if 'fbs' in t['logos'] else fallback if fallback.exists() else (ROOT/t['logo'])
        browser_teams.append(dict(team_id=ident,school=t['school'],color=t['color'] or '#4b5960',
            logo_data='data:image/png;base64,'+base64.b64encode(logo.read_bytes()).decode()))
    subprocess.run(['node',str(ROOT/'scripts/build_county_topology.cjs')],cwd=ROOT,check=True)
    topology=json.loads((ROOT/'data/counties.topojson').read_text())
    payload.update(teams=browser_teams,topology=topology)
    template=(ROOT/'maps/imperialism-template.html').read_text()
    for marker,path in [('__PLOTLY_JS__','assets/vendor/plotly-3.3.0.min.js'),('__D3_JS__','assets/vendor/d3-7.9.0.min.js'),
                        ('__TOPOJSON_JS__','assets/vendor/topojson-client-3.1.0.min.js'),('__MAP_JS__','maps/imperialism.js')]:
        template=template.replace(marker,(ROOT/path).read_text())
    template=template.replace('__TOPOJSON__',(ROOT/'assets/vendor/usa_110m.json').read_text())
    template=template.replace('__MAP_DATA__',json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    template=template.replace('__THEME_CSS__',(ROOT/'maps/theme.css').read_text()).replace('__THEME_JS__',(ROOT/'maps/theme.js').read_text())
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/imperialism.html').write_text(template)
    print('Built build/imperialism.html',flush=True)

if __name__=='__main__':build()
