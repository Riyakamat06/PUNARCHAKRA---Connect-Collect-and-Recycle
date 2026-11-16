"""
config.py  -  every rule number of Engine 2 in ONE place.

WHY ONE FILE
    The decisions of the project (limits, weights, thresholds) must not be
    scattered through the code. When the professor or the dealer/seller
    interviews change a number, you edit it here and nowhere else.

PROVISIONAL means: agreed for now, but to be confirmed after the interviews.
FIXED means: a design decision already agreed by the team.
"""

# --- Categories (FIXED: exactly five) --------------------------------------
CATEGORIES = ("metal", "wood", "e-waste", "glass", "plastic")

# Categories that only VERIFIED dealers may handle (FIXED: e-waste).
VERIFIED_ONLY_CATEGORIES = frozenset({"e-waste"})

# --- Search limits ----------------------------------------------------------
MIN_SEARCH_KM = 1            # FIXED: the seller chooses 1 to 50 km
MAX_SEARCH_KM = 50
MAX_LISTING_WEIGHT_KG = 1000  # PROVISIONAL

# --- Ranking (FIXED) --------------------------------------------------------
TOP_K = 10                    # the screen shows the best 10 dealers

# Weight profiles: points out of 100 given to each factor.
#   "best_price"      is the DEFAULT profile
#   "nearest_trusted" is the second profile used for the B2 comparison
WEIGHT_PROFILES = {
    "best_price":      {"price": 40, "availability": 25, "reliability": 20, "distance": 15},
    "nearest_trusted": {"price": 20, "availability": 15, "reliability": 30, "distance": 35},
}
DEFAULT_PROFILE = "best_price"
RANKING_FACTORS = ("price", "availability", "reliability", "distance")

# --- Reliability (FIXED) ----------------------------------------------------
NEW_DEALER_PICKUPS = 3        # fewer finished pickups than this = "new dealer"
NEW_DEALER_RELIABILITY = 50   # new dealers get a neutral score
# Rating (1 to 5) is multiplied by this to bring it to a 0-100 scale.
RATING_TO_100 = 20

# --- Soft warnings (FIXED): they warn, they never block ---------------------
LOW_RELIABILITY_BELOW = 50    # BR-21
FEW_DEALERS_BELOW = 3         # BR-22

# --- Weight check (PROVISIONAL) ---------------------------------------------
MISMATCH_LIMIT_PERCENT = 10   # BR-20: difference above this goes to the admin

# --- Duplicate listing check (PROVISIONAL) ----------------------------------
DUPLICATE_WINDOW_HOURS = 24
DUPLICATE_WEIGHT_STEP_KG = 5      # weights are compared rounded to nearest 5 kg
DUPLICATE_COORD_DECIMALS = 3      # pins compared to about 100 metres