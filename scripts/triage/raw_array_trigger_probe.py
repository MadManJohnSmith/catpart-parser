#!/usr/bin/env python3
"""Store-level probe of the stage-6 raw-array trigger (G6 stage 6, #34).

Pre-declaration measurement for the stage-4a raw-array law's exporter
integration: over every corpus part's composite store, it records

- whether the EXPORTER's table walk (composite.decode_region — bounded
  by the declared region, aborting on non-finite coordinates) fails,
  and with which signature;
- whether the store is in the walk-mismatch family (the census probe's
  semantics, composite._walk_mismatch: all slots walked bounded only by
  the payload, no coordinate aborts — a walk-exact store with junk
  coordinates is NOT the family);
- the committed raw-array criteria at the trail-escape-pinned start
  (composite.decode_raw_array: unique escape over the 4-aligned
  candidates 32..64, nice/x-ascending >= 0.98, verbatim pool
  absorption) — the projected raw-export set.

This is a STORE-level scan through the committed census locator
(classify_residue_family.locate_payload).  It is NOT the seam A/B:
part-level outcomes (first-export-wins, the stage-3a recovery reach)
are measured by ab_identity_export.py AFTER the declared-delta commit
(dispatch-recipes.md external-changeset gate rule); the locator-reach
delta between the two is part of the declared range, not an assumption.

Read-only over the corpus (symlink).  Run with the worktree venv:
  .venv/bin/python -I scripts/triage/raw_array_trigger_probe.py
Out:  docs/evidence/data/stage6-raw-trigger-probe.csv
"""

import csv
import mmap
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

from catpart.geometry import composite, pool, store  # noqa: E402
from classify_residue_family import locate_payload  # noqa: E402

FIELDS = [
    "sha256",
    "split",
    "form",
    "size_bytes",
    "payload_bytes",
    "elem_decl",
    "walk_raise",
    "family_signature",
    "walk_delta_words",
    "escape_candidates",
    "raw_start",
    "raw_nice_rate",
    "raw_x_asc_rate",
    "raw_trail_bytes",
    "pool_size",
    "raw_pool_absorbed",
    "verdict",
    "raw_error",
]


def audit_row(mm, rel):
    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    row["size_bytes"] = mm.size()
    ln = locate_payload(mm)
    if ln is None:
        row["verdict"] = "no-list-node"
        return row
    payload, c1, _c2 = ln
    row["payload_bytes"] = len(payload)
    row["elem_decl"] = c1
    row["form"] = "big" if len(payload) > 4096 else "small"
    try:
        composite.decode_region(payload, c1)
    except composite.ExportError as exc:
        row["walk_raise"] = _raise_kind(exc.detail)
    else:
        row["verdict"] = "walk-ok"
        return row  # a store the table walk handles: never routed
    profile = composite._walk_mismatch(payload, c1)
    if profile is None:
        # walk-exact with junk coordinates: not the family, re-raised
        row["verdict"] = "not-family"
        return row
    if "layout_error" in profile:
        row["family_signature"] = "layout-raise"
    else:
        row["family_signature"] = "walk-mismatch"
        row["walk_delta_words"] = profile["delta_words"]
    # the pool, the way the exporter gathers it (all groups concatenated)
    poolv = _store_pool(mm)
    row["pool_size"] = len(set(poolv))
    try:
        _points, info = composite.decode_raw_array(payload, c1, poolv)
    except composite.ExportError as exc:
        row["raw_error"] = exc.detail
        row["verdict"] = _raw_verdict(exc.detail)
        return row
    row["verdict"] = "raw-export"
    row["escape_candidates"] = 1
    row["raw_start"] = info["raw_start"]
    row["raw_nice_rate"] = info["raw_nice_rate"]
    row["raw_x_asc_rate"] = info["raw_x_asc_rate"]
    row["raw_trail_bytes"] = info["raw_trail_bytes"]
    row["raw_pool_absorbed"] = True
    return row


def _raise_kind(detail: str) -> str:
    """The decode_region raise's signature class, from the detail text."""
    if "non-finite" in detail:
        return "non-finite"
    if "exceeds the declared region" in detail:
        return "walk-overrun"
    if "consumed" in detail:
        return "walk-short"
    if "word budget" in detail:
        return "write-count-budget"
    return "layout-raise"


def _raw_verdict(detail: str) -> str:
    if "start not pinned" in detail:
        return "start-unpinned"
    if "weak fit" in detail:
        return "weak-fit"
    if "not absorbed" in detail:
        return "pool-unabsorbed"
    return "raw-gap"


def _store_pool(mm):
    """The composite store's pool vertices (all groups concatenated —
    the exporter's poolv), or [] when no composite store decodes."""
    d8_outer = int.from_bytes(mm[8:12], "big") if mm.size() >= 12 else 0
    blocks = store.valid_blocks(mm)
    for blk in [b for b, nm in blocks if nm == "CATStdCont"]:
        span = store.locate_store(mm, blk, blocks, d8_outer)
        if span is None:
            continue
        groups, kinds = pool.scan_pool_groups(mm, span.body_lo, span.body_hi)
        if not pool.has_composite_space(kinds):
            continue
        return [v for g in groups for v in g.vertices]
    return []


def main():
    rows = []
    for r in csv.DictReader(MANIFEST.open()):
        if r["split"] not in ("dev", "held-out") or r["kind"] != "part":
            continue
        path = ROOT / r["local_path"]
        with path.open("rb") as fh:
            mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                rows.append(audit_row(mm, r))
            except Exception as exc:  # noqa: BLE001 - recorded per part
                row = {k: "" for k in FIELDS}
                row["sha256"] = r["sha256"]
                row["split"] = r["split"]
                row["verdict"] = f"audit-error: {type(exc).__name__}: {exc}"
                rows.append(row)
            finally:
                mm.close()
    out_path = OUT_DIR / "stage6-raw-trigger-probe.csv"
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    summarize(rows)
    return 0


def summarize(rows):
    """The declaration figures: trigger population, verdicts, splits."""
    from collections import Counter

    print(f"wrote stage6-raw-trigger-probe.csv ({len(rows)} rows)")
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    trig = [r for r in rows if r["family_signature"]]
    print("trigger population:", len(trig))
    print(
        "  signatures:",
        dict(Counter(r["family_signature"] for r in trig)),
    )
    print(
        "  walk_raise kinds:",
        dict(Counter(r["walk_raise"] for r in trig)),
    )
    print("  verdicts:", dict(Counter(r["verdict"] for r in trig)))
    print(
        "  forms:",
        dict(Counter(r["form"] for r in trig)),
    )
    print(
        "  splits:",
        dict(Counter(r["split"] for r in trig)),
    )
    exports = [r for r in trig if r["verdict"] == "raw-export"]
    print("raw-export stores:", len(exports))


if __name__ == "__main__":
    sys.exit(main())
