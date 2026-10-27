"""Rebuild the catalog from checked-in source data and logos (no dependencies)."""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cfb import normalize

# Explicit filename aliases where the upstream spelling differs from CFBD.
FILENAME_NAMES = {
    'Alabama Birmingham Blazers': 'UAB',
    'FIU Panthers': 'Florida International',
    'Hawaii Rainbow Warriors': "Hawai'i",
    'Southern Miss Golden Eagles': 'Southern Mississippi',
    'Army West Point Black Knights': 'Army',
    'Louisiana Lafayette Ragin Cajuns': 'Louisiana',
    'Louisiana Monroe Warhawks': 'Louisiana Monroe',
    'Miami OH Redhawks': 'Miami (OH)',
    'Middle Tennessee Blue Raiders': 'Middle Tennessee',
    'North Carolina State Wolfpack': 'NC State',
    'Pitt Panthers': 'Pittsburgh',
    'Sam Houston State Bearkats': 'Sam Houston State',
    'SMU Mustang': 'SMU',
    'Texas AM University': 'Texas A&M',
    'Texas SA Roadrunners': 'UT San Antonio',
    'UMass Amherst Minutemen': 'UMass',
}
# Supplemental identities verified against ESPN's team endpoint; keep provider separate.
EXTRA = {
    2019: ('Allen', 'Yellow Jackets', 'ALN'),
    2206: ('Edward Waters', 'Tigers', 'EAU'),
    110243: ('UT Permian Basin', 'Falcons', 'UTPB'),
    110254: ('Davenport', 'Panthers', 'DAV'),
    124180: ('Bluefield State University', 'Big Blue', 'BLST'),
}

def build():
    teams = {}
    with (ROOT / 'data/sources/cfbd_teams_snapshot.csv').open(encoding='latin-1', newline='') as f:
        rows = csv.reader(f)
        header = next(rows)
        for row in rows:
            assert len(row) == len(header) + 1, 'Unexpected snapshot layout'
            r = dict(zip(header, row[1:]))
            ident = int(float(r['team_id']))
            school = r['school']
            aliases = {school, f"{school} {r['mascot']}"}
            aliases.update(r[k] for k in ('abbreviation', 'alt_name1', 'alt_name2', 'alt_name3') if r[k] != 'NA')
            teams[ident] = dict(team_id=ident, school=school, mascot=r['mascot'], abbreviation=r['abbreviation'],
                aliases=sorted(aliases), color=None if r['color']=='NA' else r['color'],
                alternate_color=None if r['alt_color']=='NA' else r['alt_color'],
                identity_source='cfbd_snapshot', logos={})
    for ident, (school, mascot, abbr) in EXTRA.items():
        teams[ident] = dict(team_id=ident, school=school, mascot=mascot, abbreviation=abbr,
            aliases=[school, school+' '+mascot, abbr], color=None, alternate_color=None,
            identity_source='espn', logos={})
    unmatched = []
    for p in sorted((ROOT / 'assets/logos/cfbd').glob('*.png')):
        if int(p.stem) in teams:
            teams[int(p.stem)]['logos']['cfbd'] = p.relative_to(ROOT).as_posix()
        else:
            unmatched.append(dict(source='cfbd', file=p.relative_to(ROOT).as_posix(), reason='Unknown team ID'))
    conferences = []
    for p in sorted((ROOT / 'assets/logos/fbs').glob('*.png')):
        name = re.sub(r'(?:[_-]logo)?-300x300$', '', p.stem, flags=re.I)
        name = re.sub('[_-]', ' ', name)
        if 'Conference' in name or name in ('Pac 12', 'Big Ten', 'Big 12', 'Division I FBS Independents'):
            conferences.append(dict(name=name, logo=p.relative_to(ROOT).as_posix()))
            continue
        key = normalize(FILENAME_NAMES.get(name, name))
        candidates = [t for t in teams.values() if key == normalize(t['school'])]
        if not candidates:
            candidates = [t for t in teams.values() if key in {normalize(a) for a in t['aliases']}]
        if len(candidates) != 1:
            unmatched.append(dict(source='fbs', file=p.relative_to(ROOT).as_posix(), name=name, reason=f'{len(candidates)} identity matches'))
            continue
        t = candidates[0]
        assert 'fbs' not in t['logos'], f'Duplicate logo for {t["school"]}'
        t['logos']['fbs'] = p.relative_to(ROOT).as_posix()
        t['aliases'] = sorted(set(t['aliases'] + [name]))
    selected = sorted((t for t in teams.values() if t['logos']), key=lambda t:t['team_id'])
    for t in selected:
        t['logo'] = t['logos'].get('fbs', t['logos'].get('cfbd'))
        t['slug'] = re.sub(r'[^a-z0-9]+', '-', normalize(t['school'])).strip('-')
    def save(name, data):
        (ROOT / 'data' / name).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')
    save('teams.json', selected)
    save('conferences.json', conferences)
    save('unmatched_logos.json', unmatched)
    with (ROOT/'data/teams.csv').open('w', newline='') as f:
        fields=['team_id','school','slug','mascot','abbreviation','color','alternate_color','logo','cfbd_logo','fbs_logo','aliases','identity_source']
        writer=csv.DictWriter(f, fieldnames=fields);writer.writeheader()
        for t in selected:
            writer.writerow({**{k:t[k] for k in fields if k in t},'aliases':'|'.join(t['aliases']), 'cfbd_logo':t['logos'].get('cfbd',''),'fbs_logo':t['logos'].get('fbs','')})
    print(f'{len(selected)} teams; {len(conferences)} conference/group logos; {len(unmatched)} unmatched')
    for item in unmatched: print(item)

if __name__ == '__main__':
    build()
