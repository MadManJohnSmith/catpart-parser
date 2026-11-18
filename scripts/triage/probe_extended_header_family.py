#!/usr/bin/env python3
"""Probe the extended-header facet family (0x47/0x4f) — 2026-11-18.

The family's header is ``01 <mk> ty b3 b4 ff`` (``ff`` at +5, not +3), so
the committed ``STRIP_RE`` discovery never sees it and the composite
decoder used to leave the records as silent gap bytes. This probe walks
every manifest part's composite stores and validates the byte law on the
discovered records only (no export, no geometry guessing):

- header form: 6-byte, markers 0x47/0x4f; the 12-byte f32le normal rides
  the 0x4f form only;
- ``ty`` = the number of independent triangles stored first in the
  reference block (``3*ty`` refs); ``b3 + b4`` = the counts-table length
  (``b3`` leading strip loops, ``b4`` trailing polygon loops);
- ``sum(counts) + 3*ty == n`` and the record ends at or before the next
  facet header (header-to-header tiling);
- every reference resolves inside the decoded element space;
- the b4 loops of the 0x4f records are coplanar against the stored
  normal (the committed PLANE_TOL battery).

Outputs (docs/evidence/data/br6-extended-header-claims.csv): aggregate
rates per claim + one row per anchored record. Read-only over the corpus;
reproduction command in the evidence note.

Usage:
  python scripts/triage/probe_extended_header_family.py
  python scripts/triage/probe_extended_header_family.py --sha16 76ff90ae634f3346
  python scripts/triage/probe_extended_header_family.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import mmap
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: Featured anchors always committed (the 2026-11-18 evidence note's
#: byte table): the Gabarit store with the 9-record family.
FEATURED_SHA16 = ("76ff90ae634f3346",)
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT = ROOT / "docs" / "evidence" / "data" / "br6-extended-header-claims.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, pool, store  # noqa: E402

FIELDS = [
    "claim",
    "statement",
    "label",
    "scope",
    "release",
    "observations",
    "passes",
    "rate",
    "value",
]


class Tally:
    def __init__(self, claim, statement, scope):
        self.claim = claim
        self.statement = statement
        self.scope = scope
        self.obs = 0
        self.ok = 0

    def add(self, passed):
        self.obs += 1
        self.ok += int(bool(passed))


def probe_part(data, row, tallies, anchor_rows, reading_rows):
    """Validate every extended record of one part's composite stores."""
    size = len(data)
    d8 = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    try:
        blocks = store.valid_blocks(data)
    except Exception:
        return
    seen_spans = set()
    for blk, _name in blocks:
        try:
            span = store.locate_store(data, blk, blocks, d8)
        except Exception:
            continue
        if span is None:
            continue
        key = (span.body_lo, span.body_hi)
        if key in seen_spans:
            continue
        seen_spans.add(key)
        lo, hi = span.body_lo, span.body_hi
        try:
            groups, kinds = pool.scan_pool_groups(data, lo, hi)
            if not pool.has_composite_space(kinds):
                continue
            node = composite.find_list_node(data, lo, hi)
            if node is None:
                continue
            elements, _info = composite.decode_region(node[0], node[1])
        except Exception:
            continue
        elem_decl = node[1]
        records, candidates = composite.parse_extended_facet_records(
            data, lo, hi, elem_decl
        )
        if not candidates:
            continue
        tallies["candidates"].add(1)
        if not records:
            continue
        tallies["records"].add(1)
        if row["sha256"][:16] in FEATURED_SHA16:
            reading_rows.extend(featured_readings(data, row))
        for rec in records:
            tallies["markers"].add(rec.marker in (0x47, 0x4F))
            tallies["loop_count"].add(rec.strips + rec.polygons == len(rec.counts))
            tallies["sum_law"].add(
                len(rec.refs) == 3 * rec.triangles + sum(rec.counts)
            )
            tallies["tiling"].add(rec.end == next_header(data, lo, hi, rec))
            tallies["refs_in_space"].add(
                all(r < elem_decl for r in rec.refs)
            )
            if rec.normal is not None:
                tallies["normal_unit"].add(
                    abs(
                        (rec.normal[0] ** 2 + rec.normal[1] ** 2 + rec.normal[2] ** 2)
                        ** 0.5
                        - 1.0
                    )
                    < 1e-3
                )
                off = 3 * rec.triangles
                for index, count in enumerate(rec.counts):
                    loop = rec.refs[off : off + count]
                    off += count
                    if index < rec.strips or count < 3:
                        continue
                    if any(elements[r][1] is None for r in loop):
                        continue
                    status, _worst = composite._loop_plane_status(
                        loop, rec.normal, elements
                    )
                    tallies["planar_b4"].add(status == "coplanar")
            featured = row["sha256"][:16] in FEATURED_SHA16
            anchor_rows.append(
                {
                    "claim": f"EXTH-09_record_anchor_{row['sha256'][:16]}_{rec.offset}",
                    "featured": featured,
                    "statement": (
                        "record law: marker/ty/b3/b4/n/counts/sum/tiling/refs"
                    ),
                    "label": "fact",
                    "scope": "corpus parts",
                    "release": row["detected_version"] or "unknown",
                    "observations": 1,
                    "passes": int(
                        rec.marker in (0x47, 0x4F)
                        and rec.strips + rec.polygons == len(rec.counts)
                        and len(rec.refs) == 3 * rec.triangles + sum(rec.counts)
                        and rec.end <= hi
                        and all(r < elem_decl for r in rec.refs)
                    ),
                    "rate": "",
                    "value": (
                        f"{row['path']}|store={lo}|mk={rec.marker:#04x}"
                        f"|ty={rec.triangles}|b3={rec.strips}|b4={rec.polygons}"
                        f"|n={len(rec.refs)}|counts_len={len(rec.counts)}"
                    ),
                }
            )


