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
