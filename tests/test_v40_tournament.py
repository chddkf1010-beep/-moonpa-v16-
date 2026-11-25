import unittest,json
from unittest.mock import patch
from campaign import Campaign,set_arena_resolver
import moonpa_tournament as cup
import moonpa_economy_v15_1 as economy
from moonpa_savegame import create_save,load_save
from test_conquest_qualifiers import ContestedConquestTests as FixtureHelper

class TournamentTest(unittest.TestCase):
    def setUp(self):
        self.c=Campaign(23,interactive=True);self.c.phase='ready';self.c.week=49
        for g in self.c.world.guilds.values():
            for f in g.fighters:f.injured=0
        self.calls=[]
        def resolve(raw):
            cfg=json.loads(raw);self.calls.append(cfg['kind'])
            return json.dumps(FixtureHelper.result(cfg,0))
        set_arena_resolver(resolve)
        self.addCleanup(set_arena_resolver,None)
    def advance(self,c,winner=0):
        c.submit_week(c.season,c.week,dict(group_mode=True))
        if c.phase=='group' and c.group_play['kind']=='tournament':
            cfg=c.group_play
            self.assertEqual(cfg['mode'],8)
            c=load_save(create_save(c))
            c.finish_group(cfg['match'],FixtureHelper.result(cfg,winner))
        return c
    def test_full_bracket_and_league_final(self):
        c=self.c
        owners=[z.owner for z in c.world.zones]
        for week,count in ((49,16),(50,24),(51,28)):
            self.assertEqual(c.week,week)
            c=self.advance(c)
            t=c.world.season_tournament
            self.assertEqual(len(t['matches']),count)
            self.assertEqual(t['points'][c.guild.gid],(week-48)*100)
            self.assertTrue(cup.valid(t,c.world))
            if week<51:
                self.assertEqual([z.owner for z in c.world.zones],owners)
                self.assertEqual(c.phase,'report')
                c.advance_phase('report')
        t=c.world.season_tournament
        self.assertEqual(self.calls.count('tournament'),25)
        for tier in range(1,5):
            self.assertEqual(sorted(t['points'][i] for i in t['seeds'][tier]),[0,0,0,0,100,100,200,300])
        self.assertEqual(len(t['final']),32)
        self.assertTrue(all(0<=r['total']<=1000 and r['total']==round(r['regular']+r['cup'],2) for r in t['final'].values()))
        self.assertEqual(c.overview()['player_journal']['difference'],0)
        self.assertTrue(cup.valid(load_save(create_save(c)).world.season_tournament,c.world))
    def test_elimination_and_old_late_save(self):
        c=self.advance(self.c,1)
        self.assertEqual(c.world.season_tournament['points'][c.guild.gid],0)
        c.advance_phase('report')
        c=self.advance(c)
        self.assertEqual(c.phase,'report')
        self.assertEqual(len(c.world.season_tournament['matches']),24)
        old=Campaign(23,interactive=True);old.phase='ready';old.week=50
        self.assertFalse(cup.window(old))
        self.assertFalse(cup.window(load_save(create_save(old))))
    def test_actual_arena_month_and_rollover(self):
        import subprocess
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        script="""import fs from 'node:fs';import {Arena} from './group-engine.mjs';
        const c=JSON.parse(fs.readFileSync(0,'utf8'));
        console.log(JSON.stringify(Arena.settle(c,{lineup:c.team,captain:c.captain,deputy:c.deputy,arts:c.chosenArts})));"""
        calls=[]
        def resolve(raw):
            cfg=json.loads(raw)
            calls.append(cfg['kind'])
            return subprocess.run(['node','--input-type=module','-e',script],input=raw,text=True,
                cwd=root,capture_output=True,check=True,timeout=20).stdout
        set_arena_resolver(resolve)
        c=self.c;c.week=48
        c.submit_month(1,48,dict(group_mode=True))
        for _ in range(15):
            if c.phase!='group':break
            cfg=c.group_play
            c=load_save(create_save(c))
            c.finish_group(cfg['match'],json.loads(resolve(json.dumps(cfg,ensure_ascii=False))))
            c.continue_month()
        self.assertEqual(c.phase,'report')
        self.assertIsNone(c.month_run)
        t=c.world.season_tournament
        self.assertEqual(len(t['matches']),28)
        self.assertEqual(len(t['final']),32)
        self.assertTrue(cup.valid(t,c.world))
        self.assertTrue(all(r['method']=='arena' for r in t['matches']))
        self.assertEqual(calls.count('tournament'),28)
        self.assertEqual(len(c.week_report['tournament_matches']),28)
        self.assertEqual(c.week_report['tournament_final'],t['final'])
        self.assertEqual(c.overview()['player_journal']['difference'],0)
        if c.season==1:
            review=c.season_contracts()
            self.assertIsNotNone(review)
            for f in list(c.guild.fighters):
                if f.contract_end<=1:
                    c.decide_contract(1,c.week,f.fid,f.contract_end,action='release')
            c.advance_phase('report')
        self.assertEqual(c.season,2)
        self.assertEqual(c.week,1)
        self.assertEqual([sum(g.tier==i for g in c.world.guilds.values()) for i in range(1,5)],[8]*4)
        self.assertEqual(c.overview()['player_journal']['difference'],0)

    def test_attack_blocked_before_mutation(self):
        c=self.c;site=next(z for z in c.world.zones if z.tier==c.guild.tier and z.owner!=c.guild.gid)
        before=c.guild.cash
        with self.assertRaises(ValueError):
            c.submit_week(1,49,dict(group_mode=True,attack=dict(zone=site.zid,setup=[dict(id=f.fid) for f in c.guild.fighters[:8]])))
        self.assertEqual((c.week,c.guild.cash),(49,before))
        self.assertFalse(hasattr(c.world,'season_tournament'))
    def test_duplicate_finish_rejected(self):
        c=self.c;c.submit_week(1,49,dict(group_mode=True))
        cfg=c.group_play;result=FixtureHelper.result(cfg,0)
        c.finish_group(cfg['match'],result)
        with self.assertRaises(ValueError):c.finish_group(cfg['match'],result)
        self.assertEqual(c.world.season_tournament['points'][c.guild.gid],100)
        self.assertEqual(len(c.world.season_tournament['matches']),16)

if __name__=='__main__':unittest.main()
