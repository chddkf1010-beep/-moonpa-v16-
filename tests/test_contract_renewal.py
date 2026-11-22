import json
import unittest
from unittest.mock import patch

from campaign import Campaign
import moonpa_economy_v15_1 as economy
from moonpa_savegame import create_save, load_save
import pages_bridge


def complete_contract_review(game):
    review = game.season_contracts()
    if review is None:
        return
    for row in review['pending']:
        game.decide_contract(game.season, game.week, row['id'], row['contract_end'], game.season + 1)
    game.advance_phase('report')


class ContractRenewalTests(unittest.TestCase):
    def test_member_endpoint_renews_early_and_rejects_a_stale_offer(self):
        game = Campaign(23, interactive=True)
        game.phase = 'ready'
        member = game.guild.fighters[0]
        member.contract_end = 2
        original = pages_bridge.game
        try:
            pages_bridge.game = game
            detail = json.loads(pages_bridge.handle('member', json.dumps(dict(id=member.fid))))
            self.assertEqual(detail['renewal']['end_seasons'], [3, 4, 5, 6])
            payload = json.dumps(dict(season=1, week=1, id=member.fid, expected_end=2, new_end=3))
            response = json.loads(pages_bridge.handle('contract_decision', payload))
            self.assertEqual(response['detail']['contract_end'], 3)
            self.assertEqual(member.wage, detail['renewal']['renewal_wage'])
            with self.assertRaises(ValueError):
                pages_bridge.handle('contract_decision', payload)
            loaded = load_save(create_save(game))
            self.assertEqual(loaded.member_detail(member.fid)['contract_end'], 3)
        finally:
            pages_bridge.game = original

    def test_last_month_holds_for_decisions_and_round_trips_release(self):
        game = Campaign(23, interactive=True)
        game.phase = 'ready'
        game.week = 48
        game.world.money.credit(game.guild, 15000, 'test_contract_funds')
        keep, release = game.guild.fighters[:2]
        for member in game.guild.fighters:
            member.contract_end = 2
        keep.contract_end = release.contract_end = 1
        keep.age = release.age = 24

        game.submit_month(1, 48, dict(mission_orders=[]))
        self.assertEqual((game.season, game.week_report['month'], game.phase), (1, 12, 'report'))
        self.assertIsNone(game.month_run)
        self.assertEqual({row['id'] for row in game.season_contracts()['pending']}, {keep.fid, release.fid})
        game.decide_contract(1, 51, keep.fid, 1, 4)
        with self.assertRaises(ValueError):
            game.advance_phase('report')
        game.decide_contract(1, 51, release.fid, 1)
        self.assertIn(release.fid, {member.fid for member in game.guild.fighters})
        game = load_save(create_save(game))
        self.assertEqual(game.season_contracts()['pending'], [])
        select_offer = economy.select_offer
        with patch.object(economy, 'select_offer', side_effect=lambda guild, world: [
                f for f in select_offer(guild, world) if f.fid != release.fid]):
            game.advance_phase('report')
        self.assertEqual((game.season, game.week), (2, 1))
        self.assertEqual(game.member_detail(keep.fid)['contract_end'], 4)
        self.assertIn(release.fid, {member.fid for member in game.world.fa})
        self.assertEqual(sum(e['amount'] for e in game.week_report['entries']), game.week_report['cash_change'])
        game.world.money.reconcile()
        game.advance_phase('report')
        self.assertEqual(game.phase, 'draft')
