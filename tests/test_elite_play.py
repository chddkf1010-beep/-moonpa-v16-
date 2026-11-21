"""Playable elite quests, real tactical results, double mission and save regression."""
import base64
import hashlib
import json
import unittest
import zlib

from campaign import Campaign, equipment, unit
import moonpa_elite_play as playable
from moonpa_savegame import create_save, load_save


class ElitePlayTests(unittest.TestCase):
    def setUp(self):
        self.g=Campaign(23,interactive=True)
        self.g.phase='ready'
        self.ids=[f.fid for f in self.g.guild.fighters]
        self.card=self.g.overview()['elite_board'][0]

    def order(self,member_count=3,choice='study'):
        return dict(id=self.card['id'],members=self.ids[:member_count],
                    lead=self.ids[0],choice=choice)

    def begin(self,assignment=None):
        self.g.submit_week(1,1,assignment or {'elite_order':self.order()})
        self.assertEqual(self.g.phase,'elite')
        self.assertIsNone(self.g.battle)
        self.assertIsNotNone(self.g.pending_week)

    def inspect(self,choice='study'):
        self.g.elite_inspect()
        self.g.elite_decide(choice)
        self.assertEqual(self.g.elite_play['stage'],'battle')
        self.assertEqual(self.g.battle_state()['kind'],'elite')

    def test_investigation_choice_combat_spoils_and_exactly_one_settlement(self):
        original_cash=self.g.guild.cash
        tx_before=self.g.world.money.transactions
        self.begin()
        scene=self.g.overview()['elite_play']
        self.assertEqual(scene['stage'],'scene')
        self.assertEqual(len(scene['team']),3)
        self.assertEqual(self.g.week,1)
        self.assertEqual(self.g.world.money.transactions,tx_before)
        with self.assertRaises(ValueError):self.g.elite_finish()
        with self.assertRaises(ValueError):self.g.elite_decide('study')
        self.g.elite_inspect()
        self.assertEqual(self.g.overview()['elite_play']['stage'],'decision')
        with self.assertRaises(ValueError):self.g.elite_decide('unknown')
        self.g.elite_decide('guard')
        self.assertEqual(len(self.g.battle.units),6)
        self.assertEqual({x.side for x in self.g.battle.units.values()}, {0,1})
        with self.assertRaises(ValueError):self.g.elite_inspect()
        self.g.step(finish=True)
        self.assertEqual(self.g.elite_play['stage'],'aftermath')
        self.assertEqual(self.g.week,1)
        self.assertEqual(self.g.world.money.transactions,tx_before)
        result=self.g.pending_week['elite_override']
        self.assertTrue(result['manual_play'])
        self.assertIn('combat',result)
        self.assertIn(result['outcome'],('success','exceptional','partial','failure'))
        self.assertEqual(result['choice'],'guard')
        self.assertEqual(result['combat']['won'],self.g.battle.winner==0)
        self.g.elite_finish()
        self.assertEqual(self.g.week,2)
        self.assertEqual(self.g.phase,'report')
        self.assertIsNone(self.g.pending_week)
        self.assertIsNone(self.g.elite_play)
        report=self.g.week_report
        self.assertEqual(len(report['elite_missions']),1)
        self.assertEqual(report['elite_missions'][0]['combat'],result['combat'])
        self.assertEqual(sum(e['amount'] for e in report['entries']),report['cash_change'])
        self.assertEqual(self.g.guild.cash,original_cash+report['cash_change'])
        self.assertEqual(sum(e['category']=='elite_preparation' for e in report['entries']),1)
        self.assertEqual(sum(e['category']=='elite_reward' for e in report['entries']),1)
        self.g.world.money.reconcile()
        with self.assertRaises(ValueError):self.g.elite_finish()

    def test_choice_changes_enemy_difficulty(self):
        team=self.g.guild.fighters[:5]
        order=dict(offer=self.card,members=team,lead=team[0],choice='study')
        make=lambda choice:playable.make_battle(self.g.seed,self.g.guild.gid,1,1,
                              order,choice,unit,equipment)
        cautious=make('guard')
        risky=make('seize')
        self.assertEqual(cautious.seed!=risky.seed,True)
        self.assertEqual(len(cautious.units),10)
        self.assertGreater(sum(x.attrs[0] for x in risky.units.values() if x.side==1),
                           sum(x.attrs[0] for x in cautious.units.values() if x.side==1))
        self.assertEqual([u.name for u in risky.units.values() if u.side==1],
                         [u.name for u in cautious.units.values() if u.side==1])
        self.assertEqual(risky.seed,make('seize').seed)

    def test_saves_at_every_interactive_stage_and_replays_same_result(self):
        self.begin()
        for stage in ('scene','decision','battle','aftermath'):
            if stage=='decision':self.g.elite_inspect()
            if stage=='battle':self.g.elite_decide('seize')
            if stage=='aftermath':self.g.step(finish=True)
            loaded=load_save(create_save(self.g))
            self.assertEqual(loaded.elite_play['stage'],stage)
            self.assertEqual(loaded.overview(),self.g.overview())
            self.assertIs(loaded.guild,loaded.world.guilds[loaded.guild.gid])
            if stage=='battle':
                self.g.step()
                loaded.step()
                self.assertEqual(loaded.battle_state(),self.g.battle_state())
                # Return both to a fresh game before next stage.
                self.g=load_save(create_save(loaded))
        restored=load_save(create_save(self.g))
        self.g.elite_finish()
        restored.elite_finish()
        self.assertEqual(self.g.week_report,restored.week_report)
        self.assertEqual(self.g.world.money.reconcile(),restored.world.money.reconcile())

    def test_same_week_zone_battle_runs_after_elite_without_double_spending(self):
        zone=next(z['id'] for z in self.g.overview()['zones']
                  if z['selectable'] and z['owner'] is None)
        defenders=self.g.guild.fighters[3:8]
        setup=[dict(id=f.fid,row='front' if index<2 else 'back',
                    skills=list(equipment(f)))
               for index,f in enumerate(defenders)]
        self.begin(dict(elite_order=self.order(),
                        attack=dict(zone=zone,setup=setup)))
        self.inspect('study')
        self.g.step(finish=True)
        self.assertTrue(self.g.overview()['elite_play']['next_attack'])
        self.g.elite_finish()
        self.assertIsNone(self.g.elite_play)
        self.assertIsNotNone(self.g.pending_week)
        self.assertEqual(self.g.battle_state()['kind'],'zone')
        self.assertEqual(self.g.week,1)
        self.g.step(finish=True)
        self.assertEqual(self.g.week,2)
        self.assertEqual(self.g.phase,'report')
        self.assertIsNotNone(self.g.week_report['battle'])
        self.assertEqual(len(self.g.week_report['elite_missions']),1)
        entries=self.g.week_report['entries']
        self.assertEqual(sum(x['category']=='elite_reward' for x in entries),1)
        self.assertEqual(sum(x['category']=='elite_preparation' for x in entries),1)
        self.assertEqual(sum(x['amount'] for x in entries),self.g.week_report['cash_change'])
        self.g.world.money.reconcile()

    def test_no_funds_blocks_elite_without_mutating_week(self):
        self.g.world.money.spend(self.g.guild,self.g.guild.cash,'test_setup')
        clock=self.g.week
        with self.assertRaisesRegex(ValueError,'준비비'):
            self.g.submit_week(1,1,{'elite_order':self.order()})
        self.assertEqual(self.g.week,clock)
        self.assertIsNone(self.g.pending_week)
        self.assertIsNone(self.g.elite_play)

    def test_elite_and_protected_zone_defense_share_budget_and_save(self):
        zone=next(z for z in self.g.world.zones if z.owner==self.g.guild.gid)
        crew=self.ids[3:8]
        self.begin(dict(elite_order=self.order(), defense=dict(zone=zone.zid,members=crew),
                        mission_orders=[]))
        self.assertEqual(self.g.pending_week['home'],zone.zid)
        self.assertEqual([f.fid for f in self.g.pending_week['defend']],crew)
        self.assertGreater(self.g.pending_week['budget']['preparation'],0)
        self.g.elite_inspect()
        self.g.elite_decide('guard')
        self.g.step(finish=True)
        restored=load_save(create_save(self.g))
        self.assertEqual(restored.pending_week['home'],zone.zid)
        restored.elite_finish()
        self.assertEqual(restored.phase,'report')
        self.assertEqual(restored.week_report['briefing']['defense_plan']['zone'],zone.zid)
        self.assertEqual(restored.week_report['budget'],
                         self.g.pending_week['budget'])
        self.assertEqual(len(restored.week_report['elite_missions']),1)
        restored.world.money.reconcile()

    def test_older_v3_saves_without_elite_play_are_still_supported(self):
        game=Campaign(23,interactive=True)
        save=create_save(game)
        graph=json.loads(zlib.decompress(base64.b64decode(save['data'])))
        del graph['nodes'][0]['attributes']['elite_play']
        raw=json.dumps(graph,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')
        save['checksum']=hashlib.sha256(raw).hexdigest()
        save['data']=base64.b64encode(zlib.compress(raw)).decode('ascii')
        restored=load_save(save)
        self.assertIsNone(restored.elite_play)
        self.assertEqual(restored.overview(),game.overview())


if __name__=='__main__':
    unittest.main()
