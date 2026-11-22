"""Live 8v8 arena tactical presets share the real campaign's save and combat data."""
import copy
import json
import unittest

from campaign import Campaign, territory_battlefield
import moonpa_prebattle as prebattle
from moonpa_savegame import create_save, load_save
import pages_bridge


class ArenaTacticsSaveTests(unittest.TestCase):
    def setUp(self):
        self.g=Campaign(23,interactive=True)
        self.g.phase='ready'
        self.attack=prebattle.arena_view(self.g,'attack')

    def save(self, config, arts=None):
        return prebattle.arena_save(self.g,config['planMode'],config['zone'],
                                   [dict(id=x['id'],line=x['line'],slot=x['slot'])
                                    for x in config['team']],
                                   config['captain'],config['deputy'],
                                   arts or ['tiger','wall'])

    def test_real_roster_terrain_and_explicit_no_settlement(self):
        config=self.attack
        actual={f.fid for f in self.g.guild.fighters}
        self.assertEqual(config['kind'],'training')
        self.assertEqual(config['mode'],8)
        self.assertEqual({x['id'] for x in config['team']}<=actual,True)
        self.assertEqual({x['id'] for x in config['bench']}.isdisjoint(
                         {x['id'] for x in config['team']}),True)
        self.assertEqual(len(config['enemyRoster']),8)
        self.assertEqual(config['terrain'],
                         territory_battlefield(config['zone'])['id'])
        self.assertEqual(len(config['chosenArts']),2)
        self.assertEqual(self.g.phase,'ready')
        self.assertIsNone(self.g.battle)
        self.assertIsNone(self.g.group_play)

    def test_tactics_save_keeps_cash_rng_world_and_restores_full_preset(self):
        g=self.g
        setup=self.attack
        before=(g.guild.cash, g.world.rng.getstate(),g.world.money.transactions,
                [(z.zid,z.owner) for z in g.world.zones],g.week,g.phase)
        saved=self.save(setup,['tiger','wall'])
        self.assertTrue(saved['saved'])
        key=g.world.prebattle_plans['attack']
        self.assertEqual(key['source'],'arena')
        self.assertEqual(key['arts'],['tiger','wall'])
        reopened=prebattle.arena_view(g,'attack',setup['zone'])
        self.assertEqual(reopened['team'],setup['team'])
        self.assertEqual(reopened['chosenArts'],['tiger','wall'])
        self.assertEqual(before,(g.guild.cash,g.world.rng.getstate(),g.world.money.transactions,
                [(z.zid,z.owner) for z in g.world.zones],g.week,g.phase))
        restored=load_save(create_save(g))
        self.assertEqual(prebattle.arena_view(restored,'attack',setup['zone']),reopened)

    def test_uses_saved_tactics_in_actual_territory_battle(self):
        g=self.g
        config=self.attack
        self.save(config,['tiger','wall'])
        zone=next(z for z in g.world.zones if z.zid==config['zone'])
        own=[next(f for f in g.guild.fighters if f.fid==u['id'])
             for u in config['team']]
        group=g.group_config('territory',own,g.world.guilds.get(zone.owner),zone)
        self.assertEqual(group['chosenArts'],['tiger','wall'])
        self.assertEqual({u['id'] for u in group['team']},
                         {u['id'] for u in config['team']})
        self.assertEqual(group['captain'],config['captain'])
        self.assertEqual(group['deputy'],config['deputy'])
        self.assertEqual([(u['id'],u['line'],u['slot']) for u in group['team']],
                         [(u['id'],u['line'],u['slot']) for u in config['team']])

    def test_defense_preset_is_saved_separately_and_uses_real_formation(self):
        g=self.g
        home=next(z.zid for z in g.world.zones if z.owner==g.guild.gid
                  and z.tier==g.guild.tier)
        defense=prebattle.arena_view(g,'defense',home)
        self.assertTrue(defense['opponentIsHypothetical'])
        self.save(defense,['lotus','turtle'])
        garrison=next(z for z in g.world.zones if z.zid==home)
        own=[next(f for f in g.guild.fighters if f.fid==u['id']) for u in defense['team']]
        rival=next(x for x in g.world.guilds.values() if x.gid!=g.guild.gid)
        actual=g.group_config('defense',own,rival,garrison)
        self.assertEqual(actual['chosenArts'],['lotus','turtle'])
        self.assertEqual(actual['captain'],defense['captain'])
        self.assertEqual(actual['deputy'],defense['deputy'])
        self.assertNotIn('attack',g.world.prebattle_plans)
        self.assertEqual(prebattle.arena_view(g,'defense',home)['chosenArts'],
                         ['lotus','turtle'])

    def test_invalid_presets_are_atomic(self):
        g=self.g
        config=self.attack
        good=[dict(id=x['id'],line=x['line'],slot=x['slot']) for x in config['team']]
        original=create_save(g)
        invalid=[
            (good[:-1],['tiger','wall']),
            ([dict(good[0]),*good[1:-1],dict(good[0])],['tiger','wall']),
            (good,['tiger','tiger']),
            (good,['unknown','wall']),
            ([dict(good[0],slot=1000),*good[1:]],['tiger','wall']),
            ([dict(good[0],id=-999999),*good[1:]],['tiger','wall']),
        ]
        for formation,arts in invalid:
            with self.subTest(formation=formation,arts=arts),self.assertRaises(ValueError):
                prebattle.arena_save(g,'attack',config['zone'],formation,
                                     config['captain'],config['deputy'],arts)
            self.assertEqual(create_save(g),original)

    def test_bridge_and_week_change_keep_reusable_formation(self):
        game=self.g
        config=self.attack
        original=pages_bridge.game
        try:
            pages_bridge.game=game
            view=json.loads(pages_bridge.handle('prebattle_arena_view',
                    json.dumps({'mode':'attack','zone_id':config['zone']})))
            self.assertEqual(view['kind'],'training')
            payload={'mode':'attack','zone_id':config['zone'],
                     'team':[{key:item[key] for key in ('id','line','slot')}
                             for item in config['team']],
                     'captain':config['captain'],'deputy':config['deputy'],
                     'chosenArts':['fog','mercy']}
            saved=json.loads(pages_bridge.handle('prebattle_arena_save',json.dumps(payload)))
            self.assertTrue(saved['saved'])
            game.week+=1
            reopened=prebattle.arena_view(game,'attack')
            self.assertEqual(reopened['chosenArts'],['fog','mercy'])
            self.assertEqual({u['id'] for u in reopened['team']},{u['id'] for u in view['team']})
        finally:
            pages_bridge.game=original


if __name__=='__main__':
    unittest.main()
