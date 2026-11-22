"""v8 prebattle planning contract. No combat ticks, battle rewards or world RNG.

This module intentionally consumes the existing Fighter/Skill sources and does
not import the independent moonpa-arena HTML/JS prototype. The exported packet
is an *input* for an eventual arena bridge, not an authorized result.
"""
from __future__ import annotations
from moonpa_sites import site_details
import moonpa_ai_tactics as ai_tactics
from statistics import mean

from combat import SKILLS, ROLE_SKILLS, SECRET_SKILLS
from moonpa_growth import ATTRIBUTES, available_skill_slots
from moonpa_portraits import portrait_asset
from moonpa_world_v15 import TIERS

ROLE_NAMES=('수호형','무인형','사수형','주술형','치유형','암살형')
FRONT_ROLES=(0,1,5)
CAPTAIN_EFFECTS=(
    (('front_guard',.22,'전열 피해 22% 경감'),('front_resolve',.18,'전열 강인함 18% 증가')),
    (('enemy_heal_block',.25,'상대 치유 효과 25% 감소'),('charge_attack',.20,'아군 돌파조 공격력 20% 증가')),
    (('ranged_barrage',.18,'아군 사수 화력 18% 증가'),('suppress_back',.18,'적 후열 방어력 18% 감소')),
    (('enemy_weakness',.18,'적 전열 방어력 18% 감소'),('enemy_slow',.18,'적 전열 이동속도 18% 감소')),
    (('group_healing',.25,'아군 치유 효과 25% 증가'),('front_shield',.16,'아군 전열 피해 16% 경감')),
    (('backline_raid',.24,'아군 침투 피해 24% 증가'),('backline_expose',.20,'적 후열 피격 피해 20% 증가')),
)
DEPUTY_EFFECTS=(
    (('rear_guard',.22,'후열 보호 효과 22% 증가'),('front_recovery',.18,'전열 보호 회복량 18% 증가')),
    (('breakout',.18,'아군 돌파조 이동속도 18% 증가'),('first_strike',.15,'초반 공격력 15% 증가')),
    (('ranged_cover',.18,'사수 엄호 효과 18% 증가'),('reposition',.16,'아군 후열 재배치 속도 16% 증가')),
    (('counter_hex',.20,'아군 약화 저항 20% 증가'),('hex_support',.15,'적 약화 지속시간 15% 증가')),
    (('rescue',.24,'후열 위기 시 치유 효과 24% 증가'),('field_medicine',.20,'부상 임계치에서 보호 효과 20% 증가')),
    (('intercept',.20,'적 침투 경로 견제 20% 증가'),('shadow_screen',.18,'아군 후열 회피 18% 증가')),
)
DEFAULT_ROLES=(0,1,0,1,4,2,3,5)
ROSTER_MIN=8


def ability(f,appointment):
    if appointment not in ('captain','deputy'):
        raise ValueError('지휘 보직을 확인하세요.')
    kind,value,description=(CAPTAIN_EFFECTS if appointment=='captain' else DEPUTY_EFFECTS)[f.role][f.fid%2]
    return dict(id=kind,value=value,label=description,appointment=appointment)


def skill_description(key):
    s=SKILLS[key]
    return dict(id=key,name=s.name,target=s.target,power=s.power,cost=s.cost,
                cooldown=s.cooldown,level=s.level,note=s.note)


def unlocked(f):
    ordinary=tuple(x for x in ROLE_SKILLS[f.role] if f.lv>=SKILLS[x].level)
    secret=tuple(x for x in f.development.secret_arts
                 if x==SECRET_SKILLS[f.role] and f.lv>=SKILLS[x].level)
    return ordinary+secret


def equipped(f):
    if f.equipped is not None:
        return tuple(x for x in f.equipped if x in unlocked(f))[:available_skill_slots(f.lv)]
    return unlocked(f)[:available_skill_slots(f.lv)]


