"""Deterministic weekly elite missions and persistent rare encounters (기연)."""
from __future__ import annotations
import hashlib
import random
from itertools import combinations
from moonpa_growth import Trait, WEIGHTS

ROLE_NAMES=('수호형','무인형','사수형','주술형','치유형','암살형')
CHOICES={
 'study':dict(label='흔적을 면밀히 살핀다',chance=.075,injury=.72,reward=.90,rare=1.2),
 'guard':dict(label='동료의 안전을 우선한다',chance=.045,injury=.45,reward=.80,rare=.85),
 'seize':dict(label='위험을 무릅쓰고 선점한다',chance=-.09,injury=1.7,reward=1.30,rare=1.6)}
RESULTS={'exceptional':'대성공','success':'성공','partial':'부분 성공',
         'failure':'실패','unfunded':'준비비 부족 취소'}
TEMPLATES=(
 dict(key='jade_cave',title='청옥 동굴의 봉인',category='탐색',difficulty=2,
      story='광부들이 봉인된 동굴에서 청옥빛을 보았다. 고대의 수련 흔적을 조사하라.',
      roles=(3,5,0),rewards=('manual','trait','renown'),
      endings=('봉인을 해제하고 온전한 수행 기록을 확보했다.','봉인 안쪽에서 수련의 단서를 찾아 돌아왔다.',
               '서둘러 철수하며 낡은 문구 일부만 읽었다.','봉인이 무너져 아무것도 살피지 못했다.')),
 dict(key='hermit_mountain',title='은거 고수의 시험',category='인연',difficulty=3,
      story='이름 없는 노고수가 산문 앞에 나타나 제자를 가려내는 시험을 연다.',
      roles=(1,4,3),rewards=('manual','bond','trait'),
      endings=('고수가 무공의 깊이를 인정하고 비밀스러운 가르침을 전했다.','문답과 겨룸을 마치고 시험을 통과했다.',
               '뜻은 통했으나 마지막 문턱을 넘지 못했다.','고수의 의도를 읽지 못한 채 내려왔다.')),
 dict(key='poison_marsh',title='독무 늪지의 영약',category='영물',difficulty=3,
      story='늪지에 피어난 희귀 영초를 찾는 탐사대가 실종되었다. 단서를 쫓아라.',
      roles=(4,2,5),rewards=('trait','renown','bond'),
      endings=('탐사대를 구조하고 영초의 씨앗까지 지켜냈다.','영초를 확보하고 무사히 귀환했다.',
               '일부 물자를 건졌지만 영초는 사라졌다.','독무가 짙어져 늪지 밖으로 물러났다.')),
 dict(key='star_tablet',title='별빛 석비의 암호',category='비급',difficulty=2,
      story='무명의 무인이 남긴 석비의 글씨가 밤마다 달라진다는 소문이 돌았다.',
      roles=(3,2,5),rewards=('manual','trait','bond'),
      endings=('사라진 초식을 해독해 전승의 계보를 밝혀냈다.','비문의 일부를 해독하고 돌아왔다.',
               '석비의 파편만 건져 의미를 추측했다.','석비의 빛이 사라져 소득 없이 돌아왔다.')),
 dict(key='sword_tomb',title='검총의 망령',category='토벌',difficulty=3,
      story='버려진 검총에서 무인들의 실종이 이어진다. 원인을 밝혀야 한다.',
      roles=(0,1,5),rewards=('trait','manual','renown'),
      endings=('원흉을 제압하고 검총에 남은 원념을 풀었다.','실종자들을 구하고 비밀을 확인했다.',
               '도움을 요청하던 사람 일부만 구조했다.','검총 깊은 곳의 함정에 막혀 철수했다.')),
 dict(key='village_oath',title='흑룡촌의 맹약',category='협객',difficulty=2,
      story='두 마을의 오랜 원한이 무력 충돌로 번지려 한다. 중재자를 구한다.',
      roles=(0,4,2),rewards=('bond','renown','trait'),
      endings=('마을 대표들이 화해하고 문파의 이름을 오래 기억하기로 했다.','충돌을 막고 휴전을 이끌었다.',
               '일시적인 휴전만 성사됐다.','끝내 두 마을의 분쟁을 막지 못했다.')))
BY_KEY={item['key']:item for item in TEMPLATES}
assert len(BY_KEY)==len(TEMPLATES)

def _rng(*parts):
    raw=':'.join(map(str,parts)).encode('utf-8')
    return random.Random(int.from_bytes(hashlib.blake2b(raw,digest_size=16).digest(),'big'))

def board(seed,gid,season,week,tier,gross_base,cost_base):
    """Three stable offers per playable week; old IDs expire next week."""
    if not 1<=week<=51:return []
    rng=_rng('elite-board-v1',seed,gid,season,week)
    return [dict(id=f"el{season}-{week}-{gid}-{item['key']}",
                 key=item['key'],title=item['title'],category=item['category'],
                 story=item['story'],difficulty=item['difficulty'],
                 difficulty_label=('보통','위험','매우 위험')[item['difficulty']-1],
                 min_members=3,max_members=5,
                 recommended_roles=[ROLE_NAMES[i] for i in item['roles']],
                 cost=max(1,round(cost_base*(.90+.20*item['difficulty']))),
                 reward=max(1,round(gross_base*(.60+.16*item['difficulty']))),
                 rewards=list(item['rewards']),
                 choices={key:value['label'] for key,value in CHOICES.items()})
            for item in rng.sample(TEMPLATES,3)]

