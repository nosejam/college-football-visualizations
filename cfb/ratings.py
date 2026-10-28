"""Validated CFBD SP+ snapshots. Network authentication stays in the refresh script."""
import datetime as dt
import math

class SnapshotError(ValueError):
    """Safe public validation reason; never contains credentials or request headers."""

MAX_AGE_DAYS = 10
SCALE = dict(unit='points relative to an average FBS team on a neutral field', verified=True,
             source='https://www.espn.com/college-football/story/_/id/45842676/college-football-2025-breakthrough-bounce-back-teams')


def aliases(catalog, overrides=None):
    result = {}
    for team in catalog:
        for name in [team['school'], *team.get('aliases', [])]:
            key = name.casefold().strip()
            result.setdefault(key, set()).add(team['team_id'])
    for name, ident in (overrides or {}).items():
        result[name.casefold().strip()] = {ident}
    return result


def parse(payload, year, catalog, roster, overrides=None, retrieved_at=None):
    if not isinstance(payload, list) or not payload:
        raise SnapshotError('SP+ response must be a nonempty array')
    lookup = aliases(catalog, overrides); ratings = {}; unmatched = []; invalid = []
    for row in payload:
        if not isinstance(row, dict) or row.get('year') != year:
            raise SnapshotError('Unexpected SP+ season or response schema')
        name = row.get('team', ''); matches = lookup.get(name.casefold().strip(), set())
        if len(matches) != 1:
            unmatched.append(name); continue
        ident = next(iter(matches)); value = row.get('rating')
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or abs(value) > 100:
            invalid.append(name); continue
        if str(ident) in ratings:
            raise SnapshotError(f'Duplicate SP+ identity: {ident}')
        # Store source components without interpreting defensive scales as net ratings.
        ratings[str(ident)] = dict(rating=value, source_team=name, ranking=row.get('ranking'),
                                  offense=row.get('offense'), defense=row.get('defense'), specialTeams=row.get('specialTeams'))
    missing = sorted(set(roster) - {int(i) for i in ratings})
    if not ratings or invalid:
        raise SnapshotError(f'Invalid SP+ ratings: {len(invalid)} invalid rows; {len(ratings)} mapped')
    return dict(schema=1, source='CFBD /ratings/sp', season=year,
                retrieved_at=retrieved_at or dt.datetime.now(dt.timezone.utc).isoformat(),
                scale=SCALE, ratings=ratings,
                coverage=dict(expected=len(roster), matched=len(set(roster) - set(missing)), missing_ids=missing, unmatched_names=unmatched),
                historical_week_snapshots=False)


def status(snapshot, year, now=None):
    if not snapshot or snapshot.get('season') != year:
        return 'missing'
    try:
        age = ((now or dt.datetime.now(dt.timezone.utc)) - dt.datetime.fromisoformat(snapshot['retrieved_at'])).total_seconds() / 86400
        if age < -1: return 'invalid'
        if not snapshot.get('scale', {}).get('verified') or not snapshot.get('ratings'): return 'invalid'
        for row in snapshot['ratings'].values():
            if not isinstance(row.get('rating'), (int,float)) or not math.isfinite(row['rating']) or abs(row['rating'])>100:return 'invalid'
        return 'stale' if age > MAX_AGE_DAYS else 'valid'
    except (KeyError, ValueError, TypeError):
        return 'invalid'
