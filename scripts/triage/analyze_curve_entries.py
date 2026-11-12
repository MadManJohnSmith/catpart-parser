#!/usr/bin/env python3
"""Corpus-wide analysis of the committed U4 curve-entry run (stage 4a-residue).

Pure-CSV analysis: reads the two COMMITTED measurements and touches no
corpus file and no src/ code -

  docs/evidence/data/curve-entries-files.csv   (decode_curve_entries.py,
                                                 stage-4a corpus run)
  docs/evidence/data/identity-export-files.csv (ab_identity_export.py,
                                                 stage-3d export census)

and writes

  docs/evidence/data/curve-entries-analysis-stores.csv   one row per
      composite store with a locatable list node (949 rows)
  docs/evidence/data/curve-entries-analysis-summary.csv  section,key,value

Definitions (all derived from the two input CSVs, no re-measurement):

- ``skips_referenced``   = ``skips_dup_prev`` of the decoder CSV: the
  decoder pins EVERY facet-loop-referenced skip slot with the dup law
  (kind ``dup_prev``), so the count equals the number of skip slots
  that any facet loop references.  The unreferenced slots are the
  decoder's ``mid`` / ``unpinned_dup`` kinds - classified BY the absence
  of a reference, so they can never touch a loop or a triangle.
- ``ce_loops_exporter``  = ``loops_curve_entry`` of the export census:
  every 0x42/0x4a/0x4c loop the shipped exporter drops because it
  references a skip slot (normal-carrying or not).
- ``tested_skipref_loops`` = the decoder's battery counters
  ``loops_skipref_coplanar + loops_skipref_nonplanar``: only
  NORMAL-carrying skip-referencing loops are coplanarity-testable.  The
  battery counts them on records the export seam does not enumerate
  identically (one store: tested > exporter count), so coverage is
  reported as ``min(tested, ce_loops)`` per store.
- ``baseline`` = the decoder's non-skip loops (``loops_coplanar`` /
  ``loops_nonplanar``) - the control rate of the same battery.
- ``export_status``: ``exported`` (export census ``export_ok = 1``) /
  ``fail-closed``.  Rows whose census class is ``malformed-store-header``
  are flagged ``stale-3a``: the 78-file validation re-run
  (probe_curve_entry_twins.py --validate) showed the census disagrees
  with current main on exactly that class.

Deterministic (sorted by sha256; no wall-clock value enters a CSV).
Run:  python3 -I scripts/triage/analyze_curve_entries.py
"""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "docs" / "evidence" / "data"
CURVE = DATA / "curve-entries-files.csv"
EXPORT = DATA / "identity-export-files.csv"
OUT_STORES = DATA / "curve-entries-analysis-stores.csv"
OUT_SUMMARY = DATA / "curve-entries-analysis-summary.csv"

STORE_FIELDS = [
    "sha256", "split", "node_form", "walk_end_ok", "export_status",
    "status_basis", "error_class", "l2_status", "failed_check",
    "skip_slots", "skips_referenced", "ce_loops_exporter",
    "tested_skipref_loops", "skipref_coplanar", "skipref_nonplanar",
    "baseline_coplanar", "baseline_nonplanar", "untested_ce_loops",
    "coverage_class", "dup_law_class", "baseline_clean",
    "e0_candidate", "e0_battery_supported",
]

# Stores whose battery is dominated by a KNOWN decode defect (named in the
# stage-4b not-manifold audit / the 3d export census): 13bb5c0c = the u24be
# width gap (element_count > 65,535, records tile exactly at u24be, 3,070 of
# the corpus's 3,337 skip-referencing nonplanar loops); cf7394ee = empty-mesh
# store with 1,990 parsed records of which 116/131 skip-referencing loops
# fail.  Reported with and without them.
DEFECT_PREFIXES = ("13bb5c0c", "cf7394ee")


def to_int(x):
    return int(x) if x not in ("", None) else 0


def quart(vals):
    v = sorted(vals)
    n = len(v)
    if not n:
        return "n=0"
    return (f"n={n} min={v[0]} q1={v[n // 4]} med={v[n // 2]} "
            f"q3={v[3 * n // 4]} max={v[-1]} sum={sum(v)}")


