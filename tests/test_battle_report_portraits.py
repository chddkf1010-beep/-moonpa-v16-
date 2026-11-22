"""Ensure both sides of a playable group match retain fighter identity artwork."""
import unittest

from campaign import Campaign
from moonpa_portraits import portrait_asset
from moonpa_savegame import create_save, load_save


class BattleReportPortraits(unittest.TestCase):
    def test_group_assigned_portraits_survive_save_and_stay_presentation_only(self):
        game=Campaign(23,interactive=True)
        game.phase='ready'
        target=next(z for z in game.overview()['zones'] if z['selectable'] and z['owner'] is None)
        team=[{'id':f.fid} for f in game.guild.fighters if not f.injured][:8]
        game.submit_week(game.season,game.week,{'group_mode':True,
                          'attack':{'zone':target['id'],'setup':team}})
        match=game.group_play
        self.assertEqual(match['mode'],8)
        original={f.fid:portrait_asset(f) for f in game.guild.fighters}
        for unit in match['team']:
            self.assertEqual(unit['portrait'],original[unit['id']])
        for unit in match['enemyRoster']:
            if unit['id'] < 0:
                self.assertNotIn('portrait',unit)
        restored=load_save(create_save(game))
        self.assertEqual(restored.group_play['team'],match['team'])
        self.assertEqual(restored.group_play['enemyRoster'],match['enemyRoster'])
        self.assertEqual(restored.guild.cash,game.guild.cash)


if __name__=='__main__':
    unittest.main()
