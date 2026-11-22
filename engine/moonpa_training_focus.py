"""v11-2 personal cultivation directions and deputy bulk recommendations.

Focus is a persistent, fighter-owned policy. It only redistributes weekly
paid-training growth after the established economy decides the actual gain.
No financial charge, power increase, weekly advancement, RNG or combat change
occurs when changing this setting. AI guilds always use balanced training.
"""
from __future__ import annotations

import hashlib
import json

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


def preview_deputy(game,mode='attack',overwrite=False):
    """Read-only, exact eight-person proposal for the current formation.

    An explicit balanced setting counts as a manual choice. The proposal
    never changes the roster, the plan, money, RNG, or save contents.
    """
    _can_update(game)
    if type(overwrite) is not bool:
        raise ValueError('기존 수련 방향 덮어쓰기 옵션이 올바르지 않습니다.')
    if mode not in ('attack','defense'):
        raise ValueError('점령조 또는 방어조를 선택하세요.')

    import moonpa_growth_dashboard as dashboard
    formation=dashboard._formation(game,mode)['formation']
    if len(formation)!=8:
        raise ValueError('가용 주력 8명 편성이 완성되지 않았습니다.')
    by_id={f.fid:f for f in game.guild.fighters}
    if len({entry['id'] for entry in formation})!=8 or any(
            entry['id'] not in by_id for entry in formation):
        raise ValueError('현재 주력 8명을 확인할 수 없습니다.')

    existing=getattr(game.world,'training_focus',{})
    members=[]
    for entry in formation:
        fid=entry['id']
        fighter=by_id[fid]
        suggested=suggest(fighter)
        manual=fid in existing
        preserved=manual and not overwrite
        current=get(game.world,fid)
        proposed=current if preserved else suggested['focus']
        members.append(dict(id=fid,name=fighter.name,role=('수호형','무인형','사수형','주술형','치유형','암살형')[fighter.role],
                            row=entry['row'],current=current,proposed=proposed,
                            recommended=suggested['focus'],reason=suggested['reason'],
                            manual=manual,preserved=preserved,changed=current!=proposed))

    # The client sends this back on commit to reject a stale proposal.
    # Include explicit override state (not just the effective focus), so a
    # newly-entered manual balanced selection also invalidates old previews.
    fingerprint=dict(season=game.season,week=game.week,mode=mode,
                     overwrite=overwrite,members=[
                         (m['id'],m['row'],m['current'],m['proposed'],m['manual'])
                         for m in members])
    token=hashlib.sha256(json.dumps(fingerprint,sort_keys=True,
                                   ensure_ascii=False).encode('utf-8')).hexdigest()
    return dict(mode=mode,overwrite=overwrite,token=token,members=members,
                selected_count=len(members),
                assigned_count=sum(not m['preserved'] for m in members),
                preserved_count=sum(m['preserved'] for m in members),
                effective_change_count=sum(m['changed'] for m in members),
                note='미리보기만으로는 수련 방향, 주간 배치, 보유금이나 게임 진행이 바뀌지 않습니다.')


def apply_deputy(game,mode='attack',overwrite=False,expected=None):
    """Apply only the proposal currently shown to the player."""
    if expected is not None and (type(expected) is not str or len(expected)!=64):
        raise ValueError('수련 추천 확인값이 올바르지 않습니다.')
    plan=preview_deputy(game,mode,overwrite)
    if expected is not None and plan['token']!=expected:
        raise ValueError('주력 편성 또는 수련 설정이 변경되었습니다. 추천안을 다시 확인하세요.')

    updates={m['id']:m['proposed'] for m in plan['members'] if not m['preserved']}
    # Apply atomically after validation; nothing mutates on stale preview.
    if not hasattr(game.world,'training_focus'):
        game.world.training_focus={}
    game.world.training_focus.update(updates)
    return dict(mode=mode,overwrite=overwrite,changed_count=len(updates),
                effective_change_count=plan['effective_change_count'],
                preserved_count=plan['preserved_count'],updated_ids=list(updates),
                recommendation=[dict(id=m['id'],focus=m['recommended'],reason=m['reason'])
                                for m in plan['members']],
                note='주력 8인에게 수련 방향만 지정했습니다. 배치·자금·경과 시간은 변경되지 않았습니다.')
