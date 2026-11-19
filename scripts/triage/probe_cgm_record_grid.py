#!/usr/bin/env python3
"""Decisive probe of the CGM record grid: two-family grammar + numeric scan.

Question (ticket #57 follow-up, CGM exact-model container): the
``CGMGeom`` region of the no-pool parts decodes as a *dictionary*
(identity preamble + object id-run records) with no knot/weight runs in
its 1.2 MB.  If the rest of the region is a record grid that tiles
exactly, the geometry could still live in records the dictionary decode
skips; if the grid does not tile, the region cannot be framed and the
exact solids are not reachable from it.

This probe answers that with two measurements, not one:

1. **Grid.**  A two-family grammar is required to tile the region from
   the end of the identity preamble to the region end with **zero
   residue**:

   - family ``idrun``: the shipped object id-run shape
     ``[k 00 04 00][u32 x][u8 flag][u32|u16 count][count u32 ids][00 00]``
     (both count widths, terminator-validated);
   - family ``companion``: ``[01 00 04 00][u32 x][u8 flag][00]
     [(flag+1) u32][u16 count][count u32 ids][00][6B trailer]``, length
     ``31 + 4*flag`` (31/35/39 B for flag 0/1/2; 43/47 for flag 3/4).
     The companion's last id is the record's type word (0x38 / 0x40 in
     the observed head records).  The 6-byte trailer is opaque here: it
     is not validated, so a companion is "framed", not "decoded".

   The grammar is tried in a fixed order (idrun u32 -> companion ->
   idrun u16); the u16 read comes last so a shifted re-read cannot
   swallow a companion (the BR5 width-gate hazard).

2. **Numeric payload.**  Every framed record body and the whole region
   are scanned for an f64 or f32 coordinate triple, a knot vector
   (non-decreasing, 0..1) and a rational-weight run (>= 4 exact 1.0).
   The f64/f32 triple scan reports the raw count and the count after
   the integer-array alias guard (a geometric power-of-two chain is a
   reinterpreted integer array, not coordinates); knot/weight counts
   come from the shipped ``cgm_nurbs.nurbs_signatures`` detector
   (BR5's guards), not a second implementation.

Every figure is reported at **both bounds**: with BR5's id-range guard on
the id list (``CG-08``; the shipped value law, so a count field read off a
shifted byte boundary cannot describe a multi-kilobyte "record" made of
payload bytes) and without it (``CG-08d``; the unguarded upper bound).
``CG-16`` prices the difference, so the guard is measured, not asserted.

Read-only over the corpus; ``src/`` and the exporter are untouched.
Run one file first, then the population:

  export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
  .venv/bin/python -I scripts/triage/probe_cgm_record_grid.py --anchor 80aad8d8
  .venv/bin/python -I scripts/triage/probe_cgm_record_grid.py

The population is the no-pool family of
``docs/evidence/data/stage13-elementspace-census.csv`` split the way
stage 13 splits it: the **128** stores with no facet geometry
(``strip_records`` empty or 0) are the measurement population, and the
three facet carriers (``66049cf3``, ``bf350820``, ``fac22ea3``) are
reported separately as a control.  The 131-row no-pool aggregate is
their sum.  Outputs ``docs/evidence/data/cgm-grid-claims.csv`` (one row
per claim; every prose figure in the evidence note is a row or
arithmetic on fields).
"""

from __future__ import annotations

import argparse
import csv
import math
import mmap
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
POPULATION = ROOT / "docs" / "evidence" / "data" / "stage13-elementspace-census.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "cgm-grid-claims.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.brep import cgm_nurbs  # noqa: E402

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]

#: Companion lengths observed: 31 (flag 0), 35 (flag 1), 39 (flag 2).
#: The length law ``31 + 4*flag`` is what the head deltas measure; flag
#: 3/4 (43/47) are admitted by the law but are not observed in the
#: population (the probe reports the histogram instead of assuming).
COMPANION_BASE = 31
COMPANION_MAX_FLAG = 4
COMPANION_TRAILER = 6
COMPANION_MAX_IDS = 64

#: BR5's object-id range: the shipped dictionary never carries an id at
#: or above 2**28 (largest observed 106,878).  It is a *value* law on the
#: id list, so it applies to both count widths: a count read off a
#: shifted boundary (the u16 width-gate hazard, or a u32 word inside
#: payload bytes) otherwise frames 1-13 KB of payload and calls a chance
#: ``00 00`` a terminator.  ``CG-16`` sizes that swallow; the unguarded
#: run is reported as the upper bound (``CG-08d``), not as framing.
BR5_MAX_ID = 1 << 28

#: Plausible coordinate magnitude for the f32/f64 triple scan.  The
#: CGM region's own integer arrays alias as denormals / tiny f32s, so
#: the floor is what makes a triple mean "number", not "bytes".
TRIPLE_FLOOR = 1e-3
TRIPLE_CEIL = 1e6


