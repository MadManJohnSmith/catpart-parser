"""CGM exact-model container decode: identity, object dictionary, NURBS
payload detector (BR5, ticket #57, Spec G #47).

The subset of the CGM (exact-model) container that BR5 could decode
byte-level over the observed corpus, plus the content-based NURBS
payload detector the BR1 census lacked.  Model (docs/evidence/
2026-11-17-br5-cgm-nurbs.md, all rates corpus-wide on the 1,089
L2-pass files):

- The ``CGMGeom`` storage block's region (B3 boundary rule) is the CGM
  **object dictionary**: a property preamble (writer id ``FINJPL  ``,
  the ``Cont_<hex>`` UTF-16LE identity name, the vendor footer) followed
  by object id-run records and offset records.  The dictionary carries
  no coordinate payload.
- **Identity record** (byte-verified on R18-R21 files): the UTF-16LE
  ``CATStorageProperty`` field, then the UTF-16LE ``Cont_<hex>``
  container name, ASCII ``FINJPL  `` writer id at ``+0x69 (105d)`` /
  ``+0x6a (106d)`` from the block start, and the footer
  ``DASSAULT-SYSTEMES`` / ``CATIA`` / a ``[0-9]{6}[A-Z]`` release token.
- **Object id-run records**: marker ``[u32le 0x0004000k]`` (bytes
  ``k 00 04 00``, k = 2..15) + ``[u32le x][u8 flag][u32le count]`` +
  ``count`` u32le ids + the ``00 00`` terminator.  Verified on id runs
  up to count = 106,912 (the ``17930bab`` dental mold: the corpus's
  largest observed object space).  Marker-1 (``01 00 04 00``) records
  are offset records of two further shapes; this scan counts them and
  covers the id runs, it does not decode the offset shapes.
- **NURBS payload detector** (the BR1 census honesty fix): the census
  labels ``GEOM_CURV_NURBS``/``GEOM_SURF_NURBS`` from ``cgm_present``
  alone (``scripts/triage/census_brep_constructs.py``: every
  CGMGeom-carrying file is labeled NURBS curve AND surface) — a
  carrier label, not a content decode.  This detector is
  content-based: a *knot-array* signature is a run of >= 8 little-
  endian f64 that is non-decreasing, carries >= 3 distinct values with
  >= 1 repeat (knot multiplicity), and passes the u32-alias guard; a
  *weight* signature is >= 4 consecutive exact f64 1.0 (rational
  weights).  What the detector does NOT discriminate: it does not
  prove a flagged array belongs to a NURBS record (no record framing),
  does not distinguish rational from non-rational splines (non-rational
  splines store no weight array), and does not distinguish curve knots
  from surface knots.  The corpus measurement of these signatures is
  the ceiling arithmetic behind BR5's NURBS outcome.

``data`` is any bytes-like buffer supporting slicing, ``find()`` and
``len()`` (``bytes`` or a read-only :class:`mmap.mmap`).
"""

from __future__ import annotations

import dataclasses
import math
import re
import struct

#: The CGM exact-model block's doc-type name (BR1 frozen vocabulary).
CGM_BLOCK_NAME = "CGMGeom"
#: The body-carrier block's doc-type name (TOP-01 census signature).
SEE_BODY_BLOCK_NAME = "CATSeeBodyCont"

#: CGM writer id (ASCII, 8 bytes incl. padding), block-relative
#: ``+0x69 (105d)``..``+0x6a (106d)`` observed.
WRITER_ID = b"FINJPL  "
#: Vendor / application footer tokens (ASCII, length-prefixed in the
#: stream; extracted by presence).
VENDOR = b"DASSAULT-SYSTEMES"
APPLICATION = b"CATIA"
_RELEASE_TOKEN = re.compile(rb"[0-3][0-9](?:[0-9][0-9])?[0-9]{4}[A-Z]")

def _utf16le(s: str) -> bytes:
    return b"".join(bytes([ord(c), 0]) for c in s)


#: UTF-16LE ``Cont_<hex>``.  The byte unit preceding ``Cont_`` varies
#: across files (``B``, ``4``, ``2``) — it is field structure (a type
#: byte), not name content, so the match anchors on ``Cont_`` itself.
_UTF16_CONT_NAME = re.compile(
    _utf16le("Cont_") + b"(?:[0-9a-fA-F_]\x00){8,}"
)

#: Object id-run record markers: ``k 00 04 00`` with k = 2..15.
#: Marker-1 (``01 00 04 00``) offset records are counted, not decoded.
_RUN_MARKER_FIRST = 2
_RUN_MARKER_LAST = 15
_MARKER_RE = re.compile(rb"[\x01-\x0f]\x00\x04\x00")

