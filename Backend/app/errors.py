"""
errors.py  -  the error types the Logic engine can raise.

WHY
    The Gate 2 interface contract promises that the Logic engine answers bad
    input with a NAMED error (for example InvalidRadius), never a crash. The
    Interface engine (FastAPI) catches DomainError, reads its code, message and
    http_status, and sends the standard error response of Gate 2 section 3.3:

        {"success": false, "code": "...", "message": "...", "details": {...}}

HTTP meaning used by the project:
    400 invalid input | 403 role not allowed | 409 rule or state conflict
"""


class DomainError(Exception):
    """Base class of every rule/validation error in the Logic engine."""

    code = "DOMAIN_ERROR"
    http_status = 400

    def __init__(self, message, **details):
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self):
        """The standard error body (Gate 2, section 3.3)."""
        return {"success": False, "code": self.code,
                "message": self.message, "details": self.details}


# ---- 400: the input itself is wrong ---------------------------------------

class InvalidRadius(DomainError):
    code = "INVALID_RADIUS"


class InvalidWeight(DomainError):
    code = "INVALID_WEIGHT"


class InvalidCategory(DomainError):
    code = "INVALID_CATEGORY"


class InvalidLocation(DomainError):
    """The map pin is outside the valid latitude/longitude range."""
    code = "INVALID_LOCATION"


class InvalidDealerData(DomainError):
    code = "INVALID_DEALER_DATA"


class InvalidRequest(DomainError):
    """A parameter such as k (how many results) is not usable."""
    code = "INVALID_REQUEST"


class WeightsInvalid(DomainError):
    """The ranking weights do not add up to 100 (Gate 2 contract: WeightsInvalid)."""
    code = "WEIGHTS_INVALID"


# ---- 403 / 409: the action is not allowed --------------------------------

class RoleNotAllowed(DomainError):
    code = "ROLE_NOT_ALLOWED"
    http_status = 403


class InvalidTransition(DomainError):
    code = "INVALID_TRANSITION"
    http_status = 409