@dataclass(frozen=True)
class Record:
    """One framed record.  ``end`` is exclusive."""

    family: str
    start: int
    end: int
    marker: int
    x: int
    flag: int
    count: int
    ids: tuple[int, ...]

    @property
    def type_word(self) -> int:
        """Last id of the record (0 when it carries none).

        The companion family stores its type (0x38 / 0x40 in the head
        records) as the final id; the id-run family's last co-id is not
        a type, so this field is reported only for the field table.
        """
        return self.ids[-1] if self.ids else 0


@dataclass(frozen=True)
class NumericScan:
    """Numeric-payload evidence over one span.

    ``*_values`` keep the guarded triples themselves so the population
    can account for its residuals by value (the note's §5) instead of
    only counting them.
    """

    f64_raw: int
    f64_guarded: int
    f32_raw: int
    f32_guarded: int
    f64_first: tuple[int, tuple[float, float, float]] | None
    f32_first: tuple[int, tuple[float, float, float]] | None
    knot_runs: int
    weight_runs: int
    f64_values: tuple[tuple[float, float, float], ...] = ()
    f32_values: tuple[tuple[float, float, float], ...] = ()


@dataclass(frozen=True)
class Tiling:
    """Grid outcome for one region."""

    region_lo: int
    region_hi: int
    grid_lo: int | None
    records: tuple[Record, ...]
    residue_lo: int | None

    @property
    def preamble(self) -> int:
        return 0 if self.grid_lo is None else self.grid_lo - self.region_lo

    @property
    def framed(self) -> int:
        return sum(r.end - r.start for r in self.records)

    @property
    def residue(self) -> int:
        if self.grid_lo is None:
            return self.region_hi - self.region_lo
        return self.region_hi - (self.grid_lo + self.framed)

    @property
    def exact(self) -> bool:
        return self.grid_lo is not None and self.residue == 0

    @property
    def coverage(self) -> float:
        body = self.region_hi - self.region_lo - self.preamble
        return 0.0 if body <= 0 else self.framed / body


