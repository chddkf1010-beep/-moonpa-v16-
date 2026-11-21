"""Full-game v3 JSON save/restore, integrity and deterministic replay."""
import base64
import copy
import hashlib
import json
import unittest
import zlib

from campaign import Campaign
from combat import SECRET_SKILLS
from moonpa_savegame import create_save, load_save, SaveError, FORMAT, VERSION


class SaveGameTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23)

    def test_roundtrip_preserves_world_references_and_rng(self):
        original=self.game
        rng_before=original.world.rng.getstate()
        cp_before=original.world.checkpoints
        view=original.overview()
        blob=create_save(original)
        self.assertEqual(blob['format'],FORMAT)
        self.assertEqual(blob['version'],VERSION)
        self.assertEqual(original.world.checkpoints,cp_before)
        self.assertEqual(original.world.rng.getstate(),rng_before)
        restored=load_save(blob)
        self.assertIsNot(restored,original)
        self.assertIs(restored.guild,restored.world.guilds[restored.guild.gid])
        self.assertIs(restored.world.money.world,restored.world)
        self.assertEqual(restored.world.rng.getstate(),rng_before)
        self.assertEqual(restored.overview(),view)
        self.assertEqual(restored.world.checkpoints,cp_before)
        self.assertEqual(restored.world.money.reconcile(),original.world.money.reconcile())

    def test_next_week_after_reload_has_identical_economy_and_fighters(self):
        original=self.game
        cloned=load_save(create_save(original))
        original.submit_week(1,1,{})
        cloned.submit_week(1,1,{})
        self.assertEqual(original.week_report,cloned.week_report)
        self.assertEqual(original.overview(),cloned.overview())
        self.assertEqual(original.world.money.transactions,cloned.world.money.transactions)
        self.assertEqual(original.world.rng.getstate(),cloned.world.rng.getstate())
        original.submit_week(1,2,{})
        cloned.submit_week(1,2,{})
        self.assertEqual(original.week_report,cloned.week_report)

    def test_quest_expedition_and_permanent_rewards_survive_reload(self):
        game=self.game
        f1,f2=game.guild.fighters[:2]
        game.world.kiyun_manuals[f1.fid]=2
        game.world.kiyun_bonds[tuple(sorted((f1.fid,f2.fid)))]=35
        f1.development.saga=dict(line='starlight',status='active',next_chapter=1,
                                 started=53,deadline=66,attempts=0,setbacks=0,ethos=1)
        f1.development.secret_arts.append(SECRET_SKILLS[f1.role])
        f1.development.personal_title='무림 신성'
        f1.development.story_events=[dict(season=1,week=1,title='서장',outcome='success')]
        offer=next(x for x in game.overview()['long_mission_board'] if x['duration']==2)
        crew=[f.fid for f in game.guild.fighters[3:6]]
        game.submit_week(1,1,{'long_orders':[dict(id=offer['id'],members=crew)]})
        state=game.overview()
        self.assertEqual(len(state['long_missions']),1)
        saved=load_save(create_save(game))
        self.assertEqual(saved.overview(),state)
        self.assertEqual(saved.world.kiyun_bonds,game.world.kiyun_bonds)
        fnext=next(f for f in saved.guild.fighters if f.fid==f1.fid)
        self.assertEqual(fnext.development.secret_arts,[SECRET_SKILLS[f1.role]])
        self.assertEqual(fnext.development.saga['line'],'starlight')
        self.assertEqual(fnext.development.story_events,f1.development.story_events)
        self.assertEqual(saved.world.away(saved.guild.gid),set(crew))
        action=[dict(id=offer['id'],choice='safe')]
        game.submit_week(1,2,{'long_actions':action})
        saved.submit_week(1,2,{'long_actions':action})
        self.assertEqual(game.week_report,saved.week_report)

    def test_mid_battle_and_week_settlement_resume_identically(self):
        game=self.game
        view=game.overview()
        zone=next(z['id'] for z in view['zones'] if z['selectable'] and z['owner'] is None)
        fighters=[f for f in view['roster'] if f['recommended']]
        setup=[dict(id=f['id'],row='front' if i<2 else 'back',
                    skills=list(f['skills'][:f['slots']]))
               for i,f in enumerate(fighters)]
        game.submit_week(1,1,{'attack':{'zone':zone,'setup':setup}})
        self.assertIsNotNone(game.pending_week)
        game.step()
        self.assertIsNotNone(game.battle)
        backup=create_save(game)
        loaded=load_save(backup)
        self.assertIsNotNone(loaded.pending_week)
        self.assertEqual(loaded.battle_state(),game.battle_state())
        self.assertIs(loaded.zone,loaded.world.zones[zone])
        self.assertIs(loaded.pending_week['attack'][0] if loaded.pending_week['attack']
                      else loaded.pending_week['training'][0],
                      next(f for f in loaded.guild.fighters if
                           f.fid in {x.fid for x in (loaded.pending_week['attack'] or loaded.pending_week['training'])}))
        game.step(finish=True)
        loaded.step(finish=True)
        self.assertEqual(loaded.result,game.result)
        self.assertEqual(loaded.week_report,game.week_report)
        self.assertEqual(loaded.world.money.reconcile(),game.world.money.reconcile())
        game.dismiss_battle()
        loaded.dismiss_battle()
        self.assertEqual(game.overview(),loaded.overview())

    def test_practice_battle_roundtrip(self):
        game=self.game
        view=game.overview()
        setup=[dict(id=f['id'],row='front' if index<2 else 'back',
                    skills=list(f['skills'][:f['slots']]))
               for index,f in enumerate(x for x in view['roster'] if x['recommended'])]
        zone=next(z['id'] for z in view['zones'] if z['selectable'])
        game.start(zone,setup,practice=True)
        game.step()
        loaded=load_save(create_save(game))
        self.assertEqual(loaded.battle_state(),game.battle_state())
        loaded.step(finish=True)
        self.assertEqual(loaded.week,1)
        loaded.dismiss_battle()
        self.assertIsNone(loaded.battle)

    def test_interactive_draft_is_restored_without_losing_order(self):
        game=Campaign(23,interactive=True)
        snapshot=load_save(create_save(game))
        self.assertEqual(snapshot.overview(),game.overview())
        game.advance_phase('tutorial')
        loaded=load_save(create_save(game))
        self.assertEqual(loaded.phase,'draft')
        self.assertIs(loaded.draft_order[loaded.draft_cursor],
                      loaded.world.guilds[loaded.draft_order[loaded.draft_cursor].gid])
        for _ in range(5):
            options=game.draft_view()['candidates']
            pick=options[0]['id'] if options and len(game.guild.fighters)<30 else None
            game.draft_pick(game.season,game.draft_round,pick)
            loaded.draft_pick(loaded.season,loaded.draft_round,pick)
        self.assertEqual(loaded.overview(),game.overview())
        self.assertEqual(loaded.world.rng.getstate(),game.world.rng.getstate())

    def test_rejects_corrupted_data_without_changing_original(self):
        game=self.game
        original=game.overview()
        save=create_save(game)
        invalid=copy.deepcopy(save)
        invalid['checksum']='0'*64
        with self.assertRaises(SaveError):load_save(invalid)
        self.assertEqual(game.overview(),original)
        invalid=copy.deepcopy(save)
        invalid['version']=999
        with self.assertRaises(SaveError):load_save(invalid)
        invalid=copy.deepcopy(save)
        invalid['data']='invalid???'
        with self.assertRaises(SaveError):load_save(invalid)
        invalid=copy.deepcopy(save)
        invalid['meta']['week']=999
        with self.assertRaises(SaveError):load_save(invalid)
        self.assertEqual(game.overview(),original)

    def test_rejects_unknown_classes_even_with_recomputed_checksum(self):
        save=create_save(self.game)
        graph=json.loads(zlib.decompress(base64.b64decode(save['data'])))
        self.assertEqual(graph['nodes'][0]['class'],'Campaign')
        graph['nodes'][0]['class']='__unsafe__'
        raw=json.dumps(graph,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        save['checksum']=hashlib.sha256(raw).hexdigest()
        save['data']=base64.b64encode(zlib.compress(raw)).decode('ascii')
        with self.assertRaises(SaveError):
            load_save(save)

    def test_bridge_import_error_is_atomic(self):
        import pages_bridge
        old=pages_bridge.game
        state=pages_bridge.handle('state','{}')
        valid=json.loads(pages_bridge.handle('export_save','{}'))
        self.assertEqual(json.loads(pages_bridge.handle('import_save',json.dumps({'save':valid}))),
                         json.loads(state))
        new=pages_bridge.game
        bad=dict(valid,checksum='0'*64)
        with self.assertRaises(SaveError):
            pages_bridge.handle('import_save',json.dumps({'save':bad}))
        self.assertIs(pages_bridge.game,new)
        self.assertNotEqual(pages_bridge.game,old)
        self.assertEqual(pages_bridge.handle('state','{}'),state)


if __name__=='__main__':
    unittest.main()
