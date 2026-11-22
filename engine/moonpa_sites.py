"""Immutable site names and income tiers keyed by the campaign's zone IDs."""

_HIGH = (
    '낙양 본성', '낙양 황궁외성', '낙양 남문 장터', '낙양 동시 상단가', '낙양 북방 무기고', '낙양 서루 전각',
    '장안 본성', '장안 주작대로', '장안 서시 호상가', '장안 동문 관아', '장안 북원 전당', '장안 남교 장터',
    '개봉 본성', '개봉 어가 대로', '개봉 대시장', '개봉 수로 상항', '개봉 동화문가', '개봉 서영루',
    '금릉 본성', '금릉 진회루 상가', '금릉 장강 선착장', '항주 본성', '항주 서호 상단가', '항주 비단전거리',
    '소주 본성', '소주 운하 상구', '소주 칠리산가', '소주 병장방', '태원 본성', '태원 철기 상단가',
    '태원 북관 요새', '형주 본성', '형주 한수 상항', '형주 남문 군자창', '하동 본성', '하동 황하 도진',
)
_MID = (
    '양주 외곽', '양주 상단거리', '양주 염전가', '양주 남부 수로', '양주 북문 주점가', '성도 외곽',
    '성도 상단거리', '성도 금관역참', '성도 서문 약재가', '성도 남교 교두보', '성도 북산 목재장', '성도 동쪽 관도',
    '여남 주성', '진류 상단가', '허창 군영외곽', '복양 하안가', '완구 동문 시장', '여강 수운소', '강릉 남부 관문',
    '무창 상선부두', '파양호 상단길', '연경 남관', '진정 북방 교역소', '기주 동부 역참', '제남 상단거리', '청주 염상가',
    '서주 남문 관도', '회안 운하 관문', '온주 외항 상가', '명주 동쪽 선창', '함양 관도역', '농서 외곽 주둔지',
    '천수 상단길', '한중 북문 관문', '면죽 동부 시장', '청성산 입구 장터', '낭중 수로 나루', '바주 산길 관문',
    '동정호 북안 상가', '악양 남부 주점가', '상사 동문 교역장', '계림 상단거리', '남창 외곽 시장', '건녕 차마고도 입구',
)
_SMALL = (
    '백로나루', '흑석관', '청강나루', '황토초소', '적벽나루', '옥문소관', '와룡진', '금사나루',
    '철교초소', '노구진', '묵호나루', '연화관', '청풍나루', '한산초소', '백마진', '용문소관',
    '흑풍채', '청솔골', '붉은바위협곡', '안개골 초소', '매화령', '천둥계곡', '백운산채', '늑대바위고개',
    '단풍골', '한빙협곡', '황룡령', '까마귀산채', '버들여관촌', '옹기마을', '낡은주막거리', '외딴대장간',
    '소금밭마을', '찻집고개마을', '옛사찰터', '갈대밭주막', '석수골마을', '목탄마을', '달빛여관터', '쇠목나루마을',
)

# Base IDs 0–47 keep their leagues and ownership in existing saves.
_BASE_PER_LEAGUE = 12
_COUNTS = {1:(18,16,8), 2:(11,12,11), 3:(5,10,11), 4:(2,6,10)}


def _sites():
    # Three representative city seats stay in 1부. Satellites circulate through
    # the other leagues even when they share a city name.
    seats = [_HIGH[i] for i in (0,6,12)]
    high = iter(seats + [name for name in _HIGH if name not in seats][::2]
                + [name for name in _HIGH if name not in seats][1::2])
    mid, small = iter(reversed(_MID)), iter(reversed(_SMALL))
    by_tier = {}
    for tier,(n_high,n_mid,n_small) in _COUNTS.items():
        pools = ((small,n_small,'소규모',(.72,.78,.84)),
                 (mid,n_mid,'중간급',(1.00,1.08,1.16)),
                 (high,n_high,'고수익',(1.40,1.52,1.64)))
        by_tier[tier] = [(tier,next(names),category,values[i % len(values)])
                         for names,count,category,values in pools for i in range(count)]
    return tuple(row for start,end in ((0,_BASE_PER_LEAGUE),(_BASE_PER_LEAGUE,None))
                 for entries in by_tier.values() for row in entries[start:end])


SITES = _sites()


def site_details(zid):
    _,name,category,_ = SITES[zid]
    return {'name':name,'site_grade':category}
