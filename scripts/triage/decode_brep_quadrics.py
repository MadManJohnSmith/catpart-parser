#!/usr/bin/env python3
"""Corpus triage of the BR4 quadric-surface slice (ticket #56, Spec G #47).

Recognizes cylindrical / conical / spherical strip patches corpus-wide
over the 1,442-part manifest (and specifically the 1,089 L2-pass
population), on the two scopes where facet references resolve to
coordinates: pool-only stores (G3/F2 lex-rank law) and composite
stores decoded by the shipped stage-3d identity decode
(``catpart.geometry.composite.find_list_node`` + ``decode_region`` +
``parse_strip_records``; candidate scope).  Also pins the census
tie-out arithmetic: the frozen ``SRF-02`` row (strip-record presence)
reproduces from the census columns; the frozen per-class ``SRF-03..07``
counts have no committed generator (the census emits one
undifferentiated ``GEOM_SURF_QUADRIC`` from CGM presence).

Outputs docs/evidence/data/br4-quadrics-claims.csv (one row per claim,
per scope — the committed artifact; every prose figure of the evidence
note is a row or row-derived sum).  The counted unit is one ``ty``
strip loop of an accepted record (a strip segment), not a record: a
record whose ``ty`` count is > 1 contributes that many units.

The per-file counter table is NOT written by default (only the
ticket's owned files land in the tree); pass --files-out PATH to write
it there.  Deterministic: sorted manifest order; no wall-clock value
enters the CSV.  Read-only over the corpus (binaries resolved against
the main checkout when absent here); run with the worktree venv:

  .venv/bin/python -I scripts/triage/decode_brep_quadrics.py
  .venv/bin/python -I scripts/triage/decode_brep_quadrics.py --selftest

``--include-sha16`` is a SUBSET/anchor mode: comma-separated hex sha256
prefixes (any length; the documented anchor form is 16 hex chars)
prefix-match the manifest digests, and the run aborts non-zero when the
selection is empty (never writing a zeroed claims file).  A subset run
never writes into a committed ``docs/evidence/data`` directory — the
guard is path-shaped, so it covers this worktree's, the main
checkout's and any other tree's copy (pass ``--out-dir`` elsewhere) —
and every row it does write carries a SUBSET RUN marker in its note
(the census tie-out rows stay full-corpus by construction):

  .venv/bin/python -I scripts/triage/decode_brep_quadrics.py \
    --include-sha16 369fc90b25b4977d --out-dir /tmp/br4-anchor
"""

from __future__ import annotations

import argparse
import csv
import mmap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
L2_STAGE15 = ROOT / "docs" / "evidence" / "data" / "stage15-identity-export-files.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"
CENSUS_FILES = ROOT / "docs" / "evidence" / "data" / "brep-census-files.csv"
MAIN_CHECKOUT = Path("/home/alan/Documents/Repos/catpart-parser")
# A committed claims directory, path-shaped: the same suffix identifies
# this worktree's copy, the main checkout's and any other tree's, so a
# subset run cannot land on a committed CSV by pointing --out-dir at a
# different checkout.
COMMITTED_DATA_SUFFIX = ("docs", "evidence", "data")

sys.path.insert(0, str(ROOT / "src"))

from catpart.brep import quadrics  # noqa: E402
from catpart.geometry import composite, facets, pool, store  # noqa: E402

CLAIM_FIELDS = [
    "claim",
    "construct",
    "statement",
    "scope",
    "observations",
    "passes",
    "rate",
    "label",
    "note",
]

FILE_FIELDS = [
    "sha256",
    "split",
    "l2_status",
    "store_class",
    "store_decoded",
    "decode_error",
    "census_strips_present",
]

STRIP_MARKERS = (0x42, 0x4A)  # the established strip families (G3 F3/C9)

# Frozen per-class counts from brep-construct-vocabulary.csv (ticket
# #48); the census's committed generator emits one undifferentiated
# GEOM_SURF_QUADRIC class from CGM presence instead.
FROZEN = {
    "SRF-02": ("GEOM_SURF_CYLINDER", 1128, 0.9972),
    "SRF-03": ("GEOM_SURF_QUADRIC", 542, 0.465),
    "SRF-04": ("GEOM_SURF_QUADRIC", 412, 0.354),
    "SRF-05": ("GEOM_SURF_QUADRIC", 320, 0.275),
    "SRF-06": ("GEOM_SURF_QUADRIC", 680, 0.582),
    "SRF-07": ("GEOM_SURF_QUADRIC", 890, 0.795),
}

