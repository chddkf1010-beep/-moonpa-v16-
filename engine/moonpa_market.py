"""Transfer valuation and bargaining for v15.1."""
from dataclasses import dataclass
from itertools import combinations
from moonpa_growth import observed_ability, observed_potential
from moonpa_world_v15 import TIERS
from moonpa_names import preference_multiplier


@dataclass(frozen=True)
class Offer:
    buyer: int
    seller: int
    member: int
    fee: int
    exchange: tuple[int, ...] = ()


def talent(f, viewer, player):
    # Grades provide a conservative estimate for rival players.
    ca = f.ca if viewer.gid == player else observed_ability(f)
    pa = f.pa if viewer.gid == player else observed_potential(f)
    return ca, pa


def value(f, season, ca, pa):
    age = 1.07 if f.age <= 23 else 1 if f.age <= 32 else .75 if f.age <= 38 else .48
    remaining = min(5, max(0, f.contract_end - season + 1))
    rights = .55 + .15 * remaining
    potential = max(0, pa - ca) * max(.1, min(1, (36 - f.age) / 12))
    trait_bonus = 12 * sum(t.bonus for t in f.development.traits)
    # Historical season 0 must use the original transfer valuation, otherwise
    # changes to current-season prices alter the prehistory world RNG and attach
    # seed-16 founder portraits to a different role/name roster.
    elite_premium = 1 if season == 0 else 1 + 2 * (max(0, ca - 85) / 68)**2.5
    return round(max(20, (4 + .0000125 * ca**3 * elite_premium) * 30 * age * rights
                     + 3 * potential + trait_bonus + 5 * (f.lv - 1)))


def estimate(w, f, viewer, season):
    return value(f, season, *talent(f, viewer, w.player))


def fixed(g):
    return g.wage_total() + TIERS[g.tier]['hall']


def requirement(w, seller, target, season, listed=False):
    if (target not in seller.fighters or target.last_transfer_season == season
            or target.fid in w.away(seller.gid)):
        return None
    peers = [f for f in seller.fighters if f.role == target.role]
    core = sorted(seller.fighters, key=lambda f: f.ca, reverse=True)[:5]
    distressed = seller.cash < 4 * fixed(seller) or w.debts[seller.gid].total()
    if len(seller.fighters) <= 15 or (target in core and len(peers) == 1 and not distressed):
        return None
    base = value(target, season, target.ca, observed_potential(target))
    factor = .78 if distressed else 1 if listed else 1.4 if target in core else 1.12
    return round(base * factor)


def seller_needs(seller, target):
    """Judge the outgoing fighter against the seller's own depth chart."""
    ranked = sorted(seller.fighters, key=lambda f: (-f.ca, f.fid))
    substitutes = [f for f in ranked if f is not target and f.role == target.role]
    best_backup = max((f.ca for f in substitutes), default=0)
    essential = target in ranked[:5] or target.ca >= best_backup + 12
    profile = ('commercial' if '상단' in seller.name or seller.strategy == 'transfer'
               else seller.strategy)
    return essential, profile


def replacement_value(w, seller, target, offered):
    ca, pa = talent(offered, seller, w.player)
    if offered.role != target.role or offered.injured:
        return None
    essential, profile = seller_needs(seller, target)
    if not essential:
        return None
    if ca >= target.ca - (6 if profile == 'conquest' else 10):
        return 'ready'
    development_margin = 8 if profile in ('commercial','growth') else 3
    if (target.age >= 30 and offered.age <= target.age - 6
            and pa >= target.ca + development_margin and ca >= target.ca - 40
            and offered.wage <= target.wage):
        return 'prospect'
    return None


def seller_credit_for(w, seller, target, offered, season):
    credit = 0
    for member in offered:
        valuation = estimate(w, member, seller, season)
        match = replacement_value(w, seller, target, member)
        factor = 1.20 if match == 'ready' else 1.10 if match == 'prospect' else .85
        credit += round(valuation * factor * preference_multiplier(seller, member))
    return credit


