"""Round-based execution of named and legendary conditional passives.

The current tactical engine has 20 rounds, not realtime seconds.  For these
experimental powers one round is treated as one second; the eventual 10v10
autobattler can migrate the same condition checks to a simulation clock.

All mutable combat talent state belongs to Battle.context and is save-safe.
"""
from math import ceil


def power(battle, unit):
    return battle.context.get('notables', {}).get(str(unit.id), {}).get('key')


def living_with(battle, side, key):
    return next((unit for unit in battle.units.values()
                 if unit.side == side and unit.hp and power(battle, unit) == key), None)


def state(battle):
    return battle.context.setdefault('notable_state', {})


def active_shield(battle, unit):
    return any(battle.active(unit, kind) for kind in ('wall', 'secret_wall', 'ward'))


def dealt_multiplier(battle, actor, target):
    if not battle.context.get('notables'):
        return 1.0
    n=state(battle)
    factor=1.0
    if actor.role == 1 and living_with(battle, actor.side, 'namgung_seol'):
        factor*=1 + min(10,n.get('namgung_stacks',{}).get(str(actor.side),0))*.01
    if power(battle,actor)=='archer_focus':
        entry=n.get('archer_focus',{}).get(str(actor.id),{})
        if entry.get('target')==target.id:
            factor*=1+min(5,entry.get('stacks',0))*.02
    if battle.active(actor,'zhuge_power') and active_shield(battle,actor):
        factor*=1.10
    marks=n.get('marks',{})
    if actor.role==2 and marks.get(str(target.id))==actor.side and living_with(battle,actor.side,'seomun_biyeon'):
        factor*=1.12
    return min(1.3,factor)


def received_multiplier(battle, target):
    factor=.70 if power(battle,target)=='jang_cheonho' and target.hp<=target.max_hp*.50 else 1.
    if battle.active(target,'zhuge_power') and active_shield(battle,target):
        factor*=.90
    return factor


def piercing(battle,actor,target):
    """Twentieth of the blocked portion? Precisely 20% reduction ignore."""
    meta=state(battle).get('pierce',{}).get(str(target.id))
    return bool(meta and meta>=battle.round and actor.role==1
                and living_with(battle,actor.side,'dokgo_mugeuk'))


def _start_dot(battle, owner, target, kind, duration, transfers=0):
    n=state(battle)
    dots=n.setdefault('dots',[])
    # Nonstacking DoTs per kind and target; another source can refresh the DoT.
    for dot in dots:
        if dot['target']==target.id and dot['kind']==kind:
            if dot['until'] < battle.round+duration:
                dot.update(owner=owner.id,until=battle.round+duration,
                           next=battle.round+1,transfers=transfers)
            return
    dots.append(dict(owner=owner.id,target=target.id,kind=kind,
                     until=battle.round+duration,next=battle.round+1,
                     transfers=transfers))
    battle.emit(f'{target.name} · {"중독" if kind=="poison" else "출혈"} {duration}초',
                'debuff',owner,target,kind)


def hit(battle, actor, target):
    if not target.hp or not actor.hp or not battle.context.get('notables'):
        return
    ability=power(battle,actor)
    n=state(battle)
    if ability=='dokgo_jin':
        _start_dot(battle,actor,target,'bleed',5)
    elif ability=='dang_soyeon':
        _start_dot(battle,actor,target,'poison',4)
    elif ability=='baek_mujin':
        key=f'{actor.id}:{target.id}'
        cooldowns=n.setdefault('seals',{})
        if cooldowns.get(key,0)<=battle.round:
            cooldowns[key]=battle.round+20
            battle.effect(target,'notable_seal',5,actor.id)
            battle.emit(f'{actor.name} · {target.name} 액티브 무공 5초 봉인',
                        'debuff',actor,target,'notable_seal')
    elif ability=='archer_focus':
        focus=n.setdefault('archer_focus',{})
        prev=focus.get(str(actor.id),{})
        stacks=min(5,(prev.get('stacks',0)+1) if prev.get('target')==target.id else 1)
        focus[str(actor.id)]=dict(target=target.id,stacks=stacks)
    if actor.role==1 and living_with(battle,actor.side,'dokgo_mugeuk'):
        hits=n.setdefault('warrior_hits',{}).setdefault(str(target.id),[])
        hits.append(actor.id)
        if (len(hits)>=10 and len(set(hits))>=3
                and n.setdefault('pierce',{}).get(str(target.id),0)<battle.round):
            n['pierce'][str(target.id)]=battle.round+4
            battle.emit(f'{target.name} · 천하일검 발동, 무인형이 피해 경감 20% 무시 (5초)',
                        'buff',actor,target,'legend_pierce')
            n['warrior_hits'][str(target.id)]=[]
    if actor.role==2 and living_with(battle,actor.side,'seomun_biyeon'):
        past=n.setdefault('archer_hits',{}).setdefault(str(target.id),[])
        past[:]=[(id,when) for id,when in past if battle.round-when<=2]
        past.append((actor.id,battle.round))
        if (len({id for id,_ in past})>=3
                and str(target.id) not in n.setdefault('marks',{})):
            n['marks'][str(target.id)]=actor.side
            battle.emit(f'{target.name} · 백발백중 표식, 사수형 피해 +12%',
                        'debuff',actor,target,'legend_mark')


