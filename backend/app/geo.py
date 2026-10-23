from math import asin, cos, radians, sin, sqrt

from app.models import Location


EARTH_RADIUS_KM = 6371.0


def haversine_km(a: Location, b: Location) -> float:
    lat1, lat2 = radians(a.lat), radians(b.lat)
    delta_lat = lat2 - lat1
    delta_lng = radians(b.lng - a.lng)
    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(haversine))


def travel_minutes(a: Location, b: Location) -> float:
    return haversine_km(a, b) / 25 * 60