def _u32(data, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def _u16(data, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def _is_marker(data, off: int, hi: int) -> bool:
    """``k 00 04 00`` for k in 0..15 (the observed marker alphabet)."""
    return (
        off + 4 <= hi
        and data[off] < 16
        and data[off + 1] == 0
        and data[off + 2] == 4
        and data[off + 3] == 0
    )


def _idrun(data, pos: int, hi: int, width: int, id_max: int | None = None) -> Record | None:
    """Object id-run record with a u32 or u16 count field."""
    if not _is_marker(data, pos, hi):
        return None
    if width == 32:
        count, ids_at = _u32(data, pos + 9), pos + 13
    else:
        count, ids_at = _u16(data, pos + 9), pos + 11
    if not 0 < count < 200_000 or ids_at + 4 * count + 2 > hi:
        return None
    if bytes(data[ids_at + 4 * count : ids_at + 4 * count + 2]) != b"\x00\x00":
        return None
    ids = struct.unpack_from(f"<{count}I", data, ids_at)
    # BR5's value law on the id list: without it a shifted count read
    # frames payload bytes as one huge record (CG-16 measures how much).
    if id_max is not None and ids and max(ids) >= id_max:
        return None
    return Record(
        family=f"idrun{width}",
        start=pos,
        end=ids_at + 4 * count + 2,
        marker=data[pos],
        x=_u32(data, pos + 4),
        flag=data[pos + 8],
        count=count,
        ids=ids,
    )


def _companion(data, pos: int, hi: int) -> Record | None:
    """The 31/35/39-byte companion (length ``31 + 4*flag``).

    Fixed fields: marker 1, a 00 byte at +9, ``flag + 1`` u32 words,
    then a u16 count, the count ids, one 00 byte and the 6-byte opaque
    trailer.  The count is bounded and the closing 00 is validated; the
    trailer is not interpreted.
    """
    if pos + COMPANION_BASE > hi or bytes(data[pos : pos + 4]) != b"\x01\x00\x04\x00":
        return None
    if data[pos + 9] != 0:
        return None
    flag = data[pos + 8]
    if flag > COMPANION_MAX_FLAG:
        return None
    end = pos + COMPANION_BASE + 4 * flag
    if end > hi:
        return None
    count_at = pos + 10 + 4 * (flag + 1)
    count = _u16(data, count_at)
    if not 1 <= count <= COMPANION_MAX_IDS:
        return None
    ids_at = count_at + 2
    if ids_at + 4 * count + 1 + COMPANION_TRAILER != end:
        return None
    if data[ids_at + 4 * count] != 0:
        return None
    ids = struct.unpack_from(f"<{count}I", data, ids_at)
    return Record(
        family="companion",
        start=pos,
        end=end,
        marker=1,
        x=_u32(data, pos + 4),
        flag=flag,
        count=count,
        ids=ids,
    )


def parse_record(data, pos: int, hi: int, id_max: int | None = None) -> Record | None:
    """Parse one record at ``pos`` in the fixed family order.

    u32 id-run first, companion second, u16 id-run last: the companion
    starts with ``01 00 04 00`` and its payload can look like a shifted
    u16 id-run, so the u16 read must not win that race.  ``id_max`` is
    the shipped id-range guard; ``None`` gives the unguarded upper bound.
    """
    return (
        _idrun(data, pos, hi, 32, id_max)
        or _companion(data, pos, hi)
        or _idrun(data, pos, hi, 16, id_max)
    )


def grid_start(data, lo: int, hi: int, id_max: int | None = None) -> int | None:
    """First offset where a record parse starts a *runnable* grid.

    The identity preamble is not a record; requiring the next position to
    parse too keeps a stray marker inside the preamble from becoming the
    grid's start.
    """
    for pos in range(lo, max(lo, hi - 4)):
        rec = parse_record(data, pos, hi, id_max)
        if rec is None:
            continue
        if rec.end >= hi or parse_record(data, rec.end, hi, id_max) is not None:
            return pos
    return None


def walk(data, lo: int, hi: int, id_max: int | None = None) -> Tiling:
    """Tile ``[lo, hi)`` with the two-family grammar."""
    start = grid_start(data, lo, hi, id_max)
    if start is None:
        return Tiling(lo, hi, None, (), lo)
    records: list[Record] = []
    pos = start
    while pos < hi:
        rec = parse_record(data, pos, hi, id_max)
        if rec is None:
            break
        records.append(rec)
        pos = rec.end
    return Tiling(lo, hi, start, tuple(records), None if pos >= hi else pos)


def _pow2_chain(a: float, b: float, eps: float = 1e-3) -> bool:
    """True when ``b/a`` is a power of two (integer-array alias)."""
    if a == 0.0 or b == 0.0:
        return False
    ratio = abs(b / a)
    if ratio <= 0.0:
        return False
    log = math.log2(ratio)
    return abs(log - round(log)) < eps


def _fixed_point_ramp(triple: tuple[float, float, float]) -> bool:
    """True when the triple is an arithmetic ramp with a 2**-k step.

    Fixed-point index arrays narrowed to f32 read as uniform ramps whose
    step is exactly ``2**-k`` (the corpus's in-record hits step by
    2**-16); coordinates are not that regular.
    """
    d1 = triple[1] - triple[0]
    d2 = triple[2] - triple[1]
    if d1 == 0.0 or abs(d1 - d2) > 1e-12 * max(1.0, abs(d1)):
        return False
    log = math.log2(abs(d1))
    return abs(log - round(log)) < 1e-9


def _ascii_word(data, off: int, size: int) -> bool:
    return all(32 <= b < 127 for b in bytes(data[off : off + size]))


def _triple_alias(data, off: int, triple: tuple[float, float, float], size: int) -> str | None:
    """Name the alias that makes this "triple" not a coordinate array."""
    if len(set(triple)) < 2:
        return "const"
    if _ascii_word(data, off, 3 * size):
        return "ascii"
    if _pow2_chain(triple[0], triple[1]) and _pow2_chain(triple[1], triple[2]):
        return "pow2"
    if _fixed_point_ramp(triple):
        return "ramp"
    return None


def _triple_scan(
    data, lo: int, hi: int, fmt: str, width: int
) -> tuple[int, int, tuple | None, tuple[tuple[float, float, float], ...]]:
    """Count coordinate triples, raw and after the alias guards."""
    raw = guarded = 0
    first = None
    values: list[tuple[float, float, float]] = []
    for phase in range(width):
        start = lo + phase
        n = (hi - start) // width
        run: list[float] = []
        for i in range(n):
            off = start + i * width
            value = struct.unpack_from(fmt, data, off)[0]
            if math.isfinite(value) and TRIPLE_FLOOR <= abs(value) <= TRIPLE_CEIL:
                run.append(value)
                if len(run) >= 3:
                    raw += 1
                    triple = (run[-3], run[-2], run[-1])
                    if _triple_alias(data, off - 2 * width, triple, width) is None:
                        guarded += 1
                        values.append(triple)
                        if first is None:
                            first = (off - 2 * width, triple)
            else:
                run = []
    return raw, guarded, first, tuple(values)


def numeric_scan(data, lo: int, hi: int) -> NumericScan:
    """f64/f32 triples plus the shipped knot/weight detector over a span."""
    f64_raw, f64_guarded, f64_first, f64_values = _triple_scan(data, lo, hi, "<d", 8)
    f32_raw, f32_guarded, f32_first, f32_values = _triple_scan(data, lo, hi, "<f", 4)
    signatures = cgm_nurbs.nurbs_signatures(data, lo, hi)
    return NumericScan(
        f64_raw=f64_raw,
        f64_guarded=f64_guarded,
        f32_raw=f32_raw,
        f32_guarded=f32_guarded,
        f64_first=f64_first,
        f32_first=f32_first,
        knot_runs=len(signatures.knot_runs),
        weight_runs=len(signatures.weight_runs),
        f64_values=f64_values,
        f32_values=f32_values,
    )


def framed_scan(data, tiling: Tiling) -> NumericScan:
    """Numeric scan restricted to the framed record bodies."""
    scan = NumericScan(0, 0, 0, 0, None, None, 0, 0, (), ())
    for rec in tiling.records:
        scan = _merge_scans(scan, numeric_scan(data, rec.start, rec.end))
    return scan


def residue_cadence(data, tiling: Tiling, top: int = 8) -> tuple[int, list[tuple[int, int]]]:
    """Marker count and marker-to-marker deltas inside the residue.

    A refusal that is *noise* has no cadence; a further record stream
    does.  The histogram is what the note's §6 uses to say which of the
    two the residue is, without fitting a third family to it.
    """
    if tiling.residue_lo is None:
        return 0, []
    lo, hi = tiling.residue_lo, tiling.region_hi
    marks = [off for off in range(lo, max(lo, hi - 3)) if _is_marker(data, off, hi)]
    deltas = Counter(b - a for a, b in zip(marks, marks[1:]))
    return len(marks), deltas.most_common(top)


def _marker_histogram(data, lo: int, hi: int) -> Counter:
    return Counter(
        int(data[off]) for off in range(lo, hi - 3) if _is_marker(data, off, hi)
    )


def _residue_head(data, residue_lo: int) -> str:
    """First 12 bytes at the unframed offset (what the grammar refused)."""
    return bytes(data[residue_lo : residue_lo + 12]).hex(" ")


def _region(data, name: str = cgm_nurbs.CGM_BLOCK_NAME):
    for block, block_name, region_end in cgm_nurbs.valid_regions(data):
        if block_name == name:
            yield block, region_end


def measure(
    data, name: str = cgm_nurbs.CGM_BLOCK_NAME, id_max: int | None = None
) -> tuple[Tiling, NumericScan, NumericScan]:
    """Tile and numeric-scan (region and framed bodies) one part."""
    tilings = []
    scans = []
    for block, region_end in _region(data, name):
        tilings.append(walk(data, block, region_end, id_max))
        scans.append(numeric_scan(data, block, region_end))
    if not tilings:
        raise SystemExit(f"no {name} region")
    tiling = tilings[0]
    scan = scans[0]
    for extra_tiling, extra_scan in zip(tilings[1:], scans[1:]):
        tiling = _merge_tilings(tiling, extra_tiling)
        scan = _merge_scans(scan, extra_scan)
    return tiling, scan, framed_scan(data, tiling)


def _merge_tilings(a: Tiling, b: Tiling) -> Tiling:
    return Tiling(
        a.region_lo,
        b.region_hi,
        a.grid_lo,
        a.records + b.records,
        a.residue_lo if a.residue_lo is not None else b.residue_lo,
    )


def _merge_scans(a: NumericScan, b: NumericScan) -> NumericScan:
    return NumericScan(
        f64_raw=a.f64_raw + b.f64_raw,
        f64_guarded=a.f64_guarded + b.f64_guarded,
        f32_raw=a.f32_raw + b.f32_raw,
        f32_guarded=a.f32_guarded + b.f32_guarded,
        f64_first=a.f64_first or b.f64_first,
        f32_first=a.f32_first or b.f32_first,
        knot_runs=a.knot_runs + b.knot_runs,
        weight_runs=a.weight_runs + b.weight_runs,
        f64_values=a.f64_values + b.f64_values,
        f32_values=a.f32_values + b.f32_values,
    )


def _rate(num: int, den: int) -> str:
    return "" if den <= 0 else f"{num / den:.4f}"


def _tiling_detail(label: str, tiling: Tiling) -> str:
    return (
        f"{label}: region={tiling.region_hi - tiling.region_lo} "
        f"preamble={tiling.preamble} records={len(tiling.records)} "
        f"framed={tiling.framed} residue={tiling.residue} "
        f"exact={int(tiling.exact)}"
    )


def field_table(tiling: Tiling, limit: int = 12) -> list[list[str]]:
    """Field table rows: marker, x, flag, count, ids, type."""
    rows = [["family", "offset", "length", "marker", "x", "flag", "count", "ids", "type"]]
    for rec in tiling.records[:limit]:
        rows.append(
            [
                rec.family,
                str(rec.start - tiling.region_lo),
                str(rec.end - rec.start),
                f"0x{rec.marker:02x}",
                f"0x{rec.x:x}",
                f"0x{rec.flag:02x}",
                str(rec.count),
                " ".join(str(i) for i in rec.ids[:8]) + (" ..." if len(rec.ids) > 8 else ""),
                f"0x{rec.type_word:x}",
            ]
        )
    return rows


def _print_table(rows: list[list[str]]) -> None:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip())


def _census_rows(path: Path, family: str) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if r["family"] == family]