def suggest_player_offer(w, buyer, seller, target, season):
    essential, profile = seller_needs(seller, target)
    message = ('주전 공백을 메울 같은 역할의 문파원이 필요합니다.' if essential
               else '현재 전력 구성을 유지할 수 있어 현금 제안도 검토합니다.')
    if essential and target.age >= 30:
        message += ' 고령 주전이라면 주급이 낮고 잠재력이 높은 젊은 후계자도 검토합니다.'
    away = w.away(buyer.gid)
    eligible = [f for f in buyer.fighters if f.last_transfer_season != season and f.fid not in away]
    eligible.sort(key=lambda f: (replacement_value(w, seller, target, f) is not None,
                                  seller_credit_for(w, seller, target, [f], season), -f.fid),
                  reverse=True)
    candidates = []
    for size in range(4):
        for bundle in combinations(eligible[:8], size):
            if essential and not any(replacement_value(w, seller, target, f) for f in bundle):
                continue
            ids = tuple(f.fid for f in bundle)
            status, counter = offer_status(w, Offer(buyer.gid,seller.gid,target.fid,0,ids), season)
            if status in ('accepted','counter','insufficient_cash'):
                fee = counter.fee if counter else 0
                candidates.append((status == 'insufficient_cash', size, fee, ids))
        if candidates and any(not item[0] for item in candidates):
            break
    if not candidates:
        status, _ = offer_status(w, Offer(buyer.gid,seller.gid,target.fid,0), season)
        return dict(status=status, message=message, profile=profile)
    unfunded, _, fee, ids = min(candidates)
    mode = next((replacement_value(w,seller,target,f) for f in eligible if f.fid in ids
                 and replacement_value(w,seller,target,f)), None)
    if mode == 'prospect':
        message = '젊은 후계자를 받아 장기 전력을 보강하되 주급 부담은 늘리지 않습니다.'
    elif mode == 'ready':
        message = '같은 역할의 즉시전력으로 주전 공백을 보완합니다.'
    return dict(status='insufficient_cash' if unfunded else 'suggested', message=message,
                profile=profile, fee=fee, exchange=list(ids))



