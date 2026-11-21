"""Persistent named heroes and legendary cultivation, independent of world RNG.

Identity lives in the world keyed by global fighter ID: transfers preserve it,
retirement never recycles an individual, and existing Fighter save layouts stay valid.
"""
import hashlib

HEROES = (
    dict(key='namgung_seol',name='남궁설',surname='남궁',given='설',role=1,rarity='named',
         title='검의',skill='검의',description='아군 무인형이 적을 쓰러뜨릴 때마다 무인형 피해 +1% (최대 10중첩)'),
    dict(key='dokgo_jin',name='독고진',surname='독고',given='진',role=5,rarity='named',
         title='절명혈',skill='절명혈',description='자신이 타격한 적은 5초 동안 매초 최대 HP의 1% 출혈, 재타격 시 갱신'),
    dict(key='zhuge_hyeon',name='제갈현',surname='제갈',given='현',role=3,rarity='named',
         title='호법진',skill='호법진',description='아군에게 방패진·호신술을 부여하면 보호 중 공격·방어 +10%, 대상별 재발동 대기 5초'),
    dict(key='jang_cheonho',name='장천호',surname='장',given='천호',role=0,rarity='named',
         title='불괴신공',skill='불괴신공',description='자신의 HP가 50% 이하일 때 받는 피해 30% 감소'),
    dict(key='baek_mujin',name='백무진',surname='백',given='무진',role=3,rarity='named',
         title='봉맥수',skill='봉맥수',description='공격 적중 시 대상 액티브 무공 5초 봉인, 대상별 20초 재발동 대기'),
    dict(key='dokgo_mugeuk',name='독고무극',surname='독고',given='무극',role=1,rarity='legend',
         title='검성',skill='천하일검',description='아군 무인형 3명이 같은 적을 10회 타격하면 5초 동안 그 적의 피해 경감 20% 무시'),
    dict(key='dang_soyeon',name='당소연',surname='당',given='소연',role=5,rarity='legend',
         title='독왕',skill='만독귀종',description='적중한 적에게 중독 부여, 중독 대상 사망 시 남은 지속 피해를 다른 적 최대 2명에게 전이'),
    dict(key='zhuge_tianming',name='제갈천명',surname='제갈',given='천명',role=3,rarity='legend',
         title='천기자',skill='천기삼변',description='아군 보호 효과가 3회 부여되면 보호 중인 아군에 5초간 공격 가속'),
    dict(key='hwangbo_jinak',name='황보진악',surname='황보',given='진악',role=0,rarity='legend',
         title='패왕',skill='부동명왕',description='전열 아군 2명 이상이 HP 35% 이하이면 5초간 아군 후열 피해의 30%를 대신 받음, 전투당 1회'),
    dict(key='baek_yeonhwa',name='백연화',surname='백',given='연화',role=4,rarity='legend',
         title='의선',skill='생사윤회',description='5초간 아군 치유 누적이 최대 체력 합계의 20%면 5초간 초과 치유의 50%를 보호막으로 전환'),
    dict(key='seomun_biyeon',name='서문비연',surname='서문',given='비연',role=2,rarity='legend',
         title='신궁',skill='백발백중',description='아군 사수 3명이 3초 안에 같은 적을 타격하면 표식: 그 적에게 사수 피해 +12%'),
)
BY_KEY={x['key']:x for x in HEROES}
NAMED={x['key']:x for x in HEROES if x['rarity']=='named'}
LEGENDS={x['key']:x for x in HEROES if x['rarity']=='legend'}
ROLE_NAMED={0:'jang_cheonho',1:'namgung_seol',2:'archer_focus',
            3:'baek_mujin',4:'zhuge_hyeon',5:'dokgo_jin'}
ROLE_LEGEND={0:'hwangbo_jinak',1:'dokgo_mugeuk',2:'seomun_biyeon',
             3:'zhuge_tianming',4:'baek_yeonhwa',5:'dang_soyeon'}
EXTRA_SKILLS={
 'archer_focus':dict(skill='집중사격',description='같은 적에게 연속 공격할 때 사수형 피해 최대 +10%'),
}
LEGEND_TITLES={0:'철벽지존',1:'검존',2:'신궁',3:'천기자',4:'의선',5:'독왕'}


def roll(seed, fid, tag):
    digest=hashlib.sha256(f'notable:{seed}:{fid}:{tag}'.encode()).digest()
    return int.from_bytes(digest[:8],'big') / 2**64


def ensure(world):
    if not hasattr(world,'notables'):
        world.notables={}
    if not hasattr(world,'notable_progress'):
        world.notable_progress={}
    return world.notables


def describe(world, fighter):
    item=ensure(world).get(fighter.fid)
    if not item:
        return None
    key=item['key']
    spec=BY_KEY.get(key, EXTRA_SKILLS.get(key,{}))
    return dict(rarity=item['rarity'],key=key,title=item['title'],
                skill=spec.get('skill','전설 절기'),
                description=spec.get('description',''),
                original=item.get('canonical',False),
                progress=dict(world.notable_progress.get(fighter.fid,{})))


