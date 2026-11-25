"""v40 phase 2: player-controlled incoming transfers, adapted from v39.

No world RNG consumed; the original browser engine owns names, contracts,
ledger, scouting and actual transfers. Never commit a counteroffer implicitly.
"""
import math
import moonpa_market as market
from moonpa_growth import observed_ability, observed_potential

MAX_PRICE=10_000_000
MAX_OPEN=6
STATUSES={'open','accepted','rejected','expired','withdrawn'}
REPLIES={'offered','agreed','counter','refused'}

def fresh():
    return dict(listings={},offers={},seq=0,cooldown={},last_clock=0)

def integer(v,lo=0,hi=MAX_PRICE):
    return type(v) is int and lo<=v<=hi

def valid_state(data):
    if type(data) is not dict or set(data)!=set(fresh()):return False
    if not integer(data['seq']) or not integer(data['last_clock']):return False
    listings,offers,cooldown=data['listings'],data['offers'],data['cooldown']
    if type(listings) is not dict or len(listings)>32 or any(not integer(k) or not integer(v) for k,v in listings.items()):return False
    if type(cooldown) is not dict or len(cooldown)>512 or any(type(k) is not str or len(k)>30 or not integer(v) for k,v in cooldown.items()):return False
    if type(offers) is not dict or len(offers)>46:return False
    for k,r in offers.items():
        if not integer(k,1,data['seq']) or type(r) is not dict or set(r)!={'id','buyer','fighter','fighter_name','fee','exchange','season','expires','attempts','revision','status','reply','listed'}:return False
        if r['id']!=k or not integer(r['buyer']) or not integer(r['fighter']) or not integer(r['fee']):return False
        if type(r['fighter_name']) is not str or len(r['fighter_name'])>100:return False
        if not valid_exchange(r['exchange']) or not integer(r['season'],1,10000) or not integer(r['expires']) or not integer(r['attempts'],0,3) or not integer(r['revision'],1,4):return False
        if type(r['status']) is not str or r['status'] not in STATUSES or type(r['reply']) is not str or r['reply'] not in REPLIES or type(r['listed']) is not bool:return False
    return sum(r['status']=='open' for r in offers.values())<=MAX_OPEN

def valid_exchange(ids):
    return type(ids) is list and len(ids)<=3 and all(integer(i) for i in ids) and len(set(ids))==len(ids)

def find(g,fid):
    return next((f for f in g.fighters if f.fid==fid),None)

def available(c,g,f):
    return f is not None and not f.injured and f.last_transfer_season!=c.season and f.contract_end>=c.season and f.fid not in c.world.away(g.gid)

def core(g,f):
    return f in sorted(g.fighters,key=lambda x:(-x.ca,x.fid))[:5]

def buyer_room(c,buyer,target,swap):
    import moonpa_economy_v15_1 as economy
    w=c.world
    if buyer is c.guild or not available(c,c.guild,target) or any(not available(c,buyer,f) or core(buyer,f) for f in swap):return -1
    if not 15<=len(buyer.fighters)+1-len(swap)<=30 or not 15<=len(c.guild.fighters)-1+len(swap)<=30:return -1
    if w.debts[buyer.gid].total():return -1
    for f in swap:
        if f.role!=target.role and not any(x.role==f.role and x not in swap for x in buyer.fighters):return -1
    wages=buyer.wage_total()+target.wage-sum(f.wage for f in swap)
    if wages>max(buyer.wage_total(),economy.ai_payroll_budget(w,buyer)):return -1
    fixed=economy.fixed_weekly_cost(w,buyer)+target.wage-sum(f.wage for f in swap)
    value=market.buyer_limit(w,buyer,target,c.season)-sum(market.estimate(w,f,buyer,c.season) for f in swap)
    return min(int(buyer.cash-4*fixed),value,MAX_PRICE)

def seller_ok(c,target,swap,fee):
    import moonpa_economy_v15_1 as economy
    g=c.guild; w=c.world
    if not 15<=len(g.fighters)-1+len(swap)<=30:return False
    old=economy.fixed_weekly_cost(w,g); new=old-target.wage+sum(f.wage for f in swap)
    if new<=old:return True
    forecast=economy.passive_week_projection(w,g)
    return not w.debts[g.gid].total() and g.cash+fee>=4*new and new<=max(old,forecast['income']-forecast['garrison'])

