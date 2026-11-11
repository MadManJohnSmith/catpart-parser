"""Facet record tiling: the clean-store width context on gap edges (P3-B, #35).

2026-11-10 re-scope: the greedy scanner's gap-edge tie-break
(``end < nxt``) no longer unconditionally prefers the narrower width. A
pre-pass over the store's exact-tile records (those whose end equals
the next header position) votes their reference width; a unanimous vote
wins the gap-edge tie-break, so a cluster-final u16be record before a
gap or a 5-byte-form header keeps its width instead of truncating to
the u8 half-read. Mixed votes (or no exact tiles) keep the historical
width-1 preference, so pure-w1 stores stay byte-identical.

2026-11-10 third re-scope (final): the store-width context is BOUNDED
to the clean store class — no ``01 02`` edge group AND no trailer
opener, the class where the cluster-final truncation was verified. The
store decode already knows the class; it passes one flag down to
:func:`scan_facets` (the exporter passes the knowledge from the
composite-space check it already performs). Composite stores — and any
caller that does not pass the flag, the fail-safe default — keep the
historical unconditional width-1 gap behavior exactly, until G6 decodes
the composite index space from first principles.

The tests are corpus-free: every store body is hand-assembled from the
F1 grammar (``01 <mk> <ty> ff [u32le n][k counts][n refs]``, marker
0x41 — a strip family, no normal payload). Reference payloads avoid the
coincidence classes that add spurious (width, k) variants: u16be refs
carry a non-zero high byte (the k+1 count window then never sums to n),
and no ref byte is ``01``-before-``[41-4f]``-before-``ff`` (no false
STRIP_RE headers). The golden export contract — the corpus-equivalent
byte-identity check through the export seam — lives in
``test_export_v1.py`` and runs unchanged.
"""

from __future__ import annotations

import struct

import pytest

from catpart.geometry.export import ExportError, _export_store
from catpart.geometry.facets import scan_facets
from catpart.geometry.store import StoreSpan
from fixtures_gen import (
    NESTED_EDGE_SUBKIND,
    NESTED_FULL_WRAP,
    NESTED_POOL_SUBKIND,
    NESTED_VREC,
)


def u32le(value: int) -> bytes:
    return struct.pack("<I", value)


def u16be_refs(values: tuple[int, ...]) -> bytes:
    return b"".join(struct.pack(">H", v) for v in values)


def facet_record(mk: int, ty: int, n: int, counts: tuple[int, ...], refs: bytes) -> bytes:
    """One 4-byte-form F1 record (0x41 carries no normal payload)."""
    out = bytearray(bytes((0x01, mk, ty, 0xFF)))
    out += u32le(n)
    out += bytes(counts)
    out += refs
    return bytes(out)


def five_byte_record(mk: int, ty: int, b3: int, tail: bytes) -> bytes:
    """One 5-byte-form F1 record (``01 <mk> <ty> <b3> ff ...``).

    STRIP_RE does not match this form, so the record is not a candidate:
    it sits in the gap between candidates (the observed 0x4b/0x4e
    variant). Its payload only has to avoid manufacturing a false
    ``01 [41-4f] . ff`` hit.
    """
    return bytes((0x01, mk, ty, b3, 0xFF)) + tail


W1_REFS = bytes((0x07, 0x0C, 0x11))  # n=3, u8
W2_REFS_3 = u16be_refs((0x0100, 0x0102, 0x0104))  # n=3, u16be
W2_REFS_4 = u16be_refs((0x0101, 0x0103, 0x0105, 0x0107))  # n=4, u16be
GAP = b"\xaa" * 6  # gap filler: no 0x01/0xff bytes, no false headers


def exact_w1() -> bytes:
    """A record whose u8 parse ends exactly at the next header."""
    return facet_record(0x41, 1, 3, (3,), W1_REFS)


def exact_w2() -> bytes:
    """A record whose u16be parse ends exactly at the next header (its
    u8 variant ends short — a gap edge — so the exact tile wins)."""
    return facet_record(0x41, 2, 3, (3,), W2_REFS_3)


def cluster_final_w2() -> bytes:
    """A u16be record followed by a gap: both width parses validate and
    end short of the next header, so the tie-break decides (the
    truncation case — the u8 half-read of the u16be payload)."""
    return facet_record(0x41, 1, 4, (4,), W2_REFS_4)


def exported_exact_w2() -> bytes:
    """``exact_w2`` under the exported 0x42 strip family (structurally
    0x4a without the normal payload; no (n, ty) byte law is checked on
    it)."""
    return facet_record(0x42, 1, 3, (3,), W2_REFS_3)


def exported_cluster_final_w2() -> bytes:
    """``cluster_final_w2`` under the exported 0x42 strip family."""
    return facet_record(0x42, 1, 4, (4,), W2_REFS_4)


# --- the store-width context (clean stores) --------------------------------


