"""pipeline.dedup unit tests."""

from __future__ import annotations

from home_seek.db.models import Source
from home_seek.pipeline.dedup import compute_fingerprint


def test_fingerprint_uses_source_id_when_present() -> None:
    fp1 = compute_fingerprint(source=Source.YAD2, source_id="abc")
    fp2 = compute_fingerprint(source=Source.YAD2, source_id="abc")
    assert fp1 == fp2
    assert len(fp1) == 64  # sha256 hex


def test_fingerprint_differs_per_source() -> None:
    assert compute_fingerprint(source=Source.YAD2, source_id="x") != compute_fingerprint(
        source=Source.MADLAN, source_id="x"
    )


def test_fingerprint_soft_match_normalizes_address() -> None:
    a = compute_fingerprint(
        source=Source.FACEBOOK,
        source_id=None,
        address="רחוב הירקון 10",
        price=7000,
        rooms=2.5,
    )
    b = compute_fingerprint(
        source=Source.FACEBOOK,
        source_id=None,
        address="רח' הירקון  10",
        price=7000,
        rooms=2.5,
    )
    assert a == b


def test_fingerprint_soft_match_differs_on_price() -> None:
    a = compute_fingerprint(
        source=Source.FACEBOOK, source_id=None, address="הירקון 10", price=7000, rooms=3
    )
    b = compute_fingerprint(
        source=Source.FACEBOOK, source_id=None, address="הירקון 10", price=7500, rooms=3
    )
    assert a != b
