"""Download historical ESPN FBS standings and CFBD-derived schedules for auditing."""
import concurrent.futures
import datetime
import gzip
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'data/sources/records'

def fetch(item):
    year,kind=item
    url=(f'https://site.api.espn.com/apis/v2/sports/football/college-football/standings?season={year}' if kind=='standings' else
         f'https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/schedules/csv/cfb_schedules_{year}.csv')
    suffix='json' if kind=='standings' else 'csv'
    path=DEST/f'{kind}_{year}.{suffix}.gz'
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=60) as response: data=response.read()
            break
        except Exception:
            if attempt==2: raise
            time.sleep(attempt+1)
    if kind=='standings':
        payload=json.loads(data)
        if payload.get('season',{}).get('year') != year:
            raise ValueError(f'Unexpected ESPN season: {payload.get("season")}')
    path.write_bytes(gzip.compress(data,mtime=0))
    return dict(season=year,kind=kind,url=url,file=path.relative_to(ROOT).as_posix(),
                retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256=hashlib.sha256(data).hexdigest())

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,[(y,k) for y in range(2016,2026) for k in ['standings','schedules']]))
    (DEST/'manifest.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f'Downloaded {len(results)} source files')

if __name__=='__main__': main()
