#!/usr/bin/env python3
"""Root-cause classification of every L2 part failure (G6 stage 1, #34).

Replays the shipped export seam over the L2 population (manifest
``kind=part``, splits dev + held-out — the same population the fitness
runner scores) and audits each failure at byte level, without changing
any decode semantics: ``catpart.geometry`` is imported read-only and
every measurement below is an analysis-only probe around the shipped
classification.  No fitness history is appended and nothing is
published.

Cross-checks (the replay must agree with the baseline report before any
subclass is trusted):

  fitness/reports/20261110T172440Z-3ea53d.json (accepted L2 baseline,
  76/1,381 dev = 5.50%): 963 undecoded-variant + 313 missing-geometry-
  store + 29 malformed-store-header dev failures, 61 held-out
  undecoded-variant.

Failure decomposition (root classes, in the shipped gate's own order):

  composite-space      an ``01 02`` edge group and/or a trailer opener
                       (``10 24 04 ff ff 00 00 00 ff ..`` wrapper) is
                       present (G3 F8, open question 1).  Audited: which
                       trigger, edge-table record census, and whether the
                       facet refs would exceed the pool if the gate were
                       bypassed (analysis-only; F8 measured 793/889).
  poolless-store       no ``01 06`` pool group decodes from the body
                       (G2 P7/P8 families, the C6 float64 reclass).
  refs-beyond-pool     non-composite store whose facet refs exceed the
                       pool (G3 open question 2).
  facet-content-variant header candidates exist but no pinned family
                       produced a triangle (G3 open questions 3-5).
  malformed-store-header a ``V5_CFV2`` header fails the shipped tail
                       validation.  Audited byte-level: the dword8-
                       overshoot family (G1 C3) and the padded-tail
                       family (G1's padded-tail variant) vs anything
                       else, plus the content class the body would show
                       under the relaxed locate law (analysis only).
  missing-store        no store located.  G1's N10 taxonomy
                       (no_stdcont / none_in_region / next_block_store /
                       embedded_doc) plus a live recovery probe: the
                       locator is CATStdCont-only, so CATXDocLinkCont and
                       CATSeeBodyCont regions are probed with the same
                       locate law and their stores classified
                       clean/composite by the pool-kind scan.

Outputs (docs/evidence/data/):
  l2-grind-classification.csv   one row per L2 part (dev + held-out)
and a summary (per-class rates + the ceiling arithmetic toward the
80% bar) on stdout.  Deterministic: sorted-manifest order, no wall-clock
value enters the CSV.

Read-only; run with the worktree venv (the replay imports ``catpart``):
  .venv/bin/python -I scripts/triage/classify_l2_grind.py
  [--include-sha16 HEX16,...]  restrict to these files (sha16 prefixes)
  [--deep]                     print a byte-level store-signature
                               survey for the selected parts (use with
                               --include-sha16; the deep sample of the
                               evidence note)
  [--report PATH]              baseline report to replay against
"""
import argparse
import csv
import mmap
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
DEFAULT_REPORT = ROOT / "fitness" / "reports" / "20261110T172440Z-3ea53d.json"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import export as export_mod  # noqa: E402
from catpart.geometry import facets, pool, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402
from decode_nested_store import analyze_region, release_of  # noqa: E402

V5_CFV2 = b"V5_CFV2\x00"
CB0001 = b"CATIA_V5 CB0001\x00"
CB_END = b"CB__END\x00"
FULL_WRAP = pool.FULL_WRAP
EDGE_SUBKIND = pool.EDGE_SUBKIND
EDGE_REC = b"\x02\x02"
SURFACICREPS_U16 = "SurfacicReps".encode("utf-16-le")

FIELDS = [
    "sha256", "split", "release", "size_bytes",
    "fitness_class", "replay_class", "replay_match",
    "root_class", "root_detail", "composite_trigger", "pool_size",
    "n_stdcont", "g1_region_class", "n_stores_located",
    "wrapper_groups", "wrapper_kinds", "pool_groups", "pool_vertices",
    "edge_groups_0102", "edge_table_records", "max_edge_endpoint",
    "ff_openers", "ff_opener_lengths",
    "facet_candidates", "facet_records", "facet_unresolved",
    "marker_census", "max_facet_ref", "refs_beyond_analysis",
    "missing_family", "seebody_store", "xdoclink_store",
    "recovery_probe", "recovery_store_class", "recovery_pool_vertices",
    "recovery_malform_family", "recovery_malform_detail",
    "recovery_postfix_class",
    "malform_family", "malform_detail", "malform_postfix_class",
    "v5cfv2_hits_file", "cb0001_hits_file",
    "region_size", "region_v5cfv2", "region_cb0001", "region_wrappers",
    "region_surfacicreps_u16",
    "containers", "audit_error",
]


