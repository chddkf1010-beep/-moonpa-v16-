"""Elite mission, persistent jiyeon and accounting regression tests."""
import unittest
from campaign import Campaign
import moonpa_elite as elite


class EliteContentTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23)
        self.offer=self.game.overview()['elite_board'][0]
        self.team=self.game.guild.fighters[:3]

    def test_offer_calendar_is_stable_and_week_scoped(self):
        args=(23,self.game.guild.gid,1,1,self.game.guild.tier,65,12)
        offers=elite.board(*args)
        self.assertEqual(offers,elite.board(*args))
        self.assertEqual(len(offers),3)
        self.assertEqual(len({x['id'] for x in offers}),3)
        self.assertNotEqual({x['id'] for x in offers},
                            {x['id'] for x in elite.board(23,self.game.guild.gid,1,2,
                                                           self.game.guild.tier,65,12)})
        self.assertEqual(elite.board(23,self.game.guild.gid,1,52,4,65,12),[])

    def test_pure_results_and_choices_have_different_risks(self):
        args=(23,self.game.guild.gid,1,1,self.offer,self.team,100,70,5)
        careful=elite.resolve(*args,choice='study',roll=.15,fate_roll=.5)
        daring=elite.resolve(*args,choice='seize',roll=.15,fate_roll=.5)
        self.assertEqual(careful,elite.resolve(*args,choice='study',roll=.15,fate_roll=.5))
        self.assertGreater(careful['chance'],daring['chance'])
        self.assertIn(careful['outcome'],('exceptional','success','partial','failure'))
        self.assertEqual(careful['members'],[f.fid for f in self.team])
        with self.assertRaises(ValueError):elite.resolve(*args,choice='hack')

    def test_encounter_rewards_persist_on_fighter(self):
        world=self.game.world
        f=self.team[0]
        before=self.game.member_detail(f.fid)['points']
        result=elite.apply_kiyun(world,self.game.guild,self.team,{'kiyun':{'kind':'manual'}})
        self.assertEqual(result['kind'],'manual')
        self.assertEqual(self.game.member_detail(f.fid)['points'],before+1)
        self.assertEqual(world.kiyun_manuals[f.fid],1)
        result=elite.apply_kiyun(world,self.game.guild,self.team,{'kiyun':{'kind':'bond'}})
        self.assertEqual(result['kind'],'bond')
        self.assertGreater(elite.bond_bonus(world,self.team),0)
        self.assertGreater(self.game.member_detail(f.fid)['bonds'][0]['value'],0)
        before_renown=self.game.guild.renown
        result=elite.apply_kiyun(world,self.game.guild,self.team,{'kiyun':{'kind':'renown'}})
        self.assertEqual(result['kind'],'renown')
        self.assertGreaterEqual(self.game.guild.renown,before_renown)
        self.assertEqual(elite.apply_kiyun(world,self.game.guild,self.team,{'kiyun':None}),None)


class EliteCampaignTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23)
        self.ids=[f.fid for f in self.game.guild.fighters]
        self.offer=self.game.overview()['elite_board'][0]

    def order(self,ids=None,offer=None):
        return dict(id=(offer or self.offer)['id'],members=ids or self.ids[:3],choice='study')

    def test_weekly_ledger_and_report(self):
        g=self.game
        before=g.guild.cash
        g.submit_week(1,1,{'elite_order':self.order()})
        report=g.week_report
        self.assertEqual(len(report['elite_missions']),1)
        result=report['elite_missions'][0]
        self.assertEqual(result['members'],self.ids[:3])
        self.assertTrue(result['funded'])
        self.assertTrue(any(e['category']=='elite_preparation' for e in report['entries']))
        self.assertTrue(any(e['category']=='elite_reward' for e in report['entries']))
        self.assertEqual(sum(e['amount'] for e in report['entries']),report['cash_change'])
        self.assertEqual(before+report['cash_change'],g.guild.cash)
        g.world.money.reconcile()
        self.assertEqual(g.week,2)

    def test_bad_orders_do_not_advance_week(self):
        g=self.game
        with self.assertRaises(ValueError):
            g.submit_week(1,1,{'elite_order':self.order(self.ids[:2])})
        with self.assertRaises(ValueError):
            g.submit_week(1,1,{'elite_order':self.order([self.ids[0]]*3)})
        with self.assertRaises(ValueError):
            g.submit_week(1,1,{'elite_order':dict(self.order(),choice='unknown')})
        with self.assertRaises(ValueError):
            g.submit_week(1,1,{'elite_order':dict(self.order(),id='el0-0-obsolete')})
        with self.assertRaises(ValueError):
            g.submit_week(1,1,{'training':[self.ids[0]],'elite_order':self.order()})
        self.assertEqual(g.week,1)

    def test_independent_elite_slot_and_no_overlap_with_long_mission(self):
        g=self.game
        short=g.overview()['mission_board'][0]
        long=next(o for o in g.overview()['long_mission_board'] if o['duration']==2)
        g.submit_week(1,1,{'mission_orders':[dict(id=short['id'],members=self.ids[3:6])],
                           'long_orders':[dict(id=long['id'],members=self.ids[6:9])],
                           'elite_order':self.order()})
        self.assertEqual(len(g.week_report['missions']),1)
        self.assertEqual(len(g.week_report['long_missions']),1)
        self.assertEqual(len(g.week_report['elite_missions']),1)
        self.assertEqual(len(g.world.long_missions[g.guild.gid]),1)
        g.world.money.reconcile()

    def test_elite_members_gain_experience(self):
        g=self.game
        before={f.fid:(f.lv,f.xp) for f in g.guild.fighters}
        g.submit_week(1,1,{'elite_order':self.order()})
        for fid in self.ids[:3]:
            f=next(f for f in g.guild.fighters if f.fid==fid)
            self.assertGreater((f.lv,f.xp),before[fid])


if __name__=='__main__':
    unittest.main()
