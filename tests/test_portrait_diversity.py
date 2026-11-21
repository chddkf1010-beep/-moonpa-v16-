"""Regression coverage for persistent age/role-aware diverse wuxia faces.

The new artwork uses one small atlas. It does not change combat, recruitment,
name generation, world RNG, character IDs or existing save-file layouts.
"""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))

from campaign import Campaign
from moonpa_world_v15 import World
from moonpa_portraits import (
    DIVERSE_PORTRAITS, assign_diverse_portrait, portrait_asset,
    portrait_profile, FOUNDER_16,
)
from moonpa_savegame import create_save, load_save


class PortraitDiversityTests(unittest.TestCase):
    def test_original_sixteen_face_atlas_exists(self):
        art=(ROOT/'assets/portraits/diverse/atlas_v1.webp').read_bytes()
        self.assertEqual(len(DIVERSE_PORTRAITS),16)
        self.assertGreater(len(art),6000)
        self.assertEqual(art[:4],b'RIFF')
        self.assertEqual(art[8:12],b'WEBP')
        self.assertEqual(int.from_bytes(art[4:8],'little'),len(art)-8)

    def test_stable_role_and_age_appropriate_faces(self):
        w=World(1825,'balanced')
        portraits=[]
        for g in w.guilds.values():
            for f in g.fighters:
                if not f.portrait_key:
                    self.assertLess(f.age,24)
                    continue
                info=portrait_profile(f)
                self.assertIsNotNone(info)
                spec=DIVERSE_PORTRAITS[info['variant']]
                self.assertIn(f.role,spec['roles'])
                self.assertGreaterEqual(f.age,spec['min_age'])
                self.assertEqual(portrait_asset(f),
                                 f'assets/portraits/diverse/v1_{info["variant"]:02d}.webp')
                portraits.append(info['variant'])
        self.assertGreaterEqual(len(set(portraits)),13)
        self.assertTrue(any(DIVERSE_PORTRAITS[i]['build']=='통통한' for i in portraits))
        self.assertTrue(any(DIVERSE_PORTRAITS[i]['impression']=='날카로운' for i in portraits))

    def test_seed_determinism_and_no_extra_world_rng(self):
        a,b=World(1825,'balanced'),World(1825,'balanced')
        sample=lambda w:[(f.fid,f.name,f.role,f.portrait_key)
                          for g in w.guilds.values() for f in g.fighters]
        self.assertEqual(sample(a),sample(b))
        self.assertEqual(a.rng.getstate(),b.rng.getstate())
        target=a.guilds[0].fighters[0]
        initial=target.portrait_key
        rng=a.rng.getstate()
        self.assertFalse(assign_diverse_portrait(a.seed,target))
        self.assertEqual(target.portrait_key,initial)
        self.assertEqual(a.rng.getstate(),rng)

    def test_founders_keep_original_seed_16_faces(self):
        campaign=Campaign(16)
        self.assertEqual([(f.fid,f.name,f.role) for f in campaign.guild.fighters],
                         [(fid,*spec) for fid,spec in FOUNDER_16.items()])
        self.assertTrue(all(f.portrait_key==f'founders/seed16_{f.fid}.webp'
                            for f in campaign.guild.fighters))

    def test_other_seed_founder_faces_not_stolen_from_seed_16(self):
        campaign=Campaign(17)
        portraits=[f.portrait_key for f in campaign.guild.fighters]
        self.assertFalse(any(p.startswith('founders/') for p in portraits))
        self.assertTrue(any(p.startswith('diverse/v1_') for p in portraits))

    def test_transfer_and_aging_cannot_change_identity(self):
        w=World(124,'baseline')
        sender=w.guilds[0]
        receiver=w.guilds[1]
        fighter=next(f for f in sender.fighters if f.portrait_key)
        original=(fighter.fid,fighter.name,fighter.portrait_key,portrait_profile(fighter))
        sender.fighters.remove(fighter)
        receiver.fighters.append(fighter)
        fighter.age+=7
        self.assertFalse(assign_diverse_portrait(w.seed,fighter))
        self.assertEqual((fighter.fid,fighter.name,fighter.portrait_key,portrait_profile(fighter)),
                         original)

    def test_save_compatibility_and_old_blank_key_unchanged(self):
        game=Campaign(21)
        target=game.guild.fighters[0]
        target.portrait_key=''   # An older save's role-based portrait.
        restored=load_save(create_save(game))
        same=next(f for f in restored.guild.fighters if f.fid==target.fid)
        self.assertEqual(same.portrait_key,'')
        newcomer=restored.world._make_fighter(
            ca=75,pa=120,lv=1,age=31,role=0,contract_end=2)
        self.assertTrue(newcomer.portrait_key.startswith('diverse/'))
        self.assertIsNotNone(portrait_profile(newcomer))

    def test_appearance_has_no_combat_stats(self):
        w=World(78,'balanced')
        f=next(f for g in w.guilds.values() for f in g.fighters if f.portrait_key)
        old=(f.ca,f.pa,f.lv,f.wage,f.role,f.injured)
        self.assertIsNotNone(portrait_profile(f))
        self.assertEqual((f.ca,f.pa,f.lv,f.wage,f.role,f.injured),old)


if __name__=='__main__':
    unittest.main()
