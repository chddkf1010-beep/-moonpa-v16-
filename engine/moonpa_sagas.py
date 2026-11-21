"""Multi-chapter rare encounters and fighter-bound wuxia personal narratives.

Fighter development owns progression, so transfers and changing guilds do not
erase the storyline. This module consumes no world RNG.
"""
from __future__ import annotations
import hashlib
import random

LINES={
 'starlight':dict(name='천문비록',secret_title='천외비맥의 계승자',
     first='비문 안쪽에서 별자리 모양의 문양이 나타났다. 조각을 풀면 새로운 무학의 길이 열린다.',
     chapters=(
      dict(key='star_tablet',title='천문비록 2장 · 무너진 관측대',
           story='첫 단서가 가리킨 관측대에서 야밤의 별지도를 복원해야 한다.'),
      dict(key='jade_cave',title='천문비록 3장 · 천외비맥',
           story='지도의 끝에 감춰진 옛 수련장을 찾아 금단의 초식을 해독하라.')),
     endings=('별의 흐름이 맞아떨어졌다. 다음 단서가 북쪽 산줄기를 가리킨다.',
              '천외비맥의 마지막 구결이 열렸다.')),
 'wanderer':dict(name='사문유서',secret_title='무명사문의 후계자',
     first='낡은 검흔에 오래전 사라진 문파의 인장이 숨어 있었다.',
     chapters=(
      dict(key='hermit_mountain',title='사문유서 2장 · 마지막 증인',
           story='과거의 문파를 기억하는 은거 고수를 찾아 진실을 확인한다.'),
      dict(key='sword_tomb',title='사문유서 3장 · 검총의 계승',
           story='검총 깊은 곳에서 명예와 복수 중 무엇을 이어받을지 선택해야 한다.')),
     endings=('고수가 잊힌 사문과 그 제자들에 관한 비밀을 전해 주었다.',
              '사라진 사문의 무학이 새로운 손에 이어졌다.')),
 'black_dragon':dict(name='흑룡맹약',secret_title='흑룡맹약의 수호자',
     first='마을의 기록에 수십 년 전 맺어진 검은 용의 맹약이 남아 있었다.',
     chapters=(
      dict(key='village_oath',title='흑룡맹약 2장 · 잊힌 증서',
           story='두 마을이 지켜 온 오래된 맹약의 진위를 확인한다.'),
      dict(key='poison_marsh',title='흑룡맹약 3장 · 검은 물의 맹세',
           story='맹약의 실마리가 이어진 독무 늪에서 마지막 증인을 구하라.')),
     endings=('잊힌 약속의 진실이 드러나 새로운 길이 열렸다.',
              '오랜 맹약의 숨은 무학을 계승했다.')),
}
LINE_FOR_OFFER={
 'jade_cave':'starlight','star_tablet':'starlight',
 'hermit_mountain':'wanderer','sword_tomb':'wanderer',
 'poison_marsh':'black_dragon','village_oath':'black_dragon',
}
ORIGINS=(
 ('변방에서 떠돌던 고아','도적에게 잃어버린 고향의 흔적을 찾고 있다.'),
 ('낡은 표국의 후예','사라진 표국의 명예를 되찾으려 한다.'),
 ('산속 은자의 제자','사부가 남긴 한마디를 평생 가슴에 품고 있다.'),
 ('몰락한 세가의 자손','가문보다 자신의 무공으로 이름을 남기려 한다.'),
 ('고을 의원의 후계자','전란 속에서 지키지 못했던 사람을 잊지 못한다.'),
 ('장터의 이름 없는 낭인','은혜를 입은 이의 이름을 반드시 기억한다.'),
)
ROLE_GOALS=('무너진 사람들을 지키는 것','스스로 검의 끝을 찾는 것','멀리서 동료의 길을 여는 것',
            '세상에 숨은 이치를 밝히는 것','다친 이를 다시 일으키는 것','그림자에서 진실을 발견하는 것')
