#!/usr/bin/env python3
"""Triage CLI (Phase 3 P3.5, approved design B): deterministic router +
jev residue arbiter over an inventory CSV.

Reads one or more inventory CSVs — the ``open-rate-files.csv`` shape
(``sha16,path,split,report kind,report class,open kind,triangles,points,
segments``, auto-detected by the ``sha16`` header) and/or the
``bench-submarine`` ``m1_files.csv`` shape (``path,size_bytes,l2_status,
error_class,failed_check,open_class,...,warnings,...``, detected by
``l2_status``) — routes every row through ``router.route``, and sends
only residue to ``jev-1.13-free`` (sampled when it exceeds ``--sample``).

Every output row carries bucket/escalate/risk plus the decision source:
``deterministic``, ``jev-1.13-free``, or ``needs_review`` with the cause
(``no_key`` / ``arbiter_error`` / ``not_sampled``). Only the compact JSON
feature record travels to the API; CATPart contents are never read here.

Key handling: ``OPENCODE_API_KEY`` env var, else ``--key-file`` pointing
at an EXTERNAL file (e.g. /tmp/oc_key.txt). Keys are never hardcoded,
committed, or read from inside the repo. Without a key, or when the
arbiter cannot be reached, the run still writes its output and exits 0 —
residue simply lands on ``needs_review``.

Usage:
  python3 scripts/triage/run_triage.py --input open-rate-files.csv \
      --input m1_files.csv --output triaged.csv \
      [--key-file /tmp/oc_key.txt] [--sample 200] [--seed 42] [--no-arbiter]
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jev_arbiter  # noqa: E402
import router  # noqa: E402

NEEDS_REVIEW = "needs_review"


def record_from_open_rate(row: dict) -> dict:
    """open-rate-files.csv row -> normalized record. The ``points`` column
    feeds both point_count and display_points: a DISPLAY row has no mesh
    vertices, so its point count is display content (S8 dataset build)."""
    return router.make_record(
        path=row["path"],
        source="open-rate",
        error_class=row["report class"].strip(),
        report_kind=row["report kind"].strip(),
        open_kind=row["open kind"].strip(),
        triangle_count=int(row["triangles"] or 0),
        point_count=int(row["points"] or 0),
        display_points=int(row["points"] or 0),
        display_segments=int(row["segments"] or 0),
    )


def record_from_m1(row: dict) -> dict:
    """m1_files.csv row -> normalized record; warnings split on ';'."""
    return router.make_record(
        path=row["path"],
        source="submarine-m1",
        error_class=row["error_class"].strip(),
        failed_check=row["failed_check"].strip(),
        l2_status=row["l2_status"].strip(),
        open_kind=row["open_class"].strip(),
        warnings=[w for w in row["warnings"].split(";") if w],
        triangle_count=int(row["triangle_count"] or 0),
        point_count=int(row["vertex_count"] or 0),
        display_points=int(row["display_points"] or 0),
        display_segments=int(row["display_segments"] or 0),
        size_bytes=int(row["size_bytes"] or 0) or None,
    )


def detect_shape(header: list[str]) -> str:
    if "sha16" in header:
        return "open-rate"
    if "l2_status" in header:
        return "submarine-m1"
    raise SystemExit(f"unrecognized inventory header: {header}")


def read_records(path: str) -> list[dict]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        shape = detect_shape(reader.fieldnames or [])
        rows = list(reader)
    make = record_from_open_rate if shape == "open-rate" else record_from_m1
    return [make(row) for row in rows]


def stratified_sample(records: list[dict], key_fn, n: int, seed: int) -> list[dict]:
    """Proportional allocation across the strata of ``key_fn`` (largest
    remainders first), seeded shuffle-within-stratum; n > population
    returns everything. Keeps the residue mix representative."""
    if n <= 0 or len(records) <= n:
        return list(records)
    strata: dict[tuple, list] = {}
    for rec in records:
        strata.setdefault(key_fn(rec), []).append(rec)
    rng = random.Random(seed)
    shares = {k: len(v) * n / len(records) for k, v in strata.items()}
    picks: list = []
    remainders = sorted(strata, key=lambda k: -(shares[k] % 1))
    for k in strata:
        take = int(shares[k])
        pool = strata[k]
        rng.shuffle(pool)
        picks.extend(pool[:take])
    for k in remainders[: n - len(picks)]:
        picks.append(strata[k][0])
    return picks[:n]


def output_row(rec: dict, bucket: str, escalate: bool, risk: int,
               source: str, confidence: float = "",
               attempts: int = "", latency_ms: int = "", cost_usd: float = "") -> dict:
    return {
        "path": rec["path"],
        "source": rec["source"],
        "resolved_class": router.resolve_class(rec),
        "residue_reason": router.residue_reason(rec),
        "route_bucket": bucket,
        "escalate": escalate,
        "risk": risk,
        "confidence": confidence,
        "decision_source": source,
        "attempts": attempts,
        "latency_ms": latency_ms,
        "arbiter_cost_usd": cost_usd,
    }


def run(inputs: list[str], output_path: str, key_file: str | None,
       sample_n: int, seed: int, use_arbiter: bool) -> int:
    records: list[dict] = []
    for path in inputs:
        records.extend(read_records(path))

    rows: list[dict] = []
    residue: list[dict] = []
    for rec in records:
        r = router.route(rec)
        if r is None:
            residue.append(rec)
        else:
            rows.append(output_row(rec, r.bucket, r.escalate, r.risk, "deterministic"))

    key = jev_arbiter.resolve_key(key_file) if use_arbiter else None
    if key is None and use_arbiter:
        print("triage: no OPENCODE_API_KEY / readable --key-file -> "
              f"{len(residue)} residue rows fall back to needs_review", flush=True)
    targets = stratified_sample(
        residue, lambda r: (r["source"], router.residue_reason(r)), sample_n, seed) \
        if (key and sample_n) else (residue if key else [])
    unsampled = len(residue) - len(targets)
    target_ids = {id(r) for r in targets}

    arbiter_rows = 0
    if key and targets:
        print(f"triage: arbitrating {len(targets)} residue records "
              f"(of {len(residue)}) with {jev_arbiter.MODEL}", flush=True)

        def progress(done: int, total: int) -> None:
            if done % 25 == 0 or done == total:
                print(f"  arbiter {done}/{total}", flush=True)

        for rec, decision in zip(targets, jev_arbiter.decide_all(key, targets, progress)):
            if decision.error:
                rows.append(output_row(rec, NEEDS_REVIEW, "", "", "arbiter_error",
                                       attempts=decision.attempts,
                                       latency_ms=decision.latency_ms))
            else:
                arbiter_rows += 1
                rows.append(output_row(
                    rec, decision.bucket, decision.escalate, decision.risk,
                    jev_arbiter.MODEL, confidence=f"{decision.confidence:.3f}",
                    attempts=decision.attempts, latency_ms=decision.latency_ms,
                    cost_usd=decision.list_cost_usd))
    for rec in residue:
        if id(rec) in target_ids:
            continue
        rows.append(output_row(rec, NEEDS_REVIEW, "", "",
                               "no_key" if key is None else "not_sampled"))

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                                ["path", "source", "resolved_class", "residue_reason",
                                 "route_bucket", "escalate", "risk", "confidence",
                                 "decision_source", "attempts", "latency_ms",
                                 "arbiter_cost_usd"])
        writer.writeheader()
        writer.writerows(rows)

    total_cost = sum(float(r["arbiter_cost_usd"] or 0.0) for r in rows)
    print(f"triage: {len(records)} records -> {output_path}")
    print(f"  deterministic: {len(records) - len(residue)}  residue: {len(residue)} "
          f"({dict(Counter(router.residue_reason(r) for r in residue))})")
    print(f"  buckets: {dict(Counter(r['route_bucket'] for r in rows))}")
    print(f"  arbiter routed: {arbiter_rows}  errors: "
          f"{sum(1 for r in rows if r['decision_source'] == 'arbiter_error')}  "
          f"unsampled: {max(0, unsampled)}  list_cost total: ${total_cost:.6f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", action="append", required=True,
                    help="inventory CSV (repeatable; shape auto-detected)")
    ap.add_argument("--output", required=True, help="output triage CSV")
    ap.add_argument("--key-file", default=None,
                    help="external API key file (e.g. /tmp/oc_key.txt; never inside the repo)")
    ap.add_argument("--sample", type=int, default=0,
                    help="arbitrate at most N residue records (0 = all)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-arbiter", action="store_true",
                    help="router only; residue becomes needs_review")
    args = ap.parse_args(argv)
    return run(args.input, args.output, args.key_file, args.sample, args.seed,
               not args.no_arbiter)


if __name__ == "__main__":
    raise SystemExit(main())