@pytest.mark.parametrize("clean_store", [False, True], ids=["default", "clean"])
def test_pure_w1_store_gap_record_stays_u8(clean_store: bool) -> None:
    """A store whose exact tiles are all u8 keeps the width-1 preference:
    the gap-edge record (whose u16be variant also validates) stays u8 —
    under the context (a unanimous u8 vote) and without it (the
    fail-safe default), alike."""
    body = exact_w1() + exact_w1() + cluster_final_w2() + b"\xaa" * 8
    scan = scan_facets(body, 0, len(body), clean_store=clean_store)
    assert scan.candidates == 3
    assert scan.unresolved_candidates == 0
    assert [r.width for r in scan.records] == [1, 1, 1]
    # the gap record keeps the historical u8 half-read of its u16be
    # payload (01 01 | 01 03 | ...): unchanged behavior at context 1
    assert scan.records[2].refs == (0x01, 0x01, 0x01, 0x03)
    assert scan.records[2].end == 37  # not the u16be variant's end (41)


def test_mixed_store_cluster_final_record_flips_to_u16be() -> None:
    """Exact u16be tiles vote 2 unanimously, so the cluster-final u16be
    record before a gap keeps its width (was truncated to u8). This is
    the unbounded mechanism's verdict, now reached on the clean-store
    path (the flag the store decode passes down)."""
    body = (
        exact_w2() + exact_w2() + cluster_final_w2() + GAP + exact_w2()
    )
    scan = scan_facets(body, 0, len(body), clean_store=True)
    assert scan.candidates == 4
    assert scan.unresolved_candidates == 0
    assert [r.width for r in scan.records] == [2, 2, 2, 2]
    assert scan.records[2].refs == (0x0101, 0x0103, 0x0105, 0x0107)
    assert scan.records[2].end == 47  # the u16be end, not the u8 half (43)


def test_mixed_store_before_5byte_header_flips_to_u16be() -> None:
    """Same flip when the gap hides a 5-byte-form record: it is not a
    candidate, so the cluster-final record's next header is far away and
    the store-width context still resolves the width."""
    five_byte = five_byte_record(
        0x4B, 0x01, 0x01, u32le(2) + bytes((0x33, 0x33)) + b"\x55" * 4
    )
    body = exact_w2() + cluster_final_w2() + five_byte + GAP + exact_w2()
    scan = scan_facets(body, 0, len(body), clean_store=True)
    assert scan.candidates == 3  # the 5-byte header is not a candidate
    assert scan.unresolved_candidates == 0
    assert [r.width for r in scan.records] == [2, 2, 2]
    assert scan.records[1].refs == (0x0101, 0x0103, 0x0105, 0x0107)
    assert scan.records[1].end == 32  # abuts the 5-byte-form record


@pytest.mark.parametrize("clean_store", [False, True], ids=["default", "clean"])
def test_ambiguous_store_keeps_width1_preference(clean_store: bool) -> None:
    """Exact tiles of both widths are a mixed vote: the gap-edge
    tie-break falls back to the historical narrower-width preference —
    under the context and without it, alike."""
    body = (
        exact_w1() + exact_w2() + cluster_final_w2() + b"\xaa" * 6
    )
    scan = scan_facets(body, 0, len(body), clean_store=clean_store)
    assert [r.width for r in scan.records] == [1, 2, 1]
    assert scan.records[2].refs == (0x01, 0x01, 0x01, 0x03)  # the u8 half-read
    assert scan.records[2].end == 40


@pytest.mark.parametrize("clean_store", [False, True], ids=["default", "clean"])
def test_store_without_exact_tiles_keeps_width1_preference(
    clean_store: bool,
) -> None:
    """No record ends at its next header: no votes at all, so the gap
    edges keep the historical width-1 preference — under the context
    and without it, alike."""
    body = cluster_final_w2() + GAP + cluster_final_w2() + b"\xaa" * 6
    scan = scan_facets(body, 0, len(body), clean_store=clean_store)
    assert scan.candidates == 2
    assert scan.unresolved_candidates == 0
    assert [r.width for r in scan.records] == [1, 1]
    assert [r.end for r in scan.records] == [13, 36]  # both u8 gap edges


@pytest.mark.parametrize("clean_store", [False, True], ids=["default", "clean"])
def test_scan_is_deterministic(clean_store: bool) -> None:
    """Scanning the same body twice yields identical records (the
    pre-pass reads, never writes)."""
    body = exact_w2() + cluster_final_w2() + GAP + exact_w2()
    assert scan_facets(
        body, 0, len(body), clean_store=clean_store
    ) == scan_facets(body, 0, len(body), clean_store=clean_store)


# --- the clean-store class bound (third re-scope, #35) ----------------------