MILESTONES=(
 (1,'첫 발자취','첫 정예 임무를 마치고 강호에 자기만의 이름을 새겼다.'),
 (3,'흔들리지 않는 마음','거듭되는 시련 속에서 자신의 강호관을 세우기 시작했다.'),
 (6,'한 사람의 강호','긴 여정 끝에 사람들이 그를 한 사람의 협객으로 기억하기 시작했다.'),
)
STATUS={'active':'진행 중','completed':'전승 완료','expired':'단서 소멸'}


def _rng(*parts):
    raw=':'.join(map(str,parts)).encode('utf-8')
    return random.Random(int.from_bytes(hashlib.blake2b(raw,digest_size=16).digest(),'big'))


def clock(season,week):
    return season*52+week


def profile(f,seed):
    """Stable identity with no world/global RNG consumption."""
    index=_rng('personal-origin-v2',seed,f.fid).randrange(len(ORIGINS))
    title,history=ORIGINS[index]
    return dict(origin=title,history=history,goal=ROLE_GOALS[f.role])


def is_current(f,season,week):
    saga=f.development.saga
    return bool(saga and saga['status']=='active'
                and clock(season,week)<=saga['deadline']
                and not f.development.secret_arts)


def current_leader(guild,season,week):
    candidates=[f for f in guild.fighters if is_current(f,season,week)]
    return min(candidates,key=lambda f:(f.development.saga['started'],f.fid)) if candidates else None


def decorate_board(guild,offers,season,week):
    """Pin one continuing story to the three-offer board, if present."""
    if not offers:return []
    leader=current_leader(guild,season,week)
    if leader is None:return offers
    quest=leader.development.saga
    next_chapter=quest['next_chapter']
    chapter=LINES[quest['line']]['chapters'][next_chapter-1]
    # Preserve the elite resolver's existing difficulty, role and payout rules.
    source=next((card for card in offers if card['key']==chapter['key']),None)
    if source is None:
        from moonpa_elite import BY_KEY, ROLE_NAMES
        item=BY_KEY[chapter['key']]
        base=offers[0]
        source=dict(base,key=chapter['key'],category='연속 기연',
             difficulty=item['difficulty'],
             difficulty_label=('보통','위험','매우 위험')[item['difficulty']-1],
             recommended_roles=[ROLE_NAMES[i] for i in item['roles']],
             cost=max(1,round(base['cost']*(1.15+.10*(item['difficulty']-2)))))
    quest_offer=dict(source,
         id=f"saga{season}-{week}-{guild.gid}-{leader.fid}-{quest['line']}-{next_chapter}",
         title=chapter['title'],story=chapter['story'],category='연속 기연',
         saga=True,saga_line=quest['line'],saga_chapter=next_chapter+1,
         saga_leader=leader.fid,saga_deadline=quest['deadline'],
         reward=max(1,round(source['reward']*1.15)))
    others=[item for item in offers if item['key']!=quest_offer['key']][:2]
    if len(others)<2:
        others=offers[:2]
    return [quest_offer,*others]


