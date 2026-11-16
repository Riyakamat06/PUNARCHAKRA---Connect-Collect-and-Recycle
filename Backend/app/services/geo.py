"""
geo.py  -  Engine 2 (Logic and Rule)  -  distance between two map pins.

WHAT THIS FILE DOES
    Gives one function, haversine_km(), that tells how many kilometres apart
    two points on the earth are, when each point is a (latitude, longitude) pin.
    The seller and the dealer both drop a pin on the OpenStreetMap map, so
    every distance in the ranking comes from here.

WHY HAVERSINE
    The earth is round, so we cannot use the flat school formula
    sqrt(dx^2 + dy^2). Haversine is the standard formula for the straight-line
    distance over the earth's surface ("as the crow flies"). It is not the road
    distance, and that is fine for ranking.

COMPLEXITY
    O(1): a fixed number of maths steps for any pair of points.
"""

from math import radians, sin, cos, asin, sqrt

# Average radius of the earth in kilometres.
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Return the distance in km between pin 1 (lat1, lon1) and pin 2 (lat2, lon2).

    Latitude and longitude come in as degrees (for example 15.36, 75.12 is
    near Hubballi). Maths functions need radians, so we convert first.
    """
    # Step 1: convert degrees to radians.
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))

    # Step 2: how far apart the pins are in each direction.
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1

    # Step 3: the haversine formula itself.
    # "a" is the squared half-chord length between the two points.
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2

    # Step 4: turn "a" into an angle, then into kilometres.
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))