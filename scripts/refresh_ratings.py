"""Explicit SP+ refresh: one authenticated request per season, at most weekly unless --force.
No key is copied to datasets, HTML, logs, or exception text. Failed refreshes preserve the last valid file.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb.ratings import parse, status


def refresh(year, force=False):
    folder=ROOT/'data/sources/ratings'; folder.mkdir(exist_ok=True)
    path=folder/f'sp_{year}.json'
    saved=json.loads(path.read_text()) if path.exists() else None
    if not force and status(saved,year)=='valid' and (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(saved['retrieved_at'])).days<7:
        print('SP+ snapshot is less than seven days old; no API request.'); return False
    key=os.environ.get('CFBD_API_KEY')
    if not key:
        print('CFBD_API_KEY unavailable; preserving cached SP+ or using explicit Elo fallback.'); return False
    catalog=json.loads((ROOT/'data/teams.json').read_text())
    roster=json.loads((ROOT/'data/imperialism.json').read_text())['seasons'][str(year)]['roster']
    alias_path=folder/'aliases.json'; overrides=json.loads(alias_path.read_text()) if alias_path.exists() else {}
    request=urllib.request.Request(f'https://api.collegefootballdata.com/ratings/sp?year={year}',headers={'Authorization':'Bearer '+key,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=40) as response:
            raw=response.read(); usage=response.headers.get('X-CallLimit-Remaining')
        payload=json.loads(raw)
        if isinstance(payload,list):
            seasons=sorted({str(row.get('year')) for row in payload if isinstance(row,dict)})
            print(f'SP+ response: {len(payload)} rows; seasons {seasons}.')
        snapshot=parse(payload,year,catalog,roster,overrides)
        # A partial provider response must not replace a more complete cached snapshot.
        if saved and snapshot['coverage']['matched']<saved['coverage']['matched']:
            raise ValueError('Coverage regressed')
        if snapshot['coverage']['matched']<len(roster)*.8:
            raise ValueError('Insufficient FBS coverage')
        snapshot['response_sha256']=hashlib.sha256(raw).hexdigest()
        snapshot['api_calls_remaining']=usage
    except urllib.error.HTTPError as error:
        print(f'SP+ refresh failed (HTTP {error.code}); last snapshot preserved.'); return False
    except (urllib.error.URLError,TimeoutError,ValueError) as error:
        reason=str(error) if isinstance(error,ValueError) else type(error).__name__
        print(f'SP+ refresh failed: {reason}; last snapshot preserved.'); return False
    archive=folder/'snapshots'/str(year); archive.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.fromisoformat(snapshot['retrieved_at']).strftime('%Y%m%dT%H%M%SZ')
    content=json.dumps(snapshot,indent=2,allow_nan=False)+'\n'
    (archive/f'{stamp}.json').write_text(content)
    temp=path.with_suffix('.pending'); temp.write_text(content); temp.replace(path)
    print(f'Saved SP+ {year}: {snapshot["coverage"]["matched"]}/{len(roster)} FBS teams; {len(snapshot["coverage"]["unmatched_names"])} unmatched names.'); return True

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--year',type=int,default=2026); parser.add_argument('--force',action='store_true')
    args=parser.parse_args(); refresh(args.year,args.force)
