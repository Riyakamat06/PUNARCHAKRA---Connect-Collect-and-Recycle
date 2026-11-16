"""
workflow.py  -  Engine 2 (Logic and Rule)  -  the request status workflow.

THE DESIGN
    The status lives on the REQUEST record (there is no separate pickup table):

        Requested -> Accepted -> Picked Up -> Paid
        plus the branches Rejected, Counter-offer and Cancelled.

    Every change of status goes through check_transition(). It answers one
    question: "may this ROLE move a request from THIS status to THAT status?".
    All the allowed moves are written in ONE table below, so the whole workflow
    can be read (and shown to the professor) in one place.

RULES THE TABLE ENFORCES
    * The dealer may accept, reject, or make ONE counter-offer. After the
      counter-offer the seller may only accept or reject it, so the table has no
      Counter-offer -> Counter-offer move: negotiation is one round only.
    * The seller can withdraw a request while it is Requested or Counter-offer.
    * A seller or a dealer can cancel an Accepted request. Once it is Picked Up
      only the ADMINISTRATOR can cancel it (the mismatch review), BR-15.
    * Pending requests never expire (no automatic move in this table).
    * Rejected, Paid and Cancelled are final: nothing leaves them.
    * Whether payment may be recorded (weight agreed or cleared by the admin) is
      decided by weight_service.payment_gate(); this file only checks the move.

COMPLEXITY
    O(1): one dictionary lookup per check.
"""

from enum import Enum

from ..errors import InvalidTransition, RoleNotAllowed


class Status(str, Enum):
    REQUESTED = "REQUESTED"
    COUNTER_OFFER = "COUNTER_OFFER"
    ACCEPTED = "ACCEPTED"
    PICKED_UP = "PICKED_UP"
    PAID = "PAID"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class Role(str, Enum):
    SELLER = "SELLER"
    DEALER = "DEALER"
    ADMIN = "ADMIN"


S, R = Status, Role

# (from status, to status) -> the roles allowed to make that move.
ALLOWED_TRANSITIONS = {
    (S.REQUESTED,     S.ACCEPTED):      {R.DEALER},            # accepts at the listed rate
    (S.REQUESTED,     S.REJECTED):      {R.DEALER},
    (S.REQUESTED,     S.COUNTER_OFFER): {R.DEALER},            # the ONE counter-offer
    (S.REQUESTED,     S.CANCELLED):     {R.SELLER},            # seller withdraws
    (S.COUNTER_OFFER, S.ACCEPTED):      {R.SELLER},            # seller agrees to counter
    (S.COUNTER_OFFER, S.REJECTED):      {R.SELLER},            # no second counter
    (S.COUNTER_OFFER, S.CANCELLED):     {R.SELLER},            # seller withdraws
    (S.ACCEPTED,      S.PICKED_UP):     {R.DEALER},
    (S.ACCEPTED,      S.CANCELLED):     {R.SELLER, R.DEALER},  # before pickup only
    (S.PICKED_UP,     S.PAID):          {R.DEALER},            # payment recorded
    (S.PICKED_UP,     S.CANCELLED):     {R.ADMIN},             # mismatch review only (BR-15)
}

FINAL_STATUSES = frozenset({S.PAID, S.REJECTED, S.CANCELLED})


def check_transition(current: Status, target: Status, role: Role) -> None:
    """Return quietly if the move is allowed, otherwise raise an error.

    InvalidTransition (HTTP 409): this move does not exist in the workflow.
    RoleNotAllowed    (HTTP 403): the move exists but not for this role.
    """
    allowed_roles = ALLOWED_TRANSITIONS.get((current, target))
    if allowed_roles is None:
        raise InvalidTransition(
            f"A request cannot move from {current.value} to {target.value}.",
            current=current.value, target=target.value)
    if role not in allowed_roles:
        raise RoleNotAllowed(
            f"A {role.value.lower()} cannot move a request from "
            f"{current.value} to {target.value}.",
            current=current.value, target=target.value, role=role.value)


def next_statuses(current: Status, role: Role) -> list:
    """The statuses this role may move the request to (used to show buttons)."""
    return sorted((to for (frm, to), roles in ALLOWED_TRANSITIONS.items()
                   if frm == current and role in roles), key=lambda s: s.value)