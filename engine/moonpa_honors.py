"""Honor, epithet, collection and season chronicle. Pure data + explicit event hooks.

League honors last exactly the season following their award. Permanent special
honors and fighter epithets are historical collections, not combat buffs.
Unavailable future modes are catalogued but never randomly/mistakenly awarded.
"""
from __future__ import annotations
from collections import Counter

# A formal honor is assigned by the finished season, and displayed in the
# NEXT season only. 5th-8th ranks do not receive a formal honor.
RANK_NAMES={
    (1,1):'천하제일',(1,2):'중원패주',(1,3):'북방웅주',(1,4):'사해명문',
    (2,1):'대호',(2,2):'청룡호',(2,3):'백호',(2,4):'중원의 호걸',
    (3,1):'소호',(3,2):'비룡문',(3,3):'풍운지문',(3,4):'신흥강호',
    (4,1):'신진맹주',(4,2):'차세대 패자',(4,3):'강호신성',(4,4):'신흥문파',
}

# id, name, threshold / published condition, live evaluator key or None.
SPECIAL=[
 ('unbeaten_sect','불패지문','한 시즌 점령전 20회 이상, 무패', 'unbeaten'),
 ('iron_sect','철혈문파','한 시즌 방어전 20회 이상 승리','iron'),
 ('victory_streak','백전백승','한 시즌 점령전 30회 이상, 승률 90% 이상','victory'),
 ('invincible','천하무적','1부 3시즌 연속 우승','triple'),
 ('eternal_throne','만년왕좌','1부 통산 5회 우승','five_champ'),
 ('rich_sect','부국강문','시즌 종료 보유금이 해당 부 1위','rich'),
 ('great_merchant','천하거상','통산 점령 순수익 누적 기준 달성',None),
 ('territory_guard','무림수호','특정 영지 10주 연속 방어',None),
 ('pioneer','개척선봉','시즌 점령전 성공 횟수 부내 1위','pioneer'),
 ('legend_home','강호명가','전설 별호를 보유한 문파원 5명 확보','legend_home'),
 ('talent_hub','인재의 요람','저전력에서 고전력으로 육성한 무인 5명','talent'),
 ('phoenix_sect','재기의 불꽃','강등 직후 다음 시즌 재승격','recovery'),
 ('promotion_king','승격불패','10대10 승강전 3연승',None),
 ('true_legend','전설의 문파','4부에서 출발해 1부 우승 달성','from_fourth'),
]
# Six groups of ten. 3rd element is an unlock method if the current engine
# supplies authoritative data, otherwise None: never fabricated.
EPITHETS=[
 ('blood_sword','혈검','일반','공격·돌파','누적 30명 처치','kills30'),
 ('breaker','파군','희귀','공격·돌파','한 전투에서 적 4명 처치','kills4'),
 ('one_strike','일격필살','영웅','공격·돌파','단일 타격 최대 체력 70% 이상 피해',None),
 ('peerless','무쌍','전설','공격·돌파','한 전투에서 적 6명 처치','kills6'),
 ('sword_demon','검귀','영웅','공격·돌파','검계 무공으로 100명 처치',None),
 ('breakthrough','돌파의 선봉','희귀','공격·돌파','전선 돌파 후 후열 침투 10회',None),
 ('nightmare','후열의 악몽','영웅','공격·돌파','후열 상대 50명 처치',None),
 ('sky_sword','천검','전설','공격·돌파','검계 무공 누적 피해 최고 단계',None),
 ('berserker','광전사','희귀','공격·돌파','빈사 상태에서 3명 처치',None),
 ('sky_breaker','파천황','전설','공격·돌파','불리한 전투를 핵심 처치로 역전',None),
 ('iron_wall','철벽','희귀','방어·생존','받은 피해 누적 3,000 이상','damage3000'),
 ('diamond','금강불괴','전설','방어·생존','막대한 피해를 받고도 무사 생존',None),
 ('phoenix','불사조','영웅','방어·생존','빈사 후 회복해 승리',None),
 ('unyielding','불굴','희귀','방어·생존','체력 10% 이하에서 치유 없이 승리',None),
 ('guardian','수호신','영웅','방어·생존','아군 대신 피해받기 100회',None),
 ('last_shield','최후의 방패','영웅','방어·생존','마지막 전열 생존자로 승리',None),
 ('one_against_many','만인적','전설','방어·생존','적 5명의 공격을 견디고 승리',None),
 ('iron_defender','철혈수비','희귀','방어·생존','방어전 30회 성공',None),
 ('veteran','백전노장','영웅','방어·생존','전투에 누적 200회 참가','battle200'),
 ('mountain','태산','전설','방어·생존','전선 붕괴를 장기간 방지',None),
 ('divine_bow','신궁','영웅','사수·주술·치유','사격 명중률과 처치 업적 달성',None),
 ('clairvoyant','천리안','희귀','사수·주술·치유','원거리 공격 200회 명중',None),
 ('perfect_shot','일발백중','전설','사수·주술·치유','일정 횟수 이상 연속 명중',None),
 ('poison_king','독왕','영웅','사수·주술·치유','약화·중독 무공 누적 성공',None),
 ('strategist','귀모','희귀','사수·주술·치유','상대 행동 방해 100회',None),
 ('dark_commander','마도군사','전설','사수·주술·치유','다수 상대에게 주술 약화 중첩',None),
 ('divine_healer','의선','전설','사수·주술·치유','누적 치유량 5,000 이상','heal5000'),
 ('hua_tuo','화타의 손','영웅','사수·주술·치유','한 전투에서 빈사 아군 3명 구조',None),
 ('life_lamp','생명의 등불','희귀','사수·주술·치유','누적 회복 행동 100회','heal100'),
 ('ward_sage','호법진인','영웅','사수·주술·치유','보호로 동료의 생존에 크게 기여',None),
 ('sword_emperor','검황','영웅','비무·대회','검계 비무대회 우승',None),
 ('fist_king','권왕','영웅','비무·대회','권계 비무대회 우승',None),
 ('spear_god','창신','영웅','비무·대회','창계 비무대회 우승',None),
 ('archery_star','궁성','영웅','비무·대회','궁술 비무대회 우승',None),
 ('martial_supreme','무림제일인','전설','비무·대회','무예대회 종합 우승',None),
 ('sword_saint','천하검성','전설','비무·대회','검계 비무대회 3연속 우승',None),
 ('tournament_prodigy','비무귀재','희귀','비무·대회','첫 비무대회 참가 우승',None),
 ('unbeaten_swordsman','불패검객','전설','비무·대회','비무 20연승',None),
 ('tournament_breaker','대회 파괴자','희귀','비무·대회','우세한 상대를 연속 3회 격파',None),
 ('runnerup','만년준우승','일반','비무·대회','비무 준우승 3회',None),
 ('prodigy','천재','희귀','성장·영입·충성','25세 이전 전력 155 도달','young155'),
 ('late_bloomer','대기만성','희귀','성장·영입·충성','30세 이후 전력 45 이상 성장','late45'),
 ('child_genius','신동','영웅','성장·영입·충성','20세 이전 전력 140 도달','child140'),
 ('perpetual_prospect','만년유망주','일반','성장·영입·충성','잠재력을 오랫동안 실현하지 못함',None),
 ('legendary_student','전설의 제자','전설','성장·영입·충성','초기 전력 90 이하에서 165 이상 성장','from90'),
 ('loyalist','충신','희귀','성장·영입·충성','동일 문파 10시즌 소속',None),
 ('wanderer','떠돌이 검객','일반','성장·영입·충성','서로 다른 5개 문파 소속',None),
 ('mercenary','강호의 용병','희귀','성장·영입·충성','이적 후 3개 문파에서 핵심 전투 승리',None),
 ('comeback','재기의 영웅','영웅','성장·영입·충성','장기 부상 복귀 후 주요 전투 승리',None),
 ('elder','노익장','희귀','성장·영입·충성','40세 이후 전투 승리','elder'),
 ('territory_lord','영지의 주인','희귀','영지·승격·특수','동일 영지 방어전 10회 승리',None),
 ('promotion_ruler','승격의 지배자','전설','영지·승격·특수','10대10 승강전 3회 승리',None),
 ('unbeaten_lion','무패의 사자','영웅','영지·승격·특수','시즌 점령전 30회 이상, 성공률 90% 이상','lion'),
 ('reverse_hero','역전의 영웅','영웅','영지·승격·특수','불리한 승격전에서 3명 처치 후 승리',None),
 ('pioneer_fighter','강호의 개척자','희귀','영지·승격·특수','서로 다른 영지 10곳 점령 참가','ten_zones'),
 ('silent_defender','침묵의 수호자','희귀','영지·승격·특수','처치 없이 다수 방어전 승리',None),
 ('fated_survivor','운명의 생존자','영웅','영지·승격·특수','연속 빈사 상태 전투 생존',None),
 ('trial_master','시련의 지배자','희귀','영지·승격·특수','고난도 정예 임무 연속 성공',None),
 ('falling_star','추락하는 별','일반','영지·승격·특수','전력 최고치 대비 30 이상 하락','fallen30'),
 ('fate_breaker','운명을 거스른 자','전설','영지·승격·특수','숨겨진 연속 기연 완료',None),
]
assert len(RANK_NAMES)==16 and len(SPECIAL)==14 and len(EPITHETS)==60
SPECIAL_BY_ID={item[0]:item for item in SPECIAL}
EPITHET_BY_ID={item[0]:item for item in EPITHETS}

