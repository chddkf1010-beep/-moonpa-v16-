"""Deterministic round-based combat. Human orders and AI share validation."""
from dataclasses import dataclass, field
from random import Random


@dataclass(frozen=True)
class Skill:
    name: str
    target: str
    power: float = 0
    cost: int = 0
    cooldown: int = 0
    note: str = ''
    level: int = 1


SKILLS = {
    'hit': Skill('일반 공격', 'front', 1),
    'guard': Skill('방어 태세', 'self', note='이번 라운드 자신이 받는 피해 50% 감소'),
    'wall': Skill('방패진', 'self', cost=18, cooldown=2, note='이번 라운드 아군 전열 피해 40% 감소'),
    'taunt': Skill('도발', 'front', cost=14, cooldown=2, note='선택한 적 전열과 다른 적 전열 한 명이 2라운드 동안 시전자를 우선 공격'),
    'strike': Skill('파쇄격', 'front', 1.65, 20, 2),
    'riposte': Skill('반격 태세', 'self', cost=14, cooldown=2, note='이번 라운드 피해 50% 감소. 첫 공격자에게 반격'),
    'arrow': Skill('관통 화살', 'enemy', 1.40, 16, 1),
    'pin': Skill('봉쇄 사격', 'enemy', .85, 22, 3, '적 한 명의 다음 행동을 기절로 취소', 3),
    'curse': Skill('쇠약의 주술', 'enemy', 0, 17, 4, '적 한 명의 공격력 50% 감소 · 2라운드 · 정신력 저항 가능'),
    'ward': Skill('호신술', 'ally', cost=17, cooldown=2, note='아군 한 명의 받는 피해 40% 감소 · 실제 체력 피해의 60% 반사 · 2라운드'),
    'heal': Skill('회생술', 'ally', 1.1, 17, 1, '아군 한 명의 체력 회복'),
    'cleanse': Skill('정화술', 'ally', cost=12, cooldown=2, note='아군 한 명의 기절·약화·도발 해제'),
    'fang': Skill('그림자 습격', 'enemy', 1.55, 19, 2),
    'veil': Skill('은신', 'self', cost=12, cooldown=3, note='적의 단일 대상 공격 대상에서 제외, 2라운드'),
}
ROLE_SKILLS = (('wall', 'taunt'), ('strike', 'riposte'), ('arrow', 'pin'),
               ('curse', 'ward'), ('heal', 'cleanse'), ('fang', 'veil'))


@dataclass
class Unit:
    id: int
    side: int
    role: int
    name: str
    row: str
    attrs: list[float]
    level: int
    loadout: tuple[str, ...]
    hp: int = 0
    max_hp: int = 0
    qi: int = 0
    max_qi: int = 0
    traits: tuple[int, ...] = ()
    portrait_key: str = ''
    effects: dict = field(default_factory=dict)
    ready: dict = field(default_factory=dict)
    damage: int = 0
    healing: int = 0
    prevented: int = 0
    actions: int = 0
    hit_taken: int = 0

    def __post_init__(self):
        self.max_hp = self.hp = round(100 + self.attrs[2] * 1.65)
        self.max_qi = self.qi = round(45 + self.attrs[4] * .55)


