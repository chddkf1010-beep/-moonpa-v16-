"""World and weekly activity resolution inherited from v13 for v15."""
from __future__ import annotations
import math, random, collections
from combat_environment import combat_context, simulated_power_bonus
from dataclasses import dataclass,field
from moonpa_growth import Development, observed_potential, observed_ability
from moonpa_names import NameRegistry, GUILD_NAMES, initial_member_hints, starting_role

TIERS={4:dict(gross=65,zone_cost=12,hall=40,sponsor=0,base_ca=80,base_lv=4,mission_gross=65,mission_cost=12,emergency=220,training_cost=3),
       3:dict(gross=100,zone_cost=15,hall=70,sponsor=40,base_ca=105,base_lv=7,mission_gross=93,mission_cost=19,emergency=350,training_cost=5),
       2:dict(gross=142,zone_cost=26,hall=110,sponsor=100,base_ca=130,base_lv=10,mission_gross=135,mission_cost=28,emergency=500,training_cost=7),
       1:dict(gross=200,zone_cost=40,hall=175,sponsor=250,base_ca=155,base_lv=13,mission_gross=215,mission_cost=40,emergency=750,training_cost=10)}
STRATS=('baseline','growth','transfer','conquest','balanced')
CAP={4:2,3:3,2:4,1:5}
AWARDS={4:1200,3:2000,2:3500,1:5000}

def clamp(x,lo,hi):return min(hi,max(lo,x))
def logistic(x):return 1/(1+math.exp(-clamp(x,-20,20)))
def xp_need(level):return 25+8*level+2*level*level

def salary(f):
    return math.ceil((5+0.0000125*f.ca**3)*(1+0.006*(f.lv-1)+0.001*max(0,observed_potential(f)-f.ca)+(0.035 if f.role in (0,4) else 0)))

@dataclass(slots=True)
class Fighter:
    fid:int;ca:float;pa:float;lv:int;age:int;role:int;curve:str;contract_end:int;wage:int=0
    xp:int=0;fatigue:float=0.0;injured:int=0;last_transfer_season:int=-1;free_since:int=-1
    development: Development | None = None
    surname: str = ''
    given_name: str = ''
    portrait_key: str = ''
    mastery: dict[str, int] = field(default_factory=dict)
    equipped: tuple[str, ...] | None = None

    @property
    def name(self):
        return self.surname + self.given_name or f"문파원 {self.fid}"

@dataclass(slots=True)
class Guild:
    gid:int;tier:int;fighters:list[Fighter];cash:float;strategy:str;renown:float=50.;score:float=0.
    last_plan:dict=field(default_factory=dict);first_reach:int=4;championships:int=0
    transfers_in:int=0;transfers_out:int=0;fa_signings:int=0;fa_releases:int=0
    missions_done:int=0;missions_won:int=0;attacks:int=0;attack_wins:int=0;defense_wins:int=0
    promoted:int=0;relegated:int=0;negative_weeks:int=0;max_negative_streak:int=0;negative_streak:int=0
    annual_best_rank:int=8;elite_born:int=0;cash_start:float=0;gold_spent_training:float=0
    name:str=''
    def wage_total(self):return sum(f.wage for f in self.fighters)
    def strength(self):
        fs=sorted(self.fighters,key=lambda f:f.ca+.12*f.lv,reverse=True)[:5]
        return sum(f.ca+.12*f.lv for f in fs)/len(fs) if fs else 0

@dataclass(slots=True)
class Zone:
    zid:int;tier:int;owner:int|None;multiplier:float;protected_until:int=0

