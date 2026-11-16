"""
factories.py  -  helpers that build the fixed TEST WORLD used by all test files.

THE FIXED TEST WORLD
    * The seller's pin is in Hubballi. Dealers are placed due NORTH of the
      seller, so the distance between them is exactly the number we choose.
    * The listing is 100 kg of metal, search distance 10 km, preferred pickup
      date Monday 16 Nov 2026 (weekday 0).
    * Unless a test says otherwise, a dealer is open every day, is NEW (fewer
      than 3 finished pickups, so reliability = 50), is not verified and has a
      very large radius and capacity.
"""

from datetime import date

from app.domain.models import Dealer, Listing

BASE_LAT, BASE_LON = 15.3647, 75.1240
KM_PER_DEGREE_LAT = 111.1949          # 6371 km x pi / 180
MONDAY = date(2026, 11, 16)           # weekday() == 0


def make_dealer(dealer_id, dist_km=2.0, rate=40.0, rates=None, radius=500,
                capacity=1000, verified=False, open_days=None,
                pickups=0, completion=0.0, rating=None):
    """A dealer placed dist_km due north of the seller."""
    return Dealer(
        dealer_id=dealer_id,
        lat=BASE_LAT + dist_km / KM_PER_DEGREE_LAT,
        lon=BASE_LON,
        service_radius_km=radius,
        capacity_kg=capacity,
        is_verified=verified,
        rates=rates if rates is not None else {"metal": rate},
        open_days=frozenset(open_days if open_days is not None else range(7)),
        finished_pickups=pickups,
        completion_pct=completion,
        avg_rating=rating,
    )


def make_listing(category="metal", weight=100, search_km=10, when=MONDAY):
    return Listing(category=category, weight_kg=weight, lat=BASE_LAT,
                   lon=BASE_LON, search_km=search_km, preferred_date=when)


def ids(result):
    """Dealer ids of a SearchResult, in rank order."""
    return [item.dealer_id for item in result.results]