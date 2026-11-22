"""Connect the tactical battle to an in-memory v15.1 campaign."""
from dataclasses import asdict
import json
import re
from types import SimpleNamespace

import moonpa_economy_v15_1 as economy
import moonpa_honors as honors
import moonpa_market as market
import moonpa_market_intel as market_intel
import moonpa_growth_dashboard as growth_dashboard
import moonpa_training_focus as training_focus
from moonpa_names import preference_multiplier
from moonpa_growth import available_skill_slots, WEIGHTS, ATTRIBUTES, observed_ability, observed_potential
import moonpa_missions as mission_content
import moonpa_long_missions as expedition_content
import moonpa_elite as elite_content
import moonpa_elite_play as playable_elite
import moonpa_sagas as saga_content
from combat import Battle, SKILLS, ROLE_SKILLS, SECRET_SKILLS, Unit
from moonpa_sites import site_details
from moonpa_month import MONTH_ENDS, month_number, summarize
from combat_environment import season_trend, zone_terrain, defending_style, combat_context, STYLES
import moonpa_notables as notables
from moonpa_portraits import portrait_asset, portrait_profile

_arena_resolver = None


def set_arena_resolver(resolver):
    global _arena_resolver
    _arena_resolver = resolver


FACILITIES = {'training': ('훈련소', 240, '1군·2군 훈련 성장 증가'),
              'estate': ('장원', 320, '주간 수입 증가 및 낭인 계약금 할인'),
              'medical': ('의료시설', 200, '부상 발생 확률 감소')}

MISSIONS = ('표국 호송', '산길 순찰', '약재 운송', '마을 경비')

ROLES = ('수호형', '무인형', '사수형', '주술형', '치유형', '암살형')


def facility_upgrade_cost(base, target_level):
    cost = base*target_level
    return cost*3//2 if target_level>=4 else cost


def unlocked(f):
    ordinary=tuple(key for key in ROLE_SKILLS[f.role] if f.lv >= SKILLS[key].level)
    secrets=tuple(key for key in f.development.secret_arts if key==SECRET_SKILLS[f.role]
                  and f.lv >= SKILLS[key].level)
    return ordinary+secrets


def equipment(f):
    if f.equipped is not None:
        return f.equipped
    slots=available_skill_slots(f.lv)
    ordinary=[key for key in ROLE_SKILLS[f.role] if f.lv>=SKILLS[key].level]
    secret=[key for key in unlocked(f) if key in f.development.secret_arts]
    return tuple((ordinary[:max(0,slots-len(secret))]+secret)[:slots])


def lineup(pool):
    ranked = sorted(pool, key=lambda f: (f.ca, -f.fid), reverse=True)
    selected = []
    for role in (0, 1, 4, 5, 3, 2):
        member = next((f for f in ranked if f.role == role and f not in selected), None)
        if member:
            selected.append(member)
    return (selected + [f for f in ranked if f not in selected])[:5]


def unit(f, side, row, loadout):
    attrs = f.development.attributes.copy()
    for t in f.development.traits:
        attrs[t.attribute] = min(200, attrs[t.attribute] + t.bonus)
    return Unit(f.fid, side, f.role, f.name, row, attrs, f.lv,
                tuple(loadout), skill_ranks=f.mastery.copy(), traits=tuple(t.attribute for t in f.development.traits if t.grade == 3),
                portrait_key=f.portrait_key)


# Width and deployment limits mirror the arena profiles rendered by the client.
TERRAIN_BATTLEFIELDS = {
    'plain': ('field',1140,5,'전 구간 이동·사격 가능'),
    'forest': ('forest',1020,4,'나무 군락을 피해 네 갈래 숲길로 우회'),
    'mountain': ('mountain',960,3,'암벽 사이 세 산길로 이동'),
    'river': ('river',900,4,'나루에서만 강을 건넘'),
    'fortress': ('gate',720,3,'성벽의 세 관문으로 이동'),
    'gorge': ('gorge',660,2,'협곡 중앙의 두 길로 진입'),
}


def territory_battlefield(zone_id):
    kind = zone_terrain(zone_id)['id']
    key,width,front,route = TERRAIN_BATTLEFIELDS[kind]
    return dict(id=key,width=width,front=front,back=8-front,route=route)


GARRISON_STRENGTH = .72
GARRISON_CA = round(GARRISON_STRENGTH * 110, 1)


def group_fighters(world, guild, limit):
    away = world.away(guild.gid)
    return sorted((f for f in guild.fighters if not f.injured and f.fid not in away),
                  key=lambda f: (-f.ca, f.fid))[:limit]


def group_average(fighters):
    return round(sum(f.ca for f in fighters)/len(fighters),1) if fighters else None


def zone_intelligence(world, zone):
    """Public, actual defensive lineup and AI tendency; no scouting gate."""
    defender = world.guilds.get(zone.owner)
    opponents = lineup([f for f in defender.fighters if not f.injured]) if defender else []
    roles = (0, 1, 4, 5, 3)
    members = ([dict(id=f.fid, name=f.name, role=ROLES[f.role],
                     ca=round(f.ca, 1), notable=notables.describe(world,f), row='전열' if i < 2 else '후열')
                for i, f in enumerate(opponents)] if defender else
               [dict(id=-1-i, name=f'구역 수비대 {i+1}', role=ROLES[roles[i]],
                     ca=None, notable=None, row='전열' if i < 2 else '후열')
                for i in range(5)])
    style = defending_style(opponents) if defender else dict(
        id='balanced', name=STYLES['balanced'][0],
        description=STYLES['balanced'][1])
    candidates = group_fighters(world,defender,8) if defender else []
    battlefield = territory_battlefield(zone.zid)
    front = battlefield['front']
    if candidates:
        priority = (0, 1, 5, 3, 2, 4)
        group_members = [dict(name=f.name, role=ROLES[f.role], ca=round(f.ca,1),
                              notable=notables.describe(world,f))
                         for f in sorted(candidates,key=lambda f: priority.index(f.role))]
    else:
        group_members = [dict(name=f'구역 수비대 {i+1}',role=ROLES[role],ca=GARRISON_CA)
                         for i,role in enumerate((0,1,5,3,2,4,0,1))]
    for i, member in enumerate(group_members):
        member['row'] = '전열' if i < front else '후열'
    return dict(terrain=zone_terrain(zone.zid), battlefield=battlefield['id'], field_layout=battlefield,
                tactic=style, enemy_lineup=members, tier=zone.tier,
                defense_power=group_average(candidates) if candidates else GARRISON_CA,
                group_defenders=group_members,
                **site_details(zone.zid))


