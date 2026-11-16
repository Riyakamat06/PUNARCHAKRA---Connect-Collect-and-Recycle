"""
duplicate_service.py  -  Engine 2 (Logic and Rule)  -  duplicate listing detection.

WHAT IT DOES
    Warns the seller when a new listing looks like one the same seller posted a
    moment ago (for example the "Post" button pressed twice).

WHEN TWO LISTINGS COUNT AS DUPLICATES
    Same seller, same category, almost the same place (pins agree to 3 decimals,
    about 100 metres), almost the same weight (rounded to the nearest 5 kg),
    posted within the last 24 hours. The 24 hours and the 5 kg are PROVISIONAL.

HOW (data structure: hash map)
    Each recent listing is turned into a "key" (a tuple of the values above). The
    keys are stored in a dictionary, so checking a new listing is ONE lookup
    instead of comparing it with every old listing.

COMPLEXITY
    Check one new listing: O(1) average, after the map is built.
    Build the map from m recent listings of one seller: O(m).

ASSUMPTION (please confirm): a duplicate is a WARNING that the seller can ignore,
not a hard block, because a seller may really have two similar loads.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, Optional

from .. import config


@dataclass(frozen=True)
class ListingRecord:
    """The few fields of an existing listing that the check needs."""
    listing_id: int
    seller_id: int
    category: str
    lat: float
    lon: float
    weight_kg: float
    posted_at: datetime


def duplicate_key(seller_id: int, category: str, lat: float, lon: float,
                  weight_kg: float) -> tuple:
    """The fingerprint of a listing. Two listings with equal keys are 'the same'."""
    step = config.DUPLICATE_WEIGHT_STEP_KG
    return (seller_id, category,
            round(lat, config.DUPLICATE_COORD_DECIMALS),
            round(lon, config.DUPLICATE_COORD_DECIMALS),
            round(weight_kg / step) * step)


def build_index(recent: Iterable[ListingRecord]) -> dict:
    """Group the recent listings by fingerprint. O(m)."""
    index = {}
    for rec in recent:
        key = duplicate_key(rec.seller_id, rec.category, rec.lat, rec.lon, rec.weight_kg)
        index.setdefault(key, []).append(rec)
    return index


def find_duplicate(index: dict, seller_id: int, category: str, lat: float,
                   lon: float, weight_kg: float, now: datetime) -> Optional[ListingRecord]:
    """Return the earlier listing this one duplicates, or None. O(1) average."""
    window_start = now - timedelta(hours=config.DUPLICATE_WINDOW_HOURS)
    key = duplicate_key(seller_id, category, lat, lon, weight_kg)
    matches = [rec for rec in index.get(key, []) if window_start <= rec.posted_at <= now]
    return max(matches, key=lambda rec: rec.posted_at) if matches else None