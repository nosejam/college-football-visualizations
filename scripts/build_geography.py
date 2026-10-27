"""Build campus locations, nearest-team county regions, and a standalone map."""
import base64
import csv
import io
import json
import math
import sys
import zipfile
from collections import Counter,defaultdict
from pathlib import Path

import shapefile
from shapely import make_valid, coverage_simplify
from shapely.geometry import shape, mapping, Point
from shapely.geometry.polygon import orient
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from cfb import load_teams
SRC=ROOT/'data/sources/geography'
# Fifty states + DC; exclude territories from the US Albers map.
STATE_CODES={f'{i:02d}' for i in [1,2,4,5,6,8,9,10,11,12,13,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,44,45,46,47,48,49,50,51,53,54,55,56]}

def save(name,data,pretty=True):
    (ROOT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2 if pretty else None,separators=None if pretty else (',',':'))+'\n')

def write_csv(name,rows):
    with (ROOT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def haversine(lat1,lon1,lat2,lon2):
    a,b=math.radians(lat1),math.radians(lat2)
    h=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371.0088*2*math.asin(math.sqrt(min(1,h)))

def locations():
    directories={}
    for year,encoding in [(2024,'utf-8-sig'),(2021,'cp1252')]:
        with zipfile.ZipFile(SRC/f'HD{year}.zip') as z:
            rows=csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]),encoding=encoding))
            directories[year]={int(r['UNITID']):r for r in rows}
    matches={r['team_id']:r for r in json.loads((SRC/'team_institutions.json').read_text())}
    overrides={r['team_id']:r for r in json.loads((SRC/'location_overrides.json').read_text())}
    result=[]
    for t in load_teams():
        ident=t['team_id']
        if ident in overrides:
            o=overrides[ident]
            result.append(dict(team_id=ident,school=t['school'],institution=o['institution'],unitid=None,
                 latitude=o['latitude'],longitude=o['longitude'],city=o['city'],state=o['state'],country=o['country'],
                 location_kind='main_campus',source_year=None,source_url=o['source_url']))
            continue
        match=matches[ident];year=match['directory_year'];r=directories[year][match['unitid']]
        assert r['INSTNM']==match['institution']
        lat,lon=float(r['LATITUDE']),float(r['LONGITUD'])
        assert 18<lat<72 and -180<lon<-60, f'Invalid US campus location: {t["school"]}'
        result.append(dict(team_id=ident,school=t['school'],institution=r['INSTNM'],unitid=int(r['UNITID']),
             latitude=lat,longitude=lon,city=r['CITY'],state=r['STABBR'],country='US',location_kind='main_campus',
             source_year=year,source_url=f'https://nces.ed.gov/ipeds/datacenter/data/HD{year}.zip'))
    save('data/school_locations.json',result)
    write_csv('data/school_locations.csv',result)
    return result

def oriented(geometry):
    # D3 uses clockwise exterior rings; GeoJSON/Shapely normally use CCW.
    if geometry.geom_type=='Polygon':return mapping(orient(geometry,sign=-1))
    if geometry.geom_type=='MultiPolygon':
        return dict(type='MultiPolygon',coordinates=[mapping(orient(p,sign=-1))['coordinates'] for p in geometry.geoms])
    polygons=[g for g in geometry.geoms if g.geom_type in ['Polygon','MultiPolygon']]
    return oriented(unary_union(polygons))

