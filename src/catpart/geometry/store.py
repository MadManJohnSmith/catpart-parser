"""Nested V5_CFV2 stream-store navigation (G1 model, ticket #29).

Adapted from ``scripts/triage/decode_nested_store.py`` (G1's corpus
decoder): the subset the exporter needs to bound a store's body —
the CATStdCont block region, the store origin (header / header-less
variants) and the catalog start — with the decode semantics unchanged.
The triage script stays the analysis tool; this module is the shipped
path (ticket #32) and does not depend on ``scripts/``.

Model (docs/evidence/2026-11-09-nested-store.md):

- A nested store sits in the ``CATStdCont`` block region of a CATIA V5
  file (N1). The region is bounded by the next valid storage block, the
  outer header dword8, or EOF (B3 boundary rule minus CB0001/OSMX, which
  occur legitimately inside a store region — correction C1).
- Header variant (N1h/N2, 1,056/1,173): a 32-byte header ``V5_CFV2\\0``
  + big-endian dword8 (catalog offset from origin) + big-endian dword12
  (catalog tail length) + ff x 8 + zeros x 8; the catalog magic
  ``CATIA_V5 CB0001\\0`` byte-verifies at ``origin + dword8`` (N3, 99.0%)
  or up to 64 B earlier (the dword8-overshoot variant, correction C3).
- Header-less variant (N1l, 12 R19 parts): origin = block start, the
  catalog sits directly in the region (found as the first ``CB0001``),
  the body starts at origin + 64, and the tail length is
  ``region_end - 126 - catalog`` (fallback ``region_end - catalog``).
- Catalog validation. G1 validates through B2's full record walk
  (``scan_tail``); the exporter consumes no catalog entries, so it
  validates the trailer laws instead — ``CB__END\\0`` as the tail's last
  8 bytes, ``C == D`` and ``G == tail length`` (N6, 1,050/1,050) — a
  strictly weaker but, combined with the header/magic requirements,
  sufficient structural check for the body extent. The body is
  ``origin + 32 .. catalog_start`` (header variant) or
  ``origin + 64 .. catalog_start`` (header-less).
- Recovery extension (stage 3a #34, the L5 lever). Two additions, both
  fail-closed, measured on the corpus in
  docs/evidence/2026-11-10-l2-grind-classification.md sections 5-6:
  (a) the relaxed tail law recovers the two G1-documented tail
  variants the shipped window rejects — the dword8-overshoot tail
  (C3: read ``[cb, cb + dword12)`` from the true catalog magic) and
  the padded tail (end the tail at its ``CB__END``, N4w); a tail
  neither family recovers keeps the shipped ``malformed-store-header``
  rejection. (b) the caller may probe ``CATXDocLinkCont`` and
  ``CATSeeBodyCont`` regions with the same law (``container`` records
  the probing family on the span) — containers the locator never
  visited before stage 3a; the exporter does this only when no
  ``CATStdCont`` region located a store. Every recovered store names
  how it was recovered (``StoreSpan.container``/``StoreSpan.tail_law``).

``data`` is any bytes-like buffer supporting slicing, ``find()`` and
``len()`` (``bytes`` or a read-only :class:`mmap.mmap`).
"""

from __future__ import annotations

import dataclasses

from catpart.geometry.errors import ExportError

V5_CFV2 = b"V5_CFV2\x00"
CB0001 = b"CATIA_V5 CB0001\x00"
CB_END = b"CB__END\x00"
BLOCK_TAG = b"\x34\x12"
STORAGE_WORD = b"CATStorageProperty"

HEADER_LEN = 32
HDRLESS_BODY = 64  # header-less store body starts at origin + 64 (N1l)
TAIL126 = 126  # inter-block tail after the container (N3b/N9)

ORIGIN_KIND_HEADER = "v5header"
ORIGIN_KIND_BLOCK = "block"

# Stage 3a recovery provenance (#34): which container family located the
# store and which catalog-tail law validated it. ``stdcont``/``shipped``
# is the pre-stage-3a behavior; every other combination is a recovery.
# Stage 12 (#34, 2026-11-13) adds the final family: ``other-container``
# — a store validated in a block region whose doc-type name is none of
# the three probed families (the corpus mass: CATBRepModeContainer 39,
# CameraStartupContainer 8, contmeasure 2, four others 1 each — the
# stage-1 census's C11 candidate upside, measured in
# docs/evidence/2026-11-13-noncomposite-census.md). The block's own
# name travels on the summary (``store_recovery.container_name``).
CONTAINER_STDCONT = "stdcont"
CONTAINER_XDOCLINK = "xdoclink"
CONTAINER_SEEBODY = "seebody"
CONTAINER_OTHER = "other-container"
TAIL_LAW_SHIPPED = "shipped"
TAIL_LAW_OVERSHOOT = "overshoot"
TAIL_LAW_PADDED = "padded"

