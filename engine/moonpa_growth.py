"""Player development parameters under test in v15."""
from dataclasses import dataclass, field
from random import Random

ATTRIBUTES = ('strength', 'defense', 'stamina', 'agility', 'inner_power',
              'sorcery', 'insight', 'willpower')
ROLES = ('guardian', 'warrior', 'archer', 'shaman', 'healer', 'assassin')
WEIGHTS = (
    (2, 5, 5, 1, 2, 1, 2, 2), (5, 3, 3, 3, 2, 0, 2, 2),
    (2, 1, 2, 5, 2, 0, 6, 2), (0, 1, 1, 2, 4, 6, 3, 3),
    (0, 2, 2, 1, 4, 4, 2, 5), (3, 1, 1, 6, 2, 1, 4, 2),
)
MIDPOINTS = (50, 110, 130, 150, 170, 190)
TRAIT_BONUSES = (1, 3, 6, 10)
PEAK_AGE = {'early': 24, 'standard': 28, 'late': 36}

# Balanced uses the precise original v15 growth formula for save/balance
# compatibility. Specialized curricula redistribute that SAME raw budget.
TRAINING_FOCUSES = {
    'balanced': ('균형 수련', (), '8개 능력치를 역할별 기본 비중으로 수련'),
    'attack': ('공격 특화', ('strength', 'agility'), '근력·민첩 성장 비중 집중'),
    'defense': ('방어 특화', ('defense', 'stamina'), '방어·체력 성장 비중 집중'),
    'ranged': ('원거리 특화', ('agility', 'insight'), '민첩·통찰 성장 비중 집중'),
    'internal': ('내공 특화', ('inner_power', 'sorcery'), '내공·술법 성장 비중 집중'),
    'support': ('생존·지원 특화', ('stamina', 'willpower'), '체력·정신력 성장 비중 집중'),
}


def training_factors(role, focus='balanced'):
    """Return 8 nonnegative allocation factors with unchanged sum (8.0).

    Rounded only when displaying to UI, never during settlement. A capped
    attribute loses unused growth rather than reallocating it into an exploit.
    """
    if focus not in TRAINING_FOCUSES:
        raise ValueError('지원하지 않는 수련 방향입니다.')
    weights = WEIGHTS[role]
    baseline = [0.5 + weight / 5 for weight in weights]
    if focus == 'balanced':
        return tuple(baseline)  # byte-for-byte equivalent to the old formula
    targets = set(TRAINING_FOCUSES[focus][1])
    biased = [factor * (1.55 if attr in targets else .78)
              for factor, attr in zip(baseline, ATTRIBUTES)]
    scale = sum(baseline) / sum(biased)
    return tuple(factor * scale for factor in biased)



def scout_grade(value):
    return min(5, max(0, int(value // 20) - 4))


@dataclass(frozen=True, slots=True)
class Trait:
    attribute: int
    grade: int

    @property
    def bonus(self):
        return TRAIT_BONUSES[self.grade]


@dataclass(slots=True)
class Development:
    attributes: list[float]
    observed_ca_grade: int
    observed_pa_grade: int
    scouting_error: int
    traits: list[Trait] = field(default_factory=list)
    trainee_weeks: int = 0
    mentor_weeks: int = 0
    squad: str = ''
    mentor_id: int | None = None
    rookie: bool = False
    # Fighter-owned story data survives free agency and cross-guild transfers.
    saga: dict | None = None
    secret_arts: list[str] = field(default_factory=list)
    elite_wins: int = 0
    personal_title: str = ''
    story_events: list[dict] = field(default_factory=list)

    @classmethod
    def create(cls, ca, pa, role, seed, fid):
        rng = Random((seed << 32) ^ fid ^ 0x5A9C)
        error = rng.randint(-10, 10)
        result = cls([ca] * 8, scout_grade(ca + error),
                     scout_grade(pa + error), error)
        offsets = [9*w + rng.uniform(-6, 6) for w in WEIGHTS[role]]
        center = sum(x * w for x, w in zip(offsets, WEIGHTS[role])) / 20
        spread = min(1, ca / 65, (200 - ca) / 65)
        result.attributes = [ca + (x - center) * spread for x in offsets]
        if rng.random() < .35:
            grade = rng.choices(range(4), (72, 22, 5, 1))[0]
            result.add_trait(Trait(rng.randrange(8), grade))
        return result

    def add_trait(self, trait):
        for index, current in enumerate(self.traits):
            if current.attribute == trait.attribute:
                self.traits[index] = Trait(trait.attribute,
                                           min(3, max(current.grade + 1, trait.grade)))
                return
        if len(self.traits) < 3:
            self.traits.append(trait)

    def rating(self, role, pa):
        base = sum(x * w for x, w in zip(self.attributes, WEIGHTS[role])) / 20
        bonus = sum(min(t.bonus, 200 - self.attributes[t.attribute])
                    * WEIGHTS[role][t.attribute] for t in self.traits) / 20
        return min(pa, base + bonus)

    def refresh(self, fighter):
        fighter.ca = self.rating(fighter.role, fighter.pa)
        self.observed_ca_grade = scout_grade(fighter.ca + self.scouting_error)

    def train(self, fighter, amount, focus='balanced'):
        # The weekly training gain budget is constant across specialties.
        # Focus changes allocation among attributes, never the amount paid,
        # level XP, mentor effects or number of training weeks.
        factors = training_factors(fighter.role, focus)
        for i, value in enumerate(self.attributes):
            self.attributes[i] = min(200, value + amount * factors[i])
        weights = WEIGHTS[fighter.role]
        self.trainee_weeks += 1
        if self.trainee_weeks in (80, 200):
            self.add_trait(Trait(max(range(8), key=weights.__getitem__), 0))
        self.refresh(fighter)


def available_skill_slots(level):
    return 2 + (level >= 5) + (level >= 10) + (level >= 15) + (level >= 20)


def observed_potential(fighter):
    return MIDPOINTS[fighter.development.observed_pa_grade]


def observed_ability(fighter):
    return MIDPOINTS[fighter.development.observed_ca_grade]
