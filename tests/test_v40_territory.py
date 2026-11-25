import unittest
from unittest.mock import patch
from campaign import Campaign
import moonpa_economy_v15_1 as economy
from moonpa_savegame import create_save, load_save
from test_conquest_qualifiers import ContestedConquestTests

class TerritoryTest(unittest.TestCase):
    def setUp(self):
        self.c=Campaign(23,interactive=True); self.c.phase='ready'
        self.w=self.c.world; self.g=self.c.guild
        self.home=next(z for z in self.w.zones if z.owner==self.g.gid)
        self.site=next(z for z in self.w.zones if z.owner is None and z.tier==self.g.tier)
        self.home.protected_until=self.site.protected_until=0
        self.rivals=[g for g in self.w.guilds.values() if g.tier==self.g.tier and g is not self.g][:3]
        for g in [self.g,*self.rivals]:
            for f in g.fighters:f.injured=0
    def scheduled(self,zid,rivals):
        original=economy.prep_plan
        ids={g.gid for g in rivals}
        def plan(w,g,week):
            p=original(w,g,week);p['attack']=[];p['attack_target']=None
            if g.gid in ids:
                reserved={f.fid for f in p['defend']}
                p['attack']=[f for f in g.fighters if not f.injured and f.fid not in reserved][:8]
                p['attack_target']=zid
            return p
        return patch.object(economy,'prep_plan',side_effect=plan)
    def finish(self,c,winner):
        group=c.group_play
        c.finish_group(group['match'],ContestedConquestTests.result(group,winner))
    def test_three_challengers_two_qualifiers_one_final_and_restore(self):
        c=self.c; crew=[f.fid for f in self.g.fighters[:8]]
        with self.scheduled(self.home.zid,self.rivals):
            c.submit_week(1,1,dict(group_mode=True,defense=dict(members=crew)))
        self.assertTrue(c.group_play['defenseQualifier']);self.assertTrue(c.group_play['observer'])
        first=c.group_play['match']; before=self.g.cash
        self.finish(c,1)
        self.assertNotEqual(c.group_play['match'],first)
        self.assertEqual(c.week,1);self.assertEqual(c.guild.cash,before)
        c=load_save(create_save(c))
        self.finish(c,0)
        self.assertEqual(c.group_play['kind'],'defense')
        final=c.group_play['sectNames'][1]
        self.finish(c,0)
        self.assertEqual(c.week,2)
        self.assertEqual(len(c.week_report['defense_qualifiers']),2)
        self.assertEqual(len(c.week_report['tactical_defenses']),1)
        self.assertEqual(c.week_report['tactical_defenses'][0]['attacker'],final)
        self.assertEqual(c.world.zones[self.home.zid].owner,c.guild.gid)
        self.assertEqual(c.world.zones[self.home.zid].protected_until,56)
        self.assertEqual(c.overview()['player_journal']['difference'],0)
    def at_cap(self):
        c=self.c
        extra=next(z for z in self.w.zones if z.owner is None and z.tier==self.g.tier and z is not self.site)
        extra.owner=self.g.gid
        self.assertEqual(sum(z.owner==self.g.gid for z in self.w.zones),economy.CAP[self.g.tier])
        with self.scheduled(self.site.zid,[]):
            c.submit_week(1,1,dict(group_mode=True,attack=dict(zone=self.site.zid,setup=[dict(id=f.fid) for f in self.g.fighters[:8]])))
        self.finish(c,0)
        self.assertIn('captureChoice',c.group_play)
        self.assertIsNone(self.site.owner);self.assertEqual(c.week,1)
        return extra
    def test_capture_replace_selected_not_automatic(self):
        extra=self.at_cap();c=load_save(create_save(self.c))
        match=c.group_play['match']; cash=c.guild.cash
        with self.assertRaises(ValueError):c.resolve_capture(match,'replace',self.site.zid)
        with self.assertRaises(ValueError):self.finish(c,0)
        self.assertEqual(c.guild.cash,cash)
        c.resolve_capture(match,'replace',self.home.zid)
        self.assertIsNone(c.world.zones[self.home.zid].owner)
        self.assertEqual(c.world.zones[extra.zid].owner,c.guild.gid)
        self.assertEqual(c.world.zones[self.site.zid].owner,c.guild.gid)
        self.assertEqual(c.world.zones[self.site.zid].protected_until,56)
        self.assertEqual(c.world.zones[self.home.zid].protected_until,56)
        self.assertEqual(c.week,2)
        with self.assertRaises(ValueError):c.resolve_capture(match,'replace',extra.zid)
        self.assertEqual(c.overview()['player_journal']['difference'],0)
    def test_capture_abandon_keeps_old_holdings(self):
        extra=self.at_cap();c=self.c
        c.resolve_capture(c.group_play['match'],'abandon')
        self.assertIsNone(self.site.owner)
        self.assertEqual(self.site.protected_until,56)
        self.assertEqual(self.home.owner,self.g.gid)
        self.assertEqual(extra.owner,self.g.gid)
        self.assertTrue(c.week_report['battle']['abandoned'])
        self.assertTrue(c.week_report['battle']['success'])
        self.assertEqual(c.week,2)
    def test_protection_two_following_weeks(self):
        self.site.protected_until=56
        for clock,allowed in [(53,False),(54,False),(55,False),(56,True)]:
            self.w.globalweek=clock
            self.assertEqual(economy.old.attack_allowed(self.w,self.g.gid,self.site),allowed)

if __name__=='__main__':unittest.main()
