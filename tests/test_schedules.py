import datetime as dt
import unittest
from cfb.schedules import events,merge,metadata,signature


def row(**extra):
    return dict(game_id=1,season=2026,week=8,season_type='regular',season_type_id=2,start_date='2026-10-24T19:30:00Z',
                completed=False,status='STATUS_SCHEDULED',neutral_site=False,conference_game=False,
                home_id=1,away_id=2,home_team='Home',away_team='Away',home_division='fbs',away_division='fbs',home_conference='ACC',away_conference='SEC',**extra)


def payload(complete=False,game_id=1,home_score=None,away_score=None,kind=2):
    competitors=[dict(homeAway='home',team=dict(id='1',displayName='Home')),dict(homeAway='away',team=dict(id='2',displayName='Away'))]
    if home_score is not None:competitors[0]['score']=home_score
    if away_score is not None:competitors[1]['score']=away_score
    return dict(events=[dict(id=str(game_id),season=dict(year=2026),seasonType=dict(type=kind),week=dict(number=8),competitions=[dict(date='2026-10-24T19:30Z',neutralSite=False,status=dict(type=dict(completed=complete,name='STATUS_FINAL' if complete else 'STATUS_SCHEDULED')),competitors=competitors)])])

class ScheduleTests(unittest.TestCase):
    def test_kickoff_updates_cancellations_and_new_playoff_games(self):
        initial=row();saved={1:initial}
        changed={**initial,'start_date':'2026-10-24T23:30:00Z'}
        saved,ids=merge(saved,[changed],authoritative=True)
        self.assertEqual(ids,{1});self.assertEqual(saved[1]['start_date'],changed['start_date'])
        canceled={**saved[1],'status':'STATUS_CANCELED'}
        saved,ids=merge(saved,[canceled],authoritative=True);self.assertEqual(ids,{1})
        added=events(payload(True,2,{'value':31},'17',kind=3),2026,metadata([initial]))
        saved,ids=merge(saved,added,authoritative=True)
        self.assertEqual(ids,{2});self.assertEqual(saved[2]['season_type'],'postseason')
        self.assertEqual(saved[2]['home_points'],31);self.assertEqual(saved[2]['away_points'],17)
        self.assertTrue(saved[2]['fbs_participant'])

    def test_preserve_finals_against_stale_sources_but_accept_live_corrections(self):
        final={**row(),'completed':True,'home_points':21,'away_points':10,'status':'STATUS_FINAL'}
        saved,ids=merge({1:final},[row()],authoritative=True)
        self.assertEqual(ids,set());self.assertEqual(saved[1]['home_points'],21)
        wrong={**final,'home_points':7}
        self.assertEqual(merge(saved,[wrong])[1],set())
        result,ids=merge(saved,[wrong],authoritative=True)
        self.assertEqual(ids,{1});self.assertEqual(result[1]['home_points'],7)
        self.assertFalse(result[1]['home_winner'])

    def test_noop_formatting_and_placeholder_scores(self):
        a={**row(),'home_points':0,'away_points':0};b={**a,'start_date':'2026-10-24T19:30:00+00:00','status':'scheduled','home_points':None,'away_points':None}
        self.assertEqual(signature(a),signature(b));self.assertEqual(merge({1:a},[b],True)[1],set())
        metadata_only={**a,'venue':'Other venue','home_rank':1}
        self.assertEqual(merge({1:a},[metadata_only],True)[1],set())

    def test_score_validation_and_no_future_results(self):
        known=metadata([row()])
        with self.assertRaises(ValueError):events(payload(True),2026,known)
        future=events(payload(True,home_score='31',away_score='17'),2026,known,as_of=dt.datetime(2026,10,23,tzinfo=dt.timezone.utc))
        self.assertFalse(future[0]['completed']);self.assertNotIn('home_points',future[0])
        self.assertEqual(events(payload(True,home_score=31,away_score=17),2025,known),[])
        with self.assertRaises(ValueError):merge({},[{'game_id':1}],True)

if __name__=='__main__':unittest.main()
