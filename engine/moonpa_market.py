"""Transfer valuation and bargaining for v15.1."""
from dataclasses import dataclass
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
    elite_premium = 1 + 2 * (max(0, ca - 85) / 68)**2.5
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
    if asking is None:
        return 'refused', None
    seller_credit = sum(estimate(w, f, seller, season) for f in offered)
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
