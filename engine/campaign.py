"""Connect the tactical battle to an in-memory v15.1 campaign."""
from dataclasses import asdict

import moonpa_economy_v15_1 as economy
from moonpa_growth import available_skill_slots
from combat import Battle, SKILLS, ROLE_SKILLS, Unit
from moonpa_portraits import portrait_asset

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
    return Unit(f.fid, side, f.role, f.name, row, attrs, f.lv,
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

    def overview(self):
        available = [f for f in self.guild.fighters if not f.injured]
        ready = {f.fid for f in lineup(available)}
        return dict(season=self.season, week=self.week, seed=self.seed, guild=self.guild.gid,
                    cash=self.guild.cash, dead=self.world.player_bankrupted,
                    guild_name=self.guild.name,
                    roster=[dict(id=f.fid, name=f.name, surname=f.surname, given_name=f.given_name,
                                 role=ROLES[f.role], role_id=f.role, ca=round(f.ca, 1),
                                 lv=f.lv, xp=f.xp, fatigue=f.fatigue, injured=f.injured,
                                 skills=unlocked(f), slots=available_skill_slots(f.lv),
                                 recommended=f.fid in ready) for f in self.guild.fighters],
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

    def battle_state(self):
        b = self.battle
        if b is None:
            return None
        return dict(round=b.round, winner=b.winner, seed=b.seed, practice=self.practice,
                    units=[dict(id=u.id, side=u.side, role=ROLES[u.role], role_id=u.role, name=u.name, row=u.row,
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
        owners = [x.owner for x in w.zones]
        before = self.guild.cash
        w.season_active, w.week_active, w.globalweek = self.season, self.week, self.clock
        plans = {g.gid:economy.prep_plan(w,g,self.week) for g in w.guilds.values()}
        # Respect weekly activity exclusivity for combatants.
        ids = set(b.units)
        for plan in plans.values():
            for key in ('training','second','overflow_bench','attack','defend','rest','emergency','scout'):
                plan[key] = [f for f in plan[key] if f.fid not in ids]
            plan['missions'] = [team for team in plan['missions'] if not any(f.fid in ids for f in team)]
        plans[self.guild.gid]['attack'] = []
        # The contested region is handled exclusively by this battle.
        for plan in plans.values():
            if plan["attack_target"] == z.zid or len(plan["attack"]) != 5:
                plan['attack'] = []
        if z.owner is not None:
            plans[z.owner]['defend'] = []
        economy.old.attempt_attacks(w,plans,self.week)
        victory = b.winner == 0
        released = None
        self.guild.attacks += 1
        if victory:
            owned = [x for x in w.zones if x.owner == self.guild.gid]
            if len(owned) >= economy.CAP[self.guild.tier]:
                dropped = min(owned,key=economy.old.zone_value)
                dropped.owner = None
                released = dropped.zid
            z.owner = self.guild.gid
            z.protected_until = self.clock+2
            self.guild.attack_wins += 1
            self.guild.score += 4
        elif z.owner is not None:
            defender = w.guilds[z.owner]
            defender.defense_wins += 1
            defender.score += 2
        participants = [f for g in w.guilds.values() for f in g.fighters if f.fid in ids]
        economy.economics_week(w,plans,owners,self.season,self.week)
        changes = []
        for f in participants:
            u = b.units[f.fid]
            xp = 12 + min(20,u.actions*2) + (8 if u.side == b.winner else 0)
            economy.old.advance_experience(f,xp)
            fatigue = min(35, 8 + u.actions + round(12*u.hit_taken/u.max_hp))
            f.fatigue = min(100,f.fatigue+fatigue)
            if not u.hp:
                f.injured = max(f.injured,2)
            changes.append(dict(id=f.fid, name=f.name, side=u.side, xp=xp, fatigue=fatigue, injured=f.injured))
        for g in w.guilds.values():
            w.trim_roster(g,self.season)
        economy.assert_world(w)
        self.week += 1
        if self.week == 52:
            economy.one_week(w,self.season,52)
            economy.annual_rollover(w,self.season)
            economy.assert_world(w)
            self.season += 1
            self.week = 1
        return dict(practice=False,success=victory,zone=z.zid,owner=z.owner,released=released,
                    cash_change=self.guild.cash-before, participants=changes)