def resolve(seed,gid,season,week,offer,team,power,base_ca,base_lv,
            choice='study',roll=None,fate_roll=None,*,injury_multiplier=1,bond_bonus=0):
    """Calculate without mutation. Roll overrides are for boundary tests only."""
    if choice not in CHOICES:raise ValueError('존재하지 않는 정예 임무 선택입니다.')
    if not offer['min_members']<=len(team)<=offer['max_members']:
        raise ValueError('정예 임무 인원은 3~5명이어야 합니다.')
    item=BY_KEY.get(offer['key'])
    if item is None:raise ValueError('존재하지 않는 정예 임무입니다.')
    path=CHOICES[choice]
    matched=len(set(f.role for f in team)&set(item['roles']))
    chance=max(.24,min(.92,.66+(power-base_ca-2*base_lv)/270+
                        .032*matched+.015*(len(team)-3)-
                        .055*(item['difficulty']-2)+
                        path['chance']+bond_bonus))
    rng=_rng('elite-result-v1',seed,gid,season,week,offer['id'],
             choice,*sorted(f.fid for f in team))
    draw=rng.random() if roll is None else float(roll)
    if not 0<=draw<1:raise ValueError('정예 임무 결과 난수가 올바르지 않습니다.')
    if draw<chance*.085:status='exceptional';factor=1.4;points=1.25
    elif draw<chance:status='success';factor=1;points=.85
    elif draw<chance+(1-chance)*.50:status='partial';factor=.30;points=.13
    else:status='failure';factor=.06;points=0
    gross=max(0,round(offer['reward']*factor*path['reward']))
    cost=offer['cost']+max(0,len(team)-3)*2
    injury_base=(.035+.028*item['difficulty'])*path['injury']*injury_multiplier
    injury_base*=2.3 if status=='failure' else 1.4 if status=='partial' else .65
    injured=[f.fid for f in team if rng.random()<min(.75,injury_base)]
    rarity={'exceptional':.62,'success':.18,'partial':.025,'failure':0}[status]
    rare_draw=rng.random() if fate_roll is None else float(fate_roll)
    if not 0<=rare_draw<1:raise ValueError('기연 판정 난수가 올바르지 않습니다.')
    kiyun=None
    if rare_draw<min(.9,rarity*path['rare']):
        kiyun=dict(kind=item['rewards'][rng.randrange(len(item['rewards']))])
    return dict(id=offer['id'],title=offer['title'],members=[f.fid for f in team],
                choice=choice,choice_label=path['label'],outcome=status,
                outcome_label=RESULTS[status],chance=round(chance,4),
                narrative=item['endings'][('exceptional','success','partial','failure').index(status)],
                gross=gross,cost=cost,net=gross-cost,score=points,injured=injured,kiyun=kiyun)

def apply_kiyun(world,guild,team,result):
    """Rewards are attached to fighter IDs or their development, surviving transfers."""
    find=result.get('kiyun')
    if find is None:return None
    kind=find['kind']
    people=sorted(team,key=lambda f:f.fid)
    if kind=='manual':
        candidates=[f for f in people if world.kiyun_manuals.get(f.fid,0)<3]
        if candidates:
            f=min(candidates,key=lambda x:(world.kiyun_manuals.get(x.fid,0),x.fid))
            world.kiyun_manuals[f.fid]=world.kiyun_manuals.get(f.fid,0)+1
            return dict(kind='manual',label='기연 비급',member=f.fid,
                        description=f'{f.name}이 비급의 요결을 깨달아 무공 수련 포인트 1점을 얻었다.')
    if kind=='trait':
        def primary(f):return max(range(8),key=lambda k:WEIGHTS[f.role][k])
        candidates=[f for f in people if len(f.development.traits)<3 or
                    any(t.attribute==primary(f) for t in f.development.traits)]
        if candidates:
            f=min(candidates,key=lambda x:(len(x.development.traits),x.fid))
            f.development.add_trait(Trait(primary(f),0))
            f.development.refresh(f)
            return dict(kind='trait',label='영약과 깨달음',member=f.fid,
                        description=f'{f.name}의 주력 능력 특성이 강화되었다.')
    if kind=='bond' and len(people)>=2:
        a,b=people[:2]
        pair=(a.fid,b.fid)
        before=world.kiyun_bonds.get(pair,0)
        world.kiyun_bonds[pair]=min(100,before+15)
        return dict(kind='bond',label='생사고락의 인연',members=[a.fid,b.fid],
                    description=f'{a.name}과 {b.name}의 인연이 깊어졌다. (인연 {before} → {world.kiyun_bonds[pair]})')
    guild.renown=min(100,guild.renown+1.5)
    return dict(kind='renown',label='강호의 명성',amount=1.5,
                description='기연이 강호에 알려져 문파 명성이 1.5 상승했다.')

def bond_bonus(world,team):
    pairs=combinations(sorted(f.fid for f in team),2)
    return min(.055,sum(world.kiyun_bonds.get(pair,0) for pair in pairs)*.00016)