_MAX_RUN_COUNT = 1_000_000

#: Knot-value floor: parameter values below this (but above zero) are
#: the denormal-alias band of integer arrays, never knot parameters.
_KNOT_FLOOR = 1e-8

_ONE_F64 = struct.pack("<d", 1.0)
_CHUNK_F64 = 1 << 13  # 8192 f64 per unpack batch


@dataclasses.dataclass(frozen=True)
class ContainerIdentity:
    """The CGM container's identity preamble, byte-verified.

    Offsets are relative to the ``CGMGeom`` block start; both bases in
    the evidence note.  ``cont_name`` is the UTF-16LE container name
    (``Cont_<hex>``; the varying byte unit before ``Cont_`` is field
    structure, not name content).
    """

    block_start: int
    region_size: int
    writer_offset: int
    cont_name: str
    cont_name_offset: int
    vendor_offset: int
    release: str

    def ok(self) -> bool:
        """All four identity elements found."""
        return (
            self.writer_offset >= 0
            and bool(self.cont_name)
            and self.vendor_offset >= 0
            and bool(self.release)
        )


@dataclasses.dataclass(frozen=True)
class IdRun:
    """One validated object id-run record.

    Layout: ``[u32le marker 0x0004000k][u32le x][u8 flag][u32le count]
    [count x u32le ids][u16le 0000]``.  ``start``/``end`` are absolute
    buffer offsets (``end`` exclusive, terminator included).
    """

    marker: int  # k, 2..15
    x: int
    flag: int
    ids: tuple[int, ...]
    start: int
    end: int


@dataclasses.dataclass(frozen=True)
class DictionaryScan:
    """The id-run decode of one CGMGeom dictionary region."""

    runs: tuple[IdRun, ...]
    offset_markers: int  # count of marker-1 offset records (not decoded)
    region_size: int

    @property
    def objects(self) -> int:
        """Total object ids across the validated runs."""
        return sum(len(r.ids) for r in self.runs)

    @property
    def max_id(self) -> int:
        """Largest object id observed (0 when no runs)."""
        return max((max(r.ids) for r in self.runs if r.ids), default=0)


@dataclasses.dataclass(frozen=True)
class KnotRun:
    """One accepted knot-array signature.

    ``offset`` is absolute; ``distinct``/``repeats`` describe the run's
    f64 values (repeats = knot multiplicity evidence).  ``aliased`` is
    always False for accepted runs (the u32-alias guard rejected the
    rest); it is kept for the CSV rows.
    """

    offset: int
    count: int
    distinct: int
    repeats: int
    lo: float
    hi: float


@dataclasses.dataclass(frozen=True)
class NurbsSignatures:
    """Content-based NURBS payload signatures over one span."""

    knot_runs: tuple[KnotRun, ...]
    weight_runs: tuple[tuple[int, int], ...]  # (offset, count)

    @property
    def present(self) -> bool:
        return bool(self.knot_runs or self.weight_runs)


def valid_regions(data) -> list[tuple[int, str, int]]:
    """``(block_start, name, region_end)`` for every storage block."""
    from catpart.geometry.store import probe_region, valid_blocks

    blocks = valid_blocks(data)
    d8_outer = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    out = []
    for blk, name in blocks:
        out.append((blk, name, probe_region(data, blk, blocks, d8_outer)))
    return out


@dataclasses.dataclass(frozen=True)
class BodyCarrier:
    """TOP-01's structural carrier, measured with the committed laws.

    ``seebody_block`` is the ``CATSeeBodyCont`` storage block's presence
    (the census's own TOPO_BODY signature); ``store_root`` is the
    nested-store root located by the shipped locator law in the
    exporter's probe order (``stdcont`` -> ``xdoclink`` -> ``seebody``
    -> ``other-container``, ``None`` when no region locates one).
    What this does NOT discriminate: body *topology* semantics — the
    locator proves container/root structure, not the body/lump record
    contents (parked, see the evidence note).
    """

    seebody_block: bool
    store_root: str | None


