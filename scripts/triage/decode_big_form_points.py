#!/usr/bin/env python3
"""Big-form point regions decoded via the 2-bit table (G6 stage 3b, #34).

Byte decode of the list-node point region driven by the per-element
2-bit table (U1, solved 2026-11-11) and the segment bookkeeping it
implies (U3): the region is ONE table + ONE P1g write count + the
writes, on both forms.  Analysis + decoder only — ``src/`` untouched
(the exporter integration of big form is a later stage).

Model (docs/evidence/2026-11-10-node-streams.md, stage-3b refinements
dated 2026-11-11, byte-measured on the corpus):

- Layout (P1t refined): payload = header + token ``ff ff 02 00 01`` +
  the declared counts (element_count, edge_ref_bound, P1g) + a zero
  block + **the 2-bit table: exactly ceil(element_count / 4) bytes**
  (the stage-2c "+1 byte" was the write-count byte miscounted into the
  table span) + **a P1g count** (1 B, ff escapes to u32le) of the
  region's f32 words + **the point region** (count x f32) + a trailing
  region (U2, open).
- Table semantics (U1, fact on the anchors): 2 bits per element,
  LSB-first within each byte, one slot per element in region order:
  value 0 = ``[x][y][z]`` full write (3 f32, x-group start), value 1 =
  skip (the element carries no coordinates in the region — the curve
  entries, U4), value 2 = ``[z]`` (1 f32), value 3 = ``[y][z]``
  (2 f32).  The initial LCP state is the origin (P1i subsumed: the
  first write's shape comes from the table like every other).  The
  walk is deterministic: no DP, no probe — it consumes exactly
  ``write_count`` f32 words.
- Segments (U3, resolved): there are no separate segment tables and no
  segment headers — the single table IS the bookkeeping.  Value-0
  slots delimit the x-groups/runs (P1r); the big-store corner groups
  sit out of x order at their element slots (70b59f2a: elements
  1812-1819, table pattern 0,2,3,2 = [x][y][z],[z],[y][z],[z] each)
  after ONE x-break; the region is otherwise lex-ascending.
- References (M2b refined): facet/edge references are 0-based ELEMENT
  indices in region order (identity — no sigma search).  Skip slots
  referenced by loops are curve entries whose coordinates live in the
  curve records (U4); their written neighbours bracket them (100/104
  skip slots on 70b59f2a have both neighbours sharing 2 coordinates).
  The loop plane law is coplanarity against the record's stored 12-B
  normal (the corner quads are slanted planes — the axis-constant
  reading was too strict).

Outputs docs/evidence/data/big-form-points-files.csv (one row per
composite store) and a summary on stdout.  Deterministic: sorted
manifest order; no wall-clock value enters the CSV.

With ``--planes`` the script instead commits the multi-plane
decomposition (stage-3b review F3, 2026-11-11): every nonplanar loop
(battery class, stage-3b item 5) on the walk-exact big-form stores is
triangulated per its family reading and classified by normal-direction
clustering — the criterion is declared in ``classify_loop_planes`` —
into single-plane-uniform (d = 1), multi-plane (d = 2-3), 4+-plane
(d >= 4) or no-triangles (fewer than 3 measurable points), with the
marker family broken out per row.  Output:
docs/evidence/data/big-form-planes-loops.csv (one row per nonplanar
loop; integers only, byte-identical across runs).

Read-only over the corpus; run with the worktree venv:
  .venv/bin/python -I scripts/triage/decode_big_form_points.py
  [--include-sha16 HEX16,...] [--planes]
"""

import argparse
import csv
import mmap
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import facets, pool, store  # noqa: E402
from catpart.geometry import composite  # noqa: E402
from decode_nested_store import release_of  # noqa: E402

FIELDS = [
    "sha256", "split", "release", "size_bytes", "pool_size",
    "node_form", "list_node_bytes", "elem_decl", "edge_bound_decl",
    "table_bytes", "write_count", "count_bytes", "region_bytes",
    "walk_end_ok", "nice_ok", "pts_written", "skip_slots",
    "pool_in_list", "pool_coverage", "pool_absorbed",
    "max_ref", "elem_eq_maxref1", "records_parsed", "width2_records",
    "norm_records", "loops", "loops_coplanar", "loops_skipref",
    "loops_beyond", "loops_nonplanar", "max_plane_residual", "audit_error",
]

