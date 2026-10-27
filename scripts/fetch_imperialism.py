"""Archive complete unified schedules, including bowls and playoffs, for imperialism."""
import concurrent.futures
import datetime
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'data/sources/imperialism'

def fetch(year):
    url=f'https://raw.githubusercontent.com/sportsdataverse/cfbfastR-cfb-data/main/cfb/cfb_schedules/parquet/cfb_schedules_{year}.parquet'
    path=DEST/f'schedules_{year}.parquet'
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url,timeout=60) as response:data=response.read()
            break
        except Exception:
            if attempt==2:raise
            time.sleep(attempt+1)
    path.write_bytes(data)
    return dict(season=year,url=url,file=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),
                retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        sources=list(pool.map(fetch,range(2016,2027)))
    manifest=dict(as_of=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=sources)
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Downloaded {len(sources)} season schedules')

if __name__=='__main__':main()
