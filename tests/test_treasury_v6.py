"""v6 treasury decisions, estate ROI and existing save/battle compatibility."""
import json
import unittest

from campaign import Campaign
import moonpa_economy_v15_1 as economy
from moonpa_savegame import SaveError, create_save, load_save
import pages_bridge


class TreasuryBalanceV6Tests(unittest.TestCase):
    def make_ready(self, seed=23):
        game=Campaign(seed, interactive=True)
        # Tests use the existing post-draft ready path without spending 5 rounds
        # in the menu. Founding and the draft itself have their own regressions.
        game.phase='ready'
        return game

    @staticmethod
    def investment_paid(game):
        return sum(-item['amount'] for item in game.week_report['entries']
                   if item['category']=='paid_investment')

    def test_policy_switch_is_validated_and_only_available_before_week(self):
        g=self.make_ready()
        self.assertEqual(g.treasury_view()['policy'],'balanced')
        for policy in ('save','growth','balanced'):
            g.set_treasury_policy(policy)
            self.assertEqual(g.treasury_view()['policy'],policy)
        old=g.treasury_view()
        for bad in (None, True, [], 'infinite',''):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                g.set_treasury_policy(bad)
            self.assertEqual(g.treasury_view(),old)
        g.pending_week={'locked':True}
        with self.assertRaises(ValueError):g.set_treasury_policy('growth')
        g.pending_week=None
        g.phase='report'
        with self.assertRaises(ValueError):g.set_treasury_policy('growth')
        g.phase='ready'
        g.interactive=False
        with self.assertRaises(ValueError):g.set_treasury_policy('growth')

    def test_treasury_policy_does_not_change_other_sects_policy(self):
        g=self.make_ready()
        g.set_treasury_policy('growth')
        for rival in g.world.guilds.values():
            if rival.gid!=g.guild.gid:
                self.assertEqual(economy.treasury_policy(g.world,rival),'balanced')
        self.assertEqual(economy.treasury_policy(g.world,g.guild),'growth')

    def test_investment_saving_balanced_growth_are_monotone(self):
        outcomes={}
        for policy in ('save','balanced','growth'):
            g=self.make_ready()
            fixed=g.operations_view()['fixed']
            target=9*fixed
            if g.guild.cash<target:
                g.world.money.credit(g.guild,target-g.guild.cash,'test_sufficient_cash')
            g.set_treasury_policy(policy)
            initial_ca=sum(f.ca for f in g.guild.fighters)
            initial_cash=g.guild.cash
            members=[f.fid for f in g.guild.fighters if not f.injured]
            self.assertGreaterEqual(len(members),15)
            g.submit_week(1,1,dict(training=members[:20]))
            report=g.week_report
            self.assertEqual(report['treasury_policy'],policy)
            self.assertEqual(report['investment_paid'],self.investment_paid(g))
            self.assertEqual(report['income']-report['expenses'],report['cash_change'])
            self.assertEqual(report['cash_before'],initial_cash)
            g.world.money.reconcile()
            outcomes[policy]=(self.investment_paid(g),sum(f.ca for f in g.guild.fighters)-initial_ca,g.guild.cash)
        self.assertEqual(outcomes['save'][0],0)
        self.assertGreater(outcomes['balanced'][0],0)
        self.assertGreaterEqual(outcomes['growth'][0],outcomes['balanced'][0])
        self.assertGreater(outcomes['growth'][1],outcomes['save'][1])
        self.assertGreaterEqual(outcomes['save'][2],outcomes['balanced'][2])
        self.assertGreaterEqual(outcomes['balanced'][2],outcomes['growth'][2])

    def test_estate_income_table_and_level_payback(self):
        self.assertEqual(economy.ESTATE_WEEKLY_INCOME,(0,20,46,78,116,160))
        for level in range(1,6):
            marginal=economy.estate_weekly_income(level)-economy.estate_weekly_income(level-1)
            self.assertGreater(marginal,0)
            self.assertLessEqual(320*level/marginal,52)
        for value in (-1,6,1.5,True,'2'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                economy.estate_weekly_income(value)

    def test_renovation_income_matches_ledger_and_view(self):
        g=self.make_ready()
        w=g.world
        w.money.credit(g.guild,10000,'test_facility_funds')
        for level in range(1,6):
            g.upgrade('estate')
            status=next(f for f in g.facility_view() if f['id']=='estate')
            self.assertEqual(status['level'],level)
            self.assertEqual(status['current_value'],economy.estate_weekly_income(level))
            self.assertEqual(status['next_cost'],320*(level+1) if level<5 else None)
        self.assertEqual(g.treasury_view()['forecast']['estate'],160)
        g.set_treasury_policy('save')
        g.submit_week(1,1,{})
        self.assertEqual(sum(e['amount'] for e in g.week_report['entries']
                             if e['category']=='estate_income'),160)
        self.assertEqual(g.week_report['treasury_policy'],'save')
        w.money.reconcile()

    def test_passive_projection_is_read_only_and_labeled_components_reconcile(self):
        g=self.make_ready()
        w=g.world
        before=(w.rng.getstate(),w.money.transactions,g.guild.cash,w.checkpoints)
        view=g.treasury_view()
        p=view['forecast']
        self.assertEqual(p['fixed'],g.guild.wage_total()+economy.TIERS[g.guild.tier]['hall'])
        self.assertEqual(p['income'],p['zone']+p['estate']+p['sponsor'])
        self.assertEqual(p['balance'],p['income']-p['garrison']-p['fixed'])
        self.assertEqual(view['available_above_reserve'],max(0,g.guild.cash-view['reserve']))
        self.assertEqual((w.rng.getstate(),w.money.transactions,g.guild.cash,w.checkpoints),before)

    def test_legacy_saves_missing_optional_policy_default_to_balanced(self):
        g=self.make_ready()
        delattr(g.world,'player_treasury_policy')
        legacy=create_save(g)
        loaded=load_save(legacy)
        self.assertEqual(loaded.treasury_view()['policy'],'balanced')
        self.assertEqual(loaded.guild.name,g.guild.name)
        self.assertEqual(loaded.league_view(),g.league_view())
        loaded.set_treasury_policy('save')
        self.assertEqual(load_save(create_save(loaded)).treasury_view()['policy'],'save')

    def test_save_policy_during_draft_and_after_policy_change(self):
        g=Campaign(23,interactive=True)
        g.found_sect('백련문','balanced')
        loaded=load_save(create_save(g))
        self.assertEqual(loaded.phase,'draft')
        self.assertEqual(loaded.treasury_view()['policy'],'balanced')
        loaded.phase='ready'
        loaded.set_treasury_policy('growth')
        restored=load_save(create_save(loaded))
        self.assertEqual(restored.treasury_view()['policy'],'growth')
        self.assertEqual(restored.guild.name,'백련문')

    def test_rejects_invalid_saved_policy_without_mutating_game(self):
        g=self.make_ready()
        g.world.player_treasury_policy='invalid'
        with self.assertRaises(SaveError):
            create_save(g)

    def test_bridge_policy_roundtrip_and_error_is_atomic(self):
        original=pages_bridge.game
        try:
            pages_bridge.game=self.make_ready()
            before=json.loads(pages_bridge.handle('state','{}'))
            self.assertEqual(before['treasury']['policy'],'balanced')
            with self.assertRaises(ValueError):
                pages_bridge.handle('treasury_policy',json.dumps({'policy':'anything'}))
            self.assertEqual(json.loads(pages_bridge.handle('state','{}')),before)
            after=json.loads(pages_bridge.handle('treasury_policy',json.dumps({'policy':'save'})))
            self.assertEqual(after['treasury']['policy'],'save')
            saved=json.loads(pages_bridge.handle('export_save','{}'))
            pages_bridge.handle('new_game','{}')
            restored=json.loads(pages_bridge.handle('import_save',json.dumps({'save':saved})))
            self.assertEqual(restored['treasury'],after['treasury'])
        finally:
            pages_bridge.game=original


if __name__=='__main__':
    unittest.main()
