"""Regression for real sect founding, league ranking and rival dossiers."""
import json
import unittest

from campaign import Campaign
from moonpa_savegame import create_save, load_save
import pages_bridge


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.g=Campaign(23, interactive=True)
        self.assertEqual(self.g.phase,'tutorial')

    def test_founding_keeps_world_roster_finances_and_enters_draft(self):
        g=self.g
        old_count=len(g.world.guilds)
        original_ids={f.fid for f in g.guild.fighters}
        baseline=g.guild.cash
        count_before=sum(len(x.fighters) for x in g.world.guilds.values())
        old_id=g.guild.gid
        g.found_sect('청룡검문','growth')
        self.assertEqual(g.guild.name,'청룡검문')
        self.assertEqual(g.guild.strategy,'growth')
        self.assertEqual(g.world.strategy,'growth')
        self.assertEqual(g.phase,'draft')
        self.assertEqual(g.world.player,old_id)
        self.assertEqual(len(g.world.guilds),old_count)
        self.assertEqual(len(g.guild.fighters),len(original_ids))
        self.assertEqual({f.fid for f in g.guild.fighters},original_ids)
        self.assertEqual(g.guild.cash,baseline)
        self.assertGreaterEqual(sum(len(x.fighters) for x in g.world.guilds.values()),count_before)
        self.assertEqual(g.overview()['strategy'],'growth')
        self.assertIn('청룡검문',g.world.names.used_sects)
        self.assertEqual(sum(x.name=='청룡검문' for x in g.world.guilds.values()),1)
        g.world.money.reconcile()

    def test_default_existing_name_can_be_kept(self):
        g=self.g
        current=g.guild.name
        g.found_sect(current,'balanced')
        self.assertEqual(g.guild.name,current)
        self.assertEqual(g.phase,'draft')

    def test_invalid_duplicate_and_unsafe_names_are_atomic(self):
        g=self.g
        initial=(g.phase,g.guild.name,g.guild.strategy,len(g.world.names.used_sects),
                 g.world.rng.getstate(),g.guild.cash)
        duplicate=next(x.name for x in g.world.guilds.values() if x.gid!=g.guild.gid)
        for name,strategy in [
            ('','balanced'), (' ', 'balanced'), ('ㅋ','balanced'),
            ('<script>', 'balanced'), ('abc'+'d'*13,'balanced'),
            (duplicate,'balanced'), ('청룡문','unknown'), ('청룡문',None),
            (0,'growth'), ('청룡문',True)]:
            with self.subTest(name=name,strategy=strategy):
                with self.assertRaises(ValueError): g.found_sect(name,strategy)
                self.assertEqual((g.phase,g.guild.name,g.guild.strategy,
                                  len(g.world.names.used_sects),
                                  g.world.rng.getstate(),g.guild.cash),initial)
        g.found_sect('청룡문','conquest')
        with self.assertRaises(ValueError): g.found_sect('백룡문','growth')
        self.assertEqual(g.guild.name,'청룡문')

    def test_all_four_leagues_have_eight_and_match_season_tiebreaks(self):
        g=self.g
        state=g.league_view()
        self.assertEqual(len(state['groups']),4)
        self.assertEqual(sum(len(x['members']) for x in state['groups']),32)
        self.assertEqual({group['tier'] for group in state['groups']},{1,2,3,4})
        for group in state['groups']:
            tier=group['tier'];rows=group['members']
            expected=sorted((x for x in g.world.guilds.values() if x.tier==tier),
                            key=lambda x:(x.score,x.strength(),-x.gid),reverse=True)
            self.assertEqual([r['id'] for r in rows],[x.gid for x in expected])
            self.assertEqual([r['rank'] for r in rows],list(range(1,9)))
            self.assertEqual(rows[0]['outlook'],
                             '1부 우승 경쟁' if tier==1 else '자동 승격권')
            self.assertEqual(rows[1]['outlook'],
                             '승격 플레이오프권' if tier>1 else '잔류권')
            self.assertEqual(rows[-1]['outlook'],
                             '잔류권' if tier==4 else '자동 강등권')
            self.assertEqual(rows[-2]['outlook'],
                             '잔류권' if tier==4 else '강등 플레이오프권')
        ours=next(r for x in state['groups'] for r in x['members'] if r['player'])
        self.assertEqual(ours['name'],g.guild.name)
        self.assertEqual(ours['rank'],g.league_rank())
        self.assertEqual(ours['tier'],g.guild.tier)

    def test_accurate_profile_without_hidden_pa_and_with_actionable_territory(self):
        g=self.g
        opponent=next(x for x in g.world.guilds.values() if x.tier==4 and
                      x.gid!=g.guild.gid and any(z.owner==x.gid for z in g.world.zones))
        profile=g.sect_profile(opponent.gid)
        row=next(r for group in g.league_view()['groups']
                 for r in group['members'] if r['id']==opponent.gid)
        self.assertEqual(profile['rank'],row['rank'])
        self.assertEqual(profile['strength'],row['strength'])
        self.assertEqual(profile['name'],opponent.name)
        self.assertFalse(profile['player'])
        self.assertIsNone(profile['cash'])
        self.assertIn(profile['treasury'],('3주 미만','3~8주 미만','8주 이상'))
        self.assertEqual(profile['zone_count'],len(profile['zones']))
        self.assertEqual(profile['roster_count'],len(profile['members']))
        self.assertEqual([r['id'] for r in profile['members']],
                         [f.fid for f in sorted(opponent.fighters,key=lambda f:(f.ca,f.lv,-f.fid),reverse=True)])
        self.assertTrue(all('pa' not in x for x in profile['members']))
        self.assertTrue(all('estimate' not in x for x in profile['members']))
        self.assertEqual(profile['market_open'],not g.market_closed())
        for z in profile['zones']:
            real=g.world.zones[z['id']]
            self.assertEqual(z['selectable'],real.tier==g.guild.tier and
                             real.protected_until<=g.clock)
        for bad in (True, '4', -1, 999999, None):
            with self.subTest(bad=bad),self.assertRaises(ValueError):g.sect_profile(bad)

    def test_save_restore_founding_strategy_and_league_during_draft(self):
        g=self.g
        g.found_sect('비연검관','transfer')
        loaded=load_save(create_save(g))
        self.assertEqual(loaded.guild.name,'비연검관')
        self.assertEqual(loaded.guild.strategy,'transfer')
        self.assertEqual(loaded.world.strategy,'transfer')
        self.assertEqual(loaded.phase,'draft')
        self.assertEqual(loaded.league_view(),g.league_view())
        self.assertEqual(loaded.sect_profile(g.guild.gid),g.sect_profile(g.guild.gid))
        loaded.world.money.reconcile()

    def test_all_divisions_remain_8_after_season_rollover(self):
        g=Campaign(23,interactive=False)
        g.week=51
        g.submit_week(1,51,{})
        self.assertEqual((g.season,g.week),(2,1))
        for group in g.league_view()['groups']:
            self.assertEqual(len(group['members']),8)
        g.world.money.reconcile()

    def test_bridge_founding_read_only_profiles_and_restore(self):
        original=pages_bridge.game
        try:
            pages_bridge.game=Campaign(23,interactive=True)
            start=json.loads(pages_bridge.handle('state','{}'))
            self.assertEqual(start['phase'],'tutorial')
            draft=json.loads(pages_bridge.handle('found_sect',json.dumps(
                {'name':'도원검문','strategy':'conquest'})))
            self.assertEqual(draft['guild_name'],'도원검문')
            self.assertEqual(draft['phase'],'draft')
            self.assertEqual(len(draft['league']['groups']),4)
            rival=next(x['id'] for group in draft['league']['groups']
                       for x in group['members'] if not x['player'])
            detail=json.loads(pages_bridge.handle('sect_profile',json.dumps({'id':rival})))
            self.assertEqual(detail['id'],rival)
            self.assertEqual(json.loads(pages_bridge.handle('state','{}')),draft)
            saved=json.loads(pages_bridge.handle('export_save','{}'))
            pages_bridge.handle('new_game','{}')
            restored=json.loads(pages_bridge.handle('import_save',
                                      json.dumps({'save':saved})))
            self.assertEqual(restored,draft)
        finally:
            pages_bridge.game=original


if __name__=='__main__':
    unittest.main()
