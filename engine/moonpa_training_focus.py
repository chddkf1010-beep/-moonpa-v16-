"""v11-2 personal cultivation directions and deputy bulk recommendations.

Focus is a persistent, fighter-owned policy. It only redistributes weekly
paid-training growth after the established economy decides the actual gain.
No financial charge, power increase, weekly advancement, RNG or combat change
occurs when changing this setting. AI guilds always use balanced training.
"""
from __future__ import annotations

from moonpa_growth import ATTRIBUTES, TRAINING_FOCUSES, training_factors

ROLE_DEFAULTS={
    0:('defense','수호형 전선 유지에 필요한 방어·체력 보강'),
    1:('attack','무인형 전방 돌파를 위한 근력·민첩 보강'),
    2:('ranged','사수형 원거리 화력을 위한 민첩·통찰 보강'),
    3:('internal','주술형 내공·술법 성장 집중'),
    4:('support','치유형 생존·지원에 필요한 체력·정신력 보강'),
    5:('attack','암살형 돌파와 침투를 위한 근력·민첩 보강'),
}
ATTRIBUTE_NAMES={
    'strength':'근력','defense':'방어','stamina':'체력',
    'agility':'민첩','inner_power':'내공','sorcery':'술법',
    'insight':'통찰','willpower':'정신력'
}


def get(world,fid):
    value=getattr(world,'training_focus',{}).get(fid,'balanced')
    return value if value in TRAINING_FOCUSES else 'balanced'


def options():
    return [dict(id=key,name=data[0],description=data[2],
                 targets=list(data[1]))
            for key,data in TRAINING_FOCUSES.items()]


def suggest(fighter):
    role=ROLE_DEFAULTS[fighter.role]
    # Investing near the PA ceiling still uses normal training rules, but
    # without a meaningful gap a neutral focus is more interpretable.
    if fighter.pa-fighter.ca<2:
        return dict(focus='balanced',
                    reason='잠재력 상한에 가까워 균형 수련 권장')
    return dict(focus=role[0],reason=role[1])


def profile(world,f):
    focus=get(world,f.fid)
    recommend=suggest(f)
    factors=training_factors(f.role,focus)
    baseline=training_factors(f.role,'balanced')
    return dict(id=f.fid,focus=focus,focus_name=TRAINING_FOCUSES[focus][0],
                recommended=recommend['focus'],recommend_reason=recommend['reason'],
                allocation=[dict(key=key,name=ATTRIBUTE_NAMES[key],
                                 share=round(100*factor/sum(factors),1),
                                 balanced_share=round(100*old/sum(baseline),1),
                                 ratio=round(factor/old,3))
                            for key,factor,old in zip(ATTRIBUTES,factors,baseline)],
                note='수련 총량은 동일하고 능력치별 배분만 변경됩니다. 다음 실제 유료 집중·2군 수련부터 적용합니다.')


def _can_update(game):
    if game.phase!='ready' or game.pending_week is not None or (
            game.battle is not None and game.battle.winner is None):
        raise ValueError('주간 편성을 진행할 수 있을 때만 수련 방향을 바꿀 수 있습니다.')
    if game.world.player_bankrupted:
        raise ValueError('해체된 문파는 수련을 변경할 수 없습니다.')


def set_one(game,fid,focus):
    _can_update(game)
    if type(fid) is not int:
        raise ValueError('문파원 ID가 올바르지 않습니다.')
    if type(focus) is not str or focus not in TRAINING_FOCUSES:
        raise ValueError('지원하지 않는 수련 방향입니다.')
    fighter=next((f for f in game.guild.fighters if f.fid==fid),None)
    if fighter is None:
        raise ValueError('현재 내 문파원이 아닙니다.')
    previous=get(game.world,fid)
    if not hasattr(game.world,'training_focus'):
        game.world.training_focus={}
    # Explicit balanced choice is a manual override respected by bulk mode.
    game.world.training_focus[fid]=focus
    return dict(id=fid,previous=previous,current=focus,
                profile=profile(game.world,fighter),changed=previous!=focus)


def apply_deputy(game,mode='attack',overwrite=False):
    _can_update(game)
    if type(overwrite) is not bool:
        raise ValueError('기존 수련 방향 덮어쓰기 옵션이 올바르지 않습니다.')
    if mode not in ('attack','defense'):
        raise ValueError('점령조 또는 방어조를 선택하세요.')

    # Use the exact authoritative currently-saved formation from v11-1.
    import moonpa_growth_dashboard as dashboard
    formation=dashboard._formation(game,mode)['formation']
    if len(formation)!=8:
        raise ValueError('가용 주력 8명 편성이 완성되지 않았습니다.')
    by_id={f.fid:f for f in game.guild.fighters}
    if len({entry['id'] for entry in formation})!=8 or any(
            entry['id'] not in by_id for entry in formation):
        raise ValueError('현재 주력 8명을 확인할 수 없습니다.')

    existing=getattr(game.world,'training_focus',{})
    updates={}
    kept=[]
    for entry in formation:
        fid=entry['id']
        if fid in existing and not overwrite:
            kept.append(fid)
            continue
        updates[fid]=suggest(by_id[fid])['focus']

    # Apply atomically after complete validation; no partial edits on errors.
    if not hasattr(game.world,'training_focus'):
        game.world.training_focus={}
    game.world.training_focus.update(updates)
    return dict(mode=mode,overwrite=overwrite,changed_count=len(updates),
                preserved_count=len(kept),updated_ids=list(updates),
                recommendation=[dict(id=fid,**suggest(by_id[fid]))
                                for fid in [x['id'] for x in formation]],
                note='주력 8인에게 수련 방향만 지정했습니다. 배치·자금·경과 시간은 변경되지 않았습니다.')
