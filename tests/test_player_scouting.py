import unittest

from campaign import Campaign


class ScoutingTest(unittest.TestCase):
    def setUp(self):
        self.game = Campaign(23)

    def find_offer(self, exchanges):
        g = self.game
        for sect in g.scouting()['sects']:
            for fighter in g.scouting(sect['id'])['candidates']:
                for ids in exchanges:
                    reply = g.transfer(1, 1, sect['id'], fighter['id'], 0, ids)
                    if reply['status'] in ('counter', 'accepted'):
                        return sect['id'], fighter, ids, reply.get('counter_fee') or 0
        self.fail('No test candidate found')

    def test_cash_preview_and_settlement_preserve_contract(self):
        g = self.game
        seller, f, ids, fee = self.find_offer([[]])
        old_cash = g.guild.cash
        seller_cash = g.world.guilds[seller].cash
        self.assertGreater(fee, 0)
        self.assertEqual(g.transfer(1,1,seller,f['id'],fee,ids)['status'],'accepted')
        self.assertEqual(g.guild.cash,old_cash)
        result = g.transfer(1,1,seller,f['id'],fee,ids,True)
        self.assertEqual(result['status'],'signed')
        self.assertEqual(result['wage'],f['wage'])
        self.assertEqual(result['contract_end'],f['contract_end'])
        self.assertEqual(g.guild.cash,old_cash-fee)
        self.assertEqual(g.world.guilds[seller].cash,seller_cash+fee)
        self.assertEqual(g.transfer(1,1,seller,f['id'],fee,ids,True)['status'],'invalid')
        self.assertNotIn('ca',f)
        self.assertNotIn('pa',f)
        self.assertIn(f['pa_grade'],'EDCBAS')

    def test_exchange_and_current_season_locks(self):
        g = self.game
        pool = g.scouting()['exchange_pool']
        seller, fighter, ids, fee = self.find_offer([[x['id']] for x in pool if not x['locked']])
        self.assertEqual(g.transfer(1,1,seller,fighter['id'],fee,ids,True)['status'],'signed')
        swapped = next(f for f in g.scouting(seller)['candidates'] if f['id']==ids[0])
        self.assertTrue(swapped['locked'])
        self.assertEqual(g.transfer(1,1,seller,swapped['id'],0,[])['status'],'locked')
        self.assertEqual(g.transfer(1,1,seller,swapped['id'],0,[ids[0]]*2)['status'],'invalid')
        self.assertEqual(g.transfer(1,1,seller,swapped['id'],0,list(range(4)))['status'],'invalid')

    def test_old_week_and_active_battle(self):
        g = self.game
        seller, f, ids, fee = self.find_offer([[]])
        with self.assertRaises(ValueError):
            g.transfer(1,0,seller,f['id'],fee,ids,True)
        state = g.overview()
        team = [dict(id=x['id'], row='front', skills=x['skills'])
                for x in state['roster'] if x['recommended']]
        g.start(next(z['id'] for z in state['zones'] if z['selectable']),team,practice=True)
        self.assertEqual(g.transfer(1,1,seller,f['id'],fee,ids,True)['status'],'market_closed')
