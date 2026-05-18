"""Format a Listing+Area context into a Telegram-ready message body."""

from __future__ import annotations

from home_seek.db.models import Area, Listing


def _yes_no(flag: bool | None) -> str:
    if flag is None:
        return "?"
    return "✓" if flag else "✗"


def _format_price(price: int | None) -> str:
    if price is None:
        return "—"
    return f"{price:,} ₪".replace(",", ",")


def format_listing_message(listing: Listing, area: Area) -> str:
    rooms_part = f"{listing.rooms:g} חדרים" if listing.rooms else "? חדרים"
    sqm_part = f'{listing.sqm} מ"ר' if listing.sqm else '? מ"ר'

    floor_part = ""
    if listing.floor is not None:
        if listing.total_floors is not None:
            floor_part = f"קומה {listing.floor}/{listing.total_floors}"
        else:
            floor_part = f"קומה {listing.floor}"

    amenities = (
        f"מעלית {_yes_no(listing.elevator)} | חניה {_yes_no(listing.parking)} | "
        f"מרפסת {_yes_no(listing.balcony)}"
    )

    addr_bits = [p for p in [listing.address, listing.neighborhood, listing.city] if p]
    address = ", ".join(addr_bits) if addr_bits else "—"

    desc = (listing.description or "").strip()
    if len(desc) > 240:
        desc = desc[:237] + "…"

    parts: list[str] = [
        f"🏠 דירה חדשה ב{area.name}",
        "",
        f"💰 {_format_price(listing.price)}",
        f"🛏 {rooms_part} | 📐 {sqm_part}",
    ]
    if floor_part:
        parts.append(f"🏢 {floor_part} | {amenities}")
    else:
        parts.append(f"🏢 {amenities}")
    parts.append(f"📍 {address}")

    if desc:
        parts.extend(["", f"“{desc}”"])

    parts.extend(["", f"🔗 {listing.url}"])
    if listing.lat is not None and listing.lng is not None:
        parts.append(f"🗺 https://www.google.com/maps?q={listing.lat},{listing.lng}")

    return "\n".join(parts)