def replay_export(mm):
    """Run the shipped decode seam read-only; return (class, detail)."""
    try:
        export_mod._export_data(mm)
        return "pass", ""
    except ExportError as exc:
        return exc.error_class, exc.detail
    except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
        return "replay-crash", f"{type(exc).__name__}: {exc}"


def body_audit(mm, span, clean_store):
    """Pool + facet census of one located store body (read-only).

    Returns the shared dict of audit fields; ``refs_beyond_analysis`` is
    an analysis-only measurement (the shipped gate raises before it on
    composite stores).
    """
    groups, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
    flat = [v for g in groups for v in g.vertices]
    n_edge = sum(1 for k in kinds if k == EDGE_SUBKIND)
    n_ff = sum(1 for k in kinds if k[:1] == b"\xff")
    ff_lens = []
    edge_recs = 0
    max_edge_end = -1
    for o in store.find_all(mm, FULL_WRAP, span.body_lo, span.body_hi):
        if mm[o + 8 : o + 9] == b"\xff":
            ff_lens.append(int.from_bytes(mm[o + 9 : o + 13], "little"))
        if bytes(mm[o + 8 : o + 10]) != EDGE_SUBKIND:
            continue
        # G3 F8 census: a count byte at +10 (ff escapes to a u32le, the
        # pool groups' P1g convention), then 6-byte `02 02 (u16be)(u16be)`
        # records while the prefix holds.  Edge groups whose records
        # carry another `02 0X` form walk 0 here — recorded as the
        # census's 0-record groups, not absorbed.
        if mm[o + 10] == 0xFF:
            q = o + 15
        else:
            q = o + 11
        while q + 6 <= span.body_hi and bytes(mm[q : q + 2]) == EDGE_REC:
            a = int.from_bytes(mm[q + 2 : q + 4], "big")
            b = int.from_bytes(mm[q + 4 : q + 6], "big")
            edge_recs += 1
            max_edge_end = max(max_edge_end, a, b)
            q += 6
    scan = facets.scan_facets(mm, span.body_lo, span.body_hi,
                              clean_store=clean_store)
    markers = Counter(rec.marker for rec in scan.records)
    max_ref = max((max(rec.refs, default=-1) for rec in scan.records),
                  default=-1)
    return {
        "wrapper_groups": len(kinds),
        "wrapper_kinds": ";".join(k.hex() for k in kinds),
        "pool_groups": len(groups),
        "pool_vertices": len(flat),
        "edge_groups_0102": n_edge,
        "edge_table_records": edge_recs,
        "max_edge_endpoint": max_edge_end,
        "ff_openers": n_ff,
        "ff_opener_lengths": ";".join(str(v) for v in ff_lens),
        "facet_candidates": scan.candidates,
        "facet_records": len(scan.records),
        "facet_unresolved": scan.unresolved_candidates,
        "marker_census": ";".join(f"0x{m:02x}={n}"
                                  for m, n in sorted(markers.items())),
        "max_facet_ref": max_ref,
        "refs_beyond_analysis": bool(max_ref >= len(flat)),
    }, flat


def classify_store_content(mm, span):
    """Content class of a probed store body under the shipped gates.

    clean = no composite marker, pool present, every facet ref inside
    the pool (exportable today); composite / poolless / refs-beyond name
    the gate that would fire instead.  Analysis-only: runs the same
    scan calls the exporter would, without changing them.
    """
    try:
        _, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
    except ExportError:
        return "pool-broken"
    if pool.has_composite_space(kinds):
        return "composite"
    if not any(k == pool.POOL_SUBKIND for k in kinds):
        return "poolless"
    flat = [v for g in pool.scan_pool_groups(mm, span.body_lo,
                                             span.body_hi)[0]
            for v in g.vertices]
    scan = facets.scan_facets(mm, span.body_lo, span.body_hi,
                              clean_store=True)
    beyond = max((max(rec.refs, default=-1) for rec in scan.records),
                 default=-1)
    if beyond >= len(flat):
        return "refs-beyond"
    return "clean"