#: The doc-type names the export seam's named probe families cover
#: (stage 3a + the shipped law). Every other valid block name belongs
#: to the stage-12 ``other-container`` probe family.
NAMED_PROBE_CONTAINERS = ("CATStdCont", "CATXDocLinkCont", "CATSeeBodyCont")


def find_all(data, needle: bytes, start: int, end: int) -> list[int]:
    """Every occurrence of ``needle`` in ``data[start:end]``, in order."""
    out = []
    i = data.find(needle, start, end)
    while i >= 0:
        out.append(i)
        i = data.find(needle, i + 1, end)
    return out


def block_name(data, blk: int) -> tuple[str, bool]:
    """Doc-type name from the block's CATUnicodeString header (G1/B1)."""
    bi = data.find(b"CATUnicodeString", blk, blk + 64)
    if bi < 0:
        return "", False
    if (
        data[bi + 16 : bi + 22] != b"\xa0\x02\x00\x00\x00\x00"
        or data[bi + 22] != 0x34
    ):
        return "", False
    ln = data[bi + 23]
    name = bytes(data[bi + 24 : bi + 24 + ln])
    if len(name) != ln:
        return "", False
    return name.decode("ascii", "replace"), True


def valid_blocks(data) -> list[tuple[int, str]]:
    """(start, name) of every storage block whose name field parses."""
    out = []
    for o in find_all(data, STORAGE_WORD, 0, len(data)):
        blk = o - 2 if data[o - 2 : o] == BLOCK_TAG else o
        nm, ok = block_name(data, blk)
        if ok:
            out.append((blk, nm))
    return out


def probe_region(data, blk: int, blocks: list[tuple[int, str]], d8_outer: int) -> int:
    """Region end of ``blk``: next valid block / outer dword8 / EOF (B3)."""
    nxt = next((b for b, _ in blocks if b > blk), None)
    ends = [len(data)]
    if nxt is not None:
        ends.append(nxt)
    if d8_outer > blk:
        ends.append(d8_outer)
    return min(ends)


def validate_catalog_tail(tail: bytes) -> bool:
    """Structural trailer laws of a nested catalog tail (G1 N6).

    The tail must end with ``CB__END\\0``, carry ``C == D`` and name its
    own length in ``G``. This replaces G1's B2 record-walk validation
    (``validate_catalog``) because the exporter reads no catalog entries;
    see the module docstring.
    """
    if len(tail) < 36 or tail[-8:] != CB_END:
        return False
    tb = tail[-36:]
    c = int.from_bytes(tb[8:12], "big")
    d = int.from_bytes(tb[12:16], "big")
    g = int.from_bytes(tb[24:28], "big")
    return c == d and g == len(tail)


@dataclasses.dataclass(frozen=True)
class StoreSpan:
    """The byte extent one validated nested store occupies.

    ``body_lo``/``body_hi`` bound the store body (the pool and facet
    territory the exporter reads); ``body_hi`` is the catalog start.
    ``container``/``tail_law`` carry the stage-3a recovery provenance
    (#34): how the store was located — which container family and which
    catalog-tail law. ``stdcont``/``shipped`` is the default (the
    pre-stage-3a law).
    """

    block_start: int
    origin: int
    origin_kind: str  # ORIGIN_KIND_HEADER or ORIGIN_KIND_BLOCK
    body_lo: int
    body_hi: int
    catalog_len: int
    container: str = CONTAINER_STDCONT
    tail_law: str = TAIL_LAW_SHIPPED


def _relaxed_tail_span(
    data, blk: int, j: int, d8n: int, d12n: int, cb: int, container: str
) -> StoreSpan | None:
    """The two G1-documented catalog-tail variants (stage 3a #34).

    Applies only after the shipped tail law rejected ``[cb, j+d8n+d12n)``:

    - dword8-overshoot (G1 correction C3, k = 5..28 B): ``dword8``
      overshoots the catalog magic by ``k`` and the shipped tail end
      inherits the same overshoot, running ``k`` bytes past the
      catalog's ``CB__END``; the true tail is ``[cb, cb + d12n)``.
    - padded-tail (G1): the catalog's trailer sits *inside* the tail,
      ``CB__END`` followed by zero padding up to the round dword12;
      the tail ends at its ``CB__END`` (N4w: the trailer's ``G`` names
      the true catalog length).

    Both recover only when the corrected tail satisfies the same N6
    trailer laws (:func:`validate_catalog_tail`); otherwise ``None`` is
    returned and the shipped rejection stands (fail-closed).
    """
    k = j + d8n - cb
    if k > 0:
        tail = bytes(data[cb : cb + d12n])
        if validate_catalog_tail(tail):
            return StoreSpan(
                block_start=blk,
                origin=j,
                origin_kind=ORIGIN_KIND_HEADER,
                body_lo=j + HEADER_LEN,
                body_hi=cb,
                catalog_len=d12n,
                container=container,
                tail_law=TAIL_LAW_OVERSHOOT,
            )
    ship_tail = bytes(data[cb : j + d8n + d12n])
    pos = ship_tail.find(CB_END)
    if pos >= 0:
        tail = ship_tail[: pos + 8]
        if validate_catalog_tail(tail):
            return StoreSpan(
                block_start=blk,
                origin=j,
                origin_kind=ORIGIN_KIND_HEADER,
                body_lo=j + HEADER_LEN,
                body_hi=cb,
                catalog_len=len(tail),
                container=container,
                tail_law=TAIL_LAW_PADDED,
            )
    return None


