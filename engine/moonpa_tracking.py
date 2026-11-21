"""Money and player-development history keyed by ownership spell."""
from dataclasses import dataclass


@dataclass(slots=True)
class Ownership:
    fid: int
    age_in: int
    ca_in: float
    value_in: int
    season_in: int
    acquisition: str
    acquisition_cash: int = 0
    wages_due: int = 0
    wages_paid_current: int = 0
    training: int = 0
    investment: int = 0
    mentor: int = 0
    mission_net_share: int = 0
    capture_income_estimate: int = 0
    sale_cash: int = 0
    noncash_trade: bool = False
    promotions: int = 0
    first_weeks: int = 0
    second_weeks: int = 0
    mission_weeks: int = 0
    battle_weeks: int = 0
    severance_due: int = 0
    value_out: int = 0
    ca_out: float = 0
    exit: str = 'held'
    season_out: int | None = None

    @property
    def total_cost(self):
        return self.acquisition_cash + self.wages_due + self.training + self.investment + self.mentor + self.severance_due


def allocate_cash(amount, weighted_members):
    """Integer pro rata allocation conserving the payment exactly."""
    total = sum(weight for _, weight in weighted_members)
    cumulative = allocated = 0
    for member, weight in weighted_members:
        cumulative += weight
        next_total = amount * cumulative // total
        yield member, next_total - allocated
        allocated = next_total
