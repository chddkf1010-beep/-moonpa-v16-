"""Pure, save-compatible tactical identities for AI sect battles.

A sect's established school determines its doctrine. Replacement sects use a
stable guild identity and operating policy; no campaign RNG is consumed.
The actual available fighters determine who can fill the formation. Tactical
titles/arts shown by scouts must be the same as those used in real combat.
"""
from __future__ import annotations

# The archetype ids are also understood by the JS group battle AI.
TACTICS = {
    'ironwall': dict(name='철벽방어', description='수호와 치유를 살려 전열을 지키는 장기전',
                     arts=('lotus','mercy'), combat_style='protect',
                     front=(0,1,5,3,2,4), back=(4,3,2,0,1,5)),
    'archery': dict(name='후열화력', description='사수·주술형이 집중 사격하고 전열이 엄호',
                    arts=('wing','rain'), combat_style='balanced',
                    front=(0,1,5,3,2,4), back=(2,3,4,1,5,0)),
    'breakthrough': dict(name='돌파공격', description='무인·암살형으로 전열을 깨뜨리는 속전',
                         arts=('tiger','wedge'), combat_style='pressure',
                         front=(1,5,0,3,2,4), back=(2,3,4,5,1,0)),
    'disrupt': dict(name='교란술책', description='주술·제압으로 상대 후열의 행동을 방해',
                    arts=('silence','fog'), combat_style='pressure',
                    front=(0,5,1,3,2,4), back=(3,2,4,5,1,0)),
    'flank': dict(name='측면침투', description='암살조가 측면을 돌아 치유·사수형을 급습',
                  arts=('net','wedge'), combat_style='pressure',
                  front=(5,1,0,3,2,4), back=(2,3,4,5,1,0)),
    'adaptive': dict(name='균형대응', description='상대의 빈틈에 맞춰 보호와 공격을 전환',
                     arts=('wall','swordlight'), combat_style='balanced',
                     front=(0,1,5,3,2,4), back=(4,2,3,1,5,0)),
    'militia': dict(name='거점수비', description='성곽과 진형을 지키는 기본 주둔 수비대',
                    arts=('wall','turtle'), combat_style='protect',
                    front=(0,1,5,3,2,4), back=(2,3,4,1,5,0)),
}

# All 32 initial sects appear here under their exact game names.
NAMED_SECTS = {
    'ironwall': ('소림사','아미파','하북팽가','공동파','청석문','정양문'),
    'archery': ('사천당문','제갈세가','낙양검문','청하문','운학문','백림문'),
    'breakthrough': ('화산파','종남파','곤륜파','해남파','금도문','하동검관'),
    'disrupt': ('무당파','청성파','모용세가','적월문','백운검문'),
    'flank': ('개방','점창파','운룡방','비호문','흑풍문'),
    'adaptive': ('남궁세가','형산파','창천문','풍림문'),
}
NAME_TO_TACTIC = {name:kind for kind,names in NAMED_SECTS.items() for name in names}
assert len(NAME_TO_TACTIC)==32

ROLE_IDS = {'guard':0,'blade':1,'bow':2,'hex':3,'heal':4,'dash':5}
STRATEGY_TYPES = {
    'baseline':'ironwall', 'growth':'adaptive', 'transfer':'archery',
    'conquest':'breakthrough', 'balanced':'adaptive',
}
NON_MILITIA = tuple(key for key in TACTICS if key!='militia')


def sect_tactic(guild, fighters=()):
    """Return deterministic doctrine with safe immutable battle payloads."""
    if guild is None:
        kind='militia'
    elif guild.name in NAME_TO_TACTIC:
        kind=NAME_TO_TACTIC[guild.name]
    else:
        # Recruit/replace sect identities stay stable between scouting and combat.
        # Existing guild strategy participates, while roster composition
        # determines deployed members rather than changing doctrine mid-week.
        seed=(int(guild.gid)*13 + sum(ord(c) for c in guild.name)
              + list(STRATEGY_TYPES).index(guild.strategy)
              if guild.strategy in STRATEGY_TYPES else int(guild.gid)*13)
        kind=NON_MILITIA[seed%len(NON_MILITIA)]
    data=TACTICS[kind]
    return dict(id=kind, name=data['name'], description=data['description'],
                combat_style=data['combat_style'], arts=list(data['arts']))


def tactical_formation(fighters, doctrine, front, *, limit=None):
    """Place *the supplied fighters* without inventing or redeploying anybody.

    Frontline roles vary by doctrine; CA decides ties, so developed roster
    compositions still affect the squad. All occupied slots are unique.
    """
    members=list(fighters)
    if limit is not None:
        members=members[:limit]
    front=max(0,min(front,len(members)))
    spec=TACTICS.get(doctrine,TACTICS['adaptive'])
    def ordered(pool, key):
        priority=spec[key]
        return sorted(pool,key=lambda f:(
            priority.index(f.role) if f.role in priority else len(priority),
            -f.ca, f.fid))
    vanguard=ordered(members,'front')[:front]
    taken={f.fid for f in vanguard}
    support=ordered((f for f in members if f.fid not in taken),'back')
    return [(f,'front',i) for i,f in enumerate(vanguard)]+[
        (f,'back',i) for i,f in enumerate(support)]


def sect_captains(cards, doctrine):
    """Leadership comes from actual deployed NPCs, never unrelated mock units."""
    if not cards:
        return None,None
    spec=TACTICS.get(doctrine,TACTICS['adaptive'])
    front=[c for c in cards if c['line']=='front']
    ranked=front or cards
    def order(member):
        role=ROLE_IDS.get(member['role'],-1)
        priority=spec['front']
        return (priority.index(role) if role in priority else 6,
                -member.get('ca',0),member['id'])
    captain=min(ranked,key=order)['id']
    candidates=[c for c in cards if c['id']!=captain]
    deputy=min(candidates,key=lambda c:(
        0 if c['role']=='heal' else 1 if c['role']=='hex' else 2,
        -c.get('ca',0),c['id']))['id'] if candidates else None
    return captain,deputy
