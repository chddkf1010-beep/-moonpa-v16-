"""Deterministic short mission board and four-tier narrative resolution.

Mission offers and resolution use their own RNG so opening the board never
changes battle, market or world randomness. The same engine is shared by
human-controlled and AI guilds. Numbers here are provisional economy tuning.
"""
from __future__ import annotations

import hashlib
import random

ROLE_NAMES = ('수호형', '무인형', '사수형', '주술형', '치유형', '암살형')
APPROACHES = {
    'cautious': dict(label='신중하게', chance=.085, reward=.84, injury=.50),
    'balanced': dict(label='정석대로', chance=0.0, reward=1.0, injury=1.0),
    'bold': dict(label='과감하게', chance=-.105, reward=1.25, injury=1.55),
}
DIFFICULTY = {
    1: dict(label='쉬움', chance=.07, injury=.004),
    2: dict(label='보통', chance=0.0, injury=.012),
    3: dict(label='어려움', chance=-.11, injury=.032),
}

# Six categories, three authored stories per category.
# min<=3<=max guarantees that legacy AI three-person teams remain valid.
TEMPLATES = (
    dict(key='caravan_herbs', category='호송', title='산길 약재 상단',
         story='남쪽 약방으로 가는 약재 수레가 도적의 표적이 되었다.',
         roles=(0, 2, 4), size=(3, 5), difficulty=1, reward=.98, cost=.92,
         texts=('상단주가 약재값 외에 특별 사례금까지 지급했다.',
                '약재 수레가 무사히 고갯길을 통과했다.',
                '수레 일부를 잃었지만 귀중한 약재는 건졌다.',
                '수레가 흩어지고 남은 짐만 간신히 회수했다.')),
    dict(key='caravan_night', category='호송', title='자정의 비밀 호송',
         story='얼굴을 가린 의뢰인이 정체불명의 문서를 밤새 운반해 달라 한다.',
         roles=(0, 3, 5), size=(2, 4), difficulty=3, reward=1.32, cost=1.14,
         texts=('매복한 자들을 역으로 포위해 추가 보수를 받았다.',
                '추적을 피해 봉인된 문서를 전달했다.',
                '시간에 늦었지만 의뢰인의 물건은 지켰다.',
                '추격을 따돌렸으나 문서의 일부가 훼손되었다.')),
    dict(key='caravan_bridge', category='호송', title='무너진 나루의 화물',
         story='거센 물살로 나루가 폐쇄돼 짐꾼들이 발이 묶였다.',
         roles=(0, 1, 4), size=(3, 5), difficulty=2, reward=1.04, cost=.96,
         texts=('무너진 나루까지 복구해 고을의 감사패를 받았다.',
                '임시 도하로 화물을 모두 옮겼다.',
                '화물은 대부분 건넜지만 일부가 물에 젖었다.',
                '물살 때문에 화물을 회수하는 데 그쳤다.')),
    dict(key='bandit_pass', category='토벌', title='협곡의 산적 소굴',
         story='통행세를 빼앗는 산적들이 좁은 협곡을 차지했다.',
         roles=(0, 1, 2), size=(3, 5), difficulty=2, reward=1.14, cost=1.08,
         texts=('두목을 사로잡아 현상금과 압수품을 확보했다.',
                '산적을 흩어놓고 통행로를 개방했다.',
                '두목은 놓쳤지만 산적들의 진지를 무너뜨렸다.',
                '산적의 역습으로 후퇴하며 물품만 확보했다.')),
    dict(key='bandit_smugglers', category='토벌', title='밀수단의 밤거래',
         story='경계가 삼엄한 폐창고에 수상한 물자가 쌓여 있다.',
         roles=(1, 3, 5), size=(2, 4), difficulty=3, reward=1.38, cost=1.18,
         texts=('밀수 장부까지 찾아 관가가 특별 상금을 지급했다.',
                '물자를 압수하고 주요 밀수책을 체포했다.',
                '밀수책은 놓쳤으나 일부 물품을 회수했다.',
                '창고가 비어 있었고 추격전만 벌어졌다.')),
    dict(key='bandit_wolves', category='토벌', title='늑대 떼의 습격',
         story='산기슭 마을이 굶주린 맹수 떼의 공격을 받고 있다.',
         roles=(0, 2, 4), size=(3, 5), difficulty=1, reward=.95, cost=.90,
         texts=('새끼 늑대의 은신처를 찾아 피해를 근본적으로 막았다.',
                '마을 주변을 순찰해 늑대 떼를 몰아냈다.',
                '마을을 지켰지만 늑대 떼 일부는 달아났다.',
                '맹수를 쫓지 못하고 주민 피난만 도왔다.')),
    dict(key='scout_manuscript', category='탐색', title='낡은 비급의 흔적',
         story='폐사찰 지하에 오래된 무공 필사본이 있다는 소문이다.',
         roles=(2, 3, 5), size=(2, 4), difficulty=3, reward=1.22, cost=1.08,
         texts=('온전한 필사본과 유물까지 찾아 높은 값을 받았다.',
                '필사본 일부를 찾아 의뢰에 응했다.',
                '판독 가능한 몇 장만 회수했다.',
                '헛된 소문이었고 여비만 들었다.')),
    dict(key='scout_ginseng', category='탐색', title='절벽 위의 약초',
         story='절벽에만 자라는 희귀 약초의 채집 시기가 다가왔다.',
         roles=(2, 4, 5), size=(2, 4), difficulty=2, reward=1.12, cost=.92,
         texts=('뿌리가 온전한 상급 약초를 한 무더기 발견했다.',
                '의뢰한 약초를 정해진 양만큼 채집했다.',
                '일부 약초가 손상됐지만 납품할 수 있었다.',
                '위험한 지형 탓에 손에 넣은 약초가 거의 없다.')),
    dict(key='scout_cave', category='탐색', title='동굴 지도 조사',
         story='석공들이 새로 발견한 동굴에서 기이한 표식을 보았다.',
         roles=(0, 3, 5), size=(3, 5), difficulty=1, reward=.94, cost=.88,
         texts=('동굴을 완전히 측량하고 숨은 통로까지 확인했다.',
                '입구에서 중심부까지 지도를 작성했다.',
                '동굴 일부만 기록하고 돌아왔다.',
                '낙석으로 조사를 중단하고 입구를 봉쇄했다.')),
    dict(key='intel_letters', category='정보', title='사라진 밀서',
         story='무역을 둘러싼 밀서가 도중에 사라져 여러 세력이 움직인다.',
         roles=(3, 5, 2), size=(2, 3), difficulty=2, reward=1.10, cost=.98,
         texts=('밀서와 위조 문서까지 찾아 배후를 밝혀냈다.',
                '밀서를 찾아 의뢰인에게 넘겼다.',
                '밀서의 내용을 확인했지만 원본은 찾지 못했다.',
                '거짓 정보에 휘말려 실마리만 남았다.')),
    dict(key='intel_spies', category='정보', title='객잔의 수상한 손님',
         story='객잔 주인이 오래 머무는 낯선 손님들을 조사해 달라 한다.',
         roles=(3, 4, 5), size=(2, 4), difficulty=1, reward=.91, cost=.88,
         texts=('첩자 조직의 연락망까지 밝혀냈다.',
                '의뢰인의 의심을 풀고 관련 정보를 전달했다.',
                '몇 가지 단서는 얻었지만 신원은 불확실하다.',
                '의심받던 손님이 사라져 조사가 공전했다.')),
    dict(key='intel_rival', category='정보', title='변경의 무림 소문',
         story='이웃 문파들의 움직임과 소문을 수집해 달라는 요청이다.',
         roles=(2, 3, 5), size=(2, 4), difficulty=2, reward=1.01, cost=.91,
         texts=('동향을 정리한 상세 보고서로 추가 보수를 받았다.',
                '신뢰할 만한 정보를 취합해 전달했다.',
                '소문 가운데 일부만 확인할 수 있었다.',
                '잘못된 소문에 흔들려 소득 없이 돌아왔다.')),
    dict(key='rescue_flood', category='구호', title='범람한 강가의 마을',
         story='폭우로 다리가 끊기고 주민들이 고립되었다.',
         roles=(0, 4, 2), size=(3, 5), difficulty=2, reward=1.0, cost=.95,
         texts=('주민 모두와 가축까지 구해 마을의 후원을 얻었다.',
                '고립된 주민들을 안전하게 피신시켰다.',
                '대부분 구조했으나 장비 일부를 잃었다.',
                '접근하지 못해 구호품 전달만 겨우 마쳤다.')),
    dict(key='rescue_plague', category='구호', title='산촌의 괴질',
         story='산촌에 원인 모를 열병이 퍼져 약재와 간호가 필요하다.',
         roles=(4, 3, 0), size=(2, 4), difficulty=3, reward=1.27, cost=1.20,
         texts=('병의 원인을 찾아 마을 전체의 피해를 막았다.',
                '약재를 전달하고 위급한 환자를 안정시켰다.',
                '일부 환자에게만 약재를 공급할 수 있었다.',
                '약재가 부족해 지원 요청만 남기고 돌아왔다.')),
    dict(key='rescue_child', category='구호', title='실종된 아이를 찾아서',
         story='산속에서 사라진 아이를 찾으려 가족들이 도움을 청한다.',
         roles=(2, 4, 5), size=(2, 4), difficulty=1, reward=.92, cost=.88,
         texts=('아이와 함께 길 잃은 행상까지 구출했다.',
                '아이를 찾아 무사히 집으로 데려왔다.',
                '행적을 찾아 구조대에 위치를 전했다.',
                '발자취를 놓쳐 수색을 중단했다.')),
    dict(key='trade_silk', category='교역', title='비단 품질 감정',
         story='서역에서 들어온 비단의 진위를 감별할 사람이 필요하다.',
         roles=(3, 4, 1), size=(2, 3), difficulty=1, reward=.96, cost=.84,
         texts=('가짜 물품을 전부 적발해 별도 수당을 받았다.',
                '비단을 감정하고 정상 거래를 성사시켰다.',
                '확실한 물품만 구분해 소액의 보수를 받았다.',
                '거래가 결렬돼 중개료 일부만 회수했다.')),
    dict(key='trade_iron', category='교역', title='철광 운송 협상',
         story='산채와 관가가 철광 채굴권을 두고 대립한다.',
         roles=(0, 1, 3), size=(3, 5), difficulty=3, reward=1.25, cost=1.18,
         texts=('양측의 협정을 이끌어 장기 중개 수당까지 받았다.',
                '충돌을 막고 운송 계약을 성사시켰다.',
                '운송 일부만 합의해 작은 수당을 받았다.',
                '협상이 깨져 운송은 지연되었다.')),
    dict(key='trade_mill', category='교역', title='주막의 물자 조달',
         story='장마로 물자 공급이 끊긴 주막에서 급히 의뢰가 들어왔다.',
         roles=(0, 2, 4), size=(2, 4), difficulty=2, reward=1.03, cost=.93,
         texts=('새로운 공급처까지 확보해 추가 사례금을 받았다.',
                '필요한 물자를 제때 전달했다.',
                '급한 물건만 조달해 일부 보상을 받았다.',
                '물자가 부족해 일부 운반비만 돌려받았다.')),
)
assert len(TEMPLATES) == 18
CATEGORIES = ('호송','토벌','탐색','정보','구호','교역')