def stats(f):
    values=list(f.development.attributes)
    for trait in f.development.traits:
        values[trait.attribute]=min(200,values[trait.attribute]+trait.bonus)
    return {key:round(value,1) for key,value in zip(ATTRIBUTES,values)}


def fighter_card(f, *, available=True, reason=''):
    return dict(id=f.fid,name=f.name,role_id=f.role,role=ROLE_NAMES[f.role],
                level=f.lv,ca=round(f.ca,1),attrs=stats(f),
                skills=[skill_description(x) for x in unlocked(f)],
                equipped=list(equipped(f)),slots=available_skill_slots(f.lv),
                injured=f.injured,portrait=portrait_asset(f),
                available=available,reason=reason,captain_ability=ability(f,'captain'),
                deputy_ability=ability(f,'deputy'))


def unit_replacement(zid, index, tier):
    role=DEFAULT_ROLES[index%len(DEFAULT_ROLES)]
    base=TIERS[tier]['base_ca']
    vals=[round(min(200,base + (12 if i in ((1,2,3) if role in FRONT_ROLES else (4,5,6)) else -7)),1)
          for i in range(len(ATTRIBUTES))]
    gid=-(zid+1)*100-index-1
    primary=ROLE_SKILLS[role][0]
    secondary=ROLE_SKILLS[role][1]
    return dict(id=gid,name=f'수비대원 {index+1}',role_id=role,role=ROLE_NAMES[role],
                level=TIERS[tier]['base_lv'],ca=float(base),attrs=dict(zip(ATTRIBUTES,vals)),
                skills=[skill_description(primary),skill_description(secondary)],
                equipped=[primary,secondary],slots=2,
                injured=0,portrait='',available=True,reason='',npc=True,
                captain_ability=dict(id='militia_command',value=.10,label='민병 전열 방어 10% 증가',appointment='captain'),
                deputy_ability=dict(id='militia_cover',value=.10,label='민병 후열 엄호 10% 증가',appointment='deputy'))


def _allowed_zones(game,mode):
    if mode not in ('attack','defense'):
        raise ValueError('점령전 또는 방어전을 선택하세요.')
    return sorted((z for z in game.world.zones if z.tier==game.guild.tier
                  and (z.owner==game.guild.gid if mode=='defense' else
                       z.owner!=game.guild.gid and z.protected_until<=game.clock)),
                  key=lambda z:z.zid)


def target(game, mode, zid):
    zones=_allowed_zones(game,mode)
    if type(zid) is not int or not any(z.zid==zid for z in zones):
        raise ValueError('현재 분석할 수 있는 전투 대상 구역이 아닙니다.')
    return next(z for z in zones if z.zid==zid)


def _enemy_squad(game,mode,z):
    """Scout the actual sect doctrine; unknown future attackers stay hypothetical."""
    from campaign import group_fighters, territory_battlefield
    if mode=='attack':
        guild=game.world.guilds.get(z.owner)
        hypothetical=guild is None
    else:
        opponents=[g for g in game.world.guilds.values()
                   if g.gid!=game.guild.gid and g.tier==game.guild.tier]
        guild=max(opponents,key=lambda g:(g.score,g.strength(),-g.gid),default=None)
        hypothetical=True

    fighters=group_fighters(game.world,guild,8) if guild is not None else []
    profile=ai_tactics.sect_tactic(guild,fighters)
    front=territory_battlefield(z.zid)['front']
    assigned=ai_tactics.tactical_formation(fighters,profile['id'],front)
    members=[dict(fighter_card(f),npc=False,row=row) for f,row,slot in assigned]
    if len(members)<8:
        for i in range(8-len(members)):
            candidate=unit_replacement(z.zid,i,z.tier)
            candidate['row']='front' if sum(x['row']=='front' for x in members)<front else 'back'
            members.append(candidate)
    first=next((m for m in members if m['row']=='front'),members[0])
    captain=first['id']
    deputy=next((m['id'] for m in members if m['id']!=captain and m['role_id']==4),
                next(m['id'] for m in members if m['id']!=captain))
    return dict(guild_id=guild.gid if guild else None,
                name=guild.name if guild else '무주지 수비대',
                is_hypothetical=hypothetical,
                tactic=profile,
                note=('예상 공격군입니다. 실제 방어전의 공격자 편성이 확정된 것은 아닙니다.'
                      if mode=='defense' else
                      '무주지의 가상 수비대 편성입니다.' if guild is None else
                      '전술·전열 편성은 현재 확인된 문파 특성을 기준으로 산정한 참고 정보입니다.'),
                members=members,captain=captain,deputy=deputy)


