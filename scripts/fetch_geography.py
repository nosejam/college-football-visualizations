"""Refresh the public campus, county, and browser-library source archives."""
import datetime
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES={
 'data/sources/geography/HD2024.zip':'https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip',
 'data/sources/geography/HD2021.zip':'https://nces.ed.gov/ipeds/datacenter/data/HD2021.zip',
 'data/sources/geography/cb_2025_us_county_500k.zip':'https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip',
 'data/sources/geography/2025_Gaz_counties_national.zip':'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_counties_national.zip',
 'assets/vendor/plotly-3.3.0.min.js':'https://cdn.plot.ly/plotly-3.3.0.min.js',
 'assets/vendor/usa_110m.json':'https://cdn.plot.ly/un/usa_110m.json',
 'assets/vendor/d3-7.9.0.min.js':'https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js',
 'assets/vendor/plotly-LICENSE':'https://raw.githubusercontent.com/plotly/plotly.js/v3.3.0/LICENSE',
 'assets/vendor/d3-LICENSE':'https://raw.githubusercontent.com/d3/d3/v7.9.0/LICENSE',
 'assets/vendor/topojson-client-3.1.0.min.js':'https://cdn.jsdelivr.net/npm/topojson-client@3.1.0/dist/topojson-client.min.js',
 'assets/vendor/topojson-server-3.0.1.min.js':'https://cdn.jsdelivr.net/npm/topojson-server@3.0.1/dist/topojson-server.min.js',
 'assets/vendor/topojson-client-LICENSE':'https://raw.githubusercontent.com/topojson/topojson-client/v3.1.0/LICENSE',
 'assets/vendor/topojson-server-LICENSE':'https://raw.githubusercontent.com/topojson/topojson-server/v3.0.1/LICENSE',
}

def main(download=True):
    manifest=[]
    for filename,url in SOURCES.items():
        path=ROOT/filename
        path.parent.mkdir(parents=True,exist_ok=True)
        if download:
            with urllib.request.urlopen(url,timeout=60) as response: data=response.read()
            path.write_bytes(data)
        data=path.read_bytes()
        manifest.append(dict(file=filename,url=url,sha256=hashlib.sha256(data).hexdigest(),
            retrieved_at=datetime.datetime.fromtimestamp(path.stat().st_mtime,datetime.timezone.utc).isoformat()))
    (ROOT/'data/sources/geography/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Recorded {len(manifest)} sources')

if __name__=='__main__':
    import sys
    main(download='--record-existing' not in sys.argv)