def credit(c,target,swap):
    return market.seller_credit_for(c.world,c.guild,target,swap,c.season)

def package(c,buyer,target,ask):
    peers=sorted((f.ca for f in buyer.fighters if f.role==target.role),reverse=True)
    if len(peers)>=2 and observed_ability(target)<=peers[1]*1.05:return None
    eligible=[f for f in buyer.fighters if available(c,buyer,f) and not core(buyer,f)]
    eligible.sort(key=lambda f:(-sum(x.role==f.role for x in buyer.fighters),-f.wage,f.fid))
    groups=[[]]+[[f] for f in eligible[:6]]+[eligible[:n] for n in (2,3) if len(eligible)>=n]
    best=None
    for group in groups:
        room=buyer_room(c,buyer,target,group)
        if room<0:continue
        value=credit(c,target,group)
        fee=min(room,max(0,ask-value))
        if fee+value<max(20,ask*.70) or not seller_ok(c,target,group,fee):continue
        rank=(int(not group and fee>=ask),min((fee+value)/max(1,ask),1),fee,-len(group))
        if best is None or rank>best[0]:best=(rank,fee,[f.fid for f in group])
    return best

def active(c,r):
    if r['status']!='open' or r['season']!=c.season or c.clock>=r['expires']:return False
    buyer=c.world.guilds.get(r['buyer']); target=find(c.guild,r['fighter'])
    if buyer is None or not available(c,c.guild,target):return False
    swap=[find(buyer,i) for i in r['exchange']]
    return all(f is not None for f in swap) and r['fee']<=buyer_room(c,buyer,target,swap) and seller_ok(c,target,swap,r['fee'])

def prune(c):
    data=c.incoming_market
    for r in data['offers'].values():
        if r['status']=='open' and not active(c,r):r['status']='expired'
    data['listings']={i:price for i,price in data['listings'].items() if (f:=find(c.guild,i)) is not None and f.last_transfer_season!=c.season and f.contract_end>=c.season}
    closed=[k for k,r in data['offers'].items() if r['status']!='open']
    for k in closed[:-40]:del data['offers'][k]
    data['cooldown']={k:v for k,v in data['cooldown'].items() if v>c.clock}

def generate(c):
    """One bid per completed week; no generation from read-only rendering."""
    if c.world.player_bankrupted:return
    data=c.incoming_market
    if c.week<=1 or data['last_clock']>=c.clock:return
    data['last_clock']=c.clock
    prune(c)
    if sum(r['status']=='open' for r in data['offers'].values())>=MAX_OPEN:return
    listed=[f for f in c.guild.fighters if f.fid in data['listings']]
    others=sorted((f for f in c.guild.fighters if f.fid not in data['listings']),key=lambda f:(-f.ca,f.fid))[:10] if c.week%2==0 else []
    existing={(r['buyer'],r['fighter']) for r in data['offers'].values() if r['status']=='open'}
    best=None
    for target in listed+others:
        if not available(c,c.guild,target):continue
        islisted=target.fid in data['listings']
        ask=data['listings'].get(target.fid,round(market.estimate(c.world,target,c.guild,c.season)*(1.4 if core(c.guild,target) else 1.12)))
        for buyer in sorted(c.world.guilds.values(),key=lambda g:g.gid):
            key=f'{buyer.gid}:{target.fid}'
            if buyer is c.guild or abs(buyer.tier-c.guild.tier)>1 or (buyer.gid,target.fid) in existing or data['cooldown'].get(key,0)>c.clock:continue
            result=package(c,buyer,target,ask)
            if result is None:continue
            rank,fee,ids=result
            score=(int(islisted),*rank,-buyer.gid,-target.fid)
            if best is None or score>best[0]:best=(score,buyer,target,fee,ids)
    if best is not None:
        _,buyer,target,fee,ids=best
        data['seq']+=1; bid=data['seq']
        data['offers'][bid]=dict(id=bid,buyer=buyer.gid,fighter=target.fid,fighter_name=target.name,fee=fee,exchange=ids,season=c.season,expires=c.clock+3,attempts=0,revision=1,status='open',reply='offered',listed=target.fid in data['listings'])
        data['cooldown'][f'{buyer.gid}:{target.fid}']=c.clock+6

