import unittest
from campaign import Campaign
from moonpa_savegame import create_save,load_save
import moonpa_economy_v15_1 as economy
from moonpa_growth import training_factors

class FacilityGrowthTest(unittest.TestCase):
    def setUp(self):
        self.c=Campaign(23,interactive=True)
        self.c.phase='ready'
        self.w=self.c.world;self.g=self.c.guild

    def test_reserve_blocks_without_cash_or_level_change(self):
        fixed=economy.fixed_weekly_cost(self.w,self.g)
        target=4*fixed+239
        if self.g.cash>target:self.w.money.spend(self.g,self.g.cash-target,'test')
        else:self.w.money.credit(self.g,target-self.g.cash,'test')
        before=self.g.cash
        row=next(x for x in self.c.facility_view() if x['id']=='training')
        self.assertEqual(row['shortfall'],1)
        self.assertFalse(row['can_upgrade'])
        with self.assertRaises(ValueError):self.c.upgrade('training')
        self.assertEqual(self.g.cash,before)
        self.assertEqual(self.w.facilities[self.g.gid]['training'],0)
        self.w.money.credit(self.g,1,'test')
        self.c.upgrade('training')
        self.assertEqual(self.g.cash,4*fixed)
        self.assertEqual(self.w.player_journal['seasons'][1]['expense_by']['facility_upgrade'],240)

    def test_medical_recovery_real_train_week_and_debt_pause(self):
        f=self.g.fighters[0]
        plan={k:[] for k in ('training','second','overflow_bench','attack','defend','missions','emergency')}
        for level in range(6):
            self.w.facilities[self.g.gid]['medical']=level
            extra=0
            for week in range(1,6):
                f.injured=4
                economy.train_week(self.w,self.g,plan,week,0)
                extra+=3-f.injured
            self.assertEqual(extra,level)
        self.w.money.obligation(self.g,'operations',100)
        f.injured=4
        economy.train_week(self.w,self.g,plan,1,0)
        self.assertEqual(f.injured,3)
        self.assertFalse(economy.facilities_operational(self.w,self.g))

    def test_debt_stops_estate_projection_and_upgrade(self):
        self.w.facilities[self.g.gid]['estate']=3
        self.assertEqual(economy.passive_week_projection(self.w,self.g)['estate'],140)
        self.w.money.obligation(self.g,'operations',100)
        self.assertEqual(economy.passive_week_projection(self.w,self.g)['estate'],0)
        self.assertEqual(economy.facility_upkeep(self.w,self.g),8)
        with self.assertRaises(ValueError):self.c.upgrade('training')

    def test_all_roster_detail_and_focus_restore(self):
        for f in self.g.fighters:
            detail=self.c.member_detail(f.fid)
            self.assertIn('cultivation',detail)
            self.assertEqual(detail['cultivation']['ownership']['total'],0)
            self.assertEqual(detail['cultivation']['gap'],round(max(0,f.pa-f.ca),2))
        target=self.g.fighters[-1]
        before=(self.g.cash,self.c.clock,target.ca,self.w.rng.getstate())
        self.c.set_training_focus(target.fid,'attack')
        self.assertEqual(before,(self.g.cash,self.c.clock,target.ca,self.w.rng.getstate()))
        restored=load_save(create_save(self.c))
        self.assertEqual(restored.member_detail(target.fid)['training_focus']['focus'],'attack')

    def test_budget_normalization_all_roles(self):
        for role in range(6):
            base=sum(training_factors(role,'balanced'))
            for focus in ('balanced','attack','defense','ranged','internal','support'):
                self.assertAlmostEqual(sum(training_factors(role,focus)),base)

    def test_actual_paid_training_and_member_history(self):
        for f in self.g.fighters:f.injured=0
        target=self.g.fighters[-1]
        self.c.set_training_focus(target.fid,'attack')
        self.c.submit_week(1,1,dict(training=[target.fid]))
        result=self.c.member_detail(target.fid)['cultivation']
        self.assertGreater(result['ownership']['training'],0)
        self.assertTrue(result['recent'])
        self.assertEqual(result['recent'][-1]['week'],1)
        self.assertEqual(self.c.overview()['player_journal']['difference'],0)

if __name__=='__main__':unittest.main()
