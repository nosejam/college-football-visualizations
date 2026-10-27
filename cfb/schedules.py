"""Normalize ESPN schedules and safely merge them with the saved unified schedule."""
import datetime as dt

FIELDS=['season','week','season_type','start_date','completed','status','neutral_site','conference_game',
        'home_id','away_id','home_team','away_team','home_division','away_division','home_conference','away_conference']


def instant(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(dt.timezone.utc)


def signature(row):
    """Ignore source formatting, cosmetic provider fields, and placeholder future scores."""
    result=[]
    for key in FIELDS:
        value=row.get(key)
        if key=='start_date' and value:value=instant(value)
        if key=='status':
            text=str(value or '').upper()
            value='FINAL' if row.get('completed') else 'CANCELED' if 'CANCEL' in text else 'POSTPONED' if 'POSTPON' in text else 'SCHEDULED'
        result.append(value)
    result.extend([row.get('home_points'),row.get('away_points')] if row.get('completed') else [None,None])
    return tuple(result)


def metadata(rows):
    teams={}
    for row in rows:
        for side in ['home','away']:
            ident=row.get(side+'_id')
            if ident is None:continue
            item=teams.setdefault(ident,{})
            for name in ['team','division','conference','abbreviation']:
                value=row.get(side+'_'+name)
                if value is not None:item[name]=value
    return teams


def score(value):
    if isinstance(value,dict):value=value.get('value',value.get('displayValue'))
    if value is None or value=='':raise ValueError('A completed competition has no final score')
    return int(float(value))


def events(payload,year,teams,group=80,kind=2,as_of=None):
    """Convert team-schedule or scoreboard events; include future games and new postseason IDs."""
    result=[]
    for event in payload.get('events',[]):
        season=event.get('season',payload.get('season',{}))
        if int(season.get('year',year))!=year:continue
        event_type=event.get('seasonType',{})
        type_id=int(event_type.get('type',event_type.get('id',season.get('type',kind))))
        for comp in event.get('competitions',[]):
            competitors={t['homeAway']:t for t in comp.get('competitors',[]) if t.get('homeAway') in ['home','away']}
            if set(competitors)!={'home','away'}:continue
            status=comp.get('status',event.get('status',{})).get('type',{})
            date=comp.get('date',event.get('date'))
            if not date:raise ValueError('Missing competition date')
            complete=bool(status.get('completed')) and not any(word in str(status.get('name','')).upper() for word in ['CANCEL','POSTPON']) and (as_of is None or instant(date)<=as_of)
            row=dict(game_id=int(event['id']),season=year,season_type='postseason' if type_id==3 else 'regular',season_type_id=type_id,
                     start_date=instant(date).isoformat(),completed=complete,status=status.get('name','STATUS_SCHEDULED'),
                     week=event.get('week',payload.get('week',{})).get('number'))
            if 'neutralSite' in comp:row['neutral_site']=bool(comp['neutralSite'])
            if 'timeValid' in comp:row['start_time_tbd']=not comp['timeValid']
            for side,competitor in competitors.items():
                team=competitor['team'];ident=int(team['id'])
                if ident<=0:break
                known=teams.get(ident,{})
                row[side+'_id']=ident
                row[side+'_team']=known.get('team') or team.get('displayName') or team.get('name') or str(ident)
                row[side+'_division']=known.get('division') or {80:'fcs',81:'fcs',35:'ii',37:'iii'}.get(group,'fcs')
                if known.get('conference') is not None:row[side+'_conference']=known['conference']
                if known.get('abbreviation') or team.get('abbreviation'):row[side+'_abbreviation']=known.get('abbreviation') or team['abbreviation']
                if complete:row[side+'_points']=score(competitor.get('score'))
            if 'home_id' not in row or 'away_id' not in row:continue
            if row['home_id']==row['away_id']:raise ValueError('Schedule has a team playing itself')
            if 'conferenceCompetition' in comp:row['conference_game']=bool(comp['conferenceCompetition'])
            elif 'conferenceCompetition' in event:row['conference_game']=bool(event['conferenceCompetition'])
            if complete:
                row['home_winner']=row['home_points']>row['away_points'];row['away_winner']=row['away_points']>row['home_points'];row['status']='STATUS_FINAL'
            if 'venue' in comp:
                venue=comp['venue'];row['venue']=venue.get('fullName');row['venue_id']=int(venue['id']) if str(venue.get('id','')).isdigit() else None
            result.append(row)
    return result


def merge(saved,incoming,authoritative=False):
    """Never let a stale mirror un-finalize or replace an already verified result."""
    result=dict(saved)
    changed=set()
    for item in incoming:
        ident=int(item['game_id']);old=result.get(ident)
        if old and old.get('completed') and (not item.get('completed') or not authoritative):continue
        row={**(old or {}),**{k:v for k,v in item.items() if v is not None}}
        if not row.get('start_date') or row.get('home_id') is None or row.get('away_id') is None:raise ValueError(f'Incomplete schedule row {ident}')
        row.setdefault('neutral_site',False)
        row.setdefault('conference_game',bool(row.get('home_conference') and row.get('home_conference')==row.get('away_conference') and row.get('home_conference')!='FBS Independents'))
        row['fbs_game']=row.get('home_division')=='fbs' and row.get('away_division')=='fbs'
        row['fbs_participant']=row.get('home_division')=='fbs' or row.get('away_division')=='fbs'
        if row.get('completed'):
            row['home_points']=score(row.get('home_points'));row['away_points']=score(row.get('away_points'))
            row['home_winner']=row['home_points']>row['away_points'];row['away_winner']=row['away_points']>row['home_points']
        if old is None or signature(old)!=signature(row):result[ident]=row;changed.add(ident)
    return result,changed
