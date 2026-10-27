"""Get 500px ESPN fallback logos for imperialism landholders absent from the FBS collection."""
import concurrent.futures
import datetime
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'data/imperialism.json').read_text())
    ids=set()
    for season in data['seasons'].values():
        ids.update(season['roster'])
        for frame in season['frames']:ids.update(frame['owners'])
    teams={t['team_id']:t for t in json.loads((ROOT/'data/teams.json').read_text())}
    destination=ROOT/'assets/imperialism/logos';destination.mkdir(parents=True,exist_ok=True)
    def fetch(ident):
        url=f'https://a.espncdn.com/i/teamlogos/ncaa/500/{ident}.png'
        path=destination/f'{ident}.png'
        try:
            with urllib.request.urlopen(url,timeout=30) as response:image=response.read()
            if not image.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Not a PNG')
            path.write_bytes(image)
            return dict(team_id=ident,url=url,file=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(image).hexdigest(),
                        retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        except Exception as error:return dict(team_id=ident,url=url,error=str(error))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,sorted(i for i in ids if 'fbs' not in teams[i]['logos'])))
    (ROOT/'data/sources/imperialism/logo_manifest.json').write_text(json.dumps(results,indent=2)+'\n')
    print(f'{len(results)} high-resolution fallback attempts; {sum("error" in r for r in results)} failures')
    for r in results:
        if 'error' in r:print(r)

if __name__=='__main__':main()