def seller_bargain(w, buyer, seller, target, season, proposed, turn=1):
    """Deterministic seller reply grounded in the same rules as actual trades.

    Propose the specific available fighter(s) the seller wants, not a phantom
    player or arbitrary cash fee. The returned counter is directly settleable.
    This function never changes squads, cash, world RNG, or the offer ledger.
    """
    status, _ = offer_status(w, proposed, season)
    if status == 'accepted':
        return dict(status='accepted', offer=proposed,
                    message='상대 문파가 제안한 조건을 수락했습니다. 거래를 확정하시겠습니까?')
    if status in ('invalid','locked','roster','outstanding_debt'):
        descriptions = {
            'invalid':'거래 대상이나 인원 구성이 올바르지 않습니다.',
            'locked':'이번 시즌에 이적했거나 원정 중인 문파원은 거래할 수 없습니다.',
            'roster':'이적 후 양측 문파의 최소·최대 정원을 지킬 수 없습니다.',
            'outstanding_debt':'미상환 채무가 있어 신규 이적 계약을 맺을 수 없습니다.',
        }
        return dict(status='refused',reason=status,message=descriptions[status])
    asking = requirement(w, seller, target, season)
    essential, profile = seller_needs(seller,target)
    if asking is None and not essential:
        return dict(status='refused',reason='core',
                    message='우리 문파가 지금 이 문파원을 내보낼 이유가 없습니다.')
    eligible = [f for f in buyer.fighters if f.fid not in w.away(buyer.gid)
                and f.last_transfer_season != season and f is not target
                and not f.injured]
    ranked = sorted(eligible,key=lambda f: (
        replacement_value(w,seller,target,f) is not None,
        f.role == target.role,
        seller_credit_for(w,seller,target,[f],season),
        -f.fid),reverse=True)
    ranked = ranked[:12]
    combinations_pool = [()]
    # Seller chooses particular replacements based on need; never asks for an
    # arbitrary highest-rated player without checking buyer/seller roster caps.
    for size in (1,2):
        if len(buyer.fighters)+1-size < 15 or len(seller.fighters)-1+size > 32:
            continue
        combinations_pool.extend(combinations(ranked,size))
    choices = []
    for bundle in combinations_pool:
        if essential and not any(replacement_value(w,seller,target,f) for f in bundle):
            continue
        ids=tuple(f.fid for f in bundle)
        quote=Offer(buyer.gid,seller.gid,target.fid,0,ids)
        state,counter=offer_status(w,quote,season)
        if state not in ('counter','accepted'):
            continue
        floor=counter.fee if counter else 0
        room=cash_room(buyer,target,bundle)
        # A credible seller may demand some cash on top of an attractive swap.
        bonus = round(max(0,asking or value(target,season,target.ca,observed_potential(target)))
                      *(.06 if profile in ('growth','conquest') else .10))
        cash=min(room,max(floor,bonus if bundle else floor))
        if cash<floor:
            continue
        actual=Offer(buyer.gid,seller.gid,target.fid,cash,ids)
        if offer_status(w,actual,season)[0]!='accepted':
            continue
        suited=sum(2 if replacement_value(w,seller,target,f)=='ready'
                   else 1 if replacement_value(w,seller,target,f)=='prospect'
                   else 0 for f in bundle)
        fit=sum(1 for f in bundle if f.role == target.role)
        # Seller priorities: fill critical lineup holes, avoid asking for extra
        # fighters needlessly, and make a payable proposal.
        priority=(suited*100+fit*15-120*max(0,len(bundle)-1)
                  -(cash/max(1,asking or 1))*10)
        choices.append((priority,-len(bundle),-cash,ids,actual))
    if not choices:
        return dict(status='refused',reason='unfunded',
                    message=('주전 공백을 메울 인물이나 운영자금을 확보할 수 없어 '
                             '현재 조건으로는 협상할 수 없습니다.'))
    # For non-essential sales, cash alone is natural when the sect needs money;
    # for a core fighter, matching replacement is nonnegotiable.
    if not essential and (profile=='commercial' or seller.cash < 4*fixed(seller)):
        cash_choices=[row for row in choices if not row[3]]
        if cash_choices:
            choices=cash_choices
    pick=max(choices,key=lambda row:(row[0],row[1],row[2],tuple(-v for v in row[3])))
    counter=pick[-1]
    required=[f for f in buyer.fighters if f.fid in counter.exchange]
    if counter.exchange:
        named='·'.join(f.name for f in required)
        text=('현금만으로는 전력 공백을 메우기 어렵습니다. '
              if essential else '우리 문파에 필요한 인재를 함께 보내주십시오. ')
        text+=f'{named} 문파원과 현금 {counter.fee:,}냥을 요구합니다.'
    else:
        text=f'선수 교환 없이 현금 {counter.fee:,}냥이라면 검토할 수 있습니다.'
    return dict(status='counter',offer=counter,message=text,
                demands=[dict(id=f.fid,name=f.name,role=f.role,
                              ca=round(f.ca,1),pa=round(f.pa,1),
                              wage=f.wage) for f in required],
                seller_profile=profile,essential=essential)

def buyer_limit(w, buyer, target, season):
    current, _ = talent(target, buyer, w.player)
    peers = sorted((f.ca for f in buyer.fighters if f.role == target.role), reverse=True)
    need = 1.45 if len(peers) < 2 else 1.2 if current > peers[1] else .92
    return round(estimate(w, target, buyer, season) * need * preference_multiplier(buyer, target))


def cash_room(buyer, target, exchange):
    next_fixed = fixed(buyer) + target.wage - sum(f.wage for f in exchange)
    return max(0, buyer.cash - 4 * next_fixed)