def split_facet_carriers(rows: list[dict]) -> tuple[list[str], list[str]]:
    """Stage-13's split of the no-pool family.

    ``strip_records`` non-empty/non-zero marks a store that carries facet
    records; those three are the control group.  The other rows are the
    128 stores stage 13 documents as carrying no facet geometry, and they
    are the population this probe measures.
    """
    primary: list[str] = []
    carriers: list[str] = []
    for row in rows:
        target = carriers if row.get("strip_records", "").strip() not in ("", "0") else primary
        target.append(row["sha256"])
    return primary, carriers


def _load_manifest() -> dict[str, str]:
    with MANIFEST.open(newline="", encoding="utf-8") as fh:
        return {r["sha256"]: r["local_path"] for r in csv.DictReader(fh)}


def run_anchor(
    sha16: str, manifest: dict[str, str]
) -> tuple[list[list[str]], Tiling, NumericScan, NumericScan]:
    path = next(
        (p for sha, p in manifest.items() if sha.startswith(sha16)),
        None,
    )
    if path is None:
        raise SystemExit(f"{sha16} not in the manifest")
    with (ROOT / path).open("rb") as fh:
        data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        tiling, scan, framed = measure(data, id_max=BR5_MAX_ID)
        markers = _marker_histogram(data, tiling.region_lo, tiling.region_hi)
        comp_flags = Counter(r.flag for r in tiling.records if r.family == "companion")
        types = Counter(r.type_word for r in tiling.records if r.family == "companion")
        families = Counter(r.family for r in tiling.records)
        identity = cgm_nurbs.parse_identity(data, tiling.region_lo, tiling.region_hi)
        cadence = residue_cadence(data, tiling)
        rows = [
            [
                "CG-01",
                sha16,
                "1",
                "1",
                "",
                "fact",
                f"CGMGeom abs [{tiling.region_lo}, {tiling.region_hi}) "
                f"size={tiling.region_hi - tiling.region_lo} "
                f"writer_offset={identity.writer_offset} "
                f"cont_name={identity.cont_name}",
            ],
            [
                "CG-02",
                sha16,
                str(sum(markers.values())),
                "1",
                _rate(markers[1], sum(markers.values())),
                "fact",
                "markers: "
                + " ".join(f"k{k}={markers[k]}" for k in sorted(markers))
                + "; raw 01000400="
                + str(bytes(data[tiling.region_lo : tiling.region_hi]).count(b"\x01\x00\x04\x00"))
                + " raw 02000400="
                + str(bytes(data[tiling.region_lo : tiling.region_hi]).count(b"\x02\x00\x04\x00")),
            ],
            [
                "CG-03",
                sha16,
                str(len(tiling.records)),
                str(int(tiling.exact)),
                _rate(tiling.framed, tiling.region_hi - tiling.region_lo - tiling.preamble),
                "fact",
                _tiling_detail("anchor", tiling),
            ],
            [
                "CG-04",
                sha16,
                str(len(tiling.records)),
                str(len(tiling.records)),
                "",
                "fact",
                "families="
                + " ".join(f"{k}={v}" for k, v in sorted(families.items()))
                + "; companion flag="
                + " ".join(f"{k}={v}" for k, v in sorted(comp_flags.items()))
                + "; companion type="
                + " ".join(f"0x{k:x}={v}" for k, v in sorted(types.items())[:8]),
            ],
        ]
        if tiling.residue_lo is not None:
            rows.append(
                [
                    "CG-05",
                    sha16,
                    "1",
                    "0",
                    "",
                    "fact",
                    "first refused offset="
                    f"{tiling.residue_lo} residue_head={_residue_head(data, tiling.residue_lo)}",
                ]
            )
        rows.append(
            [
                "CG-06",
                sha16,
                "1",
                "1" if scan.f64_guarded == 0 and scan.f32_guarded == 0 else "0",
                "",
                "fact",
                f"region: f64_triples_raw={scan.f64_raw} f64_triples_guarded={scan.f64_guarded} "
                f"f32_triples_raw={scan.f32_raw} f32_triples_guarded={scan.f32_guarded} "
                f"knot_runs={scan.knot_runs} weight_runs={scan.weight_runs}",
            ]
        )
        rows.append(
            [
                "CG-07",
                sha16,
                str(len(tiling.records)),
                "1" if framed.f64_guarded == 0 and framed.f32_guarded == 0 else "0",
                "",
                "fact",
                f"framed bodies only: f64_triples_raw={framed.f64_raw} "
                f"f64_triples_guarded={framed.f64_guarded} "
                f"f32_triples_raw={framed.f32_raw} f32_triples_guarded={framed.f32_guarded} "
                f"knot_runs={framed.knot_runs} weight_runs={framed.weight_runs}",
            ]
        )
        if tiling.residue_lo is not None:
            rows.append(
                [
                    "CG-13",
                    sha16,
                    str(len(tiling.records)),
                    "0",
                    "",
                    "fact",
                    "residue markers="
                    + str(cadence[0])
                    + " top_deltas="
                    + " ".join(f"{d}:{n}" for d, n in cadence[1]),
                ]
            )
        return rows, tiling, scan, framed