def next_header(data, lo, hi, rec):
    """The next facet header after ``rec`` (or the body end)."""
    from catpart.geometry.facets import STRIP_RE

    following = [m.start() for m in STRIP_RE.finditer(data, rec.offset + 1, hi)]
    extended = [
        o
        for o in composite.facet_headers(data, rec.offset + 1, hi)
        if o > rec.offset
    ]
    positions = sorted(set(following) | set(extended))
    return positions[0] if positions else hi


def featured_readings(data, row):
    """The three candidate readings of one featured part's records.

    Emits claim rows: the pinned split (soup + b3 strips + b4 polygons),
    the strip-only shortcut (each record's whole ref block as one strip)
    and the all-fan reading (every loop fan-triangulated). Areas are
    computed over the written points; loops touching skip slots are
    dropped by all three (the committed curve-entry rule) so the
    comparison isolates the split law.
    """
    from catpart.geometry import mesh

    size = len(data)
    d8 = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    try:
        blocks = store.valid_blocks(data)
    except Exception:
        return []
    for blk, _name in blocks:
        try:
            span = store.locate_store(data, blk, blocks, d8)
        except Exception:
            continue
        if span is None:
            continue
        lo, hi = span.body_lo, span.body_hi
        try:
            groups, kinds = pool.scan_pool_groups(data, lo, hi)
            if not pool.has_composite_space(kinds):
                continue
            node = composite.find_list_node(data, lo, hi)
            if node is None:
                continue
            elements, _info = composite.decode_region(node[0], node[1])
        except Exception:
            continue
        records, _cands = composite.parse_extended_facet_records(
            data, lo, hi, node[1]
        )
        if not records:
            continue
        written_rank = {}
        for i, (_v, pt) in enumerate(elements):
            if pt is not None:
                written_rank[i] = len(written_rank)
        points = [pt for _v, pt in elements if pt is not None]

        def triangles_of(recs, mode):
            out = []
            for rec in recs:
                if mode == "strip_only":
                    # The shortcut: one strip over the record's whole ref
                    # block, triangle-level skip drops (the ticket's
                    # "strip-only" reading).
                    for t in range(len(rec.refs) - 2):
                        tri = rec.refs[t : t + 3]
                        if any(elements[r][1] is None for r in tri):
                            continue
                        idxs = [written_rank[r] for r in tri]
                        if t % 2:
                            idxs = idxs[::-1]
                        out.append(tuple(idxs))
                    continue
                elif mode == "all_fan":
                    loops, kinds_ = [], []
                    o = 0
                    for c in rec.counts:
                        loops.append(rec.refs[o : o + c])
                        kinds_.append(0x4C)
                        o += c
                    o = 0
                    for j in range(0, 3 * rec.triangles, 3):
                        loops.append(rec.refs[j : j + 3])
                        kinds_.append(0x4C)
                else:
                    loops, kinds_ = [], []
                    o = 3 * rec.triangles
                    for index, c in enumerate(rec.counts):
                        loops.append(rec.refs[o : o + c])
                        kinds_.append(0x42 if index < rec.strips else 0x4C)
                        o += c
                    soup = [
                        rec.refs[j : j + 3] for j in range(0, 3 * rec.triangles, 3)
                    ]
                    for loop in soup:
                        if any(elements[r][1] is None for r in loop):
                            continue
                        idxs = [written_rank[r] for r in loop]
                        tris, _deg = composite._loop_triangles(0x42, idxs, points)
                        out.extend(tris)
                for loop, kind in zip(loops, kinds_):
                    if any(elements[r][1] is None for r in loop):
                        continue
                    idxs = [written_rank[r] for r in loop]
                    tris, _deg = composite._loop_triangles(kind, idxs, points)
                    out.extend(tris)
            return out

        def area_and_overuse(tris):
            total = 0.0
            for a, b, c in tris:
                pa, pb, pc = points[a], points[b], points[c]
                u = [pb[i] - pa[i] for i in range(3)]
                v = [pc[i] - pa[i] for i in range(3)]
                cross = (
                    u[1] * v[2] - u[2] * v[1],
                    u[2] * v[0] - u[0] * v[2],
                    u[0] * v[1] - u[1] * v[0],
                )
                total += 0.5 * (
                    cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2
                ) ** 0.5
            stats = mesh.mesh_stats(list(tris))
            return total, stats

        rows = []

        # The escaped-count records (FACT 1): short records whose count
        # position starts with the P1g escape. Their welded loops' area is
        # the ticket's +176 figure.
        prev = {}
        last = None
        for i, (_v, pt) in enumerate(elements):
            if pt is not None:
                last = i
            prev[i] = last
        short, _nh = composite.parse_strip_records(
            data, lo, hi, node[1], elements=elements
        )
        from catpart.geometry.facets import NORMAL_MARKERS_ALL, header_len

        escaped = []
        for offset, mk, _normal, counts, refs, _w in short:
            if len(counts) != 1 or counts[0] != len(refs):
                continue
            hlen = header_len(data, offset)
            counts_pos = offset + hlen + 4 + (
                12 if mk in NORMAL_MARKERS_ALL else 0
            )
            if data[counts_pos] == 0xFF:  # the P1g escape at the count pos
                escaped.append((offset, refs))
        for offset, loop in escaped:
            welded = [prev[r] if elements[r][1] is None else r for r in loop]
            idxs = [written_rank[r] for r in welded]
            tris, _deg = composite._loop_triangles(0x42, idxs, points)
            area, _stats = area_and_overuse(tris)
            rows.append(
                {
                    "claim": f"EXTH-11_escaped_count_record_{offset}",
                    "statement": (
                        "anchor-part short record whose single count is the "
                        "P1g escape: n, welded triangle count and area"
                    ),
                    "label": "fact",
                    "scope": "featured anchor part",
                    "release": row["detected_version"] or "unknown",
                    "observations": 1,
                    "passes": 1,
                    "rate": "",
                    "value": (
                        f"n={len(loop)}|triangles={len(tris)}|area={area:.2f}"
                    ),
                }
            )

        for mode in ("pinned", "strip_only", "all_fan"):
            tris = triangles_of(records, mode)
            area, stats = area_and_overuse(tris)
            over2 = sum(1 for _e, n in _edge_counts(tris).items() if n > 2)
            rows.append(
                {
                    "claim": f"EXTH-10_reading_{mode}",
                    "statement": (
                        "anchor-part reading comparison: area over the "
                        "written points and the assembled edge-use stats"
                    ),
                    "label": "candidate",
                    "scope": "featured anchor part",
                    "release": row["detected_version"] or "unknown",
                    "observations": 1,
                    "passes": int(stats.manifold),
                    "rate": "",
                    "value": (
                        f"triangles={len(tris)}|area={area:.2f}"
                        f"|edges_used_gt2={over2}|closed={int(stats.closed)}"
                    ),
                }
            )
        return rows
    return []