def _rng(*parts):
    serialized = ':'.join(str(part) for part in parts).encode('utf-8')
    return random.Random(int.from_bytes(hashlib.blake2b(serialized, digest_size=16).digest(), 'big'))


def board(seed: int, guild_id: int, season: int, week: int, tier: int,
          gross_base: int, cost_base: int) -> list[dict]:
    """Exactly six offers, one from every category, stable for the current week."""
    rng = _rng('mission-board-v1',seed,guild_id,season,week)
    cards=[]
    for category in CATEGORIES:
        candidates=[x for x in TEMPLATES if x['category']==category]
        item=candidates[rng.randrange(len(candidates))]
        cards.append(dict(
            id=f"ms{season}-{week}-{guild_id}-{item['key']}",
            key=item['key'], title=item['title'], story=item['story'],
            category=item['category'], min_members=item['size'][0],
            max_members=item['size'][1], difficulty=item['difficulty'],
            difficulty_label=DIFFICULTY[item['difficulty']]['label'],
            suggested_roles=[ROLE_NAMES[i] for i in item['roles']],
            reward=round(gross_base*item['reward']),
            cost=max(1,round(cost_base*item['cost'])),
            duration=1,
        ))
    rng.shuffle(cards)
    return cards


def choose_auto_offer(offers: list[dict], team: list, used: set[str]) -> dict:
    """AI and legacy three-person teams use the same candidate pool."""
    possible=[x for x in offers if x['id'] not in used and
              x['min_members'] <= len(team) <= x['max_members']]
    if not possible:
        raise ValueError('해당 인원으로 수행할 수 있는 임무가 없습니다.')
    def merit(x):
        matching=len({ROLE_NAMES[f.role] for f in team} & set(x['suggested_roles']))
        return (x['reward']-x['cost']) * (.82 if x['difficulty']==3 else 1.0) + matching*2
    return max(possible, key=merit)