class Battle:
    def __init__(self, units, seed):
        self.units = {u.id: u for u in units}
        if len(self.units) != 10 or sum(u.side == 0 for u in units) != 5:
            raise ValueError('양측에 중복 없는 문파원 5명씩이 필요합니다.')
        self.seed = seed
        self.round = 1
        self.winner = None
        self.events = []
        self.frames = []
        self.orders = []

    def active(self, u, key):
        return u.effects.get(key, (0, None))[0] >= self.round

    def targets(self, u, key):
        if (not u.hp or self.winner is not None or key not in ('hit', 'guard', *u.loadout)
                or u.qi < SKILLS[key].cost or u.ready.get(key, 0) > self.round):
            return []
        kind = SKILLS[key].target
        if kind == 'self':
            return [u.id]
        if kind == 'ally':
            return [x.id for x in self.units.values() if x.side == u.side and x.hp]
        enemies = [x for x in self.units.values() if x.side != u.side and x.hp]
        visible = [x for x in enemies if not self.active(x, 'veil')]
        front = [x for x in visible if x.row == 'front']
        if key == 'taunt':
            return [x.id for x in front]
        if self.active(u, 'taunt'):
            source = u.effects['taunt'][1]
            if any(x.id == source for x in visible):
                return [source]
        if kind == 'front' and u.role != 5 and any(x.row == 'front' for x in enemies):
            visible = front
        return [x.id for x in visible]

    def options(self, u):
        return {key: self.targets(u, key) for key in ('hit', 'guard', *u.loadout)}

    def choose(self, u, style='balanced'):
        options = self.options(u)
        for key in ('cleanse', 'heal'):
            targets = [self.units[i] for i in options.get(key, [])]
            if key == 'cleanse':
                eligible = [x for x in targets if any(self.active(x, effect) for effect in ('stun','curse','taunt'))]
                if eligible:
                    return key, eligible[0].id
            elif targets:
                target = min(targets, key=lambda x: x.hp / x.max_hp)
                if target.hp < target.max_hp * .78:
                    return key, target.id
        if style == 'protect':
            healer = next((x for x in self.units.values() if x.side == u.side and x.role == 4 and x.hp), None)
            if healer and healer.id in options.get('ward', []):
                return 'ward', healer.id
            if healer and options.get('wall'):
                return 'wall', u.id
        if options.get('curse'):
            targets = [self.units[i] for i in options['curse'] if not self.active(self.units[i], 'curse')]
            if targets:
                threat = max(targets, key=lambda x: (x.role in (1, 5), max(x.attrs[0], x.attrs[3]), -x.id))
                return 'curse', threat.id
        if options.get('ward'):
            targets = [self.units[i] for i in options['ward'] if not self.active(self.units[i], 'ward')]
            if targets:
                target = min(targets, key=lambda x: (x.row != 'front', x.hp/x.max_hp, x.id))
                return 'ward', target.id
        for key in ('fang', 'pin', 'arrow', 'strike', 'taunt', 'hit'):
            if options.get(key):
                targets = [self.units[i] for i in options[key]]
                target = min(targets, key=lambda x: (not(style == 'pressure' and x.role == 4), x.hp, x.id))
                return key, target.id
        return 'guard', u.id

    def snapshot(self):
        return [dict(id=u.id, hp=u.hp, qi=u.qi,
                     effects=[key for key in u.effects if self.active(u, key)])
                for u in self.units.values()]

    def initiative(self, rng=None):
        if rng is None:
            rng = Random((self.seed << 12) + self.round)
        living = [u for u in self.units.values() if u.hp]

        def score(u):
            return (u.attrs[3] + .30*u.attrs[6] + rng.uniform(0, 10)
                    + 6*self.active(u, 'veil') + 6*self.active(u, 'valor')
                    - 20*self.active(u, 'stun'))

        return sorted(living, key=score, reverse=True)

    def emit(self, message, kind='notice', actor=None, target=None, skill=None, amount=None):
        self.events.append(dict(round=self.round, text=message, kind=kind,
                                actor=actor.id if actor else None, target=target.id if target else None,
                                skill=skill, amount=amount, units=self.snapshot()))

    def effect(self, u, key, duration, source):
        u.effects[key] = (self.round + duration - 1, source)

    def apply_damage(self, actor, target, dealt, key, kind):
        if not dealt:
            return
        target.hp -= dealt
        target.hit_taken += dealt
        actor.damage += dealt
        label = '반사' if kind == 'reflection' else '치명타' if kind == 'critical' else '피해'
        self.emit(f'{actor.name} → {target.name} · {label} {dealt}', kind, actor, target, key, dealt)
        if not target.hp:
            self.emit(f'{target.name} 전투불능', 'knockout', actor, target, key)
            if actor.hp and 0 in actor.traits and not self.active(actor, 'valor'):
                self.effect(actor, 'valor', 20, actor.id)
                actor.attrs[0] += 15
                self.emit(f'{actor.name} · 무투가의 후예 발동 (근력 +15)', 'buff', actor, actor, key)

    def damage(self, actor, target, power, rng, key):
        a = actor.attrs
        evade = min(.24, max(.04, .08 + (target.attrs[3] - a[6]) * .001))
        if rng.random() < evade:
            self.emit(f'{target.name} 회피!', 'miss', actor, target, key)
            return False
        critical = rng.random() < min(.20, .04 + a[6]*.0007)
        offense = a[5] if actor.role in (3, 4) else a[3] if actor.role in (2, 5) else a[0]
        raw = max(5, (13 + .42 * offense - .17 * target.attrs[1]) * power * rng.uniform(.9, 1.1))
        raw *= (.5 if self.active(actor, 'curse') else 1) * (1.5 if critical else 1)
        multipliers = {'guard': .5, 'wall': .6, 'ward': .6}
        effect = min((k for k in multipliers if self.active(target, k)), key=multipliers.get, default=None)
        dealt = min(target.hp, max(0, round(raw * multipliers.get(effect, 1))))
        if effect:
            source = self.units[target.effects[effect][1]]
            source.prevented += max(0, min(target.hp, round(raw)) - dealt)
        self.apply_damage(actor, target, dealt, key, 'critical' if critical else 'damage')
        if dealt and self.active(target, 'ward') and actor.hp:
            reflected = min(actor.hp, (dealt * 6 + 5) // 10)
            self.apply_damage(target, actor, reflected, 'ward', 'reflection')
        if dealt and actor.hp and target.hp and key != 'riposte' and self.active(target, 'riposte'):
            del target.effects['riposte']
            self.damage(target, actor, .65, rng, 'riposte')
        return True

    def resolve(self, u, key, target, rng):
        if self.active(u, 'stun'):
            del u.effects['stun']
            self.emit(f'{u.name} 기절로 행동 취소', 'skip', u, target, key)
            return
        if target.id not in self.targets(u, key):
            self.emit(f'{u.name} · {SKILLS[key].name} 취소 (대상 또는 상태 변경)', 'skip', u, target, key)
            return
        skill = SKILLS[key]
        u.actions += 1
        u.qi -= skill.cost
        u.ready[key] = self.round + skill.cooldown + 1
        if key == 'taunt':
            other = next((x for x in self.initiative() if x.side != u.side and
                          x.row == 'front' and x is not target and not self.active(x, 'veil')), None)
            for opponent in (target, other):
                if opponent is not None:
                    self.effect(opponent, key, 2, u.id)
                    self.emit(f'{opponent.name} · 도발', 'debuff', u, opponent, key)
            return
        if key in ('guard','riposte','veil','ward'):
            effect = 'guard' if key == 'riposte' else key
            self.effect(target, effect, 2 if key in ('veil','ward') else 1, u.id)
            if key == 'riposte':
                self.effect(u, key, 1, u.id)
        elif key == 'wall':
            for x in self.units.values():
                if x.side == u.side and x.row == 'front' and x.hp:
                    self.effect(x, 'wall', 1, u.id)
        elif key == 'heal':
            heal = min(target.max_hp-target.hp, round((20 + .49*u.attrs[5] + .18*u.attrs[7]) * skill.power))
            target.hp += heal
            u.healing += heal
            self.emit(f'{u.name} → {target.name} · 회복 {heal}', 'heal', u, target, key, heal)
            return
        elif key == 'cleanse':
            for effect in ('stun','curse','taunt'):
                target.effects.pop(effect, None)
        elif key == 'curse':
            resistance = min(.65, max(.05, .20 + (target.attrs[7]-u.attrs[5])*.004))
            if rng.random() < resistance:
                self.emit(f'{target.name} 쇠약 저항', 'resist', u, target, key)
            else:
                self.effect(target, key, 2, u.id)
                self.emit(f'{target.name} 공격력 −50%', 'debuff', u, target, key)
            return
        else:
            hit = self.damage(u, target, skill.power, rng, key)
            if hit and target.hp and key == 'pin':
                self.effect(target, 'stun', 2, u.id)
                self.emit(f'{target.name} 기절', 'debuff', u, target, key)
            return
        self.emit(f'{u.name} → {target.name} · {skill.name}',
                  'buff', u, target, key)

    def step(self, commands=None, style='balanced'):
        if self.winner is not None:
            raise ValueError('이미 종료된 전투입니다.')
        living = [u for u in self.units.values() if u.hp]
        allied = [u for u in living if u.side == 0]
        if commands is not None and set(commands) != {u.id for u in allied}:
            raise ValueError('생존한 아군 전원의 명령을 선택하세요.')
        orders = {}
        for u in living:
            key, target = commands[u.id] if commands is not None and u.side == 0 else self.choose(u, style if u.side == 0 else 'balanced')
            if target not in self.options(u).get(key, []):
                raise ValueError(f'{u.name}의 명령이 유효하지 않습니다.')
            orders[u.id] = (key, target)
        self.orders.append(orders)
        rng = Random((self.seed << 12) + self.round)
        living = self.initiative(rng)
        frame = dict(round=self.round, order=[u.id for u in living],
                     initial=self.snapshot(), actions=[])
        for u in living:
            key, target = orders[u.id]
            start = len(self.events)
            if u.hp:
                self.resolve(u, key, self.units[target], rng)
            else:
                self.emit(f'{u.name} 전투불능으로 행동 취소', 'skip', u, self.units[target], key)
            frame['actions'].append(dict(actor=u.id, skill=key, target=target,
                                         start=start, end=len(self.events)))
            if not all(any(x.hp and x.side == side for x in living) for side in (0, 1)):
                break
        for u in living:
            if u.hp:
                u.qi = min(u.max_qi, u.qi + 8)
        totals = [sum(u.hp for u in self.units.values() if u.side == side) for side in (0,1)]
        fractions = [totals[side] / sum(u.max_hp for u in self.units.values() if u.side == side) for side in (0,1)]
        if min(totals) == 0 or self.round == 20:
            self.winner = 0 if fractions[0] > fractions[1] else 1
            self.emit('공격측 승리' if self.winner == 0 else '방어측 승리')
        frame['units'] = self.snapshot()
        frame['event_end'] = len(self.events)
        self.frames.append(frame)
        if self.winner is None:
            self.round += 1