def _edge_counts(tris):
    from collections import Counter

    counts = Counter()
    for tri in tris:
        for i in range(3):
            counts[tuple(sorted((tri[i], tri[(i + 1) % 3])))] += 1
    return counts


def selftest():
    """Synthetic positive/negative fixtures for the record law."""
    def record(marker, ty, b3, b4, counts, refs, normal=None):
        out = bytearray(bytes((0x01, marker, ty, b3, b4, 0xFF)))
        out += struct.pack("<I", len(refs))
        if normal is not None:
            out += struct.pack("<fff", *normal)
        out += bytes(counts)
        out += b"".join(struct.pack(">H", r) for r in refs)
        return bytes(out)

    good = record(0x4F, 2, 1, 1, (5, 7), tuple(range(18)), (0.0, 0.0, 1.0))
    recs, cands = composite.parse_extended_facet_records(
        good, 0, len(good), element_count=64
    )
    assert cands == 1 and len(recs) == 1
    assert recs[0].triangles == 2 and recs[0].strips == 1
    assert recs[0].polygons == 1 and recs[0].counts == (5, 7)
    bad_sum = record(0x47, 2, 1, 1, (5, 7), tuple(range(19)))
    recs, cands = composite.parse_extended_facet_records(
        bad_sum, 0, len(bad_sum), element_count=64
    )
    assert cands == 1 and recs == []
    # n must equal 3*ty + sum(counts); pad the ref block to that law first,
    # then let the element-space bound reject it.
    bad_refs = record(0x47, 1, 1, 0, (3,), (0, 1, 2, 0, 1, 0xFFFF))
    recs, cands = composite.parse_extended_facet_records(
        bad_refs, 0, len(bad_refs), element_count=64
    )
    assert cands == 1 and recs == []
    print("selftest: ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sha16", default="", help="comma-separated sha256[:16] anchors")
    ap.add_argument("--include-sha16", default="", help="same, additive")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument(
        "--max-anchors",
        type=int,
        default=400,
        help="cap on committed per-record anchor rows (aggregate rows always)",
    )
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0

    want = {h for h in (args.sha16 + "," + args.include_sha16).split(",") if h}
    rows = [
        r
        for r in csv.DictReader(MANIFEST.open())
        if r["kind"] == "part" and r["magic_ok"] == "yes"
    ]
    if want:
        rows = [r for r in rows if r["sha256"][:16] in want]

    tallies = {
        "candidates": Tally(
            "EXTH-01_parts_with_extended_candidate",
            "parts carrying >= 1 extended-header (ff at +5) candidate",
            "corpus parts",
        ),
        "records": Tally(
            "EXTH-02_parts_with_accepted_record",
            "parts where >= 1 extended record passes the 2026-11-18 law",
            "corpus parts",
        ),
        "markers": Tally(
            "EXTH-03_marker_in_family",
            "accepted records whose marker is 0x47 or 0x4f",
            "accepted records",
        ),
        "loop_count": Tally(
            "EXTH-04_b3_plus_b4_is_counts_length",
            "records where b3 + b4 equals the counts-table length",
            "accepted records",
        ),
        "sum_law": Tally(
            "EXTH-05_sum_counts_plus_3ty_is_n",
            "records where sum(counts) + 3*ty == n",
            "accepted records",
        ),
        "tiling": Tally(
            "EXTH-06_record_tiles_exactly_to_next_header",
            "records whose last reference ends at the next facet header "
            "(exact tile; gaps are counted by the parser but not here)",
            "accepted records",
        ),
        "refs_in_space": Tally(
            "EXTH-07_refs_inside_element_space",
            "records whose references resolve inside the element space",
            "accepted records",
        ),
        "normal_unit": Tally(
            "EXTH-08a_normal_unit_length",
            "0x4f records whose stored normal is unit length",
            "0x4f records",
        ),
        "planar_b4": Tally(
            "EXTH-08b_b4_loop_coplanar",
            "0x4f polygon (b4) loops coplanar against the stored normal",
            "0x4f b4 loops",
        ),
    }
    anchor_rows = []
    reading_rows = []
    for row in rows:
        path = ROOT / row["local_path"]
        try:
            with path.open("rb") as fh:
                data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
                probe_part(data, row, tallies, anchor_rows, reading_rows)
                data.close()
        except Exception as exc:  # unreadable / malformed: skipped, named
            print(f"skip {row['sha256'][:16]}: {exc}", file=sys.stderr)

    out_rows = []
    for t in tallies.values():
        out_rows.append(
            {
                "claim": t.claim,
                "statement": t.statement,
                "label": "fact" if t.ok == t.obs else "candidate",
                "scope": t.scope,
                "release": "all",
                "observations": t.obs,
                "passes": t.ok,
                "rate": "%.6f" % (t.ok / t.obs) if t.obs else "",
                "value": "",
            }
        )
    # Anchor rows: keep the CSV composable and bounded — the aggregates
    # above carry the rates; the anchors trace a deterministic sample of
    # records (the --sha16 parts sort first in manifest order).
    featured_rows = [r for r in anchor_rows if r.pop("featured", False)]
    rest = [r for r in anchor_rows if "featured" not in r]
    room = max(args.max_anchors - len(featured_rows), 0)
    if len(rest) > room:
        step = len(rest) / room if room else 0
        rest = [rest[int(k * step)] for k in range(room)]
    out_rows.extend(reading_rows)
    out_rows.extend(featured_rows + rest)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out} ({len(out_rows)} rows)")
    for t in tallies.values():
        print(f"  {t.claim:42s} {t.ok:6d}/{t.obs:6d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
