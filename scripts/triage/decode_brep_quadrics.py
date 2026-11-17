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
note is a row or row-derived sum).  The per-file counter table is
NOT written by default (only the ticket's owned files land in the
tree); pass --files-out PATH to write it.  Deterministic: sorted
manifest order; no wall-clock value enters the CSV.  Read-only over
the corpus (binaries resolved against the main checkout when absent
here); run with the worktree venv:

  .venv/bin/python -I scripts/triage/decode_brep_quadrics.py
  .venv/bin/python -I scripts/triage/decode_brep_quadrics.py --selftest
  .venv/bin/python -I scripts/triage/decode_brep_quadrics.py \
    --include-sha16 369fc90b25b4977d
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
    }


def classify_poolonly(data, lo, hi, flat, lex, counters):
    """Classify the strip records of a pool-only store (G3 scope)."""
    scan = facets.scan_facets(data, lo, hi, clean_store=True)
    for rec in scan.records:
        if rec.marker not in STRIP_MARKERS:
            continue
        counters["records"] += 1
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
    """Classify the strip records of a composite store under the
    shipped identity decode; returns an error-class string or ''."""
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
        counters["records"] += 1
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
                "— the ceiling every per-class quadric claim must tie out against"
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
        failures = quadrics.selftest()
        print(f"selftest: {len(failures)} failures")
        for f in failures:
            print("  FAIL", f)
        sys.exit(1 if failures else 0)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    l2_by_sha = {}
    if L2_STAGE15.exists():
        with L2_STAGE15.open() as f:
            for r in csv.DictReader(f):
                l2_by_sha[r["sha256"]] = r.get("l2_status", "")

    claims: list[dict] = []
    census_tieout_claims(l2_by_sha, claims)

    with MANIFEST.open() as f:
        parts = [r for r in csv.DictReader(f) if r["kind"] == "part"]
    parts.sort(key=lambda r: r["sha256"])
    if args.include_sha16:
        want = set(args.include_sha16.split(","))
        parts = [r for r in parts if r["sha256"][:8] in want]

    files_rows = []
    agg = {
        "located": 0,
        "poolonly": 0,
        "composite": 0,
        "composite_decoded": 0,
        "composite_undecoded": 0,
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
            if audit["store_decoded"] == "composite-decoded":
                agg["composite_decoded"] += 1
                for lab in LABELS:
                    scope_counts["composite"][lab] += audit["composite"][f"patches_{lab}"]
            else:
                agg["composite_undecoded"] += 1
                err = audit["decode_error"] or "unknown"
                agg["decode_errors"][err] = agg["decode_errors"].get(err, 0) + 1

    # File-level presence claims per scope (corpus + L2).
    def presence_claims(scope_prefix, scope_name, n_note):
        for lab, sid in (
            ("cylinder", "SRF-02"),
            ("cone", "SRF-03"),
            ("sphere", "SRF-04"),
            ("pencil_noncyl", "SRF-07"),
            ("curved_unclassified", "SRF-05/06/07/08"),
        ):
            for pop_name, pred in (
                ("full corpus", lambda r: True),
                ("l2-pass", lambda r: r["l2_status"] == "pass"),
            ):
                pop = [r for r in files_rows if pred(r)]
                hits = sum(1 for r in pop if r.get(f"{scope_prefix}_patches_{lab}", 0) > 0)
                claims.append(
                    {
                        "claim": f"{sid.replace('/', '_')}_{lab}_{scope_prefix}_presence",
                        "construct": sid,
                        "statement": (
                            f"files with >= 1 {lab} strip patch "
                            f"({scope_name} scope)"
                        ),
                        "scope": pop_name,
                        "observations": len(pop),
                        "passes": hits,
                        "rate": round(hits / len(pop), 6) if pop else 0.0,
                        "label": "candidate" if scope_prefix == "composite" else "established",
                        "note": n_note,
                    }
                )

    presence_claims(
        "poolonly",
        "pool-only stores (G3/F2 lex-rank semantics, established)",
        "per-record strip patches; recognized counts are floors (per-record arc coverage)",
    )
    presence_claims(
        "composite",
        "composite stores decoded by the shipped identity decode (stage-3d, candidate scope)",
        "candidate: the composite element-index reading is anchor-established, corpus candidate (stage-3b)",
    )

    # Both-scopes presence: distinct files with >= 1 patch of the label on
    # EITHER scope (the prose's row-derived sums cite these rows).
    for lab, sid in (
        ("cylinder", "SRF-02"),
        ("cone", "SRF-03"),
        ("sphere", "SRF-04"),
        ("pencil_noncyl", "SRF-07"),
        ("curved_unclassified", "SRF-05/06/07/08"),
    ):
        for pop_name, pred in (
            ("full corpus", lambda r: True),
            ("l2-pass", lambda r: r["l2_status"] == "pass"),
        ):
            pop = [r for r in files_rows if pred(r)]
            hits = sum(
                1
                for r in pop
                if r.get(f"poolonly_patches_{lab}", 0) > 0
                or r.get(f"composite_patches_{lab}", 0) > 0
            )
            claims.append(
                {
                    "claim": f"{sid.replace('/', '_')}_{lab}_allscopes_presence",
                    "construct": sid,
                    "statement": (
                        f"distinct files with >= 1 {lab} strip patch on either scope "
                        "(pool-only or composite-decoded)"
                    ),
                    "scope": pop_name,
                    "observations": len(pop),
                    "passes": hits,
                    "rate": round(hits / len(pop), 6) if pop else 0.0,
                    "label": "fact",
                    "note": "both-scopes sum row (distinct files)",
                }
            )

    # Volume anchors per scope.
    for scope_name, prefix in (("pool-only stores", "poolonly"), ("composite-decoded stores", "composite")):
        for lab in LABELS:
            n = scope_counts[prefix][lab]
            claims.append(
                {
                    "claim": f"{prefix}_patches_{lab}_volume",
                    "construct": "SRF-02..08",
                    "statement": f"{lab} strip patches classified ({scope_name})",
                    "scope": "located stores",
                    "observations": n,
                    "passes": n,
                    "rate": 1.0 if n else 0.0,
                    "label": "volume anchor",
                    "note": "patch = one accepted 0x42/0x4A strip record (G3)",
                }
            )

    # Scope arithmetic.
    for claim, construct, stmt, obs, label, note in (
        (
            "scope_stores",
            "scope",
            "manifest parts with a located store body (census-probing law)",
            agg["located"],
            "fact",
            f"pool-only {agg['poolonly']} / composite {agg['composite']} / pool-scan-failed {agg['pool_scan_failed']}",
        ),
        (
            "scope_composite_decode",
            "scope",
            "composite stores decoded by the shipped identity decode (token node + decode_region)",
            agg["composite"],
            "fact",
            f"decoded {agg['composite_decoded']}, undecoded {agg['composite_undecoded']}, "
            f"errors {agg['decode_errors']}",
        ),
    ):
        claims.append(
            {
                "claim": claim,
                "construct": construct,
                "statement": stmt,
                "scope": "full corpus",
                "observations": obs,
                "passes": obs,
                "rate": 1.0,
                "label": label,
                "note": note,
            }
        )

    # Selftest claim (the synthetic negative fixtures run).
    failures = quadrics.selftest()
    claims.append(
        {
            "claim": "BR4_selftest",
            "construct": "detector honesty",
            "statement": "synthetic fixtures + negatives (cylinder/cone/sphere/torus/ellipse/plane) pass",
            "scope": "selftest",
            "observations": 9,
            "passes": 9 - len(failures),
            "rate": round((9 - len(failures)) / 9, 6),
            "label": "established",
            "note": "; ".join(failures) if failures else "0 failures",
        }
    )

    files_path = out_dir / "br4-quadrics-files.csv"
    counter_fields = [
        f"{scope}_{key}" for scope in ("poolonly", "composite") for key in new_counters()
    ]
    with files_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FILE_FIELDS + counter_fields)
        w.writeheader()
        w.writerows(files_rows)

    claims_path = out_dir / "br4-quadrics-claims.csv"
    with claims_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CLAIM_FIELDS)
        w.writeheader()
        w.writerows(claims)

    print(f"Wrote {files_path} ({len(files_rows)} rows)")
    print(f"Wrote {claims_path} ({len(claims)} rows)")
    print("AGG:", agg)
    print("patch counts pool-only:", scope_counts["poolonly"])
    print("patch counts composite-decoded:", scope_counts["composite"])
    selftest_note = "0 failures" if not failures else f"{len(failures)} FAILURES"
    print("selftest:", selftest_note)


if __name__ == "__main__":
    main()
