"""The live map must expose real 120 sites and survive save/load without a new store."""
import collections
import unittest

from campaign import Campaign
from moonpa_savegame import create_save, load_save


class WorldMapTests(unittest.TestCase):
    def setUp(self):
        self.game = Campaign(23, interactive=True)

    def test_live_sites_and_all_32_sects(self):
        game = self.game
        view = game.overview()
        sites = view['world_map']
        self.assertEqual(len(sites), 120)
        self.assertEqual(dict(collections.Counter(s['tier'] for s in sites)),
                         {1: 42, 2: 34, 3: 26, 4: 18})
        self.assertEqual(len({site['id'] for site in sites}), 120)
        self.assertEqual(len({site['name'] for site in sites}), 120)
        sects = [sect for group in view['league']['groups'] for sect in group['members']]
        self.assertEqual(len(sects), 32)
        self.assertEqual(len({sect['id'] for sect in sects}), 32)
        self.assertEqual(len({sect['name'] for sect in sects}), 32)
        valid_owners = {sect['id'] for sect in sects}
        for zone in sites:
            self.assertIn(zone['owner'], valid_owners | {None})
            self.assertEqual(zone['name'], next(s['name'] for s in sites if s['id']==zone['id']))
            self.assertTrue(zone['site_grade'] in ('고수익', '중간급', '소규모'))
            self.assertLessEqual(abs(zone['value']-(zone['gross']-zone['upkeep'])), 1)
            if zone['owner'] is not None:
                self.assertEqual(zone['owner_name'], game.world.guilds[zone['owner']].name)

    def test_owner_change_and_restore_across_map_views(self):
        game = self.game
        site = next(z for z in game.world.zones if z.tier == game.guild.tier
                    and z.owner is not None and z.owner != game.guild.gid)
        original = game.overview()
        old_owner = site.owner
        self.assertEqual(original['world_map'][site.zid]['owner'], old_owner)

        # Losing a site changes the world; the map must read the new owner.
        site.owner = None
        updated = game.overview()
        self.assertIsNone(updated['world_map'][site.zid]['owner'])
        self.assertEqual(updated['world_map'][site.zid]['owner_name'], '수비대')

        # Switching the inspected league cannot modify ownership.
        for tier in (1, 2, 3, 4, 2, 4):
            _ = [z for z in updated['world_map'] if z['tier'] == tier]
        self.assertIsNone(game.world.zones[site.zid].owner)

        snapshot = create_save(game)
        loaded = load_save(snapshot)
        restored = loaded.overview()
        self.assertEqual(restored['world_map'], updated['world_map'])
        self.assertIsNone(loaded.world.zones[site.zid].owner)
        self.assertEqual(loaded.world.money.reconcile(), game.world.money.reconcile())

    def test_map_does_not_advance_rng_or_modify_income(self):
        game = self.game
        rng = game.world.rng.getstate()
        owners = [(zone.zid,zone.owner,zone.protected_until) for zone in game.world.zones]
        finance = game.world.money.reconcile()
        first = game.overview()['world_map']
        second = game.overview()['world_map']
        self.assertEqual(first, second)
        self.assertEqual(game.world.rng.getstate(),rng)
        self.assertEqual([(zone.zid,zone.owner,zone.protected_until) for zone in game.world.zones],owners)
        self.assertEqual(game.world.money.reconcile(), finance)


if __name__ == '__main__':
    unittest.main()
