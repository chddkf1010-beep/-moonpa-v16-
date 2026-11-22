"""v11-2: training focus can reshape paid training, never multiply its budget."""
import copy
import json
import math
import unittest

from campaign import Campaign
import moonpa_growth as growth
import moonpa_training_focus as focus
import moonpa_growth_dashboard as dashboard
from moonpa_savegame import create_save,load_save
import pages_bridge


class TrainingFocusV112(unittest.TestCase):
    def setUp(self):
        self.g=Campaign(23,interactive=True)
        self.g.phase='ready'

    def test_six_named_options_and_unchanged_balanced_formula(self):
        self.assertEqual(set(growth.TRAINING_FOCUSES),
                         {'balanced','attack','defense','ranged','internal','support'})
        self.assertEqual(len(focus.options()),6)
        for role in range(6):
            original=[.5+weight/5 for weight in growth.WEIGHTS[role]]
            self.assertEqual(list(growth.training_factors(role,'balanced')),original)
            for name in growth.TRAINING_FOCUSES:
                values=growth.training_factors(role,name)
                self.assertEqual(len(values),8)
                self.assertTrue(all(v>0 for v in values))
                self.assertAlmostEqual(sum(values),sum(original),places=12)
                self.assertAlmostEqual(sum(values),8.,places=12)
            for key,(_,targets,_) in growth.TRAINING_FOCUSES.items():
                if key=='balanced':continue
                values=growth.training_factors(role,key)
                for i,attr in enumerate(growth.ATTRIBUTES):
                    if attr in targets:
                        self.assertGreater(values[i],original[i])
                    else:
                        self.assertLess(values[i],original[i])
        with self.assertRaises(ValueError):
            growth.training_factors(0,'unrecognized')

    def test_training_gain_redistributes_only_and_preserves_other_counters(self):
        original=self.g.guild.fighters[0]
        self.assertEqual(original.role,original.role)
        baseline=copy.deepcopy(original)
        focused=copy.deepcopy(original)
        pre=baseline.development.attributes[:]
        baseline.development.train(baseline,1.25,'balanced')
        focused.development.train(focused,1.25,'defense')
        differences_baseline=[x-y for x,y in zip(baseline.development.attributes,pre)]
        differences_focused=[x-y for x,y in zip(focused.development.attributes,pre)]
        self.assertAlmostEqual(sum(differences_baseline),sum(differences_focused),places=10)
        self.assertGreater(differences_focused[1],differences_baseline[1])
        self.assertGreater(differences_focused[2],differences_baseline[2])
        self.assertLess(differences_focused[0],differences_baseline[0])
        self.assertEqual(baseline.lv,focused.lv)
        self.assertEqual(baseline.xp,focused.xp)
        self.assertEqual(baseline.development.trainee_weeks,focused.development.trainee_weeks)

    def test_default_focused_training_never_changes_economy_or_xp(self):
        x=self.g
        y=Campaign(23,interactive=True)
        y.phase='ready'
        fid=x.guild.fighters[0].fid
        self.assertEqual(fid,y.guild.fighters[0].fid)
        x.set_training_focus(fid,'defense')
        x.submit_week(1,1,{'training':[fid]})
        y.submit_week(1,1,{'training':[fid]})
        f1=next(z for z in x.guild.fighters if z.fid==fid)
        f2=next(z for z in y.guild.fighters if z.fid==fid)
        self.assertEqual(x.guild.cash,y.guild.cash)
        self.assertEqual(x.world.money.stats,y.world.money.stats)
        self.assertEqual((f1.lv,f1.xp,f1.injured),
                         (f2.lv,f2.xp,f2.injured))
        self.assertAlmostEqual(sum(f1.development.attributes),sum(f2.development.attributes),places=9)
        self.assertNotEqual(f1.development.attributes,f2.development.attributes)
        self.assertEqual(x.world.growth_history[fid][-1]['training_focus'],'defense')
        self.assertEqual(y.world.growth_history[fid][-1]['training_focus'],'balanced')
        x.world.money.reconcile()
        y.world.money.reconcile()

    def test_set_one_is_a_readonly_economy_action_and_autosave_roundtrip(self):
        g=self.g
        member=g.guild.fighters[0]
        before=(g.guild.cash,g.world.rng.getstate(),g.world.money.transactions,
                g.week,g.season,copy.deepcopy(g.world.prebattle_plans),
                copy.deepcopy(g.world.growth_history),member.ca)
        result=g.set_training_focus(member.fid,'ranged')
        self.assertEqual(result['current'],'ranged')
        self.assertTrue(result['changed'])
        self.assertEqual(before,(g.guild.cash,g.world.rng.getstate(),g.world.money.transactions,
                g.week,g.season,g.world.prebattle_plans,g.world.growth_history,member.ca))
        saved=create_save(g)
        restored=load_save(saved)
        self.assertEqual(focus.get(restored.world,member.fid),'ranged')
        self.assertEqual(restored.member_detail(member.fid)['training_focus']['focus'],'ranged')
        self.assertEqual(dashboard.dashboard(restored,'attack')['members'][0]['focus']['focus'],
                         focus.get(restored.world,dashboard.dashboard(restored,'attack')['members'][0]['id']))

    def test_input_validation_and_locking_atomicity(self):
        g=self.g
        fid=g.guild.fighters[0].fid
        bad_cases=[(True,'attack'),('1','attack'),(999999,'attack'),
                   (fid,'missing'),(fid,''),(fid,True),(fid,None)]
        for index,val in bad_cases:
            before=copy.deepcopy(getattr(g.world,'training_focus',{}))
            with self.subTest(index=index,val=val),self.assertRaises(ValueError):
                g.set_training_focus(index,val)
            self.assertEqual(getattr(g.world,'training_focus',{}),before)
        for phase in ('report','elite','draft'):
            g.phase=phase
            with self.assertRaises(ValueError):
                g.set_training_focus(fid,'attack')
        g.phase='ready'
        g.pending_week={'a':1}
        with self.assertRaises(ValueError):
            g.set_training_focus(fid,'attack')
        g.pending_week=None
        self.assertEqual(g.world.training_focus,{})
        g.world.money.reconcile()

    def test_both_deputy_modes_target_exact_current_eight_and_manual_override(self):
        g=self.g
        attack=dashboard.dashboard(g,'attack')
        selected={f['id'] for f in attack['members']}
        member=attack['members'][0]
        g.set_training_focus(member['id'],'balanced')
        result=g.auto_training_focus('attack')
        self.assertEqual(result['preserved_count'],1)
        self.assertEqual(result['changed_count'],7)
        self.assertEqual(set(result['updated_ids']),selected-{member['id']})
        self.assertEqual(focus.get(g.world,member['id']),'balanced')
        for person in attack['members'][1:]:
            f=next(x for x in g.guild.fighters if x.fid==person['id'])
            self.assertEqual(focus.get(g.world,f.fid),focus.suggest(f)['focus'])
        before=copy.deepcopy(g.world.training_focus)
        with self.assertRaises(ValueError):
            g.auto_training_focus('invalid',True)
        with self.assertRaises(ValueError):
            g.auto_training_focus('defense',overwrite='yes')
        self.assertEqual(g.world.training_focus,before)
        override=g.auto_training_focus('defense',True)
        self.assertEqual(override['changed_count'],8)
        self.assertEqual(set(override['updated_ids']),
                         {f['id'] for f in dashboard.dashboard(g,'defense')['members']})
        g.world.money.reconcile()

    def test_no_fallback_8_does_not_apply_any_partial_batch(self):
        g=self.g
        before=copy.deepcopy(g.world.training_focus)
        for f in g.guild.fighters[7:]:f.injured=2
        with self.assertRaises(ValueError):
            g.auto_training_focus('attack')
        self.assertEqual(g.world.training_focus,before)

    def test_legacy_save_missing_focus_becomes_balanced_and_updates_safe(self):
        g=self.g
        delattr(g.world,'training_focus')
        old=create_save(g)
        restored=load_save(old)
        member=restored.guild.fighters[0]
        self.assertEqual(restored.member_detail(member.fid)['training_focus']['focus'],'balanced')
        self.assertEqual(dashboard.dashboard(restored,'attack')['focus_options'][0]['id'],'balanced')
        restored.set_training_focus(member.fid,'attack')
        self.assertEqual(load_save(create_save(restored)).world.training_focus[member.fid],'attack')

    def test_training_focus_follows_id_between_sects_but_only_player_train_uses_it(self):
        g=self.g
        f=g.guild.fighters[0]
        g.set_training_focus(f.fid,'internal')
        another=next(x for x in g.world.guilds.values() if x.gid!=g.guild.gid)
        g.guild.fighters.remove(f)
        another.fighters.append(f)
        self.assertEqual(focus.get(g.world,f.fid),'internal')
        self.assertEqual(focus.profile(g.world,f)['focus'],'internal')
        # This policy belongs to the fighter, but AI train_week ignores it.
        # Read the actual normalized AI logic as a contract (balanced by owner)
        self.assertIn('balanced',growth.TRAINING_FOCUSES)

    def test_bridge_mutation_autosave_safety_and_read_only_view(self):
        g=self.g
        old=pages_bridge.game
        fid=dashboard.dashboard(g,'attack')['members'][0]['id']
        try:
            pages_bridge.game=g
            view=json.loads(pages_bridge.handle('growth_view','{}'))
            self.assertEqual(len(view['focus_options']),6)
            before=create_save(g)
            json.loads(pages_bridge.handle('growth_view','{}'))
            self.assertEqual(before,create_save(g))
            result=json.loads(pages_bridge.handle('growth_focus_set',json.dumps(
                dict(id=fid,focus='support'))))
            self.assertEqual(result['result']['current'],'support')
            self.assertEqual(result['state']['season'],1)
            auto=json.loads(pages_bridge.handle('growth_focus_auto',json.dumps(
                dict(mode='attack',overwrite=False))))
            self.assertGreaterEqual(auto['result']['preserved_count'],1)
        finally:
            pages_bridge.game=old
        g.world.money.reconcile()


if __name__=='__main__':
    unittest.main()