class Campaign:
    def __init__(self, seed=16, interactive=False):
        self.seed = seed
        self.world = economy.World15(seed, 'baseline')
        for week in range(1, 53):
            economy.one_week(self.world, 0, week)
        economy.annual_rollover(self.world, 0)
        self.guild = economy.install_player(self.world, 'balanced', founder_count=15 if interactive else 20)
        notables.initial(self.world, exclude=[f.fid for f in self.guild.fighters])
        self.interactive = interactive
        self.phase = 'tutorial' if interactive else 'ready'
        self.draft_pool = []
        self.draft_order = []
        self.draft_cursor = 0
        self.draft_round = 0
        self.draft_picks = []
        self.world.facilities = {self.guild.gid: dict.fromkeys(FACILITIES, 0)} if interactive else {}
        self.season, self.week = 1, 1
        self.battle = None
        self.zone = None
        self.result = None
        self.practice = False
        self.pending_week = None
        self.elite_play = None
        self.group_play = None
        self.week_report = None
        self.month_run = None
        self.recruitment_attempts = {}
        self.transfer_talks = {}  # Persisted per-target bargaining sessions (no money moves until signature).
        if interactive:
            growth_dashboard.record_founding(self)

    def dismiss_battle(self):
        """Close only a resolved battle; preserve the settled weekly ledger."""
        if self.battle is None:
            return
        if self.battle.winner is None or self.pending_week is not None:
            raise ValueError('진행 중인 전투는 종료할 수 없습니다.')
        self.battle=self.zone=self.result=None
        self.practice=False

    def overview(self):
        away=self.world.away(self.guild.gid)
        available = [f for f in self.guild.fighters if not f.injured and f.fid not in away]
        ready = {f.fid for f in lineup(available)}
        return dict(season=self.season, week=self.week, month=month_number(self.week),
                    month_weeks=MONTH_ENDS[month_number(self.week)-1]-self.week+1,
                    errands=dict(rate=economy.ERRAND_RATE, limit=economy.ERRAND_LIMIT),
                    seed=self.seed, guild=self.guild.gid,
                    season_trend=season_trend(self.seed,self.season), cash=self.guild.cash, renown=round(self.guild.renown,2), phase=self.phase,
                    strategy=self.guild.strategy,
                    facilities=self.facility_view(),
                    draft=self.draft_view() if self.phase=='draft' else None, tier=self.guild.tier,
                    rank=self.league_rank(), operations=self.operations_view(),
                    treasury=self.treasury_view(),
                    league=self.league_view(),
                    world_map=self.world_map_view(),
                    week_report=self.week_report, week_pending=self.pending_week is not None,
                    elite_play=self.elite_state(),
                    dead=self.world.player_bankrupted,
                    market_notables=[dict(id=f.fid,name=f.name,
                                          rarity=self.world.notables[f.fid]['rarity'])
                                     for f in self.world.fa
                                     if f.age<=42 and f.fid in getattr(self.world,'notables',{})
                                     and self.world.notables[f.fid]['rarity'] in ('named','legend')],
                    guild_name=self.guild.name,
                    guild_display_name=honors.display_name(self.world,self.guild.gid,self.season),
                    current_rank_honor=honors.current_rank(self.world,self.guild.gid,self.season),
                    last_season_review=(self.world.honor_history[-1]['guilds'].get(self.guild.gid)
                         if getattr(self.world,'honor_history',[]) and self.world.honor_history[-1]['season']==self.season-1
                         else None),
                    long_mission_board=expedition_content.board(
                        self.seed,self.guild.gid,self.season,self.week,self.guild.tier,
                        economy.TIERS[self.guild.tier]['mission_gross'],
                        economy.TIERS[self.guild.tier]['mission_cost']),
                    long_missions=[dict(id=task['id'],title=task['title'],
                        members=list(task['members']),duration=task['duration'],
                        progress=task['progress'],spent=task['spent'],
                        reward=task['reward'],weekly_cost=task['weekly_cost'],
                        event=expedition_content.preview(task))
                        for task in self.world.long_missions[self.guild.gid]],
                    elite_board=saga_content.decorate_board(self.guild,elite_content.board(
                         self.seed,self.guild.gid,self.season,self.week,self.guild.tier,
                         economy.TIERS[self.guild.tier]['mission_gross'],
                         economy.TIERS[self.guild.tier]['mission_cost']),self.season,self.week),
                     mission_board=mission_content.board(
                        self.seed,self.guild.gid,self.season,self.week,self.guild.tier,
                        economy.TIERS[self.guild.tier]['mission_gross'],
                        economy.TIERS[self.guild.tier]['mission_cost']),
                    roster=[dict(id=f.fid, name=f.name, surname=f.surname, given_name=f.given_name,
                                 notable=notables.describe(self.world,f),
                                 portrait=portrait_asset(f), appearance=portrait_profile(f), expedition=(f.fid in away),
                                 age=f.age, pa=round(f.pa,1), wage=f.wage,
                                 role=ROLES[f.role], role_id=f.role, ca=round(f.ca, 1),
                                  kiyun_manuals=self.world.kiyun_manuals.get(f.fid,0),
                                 personal_title=f.development.personal_title,
                                 epithets=[dict(id=key,name=honors.EPITHET_BY_ID[key][1],count=rec['count'])
                                           for key,rec in getattr(self.world,'honor_fighters',{}).get(f.fid,{}).items()
                                           if key in honors.EPITHET_BY_ID],
                                 saga=saga_content.view(f,self.seed,self.season,self.week)['saga'],
                                 lv=f.lv, xp=f.xp, contract_end=f.contract_end, injured=f.injured,
                                 skills=unlocked(f), equipped=equipment(f), slots=available_skill_slots(f.lv),
                                 recommended=f.fid in ready, squad=f.development.squad) for f in self.guild.fighters],
                    missions=[dict(id=i, name=name, people=3,
                                   cost=economy.TIERS[self.guild.tier]['mission_cost'],
                                   base_reward=economy.TIERS[self.guild.tier]['mission_gross'])
                              for i, name in enumerate(MISSIONS)],
                    zone_cap=economy.CAP[self.guild.tier],
                    zones=[dict(id=z.zid, owner=z.owner,
                                gross=round(7*economy.TIERS[z.tier]['gross']*z.multiplier),
                                upkeep=round(7*economy.TIERS[z.tier]['zone_cost']*z.multiplier),
                                owner_name=(self.world.guilds[z.owner].name if z.owner is not None else '수비대'),
                                value=round(economy.old.zone_value(z)), protected_until=z.protected_until,
                                selectable=z.owner != self.guild.gid and z.protected_until <= self.clock,
                                **zone_intelligence(self.world,z))
                           for z in self.world.zones if z.tier == self.guild.tier],
                    skills={key:asdict(skill) for key, skill in SKILLS.items()},
                    battle=self.battle_state(), result=self.result, group_play=self.group_play,
                    saved_attack=getattr(self.world,'prebattle_plans',{}).get('attack'),
                    saved_defense=getattr(self.world,'prebattle_plans',{}).get('defense'))

    def found_sect(self, name, strategy):
        """Initial, explicit player identity. No new roster, league slot or economy reset."""
        if not self.interactive or self.phase != 'tutorial':
            raise ValueError('문파 창설은 게임 시작 시 한 번만 가능합니다.')
        if type(name) is not str:
            raise ValueError('문파 이름은 문자로 입력하세요.')
        name = name.strip()
        if not 2 <= len(name) <= 12 or not re.fullmatch(
                r'[가-힣ㄱ-ㅎㅏ-ㅣ一-龥A-Za-z0-9]+(?: [가-힣ㄱ-ㅎㅏ-ㅣ一-龥A-Za-z0-9]+)*', name):
            raise ValueError('문파 이름은 2~12자 한글·한자·영문·숫자로 입력하세요.')
        if type(strategy) is not str or strategy not in (
                'balanced', 'growth', 'transfer', 'conquest', 'baseline'):
            raise ValueError('지원하지 않는 문파 운영 방침입니다.')
        if name != self.guild.name and name in self.world.names.used_sects:
            raise ValueError('이미 강호에 존재하는 문파 이름입니다.')
        if name != self.guild.name:
            self.world.names.reserve_sect(name)
            self.guild.name = name
        self.guild.strategy = strategy
        self.world.strategy = strategy
        self.begin_draft()

    @staticmethod
    def _league_ranked(world, tier):
        return sorted((g for g in world.guilds.values() if g.tier == tier),
                      key=lambda g:(g.score, g.strength(), -g.gid), reverse=True)

    def world_map_view(self):
        """Read-only territory atlas with current 7-day income estimates.

        Mirror collection scale overhead and garrison costs without mutating the
        world ledger. The current owner allocation determines the estimate;
        neutral territory assumes an independently held first site.
        """
        by_site_net = {}
        for guild in self.world.guilds.values():
            holdings = sorted((zone for zone in self.world.zones
                               if zone.owner == guild.gid),
                              key=economy.old.zone_value, reverse=True)
            garrison_basis = 0
            for index, zone in enumerate(holdings):
                tier = economy.TIERS[zone.tier]
                gross = round(7 * tier['gross'] * zone.multiplier)
                upkeep = round(7 * tier['zone_cost'] * zone.multiplier)
                direct_net = gross - upkeep
                overhead = round(direct_net * (1 - [1., .65, .4, .3, .2][min(index, 4)]))
                # Match round(sum(other site values) * .03) across the holdings.
                next_basis = garrison_basis + (economy.old.zone_value(zone) if index else 0)
                garrison = round(next_basis * .03) - round(garrison_basis * .03)
                garrison_basis = next_basis
                by_site_net[zone.zid] = direct_net - overhead - garrison

        sites = []
        for zone in self.world.zones:
            info = zone_intelligence(self.world, zone)
            tier = economy.TIERS[zone.tier]
            gross = round(7 * tier['gross'] * zone.multiplier)
            upkeep = round(7 * tier['zone_cost'] * zone.multiplier)
            sites.append(dict(
                id=zone.zid, tier=zone.tier, owner=zone.owner,
                owner_name=(self.world.guilds[zone.owner].name
                            if zone.owner is not None else '수비대'),
                protected_until=zone.protected_until,
                selectable=(zone.tier == self.guild.tier
                            and zone.owner != self.guild.gid
                            and zone.protected_until <= self.clock),
                gross=gross, upkeep=upkeep,
                value=round(economy.old.zone_value(zone)),
                weekly_net=by_site_net.get(zone.zid, gross - upkeep),
                defense_power=info['defense_power'],
                terrain=info['terrain'], field_layout=info['field_layout'],
                **site_details(zone.zid)))
        return sites

    def league_view(self):
        """Use the exact season-end tie breaks and 8-sect league membership."""
        zones = self.world.zones
        ranks = {}
        for tier in (1, 2, 3, 4):
            members = self._league_ranked(self.world, tier)
            assert len(members) == 8
            rows = []
            for idx, g in enumerate(members, 1):
                if tier == 1 and idx == 1:
                    outlook = '1부 우승 경쟁'
                elif tier != 1 and idx == 1:
                    outlook = '자동 승격권'
                elif tier != 1 and idx == 2:
                    outlook = '승격 플레이오프권'
                elif tier != 4 and idx == 8:
                    outlook = '자동 강등권'
                elif tier != 4 and idx == 7:
                    outlook = '강등 플레이오프권'
                else:
                    outlook = '잔류권'
                ranks[tier] = ranks.get(tier, [])
                rows.append(dict(id=g.gid, name=g.name, tier=tier, rank=idx,
                                 score=round(g.score, 2), strength=round(g.strength(), 1), roster_power=group_average(g.fighters),
                                 roster=len(g.fighters),
                                 zones=sum(z.owner == g.gid for z in zones),
                                 player=g.gid == self.guild.gid, outlook=outlook,
                                 display_name=honors.display_name(self.world,g.gid,self.season),
                                 rank_honor=honors.current_rank(self.world,g.gid,self.season)))
            ranks[tier] = rows
        return dict(season=self.season, week=self.week, current_tier=self.guild.tier,
                    groups=[dict(tier=tier, members=ranks[tier]) for tier in (1,2,3,4)],
                    rule='동일 부 8개 문파. 시즌 종료 시 점수 → 상위 5인 평균 전력 → 문파 고유번호 순으로 순위를 확정합니다. 2~4부 1위는 자동 승격, 1~3부 8위는 자동 강등, 하위 부 2위와 바로 위 부 7위는 승강전 대상입니다.')

    def sect_profile(self, guild_id):
        """Public rival report. PA and RNG-only recruitment preferences remain hidden."""
        if type(guild_id) is not int or guild_id not in self.world.guilds:
            raise ValueError('존재하지 않는 문파입니다.')
        guild=self.world.guilds[guild_id]
        row=next(x for group in self.league_view()['groups']
                 if group['tier']==guild.tier for x in group['members'] if x['id']==guild_id)
        owned=[z for z in self.world.zones if z.owner == guild_id]
        roster=sorted(guild.fighters,key=lambda f:(f.ca,f.lv,-f.fid),reverse=True)
        fixed=max(1,guild.wage_total()+economy.TIERS[guild.tier]['hall'])
        if guild.cash < fixed*3:
            reserve='3주 미만'
        elif guild.cash < fixed*8:
            reserve='3~8주 미만'
        else:
            reserve='8주 이상'
        return dict(id=guild_id,name=guild.name,
                    display_name=honors.display_name(self.world,guild_id,self.season),
                    current_rank_honor=honors.current_rank(self.world,guild_id,self.season),
                    tier=guild.tier,rank=row['rank'],
                    score=row['score'],strength=row['strength'],outlook=row['outlook'],
                    roster_power=row['roster_power'],
                    ca_min=round(min((f.ca for f in roster),default=0),1),
                    ca_max=round(max((f.ca for f in roster),default=0),1),
                    player=guild_id==self.guild.gid,
                    roster_count=len(roster),zone_count=len(owned),
                    renown=round(guild.renown,1),
                    cash=round(guild.cash) if guild_id==self.guild.gid else None,
                    treasury=reserve,weekly_wages=guild.wage_total(),
                    record=dict(attacks=guild.attacks,attack_wins=guild.attack_wins,
                                defense_wins=guild.defense_wins,
                                missions=guild.missions_done,mission_wins=guild.missions_won,
                                promoted=guild.promoted,relegated=guild.relegated,
                                championships=guild.championships),
                    zones=[dict(id=z.zid,value=round(economy.old.zone_value(z)),
                                selectable=(z.tier==self.guild.tier and
                                            z.owner!=self.guild.gid and
                                            z.protected_until<=self.clock),
                                **zone_intelligence(self.world,z))
                           for z in owned],
                    members=[dict(id=f.fid,name=f.name,role=ROLES[f.role],role_id=f.role,
                                  portrait=portrait_asset(f),age=f.age,
                                  ca=round(f.ca,1),level=f.lv,injured=bool(f.injured),
                                  notable=notables.describe(self.world,f),
                                  contract_end=f.contract_end,wage=f.wage)
                             for f in roster],
                    market_open=not self.market_closed())

    def treasury_view(self):
        """Read-only guide: passive income assumes 7-day ownership, not a promise."""
        forecast=economy.passive_week_projection(self.world,self.guild)
        reserve,rate=economy.investment_rules(self.world,self.guild)
        policy=economy.treasury_policy(self.world,self.guild)
        return dict(policy=policy,cash=self.guild.cash,
                    reserve_weeks=economy.TREASURY_POLICIES[policy][0],
                    reserve=reserve,rate=rate,
                    debt=self.world.debts[self.guild.gid].total(),
                    training_cost=economy.TIERS[self.guild.tier]['training_cost'],
                    available_above_reserve=max(0,self.guild.cash-reserve),
                    forecast=forecast)

    def set_treasury_policy(self, policy):
        """Only the player may change optional spending before weekly lock."""
        if not self.interactive or self.market_closed() or self.phase!='ready':
            raise ValueError('주간 결산이나 전투 중에는 자금 운용을 변경할 수 없습니다.')
        if type(policy) is not str or policy not in economy.TREASURY_POLICIES:
            raise ValueError('지원하지 않는 자금 운용 정책입니다.')
        self.world.player_treasury_policy=policy

    def operations_view(self):
        g = self.guild
        leader = max(other.score for other in self.world.guilds.values() if other.tier == g.tier)
        return dict(clock=self.clock, fixed=economy.fixed_weekly_cost(self.world,g),
                    debt=self.world.debts[g.gid].total(),
                    score=round(g.score, 2), leader_gap=round(leader-g.score, 2))

    def league_rank(self):
        key = lambda g: (g.score, g.strength(), -g.gid)
        return 1 + sum(key(g) > key(self.guild) for g in self.world.guilds.values()
                       if g.tier == self.guild.tier)

    def next_week_briefing(self, previous_season):
        w, g = self.world, self.guild
        if w.player_bankrupted:
            return dict(stage='bankrupt')
        if previous_season != self.season:
            return dict(stage='draft', season=self.season, tier=g.tier)
        away = w.away(g.gid)
        injured = {f.fid for f in g.fighters if f.injured}
        ready = len(g.fighters) - len(away | injured)
        tier = economy.TIERS[g.tier]
        fixed = economy.fixed_weekly_cost(w,g)
        offers = mission_content.board(self.seed,g.gid,self.season,self.week,g.tier,
                                       tier['mission_gross'],tier['mission_cost'])
        mission = min((offer for offer in offers if offer['min_members'] <= ready
                       and offer['cost'] <= max(0,g.cash-fixed)),
                      key=lambda offer: (offer['cost'],offer['id']), default=None)
        open_zones = [z for z in w.zones if z.tier == g.tier and z.protected_until <= self.clock]
        target = max((z for z in open_zones if z.owner is None),
                     key=economy.old.zone_value, default=None)
        return dict(stage='week', week=self.week, month=month_number(self.week), ready=ready, injured=len(injured), away=len(away),
                    fixed=fixed, debt=w.debts[g.gid].total(), mission=mission,
                    exposed=[z.zid for z in open_zones if z.owner == g.gid],
                    target=target.zid if target is not None and ready >= 5 else None)

    @property
    def clock(self):
        return self.season*52+self.week

    def start(self, zone_id, setup, practice=False):
        if self.battle and self.battle.winner is None:
            raise ValueError('진행 중인 전투를 먼저 끝내세요.')
        if self.phase != 'ready' or self.world.player_bankrupted or self.week >= 52:
            raise ValueError('현재 출전할 수 없습니다.')
        zone = next((z for z in self.world.zones if z.zid == zone_id), None)
        if zone is None or zone.tier != self.guild.tier or zone.owner == self.guild.gid or zone.protected_until > self.clock:
            raise ValueError('지금 공격할 수 없는 구역입니다.')
        roster = {f.fid:f for f in self.guild.fighters if not f.injured and f.fid not in self.world.away(self.guild.gid)}
        if len(setup) != 5 or len({x['id'] for x in setup}) != 5:
            raise ValueError('출전 문파원을 5명 선택하세요.')
        units = []
        for assignment in setup:
            f = roster.get(assignment['id'])
            skills = assignment['skills']
            if (f is None or assignment['row'] not in ('front','back')
                    or len(set(skills)) != len(skills) or not set(skills) <= set(unlocked(f))
                    or len(skills) > available_skill_slots(f.lv)):
                raise ValueError('출전 상태 또는 장착 무공을 확인하세요.')
            units.append(unit(f, 0, assignment['row'], skills))
        if not any(u.row == 'front' for u in units):
            raise ValueError('전열을 한 명 이상 편성하세요.')
        defender = self.world.guilds.get(zone.owner)
        opponents = lineup([f for f in defender.fighters if not f.injured]) if defender else []
        for i in range(5):
            if i < len(opponents):
                f = opponents[i]
                units.append(unit(f, 1, 'front' if i < 2 else 'back', equipment(f)))
            else:
                role = (0, 1, 4, 5, 3)[i]
                units.append(Unit(-1-i, 1, role, f'구역 수비대 {i+1}', 'front' if i < 2 else 'back',
                                  [60]*8, 1, ROLE_SKILLS[role][:1]))
        tactic=zone_intelligence(self.world,zone)['tactic']['id']
        context=combat_context(self.seed,self.season,zone_id,tactic)
        talents=notables.battle_talents(self.world,units)
        if talents:
            context['notables']=talents
        self.battle = Battle(units, self.seed*1000+zone_id+self.clock*100_000, context=context)
        self.zone, self.practice, self.result = zone, practice, None

    def begin_group(self, kind, own, rival, zone=None, pair=None, assault=None, *, ally=None, bench_plan=None):
        self.group_play = self.group_config(kind,own,rival,zone,pair,assault,ally=ally,bench_plan=bench_plan)
        self.phase = 'group'

    def group_config(self, kind, own, rival, zone=None, pair=None, assault=None, *, ally=None, bench_plan=None):
        mode = 10 if kind == 'playoff' else 8
        field = territory_battlefield(zone.zid) if zone else dict(id='field',front=5)
        terrain = field['id']
        front = 5 if mode == 10 else field['front']
        roles = ('guard', 'blade', 'bow', 'hex', 'heal', 'dash')
        priority = (0, 1, 5, 3, 2, 4)

        def card(f):
            values = list(f.development.attributes)
            for trait in f.development.traits:
                values[trait.attribute] = min(200, values[trait.attribute] + trait.bonus)
            return dict(id=f.fid, name=f.name, role=roles[f.role],
                        portrait=portrait_asset(f),
                        strength=round(max(.55, min(2, f.ca/110)), 3),
                        ca=round(f.ca,1), pa=round(f.pa,1), level=f.lv,
                        attrs={key:round(value,1) for key,value in zip(ATTRIBUTES,values)},
                        wage=f.wage,contract_end=f.contract_end,
                        notable=notables.describe(self.world,f))

        def place(fighters):
            roster = [card(f) for f in fighters]
            roster.sort(key=lambda u: priority.index(roles.index(u['role'])))
            return [dict(u, line='front' if i < front else 'back',
                         slot=i if i < front else i-front) for i, u in enumerate(roster)]
        ally = ally or self.guild

        def garrison():
            return [dict(id=-i-1, name=f'구역 수비대 {i+1}', role=roles[priority[i%6]],
                         strength=GARRISON_STRENGTH, line='front' if i < front else 'back',
                         slot=i if i < front else i-front) for i in range(mode)]

        team = place(own)
        if kind=='defense' and not team:
            team = garrison()
        defender_cards = []
        if ally is self.guild and bench_plan and kind in ('territory','conquest_duel'):
            defender_cards = place(bench_plan.get('defend',[]))
        bench = []
        if ally is self.guild and team and all(member['id']>0 for member in team):
            if bench_plan is None:
                reserve = [f for f in self.guild.fighters if not f.injured
                           and f.fid not in self.world.away(self.guild.gid)]
            else:
                reserve = [f for key in ('training','second','overflow_bench','rest','errands')
                           for f in bench_plan.get(key,[])]
            deployed = {member['id'] for member in team+defender_cards}
            available = {f.fid:f for f in reserve if f.fid not in deployed and
                         not f.injured and f.fid not in self.world.away(self.guild.gid)}
            bench = [card(f) for f in sorted(available.values(),key=lambda f:(-f.ca,f.fid))]
        captain, deputy = (team[0]['id'] if team else None,
                           team[1]['id'] if len(team)>1 else None)
        saved = getattr(self.world,'prebattle_plans',{}).get('defense' if kind=='defense' else 'attack',{})
        if ally is self.guild and zone and (saved.get('season'),saved.get('week'),saved.get('zone_id')) == (
                self.season,self.week,zone.zid):
            formation = saved['data']['formation']
            if {f['id'] for f in formation} == {f['id'] for f in team}:
                captain, deputy = saved['data']['captain'], saved['data']['deputy']
                front_ids = [f['id'] for f in formation if f['row']=='front']
                back_ids = [f['id'] for f in formation if f['row']=='back']
                if len(front_ids)>front:
                    back_ids.extend(front_ids[front:])
                    front_ids = front_ids[:front]
                back = mode-front
                if len(back_ids)>back:
                    front_ids.extend(back_ids[back:])
                    back_ids = back_ids[:back]
                by_id = {f['id']: f for f in team}
                team = [dict(by_id[fid], line=line, slot=i)
                        for line, ids in (('front',front_ids),('back',back_ids))
                        for i,fid in enumerate(ids)]
        rivals = (assault if assault is not None else group_fighters(self.world,rival,mode)) if rival else []
        enemy = place(rivals)
        if zone and not enemy:
            enemy = garrison()
        enemy_arts = {'당문': ['rain','poison'], '소림': ['lotus','mercy'],
                      '무당': ['wall','silence']}.get(rival.name if rival else '',
                                                       ['wing','turtle'])
        match = f'{self.season}:{self.week}:{kind}'
        if kind=='defense':
            match += f':{zone.zid}'
        return dict(kind=kind, match=match,
                               zoneName=site_details(zone.zid)['name'] if zone else None,
                               zone=zone.zid if zone else None, tier=zone.tier if zone else self.guild.tier, pair=pair,
                               mode=mode, terrain=terrain, team=team, bench=bench,
                               defenseTeam=defender_cards,
                               defenseEnabled=bool(ally is self.guild and
                                   (kind in ('territory','conquest_duel') or
                                    any(z.owner==self.guild.gid and z.tier==self.guild.tier
                                        for z in self.world.zones))),
                               enemyRoster=enemy,
                               scenario='defense' if kind=='defense' else 'attack',
                               captain=captain, deputy=deputy,
                               sectNames=[ally.name if own or kind!='defense' else '구역 수비대',
                                          rival.name if rival else '구역 수비대'],
                               observer=ally is not self.guild,
                               teamPower=group_average(own),
                               enemyPower=group_average(rivals) if rivals else GARRISON_CA if zone else None,
                               enemyArts=enemy_arts)

    def resolve_offscreen_attack(self, attacker, zone, defender, assault, guard):
        if _arena_resolver is None:
            return None
        config=self.group_config('territory',assault,defender,zone,assault=guard,ally=attacker)
        result=json.loads(_arena_resolver(json.dumps(config,ensure_ascii=False)))
        self.record_group_participants(self.group_replay(result),count_conquest=False,award_experience=False)
        return result['winner']==0

    def start_conquest(self, plan, own, zone):
        w=self.world
        w.season_active,w.week_active,w.globalweek=self.season,self.week,self.clock
        ai={gid:economy.prep_plan(w,guild,self.week) for gid,guild in w.guilds.items()
            if guild is not self.guild}
        order=economy.old.attack_order(w,ai)
        rivals=[gid for _,gid,zid in order if zid==zone.zid and
                economy.old.attack_allowed(w,gid,zone)]
        plan['campaign_ai']=ai
        plan['campaign_order']=order
        if not rivals:
            self.begin_group('territory',own,w.guilds.get(zone.owner),zone,
                             assault=self.site_defenders(ai,zone),bench_plan=plan)
            return
        gid=self.guild.gid
        crews={rival:self.attack_crew(rival,ai[rival]) for rival in rivals}
        crews[gid]=own
        plan['conquest']=dict(zone=zone.zid,champion=gid,remaining=rivals,crews=crews,duels=[])
        self.advance_conquest(plan)

    def advance_conquest(self, plan):
        contest=plan['conquest']
        zone=self.world.zones[contest['zone']]
        guilds=self.world.guilds
        ally=guilds[contest['champion']]
        team=contest['crews'][ally.gid]
        if contest['remaining']:
            challenger=contest['remaining'].pop(0)
            self.begin_group('conquest_duel',team,guilds[challenger],zone,
                             assault=contest['crews'][challenger],ally=ally,
                             bench_plan=plan if ally is self.guild else None)
            self.group_play['match']+=f":{len(contest['duels'])+1}"
            self.group_play['contestSides']=[ally.gid,challenger]
        else:
            kind='territory' if ally is self.guild else 'conquest_final'
            self.begin_group(kind,team,guilds.get(zone.owner),zone,ally=ally,
                             assault=self.site_defenders(plan['campaign_ai'],zone),
                             bench_plan=plan if ally is self.guild else None)
            self.group_play['contestFinal']=True

    @staticmethod
    def site_defenders(ai,zone):
        guard=ai.get(zone.owner,{})
        return guard['defend'] if guard.get('home')==zone.zid else []

    def group_assign(self, match, formation, defenders, captain, deputy):
        """Commit both attack and defense rosters before the real 8v8 encounter.

        The reserve pool is locked by the original monthly assignment. Switching
        squads is atomic and does not settle, simulate, or advance the game.
        """
        group=self.group_play
        if (self.phase!='group' or group is None or group['match']!=match
                or group.get('observer') or group['kind'] not in
                ('territory','conquest_duel','defense')):
            raise ValueError('현재 직접 편성할 수 있는 전투가 아닙니다.')
        plan=self.pending_week
        if plan is None or self.month_run is None:
            raise ValueError('진행 중인 월간 전투 편성을 찾을 수 없습니다.')
        if not isinstance(formation,list) or len(formation)!=len(group['team']):
            raise ValueError('현재 출전 인원을 모두 편성하세요.')
        if type(captain) is not int or type(deputy) is not int or captain==deputy:
            raise ValueError('출전한 대장과 부대장을 서로 다르게 지정하세요.')
        cap=territory_battlefield(group['zone']) if group['zone'] is not None else dict(front=5,back=5)
        pool={f['id']:f for f in
              [*group['team'],*group.get('defenseTeam',[]),*group.get('bench',[])]
              if f['id']>0}
        indices=set()
        ids=[]
        formation_cards=[]
        for slot in formation:
            if not isinstance(slot,dict) or type(slot.get('id')) is not int:
                raise ValueError('출전 문파원 형식이 올바르지 않습니다.')
            fid=slot['id']
            row=slot.get('line')
            index=slot.get('slot')
            if (fid not in pool or fid in ids or row not in ('front','back') or
                    type(index) is not int or not 0<=index<cap[row] or
                    (row,index) in indices):
                raise ValueError('출전 인원 또는 진형이 중복되었거나 전장 슬롯을 벗어났습니다.')
            ids.append(fid)
            indices.add((row,index))
            unit=dict(pool[fid],line=row,slot=index)
            if 'position' in slot:
                position=slot['position']
                if (not isinstance(position,dict) or
                        any(type(position.get(key)) not in (int,float)
                            or not 0<=position[key]<=1140 for key in ('x','y'))):
                    raise ValueError('전장 배치 좌표가 올바르지 않습니다.')
                unit['position']={key:position[key] for key in ('x','y')}
            formation_cards.append(unit)
        if captain not in ids or deputy not in ids:
            raise ValueError('대장·부대장이 출전 명단에 없습니다.')
        if not any(f['line']=='front' for f in formation_cards):
            raise ValueError('전열에 최소 한 명을 배치하세요.')
        if not isinstance(defenders,list) or len(defenders)>8 or any(type(fid) is not int for fid in defenders):
            raise ValueError('방어대는 최대 8명까지 편성할 수 있습니다.')
        if group['kind']=='defense':
            if defenders:
                raise ValueError('방어전에서는 상단의 수비대 편성을 변경하세요.')
            new_defenders=ids
        else:
            if defenders and not group.get('defenseEnabled'):
                raise ValueError('보유 거점이 없어 방어대를 편성할 수 없습니다.')
            if len(set(defenders))!=len(defenders) or any(fid not in pool or fid in ids for fid in defenders):
                raise ValueError('점령대와 방어대에 문파원을 중복 배치할 수 없습니다.')
            new_defenders=defenders
        remaining=[f for fid,f in pool.items() if fid not in ids and fid not in new_defenders]
        by_id={f.fid:f for f in self.guild.fighters}
        # All checks passed: commit the single source-of-truth monthly plan.
        # Troops reassigned from training/errands/reserve cannot receive the
        # same week's non-combat payout as defenders.
        assigned_now=set(ids)|set(new_defenders)
        for key in ('training','second','overflow_bench','rest','errands'):
            plan[key]=[f for f in plan.get(key,[]) if f.fid not in assigned_now]
        plan['second_ids'].difference_update(assigned_now)
        plan['defend']=[by_id[fid] for fid in new_defenders]
        self.month_run['defense']=list(new_defenders)
        if plan.get('conquest') and plan['conquest']['champion']==self.guild.gid:
            plan['conquest']['crews'][self.guild.gid]=[by_id[fid] for fid in ids]
        group['team']=formation_cards
        group['captain']=captain
        group['deputy']=deputy
        group['bench']=remaining
        group['defenseTeam']=[dict(pool[fid]) for fid in new_defenders] if group['kind']!='defense' else []
        group['teamPower']=group_average([by_id[fid] for fid in ids])
        return self.overview()

    def finish_group(self, match, result):
        group = self.group_play
        if self.phase != 'group' or group is None or match != group['match']:
            raise ValueError('진행 중인 단체전을 다시 불러오세요.')
        winner = result['winner']
        if group['kind'] in ('conquest_duel','conquest_final','territory','defense'):
            plan = self.pending_week
            player_team = not group.get('observer') and all(u['id']>0 for u in group['team'])
            if player_team and result.get('units') is not None:
                allies = [u['id'] for u in result['units'] if u.get('side')==0]
                allowed = {u['id'] for u in group['team']+group.get('bench',[])}
                if (len(allies)!=len(group['team']) or len(set(allies))!=len(allies)
                        or any(type(fid) is not int or fid not in allowed for fid in allies)):
                    raise ValueError('대기 인원을 포함한 출전 명단을 확인하세요.')
                by_id = {f.fid:f for f in self.guild.fighters}
                if group['kind']=='defense':
                    plan['defend'] = [by_id[fid] for fid in allies]
                elif group['kind']=='conquest_duel' and plan.get('conquest'):
                    plan['conquest']['crews'][self.guild.gid] = [by_id[fid] for fid in allies]
            if group['kind']=='conquest_duel':
                contest=plan['conquest']
                sides=group['contestSides']
                if winner==-1:
                    winner=int((group['enemyPower'] or 0)>(group['teamPower'] or 0))
                contest['champion']=sides[winner]
                contest['duels'].append(dict(result=result,sides=sides,winner=sides[winner]))
                return self.advance_conquest(plan)
            if group['kind']=='conquest_final':
                plan['conquest']['final']=result
            elif group['kind']=='territory':
                plan['offense_replay'] = dict(result, zone=group['zone'])
            else:
                defense = plan['defense_setup']
                if 'targets' in defense:
                    replays = plan.setdefault('defense_replays', [])
                    replays.append(result)
                    if len(replays)<len(defense['targets']):
                        offense = self.group_replay(plan.get('offense_replay'))
                        return self.start_defense(plan, defense['targets'][len(replays)],
                                                  set(offense.units) if offense else set())
                else:
                    plan['defense_replay'] = result
            self.settle_group_week(plan)
            if self.group_play is group:
                self.group_play = None
            return
        upper, lower = group['pair']
        lower_wins = winner == (0 if self.guild.gid == lower else 1)
        report = self.week_report
        ledger = self.world.money
        capture, start = ledger.capture, len(ledger.entries)
        ledger.capture = True
        tier_before = self.guild.tier
        try:
            economy.annual_rollover(self.world, self.season, interactive=self.interactive,
                                    playoff=(upper, lower, lower_wins))
            economy.assert_world(self.world)
            entries = [e for e in ledger.entries[start:] if e['guild']==self.guild.gid]
        finally:
            ledger.capture = capture
            if not capture:
                del ledger.entries[start:]
        self.season += 1
        self.week = 1
        self.phase = 'report'
        self.group_play = None
        report['entries'].extend(entries)
        report['cash'] = self.guild.cash
        report['cash_change'] = self.guild.cash-report['cash_before']
        if report['battle']:
            report['battle']['cash_change'] = report['cash_change']
        report['income'] += sum(max(0,e['amount']) for e in entries)
        report['expenses'] += sum(max(0,-e['amount']) for e in entries)
        assert sum(e['amount'] for e in report['entries']) == report['cash_change']
        report['playoff'] = dict(opponent=group['sectNames'][1], winner=winner,
                                 tier_before=tier_before, tier=self.guild.tier, performance=result.get('performance',[]))
        report['briefing'].update(tier=self.guild.tier, rank=self.league_rank(),
                                  territories=sum(z.owner==self.guild.gid for z in self.world.zones),
                                  next=self.next_week_briefing(report['season']))

    def facility_view(self):
        levels = self.world.facilities.get(self.guild.gid, {})
        values = {'training': economy.TRAINING_FACILITY_BONUS,
                  'estate': economy.ESTATE_WEEKLY_INCOME,
                  'medical': tuple(economy.MEDICAL_REDUCTION_PER_LEVEL*i for i in range(6))}
        rows = []
        for key,(name,base,effect) in FACILITIES.items():
            level = levels.get(key,0)
            next_level = min(5,level+1)
            row = dict(id=key, name=name, level=level, max=5, per_level=effect,
                       current_value=values[key][level], next_value=values[key][next_level],
                       current_upkeep=economy.FACILITY_WEEKLY_UPKEEP[level],
                       next_upkeep=economy.FACILITY_WEEKLY_UPKEEP[next_level],
                       next_cost=facility_upgrade_cost(base,next_level) if level<5 else None)
            if key=='estate':
                row['current_discount'] = economy.ESTATE_FEE_DISCOUNT_PER_LEVEL*level
                row['next_discount'] = economy.ESTATE_FEE_DISCOUNT_PER_LEVEL*next_level
            rows.append(row)
        return rows

    def upgrade(self, key):
        if not self.interactive or self.phase != 'ready' or self.market_closed() or key not in FACILITIES:
            raise ValueError('지금은 건축물을 올릴 수 없습니다.')
        levels = self.world.facilities[self.guild.gid]
        level = levels[key]
        cost = facility_upgrade_cost(FACILITIES[key][1],level+1)
        if level>=5 or self.guild.cash<cost:
            raise ValueError('최고 레벨이거나 건축 자금이 부족합니다.')
        w = self.world
        w.season_active, w.week_active, w.globalweek = self.season, self.week, self.clock
        w.money.spend(self.guild,cost,'facility_upgrade')
        levels[key] += 1
        w.money.reconcile()

    def advance_phase(self, phase):
        if phase != self.phase:
            raise ValueError('진행 상태를 다시 불러오세요.')
        if phase=='tutorial':
            self.begin_draft()
        elif phase=='fa':
            self.phase = 'ready'
        elif phase=='report':
            self.battle = self.result = self.zone = None
            if self.week_report['season'] != self.season and not self.world.player_bankrupted:
                self.begin_draft()
            else:
                self.phase = 'ready'
        else:
            raise ValueError('먼저 현재 단계를 마치세요.')

    def begin_draft(self):
        w = self.world
        count = len(w.fa)
        economy.old.generate_rookies(w,self.season,5*len(w.guilds)+8)
        self.draft_pool = w.fa[count:]
        del w.fa[count:]
        self.draft_order = sorted(w.guilds.values(), key=lambda g:(-g.tier,g.annual_best_rank*-1,g.strength(),g.gid))
        self.draft_round, self.draft_cursor, self.draft_picks = 1, 0, []
        self.phase = 'draft'
        self.advance_draft()

    def advance_draft(self):
        while self.draft_round<=5:
            g = self.draft_order[self.draft_cursor]
            if g is self.guild:
                return
            if len(g.fighters)<economy.MAX_ROSTER and self.draft_pool:
                f = max(self.draft_pool,key=lambda member:(
                    (observed_ability(member)+.55*max(0,observed_potential(member)-observed_ability(member)))
                    * preference_multiplier(g,member), -member.fid))
                reserve = 4*(g.wage_total()+f.wage+economy.TIERS[g.tier]['hall'])
                if g.cash >= reserve and not self.world.debts[g.gid].total():
                    self.sign_draft(g,f)
            self.step_draft_cursor()
        self.world.fa.extend(self.draft_pool)
        self.draft_pool = []
        self.phase = 'fa'

    def step_draft_cursor(self):
        self.draft_cursor += 1
        if self.draft_cursor == len(self.draft_order):
            self.draft_round += 1
            self.draft_cursor = 0

    def sign_draft(self,g,f):
        self.draft_pool.remove(f)
        f.contract_end = self.season
        f.last_transfer_season = self.season
        f.free_since = -1
        g.fighters.append(f)
        if g is self.guild:
            self.world.register_member(f,self.season,'draft')
            growth_dashboard.record_join(self.world,f,self.season,self.week,self.guild.gid,'드래프트')
            self.draft_picks.append(f.name)

    def draft_view(self):
        return dict(round=self.draft_round, position=self.draft_cursor+1, picks=self.draft_picks,
                    roster_full=len(self.guild.fighters)>=economy.MAX_ROSTER,
                    candidates=[dict(id=f.fid,name=f.name,role=ROLES[f.role],role_id=f.role,
                                     portrait=portrait_asset(f),age=f.age,ca=round(f.ca,1),
                                     pa=round(f.pa,1),wage=f.wage,notable=notables.describe(self.world,f)) for f in self.draft_pool])

    def draft_pick(self, season, round_no, fid):
        if self.phase!='draft' or (season,round_no)!=(self.season,self.draft_round):
            raise ValueError('현재 드래프트 순서를 다시 확인하세요.')
        if fid is not None:
            f = next((x for x in self.draft_pool if x.fid==fid),None)
            if f is None or len(self.guild.fighters)>=economy.MAX_ROSTER:
                raise ValueError('선택할 수 없는 신인이거나 정원이 가득 찼습니다.')
            self.sign_draft(self.guild,f)
        self.step_draft_cursor()
        self.advance_draft()
        economy.assert_world(self.world)

    def market_closed(self):
        return (self.phase not in ('ready','fa') or self.world.player_bankrupted or self.pending_week is not None
                or (self.battle is not None and self.battle.winner is None))

    def free_agents(self):
        return market_intel.snapshot(self)

    def market_compare(self,ids,replace_id=None):
        return market_intel.compare(self,ids,replace_id)

    def free_agent_quote(self, fighter):
        terms = self.world.free_agent_terms(self.guild, fighter)
        reason = terms.pop('reason')
        if self.market_closed():
            reason = 'market_closed'
        elif self.recruitment_attempts.get(fighter.fid) == self.clock:
            reason = 'declined_this_week'
        return dict(id=fighter.fid, name=fighter.name, role=ROLES[fighter.role],
                    role_id=fighter.role,portrait=portrait_asset(fighter),
                    notable=notables.describe(self.world,fighter),
                    age=fighter.age, ca=round(fighter.ca, 1),
                    pa=round(economy.observed_pa(fighter, True), 1),
                    level=fighter.lv, source='rookie' if fighter.development.rookie else 'fa',
                    cash_after=self.guild.cash-terms['fee'], eligible=reason is None,
                    reason=reason, **terms)

    def recruit(self, season, week, fighter_id, years):
        if (season, week) != (self.season, self.week):
            raise ValueError('영입 목록을 다시 불러오세요.')
        if type(years) is not int or not 1 <= years <= 5:
            raise ValueError('계약 기간은 1~5시즌입니다.')
        fighter = next((f for f in self.world.fa if f.fid == fighter_id and f.age <= 42), None)
        if fighter is None:
            return dict(status='unavailable', id=fighter_id)
        quote = self.free_agent_quote(fighter)
        if not quote['eligible']:
            return dict(status=quote['reason'], id=fighter_id)
        self.world.season_active, self.world.week_active = self.season, self.week
        self.world.globalweek = self.clock
        if not self.world.new_contract(self.guild, fighter, self.season, weekly=True, years=years):
            self.recruitment_attempts[fighter_id] = self.clock
            return dict(status='declined_this_week', id=fighter_id)
        self.world.money.reconcile()
        growth_dashboard.record_join(self.world,fighter,self.season,self.week,self.guild.gid,'자유 낭인 영입')
        return dict(status='signed', id=fighter_id, name=fighter.name, fee=quote['fee'],
                    wage=fighter.wage, years=years, contract_end=fighter.contract_end,
                    cash=self.guild.cash)

    def set_training_focus(self,fid,focus):
        return training_focus.set_one(self,fid,focus)

    def preview_training_focus(self,mode='attack',overwrite=False):
        return training_focus.preview_deputy(self,mode,overwrite)

    def auto_training_focus(self,mode='attack',overwrite=False,expected=None):
        return training_focus.apply_deputy(self,mode,overwrite,expected)

    def member_detail(self, fid):
        f = next((f for f in self.guild.fighters if f.fid == fid), None)
        if f is None:
            raise ValueError('현재 문파 명단에서 찾을 수 없습니다.')
        return dict(id=f.fid, name=f.name, role=ROLES[f.role], role_id=f.role,
                    portrait=portrait_asset(f),appearance=portrait_profile(f),ca=round(f.ca, 1),
                    notable=notables.describe(self.world,f),
                    legend_progress=dict(self.world.notable_progress.get(f.fid,{})),
                    pa=round(f.pa, 1), age=f.age, level=f.lv, wage=f.wage,
                    training_focus=training_focus.profile(self.world,f),
                    training_focus_options=training_focus.options(),
                    contract_end=f.contract_end, remaining=max(0, f.contract_end-self.season+1),
                    attributes=[dict(key=k, base=round(v, 1),
                                     effective=round(min(200, v+sum(t.bonus for t in f.development.traits if t.attribute==i)),1),
                                     weight=w*5)
                                for i,(k,v,w) in enumerate(zip(ATTRIBUTES,f.development.attributes,WEIGHTS[f.role]))],
                    kiyun_manuals=self.world.kiyun_manuals.get(f.fid,0),
                    bonds=[dict(id=other.fid,name=other.name,
                                value=self.world.kiyun_bonds.get(tuple(sorted((f.fid,other.fid))),0))
                           for other in self.guild.fighters if other.fid!=f.fid
                           and self.world.kiyun_bonds.get(tuple(sorted((f.fid,other.fid))),0)>0],
                    epithets=[dict(id=key,name=honors.EPITHET_BY_ID[key][1],
                                   grade=honors.EPITHET_BY_ID[key][2],
                                   count=rec['count'],seasons=rec['seasons'])
                              for key,rec in getattr(self.world,'honor_fighters',{}).get(f.fid,{}).items()
                              if key in honors.EPITHET_BY_ID],
                    personal=saga_content.view(f,self.seed,self.season,self.week),
                    traits=[dict(attribute=ATTRIBUTES[t.attribute],grade=t.grade,
                                 bonus=t.bonus) for t in f.development.traits],
                    points=max(0, f.lv-1 + self.world.kiyun_manuals.get(f.fid,0)
                               - sum(f.mastery.values())), equipped=equipment(f),
                    slots=available_skill_slots(f.lv),
                    skills=[dict(id=k,rank=f.mastery.get(k,0),secret=k in f.development.secret_arts,
                                 **asdict(SKILLS[k]))
                            for k in (*ROLE_SKILLS[f.role],*f.development.secret_arts)
                            if k in SKILLS])

    def train_skill(self, fid, key):
        if self.market_closed():
            raise ValueError('전투 또는 주간 운영이 끝난 뒤 수련하세요.')
        detail = self.member_detail(fid)
        node = next((node for node in detail['skills'] if node['id']==key), None)
        if not node or node['rank']>=3 or detail['level']<node['level'] or not detail['points']:
            raise ValueError('무공 수련 조건을 충족하지 못했습니다.')
        fighter = next(f for f in self.guild.fighters if f.fid==fid)
        fighter.mastery[key] = node['rank']+1
        return self.member_detail(fid)

    def equip(self, fid, keys):
        if self.market_closed():
            raise ValueError('지금은 무공을 장착할 수 없습니다.')
        detail = self.member_detail(fid)
        f = next(f for f in self.guild.fighters if f.fid==fid)
        if len(keys)>detail['slots'] or len(keys)!=len(set(keys)) or not set(keys)<=set(unlocked(f)):
            raise ValueError('해금된 무공을 슬롯 범위 안에서 선택하세요.')
        f.equipped = tuple(keys)
        return self.member_detail(fid)

    def scouting(self, seller_id=None):
        """List rival sects and their roster data visible to the player."""
        rivals = [g for g in self.world.guilds.values() if g.gid != self.guild.gid]
        if seller_id is not None and not any(g.gid == seller_id for g in rivals):
            raise ValueError('다른 문파를 선택하세요.')
        candidates = [
            dict(id=f.fid, name=f.name, role=ROLES[f.role], age=f.age, level=f.lv,
                 ca=round(f.ca,1), pa=round(f.pa,1), role_id=f.role,
                 notable=notables.describe(self.world,f),portrait=portrait_asset(f),
                 wage=f.wage, contract_end=f.contract_end, seller=g.gid,
                 estimate=(market.requirement(self.world,g,f,self.season)
                           or market.estimate(self.world,f,self.guild,self.season)),
                 locked=(f.last_transfer_season == self.season or f.fid in self.world.away(g.gid)))
            for g in rivals if seller_id is None or g.gid == seller_id for f in g.fighters
        ]
        return dict(season=self.season, week=self.week, cash=self.guild.cash,
                    market_closed=self.market_closed(),
                    sects=[dict(id=g.gid, name=g.name, tier=g.tier) for g in rivals],
                    candidates=candidates,
                    exchange_pool=[dict(id=f.fid, name=f.name, role=ROLES[f.role], wage=f.wage,
                                        locked=(f.last_transfer_season == self.season or
                                                f.fid in self.world.away(self.guild.gid)))
                                   for f in self.guild.fighters])

    def transfer_suggestion(self, season, week, seller_id, fighter_id):
        if (season, week) != (self.season, self.week):
            raise ValueError('이적 조건을 다시 불러오세요.')
        if self.market_closed():
            return dict(status='market_closed')
        seller = self.world.guilds.get(seller_id)
        if seller is None or seller is self.guild:
            return dict(status='invalid')
        target = next((f for f in seller.fighters if f.fid == fighter_id), None)
        if target is None:
            return dict(status='invalid')
        if target.last_transfer_season == season or target.fid in self.world.away(seller_id):
            return dict(status='locked')
        return market.suggest_player_offer(self.world,self.guild,seller,target,season)

    def _talk_context(self, season, week, seller_id, fighter_id):
        if (season,week)!=(self.season,self.week):
            raise ValueError('협상 날짜가 변경되었습니다. 이적시장을 다시 확인하세요.')
        if self.market_closed():
            raise ValueError('지금은 이적시장이 열려 있지 않습니다.')
        if type(seller_id) is not int or type(fighter_id) is not int:
            raise ValueError('협상 대상 문파와 문파원을 다시 선택하세요.')
        seller=self.world.guilds.get(seller_id)
        target=next((f for f in seller.fighters if f.fid==fighter_id),None) if seller else None
        if seller is None or seller is self.guild or target is None:
            raise ValueError('이적 대상이 더 이상 상대 문파에 없습니다.')
        return seller,target,(seller_id,fighter_id)

    def transfer_talk_view(self, season, week, seller_id, fighter_id):
        seller,target,key=self._talk_context(season,week,seller_id,fighter_id)
        talk=getattr(self,'transfer_talks',{}).get(key)
        if talk and (talk['season'],talk['week'])==(season,week):
            return dict(talk)
        essential, profile=market.seller_needs(seller,target)
        return dict(status='ready',turn=0,max_turns=4,revision=0,
                    message=('주전 공백을 메울 같은 역할의 문파원을 원합니다.' if essential
                             else '현금과 인재 교환 조건을 검토하겠습니다.'),
                    seller_profile=profile)

    def transfer_bargain(self, season, week, seller_id, fighter_id, fee, exchange):
        seller,target,key=self._talk_context(season,week,seller_id,fighter_id)
        if (type(fee) is not int or fee<0 or type(exchange) is not list
                or len(exchange)>3 or any(type(fid) is not int for fid in exchange)
                or len(set(exchange))!=len(exchange)):
            raise ValueError('현금 금액과 교환 인원 3명 이내를 확인하세요.')
        talk=getattr(self,'transfer_talks',{}).get(key)
        if talk and (talk['season'],talk['week'])!=(season,week):
            talk=None
        if talk and talk['status'] in ('signed','refused','closed'):
            return dict(talk)
        turns=talk['turn'] if talk else 0
        if turns>=4:
            return dict(talk) if talk else dict(status='closed',message='협상이 종료되었습니다.')
        offer=market.Offer(self.guild.gid,seller_id,fighter_id,fee,tuple(exchange))
        reply=market.seller_bargain(self.world,self.guild,seller,target,self.season,offer,turns+1)
        turns+=1
        status=reply['status']
        requested=reply.get('offer')
        if status=='counter' and turns>=4:
            # Last counter may still be accepted, but no additional proposal.
            reply['message']+=' 이번이 마지막 협상 조건입니다.'
        pending=(dict(fee=requested.fee,exchange=list(requested.exchange))
                 if requested else None)
        history=list(talk.get('history',[])) if talk else []
        history.append(dict(turn=turns,offered=dict(fee=fee,exchange=list(exchange)),
                            status=status,message=reply['message'],terms=pending))
        result=dict(status=status,turn=turns,max_turns=4,revision=turns,
                    message=reply['message'],terms=pending,history=history,
                    demands=reply.get('demands',[]),
                    reason=reply.get('reason'),seller_profile=reply.get('seller_profile'))
        self.transfer_talks[key]=result|dict(season=season,week=week)
        return result

    def transfer_bargain_accept(self, season, week, seller_id, fighter_id, revision):
        seller,target,key=self._talk_context(season,week,seller_id,fighter_id)
        talk=getattr(self,'transfer_talks',{}).get(key)
        if (not talk or (talk['season'],talk['week'])!=(season,week)
                or type(revision) is not int or talk['revision']!=revision
                or talk['status'] not in ('accepted','counter') or not talk.get('terms')):
            return dict(status='stale',message='협상 조건이 변경되었습니다. 다시 확인하세요.')
        terms=talk['terms']
        result=self.transfer(season,week,seller_id,fighter_id,
                             terms['fee'],terms['exchange'],commit=True)
        if result['status']=='signed':
            talk['status']='signed'
            talk['message']='양 문파가 계약을 체결했습니다.'
            talk['terms']=None
        else:
            talk['status']='closed'
            talk['message']='이적 조건이 변경되어 협상이 성사되지 않았습니다.'
            talk['terms']=None
        return dict(status=talk['status'],message=talk['message'],transfer=result)

    def transfer_bargain_decline(self, season, week, seller_id, fighter_id, revision):
        _,_,key=self._talk_context(season,week,seller_id,fighter_id)
        talk=getattr(self,'transfer_talks',{}).get(key)
        if (not talk or type(revision) is not int or talk['revision']!=revision
                or (talk['season'],talk['week'])!=(season,week)):
            return dict(status='stale',message='협상 정보를 다시 불러오세요.')
        talk['status']='closed'
        talk['message']='상대의 조건을 거절하고 협상을 종료했습니다.'
        talk['terms']=None
        return dict(talk)

    def transfer(self, season, week, seller_id, fighter_id, fee, exchange, commit=False):
        """Evaluate or settle the submitted terms using the same v15.1 market."""
        if (season, week) != (self.season, self.week):
            raise ValueError('이적 조건을 다시 불러오세요.')
        if self.market_closed():
            return dict(status='market_closed')
        if (type(seller_id) is not int or type(fighter_id) is not int
                or type(fee) is not int or fee < 0 or not isinstance(exchange, list)
                or len(exchange) > 3 or any(type(i) is not int for i in exchange)
                or len(set(exchange)) != len(exchange)):
            return dict(status='invalid')
        offer = market.Offer(self.guild.gid, seller_id, fighter_id, fee, tuple(exchange))
        status, counter = market.offer_status(self.world, offer, self.season)
        if status != 'accepted':
            reply = dict(status=status, counter_fee=counter.fee if counter else None)
            if status == 'insufficient_cash':
                seller = self.world.guilds[seller_id]
                target = next(f for f in seller.fighters if f.fid == fighter_id)
                offered = [f for f in self.guild.fighters if f.fid in exchange]
                reply['cash_limit'] = market.cash_room(self.guild, target, offered)
                reply['cash_shortfall'] = max(0, max(fee, counter.fee) - reply['cash_limit'])
            return reply
        seller = self.world.guilds[seller_id]
        target = next(f for f in seller.fighters if f.fid == fighter_id)
        result = dict(status='accepted', id=fighter_id, name=target.name, fee=fee,
                      exchange=exchange, wage=target.wage, contract_end=target.contract_end,
                      cash_after=self.guild.cash-fee,
                      roster_after=len(self.guild.fighters)+1-len(exchange))
        if commit:
            w = self.world
            w.season_active, w.week_active, w.globalweek = self.season, self.week, self.clock
            if not market.settle(w, offer, self.season):
                return dict(status='unavailable')
            growth_dashboard.record_join(w,target,self.season,self.week,self.guild.gid,'이적 영입')
            w.money.reconcile()
            result['status'] = 'signed'
        return result

    def submit_month(self, season, week, assignment):
        if self.month_run is not None:
            raise ValueError('진행 중인 월간 운영을 먼저 마치세요.')
        if (season,week)!=(self.season,self.week):
            raise ValueError('현재 월간 배치가 아닙니다.')
        month=month_number(week)
        auto_errands='mission_orders' not in assignment and 'missions' not in assignment
        if auto_errands:
            assignment=dict(assignment,mission_orders=[])
        by_id={card['id']:card for card in self.income_mission_board()} if not auto_errands else {}
        self.submit_week(season,week,assignment,auto_errands=auto_errands,manual_defense=True)
        self.month_run=dict(season=season,start_week=week,month=month,
                            end_week=MONTH_ENDS[month-1],reports=[],
                            defense=(assignment.get('defense') or {}).get('members',[]),
                            rest=assignment.get('rest',[]),training=assignment.get('training',[]),
                            orders=None if auto_errands else [dict(order,category=by_id[order['id']]['category'],
                                         difficulty=by_id[order['id']]['difficulty'])
                                    for order in assignment.get('mission_orders') or []],
                            group_mode=assignment.get('group_mode') is True)
        self.continue_month()

    def income_mission_board(self):
        rules=economy.TIERS[self.guild.tier]
        return mission_content.board(self.seed,self.guild.gid,self.season,self.week,
                                     self.guild.tier,rules['mission_gross'],rules['mission_cost'])

    def repeat_monthly_assignment(self, run):
        available={f.fid for f in self.guild.fighters
                   if not f.injured and f.fid not in self.world.away(self.guild.gid)}
        occupied=set()
        orders=[]
        offers=self.income_mission_board() if run['orders'] else []
        open_slots=max(0,2-len(self.world.long_missions[self.guild.gid]))
        for order in (run['orders'] or [])[:open_slots]:
            members=order['members']
            if not set(members)<=available-occupied:
                continue
            matching=[o for o in offers if o['category']==order['category']
                      and o['min_members']<=len(members)<=o['max_members']]
            if matching:
                offer=min(matching,key=lambda o:(abs(o['difficulty']-order['difficulty']),o['id']))
                orders.append(dict(id=offer['id'],members=members,approach=order.get('approach','balanced')))
                offers.remove(offer)
                occupied.update(members)
        rest=[fid for fid in run['rest'] if fid in available-occupied]
        has_site=any(z.owner==self.guild.gid and z.tier==self.guild.tier for z in self.world.zones)
        defense=None
        if run['group_mode'] and has_site and run['defense']:
            free=available-occupied-set(rest)
            crew=[fid for fid in run['defense'] if fid in free]
            eligible=free-set(crew)-set(run['training'])
            reserves=sorted((f for f in self.guild.fighters if f.fid in eligible),
                            key=lambda f:(f.development.squad!='second',-f.ca,f.fid))
            crew.extend(f.fid for f in reserves[:8-len(crew)])
            if len(crew)==8:
                defense=dict(members=crew)
                occupied.update(crew)
        reserved=len(self.world.away(self.guild.gid))+len(occupied)+len(rest)
        training=[fid for fid in run['training'] if fid in available-occupied and fid not in rest]
        return dict(group_mode=run['group_mode'],mission_orders=orders,defense=defense,
                    rest=rest,training=training[:max(0,20-reserved)])

    def continue_month(self):
        run=self.month_run
        while run is not None and self.phase=='report':
            report=self.week_report
            run['reports'].append(report)
            ended=self.season!=run['season'] or self.week>run['end_week']
            if ended or self.world.player_bankrupted:
                last_week=run['end_week'] if ended else report['week']
                self.week_report=summarize(run['reports'],run['month'],last_week)
                self.month_run=None
                return
            self.advance_phase('report')
            self.submit_week(self.season,self.week,self.repeat_monthly_assignment(run),
                             auto_errands=run['orders'] is None,manual_defense=True)

    def submit_week(self, season, week, assignment, *, auto_errands=False, manual_defense=False):
        """Validate a week, then settle it or lock it until its tactical battle ends."""
        if self.phase != 'ready':
            raise ValueError('현재 진행 단계를 마친 뒤 주간 배치를 확정하세요.')
        if (season, week) != (self.season, self.week):
            raise ValueError('이미 처리했거나 현재 주차가 아닙니다.')
        if self.pending_week is not None or (self.battle and self.battle.winner is None):
            raise ValueError('진행 중인 전투를 먼저 끝내세요.')
        if self.world.player_bankrupted:
            raise ValueError('해체된 문파는 주간 배치를 할 수 없습니다.')
        roster = {f.fid: f for f in self.guild.fighters}
        locked=self.world.away(self.guild.gid)
        current=self.world.long_missions[self.guild.gid]
        long_orders=assignment.get('long_orders',[])
        long_actions=assignment.get('long_actions',[])
        if not isinstance(long_orders,list) or not isinstance(long_actions,list):
            raise ValueError('장기 임무 입력 형식이 잘못되었습니다.')
        if len(long_orders)+len(current)>2:
            raise ValueError('장기 임무는 진행 중인 임무를 포함해 주간 최대 두 건입니다.')
        active_tasks={task['id'] for task in current}
        if any(not isinstance(x,dict) for x in long_actions):
            raise ValueError('원정 중간 선택 형식이 잘못되었습니다.')
        if any(type(x.get('id')) is not str for x in long_actions):
            raise ValueError('원정 ID 형식이 올바르지 않습니다.')
        if len(long_actions)!=len({x.get('id') for x in long_actions}):
            raise ValueError('동일한 원정의 결정을 중복 제출했습니다.')
        for action in long_actions:
            if action.get('id') not in active_tasks or action.get('choice') not in ('safe','push','withdraw'):
                raise ValueError('진행 중인 원정의 선택지를 확인하세요.')
        offers={offer['id']:offer for offer in expedition_content.board(
            self.seed,self.guild.gid,self.season,self.week,self.guild.tier,
            economy.TIERS[self.guild.tier]['mission_gross'],
            economy.TIERS[self.guild.tier]['mission_cost'])}
        long_member_ids=[]
        accepted_orders=[]
        used_offers=set()
        for order in long_orders:
            if not isinstance(order,dict) or not isinstance(order.get('members'),list):
                raise ValueError('장기 임무 주문 형식이 잘못되었습니다.')
            if type(order.get('id')) is not str:
                raise ValueError('원정 ID 형식이 올바르지 않습니다.')
            offer=offers.get(order.get('id'))
            if offer is None or offer['id'] in used_offers:
                raise ValueError('이번 주에 없는 원정이거나 같은 원정을 중복 신청했습니다.')
            if order.get('approach','balanced') not in expedition_content.APPROACHES:
                raise ValueError('원정 접근 방식을 다시 확인하세요.')
            member_ids=order['members']
            if (not offer['min_members']<=len(member_ids)<=offer['max_members'] or
                any(type(fid) is not int or fid not in roster for fid in member_ids)):
                raise ValueError('장기 임무 참가 인원이 올바르지 않습니다.')
            long_member_ids+=member_ids
            used_offers.add(offer['id'])
            accepted_orders.append(dict(offer=offer,members=[roster[fid] for fid in member_ids],
                                        approach=order.get('approach','balanced')))
        training = assignment.get('training', [])
        mission_orders = assignment.get('mission_orders')
        if mission_orders is not None:
            if not isinstance(mission_orders,list) or len(mission_orders)>2:
                raise ValueError('주간 수익 임무는 최대 두 건입니다.')
            offers={m['id']:m for m in mission_content.board(
                self.seed,self.guild.gid,self.season,self.week,self.guild.tier,
                economy.TIERS[self.guild.tier]['mission_gross'],
                economy.TIERS[self.guild.tier]['mission_cost'])}
            seen=set()
            missions=[]
            mission_ids=[]
            for order in mission_orders:
                if not isinstance(order,dict) or not isinstance(order.get('members'),list):
                    raise ValueError('임무 주문 형식이 올바르지 않습니다.')
                mid=order.get('id')
                if mid not in offers or mid in seen:
                    raise ValueError('현재 주차에 없는 임무이거나 같은 임무를 중복 신청했습니다.')
                if order.get('approach','balanced') not in mission_content.APPROACHES:
                    raise ValueError('지원하지 않는 임무 접근 방식입니다.')
                team=order['members']
                offer=offers[mid]
                if not offer['min_members']<=len(team)<=offer['max_members']:
                    raise ValueError('선택한 임무의 참가 인원 제한과 맞지 않습니다.')
                if any(not isinstance(fid,int) or isinstance(fid,bool) for fid in team):
                    raise ValueError('문파원 ID가 올바르지 않습니다.')
                seen.add(mid)
                missions.append(team)
        else:
            missions=assignment.get('missions', [])
            mission_ids=assignment.get('mission_ids',list(range(len(missions))))
            if (len(mission_ids)!=len(missions) or
                any(type(i) is not int or not 0<=i<len(MISSIONS) for i in mission_ids) or
                len(set(mission_ids))!=len(mission_ids)):
                raise ValueError('팀마다 서로 다른 임무를 선택하세요.')
            if len(missions)>2 or any(len(team)!=3 for team in missions):
                raise ValueError('기존 수익 임무는 3명씩 최대 두 팀까지 배치할 수 있습니다.')
        if len(missions)+len(long_orders)+len(current)>2:
            raise ValueError('진행 중인 장기 임무를 포함해 주간 임무는 최대 두 건입니다.')
        # Elite mission has one independent slot, even when both income slots are full.
        elite_request=assignment.get('elite_order')
        elite_order=None
        elite_member_ids=[]
        if elite_request is not None:
            if (not isinstance(elite_request,dict) or
                type(elite_request.get('id')) is not str or
                not isinstance(elite_request.get('members'),list)):
                raise ValueError('정예 임무 편성 형식이 올바르지 않습니다.')
            elite_offers={card['id']:card for card in saga_content.decorate_board(
                self.guild,elite_content.board(
                self.seed,self.guild.gid,self.season,self.week,self.guild.tier,
                economy.TIERS[self.guild.tier]['mission_gross'],
                economy.TIERS[self.guild.tier]['mission_cost']),self.season,self.week)}
            offer=elite_offers.get(elite_request['id'])
            if offer is None:
                raise ValueError('이번 주에 제시된 정예 임무가 아닙니다.')
            if elite_request.get('choice','study') not in elite_content.CHOICES:
                raise ValueError('정예 임무 사건 선택지를 확인하세요.')
            elite_member_ids=elite_request['members']
            if (not offer['min_members']<=len(elite_member_ids)<=offer['max_members'] or
                any(type(fid) is not int or fid not in roster for fid in elite_member_ids)):
                raise ValueError('정예 임무에는 문파원 3~5명이 필요합니다.')
            lead=elite_request.get('lead',elite_member_ids[0])
            if type(lead) is not int or lead not in elite_member_ids:
                raise ValueError('정예 임무의 핵심 인물은 참가자 중 한 명이어야 합니다.')
            if offer.get('saga') and lead!=offer['saga_leader']:
                raise ValueError('연속 기연에는 단서를 발견한 문파원이 핵심 인물로 참가해야 합니다.')
            elite_order=dict(offer=offer,
                             members=[roster[fid] for fid in elite_member_ids],
                             lead=roster[lead],
                             choice=elite_request.get('choice','study'))
        defense = assignment.get('defense') or {}
        if not isinstance(defense, dict):
            raise ValueError('방어 배치 형식이 올바르지 않습니다.')
        defenders = defense.get('members', [])
        defense_zone = next((z for z in self.world.zones if z.zid == defense.get('zone')
                             and z.owner == self.guild.gid and z.tier == self.guild.tier), None)
        group_mode = self.interactive and assignment.get('group_mode') is True
        defense_size = 8 if group_mode else 5
        can_defend = (any(z.owner==self.guild.gid and z.tier==self.guild.tier for z in self.world.zones)
                      if group_mode and defense.get('zone') is None else defense_zone is not None)
        if defense and (not can_defend or not isinstance(defenders, list)
                        or len(defenders)!=defense_size or any(type(fid) is not int for fid in defenders)
                        or any(fid in locked for fid in defenders)):
            raise ValueError(f'보유 거점과 수비대 {defense_size}명을 확인하세요.')
        rest = assignment.get('rest', [])
        attack = assignment.get('attack')
        battle_setup = []
        if attack is not None:
            if (not isinstance(attack,dict) or type(attack.get('zone')) is not int or
                    not isinstance(attack.get('setup'),list) or
                    any(not isinstance(slot,dict) or type(slot.get('id')) is not int
                        for slot in attack['setup'])):
                raise ValueError('점령전 문파원 편성이 올바르지 않습니다. 페이지를 새로고침한 뒤 다시 배치하세요.')
            battle_setup = attack['setup']
        combatants = [slot['id'] for slot in battle_setup]
        if attack and group_mode:
            zone = next((z for z in self.world.zones if z.zid == attack['zone']), None)
            if (zone is None or zone.tier != self.guild.tier or zone.owner == self.guild.gid
                    or zone.protected_until > self.clock):
                raise ValueError('지금 공격할 수 없는 구역입니다.')
            if len(combatants)!=8:
                raise ValueError('점령전에는 8명을 배치하세요.')
        active = [*training, *(fid for team in missions for fid in team),
                  *combatants, *defenders, *long_member_ids, *elite_member_ids, *sorted(locked)]
        assigned = [*active, *rest]
        if any(type(fid) is not int for fid in assigned):
            raise ValueError('주간 배치에 올바르지 않은 문파원 번호가 있습니다.')
        assigned_ids = set(assigned)
        if len(assigned_ids) != len(assigned) or not assigned_ids <= roster.keys():
            raise ValueError('문파원이 중복 배치됐거나 현재 명단에 없습니다.')
        if any(roster[fid].injured for fid in active):
            raise ValueError('부상자는 훈련·임무·전투에 배치할 수 없습니다.')
        if len(assigned) > 20:
            raise ValueError('직접 배치할 수 있는 1군은 최대 20명입니다.')
        # Fill empty first-team slots with fit trainees. Injured members recover.
        free = [f for f in economy.old.choose_active(self.guild, True)
                if f.fid not in assigned and not f.injured]
        free += [f for f in roster.values() if f.fid not in assigned and not f.injured and f not in free]
        extra = [f.fid for f in free[:20-len(assigned)]]
        active += extra
        if not manual_defense and len(active) < min(15, sum(not f.injured for f in roster.values())):
            raise ValueError('부상자를 제외한 주간 활동 인원을 최소 15명 배치하세요.')
        first = set(assigned + extra)
        unused = [f for f in roster.values() if f.fid not in first]
        first.update(f.fid for f in unused[:20-len(first)])
        reserve = [f for f in roster.values() if f.fid not in first]
        second = reserve[:economy.MAX_SECOND]
        overflow = reserve[economy.MAX_SECOND:]
        resting = [f for f in roster.values() if f.fid not in active and
                   (f.injured or f not in reserve)]
        errands=sorted(extra,key=lambda fid:(roster[fid].pa-roster[fid].ca,fid))[:economy.ERRAND_LIMIT] if auto_errands else []
        plan = dict(training=[roster[i] for i in training]+[roster[i] for i in extra if i not in errands],
                    errands=[roster[i] for i in errands],
                    missions=[[roster[i] for i in team] for team in missions],
                    mission_orders=(mission_orders or []) if mission_orders is not None else [],
                    long_orders=accepted_orders,long_actions=long_actions,
                    long_active=[roster[fid] for fid in [*sorted(locked),*long_member_ids]],
                    elite_order=elite_order,
                    elite_active=[roster[fid] for fid in elite_member_ids],
                    rest=resting, second=[f for f in second if not f.injured],
                    overflow_bench=[f for f in overflow if not f.injured], attack=[], defend=[roster[i] for i in defenders],
                    scout=[], emergency=[], attack_target=None, attack_won=False,
                    first_ids=first, second_ids={f.fid for f in second},
                    home=defense_zone or max((z for z in self.world.zones if z.owner==self.guild.gid),
                             key=economy.old.zone_value, default=None))
        if plan['home'] is not None:
            plan['home'] = plan['home'].zid
        if mission_orders is not None:
            preparation = sum(max(1, round(offers[order['id']]['cost'] *
                                           (1 + .09*(len(order['members'])-3))))
                              for order in mission_orders)
            preparation += sum(order['offer']['initial_cost'] for order in accepted_orders)
            choices = {action['id']: action['choice'] for action in long_actions}
            preparation += sum(task['weekly_cost'] for task in current
                               if choices.get(task['id']) != 'withdraw')
            if elite_order:
                preparation += elite_order['offer']['cost'] + max(0, len(elite_order['members'])-3)*2
            plan['budget'] = dict(fixed=self.operations_view()['fixed'], preparation=preparation)
        if group_mode:
            plan['group_mode'] = True
            plan['manual_defense'] = manual_defense
        if self.interactive:
            plan['mission_support'] = {
                tuple(f.fid for f in team): min(.06, .01*sum(
                    SKILLS[key].target in ('ally','self') for f in team for key in equipment(f)))
                for team in plan['missions']
            }
        if self.interactive and elite_order is not None:
            # The interactive encounter must finish before the week is settled.
            # Both elite and territory battles may be planned with disjoint teams.
            # Funding is confirmed now so the player never fights for an unfunded job.
            mission_cost=elite_order['offer']['cost']+2*max(0,len(elite_member_ids)-3)
            if self.guild.cash<mission_cost:
                raise ValueError('정예 임무 준비비가 부족합니다.')
            self.pending_week=plan
            self.elite_play=dict(stage='scene',choice=None,attack=attack)
            self.battle=self.zone=self.result=None
            self.practice=False
            self.phase='elite'
        elif attack:
            if group_mode:
                self.start_conquest(plan, [roster[fid] for fid in combatants], zone)
            else:
                self.start(attack['zone'], battle_setup)
            self.pending_week = plan
        else:
            self.battle = self.zone = self.result = None
            self.settle_week(plan=plan)

    def elite_state(self):
        """Small public state for the event UI, never a second game ledger."""
        if self.elite_play is None:
            return None
        if self.pending_week is None or not self.pending_week.get('elite_order'):
            raise AssertionError('정예 임무 진행 데이터가 누락되었습니다.')
        info=playable_elite.briefing(self.pending_week['elite_order'])
        info.update(stage=self.elite_play['stage'],
                    choice=self.elite_play.get('choice'),
                    choice_label=(elite_content.CHOICES[self.elite_play['choice']]['label']
                                  if self.elite_play.get('choice') else None),
                    next_attack=self.elite_play.get('attack') is not None,
                    combat=self.pending_week.get('elite_override'))
        return info

    def elite_inspect(self):
        if self.phase!='elite' or not self.elite_play or self.elite_play['stage']!='scene':
            raise ValueError('현재 조사할 수 있는 정예 임무가 없습니다.')
        self.elite_play['stage']='decision'

    def elite_decide(self, choice):
        if self.phase!='elite' or not self.elite_play or self.elite_play['stage']!='decision':
            raise ValueError('현재 선택할 수 있는 현장 사건이 없습니다.')
        if choice not in elite_content.CHOICES:
            raise ValueError('지원하지 않는 정예 임무 선택지입니다.')
        order=self.pending_week['elite_order']
        self.battle=playable_elite.make_battle(
            self.seed,self.guild.gid,self.season,self.week,order,choice,unit,equipment)
        order['choice']=choice
        self.elite_play['choice']=choice
        self.battle.context['notables']=notables.battle_talents(self.world,self.battle.units.values())
        self.elite_play['stage']='battle'
        self.zone=None
        self.result=None
        self.practice=False

    def elite_finish(self):
        """Commit exactly once after the encounter, then optionally start a zone fight."""
        if (self.phase!='elite' or not self.elite_play or
                self.elite_play['stage']!='aftermath' or
                self.battle is None or self.battle.winner is None or
                self.pending_week is None or 'elite_override' not in self.pending_week):
            raise ValueError('정예 임무 전투를 먼저 완료하세요.')
        plan=self.pending_week
        attack=self.elite_play['attack']
        self.elite_play=None
        self.battle=self.zone=self.result=None
        self.practice=False
        self.phase='ready'
        if attack is not None:
            if plan.get('group_mode'):
                zone = next(z for z in self.world.zones if z.zid==attack['zone'])
                roster = {f.fid:f for f in self.guild.fighters}
                self.start_conquest(plan, [roster[slot['id']] for slot in attack['setup']], zone)
            else:
                self.start(attack['zone'],attack['setup'])
            self.pending_week=plan
        else:
            if plan.get('group_mode'):
                self.settle_group_week(plan)
            else:
                self.settle_week(plan=plan)
                self.pending_week=None

    def battle_state(self):
        b = self.battle
        if b is None:
            return None
        return dict(round=b.round, winner=b.winner, seed=b.seed, practice=self.practice,
                    environment=dict(trend=season_trend(self.seed,self.season),
                                     terrain=zone_terrain(self.zone.zid),
                                     tactic=zone_intelligence(self.world,self.zone)['tactic'])
                    if self.zone is not None else None,
                    kind='elite' if self.elite_play else 'zone',
                    title=(self.pending_week['elite_order']['offer']['title']
                           if self.elite_play else None),
                    units=[dict(id=u.id, side=u.side, role=ROLES[u.role], role_id=u.role, name=u.name,
                                portrait=(f'assets/portraits/{u.portrait_key}' if u.portrait_key else ''), row=u.row,
                                hp=u.hp, max_hp=u.max_hp, skill_ranks=u.skill_ranks, qi=u.qi, max_qi=u.max_qi, damage=u.damage, hit_taken=u.hit_taken,
                                healing=u.healing, prevented=u.prevented,
                                effects=[k for k in u.effects if b.active(u,k)],
                                notable=notables.describe(self.world,next((f for g in self.world.guilds.values() for f in g.fighters if f.fid==u.id),None)) if any(f.fid==u.id for g in self.world.guilds.values() for f in g.fighters) else None,
                                options=b.options(u) if u.side == 0 else {}) for u in b.units.values()],
                    events=b.events, frames=b.frames, orders=b.orders,
                    initiative=[u.id for u in b.initiative()])

    def step(self, commands=None, style='balanced', finish=False):
        if self.battle is None:
            raise ValueError('편성부터 진행하세요.')
        if style not in ('balanced','protect','pressure'):
            raise ValueError('지원하지 않는 전술입니다.')
        self.battle.step(commands, style)
        while finish and self.battle.winner is None:
            self.battle.step(style=style)
        if self.battle.winner is not None:
            if self.elite_play is not None:
                order=self.pending_week['elite_order']
                tier=economy.TIERS[self.guild.tier]
                outcome=playable_elite.verdict(
                    self.seed,self.guild.gid,self.season,self.week,order,
                    self.battle,self.world,tier['base_ca'],tier['base_lv'])
                self.pending_week['elite_override']=outcome
                self.elite_play['stage']='aftermath'
                self.result=dict(elite=True,practice=False,success=self.battle.winner==0,
                                 title=order['offer']['title'],outcome=outcome['outcome_label'],
                                 summary=outcome['narrative'],gross=outcome['gross'],
                                 cost=outcome['cost'],rounds=len(self.battle.frames))
            else:
                self.result = self.apply()

    def apply(self):
        b, w, z = self.battle, self.world, self.zone
        if self.result is not None:
            return self.result
        if self.practice:
            return dict(practice=True, success=b.winner==0, zone=z.zid)
        report = self.settle_week(self.pending_week, b, z)
        self.pending_week = None
        return report['battle']

    @staticmethod
    def group_replay(result):
        if result is None:
            return None
        units = {u['id']: SimpleNamespace(**u) for u in result['units']}
        return SimpleNamespace(winner=result['winner'], units=units, events=result['events'],
                               performance=result.get('performance',[]))

    def settle_group_week(self, plan):
        offense = plan.get('offense_replay')
        zone = self.world.zones[offense['zone']] if offense else None
        self.settle_week(plan, self.group_replay(offense), zone)
        if self.phase!='group' or self.group_play['kind']=='playoff':
            self.pending_week = None

    def open_defense(self, plan, plans, offense_ids, order=None):
        w, gid = self.world, self.guild.gid
        order = economy.old.attack_order(w,plans) if order is None else order
        threats = {}
        for _,attacker,zid in order:
            zone = w.zones[zid]
            if plans[attacker]['attack'] and zone.owner==gid and economy.old.attack_allowed(w,attacker,zone):
                threats.setdefault(zid,(attacker,zid))
        if threats:
            targets = list(threats.values())
            plan['defense_setup'] = dict(targets=targets, order=order,
                                         ai={key: value for key,value in plans.items() if key!=gid})
            self.pending_week = plan
            self.start_defense(plan, targets[0], offense_ids)
        return order

    def attack_crew(self, attacker, attack_plan, excluded=()):
        w=self.world
        invasion=[f for f in attack_plan['attack'] if f.fid not in excluded]
        reserved=w.away(attacker) | {f.fid for key in ('long_active','defend')
                                    for f in attack_plan.get(key,[])}
        reserve=sorted((f for f in economy.old.choose_active(w.guilds[attacker])
                        if not f.injured and f.fid not in reserved
                        and f.fid not in excluded and f not in invasion),
                       key=lambda f:(-f.ca,f.fid))
        return (invasion+reserve)[:8]

    def start_defense(self, plan, threat, offense_ids):
        attacker,zid=threat
        invasion=self.attack_crew(attacker,plan['defense_setup']['ai'][attacker],offense_ids)
        self.begin_group('defense',plan['defend'],self.world.guilds[attacker],
                         self.world.zones[zid],assault=invasion,bench_plan=plan)
        self.group_play['defenseNumber'] = len(plan.get('defense_replays',[]))+1
        self.group_play['defenseTotal'] = len(plan['defense_setup']['targets'])

    def settle_week(self, plan=None, battle=None, zone=None):
        w = self.world
        owners = [z.owner for z in w.zones]
        rank_before, tier_before = self.league_rank(), self.guild.tier
        before = self.guild.cash
        initial = {f.fid: (f.ca,f.lv,f.xp,f.injured) for f in self.guild.fighters}
        initial_training = {f.fid:(w.spells[f.fid].training,w.spells[f.fid].investment)
                            for f in self.guild.fighters}
        season, week = self.season, self.week
        w.season_active, w.week_active, w.globalweek = season, week, self.clock
        defense = plan.get('defense_setup') if plan else None
        contests = []
        if defense:
            targets = defense['targets'] if 'targets' in defense else [(defense['attacker'],defense['zone'])]
            replays = plan.get('defense_replays', [plan.get('defense_replay')])
            contests = [(attacker,zid,self.group_replay(result))
                        for (attacker,zid),result in zip(targets,replays) if result is not None]
        conquest=plan.get('conquest') if plan else None
        frozen=defense['ai'] if contests else plan.get('campaign_ai') if plan else None
        plans=dict(frozen) if frozen is not None else {
            g.gid:economy.prep_plan(w,g,week) for g in w.guilds.values()
            if g is not self.guild or plan is None}
        if plan is not None:
            plans[self.guild.gid] = plan
        ids = set(battle.units) if battle else set()
        duel_replays=[self.group_replay(duel['result']) for duel in conquest['duels']] if conquest else []
        ai_final=self.group_replay(conquest.get('final')) if conquest else None
        for clash in [*duel_replays,ai_final]:
            if clash:
                ids.update(clash.units)
        for p in plans.values():
            for key in ('training','second','overflow_bench','attack','defend','rest','emergency','scout'):
                p[key] = [f for f in p[key] if f.fid not in ids]
            if 'errands' in p:
                p['errands'] = [f for f in p['errands'] if f.fid not in ids]
            p['missions'] = [team for team in p['missions'] if not any(f.fid in ids for f in team)]
            if not 4<=len(p['attack'])<=8 or (zone is not None and p['attack_target'] == zone.zid):
                p['attack'] = []
            if not 4<=len(p['defend'])<=8:
                p['defend'] = []
        plans[self.guild.gid]['attack'] = []
        if zone is not None and zone.owner is not None:
            plans[zone.owner]['defend'] = []
        order=defense['order'] if contests else plan.get('campaign_order') if plan else None
        if conquest and order is not None:
            # Losing challengers cannot subsequently attack the same site off-screen.
            order=[entry for entry in order if entry[2]!=conquest['zone']
                   or (ai_final and entry[1]==conquest['champion'])]
        if plan and plan.get('group_mode') and (plan['defend'] or self.month_run or plan.get('manual_defense')) and not contests:
            order = self.open_defense(plan,plans,ids,order)
            if 'defense_setup' in plan:
                return None
        if plan is not None:
            for f in self.guild.fighters:
                spell = w.spells[f.fid]
                if f.fid in plan['second_ids']:
                    f.development.squad = 'second'
                    spell.second_weeks += 1
                elif f.fid in plan['first_ids']:
                    spell.promotions += int(f.development.squad == 'second')
                    spell.first_weeks += 1
                    f.development.squad = 'first'
                else:
                    f.development.squad = 'overflow'
        # Keep a copy for the report before tactical participants are removed
        # from weekly training and automatic battle rewards.
        guard_post = (dict(zone=plan['home'], all_zones=bool(plan.get('group_mode')),
                           members=[f.name for f in plan['defend']]) if plan and plan['defend'] else None)
        tactical = {(attacker,zid): contest.winner for attacker,zid,contest in contests}
        if ai_final:
            tactical[(conquest['champion'],conquest['zone'])]=int(ai_final.winner==0)
        for clash in [*duel_replays,ai_final]:
            if clash:
                self.record_group_participants(clash, count_conquest=False)
        if contests:
            defenders = {fid for _,_,contest in contests for fid in contest.units}
            for p in plans.values():
                for key in ('training','second','overflow_bench','rest','scout','emergency'):
                    p[key] = [f for f in p[key] if f.fid not in defenders]
                if 'errands' in p:
                    p['errands'] = [f for f in p['errands'] if f.fid not in defenders]
                p['missions'] = [team for team in p['missions'] if not any(f.fid in defenders for f in team)]
        incidents = []
        all_defense = self.guild.gid if plan and plan.get('group_mode') and (
            not defense or 'targets' in defense) else None
        economy.old.attempt_attacks(w,plans,week,incidents=incidents,order=order,tactical=tactical,
                                    all_defense=all_defense,
                                    offscreen=self.resolve_offscreen_attack if self.interactive and _arena_resolver else None)
        defense_results = []
        for attacker,zid,contest in contests:
            post = w.zones[zid]
            held = contest.winner!=1
            participants = self.record_group_participants(contest)
            honors.record_battle(w,contest,self.season,self.week,post.zid,False)
            gross = economy.TIERS[post.tier]['gross']*post.multiplier
            defense_results.append(dict(zone=zid, zone_name=site_details(zid)['name'],
                                        attacker=w.guilds[attacker].name, held=held,
                                        participants=participants, performance=contest.performance,
                                        gross_loss=0 if held else round(7*gross)-round(4*gross)))
            plans[self.guild.gid]['defend'] = []
            plans[attacker]['attack'] = []
        battle_result = self.record_battle(battle, zone) if battle else None
        # Mirror the established partial-week ownership settlement in the report.
        territories = []
        for z in w.zones:
            owned_before = owners[z.zid] == self.guild.gid
            owned_after = z.owner == self.guild.gid
            days = 4*owned_before + 3*owned_after
            if days:
                gross = round(days*economy.TIERS[z.tier]['gross']*z.multiplier)
                territories.append(dict(zone=z.zid, zone_name=site_details(z.zid)['name'], days=days, gross=gross))
        playoff = None
        ledger = w.money
        planned_training_ids = [f.fid for f in (plans[self.guild.gid]['training'] +
                             plans[self.guild.gid]['second'] +
                             plans[self.guild.gid].get('overflow_bench', []))]
        capture_before, start = ledger.capture, len(ledger.entries)
        ledger.capture = True
        try:
            economy.economics_week(w,plans,owners,season,week)
            for g in w.guilds.values():
                w.trim_roster(g,season)
            economy.assert_world(w)
            growth_dashboard.record_week(self,season,week,plan,battle,zone,defense=contests[0][2] if contests else None)
            self.week += 1
            if self.week == 52:
                economy.one_week(w,season,52)
                # Season-close cash already includes this unplayed week.
                for held in w.zones:
                    if held.owner == self.guild.gid:
                        territories.append(dict(zone=held.zid, zone_name=site_details(held.zid)['name'],
                            days=7, gross=round(7*economy.TIERS[held.tier]['gross']*held.multiplier)))
                if plan and plan.get('group_mode') and not w.player_bankrupted:
                    playoff = next((pair for pair in economy.playoff_pairs(w)
                                    if self.guild.gid in pair), None)
                if playoff is None:
                    economy.annual_rollover(w,season,interactive=self.interactive)
                    economy.assert_world(w)
                    self.season += 1
                    self.week = 1
                else:
                    self.week = 51
                    opponent = w.guilds[next(gid for gid in playoff if gid != self.guild.gid)]
                    away = w.away(self.guild.gid)
                    own = sorted((f for f in self.guild.fighters if not f.injured and f.fid not in away),
                                 key=lambda f: (-f.ca, f.fid))[:10]
                    self.begin_group('playoff', own, opponent, pair=playoff)
            entries = [e for e in ledger.entries[start:] if e['guild']==self.guild.gid]
        finally:
            ledger.capture = capture_before
            if not capture_before:
                del ledger.entries[start:]
        members = []
        for f in self.guild.fighters:
            if f.fid not in initial:
                continue
            ca, level, xp, injured = initial[f.fid]
            members.append(dict(id=f.fid, ca_change=round(f.ca-ca,3),
                                levels=f.lv-level, xp_before=xp, xp=f.xp,
                                injured_before=injured, injured=f.injured))
        actual_plan = plans[self.guild.gid]
        training_groups = {}
        for key, description in (('training','집중 훈련'),('second','2군 수련'),
                                 ('overflow_bench','대기 수련')):
            for fighter in actual_plan.get(key,[]):
                training_groups[fighter.fid] = description
        training_rows = []
        for fighter in self.guild.fighters:
            fid = fighter.fid
            if fid not in initial_training:
                continue
            prev_training, prev_invest = initial_training[fid]
            spell = w.spells[fid]
            paid = spell.training-prev_training
            invested = spell.investment-prev_invest
            if not (paid or invested or fid in training_groups):
                continue
            before_ca = initial.get(fid,(fighter.ca,))[0]
            training_rows.append(dict(id=fid,name=fighter.name,
                group=training_groups.get(fid,'기타'),paid=paid,invested=invested,
                ca_change=round(fighter.ca-before_ca,3),
                ca=round(fighter.ca,2),pa=round(fighter.pa,2)))
        training_rows.sort(key=lambda row:(-row['paid'],-row['ca_change'],row['id']))
        training_report = dict(planned_count=len(planned_training_ids),
            funded_count=sum(row['paid']>0 for row in training_rows),
            paid_total=sum(-entry['amount'] for entry in entries
                           if entry['category']=='paid_training'),
            investment_total=sum(-entry['amount'] for entry in entries
                                 if entry['category']=='paid_investment'),
            rows=training_rows,
            note='CA 변동은 해당 주 전체 활동의 실측 결과이며 순수 훈련 효과나 미래 성장 예측이 아닙니다.')
        change = self.guild.cash-before
        assert sum(e['amount'] for e in entries)==change
        if battle_result is not None:
            battle_result['cash_change'] = change
        self.recruitment_attempts.clear()
        self.week_report = dict(season=season, week=week, battle=battle_result,
                                cash_before=before, cash=self.guild.cash, cash_change=change,
                                conquest_duels=[dict(zone=conquest['zone'],winner=w.guilds[duel['winner']].name,
                                    sides=[w.guilds[gid].name for gid in duel['sides']],
                                    performance=replay.performance) for duel,replay in zip(conquest['duels'],duel_replays)] if conquest else [],
                                conquest_final=(dict(zone=conquest['zone'],attacker=w.guilds[conquest['champion']].name,
                                    success=ai_final.winner==0,performance=ai_final.performance) if ai_final else None),
                                tactical_defenses=defense_results,
                                tactical_defense=defense_results[0] if defense_results else None,
                                income=sum(max(0,e['amount']) for e in entries),
                                expenses=sum(max(0,-e['amount']) for e in entries),
                                entries=entries, territories=territories, members=members,
                                training_report=training_report,
                                budget=plans[self.guild.gid].get('budget'),
                                treasury_policy=economy.treasury_policy(w,self.guild),
                                investment_paid=sum(-e['amount'] for e in entries if e['category']=='paid_investment'),
                                missions=plans[self.guild.gid].get('mission_outcomes', []),
                                long_missions=plans[self.guild.gid].get('long_reports', []),
                                elite_missions=plans[self.guild.gid].get('elite_reports', []))
        gid = self.guild.gid
        self.week_report['briefing'] = dict(
            rank_before=rank_before, tier_before=tier_before,
            rank=self.league_rank(), tier=self.guild.tier,
            territories_before=owners.count(gid),
            territories=sum(z.owner == gid for z in w.zones),
            defenses=[dict(attacker=w.guilds[i['attacker']].name, zone=i['zone'], zone_name=site_details(i['zone'])['name'],
                           held=not i['won']) for i in incidents if i['defender'] == gid],
            defense_plan=guard_post,
            next=self.next_week_briefing(season))
        if self.interactive and playoff is None:
            self.phase = 'report'
        return self.week_report

    def record_battle(self, battle, zone):
        w = self.world
        victory = battle.winner == 0
        released = None
        self.guild.attacks += 1
        if victory:
            owned = [z for z in w.zones if z.owner == self.guild.gid]
            if len(owned) >= economy.CAP[self.guild.tier]:
                dropped = min(owned,key=economy.old.zone_value)
                dropped.owner = None
                released = dropped.zid
            zone.owner = self.guild.gid
            zone.protected_until = self.clock+2
            self.guild.attack_wins += 1
            self.guild.score += 4
        elif zone.owner is not None:
            defender = w.guilds[zone.owner]
            defender.defense_wins += 1
            defender.score += 2
        participants = self.record_group_participants(battle)
        honors.record_battle(w,battle,self.season,self.week,zone.zid,victory)
        return dict(practice=False,success=victory,zone=zone.zid,zone_name=site_details(zone.zid)['name'],owner=zone.owner,
                    released=released,participants=participants,performance=getattr(battle,'performance',[]))

    def record_group_participants(self, battle, *, count_conquest=True, award_experience=True):
        w = self.world
        participants = []
        for g in w.guilds.values():
            for f in g.fighters:
                u = battle.units.get(f.fid)
                if not u:
                    continue
                xp = 12 + min(20,u.actions*2) + (8 if u.side == battle.winner else 0)
                if award_experience:
                    economy.old.advance_experience(f,xp)
                promoted=notables.record_battle(w,f,battle.winner==u.side,
                    sum(1 for e in battle.events if e['kind']=='knockout' and e['actor']==u.id),
                    eligible=count_conquest and g is self.guild)
                injury_risk = economy.medical_injury_multiplier(w,g)
                if not u.hp and (injury_risk==1 or w.rng.random() >= 1-injury_risk):
                    # Week-end processing deducts one recovery week.
                    f.injured = max(f.injured,3)
                if g is self.guild and award_experience:
                    w.spells[f.fid].battle_weeks += 1
                participants.append(dict(id=f.fid,name=f.name,side=u.side,xp=xp,
                                         legendary_awakened=bool(promoted),injured=max(0,f.injured-1)))
        return participants