def offer_status(w, offer, season, listed=False):
    if (offer.buyer not in w.guilds or offer.seller not in w.guilds
            or type(offer.fee) is not int or offer.fee < 0):
        return "invalid", None
    buyer, seller = w.guilds[offer.buyer], w.guilds[offer.seller]
    target = next((f for f in seller.fighters if f.fid == offer.member), None)
    offered = [f for f in buyer.fighters if f.fid in offer.exchange]
    if buyer is seller or target is None or len(offered) != len(offer.exchange) or len(offered) > 3:
        return 'invalid', None
    if (any(f.last_transfer_season == season for f in [target, *offered]) or
            target.fid in w.away(seller.gid) or
            any(f.fid in w.away(buyer.gid) for f in offered)):
        return 'locked', None
    if not (15 <= len(buyer.fighters) + 1 - len(offered) <= 32
            and 15 <= len(seller.fighters) - 1 + len(offered) <= 32):
        return 'roster', None
    asking = requirement(w, seller, target, season, listed)
    if buyer.gid == w.player and seller_needs(seller,target)[0]:
        if not any(replacement_value(w,seller,target,f) for f in offered):
            return 'replacement_required', None
        # A suitable exchange can fill the sole-role vacancy that blocks a cash sale.
        if asking is None and len(seller.fighters) >= 15:
            asking = round(value(target,season,target.ca,observed_potential(target))*1.40)
    if asking is None:
        return 'refused', None
    seller_credit = (seller_credit_for(w,seller,target,offered,season) if buyer.gid == w.player else
                     sum(estimate(w,f,seller,season) for f in offered))
    buyer_cost = sum(estimate(w, f, buyer, season) for f in offered)
    minimum = max(0, asking - seller_credit)
    room = cash_room(buyer, target, offered)
    if buyer.gid == w.player:
        if w.debts[buyer.gid].total():
            return 'outstanding_debt', None
        if minimum > room or offer.fee > room:
            return 'insufficient_cash', Offer(offer.buyer, offer.seller, offer.member, minimum, offer.exchange)
    limit = room if buyer.gid == w.player else min(room, buyer_limit(w, buyer, target, season) - buyer_cost)
    if minimum > limit or w.debts[buyer.gid].total():
        return 'unfunded', None
    if offer.fee < minimum:
        return 'counter', Offer(offer.buyer, offer.seller, offer.member, minimum, offer.exchange)
    if offer.fee > limit:
        return 'unfunded', None
    return 'accepted', None


def negotiate(w, buyer, seller, target, season, listed=False, exchange=True):
    choices = [()]
    if exchange:
        core = sorted(buyer.fighters, key=lambda f: f.ca, reverse=True)[:5]
        eligible = [f for f in buyer.fighters if f not in core and f.last_transfer_season != season
                    and f.fid not in w.away(buyer.gid)]
        eligible.sort(key=lambda f: estimate(w, f, seller, season), reverse=True)
        choices.extend(tuple(f.fid for f in eligible[:i]) for i in range(1, min(3, len(eligible)) + 1))
    for ids in choices:
        offer = Offer(buyer.gid, seller.gid, target.fid, 0, ids)
        status, counter = offer_status(w, offer, season, listed)
        if status == 'accepted':
            return offer
        if counter is not None:
            w.stats['market_counters'] += 1
            return counter
    return None


def settle(w, offer, season, listed=False):
    if offer_status(w, offer, season, listed)[0] != 'accepted':
        return False
    buyer, seller = w.guilds[offer.buyer], w.guilds[offer.seller]
    target = next(f for f in seller.fighters if f.fid == offer.member)
    exchange = [f for f in buyer.fighters if f.fid in offer.exchange]
    if w.trade(seller, buyer, target, offer.fee, exchange, season):
        w.stats['market_deals'] += 1
        w.stats['planned_sales'] += listed
        if listed and seller.gid == w.player:
            w.stats['player_planned_sales'] += 1
        return True
    return False