class World:
    def __init__(self,seed,strategy):
        self.seed=seed;self.rng=random.Random(seed);self.strategy=strategy
        self.guilds={};self.zones=[];self.fa=[];self.new_fid=0;self.player=-1
        self.stats=collections.Counter();self.yearly=[];self.globalweek=0;self.player_reached_1=None
        self.names=NameRegistry(seed)
        self._init()
    def _make_fighter(self,ca,pa,lv,age,role,contract_end,curve=None,name_hints=None):
        rng=self.rng
        f=Fighter(self.new_fid,clamp(ca,20,200),clamp(max(pa,ca),0,200),int(clamp(lv,1,20)),age,role,
                  curve or rng.choices(['early','standard','late'],[.28,.49,.23])[0],contract_end)
        f.surname, f.given_name = self.names.person(**(name_hints or {}))
        f.development = Development.create(f.ca, f.pa, role, self.seed, f.fid)
        f.development.refresh(f)
        self.new_fid+=1;f.wage=salary(f);return f
    def _init(self):
        rng=self.rng
        for tier in (1,2,3,4):
            p=TIERS[tier]
            ids=[]
            for j in range(8):
                sect_name=self.names.reserve_sect(GUILD_NAMES[tier][j])
                fighters=[]
                roster_size=rng.randint(17,20)
                for k in range(roster_size):
                    ca=clamp(rng.gauss(p['base_ca'],12),30,195)
                    pa=clamp(max(ca,rng.gauss(ca+29,17)),ca,200)
                    level=clamp(round(rng.gauss(p['base_lv'],2)),1,20)
                    age=rng.randint(18,37)
                    role=starting_role(sect_name,k,rng.randrange(6))
                    contract_end=rng.randint(1,5)
                    fighters.append(self._make_fighter(
                        ca,pa,level,age,role,contract_end,
                        name_hints=initial_member_hints(sect_name,k,roster_size)))
                cost=sum(f.wage for f in fighters)+p['hall']
                personality=['baseline','growth','transfer','conquest','balanced'][j%5]
                g=Guild(len(self.guilds),tier,fighters,cost*8*rng.uniform(.9,1.25),personality,renown=rng.uniform(45,85))
                g.name=sect_name
                self.guilds[g.gid]=g;ids.append(g.gid)
            for z in range(12):
                self.zones.append(Zone(len(self.zones),tier,ids[z] if z<8 else None,rng.choice([.86,.93,1.,1.07,1.14])))
def extract_available(g):
    return [f for f in g.fighters if f.injured==0]

# Small helpers for World kept standalone to keep determinism clear.
def zone_count(w,g):return sum(z.owner==g.gid for z in w.zones)
def zone_value(z):return 7*(TIERS[z.tier]['gross']-TIERS[z.tier]['zone_cost'])*z.multiplier
def market_value(f,known_pa=True):
    pa=f.pa if known_pa else observed_potential(f)
    aged=1.10 if f.age<=24 else 1 if f.age<=32 else .78 if f.age<=37 else .52
    ca = f.ca if known_pa else observed_ability(f)
    trait_premium = .008 * sum(t.bonus for t in f.development.traits)
    runway = {'early': .90, 'standard': 1, 'late': 1.10}[f.curve]
    ceiling_premium = .004 * max(0, pa - ca) * runway
    return max(10, round(12 * f.wage * (1 + ceiling_premium + trait_premium
                                        + .004 * (f.lv - 1)) * aged / 10) * 10)

def choose_active(g,player=False):
    st=g.strategy
    def key(f):
        estimated_pa=f.pa if player else observed_potential(f)
        prospect=max(0,estimated_pa-f.ca)
        if f.injured>0:return -1000+f.ca
        if st=='growth':return f.ca+.12*f.lv+prospect*.70-(f.age>34)*10
        if st=='transfer':return f.ca+.12*f.lv+prospect*.25
        return f.ca+.12*f.lv+prospect*.12
    return sorted(g.fighters,key=key,reverse=True)[:20]