def initialize(w):
    """Legacy saves may lack all honor fields."""
    for name,default in (('honor_titles',{}),('honor_history',[]),
                         ('honor_fighters',{}),('honor_tracking',{}),
                         ('honor_baselines',{}),('honor_known_names',{}),
                         ('honor_sect_collections',{})):
        if not hasattr(w,name):
            setattr(w,name,default.copy())
    return w

def _baseline(g):
    return dict(attacks=g.attacks,wins=g.attack_wins,defenses=g.defense_wins,
                promoted=g.promoted,relegated=g.relegated)

def reset_baseline(w,g):
    initialize(w)
    w.honor_baselines[g.gid]=_baseline(g)
    # A new player's guild occupies a dissolved sect's historical slot.
    w.honor_titles.pop(g.gid,None)

def current_rank(w,gid,season):
    entry=getattr(w,'honor_titles',{}).get(gid,{}).get('rank')
    return entry if entry and entry['valid_season']==season else None

def current_label(w,gid,season):
    rank=current_rank(w,gid,season)
    if rank:return rank['name']
    specials=getattr(w,'honor_titles',{}).get(gid,{}).get('special',{})
    if not specials:return None
    # If no seasonal honor is valid, display the rarest permanent honorary title.
    priority=('true_legend','eternal_throne','invincible','victory_streak',
              'unbeaten_sect','iron_sect','phoenix_sect','promotion_king',
              'legend_home','talent_hub','rich_sect','pioneer','territory_guard',
              'great_merchant')
    key=next((k for k in priority if k in specials),None)
    return SPECIAL_BY_ID[key][1] if key else None