def run_population(
    shas: list[str], manifest: dict[str, str], id_max: int | None = BR5_MAX_ID
) -> list[dict]:
    """Measure every part; return one measurement dict per part."""
    per_file: list[dict] = []
    for sha in shas:
        path = manifest[sha]
        with (ROOT / path).open("rb") as fh:
            data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            tiling, scan, framed = measure(data, id_max=id_max)
        per_file.append(
            {
                "sha16": sha[:8],
                "bytes": tiling.region_hi - tiling.region_lo,
                "preamble": tiling.preamble,
                "framed": tiling.framed,
                "residue": tiling.residue,
                "exact": tiling.exact,
                "coverage": tiling.coverage,
                "records": len(tiling.records),
                "f64_raw": scan.f64_raw,
                "f64_guarded": scan.f64_guarded,
                "f32_raw": scan.f32_raw,
                "f32_guarded": scan.f32_guarded,
                "knot_runs": scan.knot_runs,
                "weight_runs": scan.weight_runs,
                "f32_region_values": scan.f32_values,
                "framed_f64_raw": framed.f64_raw,
                "framed_f64_guarded": framed.f64_guarded,
                "framed_f32_raw": framed.f32_raw,
                "framed_f32_guarded": framed.f32_guarded,
                "framed_knot_runs": framed.knot_runs,
                "framed_weight_runs": framed.weight_runs,
                "f32_framed_values": framed.f32_values,
            }
        )
    return per_file


