import unittest
from test_contract_renewal import complete_contract_review

from campaign import Campaign, equipment
from combat import ROLE_SKILLS, SKILLS, Battle
from moonpa_growth import Development, available_skill_slots


class CampaignOpeningTest(unittest.TestCase):
    def setUp(self):
        self.game = Campaign(23, interactive=True)

    def open(self, pick=True):
        g = self.game
        g.advance_phase('tutorial')
        for round_no in range(1,6):
            self.assertEqual(g.draft_round, round_no)
            player = g.draft_pool[0].fid if pick else None
            g.draft_pick(1,round_no,player)
        self.assertEqual(g.phase,'fa')
        g.advance_phase('fa')

    def test_draft_facility_and_week_gate(self):
        g = self.game
        self.assertEqual(len(g.guild.fighters),15)
        with self.assertRaises(ValueError):
            g.submit_week(1,1,{})
        self.open()
        self.assertEqual(len(g.guild.fighters),20)
        quote = g.free_agent_quote(g.world.fa[0])
        balance = g.guild.cash
        g.upgrade('estate')
        self.assertEqual(balance-g.guild.cash,320)
        self.assertEqual(g.free_agent_quote(g.world.fa[0])['fee'],round(quote['fee']*.95))
        g.submit_week(1,1,{})
        self.assertEqual(g.phase,'report')
        self.assertTrue(any(e['category']=='estate_income' and e['amount']==35 for e in g.week_report['entries']))
        with self.assertRaises(ValueError):
            g.submit_week(1,2,{})
        g.advance_phase('report')
        self.assertEqual((g.phase,g.week),('ready',2))
        g.world.money.reconcile()

    def test_annual_draft(self):
        g = self.game
        self.open(False)
        g.week = 51
        g.submit_week(1,51,{})
        self.assertEqual(g.phase,'report')
        complete_contract_review(g)
        g.advance_phase('report')
        self.assertEqual((g.season,g.draft_round,g.phase),(2,1,'draft'))

    def test_role_bias_and_skill_slots(self):
        healer = Development.create(80,150,4,23,17)
        assassin = Development.create(80,150,5,23,17)
        self.assertLess(healer.attributes[0],healer.attributes[5])
        self.assertLess(assassin.attributes[5],assassin.attributes[3])
        self.assertGreater(assassin.attributes[6],assassin.attributes[5])
        self.assertEqual([available_skill_slots(x) for x in (1,5,10,15,20)],[2,3,4,5,6])
        self.assertTrue(all(len(skillset)==6 for skillset in ROLE_SKILLS))
        self.open()
        g = self.game
        f = g.guild.fighters[0]
        f.lv = 4
        with self.assertRaises(ValueError):
            g.equip(f.fid,list(ROLE_SKILLS[f.role][:3]))
        f.lv = 20
        g.equip(f.fid,list(ROLE_SKILLS[f.role]))
        self.assertEqual(tuple(ROLE_SKILLS[f.role]),equipment(f))


if __name__ == '__main__':
    unittest.main()