def display_name(w,gid,season):
    g=w.guilds[gid]
    title=current_label(w,gid,season)
    return f'{title} · {g.name}' if title else g.name

def _award(store,key,season):
    item=store.setdefault(key,dict(count=0,first_season=season,last_season=season,seasons=[]))
    if season not in item['seasons']:
        item['count']+=1
        item['last_season']=season
        item['seasons'].append(season)
        return True
    return False

def award_fighter(w,fid,key,season,gid=None):
    """Explicit authoritative achievement only, never RNG. Repeat per season."""
    initialize(w)
    if key not in EPITHET_BY_ID or type(fid) is not int:
        raise ValueError('등록되지 않은 무인 별호입니다.')
    record=w.honor_fighters.setdefault(fid,{})
    new=_award(record,key,season)
    if new and gid is not None:
        col=w.honor_sect_collections.setdefault(gid,{})
        _award(col,key,season)
    return new

def record_battle(w,battle,season,week,zone_id,victory):
    """Player tactical battle: immutable event facts, after combat resolved."""
    initialize(w)
    knockouts=Counter(e['actor'] for e in battle.events if e.get('kind')=='knockout'
                      and e.get('actor') is not None)
    zone_by_id=zone_id
    for fid,u in battle.units.items():
        if fid not in w.honor_tracking:
            w.honor_tracking[fid]={}
        track=w.honor_tracking[fid]
        track['battles']=track.get('battles',0)+1
        track['kills']=track.get('kills',0)+knockouts[fid]
        track['damage_taken']=track.get('damage_taken',0)+u.hit_taken
        track['healing']=track.get('healing',0)+u.healing
        track['heals']=track.get('heals',0)+sum(
            e.get('kind')=='heal' and e.get('actor')==fid and (e.get('amount') or 0)>0
            for e in battle.events)
        if u.side==0:
            per=track.setdefault('per_season',{})
            counts=per.setdefault(season,dict(participations=0,wins=0))
            counts['participations']+=1
            counts['wins']+=int(victory)
            if victory:
                zones=track.setdefault('captured_zones',[])
                if zone_by_id not in zones:zones.append(zone_by_id)
        guild=next((g for g in w.guilds.values() if any(f.fid==fid for f in g.fighters)),None)
        if guild is None:continue
        fighter=next(f for f in guild.fighters if f.fid==fid)
        w.honor_known_names[fid]=fighter.name
        conditions={
            'blood_sword':track['kills']>=30,
            'breaker':knockouts[fid]>=4,
            'peerless':knockouts[fid]>=6,
            'iron_wall':track['damage_taken']>=3000,
            'veteran':track['battles']>=200,
            'divine_healer':track['healing']>=5000,
            'life_lamp':track['heals']>=100,
            'elder':fighter.age>=40 and u.side==battle.winner,
            'pioneer_fighter':u.side==0 and len(track.get('captured_zones',[]))>=10,
        }
        for key,ok in conditions.items():
            if ok:award_fighter(w,fid,key,season,guild.gid)

