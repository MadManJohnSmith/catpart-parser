#!/usr/bin/env python3
"""Stage-12 Phase A (#34): byte-level census of the 310 non-composite
fail-closed stores at the stage-10 baseline.

Population: every fail-closed row of the accepted stage-10 A/B
(``stage10-identity-export-files.csv``, ``export_ok != 1``) whose
spans carry NO composite space — re-derived with OWN walkers (the
stage-11 method; the committed ``stage11-subnode-population.csv``
classification column is joined for reference only, never trusted).
At this baseline the exporter's failure families over that mass are
known from the stage-11 review tabulation (178 missing-locator + 94
"no 01 06 vertex pool decoded" + 38 "facet references beyond the
pool" = 310); this census re-derives that tabulation with the real
exporter (``build_export`` as the black-box anchor) and measures,
per family, WHAT the blocker IS at byte level and what a solution
would yield — the per-family ceiling table of the stage-1 precedent.

Method — the committed modules are infrastructure
(``store``/``pool``/``facets``/``composite``/``export._export_store``
+ ``build_export``), the orchestration and every byte census below is
this probe's own:

  - span walk: ``export._export_data``'s probe order replicated
    (CATStdCont blocks first; the xdoclink/seebody recovery probes
    only when nothing located AND no header raised); a located span
    is composite when ``pool.scan_pool_groups`` finds
    ``has_composite_space``.  Population = fail-closed parts with
    zero composite spans.
  - exporter anchor: ``build_export`` per population part; the
    failure family = the error class + detail head (missing-locator /
    no-pool / refs-beyond / other — the last named, never folded).
  - located-store census (no-pool, refs-beyond): body size, pool
    groups/kinds, the facet scan the clean path runs (candidates,
    records, max ref, skipped markers), ``05 08 01`` record census
    (occurrences, max contiguous 15-B run, records outside pool
    spans), NODE_MAGIC hits, and the raw-array signature of the body
    read as stride-12 f32le triples (the committed ``_raw_nice``
    predicate + x-ascending rate — stage-6 vocabulary, measured as a
    signature, not a decode).
  - unlocated census (missing-locator): container inventory; V5_CFV2
    hits outside offset 0 with the full N2 header signature
    (ff x 8 / zeros x 8) and sane dwords; CATIA_V5 CB0001 hits;
    ``locate_store`` PROBED ON EVERY BLOCK regardless of container
    name (the stage-3a vocabulary extension test — shipped + relaxed
    tail laws, container-independent by construction); every
    recovered span runs the real decode path (``_export_store`` —
    with the schema-neutral container label "seebody"; the true
    containing block is recorded in this probe's own columns) and
    yields its content class + L2-gate outcome as FACT; locator-free
    whole-file wrapper census (``10 24 04 ff ff 00 00 00`` + sub-kind)
    with per-occurrence region attribution; the F2 sub-question =
    composite-space wrappers (``01 02`` edge / ``ff ..`` opener) in
    bytes no located span covers, with the stage-1 C6 ``02 02``
    edge-table walk per edge wrapper.

Analysis only: src/ untouched, corpus read-only (symlink).  Run:
  python3 -I scripts/triage/stage12_noncomposite_census_probe.py
Out: docs/evidence/data/stage12-noncomposite-census.csv
     docs/evidence/data/stage12-unlocated-wrappers.csv
"""

import argparse
import csv
import dataclasses
import mmap
import struct
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
STAGE10_CSV = OUT_DIR / "stage10-identity-export-files.csv"
STAGE11_CSV = OUT_DIR / "stage11-subnode-population.csv"

sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, facets, pool, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402
from catpart.geometry.export import _export_store, build_export  # noqa: E402

FULL_WRAP = pool.FULL_WRAP
VREC = pool.VREC
NODE_MAGIC = composite.NODE_MAGIC

