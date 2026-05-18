"""pipeline.filter unit tests."""

from __future__ import annotations

from home_seek.db.models import (
    Area,
    Furnished,
    GeometryType,
    Listing,
    SearchProfile,
    Source,
)
from home_seek.pipeline.filter import matches_profile


def _area() -> Area:
    return Area(
        name="t",
        city="c",
        geometry_type=GeometryType.RADIUS,
        center_lat=32.0566,
        center_lng=34.7657,
        radius_meters=2_000,
    )


def _listing(**overrides: object) -> Listing:
    base = {
        "fingerprint": "x",
        "source": Source.YAD2,
        "url": "https://example.com",
        "title": "t",
        "price": 7000,
        "rooms": 3.0,
        "sqm": 70,
        "floor": 2,
        "total_floors": 4,
        "lat": 32.0566,
        "lng": 34.7657,
        "parking": True,
        "elevator": True,
        "balcony": True,
        "furnished": False,
        "pets_allowed": True,
        "description": "dsc",
        "is_active": True,
    }
    base.update(overrides)
    return Listing(**base)  # type: ignore[arg-type]


def _profile(**overrides: object) -> SearchProfile:
    base = {
        "area_id": 1,
        "name": "p",
        "furnished": Furnished.ANY,
        "requires_parking": False,
        "requires_elevator": False,
        "requires_balcony": False,
        "allows_pets": False,
        "active": True,
    }
    base.update(overrides)
    return SearchProfile(**base)  # type: ignore[arg-type]


def test_passes_basic_match() -> None:
    res = matches_profile(_listing(), _area(), _profile(max_price=8000))
    assert res.matches is True


def test_rejects_out_of_geo() -> None:
    far = _listing(lat=31.5, lng=35.2)
    res = matches_profile(far, _area(), _profile())
    assert not res.matches
    assert res.reason == "outside_area"


def test_rejects_above_max_price() -> None:
    res = matches_profile(_listing(price=9000), _area(), _profile(max_price=8000))
    assert not res.matches
    assert res.reason == "above_max_price"


def test_rejects_required_parking_missing() -> None:
    res = matches_profile(_listing(parking=False), _area(), _profile(requires_parking=True))
    assert not res.matches
    assert res.reason == "no_parking"


def test_rejects_excluded_keyword() -> None:
    res = matches_profile(
        _listing(description="דירת שותפים מצוינת"),
        _area(),
        _profile(keywords_exclude=["שותפים"]),
    )
    assert not res.matches
    assert res.reason.startswith("excluded_keyword")


def test_furnished_required_but_not_present() -> None:
    res = matches_profile(_listing(furnished=False), _area(), _profile(furnished=Furnished.YES))
    assert not res.matches
    assert res.reason == "not_furnished"