def attach(world, fighter, key, rarity=None, canonical=False):
    ensure(world)
    if fighter.fid in world.notables:
        return False
    definition=BY_KEY.get(key,{})
    rarity=rarity or definition.get('rarity','named')
    if canonical:
        name=definition['name']
        if name in world.names.used_people and name != fighter.name:
            return False
        # Preserve the old unique name reservation as historical; never reuse it.
        world.names.used_people.add(name)
        fighter.surname=definition['surname']
        fighter.given_name=definition['given']
    world.notables[fighter.fid]=dict(key=key,rarity=rarity,
                                    title=definition.get('title',LEGEND_TITLES.get(fighter.role,'고수')),
                                    canonical=canonical)
    return True


def initial(world, exclude=()):
    """Guaranteed recognizable initial heroes, no effect on world or naming RNG."""
    ensure(world)
    unavailable=set(exclude)
    population=[f for g in world.guilds.values() for f in g.fighters
                if f.fid not in unavailable]
    chosen=set()
    # Named individuals plus one legendary already alive somewhere in the world.
    special=[*NAMED.values(), LEGENDS['dokgo_mugeuk']]
    for spec in special:
        pool=[f for f in population if f.fid not in chosen and f.role==spec['role']]
        if not pool:
            continue
        fighter=min(pool,key=lambda f:(roll(world.seed,f.fid,spec['key']),f.fid))
        if attach(world,fighter,spec['key'],canonical=True):
            chosen.add(fighter.fid)
    for fighter in population:
        if fighter.fid in chosen:
            continue
        # Exact recruit rarity is rolled from a separate hash, never from economy RNG.
        val=roll(world.seed,fighter.fid,'initial-rarity')
        if val < .002:
            attach(world,fighter,ROLE_LEGEND[fighter.role],rarity='legend')
        elif val < .022:
            attach(world,fighter,ROLE_NAMED[fighter.role],rarity='named')


def new_rookies(world, fighters):
    ensure(world)
    for fighter in fighters:
        p=roll(world.seed,fighter.fid,'rookie-rarity')
        if p < .002:
            # Fixed legendary names are unique; unrelated legends use their own names.
            spec=next((x for x in LEGENDS.values() if x['role']==fighter.role
                       and x['name'] not in world.names.used_people),None)
            if spec is not None:
                attach(world,fighter,spec['key'],canonical=True)
            else:
                attach(world,fighter,ROLE_LEGEND[fighter.role],rarity='legend')
        elif p < .022:
            spec=next((x for x in NAMED.values() if x['role']==fighter.role
                       and x['name'] not in world.names.used_people),None)
            if spec is not None:
                attach(world,fighter,spec['key'],canonical=True)
            else:
                attach(world,fighter,ROLE_NAMED[fighter.role],rarity='named')


def battle_talents(world, units):
    registry=ensure(world)
    return {str(u.id):dict(registry[u.id]) for u in units if u.id in registry}


def record_battle(world, fighter, won, kills, eligible=True):
    """Ordinary player member earns an original-name legendary title by feats.

    Twelve won territorial battles, twenty enemy knockouts and level 10 are
    demanding cumulative milestones, not a paid rarity upgrade.
    """
    ensure(world)
    if not eligible:
        return None
    progress=world.notable_progress.setdefault(fighter.fid,dict(wins=0,kills=0))
    progress['wins']+=int(bool(won))
    progress['kills']+=max(0,int(kills))
    if (fighter.fid not in world.notables and fighter.lv>=10
            and progress['wins']>=12 and progress['kills']>=20):
        key=ROLE_LEGEND[fighter.role]
        attach(world,fighter,key,rarity='legend')
        world.notables[fighter.fid]['title']=LEGEND_TITLES[fighter.role]
        world.notables[fighter.fid]['canonical']=False
        return describe(world,fighter)
    return None


def proxy_bonus(world, team, enemy_team, mode):
    """Conservative CA proxy for AI battles without a full 20-round simulation.

    The player's tactical match uses exact conditional passives; this proxy
    gives named defenders and AI raiders value without a free rarity auto-win.
    """
    registry=ensure(world)
    if not team:
        return 0.0
    roles=[f.role for f in team]
    enemy_roles=[f.role for f in enemy_team]
    value=0.0
    for f in team:
        hero=registry.get(f.fid)
        if not hero:
            continue
        key=hero['key']
        if key=='namgung_seol':
            value+=1.0+min(2,roles.count(1)-1)*1.0
        elif key=='dokgo_jin':
            value+=2.5 if 0 in enemy_roles else 1.5
        elif key=='zhuge_hyeon':
            value+=2.5 if 0 in roles else 1.2
        elif key=='jang_cheonho':
            value+=3.0 if mode=='defense' else 2.0
        elif key=='baek_mujin':
            value+=3.0 if 4 in enemy_roles else 1.5
        elif key=='archer_focus':
            value+=2.0 if roles.count(2)>=2 else 1.0
        elif hero['rarity']=='legend':
            if key=='dokgo_mugeuk':
                value+=3.5 if roles.count(1)>=3 else 1.0
            elif key=='seomun_biyeon':
                value+=3.5 if roles.count(2)>=3 else 1.0
            elif key=='hwangbo_jinak':
                value+=3.5 if mode=='defense' else 1.5
            elif key=='baek_yeonhwa':
                value+=3.5 if 0 in roles else 2.0
            else:
                value+=2.8
    return min(5.0,value)
