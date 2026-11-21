"""v11-1: real weekly development history and primary-eight cultivation view.

Zero simulation, no cash transfers, no training orders committed here.
Snapshots are captured only on real player acquisition or weekly settlement,
never generated to fabricate unavailable old-save history.
"""
from __future__ import annotations

from statistics import mean

import moonpa_prebattle as tactics
import moonpa_market_intel as intelligence

ATTR_LABELS=dict(zip(tactics.ATTRIBUTES,
    ('근력','방어','체력','민첩','내공','술법','통찰','정신력')))
KEEP_WEEKS=156  # latest three playable seasons; first acquisition stays separately
WINDOWS=(5,10)


def ensure(world):
    if not hasattr(world,'growth_history'):
        world.growth_history={}
    if not hasattr(world,'growth_first'):
        world.growth_first={}


def number(f):
    return round(f.ca,2)


def global_week(season,week):
    return (season-1)*51+week


def _sample(f,season,week,phase,gid,activity):
    return dict(season=season,week=week,tick=global_week(season,week),
                phase=phase,guild_id=gid,ca=number(f),pa=round(f.pa,2),
                level=f.lv,attrs=tactics.stats(f),
                fatigue=round(f.fatigue,1),injured=f.injured,
                activity=activity)


def _append(world,f,sample):
    ensure(world)
    fid=f.fid
    history=world.growth_history.setdefault(fid,[])
    # Retry/re-entry of the same settled week must never double-write.
    identity=(sample['season'],sample['week'],sample['phase'])
    if history and (history[-1]['season'],history[-1]['week'],history[-1]['phase'])==identity:
        return False
    if history and sample['tick']<history[-1]['tick']:
        raise AssertionError('성장 기록의 주차가 역행했습니다.')
    history.append(sample)
    if len(history)>KEEP_WEEKS+3:
        del history[:len(history)-(KEEP_WEEKS+3)]
    world.growth_first.setdefault(fid,dict(sample))
    return True


def record_join(world,f,season,week,gid,kind='영입'):
    """Fighter's first known observation, including midseason draft/transfer."""
    sample=_sample(f,season,week,'joined',gid,kind)
    return _append(world,f,sample)


def record_founding(game):
    """Only fresh campaigns: past history of restored old saves is not invented."""
    for f in game.guild.fighters:
        record_join(game.world,f,game.season,game.week,game.guild.gid,'초기 문파원')


def activity_for(plan,battle,zone):
    schedule={}
    if plan is not None:
        for label,key in (('집중 훈련','training'),('2군 수련','second'),
                          ('대기 수련','overflow_bench'),('수익 임무','missions'),
                          ('장기 원정','long_active'),('정예 임무','elite_active'),
                          ('구역 방어','defend'),('휴식','rest')):
            items=plan.get(key,[])
            if key=='missions':
                items=[f for team in items for f in team]
            for f in items:
                schedule[f.fid]=label
    if battle is not None:
        kind='정예 임무 전투' if zone is None else '점령전'
        for u in battle.units.values():
            if u.side==0:schedule[u.id]=kind
    return schedule


def record_week(game,season,week,plan=None,battle=None,zone=None):
    """Call after actual weekly growth, before rollover. Retain a bounded window."""
    if not game.interactive or season<1 or week<1 or week>51:
        return 0
    ensure(game.world)
    cutoff=global_week(season,week)-KEEP_WEEKS
    # Departed heroes retain their first observation permanently; their
    # full weekly trail is only kept while it is within three seasons.
    for fid,rows in list(game.world.growth_history.items()):
        recent=[r for r in rows if r['tick']>=cutoff]
        if recent:game.world.growth_history[fid]=recent
        else:del game.world.growth_history[fid]
    statuses=activity_for(plan,battle,zone)
    count=0
    for f in game.guild.fighters:
        if _append(game.world,f,_sample(f,season,week,'close',game.guild.gid,
                                        statuses.get(f.fid,'자동/기타'))):
            count+=1
    return count


def _samples(world,fid):
    return getattr(world,'growth_history',{}).get(fid,[])


def series(world,fid):
    """Only actual recorded observations; no artificial interpolation."""
    samples=_samples(world,fid)
    seen=set()
    points=[]
    for sample in reversed(samples):
        # One point per week, closing sample wins over earlier acquisition.
        tick=sample['tick']
        if tick in seen:continue
        seen.add(tick)
        points.append(sample)
    return list(reversed(points))


def continuous_series(world,fid):
    """Latest uninterrupted run of weekly observations; no bridged career gaps."""
    rows=series(world,fid)
    if not rows:return []
    active=[rows[-1]]
    for previous in reversed(rows[:-1]):
        if active[-1]['tick']-previous['tick']!=1:break
        active.append(previous)
    return list(reversed(active))