def enemy_signals(enemy):
    """Only non-numeric tactical cues. Deliberately NEVER reads enemy stats."""
    rows=[dict(role_id=f['role_id'],row=f['row']) for f in enemy['members']]
    fronts=sum(x['row']=='front' for x in rows)
    ranged=sum(x['role_id'] in (2,3) for x in rows)
    healers=sum(x['role_id']==4 for x in rows)
    return dict(rows=rows,front_count=fronts,ranged_count=ranged,
                healers=healers,posture=('후열 화력 집중' if ranged>=3 else
                                        '전열 압박' if fronts>=4 else '균형'))


def deputy_pick(roster, signals):
    """Pure AI. Only own stats/skills and role+row enemy signals are read."""
    eligible=[f for f in roster if f['available']]
    if len(eligible)<ROSTER_MIN:
        return dict(formation=[],captain=None,deputy=None,
                    briefing=f'가용 인원 {len(eligible)}명 · 8명 출전이 필요합니다. 상대 수치는 참고하지 않았습니다.')
    chosen=[]
    # Backline-heavy rivals reward an additional flank threat, not hidden numbers.
    order=([0,1,5,0,4,2,3,1] if signals['ranged_count']>=3 else DEFAULT_ROLES)
    pool=sorted(eligible,key=lambda f:(-f['ca'],f['id']))
    for role in order:
        candidate=next((f for f in pool if f not in chosen and f['role_id']==role),None)
        if candidate:chosen.append(candidate)
    for f in pool:
        if len(chosen)==8:break
        if f not in chosen:chosen.append(f)
    frontline=sorted(chosen,key=lambda f:(
        0 if f['role_id']==0 else 1 if f['role_id']==1 else
        2 if f['role_id']==5 else 3,-f['ca'],f['id']))[:3]
    front_ids={f['id'] for f in frontline}
    captain=next((f for f in frontline if f['role_id']==0),frontline[0])
    deputy=next((f for f in chosen if f['role_id']==4 and f['id']!=captain['id']),
                next(f for f in chosen if f['id']!=captain['id']))
    formation=[dict(id=f['id'],row='front' if f['id'] in front_ids else 'back',
                    skills=(list(f['equipped']) if f['equipped'] else
                            [f['skills'][0]['id']])) for f in chosen]
    intention=('후열 화력 집중에 대응해 돌파조를 확보하고' if signals['ranged_count']>=3
               else '전열을 보강해 상대의 충돌에 대비하고')
    return dict(formation=formation,captain=captain['id'],deputy=deputy['id'],
                briefing=f'{intention} 전열 3명과 후열 5명을 편성했습니다. 상대의 세부 능력치·무공 수치는 사용하지 않았습니다.')


def _clamp(n):
    return max(0,min(100,int(round(n))))


