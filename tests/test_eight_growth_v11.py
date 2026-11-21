"""v11: the eight-hero growth history uses real settlements and never extrapolates."""
import copy
import json
import unittest

from campaign import Campaign
from moonpa_savegame import create_save,load_save
import moonpa_growth_dashboard as growth
import moonpa_prebattle as prebattle
import pages_bridge


class EightGrowthV11Tests(unittest.TestCase):
    def setUp(self):
        self.g=Campaign(23,interactive=True)
        self.g.phase='ready'

    def test_new_game_has_first_observation_but_no_fabricated_past(self):
        g=self.g
        w=g.world
        self.assertEqual(len(w.growth_first),len(g.guild.fighters))
        self.assertEqual(len(w.growth_history),len(g.guild.fighters))
        for f in g.guild.fighters:
            record=w.growth_history[f.fid]
            self.assertEqual(len(record),1)
            self.assertEqual((record[0]['season'],record[0]['week'],record[0]['phase']),
                             (1,1,'joined'))
            self.assertEqual(record[0]['activity'],'초기 문파원')
            self.assertEqual(set(record[0]['attrs']),set(growth.ATTR_LABELS))
        data=growth.dashboard(g,'attack')
        self.assertEqual(len(data['members']),8)
        self.assertEqual(data['source'],'부문주 기본 추천')
        self.assertEqual(data['summary']['front']+data['summary']['back'],8)
        self.assertEqual(data['summary']['growth_5_sample'],0)
        self.assertIsNone(data['summary']['growth_5'])
        self.assertTrue(all(m['growth_5']['observed_weeks']==0 for m in data['members']))
        self.assertTrue(all(m['total_delta']==0 for m in data['members']))

    def test_two_modes_respect_separate_saved_lineups_and_leaders(self):
        g=self.g
        offense=prebattle.view(g,'attack')
        defense=prebattle.view(g,'defense')
        for mode,data in (('attack',offense),('defense',defense)):
            p={k:data['plan'][k] for k in ('formation','captain','deputy')}
            if mode=='defense':
                p=copy.deepcopy(p)
                p['formation'].reverse()
                p['captain'],p['deputy']=p['deputy'],p['captain']
            prebattle.save(g,mode,data['zone_id'],p)
        attack=growth.dashboard(g,'attack')
        defending=growth.dashboard(g,'defense')
        self.assertIn('저장된 점령전',attack['source'])
        self.assertIn('저장된 방어전',defending['source'])
        self.assertNotEqual([x['id'] for x in attack['members']],
                            [x['id'] for x in defending['members']])
        self.assertEqual(attack['captain'],next(m['id'] for m in attack['members'] if m['captain']))
        self.assertEqual(defending['deputy'],next(m['id'] for m in defending['members'] if m['deputy']))
        self.assertEqual({m['id'] for m in defending['members']},
                         {m['id'] for m in attack['members']})

    def test_one_real_week_writes_once_after_training_and_marks_activity(self):
        g=self.g
        selected=g.guild.fighters[0]
        start=selected.ca
        first=copy.deepcopy(g.world.growth_first[selected.fid])
        g.submit_week(1,1,{'training':[selected.fid]})
        self.assertEqual((g.season,g.week),(1,2))
        series=g.world.growth_history[selected.fid]
        self.assertEqual(len(series),2)
        close=series[-1]
        self.assertEqual((close['season'],close['week'],close['phase']),(1,1,'close'))
        self.assertEqual(close['activity'],'집중 훈련')
        self.assertEqual(close['ca'],round(selected.ca,2))
        self.assertGreaterEqual(selected.ca,start)
        self.assertEqual(g.world.growth_first[selected.fid],first)
        self.assertFalse(growth.record_week(g,1,1,None))
        self.assertEqual(len(g.world.growth_history[selected.fid]),2)
        g.world.money.reconcile()

    def test_actual_5_and_10_week_growth_no_interpolation(self):
        g=self.g
        for week in range(1,12):
            if week>1:g.phase='ready'
            g.submit_week(1,week,{})
        v=growth.dashboard(g,'attack')
        self.assertEqual(g.week,12)
        self.assertEqual(v['summary']['growth_5_sample'],8)
        self.assertEqual(v['summary']['growth_10_sample'],8)
        for entry in v['members']:
            self.assertTrue(entry['growth_5']['complete'])
            self.assertTrue(entry['growth_10']['complete'])
            self.assertEqual(entry['growth_5']['observed_weeks'],5)
            self.assertEqual(entry['growth_10']['observed_weeks'],10)
            self.assertGreaterEqual(len(entry['history']),11)
            self.assertEqual(len({(x['season'],x['week']) for x in entry['history']}),len(entry['history']))
            self.assertEqual(set(entry['attrs']),set(growth.ATTR_LABELS))
            self.assertEqual(set(entry['stat_deltas']),set(growth.ATTR_LABELS))
        g.world.money.reconcile()

    def test_recruit_start_is_real_join_time_and_no_other_fighter_reset(self):
        g=self.g
        existing=g.guild.fighters[0]
        old=copy.deepcopy(g.world.growth_first[existing.fid])
        prospect=next(f for f in g.world.fa if f.age<=42)
        before={k:len(v) for k,v in g.world.growth_history.items()}
        growth.record_join(g.world,prospect,1,1,g.guild.gid,'자유 낭인 영입')
        self.assertEqual(g.world.growth_first[existing.fid],old)
        self.assertEqual(g.world.growth_history[prospect.fid][0]['activity'],'자유 낭인 영입')
        self.assertTrue(all(len(g.world.growth_history[k])==v for k,v in before.items()))
        # Repeat the same acquisition record is idempotent.
        self.assertFalse(growth.record_join(g.world,prospect,1,1,g.guild.gid,'자유 낭인 영입'))

    def test_transfer_preserves_fighter_global_id_series(self):
        g=self.g
        f=g.guild.fighters[0]
        growth.record_week(g,1,1,None)
        original=copy.deepcopy(g.world.growth_first[f.fid])
        earlier=len(g.world.growth_history[f.fid])
        growth.record_join(g.world,f,1,2,g.guild.gid,'이적 영입')
        self.assertEqual(g.world.growth_first[f.fid],original)
        self.assertEqual(len(g.world.growth_history[f.fid]),earlier+1)
        self.assertEqual(g.world.growth_history[f.fid][-1]['activity'],'이적 영입')

    def test_locked_members_cannot_be_recommended_for_training(self):
        g=self.g
        before=growth.dashboard(g,'attack')
        fid=before['members'][0]['id']
        f=next(x for x in g.guild.fighters if x.fid==fid)
        f.injured=2
        after=growth.dashboard(g,'attack')
        # The auto-team replaces an injured fighter, rather than implying they can train.
        self.assertNotIn(fid,[m['id'] for m in after['members']])
        f.injured=0
        g.phase='report'
        reported=growth.dashboard(g,'defense')
        self.assertFalse(reported['ready'])
        self.assertTrue(all(not m['training']['can_train'] for m in reported['members']))

    def test_recommendations_are_read_only_and_explain_roles(self):
        g=self.g
        snapshot=create_save(g)
        rng=g.world.rng.getstate()
        for mode in ('attack','defense'):
            data=growth.dashboard(g,mode)
            self.assertEqual(len(data['recommendations']),8)
            self.assertTrue(all(r['reasons'] for r in data['recommendations']))
            self.assertTrue(all(isinstance(r['score'],float) for r in data['recommendations']))
            self.assertIn('실제',data['history_note'])
            self.assertEqual(sum(data['role_counts'].values()),8)
        self.assertEqual(create_save(g),snapshot)
        self.assertEqual(g.world.rng.getstate(),rng)

    def test_no_past_for_old_v10_save_and_next_week_recording(self):
        g=self.g
        for field in ('growth_history','growth_first'):
            delattr(g.world,field)
        old=create_save(g)
        loaded=load_save(old)
        v=growth.dashboard(loaded,'attack')
        self.assertIsNone(v['summary']['growth_5'])
        self.assertTrue(all(x['history']==[] and x['initial_ca'] is None for x in v['members']))
        loaded.phase='ready'
        loaded.submit_week(1,1,{})
        self.assertEqual(len(loaded.world.growth_history),len(loaded.guild.fighters))
        first=next(iter(loaded.world.growth_history.values()))
        self.assertEqual(len(first),1)
        self.assertEqual(first[0]['phase'],'close')
        loaded.world.money.reconcile()

    def test_save_load_restores_real_observations_and_no_double_settlement(self):
        g=self.g
        g.submit_week(1,1,{})
        saved=create_save(g)
        restored=load_save(saved)
        self.assertEqual(restored.world.growth_history,g.world.growth_history)
        self.assertEqual(restored.world.growth_first,g.world.growth_first)
        self.assertEqual(growth.dashboard(restored,'attack'),growth.dashboard(g,'attack'))
        restored.world.money.reconcile()

    def test_bridge_query_does_not_trigger_saves_or_rng(self):
        g=self.g
        original=pages_bridge.game
        before=create_save(g)
        try:
            pages_bridge.game=g
            attack=json.loads(pages_bridge.handle('growth_view','{"mode":"attack"}'))
            defense=json.loads(pages_bridge.handle('growth_view','{"mode":"defense"}'))
            self.assertEqual(attack['mode'],'attack')
            self.assertEqual(defense['mode'],'defense')
            self.assertEqual(len(attack['members']),8)
            with self.assertRaises(ValueError):
                pages_bridge.handle('growth_view','{"mode":"unknown"}')
        finally:
            pages_bridge.game=original
        self.assertEqual(create_save(g),before)


if __name__=='__main__':
    unittest.main()
