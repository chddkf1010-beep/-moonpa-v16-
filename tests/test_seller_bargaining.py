"""AI seller's multi-round contract negotiation, persistence and signing."""
import copy
import unittest

from campaign import Campaign
import moonpa_market as market
from moonpa_savegame import create_save, load_save


class SellerBargainingTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23)
        self.game.phase='ready'

    def find_cash_quote(self):
        game=self.game
        for item in game.scouting()['candidates']:
            offer=market.Offer(game.guild.gid,item['seller'],item['id'],0)
            state,quote=market.offer_status(game.world,offer,game.season)
            if state=='counter' and quote is not None:
                return item
        self.fail('No viable cash-only transfer quote found')

    def test_cash_counter_is_fully_real_and_only_commits_after_confirmation(self):
        g=self.game
        item=self.find_cash_quote()
        before=(g.guild.cash, len(g.guild.fighters),
                g.world.guilds[item['seller']].cash,g.world.rng.getstate())
        offer=g.transfer_bargain(1,1,item['seller'],item['id'],0,[])
        self.assertEqual(offer['status'],'counter')
        self.assertEqual(offer['turn'],1)
        self.assertIn('현금',offer['message'])
        self.assertEqual(offer['history'][0]['offered']['fee'],0)
        terms=offer['terms']
        self.assertEqual(market.offer_status(g.world,market.Offer(
            g.guild.gid,item['seller'],item['id'],terms['fee'],
            tuple(terms['exchange'])),1)[0],'accepted')
        self.assertEqual((g.guild.cash,len(g.guild.fighters),
                          g.world.guilds[item['seller']].cash,g.world.rng.getstate()),before)
        copy_game=load_save(create_save(g))
        self.assertEqual(copy_game.transfer_talk_view(1,1,item['seller'],item['id']),offer)
        wrong=g.transfer_bargain_accept(1,1,item['seller'],item['id'],999)
        self.assertEqual(wrong['status'],'stale')
        result=g.transfer_bargain_accept(1,1,item['seller'],item['id'],offer['revision'])
        self.assertEqual(result['status'],'signed')
        self.assertEqual(result['transfer']['status'],'signed')
        self.assertEqual(g.guild.cash,before[0]-terms['fee'])
        self.assertEqual(g.world.guilds[item['seller']].cash,before[2]+terms['fee'])
        self.assertEqual(g.transfer_talks[(item['seller'],item['id'])]['status'],'signed')
        g.world.money.reconcile()
        load_save(create_save(g))

    def test_specific_fighter_and_cash_counter_uses_valid_owned_members(self):
        g=self.game
        found=None
        for card in g.scouting()['candidates']:
            seller=g.world.guilds[card['seller']]
            target=next(f for f in seller.fighters if f.fid==card['id'])
            essential,_=market.seller_needs(seller,target)
            if not essential:continue
            response=market.seller_bargain(g.world,g.guild,seller,target,g.season,
                market.Offer(g.guild.gid,seller.gid,target.fid,0))
            if response['status']=='counter' and response['offer'].exchange:
                found=(seller,target,response)
                break
        self.assertIsNotNone(found,'A viable core fighter must be able to demand an explicit replacement')
        seller,target,response=found
        wanted=response['offer'].exchange
        own_ids={f.fid for f in g.guild.fighters}
        self.assertTrue(set(wanted).issubset(own_ids))
        self.assertEqual([d['id'] for d in response['demands']],list(wanted))
        self.assertTrue(all(d['name'] for d in response['demands']))
        self.assertEqual(market.offer_status(g.world,response['offer'],g.season)[0],'accepted')
        self.assertEqual(g.world.rng.getstate(),g.world.rng.getstate())
        actual=g.transfer_bargain(1,1,seller.gid,target.fid,0,[])
        self.assertEqual(actual['status'],'counter')
        self.assertEqual(actual['terms']['exchange'],list(wanted))
        revived=load_save(create_save(g))
        self.assertEqual(revived.transfer_talk_view(1,1,seller.gid,target.fid)['terms'],actual['terms'])

    def test_reoffer_turn_limit_close_and_no_upfront_charge(self):
        g=self.game
        item=self.find_cash_quote()
        first=g.transfer_bargain(1,1,item['seller'],item['id'],0,[])
        wallet=g.guild.cash
        second=g.transfer_bargain(1,1,item['seller'],item['id'],0,[])
        self.assertEqual(second['turn'],2)
        self.assertEqual(len(second['history']),2)
        third=g.transfer_bargain(1,1,item['seller'],item['id'],0,[])
        last=g.transfer_bargain(1,1,item['seller'],item['id'],0,[])
        self.assertEqual(last['turn'],4)
        self.assertEqual(g.transfer_bargain(1,1,item['seller'],item['id'],0,[])['revision'],4)
        self.assertEqual(g.guild.cash,wallet)
        declined=g.transfer_bargain_decline(1,1,item['seller'],item['id'],last['revision'])
        self.assertEqual(declined['status'],'closed')
        self.assertEqual(g.transfer_bargain(1,1,item['seller'],item['id'],500,[])['status'],'closed')
        self.assertEqual(g.transfer_bargain_accept(1,1,item['seller'],item['id'],last['revision'])['status'],'stale')
        load_save(create_save(g))

    def test_bad_terms_do_not_change_game(self):
        g=self.game; item=self.find_cash_quote()
        before=create_save(g)
        for fee,exchange in [(-1,[]),(1,[True]),(1,[1,1]),(1,list(range(4)))]:
            with self.subTest(fee=fee,exchange=exchange),self.assertRaises(ValueError):
                g.transfer_bargain(1,1,item['seller'],item['id'],fee,exchange)
            self.assertEqual(create_save(g),before)
        with self.assertRaises(ValueError):
            g.transfer_bargain(1,0,item['seller'],item['id'],100,[])
        self.assertEqual(create_save(g),before)


if __name__=='__main__':
    unittest.main()
