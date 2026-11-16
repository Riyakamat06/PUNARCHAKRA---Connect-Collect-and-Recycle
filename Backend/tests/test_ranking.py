"""
test_ranking.py  -  the 20 ranking scenarios (plus 3 extra checks) for Engine 2.

RUN (from the backend folder):   python -m pytest -v

HOW THE EXPECTED NUMBERS WERE MADE
    Every expected score was worked out BY HAND from the agreed formulas (the
    working is written above each test), not copied from the code's output. If a
    rule or weight changes, redo the hand calculation and update the number.

THE 20 SCENARIOS
    Filters 6 | Scoring 5 | Ties 2 | Profiles 2 | Weight and payment 3 | Other 2
    (the 3 weight-and-payment scenarios are in test_weight_service.py)
"""

import random

import pytest

from app import config
from app.errors import InvalidRequest, WeightsInvalid
from app.services.min_heap import MinHeap
from app.services.ranking_service import distance_score, rank_dealers

from .factories import ids, make_dealer, make_listing


# ===========================================================================
# GROUP 1 - HARD FILTERS (6 scenarios)
# ===========================================================================

def test_f1_dealer_not_accepting_the_material_is_removed():
    # The dealer only buys plastic, the listing is metal.
    out = rank_dealers([make_dealer(1, rates={"plastic": 10})], make_listing())
    assert out.no_dealer_found and out.removed.material == 1


def test_f2_dealer_beyond_the_sellers_search_distance_is_removed():
    # 12 km away, the seller only searches 10 km.
    out = rank_dealers([make_dealer(1, dist_km=12)], make_listing(search_km=10))
    assert out.no_dealer_found and out.removed.distance == 1


def test_f3_dealer_beyond_its_own_service_radius_is_removed():
    # 5 km is inside the seller's 10 km, but the dealer only travels 3 km.
    out = rank_dealers([make_dealer(1, dist_km=5, radius=3)], make_listing())
    assert out.no_dealer_found and out.removed.distance == 1


def test_f4_dealer_with_too_little_capacity_is_removed_but_equal_capacity_passes():
    # Capacity 50 kg < listing 100 kg: removed. Capacity exactly 100 kg: kept.
    out = rank_dealers([make_dealer(1, capacity=50), make_dealer(2, capacity=100)],
                       make_listing(weight=100))
    assert out.removed.capacity == 1 and ids(out) == [2]


def test_f5_unverified_dealer_is_removed_for_ewaste():
    dealer = make_dealer(1, rates={"e-waste": 20}, verified=False)
    out = rank_dealers([dealer], make_listing(category="e-waste"))
    assert out.no_dealer_found and out.removed.verification == 1


def test_f6_verified_dealer_is_kept_for_ewaste_and_shows_the_badge():
    dealer = make_dealer(1, rates={"e-waste": 20}, verified=True)
    out = rank_dealers([dealer], make_listing(category="e-waste"))
    assert ids(out) == [1] and out.results[0].verified is True


# ===========================================================================
# GROUP 2 - SCORING (5 scenarios)
# ===========================================================================

def test_s1_three_dealers_are_scored_and_ordered_by_hand_calculation():
    # Profile best_price: price 40, availability 25, reliability 20, distance 15.
    # All three are new dealers (reliability 50) open on Monday (availability 100).
    # Highest rate = 42, so price scores are 38/42, 42/42, 40/42 (x100).
    #   A (Rs38, 2 km): price 90.476, dist 80 -> 36.190 + 25 + 10 + 12 = 83.190
    #   B (Rs42, 6 km): price 100,    dist 40 -> 40     + 25 + 10 + 6  = 81.000
    #   C (Rs40, 4 km): price 95.238, dist 60 -> 38.095 + 25 + 10 + 9  = 82.095
    dealers = [make_dealer(1, 2, 38), make_dealer(2, 6, 42), make_dealer(3, 4, 40)]
    out = rank_dealers(dealers, make_listing())
    score = {r.dealer_id: r.score for r in out.results}
    assert ids(out) == [1, 3, 2]                      # A, C, B
    assert score[1] == pytest.approx(83.190, abs=0.01)
    assert score[2] == pytest.approx(81.000, abs=0.01)
    assert score[3] == pytest.approx(82.095, abs=0.01)