def recovery_pool_size(mm, span):
    try:
        groups, _ = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
        return sum(len(g.vertices) for g in groups)
    except ExportError:
        return 0


def probe_recovery(mm, blk, blocks, d8_outer, tag):
    """Locate a store on a non-CATStdCont container (analysis probe)."""
    try:
        span = store.locate_store(mm, blk, blocks, d8_outer)
    except ExportError:
        return f"{tag}-malformed", "", ""
    if span is None:
        return None, "", ""
    return (f"{tag}-located", classify_store_content(mm, span),
            recovery_pool_size(mm, span))


def region_bounds(mm, blk, blocks, d8_outer):
    """Region end of blk: next valid block / outer dword8 / EOF."""
    nxt = next((b for b, _ in blocks if b > blk), None)
    ends = [mm.size()]
    if nxt is not None:
        ends.append(nxt)
    if d8_outer > blk:
        ends.append(d8_outer)
    return min(ends)


def _header_fields(mm, j, rend):
    """(d8n, d12n, cb) for the V5_CFV2 header at j, shipped-locator rules."""
    size = mm.size()
    nh = bytes(mm[j : j + 32])
    d8n = int.from_bytes(nh[8:12], "big")
    d12n = int.from_bytes(nh[12:16], "big")
    if not (0 < d8n and 0 < d12n and j + d8n + d12n <= size):
        return d8n, d12n, -1
    if bytes(mm[j + d8n : j + d8n + 16]) == CB0001:
        return d8n, d12n, j + d8n
    cand = mm.find(CB0001, j, min(rend, j + d8n + d12n + 512))
    if cand >= 0 and 1 <= (j + d8n - cand) <= 64:
        return d8n, d12n, cand
    return d8n, d12n, -1


def malform_audit(mm, blk, blocks, d8_outer):
    """Why the shipped tail validation rejected this region's header."""
    rend = region_bounds(mm, blk, blocks, d8_outer)
    j = mm.find(V5_CFV2, blk, rend)
    if j < 0:
        return "no-header", "locator raised but no V5_CFV2 in region"
    nh = bytes(mm[j : j + 32])
    d8n, d12n, cb = _header_fields(mm, j, rend)
    if cb < 0:
        return "no-catalog-magic", (
            f"header j={j} d8n={d8n} d12n={d12n}; no CB0001 at origin+"
            f"d8n or within the 64 B overshoot window")
    ff8 = nh[16:24] == b"\xff" * 8
    z8 = nh[24:32] == b"\x00" * 8
    if not (ff8 and z8):
        return "header-marker", f"j={j} ff8={ff8} zeros8={z8}"
    k = j + d8n - cb
    ship_tail = bytes(mm[cb : j + d8n + d12n])
    true_tail = bytes(mm[cb : cb + d12n])
    if k > 0 and true_tail[-8:] == CB_END:
        return "dword8-overshoot", (
            f"header j={j} d8n={d8n} d12n={d12n} cb={cb} overshoot_k={k}; "
            f"the shipped tail [{cb},{j + d8n + d12n}) runs {k} B past the "
            f"catalog's CB__END at {cb + d12n - 8} (G1 C3 variant: "
            "dword8 overshoots the catalog magic, and the shipped tail "
            "end inherits the same overshoot)")
    pos = ship_tail.find(CB_END)
    if pos >= 0:
        after = ship_tail[pos + 8 :]
        pad = ("all-zero" if after and not after.strip(b"\x00")
               else after[:8].hex())
        return "padded-tail", (
            f"header j={j} d12n={d12n} cb={cb}; CB__END at {cb + pos}, "
            f"{len(after)} B follow it inside dword12 ({pad} padding); "
            "G1 padded-tail variant (trailer inside the tail)")
    return "other", (
        f"header j={j} d12n={d12n} cb={cb} k={k}; "
        f"last 16 B of shipped tail: {ship_tail[-16:].hex()}")