# table value -> f32 writes (0 = skip: the element carries no coordinates)
SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}
PLANE_TOL = 2e-3  # |(p - p0) . n| / |n| bound; f32 coordinate rounding ~1e-4


def layout(payload: bytes, elem_count: int):
    """Region layout after the zero block (P1t refined): table + P1g count.

    Returns (table_start, table_len, count_pos, region_start, write_count)
    or raises ValueError when the layout does not fit the payload.
    """
    tok = payload.find(composite.LIST_TOKEN)
    if tok < 0:
        raise ValueError("no list token")
    p = tok + 5
    _, p = composite.read_count(payload, p)
    _, p = composite.read_count(payload, p)
    while p + 4 <= len(payload) and payload[p : p + 4] == b"\x00\x00\x00\x00":
        p += 4
    table_len = (elem_count + 3) // 4
    count_pos = p + table_len
    if count_pos >= len(payload):
        raise ValueError("table runs past payload")
    write_count, region_start = composite.read_count(payload, count_pos)
    region_end = region_start + 4 * write_count
    if region_end > len(payload):
        raise ValueError("region overruns payload")
    return p, table_len, count_pos, region_start, write_count


def table_slots(payload: bytes, table_start: int, table_len: int, elem_count: int):
    """The 2-bit table: LSB-first slots, one per element."""
    slots = []
    for i in range(table_start, table_start + table_len):
        b = payload[i]
        slots += [(b >> 0) & 3, (b >> 2) & 3, (b >> 4) & 3, (b >> 6) & 3]
    return slots[:elem_count]


def decode_region(payload: bytes, elem_count: int):
    """Deterministic table-driven decode of the point region.

    Returns (elements, region_start, walk_end, nice_ok, info) where
    ``elements[i] = (value, point_or_None)`` in region order (point is
    None for skip slots) and ``walk_end`` is the byte the walk reached
    (the region's declared end when the law holds).
    """
    table_start, table_len, count_pos, region_start, write_count = layout(
        payload, elem_count
    )
    slots = table_slots(payload, table_start, table_len, elem_count)
    pos = region_start
    x = y = z = 0.0  # the initial LCP state is the origin (P1i subsumed)
    elements = []
    nice_ok = True
    for v in slots:
        shape = SHAPES[v]
        if shape == 0:
            elements.append((v, None))
            continue
        if pos + 4 * shape > len(payload):
            nice_ok = False  # the walk overruns the payload: stop cleanly
            elements.append((v, None))
            break
        if shape == 3:
            x, y, z = _f32(payload, pos), _f32(payload, pos + 4), _f32(payload, pos + 8)
            ok = all(_nice(c) for c in (x, y, z))
        elif shape == 2:
            y, z = _f32(payload, pos), _f32(payload, pos + 4)
            ok = all(_nice(c) for c in (y, z))
        else:
            z = _f32(payload, pos)
            ok = _nice(z)
        nice_ok &= ok
        pos += 4 * shape
        elements.append((v, (x, y, z)))
    info = {
        "table_start": table_start,
        "table_len": table_len,
        "count_pos": count_pos,
        "write_count": write_count,
        "count_bytes": region_start - count_pos,
        "region_start": region_start,
        "region_bytes": 4 * write_count,
    }
    return elements, region_start, pos, nice_ok, info


def _f32(data, pos):
    return struct.Struct("<f").unpack_from(data, pos)[0]


def _nice(v):
    """Finite coordinate check.

    The table-driven walk needs no pruning predicate (the table fixes
    the parse), so the stage-2c probe's 1e-6 floor is dropped here:
    real tessellation coordinates reach ~1e-15 around zero (the writer
    stores sin(pi)-scale noise verbatim; the pool carries exact -0.0),
    and junk detection falls to the walk-end / pool / plane checks.
    """
    return v == v and abs(v) < 1e9