def diagnose(ours, formation):
    by_id={f['id']:f for f in ours}
    front=[by_id[x['id']] for x in formation if x['row']=='front']
    back=[by_id[x['id']] for x in formation if x['row']=='back']
    def avg(rows,keys):
        return mean(sum(f['attrs'][k] for k in keys)/len(keys) for f in rows) if rows else 0
    guard=sum(f['role_id']==0 for f in front)
    healer=sum(f['role_id']==4 for f in back)
    pressure=[f for f in front if f['role_id'] in (1,5)]
    archer=[f for f in back if f['role_id']==2]
    front_score=_clamp(avg(front,('defense','stamina'))*.32+len(front)*7+guard*7)
    rear_score=_clamp(front_score*.42+healer*17+guard*8+
                      sum(f['role_id']==3 for f in back)*7)
    break_score=_clamp(avg(pressure,('strength','agility'))*.36+len(pressure)*12)
    range_score=_clamp(avg(archer,('agility','insight'))*.35+len(archer)*16)
    notes=[]
    if len(front)<3:notes.append('전열 인원이 적어 붕괴 위험이 큽니다.')
    if not healer:notes.append('후열 치유형이 없어 지속전에서 불리합니다.')
    if not guard:notes.append('전열 수호형이 없어 피해 분산이 어렵습니다.')
    if not pressure:notes.append('돌파를 담당할 무인·암살형이 부족합니다.')
    if not notes:notes.append('전열·지원·돌파 역할이 고르게 확보되어 있습니다.')
    return dict(frontline=front_score,rear_protection=rear_score,
                breakthrough=break_score,ranged_fire=range_score,
                notes=notes,meaning='편성 특성의 상대적 지표이며 실제 승률이 아닙니다.')


def validate(game, mode, zid, data):
    z=target(game,mode,zid)
    required={'formation','captain','deputy'}
    if (type(data) is not dict or set(data) not in (required,required|{'briefing'})
            or ('briefing' in data and (type(data['briefing']) is not str or len(data['briefing'])>500))):
        raise ValueError('편성 데이터의 항목을 확인하세요.')
    squad=data['formation']
    if type(squad) is not list or len(squad)!=8:
        raise ValueError('출전 문파원 8명을 편성하세요.')
    roster={f.fid:f for f in game.guild.fighters}
    away=game.world.away(game.guild.gid)
    seen=set();checked=[]
    for slot in squad:
        if type(slot) is not dict or set(slot)!={'id','row','skills'}:
            raise ValueError('전열·후열 편성 정보가 올바르지 않습니다.')
        fid=slot['id']
        if type(fid) is not int or fid in seen or fid not in roster:
            raise ValueError('중복 또는 소속이 아닌 문파원이 있습니다.')
        f=roster[fid]
        if f.injured or fid in away:
            raise ValueError('부상 또는 원정 중인 문파원은 출전할 수 없습니다.')
        if slot['row'] not in ('front','back'):
            raise ValueError('전열 또는 후열만 지정할 수 있습니다.')
        skills=slot['skills']
        if (type(skills) is not list or any(type(x) is not str for x in skills)
                or len(skills)!=len(set(skills)) or not set(skills)<=set(unlocked(f))
                or len(skills)>available_skill_slots(f.lv)):
            raise ValueError('장착 가능한 무공과 최대 슬롯 수를 확인하세요.')
        if not skills:
            raise ValueError('각 문파원에게 무공을 하나 이상 지정하세요.')
        seen.add(fid)
        checked.append(dict(id=fid,row=slot['row'],skills=list(skills)))
    front=sum(x['row']=='front' for x in checked)
    if not 2<=front<=5:
        raise ValueError('전열은 2~5명으로 편성하세요.')
    if type(data['captain']) is not int or type(data['deputy']) is not int:
        raise ValueError('대장과 부대장을 지정하세요.')
    if data['captain']==data['deputy'] or data['captain'] not in seen or data['deputy'] not in seen:
        raise ValueError('대장·부대장은 서로 다른 출전 문파원이어야 합니다.')
    return z,dict(formation=checked,captain=data['captain'],deputy=data['deputy'])


def _public_roster(game):
    away=game.world.away(game.guild.gid)
    return [fighter_card(f,available=not f.injured and f.fid not in away,
                         reason='부상' if f.injured else '원정 중' if f.fid in away else '')
            for f in game.guild.fighters]


