"""
ranking_service.py  -  Engine 2 (Logic and Rule)  -  search and rank dealers.

THIS IS THE THEME 2 CORE (Search and Ranking System), and Gate 2 evidence B2.

WHAT THIS FILE DOES
    Given one Listing and many Dealers, it returns the best dealers (top 10), in
    order, each with a score breakdown so the seller can see WHY it is ranked
    there. It contains no SQL and no screen code: the Data engine supplies the
    Dealer objects, the Interface engine displays the SearchResult.

THE STEPS (same order as the Gate 2 design)
    1. HARD FILTERS - remove dealers who cannot do the job at all:
         material      the dealer has no rate for the listing's category
         distance      farther than the seller's search distance OR farther than
                       the dealer's own service radius
         capacity      dealer capacity is less than the listing weight
         verification  e-waste listing and the dealer is not verified
       Each removed dealer is counted under the FIRST filter it fails, so an
       empty result can be explained ("12 dealers were too far away").
    2. FOUR FACTOR SCORES, each from 0 to 100:
         price         rate / highest rate among eligible dealers x 100
                       (the seller SELLS scrap, so a higher rate is better)
         availability  100 if the dealer is open on the seller's preferred
                       weekday, otherwise 0
         reliability   0.5 x completion% + 0.5 x (average rating x 20);
                       a dealer with fewer than 3 finished pickups gets 50
         distance      100 x (1 - distance / search distance)
    3. TOTAL = sum of (weight x factor score) / 100, where the weights add up to
       100. Two profiles exist (see config.py): best_price (default) 40/25/20/15
       and nearest_trusted 20/15/30/35 for price/availability/reliability/distance.
    4. TOP K (default 10) with the hand-built min-heap (min_heap.py).
    5. TIE-BREAK for equal totals: higher reliability first, then shorter distance.
       A last step (lower dealer_id) only makes the order repeatable.

COMPLEXITY
    Filter and score: O(n)        each dealer is handled a fixed number of times
    Select top 10:    O(n log 10) one heap push per eligible dealer
    Space:            O(n)

SOFT WARNINGS (never block the search)
    FEW_DEALERS      (BR-22) fewer than 3 dealers matched
    LOW_RELIABILITY  (BR-21) a listed dealer has reliability below 50
"""

from typing import Iterable, Mapping, Optional

from .. import config
from ..domain.models import (Dealer, FactorPoints, FilterCounts, Listing,
                             RankedDealer, SearchResult, SoftWarning)
from ..errors import InvalidRequest, WeightsInvalid
from .geo import haversine_km
from .min_heap import MinHeap


# ---------------------------------------------------------------------------
# Step 1: hard filters
# ---------------------------------------------------------------------------

def removal_reason(dealer: Dealer, listing: Listing, distance_km: float) -> Optional[str]:
    """Why this dealer must be removed ("material", "distance", "capacity",
    "verification"), or None when the dealer is eligible.

    Filters run in this fixed order, so the counts never double-count.
    """
    # Material: no rate for this category means the dealer does not accept it.
    if listing.category not in dealer.rates:
        return "material"

    # Distance: inside BOTH the seller's search distance and the dealer's own
    # service radius. The limit is inclusive: exactly on the line is allowed.
    if distance_km > min(listing.search_km, dealer.service_radius_km):
        return "distance"

    # Capacity: the dealer must be able to take the whole listing.
    if dealer.capacity_kg < listing.weight_kg:
        return "capacity"

    # E-waste is handled by verified dealers only.
    if listing.category in config.VERIFIED_ONLY_CATEGORIES and not dealer.is_verified:
        return "verification"

    return None


# ---------------------------------------------------------------------------
# Step 2: the four factor scores (each 0 to 100)
# ---------------------------------------------------------------------------

def price_score(rate: float, highest_rate: float) -> float:
    """The dealer's rate as a percentage of the best rate on offer."""
    return rate / highest_rate * 100


def distance_score(distance_km: float, search_km: float) -> float:
    """100 at 0 km, falling in a straight line to 0 at the search distance."""
    return 100 * (1 - distance_km / search_km)


def availability_score(dealer: Dealer, listing: Listing) -> float:
    """100 if the dealer works on the weekday of the preferred date, else 0."""
    return 100.0 if listing.preferred_date.weekday() in dealer.open_days else 0.0


def reliability_score(dealer: Dealer) -> float:
    """Reliability from 0 to 100.

    New dealer (fewer than 3 finished pickups): a neutral 50, because there is
    too little history to judge. Otherwise half completion rate, half rating.

    ASSUMPTION (please confirm): a dealer with 3 or more pickups but no rating
    yet gets a neutral 50 for the rating half.
    """
    if dealer.finished_pickups < config.NEW_DEALER_PICKUPS:
        return float(config.NEW_DEALER_RELIABILITY)
    rating_points = (50.0 if dealer.avg_rating is None
                     else dealer.avg_rating * config.RATING_TO_100)
    return 0.5 * dealer.completion_pct + 0.5 * rating_points


# ---------------------------------------------------------------------------
# Step 3: weights
# ---------------------------------------------------------------------------

