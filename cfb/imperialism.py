"""Deterministic, county-conserving football imperialism simulation."""
import datetime as dt
from collections import Counter
from zoneinfo import ZoneInfo

EASTERN=ZoneInfo('America/New_York')

def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z','+00:00'))

def football_week(season,date):
    """Week 1 contains Labor Day weekend; weeks run Tuesday–Monday."""
    first=dt.date(season,9,1)
    labor_day=first+dt.timedelta(days=(0-first.weekday())%7)
    saturday=labor_day-dt.timedelta(days=2)
    start=saturday-dt.timedelta(days=4)
    date=timestamp(date).astimezone(EASTERN).date() if isinstance(date,str) else date
    return (date-start).days//7+1

def transfer(owners,winner,loser):
    """Mutate original-territory ownership; a landless winner can reclaim land."""
    captured=[seed for seed,owner in owners.items() if owner==loser]
    for seed in captured:owners[seed]=winner
    return captured

def simulate(initial,county_counts,games,season):
    owners={seed:seed for seed in initial}
    frames=[dict(week=None,label='Preseason',date=None,owners=[owners[s] for s in initial],events=[],games=0)]
    grouped={}
    for g in sorted(games,key=lambda g:(g['date'],g['game_id'])):
        grouped.setdefault(football_week(season,g['date']),[]).append(g)
    for week,battles in sorted(grouped.items()):
        events=[]
        for g in battles:
            if g['home_points']==g['away_points']:continue
            winner=g['home_id'] if g['home_points']>g['away_points'] else g['away_id']
            loser=g['away_id'] if winner==g['home_id'] else g['home_id']
            seeds=transfer(owners,winner,loser)
            if seeds:
                events.append(dict(game_id=g['game_id'],date=g['date'],winner=winner,loser=loser,
                    winner_points=max(g['home_points'],g['away_points']),loser_points=min(g['home_points'],g['away_points']),
                    territories=seeds,counties=sum(county_counts[s] for s in seeds)))
        last=battles[-1]['date']
        label=f'Week {week}'
        if timestamp(last).month<=6:label+=' · Spring' if timestamp(last).month>=2 else ' · Postseason'
        elif any(g['season_type']=='postseason' for g in battles):label+=' · Postseason'
        frames.append(dict(week=week,label=label,date=last,owners=[owners[s] for s in initial],events=events,games=len(battles)))
    return frames
