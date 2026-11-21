"""Seeded Korean wuxia names and concealed sect recruitment preferences.

The registry is intentionally independent of the economy/battle RNG. Never
rename a Fighter when it changes guilds; identity belongs to the fighter.
"""
from __future__ import annotations

import random
from collections import Counter

GUILD_NAMES = {
    1: ("화산파", "종남파", "남궁세가", "무당파", "소림사", "개방", "사천당문", "청성파"),
    2: ("아미파", "곤륜파", "점창파", "제갈세가", "모용세가", "하북팽가", "공동파", "형산파"),
    3: ("해남파", "백운검문", "금도문", "낙양검문", "흑풍문", "청하문", "운룡방", "적월문"),
    4: ("청석문", "풍림문", "창천문", "운학문", "정양문", "비호문", "백림문", "하동검관"),
}
assert all(len(guilds) == 8 for guilds in GUILD_NAMES.values())
assert len({name for guilds in GUILD_NAMES.values() for name in guilds}) == 32

SURNAMES = (
    "김", "이", "박", "최", "정", "조", "강", "윤", "장", "임", "한", "오",
    "서", "신", "권", "황", "안", "송", "류", "홍", "문", "백", "남", "진",
    "하", "설", "구", "여", "차", "채", "도", "마", "천", "맹", "표",
)
COMPOUND_SURNAMES = ("남궁", "제갈", "모용", "황보", "선우", "사마", "독고", "서문", "동방", "구양")
FIRST_SYLLABLES = (
    "무", "서", "해", "매", "하", "윤", "진", "정", "소", "연", "채", "호",
    "강", "운", "설", "청", "도", "경", "태", "민", "유", "희", "월",
    "백", "주", "현", "영", "준", "담", "린", "은", "형", "가", "자",
)
LAST_SYLLABLES = (
    "진", "린", "우", "호", "연", "아", "현", "검", "율", "찬", "혁", "명",
    "화", "서", "영", "휘", "랑", "설", "온", "민", "준", "빈", "수",
    "경", "운", "석", "천", "도", "희", "하", "원", "태", "별", "담",
)
REPLACEMENT_ROOTS = (
    "청룡", "자운", "백암", "취풍", "홍매", "낙성", "운산", "설봉",
    "적송", "한림", "금강", "소월", "비연", "벽산", "화령", "흑송",
)
REPLACEMENT_SUFFIXES = ("문", "파", "방", "검문", "검관", "세가")


class NameRegistry:
    """Unique names for all created people, including retirees and free agents."""

    def __init__(self, seed: int):
        # Independent RNG: adding names must not change economy or battle rolls.
        self.rng = random.Random((int(seed) * 0x9E3779B185EBCA87 + 0x6A09E667F3BCC909) & ((1 << 64) - 1))
        self.used_people: set[str] = set()
        self.used_sects: set[str] = set()

    def reserve_sect(self, name: str) -> str:
        if not name or name in self.used_sects:
            raise ValueError("문파 이름이 비어 있거나 이미 사용 중입니다.")
        self.used_sects.add(name)
        return name

    def new_sect(self) -> str:
        for _ in range(4096):
            name = self.rng.choice(REPLACEMENT_ROOTS) + self.rng.choice(REPLACEMENT_SUFFIXES)
            if name not in self.used_sects:
                return self.reserve_sect(name)
        raise RuntimeError("새로운 문파 이름을 생성할 수 없습니다.")

    def person(self, *, surname: str | None = None, contain_mae: bool = False) -> tuple[str, str]:
        for _ in range(10000):
            family = surname or self.rng.choice(COMPOUND_SURNAMES if self.rng.random() < .13 else SURNAMES)
            first = self.rng.choice(FIRST_SYLLABLES)
            last = self.rng.choice(LAST_SYLLABLES)
            if contain_mae:
                if self.rng.random() < .5:
                    first = "매"
                else:
                    last = "매"
            given = first + last
            full = family + given
            if full not in self.used_people:
                self.used_people.add(full)
                return family, given
        raise RuntimeError("고유 문파원 이름을 생성할 수 없습니다.")


def initial_member_hints(sect: str, index: int, roster_size: int) -> dict:
    """Deterministic quotas make the three initial sect identities visible."""
    if sect == "남궁세가" and index < (roster_size * 7 + 9) // 10:
        return {"surname": "남궁"}
    if sect == "화산파" and index % 4 == 0:
        return {"contain_mae": True}
    return {}


def starting_role(sect: str, index: int, default_role: int) -> int:
    # At least one in three Jongnam starters is a martial warrior (role index 1).
    return 1 if sect == "종남파" and index % 3 == 0 else default_role


def preference_multiplier(guild, fighter) -> float:
    """Private, small preference applied only AFTER the normal eligibility rules.

    This affects candidate ordering and mild willingness to pay, never cash,
    squad-size, contract, or same-season transfer restrictions.
    """
    sect = getattr(guild, "name", "")
    if sect == "남궁세가" and getattr(fighter, "surname", "") == "남궁":
        return 1.06
    if sect == "화산파" and "매" in getattr(fighter, "given_name", ""):
        return 1.035
    if sect == "종남파" and fighter.role == 1:
        # A lack of first-team martial warriors increases recruitment priority.
        active = sorted(guild.fighters, key=lambda f: f.ca + .12 * f.lv, reverse=True)[:20]
        if sum(member.role == 1 for member in active) < 3:
            return 1.055
    return 1.0