def resolve_weights(profile: str = config.DEFAULT_PROFILE,
                    weights: Optional[Mapping[str, float]] = None) -> Mapping[str, float]:
    """Choose the weights to use and check that they add up to 100.

    Pass `weights` to use values read from the ranking_weights table; otherwise
    the named profile from config.py is used.
    """
    if weights is None:
        if profile not in config.WEIGHT_PROFILES:
            raise InvalidRequest(f"Unknown ranking profile: {profile}.", profile=profile)
        weights = config.WEIGHT_PROFILES[profile]
    if set(weights) != set(config.RANKING_FACTORS):
        raise WeightsInvalid("Weights are needed for price, availability, "
                             "reliability and distance.")
    if abs(sum(weights.values()) - 100) > 1e-9 or min(weights.values()) < 0:
        raise WeightsInvalid("Ranking weights must be zero or more and add up to 100.",
                             total=sum(weights.values()))
    return weights


def factor_points(dealer: Dealer, listing: Listing, distance_km: float,
                  highest_rate: float, reliability: float,
                  weights: Mapping[str, float]) -> FactorPoints:
    """Points each factor contributes = weight x factor score / 100."""
    return FactorPoints(
        price=weights["price"] * price_score(dealer.rates[listing.category], highest_rate) / 100,
        availability=weights["availability"] * availability_score(dealer, listing) / 100,
        reliability=weights["reliability"] * reliability / 100,
        distance=weights["distance"] * distance_score(distance_km, listing.search_km) / 100,
    )


# ---------------------------------------------------------------------------
# Steps 4 and 5: the main function
# ---------------------------------------------------------------------------

def rank_dealers(dealers: Iterable[Dealer], listing: Listing, *,
                 profile: str = config.DEFAULT_PROFILE,
                 weights: Optional[Mapping[str, float]] = None,
                 k: int = config.TOP_K) -> SearchResult:
    """Filter, score and rank the dealers for one listing.

    Returns a SearchResult (see domain/models.py). It never raises for an empty
    list: nobody matching is a valid answer, shown with the removal counts.
    """
    if k < 1:
        raise InvalidRequest("k must be at least 1.", k=k)
    w = resolve_weights(profile, weights)
    removed = FilterCounts()

    # --- Step 1: hard filters ---------------------------------------------
    eligible = []                      # list of (dealer, distance_km)
    for dealer in dealers:
        # Rounded to the nearest metre so a dealer exactly on the limit is not
        # rejected by floating-point noise such as 10.0000000001 km.
        distance_km = round(haversine_km(listing.lat, listing.lon,
                                         dealer.lat, dealer.lon), 3)
        reason = removal_reason(dealer, listing, distance_km)
        if reason is None:
            eligible.append((dealer, distance_km))
        else:
            setattr(removed, reason, getattr(removed, reason) + 1)

    if not eligible:
        return SearchResult(results=[], eligible_count=0, removed=removed,
                            profile=profile)

    # The highest rate among ELIGIBLE dealers is worth 100 price points.
    highest_rate = max(d.rates[listing.category] for d, _ in eligible)

    # --- Steps 2, 3, 4: score every dealer, keep the best k ----------------
    heap = MinHeap(k)
    for dealer, distance_km in eligible:
        reliability = reliability_score(dealer)
        points = factor_points(dealer, listing, distance_km, highest_rate,
                               reliability, w)
        # Rounded so that floating-point noise cannot break a genuine tie.
        score = round(points.price + points.availability
                      + points.reliability + points.distance, 4)

        # Heap key. BIGGER = BETTER, compared left to right:
        #   1. higher score
        #   2. higher reliability      (first tie-break)
        #   3. shorter distance        (second tie-break; negated: nearer = bigger)
        #   4. lower dealer_id         (only to keep the order repeatable)
        key = (score, round(reliability, 4), -distance_km, -dealer.dealer_id)
        heap.push_top_k(key, (dealer, distance_km, reliability, points, score))

    # --- Step 5: best first, number the ranks -------------------------------
    ranked = []
    for position, (_, item) in enumerate(heap.best_first(), start=1):
        dealer, distance_km, reliability, points, score = item
        ranked.append(RankedDealer(
            rank=position,
            dealer_id=dealer.dealer_id,
            score=score,
            distance_km=distance_km,
            rate=dealer.rates[listing.category],
            verified=dealer.is_verified,
            reliability=round(reliability, 2),
            low_reliability=reliability < config.LOW_RELIABILITY_BELOW,
            breakdown=FactorPoints(*(round(v, 4) for v in (
                points.price, points.availability,
                points.reliability, points.distance))),
        ))

    # --- Soft warnings -----------------------------------------------------
    warnings = []
    if len(eligible) < config.FEW_DEALERS_BELOW:                      # BR-22
        warnings.append(SoftWarning(
            "FEW_DEALERS",
            f"Only {len(eligible)} dealer(s) matched. Try a larger search distance."))
    if any(r.low_reliability for r in ranked):                        # BR-21
        warnings.append(SoftWarning(
            "LOW_RELIABILITY", "Some dealers have a low reliability score."))

    return SearchResult(results=ranked, eligible_count=len(eligible),
                        removed=removed, warnings=warnings, profile=profile)