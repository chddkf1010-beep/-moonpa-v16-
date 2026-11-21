"""Connect the tactical battle to an in-memory v15.1 campaign."""
from dataclasses import asdict

import moonpa_economy_v15_1 as economy
from moonpa_growth import available_skill_slots
from combat import Battle, SKILLS, ROLE_SKILLS, Unit

ROLES = ('수호형', '무인형', '사수형', '주술형', '치유형', '암살형')


def unlocked(f):
    return tuple(key for key in ROLE_SKILLS[f.role] if f.lv >= SKILLS[key].level)


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
    return Unit(f.fid, side, f.role, f'{ROLES[f.role]} #{f.fid}', row, attrs, f.lv,
                tuple(loadout), traits=tuple(t.attribute for t in f.development.traits if t.grade == 3))


class Campaign:
    def __init__(self, seed=16):
        self.seed = seed
        self.world = economy.World15(seed, 'baseline')
        for week in range(1, 53):
            economy.one_week(self.world, 0, week)
        economy.annual_rollover(self.world, 0)
        self.guild = economy.install_player(self.world, 'balanced')
        self.season, self.week = 1, 1
        self.battle = None
        self.zone = None
        self.result = None
        self.practice = False
        self.pending_week = None
        self.week_report = None

    def overview(self):
        available = [f for f in self.guild.fighters if not f.injured]
        ready = {f.fid for f in lineup(available)}
        return dict(season=self.season, week=self.week, seed=self.seed, guild=self.guild.gid,
                    cash=self.guild.cash, tier=self.guild.tier,
                    rank=1+sum((g.score,g.strength(),-g.gid) >
                               (self.guild.score,self.guild.strength(),-self.guild.gid)
                               for g in self.world.guilds.values() if g.tier == self.guild.tier),
                    week_report=self.week_report, week_pending=self.pending_week is not None,
                    dead=self.world.player_bankrupted,
                    roster=[dict(id=f.fid, role=ROLES[f.role], role_id=f.role, ca=round(f.ca, 1),
                                 lv=f.lv, xp=f.xp, fatigue=f.fatigue, injured=f.injured,
                                 skills=unlocked(f), slots=available_skill_slots(f.lv),
                                 recommended=f.fid in ready) for f in self.guild.fighters],
                    zones=[dict(id=z.zid, owner=z.owner, value=round(economy.old.zone_value(z)),
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
        if self.world.player_bankrupted or self.week >= 52:
            raise ValueError('현재 출전할 수 없습니다.')
        zone = next((z for z in self.world.zones if z.zid == zone_id), None)
        if zone is None or zone.tier != self.guild.tier or zone.owner == self.guild.gid or zone.protected_until > self.clock:
            raise ValueError('지금 공격할 수 없는 구역입니다.')
        roster = {f.fid:f for f in self.guild.fighters if not f.injured}
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
                units.append(unit(f, 1, 'front' if i < 2 else 'back', unlocked(f)))
            else:
                role = (0, 1, 4, 5, 3)[i]
                units.append(Unit(-1-i, 1, role, f'구역 수비대 {i+1}', 'front' if i < 2 else 'back',
                                  [60]*8, 1, ROLE_SKILLS[role][:1]))
        self.battle = Battle(units, self.seed*1000+zone_id+self.clock*100_000)
        self.zone, self.practice, self.result = zone, practice, None

    def submit_week(self, season, week, assignment):
        """Validate a week, then settle it or lock it until its tactical battle ends."""
        if (season, week) != (self.season, self.week):
            raise ValueError('이미 처리했거나 현재 주차가 아닙니다.')
        if self.pending_week is not None or (self.battle and self.battle.winner is None):
            raise ValueError('진행 중인 전투를 먼저 끝내세요.')
        if self.world.player_bankrupted:
            raise ValueError('해체된 문파는 주간 배치를 할 수 없습니다.')
        roster = {f.fid: f for f in self.guild.fighters}
        training = assignment.get('training', [])
        missions = assignment.get('missions', [])
        rest = assignment.get('rest', [])
        attack = assignment.get('attack')
        battle_setup = attack['setup'] if attack else []
        if len(missions) > 2 or any(len(team) != 3 for team in missions):
            raise ValueError('수익 임무는 3명씩 최대 두 팀까지 배치할 수 있습니다.')
        combatants = [slot['id'] for slot in battle_setup]
        active = [*training, *(fid for team in missions for fid in team), *combatants]
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
                    rest=resting, second=[f for f in second if not f.injured],
                    overflow_bench=[f for f in overflow if not f.injured], attack=[], defend=[],
                    scout=[], emergency=[], attack_target=None, attack_won=False,
                    first_ids=first, second_ids={f.fid for f in second},
                    home=max((z for z in self.world.zones if z.owner==self.guild.gid),
                             key=economy.old.zone_value, default=None))
        if plan['home'] is not None:
            plan['home'] = plan['home'].zid
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
                    units=[dict(id=u.id, side=u.side, role=ROLES[u.role], name=u.name, row=u.row,
                                hp=u.hp, max_hp=u.max_hp, qi=u.qi, max_qi=u.max_qi, damage=u.damage,
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
        requested_missions = plans[self.guild.gid]['missions'].copy()
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
                economy.annual_rollover(w,season)
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
        self.week_report = dict(season=season, week=week, battle=battle_result,
                                cash_before=before, cash=self.guild.cash, cash_change=change,
                                income=sum(max(0,e['amount']) for e in entries),
                                expenses=sum(max(0,-e['amount']) for e in entries),
                                entries=entries, territories=territories, members=members,
                                missions=[dict(members=[f.fid for f in team],
                                               funded=team not in plans[self.guild.gid].get('unfunded_missions', []))
                                          for team in requested_missions])
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
                if not u.hp:
                    # Week-end processing deducts one recovery week.
                    f.injured = max(f.injured,3)
                if u.side == 0:
                    w.spells[f.fid].battle_weeks += 1
                participants.append(dict(id=f.fid,side=u.side,xp=xp,fatigue=fatigue,
                                         injured=max(0,f.injured-1)))
        return dict(practice=False,success=victory,zone=zone.zid,owner=zone.owner,
                    released=released,participants=participants)