def locate_store(
    data,
    blk: int,
    blocks: list[tuple[int, str]],
    d8_outer: int,
    container: str = CONTAINER_STDCONT,
) -> StoreSpan | None:
    """Bound one block region's nested store (G1 analyze_region).

    Returns ``None`` when the region carries no store (G1's
    ``none_in_region`` / ``embedded_doc`` families) and raises
    ``malformed-store-header`` when a ``V5_CFV2`` header is present but
    fails both the N2 validation and the stage-3a relaxed tail law
    (#34: G1's two documented tail variants, applied fail-closed — a
    tail neither family recovers keeps the shipped rejection).

    ``container`` records the probing family on the returned span (the
    exporter probes ``CATXDocLinkCont``/``CATSeeBodyCont`` regions too,
    stage 3a); the tail laws themselves are container-independent.
    """
    size = len(data)
    rend = probe_region(data, blk, blocks, d8_outer)

    # ---- header variant
    j = data.find(V5_CFV2, blk, rend)
    if j >= 0:
        nh = bytes(data[j : j + HEADER_LEN])
        ff8 = len(nh) == HEADER_LEN and nh[16:24] == b"\xff" * 8
        zeros8 = len(nh) == HEADER_LEN and nh[24:32] == b"\x00" * 8
        d8n = int.from_bytes(nh[8:12], "big") if len(nh) == HEADER_LEN else 0
        d12n = int.from_bytes(nh[12:16], "big") if len(nh) == HEADER_LEN else 0
        sane = 0 < d8n and 0 < d12n and j + d8n + d12n <= size
        cb = -1
        if sane and bytes(data[j + d8n : j + d8n + 16]) == CB0001:
            cb = j + d8n
        elif sane:
            # dword8-overshoot variant (C3): the catalog magic sits up to
            # 64 B before origin + dword8; everything else standard.
            cand = data.find(CB0001, j, min(rend, j + d8n + d12n + 512))
            if cand >= 0 and 1 <= (j + d8n - cand) <= 64:
                cb = cand
        if not (ff8 and zeros8) or cb < 0:
            raise ExportError(
                "malformed-store-header",
                f"V5_CFV2 header at {j} fails the G1 N2 validation "
                "(ff x 8 / zeros x 8 / sane dwords / CB0001 catalog magic "
                "at origin + dword8, N3 overshoot variant included)",
            )
        tail = bytes(data[cb : j + d8n + d12n])
        if not validate_catalog_tail(tail):
            # Stage 3a (#34): the shipped tail window is wrong for two
            # G1-documented families — the dword8-overshoot tail (the
            # end inherits the dword8 overshoot, C3) and the padded
            # tail (the trailer sits inside the zero padding). Try the
            # corrected windows fail-closed; an unrecognized tail keeps
            # the shipped malformed-store-header classification.
            span = _relaxed_tail_span(data, blk, j, d8n, d12n, cb, container)
            if span is not None:
                return span
            raise ExportError(
                "malformed-store-header",
                f"catalog tail at {cb} (length {d12n}) violates the G1 N6 "
                "trailer laws (CB__END, C == D, G == tail length) and "
                "matches neither stage-3a recovery family (dword8-"
                "overshoot, padded-tail)",
            )
        return StoreSpan(
            block_start=blk,
            origin=j,
            origin_kind=ORIGIN_KIND_HEADER,
            body_lo=j + HEADER_LEN,
            body_hi=cb,
            catalog_len=d12n,
            container=container,
        )

    # ---- header-less variant / embedded document
    cb = data.find(CB0001, blk, rend)
    if cb < 0:
        return None
    for tail_len in (rend - TAIL126 - cb, rend - cb):
        if tail_len <= 100:
            continue
        if validate_catalog_tail(bytes(data[cb : cb + tail_len])):
            return StoreSpan(
                block_start=blk,
                origin=blk,
                origin_kind=ORIGIN_KIND_BLOCK,
                body_lo=blk + HDRLESS_BODY,
                body_hi=cb,
                catalog_len=tail_len,
                container=container,
            )
    # A CB0001 that validates as neither tail form is an embedded
    # document's own outer-style catalog (G1 N10), not a stream store.
    return None