def test_s2_distance_score_is_100_at_zero_km_and_0_at_the_limit():
    assert distance_score(0, 10) == 100
    assert distance_score(10, 10) == 0
    assert distance_score(5, 10) == 50
    # A dealer EXACTLY on the search limit is still eligible (the limit is inclusive).
    out = rank_dealers([make_dealer(1, dist_km=10)], make_listing(search_km=10))
    assert ids(out) == [1] and out.results[0].breakdown.distance == 0


def test_s3_dealer_closed_on_the_preferred_day_gets_zero_availability():
    # Open Tuesday to Sunday (1..6); the seller wants Monday (0).
    dealer = make_dealer(1, open_days={1, 2, 3, 4, 5, 6})
    assert rank_dealers([dealer], make_listing()).results[0].breakdown.availability == 0


def test_s4_new_dealer_gets_reliability_50_whatever_the_rest():
    # 2 finished pickups is fewer than 3. Contribution = 20 x 50 / 100 = 10 points.
    dealer = make_dealer(1, pickups=2, completion=100, rating=5)
    item = rank_dealers([dealer], make_listing()).results[0]
    assert item.reliability == 50
    assert item.breakdown.reliability == pytest.approx(10)


def test_s5_reliability_formula_and_breakdown_adds_up_to_the_score():
    # 10 pickups, completion 90%, rating 4.5 -> 0.5*90 + 0.5*(4.5*20) = 45 + 45 = 90.
    # One dealer: price 100, distance 0 km -> 100, open Monday -> 100.
    #   best_price: 40 + 25 + 20*90/100 (=18) + 15 = 98.0
    dealer = make_dealer(1, dist_km=0, pickups=10, completion=90, rating=4.5)
    item = rank_dealers([dealer], make_listing()).results[0]
    b = item.breakdown
    assert item.reliability == 90
    assert item.score == pytest.approx(98.0, abs=0.01)
    assert b.price + b.availability + b.reliability + b.distance == pytest.approx(item.score, abs=0.001)


# ===========================================================================
# GROUP 3 - TIES (2 scenarios). Custom weights make a REAL tie.
# ===========================================================================

def test_t1_equal_scores_are_broken_by_higher_reliability():
    # Only distance counts (100). Both dealers are 4 km away -> identical score.
    # Dealer 2 has reliability 90 against 50, so it wins although listed second.
    only_distance = {"price": 0, "availability": 0, "reliability": 0, "distance": 100}
    d1 = make_dealer(1, dist_km=4)
    d2 = make_dealer(2, dist_km=4, pickups=10, completion=90, rating=4.5)
    out = rank_dealers([d1, d2], make_listing(), weights=only_distance)
    assert out.results[0].score == out.results[1].score
    assert ids(out) == [2, 1]


def test_t2_equal_score_and_reliability_are_broken_by_shorter_distance():
    # Only price counts. Same rate -> same score; both new -> same reliability.
    # The nearer dealer (3 km, id 2) must beat the farther one (7 km, id 1).
    only_price = {"price": 100, "availability": 0, "reliability": 0, "distance": 0}
    out = rank_dealers([make_dealer(1, dist_km=7, rate=40),
                        make_dealer(2, dist_km=3, rate=40)],
                       make_listing(), weights=only_price)
    assert out.results[0].score == out.results[1].score
    assert ids(out) == [2, 1]


# ===========================================================================
# GROUP 4 - WEIGHT PROFILES (2 scenarios)
#   X: Rs50, 5 km, new dealer (reliability 50).
#   Y: Rs30, 1 km, reliability 90 (10 pickups, 90%, rating 4.5). Both open Monday.
#   Highest rate 50 -> price X 100, Y 60.  Distance -> X 50, Y 90.
# ===========================================================================

def _profile_dealers():
    return [make_dealer(1, dist_km=5, rate=50),
            make_dealer(2, dist_km=1, rate=30, pickups=10, completion=90, rating=4.5)]


