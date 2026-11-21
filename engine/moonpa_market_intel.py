"""Market intelligence for filters and non-mutating 8-member acquisition previews.

All current abilities are public, but only the EXISTING observed potential
(Campaign.free_agent_quote.pa) is exposed. No true hidden PA, recruitment
preferences, RNG, contracts, formation saving or cash settlement are touched.
"""
from __future__ import annotations

from combat import SKILLS
import moonpa_prebattle as tactics
import moonpa_economy_v15_1 as economy

TAG_BY_ROLE={
    0:('전열','전선 유지','후열 보호'),
    1:('전열','돌파'),
    2:('후열','사수','원거리 화력'),
    3:('후열','주술','약화'),
    4:('후열','치유','후열 보호'),
    5:('전열','돌파','후열 침투'),
}
ROLE_NAME={r:tactics.ROLE_NAMES[r] for r in range(6)}
METRICS=('frontline','rear_protection','breakthrough','ranged_fire')


def candidate_card(game, fighter):
    """Use the same observed PA quote users already get, never fighter.pa."""
    card=game.free_agent_quote(fighter)
    # The old market quote used actual PA. Do not propagate that value into
    # this scouting UI: use the public scouting estimate instead.
    card['pa']=round(economy.observed_pa(fighter),1)
    role=fighter.role
    note=card.get('notable')
    card.update(
        role_id=role,
        rarity=(note['rarity'] if note and note['rarity'] in ('named','legend')
                else 'normal'),
        attrs=tactics.stats(fighter),
        tags=list(TAG_BY_ROLE[role]),
        skills=[tactics.skill_description(k) for k in tactics.unlocked(fighter)],
        equipped=[tactics.skill_description(k) for k in tactics.equipped(fighter)],
        captain_ability=tactics.ability(fighter,'captain'),
        deputy_ability=tactics.ability(fighter,'deputy'),
        growth_gap=round(max(0,card['pa']-card['ca']),1),
    )
    return card


def _valid_saved_lineup(game,data):
    if not isinstance(data,dict) or not isinstance(data.get('formation'),list):
        return False
    formation=data['formation']
    if len(formation)!=8 or len({x.get('id') for x in formation if isinstance(x,dict)})!=8:
        return False
    by_id={f.fid:f for f in game.guild.fighters}
    away=game.world.away(game.guild.gid)
    for entry in formation:
        if not isinstance(entry,dict) or entry.get('row') not in ('front','back'):
            return False
        f=by_id.get(entry.get('id'))
        if f is None or f.injured or f.fid in away:
            return False
    if not 2<=sum(x['row']=='front' for x in formation)<=5:
        return False
    return True


def team_snapshot(game):
    roster=tactics._public_roster(game)
    plans=getattr(game.world,'prebattle_plans',{})
    lineup=None
    source='부문주 기본 추천'
    # We do not demand that an attack zone is still selectable: a previously
    # saved roster formation remains informative even after ownership changes.
    for mode in ('attack','defense'):
        saved=plans.get(mode,{})
        if (saved.get('season'),saved.get('week'))==(game.season,game.week):
            data=saved.get('data',{})
            if _valid_saved_lineup(game,data):
                lineup=[dict(id=x['id'],row=x['row']) for x in data['formation']]
                source=f'저장된 {("점령전" if mode=="attack" else "방어전")} 편성'
                break
    if lineup is None:
        auto=tactics.deputy_pick(roster,{'ranged_count':0})
        lineup=[dict(id=x['id'],row=x['row']) for x in auto['formation']]
    by_id={f['id']:f for f in roster}
    selected=[dict(id=x['id'],name=by_id[x['id']]['name'],role=by_id[x['id']]['role'],
                   role_id=by_id[x['id']]['role_id'],row=x['row'],
                   ca=by_id[x['id']]['ca'],attrs=by_id[x['id']]['attrs'])
              for x in lineup]
    roles={n:sum(x['role_id']==n for x in selected) for n in range(6)}
    # Match tactic needs to the actual selected 8, not the entire guild.
    needs={
        0:5 if roles[0]==0 else 3 if roles[0]==1 else 0,
        1:4 if roles[1]==0 else 2 if roles[1]==1 else 0,
        2:4 if roles[2]==0 else 2 if roles[2]==1 else 0,
        3:3 if roles[3]==0 else 1 if roles[3]==1 else 0,
        4:5 if roles[4]==0 else 2 if roles[4]==1 else 0,
        5:3 if roles[5]==0 else 1 if roles[5]==1 else 0,
    }
    notes=[]
    if roles[0]==0:notes.append('수호형 부재: 전열 방어 보강 우선')
    if roles[4]==0:notes.append('치유형 부재: 후열 생존력 보강 우선')
    if roles[1]+roles[5]==0:notes.append('돌파조 부재: 무인·암살형 보강 권장')
    if roles[2]==0:notes.append('사수 부재: 원거리 화력 보강 권장')
    if not notes:notes.append('주력 8인 편성의 주요 역할을 고르게 확보했습니다.')
    return dict(source=source,members=selected,
                diagnosis=tactics.diagnose(roster,lineup) if len(lineup)==8 else None,
                role_counts={str(k):v for k,v in roles.items()},
                role_needs={str(k):v for k,v in needs.items()},
                needs=notes,
                note=('편성 미완료: 가용 문파원 8명이 필요합니다.'
                      if len(lineup)!=8 else
                      '해당 평가는 8인 역할 구성과 실제 현재 능력치를 사용한 전술 참고치입니다. 승률이 아닙니다.'))