def resolve(seed: int, guild_id: int, season: int, week: int,
            offer: dict, team: list, power: float, base_ca: float,
            base_level: float, approach='balanced', roll=None, *, support=0, injury_multiplier=1) -> dict:
    """Pure deterministic resolution; optional roll allows boundary tests."""
    if approach not in APPROACHES:
        raise ValueError('지원하지 않는 임무 접근 방식입니다.')
    if not offer['min_members'] <= len(team) <= offer['max_members']:
        raise ValueError('임무 참가 인원이 맞지 않습니다.')
    key=offer['key']
    item=next((x for x in TEMPLATES if x['key']==key), None)
    if item is None:
        raise ValueError('알 수 없는 임무입니다.')
    decision=APPROACHES[approach]
    matching=len({f.role for f in team} & set(item['roles']))
    average_fatigue=sum(f.fatigue for f in team)/len(team)
    chance = .78 + (power-base_ca-2*base_level)/260
    chance += support + .036 * matching + .022 * (len(team)-3)
    chance += DIFFICULTY[item['difficulty']]['chance'] + decision['chance']
    chance -= average_fatigue * .00045
    chance=max(.28,min(.95,chance))
    rng=_rng('mission-result-v1',seed,guild_id,season,week,offer['id'],
             *(f.fid for f in sorted(team,key=lambda f:f.fid)),approach)
    draw=rng.random() if roll is None else float(roll)
    if not 0 <= draw < 1:
        raise ValueError('임무 난수는 0 이상 1 미만이어야 합니다.')
    if draw < chance*.105:
        outcome='exceptional'; factor=1.55; points=1.1
    elif draw < chance:
        outcome='success'; factor=1.0; points=.65
    elif draw < chance+(1-chance)*.69:
        outcome='partial'; factor=.39; points=.15
    else:
        outcome='failure'; factor=.12; points=0
    gross=max(1,round(offer['reward'] * decision['reward']*factor))
    cost=max(1,round(offer['cost']*(1+.09*(len(team)-3))))
    messages=dict(zip(('exceptional','success','partial','failure'),item['texts']))
    outcome_label=dict(exceptional='대성공',success='성공',partial='부분 성공',failure='실패')
    injury_risk=DIFFICULTY[item['difficulty']]['injury']*decision['injury']*(
        1.7 if outcome=='failure' else 1.2 if outcome=='partial' else 0.35)
    injured=[]
    for f in team:
        if rng.random()<injury_risk*injury_multiplier:
            injured.append(f.fid)
    return dict(id=offer['id'],title=offer['title'],approach=approach,
                approach_label=decision['label'],outcome=outcome,
                outcome_label=outcome_label[outcome],narrative=messages[outcome],
                chance=round(chance,4),gross=gross,cost=cost,net=gross-cost,
                score=points, injured=injured)
