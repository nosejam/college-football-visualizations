"""Package only public static app files for GitHub Pages."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'index.html'
    if not source.exists():raise FileNotFoundError('Build index.html before packaging')
    html=source.read_text()
    if '__VIEWS__' in html or 'tab-predictor' not in html:raise ValueError('The app has not been fully built')
    destination=ROOT/'build/site';destination.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,destination/'index.html')
    (destination/'.nojekyll').write_text('')
    manifest=json.loads((ROOT/'data/sources/imperialism/manifest.json').read_text())
    version=dict(as_of=manifest['as_of'],default_tab='predictor',index_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    (destination/'version.json').write_text(json.dumps(version,indent=2)+'\n')
    print(f'Packaged {destination.relative_to(ROOT)}: app, .nojekyll, version.json')

if __name__=='__main__':main()