def change(world,f,period):
    """Compare only real consecutive weeks; an old transfer gap is not 5 weeks."""
    items=continuous_series(world,f.fid)
    if not items:
        return dict(delta=None,observed_weeks=0,complete=False,baseline=None)
    count=min(period,len(items)-1)
    anchor=items[-1-count]
    span=items[-1]['tick']-anchor['tick']
    return dict(delta=round(number(f)-anchor['ca'],2),
                observed_weeks=span,complete=span==period,
                baseline=round(anchor['ca'],2),
                baseline_season=anchor['season'],baseline_week=anchor['week'])


def _formation(game,mode):
    if mode not in ('attack','defense'):
        raise ValueError('점령조 또는 방어조를 선택하세요.')
    roster=tactics._public_roster(game)
    plans=getattr(game.world,'prebattle_plans',{})
    saved=plans.get(mode,{})
    formation=None;captain=deputy=None
    source='부문주 기본 추천'
    if (saved.get('season'),saved.get('week'))==(game.season,game.week):
        data=saved.get('data',{})
        if intelligence._valid_saved_lineup(game,data):
            formation=[dict(id=e['id'],row=e['row']) for e in data['formation']]
            captain, deputy=data.get('captain'),data.get('deputy')
            if captain not in {e['id'] for e in formation}:captain=None
            if deputy not in {e['id'] for e in formation} or deputy==captain:deputy=None
            source=f'저장된 {("점령전" if mode=="attack" else "방어전")} 편성'
    if formation is None:
        auto=tactics.deputy_pick(roster,{'ranged_count':0})
        formation=[dict(id=e['id'],row=e['row']) for e in auto['formation']]
        captain,deputy=auto['captain'],auto['deputy']
    return dict(formation=formation,captain=captain,deputy=deputy,source=source)


def _training_status(game,f):
    if game.phase!='ready' or game.pending_week is not None or (
            game.battle is not None and game.battle.winner is None):
        return dict(can_train=False,reason='현재 주간 배치 단계가 아닙니다.')
    if f.injured:return dict(can_train=False,reason=f'부상 {f.injured}주')
    if f.fid in game.world.away(game.guild.gid):
        return dict(can_train=False,reason='장기 원정 중')
    if f.ca>=f.pa-.01:
        return dict(can_train=True,reason='잠재력 한계에 가까워 수련 효율이 낮습니다.')
    return dict(can_train=True,reason='주간 운영에서 집중 훈련 배치 가능')


def _shortage(role_counts,f):
    count=role_counts.get(f.role,0)
    if f.role in (0,4):
        return (13 if count==1 else 6 if count==2 else 0)
    if f.role in (1,2):
        return (10 if count==1 else 4 if count==2 else 0)
    return 5 if count==1 else 1 if count==2 else 0


def recommendation(game,team_members,role_counts):
    """Explanatory heuristic; CA projections or actual win rates not claimed."""
    ranked=[]
    for fighter in team_members:
        f=fighter['fighter']
        gap=max(0,f.pa-f.ca)
        trend=fighter['growth_5']['delta']
        ready=fighter['training']['can_train']
        importance=_shortage(role_counts,f)
        growth=min(45,gap*.45)
        trend_score=8 if trend is not None and trend>=1 else 4 if trend is not None and trend>0 else 0
        score=round(growth+importance+trend_score+(8 if ready else -30),1)
        reasons=[]
        if importance>=10:
            reasons.append(f'주력 8인에서 {tactics.ROLE_NAMES[f.role]} {role_counts[f.role]}명으로 역할 보강 우선')
        if gap>=25:reasons.append(f'잔여 성장 여지 {gap:.1f}')
        elif gap<4:reasons.append('잠재 한계에 가까워 추가 투자 효율 제한')
        if trend is not None and trend>0 and fighter['growth_5']['observed_weeks']>0:
            reasons.append(f'최근 실제 기록에서 CA +{trend:.1f}')
        if not ready:reasons.append(fighter['training']['reason'])
        if not reasons:reasons.append('역할·현재 전력·잠재 여력을 종합 검토')
        ranked.append(dict(id=f.fid,name=f.name,role=tactics.ROLE_NAMES[f.role],
                           score=score,can_train=ready,
                           reasons=reasons[:3]))
    return sorted(ranked,key=lambda x:(not x['can_train'],-x['score'],x['id']))


