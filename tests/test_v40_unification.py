"""Web baseline preservation and retirement of live mission content."""
import unittest
from campaign import Campaign
import moonpa_economy_v15_1 as economy
from moonpa_savegame import create_save, load_save

class V40Unification(unittest.TestCase):
    def test_identity_and_old_save_roundtrip(self):
        game=Campaign(23)
        before=[(f.fid,f.name,f.portrait_key) for f in game.guild.fighters]
        restored=load_save(create_save(game))
        self.assertEqual(before,[(f.fid,f.name,f.portrait_key) for f in restored.guild.fighters])
        self.assertTrue(all(name and not name.startswith('문파원 ') for _,name,_ in before))
        self.assertEqual(restored.world.notables,game.world.notables)
        self.assertFalse(restored.overview()['missions_enabled'])
        self.assertEqual(restored.overview()['mission_board'],[])

    def test_new_mission_rejected_without_cash_or_clock_change(self):
        game=Campaign(23)
        before=(game.week,game.guild.cash,game.world.money.transactions)
        for key,value in [('missions',[[1,2,3]]),('mission_orders',[{}]),('long_orders',[{}]),('long_actions',[{}]),('elite_order',{'id':'old'})]:
            with self.assertRaises(ValueError):
                game.submit_week(1,1,{key:value})
            self.assertEqual(before,(game.week,game.guild.cash,game.world.money.transactions))

    def test_live_ai_and_actual_ledger(self):
        game=Campaign(23)
        world=game.world
        world.season_active=1
        for guild in world.guilds.values():
            plan=economy.prep_plan(world,guild,1)
            self.assertEqual(plan['missions'],[])
            self.assertEqual(plan['emergency'],[])
            self.assertEqual(plan['long_orders'],[])
            self.assertIsNone(plan['elite_order'])
        before=dict(world.money.categories)
        expected=sum(economy.BASIC_OPERATING_INCOME[g.tier] for g in world.guilds.values())
        game.submit_week(1,1,{})
        self.assertEqual(game.week,2)
        self.assertEqual(world.money.categories['basic_operating_income']-before.get('basic_operating_income',0),expected)
        for key in ('mission_gross_reward','mission_preparation','expedition_preparation','expedition_upkeep','expedition_reward','elite_preparation','elite_reward','errand_income','no_territory_livelihood'):
            self.assertEqual(world.money.categories[key],before.get(key,0),key)
        self.assertEqual(game.week_report['income']-game.week_report['expenses'],game.week_report['cash_change'])

if __name__=='__main__':
    unittest.main()