def parse_strip_records(data, lo, hi, elem_count):
    """Every strip record with the width disambiguated (stage-3b rule).

    Candidate parses: width u8/u16be x count-byte k (0..16) summing to n,
    ending at or before the next header.  Rank: exact tiling, then
    no-repeated-refs-within-a-loop, then no out-of-range refs, then the
    narrower width (the tiling law first; the no-repeat rule resolves
    the u8-misread of u16be records whose next header is not adjacent).
    Returns a list of (offset, marker, normal, counts, refs, width).
    """
    hdrs = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
    out = []
    for i, o in enumerate(hdrs):
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else hi
        mk = data[o + 1]
        hlen = 4 if data[o + 3] == 0xFF else 5
        if o + hlen + 4 > nxt:
            continue
        n = int.from_bytes(data[o + hlen : o + hlen + 4], "little")
        if not (0 <= n <= 1_000_000):
            continue
        has_normal = mk in facets.NORMAL_MARKERS_ALL
        base = o + hlen + 4 + (12 if has_normal else 0)
        normal = None
        if has_normal:
            normal = struct.unpack("<fff", data[o + hlen + 4 : o + hlen + 16])
        best = None
        for width in (1, 2):
            for k in range(0, 17):
                if base + k > nxt:
                    break
                counts = [data[base + j] for j in range(k)]
                if sum(counts) != n:
                    continue
                end = base + k + width * n
                if end > nxt:
                    continue
                refs = [
                    int.from_bytes(
                        data[base + k + width * j : base + k + width * (j + 1)],
                        "big",
                    )
                    for j in range(n)
                ]
                repeats = False
                off = 0
                for c in counts:
                    loop = refs[off : off + c]
                    if c > 0 and len(set(loop)) < c:
                        repeats = True
                    off += c
                oob = any(r >= elem_count for r in refs)
                rank = (
                    0 if end == nxt else 1,
                    1 if repeats else 0,
                    1 if oob else 0,
                    width,
                    k,
                )
                if best is None or rank < best[0]:
                    best = (rank, tuple(counts), tuple(refs), width)
        if best is None:
            continue
        _rank, counts, refs, width = best
        out.append((o, mk, normal, counts, refs, width))
    return out, len(hdrs)


def normal_loops(records):
    """Yield (marker, normal, loop, record_off, loop_idx) for every
    non-empty sub-loop of the normal-carrying records, in record/count
    order — the exact loop stream the battery and the --planes
    classifier both consume (one source: the two cannot split loops
    differently)."""
    for o, mk, normal, counts, refs, _w in records:
        if normal is None:
            continue
        off = 0
        for j, c in enumerate(counts):
            loop = refs[off : off + c]
            off += c
            if loop:
                yield mk, normal, loop, o, j


def loop_plane_status(loop, normal, elements, skips, elem_count):
    """One loop's battery status against its stored normal.

    'skipref' = the committed union class — a skip slot (curve entry,
    U4: coordinates live in the curve records) or a ref at/after
    elem_count — not testable here; 'beyond' = F2 (2026-11-11): a ref
    in the UNWALKED window [len(elements), elem_count) on second-family
    stores whose walk broke early — the class the unguarded
    ``elements[ref]`` used to crash on (IndexError); 'coplanar' /
    'nonplanar' = the coplanarity test at PLANE_TOL (the residual walk
    stops at the first failing point, as committed).
    Returns (status, max_residual_up_to_the_stop).
    """
    if any(r in skips or r >= elem_count for r in loop):
        return "skipref", 0.0
    if any(r >= len(elements) for r in loop):
        return "beyond", 0.0
    nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    if nn == 0:
        return "nonplanar", 0.0
    pts = [elements[r][1] for r in loop]
    p0 = pts[0]
    max_res = 0.0
    for p in pts[1:]:
        d = (
            (p[0] - p0[0]) * normal[0]
            + (p[1] - p0[1]) * normal[1]
            + (p[2] - p0[2]) * normal[2]
        ) / nn
        res = abs(d)
        if res > max_res:
            max_res = res
        if res > PLANE_TOL:
            return "nonplanar", max_res
    return "coplanar", max_res