def malform_postfix_content(mm, blk, blocks, d8_outer):
    """Content class under the relaxed locate law (analysis only).

    Relaxes exactly the two documented families: the overshoot tail is
    read from the catalog magic with length dword12 (G1 C3), the padded
    tail ends at its CB__END.  The shipped locator is unchanged.
    """
    rend = region_bounds(mm, blk, blocks, d8_outer)
    j = mm.find(V5_CFV2, blk, rend)
    if j < 0:
        return ""
    d8n, d12n, cb = _header_fields(mm, j, rend)
    if cb < 0:
        return ""
    end = cb + d12n
    if bytes(mm[cb : end])[-8:] != CB_END:
        pos = bytes(mm[cb : j + d8n + d12n]).find(CB_END)
        if pos < 0:
            return ""
        end = cb + pos + 8
    span = store.StoreSpan(block_start=blk, origin=j, origin_kind="v5header",
                           body_lo=j + 32, body_hi=cb, catalog_len=end - cb)
    return classify_store_content(mm, span)


def missing_audit(mm, blocks, d8_outer, g1_class):
    """G1 N10 family + live recovery probes for a store-less part."""
    stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
    seebody = [b for b, nm in blocks if nm == "CATSeeBodyCont"]
    xdoc = [b for b, nm in blocks if nm == "CATXDocLinkCont"]
    row = {
        "missing_family": g1_class if stdcont else "no_stdcont",
        "seebody_store": "False",
        "xdoclink_store": "False",
        "recovery_probe": "none",
        "recovery_store_class": "",
        "recovery_pool_vertices": "",
        "recovery_malform_family": "",
        "recovery_malform_detail": "",
        "recovery_postfix_class": "",
    }
    # G1-comparable presence flags: V5_CFV2 anywhere in that region
    for tag, cand_blocks in (("seebody", seebody), ("xdoclink", xdoc)):
        for blk in cand_blocks:
            rend = region_bounds(mm, blk, blocks, d8_outer)
            if mm.find(V5_CFV2, blk, rend) >= 0:
                row[f"{tag}_store"] = "True"
    # live recovery probe with the shipped locate law, xdoc first
    # (G1's next_block_store family), then seebody; a probe that raises
    # malformed-store-header is audited with the same byte-level rules as
    # the stdcont malformed family (analysis only)
    first = True
    for tag, cand_blocks in (("xdoclink", xdoc), ("seebody", seebody)):
        for blk in cand_blocks:
            probe, cls, nv = probe_recovery(mm, blk, blocks, d8_outer, tag)
            if probe is None:
                continue
            if first:
                row["recovery_probe"] = probe
                row["recovery_store_class"] = cls
                row["recovery_pool_vertices"] = nv
                first = False
            if probe == f"{tag}-malformed":
                fam, mdetail = malform_audit(mm, blk, blocks, d8_outer)
                postfix = malform_postfix_content(mm, blk, blocks, d8_outer)
                row["recovery_malform_family"] = fam
                row["recovery_malform_detail"] = mdetail
                row["recovery_postfix_class"] = postfix
            if probe.endswith("-located"):
                return row
    return row


def region_signature(mm, blocks, d8_outer, row):
    """Cheap byte signature over every CATStdCont region (joined)."""
    stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
    sizes, v5s, cbs, wraps, surfs = [], [], [], [], []
    for blk in stdcont:
        rend = region_bounds(mm, blk, blocks, d8_outer)
        sizes.append(rend - blk)
        v5s.append(mm.find(V5_CFV2, blk, rend))
        cbs.append(mm.find(CB0001, blk, rend))
        wraps.append(len(store.find_all(mm, FULL_WRAP, blk, rend)))
        surfs.append(mm.find(SURFACICREPS_U16, blk, rend))
    join = lambda vals: ";".join(str(v) for v in vals)  # noqa: E731
    row["region_size"] = join(sizes)
    row["region_v5cfv2"] = join(v5s)
    row["region_cb0001"] = join(cbs)
    row["region_wrappers"] = join(wraps)
    row["region_surfacicreps_u16"] = join(surfs)


