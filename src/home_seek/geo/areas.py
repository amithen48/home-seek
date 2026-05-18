"""Geographic predicates: is a coordinate inside an Area?

We support two area shapes (see ``Area.geometry_type``):

* ``RADIUS``  - center point + radius in meters (haversine distance).
* ``POLYGON`` - arbitrary GeoJSON ``Polygon`` with ``[lng, lat]`` coordinate
  pairs (the GeoJSON convention).
"""

from __future__ import annotations

import math
from typing import Any, cast

from shapely.geometry import Point, Polygon, shape

from home_seek.db.models import Area, GeometryType

_EARTH_RADIUS_METERS = 6_371_000.0


def distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two coordinates, in meters (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_RADIUS_METERS * math.asin(math.sqrt(a))


def _build_polygon(polygon_geojson: dict[str, object]) -> Polygon:
    """Build a shapely Polygon from a GeoJSON dict.

    Accepts either a bare ``Polygon`` geometry or a ``Feature`` wrapper.
    """
    geom = polygon_geojson
    if geom.get("type") == "Feature":
        geom = cast(dict[str, object], geom.get("geometry", {}))
    return cast(Polygon, shape(cast(Any, geom)))


def point_in_area(lat: float | None, lng: float | None, area: Area) -> bool:
    """Return True iff (lat, lng) falls inside the given area.

    Returns False for missing coordinates rather than raising - upstream callers
    treat missing geo data as "doesn't match" rather than as an error.
    """
    if lat is None or lng is None:
        return False

    if area.geometry_type is GeometryType.RADIUS:
        if area.center_lat is None or area.center_lng is None or area.radius_meters is None:
            return False
        return distance_meters(lat, lng, area.center_lat, area.center_lng) <= area.radius_meters

    if area.geometry_type is GeometryType.POLYGON:
        if not area.polygon_json:
            return False
        polygon = _build_polygon(area.polygon_json)
        return bool(polygon.contains(Point(lng, lat)))

    return False