def protect(battle, target, source):
    if not battle.context.get('notables') or not target.hp:
        return
    n=state(battle)
    zhuge=living_with(battle,target.side,'zhuge_hyeon')
    if zhuge:
        last=n.setdefault('zhuge_cooldown',{})
        key=str(target.id)
        if last.get(key,0)<=battle.round:
            last[key]=battle.round+5
            battle.effect(target,'zhuge_power',5,zhuge.id,notable_hook=False)
            battle.emit(f'{target.name} · 호법진: 보호 중 공격·방어 +10%',
                        'buff',zhuge,target,'zhuge_power')
    tianming=living_with(battle,target.side,'zhuge_tianming')
    if tianming:
        key=str(tianming.id)
        cooldown=n.setdefault('tianming_cooldown',{})
        if cooldown.get(key,0)<=battle.round:
            count=n.setdefault('tianming_count',{})
            count[key]=count.get(key,0)+1
            if count[key]>=3:
                count[key]=0
                cooldown[key]=battle.round+15
                affected=0
                for unit in battle.units.values():
                    if unit.side==target.side and unit.hp and active_shield(battle,unit):
                        battle.effect(unit,'legend_speed',5,tianming.id,notable_hook=False)
                        affected+=1
                if affected:
                    battle.emit(f'{tianming.name} · 천기삼변: 보호 중인 아군 {affected}명 공격 가속 (5초)',
                                'buff',tianming,target,'legend_speed')


def healed(battle, healer, target, amount, overflow):
    if not battle.context.get('notables'):
        return
    yeonhwa=living_with(battle,healer.side,'baek_yeonhwa')
    if not yeonhwa:
        return
    n=state(battle)
    side=str(healer.side)
    active=n.setdefault('yeonhwa_active',{})
    if active.get(side,0)>=battle.round and overflow>0:
        shields=n.setdefault('barriers',{})
        barrier=shields.get(str(target.id),{})
        old=barrier.get('amount',0) if barrier.get('until',0)>=battle.round else 0
        new=min(round(target.max_hp*.20),old+round(overflow*.50))
        if new>old:
            shields[str(target.id)]=dict(amount=new,until=battle.round+4)
            battle.effect(target,'legend_barrier',5,yeonhwa.id,notable_hook=False)
            battle.emit(f'{target.name} · 생사윤회 보호막 +{new-old}',
                        'buff',yeonhwa,target,'legend_barrier',new-old)
    tracks=n.setdefault('heal_track',{}).setdefault(side,[])
    tracks[:]=[(when,points) for when,points in tracks if battle.round-when<=4]
    if amount:
        tracks.append((battle.round,amount))
    cd=n.setdefault('yeonhwa_cooldown',{})
    if cd.get(side,0)<=battle.round:
        total_hp=sum(u.max_hp for u in battle.units.values() if u.side==healer.side)
        if sum(points for _,points in tracks)>=total_hp*.20:
            active[side]=battle.round+4
            cd[side]=battle.round+15
            battle.emit(f'{yeonhwa.name} · 생사윤회 발동: 초과 치유의 50% 보호막화 (5초)',
                        'buff',yeonhwa,target,'legend_barrier')


def absorb(battle,target,dealt):
    n=battle.context.get('notable_state',{})
    pool=n.get('barriers',{}).get(str(target.id),{})
    if not pool or pool['until']<battle.round or not pool['amount'] or not dealt:
        return dealt
    taken=min(dealt,pool['amount'])
    pool['amount']-=taken
    target.prevented+=taken
    battle.emit(f'{target.name} · 보호막이 피해 {taken} 흡수',
                'buff',None,target,'legend_barrier',taken)
    if not pool['amount']:
        target.effects.pop('legend_barrier',None)
    return dealt-taken


