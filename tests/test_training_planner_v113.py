"""v11-3: dry-run training recommendations and ledger-backed training reports."""
import copy
import json
import unittest

from campaign import Campaign
import moonpa_training_planner as planner
from moonpa_savegame import create_save, load_save
import pages_bridge


class TrainingPlannerV113(unittest.TestCase):
    def setUp(self):
        self.game = Campaign(23, interactive=True)
        self.game.phase = 'ready'

    def test_preview_readonly_8_people_and_budget_units(self):
        game = self.game
        before = create_save(game)
        p = planner.preview(game, 'attack', {}, 4)
        self.assertEqual(before, create_save(game))
        self.assertEqual(len(p['members']), 8)
        self.assertEqual(len(set(m['id'] for m in p['members'])), 8)
        self.assertEqual(len(p['selected_ids']), 4)
        self.assertEqual(p['direct_nominal_cost'],
                         p['unit_cost'] * len(p['selected_ids']))
        self.assertEqual(p['fixed_cost'], game.operations_view()['fixed'])
        self.assertEqual(p['conservative_cash'], max(0, game.guild.cash - p['fixed_cost']))
        self.assertTrue(all(row['status'] == 'available' for row in p['members']))

    def test_manual_missions_attack_rest_and_existing_training_not_overwritten(self):
        game = self.game
        people = planner.preview(game, 'attack', {}, 8)['members']
        ids = [m['id'] for m in people]
        assignments = {str(ids[0]): 'attack',
                       str(ids[1]): 'elite',
                       str(ids[2]): 'rest',
                       str(ids[3]): 'training',
                       str(ids[4]): 'mission1',
                       str(ids[5]): 'defend'}
        before = create_save(game)
        result = planner.preview(game, 'attack', assignments, 8)
        statuses = {m['id']:m['status'] for m in result['members']}
        self.assertEqual([statuses[i] for i in ids[:6]],
                         ['reserved','reserved','reserved','already','reserved','reserved'])
        self.assertTrue(set(result['selected_ids']).isdisjoint(ids[:6]))
        self.assertEqual(result['already_training'], 1)
        self.assertEqual(result['free_first'], 14)
        self.assertEqual(before, create_save(game))

    def test_injuries_away_and_phase_are_excluded(self):
        game = self.game
        people = planner.preview(game)['members']
        fighter = next(f for f in game.guild.fighters if f.fid==people[0]['id'])
        fighter.injured = 2
        p = planner.preview(game)
        # The existing prebattle deputy replaces injured members in the eight.
        self.assertNotIn(fighter.fid,{row['id'] for row in p['members']})
        self.assertNotIn(fighter.fid,p['selected_ids'])
        game.phase='report'
        before=create_save(game)
        locked=planner.preview(game)
        self.assertFalse(locked['ready'])
        self.assertFalse(locked['selected_ids'])
        self.assertEqual(before,create_save(game))

    def test_first_team_capacity_and_invalid_orders(self):
        game = self.game
        people = planner.preview(game, count=8)['members']
        # Keep the 8 primaries free, reserve 14 other available members if any.
        others = [f for f in game.guild.fighters
                  if f.fid not in {m['id'] for m in people}]
        assignment = {str(f.fid):'rest' for f in others}
        p = planner.preview(game, assignments=assignment, count=8)
        self.assertEqual(p['free_first'],max(0,20-len(others)))
        self.assertLessEqual(len(p['selected_ids']),p['free_first'])
        before=create_save(game)
        invalid = [({'999999':'training'},4),
                   ({str(people[0]['id']):'invalid'},4),
                   ({str(people[0]['id']):True},4),
                   ({'01':'training'},4),
                   ({},0), ({},9), ({},True)]
        for assignments,count in invalid:
            with self.subTest(assignments=assignments,count=count):
                with self.assertRaises(ValueError):
                    planner.preview(game,assignments=assignments,count=count)
        with self.assertRaises(ValueError):
            planner.preview(game,mode='invalid')
        self.assertEqual(before,create_save(game))

    def test_weekly_training_report_reconciles_actual_ledger_and_spells(self):
        game=self.game
        fighter=game.guild.fighters[0]
        before={f.fid:(game.world.spells[f.fid].training,
                       game.world.spells[f.fid].investment) for f in game.guild.fighters}
        ca_before={f.fid:f.ca for f in game.guild.fighters}
        game.submit_week(1,1,{'training':[fighter.fid]})
        report=game.week_report
        training=report['training_report']
        ledger_cost=sum(-row['amount'] for row in report['entries']
                        if row['category']=='paid_training')
        invested=sum(-row['amount'] for row in report['entries']
                     if row['category']=='paid_investment')
        self.assertEqual(training['paid_total'],ledger_cost)
        self.assertEqual(training['investment_total'],invested)
        self.assertEqual(sum(row['paid'] for row in training['rows']),ledger_cost)
        self.assertEqual(sum(row['invested'] for row in training['rows']),invested)
        self.assertEqual(training['funded_count'],
                         sum(row['paid']>0 for row in training['rows']))
        by_id={row['id']:row for row in training['rows']}
        self.assertIn(fighter.fid,by_id)
        self.assertEqual(by_id[fighter.fid]['group'],'집중 훈련')
        for fid,row in by_id.items():
            spell=game.world.spells[fid]
            self.assertEqual(row['paid'],spell.training-before[fid][0])
            self.assertEqual(row['invested'],spell.investment-before[fid][1])
            self.assertAlmostEqual(row['ca_change'],round(next(
                f.ca for f in game.guild.fighters if f.fid==fid)-ca_before[fid],3))
        self.assertEqual(report['cash_change'],sum(x['amount'] for x in report['entries']))
        game.world.money.reconcile()

    def test_bridge_does_not_autosave_or_advance_clock_and_weekly_report_roundtrip(self):
        game = self.game
        previous=pages_bridge.game
        try:
            pages_bridge.game=game
            before=create_save(game)
            request=dict(mode='defense',count=3,assignments={})
            reply=json.loads(pages_bridge.handle('growth_training_plan',json.dumps(request)))
            self.assertEqual(len(reply['selected_ids']),3)
            self.assertEqual(before,create_save(game))
            self.assertEqual((game.season,game.week),(1,1))
            game.submit_week(1,1,{'training':reply['selected_ids']})
            snapshot=create_save(game)
            restored=load_save(snapshot)
            self.assertEqual(restored.week_report['training_report'],
                             game.week_report['training_report'])
        finally:
            pages_bridge.game=previous


if __name__=='__main__':
    unittest.main()
