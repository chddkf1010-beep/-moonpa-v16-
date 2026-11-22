"""B/C combat meta: one seeded seasonal trend and a permanent terrain for each zone.

This module has no mutable global state, so previews and combat use identical
rules without changing the economic world's RNG or save data.
"""
import random

from moonpa_sites import SITES

TRENDS = (
    ("vanguard", "선봉 유행", "무인·암살형이 첫 3라운드에 가하는 피해 +10%"),
    ("bulwark", "철벽 유행", "수호형이 첫 3라운드에 받는 피해 -10%"),
    ("archery", "궁술 유행", "사수형이 가하는 피해 +10%"),
    ("mystic", "주술 유행", "주술형이 가하는 피해 +10%"),
    ("healing", "의술 유행", "치유형이 주는 회복량 +12%"),
    ("ambush", "암습 유행", "암살형이 적 후열에 가하는 피해 +10%"),
)
TERRAINS = (
    ("mountain", "산악", "첫 3라운드 전열이 받는 피해 -8%"),
    ("plain", "평야", "첫 2라운드 모든 공격 피해 +7%"),
    ("forest", "숲길", "암살형이 후열에 가하는 피해 +8%"),
    ("river", "수변", "양측 회복량 +8%"),
    ("fortress", "성곽", "첫 3라운드 수비측이 받는 피해 -8%"),
    ("gorge", "협곡", "첫 3라운드 후열이 받는 피해 -8%"),
)
STYLES = {
    "balanced": ("균형", "기본 공격·회복·방어를 상황에 맞게 사용"),
    "protect": ("보호", "치유형 보호 및 전열 방어를 우선"),
    "pressure": ("후열 압박", "상대 치유형을 우선 공격"),
}


def season_trend(seed, season):
    """Deterministic per campaign/season, avoiding consecutive repeats."""
    if type(seed) is not int or type(season) is not int or season < 0:
        raise ValueError("시즌 정보가 올바르지 않습니다.")
    rng = random.Random(f"moonpa-season-trend:{seed}")
    previous = None
    for _ in range(season + 1):
        options = [i for i in range(len(TRENDS)) if i != previous]
        previous = rng.choice(options)
    code, name, description = TRENDS[previous]
    return dict(id=code, name=name, description=description)


def zone_terrain(zone_id):
    """Each zone always retains the same battleground environment."""
    if type(zone_id) is not int or zone_id < 0:
        raise ValueError("구역 정보가 올바르지 않습니다.")
    index = (zone_id * 5 + zone_id // 12) % len(TERRAINS)
    if zone_id < len(SITES):
        site = SITES[zone_id][1]
        if any(term in site for term in ('나루','수로','운하','선창','부두','선착장','상항',' 도진')):
            index = 3
        elif site.endswith(('본성','요새','관문','소관')) or site=='흑석관':
            index = 4
        elif '협곡' in site:
            index = 5
    code, name, description = TERRAINS[index]
    return dict(id=code, name=name, description=description)


def defending_style(fighters):
    """The displayed tactical inclination is also used by the battle AI."""
    roles = [f.role for f in fighters]
    if roles.count(0) >= 2 or (0 in roles and 4 in roles):
        code = "protect"
    elif roles.count(5) >= 2 or (5 in roles and 2 in roles):
        code = "pressure"
    else:
        code = "balanced"
    name, description = STYLES[code]
    return dict(id=code, name=name, description=description)


def combat_context(seed, season, zone_id, style="balanced"):
    if style not in STYLES:
        raise ValueError("상대 전술이 올바르지 않습니다.")
    return dict(trend=season_trend(seed, season)["id"],
                terrain=zone_terrain(zone_id)["id"], enemy_style=style)


def damage_multiplier(context, actor, target, round_no):
    """Apply B and C symmetrically, with a global 20% total modifier cap."""
    if not context:
        return 1.0
    trend, terrain = context.get("trend"), context.get("terrain")
    value = 1.0
    if trend == "vanguard" and actor.role in (1, 5) and round_no <= 3:
        value *= 1.10
    elif trend == "bulwark" and target.role == 0 and round_no <= 3:
        value *= .90
    elif trend == "archery" and actor.role == 2:
        value *= 1.10
    elif trend == "mystic" and actor.role == 3:
        value *= 1.10
    elif trend == "ambush" and actor.role == 5 and target.row == "back":
        value *= 1.10
    if terrain == "mountain" and target.row == "front" and round_no <= 3:
        value *= .92
    elif terrain == "plain" and round_no <= 2:
        value *= 1.07
    elif terrain == "forest" and actor.role == 5 and target.row == "back":
        value *= 1.08
    elif terrain == "fortress" and target.side == 1 and round_no <= 3:
        value *= .92
    elif terrain == "gorge" and target.row == "back" and round_no <= 3:
        value *= .92
    return min(1.20, max(.80, value))


def healing_multiplier(context, actor):
    if not context:
        return 1.0
    value = 1.12 if context.get("trend") == "healing" and actor.role == 4 else 1.0
    if context.get("terrain") == "river":
        value *= 1.08
    return min(1.20, value)


def simulated_power_bonus(context, team, side, round_no=1):
    """Small proxy for AI-vs-AI territory battles, measured in CA points.

    The tactical battle uses actual outgoing/incoming modifiers instead.
    """
    if not team or not context:
        return 0.0
    trend, terrain = context["trend"], context["terrain"]
    roles = [f.role for f in team]
    bonus = 0.0
    if trend == "vanguard" and (1 in roles or 5 in roles):
        bonus += 2.0
    elif trend == "bulwark" and 0 in roles:
        bonus += 2.0
    elif trend == "archery" and 2 in roles:
        bonus += 2.0
    elif trend == "mystic" and 3 in roles:
        bonus += 2.0
    elif trend == "healing" and 4 in roles:
        bonus += 2.0
    elif trend == "ambush" and 5 in roles:
        bonus += 2.0
    if terrain == "mountain" and 0 in roles:
        bonus += 1.5
    elif terrain == "plain":
        bonus += 1.0
    elif terrain == "forest" and 5 in roles:
        bonus += 1.5
    elif terrain == "river" and 4 in roles:
        bonus += 1.5
    elif terrain == "fortress" and side == 1:
        bonus += 1.5
    elif terrain == "gorge":
        bonus += 1.0
    return bonus