FIELDS = [
    "sha256", "split", "stage10_error_class", "family",
    "anchor_detail_head", "s11_classification",
    # located-store census (no-pool / refs-beyond / other)
    "container", "span_ordinal", "tail_law", "body_bytes",
    "pool_groups", "pool_vertices", "pool_distinct", "pool_sizes_head",
    "kinds", "strip_candidates", "strip_records", "max_ref",
    "markers", "vrec_occ", "vrec_run_max", "vrec_outside_pool",
    "node_magic_hits", "token_nodes", "token_node_c1s",
    "raw_triples", "raw_nice_rate", "raw_xasc_rate",
    # unlocated census (missing-locator)
    "containers", "v5_hits", "v5_fullsig", "cb0001_hits",
    "probe_blocks", "probe_recovered", "probe_malformed",
    "recovered_regions", "recovery_outcomes", "content_classes",
    "would_export", "would_pass",
    "wrappers_total", "wrappers_pool", "wrappers_edge", "wrappers_opener",
    "wrapper_regions", "f2", "f2_edge_tables",
    "wrappers_in_recovered_bodies", "wrapper_note",
]

WFIELDS = [
    "sha256", "file_offset", "region", "sub_kind", "occ_index",
    "in_recovered_body", "edge_count_field", "edge_records_walked",
    "edge_max_endpoint", "nearest_v5_behind", "nearest_cb0001_behind",
]

NO_SUBKIND = {"01 06": "pool", "01 02": "edge"}


def own_spans(mm):
    """``export._export_data``'s probe order, replicated and recorded.

    Returns ``(blocks, d8_outer, spans, first_error, located)`` where
    ``spans`` lists ``(container_tag, ordinal, span)`` in probe order.
    """
    size = mm.size()
    d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(mm)
    first_error = None
    located = False
    spans = []
    families = (
        ("stdcont", "CATStdCont"),
        ("xdoclink", "CATXDocLinkCont"),
        ("seebody", "CATSeeBodyCont"),
    )
    # export.py's rule: the stdcont family is probed first and the
    # recovery probes (xdoclink, then seebody) run only when NOTHING
    # located AND no header raised there; within the recovery phase
    # both families are probed in full (no break between them).
    for fidx, (tag, name) in enumerate(families):
        cands = [b for b, nm in blocks if nm == name]
        for ordinal, blk in enumerate(cands):
            try:
                span = store.locate_store(mm, blk, blocks, d8_outer, container=tag)
            except ExportError as exc:
                if first_error is None:
                    first_error = exc
                continue
            if span is None:
                continue
            located = True
            spans.append((tag, ordinal, span))
        if fidx == 0 and (located or first_error is not None):
            break
    return blocks, d8_outer, spans, first_error, located


def anchor_family(err_class, detail):
    """The exporter's failure family from the black-box anchor."""
    if err_class == "missing-geometry-store":
        return "missing-locator"
    if "no 01 06 vertex pool decoded" in detail:
        return "no-pool"
    if "facet references beyond the pool" in detail:
        return "refs-beyond"
    return "other"


def _census_hex(counter):
    return ";".join(f"{k}:{v}" for k, v in sorted(counter.items()))


def vrec_census(bd, pool_spans):
    """``05 08 01`` record census over a body slice."""
    occ = outside = 0
    positions = []
    q = 0
    while True:
        q = bd.find(VREC, q)
        if q < 0:
            break
        if q + 15 <= len(bd):
            occ += 1
            positions.append(q)
            if not any(a <= q < b for a, b in pool_spans):
                outside += 1
        q += 1
    run_max = 0
    run = 0
    prev = None
    for p in positions:
        run = run + 1 if prev is not None and p == prev + 15 else 1
        run_max = max(run_max, run)
        prev = p
    return occ, run_max, outside


