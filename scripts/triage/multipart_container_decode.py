#!/usr/bin/env python3
"""Decode/verify the U3-variant multi-part container reading (stage 7, #34).

Population: the 93 walk-mismatch composite stores the stage-6 raw-array law
leaves fail-closed (stage6-raw-trigger-probe.csv verdicts start-unpinned /
weak-fit / pool-unabsorbed).  Standing hypothesis (handoff + the 4a note's
named open): the list-node payload is a MULTI-PART container -- the P1t
layout repeating after the header -- complementary to the stage-5 per-rep
law (which handles multiple pool groups + list NODES, not multiple parts
inside one node's payload).

The reading this script pins, from observed bytes only (docs/evidence/
2026-11-12-multipart-container.md carries the field-by-field law):

  payload = [node header][token ff ff 02 00 01][count1 P1g][count2 P1g]
            [4-byte post-count field]
            [PART 1 region: count1 x f32 (x,y,z) triples, stride 12]
            [sub-sections: edge sub-nodes, vertex sub-nodes, ...]
            [trailer: f32 tolerance + 00 04 02 0a + P1g count]

- PART 1 is the RAW-ARRAY packing (the stage-4a law's region) with the
  FF trail-escape replaced by the sub-sections -- exactly the stores the
  raw law's start rule rejects (payload[start + 12*count1] != 0xFF).
- Edge sub-node: 04 04 ff ff + 4B header + u16be group count + that many
  02 <n> <n u8 refs> polyline groups (refs are element indices < count1;
  the stage-2a POLYLINE-table law inside the payload).
- Vertex sub-node: 04 ff ff + 4B post-count field + kind byte + count byte
  + count x (05 08 01 + 12B f32) -- per-vertex records re-listing points.
- Trailer: f32 tolerance (store-variable: 0.2, 0.05, 0.01, ...) +
  00 04 02 0a + a P1g count -- observed on walk-OK stores too (the U2
  trailing structure's tail); not a U3 discriminator by itself.

The region's coordinates are validated with the exporter's finite/plausible
predicate (v == v and |v| < 1e9) -- the raw scan's 1e-6 floor rejects real
near-zero coordinates on these stores (measured; the raw law keeps its own
predicate for ITS fit rates, that is not re-litigated here).

Every byte the parser cannot tie to a section is reported as unexplained
and named per store -- nothing is guessed.  Verdicts, per store:

- region-fit    : 12*count1 fits after the post-count field AND decodes
                  all-nice (the container's PART 1 reading holds).
- region-overflow: 12*count1 exceeds the payload (the big-store packing
                  family: the region cannot be count1 flat triples).
- unexplained bytes / section parse failures are named per store.

Read-only over the corpus (symlink).  Analysis only: src/ untouched.
Run:  python3 -I scripts/triage/multipart_container_decode.py
Out:  docs/evidence/data/multipart-container-files.csv
"""

import csv
import mmap
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
PROBE_CSV = OUT_DIR / "stage6-raw-trigger-probe.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, pool, store  # noqa: E402
from classify_residue_family import locate_payload  # noqa: E402

FIELDS = [
    "sha256", "split", "form", "verdict_stage6", "size_bytes", "payload_bytes",
    "elem_decl", "edge_bound", "tail_field", "region_ok", "region_pair_ok",
    "region_triples",
    "region_bytes", "region_x_asc", "region_pool_hits", "pool_distinct",
    "pool_groups", "edge_subnodes", "edge_groups", "edge_refs_ok",
    "vertex_subnodes", "vertex_records", "vertex_in_region",
    "trailer_ok", "trailer_tol", "explained_bytes", "unexplained_bytes",
    "unexplained_spans", "verdict", "note",
]


def nice(v: float) -> bool:
    """The exporter's finite/plausible coordinate predicate (composite._nice).

    The raw scan's 1e-6 floor is NOT applied here: the U3-variant regions
    carry genuine near-zero coordinates (e.g. 7d27c73d z = -1.19e-14,
    dd610ca5 x = 9.4e-15) that the floor rejects; this script maps the
    container STRUCTURE, it does not re-measure the raw law's fit rates."""
    return v == v and abs(v) < 1e9


def read_count(d, p):
    """P1g count: one byte, ff escapes to u32le."""
    if d[p] == 0xFF:
        return int.from_bytes(d[p + 1 : p + 5], "little"), p + 5
    return d[p], p + 1