def observe_growth(w,season):
    """Idempotent per-season threshold unlocks, no fake tournament data."""
    initialize(w)
    for guild in w.guilds.values():
        for fighter in guild.fighters:
            fid=fighter.fid
            track=w.honor_tracking.setdefault(fid,{})
            track.setdefault('first_ca',round(fighter.ca,2))
            track['peak_ca']=max(track.get('peak_ca',fighter.ca),fighter.ca)
            w.honor_known_names[fid]=fighter.name
            # Thresholds unlock once, not every subsequent week/season.
            unlocked=w.honor_fighters.get(fid,{})
            for key,met in (
                ('prodigy',fighter.age<25 and fighter.ca>=155),
                ('child_genius',fighter.age<20 and fighter.ca>=140),
                ('late_bloomer',fighter.age>=30 and fighter.ca-track['first_ca']>=45),
                ('legendary_student',track['first_ca']<=90 and fighter.ca>=165),
                ('falling_star',track['peak_ca']-fighter.ca>=30),
            ):
                if met and key not in unlocked:award_fighter(w,fid,key,season,guild.gid)
            # Existing old title of a newly hired character remains theirs.
            for key in w.honor_fighters.get(fid,{}):
                w.honor_sect_collections.setdefault(guild.gid,{}).setdefault(
                    key,dict(count=1,first_season=season,last_season=season,seasons=[season]))

