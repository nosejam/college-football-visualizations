"""Recompute game-by-game Elo and weekly team parameters from completed results."""
import gzip
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb.elo import MODEL,simulate


def build():
    source=ROOT/'data/imperialism_games.json.gz'
    games=json.loads(gzip.decompress(source.read_bytes()))
    timeline=json.loads((ROOT/'data/imperialism.json').read_text())
    ids={t['team_id'] for t in json.loads((ROOT/'data/teams.json').read_text())}
    ids.update(t['team_id'] for t in json.loads((ROOT/'data/sources/circles/team_manifest.json').read_text()))
    result=dict(model=MODEL,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),as_of=timeline['as_of'],seasons={})
    for year,season in timeline['seasons'].items():
        result['seasons'][year]=simulate(games[year],int(year),season['frames'],ids|set(season['roster']))
    path=ROOT/'data/team_elo.json.gz'
    path.write_bytes(gzip.compress(json.dumps(result,separators=(',',':')).encode(),mtime=0))
    print(f'Built {path.relative_to(ROOT)}: {sum(len(s["games"]) for s in result["seasons"].values())} game updates, {len(result["seasons"])} seasons',flush=True)

if __name__=='__main__':build()
