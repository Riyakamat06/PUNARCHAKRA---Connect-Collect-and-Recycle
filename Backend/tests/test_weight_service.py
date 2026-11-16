"""
test_weight_service.py  -  scenarios W1 to W3 (weight and payment) plus the payment gate.
"""

from decimal import Decimal

import pytest

from app.errors import InvalidWeight
from app.services.weight_service import (AdminDecision, PaymentGate,
                                         SellerResponse, check_weight_mismatch,
                                         payment_amount, payment_gate)


def test_w1_exactly_ten_percent_difference_is_not_a_mismatch():
    # |110 - 100| / 100 x 100 = 10.00 -> not ABOVE the 10% limit.
    check = check_weight_mismatch(100, 110)
    assert check.difference_pct == Decimal("10.00") and check.is_mismatch is False


def test_w2_twelve_percent_difference_is_flagged_for_admin_review():
    # |88 - 100| / 100 x 100 = 12.00 -> above 10, flagged.
    check = check_weight_mismatch(100, 88)
    assert check.difference_pct == Decimal("12.00") and check.is_mismatch is True


def test_w3_payment_amount_is_final_weight_times_agreed_rate():
    # 87.5 kg x Rs38 = Rs3325.00 (exact, no floating-point error)
    assert payment_amount(87.5, 38) == Decimal("3325.00")
    assert payment_amount("12.3", "40.5") == Decimal("498.15")     # 12.3 x 40.5
    with pytest.raises(InvalidWeight):
        payment_amount(0, 38)


def test_weights_must_be_positive():
    with pytest.raises(InvalidWeight):
        check_weight_mismatch(0, 50)


def test_payment_gate_follows_the_agreed_pickup_rules():
    A, D = SellerResponse.AGREE, SellerResponse.DISAGREE
    assert payment_gate(False, None) is PaymentGate.WAITING_FOR_SELLER
    assert payment_gate(False, A) is PaymentGate.ALLOWED
    assert payment_gate(False, D) is PaymentGate.NEEDS_ADMIN_REVIEW     # disagreement
    assert payment_gate(True, A) is PaymentGate.NEEDS_ADMIN_REVIEW      # above 10%
    assert payment_gate(True, D, AdminDecision.APPROVE_DEALER_WEIGHT) is PaymentGate.ALLOWED
    assert payment_gate(True, D, AdminDecision.CANCEL_PICKUP) is PaymentGate.PICKUP_CANCELLED