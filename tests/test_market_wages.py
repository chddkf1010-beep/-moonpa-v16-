import unittest
from unittest.mock import patch

from campaign import Campaign
import moonpa_economy_v15_1 as economy


class MarketWageTests(unittest.TestCase):
    def test_wage_premium_accelerates_and_fa_contract_uses_the_quote(self):
        game = Campaign(23)
        world = game.world
        fighter = world.fa[0]
        fighter.role = 2
        fighter.lv = 10
        fighter.age = 24
        rates = []
        for grade, ca in enumerate((100, 120, 140, 160, 180), start=1):
            fighter.ca, fighter.pa = ca, ca+20
            fighter.development.observed_pa_grade = grade
            rates.append(economy.market_wage(fighter))
        self.assertEqual(rates, [19, 32, 54, 94, 164])

        world.money.credit(game.guild, 10000, 'test_funds')
        quote = world.free_agent_terms(game.guild, fighter)
        self.assertEqual((quote['wage'], quote['fee']), (174, 870))
        current = game.guild.fighters[0]
        current_wage = current.wage
        with patch.object(world.rng, 'random', return_value=0):
            self.assertTrue(world.new_contract(game.guild, fighter, 1, years=2))
        self.assertEqual(fighter.wage, quote['wage'])
        self.assertEqual(current.wage, current_wage)
        world.money.reconcile()

    def test_ai_reserves_payroll_for_existing_contracts(self):
        game = Campaign(23, interactive=True)
        world = game.world
        guild = next(g for g in world.guilds.values() if g.tier==1)
        expiring = next(f for f in guild.fighters if f.age<33)
        existing = next(f for f in guild.fighters if f is not expiring and f.age<33)
        for fighter in guild.fighters:
            fighter.contract_end = 3
        expiring.contract_end = 1
        remaining_payroll = guild.wage_total()-expiring.wage
        budget_for = economy.ai_payroll_budget
        with patch.object(economy, 'ai_payroll_budget', side_effect=lambda w,g:
                remaining_payroll if g is guild else budget_for(w,g)):
            economy.annual_rollover(world, 1, interactive=True)
        self.assertNotIn(expiring, guild.fighters)
        self.assertIn(existing, guild.fighters)
        self.assertGreater(world.stats['renewal_budget_release'], 0)
        economy.assert_world(world)

    def test_losing_territory_reduces_ai_contract_budget(self):
        game = Campaign(23)
        world = game.world
        guild = next(g for g in world.guilds.values() if g.tier==1 and
                     sum(z.owner==g.gid for z in world.zones)>=2)
        owned_budget = economy.ai_payroll_budget(world, guild)
        for zone in world.zones:
            if zone.owner == guild.gid:
                zone.owner = None
        self.assertLess(economy.ai_payroll_budget(world, guild), owned_budget)
