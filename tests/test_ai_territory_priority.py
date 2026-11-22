import unittest
from unittest.mock import patch

from campaign import Campaign, group_fighters
import moonpa_economy_v15_1 as economy
from moonpa_world_v15 import Zone, zone_value


class AITerritoryPriorityTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23,interactive=True)
        self.world=self.game.world
        self.world.season_active=1
        self.guild=next(g for g in self.world.guilds.values() if g.tier==4 and g is not self.game.guild)

    def test_ai_prefers_real_income_and_does_not_replace_with_a_worse_site(self):
        guild,w=self.guild,self.world
        team=guild.fighters[:5]
        home=Zone(0,4,guild.gid,.85)
        weaker=Zone(1,4,None,.72)
        high=Zone(2,4,None,1.64)
        self.assertIs(economy.economic_attack_target(w,guild,[home],[weaker,high],team),high)
        second=Zone(3,4,guild.gid,1.52)
        self.assertIsNone(economy.economic_attack_target(w,guild,[home,second],[weaker],team))
        self.assertIs(economy.economic_attack_target(w,guild,[home,second],[high],team),high)

    def test_attack_and_defense_can_be_staffed_together_while_a_party_is_away(self):
        guild,w=self.guild,self.world
        for zone in w.zones:
            if zone.owner==guild.gid:zone.owner=None
        owned=min((z for z in w.zones if z.tier==4 and z.owner is None),key=zone_value)
        owned.owner=guild.gid
        away={f.fid for f in group_fighters(w,guild,3)}
        actual_away=w.away
        with patch.object(w,'away',side_effect=lambda gid:away if gid==guild.gid else actual_away(gid)), \
             patch.object(w.rng,'random',return_value=0):
            plan=economy.prep_plan(w,guild,1)
        attackers={f.fid for f in plan['attack']}
        defenders={f.fid for f in plan['defend']}
        self.assertEqual((len(attackers),len(defenders)),(5,5))
        self.assertTrue(attackers.isdisjoint(defenders|away))
        self.assertTrue(defenders.isdisjoint(away))
        self.assertEqual(plan['home'],owned.zid)
        self.assertGreater(zone_value(w.zones[plan['attack_target']]),zone_value(owned))

    def test_roster_total_average_and_top_five_are_separate_public_stats(self):
        guild=self.guild
        profile=self.game.sect_profile(guild.gid)
        self.assertEqual(profile['roster_power'],round(sum(f.ca for f in guild.fighters)/len(guild.fighters),1))
        self.assertEqual(profile['strength'],round(guild.strength(),1))
        self.assertEqual(profile['ca_min'],round(min(f.ca for f in guild.fighters),1))
        self.assertEqual(profile['ca_max'],round(max(f.ca for f in guild.fighters),1))
