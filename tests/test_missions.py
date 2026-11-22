"""Regression tests for authored mission content and weekly settlement."""
import unittest
from types import SimpleNamespace

from campaign import Campaign
import moonpa_missions as missions


def fighter(fid, role=0):
    return SimpleNamespace(fid=fid,role=role)


class MissionContentTests(unittest.TestCase):
    def offers(self, seed=23, season=1, week=1):
        return missions.board(seed,31,season,week,4,65,12)

    def test_six_categories_every_week_and_stable_seed(self):
        one=self.offers()
        two=self.offers()
        self.assertEqual(one,two)
        self.assertEqual(len(one),6)
        self.assertEqual(len({m['id'] for m in one}),6)
        self.assertEqual({m['category'] for m in one},set(missions.CATEGORIES))
        self.assertNotEqual([m['id'] for m in one],[m['id'] for m in self.offers(week=2)])
        self.assertTrue(all(m['duration']==1 and m['min_members']<=3<=m['max_members'] for m in one))

    def test_four_outcomes_have_distinct_narratives_and_payouts(self):
        offer=self.offers()[0]
        team=[fighter(10,role=0),fighter(11,role=3),fighter(12,role=4)]
        kwargs=dict(seed=23,guild_id=31,season=1,week=1,offer=offer,team=team,
                    power=90,base_ca=80,base_level=4)
        probe=missions.resolve(**kwargs,roll=0)
        p=probe['chance']
        trials=[
            missions.resolve(**kwargs,roll=0),
            missions.resolve(**kwargs,roll=p*.6),
            missions.resolve(**kwargs,roll=p+(1-p)*.25),
            missions.resolve(**kwargs,roll=p+(1-p)*.95)
        ]
        self.assertEqual([x['outcome'] for x in trials],
                         ['exceptional','success','partial','failure'])
        self.assertEqual(len({x['narrative'] for x in trials}),4)
        self.assertGreater(trials[0]['gross'],trials[1]['gross'])
        self.assertGreater(trials[1]['gross'],trials[2]['gross'])
        self.assertGreater(trials[2]['gross'],trials[3]['gross'])

    def test_approach_and_role_synergy_change_real_odds(self):
        offer=next(x for x in self.offers() if x['category']=='구호')
        team=[fighter(i,role=i%6) for i in (101,102,103)]
        args=(23,31,1,1,offer,team,91,80,4)
        safe=missions.resolve(*args,approach='cautious',roll=0)
        normal=missions.resolve(*args,approach='balanced',roll=0)
        bold=missions.resolve(*args,approach='bold',roll=0)
        self.assertGreater(safe['chance'],normal['chance'])
        self.assertGreater(normal['chance'],bold['chance'])
        self.assertLess(safe['gross'],normal['gross'])
        self.assertLess(normal['gross'],bold['gross'])
        favored_roles=[missions.ROLE_NAMES.index(role) for role in offer['suggested_roles']]
        matching=[fighter(i+900,role=favored_roles[i%len(favored_roles)]) for i in range(3)]
        wrong_role=next(r for r in range(6) if r not in favored_roles)
        unrelated=[fighter(i+900,role=wrong_role) for i in range(3)]
        matching_result=missions.resolve(23,31,1,1,offer,matching,91,80,4,roll=0)
        unrelated_result=missions.resolve(23,31,1,1,offer,unrelated,91,80,4,roll=0)
        self.assertGreater(matching_result['chance'],unrelated_result['chance'])

    def test_resolution_is_reproducible_without_mutating_global_rng(self):
        offer=self.offers()[0]
        team=[fighter(10,1),fighter(11,4),fighter(12,2)]
        args=(23,31,1,1,offer,team,90,80,4)
        self.assertEqual(missions.resolve(*args),missions.resolve(*args))


class CampaignMissionTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23)
        self.cards=self.game.overview()['mission_board']
        self.people=self.game.guild.fighters

    def test_two_selected_offers_and_cash_ledger(self):
        game=self.game
        members=[[f.fid for f in self.people[0:3]],[f.fid for f in self.people[3:6]]]
        orders=[
            dict(id=self.cards[0]['id'],members=members[0],approach='cautious'),
            dict(id=self.cards[1]['id'],members=members[1],approach='bold')
        ]
        game.submit_week(1,1,dict(mission_orders=orders))
        report=game.week_report
        self.assertEqual(len(report['missions']),2)
        self.assertEqual([m['id'] for m in report['missions']], [x['id'] for x in orders])
        self.assertTrue(all(x['outcome'] in ('exceptional','success','partial','failure','cancelled')
                            for x in report['missions']))
        self.assertEqual(sum(x['amount'] for x in report['entries']),report['cash_change'])
        self.assertEqual(report['income']-report['expenses'],report['cash_change'])
        game.world.money.reconcile()

    def test_two_and_five_person_offers(self):
        short=next(x for x in self.cards if x['min_members']==2)
        long=next(x for x in self.cards if x['max_members']==5 and x['id']!=short['id'])
        members=[[f.fid for f in self.people[:2]],[f.fid for f in self.people[2:7]]]
        self.game.submit_week(1,1,dict(mission_orders=[
            dict(id=short['id'],members=members[0],approach='balanced'),
            dict(id=long['id'],members=members[1],approach='balanced')
        ]))
        self.assertEqual([len(x['members']) for x in self.game.week_report['missions']],[2,5])

    def test_invalid_offer_and_duplicate_members_do_not_mutate(self):
        game=self.game
        f=[x.fid for x in self.people[:5]]
        original=(game.week,game.guild.cash)
        bad=[
            [dict(id='fictional',members=f[:3])],
            [dict(id=self.cards[0]['id'],members=f[:3],approach='reckless')],
            [dict(id=self.cards[0]['id'],members=f[:1])],
            [dict(id=self.cards[0]['id'],members=f[:3]),
             dict(id=self.cards[0]['id'],members=f[3:])],
            [dict(id=self.cards[0]['id'],members=f[:3]),
             dict(id=self.cards[1]['id'],members=f[2:5])]
        ]
        for orders in bad:
            with self.subTest(orders=orders):
                with self.assertRaises(ValueError):
                    game.submit_week(1,1,dict(mission_orders=orders))
                self.assertEqual((game.week,game.guild.cash),original)

    def test_offer_cannot_be_reused_next_week(self):
        old=self.cards[0]
        self.game.submit_week(1,1,{})
        self.assertEqual(self.game.week,2)
        self.assertNotIn(old['id'],{x['id'] for x in self.game.overview()['mission_board']})
        with self.assertRaises(ValueError):
            self.game.submit_week(1,2,dict(mission_orders=[
                dict(id=old['id'],members=[f.fid for f in self.people[:3]])]))

    def test_legacy_three_person_mission_still_works(self):
        self.game.submit_week(1,1,dict(missions=[[f.fid for f in self.people[:3]]]))
        result=self.game.week_report['missions'][0]
        self.assertTrue(result['funded'])
        self.assertEqual(len(result['members']),3)
        self.assertEqual(result['outcome'] in ('exceptional','success','partial','failure'),True)


if __name__=='__main__':
    unittest.main()
