import json
import math
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
        sign_contract(game, row['id'], row['contract_end'], game.season + 1)
    game.advance_phase('report')


def sign_contract(game, fid, expected_end, end):
    fighter = next(f for f in game.guild.fighters if f.fid == fid)
    wage = math.ceil(max(fighter.wage, economy.old.salary(fighter)) * 0.9)
    result = game.decide_contract(game.season, game.week, fid, expected_end, action='offer',
                                  new_end=end, wage=wage, expected_attempts=0)
    terms = next(option for option in result['options'] if option['end'] == end)
    game.decide_contract(game.season, game.week, fid, expected_end, action='sign',
                         new_end=end, wage=terms['wage'], expected_attempts=1)


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
            payload = dict(season=1, week=1, id=member.fid, expected_end=2, new_end=3, wage=100)
            offer = json.loads(pages_bridge.handle('contract_decision', json.dumps(
                dict(payload, action='offer', expected_attempts=0))))
            self.assertEqual(offer['result']['status'], 'accepted')
            self.assertEqual(member.contract_end, 2)
            sign = json.dumps(dict(payload, action='sign', expected_attempts=1))
            response = json.loads(pages_bridge.handle('contract_decision', sign))
            self.assertEqual(response['detail']['contract_end'], 3)
            self.assertEqual(member.wage, 100)
            with self.assertRaises(ValueError):
                pages_bridge.handle('contract_decision', sign)
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
        sign_contract(game, keep.fid, 1, 4)
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

    def test_offer_limit_persists_and_final_counter_can_still_be_signed(self):
        game = Campaign(23, interactive=True)
        game.phase = 'ready'
        f = game.guild.fighters[0]
        f.contract_end = 1
        seeded_profile = (2, 100, 1, dict(tenure=0, loyalty=0, performance=0))
        with patch.object(Campaign, 'renewal_profile', return_value=seeded_profile):
            def propose(current, count, end, wage):
                return current.decide_contract(1, current.week, f.fid, 1, action='offer',
                                               new_end=end, wage=wage, expected_attempts=count)
            self.assertEqual(propose(game, 0, 5, 50)['status'], 'declined')
            self.assertEqual(propose(game, 1, 5, 50)['status'], 'declined')
            self.assertEqual(propose(game, 1, 4, 85)['status'], 'counter')
            game = load_save(create_save(game))
            self.assertEqual(game.member_detail(f.fid)['renewal']['remaining_offers'], 1)
            game.week = 51
            game.world.money.credit(game.guild, 5000, 'test_contract_funds')
            game.submit_week(1, 51, {})
            pending = next(row for row in game.season_contracts()['pending'] if row['id'] == f.fid)
            self.assertEqual(pending['remaining_offers'], 1)
            third = propose(game, 2, 5, 55)
            self.assertEqual(third['status'], 'declined')
            self.assertEqual([option['end'] for option in third['options']], [3, 4])
            with self.assertRaises(ValueError):
                propose(game, 3, 4, 99)
            option = third['options'][0]
            with self.assertRaises(ValueError):
                game.decide_contract(1, game.week, f.fid, 1, action='sign',
                                     new_end=option['end'], wage=option['wage']-1, expected_attempts=3)
            game.decide_contract(1, game.week, f.fid, 1, action='sign', new_end=option['end'],
                                 wage=option['wage'], expected_attempts=3)
            detail = game.member_detail(f.fid)
            self.assertEqual((detail['contract_end'], detail['wage']), (3, 100))
            self.assertEqual(detail['renewal']['remaining_offers'], 0)

    def test_tenure_and_relative_standings_lower_asking_wage(self):
        game = Campaign(23, interactive=True)
        game.season = 6
        game.week = 32
        member = min(game.guild.fighters, key=lambda f:f.ca)
        spell = game.world.spells[member.fid]
        spell.season_in = game.season
        game.guild.score = -10000
        bottom = game.renewal_profile(member)
        spell.season_in = game.season-4
        loyal = game.renewal_profile(member)
        self.assertEqual(loyal[3]['loyalty'], 8)
        self.assertLess(loyal[2], bottom[2])
        game.guild.score = 10000
        leading = game.renewal_profile(member)
        self.assertGreater(leading[3]['performance'], loyal[3]['performance'])
        self.assertLess(leading[2], loyal[2])

    def test_prior_save_without_negotiations_defaults_to_three_offers(self):
        game = Campaign(23, interactive=True)
        fid = game.guild.fighters[0].fid
        del game.contract_talks
        restored = load_save(create_save(game))
        self.assertEqual(restored.member_detail(fid)['renewal']['remaining_offers'], 3)