def build_rows():
    cur = {r["sha256"]: r for r in csv.DictReader(CURVE.open())}
    exp = {r["sha256"]: r for r in csv.DictReader(EXPORT.open())}
    rows = []
    for k in sorted(cur):
        c = cur[k]
        if not c["node_form"]:
            continue
        e = exp[k]
        ok = e["export_ok"] == "1"
        tested_a = to_int(c["loops_skipref_coplanar"])
        tested_b = to_int(c["loops_skipref_nonplanar"])
        tested = tested_a + tested_b
        ce = to_int(e["loops_curve_entry"]) if ok else None
        r = {f: "" for f in STORE_FIELDS}
        r.update(
            sha256=k, split=c["split"], node_form=c["node_form"],
            walk_end_ok=c["walk_end_ok"],
            export_status="exported" if ok else "fail-closed",
            status_basis=("stale-3a" if e["error_class"]
                          == "malformed-store-header" else "export-census"),
            error_class=e["error_class"], l2_status=e["l2_status"],
            failed_check=e["failed_check"], skip_slots=to_int(c["skip_slots"]),
            skips_referenced=to_int(c["skips_dup_prev"]),
            tested_skipref_loops=tested, skipref_coplanar=tested_a,
            skipref_nonplanar=tested_b, baseline_coplanar=to_int(c["loops_coplanar"]),
            baseline_nonplanar=to_int(c["loops_nonplanar"]),
        )
        r["baseline_clean"] = r["baseline_nonplanar"] == 0
        if tested == 0:
            r["dup_law_class"] = "no-tested-loops"
        elif tested_b == 0:
            r["dup_law_class"] = "all-coplanar"
        elif tested_a == 0:
            r["dup_law_class"] = "all-nonplanar"
        else:
            r["dup_law_class"] = "mixed"
        if ok:
            r["ce_loops_exporter"] = ce
            if ce == 0:
                r["coverage_class"] = "no-ce-loops"
                r["untested_ce_loops"] = 0
            else:
                t = min(tested, ce)
                r["untested_ce_loops"] = ce - t
                r["coverage_class"] = (
                    "full" if t == ce else "partial" if t else "none")
            empty = e["failed_check"] == "empty-mesh"
            r["e0_candidate"] = empty and (ce or 0) > 0
            r["e0_battery_supported"] = (
                r["e0_candidate"] and r["coverage_class"] == "full"
                and tested_b == 0
            )
        else:
            r["coverage_class"] = "n/a"
            r["e0_candidate"] = False
            r["e0_battery_supported"] = False
        rows.append(r)
    return rows


