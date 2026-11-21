import unittest

from campaign import Campaign


class RecruitmentTest(unittest.TestCase):
    def setUp(self):
        self.game = Campaign(23)
        self.candidate = next(f for f in self.game.free_agents()['candidates'] if f['eligible'])

    def sign(self, years=3):
        return self.game.recruit(1, 1, self.candidate['id'], years)

    def test_quote_matches_ledger_and_roster(self):
        g = self.game
        g.world.rng.random = lambda: 0
        signed = self.sign()
        self.assertEqual(signed['status'], 'signed')
        self.assertEqual(signed['cash'], self.candidate['cash_after'])
        self.assertEqual(signed['contract_end'], 4)
        f = next(f for f in g.guild.fighters if f.fid == self.candidate['id'])
        self.assertEqual((f.name, f.wage, f.last_transfer_season),
                         (self.candidate['name'], self.candidate['wage'], 1))
        self.assertEqual(self.sign()['status'], 'unavailable')
        self.assertEqual(g.guild.cash, signed['cash'])
        g.world.money.reconcile()
        g.submit_week(1, 1, {})
        self.assertEqual(g.week, 2)

    def test_no_cash_and_capacity_are_checked_before_charging(self):
        g = self.game
        g.world.money.spend(g.guild, g.guild.cash, 'test_setup')
        self.assertEqual(self.sign()['status'], 'insufficient_cash')
        g.guild.fighters += g.world.fa[:32-len(g.guild.fighters)]
        self.assertEqual(self.sign()['status'], 'roster_full')
        self.assertEqual(g.guild.cash, 0)

    def test_decline_blocks_repeat_and_does_not_charge(self):
        g = self.game
        cash = g.guild.cash
        g.world.rng.random = lambda: 1
        self.assertEqual(self.sign()['status'], 'declined_this_week')
        g.world.rng.random = lambda: 0
        self.assertEqual(self.sign()['status'], 'declined_this_week')
        self.assertEqual(g.guild.cash, cash)
        self.assertTrue(any(f.fid == self.candidate['id'] for f in g.world.fa))

    def test_invalid_period_or_busy_battle(self):
        g = self.game
        with self.assertRaises(ValueError):
            self.sign(0)
        with self.assertRaises(ValueError):
            g.recruit(1, 0, self.candidate['id'], 1)
        state = g.overview()
        team = [dict(id=f['id'], row='front', skills=f['skills'])
                for f in state['roster'] if f['recommended']]
        g.start(next(z['id'] for z in state['zones'] if z['selectable']), team, practice=True)
        self.assertEqual(self.sign()['status'], 'market_closed')