def raw_signature(bd):
    """The body read as stride-12 f32le triples from the slice start:
    the committed ``_raw_nice`` coordinate rate + the x-ascending
    rate (stage-6 raw-array vocabulary, measured as a signature)."""
    n = len(bd) // 12
    if n < 2:
        return n, "", ""
    vals = struct.unpack(f"<{n * 3}f", bd[: n * 12])
    nice = sum(1 for v in vals if composite._raw_nice(v)) / (n * 3)
    xs = vals[0::3]
    asc = sum(1 for i in range(n - 1) if xs[i + 1] > xs[i]) / (n - 1)
    return n, f"{nice:.4f}", f"{asc:.4f}"


def token_node_census(bd):
    """Token-bearing list nodes over a body slice (the census and
    ``_scan_token_nodes`` convention: NODE_MAGIC to NODE_MAGIC,
    LIST_TOKEN within the first 64 bytes, 0 < c1 <= MAX)."""
    nodes = 0
    c1s = []
    pos = 0
    while True:
        pos = bd.find(NODE_MAGIC, pos)
        if pos < 0:
            break
        end = bd.find(NODE_MAGIC, pos + 4)
        if end < 0:
            end = len(bd)
        payload = bd[pos + 4 : end]
        tok = payload.find(composite.LIST_TOKEN)
        if 0 <= tok <= 64:
            p = tok + 5
            try:
                c1, p = composite.read_count(payload, p)
                _c2, p = composite.read_count(payload, p)
            except (IndexError, struct.error):
                pos += 1
                continue
            if 0 < c1 <= composite.MAX_ELEMENT_COUNT:
                nodes += 1
                c1s.append(c1)
        pos += 1
    return nodes, c1s


def census_located(mm, span):
    """The located-store census (the no-pool / refs-beyond families)."""
    bd = bytes(mm[span.body_lo : span.body_hi])
    row = {"body_bytes": len(bd)}
    groups, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
    row["pool_groups"] = len(groups)
    row["pool_vertices"] = sum(len(g.vertices) for g in groups)
    row["pool_distinct"] = len({v for g in groups for v in g.vertices})
    row["pool_sizes_head"] = ";".join(str(len(g.vertices)) for g in groups[:8])
    row["kinds"] = _census_hex(Counter(k.hex() for k in kinds))
    pool_spans = []
    for g in groups:
        o = g.offset - span.body_lo
        q = o + (15 if bd[o + 10] == 0xFF else 11)
        pool_spans.append((q, q + 15 * g.count_field))
    scan = facets.scan_facets(mm, span.body_lo, span.body_hi, clean_store=True)
    row["strip_candidates"] = scan.candidates
    row["strip_records"] = len(scan.records)
    refs = [r for rec in scan.records for r in rec.refs]
    row["max_ref"] = max(refs, default=-1)
    row["markers"] = _census_hex(Counter(scan.skipped_markers))
    occ, run_max, outside = vrec_census(bd, pool_spans)
    row["vrec_occ"] = occ
    row["vrec_run_max"] = run_max
    row["vrec_outside_pool"] = outside
    row["node_magic_hits"] = bd.count(NODE_MAGIC)
    nodes, c1s = token_node_census(bd)
    row["token_nodes"] = nodes
    row["token_node_c1s"] = ";".join(str(c) for c in c1s[:8])
    n, nice, asc = raw_signature(bd)
    row["raw_triples"] = n
    row["raw_nice_rate"] = nice
    row["raw_xasc_rate"] = asc
    return row


def regions_of(blocks, d8_outer, size):
    """``(blk, name, region_end)`` per valid block (B3's region law)."""
    out = []
    for blk, nm in blocks:
        nxt = next((b for b, _ in blocks if b > blk), None)
        ends = [size]
        if nxt is not None:
            ends.append(nxt)
        if d8_outer > blk:
            ends.append(d8_outer)
        out.append((blk, nm, min(ends)))
    return out


def region_of(regions, pos):
    for blk, nm, rend in regions:
        if blk <= pos < rend:
            return nm
    return "unlocated"


