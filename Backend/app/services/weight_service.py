"""
weight_service.py  -  Engine 2 (Logic and Rule)  -  weight check, payment gate, amount.

THE PICKUP RULES THIS FILE IMPLEMENTS (agreed design)
    1. At pickup the DEALER enters the actual weight.
    2. The SELLER must press Agree or Disagree.
    3. The case goes to the ADMINISTRATOR when the seller disagrees OR when the
       actual weight differs from the estimate by MORE than 10% (BR-20).
    4. The administrator has only two choices: approve the dealer's weight
       (payment goes ahead) or cancel the pickup with a note.
    5. Payment is only RECORDED in the system. Nothing is processed online.
       Amount = final weight x agreed rate per kg.

WHY Decimal
    Money and weights are exact figures. Python's float cannot store 0.1 exactly,
    so a limit check such as "difference above 10%" or an amount such as
    Rs 3325.00 could be off by a tiny amount. Decimal is exact. Values may be
    passed as int, float, str or Decimal; they are converted safely.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional, Union

from .. import config
from ..errors import InvalidWeight

Number = Union[int, float, str, Decimal]


def _dec(value: Number) -> Decimal:
    """Convert to Decimal through str(), so 0.1 stays 0.1 and not 0.1000000000000000055."""
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# Weight mismatch (BR-20)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WeightCheck:
    difference_pct: Decimal     # |actual - estimated| / estimated x 100, 2 decimals
    is_mismatch: bool           # True only when ABOVE the limit


def check_weight_mismatch(estimated_kg: Number, actual_kg: Number,
                          limit_percent: Number = config.MISMATCH_LIMIT_PERCENT) -> WeightCheck:
    """Compare the seller's estimate with the dealer's measured weight.

    Exactly on the limit (10.00%) is still fine; only MORE than the limit is a
    mismatch. The flag is decided on the exact value, the shown figure is
    rounded to 2 decimals.
    """
    estimated, actual = _dec(estimated_kg), _dec(actual_kg)
    if estimated <= 0 or actual <= 0:
        raise InvalidWeight("Weights must be above zero.",
                            estimated_kg=str(estimated), actual_kg=str(actual))
    difference = abs(actual - estimated) / estimated * 100
    return WeightCheck(
        difference_pct=difference.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        is_mismatch=difference > _dec(limit_percent),
    )


# ---------------------------------------------------------------------------
# Payment gate: may the payment be recorded yet?
# ---------------------------------------------------------------------------

class SellerResponse(str, Enum):
    AGREE = "AGREE"
    DISAGREE = "DISAGREE"


class AdminDecision(str, Enum):
    APPROVE_DEALER_WEIGHT = "APPROVE_DEALER_WEIGHT"
    CANCEL_PICKUP = "CANCEL_PICKUP"


class PaymentGate(str, Enum):
    ALLOWED = "ALLOWED"                          # record the payment now
    WAITING_FOR_SELLER = "WAITING_FOR_SELLER"    # seller has not answered yet
    NEEDS_ADMIN_REVIEW = "NEEDS_ADMIN_REVIEW"    # goes to the administrator
    PICKUP_CANCELLED = "PICKUP_CANCELLED"        # administrator cancelled it


def payment_gate(is_mismatch: bool,
                 seller_response: Optional[SellerResponse],
                 admin_decision: Optional[AdminDecision] = None) -> PaymentGate:
    """Decide whether payment may be recorded.

    The administrator's decision always wins. Without one, payment is allowed
    only when the seller agreed AND the weight is within the limit.
    """
    if admin_decision is AdminDecision.CANCEL_PICKUP:
        return PaymentGate.PICKUP_CANCELLED
    if admin_decision is AdminDecision.APPROVE_DEALER_WEIGHT:
        return PaymentGate.ALLOWED
    if seller_response is None:
        return PaymentGate.WAITING_FOR_SELLER
    if seller_response is SellerResponse.DISAGREE or is_mismatch:
        return PaymentGate.NEEDS_ADMIN_REVIEW
    return PaymentGate.ALLOWED


# ---------------------------------------------------------------------------
# Payment amount
# ---------------------------------------------------------------------------

def payment_amount(final_weight_kg: Number, agreed_rate_per_kg: Number) -> Decimal:
    """Amount to record in rupees = final weight x agreed rate, to 2 decimals."""
    weight, rate = _dec(final_weight_kg), _dec(agreed_rate_per_kg)
    if weight <= 0 or rate <= 0:
        raise InvalidWeight("Weight and rate must be above zero.")
    return (weight * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)