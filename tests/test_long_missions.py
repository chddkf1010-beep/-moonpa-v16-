"""Long-expedition lifecycle, transfer locks, rollover and economic regression."""
import unittest

from campaign import Campaign
import moonpa_long_missions as expeditions
import moonpa_economy_v15_1 as economy
import moonpa_market as market


class ExpeditionContentTests(unittest.TestCase):
    def test_board_is_deterministic_and_duration_2_to_4(self):
        a=expeditions.board(23,31,1,1,4,65,12)
        self.assertEqual(a,expeditions.board(23,31,1,1,4,65,12))
        self.assertEqual(len(a),6)
        self.assertEqual({o['duration'] for o in a},{2,3,4})
        self.assertTrue(all(o['reward']>o['initial_cost'] for o in a))
        self.assertEqual(expeditions.board(23,31,1,51,4,65,12),[])
        self.assertTrue(all(o['duration']==2 for o in
                            expeditions.board(23,31,1,50,4,65,12)))

    def test_intermediate_events_are_stable_and_have_choices(self):
        offer=next(o for o in expeditions.board(23,31,1,1,4,65,12)
                   if o['duration']==2)
        t=expeditions.start(offer,[10,11,12],'balanced',1,1)
        crew=[type('F',(),{'fid':i,'ca':90,'lv':5,'role':i%6})()
              for i in [10,11,12]]
        self.assertEqual(expeditions.preview(t)['stage'],1)
        first=expeditions.step(t,23,1,crew,'safe')
        self.assertEqual(first['status'],'progress')
        self.assertEqual(t['progress'],1)
        self.assertEqual(expeditions.preview(t)['stage'],2)
        last=expeditions.step(t,23,2,crew,'push')
        self.assertIsNotNone(last['final'])
        self.assertIn(last['status'],('exceptional','success','partial','failure'))
        self.assertEqual(len(t['events']),2)
        self.assertEqual(last['final']['gross']>=0,True)
        with self.assertRaises(ValueError):
            expeditions.step(t,23,3,crew)

    def test_different_week_choice_changes_momentum(self):
        offer=next(o for o in expeditions.board(23,31,1,1,4,65,12)
                   if o['duration']==2)
        safe=expeditions.start(offer,[10,11],'balanced',1,1)
        risky=expeditions.start(offer,[10,11],'balanced',1,1)
        crew=[type('F',(),{'fid':i,'ca':100,'lv':7,'role':i%6})()
              for i in [10,11]]
        expeditions.step(safe,23,1,crew,'safe')
        expeditions.step(risky,23,1,crew,'push')
        self.assertNotEqual((safe['momentum'],safe['bonus']),
                            (risky['momentum'],risky['bonus']))


class ExpeditionCampaignTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23)
        self.ids=[f.fid for f in self.game.guild.fighters]
        self.offers=self.game.overview()['long_mission_board']

    def send(self,offer=None,members=None,approach='balanced',actions=None,short=None):
        g=self.game
        payload={'long_orders':([] if offer is None else
                                 [dict(id=offer['id'],members=members or self.ids[:3],approach=approach)]),
                 'long_actions':actions or [],
                 'mission_orders':short or []}
        g.submit_week(g.season,g.week,payload)
        return g.week_report

    def test_two_week_mission_locks_then_rewards_and_releases(self):
        offer=next(x for x in self.offers if x['duration']==2)
        roster=self.ids[:3]
        report1=self.send(offer,roster)
        self.assertEqual(report1['long_missions'][0]['status'],'progress')
        self.assertEqual(report1['long_missions'][0]['cost'],offer['initial_cost'])
        self.assertEqual(len(self.game.world.long_missions[self.game.guild.gid]),1)
        view=self.game.overview()
        self.assertTrue(all(x['expedition'] for x in view['roster'] if x['id'] in roster))
        self.assertTrue(all(x['id'] not in roster for x in view['roster'] if x['recommended']))
        self.assertEqual(self.game.world.away(self.game.guild.gid),set(roster))
        with self.assertRaises(ValueError):
            self.game.submit_week(1,2,{'training':[roster[0]]})
        report2=self.send(actions=[dict(id=offer['id'],choice='push')])
        self.assertEqual(len(self.game.world.long_missions[self.game.guild.gid]),0)
        self.assertIn(report2['long_missions'][0]['status'],
                      ('exceptional','success','partial','failure'))
        self.assertTrue(any(e['category']=='expedition_reward' for e in report2['entries']))
        self.assertTrue(any(e['category']=='expedition_upkeep' for e in report2['entries']))
        self.assertEqual(sum(e['amount'] for e in report2['entries']),report2['cash_change'])
        self.game.world.money.reconcile()

    def test_two_long_missions_consume_both_weekly_slots(self):
        options=[o for o in self.offers if o['duration']==2][:2]
        self.assertEqual(len(options),2)
        orders=[dict(id=options[0]['id'],members=self.ids[:3],approach='balanced'),
                dict(id=options[1]['id'],members=self.ids[3:6],approach='cautious')]
        self.game.submit_week(1,1,dict(long_orders=orders))
        self.assertEqual(len(self.game.world.long_missions[self.game.guild.gid]),2)
        with self.assertRaises(ValueError):
            self.game.submit_week(1,2,dict(
                mission_orders=[dict(id=self.game.overview()['mission_board'][0]['id'],
                                     members=self.ids[6:9])]))

    def test_short_and_long_share_two_weekly_slots(self):
        short=self.game.overview()['mission_board'][0]
        offer=self.offers[0]
        report=self.send(offer,self.ids[:3],short=[dict(id=short['id'],members=self.ids[3:6])])
        self.assertEqual(len(report['missions']),1)
        self.assertEqual(len(report['long_missions']),1)
        self.assertEqual(self.game.world.away(self.game.guild.gid),set(self.ids[:3]))
        self.game.world.money.reconcile()

    def test_abandon_does_not_refund_and_releases_members(self):
        offer=next(x for x in self.offers if x['duration']==3)
        self.send(offer)
        paid=self.game.world.long_missions[self.game.guild.gid][0]['spent']
        self.assertGreater(paid,0)
        result=self.send(actions=[dict(id=offer['id'],choice='withdraw')])
        self.assertEqual(result['long_missions'][0]['status'],'abandoned')
        self.assertEqual(result['long_missions'][0]['gross'],0)
        self.assertFalse(self.game.world.long_missions[self.game.guild.gid])
        self.assertFalse(any(e['category']=='expedition_reward' for e in result['entries']))

    def test_transfer_of_absent_member_is_rejected(self):
        offer=next(x for x in self.offers if x['duration']==3)
        self.send(offer)
        f=self.game.guild.fighters[0]
        seller=self.game.guild
        buyer=next(g for g in self.game.world.guilds.values()
                   if g is not seller and g.tier==seller.tier)
        self.assertFalse(self.game.world.trade(seller,buyer,f,0,[],1))
        self.assertIsNone(market.requirement(self.game.world,seller,f,1))
        self.assertEqual(set(self.ids[:3]),self.game.world.away(seller.gid))

    def test_four_week_mission_resolves_and_no_calendar_stall(self):
        offer=next(o for o in self.offers if o['duration']==4)
        self.send(offer)
        for _ in range(3):
            report=self.send()
        self.assertEqual(report['long_missions'][0]['stage'],4)
        self.assertFalse(self.game.world.long_missions[self.game.guild.gid])
        self.assertEqual(self.game.week,5)
        self.assertEqual(sum(e['amount'] for e in report['entries']),report['cash_change'])

    def test_cannot_begin_mission_that_would_cross_season(self):
        self.game.week=50
        cards=self.game.overview()['long_mission_board']
        self.assertTrue(cards)
        self.assertTrue(all(x['duration']==2 for x in cards))
        with self.assertRaises(ValueError):
            self.game.submit_week(1,50,dict(long_orders=[
                dict(id=self.offers[0]['id'],members=self.ids[:3])]))
        self.send(cards[0])
        self.send()
        self.assertEqual((self.game.season,self.game.week),(2,1))
        self.assertFalse(self.game.world.long_missions[self.game.guild.gid])

    def test_invalid_repeated_member_and_bad_choice_do_not_mutate(self):
        offer=self.offers[0]
        before=(self.game.week,self.game.guild.cash)
        for orders in ([dict(id=offer['id'],members=self.ids[:2]*2)],
                       [dict(id=offer['id'],members=self.ids[:3],approach='fictional')]):
            with self.assertRaises(ValueError):
                self.game.submit_week(1,1,dict(long_orders=orders))
            self.assertEqual((self.game.week,self.game.guild.cash),before)
        self.send(offer)
        before=(self.game.week,self.game.guild.cash)
        with self.assertRaises(ValueError):
            self.game.submit_week(1,2,dict(long_actions=[
                dict(id=offer['id'],choice='teleport')]))
        self.assertEqual((self.game.week,self.game.guild.cash),before)

    def test_unfunded_launch_has_no_negative_cash_and_no_lock(self):
        g=self.game
        # Record the pre-test cash drain through the same ledger.
        g.world.money.spend(g.guild,g.guild.cash,'test_treasury_drain')
        for z in g.world.zones:
            if z.owner==g.guild.gid:z.owner=None
        result=self.send(self.offers[0])
        self.assertEqual(result['long_missions'][0]['status'],'unfunded')
        self.assertFalse(g.world.long_missions[g.guild.gid])
        self.assertTrue(g.guild.cash>=0)
        g.world.money.reconcile()


if __name__=='__main__':
    unittest.main()