def plane_battery(records, elements, elem_count):
    """Coplanarity of every normal-carrying loop against its stored normal.

    Loops referencing skip slots (or refs at/after elem_count — the
    committed union class) are counted separately (curve entries:
    coordinates live in the curve records, U4 — not testable here), as
    are loops referencing the UNWALKED window [len(elements),
    elem_count) on second-family stores (stage-3b review F2,
    2026-11-11: the walk breaks early there, elements is shorter than
    elem_decl, and the unguarded ``elements[ref]`` crashed the battery —
    the 6 stores 88ad0be6, a7aef50e, ac9483aa, ae85fae7, bad44bdf,
    fd4201aa now get real battery rows instead of an IndexError).
    Returns (norm_records, loops, coplanar, skipref, beyond, nonplanar,
    max_residual).
    """
    skips = {i for i, (v, pt) in enumerate(elements) if pt is None}
    norm_records = sum(
        1 for _o, _mk, normal, _c, _r, _w in records if normal is not None
    )
    loops = coplanar = skipref = beyond = nonplanar = 0
    max_res = 0.0
    for _mk, normal, loop, _o, _j in normal_loops(records):
        loops += 1
        status, res = loop_plane_status(
            loop, normal, elements, skips, elem_count
        )
        if res > max_res:
            max_res = res
        if status == "coplanar":
            coplanar += 1
        elif status == "nonplanar":
            nonplanar += 1
        elif status == "beyond":
            beyond += 1
        else:
            skipref += 1
    return norm_records, loops, coplanar, skipref, beyond, nonplanar, max_res


COS_TOL = 0.999  # direction-cluster tolerance: |cos| >= 0.999 (~2.56 deg)


def _unit_normal(p0, p1, p2):
    """Unit normal of the triangle (p0, p1, p2); None when degenerate."""
    ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    n2 = nx * nx + ny * ny + nz * nz
    if n2 <= 0.0:
        return None
    s = n2**0.5
    return (nx / s, ny / s, nz / s)


def loop_triangles(loop, marker):
    """Point-index triangles of one sub-loop, per the shipped family
    readings (``facets.STRIP_MARKERS`` / ``facets.POLY_MARKERS``).

    Strips (0x41/0x42/0x49/0x4A): consecutive triples with the flip on
    odd t (GE-F3, 6.3.1) — for 0x49 this is the declared working
    reading, its primitive semantics stay open per GE-F9.  Polygons
    (0x4C per GE-F4; also the open 0x4B/0x4E): fan from the first
    corner.  Degenerate triangles (repeated coordinates / zero cross
    product) are dropped by ``classify_loop_planes``, as in the shipped
    soup decoder.
    """
    if marker in facets.STRIP_MARKERS:
        for i in range(len(loop) - 2):
            tri = (loop[i], loop[i + 1], loop[i + 2])
            yield tri[::-1] if i % 2 else tri
    else:
        for i in range(1, len(loop) - 1):
            yield loop[0], loop[i], loop[i + 1]


def classify_loop_planes(loop, marker, elements, normal, cos_tol=COS_TOL):
    """The multi-plane criterion (stage-3b review F3, 2026-11-11).

    Normal-direction clustering: the loop's triangles (``loop_triangles``)
    each contribute a unit triangle normal; two normals sit in the same
    direction class iff their unsigned cosine |n1 . n2| >= 0.999
    (~2.56 deg) — unsigned because a plane's orientation is defined up
    to sign — clustered greedily in triangle order.  d = the number of
    direction classes; class = single-plane-uniform (d == 1), multi-plane
    (2 <= d <= 3), 4-plus-plane (d >= 4), or no-triangles when no
    triangle survives degeneracy.  Deterministic: the cluster order is
    the fixed triangle order; integers only enter the output CSV.
    Returns (n_tri, d, plane_class, cos1000) where cos1000 rounds
    1000 x |dot(first_representative, stored_unit_normal)| to an int
    (0 when the stored normal is zero-length) — the auxiliary that
    separates a single-plane-uniform loop the stored normal agrees with
    (cos1000 >= 999: flat but mis-tested) from one it disagrees with.
    """
    normals = []
    for tri in loop_triangles(loop, marker):
        pts = [elements[r][1] for r in tri]
        n = _unit_normal(*pts)
        if n is not None:
            normals.append(n)
    if not normals:
        return 0, 0, "no-triangles", 0
    reps = []
    for n in normals:
        for rep in reps:
            if abs(rep[0] * n[0] + rep[1] * n[1] + rep[2] * n[2]) >= cos_tol:
                break
        else:
            reps.append(n)
    d = len(reps)
    nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    cos1000 = (
        round(1000 * abs(reps[0][0] * normal[0] + reps[0][1] * normal[1]
                         + reps[0][2] * normal[2]) / nn)
        if nn
        else 0
    )
    if d == 1:
        return len(normals), d, "single-plane-uniform", cos1000
    if d <= 3:
        return len(normals), d, "multi-plane", cos1000
    return len(normals), d, "4-plus-plane", cos1000


