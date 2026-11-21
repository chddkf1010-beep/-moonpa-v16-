import unittest

from campaign import Campaign
from moonpa_savegame import create_save, load_save


class WeeklyCampaignTest(unittest.TestCase):
    def setUp(self):
        self.game = Campaign(23)
        state = self.game.overview()
        self.team = [dict(id=f['id'], row='front' if f['role_id'] in (0, 1) else 'back',
                          skills=f['skills']) for f in state['roster'] if f['recommended']]
        self.zone = next(z['id'] for z in state['zones'] if z['owner'] is None and z['selectable'])

    def test_capture_then_income_and_no_double_settlement(self):
        g = self.game
        g.submit_week(1, 1, dict(attack=dict(zone=self.zone, setup=self.team)))
        self.assertEqual(g.week, 1)
        self.assertIsNone(g.week_report)
        self.assertTrue(g.overview()['week_pending'])
        with self.assertRaises(ValueError):
            g.submit_week(1, 1, {})
        g.step(finish=True, style='pressure')
        self.assertTrue(g.result['success'])
        self.assertEqual(g.week, 2)
        self.assertEqual(g.apply(),g.result)
        receipt = next(x for x in g.week_report['territories'] if x['zone']==self.zone)
        self.assertEqual(receipt['days'],3)
        transaction_count = g.world.money.transactions
        with self.assertRaises(ValueError):
            g.submit_week(1, 1, {})
        self.assertEqual(g.world.money.transactions,transaction_count)
        g.submit_week(1, 2, {})
        self.assertEqual(g.week,3)
        report = g.week_report
        receipt = next(x for x in report['territories'] if x['zone']==self.zone)
        self.assertEqual(receipt['days'],7)
        self.assertGreater(receipt['gross'],0)
        self.assertEqual(sum(t['gross'] for t in report['territories']),
                         sum(e['amount'] for e in report['entries'] if e['category']=='territory_gross'))
        self.assertEqual(report['income']-report['expenses'],report['cash_change'])

    def test_invalid_assignment_does_not_mutate_week(self):
        g = self.game
        fid = self.team[0]['id']
        cash = g.guild.cash
        with self.assertRaises(ValueError):
            g.submit_week(1,1,dict(training=[fid],rest=[fid]))
        g.guild.fighters[0].injured = 2
        with self.assertRaises(ValueError):
            g.submit_week(1,1,dict(training=[g.guild.fighters[0].fid]))
        self.assertEqual((g.week,g.guild.cash),(1,cash))

    def test_mission_training_and_recovery_without_battle(self):
        g = self.game
        f = g.guild.fighters
        f[4].fatigue = 65
        g.submit_week(1,1,dict(missions=[[x.fid for x in f[:3]]],training=[f[3].fid],rest=[f[4].fid]))
        report = g.week_report
        self.assertIsNone(report['battle'])
        self.assertTrue(report['missions'][0]['funded'])
        self.assertTrue(any(e['category']=='mission_gross_reward' for e in report['entries']))
        self.assertGreater(next(x['ca_change'] for x in report['members'] if x['id']==f[3].fid),0)
        self.assertEqual(f[4].fatigue,17)

    def test_defense_budget_and_report_survive_reload(self):
        g = self.game
        g.interactive = True
        zone = g.world.zones[self.zone]
        zone.owner = g.guild.gid
        ids = [f['id'] for f in self.team]
        defense = dict(zone=self.zone, members=ids)
        fixed = g.overview()['operations']['fixed']
        with self.assertRaises(ValueError):
            g.submit_week(1,1,dict(defense=defense, training=[ids[0]]))
        self.assertEqual(g.week,1)
        g.submit_week(1,1,dict(defense=defense, mission_orders=[]))
        restored = load_save(create_save(g))
        report = restored.week_report
        self.assertEqual(restored.phase,'report')
        self.assertEqual(report['briefing']['defense_plan']['zone'],self.zone)
        self.assertEqual(len(report['briefing']['defense_plan']['members']),5)
        self.assertEqual(report['budget'],dict(fixed=fixed,preparation=0))
        self.assertEqual(report['income']-report['expenses'],report['cash_change'])
        transactions = restored.world.money.transactions
        with self.assertRaises(ValueError):
            restored.submit_week(1,1,{})
        restored.advance_phase('report')
        self.assertEqual((restored.week,restored.world.money.transactions),(2,transactions))

    def test_season_rollover_reconciles(self):
        g = self.game
        g.week = 51
        g.submit_week(1,51,{})
        self.assertEqual((g.season,g.week),(2,1))
        self.assertEqual((g.week_report['season'],g.week_report['week']),(1,51))
        g.world.money.reconcile()


if __name__ == '__main__':
    unittest.main()

