import unittest
from campaign import Campaign
from moonpa_savegame import create_save,load_save,SaveError
import moonpa_player_ledger as journal
import moonpa_economy_v15_1 as economy

class PlayerJournalTest(unittest.TestCase):
    def setUp(self):
        self.c=Campaign(23)
        self.w=self.c.world
        self.g=self.c.guild
        self.j=self.w.player_journal
        self.w.season_active,self.w.week_active,self.w.globalweek=1,1,self.c.clock

    def test_opening_and_monthly_capture_independent(self):
        opening=self.g.cash
        self.assertEqual(self.j['opening'],opening)
        self.c.submit_week(1,1,{})
        self.assertEqual(self.j['count'],len(self.c.week_report['entries']))
        self.assertEqual(self.j['income']-self.j['expenses'],self.c.week_report['cash_change'])
        self.assertEqual(self.g.cash,self.j['closing'])
        self.assertTrue(journal.validate(self.w,self.g,self.j))
        self.assertFalse(self.w.money.capture)
        self.assertEqual(self.w.money.entries,[])
        self.assertEqual(self.c.overview()['player_journal']['difference'],0)

    def test_cash_move_outside_month_and_sign_separation(self):
        other=next(g for g in self.w.guilds.values() if g is not self.g)
        self.w.money.credit(other,1000,'test_npc')
        opening=self.g.cash
        self.assertTrue(self.w.money.move(other,self.g,300))
        self.assertTrue(self.w.money.move(self.g,other,120))
        self.w.money.spend(self.g,25,'facility_upgrade')
        self.assertEqual(self.j['income'],300)
        self.assertEqual(self.j['expenses'],145)
        p=self.j['seasons'][1]
        self.assertEqual(p['income_by']['transfer_fee'],300)
        self.assertEqual(p['expense_by']['transfer_fee'],120)
        self.assertEqual(self.g.cash,opening+155)
        self.assertEqual([r['after'] for r in self.j['recent']],[opening+300,opening+180,opening+155])
        self.assertTrue(journal.validate(self.w,self.g,self.j))

    def test_actual_facility_upgrade_and_restore(self):
        c=Campaign(23,interactive=True)
        c.phase='ready'
        c.world.money.credit(c.guild,10000,'test_capital')
        start=c.guild.cash
        c.upgrade('training')
        restored=load_save(create_save(c))
        j=restored.world.player_journal
        self.assertEqual(j['seasons'][1]['expense_by']['facility_upgrade'],start-c.guild.cash)
        self.assertEqual(j,c.world.player_journal)
        self.assertEqual(restored.overview()['player_journal']['difference'],0)

    def test_bounded_recent_full_totals_across_seasons(self):
        opening=self.g.cash
        for _ in range(125):self.w.money.credit(self.g,1,'basic_operating_income')
        self.w.season_active,self.w.week_active,self.w.globalweek=2,1,105
        self.c.season=2
        self.w.money.spend(self.g,20,'weekly_wages')
        self.assertEqual(len(self.j['recent']),120)
        self.assertEqual(self.j['recent'][0]['seq'],7)
        self.assertEqual(self.j['count'],126)
        self.assertEqual(self.j['income'],125)
        self.assertEqual(self.j['seasons'][2]['opening'],opening+125)
        self.assertEqual(self.j['seasons'][2]['closing'],opening+105)
        self.assertTrue(journal.validate(self.w,self.g,self.j))
        self.assertEqual(load_save(create_save(self.c)).world.player_journal,self.j)

    def test_old_save_starts_at_actual_balance_without_fabrication(self):
        self.w.money.credit(self.g,150,'basic_operating_income')
        self.c.week=3
        del self.w.player_journal
        g=load_save(create_save(self.c))
        j=g.world.player_journal
        self.assertEqual((j['opening'],j['count'],j['origin'],j['start_week']),(g.guild.cash,0,'migration',3))
        self.assertEqual(j['seasons'],{})
        g.world.season_active,g.world.week_active=1,3
        g.world.money.spend(g.guild,20,'paid_training')
        self.assertTrue(journal.validate(g.world,g.guild,j))

    def test_failed_spend_and_read_only_view(self):
        before=create_save(self.c)
        self.assertEqual(self.w.money.spend(self.g,self.g.cash+1,'paid_training'),0)
        self.c.overview()
        self.assertEqual(create_save(self.c),before)

    def test_corrupted_totals_detected(self):
        self.w.money.credit(self.g,10,'basic_operating_income')
        self.j['income']+=1
        self.assertFalse(journal.validate(self.w,self.g,self.j))
        with self.assertRaises(SaveError):create_save(self.c)

    def test_dissolution_excludes_successor_capital(self):
        self.w.disband(self.g,1)
        self.assertTrue(self.j['closed'])
        self.assertEqual(self.j['closing'],0)
        self.assertNotIn('replacement_founder_capital',self.j['seasons'][1]['income_by'])
        self.assertTrue(journal.validate(self.w,self.g,self.j))
        self.assertEqual(journal.view(self.w,self.g,1,1)['difference'],0)

if __name__=='__main__':unittest.main()
