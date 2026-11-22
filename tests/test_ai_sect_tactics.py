"""Regression: AI sect doctrine changes real battles, not only names."""
import copy
import unittest
from types import SimpleNamespace

from campaign import Campaign, group_fighters, zone_intelligence
from moonpa_names import GUILD_NAMES
from moonpa_ai_tactics import NAME_TO_TACTIC, TACTICS, sect_tactic, tactical_formation
from moonpa_prebattle import _enemy_squad, arena_view
from moonpa_savegame import create_save, load_save


class SectTacticsTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23, interactive=True)
        self.game.phase='ready'

    def test_all_32_initial_sects_have_explicit_doctrines_and_distinct_arts(self):
        names={name for tier in GUILD_NAMES.values() for name in tier}
        self.assertEqual(names,set(NAME_TO_TACTIC))
        self.assertEqual(len(names),32)
        self.assertGreaterEqual(len(set(NAME_TO_TACTIC.values())),6)
        profiles={name:sect_tactic(SimpleNamespace(name=name,gid=1,strategy='balanced'))
                  for name in names}
        self.assertEqual(profiles['사천당문']['arts'],['wing','rain'])
        self.assertEqual(profiles['소림사']['arts'],['lotus','mercy'])
        self.assertEqual(profiles['무당파']['arts'],['silence','fog'])
        self.assertGreaterEqual(len({tuple(p['arts']) for p in profiles.values()}),6)
        self.assertTrue(all(len(p['arts'])==2 and len(set(p['arts']))==2
                            for p in profiles.values()))

    def test_formation_differs_on_same_roster_without_creating_fighters(self):
        pool=[SimpleNamespace(fid=i+1,role=role,ca=100+i)
              for i,role in enumerate((0,0,1,1,2,3,4,5))]
        wall=tactical_formation(pool,'ironwall',3)
        raid=tactical_formation(pool,'breakthrough',3)
        self.assertNotEqual([f.role for f,r,i in wall if r=='front'],
                            [f.role for f,r,i in raid if r=='front'])
        for arranged in (wall,raid):
            self.assertEqual({f.fid for f,r,i in arranged},{f.fid for f in pool})
            self.assertEqual(len({(r,i) for f,r,i in arranged}),len(pool))
        self.assertEqual(tactical_formation(pool,'ironwall',3),wall)

    def test_real_group_uses_opponents_own_doctrine_and_lineup(self):
        game=self.game
        rng=game.world.rng.getstate()
        owners=[(z.zid,z.owner) for z in game.world.zones]
        ours=game.guild.fighters[:8]
        profiles=set()
        for enemy in game.world.guilds.values():
            if enemy.gid==game.guild.gid:continue
            zone=next(z for z in game.world.zones if z.tier==enemy.tier)
            packet=game.group_config('territory',ours,enemy,zone)
            expected=sect_tactic(enemy,group_fighters(game.world,enemy,8))
            profiles.add(packet['enemyTactic']['id'])
            self.assertEqual(packet['enemyTactic'],expected)
            self.assertEqual(packet['enemyArts'],expected['arts'])
            self.assertEqual({x['id'] for x in packet['enemyRoster']},
                             {x.fid for x in group_fighters(game.world,enemy,8)})
            self.assertEqual(len({(x['line'],x['slot']) for x in packet['enemyRoster']}),
                             len(packet['enemyRoster']))
            self.assertEqual(packet['enemyCaptain'] in
                             {x['id'] for x in packet['enemyRoster']},True)
            self.assertNotEqual(packet['enemyDeputy'],packet['enemyCaptain'])
        self.assertGreaterEqual(len(profiles),5)
        self.assertEqual(rng,game.world.rng.getstate())
        self.assertEqual(owners,[(z.zid,z.owner) for z in game.world.zones])

    def test_scout_preview_uses_same_tactic_as_real_group(self):
        game=self.game
        zone=next(z for z in game.world.zones if z.tier==game.guild.tier
                  and z.owner is not None and z.owner!=game.guild.gid
                  and z.protected_until<=game.clock)
        defender=game.world.guilds[zone.owner]
        scout=_enemy_squad(game,'attack',zone)
        live=game.group_config('territory',game.guild.fighters[:8],defender,zone)
        intelligence=zone_intelligence(game.world,zone)
        self.assertEqual(scout['tactic'],live['enemyTactic'])
        self.assertEqual(intelligence['sect_tactic'],live['enemyTactic'])
        self.assertEqual(scout['tactic']['arts'],live['enemyArts'])
        preview=arena_view(game,'attack',zone.zid)
        self.assertEqual(preview['enemyArts'],live['enemyArts'])
        self.assertEqual(preview['enemyTactic'],live['enemyTactic'])
        self.assertEqual({(m['id'],m['row']) for m in scout['members'] if m['id']>0},
                         {(m['id'],m['line']) for m in live['enemyRoster']})
        self.assertIn(preview['enemyCaptain'],{m['id'] for m in preview['enemyRoster']})

    def test_neutral_is_basic_militia_and_save_load_preserves_doctrines(self):
        game=self.game
        zone=next(z for z in game.world.zones if z.tier==game.guild.tier
                  and z.owner is None)
        packet=game.group_config('territory',game.guild.fighters[:8],None,zone)
        self.assertEqual(packet['enemyTactic']['id'],'militia')
        self.assertEqual(packet['enemyArts'],['wall','turtle'])
        before=create_save(game)
        restored=load_save(copy.deepcopy(before))
        self.assertEqual(restored.overview()['world_map'],
                         game.overview()['world_map'])
        self.assertEqual(restored.world.money.reconcile(),
                         game.world.money.reconcile())


if __name__=='__main__':
    unittest.main()
