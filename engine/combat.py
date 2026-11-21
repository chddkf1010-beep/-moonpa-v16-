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
    'taunt': Skill('도발', 'front', cost=14, cooldown=2, note='적 한 명이 2라운드 동안 시전자를 우선 공격'),
    'strike': Skill('파쇄격', 'front', 1.65, 20, 2),
    'riposte': Skill('반격 태세', 'self', cost=14, cooldown=2, note='이번 라운드 피해 50% 감소. 첫 공격자에게 반격'),
    'arrow': Skill('관통 화살', 'enemy', 1.40, 16, 1),
    'pin': Skill('봉쇄 사격', 'enemy', .85, 22, 3, '적 한 명의 다음 행동을 기절로 취소', 3),
    'curse': Skill('쇄기술', 'enemy', 1.15, 17, 2, '적 한 명의 공격 피해 28% 감소, 2라운드'),
    'ward': Skill('호신술', 'ally', cost=17, cooldown=2, note='아군 한 명이 받는 피해 40% 감소, 2라운드'),
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
        if kind == 'front' and u.role != 5 and any(x.row == 'front' for x in enemies):
            visible = front
        if self.active(u, 'taunt'):
            source = u.effects['taunt'][1]
            if any(x.id == source for x in visible):
                return [source]
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
        for key in ('fang', 'pin', 'arrow', 'curse', 'strike', 'taunt', 'hit'):
            if options.get(key):
                targets = [self.units[i] for i in options[key]]
                target = min(targets, key=lambda x: (not(style == 'pressure' and x.role == 4), x.hp, x.id))
                return key, target.id
        return 'guard', u.id

    def emit(self, message):
        self.events.append(dict(round=self.round, text=message))

    def effect(self, u, key, duration, source):
        u.effects[key] = (self.round + duration - 1, source)

    def damage(self, actor, target, power, rng, key):
        a = actor.attrs
        offense = a[5] if actor.role in (3, 4) else a[3] if actor.role in (2, 5) else a[0]
        raw = max(5, (13 + .42 * offense - .17 * target.attrs[1]) * power * rng.uniform(.9, 1.1))
        if self.active(actor, 'curse'):
            raw *= .72
        multipliers = {'guard': .5, 'wall': .6, 'ward': .6}
        factor = min((value for effect, value in multipliers.items() if self.active(target, effect)), default=1)
        dealt = min(target.hp, max(1, round(raw * factor)))
        if factor < 1:
            effect = min((k for k in multipliers if self.active(target, k)), key=multipliers.get)
            source = self.units[target.effects[effect][1]]
            prevented = max(0, min(target.hp, round(raw)) - dealt)
            source.prevented += prevented
            self.emit(f'{source.name} 보호로 피해 {prevented} 감소')
        target.hp -= dealt
        target.hit_taken += dealt
        actor.damage += dealt
        self.emit(f'{actor.name} → {target.name} · {SKILLS[key].name} 피해 {dealt}')
        if not target.hp:
            self.emit(f'{target.name} 전투불능')
            if 0 in actor.traits and not self.active(actor, 'valor'):
                self.effect(actor, 'valor', 20, actor.id)
                actor.attrs[0] += 15
                self.emit(f'{actor.name} · 무투가의 후예 발동 (근력 +15)')
        elif key != 'riposte' and self.active(target, 'riposte'):
            del target.effects['riposte']
            self.damage(target, actor, .65, rng, 'riposte')

    def resolve(self, u, key, target, rng):
        if self.active(u, 'stun'):
            del u.effects['stun']
            self.emit(f'{u.name} 기절로 행동 취소')
            return
        if target.id not in self.targets(u, key):
            self.emit(f'{u.name} · {SKILLS[key].name} 취소 (대상 또는 상태 변경)')
            return
        skill = SKILLS[key]
        u.actions += 1
        u.qi -= skill.cost
        u.ready[key] = self.round + skill.cooldown + 1
        if key in ('guard','riposte','veil','taunt','ward'):
            effect = 'guard' if key == 'riposte' else key
            self.effect(target, effect, 2 if key in ('veil','taunt','ward') else 1, u.id)
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
            self.emit(f'{u.name} → {target.name} · 회복 {heal}')
            return
        elif key == 'cleanse':
            for effect in ('stun','curse','taunt'):
                target.effects.pop(effect, None)
        else:
            self.damage(u, target, skill.power, rng, key)
            if target.hp and key in ('pin', 'curse'):
                self.effect(target, 'stun' if key == 'pin' else 'curse', 2, u.id)
            return
        self.emit(f'{u.name} → {target.name} · {skill.name}')

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
        living.sort(key=lambda u: -(u.attrs[3] + .30*u.attrs[6] + rng.uniform(0, 10)))
        for u in living:
            if u.hp:
                key, target = orders[u.id]
                self.resolve(u, key, self.units[target], rng)
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
        self.frames.append(dict(round=self.round, units=[dict(id=u.id,hp=u.hp,qi=u.qi) for u in self.units.values()]))
        if self.winner is None:
            self.round += 1