LABELS = (
    "planar",
    "degenerate",
    "cylinder",
    "sphere",
    "cone",
    "pencil_noncyl",
    "curved_unclassified",
)


def resolve_path(rel):
    path = ROOT / rel["local_path"]
    if path.exists():
        return path
    return MAIN_CHECKOUT / rel["local_path"]


def locate_span(mm):
    """Store-body span via the census's container-probing law, or None."""
    d8 = int.from_bytes(mm[8:12], "big") if len(mm) >= 12 else 0
    blocks = store.valid_blocks(mm)
    name_of = {
        store.CONTAINER_STDCONT: "CATStdCont",
        store.CONTAINER_XDOCLINK: "CATXDocLinkCont",
        store.CONTAINER_SEEBODY: "CATSeeBodyCont",
    }
    for container in (
        store.CONTAINER_STDCONT,
        store.CONTAINER_XDOCLINK,
        store.CONTAINER_SEEBODY,
        store.CONTAINER_OTHER,
    ):
        want = name_of.get(container)
        cands = [b for b, nm in blocks if want is None or nm == want]
        for blk in cands:
            try:
                span = store.locate_store(mm, blk, blocks, d8, container=container)
            except Exception:  # noqa: BLE001 - recorded per part
                continue
            if span is not None:
                return span
    return None


def new_counters():
    return {f"patches_{lab}": 0 for lab in LABELS} | {
        "loops_oop": 0,
        "loops_oob": 0,
        "loops_skipref": 0,
        "records": 0,
        "records_42": 0,
        "records_4a": 0,
        "records_5byte": 0,
    }


def note_record(marker, header_len, counters):
    """Count one accepted strip record and its carrier layout family.

    ``0x42`` carries NO normal (``facets.NORMAL_MARKERS_ALL`` is
    0x49/0x4a/0x4b/0x4c/0x4e), so its ``ty`` counts start at
    ``+0x08 (8d)``; ``0x4a`` carries the 12-B normal, counts at
    ``+0x14 (20d)``.  ``header_len`` 5 is the form whose byte at
    ``+0x03 (3d)`` is not ``0xff`` (every following offset shifts +1).
    """
    counters["records"] += 1
    counters["records_42" if marker == 0x42 else "records_4a"] += 1
    if header_len == 5:
        counters["records_5byte"] += 1


def classify_poolonly(data, lo, hi, flat, lex, counters):
    """Classify the strip loops of a pool-only store (G3 scope).

    The counted unit is one ``ty`` strip loop of an accepted record (a
    strip segment); a record with several ``ty`` loops contributes
    several units.
    """
    scan = facets.scan_facets(data, lo, hi, clean_store=True)
    for rec in scan.records:
        if rec.marker not in STRIP_MARKERS:
            continue
        note_record(rec.marker, rec.header_len, counters)
        for refs in facets.record_loops(rec):
            if not refs:
                continue
            if max(refs) >= len(flat):
                counters["loops_oop"] += 1
                continue
            resolved = [lex[x] for x in refs]
            fit = quadrics.classify_strip_patch(resolved, flat)
            counters[f"patches_{fit.label.replace('-', '_')}"] += 1


