"""2–4 week wuxia expeditions with persistent crews and week-by-week events.

The board, events and outcomes use a private deterministic RNG. The world RNG
that creates historical fighters is deliberately untouched. Monetary amounts,
injury risk and reward multipliers are provisional balancing assumptions.
"""
from __future__ import annotations

import hashlib
import random


def _rng(*parts):
    key=':'.join(map(str,parts)).encode('utf-8')
    return random.Random(int.from_bytes(hashlib.blake2b(key,digest_size=16).digest(),'big'))


# Each project can be completed entirely in the playable 1–51 weekly window.
TEMPLATES=(
    dict(key='herbal_pass',title='천령산 약재 호송',category='호송',duration=2,
         story='전염병이 돌기 시작한 산촌으로 구급 약재를 운반한다.',
         roles=(0,2,4),difficulty=1,reward=1.24,
         stages=('절벽 아래에서 약재 수레를 점검한다.','폭우로 무너진 산길에 도착했다.'),
         endings=('산촌에 제때 도착해 상단의 추가 사례금을 받았다.','약재를 안전하게 전달했다.',
                  '도착이 늦어 일부 약재를 버려야 했다.','약재를 지키지 못해 돌아왔다.')),
    dict(key='border_escort',title='변방 표국 장거리 호송',category='호송',duration=3,
         story='세 개 고을을 지나는 긴 호송길에 경계 인원을 파견한다.',
         roles=(0,1,2),difficulty=2,reward=1.48,
         stages=('표국과 함께 장거리 행렬을 꾸렸다.','갈림길에서 도적의 흔적을 발견했다.','국경의 검문소가 호송을 막아섰다.'),
         endings=('매복을 간파하고 모든 화물을 지켜 특별 포상을 받았다.','호송 대상과 물자를 무사히 넘겼다.',
                  '약속된 화물 일부를 잃었지만 목적지에 도달했다.','호송이 무산돼 최소한의 인원만 귀환했다.')),
    dict(key='ruins_codex',title='폐사찰 비급 조사',category='탐색',duration=3,
         story='버려진 사찰 깊은 곳에 오래된 무공 필사본이 남아 있다고 한다.',
         roles=(3,5,2),difficulty=3,reward=1.60,
         stages=('무너진 사찰의 오래된 지도를 펼쳤다.','지하 회랑에서 미로와 함정을 마주했다.','봉인된 서고의 마지막 문을 발견했다.'),
         endings=('온전한 비급과 역사 기록을 확보해 큰 대가를 받았다.','흩어진 비급을 모아 의뢰를 마쳤다.',
                  '손상된 기록 일부만 들고 돌아왔다.','함정에 막혀 서고를 확인하지 못했다.')),
    dict(key='healer_village',title='장기 산촌 의료 지원',category='구호',duration=4,
         story='산골 마을에서 계절성 괴질이 돌기 시작해 장기 지원이 필요하다.',
         roles=(4,3,0),difficulty=2,reward=1.55,
         stages=('마을의 환자들을 진찰하고 물자를 배분한다.','약초를 구하러 산 너머 숲에 들어갔다.',
                 '추가 환자가 발생해 간호 인력이 부족해졌다.','회복한 마을 사람들의 귀환을 돕는다.'),
         endings=('병의 근원을 찾아 마을을 완전히 구했다.','마을의 전염을 막고 주민을 돌봤다.',
                  '대부분 회복했으나 추가 지원을 요청했다.','의료 물자 부족으로 지원을 중단했다.')),
    dict(key='smugglers_trail',title='밀수 조직 잠입 추적',category='정보',duration=2,
         story='하룻밤 새 사라지는 물자와 밀수책을 뒤쫓는다.',
         roles=(5,3,2),difficulty=3,reward=1.37,
         stages=('암시장에 잠입해 거래 장부를 찾아 나섰다.','밀수단의 비밀 집회 장소를 찾아냈다.'),
         endings=('밀수 조직의 우두머리와 장부를 동시에 확보했다.','관련 정보를 빼내고 발각되기 전에 돌아왔다.',
                  '거래 일부만 확인하고 서둘러 철수했다.','정체가 드러나 추적을 포기했다.')),
    dict(key='mine_treaty',title='철광 운송로 개척',category='교역',duration=4,
         story='산채와 마을 사이의 낡은 철광 운송로를 조사하고 협약을 맺는다.',
         roles=(1,0,3),difficulty=2,reward=1.60,
         stages=('낡은 광산 진입로를 조사한다.','석공과 운송상 사이의 분쟁이 커졌다.',
                 '낙석으로 새로운 길을 찾아야 한다.','협약 조건을 최종 조정한다.'),
         endings=('안전한 운송로와 장기 협정을 동시에 확보했다.','교역로를 열고 양측의 약속을 받아냈다.',
                  '임시 통로만 마련해 일부 보상을 받았다.','교역로를 개척하지 못한 채 돌아왔다.')),
)
BY_KEY={x['key']:x for x in TEMPLATES}
APPROACHES={'cautious':'신중하게','balanced':'정석대로','bold':'과감하게'}
CHOICES={'safe':'안전을 우선한다','push':'위험을 감수하고 밀어붙인다','withdraw':'원정을 중단하고 귀환한다'}
RESULTS={'exceptional':'대성공','success':'성공','partial':'부분 성공',
         'failure':'실패','abandoned':'중도 포기','unfunded':'비용 부족 취소',
         'disrupted':'원정 중단','progress':'진행 중'}