def top01_carrier(data) -> BodyCarrier:
    """Measure TOP-01's structural carrier on one part."""
    from catpart.geometry import store
    from catpart.geometry.errors import ExportError

    blocks = store.valid_blocks(data)
    seebody = any(nm == SEE_BODY_BLOCK_NAME for _, nm in blocks)
    d8_outer = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    root: str | None = None
    for tag, wanted in (
        (store.CONTAINER_STDCONT, "CATStdCont"),
        (store.CONTAINER_XDOCLINK, "CATXDocLinkCont"),
        (store.CONTAINER_SEEBODY, SEE_BODY_BLOCK_NAME),
    ):
        for blk, nm in blocks:
            if nm != wanted:
                continue
            try:
                span = store.locate_store(data, blk, blocks, d8_outer, container=tag)
            except ExportError:
                continue
            if span is not None:
                root = span.container
                break
        if root is not None:
            break
    if root is None:
        for blk, nm in blocks:
            if nm in store.NAMED_PROBE_CONTAINERS:
                continue
            try:
                span = store.locate_store(
                    data, blk, blocks, d8_outer, container=store.CONTAINER_OTHER
                )
            except ExportError:
                continue
            if span is not None:
                root = span.container
                break
    return BodyCarrier(seebody_block=seebody, store_root=root)


def _decode_utf16_ascii(buf: bytes) -> str:
    chars = []
    for i in range(0, len(buf) - 1, 2):
        c = buf[i]
        if buf[i + 1] != 0 or not (0x20 <= c < 0x7F):
            break
        chars.append(chr(c))
    return "".join(chars)


def parse_identity(data, block_start: int, region_end: int) -> ContainerIdentity:
    """Decode the CGM container identity preamble (BR5-01).

    Every element is extracted by content (no structural length fields
    are trusted): the ``FINJPL  `` writer id, the UTF-16LE ``Cont_*``
    name following the ``CATStorageProperty`` field, the vendor footer
    and the release token.  Missing elements come back as ``""`` / -1
    so callers can rate the parts independently.
    """
    end = min(region_end, len(data))
    writer = data.find(WRITER_ID, block_start, end)
    # The identity name follows the UTF-16LE "CATStorageProperty" field.
    catstor = _utf16le("CATStorageProperty")
    name = ""
    name_off = -1
    j = data.find(catstor, block_start, end)
    if j >= 0:
        m = _UTF16_CONT_NAME.search(data, j, min(j + 512, end))
        if m is not None:
            # The match runs to the first non-ASCII UTF-16 unit; decode
            # forward from the match start until the run breaks.
            raw = bytes(data[m.start(): min(m.start() + 200, end)])
            name = _decode_utf16_ascii(raw)
            name_off = m.start() - block_start
    vendor = data.find(VENDOR, block_start, end)
    release = ""
    if vendor >= 0:
        m = _RELEASE_TOKEN.search(data, vendor, min(vendor + 128, end))
        if m is not None:
            release = m.group(0).decode("ascii")
    return ContainerIdentity(
        block_start=block_start,
        region_size=end - block_start,
        writer_offset=writer - block_start if writer >= 0 else -1,
        cont_name=name,
        cont_name_offset=name_off,
        vendor_offset=vendor - block_start if vendor >= 0 else -1,
        release=release,
    )


def scan_dictionary(data, lo: int, hi: int) -> DictionaryScan:
    """Decode the object id-run records of one dictionary span (BR5-02).

    Walks every ``k 00 04 00`` candidate marker (k = 2..15) and accepts
    it as an id run when the record validates: sane count, the id array
    fits, and the ``00 00`` terminator closes it.  Marker-1 offset
    records are counted (two shapes exist in the corpus; their field
    decode is parked, see the evidence note).  The walk resumes at the
    terminator of each accepted run; rejected candidates advance by one
    marker occurrence, so coverage is measured, not assumed.
    """
    runs: list[IdRun] = []
    offset_markers = 0
    pos = lo
    for m in _MARKER_RE.finditer(data, lo, hi):
        s = m.start()
        if s < pos:
            continue
        k = data[s]
        if k == 1:
            offset_markers += 1
            pos = s + 4
            continue
        if k < _RUN_MARKER_FIRST or k > _RUN_MARKER_LAST:
            continue
        x = int.from_bytes(bytes(data[s + 4: s + 8]), "little")
        flag = data[s + 8]
        # Count-width variants (both byte-verified): the u32le count is
        # the sampled R20/R21 form; R19-era records write a u16le count
        # (``05 00``) with the id array immediately after.  The u16le
        # fallback applies only when the u32le count cannot describe
        # any record in the remaining span — otherwise a u32le record
        # whose terminator fails would re-parse shifted as u16le and
        # accept garbage ids (the shifted-parse negative fixture).
        u32_count = int.from_bytes(bytes(data[s + 9: s + 13]), "little")
        forms = [(u32_count, s + 13)]
        if u32_count * 4 + 15 > hi - s:
            forms.append((int.from_bytes(bytes(data[s + 9: s + 11]), "little"), s + 11))
        for count, ids_at in forms:
            end_ids = ids_at + 4 * count
            if count > _MAX_RUN_COUNT or end_ids + 2 > hi:
                continue
            if bytes(data[end_ids: end_ids + 2]) != b"\x00\x00":
                continue
            ids = struct.unpack_from(f"<{count}I", data, ids_at)
            if not ids or max(ids) >= 0x10000000:
                continue
            runs.append(
                IdRun(marker=k, x=x, flag=flag, ids=ids, start=s, end=end_ids + 2)
            )
            pos = end_ids + 2
            break
    return DictionaryScan(
        runs=tuple(runs), offset_markers=offset_markers, region_size=hi - lo
    )


