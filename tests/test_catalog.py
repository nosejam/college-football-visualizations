import json
import struct
import unittest
import zlib
from cfb import ROOT, load_teams, logo_path, resolve_team

class CatalogTests(unittest.TestCase):
    def test_identity_and_aliases(self):
        for alias, ident in [('Alabama',333), ('UAB',5), ('Texas A&M',245), ('UTSA',2636),
                             ('Pitt',221), ('Miami (OH)',193), ('Miami',2390), ('San José State',23)]:
            with self.subTest(alias=alias):
                self.assertEqual(resolve_team(alias)['team_id'], ident)
                self.assertTrue(logo_path(alias).is_file())
        self.assertEqual(resolve_team(333), resolve_team('333'))
        with self.assertRaises(KeyError): resolve_team('invented team')
        with self.assertRaises(ValueError): resolve_team('SDSU')

    def test_catalog_integrity(self):
        teams = load_teams()
        self.assertEqual(len(teams), len({t['team_id'] for t in teams}))
        self.assertEqual(len(teams), len({t['slug'] for t in teams}))
        for t in teams:
            self.assertIn(t['logo'], t['logos'].values())
            for path in t['logos'].values():
                self.assertTrue((ROOT/path).is_file())
        assigned = [p for t in teams for p in t['logos'].values()]
        assigned += [c['logo'] for c in json.loads((ROOT/'data/conferences.json').read_text())]
        assigned += [c['file'] for c in json.loads((ROOT/'data/unmatched_logos.json').read_text())]
        actual = {p.relative_to(ROOT).as_posix() for p in (ROOT/'assets/logos').rglob('*.png')}
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), actual)

    def test_png_files_are_complete(self):
        for p in (ROOT/'assets/logos').rglob('*.png'):
            with self.subTest(path=p.name):
                data=p.read_bytes()
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                offset=8
                final=None
                while offset<len(data):
                    size=struct.unpack('>I',data[offset:offset+4])[0]
                    kind=data[offset+4:offset+8]
                    payload=data[offset+8:offset+8+size]
                    crc=struct.unpack('>I',data[offset+8+size:offset+12+size])[0]
                    self.assertEqual(zlib.crc32(kind+payload)&0xffffffff,crc)
                    offset+=size+12
                    final=kind
                self.assertEqual(final,b'IEND')
                self.assertEqual(offset,len(data))

if __name__=='__main__': unittest.main()
