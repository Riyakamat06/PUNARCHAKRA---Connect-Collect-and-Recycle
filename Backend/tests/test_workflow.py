"""
test_workflow.py  -  the request status workflow (Requested -> Accepted -> Picked Up -> Paid).
"""

import pytest

from app.errors import InvalidTransition, RoleNotAllowed
from app.services.workflow import (ALLOWED_TRANSITIONS, FINAL_STATUSES, Role,
                                   Status as S, check_transition, next_statuses)


def test_happy_path_requested_to_paid():
    check_transition(S.REQUESTED, S.ACCEPTED, Role.DEALER)
    check_transition(S.ACCEPTED, S.PICKED_UP, Role.DEALER)
    check_transition(S.PICKED_UP, S.PAID, Role.DEALER)


def test_counter_offer_is_one_round_only():
    check_transition(S.REQUESTED, S.COUNTER_OFFER, Role.DEALER)
    check_transition(S.COUNTER_OFFER, S.ACCEPTED, Role.SELLER)
    check_transition(S.COUNTER_OFFER, S.REJECTED, Role.SELLER)
    with pytest.raises(InvalidTransition):                 # no second counter
        check_transition(S.COUNTER_OFFER, S.COUNTER_OFFER, Role.DEALER)
    with pytest.raises(RoleNotAllowed):                    # dealer cannot answer own counter
        check_transition(S.COUNTER_OFFER, S.ACCEPTED, Role.DEALER)


def test_seller_can_withdraw_and_either_side_can_cancel_before_pickup():
    check_transition(S.REQUESTED, S.CANCELLED, Role.SELLER)
    check_transition(S.ACCEPTED, S.CANCELLED, Role.SELLER)
    check_transition(S.ACCEPTED, S.CANCELLED, Role.DEALER)


def test_after_pickup_only_the_administrator_can_cancel():          # BR-15
    check_transition(S.PICKED_UP, S.CANCELLED, Role.ADMIN)
    for role in (Role.SELLER, Role.DEALER):
        with pytest.raises(RoleNotAllowed):
            check_transition(S.PICKED_UP, S.CANCELLED, role)


def test_wrong_role_gets_403_and_missing_move_gets_409():
    with pytest.raises(RoleNotAllowed) as wrong_role:
        check_transition(S.REQUESTED, S.ACCEPTED, Role.SELLER)
    assert wrong_role.value.http_status == 403
    with pytest.raises(InvalidTransition) as no_move:
        check_transition(S.REQUESTED, S.PAID, Role.DEALER)           # skipping steps
    assert no_move.value.http_status == 409
    assert no_move.value.to_dict()["code"] == "INVALID_TRANSITION"


def test_final_statuses_have_no_way_out():
    for (current, _), _roles in ALLOWED_TRANSITIONS.items():
        assert current not in FINAL_STATUSES


def test_next_statuses_lists_the_buttons_a_role_may_see():
    assert next_statuses(S.REQUESTED, Role.DEALER) == [S.ACCEPTED, S.COUNTER_OFFER, S.REJECTED]
    assert next_statuses(S.REQUESTED, Role.SELLER) == [S.CANCELLED]
    assert next_statuses(S.PAID, Role.ADMIN) == []