def _special_conditions(w,g,rank,tier,delta,history,by_tier):
    recent=history[-2:] if history else []
    return dict(
        unbeaten=delta['attacks']>=20 and delta['attacks']==delta['wins'],
        iron=delta['defenses']>=20,
        victory=delta['attacks']>=30 and delta['wins']/max(1,delta['attacks'])>=.90,
        triple=(tier==1 and rank==1 and len(recent)==2 and
                all(x['tier']==1 and x['rank']==1 for x in recent)),
        five_champ=g.championships>=5,
        rich=g is max(by_tier[tier],key=lambda x:(x.cash,-x.gid)),
        pioneer=(delta['wins']>0 and delta['wins']==max(
            w.guilds[other.gid].attack_wins-w.honor_baselines.get(other.gid,_baseline(other))['wins']
            for other in by_tier[tier])),
        legend_home=sum(any(EPITHET_BY_ID[k][2]=='전설'
                            for k in w.honor_fighters.get(f.fid,{})) for f in g.fighters)>=5,
        talent=sum(w.honor_tracking.get(f.fid,{}).get('first_ca',f.ca)<=90 and f.ca>=155
                   for f in g.fighters)>=5,
        recovery=bool(history and history[-1]['result']=='강등' and g.tier<tier),
        from_fourth=bool(tier==1 and rank==1 and g.first_reach==1 and
                         any(x['tier']==4 for x in history)),
    )

def finish_season(w,season,rank_by_tier,pre_move_tiers):
    """Called exactly once after promotion/relegation, before annual resets."""
    initialize(w)
    if season==0:
        for g in w.guilds.values():w.honor_baselines[g.gid]=_baseline(g)
        return None
    if w.honor_history and w.honor_history[-1]['season']>=season:
        raise AssertionError('동일 시즌 존호와 연대기를 중복 결산할 수 없습니다.')
    observe_growth(w,season)
    history_by_guild={gid:[h['guilds'][gid] for h in w.honor_history if gid in h['guilds']]
                      for gid in w.guilds}
    tables={}
    current={}
    for tier,ranked in rank_by_tier.items():
        tables[tier]=[dict(id=g.gid,name=g.name,rank=i,tier=tier,score=round(g.score,2),
                           ca=round(g.strength(),2),cash=g.cash)
                       for i,g in enumerate(ranked,1)]
    for tier,ranked in rank_by_tier.items():
        for i,g in enumerate(ranked,1):
            base=w.honor_baselines.get(g.gid,_baseline(g))
            delta={key:max(0,getattr(g,field)-base.get(key,0)) for key,field in (
                ('attacks','attacks'),('wins','wins'),('defenses','defenses'))}
            # Baseline's wins/defenses are captured by their actual field names.
            delta['wins']=max(0,g.attack_wins-base.get('wins',g.attack_wins))
            delta['defenses']=max(0,g.defense_wins-base.get('defenses',g.defense_wins))
            next_tier=g.tier
            result='승격' if next_tier<tier else '강등' if next_tier>tier else '잔류'
            rank_name=RANK_NAMES.get((tier,i))
            titles=w.honor_titles.setdefault(g.gid,{'rank':None,'special':{}})
            if rank_name:
                titles['rank']=dict(id=f'rank_{tier}_{i}',name=rank_name,
                                    award_season=season,valid_season=season+1,
                                    tier=tier,rank=i)
            else:
                titles['rank']=None
            history=history_by_guild[g.gid]
            factors=_special_conditions(w,g,i,tier,delta,history,rank_by_tier)
            awarded=[]
            for key,name,_,flag in SPECIAL:
                if flag and factors.get(flag,False):
                    if _award(titles.setdefault('special',{}),key,season):
                        awarded.append(name)
            current[g.gid]=dict(id=g.gid,name=g.name,tier=tier,rank=i,
                score=round(g.score,2),next_tier=next_tier,result=result,
                rank_title=rank_name,special_awards=awarded,
                season_attacks=delta['attacks'],season_wins=delta['wins'],
                season_defenses=delta['defenses'],
                titles=[rank_name] if rank_name else [])
            current[g.gid]['titles']+=awarded
            w.honor_baselines[g.gid]=_baseline(g)
    archive=dict(season=season,tiers=tables,guilds=current)
    w.honor_history.append(archive)
    return archive

