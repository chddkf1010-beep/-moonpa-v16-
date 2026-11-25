import unittest
from campaign import Campaign
from moonpa_savegame import create_save, load_save

class CombatConfig(unittest.TestCase):
    def test_new_battle_configuration_version_and_old_save(self):
        c=Campaign(23)
        own=c.guild.fighters[:8]
        other=next(g for g in c.world.guilds.values() if g is not c.guild and len(g.fighters)>=8)
        config=c.group_config('territory',own,other,assault=other.fighters[:8])
        self.assertEqual(config['combatRules'],2)
        self.assertIn('enemyTactic',config)
        self.assertTrue(all('notable' in f for f in config['team']))
        restored=load_save(create_save(c))
        self.assertEqual(restored.group_config('territory',restored.guild.fighters[:8],
            restored.world.guilds[other.gid],assault=restored.world.guilds[other.gid].fighters[:8]),config)

if __name__=='__main__':unittest.main()