def _aggregate(per_file: list[dict]) -> dict:
    return {
        "regions": len(per_file),
        "bytes": sum(r["bytes"] for r in per_file),
        "preamble": sum(r["preamble"] for r in per_file),
        "framed": sum(r["framed"] for r in per_file),
        "residue": sum(r["residue"] for r in per_file),
        "exact": sum(1 for r in per_file if r["exact"]),
        "nogrid": sum(1 for r in per_file if r["records"] == 0),
    }


def _aggregate_row(claim: str, scope: str, per_file: list[dict]) -> list[str]:
    agg = _aggregate(per_file)
    body = agg["bytes"] - agg["preamble"]
    partial = agg["regions"] - agg["exact"] - agg["nogrid"]
    return [
        claim,
        scope,
        str(agg["regions"]),
        str(agg["exact"]),
        _rate(agg["framed"], body),
        "fact",
        f"regions={agg['regions']} bytes={agg['bytes']} preamble={agg['preamble']} "
        f"framed={agg['framed']} residue={agg['residue']} body={body} "
        f"exact={agg['exact']} partial={partial} nogrid={agg['nogrid']}",
    ]


def _fmt_triple(triple: tuple[float, float, float]) -> str:
    return "(" + ", ".join(f"{v:.9g}" for v in triple) + ")"


def _residual_row(claim: str, scope: str, per_file: list[dict], field: str) -> list[str]:
    """Guarded f32 triples by value: the §5 alias accounting, measured."""
    hits: Counter = Counter()
    files: Counter = Counter()
    for r in per_file:
        values = r[field]
        hits.update(values)
        for triple in set(values):
            files[triple] += 1
    top = hits.most_common(1)
    detail = "top=none"
    if top:
        triple, count = top[0]
        detail = f"top={_fmt_triple(triple)} hits={count} files={files[triple]}"
    return [
        claim,
        scope,
        str(len(per_file)),
        "0",
        "",
        "fact",
        f"guarded={sum(hits.values())} distinct={len(hits)} {detail}",
    ]


def guard_footprint(
    shas: list[str], manifest: dict[str, str], guarded: list[dict], upper: list[dict]
) -> dict:
    """What the id-range guard refuses: the bytes the unguarded read calls framing.

    One extra unguarded pass, kept off the measurement path, so ``CG-16``
    can name the swallow (bytes, families, longest record) instead of
    asserting it.  A record counts as swallowed when an id in its list is
    at or above ``BR5_MAX_ID`` — that is precisely the record the guard
    removes.
    """
    files = 0
    by_family: Counter = Counter()
    swallowed = 0
    longest = 0
    for sha, low, high in zip(shas, guarded, upper):
        if (low["framed"], low["records"]) == (high["framed"], high["records"]):
            continue
        files += 1
        with (ROOT / manifest[sha]).open("rb") as fh:
            data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            tiling = measure(data, id_max=None)[0]
        for rec in tiling.records:
            if rec.ids and max(rec.ids) >= BR5_MAX_ID:
                by_family[rec.family] += 1
                swallowed += rec.end - rec.start
                longest = max(longest, rec.end - rec.start)
    return {
        "files": files,
        "swallowed": swallowed,
        "by_family": by_family,
        "longest": longest,
        "exact_unguarded": sum(1 for r in upper if r["exact"]),
        "exact_guarded": sum(1 for r in guarded if r["exact"]),
        "nogrid_guarded": sum(1 for r in guarded if r["records"] == 0),
        "nogrid_unguarded": sum(1 for r in upper if r["records"] == 0),
    }


