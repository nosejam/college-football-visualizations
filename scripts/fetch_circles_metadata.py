"""Refresh supplemental ESPN identities absent from the original team catalog."""
import datetime,hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    output=ROOT/'data/sources/circles';output.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for ident in [292,2341,2698]:
        url=f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{ident}'
        with urllib.request.urlopen(url,timeout=30) as response:blob=response.read()
        team=json.loads(blob)['team'];path=output/f'team_{ident}.json';path.write_bytes(blob)
        manifest.append(dict(team_id=ident,school=team.get('location') or team['displayName'],abbreviation=team.get('abbreviation'),
            color='#'+(team.get('color') or '4b5960'),url=url,file=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(blob).hexdigest(),
            retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    (output/'team_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':main()
