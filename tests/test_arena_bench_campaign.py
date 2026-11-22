import unittest

from campaign import Campaign
from moonpa_savegame import create_save, load_save


def replay_units(ids):
    return [dict(id=fid,side=0,hp=100,max_hp=100,
                 healing=0,hit_taken=0,actions=3)
            for fid in ids]


class ArenaBenchCampaignTest(unittest.TestCase):
    def new_attack(self):
        game=Campaign(23,interactive=True)
        game.phase='ready'
        zone=next(z for z in game.overview()['zones']
                  if z['selectable'] and z['owner'] is None)
        team=[dict(id=f.fid) for f in game.guild.fighters if not f.injured][:8]
        game.submit_week(1,1,dict(group_mode=True,
            attack=dict(zone=zone['id'],setup=team)))
        return game,zone

    def test_reserves_really_exist_and_survive_midbattle_save(self):
        game,_=self.new_attack()
        match=game.group_play
        self.assertEqual(len(match['team']),8)
        self.assertGreaterEqual(len(match['bench']),1)
        team_ids={f['id'] for f in match['team']}
        bench_ids={f['id'] for f in match['bench']}
        self.assertFalse(team_ids&bench_ids)
        self.assertTrue(bench_ids.issubset({f.fid for f in game.guild.fighters}))
        self.assertTrue(all(isinstance(f['ca'],float) and
                            isinstance(f['pa'],float) and len(f['attrs'])==8
                            for f in match['bench']))
        loaded=load_save(create_save(game))
        self.assertEqual(loaded.group_play['bench'],match['bench'])

    def test_substituted_fighter_participates_in_actual_conquest(self):
        game,zone=self.new_attack()
        group=game.group_play
        original=group['team'][0]['id']
        spare=group['bench'][0]['id']
        ids=[spare]+[f['id'] for f in group['team'][1:]]
        game.finish_group(group['match'],dict(winner=0,
                          units=replay_units(ids),events=[]))
        self.assertEqual(game.world.zones[zone['id']].owner,game.guild.gid)
        actual={p['id'] for p in game.week_report['battle']['participants'] if p['side']==0}
        self.assertIn(spare,actual)
        self.assertNotIn(original,actual)
        self.assertEqual(game.phase,'report')
        game.world.money.reconcile()

    def test_unlisted_or_duplicate_fighters_cannot_submit(self):
        game,_=self.new_attack()
        group=game.group_play
        ids=[f['id'] for f in group['team']]
        for candidate in ([999999]+ids[1:],[ids[0],ids[0]]+ids[2:]):
            before=create_save(game)
            with self.assertRaisesRegex(ValueError,'출전 명단'):
                game.finish_group(group['match'],dict(winner=0,
                                 units=replay_units(candidate),events=[]))
            self.assertEqual(create_save(game),before)


if __name__=='__main__':
    unittest.main()
