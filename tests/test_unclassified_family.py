"""The W8 ``empty-geometry-store`` signature law (unit level).

Corpus-free: the law runs on synthetic byte buffers and a synthetic
``StoreSpan``; the end-to-end classification rides the committed
``geometry-empty-body`` fixture (``test_export_v1.py``'s corrupted-
variants table, where the native-Port parity pin also exercises it).
"""

from __future__ import annotations

import struct

from catpart.geometry import store
from catpart.geometry.errors import ExportError
from catpart.geometry.unclassified import (
    EMPTY_GEOMETRY_STORE,
    UNDECODED_VARIANT,
    body_signature,
    no_pool_error,
)


def _span(body_lo: int, body_hi: int) -> store.StoreSpan:
    return store.StoreSpan(
        block_start=0,
        origin=body_lo - 32,
        origin_kind=store.ORIGIN_KIND_HEADER,
        body_lo=body_lo,
        body_hi=body_hi,
        catalog_len=52,
    )


def _facet_record(marker: int = 0x42) -> bytes:
    """One well-formed 0x4A-family facet record (F9's byte law shape)."""
    refs = (0, 1, 2, 3)
    return (
        bytes([0x01, marker, 0x01, 0xFF])
        + struct.pack("<I", len(refs))
        + struct.pack("<fff", 0.0, 0.0, 1.0)
        + bytes([len(refs), 0, 0])
        + b"".join(struct.pack("<H", r) for r in refs)
    )


def test_empty_body_matches_the_signature_law() -> None:
    # A zero-marker body: no wrappers, no facet candidates -> the law
    # fires (the CAA fixture cluster's signature, 10/10 corpus files).
    data = b"\x00" * 64
    sig = body_signature(data, 16, 48)
    assert sig.body_bytes == 32
    assert sig.pool_groups == 0
    assert sig.kinds == ()
    assert sig.facet_candidates == 0
    assert sig.is_empty_payload
    assert sig.signature == "body=32 pools=0 kinds=- facet-cands=0"


def test_wrapper_marker_keeps_undecoded_variant() -> None:
    # ANY wrapper marker (here a non-pool, non-composite 01 03
    # sub-kind) is a variant gap, not an empty payload (fail-closed).
    data = pool_wrapper_body()
    sig = body_signature(data, 0, len(data))
    assert sig.kinds == (b"\x01\x03",)
    assert not sig.is_empty_payload
    assert sig.signature == "body=%d pools=0 kinds=0103 facet-cands=0" % len(data)


def pool_wrapper_body() -> bytes:
    body = b"\x10\x24\x04\xff\xff\x00\x00\x00" + b"\x01\x03" + b"\x02\x00\x00\x00"
    return body + b"\x00" * 8


def test_facet_candidate_keeps_undecoded_variant() -> None:
    # A body carrying a parseable facet record has a payload marker:
    # the law does not fire (the stage-13 no-node negative's shape).
    body = _facet_record()
    data = body + b"\x00" * 8
    sig = body_signature(data, 0, len(data))
    assert sig.facet_candidates == 1
    assert not sig.is_empty_payload


def test_no_pool_error_names_the_empty_payload_class() -> None:
    data = b"\x00" * 96
    error = no_pool_error(data, _span(32, 64), kinds=[])
    assert isinstance(error, ExportError)
    assert error.error_class == EMPTY_GEOMETRY_STORE
    assert "no geometry payload of any pinned kind" in error.detail
    assert "body=32" in error.detail


def test_no_pool_error_keeps_the_original_variant_error() -> None:
    # A body with a wrapper marker: the original G2 P8 error verbatim
    # (detail byte-identical to the pre-W8 raise, row-identical).
    data = pool_wrapper_body()
    error = no_pool_error(data, _span(0, len(data)), kinds=[b"\x01\x03"])
    assert error.error_class == UNDECODED_VARIANT
    assert error.detail.startswith(
        "no 01 06 vertex pool decoded from the store body"
    )


def test_signature_string_is_stable_for_the_census_csv() -> None:
    # The cluster signature string the census tool hashes (stable field
    # order; '-' names an empty kinds list).
    data = b"\x00" * 2575
    sig = body_signature(data, 0, 2575)
    assert sig.signature == "body=2575 pools=0 kinds=- facet-cands=0"
