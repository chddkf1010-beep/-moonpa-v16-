"""Playable elite investigations, choices, tactical encounters and loot.

This module adds no global RNG consumption. The 3-5-person party fights a
matching 3-5-person encounter using the existing tactical Battle engine.
All cash, XP and persistent rewards still settle once in the weekly ledger.
"""
from __future__ import annotations

from combat import Battle, Unit, ROLE_SKILLS
import moonpa_elite as elite

SCENES={
 'jade_cave':(
  '석문을 밀자 동굴 벽에 청옥빛 문양이 피어났다. 무너진 기둥 뒤에서 발자국이 이어진다.',
  '봉인이 풀리는 소리와 함께 청옥 수호자들이 길을 막는다.',
  ('청옥 문지기','청옥 수호검','동굴 망령','봉인 파수꾼','청옥 술사')),
 'hermit_mountain':(
  '산문에는 검을 뽑지 말라는 경고와 낡은 돌바둑판이 남아 있다.',
  '은거 고수의 제자들이 진법을 펼쳐 마지막 자격을 시험한다.',
  ('문하 검수','은거 수호자','청명 무인','산문 수행자','묵객')),
 'poison_marsh':(
  '잃어버린 탐사대의 깃발이 검은 물가에 걸려 있다. 풀잎에는 독무가 내려앉았다.',
  '영초를 지키는 늪지의 사냥꾼들이 수면에서 모습을 드러낸다.',
  ('독무 추적자','늪지 수문장','독화 궁수','맹독 술사','영초 파수꾼')),
 'star_tablet':(
  '석비의 비문이 달빛 아래에서만 읽힌다. 움직이는 글자를 따라가자 통로가 열린다.',
  '석비의 비밀을 지키는 고대의 결계 무인들이 나타난다.',
  ('석비 검객','별빛 문지기','천문 궁수','천문 술사','석각 수호자')),
 'sword_tomb':(
  '버려진 검총에서 아직도 검을 부딪치는 소리가 들린다. 검집에는 붉은 실이 감겨 있다.',
  '검총을 점령한 무리와 맞서야 실종자들을 구출할 수 있다.',
  ('검총 원귀','묘역 무인','망령 궁수','그림자 검수','검총 수호자')),
 'village_oath':(
  '마을회관에는 찢긴 맹약서가 놓여 있다. 대표자들의 말이 엇갈린다.',
  '충돌을 부추긴 사병들이 마을 길목을 막아선다.',
  ('흑룡 사병','산채 무인','경계 궁수','촌락 파수꾼','흑룡 술사')),
}
DECISION={
 'study':dict(title='흔적을 면밀히 살핀다',
              summary='단서를 해독하고 적의 약점을 살핀다. 승리 보상은 신중하지만 기연 발견에 유리하다.',
              tone='조사한 약점을 바탕으로 진형을 펼쳤다.'),
 'guard':dict(title='동료의 안전을 우선한다',
              summary='부상 위험과 적의 압박을 낮춘다. 전리품 보상은 다소 적다.',
              tone='동료를 보호하며 안전한 진입로를 확보했다.'),
 'seize':dict(title='위험을 무릅쓰고 선점한다',
              summary='더 강한 적과 싸운다. 승리한다면 높은 보상과 희귀 기연을 기대할 수 있다.',
              tone='정면으로 돌파해 단서를 먼저 차지하기로 했다.'),
}
ENEMY_ROLES=(1,0,2,5,3)


def briefing(order):
    offer=order['offer']
    scene,threat,_=SCENES[offer['key']]
    return dict(title=offer['title'],story=offer['story'],scene=scene,
                warning=threat,lead=order['lead'].fid,lead_name=order['lead'].name,
                team=[dict(id=f.fid,name=f.name,role=elite.ROLE_NAMES[f.role]) for f in order['members']],
                difficulty=offer['difficulty_label'],
                saga=bool(offer.get('saga')),
                choices={key:dict(title=d['title'],description=d['summary'])
                         for key,d in DECISION.items()})