assert len({x['key'] for x in TEMPLATES})==len(TEMPLATES)
assert all(2<=x['duration']<=4 and len(x['stages'])==x['duration'] for x in TEMPLATES)


def board(seed,gid,season,week,tier,gross_base,cost_base):
    """Six unique offers, but exclude expeditions that cannot finish by week 51."""
    rng=_rng('expedition-board-v1',seed,gid,season,week)
    templates=list(TEMPLATES)
    rng.shuffle(templates)
    cards=[]
    for item in templates:
        duration=item['duration']
        if week+duration-1>51:
            continue
        initial=max(1,round(cost_base*(1.25+.15*duration)))
        upkeep=max(1,round(cost_base*.62))
        payout=max(1,round(gross_base*duration*item['reward']))
        cards.append(dict(
            id=f"lx{season}-{week}-{gid}-{item['key']}",key=item['key'],
            title=item['title'],story=item['story'],category=item['category'],
            duration=duration,min_members=2,max_members=5,
            difficulty=item['difficulty'],recommended_roles=list(item['roles']),
            reward=payout,initial_cost=initial,weekly_cost=upkeep,
            # Total nominal cost includes recurring upkeep and initial supplies.
            total_estimated_cost=initial+(duration-1)*upkeep,
        ))
    return cards


def preview(task):
    """Event shown BEFORE the player chooses how to navigate the coming week."""
    item=BY_KEY[task['key']]
    index=task['progress']
    return dict(stage=index+1,stage_total=task['duration'],
                description=item['stages'][index],choices=CHOICES.copy())


def start(offer,member_ids,approach,season,week):
    if approach not in APPROACHES:
        raise ValueError('지원하지 않는 원정 접근 방식입니다.')
    if not offer['min_members']<=len(member_ids)<=offer['max_members']:
        raise ValueError('장기 임무 편성 인원이 올바르지 않습니다.')
    if len(set(member_ids))!=len(member_ids):
        raise ValueError('중복된 문파원이 있습니다.')
    return dict(id=offer['id'],key=offer['key'],title=offer['title'],
                guild_id=None,season=season,start_week=week,
                duration=offer['duration'],progress=0,members=list(member_ids),
                approach=approach,reward=offer['reward'],
                initial_cost=offer['initial_cost'],weekly_cost=offer['weekly_cost'],
                difficulty=offer['difficulty'],momentum=0.0,
                bonus=1.0,spent=0,events=[])


def step(task,seed,week,team,choice='safe'):
    """Advance exactly one funded week; returns a story event and optional finale.

    Cash accounting is handled by the caller. This is deterministic and never
    changes the global world RNG.
    """
    if choice not in ('safe','push'):
        raise ValueError('잘못된 원정 진행 선택입니다.')
    item=BY_KEY[task['key']]
    index=task['progress']
    if index>=task['duration']:
        raise ValueError('이미 완료한 원정입니다.')
    rng=_rng('expedition-week-v1',seed,task['id'],week,
             *sorted(f.fid for f in team),choice)
    # Optional hard approach applies to the whole expedition; the weekly choice
    # changes success odds but never silently increases cash or hires members.
    success_threshold=(.77 if choice=='safe' else .50)
    success_threshold-=.045*(task['difficulty']-1)
    safe=rng.random()<success_threshold
    if choice=='safe':
        modifier=.075 if safe else -.045
    else:
        modifier=.18 if safe else -.14
        task['bonus']*=1.07 if safe else .96
    task['momentum']+=modifier
    task['progress']+=1
    event=dict(stage=task['progress'],choice=choice,
               text=item['stages'][index],
               outcome=('무사히 고비를 넘겼다.' if safe else '예상치 못한 난관에 부딪혔다.'),
               momentum=round(task['momentum'],3))
    task['events'].append(event)
    if task['progress']<task['duration']:
        return dict(status='progress',event=event,final=None)
    average_power=sum(f.ca+.14*f.lv-.10*f.fatigue for f in team)/len(team)
    role_match=len({f.role for f in team} & set(item['roles']))
    chance=(.53+.0014*average_power+.034*role_match
            -.075*(task['difficulty']-1)+task['momentum']
            +{'cautious':.07,'balanced':0,'bold':-.07}[task['approach']])
    chance=max(.16,min(.92,chance))
    final_rng=_rng('expedition-final-v1',seed,task['id'],
                   *sorted(f.fid for f in team))
    draw=final_rng.random()
    if draw<chance*.12: outcome='exceptional'; factor=1.58;score=1.25
    elif draw<chance:outcome='success';factor=1.0;score=.85
    elif draw<chance+(1-chance)*.64:outcome='partial';factor=.38;score=.25
    else:outcome='failure';factor=.10;score=0
    factor*=task['bonus']*{'cautious':.85,'balanced':1.0,'bold':1.18}[task['approach']]
    gross=max(0,round(task['reward']*factor))
    injury_risk=(.014+.014*(task['difficulty']-1))*(
        1.7 if outcome=='failure' else 1.15 if outcome=='partial' else .45)
    injury_risk*={'cautious':.6,'balanced':1,'bold':1.45}[task['approach']]
    injured=[f.fid for f in team if final_rng.random()<injury_risk]
    final=dict(status=outcome,outcome_label=RESULTS[outcome],
               narrative=item['endings'][('exceptional','success','partial','failure').index(outcome)],
               gross=gross,score=score,injured=injured,chance=round(chance,4))
    return dict(status=outcome,event=event,final=final)
