"""Season-trend (B), terrain (C), and always-visible opponent intelligence."""
import base64
import hashlib
import json
import unittest
import zlib
from random import Random

from campaign import Campaign
from combat import Battle, Unit
from combat_environment import (season_trend, zone_terrain, combat_context,
                                damage_multiplier, healing_multiplier, simulated_power_bonus)
from moonpa_savegame import create_save, load_save


class BCMetaTests(unittest.TestCase):
    def test_season_trends_are_deterministic_and_rotate(self):
        for seed in (2, 23, 310):
            one = [season_trend(seed, season) for season in range(1, 11)]
            two = [season_trend(seed, season) for season in range(1, 11)]
            self.assertEqual(one, two)
            self.assertTrue(all(a['id'] != b['id'] for a, b in zip(one, one[1:])))
            self.assertGreaterEqual(len(set(x['id'] for x in one)), 3)

    def test_each_zone_has_permanent_terrain(self):
        environments = [zone_terrain(i) for i in range(48)]
        self.assertEqual(environments, [zone_terrain(i) for i in range(48)])
        self.assertEqual(len({x['id'] for x in environments}), 6)

    def test_combat_damage_is_context_sensitive_and_bounded(self):
        def run(context):
            attacker=Unit(1,0,1,'검객','front',[80]*8,5,('strike',))
            target=Unit(2,1,0,'수호자','front',[80]*8,5,('wall',))
            attacker.attrs[6]=0
            battle=Battle([attacker,target]+[
                Unit(10+i, side, 4, str(i), 'back', [80]*8, 5, ('heal',))
                for i,side in enumerate((0,0,1,1))
            ],77,context=context)
            before=target.hp
            battle.damage(attacker,target,1,Random(2),'hit')
            return before-target.hp
        plain=run({})
        boosted=run({'trend':'vanguard','terrain':'plain','enemy_style':'balanced'})
        self.assertGreaterEqual(boosted,plain)
        self.assertLessEqual(boosted,round(plain*1.21)+1)
        a=Unit(7,0,4,'의원','back',[80]*8,5,('heal',))
        self.assertEqual(healing_multiplier({},a),1)
        self.assertEqual(healing_multiplier({'trend':'healing','terrain':'river'},a),1.20)

    def test_prebattle_information_matches_actual_battle_context(self):
        game=Campaign(23)
        view=game.overview()
        self.assertEqual(view['season_trend'],season_trend(23,game.season))
        zone=next(z for z in view['zones'] if z['selectable'] and z['owner'] is not None)
        self.assertEqual(zone['terrain'],zone_terrain(zone['id']))
        self.assertEqual(len(zone['enemy_lineup']),5)
        self.assertTrue(all('role' in f and 'row' in f for f in zone['enemy_lineup']))
        fighters=[f for f in view['roster'] if f['recommended']]
        setup=[dict(id=f['id'],row='front' if i<2 else 'back',
                    skills=list(f['skills'][:f['slots']]))
               for i,f in enumerate(fighters)]
        game.start(zone['id'],setup,practice=True)
        self.assertEqual(game.battle.context,
                         combat_context(game.seed,game.season,zone['id'],zone['tactic']['id']))
        self.assertEqual(game.battle_state()['environment']['tactic'],zone['tactic'])
        restored=load_save(create_save(game))
        self.assertEqual(restored.battle.context,game.battle.context)
        self.assertEqual(restored.battle_state(),game.battle_state())

    def test_older_in_progress_battle_save_can_still_load(self):
        game=Campaign(23)
        view=game.overview()
        zone=next(z for z in view['zones'] if z['selectable'])
        fighters=[f for f in view['roster'] if f['recommended']]
        setup=[dict(id=f['id'],row='front' if i<2 else 'back',
                    skills=list(f['skills'][:f['slots']]))
               for i,f in enumerate(fighters)]
        game.start(zone['id'],setup,practice=True)
        blob=create_save(game)
        graph=json.loads(zlib.decompress(base64.b64decode(blob['data'])))
        battles=[x for x in graph['nodes'] if x.get('class')=='Battle']
        self.assertEqual(len(battles),1)
        del battles[0]['attributes']['context']
        raw=json.dumps(graph,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        blob['data']=base64.b64encode(zlib.compress(raw)).decode('ascii')
        blob['checksum']=hashlib.sha256(raw).hexdigest()
        loaded=load_save(blob)
        self.assertEqual(loaded.battle.context,{})
        loaded.step()

if __name__=='__main__':
    unittest.main()
