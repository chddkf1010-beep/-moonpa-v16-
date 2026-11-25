import unittest
from campaign import Campaign
from moonpa_savegame import create_save,load_save
import moonpa_incoming as bids
import moonpa_economy_v15_1 as economy
from unittest.mock import patch

class IncomingTest(unittest.TestCase):
    def setUp(self):
        self.c=Campaign(23)
        self.c.week=2
        self.c.world.season_active=1
        self.target=next(f for f in self.c.guild.fighters if not f.injured and f.contract_end>=1)
        self.buyer=next(g for g in self.c.world.guilds.values() if g is not self.c.guild and abs(g.tier-self.c.guild.tier)<=1 and 15<=len(g.fighters)<30)
        self.c.world.money.credit(self.buyer,50000,'test_capital')

    def seeded_offer(self,fee=300,swap=None):
        d=self.c.incoming_market
        d['seq']=1
        d['offers'][1]=dict(id=1,buyer=self.buyer.gid,fighter=self.target.fid,fighter_name=self.target.name,fee=fee,exchange=swap or [],season=1,expires=self.c.clock+3,attempts=0,revision=1,status='open',reply='offered',listed=True)
        return d['offers'][1]

    def test_listing_roundtrip_no_cash_change(self):
        cash=self.c.guild.cash
        bids.listing(self.c,1,2,self.target.fid,300)
        self.assertEqual(self.c.guild.cash,cash)
        self.assertEqual(load_save(create_save(self.c)).incoming_market['listings'],{self.target.fid:300})
        bids.listing(self.c,1,2,self.target.fid,None)
        self.assertEqual(self.c.incoming_market['listings'],{})

    def test_old_save_without_market_field(self):
        # Encoder accepts the old layout; decoder supplies the optional field.
        import base64, hashlib, json, zlib
        from moonpa_savegame import Encoder
        envelope=create_save(self.c)
        del self.c.incoming_market
        raw=json.dumps(Encoder().encode(self.c),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
        envelope['data']=base64.b64encode(zlib.compress(raw,6)).decode('ascii')
        envelope['checksum']=hashlib.sha256(raw).hexdigest()
        restored=load_save(envelope)
        self.assertEqual(restored.incoming_market,bids.fresh())

    def test_generation_deterministic_and_no_transfer(self):
        bids.listing(self.c,1,2,self.target.fid,100)
        before=self.c.guild.cash
        rng=self.c.world.rng.getstate()
        with patch.object(bids,'package',side_effect=lambda c,g,f,a: ((1,1,100,0),100,[]) if g is self.buyer and f is self.target else None):
            bids.generate(self.c);bids.generate(self.c)
        self.assertEqual(len(self.c.incoming_market['offers']),1)
        self.assertEqual(self.c.guild.cash,before)
        self.assertIn(self.target,self.c.guild.fighters)
        self.assertEqual(self.c.world.rng.getstate(),rng)

    def test_counter_requires_confirmation_and_actual_cash_transfer(self):
        r=self.seeded_offer()
        before=self.c.guild.cash; other=self.buyer.cash; wage=self.target.wage; end=self.target.contract_end
        with patch.object(bids,'buyer_room',return_value=500):
            bids.respond(self.c,1,2,1,1,'counter',400,[])
            self.assertEqual(r['reply'],'agreed')
            self.assertEqual(self.c.guild.cash,before)
            self.assertIn(self.target,self.c.guild.fighters)
            with self.assertRaises(ValueError):bids.respond(self.c,1,2,1,1,'accept')
            bids.respond(self.c,1,2,1,2,'accept')
        self.assertEqual(self.c.guild.cash,before+400)
        self.assertEqual(self.buyer.cash,other-400)
        self.assertIn(self.target,self.buyer.fighters)
        self.assertEqual((self.target.wage,self.target.contract_end),(wage,end))
        self.assertEqual(r['status'],'accepted')
        self.c.world.money.reconcile()

    def test_real_buyer_constraints_and_reject(self):
        room=bids.buyer_room(self.c,self.buyer,self.target,[])
        self.assertIsInstance(room,int)
        self.target.injured=2
        self.assertEqual(bids.buyer_room(self.c,self.buyer,self.target,[]),-1)
        self.target.injured=0
        r=self.seeded_offer()
        with patch.object(bids,'buyer_room',return_value=500):
            bids.respond(self.c,1,2,1,1,'reject')
        self.assertEqual(r['status'],'rejected')
        self.assertIn(self.target,self.c.guild.fighters)

    def test_real_package_and_settlement(self):
        # Use real valuation, wage caps, reserve and role-need checks.
        # Capital injection is explicit in the ledger, not a mocked limit.
        for buyer in self.c.world.guilds.values():
            if buyer is not self.c.guild and abs(buyer.tier-self.c.guild.tier)<=1:
                self.c.world.money.credit(buyer,50000,'test_capital')
        candidate=next((f for f in self.c.guild.fighters if bids.available(self.c,self.c.guild,f)
            and any(g is not self.c.guild and abs(g.tier-self.c.guild.tier)<=1 and bids.package(self.c,g,f,100)
                    for g in self.c.world.guilds.values())),None)
        self.assertIsNotNone(candidate,'No feasible buyer under actual market rules')
        bids.listing(self.c,1,2,candidate.fid,100)
        bids.generate(self.c)
        row=next(r for r in self.c.incoming_market['offers'].values() if r['fighter']==candidate.fid)
        self.assertTrue(bids.active(self.c,row))
        game=load_save(create_save(self.c))
        row=game.incoming_market['offers'][row['id']]
        before=game.guild.cash
        buyer=game.world.guilds[row['buyer']]
        old=buyer.cash
        bids.respond(game,1,2,row['id'],row['revision'],'accept')
        self.assertEqual(game.guild.cash,before+row['fee'])
        self.assertEqual(buyer.cash,old-row['fee'])
        self.assertTrue(any(f.fid==candidate.fid for f in buyer.fighters))
        self.assertEqual(row['status'],'accepted')
        game.world.money.reconcile()

    def test_validation_and_expiry(self):
        r=self.seeded_offer()
        self.assertTrue(bids.valid_state(self.c.incoming_market))
        r['exchange']=[True]
        self.assertFalse(bids.valid_state(self.c.incoming_market))
        r['exchange']=[]
        self.c.week=5
        self.assertFalse(bids.active(self.c,r))
        bids.prune(self.c)
        self.assertEqual(r['status'],'expired')

if __name__=='__main__':unittest.main()
