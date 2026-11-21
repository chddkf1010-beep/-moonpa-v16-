"""문파 키우기 v15.1: 32-sect, 10-season financial integrity simulator.

Builds on the explicitly simplified v13 strategy simulator but replaces all
cash-mutating operations and seasonal FA with recorded, integer transactions.
This is NOT the 20-round playable combat engine or a player-facing GUI.

Run:
    python moonpa_economy_v15_1.py --seeds 5 --jobs 2 --prefix /mnt/data/moonpa_v14
    python moonpa_economy_v15_1.py --seeds 1 --jobs 1 --capture-ledger

The pre-history simulation is one AI season (season 0); 10 playable seasons follow.
"""
from __future__ import annotations
import argparse, collections, csv, json, math, random, statistics, time
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import moonpa_world_v15 as old
import moonpa_market as market
from dataclasses import asdict
from moonpa_growth import ATTRIBUTES, ROLES, PEAK_AGE, available_skill_slots, observed_potential
from moonpa_tracking import Ownership, allocate_cash

TIERS=old.TIERS; STRATS=old.STRATS; CAP=old.CAP; AWARDS=old.AWARDS
CASH_RESERVE_WEEKS=4
BANKRUPTCY_WEEKS=8          # provisional balancing value, not player-confirmed
OVERFLOW_WEEKS=2            # player-confirmed
MAX_ROSTER=30
MAX_TEMP_ROSTER=32
REGULAR_ACTIVE=20
MAX_SECOND=10
GRADES=((180,'S'),(160,'A'),(140,'B'),(120,'C'),(100,'D'),(0,'E'))
GRADE_CENTER={'S':190,'A':170,'B':150,'C':130,'D':110,'E':60}
DAYS_PER_WEEK=7


def pa_grade(pa):
    return next(label for threshold,label in GRADES if pa>=threshold)


def observed_pa(f,viewer_is_player=False):
    return f.pa if viewer_is_player else observed_potential(f)


@dataclass
class Debt:
    wages:int=0
    operations:int=0
    severance:int=0
    unpaid_weeks:int=0
    ever_unpaid_weeks:int=0
    max_unpaid_weeks:int=0
    state:str='healthy'
    overflow_first_week:int|None=None
    liquidations:int=0
    def total(self):return self.wages+self.operations+self.severance


