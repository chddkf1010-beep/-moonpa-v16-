"""v11-2: deputy suggestion preview is read-only and commit is plan-checked."""
import copy
import json
import unittest

from campaign import Campaign
from moonpa_savegame import create_save
import pages_bridge


class TrainingFocusPreview(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23,interactive=True)
        self.game.phase='ready'

    def test_preview_eight_members_is_pure_read_and_has_no_training_cost(self):
        game=self.game
        fid=game.guild.fighters[0].fid
        game.set_training_focus(fid,'balanced')
        before=create_save(game)
        for mode in ('attack','defense'):
            proposal=game.preview_training_focus(mode)
            self.assertEqual(len(proposal['members']),8)
            self.assertEqual(len({r['id'] for r in proposal['members']}),8)
            self.assertEqual(len(proposal['token']),64)
            self.assertEqual(proposal['assigned_count']+proposal['preserved_count'],8)
            self.assertLessEqual(proposal['effective_change_count'],proposal['assigned_count'])
        self.assertEqual(before,create_save(game))

    def test_preview_exactly_matches_applied_changes_and_preserves_manual(self):
        game=self.game
        fid=game.preview_training_focus('attack')['members'][0]['id']
        game.set_training_focus(fid,'balanced')
        proposal=game.preview_training_focus('attack',False)
        current={m['id']:m['current'] for m in proposal['members']}
        self.assertEqual(proposal['preserved_count'],1)
        self.assertEqual(proposal['assigned_count'],7)
        self.assertEqual(next(m for m in proposal['members'] if m['id']==fid)['proposed'],'balanced')
        result=game.auto_training_focus('attack',False,proposal['token'])
        self.assertEqual(result['changed_count'],proposal['assigned_count'])
        self.assertEqual(result['effective_change_count'],proposal['effective_change_count'])
        self.assertEqual(result['preserved_count'],proposal['preserved_count'])
        for m in proposal['members']:
            self.assertEqual(game.world.training_focus[m['id']],m['proposed'])
            self.assertEqual(m['changed'],current[m['id']]!=m['proposed'])
        self.assertEqual(game.world.training_focus[fid],'balanced')

    def test_overwrite_preview_proposes_all_eight(self):
        game=self.game
        fid=game.preview_training_focus('defense')['members'][0]['id']
        game.set_training_focus(fid,'support')
        proposal=game.preview_training_focus('defense',True)
        self.assertEqual(proposal['assigned_count'],8)
        self.assertEqual(proposal['preserved_count'],0)
        self.assertTrue(next(m for m in proposal['members'] if m['id']==fid)['manual'])
        result=game.auto_training_focus('defense',True,proposal['token'])
        self.assertEqual(result['changed_count'],8)
        for member in proposal['members']:
            self.assertEqual(game.world.training_focus[member['id']],member['proposed'])

    def test_stale_proposal_rejects_without_partial_updates(self):
        game=self.game
        proposal=game.preview_training_focus('attack')
        fid=proposal['members'][0]['id']
        # A manually selected balanced focus must also invalidate a proposal.
        game.set_training_focus(fid,'balanced')
        before=create_save(game)
        with self.assertRaisesRegex(ValueError,'다시 확인'):
            game.auto_training_focus('attack',False,proposal['token'])
        self.assertEqual(before,create_save(game))
        with self.assertRaises(ValueError):
            game.auto_training_focus('attack',False,'invalid')
        self.assertEqual(before,create_save(game))

    def test_invalid_formation_and_state_do_not_mutate(self):
        game=self.game
        before=create_save(game)
        for bad in (None,1,'unknown',[]):
            with self.assertRaises(ValueError):
                game.preview_training_focus(bad)
        with self.assertRaises(ValueError):
            game.preview_training_focus('attack',overwrite='yes')
        game.phase='report'
        with self.assertRaises(ValueError):
            game.preview_training_focus('attack')
        game.phase='ready'
        self.assertEqual(before,create_save(game))

    def test_bridge_preview_is_readonly_and_commit_guarded(self):
        game=self.game
        old=pages_bridge.game
        try:
            pages_bridge.game=game
            snapshot=create_save(game)
            plan=json.loads(pages_bridge.handle(
                'growth_focus_preview','{"mode":"attack","overwrite":false}'))
            self.assertEqual(snapshot,create_save(game))
            self.assertEqual(plan['selected_count'],8)
            response=json.loads(pages_bridge.handle('growth_focus_auto',json.dumps(
                dict(mode='attack',overwrite=False,expected=plan['token']))))
            self.assertEqual(response['result']['changed_count'],8)
            self.assertEqual(len(response['result']['updated_ids']),8)
        finally:
            pages_bridge.game=old


if __name__=='__main__':
    unittest.main()