def advance(f,seed,season,week,offer,result,choice):
    """Advance only after the elite mission was financed. Return story events."""
    dev=f.development
    events=[]
    now=clock(season,week)
    saga=dev.saga
    if saga and saga['status']=='active' and now>saga['deadline']:
        saga['status']='expired'
        events.append(dict(kind='expired',title='기연의 단서 소멸',
                           text=f'{f.name}이 좇던 {LINES[saga["line"]]["name"]}의 흔적이 끊겼다.'))
    if offer.get('saga'):
        if not saga or saga['status']!='active' or saga['next_chapter']!=offer['saga_chapter']-1:
            raise AssertionError('검증되지 않은 연속 기연이 정산에 도착했습니다.')
        saga['attempts']+=1
        saga['ethos']+=(-1 if choice=='seize' else 1 if choice=='guard' else 0)
        if result['outcome'] in ('exceptional','success'):
            chapter=saga['next_chapter']
            text=LINES[saga['line']]['endings'][chapter-1]
            if chapter==2:
                from combat import SECRET_SKILLS
                secret=SECRET_SKILLS[f.role]
                if secret not in dev.secret_arts:
                    dev.secret_arts.append(secret)
                saga['status']='completed'
                saga['completed']=now
                dev.personal_title=LINES[saga['line']]['secret_title']
                events.append(dict(kind='secret',title='숨겨진 무공 전승',
                                   text=f'{f.name}이 {LINES[saga["line"]]["name"]}을(를) 마치고 '
                                        f'비전 무공을 전승받았다. {text}',
                                   skill=secret,recipient=f.fid))
            else:
                saga['next_chapter']=2
                saga['deadline']=now+12
                events.append(dict(kind='progress',title='연속 기연 2장 완료',
                                   text=f'{f.name}: {text}'))
        elif result['outcome']=='partial':
            events.append(dict(kind='delay',title='기연 조사 지연',
                               text=f'{f.name}이 단서 일부만 찾았다. 같은 장을 다시 시도할 수 있다.'))
        else:
            saga['setbacks']+=1
            if saga['setbacks']>=3:
                saga['status']='expired'
                events.append(dict(kind='expired',title='기연 추적 실패',
                                   text='세 차례 실패로 이번 전승의 단서를 잃었다.'))
            else:
                events.append(dict(kind='delay',title='기연 추적 난항',
                                   text='추적에 실패했지만 재도전할 기회는 남아 있다.'))
    elif result['outcome'] in ('exceptional','success') and not dev.secret_arts:
        leader_busy=dev.saga and dev.saga['status']=='active'
        if not leader_busy:
            threshold=.90 if result['outcome']=='exceptional' else .40
            rng=_rng('saga-discovery-v2',seed,season,week,f.fid,offer['id'],choice)
            if rng.random()<threshold:
                line=LINE_FOR_OFFER.get(offer['key'],'starlight')
                dev.saga=dict(line=line,status='active',next_chapter=1,
                              started=now,deadline=now+12,attempts=0,
                              setbacks=0,ethos=1 if choice=='guard' else -1 if choice=='seize' else 0)
                events.append(dict(kind='clue',title=LINES[line]['name']+' · 첫 장',
                                   text=f'{f.name}: {LINES[line]["first"]}'))
    if result['outcome'] in ('exceptional','success'):
        dev.elite_wins+=1
        for milestone,title,text in MILESTONES:
            if dev.elite_wins==milestone:
                if not dev.secret_arts:
                    dev.personal_title=title
                events.append(dict(kind='personal',title=f'{f.name} · {title}',
                                   text=f'{f.name}은(는) {profile(f,seed)["origin"]} 출신이다. {text}'))
    if result['outcome']!='unfunded':
        decision={'study':'진실을 끝까지 추적했다','guard':'동료를 지키는 길을 택했다',
                  'seize':'위험을 감수하고 앞장섰다'}[choice]
        dev.story_events.append(dict(season=season,week=week,
                     title=offer['title'],outcome=result['outcome_label'],
                     story=f'{decision}. {result["narrative"]}'))
        dev.story_events=dev.story_events[-12:]
    return events


def view(f,seed,season,week):
    p=profile(f,seed)
    saga=f.development.saga
    p.update(title=f.development.personal_title or '무명의 무인',
             elite_wins=f.development.elite_wins,
             events=list(f.development.story_events),
             secrets=list(f.development.secret_arts))
    if saga:
        status='expired' if saga['status']=='active' and clock(season,week)>saga['deadline'] else saga['status']
        p['saga']=dict(line=LINES[saga['line']]['name'],status=status,
                       status_label=STATUS[status],chapter=1+saga['next_chapter'] if status=='active' else 3 if status=='completed' else 0,
                       deadline=saga['deadline'],attempts=saga['attempts'],
                       ending=('보호와 협의' if saga['ethos']>0 else '선점과 결단' if saga['ethos']<0 else '탐색과 균형'))
    else:p['saga']=None
    return p