class Ledger:
    """All cash operations recorded. Source/sink modify world money; transfers do not.

    Insufficient balances cannot be debited. Mandatory unpaid bills accrue in
    debt ledgers as liabilities, not fictitious negative cash.
    """
    def __init__(self,world,capture=False):
        self.world=world
        self.capture=capture
        self.entries=[]
        self.stats=collections.Counter()
        self.categories=collections.Counter()
        self.by_season=collections.defaultdict(collections.Counter)
        self.opening=sum(g.cash for g in world.guilds.values())
        self.source=0;self.sink=0;self.transfer_in=0;self.transfer_out=0
        self.transactions=0;self.accrued=collections.Counter()
        self.transfer_id=0
    def _time(self):
        t=self.world.globalweek
        # Prehistory uses season=0; main game starts with week=1 in season=1.
        season=max(0,(t-1)//52+1) if t>=1 else 0
        if getattr(self.world,'season_active',None) is not None:season=self.world.season_active
        week=getattr(self.world,'week_active',0)
        return season,week,t
    def _record(self,g,category,delta,flow,counterparty=None,transfer_id=None):
        assert isinstance(delta,int) and g.cash+delta>=0,(g.gid,category,g.cash,delta)
        before=g.cash;g.cash+=delta
        season,week,t=self._time()
        self.transactions+=1
        self.categories[category]+=abs(delta)
        self.by_season[season][category]+=abs(delta)
        if flow=='source':
            assert delta>=0;self.source+=delta;self.stats['sources']+=delta;self.by_season[season]['total_source']+=delta
        elif flow=='sink':
            assert delta<=0;self.sink-=delta;self.stats['sinks']-=delta;self.by_season[season]['total_sink']-=delta
        elif flow=='transfer_in':
            assert delta>=0;self.transfer_in+=delta;self.stats['transfers_received']+=delta
            self.by_season[season]['transfer_in']+=delta
        elif flow=='transfer_out':
            assert delta<=0;self.transfer_out-=delta;self.stats['transfers_paid']-=delta
            self.by_season[season]['transfer_out']-=delta
        else:raise ValueError(flow)
        if self.capture:
            self.entries.append(dict(season=season,week=week,global_week=t,guild=g.gid,
                 category=category,flow=flow,amount=delta,before=before,after=g.cash,
                 counterparty=counterparty,transfer_id=transfer_id))
    def credit(self,g,amount,category):
        amount=int(round(amount));assert amount>=0
        if amount:self._record(g,category,amount,'source')
        return amount
    def spend(self,g,amount,category,partial=False):
        amount=int(round(amount));assert amount>=0
        paid=min(g.cash,amount) if partial else (amount if g.cash>=amount else 0)
        if paid:self._record(g,category,-paid,'sink')
        return paid
    def move(self,payer,receiver,amount,category='transfer_fee'):
        amount=int(round(amount));assert amount>=0 and payer.gid!=receiver.gid
        if payer.cash<amount:return False
        self.transfer_id+=1
        tx=self.transfer_id
        if amount:
            self._record(payer,category,-amount,'transfer_out',receiver.gid,tx)
            self._record(receiver,category,amount,'transfer_in',payer.gid,tx)
        return True
    def obligation(self,g,kind,amount):
        amount=int(round(amount));assert amount>=0
        if amount:
            d=self.world.debts[g.gid]
            setattr(d,kind,getattr(d,kind)+amount)
            self.accrued[kind]+=amount
            self.stats['liabilities_accrued']+=amount
    def reconcile(self):
        world_total=sum(g.cash for g in self.world.guilds.values())
        delta=world_total-self.opening
        expected=self.source-self.sink+self.transfer_in-self.transfer_out
        assert self.transfer_in==self.transfer_out, ('nonzero transfer supply',self.transfer_in,self.transfer_out)
        assert delta==expected,('cash imbalance',delta,expected)
        assert all(isinstance(g.cash,int) and g.cash>=0 for g in self.world.guilds.values())
        return delta


class World15(old.World):
    def __init__(self,seed,strategy,capture_ledger=False,conservative=True):
        self.conservative = conservative
        super().__init__(seed,strategy)
        self.mentors = {}
        self.spells = {}
        self.closed_spells = []
        self.player_snapshots = []
        self.player_best_division = 4
        self.player_titles = 0
        for g in self.guilds.values():g.cash=int(round(g.cash))
        self.debts={gid:Debt() for gid in self.guilds}
        self.season_active=0
        self.week_active=0
        self.globalweek=0
        self.player_id=-1
        self.player_bankrupted=False
        self.player_bankrupt_season=None
        self.capture_ledger=capture_ledger
        self.money=Ledger(self,capture_ledger)
        self.roster_overflow_events=0
        self.roster_auto_releases=0
        self.accrued_unpaid=0
        self.bankruptcies=0
        self.season_data=[]
        self.unemployment_exit=0
        self.freeagent_weekly=0
        self.severance_total=0
        self.checkpoints=0
        self.new_foundations=0
        self.missed_wages_weeks=0
        self.loan_balance=0    # there is no lending mechanism in v14
        self.trade_swaps=0
        self.transfer_banned_attempts=0
    def register_member(self, fighter, season, acquisition, cash=0, swap=False):
        self.spells[fighter.fid] = Ownership(
            fighter.fid, fighter.age, fighter.ca, market.value(fighter, season, fighter.ca, fighter.pa),
            season, acquisition, acquisition_cash=cash, noncash_trade=swap,
        )

    def close_member(self, fighter, season, reason, cash=0, swap=False):
        spell = self.spells.pop(fighter.fid, None)
        if spell is not None:
            spell.sale_cash = cash
            spell.noncash_trade |= swap
            spell.ca_out = fighter.ca
            spell.value_out = market.value(fighter, season, fighter.ca, fighter.pa)
            spell.season_out = season
            spell.exit = reason
            self.closed_spells.append(spell)

    def snapshot(self, guild, season):
        if guild.gid != self.player:
            return
        for f in guild.fighters:
            d = f.development
            row = dict(seed=self.seed, strategy=self.strategy, season=season, fid=f.fid,
                       age=f.age, role=ROLES[f.role], curve=f.curve, ca=round(f.ca, 3),
                       pa=round(f.pa, 3), level=f.lv, xp=f.xp, skill_points=f.lv-1,
                       skill_slots=available_skill_slots(f.lv), squad=d.squad,
                       wage=f.wage, contract_end=f.contract_end, rookie=d.rookie,
                       market_value=market.value(f, season, f.ca, f.pa), mentor_id=d.mentor_id,
                       traits='|'.join(f'{ATTRIBUTES[t.attribute]}+{t.bonus}' for t in d.traits))
            row.update(zip(ATTRIBUTES, (round(value, 3) for value in d.attributes)))
            self.player_snapshots.append(row)

    def settle_debt(self,g):
        d=self.debts[g.gid]
        for category,name in (('wage_arrears','wages'),('operation_arrears','operations'),('severance_arrears','severance')):
            amount=getattr(d,name)
            if amount<=0:continue
            paid=self.money.spend(g,amount,category,partial=True)
            setattr(d,name,amount-paid)
    def mandatory(self,g,amount,category,kind):
        amount=int(round(amount))
        paid=self.money.spend(g,amount,category,partial=True)
        if paid<amount:self.money.obligation(g,kind,amount-paid)
        return paid==amount
    def register_overflow(self,g):
        d=self.debts[g.gid]
        if len(g.fighters)>MAX_ROSTER:
            if d.overflow_first_week is None:
                d.overflow_first_week=self.globalweek
                self.roster_overflow_events+=1
        else:d.overflow_first_week=None
    def trim_roster(self,g,season,forced=False):
        if len(g.fighters)<=MAX_ROSTER:
            self.register_overflow(g);return 0
        d=self.debts[g.gid]
        if not forced and d.overflow_first_week is not None and self.globalweek-d.overflow_first_week+1<OVERFLOW_WEEKS:return 0
        ranked=sorted(g.fighters,key=lambda f:(f.ca+.12*f.lv+.1*(observed_pa(f,g.gid==self.player)-f.ca))-(f.wage*2))
        removed=0
        while len(g.fighters)>MAX_ROSTER:
            f=ranked.pop(0)
            severance=math.ceil(.30*f.wage*52*max(0,f.contract_end-season))
            # Creditors get a payable if the sect cannot pay severance immediately.
            self.mandatory(g,severance,'severance','severance')
            self.severance_total+=severance
            if g.gid == self.player:
                self.spells[f.fid].severance_due += severance
                self.close_member(f, season, "released")
            g.fighters.remove(f);f.free_since=season
            self.fa.append(f);removed+=1
            self.roster_auto_releases+=1
        self.register_overflow(g)
        return removed
    def financial_control(self,g,season):
        d=self.debts[g.gid]
        if d.total()>0:
            d.unpaid_weeks+=1;d.ever_unpaid_weeks+=1
            d.max_unpaid_weeks=max(d.max_unpaid_weeks,d.unpaid_weeks)
            if d.unpaid_weeks>=5:d.state='distress'
            elif d.unpaid_weeks>=3:d.state='restructuring'
            else:d.state='warning'
            g.negative_weeks+=1;g.negative_streak+=1
            g.max_negative_streak=max(g.max_negative_streak,g.negative_streak)
            self.stats['financial_distress_guildweeks']+=1
            if d.unpaid_weeks in (3,5,6,8):
                if self.distress_sale(g,season):
                    # Proceeds may clear actual arrears before any closure decision.
                    self.settle_debt(g)
            if d.total()==0:
                d.unpaid_weeks=0;d.state='healthy';g.negative_streak=0
            elif d.unpaid_weeks>=BANKRUPTCY_WEEKS:
                self.disband(g,season)
        else:
            d.unpaid_weeks=0;d.state='healthy';g.negative_streak=0
    def distress_sale(self,g,season):
        if len(g.fighters)<=15:return False
        candidates=[f for f in g.fighters if f.last_transfer_season!=season]
        if not candidates:return False
        candidates.sort(key=lambda f:f.ca+.12*f.lv-(f.wage*2))
        # Look for funded, non-distressed buyer. A sale is a real transfer, no money creation.
        for f in candidates[:4]:
            if sell_to_bidders(self, g, f, season, listed=False):
                self.stats['distress_sales'] += 1
                return True
        return False
    def disband(self,g,season):
        self.mentors.pop(g.gid, None)
        self.bankruptcies+=1
        if g.gid==self.player_id:
            for fighter in g.fighters:
                self.close_member(fighter, season, "dissolved")
            self.player_bankrupted=True
            self.player_bankrupt_season=season
            self.player=-1              # Successor is AI-run; player's playthrough ended.
        d=self.debts[g.gid]
        # Unpaid claims are written off, explicitly tracked (not paid in imaginary cash).
        self.money.stats['liabilities_written_off']+=d.total()
        # Real remaining cash at closure leaves the system, not transferred to a ghost.
        self.money.spend(g,g.cash,'dissolution_cash_sink')
        for f in g.fighters:
            f.free_since=season
            self.fa.append(f)
        g.fighters=[]
        for z in self.zones:
            if z.owner==g.gid:z.owner=None
        # New charter, same league slot and guild id, preserving exactly 32 sects.
        p=TIERS[g.tier]
        for _ in range(20):
            ca=old.clamp(self.rng.gauss(p['base_ca']*.78,10),30,180)
            pa=old.clamp(ca+self.rng.randint(8,54),ca,200)
            f=self._make_fighter(ca,pa,self.rng.randint(1,4),self.rng.randint(18,32),self.rng.randrange(6),season+self.rng.randint(1,4))
            g.fighters.append(f)
        g.strategy=self.rng.choice(STRATS)
        startup=8*(g.wage_total()+p['hall'])
        self.money.credit(g,startup,'replacement_founder_capital')
        self.new_foundations+=1
        g.score=0;g.renown=40;g.negative_streak=0
        self.debts[g.gid]=Debt(liquidations=d.liquidations+1)
        # Note: new charter starts without a zone and can choose livelihood work.
    def trade(self,seller,buyer,target,fee,swap,season):
        """Atomic 0~3 player exchange + cash negotiation.
        swap is a list of buyer guild members offered to the seller.
        """
        if target not in seller.fighters or buyer.gid==seller.gid:return False
        if target.last_transfer_season==season:return False
        if len(swap)>3 or len({x.fid for x in swap})!=len(swap):return False
        if any(f not in buyer.fighters or f.last_transfer_season==season for f in swap):return False
        if len(buyer.fighters)+1-len(swap)>MAX_TEMP_ROSTER:return False
        if len(seller.fighters)-1+len(swap)>MAX_TEMP_ROSTER:return False
        fee=int(round(fee))
        if fee<0 or buyer.cash<fee:return False
        if not self.money.move(buyer,seller,fee):return False
        seller.fighters.remove(target);buyer.fighters.append(target)
        target.last_transfer_season=season
        for f in swap:
            buyer.fighters.remove(f);seller.fighters.append(f)
            f.last_transfer_season=season
        seller.transfers_out+=1;buyer.transfers_in+=1
        seller.transfers_in+=len(swap);buyer.transfers_out+=len(swap)
        self.stats['transfers']+=1
        if seller.gid == self.player:
            self.close_member(target, season, 'sold', fee, bool(swap))
            for f in swap:
                self.register_member(f, season, 'exchange', swap=True)
        if buyer.gid == self.player:
            self.register_member(target, season, 'transfer', fee, bool(swap))
            for f in swap:
                self.close_member(f, season, 'exchanged', swap=True)
        self.trade_swaps+=len(swap)
        self.register_overflow(buyer);self.register_overflow(seller)
        return True
    def new_contract(self,g,f,season,weekly=False):
        """Contract free agent; existing wage is not repriced on an in-contract trade."""
        if f not in self.fa or len(g.fighters)>=MAX_TEMP_ROSTER:return False
        joining=math.ceil(old.salary(f)*1.06)
        fee=5*joining
        mandatory_reserve=CASH_RESERVE_WEEKS*(g.wage_total()+joining+TIERS[g.tier]['hall'])
        if g.cash<fee+mandatory_reserve or self.debts[g.gid].total()>0:return False
        # Contract willingness explicitly excludes playing-time predictions.
        base_offer=1.06
        appeal=(g.renown-50)/800
        if self.rng.random() > old.clamp(.85+appeal+.03*(base_offer-1),.70,.97):return False
        self.money.spend(g,fee,'fa_signing_fee')
        self.fa.remove(f)
        g.fighters.append(f)
        f.wage=joining;f.contract_end=season+self.rng.randint(1,5)
        f.last_transfer_season=season
        f.free_since=-1;g.fa_signings+=1
        self.stats['fa_signings']+=1
        if weekly:self.freeagent_weekly+=1
        self.register_overflow(g)
        if g.gid == self.player:
            self.register_member(f, season, "rookie" if f.development.rookie else "fa", fee)
        return True


def select_offer(g,w):
    pool=w.fa
    if not pool:return []
    player=g.gid==w.player
    targets=[]
    # AI sees only a grade; player sees precise PA.
    for f in pool:
        if f.age>42:continue
        pa=observed_pa(f,player)
        potential=max(0,pa-f.ca)
        if g.strategy=='growth':value=.9*f.ca+1.2*potential+.12*f.lv-.60*old.salary(f)
        elif g.strategy=='transfer':value=f.ca+.5*potential+.12*f.lv-.55*old.salary(f)
        else:value=f.ca+.4*potential+.12*f.lv-.70*old.salary(f)
        targets.append((value,-f.fid,f))
    targets.sort(reverse=True)
    return [f for _,__,f in targets[:6]]


def freeagent_week(w,season):
    # Uncontracted FA signings available all weeks, but the annual draft retains priority.
    for g in w.guilds.values():
        if len(g.fighters)>=MAX_ROSTER:continue
        shortage=len(g.fighters)<15
        if shortage or (len(g.fighters)<22 and g.cash>10*(g.wage_total()+TIERS[g.tier]['hall'])
                        and w.rng.random()<.012):
            for f in select_offer(g,w):
                if w.new_contract(g,f,season,weekly=True):break


def sell_to_bidders(w, seller, target, season, listed):
    asking = market.requirement(w, seller, target, season, listed)
    if asking is None:
        return False
    bids = []
    for buyer in w.guilds.values():
        if (buyer is seller or len(buyer.fighters) >= MAX_ROSTER
                or w.debts[buyer.gid].total() or buyer.tier < seller.tier - 1):
            continue
        limit = min(market.cash_room(buyer, target, ()), market.buyer_limit(w, buyer, target, season))
        if limit >= asking:
            fee = asking + (limit - asking) // 2
            bids.append((fee, -buyer.gid, buyer))
    if not bids:
        return False
    fee, _, buyer = max(bids)
    return market.settle(w, market.Offer(buyer.gid, seller.gid, target.fid, fee), season, listed)


def buy_from_world(w, buyer, season, aggressive=False):
    if len(buyer.fighters) >= MAX_ROSTER or w.debts[buyer.gid].total():
        return False
    if buyer.cash < 2 * market.fixed(buyer):
        return False
    candidates = []
    for seller in w.guilds.values():
        if seller is buyer or len(seller.fighters) <= 15 or seller.tier < buyer.tier - 1:
            continue
        for f in seller.fighters:
            if f.last_transfer_season == season:
                continue
            ca, pa = market.talent(f, buyer, w.player)
            price = market.value(f, season, ca, pa)
            score = (ca + (0.30 if aggressive else .5) * max(0, pa-ca) - .3*f.wage) / price**.28
            candidates.append((score, -f.fid, seller, f))
    for _, _, seller, target in sorted(candidates, reverse=True)[:12]:
        offer = market.negotiate(w, buyer, seller, target, season)
        if offer is not None and market.settle(w, offer, season):
            return True
    return False


def list_graduate(w, seller, season):
    candidates = [f for f in seller.fighters if f.development.rookie and 19 <= f.age <= 27
                  and f.development.trainee_weeks >= 45 and f.last_transfer_season != season]
    candidates.sort(key=lambda f: market.value(f, season, f.ca, observed_pa(f)), reverse=True)
    for f in candidates[:3]:
        if sell_to_bidders(w, seller, f, season, listed=True):
            return True
    return False


def market_week(w,season,week):
    # Continuous inter-guild transfer market + continuous unsigned FA pool.
    freeagent_week(w,season)
    for g in list(w.guilds.values()):
        if w.debts[g.gid].unpaid_weeks>=2:continue
        if (g.strategy == 'growth' and len(g.fighters) > 20 and week % 4 == 0
                and list_graduate(w, g, season)):
            continue
        reserve=4*(g.wage_total()+TIERS[g.tier]['hall'])
        if g.cash<reserve and len(g.fighters)>24 and w.rng.random()<.30:
            w.distress_sale(g,season);continue
        rate=({'baseline':.018,'growth':.025,'transfer':.24,'conquest':.025,'balanced':.045}[w.strategy]
              if g.gid==w.player else {'baseline':.018,'growth':.022,'transfer':.04,'conquest':.016,'balanced':.026}[g.strategy])
        if w.rng.random()<rate:buy_from_world(w,g,season,aggressive=(g.gid==w.player and w.strategy=='transfer'))


def prep_plan(w,g,week):
    plan=old.prep_plan(w,g,week)
    # v13 places any >20 in the second squad; v14 tracks 10 proper 2nd-team
    # slots and at most two temporary unregistered first-team reserves.
    active_ids={f.fid for f in old.choose_active(g,g.gid==w.player)}
    nonactive=[f for f in g.fighters if f.fid not in active_ids]
    for index, f in enumerate(nonactive):
        f.development.squad = 'second' if index < MAX_SECOND else 'overflow'
        if g.gid == w.player and index < MAX_SECOND:
            w.spells[f.fid].second_weeks += 1
    for f in g.fighters:
        if f.fid not in active_ids:
            continue
        if g.gid == w.player:
            spell = w.spells[f.fid]
            spell.first_weeks += 1
            spell.promotions += int(f.development.squad == 'second')
        f.development.squad = 'first' 
    plan['second']=nonactive[:MAX_SECOND]
    plan['overflow_bench']=nonactive[MAX_SECOND:]
    assert len(plan['second'])<=10 and len(plan['overflow_bench'])<=2
    return plan


def mission_week_details(w,g,plan):
    rng=w.rng;p=TIERS[g.tier];total_gross=total_cost=0;success=0
    for team in plan['missions']:
        power=old.team_power(team,None,'mission')
        chance=old.clamp(.78+(power-p['base_ca']-2*p['base_lv'])/260,.42,.95)
        potential=round(p['mission_gross']*rng.uniform(.8,1.2))
        cost=p['mission_cost']
        if g.cash<cost:
            w.stats['cancelled_unfunded_missions']+=1
            plan.setdefault('unfunded_missions',[]).append(team)
            continue
        w.money.spend(g,cost,'mission_preparation')
        ok=rng.random()<chance
        gross=potential if ok else round(.18*potential)
        w.money.credit(g,gross,'mission_gross_reward')
        if g.gid == w.player:
            for member, amount in allocate_cash(gross - cost, [(member, 1) for member in team]):
                w.spells[member.fid].mission_net_share += amount
        g.missions_done+=1;g.missions_won+=int(ok)
        if ok:g.score+=.65
        total_gross+=gross;total_cost+=cost;success+=int(ok)
    if plan.get('unfunded_missions'):
        bad={id(t) for t in plan['unfunded_missions']}
        plan['missions']=[t for t in plan['missions'] if id(t) not in bad]
    return success


def collect_zone_income(w,old_owners,g,week):
    items=[]
    for z in w.zones:
        prev=old_owners[z.zid];now=z.owner
        if week<52:
            days=7 if prev==now==g.gid else 4 if prev==g.gid else 3 if now==g.gid else 0
        else:days=7 if now==g.gid else 0
        if not days:continue
        p=TIERS[z.tier]
        gross=round(days*p['gross']*z.multiplier)
        maintenance=round(days*p['zone_cost']*z.multiplier)
        items.append((gross,maintenance,z))
    items.sort(key=lambda x:x[0]-x[1],reverse=True)
    for i,(gross,maintenance,z) in enumerate(items):
        w.money.credit(g,gross,'territory_gross')
        # Gross always arrives together with the direct maintenance for that zone.
        paid=w.money.spend(g,maintenance,'territory_direct_maintenance')
        assert paid==maintenance,(g.gid,z.zid)
        net=gross-maintenance
        overhead=round(net*(1-[1.,.65,.4,.3,.2][min(i,4)]))
        if overhead:w.money.spend(g,overhead,'territory_scale_overhead')


def train_week(w, g, plan, week, invest):
    if week == 52:
        for f in g.fighters:
            f.fatigue = max(0, f.fatigue - 42)
            f.injured = max(0, f.injured - 1)
        return
    trainees = plan['training'] + plan['second'] + plan.get('overflow_bench', [])
    share = {'baseline': .35, 'growth': .8, 'transfer': .25,
             'conquest': .20, 'balanced': .5}[g.strategy]
    improving = sum(f.ca < f.pa - .01 for f in trainees)
    multiplier = 1 + min(.30, invest * share / (12 * max(1, improving)))

    available_mentors = w.mentors.get(g.gid, {})
    for f in trainees:
        f.development.mentor_id = None
    if available_mentors and g.cash >= (g.wage_total() + TIERS[g.tier]['hall']) * 10:
        assigned = set()
        for f in plan['second']:
            mentor = available_mentors.get(f.role)
            if f.injured or f.age > 24 or observed_pa(f, g.gid == w.player) - f.ca < 1 or mentor is None or mentor in assigned:
                continue
            if w.money.spend(g, 4, 'mentor_fee') == 4:
                assigned.add(mentor)
                f.development.mentor_id = mentor
                f.development.mentor_weeks += 1
                if f.fid in w.spells:
                    w.spells[f.fid].mentor += 4

    def update(f, base, xp, fatigue, training=False):
        if not f.injured:
            gap = max(0, f.pa - f.ca)
            mentor_bonus = 1.12 if training and f.development.mentor_id is not None else 1
            gain = base * old.age_factor(f) * gap / max(1, f.pa)
            if training:
                gain *= multiplier * mentor_bonus
                f.development.train(f, gain)
            elif gain > 0:
                for i, value in enumerate(f.development.attributes):
                    f.development.attributes[i] = min(200, value + gain)
                f.development.refresh(f)
            old.advance_experience(f, xp)
        f.fatigue = old.clamp(f.fatigue + fatigue, 0, 100)

    for f in plan['training']:
        update(f, .80, 12, -2, True)
    for f in plan['second'] + plan.get('overflow_bench', []):
        update(f, .60, 9, -3, True)
    for f in plan['attack']:
        update(f, .40, 24 + 8 * plan['attack_won'], 21)
    for f in plan['defend']:
        update(f, .32, 13, 9)
    for team in plan['missions']:
        for f in team:
            update(f, .34, 22, 18)
    for f in plan['emergency']:
        update(f, .19, 13, 12)
    for f in plan['rest']:
        f.fatigue = max(0, f.fatigue - 48)
    for f in g.fighters:
        f.injured = max(0, f.injured - 1)


def productive_investment_ceiling(g,plan):
    # v13/14 growth bonus cap: min(.30, investment * training_share / (12 * trainees)).
    # No paid trainee => no effect => no investment. Disallow useless surplus sink.
    share={'baseline':.35,'growth':.8,'transfer':.25,'conquest':.20,'balanced':.5}[g.strategy]
    trainee=sum(not f.injured and f.ca < f.pa - .01 for f in
                plan['training'] + plan['second'] + plan.get('overflow_bench', []))
    if trainee<=0:return 0
    return math.floor(.30*12*trainee/share)


def economics_week(w,plans,old_owners,season,week):
    # Deterministic weekly order: zone -> sponsor -> mission -> operations ->
    # old debts -> wages & hall -> paid training -> optional reinvest -> rest/growth.
    owners_at_week_start=set(i for i in old_owners if i is not None)
    for g in w.guilds.values():
        p=TIERS[g.tier]
        plan=plans[g.gid]
        collect_zone_income(w,old_owners,g,week)
        if p['sponsor']:w.money.credit(g,p['sponsor'],'league_sponsor')
        urgent=(not g.gid in owners_at_week_start and week<52 and len(plan['emergency'])==5)
        if urgent:w.money.credit(g,p['emergency'],'no_territory_livelihood')
        success=mission_week_details(w,g,plan) if week<52 else 0
        # Active garrison cost by territory outside weekly 5-person assignment.
        protected=[z for z in w.zones if z.owner==g.gid and z.zid!=plan['home']]
        garrison=round(sum(old.zone_value(z) for z in protected)*.03) if protected else 0
        if garrison:w.mandatory(g,garrison,'garrison_cost','operations')
        w.settle_debt(g)
        wages_paid = min(g.cash, g.wage_total())
        paid_wages=w.mandatory(g,g.wage_total(),'weekly_wages','wages')
        if g.gid == w.player:
            for f, cash in allocate_cash(wages_paid, [(f, f.wage) for f in g.fighters]):
                spell = w.spells[f.fid]
                spell.wages_due += f.wage
                spell.wages_paid_current += cash
            for f in plan['attack'] + plan['defend']:
                w.spells[f.fid].battle_weeks += 1
            for team in plan['missions']:
                for f in team:
                    w.spells[f.fid].mission_weeks += 1
        w.mandatory(g,p['hall'],'hall_upkeep','operations')
        if not paid_wages:w.missed_wages_weeks+=1
        # If a club cannot fund training, it does not receive free CA gains.
        if week < 52:
            for unit in ('training', 'second', 'overflow_bench'):
                plan[unit] = [f for f in plan[unit] if not f.injured]
        weighted = [(f, 4) for f in plan['training']]
        weighted += [(f, 3) for f in plan['second'] + plan.get('overflow_bench', [])]
        training = round(p['training_cost'] * sum(weight for _, weight in weighted) / 4)
        fixed = g.wage_total() + p['hall']
        # In the treasury-policy experiment a low reserve leaves reserve training idle.
        if w.conservative and g.strategy == 'growth' and g.cash < 10 * fixed:
            plan['second'] = []
            plan['overflow_bench'] = []
            weighted = [(f, 4) for f in plan['training']]
            training = p['training_cost'] * len(weighted)
        if training and w.money.spend(g, training, 'paid_training') != training:
            plan['training'] = []; plan['second'] = []; plan['overflow_bench'] = []
            weighted = []
            w.stats['unfunded_training_weeks'] += 1
        invest=0
        if week<52 and w.debts[g.gid].total()==0:
            fixed=g.wage_total()+p['hall']
            reserve=8*fixed
            rate={'baseline':.13,'growth':.19,'transfer':.08,'conquest':.13,'balanced':.15}[g.strategy]
            if g.strategy=='growth' and g.cash<10*fixed:
                rate=0 if w.conservative else .08
            unconstrained=max(0,min(round(rate*max(0,g.cash-reserve)),round(.80*max(0,g.cash))))
            cap=productive_investment_ceiling(g,plan)
            w.stats['avoided_unproductive_investment']+=max(0,unconstrained-cap)
            invest=w.money.spend(g,min(unconstrained,cap),'paid_investment') if unconstrained and cap else 0
            g.gold_spent_training+=invest*{'baseline':.35,'growth':.8,'transfer':.25,'conquest':.20,'balanced':.5}[g.strategy]+training
        g.renown=old.clamp(g.renown+invest/22000+success*.003,0,100)
        g.score+=sum(1.0 if z.tier==g.tier else .35 for z in w.zones if z.owner==g.gid)
        if g.gid == w.player:
            for f, cost in allocate_cash(training, weighted):
                w.spells[f.fid].training += cost
            eligible = [(f, weight) for f, weight in weighted if f.ca < f.pa - .01]
            for f, cost in allocate_cash(invest, eligible):
                w.spells[f.fid].investment += cost
        train_week(w,g,plan,week,invest)
        w.financial_control(g,season)


def add_annual_rookies(w,season):
    # New cohort at season end; only unsold FA can be signed during the season.
    old.generate_rookies(w,season)


def annual_rollover(w,season):
    rng=w.rng
    rank_by_tier={}
    fa_order=[]
    for tier in (1,2,3,4):
        ranked=sorted((g for g in w.guilds.values() if g.tier==tier),key=lambda g:(g.score,g.strength(),-g.gid),reverse=True)
        assert len(ranked)==8
        rank_by_tier[tier]=ranked
        fa_order.extend(reversed(ranked))
        for idx,g in enumerate(ranked):
            if g.gid==w.player_id:g.annual_best_rank=idx+1
        w.money.credit(ranked[0],AWARDS[tier],'league_champion_award')
        w.money.credit(ranked[1],AWARDS[tier]//2,'league_runnerup_award')
        if tier==1:
            ranked[0].championships+=1
            w.player_titles += int(ranked[0].gid == w.player)
    moves=[]
    for upper,lower in ((1,2),(2,3),(3,4)):
        hi=rank_by_tier[upper];lo=rank_by_tier[lower]
        moves.extend(((lo[0],upper),(hi[-1],lower)))
        p=old.clamp(old.logistic((lo[1].strength()-hi[-2].strength())/15),.07,.93)
        if rng.random()<p:moves.extend(((lo[1],upper),(hi[-2],lower)))
    for g,newtier in moves:
        if g.tier==newtier:continue
        if newtier<g.tier:g.promoted+=1
        else:g.relegated+=1
        g.tier=newtier;g.first_reach=min(g.first_reach,newtier)
        if g.gid==w.player:
            w.player_best_division = min(w.player_best_division, newtier)
            if newtier==1 and w.player_reached_1 is None:w.player_reached_1=season
    assert [sum(g.tier==tier for g in w.guilds.values()) for tier in (1,2,3,4)]==[8]*4
    for g in w.guilds.values():
        owned=sorted((z for z in w.zones if z.owner==g.gid),key=old.zone_value)
        for z in owned[:max(0,len(owned)-CAP[g.tier])]:z.owner=None
    # Already unsigned free agents age once per year. Newly expired roster
    # members will be aged in the guild loop below, so don't age them twice.
    for f in w.fa:f.age+=1
    # End-of-season explicit renewal decision for every expiring contract.
    # Player GUI not yet available: player uses the named simulated AI policy.
    for g in w.guilds.values():
        kept=[]
        important_ids={f.fid for f in sorted(g.fighters,key=lambda x:x.ca+.12*x.lv,reverse=True)[:16]}
        for f in g.fighters:
            f.age+=1
            if f.age > PEAK_AGE[f.curve] + 6:
                factor = .97 if f.age <= PEAK_AGE[f.curve] + 11 else .94
                f.development.attributes = [value * factor for value in f.development.attributes]
                f.development.refresh(f)
            if f.age>46 or (f.age>41 and rng.random()<.06):
                w.mentors.setdefault(g.gid, {})[f.role] = f.fid
                if g.gid == w.player:
                    w.close_member(f, season, 'retired')
                w.stats['retired']+=1
                continue
            if f.contract_end<=season:
                important=f.fid in important_ids
                enough=g.cash>4*(g.wage_total()+TIERS[g.tier]['hall'])
                desire=(.94 if important else .70)*(1 if enough else .55)
                if w.debts[g.gid].total()>0:desire*=.35
                if rng.random()<desire:
                    f.contract_end=season+rng.randint(1,5)
                    f.wage=math.ceil(old.salary(f)*rng.uniform(1.00,1.15))
                    kept.append(f)
                    w.stats['renewal_decision_keep']+=1
                else:
                    if g.gid == w.player:
                        w.close_member(f, season, 'expired')
                    f.free_since=season;w.fa.append(f);g.fa_releases+=1
                    w.stats['renewal_decision_release']+=1
            else:kept.append(f)
        g.fighters=kept
    add_annual_rookies(w,season)
    # Annual reverse order 1st league 8th->1st, then 2nd, 3rd, 4th.
    for rnd in range(3):
        for g in fa_order:
            if not w.fa or len(g.fighters)>=MAX_ROSTER:continue
            should=(len(g.fighters)<17 or
                (g.gid==w.player and w.strategy=='growth' and rnd<3) or
                (g.strategy=='growth' and len(g.fighters)<25 and rnd<2) or
                (g.strategy in ('balanced','transfer') and len(g.fighters)<23 and rnd<2))
            if not should:continue
            for f in select_offer(g,w):
                if w.new_contract(g,f,season,weekly=False):break
    # Two full year-ends unsigned => exits pool, doesn't mysteriously reappear.
    previously=len(w.fa)
    w.fa[:]=[f for f in w.fa if season-f.free_since<2 and f.age<=42]
    w.unemployment_exit+=previously-len(w.fa)
    for g in w.guilds.values():
        w.trim_roster(g,season,forced=True) if len(g.fighters)>MAX_ROSTER else None
        g.score=0


def assert_world(w):
    w.money.reconcile()
    assert len(w.guilds)==32
    assert [sum(g.tier==t for g in w.guilds.values()) for t in (1,2,3,4)]==[8,8,8,8]
    unique=[f.fid for g in w.guilds.values() for f in g.fighters]+[f.fid for f in w.fa]
    assert len(set(unique))==len(unique),'Duplicated character between guilds/FA'
    assert all(0<=len(g.fighters)<=MAX_TEMP_ROSTER for g in w.guilds.values())
    assert all(old.zone_count(w,g)<=CAP[g.tier] for g in w.guilds.values())
    assert all(d.total()>=0 for d in w.debts.values())
    w.checkpoints+=1


def one_week(w,season,week):
    w.season_active=season;w.week_active=week
    # Season0 is the pre-history, not playable time.
    w.globalweek=season*52+week
    if week<52:market_week(w,season,week)
    plans={g.gid:(prep_plan(w,g,week) if week<52 else dict(
        attack=[],defend=[],missions=[],training=[],rest=[],second=[],overflow_bench=[],scout=[],emergency=[],home=None,attack_target=None,attack_won=False))
        for g in w.guilds.values()}
    owners=[z.owner for z in w.zones]
    if week < 52:
        changes = old.attempt_attacks(w, plans, week)
        for zid, (_, new_owner) in changes.items():
            if new_owner == w.player:
                members = plans[new_owner]['attack']
                for f, estimated in allocate_cash(round(old.zone_value(w.zones[zid])),
                                                  [(f, 1) for f in members]):
                    w.spells[f.fid].capture_income_estimate += estimated
    economics_week(w,plans,owners,season,week)
    for g in w.guilds.values():
        w.trim_roster(g,season)
    assert_world(w)


def install_player(w,strategy):
    # One simulated prehistory season completed; replace the weakest 4th division sect.
    last=min((g for g in w.guilds.values() if g.tier==4),key=lambda g:g.strength())
    home=next((z for z in w.zones if z.owner==last.gid),None)
    if home is None:home=next((z for z in w.zones if z.tier==4 and z.owner is None),None)
    if home is None:home=w.rng.choice([z for z in w.zones if z.tier==4])
    for z in w.zones:
        if z.owner==last.gid:z.owner=None
    home.owner=last.gid
    w.money.spend(last,last.cash,'prehistory_sect_closeout')
    for f in last.fighters:
        f.free_since=0;w.fa.append(f)
    last.fighters=[]
    for _ in range(20):
        ca=old.clamp(w.rng.gauss(80,12),50,112)
        pa=old.clamp(ca+w.rng.randint(10,65),ca,200)
        if w.rng.random()<.08:pa=max(pa,old.clamp(w.rng.gauss(180,12),ca,200))
        f=w._make_fighter(ca,pa,w.rng.randint(1,5),w.rng.randint(18,33),w.rng.randrange(6),w.rng.randint(1,5))
        last.fighters.append(f)
    initial=8*(last.wage_total()+TIERS[4]['hall'])
    w.money.credit(last,initial,'player_founder_capital')
    last.cash_start=initial;last.strategy=strategy
    last.score=0;last.renown=50;last.negative_weeks=0;last.negative_streak=0
    last.first_reach=4;last.championships=0
    w.debts[last.gid]=Debt()
    w.strategy=strategy;w.player=last.gid;w.player_id=last.gid
    for f in last.fighters:
        w.register_member(f, 1, "founder")
    w.snapshot(last, 0)
    w.money.reconcile()
    return last


def run(seed,strategy,capture_ledger=False,conservative=True):
    w=World15(seed,'baseline',capture_ledger=capture_ledger,conservative=conservative)
    for week in range(1,53):one_week(w,0,week)
    annual_rollover(w,0)
    pg=install_player(w,strategy)
    annual=[]
    yearly_ledger=[]
    for season in range(1,11):
        low_cover = float("inf")
        max_debt = 0
        opening_w= sum(g.cash for g in w.guilds.values())
        opening_src=w.money.source;opening_snk=w.money.sink
        for week in range(1,53):
            one_week(w,season,week)
            if w.player_bankrupt_season == season:
                low_cover = 0
            if not w.player_bankrupted:
                low_cover = min(low_cover, pg.cash / (pg.wage_total() + TIERS[pg.tier]['hall']))
                max_debt = max(max_debt, w.debts[pg.gid].total())
        tier=pg.tier
        rank=sorted((g for g in w.guilds.values() if g.tier==tier),key=lambda g:g.score,reverse=True).index(pg)+1
        prefa=pg.cash
        annual_rollover(w,season)
        w.snapshot(pg, season)
        assert_world(w)
        c= w.money.by_season[season]
        ys=dict(seed=seed,strategy=strategy,season=season,world_cash_before=opening_w,
            world_cash_end=sum(g.cash for g in w.guilds.values()),sources=w.money.source-opening_src,
            sinks=w.money.sink-opening_snk,fa_pool=len(w.fa),world_roster=sum(len(g.fighters) for g in w.guilds.values()),
            arrears=sum(d.total() for d in w.debts.values()),bankruptcies=w.bankruptcies,
            transfers=w.stats['transfers'],player_debt=None if w.player_bankrupted else w.debts[w.player_id].total(),
            player_alive=int(not w.player_bankrupted),new_foundations=w.new_foundations,
            player_cash_end=None if w.player_bankrupted else pg.cash,player_tier=None if w.player_bankrupted else pg.tier)
        ys['net_cash_change']=ys['world_cash_end']-opening_w
        ys['booked_net_cash_change']=ys['sources']-ys['sinks']
        assert ys['net_cash_change']==ys['booked_net_cash_change']
        yearly_ledger.append(ys)
        annual.append(dict(seed=seed,strategy=strategy,season=season,league_pre=tier if not w.player_bankrupted else None,rank=rank if not w.player_bankrupted else None,
            cash_preFA=prefa if not w.player_bankrupted else None,cash_postFA=pg.cash if not w.player_bankrupted else None,league_post=pg.tier if not w.player_bankrupted else None,zone_pre=old.zone_count(w,pg) if not w.player_bankrupted else None,
            roster=len(pg.fighters) if not w.player_bankrupted else None,player_debt=None if w.player_bankrupted else w.debts[w.player_id].total(),
            player_alive=int(not w.player_bankrupted),source=ys['sources'],sink=ys['sinks'],
            world_cash=ys['world_cash_end'],bankruptcies=w.bankruptcies,
            free_market=len(w.fa),reaches_1=(w.player_best_division==1),
            min_cash_cover_weeks=round(low_cover, 2) if math.isfinite(low_cover) else None,
            peak_player_debt=max_debt if math.isfinite(low_cover) else None,
            top5_CA=round(sum(f.ca for f in sorted(pg.fighters,key=lambda f:f.ca,reverse=True)[:5])/max(1,min(5,len(pg.fighters))),1) if not w.player_bankrupted else None))
    for f in pg.fighters:
        if f.fid in w.spells:
            w.spells[f.fid].ca_out = f.ca
            w.spells[f.fid].value_out = market.value(f, 10, f.ca, f.pa)
    result=dict(seed=seed,strategy=strategy,initial_cash=pg.cash_start,
        individuals=w.player_snapshots,
        ownership=[dict(seed=seed, strategy=strategy, **asdict(spell),
                        total_cost=spell.total_cost, cash_sale_less_accrued_cost=spell.sale_cash-spell.total_cost,
                        proceeds_plus_contribution_less_cost=spell.sale_cash+spell.mission_net_share+
                        spell.capture_income_estimate-spell.total_cost)
                   for spell in w.closed_spells + list(w.spells.values())],
        final_cash=None if w.player_bankrupted else pg.cash,
        successor_cash=pg.cash if w.player_bankrupted else None,
        player_bankrupted=w.player_bankrupted,player_bankrupt_season=w.player_bankrupt_season,
        best_division=w.player_best_division,
        final_division=pg.tier if not w.player_bankrupted else None,
        reached_1=w.player_best_division==1,
        title=w.player_titles>0,
        average_player_debt=round(statistics.mean([x['player_debt'] for x in annual if x['player_debt'] is not None] or [0])),
        negative_player_weeks=pg.negative_weeks,money_source=w.money.source,money_sink=w.money.sink,
        final_world_cash=sum(g.cash for g in w.guilds.values()),opening_world_cash=w.money.opening,
        total_ledger_error=w.money.reconcile()-(w.money.source-w.money.sink),
        weekly_fa_signings=w.freeagent_weekly,fa_signings=w.stats['fa_signings'],
        transfers=w.stats['transfers'],swap_players=w.trade_swaps,bankruptcies=w.bankruptcies,
        arrears_final=sum(d.total() for d in w.debts.values()),
        max_debt_streak=max(d.max_unpaid_weeks for d in w.debts.values()),
        auto_overflow_releases=w.roster_auto_releases,overflows=w.roster_overflow_events,
        uncontracted_exits=w.unemployment_exit,foundations=w.new_foundations,
        total_roster=sum(len(g.fighters) for g in w.guilds.values()),fa_pool=len(w.fa),
        avoided_unproductive_investment=w.stats['avoided_unproductive_investment'],
        planned_sales=w.stats['planned_sales'],player_planned_sales=w.stats['player_planned_sales'],
        market_deals=w.stats['market_deals'],market_counters=w.stats['market_counters'],
        check_count=w.checkpoints,annual=annual,yearly_ledger=yearly_ledger,
        category_ledger=dict(w.money.categories),ledger_entries=w.money.entries if capture_ledger else [])
    return result


def summarize(runs):
    out=[]
    for strategy in STRATS:
        x=[r for r in runs if r['strategy']==strategy]
        if not x:continue
        median=lambda k:round(statistics.median(v[k] for v in x if v[k] is not None),1) if any(v[k] is not None for v in x) else None
        avg=lambda k:round(statistics.mean(v[k] for v in x),2)
        out.append(dict(strategy=strategy,n=len(x),reached_1=sum(v['reached_1'] for v in x),
            bankrupt_player=sum(v['player_bankrupted'] for v in x),title=sum(v['title'] for v in x),
            final_cash_median=median('final_cash'),final_world_cash_median=median('final_world_cash'),
            avg_distress_weeks=avg('negative_player_weeks'),avg_bankruptcies=avg('bankruptcies'),
            avg_weekly_fa=avg('weekly_fa_signings'),avg_fa=avg('fa_signings'),
            avg_transfers=avg('transfers'),avg_final_arrears=avg('arrears_final'),
            avg_avoided_waste=avg('avoided_unproductive_investment'),
            med_total_roster=median('total_roster'),avg_uncontracted_exits=avg('uncontracted_exits'),
            total_ledger_errors=sum(abs(v['total_ledger_error']) for v in x),
            min_final_cash=min((v['final_cash'] for v in x if v['final_cash'] is not None),default=None)))
    return out


def run_task(args):return run(*args)


def write_outputs(runs,prefix):
    stem=Path(prefix);stem.parent.mkdir(parents=True,exist_ok=True)
    summ=summarize(runs)
    with open(str(stem)+'_summary.csv','w',encoding='utf-8-sig',newline='') as file:
        wr=csv.DictWriter(file,fieldnames=summ[0].keys());wr.writeheader();wr.writerows(summ)
    for suffix,rows in [('annual',[a for r in runs for a in r['annual']]),
                        ('world_ledger',[a for r in runs for a in r['yearly_ledger']]),
                        ('individuals',[a for r in runs for a in r['individuals']]),
                        ('ownership',[a for r in runs for a in r['ownership']])]:
        with open(str(stem)+'_'+suffix+'.csv','w',encoding='utf-8-sig',newline='') as file:
            wr=csv.DictWriter(file,fieldnames=rows[0].keys());wr.writeheader();wr.writerows(rows)
    with open(str(stem)+'_runs.json','w',encoding='utf-8') as file:
        json.dump([{k:v for k,v in r.items() if k not in ('ledger_entries','individuals','ownership')} for r in runs],file,ensure_ascii=False,indent=1)
    for r in runs:
        if r['ledger_entries']:
            out=str(stem)+f"_ledger_seed{r['seed']}_{r['strategy']}.csv"
            with open(out,'w',encoding='utf-8-sig',newline='') as file:
                wr=csv.DictWriter(file,fieldnames=r['ledger_entries'][0].keys())
                wr.writeheader();wr.writerows(r['ledger_entries'])
    return summ


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seeds',type=int,default=5)
    ap.add_argument('--start',type=int,default=0)
    ap.add_argument('--jobs',type=int,default=2)
    ap.add_argument('--prefix',default='data/v15_1')
    ap.add_argument('--capture-ledger',action='store_true')
    ap.add_argument('--growth-only', action='store_true')
    args=ap.parse_args()
    st=time.perf_counter()
    tasks=[(seed,strategy,args.capture_ledger and seed==args.start and strategy=='balanced', not args.growth_only)
           for seed in range(args.start,args.start+args.seeds) for strategy in STRATS]
    if args.jobs>1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            runs=list(ex.map(run_task,tasks))
    else:runs=[run_task(t) for t in tasks]
    print(json.dumps(write_outputs(runs,args.prefix),ensure_ascii=False,indent=2))
    print('elapsed seconds',round(time.perf_counter()-st,2))

if __name__=='__main__':main()
