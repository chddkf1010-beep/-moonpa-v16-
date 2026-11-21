"""v8: real roster, complete opposition intel, restricted deputy AI, packet and saves."""
import copy
import json
import unittest

from campaign import Campaign
import moonpa_prebattle as prebattle
from moonpa_savegame import create_save,load_save
import pages_bridge


class PrebattleV8Tests(unittest.TestCase):
    def setUp(self):
        self.g=Campaign(23,interactive=True)
        self.g.phase='ready'
        self.v=prebattle.view(self.g,'attack')
        self.assertIsNotNone(self.v['zone_id'])
        self.zone=self.v['zone_id']
        self.p={k:self.v['plan'][k] for k in ('formation','captain','deputy')}

    def test_8v8_enemy_full_reveal_uses_real_character_and_martial_arts(self):
        v=self.v
        self.assertEqual(len(v['enemy']['members']),8)
        self.assertEqual(len(v['plan']['formation']),8)
        self.assertTrue(v['diagnosis'])
        self.assertIn('전열',v['plan']['briefing'])
        self.assertTrue(v['enemy']['captain']!=v['enemy']['deputy'])
        for unit in v['enemy']['members']:
            self.assertEqual(set(unit['attrs']),set(prebattle.ATTRIBUTES))
            self.assertTrue(unit['skills'])
            self.assertTrue(unit['equipped'])
            self.assertIn(unit['row'],('front','back'))
            # Ability schema intentionally has only label + id/value/appointment.
            self.assertIn('label',unit['captain_ability'])
        self.assertEqual(len(v['roster']),len(self.g.guild.fighters))
        ids={f.fid for f in self.g.guild.fighters}
        self.assertEqual({r['id'] for r in self.p['formation']}<=ids,True)

    def test_auto_cannot_read_enemy_attributes_or_equipped_skills(self):
        enemy=self.v['enemy']
        sig=prebattle.enemy_signals(enemy)
        self.assertNotIn('attrs',str(sig))
        a=prebattle.deputy_pick(self.v['roster'],sig)
        alt=copy.deepcopy(enemy)
        for f in alt['members']:
            f['attrs']={x:9999 for x in prebattle.ATTRIBUTES}
            f['ca']=99999
            f['skills']=[]
            f['equipped']=[]
            f['captain_ability']['value']=99
        b=prebattle.deputy_pick(self.v['roster'],prebattle.enemy_signals(alt))
        self.assertEqual(a,b)
        self.assertIn('세부 능력치',a['briefing'])

    def test_no_rng_or_ledger_side_effect_for_view_auto_preview_export(self):
        g=self.g
        w=g.world
        snap=(w.rng.getstate(),w.money.transactions,g.guild.cash,w.checkpoints,
              g.week,g.phase,g.pending_week,copy.deepcopy(w.prebattle_plans))
        for _ in range(3):
            v=prebattle.view(g,'attack',self.zone)
            suggestion=prebattle.deputy_pick(v['roster'],prebattle.enemy_signals(v['enemy']))
            packet=prebattle.preview(g,'attack',self.zone,suggestion)
            self.assertEqual(packet['packet']['kind'],'group_8v8')
            self.assertEqual(packet['packet']['schema'],'moonpa.prebattle.v1')
            self.assertEqual(packet['packet']['settlement_owner'],'campaign')
            self.assertFalse(packet['packet']['settlement_permitted'])
            self.assertEqual(len(packet['packet']['ally']['members']),8)
            self.assertEqual(len(packet['packet']['opponent']['members']),8)
            self.assertEqual(set(packet['diagnosis']),set(
                ('frontline','rear_protection','breakthrough','ranged_fire','notes','meaning')))
        self.assertEqual(snap,(w.rng.getstate(),w.money.transactions,g.guild.cash,
                               w.checkpoints,g.week,g.phase,g.pending_week,w.prebattle_plans))

    def test_leader_abilities_differ_by_assignment_and_are_not_applied(self):
        v=prebattle.preview(self.g,'attack',self.zone,self.p)
        ally=v['packet']['ally']
        c=ally['captain'];d=ally['deputy']
        self.assertNotEqual(c,d)
        self.assertEqual(ally['command']['captain']['appointment'],'captain')
        self.assertEqual(ally['command']['deputy']['appointment'],'deputy')
        self.assertNotIn('applied',ally)
        self.assertTrue(0<ally['command']['captain']['value']<1)
        self.assertTrue(0<ally['command']['deputy']['value']<1)

    def test_invalid_assignments_do_not_mutate_cash_seed_or_saved_plan(self):
        g=self.g
        snapshot=(g.guild.cash,g.world.money.transactions,
                  g.world.rng.getstate(),g.world.prebattle_plans.copy())
        cases=[]
        cases.append(dict(self.p,formation=self.p['formation'][:-1]))
        bad=copy.deepcopy(self.p);bad['formation'][1]['id']=bad['formation'][0]['id'];cases.append(bad)
        bad=copy.deepcopy(self.p);bad['captain']=bad['deputy'];cases.append(bad)
        bad=copy.deepcopy(self.p);bad['formation'][0]['skills']=['unlearned_skill'];cases.append(bad)
        bad=copy.deepcopy(self.p);bad['formation'][0]['skills']=[];cases.append(bad)
        bad=copy.deepcopy(self.p)
        for x in bad['formation']:x['row']='front'
        cases.append(bad)
        bad=copy.deepcopy(self.p);bad['formation'][0]['row']='side';cases.append(bad)
        for data in cases:
            with self.subTest(data=data),self.assertRaises(ValueError):
                prebattle.save(g,'attack',self.zone,data)
            self.assertEqual(snapshot,(g.guild.cash,g.world.money.transactions,
                                       g.world.rng.getstate(),g.world.prebattle_plans))
        with self.assertRaises(ValueError):
            prebattle.save(g,'attack',-987,self.p)

    def test_injured_and_away_members_cannot_play(self):
        g=self.g
        fid=self.p['formation'][0]['id']
        f=next(f for f in g.guild.fighters if f.fid==fid)
        f.injured=1
        with self.assertRaises(ValueError):prebattle.preview(g,'attack',self.zone,self.p)
        v=prebattle.view(g,'attack',self.zone)
        self.assertEqual(len(v['plan']['formation']),8)
        self.assertNotIn(fid,[row['id'] for row in v['plan']['formation']])
        f.injured=0
        # Busy expedition members must be treated like injured members.
        g.world.long_missions[g.guild.gid].append(
            dict(id='dummy',members=[fid],duration=2,progress=1,weekly_cost=1))
        try:
            with self.assertRaises(ValueError):prebattle.preview(g,'attack',self.zone,self.p)
        finally:
            g.world.long_missions[g.guild.gid].clear()

    def test_defense_is_hypothetical_until_actual_attacker_is_known(self):
        g=self.g
        home=next(z.zid for z in g.world.zones if z.owner==g.guild.gid and
                  z.tier==g.guild.tier)
        v=prebattle.view(g,'defense',home)
        self.assertTrue(v['enemy']['is_hypothetical'])
        self.assertIn('예상 공격군',v['enemy']['note'])
        self.assertEqual(len(v['enemy']['members']),8)
        packet=prebattle.preview(g,'defense',home,{
            key:v['plan'][key] for key in ('formation','captain','deputy')})['packet']
        self.assertEqual(packet['zone_id'],home)
        self.assertEqual(packet['mode'],'defense')
        self.assertFalse(packet['settlement_permitted'])
        with self.assertRaises(ValueError):prebattle.view(g,'defense',self.zone)

    def test_save_load_keeps_zone_leaders_and_skills_without_affecting_legacy_battles(self):
        g=self.g
        original=(g.guild.cash,g.world.money.transactions,g.week,g.phase)
        res=prebattle.save(g,'attack',self.zone,self.p)
        self.assertTrue(res['saved'])
        self.assertEqual(original,(g.guild.cash,g.world.money.transactions,g.week,g.phase))
        restored=load_save(create_save(g))
        view=prebattle.view(restored,'attack',self.zone)
        self.assertEqual(view['plan'],self.p)
        self.assertEqual(prebattle.preview(restored,'attack',self.zone,self.p)['packet'],
                         prebattle.preview(g,'attack',self.zone,self.p)['packet'])
        self.assertEqual(restored.guild.name,g.guild.name)
        restored.world.money.reconcile()

    def test_old_save_without_prebattle_plans_can_be_read(self):
        g=self.g
        delattr(g.world,'prebattle_plans')
        restored=load_save(create_save(g))
        self.assertEqual(restored.week,1)
        self.assertEqual(len(prebattle.view(restored,'attack')['plan']['formation']),8)
        prebattle.save(restored,'attack',self.zone,self.p)
        self.assertIn('attack',restored.world.prebattle_plans)

    def test_saved_formation_is_stale_after_week_changes(self):
        g=self.g
        prebattle.save(g,'attack',self.zone,self.p)
        self.assertEqual(prebattle.view(g,'attack',self.zone)['plan'],self.p)
        g.week=2
        v=prebattle.view(g,'attack',self.zone)
        self.assertIn('briefing',v['plan'])
        self.assertNotIn('briefing',self.p)

    def test_not_allowed_during_report_and_pending_battle(self):
        g=self.g
        for phase in ('report','tutorial','draft','fa'):
            g.phase=phase
            with self.subTest(phase=phase),self.assertRaises(ValueError):
                prebattle.save(g,'attack',self.zone,self.p)
        g.phase='ready'
        g.pending_week={'phase':'pending'}
        with self.assertRaises(ValueError):prebattle.save(g,'attack',self.zone,self.p)
        g.pending_week=None
        g.world.player_bankrupted=True
        with self.assertRaises(ValueError):prebattle.save(g,'attack',self.zone,self.p)

    def test_json_bridge_preserves_legacy_state_and_separate_contract(self):
        original=pages_bridge.game
        try:
            pages_bridge.game=self.g
            v=json.loads(pages_bridge.handle('prebattle_view',json.dumps({'mode':'attack'})))
            auto=json.loads(pages_bridge.handle('prebattle_auto',json.dumps(
                {'mode':'attack','zone_id':v['zone_id']})))
            data={x:auto['plan'][x] for x in ('formation','captain','deputy')}
            packet=json.loads(pages_bridge.handle('prebattle_preview',json.dumps(
                {'mode':'attack','zone_id':v['zone_id'],'data':data})))
            self.assertEqual(packet['packet']['kind'],'group_8v8')
            self.assertIsNone(self.g.week_report)
            persisted=json.loads(pages_bridge.handle('prebattle_save',json.dumps(
                {'mode':'attack','zone_id':v['zone_id'],'data':data})))
            self.assertTrue(persisted['saved'])
            saved=json.loads(pages_bridge.handle('export_save','{}'))
            pages_bridge.handle('new_game','{}')
            state=json.loads(pages_bridge.handle('import_save',json.dumps({'save':saved})))
            self.assertEqual(state['phase'],'ready')
            reread=json.loads(pages_bridge.handle('prebattle_view',json.dumps(
                {'mode':'attack','zone_id':v['zone_id']})))
            self.assertEqual(reread['plan'],data)
        finally:
            pages_bridge.game=original


if __name__=='__main__':
    unittest.main()
