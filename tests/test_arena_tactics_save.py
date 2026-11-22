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

    def test_all_owned_fighters_are_visible_including_injured_and_busy(self):
        g=self.g
        injured=g.guild.fighters[0]
        injured.injured=3
        attack=prebattle.arena_view(g,'attack')
        visible=attack['team']+attack['bench']
        self.assertEqual({x['id'] for x in visible},
                         {f.fid for f in g.guild.fighters})
        self.assertEqual(len(visible),len(g.guild.fighters))
        wounded=next(x for x in visible if x['id']==injured.fid)
        self.assertEqual(wounded['injured'],3)
        self.assertFalse(wounded['available'])
        self.assertEqual(wounded['reason'],'부상')
        # Strategy may include the injured person and be saved, unlike a
        # real battle/weekly assignment.
        if injured.fid not in {x['id'] for x in attack['team']}:
            source=next(x for x in attack['bench'] if x['id']==injured.fid)
            replacement=attack['team'][-1]
            attack['bench']=[x for x in attack['bench'] if x['id']!=injured.fid]+[replacement]
            attack['team'][-1]=dict(source,line=replacement['line'],slot=replacement['slot'])
            if attack['captain']==replacement['id']:
                attack['captain']=attack['team'][0]['id']
            if attack['deputy']==replacement['id']:
                attack['deputy']=attack['team'][1]['id']
        saved=self.save(attack)
        self.assertTrue(saved['saved'])
        self.assertIn(injured.fid,
                      {u['id'] for u in g.world.prebattle_plans['attack']['data']['formation']})

    def test_defense_save_without_owned_zone_and_independent_mode(self):
        g=self.g
        self.save(self.attack,['rain','wall'])
        opponent=next(guild.gid for guild in g.world.guilds.values()
                      if guild.gid!=g.guild.gid and guild.tier==g.guild.tier)
        for zone in g.world.zones:
            if zone.owner==g.guild.gid:
                zone.owner=opponent
        defense=prebattle.arena_view(g,'defense')
        self.assertEqual(defense['planMode'],'defense')
        self.assertEqual(len(defense['team'])+len(defense['bench']),len(g.guild.fighters))
        self.assertEqual(defense['zoneName'],'공통 전술 연무장')
        self.assertTrue(self.save(defense,['lotus','turtle'])['saved'])
        self.assertEqual(g.world.prebattle_plans['attack']['arts'],['rain','wall'])
        self.assertEqual(g.world.prebattle_plans['defense']['arts'],['lotus','turtle'])
        self.assertEqual(prebattle.arena_view(g,'defense')['chosenArts'],['lotus','turtle'])

    def test_injured_preset_member_is_not_in_real_battle(self):
        g=self.g
        draft=self.attack
        self.save(draft,['tiger','wall'])
        wounded_id=draft['team'][0]['id']
        injured=next(f for f in g.guild.fighters if f.fid==wounded_id)
        injured.injured=3
        real=[f for f in g.guild.fighters if not f.injured][:8]
        zone=next(z for z in g.world.zones if z.zid==draft['zone'])
        enemy=g.world.guilds.get(zone.owner)
        live=g.group_config('territory',real,enemy,zone)
        self.assertNotIn(wounded_id,{u['id'] for u in live['team']})
        self.assertEqual(live['chosenArts'],['tiger','wall'])
        for member in live['team']:
            previous=next((x for x in draft['team'] if x['id']==member['id']),None)
            if previous:
                self.assertEqual((member['line'],member['slot']),
                                 (previous['line'],previous['slot']))

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
