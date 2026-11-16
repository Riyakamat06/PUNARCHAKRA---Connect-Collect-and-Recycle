"""
test_duplicate_and_models.py  -  duplicate listing check and input validation.
"""

from datetime import datetime, timedelta

import pytest

from app.domain.models import Dealer, Listing
from app.errors import (InvalidCategory, InvalidDealerData, InvalidLocation,
                        InvalidRadius, InvalidWeight)
from app.services.duplicate_service import (ListingRecord, build_index,
                                            find_duplicate)

from .factories import BASE_LAT, BASE_LON, MONDAY, make_dealer

NOW = datetime(2026, 11, 16, 12, 0)


def _record(listing_id=1, seller=7, category="metal", weight=100, hours_ago=2):
    return ListingRecord(listing_id, seller, category, BASE_LAT, BASE_LON,
                         weight, NOW - timedelta(hours=hours_ago))


# ---- duplicate detection ---------------------------------------------------

def test_same_listing_within_24_hours_is_a_duplicate():
    index = build_index([_record(1)])
    # 102 kg rounds to the same 5 kg step as 100 kg, so it still matches.
    found = find_duplicate(index, 7, "metal", BASE_LAT, BASE_LON, 102, NOW)
    assert found is not None and found.listing_id == 1


def test_different_seller_category_weight_or_old_listing_is_not_a_duplicate():
    index = build_index([_record(1)])
    assert find_duplicate(index, 8, "metal", BASE_LAT, BASE_LON, 100, NOW) is None   # other seller
    assert find_duplicate(index, 7, "glass", BASE_LAT, BASE_LON, 100, NOW) is None   # other category
    assert find_duplicate(index, 7, "metal", BASE_LAT, BASE_LON, 130, NOW) is None   # other weight
    old = build_index([_record(2, hours_ago=30)])
    assert find_duplicate(old, 7, "metal", BASE_LAT, BASE_LON, 100, NOW) is None     # older than 24 h


# ---- input validation ------------------------------------------------------

def test_listing_rejects_bad_values():
    good = dict(category="metal", weight_kg=50, lat=15.3, lon=75.1,
                search_km=10, preferred_date=MONDAY)
    assert Listing(**good)
    with pytest.raises(InvalidCategory):
        Listing(**{**good, "category": "paper"})
    for bad_weight in (0, -5, 1001):
        with pytest.raises(InvalidWeight):
            Listing(**{**good, "weight_kg": bad_weight})
    for bad_radius in (0, 0.5, 51):
        with pytest.raises(InvalidRadius):
            Listing(**{**good, "search_km": bad_radius})
    with pytest.raises(InvalidLocation):
        Listing(**{**good, "lat": 95})


def test_dealer_rejects_bad_values_and_is_read_only():
    with pytest.raises(InvalidDealerData):
        make_dealer(1, radius=0)
    with pytest.raises(InvalidDealerData):
        make_dealer(1, rate=-4)
    with pytest.raises(InvalidDealerData):
        make_dealer(1, open_days={9})
    with pytest.raises(InvalidDealerData):
        make_dealer(1, rating=7)
    dealer = make_dealer(1)
    with pytest.raises(Exception):               # frozen: cannot be changed afterwards
        dealer.is_verified = True
    with pytest.raises(TypeError):               # rates are read-only too
        dealer.rates["metal"] = 999