PLANES_FIELDS = [
    "sha256", "split", "release", "record_off", "loop_idx", "marker",
    "n_refs", "n_tri", "d", "plane_class", "cos1000",
]


def run_planes(rows_in, out_dir: Path):
    """--planes mode: the full-census multi-plane decomposition (F3).

    For every walk-exact big-form store (walk consumes exactly the
    declared write count — the battery's decoded scope) each battery-
    nonplanar loop is classified by ``classify_loop_planes``; one CSV
    row per nonplanar loop.  A per-store cross-check asserts the
    classified loop set equals the battery's nonplanar count (both
    share ``normal_loops`` / ``loop_plane_status``, so a divergence
    cannot pass silently).
    """
    out_rows = []
    stores = 0
    mism = 0
    for r in rows_in:
        path = ROOT / r["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                row, records, elements = audit_part(mm, r, with_internals=True)
            except Exception:  # noqa: BLE001 - audit errors have no battery
                continue
            finally:
                mm.close()
        if row.get("node_form") != "big" or row.get("walk_end_ok") is not True:
            continue
        stores += 1
        skips = {i for i, (v, pt) in enumerate(elements) if pt is None}
        elem_count = int(row["elem_decl"])
        classified = 0
        for mk, normal, loop, o, j in normal_loops(records):
            status, _res = loop_plane_status(
                loop, normal, elements, skips, elem_count
            )
            if status != "nonplanar":
                continue
            n_tri, d, plane_class, cos1000 = classify_loop_planes(
                loop, mk, elements, normal
            )
            classified += 1
            out_rows.append({
                "sha256": r["sha256"],
                "split": r["split"],
                "release": row["release"],
                "record_off": o,
                "loop_idx": j,
                "marker": f"0x{mk:02x}",
                "n_refs": len(loop),
                "n_tri": n_tri,
                "d": d,
                "plane_class": plane_class,
                "cos1000": cos1000,
            })
        if classified != int(row["loops_nonplanar"]):
            print(
                f"CROSS-CHECK FAILED: {r['sha256'][:16]} classified "
                f"{classified} nonplanar loops, battery counted "
                f"{row['loops_nonplanar']}",
                file=sys.stderr,
            )
            mism += 1
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "big-form-planes-loops.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PLANES_FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    summarize_planes(out_rows, stores, mism)
    return 0


def summarize_planes(rows, stores, mism):
    """The decomposition figures the note restates (F3/F4b)."""
    by_class = Counter(r["plane_class"] for r in rows)
    by_fam = Counter(r["marker"] for r in rows)
    multi = by_class["multi-plane"]
    total = len(rows)
    print(f"== planes: {total} nonplanar loops on {stores} walk-exact big "
          f"stores (cross-check failures: {mism})")
    print(f"   classes: single-plane-uniform {by_class['single-plane-uniform']}, "
          f"multi-plane (d=2-3) {multi} [d=2 {sum(1 for r in rows if r['d'] == 2)}, "
          f"d=3 {sum(1 for r in rows if r['d'] == 3)}], "
          f"4-plus-plane {by_class['4-plus-plane']}, "
          f"no-triangles {by_class['no-triangles']}")
    fams = ", ".join(f"{k} {v}" for k, v in sorted(by_fam.items()))
    print(f"   families: {fams}")
    spu = [r for r in rows if r["plane_class"] == "single-plane-uniform"]
    if spu:
        agree = sum(1 for r in spu if int(r["cos1000"]) >= 999)
        disagree = sum(1 for r in spu if int(r["cos1000"]) < 500)
        print(f"   single-plane-uniform vs its stored normal: cos1000 >= 999 "
              f"(flat, stored normal agrees) {agree}; cos1000 < 500 "
              f"(stored normal disagrees grossly) {disagree}; total {len(spu)}")
    if total:
        print(f"   multi-plane share of the nonplanar loops: "
              f"{multi}/{total} = {multi / total:.3f}")


def audit_part(mm, rel, with_internals=False):
    """One part: table-driven point-region audit. Returns the CSV row —
    or, with ``with_internals`` (the --planes classifier), the triple
    (row, records, elements) so the classifier consumes the exact
    records/elements the battery saw."""
    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    row["release"] = release_of(rel["detected_version"])
    row["size_bytes"] = mm.size()
    records: list = []
    elements: list = []

    def finish():
        return (row, records, elements) if with_internals else row

    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        try:
            span = store.locate_store(mm, blk, blocks, d8_outer)
        except Exception:  # noqa: BLE001 - recorded per part
            continue
        if span is None:
            continue
        lo, hi = span.body_lo, span.body_hi
        try:
            groups, kinds = pool.scan_pool_groups(mm, lo, hi)
        except Exception:  # noqa: BLE001 - recorded per part
            continue
        if not pool.has_composite_space(kinds):
            continue
        poolv = [v for g in groups for v in g.vertices]
        row["pool_size"] = len(poolv)
        hdrs = [m.start() for m in facets.STRIP_RE.finditer(mm, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        ln = composite.find_list_node(mm, lo, node_hi)
        if ln is None:
            return finish()
        payload, c1, c2 = ln
        row["list_node_bytes"] = len(payload)
        row["elem_decl"] = c1
        row["edge_bound_decl"] = c2
        row["node_form"] = "big" if len(payload) > 4096 else "small"
        try:
            elements, region_start, walk_end, nice_ok, info = decode_region(
                payload, c1
            )
        except ValueError as exc:
            row["audit_error"] = f"layout: {exc}"
            return finish()
        row["table_bytes"] = info["table_len"]
        row["write_count"] = info["write_count"]
        row["count_bytes"] = info["count_bytes"]
        row["region_bytes"] = info["region_bytes"]
        row["walk_end_ok"] = walk_end == info["region_start"] + info["region_bytes"]
        row["nice_ok"] = nice_ok
        written = [pt for _v, pt in elements if pt is not None]
        row["pts_written"] = len(written)
        row["skip_slots"] = sum(1 for _v, pt in elements if pt is None)
        ps = set(poolv)
        hits = len(ps & set(written))
        row["pool_in_list"] = hits
        row["pool_coverage"] = round(hits / len(poolv), 4) if poolv else ""
        row["pool_absorbed"] = hits == len(ps)
        records, n_hdrs = parse_strip_records(mm, lo, hi, c1)
        row["records_parsed"] = len(records)
        row["width2_records"] = sum(1 for r in records if r[5] == 2)
        all_refs = [r for _o, _mk, _n, _c, refs, _w in records for r in refs]
        row["max_ref"] = max(all_refs) if all_refs else ""
        row["elem_eq_maxref1"] = (
            (c1 == max(all_refs) + 1) if all_refs else ""
        )
        nr, loops, cop, skp, bey, non, max_res = plane_battery(
            records, elements, c1
        )
        row["norm_records"] = nr
        row["loops"] = loops
        row["loops_coplanar"] = cop
        row["loops_skipref"] = skp
        row["loops_beyond"] = bey
        row["loops_nonplanar"] = non
        row["max_plane_residual"] = round(max_res, 6) if max_res else 0.0
        return finish()
    return finish()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument(
        "--planes",
        action="store_true",
        help="write the multi-plane decomposition CSV (big-form-planes-"
        "loops.csv) over the full census instead of the per-store audit",
    )
    args = ap.parse_args()
    rows_in = [
        r
        for r in csv.DictReader(MANIFEST.open())
        if r["split"] in ("dev", "held-out") and r["kind"] == "part"
    ]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows_in = [r for r in rows_in if r["sha256"][:16] in want]
    rows_in.sort(key=lambda r: r["sha256"])
    out_dir = Path(args.out_dir)
    if args.planes:
        return run_planes(rows_in, out_dir)
    out_rows = []
    for r in rows_in:
        path = ROOT / r["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                row = audit_part(mm, r)
            except Exception as exc:  # noqa: BLE001 - recorded per part
                row = {k: "" for k in FIELDS}
                row["sha256"] = r["sha256"]
                row["split"] = r["split"]
                row["audit_error"] = f"{type(exc).__name__}: {exc}"
            finally:
                mm.close()
        out_rows.append(row)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "big-form-points-files.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")
    summarize(out_rows)
    return 0


def _rate(rows, key):
    have = [r for r in rows if str(r.get(key)) not in ("", "None")]
    return have, len(have)


def summarize(rows):
    """Per-claim rates over the audited stores."""
    have = [r for r in rows if r.get("node_form") in ("small", "big")]
    aerr = [r for r in rows if r["audit_error"]]
    print(f"== table-driven point-region audit: {len(have)} composite stores "
          f"of {len(rows)} parts (audit errors: {len(aerr)})")
    if not have:
        return
    for form in ("big", "small"):
        fr = [r for r in have if r["node_form"] == form]
        if not fr:
            continue
        print(f"-- {form}-form: {len(fr)} stores")
        end_ok = [r for r in fr if str(r["walk_end_ok"]) == "True"]
        nice = [r for r in fr if str(r["nice_ok"]) == "True"]
        both = [r for r in end_ok if str(r["nice_ok"]) == "True"]
        print(f"   walk consumes exactly write_count words: {len(end_ok)}/{len(fr)}"
              f" (nice words throughout: {len(nice)}, both: {len(both)})")
        absorbed = [r for r in fr if str(r["pool_absorbed"]) == "True"]
        print(f"   pool fully re-listed in the decoded points: "
              f"{len(absorbed)}/{len(fr)}")
        n2 = [r for r in fr if str(r["elem_eq_maxref1"]) == "True"]
        n2_have, n2_n = _rate(fr, "elem_eq_maxref1")
        print(f"   elem_decl == max_ref + 1: {len(n2)}/{n2_n} stores carrying refs")
        lp = [r for r in fr if str(r["loops"]) not in ("", "0")]
        cp = [r for r in lp if str(r["loops_nonplanar"]) == "0"]
        skp = [r for r in lp if str(r["loops_skipref"]) not in ("", "0")]
        clean = [r for r in lp if str(r["loops_skipref"]) in ("", "0")]
        clean_ok = [r for r in clean if str(r["loops_coplanar"]) == str(r["loops"])]
        tot_loops = sum(int(r["loops"]) for r in lp)
        tot_cop = sum(int(r["loops_coplanar"]) for r in lp)
        tot_skp = sum(int(r["loops_skipref"]) for r in lp)
        tot_bey = sum(int(r["loops_beyond"]) for r in lp)
        tot_non = sum(int(r["loops_nonplanar"]) for r in lp)
        print(f"   normal-carrying loops: {tot_loops} across {len(lp)} stores —"
              f" coplanar {tot_cop}, skip-ref (curve entries, U4) {tot_skp},"
              f" beyond the walked element space (F2) {tot_bey},"
              f" nonplanar {tot_non}")
        print(f"   stores with zero nonplanar loops: {len(cp)}/{len(lp)};"
              f" skip-ref-free stores fully coplanar: "
              f"{len(clean_ok)}/{len(clean) if clean else 0}")
    big = [r for r in have if r["node_form"] == "big"]
    dec = [r for r in big if str(r["walk_end_ok"]) == "True"
           and str(r["nice_ok"]) == "True" and str(r["pool_absorbed"]) == "True"]
    print(f"== headline: big-form stores whose region decodes under the table"
          f" law with the pool fully contained: {len(dec)}/{len(big)}")


if __name__ == "__main__":
    sys.exit(main())