def test_composite_store_keeps_width1_gap_behavior() -> None:
    """The bound: the store-width context applies ONLY to clean stores.
    A composite store (an ``01 02`` edge group or a trailer opener is
    present — the caller's knowledge, the scanner's flag) keeps the
    historical unconditional width-1 gap behavior: the same w2-exact +
    w1-gap structure that flips a clean store does NOT flip here. The
    default flag value — any caller that does not pass it — behaves as
    the composite path (fail-safe = the pre-bound behavior)."""
    body = exact_w2() + exact_w2() + cluster_final_w2() + GAP + exact_w2()
    default_scan = scan_facets(body, 0, len(body))
    composite_scan = scan_facets(body, 0, len(body), clean_store=False)
    assert default_scan == composite_scan
    assert composite_scan.candidates == 4
    assert composite_scan.unresolved_candidates == 0
    # the exact tiles still decode u16be; only the gap edge is bound
    assert [r.width for r in composite_scan.records] == [2, 2, 1, 2]
    assert composite_scan.records[2].refs == (0x01, 0x01, 0x01, 0x03)
    assert composite_scan.records[2].end == 43  # not the u16be end (47)


# --- the exporter plumbing (the flag through the export seam) ---------------

#: The composite-space classification.  At main 781d1fa (2026-11-10)
#: the exporter's undecoded-variant raise preceded the facet scan; the
#: stage-2c integration (#34, 2026-11-11) decodes composite stores
#: under the recovered merge law instead, so a composite body without a
#: token-bearing list node fails with the node gap (the store this
#: body builds carries no node).
COMPOSITE_DETAIL = (
    "composite store without a token-bearing list node "
    "(N1: 939/939 composite stores carry one)"
)


def pool_group_bytes(n_vertices: int) -> bytes:
    """One ``01 06`` pool group of ``n_vertices`` lex-distinct vertices.

    Vertex ``i`` sits at ``(i, i % 5, 0)``: the x coordinate is the walk
    index, so the lexicographic rank map is the identity and u16be
    references can name ranks directly; the y coordinate varies so the
    strip triangles are not collinear."""
    vertices = b"".join(
        NESTED_VREC + struct.pack("<fff", float(i), float(i % 5), 0.0)
        for i in range(n_vertices)
    )
    return (
        NESTED_FULL_WRAP
        + NESTED_POOL_SUBKIND
        + b"\xff"
        + u32le(n_vertices)
        + vertices
    )


def gap_edge_store_body(composite: bool) -> bytes:
    """A store body with the corpus mixed-store structure: exact u16be
    tiles + a cluster-final u16be record before a gap. With 264 pool
    vertices both width parses stay in-pool, so the width decides the
    exported triangles (the u8 half-read of the cluster-final record is
    the (1, 1, 1 | 1, 1, 3) strip — every triangle degenerate)."""
    parts = [pool_group_bytes(264)]
    if composite:
        # G3 F8's edge-table sketch: the composite-index-space marker.
        parts.append(
            NESTED_FULL_WRAP
            + NESTED_EDGE_SUBKIND
            + b"\x02\x02"
            + struct.pack(">HH", 0, 1)
        )
    parts.append(exported_exact_w2())
    # second exact tile, distinct ranks (two identical records would
    # emit the same triangle twice)
    parts.append(facet_record(0x42, 1, 3, (3,), u16be_refs((0x0102, 0x0104, 0x0106))))
    parts.append(exported_cluster_final_w2())
    parts.append(GAP)
    return b"".join(parts)


def export_body(data: bytes):
    """Run the exporter's per-store seam on a hand-built body (the span
    a ``v5header``-origin locate would produce)."""
    span = StoreSpan(
        block_start=0,
        origin=0,
        origin_kind="v5header",
        body_lo=0,
        body_hi=len(data),
        catalog_len=0,
    )
    return _export_store(data, span, 0)


def test_export_passes_the_clean_store_flag_to_the_scanner() -> None:
    """The exporter passes the class knowledge its decode already
    performed (the composite-space check) down to :func:`scan_facets`:
    on the clean store the gap-edge record keeps its u16be width, and
    the exported soup carries the u16be reading's triangles (the
    width-1 fallback would leave the cluster-final record's half-read,
    all-degenerate strips)."""
    summary, flat, triangles = export_body(gap_edge_store_body(composite=False))
    assert summary["facet_candidate_count"] == 3
    assert summary["facet_record_count"] == 3
    assert len(flat) == 264
    assert sorted(triangles) == sorted(
        [
            (256, 258, 260),  # exact tile 1
            (258, 260, 262),  # exact tile 2
            (257, 259, 261),  # cluster-final record, u16be t=0
            (263, 261, 259),  # cluster-final record, u16be t=1 (flipped)
        ]
    )


def test_export_composite_classification_unchanged() -> None:
    """A composite store with the same w2-exact + w1-gap structure
    classifies exactly as at main: the undecoded-variant raise precedes
    the facet scan, byte-identical class and detail."""
    with pytest.raises(ExportError) as excinfo:
        export_body(gap_edge_store_body(composite=True))
    assert excinfo.value.error_class == "undecoded-variant"
    assert excinfo.value.detail == COMPOSITE_DETAIL