def guard(c,season,week):
    if type(season) is not int or type(week) is not int or (season,week)!=(c.season,c.week) or c.market_closed() or c.phase!='ready':
        raise ValueError('현재 운영 단계 또는 주차를 다시 확인하세요.')

def listing(c,season,week,fid,price):
    guard(c,season,week)
    if not integer(fid) or (price is not None and not integer(price)):raise ValueError('희망 이적금은 0~10000000냥 정수입니다.')
    data=c.incoming_market
    if price is None:
        if fid not in data['listings']:raise ValueError('등록된 매물이 아닙니다.')
        del data['listings'][fid]
        for r in data['offers'].values():
            if r['fighter']==fid and r['listed'] and r['status']=='open':r['status']='withdrawn'
        return
    if not available(c,c.guild,find(c.guild,fid)):raise ValueError('소속·부상·계약·이적 제한을 확인하세요.')
    data['listings'][fid]=price

def respond(c,season,week,bid,revision,choice,fee=None,exchange=None):
    guard(c,season,week)
    r=c.incoming_market['offers'].get(bid) if integer(bid,1) else None
    if r is None or not integer(revision,1,4) or revision!=r['revision'] or not active(c,r):raise ValueError('제안이 만료되었거나 조건이 변경되었습니다.')
    if choice=='reject':r['status']='rejected';return
    buyer=c.world.guilds[r['buyer']];target=find(c.guild,r['fighter'])
    if choice=='accept':fee,exchange=r['fee'],r['exchange']
    elif choice=='counter':
        if r['attempts']>=3:raise ValueError('역제안은 최대 3회입니다.')
        if not integer(fee) or not valid_exchange(exchange):raise ValueError('이적금과 교환 인원을 확인하세요.')
    else:raise ValueError('지원하지 않는 응답입니다.')
    swap=[find(buyer,i) for i in exchange]
    if any(f is None for f in swap):raise ValueError('교환 인원의 소속을 확인하세요.')
    room=buyer_room(c,buyer,target,swap)
    if choice=='counter':
        if not seller_ok(c,target,swap,fee) or fee+credit(c,target,swap)<20:raise ValueError('정원·급여·거래 가치를 확인하세요.')
        r['attempts']+=1;r['revision']+=1
        if room>=fee:r.update(fee=fee,exchange=list(exchange),reply='agreed')
        elif room>=0 and room+credit(c,target,swap)>=20 and seller_ok(c,target,swap,room):r.update(fee=room,exchange=list(exchange),reply='counter')
        else:
            r['reply']='refused'
            if r['attempts']>=3:r['status']='rejected'
        return
    if fee>room or fee+credit(c,target,swap)<20 or not seller_ok(c,target,swap,fee):raise ValueError('현재 양측 자금·정원·계약 조건을 확인하세요.')
    w=c.world
    w.season_active,w.week_active,w.globalweek=c.season,c.week,c.clock
    if not w.trade(c.guild,buyer,target,fee,swap,c.season):raise ValueError('이적 처리 실패')
    import moonpa_growth_dashboard as growth
    for f in swap:growth.record_join(w,f,c.season,c.week,c.guild.gid,'교환 영입')
    w.stats['market_deals']+=1
    w.stats['player_planned_sales']+=int(r['listed'])
    w.money.reconcile()
    r['status']='accepted'
    c.incoming_market['listings'].pop(target.fid,None)
    prune(c)

def overview(c):
    data=c.incoming_market
    rows=[]
    for r in reversed(list(data['offers'].values())):
        buyer=c.world.guilds.get(r['buyer'])
        row=dict(r)
        row['status']='expired' if r['status']=='open' and not active(c,r) else r['status']
        row['buyer_name']=buyer.name if buyer else '해산 문파'
        row['remaining']=max(0,r['expires']-c.clock)
        row['exchange_names']=[(find(buyer,i).name if buyer and find(buyer,i) else f'#{i}') for i in r['exchange']]
        row['candidates']=[dict(id=f.fid,name=f.name,ca=round(observed_ability(f)),pa=round(observed_potential(f)),wage=f.wage) for f in buyer.fighters if available(c,buyer,f) and not core(buyer,f)] if buyer and row['status']=='open' else []
        rows.append(row)
    return dict(listings={str(i):p for i,p in data['listings'].items() if find(c.guild,i) is not None},offers=rows,blocked=c.market_closed() or c.phase!='ready')