def parse_edge_subnode(d, p, elem_decl):
    """Edge sub-node at p: 04 04 ff ff + 4B + u16be count + groups.

    Returns (end, n_groups, refs_ok, groups) or None if it does not parse."""
    if d[p : p + 4] != b"\x04\x04\xff\xff":
        return None
    q = p + 4 + 4  # skip the 4B sub-header (semantics open)
    if q + 2 > len(d):
        return None
    n_groups = int.from_bytes(d[q : q + 2], "big")
    q += 2
    groups = 0
    refs_ok = True
    for _ in range(n_groups):
        if q + 2 > len(d) or d[q] != 0x02:
            return None
        n = d[q + 1]
        if n == 0 or q + 2 + n > len(d):
            return None
        refs = d[q + 2 : q + 2 + n]
        if any(r >= elem_decl for r in refs):
            refs_ok = False
        groups += 1
        q += 2 + n
    return q, groups, refs_ok


def parse_vertex_subnode(d, p, region_points):
    """Vertex sub-node at p: 04 ff ff + 4B + kind byte + count byte +
    count x (05 08 01 + 12B f32).  Returns (end, n_rec, in_region) or None."""
    if d[p : p + 3] != b"\x04\xff\xff":
        return None
    q = p + 3 + 4  # 4B post-count field
    if q + 2 > len(d):
        return None
    n = d[q + 1]
    q += 2
    recs = 0
    in_region = 0
    for _ in range(n):
        if q + 15 > len(d) or d[q : q + 3] != b"\x05\x08\x01":
            return None
        pt = struct.unpack_from("<fff", d, q + 3)
        if all(nice(c) for c in pt) and pt in region_points:
            in_region += 1
        recs += 1
        q += 15
    return q, recs, in_region


def parse_trailer(d, p):
    """Trailer at p: f32 + 00 04 02 0a + P1g count.  Returns (end, tol) or None."""
    if p + 9 > len(d) or d[p + 4 : p + 8] != b"\x00\x04\x02\x0a":
        return None
    tol = struct.unpack_from("<f", d, p)[0]
    _c, end = read_count(d, p + 8)
    return end, tol