def make_battle(seed,gid,season,week,order,choice,actor_factory,equipment):
    if choice not in DECISION:
        raise ValueError('정예 임무의 현장 결정을 확인하세요.')
    team=order['members']
    if not 3<=len(team)<=5:
        raise ValueError('정예 임무에 3~5명이 필요합니다.')
    offer=order['offer']
    lead=order['lead']
    if lead not in team:
        raise ValueError('핵심 문파원이 임무에서 빠졌습니다.')
    rows=['front' if i<2 or f.role in (0,1) else 'back' for i,f in enumerate(team)]
    ours=[actor_factory(f,0,row,equipment(f)) for f,row in zip(team,rows)]
    enemy_names=SCENES[offer['key']][2]
    level=round(sum(f.lv for f in team)/len(team))
    # Risk depends on the player's explicit decision, not a hidden dice roll.
    multiplier=(.85 + .065*offer['difficulty'] +
                {'guard':-.055,'study':0.,'seize':.090}[choice])
    base=[sum(u.attrs[i] for u in ours)/len(ours) for i in range(8)]
    opponents=[]
    for i in range(len(team)):
        role=ENEMY_ROLES[i]
        attrs=[max(25.,min(190.,v*multiplier*(.99+((i%3)-1)*.035))) for v in base]
        # Role-specialized opposition without hidden asymmetric random boosts.
        attrs[(0,1,3,6,5)[i]]+=5
        row='front' if i<2 else 'back'
        opponents.append(Unit(-1-i,1,role,enemy_names[i],row,attrs,
                              max(1,min(20,level+offer['difficulty']-2)),
                              tuple(ROLE_SKILLS[role][:2])))
    rng=elite._rng('elite-combat-v4',seed,gid,season,week,offer['id'],choice,
                   *sorted(f.fid for f in team))
    return Battle(ours+opponents,rng.randrange(2**30,2**31))


def verdict(seed,gid,season,week,order,battle,world,base_ca,base_lv):
    """Battle outcome determines settlement, while the original elite resolve
    still computes cost, fame, injuries, loot rarity and narrative consistently.
    """
    if battle.winner is None:
        raise ValueError('아직 끝나지 않은 정예 전투입니다.')
    offer=order['offer']
    team=order['members']
    choice=order['choice']
    power=sum(f.ca+.12*f.lv-.11*f.fatigue for f in team)/len(team)
    # Obtain the exact base chance without consuming global RNG.
    preview=elite.resolve(seed,gid,season,week,offer,team,power,base_ca,base_lv,
                          choice,roll=.999, bond_bonus=elite.bond_bonus(world,team))
    chance=preview['chance']
    survivors=[battle.units[f.fid] for f in team]
    health=sum(u.hp for u in survivors)/sum(u.max_hp for u in survivors)
    rng=elite._rng('elite-verdict-v4',seed,gid,season,week,offer['id'],choice,
                   *sorted(f.fid for f in team))
    if battle.winner==0:
        # Exceptional victory requires a clean win, not a generic dice result.
        exceptional=health>=.70 and rng.random()<.23
        roll=chance*(.04 if exceptional else .55)
    else:
        roll=chance+(1-chance)*(.26 if health>=.25 else .82)
    result=elite.resolve(seed,gid,season,week,offer,team,power,base_ca,base_lv,
                         choice,roll=roll,bond_bonus=elite.bond_bonus(world,team),
                         injury_multiplier=1-.12*getattr(world,'facilities',{}).get(gid,{}).get('medical',0))
    fallen=[u.id for u in survivors if u.hp<=0]
    result['injured']=sorted(set(result['injured'])|set(fallen))
    result['narrative']=DECISION[choice]['tone']+' '+result['narrative']
    result['combat']=dict(won=battle.winner==0,rounds=len(battle.frames),
                          health=round(health,3),fallen=fallen,
                          enemy=SCENES[offer['key']][1])
    result['manual_play']=True
    return result
