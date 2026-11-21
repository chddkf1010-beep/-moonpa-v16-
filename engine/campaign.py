"""Connect the tactical battle to an in-memory v15.1 campaign."""
from dataclasses import asdict

import moonpa_economy_v15_1 as economy
import moonpa_market as market
from moonpa_names import preference_multiplier
from moonpa_growth import available_skill_slots, WEIGHTS, ATTRIBUTES, observed_ability, observed_potential
import moonpa_missions as mission_content
import moonpa_long_missions as expedition_content
import moonpa_elite as elite_content
import moonpa_sagas as saga_content
from combat import Battle, SKILLS, ROLE_SKILLS, SECRET_SKILLS, Unit
from moonpa_portraits import portrait_asset

FACILITIES = {'training': ('훈련소', 240, '훈련 성장 +8%'),
              'estate': ('장원', 320, '주간 수입 +20냥 · FA 계약금 4% 할인'),
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


class Campaign:
    def __init__(self, seed=16, interactive=False):
        self.seed = seed
        self.world = economy.World15(seed, 'baseline')
        for week in range(1, 53):
            economy.one_week(self.world, 0, week)
        economy.annual_rollover(self.world, 0)
        self.guild = economy.install_player(self.world, 'balanced', founder_count=15 if interactive else 20)
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
        self.week_report = None
        self.recruitment_attempts = {}

    def overview(self):
        away=self.world.away(self.guild.gid)
        available = [f for f in self.guild.fighters if not f.injured and f.fid not in away]
        ready = {f.fid for f in lineup(available)}
        return dict(season=self.season, week=self.week, seed=self.seed, guild=self.guild.gid,
                    cash=self.guild.cash, renown=round(self.guild.renown,2), phase=self.phase,
                    facilities=self.facility_view(),
                    draft=self.draft_view() if self.phase=='draft' else None, tier=self.guild.tier,
                    rank=1+sum((g.score,g.strength(),-g.gid) >
                               (self.guild.score,self.guild.strength(),-self.guild.gid)
                               for g in self.world.guilds.values() if g.tier == self.guild.tier),
                    week_report=self.week_report, week_pending=self.pending_week is not None,
                    dead=self.world.player_bankrupted,
                    guild_name=self.guild.name,
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
                                 portrait=portrait_asset(f), expedition=(f.fid in away),
                                 role=ROLES[f.role], role_id=f.role, ca=round(f.ca, 1),
                                  kiyun_manuals=self.world.kiyun_manuals.get(f.fid,0),
                                 personal_title=f.development.personal_title,
                                 saga=saga_content.view(f,self.seed,self.season,self.week)['saga'],
                                 lv=f.lv, xp=f.xp, contract_end=f.contract_end, fatigue=f.fatigue, injured=f.injured,
                                 skills=unlocked(f), equipped=equipment(f), slots=available_skill_slots(f.lv),
                                 recommended=f.fid in ready) for f in self.guild.fighters],
                    missions=[dict(id=i, name=name, people=3,
                                   cost=economy.TIERS[self.guild.tier]['mission_cost'],
                                   base_reward=economy.TIERS[self.guild.tier]['mission_gross'])
                              for i, name in enumerate(MISSIONS)],
                    zones=[dict(id=z.zid, owner=z.owner,
                                owner_name=(self.world.guilds[z.owner].name if z.owner is not None else '수비대'),
                                value=round(economy.old.zone_value(z)),
                                selectable=z.owner != self.guild.gid and z.protected_until <= self.clock)
                           for z in self.world.zones if z.tier == self.guild.tier],
                    skills={key:asdict(skill) for key, skill in SKILLS.items()},
                    battle=self.battle_state(), result=self.result)

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
        self.battle = Battle(units, self.seed*1000+zone_id+self.clock*100_000)
        self.zone, self.practice, self.result = zone, practice, None

    def facility_view(self):
        levels = self.world.facilities.get(self.guild.gid, {})
        return [dict(id=k, name=name, level=levels.get(k,0), max=5, per_level=effect,
                     current_value=(levels.get(k,0) * {'training':8,'estate':20,'medical':12}[k]),
                     next_value=(min(5,levels.get(k,0)+1) * {'training':8,'estate':20,'medical':12}[k]),
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
            self.draft_picks.append(f.name)

    def draft_view(self):
        return dict(round=self.draft_round, position=self.draft_cursor+1, picks=self.draft_picks,
                    roster_full=len(self.guild.fighters)>=economy.MAX_ROSTER,
                    candidates=[dict(id=f.fid,name=f.name,role=ROLES[f.role],age=f.age,ca=round(f.ca,1),
                                     pa=round(f.pa,1),wage=f.wage) for f in self.draft_pool])

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
        return dict(season=self.season, week=self.week, cash=self.guild.cash,
                    terms_years=list(range(1, 6)), normal_roster_limit=economy.MAX_ROSTER, roster_count=len(self.guild.fighters),
                    roster_limit=economy.MAX_TEMP_ROSTER,
                    candidates=[self.free_agent_quote(f) for f in self.world.fa if f.age <= 42])

    def free_agent_quote(self, fighter):
        terms = self.world.free_agent_terms(self.guild, fighter)
        reason = terms.pop('reason')
        if self.market_closed():
            reason = 'market_closed'
        elif self.recruitment_attempts.get(fighter.fid) == self.clock:
            reason = 'declined_this_week'
        return dict(id=fighter.fid, name=fighter.name, role=ROLES[fighter.role],
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
        return dict(status='signed', id=fighter_id, name=fighter.name, fee=quote['fee'],
                    wage=fighter.wage, years=years, contract_end=fighter.contract_end,
                    cash=self.guild.cash)

    def member_detail(self, fid):
        f = next((f for f in self.guild.fighters if f.fid == fid), None)
        if f is None:
            raise ValueError('현재 문파 명단에서 찾을 수 없습니다.')
        return dict(id=f.fid, name=f.name, role=ROLES[f.role], ca=round(f.ca, 1),
                    pa=round(f.pa, 1), age=f.age, level=f.lv, wage=f.wage,
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
        rest = assignment.get('rest', [])
        attack = assignment.get('attack')
        battle_setup = attack['setup'] if attack else []
        combatants = [slot['id'] for slot in battle_setup]
        active = [*training, *(fid for team in missions for fid in team),
                  *combatants, *long_member_ids, *elite_member_ids, *sorted(locked)]
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
                    overflow_bench=[f for f in overflow if not f.injured], attack=[], defend=[],
                    scout=[], emergency=[], attack_target=None, attack_won=False,
                    first_ids=first, second_ids={f.fid for f in second},
                    home=max((z for z in self.world.zones if z.owner==self.guild.gid),
                             key=economy.old.zone_value, default=None))
        if plan['home'] is not None:
            plan['home'] = plan['home'].zid
        if self.interactive:
            plan['mission_support'] = {
                tuple(f.fid for f in team): min(.06, .01*sum(
                    SKILLS[key].target in ('ally','self') for f in team for key in equipment(f)))
                for team in plan['missions']
            }
        if attack:
            self.start(attack['zone'], battle_setup)
            self.pending_week = plan
        else:
            self.battle = self.zone = self.result = None
            self.settle_week(plan=plan)

    def battle_state(self):
        b = self.battle
        if b is None:
            return None
        return dict(round=b.round, winner=b.winner, seed=b.seed, practice=self.practice,
                    units=[dict(id=u.id, side=u.side, role=ROLES[u.role], role_id=u.role, name=u.name,
                                portrait=(f'assets/portraits/{u.portrait_key}' if u.portrait_key else ''), row=u.row,
                                hp=u.hp, max_hp=u.max_hp, skill_ranks=u.skill_ranks, qi=u.qi, max_qi=u.max_qi, damage=u.damage,
                                healing=u.healing, prevented=u.prevented,
                                effects=[k for k in u.effects if b.active(u,k)],
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
        economy.old.attempt_attacks(w,plans,week)
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
        ledger = w.money
        capture_before, start = ledger.capture, len(ledger.entries)
        ledger.capture = True
        try:
            economy.economics_week(w,plans,owners,season,week)
            for g in w.guilds.values():
                w.trim_roster(g,season)
            economy.assert_world(w)
            self.week += 1
            if self.week == 52:
                economy.one_week(w,season,52)
                economy.annual_rollover(w,season,interactive=self.interactive)
                economy.assert_world(w)
                self.season += 1
                self.week = 1
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
                                missions=plans[self.guild.gid].get('mission_outcomes', []),
                                long_missions=plans[self.guild.gid].get('long_reports', []),
                                elite_missions=plans[self.guild.gid].get('elite_reports', []))
        if self.interactive:
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
                fatigue = min(35, 8 + u.actions + round(12*u.hit_taken/u.max_hp))
                f.fatigue = min(100,f.fatigue+fatigue)
                medical = w.facilities.get(g.gid,{}).get('medical',0)
                if not u.hp and (not medical or w.rng.random() >= .12*medical):
                    # Week-end processing deducts one recovery week.
                    f.injured = max(f.injured,3)
                if u.side == 0:
                    w.spells[f.fid].battle_weeks += 1
                participants.append(dict(id=f.fid,name=f.name,side=u.side,xp=xp,fatigue=fatigue,
                                         injured=max(0,f.injured-1)))
        return dict(practice=False,success=victory,zone=zone.zid,owner=zone.owner,
                    released=released,participants=participants)
