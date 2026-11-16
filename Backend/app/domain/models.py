"""
models.py  -  the data shapes that the Logic engine receives and returns.

WHY CLASSES INSTEAD OF PLAIN DICTIONARIES
    * A wrong value is caught the moment the object is created (for example a
      dealer with a negative radius), so the ranking code never has to doubt its
      input. This is the "server-side re-validation" of the Gate 2 design.
    * Every field is named and typed, so reading the code is easier.
    * The objects are frozen (read-only), so a function cannot change a dealer
      by accident while ranking.

HOW THE ENGINES USE THEM
    Data engine      builds Dealer and Listing objects from database rows.
    Logic engine     (rank_dealers) returns a SearchResult.
    Interface engine turns SearchResult into JSON with result.to_dict().
"""

from dataclasses import dataclass, field, asdict
from datetime import date
from types import MappingProxyType
from typing import Mapping, Optional

from .. import config
from ..errors import (InvalidCategory, InvalidDealerData, InvalidLocation,
                      InvalidRadius, InvalidWeight)


# ===========================================================================
# INPUT: a seller's listing
# ===========================================================================

@dataclass(frozen=True)
class Listing:
    """What the seller is trying to sell, and where.

    category        one of config.CATEGORIES
    weight_kg       estimated weight, above 0 and at most config.MAX_LISTING_WEIGHT_KG
    lat, lon        the seller's map pin
    search_km       how far the seller is willing to search (1 to 50 km)
    preferred_date  the day the seller would like the pickup
    """
    category: str
    weight_kg: float
    lat: float
    lon: float
    search_km: float
    preferred_date: date

    def __post_init__(self):
        if self.category not in config.CATEGORIES:
            raise InvalidCategory(
                f"Category must be one of: {', '.join(config.CATEGORIES)}.",
                category=self.category)
        if not 0 < self.weight_kg <= config.MAX_LISTING_WEIGHT_KG:
            raise InvalidWeight(
                f"Weight must be above 0 and at most {config.MAX_LISTING_WEIGHT_KG} kg.",
                weight_kg=self.weight_kg)
        if not config.MIN_SEARCH_KM <= self.search_km <= config.MAX_SEARCH_KM:
            raise InvalidRadius(
                f"Search distance must be {config.MIN_SEARCH_KM} to "
                f"{config.MAX_SEARCH_KM} km.", search_km=self.search_km)
        _check_pin(self.lat, self.lon, InvalidLocation)


# ===========================================================================
# INPUT: a dealer, as the ranking needs to see it
# ===========================================================================

@dataclass(frozen=True)
class Dealer:
    """One dealer, with the figures the ranking needs.

    dealer_id          database id
    lat, lon           the dealer's map pin
    service_radius_km  how far the dealer is willing to travel
    capacity_kg        how much weight the dealer can take
    is_verified        True when the administrator has verified the dealer
    rates              {"metal": 38.0, ...} latest rate per kg per category;
                       a category that is missing means "not accepted"
    open_days          weekdays the dealer works (0 = Monday ... 6 = Sunday)
    finished_pickups   completed pickups so far
    completion_pct     completed / accepted requests x 100 (0 to 100)
    avg_rating         average rating 1 to 5, or None when not rated yet
    """
    dealer_id: int
    lat: float
    lon: float
    service_radius_km: float
    capacity_kg: float
    is_verified: bool
    rates: Mapping[str, float]
    open_days: frozenset
    finished_pickups: int = 0
    completion_pct: float = 0.0
    avg_rating: Optional[float] = None

    def __post_init__(self):
        _check_pin(self.lat, self.lon, InvalidDealerData)
        if self.service_radius_km <= 0 or self.capacity_kg <= 0:
            raise InvalidDealerData("Radius and capacity must be above 0.",
                                    dealer_id=self.dealer_id)
        if any(category not in config.CATEGORIES or rate <= 0
               for category, rate in self.rates.items()):
            raise InvalidDealerData("Rates must be above 0 and use a valid category.",
                                    dealer_id=self.dealer_id)
        if not set(self.open_days) <= set(range(7)):
            raise InvalidDealerData("Open days must be numbers 0 to 6.",
                                    dealer_id=self.dealer_id)
        if self.finished_pickups < 0 or not 0 <= self.completion_pct <= 100:
            raise InvalidDealerData("Pickup history is out of range.",
                                    dealer_id=self.dealer_id)
        if self.avg_rating is not None and not 1 <= self.avg_rating <= 5:
            raise InvalidDealerData("Rating must be between 1 and 5.",
                                    dealer_id=self.dealer_id)
        # A frozen object cannot assign normally, so use object.__setattr__ to
        # store read-only copies (callers cannot change them afterwards).
        object.__setattr__(self, "rates", MappingProxyType(dict(self.rates)))
        object.__setattr__(self, "open_days", frozenset(self.open_days))


def _check_pin(lat, lon, error_class):
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise error_class("Latitude must be -90 to 90 and longitude -180 to 180.",
                          lat=lat, lon=lon)


# ===========================================================================
# OUTPUT: what the ranking returns
# ===========================================================================

@dataclass(frozen=True)
class FactorPoints:
    """Points each factor contributed. The four add up to the total score."""
    price: float
    availability: float
    reliability: float
    distance: float


@dataclass(frozen=True)
class RankedDealer:
    """One line of the result list."""
    rank: int
    dealer_id: int
    score: float
    distance_km: float
    rate: float
    verified: bool            # the screen shows the "Verified" badge
    reliability: float
    low_reliability: bool     # soft warning BR-21
    breakdown: FactorPoints


@dataclass
class FilterCounts:
    """How many dealers each hard filter removed (explains an empty result)."""
    material: int = 0
    distance: int = 0
    capacity: int = 0
    verification: int = 0

    @property
    def total(self):
        return self.material + self.distance + self.capacity + self.verification


@dataclass(frozen=True)
class SoftWarning:
    """A soft warning. It informs the user and never blocks the action."""
    code: str
    message: str


@dataclass
class SearchResult:
    """Everything the screen needs after a search."""
    results: list
    eligible_count: int
    removed: FilterCounts
    warnings: list = field(default_factory=list)
    profile: str = config.DEFAULT_PROFILE

    @property
    def no_dealer_found(self):
        """True -> show the 'no dealer found' screen with the removal counts."""
        return self.eligible_count == 0

    @property
    def more_than_top_k(self):
        """True -> show the 'too many dealers' screen ('best 10 of N')."""
        return self.eligible_count > len(self.results)

    def to_dict(self):
        """Plain dictionary, ready to be sent as JSON by the Interface engine."""
        body = asdict(self)
        body["removed"]["total"] = self.removed.total
        body["no_dealer_found"] = self.no_dealer_found
        body["more_than_top_k"] = self.more_than_top_k
        return body