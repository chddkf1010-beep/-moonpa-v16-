"""Immutable portrait bindings for the shipped default seed-16 founding roster.

Portrait names/roles are checked to prevent attaching a face to a different
person after world generation rules change. Other seeds retain role art.
"""
FOUNDER_16 = {
    640: ("차자찬", 5),
    641: ("서문매휘", 4),
    642: ("표담별", 3),
    643: ("구은휘", 5),
    644: ("설민현", 4),
    645: ("마린온", 4),
    646: ("송하아", 3),
    647: ("문운희", 4),
    648: ("정준운", 5),
    649: ("정서아", 1),
    650: ("천소준", 0),
    651: ("표영현", 1),
    652: ("구희온", 1),
    653: ("안현수", 5),
    654: ("설경천", 5),
    655: ("독고정담", 0),
    656: ("조운별", 2),
    657: ("윤매진", 3),
    658: ("최희화", 5),
    659: ("정윤아", 0),
}


def assign_default_founder_portrait(seed, fighter):
    if seed != 16:
        return False
    identity = FOUNDER_16.get(fighter.fid)
    if identity != (fighter.name, fighter.role):
        return False
    # This property belongs to the Fighter, never the Guild.
    fighter.portrait_key = f"founders/seed16_{fighter.fid}.webp"
    return True


def portrait_asset(fighter):
    return f"assets/portraits/{fighter.portrait_key}" if fighter.portrait_key else ""


# Portraits in the diverse v1 atlas are ORIGINAL commissioned game art.
# Each tile is 1/4 of its atlas dimension.  Index-to-traits mapping is
# deliberately immutable: old save files persist portrait_key, not a RNG seed.
# role ids: 0 guardian, 1 warrior, 2 archer, 3 shaman, 4 healer, 5 assassin.
DIVERSE_PORTRAITS = (
    dict(roles=(0, 1),min_age=28,build='거구',impression='엄격한',details=('짙은 수염','흉터')),
    dict(roles=(0, 4),min_age=24,build='통통한',impression='푸근한',details=('볼살','넓은 얼굴')),
    dict(roles=(0, 1),min_age=38,build='다부진',impression='노련한',details=('백발','주름')),
    dict(roles=(0, 1),min_age=27,build='장대한',impression='호방한',details=('거친 수염','덧니')),
    dict(roles=(3, 4),min_age=38,build='마른',impression='침착한',details=('백발','깊은 주름')),
    dict(roles=(0, 1),min_age=19,build='다부진',impression='굳센',details=('흉터','강한 눈썹')),
    dict(roles=(1, 3, 5),min_age=18,build='마른',impression='날카로운',details=('수척한 뺨','매서운 눈매')),
    dict(roles=(1, 2, 5),min_age=20,build='보통',impression='냉철한',details=('얼굴 흉터','거친 피부')),
    dict(roles=(2, 5),min_age=18,build='날렵한',impression='진지한',details=('긴 눈매','집중한 표정')),
    dict(roles=(2, 3),min_age=36,build='마른',impression='노련한',details=('회색 수염','주름')),
    dict(roles=(3, 4),min_age=26,build='통통한',impression='속을 알 수 없는',details=('볼살','처진 눈')),
    dict(roles=(3, 4),min_age=37,build='마른',impression='엄숙한',details=('깊은 주름','희끗한 머리')),
    dict(roles=(4, 0),min_age=23,build='통통한',impression='다정한',details=('동그란 얼굴','웃는 눈')),
    dict(roles=(4, 3),min_age=38,build='마른',impression='온화한',details=('백발','주름')),
    dict(roles=(5, 4),min_age=18,build='통통한',impression='무심한',details=('볼살','굳게 다문 입')),
    dict(roles=(5, 3),min_age=18,build='마른',impression='음울한',details=('깊은 눈매','매부리코')),
)
DIVERSE_PORTRAIT_PREFIX='diverse/v1_'
DIVERSE_PORTRAIT_SUFFIX='.webp'


def assign_diverse_portrait(seed, fighter):
    """Bind a stable portrait to a new fighter; never advance World/Name RNG.

    No existing portrait is replaced; seed-16 founder originals are assigned
    later by assign_default_founder_portrait and take precedence as before.
    """
    import hashlib

    if fighter.portrait_key:
        return False
    possible=[idx for idx,spec in enumerate(DIVERSE_PORTRAITS)
              if fighter.role in spec['roles'] and fighter.age>=spec['min_age']]
    if not possible:
        # 17-year-old guards/healers may keep role art instead of an elderly face.
        return False
    raw=hashlib.blake2s(
        f'portrait-diversity-v1:{int(seed)}:{fighter.fid}:{fighter.role}'.encode(),
        digest_size=8).digest()
    index=possible[int.from_bytes(raw,'big')%len(possible)]
    fighter.portrait_key=f'{DIVERSE_PORTRAIT_PREFIX}{index:02d}{DIVERSE_PORTRAIT_SUFFIX}'
    return True


def portrait_profile(fighter):
    """Optional UI-only metadata; appearance never changes combat or scouting."""
    key=getattr(fighter,'portrait_key','')
    if not (key.startswith(DIVERSE_PORTRAIT_PREFIX)
            and key.endswith(DIVERSE_PORTRAIT_SUFFIX)):
        return None
    suffix=key[len(DIVERSE_PORTRAIT_PREFIX):-len(DIVERSE_PORTRAIT_SUFFIX)]
    if len(suffix)!=2 or not suffix.isdigit():
        return None
    index=int(suffix)
    if not 0<=index<len(DIVERSE_PORTRAITS):
        return None
    spec=DIVERSE_PORTRAITS[index]
    return dict(version=1,variant=index,build=spec['build'],
                impression=spec['impression'],details=list(spec['details']))
