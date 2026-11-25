"""End-of-season division cups. Each division plays 4+2+1 fixtures."""
import math
WEEKS=(49,50,51)
LABELS={49:'8강',50:'4강',51:'결승'}

def current(c):
    t=getattr(c.world,'season_tournament',None)
    return t if t and t['season']==c.season else None

def window(c):
    return c.interactive and (c.week==49 or (c.week in (50,51) and current(c) is not None))

def begin(c):
    existing=current(c)
    if existing is not None:return existing
    if c.week!=49:raise ValueError('무투대회는 49주차부터 시작합니다.')
    seeds={}
    for tier in (1,2,3,4):
        ranked=c._league_ranked(c.world,tier)
        seeds[tier]=[ranked[i].gid for i in (0,7,3,4,1,6,2,5)]
    t=dict(season=c.season,seeds=seeds,matches=[],points={g:0 for g in c.world.guilds},final=None)
    c.world.season_tournament=t
    return t

def fixtures(t,week):
    if week not in WEEKS:return []
    out=[]
    for tier in (1,2,3,4):
        if week==49:ids=t['seeds'][tier]
        else:
            rows=sorted((r for r in t['matches'] if r['tier']==tier and r['week']==week-1),key=lambda r:r['slot'])
            if len(rows)!={50:4,51:2}[week]:raise ValueError('이전 무투대회 결과가 누락되었습니다.')
            ids=[r['winner'] for r in rows]
        out.extend(dict(tier=tier,week=week,slot=i//2,sides=[ids[i],ids[i+1]]) for i in range(0,len(ids),2))
    return out

def record(c,fixture,winner,method):
    t=current(c);a,b=fixture['sides']
    if winner not in (a,b) or any((r['week'],r['tier'],r['slot'])==(fixture['week'],fixture['tier'],fixture['slot']) for r in t['matches']):
        raise ValueError('이미 정산했거나 올바르지 않은 무투대회 결과입니다.')
    t['matches'].append(dict(fixture,winner=winner,method=method,
        names=[c.world.guilds[i].name for i in (a,b)]))
    t['points'][winner]+=100

def finalize(c):
    """Normalize the existing regular-season score only once, after week 52."""
    t=current(c)
    if not t or t['final'] is not None or len(t['matches'])!=28:return
    result={}
    for tier in (1,2,3,4):
        members=[c.world.guilds[i] for i in t['seeds'][tier]]
        maximum=max(0,*[g.score for g in members])
        for g in members:
            raw=g.score
            regular=round(700*max(0,raw)/maximum,2) if maximum else 0
            cup=t['points'][g.gid]
            g.score=round(regular+cup,2)
            result[g.gid]=dict(tier=tier,raw=raw,regular=regular,cup=cup,total=g.score,name=g.name)
    t['final']=result

def overview(c):
    t=getattr(c.world,'season_tournament',None)
    if not t:return dict(window=window(c),season=None,matches=[],points={},final=None)
    return dict(t,window=window(c))

def valid(t,w):
    if type(t) is not dict or set(t)!={'season','seeds','matches','points','final'}:return False
    if type(t['season']) is not int or not 1<=t['season']<=10000:return False
    if type(t['seeds']) is not dict or set(t['seeds'])!={1,2,3,4}:return False
    ids=[]
    for v in t['seeds'].values():
        if type(v) is not list or len(v)!=8 or any(type(i) is not int for i in v):return False
        ids.extend(v)
    if len(set(ids))!=32 or set(ids)!=set(w.guilds):return False
    if type(t['matches']) is not list or len(t['matches'])>28:return False
    seen=set();points={i:0 for i in ids}
    for r in t['matches']:
        if type(r) is not dict or set(r)!={'tier','week','slot','sides','winner','method','names'}:return False
        if type(r['tier']) is not int or r['tier'] not in (1,2,3,4) or type(r['week']) is not int or r['week'] not in WEEKS or type(r['slot']) is not int or not 0<=r['slot']<{49:4,50:2,51:1}[r['week']]:return False
        k=(r['week'],r['tier'],r['slot'])
        if k in seen:return False
        seen.add(k)
        if type(r['sides']) is not list or len(r['sides'])!=2 or any(type(i) is not int or i not in t['seeds'][r['tier']] for i in r['sides']) or r['sides'][0]==r['sides'][1] or r['winner'] not in r['sides']:return False
        if r['method'] not in ('arena','forfeit','power') or type(r['names']) is not list or len(r['names'])!=2 or any(type(n) is not str for n in r['names']):return False
        points[r['winner']]+=100
    if t['points']!=points or any(p>300 for p in points.values()):return False
    # Every recorded fixture must agree with its bracket ancestry.
    for week in WEEKS:
        recorded=[r for r in t['matches'] if r['week']==week]
        if not recorded:continue
        try:expected={(r['tier'],r['slot']):r['sides'] for r in fixtures(t,week)}
        except ValueError:return False
        if any(expected.get((r['tier'],r['slot']))!=r['sides'] for r in recorded):return False
    f=t['final']
    if f is None:return True
    if len(seen)!=28 or type(f) is not dict or set(f)!=set(ids):return False
    for gid,r in f.items():
        if type(r) is not dict or set(r)!={'tier','raw','regular','cup','total','name'}:return False
        if r['tier'] not in (1,2,3,4) or gid not in t['seeds'][r['tier']] or r['cup']!=points[gid] or type(r['name']) is not str:return False
        if any(type(r[k]) not in (int,float) or not math.isfinite(r[k]) for k in ('raw','regular','total')) or not 0<=r['regular']<=700 or r['total']!=round(r['regular']+r['cup'],2):return False
    return True
