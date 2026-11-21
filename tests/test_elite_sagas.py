"""Narrative saga, hidden martial-art and transfer regression checks."""
import random
import unittest

from campaign import Campaign, unlocked, equipment
from combat import Battle, Unit, SKILLS, ROLE_SKILLS, SECRET_SKILLS
import moonpa_elite as elite
import moonpa_sagas as saga
import moonpa_economy_v15_1 as economy


class SagaTests(unittest.TestCase):
    def setUp(self):
        self.game=Campaign(23)
        self.f=self.game.guild.fighters[0]
        self.fid=self.f.fid
        self.crew=self.game.guild.fighters[:3]

    def activate(self,line='starlight'):
        self.f.development.saga={
            'line':line,'status':'active','next_chapter':1,
            'started':saga.clock(1,1),'deadline':saga.clock(1,1)+12,
            'attempts':0,'setbacks':0,'ethos':0,
        }

    def board(self,week=2,guild=None):
        g=guild or self.game.guild
        base=elite.board(23,g.gid,1,week,g.tier,65,12)
        return saga.decorate_board(g,base,1,week)

    def outcome(self,status='success'):
        return dict(outcome=status,outcome_label=elite.RESULTS[status],
                    narrative='임무 결과를 확인했다.')

    def test_personal_origin_is_stable_and_unique_per_fighter(self):
        first=saga.profile(self.f,23)
        self.assertEqual(first,saga.profile(self.f,23))
        self.assertIn('origin',first)
        self.assertIn('history',first)
        self.assertIn('goal',first)
        self.assertEqual(saga.view(self.f,23,1,1)['elite_wins'],0)
        self.assertEqual(len(self.f.development.story_events),0)

    def test_continuation_is_pinned_without_mutating_existing_board(self):
        self.activate()
        old=elite.board(23,self.game.guild.gid,1,2,self.game.guild.tier,65,12)
        current=self.board()
        self.assertEqual(len(current),3)
        self.assertEqual(current,self.board())
        self.assertEqual(old,elite.board(23,self.game.guild.gid,1,2,self.game.guild.tier,65,12))
        self.assertEqual(current[0]['saga_leader'],self.fid)
        self.assertEqual(current[0]['saga_chapter'],2)
        self.assertTrue(current[0]['saga'])
        self.assertEqual(len({c['id'] for c in current}),3)

    def test_two_successes_unlock_one_real_seventh_skill(self):
        self.activate()
        first=self.board(2)[0]
        events=saga.advance(self.f,23,1,2,first,self.outcome(),'guard')
        self.assertTrue(any(e['kind']=='progress' for e in events))
        self.assertEqual(self.f.development.saga['next_chapter'],2)
        self.assertEqual(self.f.development.elite_wins,1)
        final=self.board(3)[0]
        self.assertEqual(final['saga_chapter'],3)
        events=saga.advance(self.f,23,1,3,final,self.outcome(),'study')
        self.assertEqual(len([e for e in events if e['kind']=='secret']),1)
        self.assertEqual(self.f.development.saga['status'],'completed')
        self.assertEqual(self.f.development.secret_arts,[SECRET_SKILLS[self.f.role]])
        self.assertEqual(len(ROLE_SKILLS[self.f.role]),6)
        self.f.lv=7
        self.assertIn(SECRET_SKILLS[self.f.role],unlocked(self.f))
        self.assertIn(SECRET_SKILLS[self.f.role],equipment(self.f))
        self.assertIn(SECRET_SKILLS[self.f.role],
                      [x['id'] for x in self.game.member_detail(self.fid)['skills']])
        self.game.equip(self.fid,[SECRET_SKILLS[self.f.role]])
        self.assertEqual(equipment(self.f),(SECRET_SKILLS[self.f.role],))
        self.assertTrue(saga.view(self.f,23,1,4)['secrets'])

    def test_failures_and_deadline_are_real(self):
        self.activate()
        offer=self.board()[0]
        for i in range(3):
            saga.advance(self.f,23,1,2+i,dict(offer),self.outcome('failure'),'seize')
        self.assertEqual(self.f.development.saga['status'],'expired')
        self.assertFalse(self.board(5)[0].get('saga'))
        self.activate()
        self.assertIsNone(saga.current_leader(self.game.guild,1,20))
        self.assertFalse(self.board(20)[0].get('saga'))
        self.assertEqual(saga.view(self.f,23,1,20)['saga']['status'],'expired')

    def test_story_survives_real_interguild_transfer(self):
        self.activate()
        seller=self.game.guild
        buyer=next(g for g in self.game.world.guilds.values()
                   if g.gid!=seller.gid and len(g.fighters)<economy.MAX_TEMP_ROSTER)
        self.assertTrue(self.game.world.trade(seller,buyer,self.f,0,[],1))
        self.assertNotIn(self.f,seller.fighters)
        self.assertIn(self.f,buyer.fighters)
        board=self.board(2,buyer)
        self.assertEqual(board[0]['saga_leader'],self.fid)
        self.assertEqual(board[0]['saga_chapter'],2)
        self.assertEqual(self.f.development.saga['line'],'starlight')

    def test_weekly_validation_requires_continuation_leader(self):
        self.activate()
        card=self.game.overview()['elite_board'][0]
        ids=[x.fid for x in self.crew]
        self.assertEqual(card['saga_leader'],self.fid)
        with self.assertRaisesRegex(ValueError,'핵심 인물'):
            self.game.submit_week(1,1,{'elite_order':
                {'id':card['id'],'members':ids[1:]+[self.game.guild.fighters[3].fid],
                 'lead':ids[1],'choice':'study'}})
        with self.assertRaisesRegex(ValueError,'핵심 인물'):
            self.game.submit_week(1,1,{'elite_order':
                {'id':card['id'],'members':ids,'lead':ids[1],'choice':'study'}})
        self.assertEqual(self.game.week,1)

    def test_campaign_week_resolves_story_and_reconciles(self):
        self.activate()
        card=self.game.overview()['elite_board'][0]
        self.game.submit_week(1,1,{'elite_order':
            {'id':card['id'],'members':[f.fid for f in self.crew],
             'lead':self.fid,'choice':'guard'}})
        report=self.game.week_report
        self.assertEqual(len(report['elite_missions']),1)
        result=report['elite_missions'][0]
        self.assertTrue(result['funded'])
        self.assertEqual(result['lead'],self.fid)
        self.assertIsInstance(result['story_events'],list)
        self.assertEqual(sum(e['amount'] for e in report['entries']),report['cash_change'])
        self.game.world.money.reconcile()