def view(game,mode='attack',zid=None):
    candidates=_allowed_zones(game,mode)
    saved=getattr(game.world,'prebattle_plans',{}).get(mode)
    reusable=bool(saved and saved.get('source')=='arena')
    if zid is None:
        if saved and ((saved.get('season'),saved.get('week'))==(game.season,game.week) or reusable):
            zid=saved.get('zone_id')
        if zid is None or not any(z.zid==zid for z in candidates):
            zid=candidates[0].zid if candidates else None
    elif type(zid) is not int or not any(z.zid==zid for z in candidates):
        raise ValueError('전투 대상 구역을 확인하세요.')
    ours=_public_roster(game)
    opponent=_enemy_squad(game,mode,target(game,mode,zid)) if zid is not None else None
    suggestion=deputy_pick(ours,enemy_signals(opponent)) if opponent else None
    lineup=suggestion
    if saved and (reusable or (saved.get('season'),saved.get('week'),saved.get('zone_id'))==(
            game.season,game.week,zid)):
        try:
            validate(game,mode,zid,saved['data'])
            lineup=saved['data']
        except (KeyError,TypeError,ValueError):
            pass
    diagnostics=None
    if lineup and len(lineup['formation'])==8:
        diagnostics=diagnose(ours,lineup['formation'])
    return dict(mode=mode,diagnosis=diagnostics,
                briefing=(lineup.get('briefing') if lineup else None),
                zone_id=zid,zones=[dict(id=z.zid,**site_details(z.zid),
                opponent=game.world.guilds[z.owner].name if z.owner in game.world.guilds
                         else '무주지 수비대',owner=z.owner) for z in candidates],
                our_guild=game.guild.name,roster=ours,enemy=opponent,
                plan=lineup,
                note=('같은 주·구역에서 주간 운영의 추천 편성을 누르면 저장한 점령대가 배치됩니다.'
                      if mode=='attack' else '방어전 편성·분석 화면입니다. 주간 방어는 주간 운영에서 배치합니다.'),
                locked=game.phase!='ready' or game.pending_week is not None)


def preview(game,mode,zid,data):
    _,clean=validate(game,mode,zid,data)
    ours=_public_roster(game)
    by_id={f['id']:f for f in ours}
    selected=[dict(by_id[x['id']],row=x['row'],equipped=x['skills'])
              for x in clean['formation']]
    enemy=_enemy_squad(game,mode,target(game,mode,zid))
    captain=by_id[clean['captain']]
    deputy=by_id[clean['deputy']]
    squad=dict(name=game.guild.name,guild_id=game.guild.gid,members=selected,
               captain=clean['captain'],deputy=clean['deputy'],
               command={'captain':captain['captain_ability'],
                        'deputy':deputy['deputy_ability']})
    enemy_by_id={f['id']:f for f in enemy['members']}
    counter=dict(captain=enemy_by_id[enemy['captain']]['captain_ability'],
                 deputy=enemy_by_id[enemy['deputy']]['deputy_ability'])
    packet=dict(schema='moonpa.prebattle.v1',kind='group_8v8',
                season=game.season,week=game.week,zone_id=zid,mode=mode,
                settlement_owner='campaign',settlement_permitted=False,
                ally=squad,opponent=dict(enemy,command=counter),
                disclaimer='이 입력 패킷은 전투를 시작하거나 구역·경제·경험치를 갱신하지 않습니다.')
    return dict(packet=packet,diagnosis=diagnose(ours,clean['formation']))


def save(game,mode,zid,data):
    if (not game.interactive or game.world.player_bankrupted or game.phase!='ready'
            or game.pending_week is not None
            or (game.battle and game.battle.winner is None)):
        raise ValueError('전투 준비 중인 주차에서만 편성을 저장할 수 있습니다.')
    _,clean=validate(game,mode,zid,data)
    # All checks before mutation. Saving is not a battle commit.
    if not hasattr(game.world,'prebattle_plans'):
        game.world.prebattle_plans={}
    previous=game.world.prebattle_plans.get(mode,{})
    extra=({key:previous[key] for key in ('arts','slots','source')
            if key in previous} if previous.get('zone_id')==zid
            and (previous.get('source')=='arena' or
                 (previous.get('season'),previous.get('week'))==(game.season,game.week))
            else {})
    game.world.prebattle_plans[mode]=dict(season=game.season,week=game.week,
                                         zone_id=zid,data=clean,**extra)
    game.world.money.reconcile()
    return dict(saved=True,view=view(game,mode,zid),**preview(game,mode,zid,clean))


