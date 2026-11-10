"""Facet record tiling: the store-width context on gap edges (P3-B, #35).

2026-11-10 re-scope: the greedy scanner's gap-edge tie-break
(``end < nxt``) no longer unconditionally prefers the narrower width. A
pre-pass over the store's exact-tile records (those whose end equals
the next header position) votes their reference width; a unanimous vote
wins the gap-edge tie-break, so a cluster-final u16be record before a
gap or a 5-byte-form header keeps its width instead of truncating to
the u8 half-read. Mixed votes (or no exact tiles) keep the historical
width-1 preference, so pure-w1 stores stay byte-identical.

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

from catpart.geometry.facets import scan_facets


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


# --- the store-width context ------------------------------------------------


def test_pure_w1_store_gap_record_stays_u8() -> None:
    """A store whose exact tiles are all u8 keeps the width-1 preference:
    the gap-edge record (whose u16be variant also validates) stays u8."""
    body = exact_w1() + exact_w1() + cluster_final_w2() + b"\xaa" * 8
    scan = scan_facets(body, 0, len(body))
    assert scan.candidates == 3
    assert scan.unresolved_candidates == 0
    assert [r.width for r in scan.records] == [1, 1, 1]
    # the gap record keeps the historical u8 half-read of its u16be
    # payload (01 01 | 01 03 | ...): unchanged behavior at context 1
    assert scan.records[2].refs == (0x01, 0x01, 0x01, 0x03)
    assert scan.records[2].end == 37  # not the u16be variant's end (41)


def test_mixed_store_cluster_final_record_flips_to_u16be() -> None:
    """Exact u16be tiles vote 2 unanimously, so the cluster-final u16be
    record before a gap keeps its width (was truncated to u8)."""
    body = (
        exact_w2() + exact_w2() + cluster_final_w2() + GAP + exact_w2()
    )
    scan = scan_facets(body, 0, len(body))
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
    scan = scan_facets(body, 0, len(body))
    assert scan.candidates == 3  # the 5-byte header is not a candidate
    assert scan.unresolved_candidates == 0
    assert [r.width for r in scan.records] == [2, 2, 2]
    assert scan.records[1].refs == (0x0101, 0x0103, 0x0105, 0x0107)
    assert scan.records[1].end == 32  # abuts the 5-byte-form record


def test_ambiguous_store_keeps_width1_preference() -> None:
    """Exact tiles of both widths are a mixed vote: the gap-edge
    tie-break falls back to the historical narrower-width preference."""
    body = (
        exact_w1() + exact_w2() + cluster_final_w2() + b"\xaa" * 6
    )
    scan = scan_facets(body, 0, len(body))
    assert [r.width for r in scan.records] == [1, 2, 1]
    assert scan.records[2].refs == (0x01, 0x01, 0x01, 0x03)  # the u8 half-read
    assert scan.records[2].end == 40


def test_store_without_exact_tiles_keeps_width1_preference() -> None:
    """No record ends at its next header: no votes at all, so the gap
    edges keep the historical width-1 preference."""
    body = cluster_final_w2() + GAP + cluster_final_w2() + b"\xaa" * 6
    scan = scan_facets(body, 0, len(body))
    assert scan.candidates == 2
    assert scan.unresolved_candidates == 0
    assert [r.width for r in scan.records] == [1, 1]
    assert [r.end for r in scan.records] == [13, 36]  # both u8 gap edges


def test_scan_is_deterministic() -> None:
    """Scanning the same body twice yields identical records (the
    pre-pass reads, never writes)."""
    body = exact_w2() + cluster_final_w2() + GAP + exact_w2()
    assert scan_facets(body, 0, len(body)) == scan_facets(body, 0, len(body))