def chronicle(w,gid,season):
    initialize(w)
    g=w.guilds[gid]
    entries=[dict(x['guilds'][gid],season=x['season'],standings=x['tiers'][x['guilds'][gid]['tier']])
             for x in w.honor_history if gid in x['guilds']]
    titles=w.honor_titles.get(gid,{})
    current=current_rank(w,gid,season)
    collection=w.honor_sect_collections.get(gid,{})
    return dict(id=gid,name=g.name,display_name=display_name(w,gid,season),
                current_rank=current,season=season,tier=g.tier,
                best_tier=g.first_reach,promotions=g.promoted,relegations=g.relegated,
                championships=g.championships,
                title_count=len({x['rank_title'] for x in entries if x['rank_title']})+
                            len(titles.get('special',{})),
                epithet_count=len(collection),
                entries=entries,specials=[dict(id=key,name=SPECIAL_BY_ID[key][1],**rec)
                        for key,rec in titles.get('special',{}).items()
                        if key in SPECIAL_BY_ID],
                collection=[dict(id=key,name=EPITHET_BY_ID[key][1],**rec)
                        for key,rec in collection.items() if key in EPITHET_BY_ID])

def codex(w,gid,season):
    initialize(w)
    history=chronicle(w,gid,season)
    titles=w.honor_titles.get(gid,{})
    all_ranks={x['rank_title'] for x in history['entries'] if x['rank_title']}
    owner=w.guilds[gid]
    owned= {f.fid:f.name for f in owner.fighters}
    acquired=w.honor_sect_collections.get(gid,{})
    nicknames=[]
    for key,name,grade,category,condition,flag in EPITHETS:
        holders=[dict(id=fid,name=owned[fid],count=w.honor_fighters[fid][key]['count'])
                 for fid in owned if key in w.honor_fighters.get(fid,{})]
        nicknames.append(dict(id=key,name=name,grade=grade,category=category,
             condition=('???' if grade=='전설' and flag is None else condition),
             status='획득' if key in acquired or holders else '미획득',
             available=flag is not None, count=acquired.get(key,{}).get('count',0),
             seasons=acquired.get(key,{}).get('seasons',[]),holders=holders))
    rank=[dict(id=f'rank_{tier}_{position}',name=name,tier=tier,rank=position,
                unlocked=name in all_ranks,
                current=bool(current_rank(w,gid,season) and
                             current_rank(w,gid,season)['name']==name),
                seasons=[x['season'] for x in history['entries'] if x['rank_title']==name])
          for (tier,position),name in RANK_NAMES.items()]
    special=[dict(id=key,name=name,condition=condition,
                  available=flag is not None,
                  unlocked=key in titles.get('special',{}),
                  count=titles.get('special',{}).get(key,{}).get('count',0),
                  seasons=titles.get('special',{}).get(key,{}).get('seasons',[]))
             for key,name,condition,flag in SPECIAL]
    return dict(id=gid,name=owner.name,season=season,rank=rank,
                special=special,nicknames=nicknames,
                totals=dict(rank=sum(x['unlocked'] for x in rank),
                            special=sum(x['unlocked'] for x in special),
                            nicknames=sum(x['status']=='획득' for x in nicknames)),
                status_note='미지원 대회·10대10 승강전 업적은 향후 전투 기록 연결 시 해금됩니다. 현재 획득 가능 조건은 실제 기록만으로 판정합니다.')
