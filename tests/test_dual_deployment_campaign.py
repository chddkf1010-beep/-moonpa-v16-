import unittest

from campaign import Campaign
from moonpa_savegame import create_save,load_save


class DualDeploymentCampaignTests(unittest.TestCase):
    def game_with_conquest(self):
        game=Campaign(23,interactive=True)
        game.phase='ready'
        target=next(z for z in game.overview()['zones']
                    if z['selectable'] and z['owner'] is None)
        ids=[f.fid for f in game.guild.fighters if not f.injured][:8]
        game.submit_month(1,1,dict(group_mode=True,
             attack=dict(zone=target['id'],setup=[dict(id=fid) for fid in ids])))
        self.assertEqual(game.phase,'group')
        return game

    @staticmethod
    def formation(group,replace=None):
        return [dict(id=replace if i==0 and replace is not None else member['id'],
                     line=member['line'],slot=member['slot'])
                for i,member in enumerate(group['team'])]

    def test_move_original_attacker_down_to_real_monthly_defense(self):
        game=self.game_with_conquest()
        match=game.group_play
        self.assertTrue(match['defenseEnabled'])
        self.assertEqual(match['defenseTeam'],[])
        original=match['team'][0]['id']
        backup=match['bench'][0]['id']
        captain=backup if match['captain']==original else match['captain']
        updated=game.group_assign(match['match'],self.formation(match,backup),
                                  [original],captain,match['deputy'])
        self.assertEqual(updated['group_play']['team'][0]['id'],backup)
        self.assertEqual(updated['group_play']['defenseTeam'][0]['id'],original)
        self.assertEqual([f.fid for f in game.pending_week['defend']],[original])
        self.assertEqual(game.month_run['defense'],[original])
        self.assertNotIn(original,[f['id'] for f in game.group_play['bench']])
        loaded=load_save(create_save(game))
        self.assertEqual(loaded.group_play['team'][0]['id'],backup)
        self.assertEqual(loaded.group_play['defenseTeam'][0]['id'],original)
        self.assertEqual(loaded.month_run['defense'],[original])
        self.assertEqual(loaded.phase,'group')

    def test_full_defense_can_be_reassigned_without_duplicate_members(self):
        game=self.game_with_conquest()
        match=game.group_play
        initial=match['team'][0]['id']
        spare=match['bench'][0]['id']
        formation=self.formation(match,spare)
        game.group_assign(match['match'],formation,[initial],spare,match['deputy'])
        again=game.group_play
        new_def=again['defenseTeam'][0]['id']
        original=again['bench'][0]['id']
        formation=self.formation(again,original)
        captain=original if again['captain']==spare else again['captain']
        game.group_assign(again['match'],formation,[new_def],captain,again['deputy'])
        self.assertEqual(game.group_play['team'][0]['id'],original)
        self.assertNotIn(original,[f['id'] for f in game.group_play['defenseTeam']])

    def test_invalid_changes_do_not_mutate_current_season_or_save(self):
        game=self.game_with_conquest()
        match=game.group_play
        team=self.formation(match)
        before=create_save(game)
        for broken,defenders,captain,deputy in [
            (team[:-1],[match['team'][0]['id']],match['captain'],match['deputy']),
            (team,[match['team'][0]['id']],match['captain'],match['deputy']),
            ([dict(team[0],id=999999),*team[1:]],[],match['captain'],match['deputy']),
            (team,[],match['captain'],match['captain']),
        ]:
            with self.assertRaises(ValueError):
                game.group_assign(match['match'],broken,defenders,captain,deputy)
            self.assertEqual(create_save(game),before)
        with self.assertRaises(ValueError):
            game.group_assign('wrong',team,[],match['captain'],match['deputy'])
        self.assertEqual(create_save(game),before)

    def test_group_formation_rejects_other_phases(self):
        game=self.game_with_conquest()
        match=game.group_play
        game.phase='report'
        with self.assertRaises(ValueError):
            game.group_assign(match['match'],self.formation(match),[],
                              match['captain'],match['deputy'])


if __name__=='__main__':
    unittest.main()