def summarize(rows):
    out = []

    def put(section, key, value):
        out.append({"section": section, "key": key, "value": value})

    put("population", "composite_stores_with_list_node", len(rows))
    for form in ("small", "big"):
        put("population", f"{form}_stores",
            sum(1 for r in rows if r["node_form"] == form))
    put("population", "split", dict(sorted(Counter(r["split"] for r in rows).items())))
    exported = [r for r in rows if r["export_status"] == "exported"]
    closed = [r for r in rows if r["export_status"] == "fail-closed"]
    put("population", "exported", len(exported))
    put("population", "fail_closed", len(closed))
    put("population", "fail_closed_stale_3a",
        sum(1 for r in closed if r["status_basis"] == "stale-3a"))

    # Distribution of curve-entry-referencing loops
    for status, grp in (("exported", exported), ("fail-closed", closed)):
        for form in ("small", "big", "all"):
            g = [r for r in grp if form == "all" or r["node_form"] == form]
            key = f"{status}.{form}"
            put("skip_slots", key + ".stores", len(g))
            put("skip_slots", key + ".stores_with_skips",
                sum(1 for r in g if r["skip_slots"] > 0))
            put("skip_slots", key + ".skip_slots", quart([r["skip_slots"] for r in g]))
            put("skip_slots", key + ".skips_loop_referenced",
                quart([r["skips_referenced"] for r in g]))
            put("tested_skipref", key + ".stores_with_tested_loops",
                sum(1 for r in g if r["tested_skipref_loops"] > 0))
            put("tested_skipref", key + ".loops",
                quart([r["tested_skipref_loops"] for r in g]))
            if status == "exported":
                put("ce_loops", key + ".stores_with_ce_loops",
                    sum(1 for r in g if r["ce_loops_exporter"] > 0))
                put("ce_loops", key + ".loops_per_store",
                    quart([r["ce_loops_exporter"] for r in g]))

    # Coverage of the exporter's dropped loops by the battery
    cov = Counter(r["coverage_class"] for r in exported)
    for k, v in sorted(cov.items()):
        put("coverage", f"exported.stores.{k}", v)
    ce_total = sum(r["ce_loops_exporter"] for r in exported)
    untested = sum(r["untested_ce_loops"] for r in exported)
    put("coverage", "exported.ce_loops_total", ce_total)
    put("coverage", "exported.ce_loops_battery_tested", ce_total - untested)
    put("coverage", "exported.ce_loops_untested", untested)

    # Dup-law battery rate, several scopes + the control
    def dup(label, g):
        a = sum(r["skipref_coplanar"] for r in g)
        b = sum(r["skipref_nonplanar"] for r in g)
        ca = sum(r["baseline_coplanar"] for r in g)
        cb = sum(r["baseline_nonplanar"] for r in g)
        put("dup_law", label + ".stores", len(g))
        put("dup_law", label + ".skipref_coplanar", a)
        put("dup_law", label + ".skipref_nonplanar", b)
        put("dup_law", label + ".skipref_rate", f"{a / (a + b):.4f}" if a + b else "")
        put("dup_law", label + ".control_coplanar", ca)
        put("dup_law", label + ".control_nonplanar", cb)
        put("dup_law", label + ".control_rate", f"{ca / (ca + cb):.4f}" if ca + cb else "")

    walk = [r for r in rows if r["walk_end_ok"] == "True"]
    dup("walk_exact.exported", [r for r in walk if r["export_status"] == "exported"])
    ex2 = [r for r in exported if not r["sha256"].startswith(DEFECT_PREFIXES)]
    dup("walk_exact.exported_minus_13bb_cf73", [r for r in walk if r in ex2])
    dup("walk_exact.exported_l2_pass_minus", [r for r in ex2 if r["l2_status"] == "pass"])
    dup("walk_exact.exported_baseline_clean_minus",
        [r for r in ex2 if r["baseline_clean"] and r["tested_skipref_loops"] > 0])
    for form in ("small", "big"):
        dup(f"walk_exact.exported_minus.{form}", [r for r in ex2 if r["node_form"] == form])
    dup("walk_exact.exported_l2_fail", [r for r in exported if r["l2_status"] == "fail"])
    dup("walk_exact.fail_closed_NOT_EVIDENCE",
        [r for r in walk if r["export_status"] == "fail-closed"])
    put("dup_law", "exported_minus.store_classes",
        dict(sorted(Counter(r["dup_law_class"] for r in ex2).items())))
    put("dup_law", "exported_minus.stores_mixed_or_nonplanar_baseline_clean",
        sum(1 for r in ex2 if r["dup_law_class"] in ("mixed", "all-nonplanar")
            and r["baseline_clean"]))

    # L2 exposure of the curve-entry rule (exported-set membership)
    ceb = [r for r in exported if r["ce_loops_exporter"] > 0]
    put("l2_exposure", "exported_stores_with_ce_loops", len(ceb))
    for k, v in sorted(Counter(
            f"{r['l2_status']}/{r['failed_check'] or '-'}" for r in ceb).items()):
        put("l2_exposure", "exported_with_ce_loops." + k, v)
    for k, v in sorted(Counter(
            f"{r['l2_status']}/{r['failed_check'] or '-'}" for r in exported
            if r["ce_loops_exporter"] == 0).items()):
        put("l2_exposure", "exported_without_ce_loops." + k, v)
    e0 = [r for r in exported if r["e0_candidate"]]
    put("l2_exposure", "e0_candidates_empty_mesh_with_ce_loops", len(e0))
    put("l2_exposure", "e0_battery_supported",
        sum(1 for r in e0 if r["e0_battery_supported"]))
    put("l2_exposure", "e0_by_coverage",
        dict(sorted(Counter(r["coverage_class"] for r in e0).items())))
    put("l2_exposure", "e0_by_form", dict(sorted(Counter(r["node_form"] for r in e0).items())))
    put("l2_exposure", "e0_by_split", dict(sorted(Counter(r["split"] for r in e0).items())))
    put("l2_exposure", "empty_mesh_without_ce_loops",
        sum(1 for r in exported if r["failed_check"] == "empty-mesh"
            and r["ce_loops_exporter"] == 0))
    put("l2_exposure", "not_manifold_with_ce_loops",
        sum(1 for r in ceb if r["failed_check"] == "not-manifold"))
    put("l2_exposure", "passing_stores_at_risk_if_ce_loops_exported",
        sum(1 for r in ceb if r["l2_status"] == "pass"))
    put("l2_exposure", "passing_at_risk_battery_supported",
        sum(1 for r in ceb if r["l2_status"] == "pass"
            and r["coverage_class"] == "full" and r["skipref_nonplanar"] == 0))
    # fail-closed stores that a later integration could bring into the exported set
    put("l2_exposure", "fail_closed_with_skips",
        sum(1 for r in closed if r["skip_slots"] > 0))
    put("l2_exposure", "fail_closed_with_tested_skipref_loops",
        sum(1 for r in closed if r["tested_skipref_loops"] > 0))

    # twin-family census (decoder-CSV signature: pool, elem, skips, records)
    cur = {r["sha256"]: r for r in csv.DictReader(CURVE.open())}
    sig = defaultdict(list)
    for k, c in cur.items():
        if c["node_form"]:
            sig[(c["pool_size"], c["elem_decl"], c["skip_slots"],
                 c["records_parsed"])].append(k)
    fam = [v for v in sig.values() if len(v) > 1]
    put("twin_families", "signature_families_gt1", len(fam))
    put("twin_families", "stores_in_families", sum(len(v) for v in fam))
    put("twin_families", "families_with_skips_gt0",
        sum(1 for v in fam if to_int(cur[v[0]]["skip_slots"]) > 0))

    # Composite exports the DECODER cannot see (post-3a baseline only): the
    # stage-3a locator recovery (66 former missing-geometry-store parts)
    # exports stores whose body the decoder's strict locator does not reach,
    # so they have no curve-entry measurement (node_form = "" here).  Census
    # columns only; the battery says nothing about them.
    exp_all = {r["sha256"]: r for r in csv.DictReader(EXPORT.open())}
    blind = [k for k, e in exp_all.items()
             if e["export_ok"] == "1" and to_int(e["element_decl"]) > 0
             and not cur[k]["node_form"]]
    put("decoder_blind", "composite_exports_total",
        sum(1 for e in exp_all.values()
            if e["export_ok"] == "1" and to_int(e["element_decl"]) > 0))
    put("decoder_blind", "exports_outside_decoder_population", len(blind))
    put("decoder_blind", "with_dropped_loops",
        sum(1 for k in blind if to_int(exp_all[k]["loops_curve_entry"]) > 0))
    put("decoder_blind", "dropped_loops",
        sum(to_int(exp_all[k]["loops_curve_entry"]) for k in blind))
    put("decoder_blind", "l2_pass",
        sum(1 for k in blind if exp_all[k]["l2_status"] == "pass"))
    put("decoder_blind", "l2_fail",
        sum(1 for k in blind if exp_all[k]["l2_status"] == "fail"))
    put("decoder_blind", "empty_mesh_with_dropped_loops",
        sum(1 for k in blind if exp_all[k]["failed_check"] == "empty-mesh"
            and to_int(exp_all[k]["loops_curve_entry"]) > 0))
    # E0 at census scope (all composite exports; battery unknown for the
    # blind part): exported + empty-mesh + >= 1 dropped loop.
    ce_all = [k for k, e in exp_all.items()
              if e["export_ok"] == "1" and to_int(e["element_decl"]) > 0
              and e["failed_check"] == "empty-mesh"
              and to_int(e["loops_curve_entry"]) > 0]
    put("l2_exposure", "e0_candidates_census_scope", len(ce_all))
    put("l2_exposure", "e0_census_scope_blind",
        sum(1 for k in ce_all if k in blind))
    return out


def main():
    rows = build_rows()
    with OUT_STORES.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=STORE_FIELDS)
        w.writeheader()
        w.writerows(rows)
    summary = summarize(rows)
    with OUT_SUMMARY.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["section", "key", "value"])
        w.writeheader()
        w.writerows(summary)
    print(f"wrote {OUT_STORES} ({len(rows)} rows)")
    print(f"wrote {OUT_SUMMARY} ({len(summary)} rows)")
    for r in summary:
        print(f"{r['section']:15s} {r['key']:62s} {r['value']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
