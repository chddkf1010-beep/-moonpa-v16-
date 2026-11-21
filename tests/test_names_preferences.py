"""Regression tests for deterministic names and concealed sect preferences.

Run from the repository root:
    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

import moonpa_world_v15 as old
import moonpa_economy_v15_1 as economy
import moonpa_market as market
from moonpa_names import GUILD_NAMES, NameRegistry, preference_multiplier
from campaign import Campaign


class NamingTests(unittest.TestCase):
    def test_named_leagues_and_initial_rosters(self):
        world = economy.World15(2345, "baseline")
        self.assertEqual(len(world.guilds), 32)
        names = [guild.name for guild in world.guilds.values()]
        self.assertEqual(len(set(names)), 32)
        for tier in (1, 2, 3, 4):
            matching = [g for g in world.guilds.values() if g.tier == tier]
            self.assertEqual(len(matching), 8)
            self.assertEqual({g.name for g in matching}, set(GUILD_NAMES[tier]))
        namgung = next(g for g in world.guilds.values() if g.name == "남궁세가")
        self.assertGreaterEqual(sum(f.surname == "남궁" for f in namgung.fighters),
                                (len(namgung.fighters) * 7 + 9) // 10)
        hwasan = next(g for g in world.guilds.values() if g.name == "화산파")
        self.assertGreaterEqual(sum("매" in f.given_name for f in hwasan.fighters), 4)
        jongnam = next(g for g in world.guilds.values() if g.name == "종남파")
        self.assertGreaterEqual(sum(f.role == 1 for f in jongnam.fighters), len(jongnam.fighters) // 3)
        for g in world.guilds.values():
            for fighter in g.fighters:
                self.assertEqual(fighter.name, fighter.surname + fighter.given_name)
                self.assertEqual(len(fighter.given_name), 2)
                self.assertIn(len(fighter.surname), (1, 2))

    def test_all_names_unique_and_same_seed_reproducible(self):
        worlds = [economy.World15(8382, "baseline") for _ in range(2)]
        for w in worlds:
            old.generate_rookies(w, 1)
        def snapshot(w):
            return (
                [(g.gid, g.name) for g in w.guilds.values()],
                [(f.fid, f.surname, f.given_name, f.role)
                 for g in w.guilds.values() for f in g.fighters],
                [(f.fid, f.surname, f.given_name) for f in w.fa],
            )
        self.assertEqual(snapshot(worlds[0]), snapshot(worlds[1]))
        people = [f.name for g in worlds[0].guilds.values() for f in g.fighters]
        people += [f.name for f in worlds[0].fa]
        self.assertEqual(len(people), len(set(people)))

    def test_player_replaces_exactly_one_4th_tier_sect(self):
        w = economy.World15(110, "baseline")
        guild = economy.install_player(w, "balanced")
        self.assertEqual(guild.name, "신생문파")
        self.assertEqual(guild.tier, 4)
        self.assertEqual(len(guild.fighters), 20)
        self.assertEqual(len(w.guilds), 32)
        self.assertEqual(sum(g.tier == 4 for g in w.guilds.values()), 8)
        self.assertEqual(sum(z.owner == guild.gid for z in w.zones), 1)
        self.assertEqual(len({f.name for g in w.guilds.values() for f in g.fighters}),
                         sum(len(g.fighters) for g in w.guilds.values()))
        self.assertNotIn(guild.name, [g.name for g in w.guilds.values() if g is not guild])

    def test_transfer_never_renames_person(self):
        w = economy.World15(77, "balanced")
        seller, buyer = list(w.guilds.values())[:2]
        person = seller.fighters[0]
        identity = (person.fid, person.name, person.surname, person.given_name)
        self.assertTrue(w.trade(seller, buyer, person, 0, [], season=1))
        self.assertIn(person, buyer.fighters)
        self.assertNotIn(person, seller.fighters)
        self.assertEqual((person.fid, person.name, person.surname, person.given_name), identity)
        self.assertFalse(w.trade(buyer, seller, person, 0, [], season=1))

    def test_battle_units_keep_full_character_names(self):
        c = Campaign(seed=48)
        data = c.overview()
        selected = [f for f in data["roster"] if f["recommended"] and not f["injured"]][:5]
        self.assertEqual(len(selected), 5)
        zone = next(z for z in data["zones"] if z["selectable"])
        setup = [dict(id=f["id"], row="front" if index < 2 else "back",
                      skills=f["skills"][:f["slots"]])
                 for index, f in enumerate(selected)]
        c.start(zone["id"], setup, practice=True)
        battle = c.battle_state()
        allied_names = {u["name"] for u in battle["units"] if u["side"] == 0}
        self.assertEqual(allied_names, {f["name"] for f in selected})
        self.assertTrue(all("#" not in u["name"] for u in battle["units"] if u["side"] == 0))

    def test_new_sects_do_not_reuse_initial_names(self):
        a, b = NameRegistry(123), NameRegistry(123)
        for registry in (a, b):
            for names in GUILD_NAMES.values():
                for sect in names:
                    registry.reserve_sect(sect)
        replacements_a = [a.new_sect() for _ in range(40)]
        replacements_b = [b.new_sect() for _ in range(40)]
        self.assertEqual(replacements_a, replacements_b)
        self.assertEqual(len(set(replacements_a)), 40)
        self.assertFalse(set(replacements_a) & {n for names in GUILD_NAMES.values() for n in names})

    def test_campaign_names_are_exposed_without_bias_metadata(self):
        c = Campaign(seed=22)
        state = c.overview()
        self.assertEqual(state["guild_name"], c.guild.name)
        self.assertTrue(all(f["name"] and f["surname"] and f["given_name"] for f in state["roster"]))
        self.assertTrue(all(z["owner_name"] for z in state["zones"]))
        self.assertNotIn("recruitment_preference", state)
        self.assertNotIn("preference_multiplier", str(state))


class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.w = economy.World15(88, "baseline")

    def guild(self, sect):
        return next(g for g in self.w.guilds.values() if g.name == sect)

    def pair(self, sect):
        """Near-identical candidates; lower fid is the ordinary tie winner."""
        plain = self.w._make_fighter(133, 159, 10, 23, 5, 4)
        favored = self.w._make_fighter(133, 159, 10, 23, 5, 4)
        plain.surname, plain.given_name = "김", "서린"
        favored.surname, favored.given_name = "김", "서린"
        if sect == "남궁세가":
            favored.surname = "남궁"
        elif sect == "화산파":
            favored.given_name = "매린"
            plain.surname = "매"
        elif sect == "종남파":
            # Assassin and warrior have the same basic salary treatment.
            favored.role = 1
            plain.role = 5
            guild = self.guild(sect)
            guild.fighters = [f for f in guild.fighters if f.role != 1]
        plain.wage = favored.wage
        plain.development.observed_pa_grade = favored.development.observed_pa_grade = 3
        plain.development.observed_ca_grade = favored.development.observed_ca_grade = 3
        return plain, favored

    def test_all_three_prefer_matching_fa_candidate(self):
        for sect in ("남궁세가", "화산파", "종남파"):
            with self.subTest(sect=sect):
                guild = self.guild(sect)
                plain, favored = self.pair(sect)
                self.w.fa = [plain, favored]
                self.assertGreater(preference_multiplier(guild, favored), preference_multiplier(guild, plain))
                self.assertIs(economy.select_offer(guild, self.w)[0], favored)

    def test_all_three_scout_similar_candidates_in_preferred_order(self):
        for sect in ("남궁세가", "화산파", "종남파"):
            with self.subTest(sect=sect):
                w = economy.World15(881, "baseline")
                buyer = next(g for g in w.guilds.values() if g.name == sect)
                seller = next(g for g in w.guilds.values() if g.name != sect and g.tier == buyer.tier)
                # Ensure enough retained players for the seller to be eligible.
                cheap = [w._make_fighter(30, 37, 1, 20, 2, 5) for _ in range(15)]
                standard = w._make_fighter(170, 180, 12, 22, 5, 5)
                preferred = w._make_fighter(170, 180, 12, 22, 5, 5)
                standard.surname, standard.given_name = "김", "서린"
                preferred.surname, preferred.given_name = "김", "서린"
                if sect == "남궁세가":
                    preferred.surname = "남궁"
                elif sect == "화산파":
                    preferred.given_name = "매린"
                    standard.surname = "매"
                else:
                    buyer.fighters = [f for f in buyer.fighters if f.role != 1]
                    preferred.role = 1
                standard.wage = preferred.wage
                standard.development.observed_pa_grade = preferred.development.observed_pa_grade = 4
                standard.development.observed_ca_grade = preferred.development.observed_ca_grade = 4
                seller.fighters = cheap + [standard, preferred]
                w.guilds = {buyer.gid: buyer, seller.gid: seller}
                inspected = []
                def fake_negotiate(world, source, target_guild, fighter, season, **_kwargs):
                    inspected.append(fighter)
                    return None
                with patch.object(economy.market, "negotiate", side_effect=fake_negotiate):
                    economy.buy_from_world(w, buyer, 1)
                self.assertTrue(inspected)
                self.assertIs(inspected[0], preferred)

    def test_bids_obey_funds_and_transfer_ban(self):
        w = self.w
        buyer = self.guild("남궁세가")
        seller = self.guild("화산파")
        target = seller.fighters[-1]
        target.surname = "남궁"
        self.assertGreater(preference_multiplier(buyer, target), 1)
        self.assertFalse(w.trade(seller, buyer, target, buyer.cash + 1, [], 1))
        target.last_transfer_season = 1
        self.assertIsNone(market.requirement(w, seller, target, 1))


if __name__ == "__main__":
    unittest.main()
