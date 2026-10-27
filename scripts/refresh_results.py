"""Download current schedules and results, then rebuild all three offline views."""
import argparse
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb.schedules import events,instant,merge,metadata


def download(spec):
    for attempt in range(3):
        try:
            request=urllib.request.Request(spec['url'],headers={'User-Agent':'CollegeFootballVisualizations/1.0'})
            with urllib.request.urlopen(request,timeout=40) as response:raw=response.read()
            return spec,raw
        except (urllib.error.URLError,TimeoutError):
            if attempt==2:raise
            time.sleep(attempt+1)


def build(manifest,path):
    subprocess.run([sys.executable,str(ROOT/'scripts/build.py')],cwd=ROOT,check=True)
    manifest.pop('build_pending',None)
    path.write_text(json.dumps(manifest,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force-build',action='store_true',help='Rebuild the app even if the schedule is unchanged')
    args=parser.parse_args()
    src=ROOT/'data/sources/imperialism';manifest_path=src/'manifest.json'
    manifest=json.loads(manifest_path.read_text());now=dt.datetime.now(dt.timezone.utc)
    year=max(source['season'] for source in manifest['sources'])
    path=src/f'schedules_{year}.parquet';table=pq.read_table(path);rows={r['game_id']:r for r in table.to_pylist()}
    original=dict(rows);inputs=[]
    # The mirror supplies complete all-division metadata; ESPN supplies current schedules and corrections.
    mirror=dict(name='upstream.parquet',url=f'https://raw.githubusercontent.com/sportsdataverse/cfbfastR-cfb-data/main/cfb/cfb_schedules/parquet/cfb_schedules_{year}.parquet')
    try:
        spec,raw=download(mirror);fresh=pq.ParquetFile(pa.BufferReader(raw)).read().to_pylist()
        fresh=[r for r in fresh if r.get('season')==year]
        for row in fresh:
            if row.get('completed') and (row.get('home_points') is None or row.get('away_points') is None or instant(row['start_date'])>now):row['completed']=False
        rows,_=merge(rows,fresh);inputs.append((spec,raw))
    except (urllib.error.URLError,TimeoutError) as error:
        print(f'Unified mirror unavailable; using saved metadata and live ESPN feeds: {type(error).__name__}',flush=True)
    teams=metadata(rows.values())
    fbs=sorted(ident for ident,t in teams.items() if t.get('division')=='fbs')
    specs=[dict(name=f'team-{ident}-{kind}.json.gz',group=80,kind=kind,url=f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{ident}/schedule?season={year}&seasontype={kind}') for ident in fbs for kind in [2,3]]
    latest=max((instant(r['start_date']) for r in original.values() if r.get('completed')),default=now-dt.timedelta(days=7))
    start=max((latest-dt.timedelta(days=2)).date(),now.date()-dt.timedelta(days=14))
    dates=[start+dt.timedelta(days=i) for i in range(max(0,(now.date()-start).days+1))]
    for day in dates:
        for group in [80,81,35,37]:
            specs.append(dict(name=f'scores-{day:%Y%m%d}-{group}.json.gz',group=group,kind=2,url=f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates={day:%Y%m%d}&groups={group}&limit=500'))
    print(f'Refreshing {len(fbs)} FBS team schedules (regular + postseason) and {len(dates)} days of all-division results',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for index,(spec,raw) in enumerate(pool.map(download,specs),1):
            payload=json.loads(raw)
            if spec['name'].startswith('scores-') and len(payload.get('events',[]))>=500:raise ValueError('Scoreboard may be truncated')
            updates=events(payload,year,teams,group=spec['group'],kind=spec['kind'],as_of=now)
            rows,_=merge(rows,updates,authoritative=True);inputs.append((spec,raw))
            if index%50==0:print(f'Fetched {index}/{len(specs)} ESPN feeds',flush=True)
    # Only meaningful row changes count; raw endpoint timestamps do not create daily commits.
    from cfb.schedules import signature
    changed=[ident for ident,row in rows.items() if ident not in original or signature(original[ident])!=signature(row)]
    if not changed:
        print('No schedule or completed-result changes; saved inputs unchanged.',flush=True)
        if args.force_build or manifest.get('build_pending'):build(manifest,manifest_path)
        return
    archive=src/'updates'/now.strftime('%Y%m%dT%H%M%SZ');archive.mkdir(parents=True,exist_ok=False)
    sources=[]
    for spec,raw in inputs:
        saved=gzip.compress(raw,mtime=0) if spec['name'].endswith('.gz') else raw
        dest=archive/spec['name'];dest.write_bytes(saved)
        sources.append(dict(url=spec['url'],file=str(dest.relative_to(ROOT)),sha256=hashlib.sha256(saved).hexdigest()))
    old=archive/'base.parquet';old.write_bytes(path.read_bytes())
    temp=path.with_suffix('.pending.parquet')
    ordered=sorted(rows.values(),key=lambda r:(instant(r['start_date']),r['game_id']))
    pq.write_table(pa.Table.from_pylist(ordered,schema=table.schema),temp)
    for source in manifest['sources']:
        if source['season']==year:
            base={key:source[key] for key in ['url','sha256','retrieved_at']};base['file']=str(old.relative_to(ROOT))
            source.update(sha256=hashlib.sha256(temp.read_bytes()).hexdigest(),retrieved_at=now.isoformat(),format='merged_parquet',base=base,updates=sources)
    manifest['as_of']=now.isoformat();manifest['build_pending']=True
    temp.replace(path);manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Updated {len(changed)} scheduled/completed games ({sum(ident not in original for ident in changed)} newly announced). Rebuilding…',flush=True)
    build(manifest,manifest_path)

if __name__=='__main__':main()
