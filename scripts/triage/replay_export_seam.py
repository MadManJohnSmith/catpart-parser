#!/usr/bin/env python3
"""Read-only replay of the L2 population through the shipped export seam.

One row per manifest ``kind=part`` row (dev + held-out): the part goes
through :func:`catpart.geometry.build_export` — the exact seam the
fitness runner measures — and the row records the outcome, the PLY
digest and the L2-relevant digest, and (on composite exports) the decode
stage the summary names.  The purpose is the no-regression check (#34):
every currently-exporting store must keep its PLY bytes and its
L2-relevant summary state identical unless a named law application
changed them, and the coverage split (clean / composite stages / error
classes) must be reproducible from the committed CSV.

Stage-5 fold-in (2026-11-12, #34): cherry-picked from the stage-3d
reconciliation's alt tree (``d832b86``, note section 5) and adapted —
the alt script hashed the WHOLE summary, which changes whenever any
``info`` key changes (this stage adds ``node_bytes`` and the per-rep
keys to every composite summary), so byte-identity of the decoded state
would be unmeasurable across integrations.  This version hashes the PLY
and the L2-RELEVANT summary fields SEPARATELY (``l2_fields_sha256``:
vertex/triangle counts, bounding box, degenerate count and the mesh
block — exactly what ``catpart.fitness.runner._score_export`` reads).

Read-only over the corpus and the fitness artifacts: nothing is written
outside the ``--out-dir``; no fitness history row is appended.  A
per-store wall-clock guard (``--timeout`` seconds, SIGALRM) bounds
pathological stores; timed-out stores are recorded as ``timeout``.

Deterministic: sorted manifest order; no wall-clock value enters the CSV.

  .venv/bin/python -I scripts/triage/replay_export_seam.py [--out-dir DIR]
"""

import argparse
import csv
import hashlib
import json
import signal
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_DIR = ROOT / "docs" / "evidence" / "data"

sys.path.insert(0, str(ROOT / "src"))

FIELDS = [
    "sha256", "split", "size_bytes", "status", "error_class",
    "error_detail", "vertex_count", "triangle_count",
    "ply_sha256", "l2_fields_sha256", "composite_stage", "node_bytes",
]

DETAIL_CAP = 200

# The L2-relevant summary subset (the fields catpart.fitness.runner
# ._score_export consumes): byte-identity of these is what "the pass
# state did not drift" means.  Kept separate from the PLY digest (the
# two can legitimately diverge: vertex order changes without count
# changes) and from the whole-summary hash (additive info keys change
# it without touching the decoded state).
L2_FIELDS = ("vertex_count", "triangle_count", "bounding_box",
             "degenerate_triangle_count", "mesh")


def _l2_fields_digest(summary: dict) -> str:
    l2_view = {k: summary[k] for k in L2_FIELDS}
    return hashlib.sha256(
        json.dumps(l2_view, sort_keys=True).encode("utf-8")
    ).hexdigest()


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


def replay_part(rel, ply_dir: Path, timeout: int) -> dict:
    """Export one part through the shipped seam; return the CSV row."""
    from catpart.geometry import build_export
    from catpart.geometry.errors import ExportError

    row = {k: "" for k in FIELDS}
    row["sha256"] = rel["sha256"]
    row["split"] = rel["split"]
    path = ROOT / rel["local_path"]
    if not path.exists():
        row["status"] = "missing-file"
        return row
    row["size_bytes"] = path.stat().st_size
    ply_path = ply_dir / f"{rel['sha256'][:16]}.ply"
    try:
        summary = build_export(path, ply_path)
    except ExportError as exc:
        row["status"] = "error"
        row["error_class"] = exc.error_class
        row["error_detail"] = exc.detail[:DETAIL_CAP]
        return row
    except Timeout:
        row["status"] = "timeout"
        row["error_class"] = "timeout"
        row["error_detail"] = f"build_export exceeded the {timeout}-s guard"
        return row
    row["status"] = "exported"
    row["vertex_count"] = summary["vertex_count"]
    row["triangle_count"] = summary["triangle_count"]
    row["ply_sha256"] = hashlib.sha256(ply_path.read_bytes()).hexdigest()
    row["l2_fields_sha256"] = _l2_fields_digest(summary)
    composite_info = summary.get("composite")
    if isinstance(composite_info, dict):
        row["composite_stage"] = str(composite_info.get("stage", ""))
        row["node_bytes"] = composite_info.get("node_bytes", "")
    ply_path.unlink(missing_ok=True)
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--timeout", type=int, default=120,
                    help="per-store wall-clock guard in seconds (SIGALRM)")
    ap.add_argument("--out-name", default="replay-export-seam.csv")
    args = ap.parse_args()

    rows_in = [
        r for r in csv.DictReader(MANIFEST.open())
        if r["kind"] == "part"
    ]
    rows_in.sort(key=lambda r: r["sha256"])

    signal.signal(signal.SIGALRM, _alarm)
    out_rows = []
    with tempfile.TemporaryDirectory(prefix="replay-plies-") as tmp:
        ply_dir = Path(tmp)
        for i, rel in enumerate(rows_in):
            signal.alarm(args.timeout)
            try:
                row = replay_part(rel, ply_dir, args.timeout)
            except Timeout:
                row = {k: "" for k in FIELDS}
                row["sha256"] = rel["sha256"]
                row["split"] = rel["split"]
                row["status"] = "timeout"
                row["error_class"] = "timeout"
                row["error_detail"] = (
                    f"build_export exceeded the {args.timeout}-s guard"
                )
            finally:
                signal.alarm(0)
            out_rows.append(row)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(rows_in)}", file=sys.stderr)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / args.out_name
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    print(f"wrote {out_path} ({len(out_rows)} rows)")
    summarize(out_rows)
    return 0


def summarize(rows) -> None:
    """Coverage split: clean vs composite stages vs error classes."""
    from collections import Counter

    statuses = Counter(r["status"] for r in rows)
    print(f"== replay: {len(rows)} parts — {dict(statuses)}")
    exported = [r for r in rows if r["status"] == "exported"]
    stages = Counter(r["composite_stage"] or "clean/pool" for r in exported)
    print(f"   exported by decode stage: {dict(stages)}")
    classes = Counter(
        r["error_class"] for r in rows if r["status"] in ("error", "timeout")
    )
    print(f"   failures by class: {dict(classes)}")
    # composite exports split by node form (big = payload > 4096 B)
    big = [r for r in exported if str(r["node_bytes"]) not in ("", "None")
           and int(r["node_bytes"]) > 4096]
    small = [r for r in exported
             if str(r["node_bytes"]) not in ("", "None")
             and int(r["node_bytes"]) <= 4096]
    print(f"   composite exports: big-form {len(big)}, small-form {len(small)}")


if __name__ == "__main__":
    sys.exit(main())
