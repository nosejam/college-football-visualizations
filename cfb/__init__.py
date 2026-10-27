"""Resolve team names and provider IDs to local logo paths."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def normalize(name):
    value = unicodedata.normalize('NFKD', str(name)).encode('ascii', 'ignore').decode().casefold()
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()

def load_teams():
    return json.loads((ROOT/'data/teams.json').read_text())

def resolve_team(name_or_id):
    teams = load_teams()
    if isinstance(name_or_id, int) or str(name_or_id).isdigit():
        matches = [t for t in teams if t['team_id']==int(name_or_id)]
    else:
        key = normalize(name_or_id)
        matches = [t for t in teams if key in {normalize(a) for a in t['aliases']+[t['slug']]}]
    if not matches:
        raise KeyError(f'Unknown team: {name_or_id!r}')
    if len(matches)>1:
        raise ValueError(f'Ambiguous team {name_or_id!r}: '+', '.join(t['school'] for t in matches))
    return matches[0]

def logo_path(name_or_id, source=None):
    team = resolve_team(name_or_id)
    return ROOT / (team['logos'][source] if source else team['logo'])

def load_season_records(team=None, season=None):
    """Load 2016–2025 FBS records, optionally filtered by team name/ID and season."""
    records = json.loads((ROOT/'data/season_records.json').read_text())
    ident = resolve_team(team)['team_id'] if team is not None else None
    return [r for r in records if (ident is None or r['team_id']==ident)
            and (season is None or r['season']==int(season))]

def load_school_locations():
    """Return main-campus coordinates and source metadata for all catalog schools."""
    return json.loads((ROOT/'data/school_locations.json').read_text())
