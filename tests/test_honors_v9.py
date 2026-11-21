"""v9: one-season formal rank honors, permanent catalog, fighter persistence."""
import copy
import json
import unittest
from types import SimpleNamespace
from campaign import Campaign
import moonpa_honors as honor
from moonpa_savegame import create_save, load_save
import pages_bridge


class HonorChronicleTests(unittest.TestCase):
    def make_ready(self):
        g=Campaign(23,interactive=True)
        g.phase='ready'
        return g

    def test_all_16_14_60_titles_are_unique_and_organized(self):
        self.assertEqual(len(honor.RANK_NAMES),16)
        self.assertEqual(len(honor.SPECIAL),14)
        self.assertEqual(len(honor.EPITHETS),60)
        self.assertEqual(len({x[0] for x in honor.SPECIAL}),14)
        self.assertEqual(len({x[0] for x in honor.EPITHETS}),60)
        self.assertEqual(len({x[1] for x in honor.EPITHETS}),60)
        self.assertEqual(set(x[3] for x in honor.EPITHETS),
                         {'공격·돌파','방어·생존','사수·주술·치유','비무·대회','성장·영입·충성','영지·승격·특수'})
        self.assertEqual(honor.RANK_NAMES[(1,1)],'천하제일')
        self.assertEqual(honor.RANK_NAMES[(4,1)],'신진맹주')

    def test_no_honors_awarded_in_prehistory_before_player_exists(self):
        g=self.make_ready()
        self.assertEqual(g.world.honor_history,[])
        self.assertIsNone(honor.current_rank(g.world,g.guild.gid,1))
        self.assertEqual(honor.chronicle(g.world,g.guild.gid,1)['entries'],[])

    def test_rank_honor_valid_exactly_one_following_season_and_past_remains(self):
        game=self.make_ready()
        g=game.guild
        self.assertEqual(g.tier,4)
        g.score=100000  # conclusively 4th-division champion
        game.week=51
        game.submit_week(1,51,{})
        self.assertEqual((game.season,game.week),(2,1))
        first=game.world.honor_history[-1]
        self.assertEqual(first['season'],1)
        self.assertEqual(first['guilds'][g.gid]['tier'],4)
        self.assertEqual(first['guilds'][g.gid]['rank'],1)
        self.assertEqual(first['guilds'][g.gid]['next_tier'],3)
        self.assertEqual(honor.current_rank(game.world,g.gid,2)['name'],'신진맹주')
        self.assertIn('신진맹주 · ',honor.display_name(game.world,g.gid,2))
        self.assertIsNone(honor.current_rank(game.world,g.gid,3))
        self.assertEqual(game.overview()['last_season_review']['rank_title'],'신진맹주')
        self.assertEqual(game.week_report['season'],1)
        # Old award ends when season 2 finishes; rank 5-8 cannot renew it.
        game.phase='ready'
        game.week=51
        g.score=-100000
        game.submit_week(2,51,{})
        self.assertEqual(game.season,3)
        self.assertIsNone(honor.current_rank(game.world,g.gid,3))
        history=honor.chronicle(game.world,g.gid,3)
        self.assertEqual(len(history['entries']),2)
        self.assertEqual(history['entries'][0]['rank_title'],'신진맹주')
        self.assertIsNone(history['entries'][1]['rank_title'])
        self.assertEqual(honor.codex(game.world,g.gid,3)['totals']['rank'],1)
        self.assertEqual(len(history['entries'][0]['standings']),8)
        game.world.money.reconcile()

    def test_rank_honor_renews_only_if_new_season_qualifies(self):
        game=self.make_ready()
        g=game.guild
        g.score=100000
        game.week=51;game.submit_week(1,51,{})
        self.assertEqual(g.tier,3)
        game.phase='ready'
        g.score=100000
        game.week=51;game.submit_week(2,51,{})
        self.assertEqual(g.tier,2)
        self.assertEqual(honor.current_rank(game.world,g.gid,3)['name'],'소호')
        self.assertNotIn('신진맹주',honor.display_name(game.world,g.gid,3))
        ranks=honor.codex(game.world,g.gid,3)['rank']
        self.assertTrue(next(x for x in ranks if x['name']=='신진맹주')['unlocked'])
        self.assertTrue(next(x for x in ranks if x['name']=='소호')['current'])

    def test_all_32_rival_season_snapshots_and_public_history(self):
        game=self.make_ready()
        game.week=51
        game.submit_week(1,51,{})
        snapshot=game.world.honor_history[-1]
        self.assertEqual(len(snapshot['guilds']),32)
        self.assertEqual(sorted(snapshot['tiers']),[1,2,3,4])
        for tier in range(1,5):
            rows=snapshot['tiers'][tier]
            self.assertEqual(len(rows),8)
            self.assertEqual([r['rank'] for r in rows],list(range(1,9)))
            self.assertEqual(len({r['id'] for r in rows}),8)
            for r in rows:
                self.assertEqual(r['tier'],tier)
        rival=next(g for g in game.world.guilds.values() if g.gid!=game.guild.gid)
        their=honor.chronicle(game.world,rival.gid,game.season)
        self.assertEqual(len(their['entries']),1)
        self.assertEqual(their['entries'][0]['name'],rival.name)

    def test_special_honors_permanent_after_rank_expiration(self):
        game=self.make_ready()
        w,g=game.world,game.guild
        record=w.honor_titles.setdefault(g.gid,dict(rank=None,special={}))
        record['special']['rich_sect']=dict(count=2,first_season=1,last_season=3,seasons=[1,3])
        self.assertEqual(honor.current_label(w,g.gid,2),'부국강문')
        self.assertEqual(honor.current_label(w,g.gid,50),'부국강문')
        entry=honor.codex(w,g.gid,2)['special']
        item=next(x for x in entry if x['id']=='rich_sect')
        self.assertTrue(item['unlocked'])
        self.assertEqual(item['count'],2)
        record['rank']=dict(name='대호',valid_season=3,award_season=2)
        self.assertEqual(honor.current_label(w,g.gid,3),'대호')
        self.assertEqual(honor.current_label(w,g.gid,4),'부국강문')

    def test_fighter_epithet_sticks_across_transfer_and_repeated_seasons(self):
        game=self.make_ready()
        w=game.world
        player=game.guild
        fighter=player.fighters[0]
        fid=fighter.fid
        self.assertTrue(honor.award_fighter(w,fid,'iron_wall',1,player.gid))
        self.assertFalse(honor.award_fighter(w,fid,'iron_wall',1,player.gid))
        self.assertTrue(honor.award_fighter(w,fid,'iron_wall',2,player.gid))
        self.assertEqual(w.honor_fighters[fid]['iron_wall']['count'],2)
        rival=next(g for g in w.guilds.values() if g.gid!=player.gid)
        player.fighters.remove(fighter)
        rival.fighters.append(fighter)
        honor.observe_growth(w,2)
        self.assertIn('iron_wall',w.honor_sect_collections[rival.gid])
        self.assertEqual(w.honor_fighters[fid]['iron_wall']['count'],2)
        self.assertIn('iron_wall', [x['id'] for x in honor.codex(w,rival.gid,2)['nicknames'] if x['status']=='획득'])

    def test_no_tournament_winner_without_an_actual_tournament(self):
        game=self.make_ready()
        w=game.world
        c=honor.codex(w,game.guild.gid,1)
        for key in ('sword_emperor','fist_king','martial_supreme','promotion_ruler'):
            item=next(x for x in c['nicknames'] if x['id']==key)
            self.assertFalse(item['available'])
            self.assertEqual(item['status'],'미획득')
        for guild in w.guilds.values():
            self.assertNotIn('promotion_king',w.honor_titles.get(guild.gid,{}).get('special',{}))

    def test_actual_damage_kill_heal_events_award_once_and_reconcile(self):
        game=self.make_ready()
        w=game.world
        f=game.guild.fighters[0]
        others=[x for x in game.guild.fighters if x.fid!=f.fid][:2]
        units={f.fid:SimpleNamespace(side=0,hit_taken=3050,healing=5100,hp=200)}
        units.update({x.fid:SimpleNamespace(side=0,hit_taken=0,healing=0,hp=200) for x in others})
        target=next(g for g in w.guilds.values() if g.gid!=game.guild.gid).fighters[0]
        units[target.fid]=SimpleNamespace(side=1,hit_taken=0,healing=0,hp=0)
        events=[dict(kind='knockout',actor=f.fid) for _ in range(4)]
        events+= [dict(kind='heal',actor=f.fid,amount=20) for _ in range(100)]
        before=(game.guild.cash,w.money.transactions,w.rng.getstate())
        honor.record_battle(w,SimpleNamespace(units=units,events=events,winner=0),1,8,4,True)
        earned=w.honor_fighters[f.fid]
        for key in ('breaker','iron_wall','divine_healer','life_lamp'):
            self.assertIn(key,earned)
        self.assertEqual((game.guild.cash,w.money.transactions,w.rng.getstate()),before)
        honor.record_battle(w,SimpleNamespace(units=units,events=events,winner=0),1,9,4,True)
        self.assertEqual(w.honor_fighters[f.fid]['breaker']['count'],1)
        w.money.reconcile()

    def test_growth_unlocks_only_proven_and_saves(self):
        game=self.make_ready()
        w=game.world
        f=game.guild.fighters[0]
        w.honor_tracking[f.fid]={'first_ca':75}
        f.age=24;f.ca=166
        honor.observe_growth(w,1)
        self.assertIn('prodigy',w.honor_fighters[f.fid])
        self.assertIn('legendary_student',w.honor_fighters[f.fid])
        gold=create_save(game)
        loaded=load_save(gold)
        self.assertEqual(loaded.world.honor_fighters[f.fid],w.honor_fighters[f.fid])
        self.assertEqual(loaded.world.honor_sect_collections,w.honor_sect_collections)
        loaded.world.money.reconcile()

    def test_legacy_v8_save_missing_honor_fields_still_loads(self):
        game=self.make_ready()
        props=['honor_titles','honor_history','honor_fighters','honor_tracking',
               'honor_baselines','honor_known_names','honor_sect_collections']
        for key in props:delattr(game.world,key)
        old=create_save(game)
        new=load_save(old)
        self.assertEqual(new.overview()['guild_name'],game.guild.name)
        self.assertEqual(honor.codex(new.world,new.guild.gid,new.season)['totals']['rank'],0)
        new.week=51
        new.submit_week(1,51,{})
        self.assertEqual(len(new.world.honor_history),1)
        new.world.money.reconcile()

    def test_bridge_codex_and_history_do_not_change_economy(self):
        game=self.make_ready()
        before=(game.guild.cash,game.world.money.transactions,game.world.rng.getstate())
        original=pages_bridge.game
        try:
            pages_bridge.game=game
            codex=json.loads(pages_bridge.handle('honors_codex','{}'))
            history=json.loads(pages_bridge.handle('honors_history','{}'))
            self.assertEqual(len(codex['rank']),16)
            self.assertEqual(len(codex['special']),14)
            self.assertEqual(len(codex['nicknames']),60)
            self.assertEqual(history['entries'],[])
            with self.assertRaises(ValueError):
                pages_bridge.handle('honors_history',json.dumps({'guild_id':9999999}))
        finally:pages_bridge.game=original
        self.assertEqual((game.guild.cash,game.world.money.transactions,game.world.rng.getstate()),before)


if __name__=='__main__':
    unittest.main()