def _footprint_row(per_file: list[dict], upper: list[dict], footprint: dict) -> list[str]:
    """``CG-16``: the guard's footprint, in bytes and in reframed files."""
    framed_delta = sum(r["framed"] for r in upper) - sum(r["framed"] for r in per_file)
    families = " ".join(f"{k}={v}" for k, v in sorted(footprint["by_family"].items())) or "none"
    return [
        "CG-16",
        f"population:{len(per_file)}",
        str(footprint["files"]),
        "0",
        "",
        "fact",
        f"files_reframed={footprint['files']} framed_delta={framed_delta} "
        f"swallowed={footprint['swallowed']} families={families} "
        f"longest={footprint['longest']} "
        f"exact guarded={footprint['exact_guarded']} unguarded={footprint['exact_unguarded']} "
        f"nogrid guarded={footprint['nogrid_guarded']} "
        f"unguarded={footprint['nogrid_unguarded']}",
    ]


def per_file_claims(
    per_file: list[dict],
    carriers: list[dict],
    upper: list[dict],
    upper_carriers: list[dict],
    footprint: dict | None = None,
) -> list[list[str]]:
    """Claim rows for the 128 population, its 131 superset and the control.

    ``per_file``/``carriers`` are the guarded (shipped id-range) run;
    ``upper``/``upper_carriers`` are the same parts tiled with count +
    terminator only, the unguarded upper bound.  ``footprint`` (from
    :func:`guard_footprint`) adds ``CG-16``, the price of the guard.
    """
    everything = per_file + carriers
    rows = [
        _aggregate_row("CG-08", f"population:{len(per_file)}", per_file),
        _aggregate_row("CG-08b", f"population:{len(everything)}", everything),
        _aggregate_row("CG-08c", f"population:{len(carriers)}", carriers),
        _aggregate_row("CG-08d", f"population:{len(upper)}:unguarded", upper),
        _aggregate_row("CG-08e", f"population:{len(upper) + len(upper_carriers)}:unguarded", upper + upper_carriers),
        [
            "CG-09",
            f"population:{len(per_file)}",
            str(len(per_file)),
            str(_aggregate(per_file)["exact"]),
            _rate(_aggregate(per_file)["exact"], len(per_file)),
            "fact",
            "per-file outcome: exact="
            + str(_aggregate(per_file)["exact"])
            + " partial="
            + str(
                len(per_file) - _aggregate(per_file)["exact"] - _aggregate(per_file)["nogrid"]
            )
            + " nogrid="
            + str(_aggregate(per_file)["nogrid"])
            + "; coverage quartiles="
            + " ".join(
                f"{q}={sorted(r['coverage'] for r in per_file)[int(q * (len(per_file) - 1))]:.4f}"
                for q in (0.25, 0.5, 0.75)
            ),
        ],
        [
            "CG-10",
            f"population:{len(per_file)}",
            str(len(per_file)),
            "1" if per_file else "0",
            "",
            "fact",
            f"region scan: f64_triples_raw={sum(r['f64_raw'] for r in per_file)} "
            f"f64_triples_guarded={sum(r['f64_guarded'] for r in per_file)} "
            f"f32_triples_raw={sum(r['f32_raw'] for r in per_file)} "
            f"f32_triples_guarded={sum(r['f32_guarded'] for r in per_file)} "
            f"knot_runs={sum(r['knot_runs'] for r in per_file)} "
            f"weight_runs={sum(r['weight_runs'] for r in per_file)}",
        ],
        [
            "CG-11",
            f"population:{len(per_file)}",
            str(len(per_file)),
            "1" if per_file else "0",
            "",
            "fact",
            f"framed bodies only: f64_triples_raw={sum(r['framed_f64_raw'] for r in per_file)} "
            f"f64_triples_guarded={sum(r['framed_f64_guarded'] for r in per_file)} "
            f"f32_triples_raw={sum(r['framed_f32_raw'] for r in per_file)} "
            f"f32_triples_guarded={sum(r['framed_f32_guarded'] for r in per_file)} "
            f"knot_runs={sum(r['framed_knot_runs'] for r in per_file)} "
            f"weight_runs={sum(r['framed_weight_runs'] for r in per_file)}",
        ],
        _residual_row("CG-14", f"population:{len(per_file)}", per_file, "f32_region_values"),
        _residual_row("CG-14b", f"population:{len(everything)}", everything, "f32_region_values"),
        _residual_row("CG-15", f"population:{len(per_file)}", per_file, "f32_framed_values"),
    ]
    if footprint is not None:
        rows.append(_footprint_row(per_file, upper, footprint))
    return rows


def _claim_rank(claim: str) -> tuple[int, str]:
    """Order ``CG-08``, ``CG-08b``, ``CG-09``, ... as the note numbers them."""
    number = claim.split("-", 1)[1]
    digits = number.rstrip("abcdefghijklmnopqrstuvwxyz")
    return int(digits), number[len(digits) :]