def build():
    all_locations=locations()
    locs={r['team_id']:r for r in all_locations}
    records=json.loads((ROOT/'data/season_records.json').read_text())
    ids={r['team_id'] for r in records if r['season']==2025}
    roster=[{**t,**locs[t['team_id']]} for t in load_teams() if t['team_id'] in ids]
    roster.sort(key=lambda t:t['team_id'])
    with zipfile.ZipFile(SRC/'2025_Gaz_counties_national.zip') as z:
        gaz={r['GEOID']:r for r in csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]),encoding='utf-8-sig'),delimiter='|')}
    stem='cb_2025_us_county_500k'
    features=[];assignments=[];regions=defaultdict(list)
    raw_counties=[]
    with zipfile.ZipFile(SRC/(stem+'.zip')) as z:
        reader=shapefile.Reader(shp=z.open(stem+'.shp'),shx=z.open(stem+'.shx'),dbf=z.open(stem+'.dbf'))
        for item in reader.iterShapeRecords():
            r=item.record.as_dict()
            if r['STATEFP'] in STATE_CODES:
                raw_counties.append((r,make_valid(shape(item.shape.__geo_interface__))))
    # Simplify shared edges together, avoiding artificial seams/holes inside unions.
    geometries=coverage_simplify([geometry for _,geometry in raw_counties],0.003)
    for (r,_),geometry in zip(raw_counties,geometries):
        g=gaz[r['GEOID']]
        lat,lon=float(g['INTPTLAT']),float(g['INTPTLONG'])
        nearest=min(roster,key=lambda t:(haversine(lat,lon,t['latitude'],t['longitude']),t['team_id']))
        distance=haversine(lat,lon,nearest['latitude'],nearest['longitude'])
        regions[nearest['team_id']].append(geometry)
        p=dict(fips=r['GEOID'],name=r['NAMELSAD'],state=r['STUSPS'],latitude=lat,longitude=lon,
               team_id=nearest['team_id'],school=nearest['school'],distance_km=round(distance,3),color=nearest['color'])
        assignments.append(p)
        features.append(dict(type='Feature',id=r['GEOID'],properties=p,geometry=oriented(geometry)))
    features.sort(key=lambda f:f['id']);assignments.sort(key=lambda r:r['fips'])
    region_features=[];exceptions=[]
    counts=Counter(a['team_id'] for a in assignments)
    for t in roster:
        parts=regions[t['team_id']]
        region=unary_union(parts) if parts else None
        inside=bool(region is not None and region.covers(Point(t['longitude'],t['latitude'])))
        reason=None if inside else 'no_counties' if not parts else 'campus_outside_region'
        if reason:exceptions.append(dict(team_id=t['team_id'],school=t['school'],reason=reason,counties=counts[t['team_id']]))
        t['county_count']=counts[t['team_id']];t['logo_fits_at_campus']=inside;t['logo_exception']=reason
        t['logo_data']='data:image/png;base64,'+base64.b64encode((ROOT/t['logo']).read_bytes()).decode()
        if region is not None:
            region_features.append(dict(type='Feature',id=t['team_id'],properties=dict(school=t['school']),geometry=oriented(region)))
    data=dict(season=2025,county_vintage=2025,teams=roster,counties=dict(type='FeatureCollection',features=features),
              regions=dict(type='FeatureCollection',features=region_features),logo_exceptions=exceptions)
    save('data/county_assignments.json',assignments)
    write_csv('data/county_assignments.csv',assignments)
    save('data/counties.geojson',data['counties'],pretty=False)
    save('data/team_regions.geojson',data['regions'],pretty=False)
    save('data/map_coverage.json',dict(schools=len(all_locations),mapped_teams=len(roster),counties=len(features),
        states=len({r['state'] for r in assignments}),logo_exceptions=exceptions,
        distance_method='Haversine great-circle distance from Census county internal reference point to IPEDS main-campus point.',
        campus_source_years=dict(Counter(str(r['source_year']) for r in all_locations))))
    template=(ROOT/'maps/template.html').read_text()
    for marker,path in [('__PLOTLY_JS__','assets/vendor/plotly-3.3.0.min.js'),('__D3_JS__','assets/vendor/d3-7.9.0.min.js'),('__MAP_JS__','maps/map.js')]:
        template=template.replace(marker,(ROOT/path).read_text())
    template=template.replace('__TOPOJSON__',(ROOT/'assets/vendor/usa_110m.json').read_text())
    template=template.replace('__MAP_DATA__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/'))
    (ROOT/'build').mkdir(exist_ok=True)
    (ROOT/'build/closest-teams.html').write_text(template)
    print(f'{len(all_locations)} campus coordinates; {len(roster)} FBS teams; {len(features)} counties; {len(exceptions)} logo exceptions')
    for r in exceptions:print(r)

if __name__=='__main__':build()
