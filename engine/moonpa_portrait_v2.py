"""Forty-eight age-appropriate wuxia portraits, eight for each of six roles.

Visual variety is independent from statistics, gender/ethnicity guessing,
rarity, hero identity and role power. Preserve the legacy v1 and founding art.
Each of three 4×4 sheets contains two roles in eight consecutive cells:
0 guardians/warlords; 1 archers/shamans; 2 healers/assassins.
"""
import hashlib
import re

# index within role, inclusive age brackets. Illustration depicts a *look*;
# this is a matching constraint, not a statement about a fighter's real age.
# (age_min, age_max, body, impression, details)
GROUPS=(
 (
  (28,42,'거구','무뚝뚝한',('굵은 눈썹','짙은 수염')),
  (18,35,'통통한','무심한',('둥근 볼','단정한 머리')),
  (18,34,'다부진','자신감 있는',('굵은 눈썹','짧은 흉터')),
  (30,45,'거구','호방한',('거친 수염','주름진 미소')),
  (24,43,'통통한','푸근한',('볼살','웃는 눈')),
  (26,42,'마른 근육질','매서운',('각진 광대','진한 눈매')),
  (30,46,'다부진','침착한',('짧은 수염','단단한 턱')),
  (48,75,'장대한','노련한',('백발','긴 수염')),
 ),
 (
  (16,25,'날렵한','날카로운',('곧은 눈썹','짙은 눈빛')),
  (18,30,'보통','냉정한',('갸름한 얼굴','긴 머리')),
  (19,35,'통통한','고집스러운',('둥근 볼','굳은 입매')),
  (25,41,'근육질','굳센',('짧은 머리','투박한 얼굴')),
  (18,29,'마른','진지한',('긴 눈매','집중한 표정')),
  (25,42,'다부진','거친',('얼굴 흉터','짙은 수염')),
  (28,44,'보통','냉철한',('짧은 수염','좁은 눈매')),
  (33,49,'거구','강인한',('굵은 수염','각진 턱')),
 ),
 (
  (16,26,'보통','예민한',('주근깨','집중한 눈')),
  (18,33,'보통','담담한',('긴 눈매','고운 얼굴선')),
  (18,34,'마른','날카로운',('매서운 눈썹','뾰족한 턱')),
  (20,36,'통통한','무심한',('둥근 볼','넓은 얼굴')),
  (20,37,'다부진','자유로운',('그을린 피부','헝클어진 머리')),
  (20,38,'날렵한','냉정한',('차가운 눈빛','짧은 흉터')),
  (29,46,'근육질','노련한',('짧은 수염','굳은 표정')),
  (35,51,'마른','침착한',('눈가 주름','희끗한 수염')),
 ),
 (
  (17,27,'마른','수상한',('날카로운 눈','헝클어진 머리')),
  (18,35,'보통','고고한',('단정한 머리','긴 눈매')),
  (20,34,'마른','음울한',('그늘진 눈','수척한 얼굴')),
  (20,38,'통통한','능글맞은',('둥근 볼','느긋한 미소')),
  (28,46,'마른','엄격한',('가는 수염','날카로운 눈')),
  (22,40,'마른','피곤한',('다크서클','거친 얼굴')),
  (27,43,'통통한','의뭉스러운',('처진 눈','넓은 코')),
  (39,60,'마른','노련한',('주름','희끗한 수염')),
 ),
 (
  (17,32,'보통','차분한',('단정한 얼굴','온화한 눈')),
  (19,39,'통통한','푸근한',('볼살','부드러운 미소')),
  (20,35,'마른','냉철한',('침착한 눈빛','갸름한 턱')),
  (28,47,'보통','엄격한',('짧은 수염','단호한 표정')),
  (24,44,'통통한','호탕한',('둥근 얼굴','밝은 미소')),
  (29,47,'마른','피곤한',('눈가 주름','수척한 뺨')),
  (29,47,'보통','인자한',('부드러운 표정','짧은 수염')),
  (49,77,'마른','온화한',('백발','깊은 주름')),
 ),
 (
  (16,27,'마른','무심한',('차가운 눈빛','긴 앞머리')),
  (18,34,'날렵한','냉정한',('긴 눈매','갸름한 턱')),
  (19,34,'통통한','능글맞은',('볼살','단단한 입매')),
  (20,38,'마른','매서운',('날카로운 눈','움푹 팬 볼')),
  (21,40,'다부진','거친',('작은 흉터','짙은 눈썹')),
  (26,43,'보통','평범한',('무표정','검은 눈')),
  (27,46,'마른','음울한',('그늘진 눈매','뾰족한 턱')),
  (33,49,'근육질','노련한',('굵은 수염','투박한 얼굴')),
 ),
)
ROLE_NAMES=('수호','무인','사수','주술','치유','암살')
KEY_RE=re.compile(r'^diverse/v2_([0-5])_([0-7])[.]webp$')
PORTRAIT_COUNT=sum(map(len,GROUPS))
assert PORTRAIT_COUNT==48 and all(len(g)==8 for g in GROUPS)


def pick_v2(seed,fighter):
    """Deterministic age/role selection; never consumes world RNG."""
    age=int(fighter.age)
    role=int(fighter.role)
    if role<0 or role>=6:
        return None
    candidates=[i for i,(low,high,*_) in enumerate(GROUPS[role])
                if low<=age<=high]
    if not candidates:
        return None
    hashed=hashlib.blake2s(
        f'portrait-v2:{int(seed)}:{fighter.fid}:{role}'.encode(),
        digest_size=8).digest()
    return candidates[int.from_bytes(hashed,'big')%len(candidates)]


def assign_v2_portrait(seed,fighter):
    if getattr(fighter,'portrait_key',''):
        return False
    slot=pick_v2(seed,fighter)
    if slot is None:
        return False
    fighter.portrait_key=f'diverse/v2_{fighter.role}_{slot}.webp'
    return True


def profile_v2(fighter):
    matched=KEY_RE.fullmatch(getattr(fighter,'portrait_key',''))
    if not matched:
        return None
    role,slot=map(int,matched.groups())
    low,high,build,impression,details=GROUPS[role][slot]
    return dict(version=2,variant=slot,role=role,role_name=ROLE_NAMES[role],
                age_range=[low,high],build=build,impression=impression,
                details=list(details))


def atlas_v2(key):
    """Map a logical saved key to physical atlas path & tile index."""
    matched=KEY_RE.fullmatch(key)
    if not matched:
        return None
    role,slot=map(int,matched.groups())
    return f'assets/portraits/diverse/atlas_v2_{role//2}.webp', (role%2)*8+slot
