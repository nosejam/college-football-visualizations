"""Season-local, zero-sum win/loss Elo with no home-field or score-margin adjustment."""
from cfb.imperialism import football_week, timestamp

INITIAL_RATING=1500.0
K_FACTOR=32.0
SCALE=400.0
MODEL=dict(name='Season win/loss Elo',initial_rating=INITIAL_RATING,k_factor=K_FACTOR,
           scale=SCALE,season_reset=True,home_advantage=0,margin_adjustment=False,
           order='kickoff UTC, then game_id',precision='Full precision for updates; 3 decimals in saved data',
           reference='https://www.stat.cmu.edu/cmsac/football/2-elo-intro.html')


def update(home,away,home_points,away_points):
    expected=1/(1+10**((away-home)/SCALE))
    actual=1.0 if home_points>away_points else 0.0 if home_points<away_points else .5
    change=K_FACTOR*(actual-expected)
    return home+change,away-change


def simulate(games,season,frames,team_ids=()):
    """Return every game's pre/post ratings and week-end snapshots, without future results."""
    games=sorted(games,key=lambda g:(timestamp(g['date']),g['game_id']))
    ids=sorted(set(team_ids)|{g[s+'_id'] for g in games for s in ['home','away']})
    ratings=dict.fromkeys(ids,INITIAL_RATING)
    ledger=[];snapshots=[];cursor=0
    def saved():return [round(ratings[ident],3) for ident in ids]
    seen=set()
    for frame in frames:
        week=frame['week']
        while week is not None and cursor<len(games) and football_week(season,games[cursor]['date'])<=week:
            game=games[cursor];ident=game['game_id']
            if ident in seen:raise ValueError(f'Duplicate Elo game {ident}')
            seen.add(ident)
            home,away=game['home_id'],game['away_id']
            if home==away:raise ValueError('A team cannot play itself')
            before=[ratings[home],ratings[away]]
            after=update(*before,game['home_points'],game['away_points'])
            ratings[home],ratings[away]=after
            ledger.append(dict(game_id=ident,date=game['date'],week=football_week(season,game['date']),
                               home_id=home,away_id=away,before=[round(r,3) for r in before],after=[round(r,3) for r in after]))
            cursor+=1
        snapshots.append(dict(week=week,ratings=saved()))
    if cursor!=len(games):raise ValueError('Elo timeline does not cover every completed game')
    return dict(team_ids=ids,games=ledger,frames=snapshots)