def deep_survey(mm, rel):
    """Byte-level store-signature survey for one part (the deep sample)."""
    size = mm.size()
    d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(mm)
    print(f"== deep survey {rel['sha256'][:16]} {rel['detected_version']} "
          f"size={size}")
    print(f"  outer dword8={d8_outer}  magic[:16]={bytes(mm[:16]).hex()}")
    for b, nm in blocks:
        rend = region_bounds(mm, b, blocks, d8_outer)
        print(f"  block {nm:24s} at {b} (region to {rend}, {rend - b} B)")
    for needle, label in ((V5_CFV2, "V5_CFV2"), (CB0001, "CB0001"),
                          (CB_END, "CB__END"),
                          (SURFACICREPS_U16, "SurfacicReps(u16)")):
        hits = store.find_all(mm, needle, 0, size)
        print(f"  {label:18s} x{len(hits)} at {hits[:12]}"
              f"{' ...' if len(hits) > 12 else ''}")
    for b, nm in blocks:
        if nm not in ("CATStdCont", "CATSeeBodyCont", "CATXDocLinkCont"):
            continue
        rend = region_bounds(mm, b, blocks, d8_outer)
        print(f"  {nm} region [{b},{rend}) size={rend - b}")
        print(f"    first 48 B: {bytes(mm[b:b + 48]).hex(' ')}")
        wrappers = store.find_all(mm, FULL_WRAP, b, rend)
        kinds = [bytes(mm[o + 8 : o + 10]).hex() for o in wrappers]
        print(f"    pool wrappers x{len(wrappers)} kinds={kinds[:16]}")
        j = mm.find(V5_CFV2, b, rend)
        if j >= 0:
            d8n, d12n, cb = _header_fields(mm, j, rend)
            nh = bytes(mm[j : j + 32])
            ff8 = nh[16:24] == b"\xff" * 8
            z8 = nh[24:32] == b"\x00" * 8
            print(f"    nested header at {j}: d8n={d8n} d12n={d12n} "
                  f"ff8={ff8} z8={z8} cb={cb}")
            if cb >= 0 and d12n:
                tail = bytes(mm[cb : cb + d12n])
                print(f"    tail[-36:]: {tail[-36:].hex(' ')}")


