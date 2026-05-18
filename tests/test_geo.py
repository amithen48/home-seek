"""geo.areas unit tests."""

from __future__ import annotations

from home_seek.db.models import Area, GeometryType
from home_seek.geo.areas import distance_meters, point_in_area


def test_distance_meters_known_pair() -> None:
    # Tel Aviv → Jerusalem ≈ 54 km. Loose bound is enough.
    d = distance_meters(32.0853, 34.7818, 31.7683, 35.2137)
    assert 50_000 < d < 60_000


def test_point_in_radius_area_hits_when_inside() -> None:
    area = Area(
        name="t",
        city="c",
        geometry_type=GeometryType.RADIUS,
        center_lat=32.0566,
        center_lng=34.7657,
        radius_meters=500,
    )
    assert point_in_area(32.0567, 34.7658, area) is True


def test_point_in_radius_area_misses_when_outside() -> None:
    area = Area(
        name="t",
        city="c",
        geometry_type=GeometryType.RADIUS,
        center_lat=32.0566,
        center_lng=34.7657,
        radius_meters=200,
    )
    assert point_in_area(32.10, 34.80, area) is False


def test_point_in_polygon_area() -> None:
    area = Area(
        name="t",
        city="c",
        geometry_type=GeometryType.POLYGON,
        polygon_json={
            "type": "Polygon",
            "coordinates": [
                [
                    [34.81, 32.08],
                    [34.83, 32.08],
                    [34.82, 32.09],
                    [34.81, 32.08],
                ]
            ],
        },
    )
    # Roughly the centroid.
    assert point_in_area(32.083, 34.82, area) is True
    # Far away.
    assert point_in_area(32.05, 34.77, area) is False


def test_missing_coords_never_match() -> None:
    area = Area(
        name="t",
        city="c",
        geometry_type=GeometryType.RADIUS,
        center_lat=32.0,
        center_lng=34.0,
        radius_meters=10_000,
    )
    assert point_in_area(None, 34.0, area) is False
    assert point_in_area(32.0, None, area) is False
