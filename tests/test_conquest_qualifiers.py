import json
import unittest
from unittest.mock import patch

from campaign import Campaign, set_arena_resolver
import moonpa_economy_v15_1 as economy
from moonpa_savegame import create_save, load_save


class ContestedConquestTests(unittest.TestCase):
    def setUp(self):
        game=self.game=Campaign(23,interactive=True)
        game.phase='ready'
        self.site=next(z for z in game.world.zones if z.tier==game.guild.tier and z.owner is None)
        self.rival=next(g for g in game.world.guilds.values() if g.tier==game.guild.tier and g is not game.guild)
        self.post=next(z for z in game.world.zones if z.owner==game.guild.gid)
        self.site.protected_until=self.post.protected_until=0

    def scheduled(self,gid,zid,at_week):
        original=economy.prep_plan
        def plan(world,guild,week):
            assignment=original(world,guild,week)
            assignment['attack']=[]
            assignment['attack_target']=None
            if guild.gid==gid and week==at_week:
                reserved={f.fid for f in assignment['defend']}
                assignment['attack']=[f for f in guild.fighters if not f.injured and f.fid not in reserved][:8]
                assignment['attack_target']=zid
            return assignment
        return patch.object(economy,'prep_plan',side_effect=plan)

    @staticmethod
    def result(match,winner):
        return dict(winner=winner,events=[],units=[
            dict(id=f['id'],side=side,hp=100,max_hp=100,actions=1,healing=0,hit_taken=0)
            for side,key in enumerate(('team','enemyRoster')) for f in match[key] if f['id']>=0])

    def start(self):
        g=self.game
        team=[dict(id=f.fid) for f in g.guild.fighters if not f.injured][:8]
        with self.scheduled(self.rival.gid,self.site.zid,1):
            g.submit_week(1,1,dict(group_mode=True,attack=dict(zone=self.site.zid,setup=team)))
        self.assertEqual(g.group_play['kind'],'conquest_duel')
        self.assertEqual(len(g.group_play['team']),8)
        self.assertIsNone(self.site.owner)
        return load_save(create_save(g))

    def test_player_wins_qualifier_then_fights_garrison(self):
        game=self.start()
        duel=game.group_play
        game.finish_group(duel['match'],self.result(duel,0))
        final=game.group_play
        self.assertEqual(final['kind'],'territory')
        self.assertTrue(final['contestFinal'])
        self.assertEqual(final['sectNames'][1],'구역 수비대')
        self.assertIsNone(game.world.zones[self.site.zid].owner)
        with self.assertRaises(ValueError):
            game.finish_group(duel['match'],self.result(duel,0))
        game.finish_group(final['match'],self.result(final,0))
        self.assertEqual(game.world.zones[self.site.zid].owner,game.guild.gid)
        self.assertEqual(game.week_report['conquest_duels'][0]['winner'],game.guild.name)
        game.world.money.reconcile()

    def test_ai_wins_qualifier_and_final_is_spectated(self):
        game=self.start()
        match=game.group_play
        game.finish_group(match['match'],self.result(match,1))
        self.assertTrue(game.group_play['observer'])
        game=load_save(create_save(game))
        final=game.group_play
        self.assertEqual(final['kind'],'conquest_final')
        self.assertEqual(final['sectNames'][0],self.rival.name)
        game.finish_group(final['match'],self.result(final,0))
        self.assertEqual(game.world.zones[self.site.zid].owner,self.rival.gid)
        self.assertTrue(game.week_report['conquest_final']['success'])
        game.world.money.reconcile()

    def test_offscreen_ai_uses_the_arena_result_and_same_injury_rule(self):
        game=self.game
        captured=[]
        def resolve(raw):
            config=json.loads(raw)
            captured.append(config)
            result=self.result(config,0)
            result['units'][0]['hp']=0
            return json.dumps(result)
        set_arena_resolver(resolve)
        self.addCleanup(set_arena_resolver,None)
        with self.scheduled(self.rival.gid,self.site.zid,1):
            game.submit_week(1,1,dict(group_mode=True))
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0]['sectNames'][0],self.rival.name)
        self.assertEqual(game.world.zones[self.site.zid].owner,self.rival.gid)
        knockout=captured[0]['team'][0]['id']
        self.assertEqual(next(f.injured for f in self.rival.fighters if f.fid==knockout),2)
        game.world.money.reconcile()

    def test_short_custom_squads_are_rejected_without_advancing(self):
        game=self.game
        members=[f.fid for f in game.guild.fighters if not f.injured][:7]
        with self.assertRaisesRegex(ValueError,'8명'):
            game.submit_month(1,1,dict(group_mode=True,defense=dict(members=members)))
        with self.assertRaisesRegex(ValueError,'8명'):
            game.submit_month(1,1,dict(group_mode=True,
                attack=dict(zone=self.site.zid,setup=[dict(id=fid) for fid in members])))
        self.assertEqual((game.phase,game.week),('ready',1))

    def test_monthly_defense_replaces_injury_with_second_squad_first(self):
        game=self.game
        crew=game.guild.fighters[:8]
        reserve=game.guild.fighters[8]
        for fighter in game.guild.fighters:
            fighter.injured=0
        crew[0].injured=2
        reserve.development.squad='second'
        run=dict(defense=[f.fid for f in crew],group_mode=True,orders=None,training=[],rest=[])
        defense=game.repeat_monthly_assignment(run)['defense']
        self.assertEqual(defense['members'],[f.fid for f in crew[1:]]+[reserve.fid])
        for fighter in game.guild.fighters[8:]:
            fighter.injured=2
        self.assertIsNone(game.repeat_monthly_assignment(run)['defense'])

    def test_unstaffed_defense_opens_manual_choice_during_the_month(self):
        g=self.game
        for fighter in g.guild.fighters[5:]:
            fighter.injured=2
        with self.scheduled(self.rival.gid,self.post.zid,2):
            g.submit_month(1,1,dict(group_mode=True,rest=[g.guild.fighters[0].fid]))
        self.assertEqual((g.week,g.group_play['kind']),(2,'defense'))
        self.assertEqual(g.world.zones[self.post.zid].owner,g.guild.gid)
        self.assertTrue(all(f['id']<0 for f in g.group_play['team']))
        self.assertFalse(g.group_play['observer'])
        self.assertNotIn('month_auto',g.overview())
        match=g.group_play
        with self.scheduled(self.rival.gid,self.post.zid,2):
            g.finish_group(match['match'],self.result(match,0))
            g.continue_month()
        self.assertEqual(g.phase,'report')
        self.assertEqual(g.week_report['tactical_defenses'][0]['week'],2)
        self.assertEqual(g.world.zones[self.post.zid].owner,g.guild.gid)
