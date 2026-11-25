"""Persistent, player-only cash journal; independent of temporary monthly capture."""
RECENT_LIMIT=120
FLOWS={'source','sink','transfer_in','transfer_out'}

def start(world,guild,season,week,origin):
    cash=0 if world.player_bankrupted else guild.cash
    world.player_journal=dict(guild=guild.gid,start_season=season,start_week=week,
        origin=origin,opening=cash,closing=cash,income=0,expenses=0,count=0,
        seasons={},recent=[],closed=bool(world.player_bankrupted))

def record(world,row):
    j=getattr(world,'player_journal',None)
    if j is None or j['closed'] or row['guild']!=j['guild']:return
    # Accounting clock may still be season 0 immediately after founding.
    season=max(j['start_season'],row['season'])
    week=row['week'] if row['season']==season else j['start_week']
    week=max(1,min(52,week))
    amount=row['amount']
    if not amount:return
    p=j['seasons'].setdefault(season,dict(opening=row['before'],closing=row['before'],
        income=0,expenses=0,count=0,income_by={},expense_by={}))
    direction='income' if amount>0 else 'expenses'
    categories='income_by' if amount>0 else 'expense_by'
    value=abs(amount)
    p[direction]+=value
    p[categories][row['category']]=p[categories].get(row['category'],0)+value
    p['closing']=row['after'];p['count']+=1
    j[direction]+=value;j['closing']=row['after'];j['count']+=1
    j['recent'].append(dict(row,season=season,week=week,seq=j['count']))
    if len(j['recent'])>RECENT_LIMIT:del j['recent'][:-RECENT_LIMIT]

def close(world,guild):
    j=getattr(world,'player_journal',None)
    if j is not None and guild.gid==j['guild']:j['closed']=True

def cash_for(world,guild,j):
    return 0 if j['closed'] else guild.cash

def view(world,guild,season,week):
    j=getattr(world,'player_journal',None)
    if j is None:return None
    actual=cash_for(world,guild,j)
    expected=j['opening']+j['income']-j['expenses']
    periods=[dict(p,season=key) for key,p in sorted(j['seasons'].items(),reverse=True)]
    if not j['closed'] and season not in j['seasons']:
        periods.insert(0,dict(season=season,opening=actual,closing=actual,income=0,expenses=0,count=0,income_by={},expense_by={}))
    return dict(j,actual=actual,expected=expected,difference=actual-expected,
                periods=periods,recent=list(reversed(j['recent'])))

def nonnegative(v):
    return type(v) is int and 0<=v<=10**15

def category_map(d):
    return type(d) is dict and len(d)<=256 and all(type(k) is str and 0<len(k)<=100 and nonnegative(v) for k,v in d.items())

def validate(world,guild,j):
    """Validate the persisted cash equation, periods and recent transaction chain."""
    if type(j) is not dict or set(j)!={'guild','start_season','start_week','origin','opening','closing','income','expenses','count','seasons','recent','closed'}:return False
    if j['guild']!=guild.gid or type(j['guild']) is not int or type(j['closed']) is not bool:return False
    if j['origin'] not in ('founding','migration') or type(j['start_season']) is not int or not 1<=j['start_season']<=10000 or type(j['start_week']) is not int or not 1<=j['start_week']<=51:return False
    if not all(nonnegative(j[k]) for k in ('opening','closing','income','expenses','count')):return False
    if j['opening']+j['income']-j['expenses']!=j['closing'] or j['closing']!=cash_for(world,guild,j):return False
    if j['closed']!=bool(world.player_bankrupted):return False
    periods=j['seasons'];recent=j['recent']
    if type(periods) is not dict or len(periods)>10000 or type(recent) is not list or len(recent)!=min(j['count'],RECENT_LIMIT):return False
    balance=j['opening'];inc=out=count=0
    for key,p in sorted(periods.items()):
        if type(key) is not int or not j['start_season']<=key<=10000 or type(p) is not dict or set(p)!={'opening','closing','income','expenses','count','income_by','expense_by'}:return False
        if not all(nonnegative(p[k]) for k in ('opening','closing','income','expenses','count')) or p['count']==0:return False
        if not category_map(p['income_by']) or not category_map(p['expense_by']):return False
        if p['opening']!=balance or p['opening']+p['income']-p['expenses']!=p['closing']:return False
        if sum(p['income_by'].values())!=p['income'] or sum(p['expense_by'].values())!=p['expenses']:return False
        balance=p['closing'];inc+=p['income'];out+=p['expenses'];count+=p['count']
    if (balance,inc,out,count)!=(j['closing'],j['income'],j['expenses'],j['count']):return False
    previous=None
    for seq,row in enumerate(recent,j['count']-len(recent)+1):
        if type(row) is not dict or set(row)!={'season','week','global_week','guild','category','flow','amount','before','after','counterparty','transfer_id','seq'}:return False
        if row['seq']!=seq or row['guild']!=j['guild'] or row['season'] not in periods or not nonnegative(row['global_week']) or type(row['week']) is not int or not 1<=row['week']<=52:return False
        if type(row['category']) is not str or not 0<len(row['category'])<=100 or row['flow'] not in FLOWS:return False
        if type(row['amount']) is not int or not row['amount'] or not nonnegative(row['before']) or not nonnegative(row['after']):return False
        if (row['amount']>0)!=(row['flow'] in ('source','transfer_in')):return False
        if row['before']+row['amount']!=row['after'] or (previous is not None and row['before']!=previous):return False
        if row['flow'].startswith('transfer'):
            if type(row['counterparty']) is not int or row['counterparty']==j['guild'] or not nonnegative(row['transfer_id']):return False
        elif row['counterparty'] is not None or row['transfer_id'] is not None:return False
        previous=row['after']
    if recent and (previous!=j['closing'] or (j['count']<=RECENT_LIMIT and recent[0]['before']!=j['opening'])):return False
    return True