def snapshot(game):
    team=team_snapshot(game)
    return dict(season=game.season,week=game.week,cash=game.guild.cash,
                terms_years=list(range(1,6)),
                normal_roster_limit=economy.MAX_ROSTER,roster_count=len(game.guild.fighters),
                roster_limit=economy.MAX_TEMP_ROSTER,
                refresh_note='낭인 풀은 다음 주차 진행 시 바뀔 수 있으며 신규 계약·이탈은 보장된 시간이 아닙니다.',
                attribute_labels={key:name for key,name in zip(
                    tactics.ATTRIBUTES,('근력','방어','체력','민첩','내공','술법','통찰','정신력'))},
                team=team,
                candidates=[candidate_card(game,f) for f in game.world.fa if f.age<=42])


def _replacement(team,card,explicit):
    group=team['members']
    if explicit is not None:
        if type(explicit) is not int:
            raise ValueError('교체 기준 문파원을 확인하세요.')
        item=next((u for u in group if u['id']==explicit),None)
        if item is None:
            raise ValueError('교체 기준은 현재 출전 8인 중에서 선택하세요.')
        return item
    if not group:return None
    role=card['role_id']
    ideal='front' if role in tactics.FRONT_ROLES else 'back'
    same_role=[x for x in group if x['role_id']==role]
    same_row=[x for x in group if x['row']==ideal]
    return min(same_role or same_row or group,key=lambda x:(x['ca'],x['id']))


def compare(game,ids,replace_id=None):
    """Read-only batch comparison: maximum three current free agent IDs."""
    if (type(ids) is not list or not 1<=len(ids)<=3
            or any(type(fid) is not int for fid in ids)
            or len(set(ids))!=len(ids)):
        raise ValueError('비교 후보는 서로 다른 낭인 1~3명이어야 합니다.')
    active={f.fid:f for f in game.world.fa if f.age<=42}
    if any(fid not in active for fid in ids):
        raise ValueError('시장 매물이 바뀌었습니다. 후보를 다시 선택하세요.')
    team=team_snapshot(game)
    all_ours=tactics._public_roster(game)
    base=team['diagnosis']
    comparisons=[]
    for fid in ids:
        fighter=active[fid]
        card=candidate_card(game,fighter)
        replacement=_replacement(team,card,replace_id)
        delta=None
        before=None
        after=None
        note=''
        warning=''
        if replacement:
            before=next(f for f in game.guild.fighters if f.fid==replacement['id'])
            rows=[dict(id=(fid if x['id']==before.fid else x['id']),row=x['row'])
                  for x in team['members']]
            replaced=dict(tactics.fighter_card(fighter),id=fid)
            after=tactics.diagnose([*all_ours,replaced],rows)
            delta={key:after[key]-base[key] for key in METRICS}
            note=f'{before.name} 대신 {fighter.name}을(를) 같은 {("전열" if replacement["row"]=="front" else "후열")} 슬롯에 배치했을 때의 단순 특성 변화입니다.'
            # Do not silently reassign captains/deputies or claim those buffs apply.
            stored=getattr(game.world,'prebattle_plans',{}).get('attack',{})
            data=stored.get('data',{}) if stored.get('season')==game.season and stored.get('week')==game.week else {}
            if before.fid in (data.get('captain'),data.get('deputy')):
                warning='교체 대상이 기존 대장 또는 부대장입니다. 실제 편성에서는 지휘 보직을 다시 지정해야 합니다.'
        comparisons.append(dict(candidate=card,replacement=replacement,
                                baseline=base,after=after,delta=delta,
                                replaced_ca=round(before.ca,1) if before else None,
                                replaced_pa=round(before.pa,1) if before else None,
                                # The incoming candidate is not yet in guild and no
                                # hypothetical signing or lineup mutation occurs.
                                note=note,warning=warning))
    return dict(team=team,comparisons=comparisons,
                disclaimer='영입·교체 미리보기 전용입니다. 전투 결과·승률·지휘 보너스나 실제 자금·명단·편성을 변경하지 않습니다. 낭인 PA는 관측 추정치이고 기존 문파원 PA는 보유 명단의 값입니다.')