def test_p1_best_price_profile_puts_the_higher_rate_first():
    # X = .40*100 + .25*100 + .20*50 + .15*50 = 40 + 25 + 10 + 7.5  = 82.5
    # Y = .40*60  + .25*100 + .20*90 + .15*90 = 24 + 25 + 18 + 13.5 = 80.5
    out = rank_dealers(_profile_dealers(), make_listing(), profile="best_price")
    assert ids(out) == [1, 2]
    assert out.results[0].score == pytest.approx(82.5, abs=0.01)
    assert out.results[1].score == pytest.approx(80.5, abs=0.01)


def test_p2_nearest_and_trusted_profile_puts_the_close_reliable_dealer_first():
    # Weights 20/15/30/35.
    # X = .20*100 + .15*100 + .30*50 + .35*50 = 20 + 15 + 15 + 17.5 = 67.5
    # Y = .20*60  + .15*100 + .30*90 + .35*90 = 12 + 15 + 27 + 31.5 = 85.5
    out = rank_dealers(_profile_dealers(), make_listing(), profile="nearest_trusted")
    assert ids(out) == [2, 1]
    assert out.results[0].score == pytest.approx(85.5, abs=0.01)
    assert out.results[1].score == pytest.approx(67.5, abs=0.01)


# ===========================================================================
# GROUP 6 - OTHER RULES (2 scenarios)
# ===========================================================================

def test_o1_fewer_than_three_matches_gives_a_soft_warning_but_still_ranks():
    two = rank_dealers([make_dealer(1), make_dealer(2)], make_listing())
    assert [w.code for w in two.warnings] == ["FEW_DEALERS"]
    assert len(two.results) == 2                          # the warning never blocks
    three = rank_dealers([make_dealer(i) for i in (1, 2, 3)], make_listing())
    assert all(w.code != "FEW_DEALERS" for w in three.warnings)


def test_o2_low_reliability_dealer_is_flagged_but_not_removed():
    # 5 pickups, completion 20%, rating 1 -> 0.5*20 + 0.5*(1*20) = 10 + 10 = 20 (< 50).
    weak = make_dealer(1, pickups=5, completion=20, rating=1)
    out = rank_dealers([weak, make_dealer(2), make_dealer(3)], make_listing())
    flagged = {r.dealer_id: r.low_reliability for r in out.results}
    assert flagged[1] is True and flagged[2] is False
    assert any(w.code == "LOW_RELIABILITY" for w in out.warnings)


# ===========================================================================
# EXTRA CHECKS
# ===========================================================================

def test_x1_heap_keeps_exactly_the_best_ten_of_many():
    rng = random.Random(7)
    numbers = [rng.random() for _ in range(300)]
    heap = MinHeap(10)
    for n in numbers:
        heap.push_top_k((n,), n)
    assert [p for _, p in heap.best_first()] == sorted(numbers, reverse=True)[:10]


def test_x2_ranking_returns_top_ten_and_flags_more_than_ten():
    dealers = [make_dealer(i, dist_km=1 + i * 0.1, rate=30 + i) for i in range(1, 26)]
    out = rank_dealers(dealers, make_listing())
    assert len(out.results) == config.TOP_K == 10
    assert out.eligible_count == 25 and out.more_than_top_k is True
    assert [r.rank for r in out.results] == list(range(1, 11))
    assert out.to_dict()["results"][0]["breakdown"]["price"] > 0      # JSON-ready


def test_x3_bad_weights_profile_or_k_are_rejected():
    with pytest.raises(InvalidRequest):
        rank_dealers([make_dealer(1)], make_listing(), profile="cheapest")
    with pytest.raises(WeightsInvalid):
        rank_dealers([make_dealer(1)], make_listing(),
                     weights={"price": 50, "availability": 10, "reliability": 10, "distance": 10})
    with pytest.raises(InvalidRequest):
        rank_dealers([make_dealer(1)], make_listing(), k=0)
    assert all(sum(p.values()) == 100 for p in config.WEIGHT_PROFILES.values())