def audit_part(mm, rel, fitness_class):
    """One part: replay + byte audit. Returns the CSV row dict."""
    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    row["release"] = release_of(rel["detected_version"])
    size = mm.size()
    row["size_bytes"] = size
    d8_outer = int.from_bytes(mm[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(mm)
    stdcont = [b for b, nm in blocks if nm == "CATStdCont"]
    row["n_stdcont"] = len(stdcont)
    row["containers"] = ";".join(nm for _, nm in blocks)
    row["v5cfv2_hits_file"] = len(store.find_all(mm, V5_CFV2, 0, size))
    row["cb0001_hits_file"] = len(store.find_all(mm, CB0001, 0, size))

    rclass, rdetail = replay_export(mm)
    row["replay_class"] = rclass
    row["replay_match"] = str(rclass == (fitness_class or "pass"))

    # G1 region class of the first CATStdCont region (N10 taxonomy,
    # including G1's next-block rule)
    g1_class = ""
    if stdcont:
        g1_class = analyze_region(
            mm, stdcont[0], blocks, d8_outer,
            {"sha256": rel["sha256"],
             "detected_version": rel["detected_version"]}, 0)[0]
        xdoc = next((b for b, nm in blocks if nm == "CATXDocLinkCont"), None)
        if g1_class == "none_in_region" and xdoc is not None and \
                xdoc == next((b for b, _ in blocks if b > stdcont[0]), None):
            xrend = region_bounds(mm, xdoc, blocks, d8_outer)
            if mm.find(V5_CFV2, xdoc, xrend) >= 0:
                g1_class = "next_block_store"
    row["g1_region_class"] = g1_class

    # shipped locator across every CATStdCont region (export._export_data
    # semantics: first located span's failure is the reported one)
    spans = []
    for blk in stdcont:
        try:
            span = store.locate_store(mm, blk, blocks, d8_outer)
        except ExportError:
            continue
        if span is not None:
            spans.append(span)
    row["n_stores_located"] = len(spans)

    if rclass == "pass":
        root, detail = "pass", ""
    elif rclass == "missing-geometry-store":
        root = "missing-store"
        row.update(missing_audit(mm, blocks, d8_outer, g1_class))
        region_signature(mm, blocks, d8_outer, row)
        detail = f"{row['missing_family']}; recovery={row['recovery_probe']}"
        if row["recovery_store_class"]:
            detail += f" ({row['recovery_store_class']})"
    elif rclass == "malformed-store-header":
        root = "malformed-store-header"
        if stdcont:
            fam, mdetail = malform_audit(mm, stdcont[0], blocks, d8_outer)
            row["malform_family"] = fam
            row["malform_detail"] = mdetail
            postfix = malform_postfix_content(mm, stdcont[0], blocks,
                                              d8_outer)
        else:
            fam, mdetail, postfix = "no-stdcont", "malformed w/o stdcont", ""
        row["malform_postfix_class"] = postfix
        detail = f"{fam}; postfix={postfix}"
    elif rclass == "undecoded-variant":
        root, detail = _undecoded_audit(mm, spans, rdetail, row)
    else:
        root, detail = f"replay-{rclass}", rdetail[:120]
    row["root_class"] = root
    row["root_detail"] = detail
    return row


def _undecoded_audit(mm, spans, rdetail, row):
    """Decompose one undecoded-variant failure at byte level.

    The shipped gate reports the FIRST located span's failure
    (export._export_data), so the audit targets ``spans[0]``.
    """
    if not spans:
        return "audit-gap", "undecoded but no span located"
    span = spans[0]
    try:
        _, kinds_pre = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
        composite = pool.has_composite_space(kinds_pre)
    except ExportError:
        composite = False
    aud, flat = body_audit(mm, span, clean_store=not composite)
    row.update(aud)
    row["pool_size"] = len(flat)
    if rdetail.startswith("composite index space"):
        if row["edge_groups_0102"] and row["ff_openers"]:
            trig = "both"
        elif row["edge_groups_0102"]:
            trig = "edge-group"
        else:
            trig = "ff-opener"
        row["composite_trigger"] = trig
        return "composite-space", (
            f"trigger={trig}; edge_recs={row['edge_table_records']} "
            f"(max endpoint {row['max_edge_endpoint']} vs pool "
            f"{row['pool_vertices']}); refs_beyond_analysis="
            f"{row['refs_beyond_analysis']} (max ref "
            f"{row['max_facet_ref']} vs pool {row['pool_vertices']})")
    if rdetail.startswith("no 01 06 vertex pool"):
        strips = sum(1 for _ in facets.STRIP_RE.finditer(
            mm, span.body_lo, span.body_hi))
        if row["wrapper_groups"] == 0:
            sub = "no-wrappers"
        elif strips:
            sub = "strips-no-pool"
        else:
            sub = "wrappers-no-0106"
        return "poolless-store", (
            f"{sub}; wrappers={row['wrapper_groups']} "
            f"kinds={row['wrapper_kinds'][:48]}; "
            f"strip_candidates={strips}; "
            f"body={span.body_hi - span.body_lo} B")
    if rdetail.startswith("facet references beyond"):
        return "refs-beyond-pool", (
            f"max ref {row['max_facet_ref']} vs pool {row['pool_vertices']}")
    if rdetail.startswith("no exportable facet content"):
        return "facet-content-variant", rdetail[:120]
    return "replay-other", rdetail[:120]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--report", default=str(DEFAULT_REPORT))
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    args = ap.parse_args()

    import json

    report = json.loads(Path(args.report).read_text())
    fitness = {}
    for rec in report["files"]:
        l2 = rec.get("l2") or {}
        if l2.get("status") == "fail":
            fitness[rec["sha256"]] = l2.get("error_class")
        elif l2.get("status") == "pass":
            fitness[rec["sha256"]] = "pass"

    rows = [r for r in csv.DictReader(MANIFEST.open())
            if r["split"] in ("dev", "held-out") and r["kind"] == "part"]
    if args.include_sha16:
        want = {h for h in args.include_sha16.split(",") if h}
        rows = [r for r in rows if r["sha256"][:16] in want]
    rows.sort(key=lambda r: r["sha256"])

    out_rows = []
    for r in rows:
        path = ROOT / r["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                if args.deep:
                    deep_survey(mm, r)
                else:
                    out_rows.append(
                        audit_part(mm, r, fitness.get(r["sha256"], "")))
            except Exception as exc:  # noqa: BLE001 - recorded per part
                row = {k: "" for k in FIELDS}
                row["sha256"] = r["sha256"]
                row["split"] = r["split"]
                row["audit_error"] = f"{type(exc).__name__}: {exc}"
                out_rows.append(row)
            finally:
                mm.close()

    if args.deep:
        return 0
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "l2-grind-classification.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")
    summarize(out_rows)
    return 0


def summarize(rows):
    """Per-class rates + the ceiling arithmetic toward the 80% bar."""
    dev = [r for r in rows if r["split"] == "dev"]
    ho = [r for r in rows if r["split"] == "held-out"]
    print("== root-class census ==")
    for label, pop in (("dev", dev), ("held-out", ho)):
        n = len(pop)
        c = Counter(r["root_class"] for r in pop)
        print(f"  {label}: n={n} " +
              " ".join(f"{k}={v} ({v / n:.3f})"
                       for k, v in sorted(c.items(), key=lambda x: -x[1])))
    mism = [r["sha256"][:12] for r in rows if r["replay_match"] != "True"]
    print(f"  replay mismatches vs baseline report: {len(mism)} {mism[:5]}")
    aerr = [r["sha256"][:12] for r in rows if r["audit_error"]]
    print(f"  audit errors: {len(aerr)} {aerr[:5]}")

    dev_comp = [r for r in dev if r["root_class"] == "composite-space"]
    trig = Counter(r["composite_trigger"] for r in dev_comp)
    beyond = sum(1 for r in dev_comp if r["refs_beyond_analysis"])
    print(f"  composite triggers (dev): {dict(trig)}; refs-beyond measured "
          f"under analysis: {beyond}/{len(dev_comp)}")

    poolless = [r for r in dev if r["root_class"] == "poolless-store"]
    subs = Counter(r["root_detail"].split(";")[0] for r in poolless)
    print(f"  poolless sub-classes (dev): {dict(subs)}")

    rec = [r for r in dev if r["root_class"] == "missing-store"]
    fams = Counter(r["missing_family"] for r in rec)
    probes = Counter(r["recovery_probe"] for r in rec)
    rcls = Counter(r["recovery_store_class"] for r in rec
                   if r["recovery_probe"].endswith("-located"))
    rmfam = Counter(r["recovery_malform_family"] for r in rec
                    if r["recovery_malform_family"])
    rpost = Counter(r["recovery_postfix_class"] for r in rec
                    if r["recovery_postfix_class"])
    print(f"  missing families (dev): {dict(fams)}")
    print(f"  recovery probes: {dict(probes)}")
    print(f"  recovered-store classes: {dict(rcls)}")
    print(f"  recovery-probe malform families: {dict(rmfam)}")
    print(f"  recovery post-fix content classes: {dict(rpost)}")

    mal = [r for r in dev if r["root_class"] == "malformed-store-header"]
    mfam = Counter(r["malform_family"] for r in mal)
    mpost = Counter(r["malform_postfix_class"] for r in mal)
    print(f"  malformed families (dev): {dict(mfam)}")
    print(f"  malformed post-fix content classes: {dict(mpost)}")

    # ---- ceiling arithmetic (dev; bar = 80% of n_dev, rounded up)
    n_dev = len(dev)
    bar = -(-80 * n_dev // 100)
    base_pass = sum(1 for r in dev if r["root_class"] == "pass")
    n_composite = len(dev_comp)
    n_poolless = len(poolless)
    n_refs = sum(1 for r in dev if r["root_class"] == "refs-beyond-pool")
    located_now = base_pass + n_composite + n_poolless + n_refs

    # recovery classes: probes located by the shipped law (xdoc/seebody)
    # plus the relaxed-law post-fix classes on the malformed probes
    rec_loc = [r for r in rec if r["recovery_probe"].endswith("-located")]
    rec_relax = [r for r in rec
                 if r["recovery_malform_family"] in
                 ("dword8-overshoot", "padded-tail")]
    n_rec = len(rec_loc) + len(rec_relax)
    rec_cls = Counter(
        [r["recovery_store_class"] for r in rec_loc]
        + [r["recovery_postfix_class"] for r in rec_relax])
    mal_cls = Counter(r["malform_postfix_class"] for r in mal
                      if r["malform_family"] in
                      ("dword8-overshoot", "padded-tail"))
    # pass contribution of each class under each lever
    #   composite bodies pass under L1; poolless under L2; refs-beyond
    #   under L3; clean recovery bodies pass with their location alone;
    #   stdcont-malformed bodies need L4 first, then their class lever.
    located_cap_b = located_now + len(mal) + n_rec
    print("== ceiling arithmetic (dev) ==")
    print(f"  bar: {bar} passes = {bar / n_dev:.4f} of {n_dev}")
    print(f"  baseline pass {base_pass}; located now {located_now} "
          f"({located_now / n_dev:.4f})")
    print(f"  class pools: located (composite {n_composite}, poolless "
          f"{n_poolless}, refs-beyond {n_refs}); recovery {n_rec} "
          f"({dict(rec_cls)}); malformed-postfix {len(mal)} "
          f"({dict(mal_cls)})")
    print(f"  recovery candidates {n_rec} = {len(rec_loc)} located by the "
          f"shipped law + {len(rec_relax)} by the relaxed tail law")
    print(f"  located caps: A (now) {located_now} = "
          f"{located_now / n_dev:.4f}; B (+ stdcont-malformed fix) "
          f"{located_now + len(mal)} = {(located_now + len(mal)) / n_dev:.4f}; "
          f"C (+ recovery extension) {located_cap_b} = "
          f"{located_cap_b / n_dev:.4f}")

    def reachable(use_l1, use_l2, use_l3, use_l4, use_l5):
        """Pass ceiling for a lever set.

        L1 composite / L2 poolless / L3 refs-beyond cover their located
        classes; L4 recovers the 29 stdcont-malformed bodies (their
        class lever must also be on); L5 recovers the 135 missing-store
        candidates the same way, plus the clean ones that pass with
        location alone.
        """
        n = base_pass
        n += use_l1 * (n_composite
                       + use_l5 * rec_cls["composite"]
                       + use_l4 * mal_cls["composite"])
        n += use_l2 * (n_poolless
                       + use_l5 * rec_cls["poolless"]
                       + use_l4 * mal_cls["poolless"])
        n += use_l3 * (n_refs + use_l5 * rec_cls["refs-beyond"])
        n += use_l5 * rec_cls["clean"]
        return n

    names = ("L1 composite", "L2 poolless", "L3 refs-beyond",
             "L4 malfix", "L5 recovery")
    print("  pass ceilings by lever set:")
    combos = []
    for mask in range(32):
        flags = [bool(mask >> i & 1) for i in range(5)]
        n = reachable(*flags)
        combos.append((n, flags))
    for mask in (0b00001, 0b00011, 0b00111, 0b01001, 0b01011, 0b10011,
                 0b11001, 0b11011, 0b11111):
        flags = [bool(mask >> i & 1) for i in range(5)]
        label = " + ".join(nm.split()[0] for nm, f in zip(names, flags)
                           if f) or "none"
        n = reachable(*flags)
        print(f"    {{{label}}}: {n} "
              f"({'REACHES bar' if n >= bar else 'below bar'})")

    def reaches(flags):
        return reachable(*flags) >= bar

    minimal = []
    for mask in range(32):
        flags = [bool(mask >> i & 1) for i in range(5)]
        if not reaches(flags):
            continue
        if not any(sum(g) < sum(flags) and all(gi or not fi
                                               for gi, fi in zip(g, flags))
                   for g in ([bool(m >> i & 1) for i in range(5)]
                             for m in range(32)) if reaches(g)):
            minimal.append(flags)
    for f in sorted(minimal, key=sum):
        label = " + ".join(nm.split()[0] for nm, fl in zip(names, f) if fl)
        print(f"  minimal lever set reaching the bar: {{{label}}} "
              f"-> {reachable(*f)}")
    print(f"  without L1 (composite): max "
          f"{reachable(False, True, True, True, True)} < {bar} "
          "-> composite decode is REQUIRED")
    no_l5 = reachable(True, True, True, True, False)
    print(f"  without L5 (recovery): max {no_l5} "
          f"({'< ' + str(bar) + ' -> the recovery extension is REQUIRED' if no_l5 < bar else '>= bar'})")
    print(f"  held-out (no-regret scope): "
          f"{dict(Counter(r['root_class'] for r in ho))}")


if __name__ == "__main__":
    sys.exit(main())