class MartialArtsCombatTests(unittest.TestCase):
    @staticmethod
    def battle(key):
        units=[]
        for i in range(10):
            units.append(Unit(i,0 if i<5 else 1,1,'검객'+str(i),
                'front' if i%5<2 else 'back',[120]*8,10,
                (key,) if i==0 else ('strike',)))
        return Battle(units,23)

    def test_secret_strike_actually_does_more_damage(self):
        base=self.battle('strike')
        secret=self.battle('secret_1')
        base.resolve(base.units[0],'strike',base.units[5],random.Random(41))
        secret.resolve(secret.units[0],'secret_1',secret.units[5],random.Random(41))
        self.assertLess(secret.units[5].hp,base.units[5].hp)
        self.assertGreater(SKILLS['secret_1'].power,SKILLS['strike'].power)

    def test_all_six_secret_arts_are_distinct_from_base_roster(self):
        self.assertEqual(len(SECRET_SKILLS),6)
        self.assertEqual(len(set(SECRET_SKILLS.values())),6)
        for role,skill in SECRET_SKILLS.items():
            self.assertNotIn(skill,ROLE_SKILLS[role])
            self.assertEqual(SKILLS[skill].level,7)
        base=self.battle('strike')
        self.assertNotIn('secret_1',base.options(base.units[0]))


if __name__=='__main__':
    unittest.main()
