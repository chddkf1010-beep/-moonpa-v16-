"""Connect the tactical battle to an in-memory v15.1 campaign."""
from dataclasses import asdict
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
from combat_environment import season_trend, zone_terrain, defending_style, combat_context, STYLES
import moonpa_notables as notables
from moonpa_portraits import portrait_asset, portrait_profile

FACILITIES = {'training': ('훈련소', 240, '훈련 성장 +8%'),
              'estate': ('장원', 320, '레벨별 누적 주간 수입 증가 · FA 계약금 레벨당 4% 할인'),
              'medical': ('의료시설', 200, '부상 발생 확률 12% 감소')}

MISSIONS = ('표국 호송', '산길 순찰', '약재 운송', '마을 경비')

ROLES = ('수호형', '무인형', '사수형', '주술형', '치유형', '암살형')


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
    return dict(terrain=zone_terrain(zone.zid), tactic=style, enemy_lineup=members)


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
        self.recruitment_attempts = {}
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
        return dict(season=self.season, week=self.week, seed=self.seed, guild=self.guild.gid,
                    season_trend=season_trend(self.seed,self.season), cash=self.guild.cash, renown=round(self.guild.renown,2), phase=self.phase,
                    strategy=self.guild.strategy,
                    facilities=self.facility_view(),
                    draft=self.draft_view() if self.phase=='draft' else None, tier=self.guild.tier,
                    rank=self.league_rank(), operations=self.operations_view(),
                    treasury=self.treasury_view(),
                    league=self.league_view(),
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
                                 lv=f.lv, xp=f.xp, contract_end=f.contract_end, fatigue=f.fatigue, injured=f.injured,
                                 skills=unlocked(f), equipped=equipment(f), slots=available_skill_slots(f.lv),
                                 recommended=f.fid in ready) for f in self.guild.fighters],
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
                    saved_attack=getattr(self.world,'prebattle_plans',{}).get('attack'))

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
                                 score=round(g.score, 2), strength=round(g.strength(), 1),
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
                    zones=[dict(id=z.zid,tier=z.tier,value=round(economy.old.zone_value(z)),
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
        return dict(clock=self.clock, fixed=g.wage_total()+economy.TIERS[g.tier]['hall'],
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
        fixed = g.wage_total() + tier['hall']
        offers = mission_content.board(self.seed,g.gid,self.season,self.week,g.tier,
                                       tier['mission_gross'],tier['mission_cost'])
        mission = min((offer for offer in offers if offer['min_members'] <= ready
                       and offer['cost'] <= max(0,g.cash-fixed)),
                      key=lambda offer: (offer['cost'],offer['id']), default=None)
        open_zones = [z for z in w.zones if z.tier == g.tier and z.protected_until <= self.clock]
        target = max((z for z in open_zones if z.owner is None),
                     key=economy.old.zone_value, default=None)
        return dict(stage='week', week=self.week, ready=ready, injured=len(injured), away=len(away),
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

    def begin_group(self, kind, own, rival, zone=None, pair=None):
        mode = 10 if kind == 'playoff' else 8
        terrain = {'mountain': 'gate', 'fortress': 'gate', 'gorge': 'gate',
                   'river': 'river'}.get(zone_terrain(zone.zid)['id'], 'field') if zone else 'field'
        front = 5 if mode == 10 else {'field': 5, 'gate': 3, 'river': 4}[terrain]
        roles = ('guard', 'blade', 'bow', 'hex', 'heal', 'dash')
        priority = (0, 1, 5, 3, 2, 4)

        def fit(guild):
            away = self.world.away(guild.gid)
            return sorted((f for f in guild.fighters if not f.injured and f.fid not in away),
                          key=lambda f: (-f.ca, f.fid))[:mode]

        def place(fighters):
            roster = [dict(id=f.fid, name=f.name, role=roles[f.role],
                           strength=round(max(.55, min(2, f.ca/110)), 3)) for f in fighters]
            roster.sort(key=lambda u: priority.index(roles.index(u['role'])))
            return [dict(u, line='front' if i < front else 'back',
                         slot=i if i < front else i-front) for i, u in enumerate(roster)]

        team = place(own)
        captain, deputy = (team[0]['id'] if team else None,
                           team[1]['id'] if len(team)>1 else None)
        saved = getattr(self.world,'prebattle_plans',{}).get('attack',{})
        if zone and (saved.get('season'),saved.get('week'),saved.get('zone_id')) == (
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
        enemy = place(fit(rival)) if rival else []
        if zone and not enemy:
            enemy = [dict(id=-i-1, name=f'구역 수비대 {i+1}', role=roles[priority[i%6]],
                          strength=.72, line='front' if i < front else 'back',
                          slot=i if i < front else i-front) for i in range(mode)]
        enemy_arts = {'당문': ['rain','poison'], '소림': ['lotus','mercy'],
                      '무당': ['wall','silence']}.get(rival.name if rival else '',
                                                       ['wing','turtle'])
        self.group_play = dict(kind=kind, match=f'{self.season}:{self.week}:{kind}',
                               zone=zone.zid if zone else None, pair=pair,
                               mode=mode, terrain=terrain, team=team, enemyRoster=enemy,
                               captain=captain, deputy=deputy,
                               sectNames=[self.guild.name, rival.name if rival else '구역 수비대'],
                               enemyArts=enemy_arts)
        self.phase = 'group'

    def finish_group(self, match, result):
        group = self.group_play
        if self.phase != 'group' or group is None or match != group['match']:
            raise ValueError('진행 중인 단체전을 다시 불러오세요.')
        winner = result['winner']
        if group['kind'] == 'territory':
            zone = next(z for z in self.world.zones if z.zid == group['zone'])
            units = {u['id']: SimpleNamespace(**u) for u in result['units']}
            battle = SimpleNamespace(winner=winner, units=units, events=result['events'])
            self.settle_week(self.pending_week, battle, zone)
            self.pending_week = None
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
                                 tier_before=tier_before, tier=self.guild.tier)
        report['briefing'].update(tier=self.guild.tier, rank=self.league_rank(),
                                  territories=sum(z.owner==self.guild.gid for z in self.world.zones),
                                  next=self.next_week_briefing(report['season']))

    def facility_view(self):
        levels = self.world.facilities.get(self.guild.gid, {})
        return [dict(id=k, name=name, level=levels.get(k,0), max=5, per_level=effect,
                     current_value=(economy.estate_weekly_income(levels.get(k,0)) if k=='estate' else levels.get(k,0)*{'training':8,'medical':12}[k]),
                     next_value=(economy.estate_weekly_income(min(5,levels.get(k,0)+1)) if k=='estate' else min(5,levels.get(k,0)+1)*{'training':8,'medical':12}[k]),
                     next_cost=base*(levels.get(k,0)+1) if levels.get(k,0)<5 else None)
                for k,(name,base,effect) in FACILITIES.items()]

    def upgrade(self, key):
        if not self.interactive or self.phase != 'ready' or self.market_closed() or key not in FACILITIES:
            raise ValueError('지금은 건축물을 올릴 수 없습니다.')
        levels = self.world.facilities[self.guild.gid]
        level = levels[key]
        cost = FACILITIES[key][1]*(level+1)
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

    def submit_week(self, season, week, assignment):
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
        if defense and (defense_zone is None or not isinstance(defenders, list)
                        or len(defenders) != 5 or any(type(fid) is not int for fid in defenders)
                        or any(fid in locked for fid in defenders)):
            raise ValueError('보유 구역과 방어 인원 5명을 확인하세요.')
        rest = assignment.get('rest', [])
        attack = assignment.get('attack')
        battle_setup = attack['setup'] if attack else []
        combatants = [slot['id'] for slot in battle_setup]
        group_mode = self.interactive and assignment.get('group_mode') is True
        if attack and group_mode:
            zone = next((z for z in self.world.zones if z.zid == attack['zone']), None)
            if (zone is None or zone.tier != self.guild.tier or zone.owner == self.guild.gid
                    or zone.protected_until > self.clock):
                raise ValueError('지금 공격할 수 없는 구역입니다.')
            if len(combatants) != 8:
                raise ValueError('점령전에는 8명을 배치하세요.')
        active = [*training, *(fid for team in missions for fid in team),
                  *combatants, *defenders, *long_member_ids, *elite_member_ids, *sorted(locked)]
        assigned = [*active, *rest]
        if len(set(assigned)) != len(assigned) or not set(assigned) <= roster.keys():
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
        if len(active) < min(15, sum(not f.injured for f in roster.values())):
            raise ValueError('부상자를 제외한 주간 활동 인원을 최소 15명 배치하세요.')
        first = set(assigned + extra)
        unused = [f for f in roster.values() if f.fid not in first]
        first.update(f.fid for f in unused[:20-len(first)])
        reserve = [f for f in roster.values() if f.fid not in first]
        second = reserve[:economy.MAX_SECOND]
        overflow = reserve[economy.MAX_SECOND:]
        resting = [f for f in roster.values() if f.fid not in active and
                   (f.injured or f not in reserve)]
        plan = dict(training=[roster[i] for i in [*training, *extra]],
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
                self.begin_group('territory', [roster[fid] for fid in combatants],
                                 self.world.guilds.get(zone.owner), zone)
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
                self.begin_group('territory', [roster[slot['id']] for slot in attack['setup']],
                                 self.world.guilds.get(zone.owner), zone)
            else:
                self.start(attack['zone'],attack['setup'])
            self.pending_week=plan
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
                                hp=u.hp, max_hp=u.max_hp, skill_ranks=u.skill_ranks, qi=u.qi, max_qi=u.max_qi, damage=u.damage,
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

    def settle_week(self, plan=None, battle=None, zone=None):
        w = self.world
        owners = [z.owner for z in w.zones]
        rank_before, tier_before = self.league_rank(), self.guild.tier
        before = self.guild.cash
        initial = {f.fid: (f.ca,f.lv,f.xp,f.fatigue,f.injured) for f in self.guild.fighters}
        season, week = self.season, self.week
        w.season_active, w.week_active, w.globalweek = season, week, self.clock
        plans = {g.gid:economy.prep_plan(w,g,week) for g in w.guilds.values()
                 if g is not self.guild or plan is None}
        if plan is not None:
            plans[self.guild.gid] = plan
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
        ids = set(battle.units) if battle else set()
        for p in plans.values():
            for key in ('training','second','overflow_bench','attack','defend','rest','emergency','scout'):
                p[key] = [f for f in p[key] if f.fid not in ids]
            p['missions'] = [team for team in p['missions'] if not any(f.fid in ids for f in team)]
            if len(p['attack']) != 5 or (zone is not None and p['attack_target'] == zone.zid):
                p['attack'] = []
            if len(p['defend']) != 5:
                p['defend'] = []
        plans[self.guild.gid]['attack'] = []
        if zone is not None and zone.owner is not None:
            plans[zone.owner]['defend'] = []
        incidents = []
        economy.old.attempt_attacks(w,plans,week,incidents=incidents)
        battle_result = self.record_battle(battle, zone) if battle else None
        # Mirror the established partial-week ownership settlement in the report.
        territories = []
        for z in w.zones:
            owned_before = owners[z.zid] == self.guild.gid
            owned_after = z.owner == self.guild.gid
            days = 4*owned_before + 3*owned_after
            if days:
                gross = round(days*economy.TIERS[z.tier]['gross']*z.multiplier)
                territories.append(dict(zone=z.zid, days=days, gross=gross))
        playoff = None
        ledger = w.money
        capture_before, start = ledger.capture, len(ledger.entries)
        ledger.capture = True
        try:
            economy.economics_week(w,plans,owners,season,week)
            for g in w.guilds.values():
                w.trim_roster(g,season)
            economy.assert_world(w)
            growth_dashboard.record_week(self,season,week,plan,battle,zone)
            self.week += 1
            if self.week == 52:
                economy.one_week(w,season,52)
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
            ca, level, xp, fatigue, injured = initial[f.fid]
            members.append(dict(id=f.fid, ca_change=round(f.ca-ca,3),
                                levels=f.lv-level, xp_before=xp, xp=f.xp,
                                fatigue_change=f.fatigue-fatigue, fatigue=f.fatigue,
                                injured_before=injured, injured=f.injured))
        change = self.guild.cash-before
        assert sum(e['amount'] for e in entries)==change
        if battle_result is not None:
            battle_result['cash_change'] = change
        self.recruitment_attempts.clear()
        self.week_report = dict(season=season, week=week, battle=battle_result,
                                cash_before=before, cash=self.guild.cash, cash_change=change,
                                income=sum(max(0,e['amount']) for e in entries),
                                expenses=sum(max(0,-e['amount']) for e in entries),
                                entries=entries, territories=territories, members=members,
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
            defenses=[dict(attacker=w.guilds[i['attacker']].name, zone=i['zone'],
                           held=not i['won']) for i in incidents if i['defender'] == gid],
            defense_plan=dict(zone=plans[gid]['home'], members=[f.name for f in plans[gid]['defend']])
                         if plans[gid]['defend'] else None,
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
        participants = []
        for g in w.guilds.values():
            for f in g.fighters:
                u = battle.units.get(f.fid)
                if not u:
                    continue
                xp = 12 + min(20,u.actions*2) + (8 if u.side == battle.winner else 0)
                economy.old.advance_experience(f,xp)
                promoted=notables.record_battle(w,f,battle.winner==u.side,
                    sum(1 for e in battle.events if e['kind']=='knockout' and e['actor']==u.id),
                    eligible=u.side==0)
                fatigue = min(35, 8 + u.actions + round(12*u.hit_taken/u.max_hp))
                f.fatigue = min(100,f.fatigue+fatigue)
                medical = w.facilities.get(g.gid,{}).get('medical',0)
                if not u.hp and (not medical or w.rng.random() >= .12*medical):
                    # Week-end processing deducts one recovery week.
                    f.injured = max(f.injured,3)
                if u.side == 0:
                    w.spells[f.fid].battle_weeks += 1
                participants.append(dict(id=f.fid,name=f.name,side=u.side,xp=xp,fatigue=fatigue,
                                         legendary_awakened=bool(promoted),injured=max(0,f.injured-1)))
        honors.record_battle(w,battle,self.season,self.week,zone.zid,victory)
        return dict(practice=False,success=victory,zone=zone.zid,owner=zone.owner,
                    released=released,participants=participants)
