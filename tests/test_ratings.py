import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from cfb.ratings import parse, status
ROOT=Path(__file__).resolve().parents[1]

class RatingsTests(unittest.TestCase):
    catalog=[dict(team_id=1,school='Alpha',aliases=['Alpha State']),dict(team_id=2,school='Beta',aliases=[])]
    rows=[dict(year=2026,team='Alpha State',rating=20.5,offense={'rating':40},defense={'rating':20},specialTeams={'rating':.5})]
    def test_mapping_components_and_missing(self):
        s=parse(self.rows,2026,self.catalog,[1,2]);self.assertEqual(s['ratings']['1']['rating'],20.5)
        self.assertEqual(s['coverage']['missing_ids'],[2]);self.assertEqual(s['ratings']['1']['defense'],{'rating':20})
        self.assertEqual(status(s,2026),'valid');self.assertNotIn('2',s['ratings'])
    def test_alias_and_ambiguous_names(self):
        s=parse([dict(year=2026,team='A',rating=4)],2026,self.catalog,[1],{'A':1});self.assertEqual(s['coverage']['matched'],1)
        with self.assertRaises(ValueError):parse(self.rows,2026,self.catalog+[dict(team_id=3,school='Alpha State')],[1])
    def test_invalid_scale_and_seasons(self):
        for value in [None,float('nan'),float('inf'),True,200]:
            with self.assertRaises(ValueError):parse([{**self.rows[0],'rating':value}],2026,self.catalog,[1])
        with self.assertRaises(ValueError):parse(self.rows,2025,self.catalog,[1])
        with self.assertRaises(ValueError):parse({'message':'unauthorized'},2026,self.catalog,[1])
        s=parse(self.rows,2026,self.catalog,[1]);s['scale']={};self.assertEqual(status(s,2026),'invalid')
    def test_stale_and_expired(self):
        s=parse(self.rows,2026,self.catalog,[1],retrieved_at='2026-09-01T00:00:00+00:00')
        self.assertEqual(status(s,2026,dt.datetime(2026,9,12,tzinfo=dt.timezone.utc)),'stale');self.assertEqual(status(s,2025),'missing')
    def test_refresh_errors_preserve_snapshot_and_limit_calls(self):
        spec=importlib.util.spec_from_file_location('refresh_ratings',ROOT/'scripts/refresh_ratings.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'data/sources/ratings';folder.mkdir(parents=True)
            (root/'data/teams.json').write_text(json.dumps(self.catalog));(root/'data/imperialism.json').write_text(json.dumps({'seasons':{'2026':{'roster':[1]}}}))
            s=parse(self.rows,2026,self.catalog,[1]);path=folder/'sp_2026.json';content=json.dumps(s);path.write_text(content)
            with patch.object(module,'ROOT',root),patch.dict(module.os.environ,{'CFBD_API_KEY':'test-secret'}):
                with patch.object(module.urllib.request,'urlopen') as request:
                    self.assertFalse(module.refresh(2026));request.assert_not_called()
                for code in [401,403,429,500]:
                    with patch.object(module.urllib.request,'urlopen',side_effect=urllib.error.HTTPError('redacted',code,'error',{},None)) as request:
                        self.assertFalse(module.refresh(2026,True));self.assertEqual(path.read_text(),content);self.assertEqual(request.call_count,1)
                with patch.object(module.urllib.request,'urlopen') as request:
                    request.return_value.__enter__.return_value.read.return_value=b'not json'
                    self.assertFalse(module.refresh(2026,True));self.assertEqual(path.read_text(),content)
    def test_credential_normalization_and_redaction(self):
        import contextlib
        import io
        spec=importlib.util.spec_from_file_location('refresh_ratings',ROOT/'scripts/refresh_ratings.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data/sources/ratings').mkdir(parents=True)
            (root/'data/teams.json').write_text(json.dumps(self.catalog));(root/'data/imperialism.json').write_text(json.dumps({'seasons':{'2026':{'roster':[1]}}}))
            with patch.object(module,'ROOT',root),patch.dict(module.os.environ,{'CFBD_API_KEY':'  Bearer test-secret\n'}):
                with patch.object(module.urllib.request,'urlopen') as request:
                    response=request.return_value.__enter__.return_value;response.read.return_value=json.dumps(self.rows).encode();response.headers={}
                    self.assertTrue(module.refresh(2026,True));self.assertEqual(request.call_args.args[0].get_header('Authorization'),'Bearer test-secret')
                output=io.StringIO()
                with patch.object(module.urllib.request,'urlopen',side_effect=ValueError('invalid header test-secret')),contextlib.redirect_stdout(output):
                    self.assertFalse(module.refresh(2026,True))
                self.assertNotIn('test-secret',output.getvalue())
                with patch.dict(module.os.environ,{'CFBD_API_KEY':'test\nsecret'}),patch.object(module.urllib.request,'urlopen') as request:
                    self.assertFalse(module.refresh(2026,True));request.assert_not_called()
    def test_point_scale_consistency(self):
        bad={**self.rows[0],'rating':80}
        with self.assertRaisesRegex(ValueError,'point-scale'):parse([bad],2026,self.catalog,[1])
    def test_explicit_app_state_and_aggregate(self):
        catalog=[dict(team_id=2026,school='Appalachian State',aliases=[])]
        rows=[dict(year=2026,team='App State',rating=-5),dict(year=2026,team='nationalAverages',rating=None)]
        s=parse(rows,2026,catalog,[2026],{'App State':2026})
        self.assertEqual(s['coverage']['matched'],1);self.assertEqual(s['coverage']['unmatched_names'],[])
        self.assertEqual(s['coverage']['ignored_aggregate_names'],['nationalAverages'])