# The live arena group engine has two selectable sect arts. Keep their keys
# aligned with group-engine.mjs and reject unknown/duplicate choices.
ARENA_ARTS=frozenset((
    'rain','poison','tiger','swordlight','lotus','wall','turtle','reflect',
    'mercy','cleanse','medic','revive','net','silence','fog','morale',
    'wing','wedge','withdraw','escort',
))
ARENA_ROLES=('guard','blade','bow','hex','heal','dash')


def _arena_layout(formation, terrain):
    """Respect the real terrain's front/back limits without losing fighters."""
    from campaign import territory_battlefield
    # terrain is the field-layout dict from territory_battlefield, not fake UI geometry.
    front=[x for x in formation if x['row']=='front']
    back=[x for x in formation if x['row']=='back']
    if len(front)>terrain['front']:
        back.extend(front[terrain['front']:])
        front=front[:terrain['front']]
    if len(back)>terrain['back']:
        front.extend(back[terrain['back']:])
        back=back[:terrain['back']]
    if len(front)>terrain['front'] or len(back)>terrain['back']:
        raise ValueError('실제 지형의 전열·후열 배치 한도를 초과했습니다.')
    return [dict(id=x['id'],line=row,slot=n)
            for row,part in (('front',front),('back',back))
            for n,x in enumerate(part)]


