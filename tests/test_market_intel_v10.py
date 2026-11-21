"""v10 market scouting: separate CA/observed PA, all eight abilities, 8v8 swaps."""
import copy
import json
import unittest

from campaign import Campaign
from moonpa_growth import ATTRIBUTES, observed_potential
from moonpa_savegame import create_save, load_save
import moonpa_market_intel as intel
import moonpa_notables as notables
import moonpa_prebattle as tactics
import moonpa_economy_v15_1 as economy
import pages_bridge


class MarketIntelV10Tests(unittest.TestCase):
    def setUp(self):
        self.g=Campaign(23,interactive=True)
        self.g.phase='ready'

    def test_snapshot_complete_attributes_role_rarity_and_observed_potential(self):
        g=self.g
        m=g.free_agents()
        self.assertEqual(m['roster_count'],len(g.guild.fighters))
        self.assertEqual(m['normal_roster_limit'],economy.MAX_ROSTER)
        self.assertEqual(m['roster_limit'],economy.MAX_TEMP_ROSTER)
        self.assertEqual(list(m['attribute_labels']),list(ATTRIBUTES))
        self.assertGreater(len(m['candidates']),0)
        by_id={x.fid:x for x in g.world.fa}
        mismatches=0
        for card in m['candidates']:
            f=by_id[card['id']]
            self.assertEqual(card['role_id'],f.role)
            self.assertEqual(card['attrs'],tactics.stats(f))
            self.assertEqual(set(card['attrs']),set(ATTRIBUTES))
            self.assertEqual(card['rarity'],'normal' if not card['notable'] else card['notable']['rarity'])
            self.assertEqual(card['pa'],round(observed_potential(f),1))
            self.assertEqual(card['growth_gap'],round(max(0,card['pa']-card['ca']),1))
            self.assertTrue(card['skills'])
            self.assertTrue(card['tags'])
            self.assertIn('captain_ability',card)
            self.assertIn('deputy_ability',card)
            mismatches+=(card['pa']!=round(f.pa,1))
        self.assertGreater(mismatches,0,'observed PA should not always reveal real potential')

    def test_snapshot_and_comparison_are_readonly(self):
        g=self.g
        w=g.world
        before=(w.rng.getstate(),w.money.transactions,g.guild.cash,
                g.week,g.season,copy.deepcopy(w.prebattle_plans),len(w.fa),
                {f.fid:f.ca for f in g.guild.fighters})
        market=g.free_agents()
        ids=[x['id'] for x in market['candidates'][:3]]
        for _ in range(3):
            res=g.market_compare(ids)
            self.assertEqual(len(res['comparisons']),3)
            self.assertEqual(len(res['team']['members']),8)
            self.assertIn('승률',res['disclaimer'])
        self.assertEqual(before,(w.rng.getstate(),w.money.transactions,
            g.guild.cash,g.week,g.season,w.prebattle_plans,len(w.fa),
            {f.fid:f.ca for f in g.guild.fighters}))
        w.money.reconcile()

    def test_simulated_swaps_match_exact_prebattle_diagnosis(self):
        g=self.g
        m=g.free_agents()
        c=m['candidates'][0]
        base=m['team']
        self.assertEqual(len(base['members']),8)
        replacement=base['members'][2]
        result=g.market_compare([c['id']],replacement['id'])
        value=result['comparisons'][0]
        self.assertEqual(value['replacement']['id'],replacement['id'])
        self.assertEqual(value['baseline'],base['diagnosis'])
        rows=[{'id':c['id'] if x['id']==replacement['id'] else x['id'],
               'row':x['row']} for x in base['members']]
        own=tactics._public_roster(g)
        fake=tactics.fighter_card(next(x for x in g.world.fa if x.fid==c['id']))
        expected=tactics.diagnose([*own,fake],rows)
        self.assertEqual(value['after'],expected)
        for key in intel.METRICS:
            self.assertEqual(value['delta'][key],expected[key]-base['diagnosis'][key])
        self.assertEqual(value['replaced_ca'],replacement['ca'])
        self.assertEqual(value['replaced_pa'],round(next(f for f in g.guild.fighters if f.fid==replacement['id']).pa,1))

    def test_market_team_uses_saved_eight_without_modifying_saved_plan(self):
        g=self.g
        v=tactics.view(g,'attack')
        data={key:v['plan'][key] for key in ('formation','captain','deputy')}
        tactics.save(g,'attack',v['zone_id'],data)
        saved=copy.deepcopy(g.world.prebattle_plans)
        m=g.free_agents()
        self.assertEqual(m['team']['source'],'저장된 점령전 편성')
        self.assertEqual([f['id'] for f in m['team']['members']],
                         [f['id'] for f in data['formation']])
        g.market_compare([m['candidates'][0]['id']])
        self.assertEqual(saved,g.world.prebattle_plans)

    def test_malformed_comparisons_rejected_before_mutation(self):
        g=self.g
        fid=g.free_agents()['candidates'][0]['id']
        cases=[([],None),([fid]*2,None),([fid]*4,None),(['x'],None),
               ([True],None),([fid],False),([fid],-99999),([999999],None)]
        world_before=copy.deepcopy(g.world.prebattle_plans)
        for ids,member in cases:
            with self.subTest(ids=ids,member=member),self.assertRaises(ValueError):
                g.market_compare(ids,member)
            self.assertEqual(g.world.prebattle_plans,world_before)

    def test_no_eight_available_returns_explicit_incomplete_warning(self):
        g=self.g
        for f in g.guild.fighters[7:]:
            f.injured=2
        m=g.free_agents()
        self.assertEqual(m['team']['members'],[])
        self.assertIn('미완료',m['team']['note'])
        info=g.market_compare([m['candidates'][0]['id']])['comparisons'][0]
        self.assertIsNone(info['delta'])
        self.assertIsNone(info['replacement'])

    def test_roster_role_gap_is_based_on_playing_eight_not_full_roster(self):
        g=self.g
        m=g.free_agents()
        team=m['team']
        healers=sum(f['role_id']==4 for f in team['members'])
        self.assertEqual(team['role_counts']['4'],healers)
        self.assertEqual(team['role_needs']['4'],5 if healers==0 else 2 if healers==1 else 0)
        self.assertIn('승률이 아닙니다',team['note'])

    def test_named_alert_only_refers_to_actual_market_not_roster(self):
        g=self.g
        f=next(x for x in g.world.fa if x.age<=42)
        notables.attach(g.world,f,notables.ROLE_NAMED[f.role],rarity='named')
        state=g.overview()
        names={x['id']:x for x in state['market_notables']}
        self.assertIn(f.fid,names)
        self.assertEqual(names[f.fid]['rarity'],'named')
        matching=next(x for x in g.free_agents()['candidates'] if x['id']==f.fid)
        self.assertEqual(matching['rarity'],'named')
        roster_ids={x.fid for x in g.guild.fighters}
        self.assertTrue(set(names).isdisjoint(roster_ids))

    def test_prebattle_old_save_roundtrip_and_new_market_fields_not_persisted(self):
        g=self.g
        before=create_save(g)
        snap=g.free_agents()
        comparison=g.market_compare([snap['candidates'][0]['id']])
        after=create_save(g)
        self.assertEqual(before,after)
        revived=load_save(after)
        self.assertEqual(revived.free_agents()['team'],snap['team'])
        self.assertEqual(revived.market_compare([snap['candidates'][0]['id']])['team'],comparison['team'])

    def test_market_bridge_uses_same_readonly_quote_and_no_autosave(self):
        original=pages_bridge.game
        g=self.g
        before=(g.world.rng.getstate(),g.guild.cash)
        try:
            pages_bridge.game=g
            market=json.loads(pages_bridge.handle('free_agents','{}'))
            ids=[x['id'] for x in market['candidates'][:3]]
            response=json.loads(pages_bridge.handle('market_compare',json.dumps(
                {'ids':ids,'replace_id':None})))
            self.assertEqual(len(response['comparisons']),3)
            self.assertEqual(market['team']['source'],response['team']['source'])
        finally:
            pages_bridge.game=original
        self.assertEqual(before,(g.world.rng.getstate(),g.guild.cash))


if __name__=='__main__':
    unittest.main()