def _chain_fraction(words: list[bytes]) -> float:
    """Share of consecutive f64 words chaining as a u32le array.

    A u32le array misread as f64 has word ``i``'s high half equal to
    word ``i+1``'s low half (the two u32s chain).  Real knot arrays do
    not.  This is the anti-alias guard's discriminating edge.
    """
    if len(words) < 2:
        return 0.0
    chained = 0
    for a, b in zip(words, words[1:]):
        if a[4:8] == b[0:4]:
            chained += 1
    return chained / (len(words) - 1)


def nurbs_signatures(data, lo: int, hi: int) -> NurbsSignatures:
    """Content-based NURBS payload signatures over ``[lo, hi)`` (BR5-03).

    - *knot-array*: >= 8 consecutive little-endian f64, all finite in
      ``[0, 1e7)`` with the denormal band ``(0, 1e-8)`` excluded (the
      corpus's integer index arrays alias as denormal f64 runs — the
      band cut is the second alias guard, after the chain check),
      non-decreasing, >= 3 distinct values, >= 1 repeat, and
      chain-fraction < 0.75 (the u32-alias guard).  Interior knot
      multiplicity produces the repeats; control-point xyz arrays are
      not non-decreasing, so they do not qualify.
    - *weight*: >= 4 consecutive exact f64 ``1.0`` (rational weights).

    The signatures locate payload, not record semantics: a flagged
    array is not proven to belong to a NURBS record (the exact-model
    record framing is parked), and non-rational splines carry no weight
    array at all.  See the module docstring's honesty line.
    """
    # --- weight runs (exact 1.0 f64)
    weight_runs: list[tuple[int, int]] = []
    pos = lo
    while True:
        i = data.find(_ONE_F64, pos, hi)
        if i < 0:
            break
        j = i
        while j + 8 <= hi and bytes(data[j: j + 8]) == _ONE_F64:
            j += 8
        count = (j - i) // 8
        if count >= 4:
            weight_runs.append((i, count))
        pos = max(j, i + 1)
    # --- knot-array runs (batched f64 unpack, all even byte phases:
    # the corpus's record fields sit at 2- or 4-byte alignment, so an
    # f64 payload array can start at any even offset; odd-start arrays
    # are structurally implausible and remain a named limitation)
    accepted: list[KnotRun] = []
    for phase in (0, 2, 4, 6):
        start = lo + ((phase - lo) % 8)
        n = (hi - start) // 8
        run_start = None
        prev = None
        for idx in range(n + 1):
            if idx < n:
                off = start + idx * 8
                v = struct.unpack_from("<d", data, off)[0]
                ok = (
                    math.isfinite(v)
                    and (v == 0.0 or v >= _KNOT_FLOOR)
                    and v < 1e7
                    and (prev is None or v >= prev - 1e-9)
                )
                if ok:
                    if run_start is None:
                        run_start = off
                    prev = v
                    continue
            if run_start is not None:
                cand = _accept_knot_run(data, run_start, start + idx * 8)
                if cand is not None and not _overlaps(accepted, cand):
                    accepted.append(cand)
            run_start = None
            prev = None
    return NurbsSignatures(
        knot_runs=tuple(accepted), weight_runs=tuple(weight_runs)
    )


def _overlaps(accepted: list[KnotRun], cand: KnotRun) -> bool:
    end = cand.offset + cand.count * 8
    return any(
        r.offset < end and cand.offset < r.offset + r.count * 8 for r in accepted
    )


def _accept_knot_run(data, run_start: int, run_end: int) -> KnotRun | None:
    count = (run_end - run_start) // 8
    if count < 8:
        return None
    vals = struct.unpack_from(f"<{count}d", data, run_start)
    distinct = len(set(vals))
    if distinct < 3 or count - distinct < 1:
        return None
    words = [bytes(data[run_start + k * 8: run_start + k * 8 + 8]) for k in range(count)]
    if _chain_fraction(words) >= 0.75:
        return None
    return KnotRun(
        offset=run_start,
        count=count,
        distinct=distinct,
        repeats=count - distinct,
        lo=vals[0],
        hi=vals[-1],
    )