def prep_plan(w,g,week):
    rng=w.rng; p=TIERS[g.tier]; st=g.strategy
    active=choose_active(g,player=(g.gid==w.player))
    fit=[f for f in active if f.injured==0]
    owned=[z for z in w.zones if z.owner==g.gid]
    plan=dict(attack=[],defend=[],missions=[],training=[],rest=[],second=[],scout=[],emergency=[],home=None,attack_target=None,attack_won=False)
    # Each strategy produces DIFFERENT allocation, not just a different fight modifier.
    attack_probs=dict(baseline=.36,growth=.28,transfer=.48,conquest=.92,balanced=.65)
    defense_probs=dict(baseline=.70,growth=.78,transfer=.72,conquest=.38,balanced=.80)
    mission_goal=dict(baseline=2,growth=1,transfer=2,conquest=1,balanced=2)[st]
    # TUNING v12: growth-oriented clubs must earn enough to sustain 2nd-team training.
    # Apply the exact same budget rule to player and AI clubs.
    if st=='growth' and g.cash<10*(g.wage_total()+p['hall']):mission_goal=2
    cap=CAP[g.tier];myzones=zone_count(w,g)
    if owned:
        plan['home']=max(owned,key=zone_value).zid
    # Setting a five-person defense squad consumes people for the entire week.
    if owned and len(fit)>=5 and rng.random()<defense_probs[st]:
        team=sorted(fit,key=lambda f:f.ca+.12*f.lv,reverse=True)[:5]
        plan['defend']=team
        team_ids={f.fid for f in team};fit=[f for f in fit if f.fid not in team_ids]
    targetable=[z for z in w.zones if z.tier==g.tier and z.owner!=g.gid and z.protected_until<=w.globalweek]
    if targetable and len(fit)>=5+(6 if mission_goal==2 and w.conservative and st=='growth' else 0) and rng.random()<attack_probs[st]:
        # A player competing for promotion prioritizes holders; risk-averse mode prioritizes empty land.
        unowned=[z for z in targetable if z.owner is None]
        if st in ('baseline','growth') and unowned and rng.random()<.75:
            z=rng.choice(unowned)
        elif st=='conquest':
            z=max(targetable,key=lambda z:(0 if z.owner is None else 1)+zone_value(z)/2000+rng.random()*.6)
        else:
            z=rng.choice(targetable)
        # If already at zone cap, successful attack forfeits lowest-value zone (same as replacement slot).
        plan['attack_target']=z.zid
        team=sorted(fit,key=lambda f:f.ca+.12*f.lv,reverse=True)[:5]
        plan['attack']=team
        team_ids={f.fid for f in team};fit=[f for f in fit if f.fid not in team_ids]
    for m in range(mission_goal):
        if len(fit)<3:break
        # Growth strategy protects its most promising trainees; cash-focused sends best available.
        if st=='growth':
            members=sorted(fit,key=lambda f:f.ca+.12*f.lv-.4*((f.pa if g.gid==w.player else observed_potential(f))-f.ca),reverse=True)[:3]
        else: members=sorted(fit,key=lambda f:f.ca+.12*f.lv,reverse=True)[:3]
        plan['missions'].append(members)
        member_ids={f.fid for f in members};fit=[f for f in fit if f.fid not in member_ids]
    # A no-zone livelihood mission consumes five distinct weekly activity slots.
    if not owned and len(fit)>=5:
        plan['emergency']=fit[:5]
        fit=fit[5:]
    # Everyone else either trains or rests; injured count as resting and don't use an additional slot.
    for f in fit:
        if f.fatigue>=73 and len(fit)+len(plan['defend'])+len(plan['attack'])+3*len(plan['missions'])+len(plan['emergency'])-len(plan['rest'])>15:plan['rest'].append(f)
        else:plan['training'].append(f)
    active_ids={f.fid for f in active};plan['second']=[f for f in g.fighters if f.fid not in active_ids][:10]
    # Every f is assigned to at most one activity, except injured who are automatically resting.
    scheduled=[f.fid for k in ('attack','defend','training','rest','emergency') for f in plan[k]]
    for team in plan['missions']:scheduled += [f.fid for f in team]
    assert len(scheduled)==len(set(scheduled)), 'Double booking'
    assert len(scheduled)<=20
    return plan

def team_power(team,enemy_team,mode):
    if not team:return 0
    roles={f.role for f in team};role_bonus=(3.0 if 0 in roles else 0)+(2.5 if 4 in roles else 0)+(1.5 if 3 in roles else 0)
    # Assassin (5) helps vs mage/healer (3,4). Tank (0) partially counters.
    if enemy_team:
        enemy_roles={x.role for x in enemy_team}
        if 5 in roles and ({3,4}&enemy_roles):role_bonus+=3.5
        if 5 in roles and 0 in enemy_roles:role_bonus-=1.5
    base=sum(f.ca+.12*f.lv-0.11*f.fatigue for f in team)/len(team)
    return base+role_bonus+(1.5 if mode=='defense' else 0)

