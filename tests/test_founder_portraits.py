"""Portrait identity stability in the playable campaign (not only the naming RNG)."""
import unittest
import sys
import json
import hashlib
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from campaign import Campaign
from moonpa_portraits import FOUNDER_16


class FounderPortraitTests(unittest.TestCase):
    def test_deployed_sprite_atlas_matches_manifest(self):
        root=Path(__file__).resolve().parents[1]
        atlas=root/'assets/portraits/founders/founder_atlas.webp'
        data=atlas.read_bytes()
        self.assertEqual(data[:4],b'RIFF')
        self.assertEqual(data[8:12],b'WEBP')
        self.assertEqual(len(data),3112)
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         'c9463729f10941838f95960a18e357c637f64237b783836ff2d85259277ad6b0')
        manifest=json.loads((root/'assets/portraits/founder_manifest.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['seed'],16)
        self.assertEqual(len(manifest['characters']),20)
        for fid,(name,role) in FOUNDER_16.items():
            row=manifest['characters'][str(fid)]
            self.assertEqual((row['name'],row['role_id'],row['atlas_index']), (name,role,fid-640))

    def test_default_founders_all_have_unique_portraits(self):
        c=Campaign(seed=16)
        self.assertEqual(len(c.guild.fighters),20)
        self.assertEqual({f.fid for f in c.guild.fighters},set(FOUNDER_16))
        assets=set()
        for fighter in c.guild.fighters:
            self.assertEqual((fighter.name,fighter.role),FOUNDER_16[fighter.fid])
            self.assertEqual(fighter.portrait_key,f'founders/seed16_{fighter.fid}.webp')
            assets.add(fighter.portrait_key)
        self.assertEqual(len(assets),20)

    def test_same_seed_has_same_name_and_portrait(self):
        def sample():
            c=Campaign(seed=16)
            return [(f.fid,f.name,f.role,f.portrait_key) for f in c.guild.fighters]
        self.assertEqual(sample(),sample())

    def test_other_seed_does_not_attach_wrong_face(self):
        c=Campaign(seed=17)
        self.assertFalse(any(f.portrait_key.startswith('founders/') for f in c.guild.fighters))
        self.assertTrue(any(f.portrait_key.startswith('diverse/v1_') for f in c.guild.fighters))

    def test_transfer_preserves_fighter_face_and_name(self):
        c=Campaign(seed=16)
        target=c.guild.fighters[0]
        ident=(target.fid,target.name,target.portrait_key)
        buyer=next(g for g in c.world.guilds.values() if g is not c.guild and g.tier==c.guild.tier)
        self.assertTrue(c.world.trade(c.guild,buyer,target,0,[],season=1))
        self.assertIn(target,buyer.fighters)
        self.assertEqual((target.fid,target.name,target.portrait_key),ident)

    def test_battle_state_exposes_correct_portrait(self):
        c=Campaign(seed=16)
        state=c.overview()
        self.assertTrue(all(f['portrait'].endswith(f"{f['id']}.webp") for f in state['roster']))
        fighters=[f for f in state['roster'] if f['recommended']][:5]
        self.assertEqual(len(fighters),5)
        zone=next(z for z in state['zones'] if z['selectable'])
        lineup=[{'id':f['id'], 'row':'front' if i<2 else 'back',
                 'skills':f['skills'][:f['slots']]} for i,f in enumerate(fighters)]
        c.start(zone['id'],lineup,practice=True)
        units=[u for u in c.battle_state()['units'] if u['side']==0]
        self.assertEqual({x['portrait'] for x in units},
                         {x['portrait'] for x in fighters})


if __name__=='__main__':
    unittest.main()
