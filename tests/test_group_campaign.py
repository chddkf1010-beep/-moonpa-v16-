import unittest

from campaign import Campaign
import moonpa_economy_v15_1 as economy
from moonpa_savegame import create_save, load_save


class GroupCampaignTest(unittest.TestCase):
    def setUp(self):
        self.game = Campaign(23, interactive=True)
        self.game.phase = 'ready'

    def test_territory_result_survives_reload_and_settles_once(self):
        game = self.game
        zone = next(z for z in game.overview()['zones'] if z['selectable'] and z['owner'] is None)
        team = [{'id': f.fid} for f in game.guild.fighters if not f.injured][:8]
        game.submit_week(1, 1, {'group_mode': True, 'attack': {'zone': zone['id'], 'setup': team}})
        game = load_save(create_save(game))
        match = game.group_play
        self.assertEqual((match['mode'], len(match['team']), len(match['enemyRoster'])), (8, 8, 8))
        units = [dict(id=u['id'], side=0, hp=100, max_hp=100, healing=0, hit_taken=0, actions=3)
                 for u in match['team']]
        result = dict(winner=0, units=units, events=[])
        game.finish_group(match['match'], result)
        self.assertEqual(game.world.zones[zone['id']].owner, game.guild.gid)
        self.assertEqual(game.phase, 'report')
        self.assertEqual(game.week, 2)
        self.assertEqual(len(game.week_report['battle']['participants']), 8)
        with self.assertRaises(ValueError):
            game.finish_group(match['match'], result)
        game.world.money.reconcile()

    def test_invalid_attacker_payload_does_not_change_week(self):
        game = load_save(create_save(self.game))
        zone = next(z['id'] for z in game.overview()['zones'] if z['selectable'])
        team = [f for f in game.overview()['roster'] if not f['injured']][:8]
        invalid = [{'id': f} for f in team]
        before = create_save(game)
        with self.assertRaisesRegex(ValueError, '점령전 문파원 편성'):
            game.submit_week(1, 1, {'group_mode': True, 'attack': {'zone': zone, 'setup': invalid}})
        self.assertEqual(create_save(game), before)
        game.submit_week(1, 1, {'group_mode': True, 'attack': {'zone': zone,
                         'setup': [{'id': f['id']} for f in team]}})
        self.assertEqual((game.phase, game.group_play['kind']), ('group', 'territory'))
        self.assertEqual({member['id'] for member in game.group_play['team']},
                         {f['id'] for f in team})

    def test_saved_tactical_order_survives_terrain_capacity_adjustment(self):
        game = self.game
        zone = next(z for z in game.world.zones if z.tier == game.guild.tier and z.owner is None)
        fighters = game.guild.fighters[:8]
        ids = [f.fid for f in reversed(fighters)]
        formation = [dict(id=fid, row='front' if i<2 else 'back') for i,fid in enumerate(ids)]
        game.world.prebattle_plans = {
            'attack': dict(season=1, week=1, zone_id=zone.zid,
                           data=dict(formation=formation, captain=ids[0], deputy=ids[1]))}
        game.begin_group('territory', fighters, None, zone)
        team = game.group_play['team']
        for row, first in [('front',ids[:2]),('back',ids[2:4])]:
            by_slot = sorted((f for f in team if f['line']==row), key=lambda f:f['slot'])
            self.assertEqual([f['id'] for f in by_slot[:2]], first)

    def test_season_playoff_sets_division_and_opens_next_draft(self):
        game = self.game
        game.week = 51
        original_one_week = economy.one_week

        def decide_standings(world, season, week):
            original_one_week(world, season, week)
            fourth = [guild for guild in world.guilds.values() if guild.tier == 4 and guild is not game.guild]
            fourth[0].score = 20000
            game.guild.score = 10000

        from unittest.mock import patch
        with patch.object(economy, 'one_week', side_effect=decide_standings):
            game.submit_week(1, 51, {'group_mode': True})
        game = load_save(create_save(game))
        match = game.group_play
        self.assertEqual(match['mode'], 10)
        self.assertEqual(match['kind'], 'playoff')
        self.assertEqual(len([u for u in match['team'] if u['line'] == 'front']), 5)
        self.assertEqual(len([u for u in match['team'] if u['line'] == 'back']), 5)
        game.finish_group(match['match'], {'winner': 0})
        self.assertEqual((game.guild.tier, game.season, game.week), (3, 2, 1))
        report = game.week_report
        self.assertEqual(sum(entry['amount'] for entry in report['entries']), report['cash_change'])
        game.world.money.reconcile()
        game.advance_phase('report')
        self.assertEqual(game.phase, 'draft')


