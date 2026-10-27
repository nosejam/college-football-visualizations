import csv
import hashlib
import json
import math
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(name):return json.loads((ROOT/'data'/name).read_text())

class GeographyTests(unittest.TestCase):
    def test_all_catalog_schools_have_coordinates(self):
        teams=read('teams.json');locs=read('school_locations.json')
        self.assertEqual(len(locs),452)
        self.assertEqual({t['team_id'] for t in teams},{r['team_id'] for r in locs})
        self.assertEqual(len(locs),len({r['team_id'] for r in locs}))
        for r in locs:
            self.assertTrue(-90<=r['latitude']<=90)
            self.assertTrue(-180<=r['longitude']<=180)
            self.assertEqual(r['location_kind'],'main_campus')
            self.assertTrue(r['source_url'].startswith('https://'))
        byid={r['team_id']:r for r in locs}
        # Catch same-name institutions, branch-campus confusion, and stadium proxies.
        for ident,lat,lon in [(251,30.286,-97.740),(9,33.42,-111.93),(25,37.87,-122.26),
                              (26,34.07,-118.44),(2390,25.72,-80.28),(62,21.30,-157.82)]:
            self.assertAlmostEqual(byid[ident]['latitude'],lat,delta=.03)
            self.assertAlmostEqual(byid[ident]['longitude'],lon,delta=.03)

    def test_county_coverage_and_nearest_team(self):
        assignments=read('county_assignments.json')
        self.assertEqual(len(assignments),3144)
        self.assertEqual(len({r['fips'] for r in assignments}),3144)
        self.assertEqual(len({r['state'] for r in assignments}),51)
        self.assertEqual(sum(r['state']=='CT' for r in assignments),9)
        self.assertEqual(sum(r['state']=='DC' for r in assignments),1)
        team_ids={r['team_id'] for r in read('season_records.json') if r['season']==2025}
        locs={r['team_id']:r for r in read('school_locations.json') if r['team_id'] in team_ids}
        teams={t['team_id']:t for t in read('teams.json')}
        def dist(a,b):
            la,lb=math.radians(a['latitude']),math.radians(b['latitude'])
            h=math.sin((lb-la)/2)**2+math.cos(la)*math.cos(lb)*math.sin(math.radians(b['longitude']-a['longitude'])/2)**2
            return 6371.0088*2*math.asin(math.sqrt(min(1,h)))
        for row in assignments:
            expected=min(locs,key=lambda i:(dist(row,locs[i]),i))
            self.assertEqual(row['team_id'],expected)
            self.assertEqual(row['color'],teams[expected]['color'])
            self.assertAlmostEqual(row['distance_km'],dist(row,locs[expected]),delta=.00051)
        with (ROOT/'data/county_assignments.csv').open() as f:
            self.assertEqual([r['fips'] for r in csv.DictReader(f)],[r['fips'] for r in assignments])

    def test_source_integrity(self):
        for source in read('sources/geography/manifest.json'):
            self.assertEqual(hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest(),source['sha256'])

    def test_region_geometry_and_logo_exceptions(self):
        try:
            from shapely.geometry import Point,shape
            from shapely.ops import unary_union
        except ImportError:
            self.skipTest('Install requirements.txt for geometric validation')
        counties=read('counties.geojson')['features']
        regions={int(f['id']):shape(f['geometry']) for f in read('team_regions.geojson')['features']}
        locations={r['team_id']:r for r in read('school_locations.json')}
        report=read('map_coverage.json')
        exceptions={r['team_id']:r for r in report['logo_exceptions']}
        self.assertEqual(len(exceptions),8)
        self.assertEqual(exceptions[2390]['reason'],'no_counties')
        groups={i:[] for i in regions}
        for county in counties:groups[county['properties']['team_id']].append(shape(county['geometry']))
        for ident,region in regions.items():
            self.assertTrue(region.is_valid)
            self.assertLess(region.symmetric_difference(unary_union(groups[ident])).area,1e-10)
            loc=locations[ident]
            inside=region.covers(Point(loc['longitude'],loc['latitude']))
            self.assertEqual(inside,ident not in exceptions)

if __name__=='__main__':unittest.main()