def classify_composite(data, lo, hi, counters):
    """Classify the strip loops of a composite store under the identity
    table-walk reading; returns an error-class string or ''.

    This is the IDENTITY path only — ``find_list_node`` +
    ``decode_region`` + ``parse_strip_records``.  The shipped stage-3d
    export's fallback laws (raw-array, per-rep, mixed-write) and its
    refs-beyond-element-space gate (``composite.py``'s
    ``decode_composite_store``) are NOT run here, so a store this
    function rejects may still export; the claims carry the
    cross-tabulation against ``stage15-identity-export-files.csv``.
    The counted unit is one ``ty`` strip loop of an accepted record (a
    strip segment), not a record.
    """
    hdrs = [m.start() for m in composite.STRIP_RE.finditer(data, lo, hi)]
    node_hi = hdrs[0] if hdrs else hi
    ln = composite.find_list_node(data, lo, node_hi)
    if ln is None:
        return "no-token-node"
    payload, elem_decl, _edge_bound = ln
    try:
        elements, _info = composite.decode_region(payload, elem_decl)
    except Exception as exc:  # noqa: BLE001 - recorded per part
        return getattr(exc, "error_class", "decode-region-failed")
    records, _nh = composite.parse_strip_records(data, lo, hi, elem_decl, elements)
    for off, mk, _normal, counts, refs, _width in records:
        if mk not in STRIP_MARKERS:
            continue
        note_record(mk, 5 if data[off + 3] != 0xFF else 4, counters)
        pos = 0
        for c in counts:
            loop = refs[pos : pos + c]
            pos += c
            if not loop:
                continue
            if any(r >= len(elements) for r in loop):
                counters["loops_oob"] += 1
                continue
            pts = [elements[r][1] for r in loop]
            if any(p is None for p in pts):
                counters["loops_skipref"] += 1
                continue
            fit = quadrics.classify_strip_patch(list(range(len(pts))), pts)
            counters[f"patches_{fit.label.replace('-', '_')}"] += 1
    return ""


def audit_part(mm):
    """One part's BR4 audit — the per-file counters feeding the claims."""
    out = {
        "store_class": "",
        "store_decoded": "",
        "decode_error": "",
        "census_strips_present": 0,
        "poolonly": new_counters(),
        "composite": new_counters(),
    }
    span = None
    try:
        span = locate_span(mm)
    except Exception:  # noqa: BLE001 - recorded per part
        span = None
    if span is None:
        return out
    lo, hi = span.body_lo, span.body_hi

    # Census tie-out scan: the census's default scan (no clean flag),
    # counting accepted 0x42/0x4A records (the census's strips counter).
    scan = facets.scan_facets(mm, lo, hi)
    out["census_strips_present"] = int(
        any(r.marker in STRIP_MARKERS for r in scan.records)
    )

    try:
        groups, kinds = pool.scan_pool_groups(mm, lo, hi)
    except Exception:  # noqa: BLE001 - recorded per part
        out["store_class"] = "pool-scan-failed"
        return out
    composite_store = pool.has_composite_space(kinds)
    out["store_class"] = "composite" if composite_store else "pool-only"

    if not composite_store:
        flat = [v for g in groups for v in g.vertices]
        lex = facets.lex_rank_map(flat)
        classify_poolonly(mm, lo, hi, flat, lex, out["poolonly"])
        out["store_decoded"] = "pool-only"
        return out

    err = classify_composite(mm, lo, hi, out["composite"])
    out["decode_error"] = err
    out["store_decoded"] = "composite-decoded" if not err else "composite-undecoded"
    return out


