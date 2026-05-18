"""Compute stable fingerprints to dedupe listings across runs and sources."""

from __future__ import annotations

import hashlib
import re

from home_seek.db.models import Source

_WHITESPACE_RE = re.compile(r"\s+")
# Common Hebrew prefixes to strip when comparing addresses.
_ADDRESS_PREFIXES = ["רחוב ", "רח'", "רח׳", "שדרות ", "שד'", "שד׳"]  # noqa: RUF001


def _normalize_address(address: str | None) -> str:
    if not address:
        return ""
    addr = address.strip().lower()
    for prefix in _ADDRESS_PREFIXES:
        addr = addr.replace(prefix.lower(), "")
    return _WHITESPACE_RE.sub(" ", addr).strip()


def compute_fingerprint(
    *,
    source: Source,
    source_id: str | None,
    address: str | None = None,
    price: int | None = None,
    rooms: float | None = None,
) -> str:
    """Return a stable ``sha256`` hex digest identifying the listing.

    Prefers ``(source, source_id)`` when the source provides a stable id.
    Falls back to ``(normalized_address, price, rooms)`` otherwise - this is
    weaker but lets us dedupe sources that lack stable ids (e.g. Facebook posts).
    """
    if source_id:
        material = f"{source.value}::id::{source_id}"
    else:
        material = (
            f"{source.value}::soft::{_normalize_address(address)}|{price or ''}|{rooms or ''}"
        )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