def find_all_mm(mm, needle, start=0):
    out = []
    i = mm.find(needle, start)
    while i >= 0:
        out.append(i)
        i = mm.find(needle, i + 1)
    return out


def walk_edge_table(mm, o, size):
    """The stage-1 C6 edge-table walk under an ``01 02`` wrapper:
    count byte at +10 (ff escapes to u32le at +11, the P1g
    convention), ``02 02 (u16be)(u16be)`` 6-byte records."""
    b10 = mm[o + 10] if o + 11 <= size else 0
    if b10 == 0xFF:
        if o + 15 > size:
            return -1, -1, -1
        cnt = int.from_bytes(mm[o + 11 : o + 15], "little")
        q = o + 15
    else:
        cnt = b10
        q = o + 11
    walked = 0
    max_ep = -1
    while walked < cnt and q + 6 <= size and mm[q : q + 2] == b"\x02\x02":
        a = int.from_bytes(mm[q + 2 : q + 4], "big")
        b = int.from_bytes(mm[q + 4 : q + 6], "big")
        max_ep = max(max_ep, a, b)
        walked += 1
        q += 6
    return cnt, walked, max_ep


def census_unlocated(mm, blocks, d8_outer, spans):
    """The unlocated census (the missing-locator family): container
    inventory, header/magic hits, per-block locate probes, recovered
    spans' content classes, and the whole-file wrapper census with
    region attribution.  Returns (row, wrapper_rows)."""
    size = mm.size()
    row = {}
    row["containers"] = _census_hex(Counter(nm for _b, nm in blocks))
    regions = regions_of(blocks, d8_outer, size)

    v5 = []
    for q in find_all_mm(mm, store.V5_CFV2, 1):  # offset 0 = the outer magic
        nh = bytes(mm[q : q + 32])
        full = len(nh) == 32 and nh[16:24] == b"\xff" * 8 and nh[24:32] == b"\x00" * 8
        d8n = int.from_bytes(nh[8:12], "big") if len(nh) == 32 else 0
        d12n = int.from_bytes(nh[12:16], "big") if len(nh) == 32 else 0
        sane = 0 < d8n and 0 < d12n and q + d8n + d12n <= size
        v5.append((q, full, sane))
    row["v5_hits"] = len(v5)
    row["v5_fullsig"] = sum(1 for _q, full, _s in v5 if full)
    row["cb0001_hits"] = len(find_all_mm(mm, store.CB0001))

    # the stage-3a vocabulary extension test: locate_store probed on
    # EVERY block, whatever its container name
    recovered = []
    probe_out = []
    malformed = 0
    for blk, nm in blocks:
        try:
            span = store.locate_store(mm, blk, blocks, d8_outer, container=nm)
        except ExportError as exc:
            malformed += 1
            probe_out.append(f"{nm}@{blk}:malformed:{exc.detail[:60]}")
            continue
        if span is None:
            probe_out.append(f"{nm}@{blk}:none")
            continue
        recovered.append((nm, span))
        probe_out.append(
            f"{nm}@{blk}:recovered:{span.tail_law}:{span.body_lo}-{span.body_hi}"
        )
    row["probe_blocks"] = len(blocks)
    row["probe_recovered"] = len(recovered)
    row["probe_malformed"] = malformed
    row["recovered_regions"] = ";".join(
        f"{nm}:{span.tail_law}:{span.body_lo}-{span.body_hi}"
        for nm, span in recovered
    )
    row["recovery_outcomes"] = ";".join(probe_out)

    # recovered spans through the REAL decode path (the L2 gate's own
    # scorer applied to the returned summary).  The schema's
    # store_recovery.container enum is stdcont/xdoclink/seebody only,
    # so the measurement run relabels the span "seebody" — the true
    # containing block is in recovered_regions/content_classes.
    classes = []
    would_export = would_pass = 0
    bodies = []
    for nm, span in recovered:
        bodies.append((span.body_lo, span.body_hi))
        mspan = dataclasses.replace(span, container="seebody")
        try:
            summary, _v, _t = _export_store(mm, mspan, 0)
        except ExportError as exc:
            classes.append(f"{nm}:{exc.error_class}:{exc.detail[:80]}")
            continue
        would_export += 1
        mesh = summary["mesh"]
        bbox = summary["bounding_box"]
        plausible = bbox is not None and all(
            bbox["min"][a] <= bbox["max"][a] for a in range(3)
        )
        if summary["vertex_count"] < 1 or summary["triangle_count"] < 1:
            check = "empty-mesh"
        elif not mesh["manifold"]:
            check = "not-manifold"
        elif not plausible:
            check = "nonfinite-bbox"
        elif summary["degenerate_triangle_count"] > 0:
            check = "degenerate-triangles"
        else:
            check = "pass"
        if check == "pass":
            would_pass += 1
        stage = (summary.get("composite") or {}).get("stage", "clean")
        classes.append(
            f"{nm}:export:{check}:v{summary['vertex_count']}"
            f"t{summary['triangle_count']}:{stage}"
        )
    row["content_classes"] = ";".join(classes)
    row["would_export"] = would_export
    row["would_pass"] = would_pass

    # locator-free whole-file wrapper census with region attribution
    wrapper_rows = []
    kinds = Counter()
    reg_census = Counter()
    edge_heads = []
    in_body = 0
    idx = 0
    v5_pos = [q for q, _f, _s in v5]
    cb1_pos = find_all_mm(mm, store.CB0001)
    for o in find_all_mm(mm, FULL_WRAP):
        idx += 1
        sub = bytes(mm[o + 8 : o + 10])
        kind = NO_SUBKIND.get(
            sub.hex(" "), "opener" if sub[:1] == b"\xff" else f"other:{sub.hex(' ')}"
        )
        kinds[kind] += 1
        reg = region_of(regions, o)
        reg_census[reg] += 1
        hit_body = any(a <= o < b for a, b in bodies)
        in_body += hit_body
        wrow = dict.fromkeys(WFIELDS, "")
        wrow["sha256"] = ""  # filled by the caller
        wrow["file_offset"] = o
        wrow["region"] = reg
        wrow["sub_kind"] = sub.hex(" ")
        wrow["occ_index"] = idx
        wrow["in_recovered_body"] = 1 if hit_body else 0
        v_behind = [p for p in v5_pos if p <= o]
        wrow["nearest_v5_behind"] = o - max(v_behind) if v_behind else -1
        c_behind = [p for p in cb1_pos if p <= o]
        wrow["nearest_cb0001_behind"] = o - max(c_behind) if c_behind else -1
        if kind == "edge":
            cnt, walked, max_ep = walk_edge_table(mm, o, size)
            wrow["edge_count_field"] = cnt
            wrow["edge_records_walked"] = walked
            wrow["edge_max_endpoint"] = max_ep
            edge_heads.append(f"@{o}:{walked}/{cnt}:max{max_ep}")
        wrapper_rows.append(wrow)
    row["wrappers_total"] = idx
    row["wrappers_pool"] = kinds.get("pool", 0)
    row["wrappers_edge"] = kinds.get("edge", 0)
    row["wrappers_opener"] = kinds.get("opener", 0)
    row["wrapper_regions"] = _census_hex(reg_census)
    row["wrappers_in_recovered_bodies"] = in_body
    row["f2_edge_tables"] = ";".join(edge_heads[:6])
    return row, wrapper_rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--sha16",
        action="append",
        default=[],
        help="restrict to these sha16 prefixes (repeatable; anchor runs)",
    )
    args = ap.parse_args(argv)
    stage10 = list(csv.DictReader(STAGE10_CSV.open()))
    fail_closed = [r for r in stage10 if r["export_ok"] != "1"]
    s11 = {r["sha256"]: r for r in csv.DictReader(STAGE11_CSV.open())}
    manifest = {r["sha256"]: r for r in csv.DictReader(MANIFEST.open())}
    if args.sha16:
        fail_closed = [
            r for r in fail_closed if r["sha256"].startswith(tuple(args.sha16))
        ]
    print(f"stage-10 rows: {len(stage10)}; fail-closed: {len(fail_closed)}")

    rows = []
    all_wrappers = []
    fam_count = Counter()
    mismatches = []
    for sr in sorted(fail_closed, key=lambda r: r["sha256"]):
        sha = sr["sha256"]
        rel = manifest[sha]
        path = ROOT / rel["local_path"]
        row = {k: "" for k in FIELDS}
        row["sha256"] = sha
        row["split"] = sr["split"]
        row["stage10_error_class"] = sr["error_class"]
        row["s11_classification"] = s11.get(sha, {}).get("classification", "")
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                blocks, _d8, spans, first_err, located = own_spans(mm)
                composite_spans = []
                malformed_spans = []
                for tag, ordinal, span in spans:
                    try:
                        _groups, kinds = pool.scan_pool_groups(
                            mm, span.body_lo, span.body_hi
                        )
                    except ExportError as exc:
                        malformed_spans.append((tag, ordinal, span, exc))
                        continue
                    if pool.has_composite_space(kinds):
                        composite_spans.append((tag, ordinal, span))
                if composite_spans:
                    mismatches.append(
                        f"{sha[:16]}: {len(composite_spans)} composite span(s) "
                        "— excluded from this stage's population (the stage-11 "
                        "composite fail-closed set)"
                    )
                    continue  # not in this stage's population
                # exporter anchor: the real seam, black box
                with tempfile.TemporaryDirectory(prefix="stage12-phasea-") as td:
                    out = Path(td) / f"{sha[:16]}.ply"
                    try:
                        build_export(path, out)
                    except ExportError as exc:
                        row["family"] = anchor_family(exc.error_class, exc.detail)
                        row["anchor_detail_head"] = exc.detail[:200]
                    else:
                        row["family"] = "exported?!"
                        mismatches.append(f"{sha[:16]}: EXPORTED (not fail-closed)")
                fam_count[row["family"]] += 1
                if row["family"] == "missing-locator":
                    if located or first_err is not None:
                        row["wrapper_note"] = (
                            f"anchor=missing-locator but own walk located={located} "
                            f"first_err={str(first_err)[:80]}"
                        )
                        mismatches.append(f"{sha[:16]}: anchor/own-walk locate mismatch")
                    urow, wrapper_rows = census_unlocated(mm, blocks, _d8, spans)
                    row.update(urow)
                    row["f2"] = 1 if (urow["wrappers_edge"] or urow["wrappers_opener"]) else 0
                    for wrow in wrapper_rows:
                        wrow["sha256"] = sha
                        all_wrappers.append(wrow)
                else:
                    if not spans:
                        row["wrapper_note"] = (
                            f"anchor={row['family']} but own walk located no span"
                        )
                        mismatches.append(
                            f"{sha[:16]}: anchor={row['family']}, no span in own walk"
                        )
                        continue
                    if malformed_spans:
                        row["wrapper_note"] = (
                            f"{len(malformed_spans)} span(s) malformed at the "
                            "pool scan (not composite, not censused)"
                        )
                    tag, ordinal, span = spans[0]
                    row["container"] = tag
                    row["span_ordinal"] = ordinal
                    row["tail_law"] = span.tail_law
                    row.update(census_located(mm, span))
            finally:
                mm.close()
        rows.append(row)

    out = OUT_DIR / "stage12-noncomposite-census.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    wout = OUT_DIR / "stage12-unlocated-wrappers.csv"
    with wout.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=WFIELDS)
        w.writeheader()
        w.writerows(all_wrappers)
    print(f"wrote {out} ({len(rows)} rows)")
    print(f"wrote {wout} ({len(all_wrappers)} wrapper rows)")

    print("\n== family taxonomy (exporter anchor) ==")
    for fam, n in fam_count.most_common():
        print(f"  {fam}: {n}")
    by_class = Counter(r["s11_classification"] for r in rows)
    print(f"s11 classification join: {by_class.most_common()}")
    if mismatches:
        print(f"\nMEMBERSHIP MISMATCHES ({len(mismatches)}):")
        for m in mismatches[:20]:
            print(f"  {m}")

    # family detail summaries
    loc = [r for r in rows if r["family"] == "missing-locator"]
    f2 = [r for r in loc if str(r["f2"]) == "1"]
    print("\n== missing-locator census ==")
    print(f"  parts: {len(loc)}; with composite-space wrappers (F2): {len(f2)}")
    rec_any = [r for r in loc if str(r["probe_recovered"]) not in ("", "0")]
    print(f"  parts with >= 1 span recovered by the per-block probe: {len(rec_any)}")
    wp = sum(int(r["would_pass"] or 0) for r in loc)
    we = sum(int(r["would_export"] or 0) for r in loc)
    print(f"  recovered spans that would EXPORT: {we}; would PASS the L2 gate: {wp}")
    reg_any = [r for r in loc if str(r["wrappers_total"]) not in ("", "0")]
    print(f"  parts with any wrapper at all: {len(reg_any)}")
    cc = Counter()
    for r in loc:
        for item in (r["content_classes"] or "").split(";"):
            if item:
                cc[item.split(":", 2)[1] + ":" + item.split(":", 2)[2].split(":")[0]] += 1
    print(f"  recovered-span content classes: {cc.most_common()}")

    np_ = [r for r in rows if r["family"] == "no-pool"]
    print("\n== no-pool census ==")
    print(f"  parts: {len(np_)}")
    print(f"  wrapper kinds census: {Counter(r['kinds'] for r in np_).most_common(8)}")
    print(f"  strip candidates == 0: {sum(1 for r in np_ if str(r['strip_candidates']) == '0')}")
    nm_hit = sum(1 for r in np_ if str(r["node_magic_hits"]) not in ("", "0"))
    tn_hit = sum(1 for r in np_ if str(r["token_nodes"]) not in ("", "0"))
    print(f"  parts with NODE_MAGIC hits in the body: {nm_hit}")
    print(f"  parts with TOKEN-BEARING list nodes in the body: {tn_hit}")
    vr = sum(1 for r in np_ if str(r["vrec_occ"]) not in ("", "0"))
    print(f"  parts with 05 08 01 records in the body: {vr}")
    strong_raw = sum(
        1
        for r in np_
        if r["raw_nice_rate"] not in ("",) and float(r["raw_nice_rate"]) >= 0.98
        and float(r["raw_xasc_rate"]) >= 0.98
    )
    print(f"  parts with the stage-6 strong raw signature (nice>=0.98 AND xasc>=0.98): {strong_raw}")

    rb = [r for r in rows if r["family"] == "refs-beyond"]
    print("\n== refs-beyond census ==")
    print(f"  parts: {len(rb)}")
    print(f"  wrapper kinds census: {Counter(r['kinds'] for r in rb).most_common(8)}")
    print(
        f"  pool groups: {Counter(str(r['pool_groups']) for r in rb).most_common()}"
    )
    over = sum(
        1 for r in rb if int(r["max_ref"]) >= int(r["pool_vertices"] or 0)
    )
    print(f"  parts with max ref >= own pool size (the anchor family, re-measured): {over}")
    multi = sum(1 for r in rb if str(r["pool_groups"]) not in ("", "0", "1"))
    print(f"  parts with > 1 pool group: {multi}")

    oth = [r for r in rows if r["family"] == "other"]
    if oth:
        print("\n== other (named, never folded) ==")
        for r in oth[:10]:
            print(f"  {r['sha256'][:16]} {r['anchor_detail_head'][:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