def census_tieout_claims(l2_by_sha, claims):
    """The census tie-out arithmetic from the committed census CSV.

    SRF-02's frozen row (strip presence) reproduces from the census
    columns; SRF-03..07's frozen per-class counts do not (the
    committed generator emits GEOM_SURF_QUADRIC from CGM presence).
    """
    if not CENSUS_FILES.exists():
        return
    with CENSUS_FILES.open() as f:
        rows = list(csv.DictReader(f))
    l2_rows = [r for r in rows if l2_by_sha.get(r["sha256"]) == "pass"]
    n_l2 = len(l2_rows)
    strips_corpus = sum(1 for r in rows if int(r["facet_strips"]) > 0)
    strips_l2 = sum(1 for r in l2_rows if int(r["facet_strips"]) > 0)
    cgm_corpus = sum(1 for r in rows if r["cgm_present"] in ("True", "true", "1"))
    cgm_l2 = sum(1 for r in l2_rows if r["cgm_present"] in ("True", "true", "1"))

    claims.append(
        {
            "claim": "S02_census_tieout_corpus",
            "construct": "SRF-02",
            "statement": (
                "corpus parts with >= 1 accepted 0x42/0x4A strip record "
                f"[frozen GEOM_SURF_CYLINDER: {FROZEN['SRF-02'][1]}]"
            ),
            "scope": "full corpus",
            "observations": len(rows),
            "passes": strips_corpus,
            "rate": round(strips_corpus / len(rows), 6) if rows else 0.0,
            "label": "fact",
            "note": "reproduces the frozen row exactly (census strips column)",
        }
    )
    claims.append(
        {
            "claim": "S02_census_tieout_l2",
            "construct": "SRF-02",
            "statement": (
                "L2-pass files with >= 1 accepted 0x42/0x4A strip record "
                f"[frozen rate: {FROZEN['SRF-02'][2]}]"
            ),
            "scope": "l2-pass",
            "observations": n_l2,
            "passes": strips_l2,
            "rate": round(strips_l2 / n_l2, 6) if n_l2 else 0.0,
            "label": "fact",
            "note": "reproduces the frozen row exactly (census strips column)",
        }
    )
    for sid, (census_label, frozen_n, frozen_rate) in FROZEN.items():
        if sid == "SRF-02":
            continue
        claims.append(
            {
                "claim": f"{sid}_frozen_generator_drift",
                "construct": sid,
                "statement": (
                    f"frozen count {frozen_n} corpus / rate {frozen_rate} has NO "
                    f"committed generator: the census emits {census_label} from "
                    "CGM presence (one undifferentiated class)"
                ),
                "scope": "full corpus",
                "observations": len(rows),
                "passes": cgm_corpus,
                "rate": round(cgm_corpus / len(rows), 6) if rows else 0.0,
                "label": "drift (fact)",
                "note": (
                    "cgm_present corpus count shown; differs from the frozen "
                    "per-class count — treat the frozen split as unprovenanced "
                    "(BR3 §6.3 pattern)"
                ),
            }
        )
    claims.append(
        {
            "claim": "S03_07_census_quadric_presence",
            "construct": "SRF-03..07",
            "statement": (
                "the census's actual GEOM_SURF_QUADRIC detector = CGM presence, "
                "undifferentiated across cone/sphere/torus/revolution/extrusion"
            ),
            "scope": "full corpus",
            "observations": len(rows),
            "passes": cgm_corpus,
            "rate": round(cgm_corpus / len(rows), 6) if rows else 0.0,
            "label": "fact",
            "note": (
                f"L2-pass: {cgm_l2}/{n_l2} = {round(cgm_l2 / n_l2, 6) if n_l2 else 0} "
                "— the upper bound every per-class quadric claim must tie out against"
            ),
        }
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--include-sha16", default="")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--files-out", default="")
    args = ap.parse_args()

    if args.selftest:
        n_checks = quadrics.selftest_count()
        failures = quadrics.selftest()
        print(f"selftest: {n_checks - len(failures)}/{n_checks} cases pass")
        for f in failures:
            print("  FAIL", f)
        sys.exit(1 if failures else 0)

    out_dir = Path(args.out_dir)

    l2_by_sha = {}
    shipped_by_sha = {}
    if L2_STAGE15.exists():
        with L2_STAGE15.open() as f:
            for r in csv.DictReader(f):
                l2_by_sha[r["sha256"]] = r.get("l2_status", "")
                shipped_by_sha[r["sha256"]] = r

    claims: list[dict] = []
    census_tieout_claims(l2_by_sha, claims)

    with MANIFEST.open() as f:
        parts = [r for r in csv.DictReader(f) if r["kind"] == "part"]
    parts.sort(key=lambda r: r["sha256"])
    n_manifest = len(parts)
    if args.include_sha16:
        prefixes = [p.strip().lower() for p in args.include_sha16.split(",") if p.strip()]
        if not prefixes:
            ap.error("--include-sha16 needs at least one hex sha256 prefix")
        for prefix in prefixes:
            if len(prefix) > 64 or any(c not in "0123456789abcdef" for c in prefix):
                ap.error(f"--include-sha16: {prefix!r} is not a hex sha256 prefix")
        parts = [
            r for r in parts if any(r["sha256"].lower().startswith(p) for p in prefixes)
        ]
        if not parts:
            print(
                f"include-sha16: no manifest part matches {args.include_sha16!r}; "
                "nothing written",
                file=sys.stderr,
            )
            sys.exit(2)
        if out_dir.resolve().parts[-3:] == COMMITTED_DATA_SUFFIX:
            ap.error(
                "--include-sha16 is a subset mode: --out-dir must not resolve into a "
                "committed docs/evidence/data directory (this checkout's or any other "
                "tree's) — a subset must never overwrite a committed claims CSV"
            )

    out_dir.mkdir(parents=True, exist_ok=True)

    files_rows = []
    agg = {
        "located": 0,
        "poolonly": 0,
        "composite": 0,
        "composite_decoded": 0,
        "composite_undecoded": 0,
        "composite_decoded_shipped_fail": 0,
        "composite_fallback_only": 0,
        "composite_undecoded_both": 0,
        "fallback_stages": {},
        "pool_scan_failed": 0,
        "decode_errors": {},
    }
    scope_counts = {"poolonly": {lab: 0 for lab in LABELS}, "composite": {lab: 0 for lab in LABELS}}

    for rel in parts:
        path = resolve_path(rel)
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                audit = audit_part(mm)
            finally:
                mm.close()
        row = {k: audit[k] for k in FILE_FIELDS if k in audit}
        for scope in ("poolonly", "composite"):
            for key, val in audit[scope].items():
                row[f"{scope}_{key}"] = val
        row["sha256"] = rel["sha256"]
        row["split"] = rel.get("split", "")
        row["l2_status"] = l2_by_sha.get(rel["sha256"], "")
        files_rows.append(row)

        if audit["store_class"] == "pool-scan-failed":
            agg["pool_scan_failed"] += 1
            continue
        if not audit["store_class"]:
            continue
        agg["located"] += 1
        if audit["store_class"] == "pool-only":
            agg["poolonly"] += 1
            for lab in LABELS:
                scope_counts["poolonly"][lab] += audit["poolonly"][f"patches_{lab}"]
        else:
            agg["composite"] += 1
            shipped = shipped_by_sha.get(rel["sha256"])
            shipped_ok = bool(shipped) and shipped.get("export_ok") == "1"
            if audit["store_decoded"] == "composite-decoded":
                agg["composite_decoded"] += 1
                if shipped and not shipped_ok:
                    agg["composite_decoded_shipped_fail"] += 1
                for lab in LABELS:
                    scope_counts["composite"][lab] += audit["composite"][f"patches_{lab}"]
            else:
                agg["composite_undecoded"] += 1
                err = audit["decode_error"] or "unknown"
                agg["decode_errors"][err] = agg["decode_errors"].get(err, 0) + 1
                if shipped_ok:
                    agg["composite_fallback_only"] += 1
                    stage = shipped.get("stage") or "unknown"
                    agg["fallback_stages"][stage] = agg["fallback_stages"].get(stage, 0) + 1
                elif shipped:
                    agg["composite_undecoded_both"] += 1

    def add_claim(claim, construct, statement, scope, obs, passes, label, note):
        claims.append(
            {
                "claim": claim,
                "construct": construct,
                "statement": statement,
                "scope": scope,
                "observations": obs,
                "passes": passes,
                "rate": round(passes / obs, 6) if obs else 0.0,
                "label": label,
                "note": note,
            }
        )

    unit_note = (
        "unit = one ty strip loop of an accepted 0x42/0x4a record (a strip "
        "segment, G3 phase reset); a record with ty > 1 contributes that many units"
    )

    # File-level presence claims per scope (corpus + L2; the L2 row carries
    # the _l2 suffix so claim ids stay unique).
    def presence_claims(scope_prefix, scope_name, note):
        for lab, sid in (
            ("cylinder", "SRF-02"),
            ("cone", "SRF-03"),
            ("sphere", "SRF-04"),
            ("pencil_noncyl", "SRF-07"),
            ("curved_unclassified", "SRF-05/06/07/08"),
        ):
            for pop_name, suffix, pred in (
                ("full corpus", "", lambda r: True),
                ("l2-pass", "_l2", lambda r: r["l2_status"] == "pass"),
            ):
                pop = [r for r in files_rows if pred(r)]
                hits = sum(1 for r in pop if r.get(f"{scope_prefix}_patches_{lab}", 0) > 0)
                add_claim(
                    f"{sid.replace('/', '_')}_{lab}_{scope_prefix}_presence{suffix}",
                    sid,
                    f"files with >= 1 {lab} strip loop ({scope_name} scope)",
                    pop_name,
                    len(pop),
                    hits,
                    "candidate" if scope_prefix == "composite" else "established",
                    note,
                )

    presence_claims(
        "poolonly",
        "pool-only stores (G3/F2 lex-rank semantics, established)",
        f"per-loop strip readings; recognized counts are floors.  {unit_note}",
    )
    presence_claims(
        "composite",
        "composite stores decoded by the identity table-walk reading (stage-3d, candidate scope)",
        "candidate: the composite element-index reading is anchor-established, corpus "
        f"candidate (stage-3b).  {unit_note}",
    )

    # Both-scopes presence: distinct files with >= 1 loop of the label on
    # EITHER scope (the prose's row-derived sums cite these rows).
    for lab, sid in (
        ("cylinder", "SRF-02"),
        ("cone", "SRF-03"),
        ("sphere", "SRF-04"),
        ("pencil_noncyl", "SRF-07"),
        ("curved_unclassified", "SRF-05/06/07/08"),
    ):
        for pop_name, suffix, pred in (
            ("full corpus", "", lambda r: True),
            ("l2-pass", "_l2", lambda r: r["l2_status"] == "pass"),
        ):
            pop = [r for r in files_rows if pred(r)]
            hits = sum(
                1
                for r in pop
                if r.get(f"poolonly_patches_{lab}", 0) > 0
                or r.get(f"composite_patches_{lab}", 0) > 0
            )
            add_claim(
                f"{sid.replace('/', '_')}_{lab}_allscopes_presence{suffix}",
                sid,
                f"distinct files with >= 1 {lab} strip loop on either scope "
                "(pool-only or composite identity-decoded)",
                pop_name,
                len(pop),
                hits,
                "fact",
                "both-scopes sum row (distinct files)",
            )

    # Volume anchors per scope.
    for scope_name, prefix in (
        ("pool-only stores", "poolonly"),
        ("composite identity-decoded stores", "composite"),
    ):
        for lab in LABELS:
            n = scope_counts[prefix][lab]
            add_claim(
                f"{prefix}_patches_{lab}_volume",
                "SRF-02..08",
                f"{lab} strip loops classified ({scope_name})",
                "located stores",
                n,
                n,
                "volume anchor",
                unit_note,
            )

    # SRF-05 upper bound: NO class is a torus population.  A torus band
    # is consistent with >= 2 laws — cylinder at either equator
    # (torus_equator_cylinder), cone or sphere over a short span
    # (torus_short_span_cone/_sphere), planar near the pole
    # (torus_pole_planar) — so every recognized loop of any class could
    # be a torus band and nothing can be subtracted.  The bound is the
    # whole classified total; it covers the CLASSIFIED population only.
    classified_total = sum(
        scope_counts[prefix][lab] for prefix in ("poolonly", "composite") for lab in LABELS
    )
    add_claim(
        "SRF-05_upper_bound_classified_patches",
        "SRF-05",
        "torus upper bound: the full classified strip-loop total — a torus band "
        "is consistent with >= 2 laws (cylinder at either equator, cone or sphere "
        "over a short span, planar near the pole), so no class is a torus "
        "population and none can be subtracted",
        "located stores",
        classified_total,
        classified_total,
        "upper bound (row-derived sum)",
        "= every *_patches_*_volume row summed over both scopes (planar, "
        "degenerate, cylinder, sphere, cone, pencil_noncyl, curved_unclassified); "
        "fixtures pin the measured escapes: torus_equator_cylinder (cylinder, "
        "R 33.998 / 26.002), torus_pole_planar, torus_short_span_cone, "
        "torus_short_span_sphere, torus_fillet.  Bounds the CLASSIFIED population "
        "only: composite_loops_excluded_share (90,451 loops) and the undecoded "
        "stores of scope_composite_decode are above it, so it is not a corpus "
        "ceiling",
    )
    for pop_name, suffix, pred in (
        ("full corpus", "", lambda r: True),
        ("l2-pass", "_l2", lambda r: r["l2_status"] == "pass"),
    ):
        pop = [r for r in files_rows if pred(r)]
        hits = sum(
            1
            for r in pop
            if any(
                r.get(f"{scope}_patches_{lab}", 0) > 0
                for scope in ("poolonly", "composite")
                for lab in LABELS
            )
        )
        add_claim(
            f"SRF-05_upper_bound_allscopes_presence{suffix}",
            "SRF-05",
            "distinct files with >= 1 classified strip loop on either scope "
            "(the torus upper-bound population: any classified loop could be a "
            "torus band)",
            pop_name,
            len(pop),
            hits,
            "fact",
            "row-derived union over the seven classified classes",
        )

    # Carrier layout families (BR4 note section 2.1): 0x42 carries no
    # normal (facets.NORMAL_MARKERS_ALL), 0x4a does; both offsets are
    # measured corpus-wide, never assumed.
    families = (
        (
            "records_42",
            "0x42",
            "0x42 carries NO normal (facets.NORMAL_MARKERS_ALL = "
            "0x49/0x4a/0x4b/0x4c/0x4e): ty counts at +0x08 (8d)",
        ),
        (
            "records_4a",
            "0x4a",
            "0x4a is normal-bearing: 12-B f32le normal at +0x08..+0x13 (8d..19d), "
            "ty counts at +0x14 (20d)",
        ),
    )
    for prefix, scope_name in (
        ("poolonly", "pool-only stores"),
        ("composite", "composite identity-decoded stores"),
    ):
        for key, marker, note in families:
            n = sum(int(r[f"{prefix}_{key}"]) for r in files_rows if r.get(f"{prefix}_{key}") is not None)
            add_claim(
                f"{prefix}_strip_{key}_volume",
                "carrier layout",
                f"accepted strip records with marker {marker} ({scope_name})",
                "located stores",
                n,
                n,
                "volume anchor",
                note,
            )
    n5 = sum(
        int(r[f"{prefix}_records_5byte"])
        for prefix in ("poolonly", "composite")
        for r in files_rows
        if r.get(f"{prefix}_records_5byte") is not None
    )
    add_claim(
        "strip_records_5byte_volume",
        "carrier layout",
        "accepted strip records in the 5-byte header form (the byte at "
        "+0x03 (3d) is not 0xff)",
        "located stores",
        n5,
        n5,
        "volume anchor",
        "the 5-byte form shifts n to +0x05 (5d) and the ty counts to "
        "+0x09 (9d) on 0x42 (+0x15 (21d) on the normal-bearing markers)",
    )

    # Composite loop accounting: the excluded loops sit above every
    # composite bound (they are loops the recognizer never saw).
    comp_files = [r for r in files_rows if r.get("store_decoded") == "composite-decoded"]
    skip_total = sum(int(r["composite_loops_skipref"]) for r in comp_files)
    oob_total = sum(int(r["composite_loops_oob"]) for r in comp_files)
    skip_files = sum(1 for r in comp_files if int(r["composite_loops_skipref"]))
    oob_files = sum(1 for r in comp_files if int(r["composite_loops_oob"]))
    classified = sum(scope_counts["composite"].values())
    excluded = skip_total + oob_total
    add_claim(
        "composite_loops_skipref_volume",
        "cap-raiser",
        "composite strip loops excluded for skip references (element slots with "
        "no coordinates)",
        "composite identity-decoded stores",
        skip_total,
        skip_total,
        "volume anchor",
        f"files {skip_files}/{len(comp_files)}; never guessed — above every "
        "composite bound jointly with the oob row",
    )
    add_claim(
        "composite_loops_oob_volume",
        "cap-raiser",
        "composite strip loops excluded for references beyond the element space "
        "(the shipped refs-beyond gate's population)",
        "composite identity-decoded stores",
        oob_total,
        oob_total,
        "volume anchor",
        f"files {oob_files}/{len(comp_files)}; above every composite bound "
        "jointly with the skipref row",
    )
    add_claim(
        "composite_loops_excluded_share",
        "cap-raiser",
        "share of composite strip loops excluded from the classified volume "
        "(skipref + refs beyond the element space)",
        "composite identity-decoded stores",
        classified + excluded,
        excluded,
        "fact",
        f"classified {classified} + skipref {skip_total} + oob {oob_total} = "
        f"{classified + excluded} loops seen; zero-count ty loops are counted nowhere",
    )

    # Scope arithmetic.
    add_claim(
        "scope_stores",
        "scope",
        "manifest parts with a located store body (census-probing law)",
        "full corpus",
        n_manifest,
        agg["located"],
        "fact",
        f"of {n_manifest} manifest parts; pool-only {agg['poolonly']} / "
        f"composite {agg['composite']} / pool-scan-failed {agg['pool_scan_failed']}",
    )
    add_claim(
        "scope_composite_decode",
        "scope",
        "composite stores decoded by the identity table-walk reading "
        "(find_list_node + decode_region)",
        "full corpus",
        agg["composite"],
        agg["composite_decoded"],
        "fact",
        f"undecoded {agg['composite_undecoded']}, errors {agg['decode_errors']}; the "
        "classified composite volumes cover THESE stores only (not the shipped "
        "fallback-only stores)",
    )
    if shipped_by_sha:
        shipped_decoded = (
            agg["composite_decoded"]
            - agg["composite_decoded_shipped_fail"]
            + agg["composite_fallback_only"]
        )
        stages = ", ".join(f"{k} {v}" for k, v in sorted(agg["fallback_stages"].items()))
        add_claim(
            "scope_composite_decode_shipped",
            "scope",
            "composite stores the shipped stage-3d export decodes "
            "(stage15-identity-export-files.csv export_ok=1)",
            "full corpus",
            agg["composite"],
            shipped_decoded,
            "fact",
            f"identity table-walk {agg['composite_decoded']} (of which "
            f"{agg['composite_decoded_shipped_fail']} is a shipped undecoded-variant) + "
            f"shipped-fallback-only {agg['composite_fallback_only']} ({stages})",
        )
        add_claim(
            "scope_composite_decode_gap",
            "scope",
            "identity-undecoded composite stores the shipped fallbacks still do not export",
            "full corpus",
            agg["composite_undecoded"],
            agg["composite_undecoded_both"],
            "fact",
            f"{agg['composite_fallback_only']} of the {agg['composite_undecoded']} "
            "identity-undecoded stores ARE exported by the shipped fallbacks; "
            f"{agg['composite_undecoded_both']} stay undecoded by both",
        )

    # Selftest claim (the synthetic fixtures run; the count is derived).
    n_checks = quadrics.selftest_count()
    failures = quadrics.selftest()
    add_claim(
        "BR4_selftest",
        "detector honesty",
        "synthetic fixtures + negatives (cylinder/cone/sphere/torus escapes/"
        "ellipse/plane and the cone-sphere span edge) pass",
        "selftest",
        n_checks,
        n_checks - len(failures),
        "established",
        "; ".join(failures) if failures else "0 failures",
    )

    files_path = Path(args.files_out) if args.files_out else None
    if files_path:
        counter_fields = [
            f"{scope}_{key}" for scope in ("poolonly", "composite") for key in new_counters()
        ]
        files_path.parent.mkdir(parents=True, exist_ok=True)
        with files_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FILE_FIELDS + counter_fields)
            w.writeheader()
            w.writerows(files_rows)
        print(f"Wrote {files_path} ({len(files_rows)} rows)")

    # A subset run's rows must never read as full-corpus measurements:
    # the per-part rows cover the selected parts while the census
    # tie-out rows are computed from the whole census CSV, so the marker
    # states both.
    if args.include_sha16:
        marker = (
            f" SUBSET RUN (--include-sha16 {args.include_sha16}): {len(parts)}/"
            f"{n_manifest} manifest parts; per-part rows cover the subset, the "
            "census tie-out rows stay full-corpus"
        )
        for row in claims:
            row["note"] = f"{row['note']}{marker}"

    claims_path = out_dir / "br4-quadrics-claims.csv"
    with claims_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        w.writerows(claims)

    print(f"Wrote {claims_path} ({len(claims)} rows)")
    print("AGG:", agg)
    print("patch counts pool-only:", scope_counts["poolonly"])
    print("patch counts composite-identity:", scope_counts["composite"])
    print("selftest:", f"{n_checks - len(failures)}/{n_checks} cases pass")


if __name__ == "__main__":
    main()
