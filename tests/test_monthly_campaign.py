import unittest

from campaign import Campaign
from moonpa_month import MONTH_ENDS
from moonpa_savegame import create_save, load_save


class MonthlyCampaignTests(unittest.TestCase):
    def ready(self):
        game=Campaign(23,interactive=True)
        game.phase='ready'
        return game

    def test_month_reconciles_actual_weeks_and_growth(self):
        game=self.ready()
        game.world.facilities[game.guild.gid]['estate']=5
        baseline=load_save(create_save(game))
        assignment=dict(mission_orders=[],group_mode=True)
        weekly=[]
        for week in range(1,5):
            baseline.submit_week(1,week,assignment)
            weekly.append(baseline.week_report)
            baseline.advance_phase('report')
        game.submit_month(1,1,assignment)
        report=game.week_report
        self.assertEqual((game.week,game.phase,report['month'],report['end_week']),(5,'report',1,4))
        self.assertEqual(report['cash'],baseline.guild.cash)
        self.assertEqual(report['cash_change'],sum(r['cash_change'] for r in weekly))
        self.assertEqual(report['income']-report['expenses'],report['cash_change'])
        self.assertEqual(sum(e['amount'] for e in report['entries'] if e['category']=='estate_income'),305*4)
        self.assertEqual(sum(e['amount'] for e in report['entries'] if e['category']=='facility_upkeep'),-40*4)
        for member in report['members']:
            actual=sum(f['ca_change'] for w in weekly for f in w['members'] if f['id']==member['id'])
            self.assertAlmostEqual(member['ca_change'],actual,places=3)
        self.assertEqual(load_save(create_save(game)).week_report,report)

    def test_assigned_mission_repeats_and_tactical_battle_survives_save(self):
        game=self.ready()
        card=game.income_mission_board()[0]
        roster=[f.fid for f in game.guild.fighters if not f.injured]
        zone=next(z for z in game.overview()['zones'] if z['selectable'] and z['owner'] is None)
        assignment=dict(group_mode=True,mission_orders=[dict(id=card['id'],members=roster[:3])],
                        attack=dict(zone=zone['id'],setup=[dict(id=fid) for fid in roster[3:11]]))
        game.submit_month(1,1,assignment)
        self.assertEqual(game.phase,'group')
        game=load_save(create_save(game))
        match=game.group_play
        game.finish_group(match['match'],dict(winner=0,events=[],units=[
            dict(id=f['id'],side=0,hp=100,max_hp=100,actions=0,hit_taken=0,healing=0) for f in match['team']]))
        game.continue_month()
        self.assertEqual(game.phase,'report')
        self.assertTrue(game.week_report['battle']['success'])
        self.assertGreater(len(game.week_report['missions']),1)
        self.assertEqual(game.week_report['missions'][0]['week'],1)
        self.assertLessEqual(len(game.week_report['missions']),4)
        self.assertEqual(game.week,5)

    def test_twelve_month_boundaries_keep_season_rollover(self):
        game=self.ready()
        game.world.money.credit(game.guild,25000,'test_calendar_funds')
        for month,end in enumerate(MONTH_ENDS,1):
            game.submit_month(1,game.week,dict(mission_orders=[]))
            self.assertEqual((game.week_report['month'],game.week_report['end_week']),(month,end))
            self.assertEqual((game.season,game.week),(1,end+1) if month<12 else (2,1))
            self.assertEqual(sum(row['gross'] for row in game.week_report['territories']),
                sum(e['amount'] for e in game.week_report['entries'] if e['category']=='territory_gross'))
            game.advance_phase('report')
        self.assertEqual(game.phase,'draft')

    def test_old_save_starts_from_current_internal_week(self):
        game=self.ready()
        game.week=3
        del game.month_run
        # The previous format has no month field in its metadata or object.
        from moonpa_savegame import Encoder, FORMAT, VERSION
        import base64, hashlib, json, zlib
        raw=json.dumps(Encoder().encode(game),ensure_ascii=False).encode('utf-8')
        envelope=dict(format=FORMAT,version=VERSION,meta=dict(guild=game.guild.name,
            seed=game.seed,season=game.season,week=game.week,phase=game.phase),
            checksum=hashlib.sha256(raw).hexdigest(),data=base64.b64encode(zlib.compress(raw)).decode())
        restored=load_save(envelope)
        restored.submit_month(1,3,dict(mission_orders=[]))
        self.assertEqual((restored.week_report['week'],restored.week_report['end_week'],restored.week),(3,4,5))
