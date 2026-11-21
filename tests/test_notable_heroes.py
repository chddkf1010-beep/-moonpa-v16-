"""Named/legendary conditional passive combat and persistent rarity regression."""
import unittest
from random import Random

from campaign import Campaign
from combat import Battle, Unit
import moonpa_notable_combat as powers
import moonpa_notables as heroes
from moonpa_savegame import create_save, load_save


def unit(fid, side, role, row='front', hp=None):
    x=Unit(fid,side,role,str(fid),row,[95]*8,10,('strike',) if role==1 else ('heal',) if role==4 else ('wall',) if role==0 else ('fang',))
    if hp is not None:
        x.hp=hp
    return x


def duel_context(talent_map):
    return {'notables':{str(fid):dict(key=skill,rarity='named') for fid,skill in talent_map.items()}}


class NamedHeroTests(unittest.TestCase):
    def make_battle(self,talents):
        units=[unit(1,0,1),unit(2,0,0),unit(3,0,4,'back'),
               unit(4,1,0),unit(5,1,1),unit(6,1,4,'back')]
        return Battle(units,99,context=duel_context(talents))

    def test_jang_cheonho_is_exact_threshold_not_gradual(self):
        low=self.make_battle({4:'jang_cheonho'})
        high=self.make_battle({})
        for battle in (low,high):
            b=battle.units[4]
            b.hp=b.max_hp//2
        attacker=low.units[1]
        self.assertEqual(powers.received_multiplier(low,low.units[4]),.70)
        self.assertEqual(powers.received_multiplier(high,high.units[4]),1.)
        low.damage(attacker,low.units[4],1,Random(123),'hit')
        high.damage(high.units[1],high.units[4],1,Random(123),'hit')
        self.assertLess(low.units[4].hit_taken,high.units[4].hit_taken)
        low.units[4].hp=low.units[4].max_hp//2+1
        self.assertEqual(powers.received_multiplier(low,low.units[4]),1.)

    def test_namgung_stack_only_on_warrior_kill_not_hit(self):
        battle=self.make_battle({1:'namgung_seol'})
        attacker=battle.units[1]
        victim=battle.units[4]
        powers.hit(battle,attacker,victim)
        self.assertEqual(powers.state(battle).get('namgung_stacks',{}),{})
        battle.apply_damage(attacker,victim,victim.hp,'hit','damage')
        self.assertEqual(powers.state(battle)['namgung_stacks']['0'],1)
        self.assertAlmostEqual(powers.dealt_multiplier(battle,attacker,battle.units[5]),1.01)
        battle.apply_damage(battle.units[2],battle.units[5],battle.units[5].hp,'hit','damage')
        self.assertEqual(powers.state(battle)['namgung_stacks']['0'],1)

    def test_baek_seals_active_skills_five_rounds_and_respects_cooldown(self):
        battle=self.make_battle({1:'baek_mujin'})
        mage=battle.units[1]
        mage.role=3
        target=battle.units[5]
        powers.hit(battle,mage,target)
        self.assertTrue(battle.active(target,'notable_seal'))
        self.assertEqual(battle.targets(target,'strike'),[])
        self.assertTrue(battle.targets(target,'hit'))
        battle.round=6
        self.assertFalse(battle.active(target,'notable_seal'))
        powers.hit(battle,mage,target)
        self.assertFalse(battle.active(target,'notable_seal'))
        battle.round=21
        powers.hit(battle,mage,target)
        self.assertTrue(battle.active(target,'notable_seal'))

    def test_dokgo_dot_is_one_percent_hp_each_round_not_stacking(self):
        battle=self.make_battle({1:'dokgo_jin'})
        attacker=battle.units[1]
        target=battle.units[4]
        attacker.role=5
        powers.hit(battle,attacker,target)
        powers.hit(battle,attacker,target)
        self.assertEqual(len(powers.state(battle)['dots']),1)
        before=target.hp
        battle.round=2
        powers.end_round(battle)
        self.assertEqual(before-target.hp,(target.max_hp+99)//100)

    def test_zhuge_requires_protect_and_buff_ends_with_protection(self):
        battle=self.make_battle({3:'zhuge_hyeon'})
        protected=battle.units[1]
        self.assertEqual(powers.dealt_multiplier(battle,protected,battle.units[4]),1)
        battle.effect(protected,'ward',2,3)
        self.assertTrue(battle.active(protected,'zhuge_power'))
        self.assertAlmostEqual(powers.dealt_multiplier(battle,protected,battle.units[4]),1.1)
        battle.round=3
        self.assertAlmostEqual(powers.dealt_multiplier(battle,protected,battle.units[4]),1.0)


class LegendaryTests(unittest.TestCase):
    def test_dokgo_mugeuk_requires_three_distinct_warriors_ten_hits(self):
        units=[unit(i,0,1) for i in (1,2,3)]
        units += [unit(i,1,0) for i in (4,5,6)]
        battle=Battle(units,10,context=duel_context({1:'dokgo_mugeuk'}))
        for i in range(9):
            powers.hit(battle,battle.units[(i%3)+1],battle.units[4])
        self.assertFalse(powers.piercing(battle,battle.units[1],battle.units[4]))
        powers.hit(battle,battle.units[1],battle.units[4])
        self.assertTrue(powers.piercing(battle,battle.units[1],battle.units[4]))

    def test_hwangbo_redirects_backline_attack_after_two_low_frontliners(self):
        battle=Battle([unit(1,0,0),unit(2,0,1),unit(3,0,4,'back'),
                       unit(4,1,1),unit(5,1,0),unit(6,1,4,'back')],77,
                      context=duel_context({1:'hwangbo_jinak'}))
        for id in (1,2):
            v=battle.units[id]
            v.hp=int(v.max_hp*.30)
        powers.hp_changed(battle)
        self.assertTrue(battle.active(battle.units[1],'legend_redirect'))
        before=battle.units[1].hp
        damage=powers.split(battle,battle.units[4],battle.units[3],100)
        self.assertEqual(damage,70)
        self.assertEqual(before-battle.units[1].hp,30)

    def test_seomun_biyeon_requires_three_archers(self):
        battle=Battle([unit(i,0,2,'back') for i in (1,2,3)]
                      +[unit(i,1,0) for i in (4,5,6)],10,
                      context=duel_context({1:'seomun_biyeon'}))
        powers.hit(battle,battle.units[1],battle.units[4])
        powers.hit(battle,battle.units[1],battle.units[4])
        powers.hit(battle,battle.units[2],battle.units[4])
        self.assertEqual(powers.state(battle).get('marks',{}),{})
        powers.hit(battle,battle.units[3],battle.units[4])
        self.assertEqual(powers.state(battle)['marks']['4'],0)
        self.assertAlmostEqual(powers.dealt_multiplier(battle,battle.units[2],battle.units[4]),1.12)

    def test_growth_legend_preserves_original_name_and_is_singular(self):
        campaign=Campaign(37)
        fighter=campaign.guild.fighters[0]
        identity=fighter.name
        fighter.lv=10
        for _ in range(11):
            self.assertIsNone(heroes.record_battle(campaign.world,fighter,True,2))
        awakened=heroes.record_battle(campaign.world,fighter,True,2)
        self.assertIsNotNone(awakened)
        self.assertEqual(awakened['rarity'],'legend')
        self.assertEqual(fighter.name,identity)
        self.assertFalse(awakened['original'])
        self.assertIsNone(heroes.record_battle(campaign.world,fighter,True,3))

    def test_no_economy_rng_drift_or_renaming_of_founders_and_save_roundtrip(self):
        a,b=Campaign(16),Campaign(16)
        self.assertEqual([f.name for f in a.guild.fighters],
                         [f.name for f in b.guild.fighters])
        self.assertEqual(a.world.rng.getstate(),b.world.rng.getstate())
        self.assertEqual(a.world.notables,b.world.notables)
        self.assertGreaterEqual(sum(v['rarity']=='legend' for v in a.world.notables.values()),1)
        self.assertGreaterEqual(sum(v['rarity']=='named' for v in a.world.notables.values()),5)
        restored=load_save(create_save(a))
        self.assertEqual(a.world.notables,restored.world.notables)
        self.assertEqual(a.overview(),restored.overview())

    def test_battle_save_replays_with_talent_cooldowns(self):
        game=Campaign(16)
        person=game.guild.fighters[0]
        self.assertTrue(heroes.attach(game.world,person,'jang_cheonho'))
        view=game.overview()
        setup=[dict(id=f['id'],row='front' if i<2 else 'back',
                    skills=list(f['skills'][:f['slots']]))
               for i,f in enumerate(x for x in view['roster'] if x['recommended'])]
        zone=next(x for x in view['zones'] if x['selectable'])
        game.start(zone['id'],setup,practice=True)
        game.step()
        loaded=load_save(create_save(game))
        self.assertEqual(loaded.battle.context,game.battle.context)
        self.assertEqual(loaded.battle_state(),game.battle_state())
        game.step(finish=True)
        loaded.step(finish=True)
        self.assertEqual(game.battle_state(),loaded.battle_state())


if __name__=='__main__':
    unittest.main()