def write_claims(rows: list[list[str]], out: Path = OUT_CLAIMS) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CLAIM_FIELDS)
        writer.writerows(sorted(rows, key=lambda row: _claim_rank(row[0])))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--anchor", default="80aad8d8", help="sha16 of the worked example")
    parser.add_argument(
        "--population",
        type=Path,
        default=POPULATION,
        help="census CSV with a family column (default: stage13 no-pool)",
    )
    parser.add_argument("--family", default="no-pool")
    parser.add_argument("--limit", type=int, default=0, help="cap the population (0 = all)")
    parser.add_argument("--out", type=Path, default=OUT_CLAIMS)
    parser.add_argument(
        "--no-population", action="store_true", help="anchor only (one-file first run)"
    )
    args = parser.parse_args(argv)

    manifest = _load_manifest()
    rows: list[list[str]] = []
    anchor_rows, tiling, scan, framed = run_anchor(args.anchor, manifest)
    rows.extend(anchor_rows)

    print(f"== anchor {args.anchor}: region {tiling.region_lo}..{tiling.region_hi}")
    print(
        f"   records={len(tiling.records)} framed={tiling.framed} "
        f"residue={tiling.residue} coverage={tiling.coverage:.4f} exact={tiling.exact}"
    )
    print("   field table (first records):")
    _print_table(field_table(tiling))

    if not args.no_population:
        primary, carriers = split_facet_carriers(_census_rows(args.population, args.family))
        if args.limit:
            primary = primary[: args.limit]
        per_file = run_population(primary, manifest)
        carrier_file = run_population(carriers, manifest)
        upper = run_population(primary, manifest, id_max=None)
        upper_carriers = run_population(carriers, manifest, id_max=None)
        footprint = guard_footprint(primary, manifest, per_file, upper)
        rows.extend(per_file_claims(per_file, carrier_file, upper, upper_carriers, footprint))
        exact_files = sum(1 for r in per_file if r["exact"])
        framed_bytes = sum(r["framed"] for r in per_file)
        residue_bytes = sum(r["residue"] for r in per_file)
        total = sum(r["bytes"] for r in per_file)
        preamble = sum(r["preamble"] for r in per_file)
        print(
            f"== population {len(per_file)} (guarded): bytes={total} preamble={preamble} "
            f"framed={framed_bytes} residue={residue_bytes} "
            f"coverage={framed_bytes / (total - preamble):.4f} exact={exact_files} "
            f"nogrid={footprint['nogrid_guarded']}"
        )
        upper_framed = sum(r["framed"] for r in upper)
        upper_preamble = sum(r["preamble"] for r in upper)
        print(
            f"== population {len(upper)} (unguarded upper bound): "
            f"framed={upper_framed} residue={sum(r['residue'] for r in upper)} "
            f"coverage={upper_framed / (total - upper_preamble):.4f} "
            f"exact={sum(1 for r in upper if r['exact'])} "
            f"nogrid={footprint['nogrid_unguarded']}"
        )
        print(
            f"== guard footprint: files_reframed={footprint['files']} "
            f"framed_delta={upper_framed - framed_bytes} "
            f"swallowed={footprint['swallowed']} longest={footprint['longest']} "
            + " ".join(f"{k}={v}" for k, v in sorted(footprint["by_family"].items()))
        )
        print(
            "   region numeric: "
            f"f64_guarded={sum(r['f64_guarded'] for r in per_file)} "
            f"f32_guarded={sum(r['f32_guarded'] for r in per_file)} "
            f"knots={sum(r['knot_runs'] for r in per_file)} "
            f"weights={sum(r['weight_runs'] for r in per_file)}"
        )
        print(
            "   framed numeric: "
            f"f64_guarded={sum(r['framed_f64_guarded'] for r in per_file)} "
            f"f32_guarded={sum(r['framed_f32_guarded'] for r in per_file)} "
            f"knots={sum(r['framed_knot_runs'] for r in per_file)} "
            f"weights={sum(r['framed_weight_runs'] for r in per_file)}"
        )
        if carrier_file:
            print(
                f"   control (facet carriers) {len(carrier_file)}: "
                f"bytes={sum(r['bytes'] for r in carrier_file)} "
                f"framed={sum(r['framed'] for r in carrier_file)} "
                f"residue={sum(r['residue'] for r in carrier_file)}"
            )

    numeric = framed.f64_guarded + framed.knot_runs + framed.weight_runs
    if tiling.exact and numeric:
        verdict = "exact tiling; numeric array present -> report family and next step"
    elif tiling.exact:
        verdict = "exact tiling and no numeric array -> CGM region cannot yield exact solids"
    else:
        verdict = (
            "no exact tiling at the bar (coverage "
            f"{tiling.coverage:.4f}, residue {tiling.residue} B) and no numeric array "
            "-> the grid cannot be framed; STOP, open-ended class-header RE"
        )
    rows.append(
        [
            "CG-12",
            args.anchor,
            "1",
            "1",
            _rate(tiling.framed, tiling.region_hi - tiling.region_lo - tiling.preamble),
            "inference",
            f"exact={int(tiling.exact)} numeric_arrays={numeric} "
            f"f64_triples={framed.f64_guarded} knot_runs={framed.knot_runs} "
            f"weight_runs={framed.weight_runs} f32_guarded={framed.f32_guarded} "
            f"(alias-accounted) verdict={verdict}",
        ]
    )
    write_claims(rows, args.out)
    print("== verdict:", verdict)
    print("claims ->", args.out)
    return 0 if tiling.exact else 2


if __name__ == "__main__":
    raise SystemExit(main())