def arena_view(game, mode='attack', zid=None):
    """Build independent attack/defense strategy drafts using *all* owned fighters.

    Injury and weekly deployment are NOT planning restrictions. They are checked
    when the actual month runs, so injured fighters never enter real combat.
    """
    from campaign import territory_battlefield
    if mode not in ('attack','defense'):
        raise ValueError('점령전 또는 방어전을 선택하세요.')
    roster_cards=_public_roster(game)
    candidates=_allowed_zones(game,mode)
    saved=getattr(game.world,'prebattle_plans',{}).get(mode,{})
    # A defensive preset is global and editable even before the first capture.
    # It still uses a real league terrain, never a fabricated site or fighter.
    eligible_ids={z.zid for z in candidates}
    if zid not in eligible_ids:
        zid=saved.get('zone_id') if saved.get('zone_id') in eligible_ids else None
    if zid is None and candidates:
        zid=candidates[0].zid
    if zid is None:
        training_zones=sorted((z for z in game.world.zones if z.tier==game.guild.tier),
                              key=lambda z:z.zid)
        if not training_zones:
            raise ValueError('현재 리그에 사용할 연무장 지형이 없습니다.')
        zid=training_zones[0].zid
    zone=next(z for z in game.world.zones if z.zid==zid)
    terrain=territory_battlefield(zid)
    enemy_mode=mode if (mode=='defense' or zone.owner!=game.guild.gid) else 'defense'
    opponent=_enemy_squad(game,enemy_mode,zone)

    owned={x['id']:x for x in roster_cards}
    previous=saved.get('data',{})
    previous_team=previous.get('formation',[]) if isinstance(previous,dict) else []
    valid_saved=(isinstance(previous_team,list) and len(previous_team)==8
                 and all(isinstance(x,dict) and x.get('id') in owned for x in previous_team)
                 and len({x['id'] for x in previous_team})==8)
    if valid_saved:
        formation=previous_team
        captain=previous.get('captain')
        deputy=previous.get('deputy')
    else:
        planning_roster=[dict(x,available=True,reason='') for x in roster_cards]
        suggested=deputy_pick(planning_roster,enemy_signals(opponent))
        formation=suggested['formation']
        captain=suggested['captain']
        deputy=suggested['deputy']
        if not formation:
            # Still show the whole guild, even with fewer than eight members.
            formation=[dict(id=x['id'],row='front' if i<3 else 'back')
                       for i,x in enumerate(planning_roster[:8])]
            captain=formation[0]['id'] if formation else None
            deputy=formation[1]['id'] if len(formation)>1 else None
    ids={f['id'] for f in formation}
    if captain not in ids: captain=formation[0]['id'] if formation else None
    if deputy not in ids or deputy==captain:
        deputy=next((x['id'] for x in formation if x['id']!=captain),None)
    existing_slots=saved.get('slots') if valid_saved else None
    if (type(existing_slots) is list and len(existing_slots)==len(formation)
            and all(type(p) is dict and p.get('line') in ('front','back')
                    and type(p.get('slot')) is int
                    and 0<=p['slot']<terrain[p['line']] for p in existing_slots)
            and len({(p['line'],p['slot']) for p in existing_slots})==len(formation)
            and {p.get('id') for p in existing_slots}==ids):
        positions=existing_slots
    else:
        positions=_arena_layout(formation,terrain)
    actual_fighters={f.fid:f for f in game.guild.fighters}
    def convert(card):
        return dict(id=card['id'],name=card['name'],role=ARENA_ROLES[card['role_id']],
                    strength=round(max(.55,min(2,card['ca']/110)),3),
                    portrait=card['portrait'],ca=card['ca'],
                    pa=round(actual_fighters[card['id']].pa,1),
                    level=card['level'],attrs=card['attrs'],
                    injured=card['injured'],available=card['available'],
                    reason=card['reason'])
    team=[dict(convert(owned[item['id']]),line=item['line'],slot=item['slot'],
               **({'position':item['position']} if isinstance(item.get('position'),dict) else {}))
          for item in positions]
    # No filtering by injured, away, training, defending or attacking assignment.
    bench=[convert(x) for x in roster_cards if x['id'] not in ids]
    opponents=opponent['members']
    foe_positions=_arena_layout([
        dict(id=f['id'],row=f['row']) for f in opponents],terrain)
    enemies={f['id']:f for f in opponents}
    enemy=[dict(id=p['id'],name=enemies[p['id']]['name'],
                role=ARENA_ROLES[enemies[p['id']]['role_id']],
                strength=round(max(.55,min(2,enemies[p['id']]['ca']/110)),3),
                line=p['line'],slot=p['slot']) for p in foe_positions]
    arts=saved.get('arts')
    if not (type(arts) is list and len(arts)==2 and len(set(arts))==2
            and all(a in ARENA_ARTS for a in arts)):
        arts=['lotus','cleanse']
    return dict(kind='training',planMode=mode,zone=zid,
                zoneName=site_details(zid)['name'] if zid in eligible_ids else '공통 전술 연무장',
                mode=8,terrain=terrain['id'],
                team=team,bench=bench,enemyRoster=enemy,
                captain=captain,deputy=deputy,
                chosenArts=arts,scenario=mode,
                sectNames=[game.guild.name,opponent['name']],
                enemyArts=list(opponent['tactic']['arts']),
                enemyTactic=opponent['tactic'],
                enemyCaptain=opponent['captain'],enemyDeputy=opponent['deputy'],
                opponentIsHypothetical=opponent['is_hypothetical'],
                totalRoster=len(roster_cards),
                note='전술 편성에는 부상·다른 임무 배치 문파원도 표시됩니다. 실제 전투에서는 출전 불가 인원이 제외됩니다.')

