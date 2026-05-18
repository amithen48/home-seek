"""Decide whether a Listing matches an Area + SearchProfile."""

from __future__ import annotations

from dataclasses import dataclass

from home_seek.db.models import Area, Furnished, Listing, SearchProfile
from home_seek.geo.areas import point_in_area


@dataclass(frozen=True, slots=True)
class MatchReason:
    """Result of a match attempt - either ``matches=True`` or a reason string."""

    matches: bool
    reason: str = ""


def matches_profile(listing: Listing, area: Area, profile: SearchProfile) -> MatchReason:
    """Run the full filter chain. Returns the first failure reason, if any."""
    if not point_in_area(listing.lat, listing.lng, area):
        return MatchReason(False, "outside_area")

    if profile.min_price is not None and (listing.price or 0) < profile.min_price:
        return MatchReason(False, "below_min_price")
    if profile.max_price is not None and (listing.price or 0) > profile.max_price:
        return MatchReason(False, "above_max_price")

    if profile.min_rooms is not None and (listing.rooms or 0) < profile.min_rooms:
        return MatchReason(False, "below_min_rooms")
    if profile.max_rooms is not None and (listing.rooms or 0) > profile.max_rooms:
        return MatchReason(False, "above_max_rooms")

    if profile.min_sqm is not None and (listing.sqm or 0) < profile.min_sqm:
        return MatchReason(False, "below_min_sqm")
    if profile.max_sqm is not None and (listing.sqm or 0) > profile.max_sqm:
        return MatchReason(False, "above_max_sqm")

    if profile.floor_min is not None and (listing.floor or 0) < profile.floor_min:
        return MatchReason(False, "below_min_floor")
    if profile.floor_max is not None and (listing.floor or 0) > profile.floor_max:
        return MatchReason(False, "above_max_floor")

    if profile.requires_parking and not listing.parking:
        return MatchReason(False, "no_parking")
    if profile.requires_elevator and not listing.elevator:
        return MatchReason(False, "no_elevator")
    if profile.requires_balcony and not listing.balcony:
        return MatchReason(False, "no_balcony")
    if profile.allows_pets and listing.pets_allowed is False:
        return MatchReason(False, "no_pets")

    if profile.furnished is Furnished.YES and listing.furnished is False:
        return MatchReason(False, "not_furnished")
    if profile.furnished is Furnished.NO and listing.furnished is True:
        return MatchReason(False, "furnished")

    text = f"{listing.title or ''} {listing.description or ''}".lower()
    if profile.keywords_exclude:
        for kw in profile.keywords_exclude:
            if kw.lower() in text:
                return MatchReason(False, f"excluded_keyword:{kw}")
    if profile.keywords_include and not any(kw.lower() in text for kw in profile.keywords_include):
        return MatchReason(False, "missing_include_keyword")

    return MatchReason(True)
