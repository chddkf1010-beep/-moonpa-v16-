"""v11-3: read-only, roster-safe eight-person training planning.

A recommendation is a proposal for the browser's weekly draft, not a training
order. No economy, RNG, phase, saved formation or fighter fields mutate.
"""
from __future__ import annotations

import moonpa_economy_v15_1 as economy
import moonpa_growth_dashboard as growth

ACTIVITIES = frozenset(('auto', 'training', 'mission1', 'mission2',
    'expedition1', 'expedition2', 'elite', 'rest', 'defend', 'attack'))


def preview(game, mode='attack', assignments=None, count=4):
    if mode not in ('attack', 'defense'):
        raise ValueError('점령조 또는 방어조를 선택하세요.')
    if type(count) is not int or not 1 <= count <= 8:
        raise ValueError('추천할 훈련 인원은 1~8명이어야 합니다.')
    if assignments is None:
        assignments = {}
    if type(assignments) is not dict:
        raise ValueError('주간 배치 입력 형식이 올바르지 않습니다.')
    roster = {f.fid: f for f in game.guild.fighters}
    normalized = {}
    for raw_id, activity in assignments.items():
        if type(raw_id) is not str or not raw_id.isdecimal() or type(activity) is not str:
            raise ValueError('주간 배치 정보가 올바르지 않습니다.')
        fid = int(raw_id)
        if fid not in roster or str(fid) != raw_id or activity not in ACTIVITIES:
            raise ValueError('현재 문파원 및 주간 배치 상태를 다시 확인하세요.')
        normalized[fid] = activity
    ready = (game.phase == 'ready' and game.pending_week is None
             and (game.battle is None or game.battle.winner is not None)
             and not game.world.player_bankrupted)
    away = game.world.away(game.guild.gid)
    # Existing manual assignments, including rest and training, are never
    # overwritten. Away members already consume active first-team places.
    directly_assigned = sum(v != 'auto' for v in normalized.values())
    free_first = max(0, 20 - directly_assigned
                     - sum(fid not in normalized or normalized[fid] == 'auto' for fid in away))
    dashboard = growth.dashboard(game, mode)
    by_id = {m['id']: m for m in dashboard['members']}
    ranked = []
    for recommendation in dashboard['recommendations']:
        fid = recommendation['id']
        f = roster[fid]
        activity = normalized.get(fid, 'auto')
        if not ready:
            status, reason = 'locked', '현재 주간 배치를 변경할 수 없습니다.'
        elif fid in away:
            status, reason = 'away', '장기 원정 중'
        elif f.injured:
            status, reason = 'injured', f'부상 {f.injured}주'
        elif activity == 'training':
            status, reason = 'already', '이미 집중 훈련에 배치됨'
        elif activity != 'auto':
            status, reason = 'reserved', '기존 배치 유지: ' + activity
        else:
            status, reason = 'available', '배치 가능'
        ranked.append(dict(id=fid, name=f.name, role=by_id[fid]['role'],
                           ca=by_id[fid]['ca'], pa=by_id[fid]['pa'],
                           gap=by_id[fid]['gap'], score=recommendation['score'],
                           status=status, status_reason=reason,
                           reasons=recommendation['reasons']))
    candidates = [row for row in ranked if row['status'] == 'available']
    selected = candidates[:min(count, free_first)]
    selected_ids = [row['id'] for row in selected]
    unit_cost = economy.TIERS[game.guild.tier]['training_cost']
    nominal = unit_cost * len(selected_ids)
    # Deliberately exclude automatic first-team fill, 2nd squad, mentors and
    # economy ordering. This is NOT a guaranteed all-in weekly training bill.
    fixed = game.operations_view()['fixed']
    cash = game.guild.cash
    conservative_cash = max(0, cash-fixed)
    warning = ''
    if not ready:
        warning = '현재 주간 배치 단계가 아니므로 추천을 적용할 수 없습니다.'
    elif free_first == 0:
        warning = '직접 배치할 수 있는 1군 20명이 이미 모두 지정되었습니다.'
    elif len(selected_ids) < count:
        warning = '배치 가능한 주력 인원 또는 1군 잔여 자리가 부족합니다.'
    elif nominal > conservative_cash:
        warning = '보유금에서 기본 고정 지출을 제외하면 추천 훈련비보다 적습니다.'
    return dict(mode=mode, season=game.season, week=game.week, ready=ready,
                count=count, selected_ids=selected_ids, members=ranked,
                available_count=len(candidates), free_first=free_first,
                already_training=sum(v == 'training' for v in normalized.values()),
                unit_cost=unit_cost, direct_nominal_cost=nominal,
                fixed_cost=fixed, cash=cash, conservative_cash=conservative_cash,
                warning=warning,
                note=('추가 직접 집중 훈련 배치분의 명목 단가입니다. 실제 훈련비는 자동 배치, '
                      '2군·대기 인원, 주간 수익·채무 및 자금 부족에 따라 달라집니다. '
                      '추천·배치 단계에서는 능력치와 보유금이 변경되지 않습니다.'))