class TacticalDefenseTest(unittest.TestCase):
    def encounter(self, *, raid=True, counterattack=False):
        from unittest.mock import patch
        game = Campaign(23)
        game.interactive = True
        post = next(z for z in game.world.zones if z.tier == game.guild.tier and z.owner is None)
        goal = next(z for z in game.world.zones if z is not post and z.tier == post.tier
                    and z.owner != game.guild.gid)
        goal.owner, goal.protected_until = None, 0
        for zone in game.world.zones:
            if zone.owner==game.guild.gid:
                zone.owner = None
        post.owner = game.guild.gid
        rival = next(g for g in game.world.guilds.values() if g.tier == post.tier and g is not game.guild)
        normal_plan = economy.prep_plan

        def planned_attack(world, guild, week):
            plan = normal_plan(world, guild, week)
            plan['attack'] = []
            if raid and guild is rival:
                plan['attack'] = [f for f in economy.old.choose_active(guild,False) if not f.injured][:5]
                plan['attack_target'] = post.zid
            return plan

        available = [f.fid for f in game.guild.fighters if not f.injured]
        assignment = {'group_mode': True, 'defense': {'zone': post.zid, 'members': available[:8]}}
        if counterattack:
            assignment['attack'] = {'zone': goal.zid, 'setup': [{'id': fid} for fid in available[8:16]]}
        with patch.object(economy, 'prep_plan', side_effect=planned_attack):
            game.submit_week(1,1,assignment)
            if counterattack:
                self.assertEqual(game.group_play['kind'],'territory')
                game.finish_group(game.group_play['match'],self.result(game.group_play,0))
        return game, post.zid, rival.gid, goal.zid

    @staticmethod
    def result(match,winner):
        units = [dict(id=u['id'],side=side,hp=0 if u['id']==match['captain'] else 100,
                      max_hp=100,healing=0,hit_taken=0,actions=3)
                 for side,roster in enumerate((match['team'],match['enemyRoster'])) for u in roster
                 if u['id']>=0]
        return dict(winner=winner,units=units,events=[])

    def test_defense_loss_releases_zone_and_books_the_partial_week_once(self):
        game, post, attacker, _ = self.encounter()
        self.assertEqual((game.phase,game.week),('group',1))
        self.assertEqual(game.world.zones[post].owner,game.guild.gid)
        game = load_save(create_save(game))
        match = game.group_play
        self.assertEqual((match['kind'],match['scenario'],len(match['team']),len(match['enemyRoster'])),
                         ('defense','defense',8,8))
        result = self.result(match,1)
        game.finish_group(match['match'],result)
        self.assertEqual(game.world.zones[post].owner,attacker)
        report = game.week_report
        self.assertEqual(next(z['days'] for z in report['territories'] if z['zone']==post),4)
        self.assertGreater(report['tactical_defense']['gross_loss'],0)
        self.assertTrue(any(u['injured'] for u in report['tactical_defense']['participants'] if u['side']==0))
        self.assertEqual((game.phase,game.week),('report',2))
        with self.assertRaises(ValueError):
            game.finish_group(match['match'],result)
        game.world.money.reconcile()

    def test_attack_then_defense_draw_settle_together(self):
        game, post, _, goal = self.encounter(counterattack=True)
        self.assertEqual(game.group_play['kind'],'defense')
        self.assertIsNone(game.week_report)
        game = load_save(create_save(game))
        game.finish_group(game.group_play['match'],self.result(game.group_play,-1))
        self.assertEqual(game.world.zones[post].owner,game.guild.gid)
        self.assertEqual(game.world.zones[goal].owner,game.guild.gid)
        self.assertTrue(game.week_report['battle']['success'])
        self.assertTrue(game.week_report['tactical_defense']['held'])
        self.assertEqual(game.week_report['tactical_defense']['gross_loss'],0)

    def test_two_raids_reuse_entire_defense_team_and_settle_once(self):
        from unittest.mock import patch
        game = Campaign(23, interactive=True)
        game.phase='ready'
        world, guild = game.world, game.guild
        for zone in world.zones:
            if zone.owner==guild.gid:
                zone.owner=None
        posts = [z for z in world.zones if z.tier==guild.tier and z.owner is None][:2]
        for post in posts:
            post.owner,post.protected_until=guild.gid,0
        rivals = [g for g in world.guilds.values() if g.tier==guild.tier and g is not guild][:2]
        targets = {rival.gid:post.zid for rival,post in zip(rivals,posts)}
        normal = economy.prep_plan

        def plans(w,g,week):
            plan = normal(w,g,week)
            plan['attack'] = [f for f in g.fighters if not f.injured][:5] if g.gid in targets else []
            plan['attack_target'] = targets.get(g.gid)
            return plan

        ids = [f.fid for f in guild.fighters if not f.injured][:8]
        with patch.object(economy,'prep_plan',side_effect=plans):
            game.submit_week(1,1,{'group_mode':True,'defense':{'members':ids}})
        first = game.group_play
        self.assertEqual(first['defenseTotal'],2)
        cash = guild.cash
        game.finish_group(first['match'],self.result(first,1))
        self.assertIsNone(game.week_report)
        self.assertEqual(guild.cash,cash)
        self.assertEqual(game.week,1)
        self.assertTrue(all(f.injured==0 for f in guild.fighters if f.fid in ids))
        game = load_save(create_save(game))
        second = game.group_play
        self.assertEqual(second['defenseNumber'],2)
        self.assertNotEqual(first['zone'],second['zone'])
        self.assertNotEqual(first['match'],second['match'])
        self.assertEqual({f['id'] for f in second['team']},set(ids))
        with self.assertRaises(ValueError):
            game.finish_group(first['match'],self.result(first,1))
        game.finish_group(second['match'],self.result(second,0))
        report = game.week_report
        self.assertEqual([r['held'] for r in report['tactical_defenses']],[False,True])
        self.assertNotEqual(game.world.zones[first['zone']].owner,game.guild.gid)
        self.assertEqual(game.world.zones[second['zone']].owner,game.guild.gid)
        self.assertEqual([next(t['days'] for t in report['territories'] if t['zone']==z)
                          for z in (first['zone'],second['zone'])],[4,7])
        self.assertEqual((game.phase,game.week),('report',2))
        self.assertEqual(sum(entry['amount'] for entry in report['entries']),report['cash_change'])
        game.world.money.reconcile()

    def test_no_raid_goes_directly_to_report(self):
        game, post, _, _ = self.encounter(raid=False)
        self.assertIsNone(game.group_play)
        self.assertEqual(game.phase,'report')
        self.assertIsNone(game.week_report['tactical_defense'])
        self.assertEqual(game.week_report['briefing']['defense_plan']['zone'],post)