def audit_row(mm, rel, stage6_verdict):
    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    row["size_bytes"] = mm.size()
    row["verdict_stage6"] = stage6_verdict
    got = body_of(mm)
    if got is None:
        row["verdict"] = "no-body"
        return row
    lo, hi, groups = got
    pv = [v for g in groups for v in g.vertices]
    ps = set(pv)
    row["pool_distinct"] = len(ps)
    row["pool_groups"] = len(groups)
    ln = locate_payload(mm)
    if ln is None:
        row["verdict"] = "no-list-node"
        return row
    payload, c1, c2 = ln
    d = bytes(payload)
    row["form"] = "big" if len(d) > 4096 else "small"
    row["payload_bytes"] = len(d)
    row["elem_decl"] = c1
    row["edge_bound"] = c2
    tok = d.find(composite.LIST_TOKEN)
    p = tok + 5
    v1, p = read_count(d, p)
    v2, p = read_count(d, p)
    row["tail_field"] = d[p : p + 4].hex(" ")
    counts_end = p
    region_start = p + 4
    notes = []

    # PART 1 readings: (a) count1 x stride-12 triples (the raw-array
    # packing), (b) count1 x stride-8 f32 PAIRS (the stage-3b "float-pair"
    # reading: 2D points; the 12B scan of a pair array stays nice for
    # 2/3 x count1 triples -- measured on the corpus).
    region_end = region_start + 12 * c1
    region_points = set()
    pair_bytes = region_start + 8 * c1
    pair_ok = pair_bytes <= len(d)
    if pair_ok:
        for _ in range(c1):
            x, y = struct.unpack_from("<ff", d, region_start + 8 * _)
            if not (nice(x) and nice(y)):
                pair_ok = False
                break
    row["region_pair_ok"] = pair_ok
    if region_end > len(d):
        row["region_ok"] = False
        row["verdict"] = "region-overflow"
        row["region_bytes"] = 12 * c1
        notes.append(
            f"12*{c1}={12 * c1}B region overflows the {len(d)}B payload "
            f"(fits {max(0, (len(d) - region_start) // 12)} triples); the "
            f"8B-pair reading ({8 * c1}B) "
            + ("fits and is all-nice" if pair_ok else "does not fit or is not all-nice")
        )
    else:
        xs = []
        okall = True
        pos = region_start
        for _ in range(c1):
            x, y, z = struct.unpack_from("<fff", d, pos)
            if not (nice(x) and nice(y) and nice(z)):
                okall = False
                break
            xs.append(x)
            region_points.add((x, y, z))
            pos += 12
        row["region_ok"] = okall
        row["region_triples"] = c1 if okall else (pos - region_start) // 12
        row["region_bytes"] = pos - region_start if okall else pos - region_start
        asc = (
            round(
                sum(1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6) / (c1 - 1), 4
            )
            if len(xs) > 1
            else ""
        )
        row["region_x_asc"] = asc
        row["region_pool_hits"] = len(ps & region_points)
        row["verdict"] = "region-fit" if okall else "region-junk"
        if not okall:
            notes.append(
                f"region breaks at triple {pos - region_start}//12 with a "
                "non-finite/implausible coordinate"
            )

    # sub-sections over the remainder
    explained = region_start + (12 * c1 if row["region_ok"] else 0)
    cur = region_start + (12 * c1 if row["region_ok"] else 0)
    edge_nodes = edge_groups = vertex_nodes = vertex_recs = 0
    edge_refs_ok = vertex_in_region = 0
    trailer_ok = False
    unexpl = []
    span_start = cur
    tol = ""

    def close_span(to):
        nonlocal span_start
        if to > span_start:
            unexpl.append((span_start, to))
        span_start = to

    while cur < len(d):
        e = parse_edge_subnode(d, cur, c1)
        if e is not None:
            close_span(cur)
            end, ng, rok = e
            edge_nodes += 1
            edge_groups += ng
            edge_refs_ok += rok
            cur = end
            span_start = cur
            continue
        v = parse_vertex_subnode(d, cur, region_points)
        if v is not None:
            close_span(cur)
            end, nr, inr = v
            vertex_nodes += 1
            vertex_recs += nr
            vertex_in_region += inr
            cur = end
            span_start = cur
            continue
        t = parse_trailer(d, cur)
        if t is not None:
            end, tol_v = t
            if end >= len(d):
                # the trailer must end at (or within a few bytes of) the end
                close_span(cur)
                trailer_ok = True
                tol = round(tol_v, 6)
                cur = end
                span_start = cur
                if end < len(d):
                    unexpl.append((end, len(d)))
                    cur = len(d)
                break
        cur += 1
    close_span(min(cur, len(d)))

    row["edge_subnodes"] = edge_nodes
    row["edge_groups"] = edge_groups
    row["edge_refs_ok"] = edge_refs_ok == edge_nodes if edge_nodes else ""
    row["vertex_subnodes"] = vertex_nodes
    row["vertex_records"] = vertex_recs
    row["vertex_in_region"] = vertex_in_region
    row["trailer_ok"] = trailer_ok
    row["trailer_tol"] = tol
    unexpl_total = sum(e - s for s, e in unexpl)
    row["explained_bytes"] = len(d) - unexpl_total
    row["unexplained_bytes"] = unexpl_total
    row["unexplained_spans"] = ";".join(f"{s}-{e}" for s, e in unexpl[:8])

    if row["verdict"] == "region-fit":
        if row["unexplained_bytes"] == 0:
            row["verdict"] = "container-tiled"
        else:
            row["verdict"] = "container-partial"
            notes.append(
                f"{row['unexplained_bytes']}B unexplained "
                f"({row['unexplained_spans']})"
            )
    row["note"] = " | ".join(notes)
    return row


def body_of(mm):
    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        span = store.locate_store(mm, blk, blocks, d8_outer)
        if span is None:
            continue
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(mm, lo, hi)
        if pool.has_composite_space(kinds):
            return lo, hi, groups
    return None


def main():
    probe = {
        r["sha256"]: r
        for r in csv.DictReader(PROBE_CSV.open())
    }
    targets = [
        s
        for s, r in probe.items()
        if r["verdict"] in ("start-unpinned", "weak-fit", "pool-unabsorbed")
    ]
    rows = []
    manifest = {r["sha256"]: r for r in csv.DictReader(MANIFEST.open())}
    for sha in sorted(targets):
        rel = manifest[sha]
        path = ROOT / rel["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                rows.append(audit_row(mm, rel, probe[sha]["verdict"]))
            finally:
                mm.close()
    out = OUT_DIR / "multipart-container-files.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} stores)")
    print("verdicts:", Counter(r["verdict"] for r in rows).most_common())
    print("tail fields:", Counter(r["tail_field"] for r in rows).most_common())
    print(
        "edge subnodes present:",
        sum(1 for r in rows if r["edge_subnodes"]),
        "| vertex subnodes present:",
        sum(1 for r in rows if r["vertex_subnodes"]),
    )
    tiled = [r for r in rows if r["verdict"] == "container-tiled"]
    print("container-tiled:", len(tiled))
    return 0


if __name__ == "__main__":
    sys.exit(main())