def split(battle,actor,target,dealt):
    if not dealt or target.row!='back' or not battle.context.get('notables'):
        return dealt
    guard=living_with(battle,target.side,'hwangbo_jinak')
    if not guard or not battle.active(guard,'legend_redirect') or guard is target:
        return dealt
    redirected=min(guard.hp,round(dealt*.30))
    if redirected:
        battle.apply_damage(actor,guard,redirected,'legend_redirect','reflection')
    return dealt-redirected


def hp_changed(battle):
    if not battle.context.get('notables'):
        return
    n=state(battle)
    used=n.setdefault('hwangbo_used',{})
    for unit in tuple(battle.units.values()):
        if power(battle,unit)!='hwangbo_jinak' or not unit.hp:
            continue
        if used.get(str(unit.id)):
            continue
        critical=[u for u in battle.units.values() if u.side==unit.side and u.row=='front'
                  and u.hp and u.hp/u.max_hp<=.35]
        if len(critical)>=2:
            used[str(unit.id)]=True
            battle.effect(unit,'legend_redirect',5,unit.id,notable_hook=False)
            battle.emit(f'{unit.name} · 부동명왕 발동: 후열 피해 30% 대신 수호 (5초)',
                        'buff',unit,unit,'legend_redirect')


def knockout(battle,actor,target):
    if not battle.context.get('notables'):
        return
    n=state(battle)
    if actor.side!=target.side and actor.role==1:
        namgung=living_with(battle,actor.side,'namgung_seol')
        if namgung:
            stacks=n.setdefault('namgung_stacks',{})
            side=str(actor.side)
            stacks[side]=min(10,stacks.get(side,0)+1)
            battle.emit(f'{namgung.name} · 검의 {stacks[side]}중첩: 무인형 피해 +{stacks[side]}%',
                        'buff',namgung,actor,'namgung_seol',stacks[side])
    n.setdefault('marks',{}).pop(str(target.id),None)
    n.setdefault('archer_hits',{}).pop(str(target.id),None)
    n.setdefault('warrior_hits',{}).pop(str(target.id),None)
    dots=n.setdefault('dots',[])
    poison=[d for d in dots if d['target']==target.id and d['kind']=='poison'
            and d['until']>=battle.round and d['transfers']==0]
    for d in poison:
        owner=battle.units.get(d['owner'])
        if not owner or power(battle,owner)!='dang_soyeon':
            continue
        remaining=max(0,d['until']-battle.round)
        spread=remaining//2
        if spread:
            victims=sorted((u for u in battle.units.values() if u.side==target.side
                            and u.hp and u.id!=target.id),key=lambda u:(u.hp/u.max_hp,u.id))
            for enemy in victims[:2]:
                _start_dot(battle,owner,enemy,'poison',spread,transfers=1)
            if victims:
                battle.emit(f'{owner.name} · 만독귀종: 중독 {min(2,len(victims))}명 전이',
                            'debuff',owner,target,'dang_soyeon')
    dots[:]=[d for d in dots if d['target']!=target.id]


def end_round(battle):
    if not battle.context.get('notables'):
        return
    n=state(battle)
    dots=n.setdefault('dots',[])
    for dot in tuple(dots):
        victim=battle.units.get(dot['target'])
        source=battle.units.get(dot['owner'])
        if (victim is None or source is None or victim.hp<=0
                or dot['until']<battle.round or dot['next']>battle.round):
            continue
        tick=min(victim.hp,max(1,ceil(victim.max_hp*.01)))
        # Damage over time ignores barrier but still records combat contribution.
        battle.apply_damage(source,victim,tick,dot['kind'],'damage')
        dot['next']=battle.round+1
    dots[:]=[d for d in dots if d['until']>battle.round and battle.units[d['target']].hp]


def extra_attack(battle,actor,rng):
    if not actor.hp or not battle.active(actor,'legend_speed') or rng.random()>=.15:
        return
    targets=[u for u in battle.units.values() if u.side!=actor.side and u.hp]
    if not targets:
        return
    enemy=min(targets,key=lambda u:(u.hp,u.id))
    battle.emit(f'{actor.name} · 천기삼변 추가 공격', 'buff',actor,enemy,'legend_speed')
    battle.damage(actor,enemy,.65,rng,'hit')