def attempt_attacks(w,plans,week,*,incidents=None):
    if week==52:return {}
    rng=w.rng;changes={};attempts=[]
    for gid,pl in plans.items():
        if pl['attack'] and pl['attack_target'] is not None:
            attempts.append((rng.random(),gid,pl['attack_target']))
    attempts.sort()
    used_owners=set();used_zones=set();fought=[]
    for _,gid,zid in attempts:
        a=w.guilds[gid];z=w.zones[zid]
        if z.tier!=a.tier or z.protected_until>w.globalweek or z.owner==gid or zid in used_zones:continue
        owner=z.owner
        if owner is not None and owner in used_owners:continue
        used_zones.add(zid)
        if owner is not None:used_owners.add(owner)
        d=w.guilds.get(owner)
        attack_team=plans[gid]['attack']
        defend_team=plans[owner]['defend'] if owner is not None and plans[owner]['home']==zid else []
        attack_power=team_power(attack_team,defend_team,'attack')
        if d:
            # Undeployed basic defense force is much weaker, with separately priced garrison.
            defense_power=team_power(defend_team,attack_team,'defense') if defend_team else d.strength()-30
        else:defense_power=TIERS[z.tier]['base_ca']-28
        # Keep season-0 prehistory unchanged: founder identities, roles and portraits
        # are fixed by the established seed before the playable campaign begins.
        season=getattr(w,'season_active',0)
        if season is not None and season >= 1:
            environment=combat_context(w.seed,season,zid)
            attack_power+=simulated_power_bonus(environment,attack_team,0)
            defense_power+=simulated_power_bonus(environment,defend_team,1)
        p=clamp(logistic((attack_power-defense_power)/16),.08,.92)
        win=rng.random()<p
        a.attacks+=1;w.stats['battles']+=1
        if win:
            if zone_count(w,a)>=CAP[a.tier]:
                owned=[q for q in w.zones if q.owner==gid]
                if not owned:continue
                to_release=min(owned,key=zone_value)
                changes[to_release.zid]=(gid,None)
            changes[zid]=(owner,gid)
            z.protected_until=w.globalweek+2
            a.attack_wins+=1;plans[gid]['attack_won']=True;w.stats['captures']+=1
            a.score+=4
        elif d:
            d.defense_wins+=1;d.score+=2
        if incidents is not None:
            incidents.append(dict(attacker=gid, defender=owner, zone=zid, won=win))
        fought.append((gid,owner,attack_team,defend_team,win))
        # Weekly fights cause fatigue and small injury risk, even though combat is a proxy.
        for team in (attack_team,defend_team):
            for f in team:
                f.fatigue=clamp(f.fatigue+12,0,100)
                if rng.random()<.007:f.injured=max(f.injured,1)
    for zid,(_,new_owner) in changes.items():w.zones[zid].owner=new_owner
    return changes

def advance_experience(f,xp):
    f.xp+=int(xp)
    while f.lv<20 and f.xp>=xp_need(f.lv):
        f.xp-=xp_need(f.lv);f.lv+=1

def age_factor(f):
    a=f.age
    if f.curve=='early':return 1.4 if a<=22 else 1.18 if a<=26 else .70 if a<=30 else .12
    if f.curve=='standard':return 1.1 if a<=24 else 1.16 if a<=29 else .85 if a<=34 else .28
    return .72 if a<=24 else .88 if a<=29 else 1.12 if a<=34 else 1.13 if a<=39 else .30

def generate_rookies(w,season,count=46):
    rng=w.rng
    # Supply exists globally across 4 leagues; rare high potential is not limited to 1st division.
    for _ in range(count):
        ca=clamp(rng.gauss(67,16),25,125)
        pa=clamp(max(ca,rng.gauss(130,30)),ca,200)
        # A small number of exceptional rookie prospects keeps 4th-tier discovery meaningful.
        if rng.random()<.08:pa=clamp(max(pa,rng.gauss(183,9)),ca,200)
        level = rng.choice([1,1,2,2,3,4])
        age = rng.randint(17,22)
        # Newly generated prospects start below their ceiling. Older rookies
        # can enter with a larger share of their potential already developed.
        maturity_limit = .72 + .03 * (age-17)
        ca = max(20, min(ca, pa*maturity_limit))
        f=w._make_fighter(ca,pa,level,age,rng.randrange(6),season+rng.randint(1,5))
        f.development.rookie = True
        f.free_since=season
        w.fa.append(f)