def dashboard(game,mode='attack'):
    plan=_formation(game,mode)
    by_id={f.fid:f for f in game.guild.fighters}
    history=getattr(game.world,'growth_history',{})
    available=plan['formation']
    members=[]
    role_counts={i:0 for i in range(6)}
    for position in available:
        f=by_id.get(position['id'])
        if f is None:continue
        role_counts[f.role]+=1
        first=getattr(game.world,'growth_first',{}).get(f.fid)
        recent_5=change(game.world,f,5)
        recent_10=change(game.world,f,10)
        timeline=continuous_series(game.world,f.fid)
        last=timeline[-1] if timeline else None
        # Current stats are live; older weeks have immutable recorded snapshots.
        attr_deltas=(dict((k,round(tactics.stats(f)[k]-timeline[0]['attrs'][k],2))
                          for k in tactics.ATTRIBUTES) if timeline else None)
        members.append(dict(fighter=f,id=f.fid,name=f.name,
            role=tactics.ROLE_NAMES[f.role],role_id=f.role,
            row=position['row'],captain=f.fid==plan['captain'],deputy=f.fid==plan['deputy'],
            level=f.lv,ca=number(f),pa=round(f.pa,2),gap=round(max(0,f.pa-f.ca),2),
            attrs=tactics.stats(f),initial_ca=first['ca'] if first else None,
            first_record=(dict(season=first['season'],week=first['week'])
                          if first else None),
            total_delta=round(number(f)-first['ca'],2) if first else None,
            growth_5=recent_5,growth_10=recent_10,
            stat_deltas=attr_deltas,
            recent_activity=last['activity'] if last else '기록 없음',
            training=_training_status(game,f)))
    def mean_or_none(nums):
        return round(mean(nums),2) if nums else None
    week5=[x['growth_5']['delta'] for x in members
           if x['growth_5']['delta'] is not None and x['growth_5']['observed_weeks']>0]
    week10=[x['growth_10']['delta'] for x in members
           if x['growth_10']['delta'] is not None and x['growth_10']['observed_weeks']>0]
    result=[]
    for item in members:
        entry={k:v for k,v in item.items() if k!='fighter'}
        entry['history']=[
            dict(season=x['season'],week=x['week'],phase=x['phase'],ca=x['ca'],
                 pa=x['pa'],level=x['level'],attrs=x['attrs'],
                 activity=x['activity'],fatigue=x['fatigue'],injured=x['injured'])
            for x in continuous_series(game.world,item['id'])[-11:]]
        result.append(entry)
    roster=tactics._public_roster(game)
    diag=tactics.diagnose(roster,available) if len(available)==8 else None
    missing_roles=[]
    if not role_counts[0]:missing_roles.append('수호형 부재: 전열 보호 인재 영입 검토')
    if not role_counts[4]:missing_roles.append('치유형 부재: 치유 인재 영입 검토')
    if not role_counts[2]:missing_roles.append('사수형 부재: 원거리 화력 인재 검토')
    if not role_counts[1]+role_counts[5]:
        missing_roles.append('돌파조 부재: 무인·암살형 영입 검토')
    return dict(mode=mode,source=plan['source'],season=game.season,week=game.week,
                roster_size=len(game.guild.fighters),
                ready=game.phase=='ready' and game.pending_week is None,
                captain=plan['captain'],deputy=plan['deputy'],
                members=result,role_counts={str(k):v for k,v in role_counts.items()},
                summary=dict(complete=len(members)==8,
                    avg_ca=mean_or_none([x['ca'] for x in members]),
                    avg_pa=mean_or_none([x['pa'] for x in members]),
                    avg_gap=mean_or_none([x['gap'] for x in members]),
                    growth_5=mean_or_none(week5),growth_5_sample=len(week5),
                    growth_10=mean_or_none(week10),growth_10_sample=len(week10),
                    front=sum(x['row']=='front' for x in members),
                    back=sum(x['row']=='back' for x in members),
                    diagnosis=diag),
                recommendations=recommendation(game,members,role_counts),
                missing_roles=missing_roles,
                note=('주력 명단이 8명 미만입니다. 가용 문파원을 확보하거나 부상·원정 상태를 확인하세요.'
                      if len(members)<8 else
                      '현재 편성 기준 육성 분석입니다. 저장되지 않은 지난 주 기록은 추정하지 않으며 수련 추천은 실제 배치가 아닙니다.'),
                history_note=('기록은 주간 결산 이후에만 추가됩니다. 최초 등록 시점 이전의 데이터는 존재하지 않습니다. '
                              '차트는 실제 기록만 보여주며 성장값은 성과이지 미래 예측이 아닙니다.'),
                attribute_labels=ATTR_LABELS)