def arena_save(game,mode,zid,formation,captain,deputy,arts):
    """Atomic, validated permanent attack/defense tactical preset."""
    from campaign import territory_battlefield
    if not isinstance(formation,list) or len(formation)!=8:
        raise ValueError('연무장에 문파원 8명을 편성하세요.')
    if (type(arts) is not list or len(arts)!=2 or len(set(arts))!=2
            or any(type(a) is not str or a not in ARENA_ARTS for a in arts)):
        raise ValueError('문파 무공 2종을 서로 다르게 선택하세요.')
    field=territory_battlefield(zid)
    used=set()
    members=[]
    for item in formation:
        if (type(item) is not dict or set(item) not in (
             {'id','line','slot'},{'id','line','slot','position'})):
            raise ValueError('연무장 배치 데이터가 올바르지 않습니다.')
        fid=item['id'];row=item['line'];slot=item['slot']
        if (type(fid) is not int or row not in ('front','back')
                or type(slot) is not int or not 0<=slot<field[row]
                or fid in used or (row,slot) in
                {(m['line'],m['slot']) for m in members}):
            raise ValueError('출전 인원이 중복되었거나 전장 슬롯을 벗어났습니다.')
        used.add(fid)
        clean=dict(id=fid,line=row,slot=slot)
        if 'position' in item and item['position'] is not None:
            point=item['position']
            if (type(point) is not dict or set(point)!={'x','y'} or
                    any(type(point[k]) not in (int,float) or not 0<=point[k]<=1140
                        for k in ('x','y'))):
                raise ValueError('전술 배치 좌표가 올바르지 않습니다.')
            clean['position']={k:round(point[k],2) for k in ('x','y')}
        members.append(clean)
    if mode not in ('attack','defense'):
        raise ValueError('점령전 또는 방어전을 선택하세요.')
    if not any(z.zid==zid and z.tier==game.guild.tier for z in game.world.zones):
        raise ValueError('현재 리그의 연무장 지형만 선택할 수 있습니다.')
    previous=getattr(game.world,'prebattle_plans',{}).get(mode,{})
    previous_data=previous.get('data',{}).get('formation',[])
    skills={entry['id']:entry['skills'] for entry in previous_data
            if isinstance(entry,dict) and 'id' in entry and 'skills' in entry}
    own={f.fid:f for f in game.guild.fighters}
    checked=[]
    for m in members:
        f=own.get(m['id'])
        if f is None:
            raise ValueError('현재 소속 문파원만 전술에 배치할 수 있습니다.')
        assigned=skills.get(m['id']) or list(equipped(f))
        if (not assigned or len(assigned)!=len(set(assigned))
                or len(assigned)>available_skill_slots(f.lv)
                or not set(assigned)<=set(unlocked(f))):
            assigned=list(equipped(f))
        if not assigned:
            raise ValueError('각 문파원의 장착 무공을 확인하세요.')
        checked.append(dict(id=m['id'],row=m['line'],skills=list(assigned)))
    front=sum(m['row']=='front' for m in checked)
    if not 2<=front<=5:
        raise ValueError('전열은 2~5명으로 편성하세요.')
    if (type(captain) is not int or type(deputy) is not int
            or captain==deputy or {captain,deputy}-used):
        raise ValueError('서로 다른 출전 문파원을 대장·부대장으로 지정하세요.')
    payload=dict(formation=checked,captain=captain,deputy=deputy)
    # Planning intentionally accepts injured/assigned units. Actual combat
    # selects healthy available fighters separately in campaign.py.
    if (not game.interactive or game.world.player_bankrupted or game.phase!='ready'
            or game.pending_week is not None or game.month_run is not None
            or (game.battle and game.battle.winner is None)):
        raise ValueError('전술 저장은 월간 운영을 시작하기 전만 가능합니다.')
    w=game.world
    if not hasattr(w,'prebattle_plans'):
        w.prebattle_plans={}
    w.prebattle_plans[mode]=dict(source='arena',season=game.season,
                                 week=game.week,zone_id=zid,data=payload,
                                 arts=list(arts),slots=members)
    w.money.reconcile()
    return dict(saved=True,message=('점령전' if mode=='attack' else '방어전')+
                ' 전술을 저장했습니다. 부상자는 실전에서 제외되며 남은 출전 인원에 전술이 적용됩니다.',
                config=arena_view(game,mode,zid))
