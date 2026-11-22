#!/usr/bin/env python3
"""w4 parity sweep: Python ``catpart-export`` vs Rust ``fidelity-cli``
over the no-surface population (the rows whose summary can carry the
additive ``feature_tree`` block) + the face-gp fires.

One row per line, streaming, ``gc.collect()`` between rows (the
anti-OOM sweep rule); writes
``docs/evidence/data/w4-parity-no-surface.csv``.  The PLYs go to a
temporary directory and are discarded.

Run::

    .venv/bin/python -I scripts/triage/probe_w4_parity.py
"""

import csv
import gc
import json
import numbers
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "triage"))

from probe_bagrep import load_manifest  # noqa: E402
from catpart.geometry.export import build_export  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

OUT = os.path.join(ROOT, "docs", "evidence", "data", "w4-parity-no-surface.csv")
CLI = os.path.join(ROOT, "port", "target", "release", "fidelity-cli")


def doc_equal(a, b) -> bool:
    """Parsed-document equality (the fidelity harness's definition)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(doc_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(doc_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, numbers.Number) and isinstance(b, numbers.Number):
        return float(a) == float(b)
    return a == b


def main() -> int:
    man = load_manifest(ROOT)
    import csv as _csv

    fires = set()
    sweep = os.path.join(ROOT, "docs", "evidence", "data", "w4-face-gp-sweep.csv")
    if os.path.exists(sweep):
        with open(sweep, newline="") as fh:
            for row in _csv.DictReader(fh):
                if row["fires"] == "yes":
                    fires.add(row["path"])

    rows = list(_csv.DictReader(open(os.path.join(ROOT, "manifests", "corpus-manifest.csv"))))
    with tempfile.TemporaryDirectory(prefix="w4-parity-") as tmp:
        ply_py = os.path.join(tmp, "py.ply")
        ply_rs = os.path.join(tmp, "rs.ply")
        ok = bad = no_surface = fires_checked = 0
        out = open(OUT, "w", newline="")
        writer = _csv.writer(out)
        writer.writerow([
            "sha16", "path", "split", "population", "py_error_class",
            "rs_error_class", "ply_equal", "summary_equal",
        ])
        for row in rows:
            if row["kind"] != "part":
                continue
            local = row["local_path"]
            if not os.path.exists(local):
                continue
            # classify by a Python export first (the probe's own rule)
            try:
                summary = build_export(Path(local), ply_py)
                error_class = None
            except ExportError as exc:
                summary, error_class = None, exc.error_class
            except OSError as exc:
                summary, error_class = None, "unreadable-file"
            is_fire = row["path"] in fires
            is_no_surface = summary is not None and summary["triangle_count"] == 0
            if not (is_fire or is_no_surface or error_class):
                continue
            population = "fire" if is_fire else ("display" if is_no_surface else "error")
            if population == "error":
                no_surface += 1
            elif population == "fire":
                fires_checked += 1
            else:
                no_surface += 1
            # the Rust twin
            proc = subprocess.run([CLI, "export", local, ply_rs], capture_output=True, text=True)
            py_err = error_class or ""
            if proc.returncode != 0:
                rs_err = ""
                try:
                    rs_err = json.loads(proc.stderr).get("error_class", "")
                except Exception:  # noqa: BLE001
                    rs_err = proc.stderr.strip()[:80]
                ply_equal = py_err == rs_err and py_err != ""
                summary_equal = ply_equal
                good = ply_equal
            else:
                doc_rs = json.loads(proc.stdout)
                rs_bytes = open(ply_rs, "rb").read()
                py_bytes = open(ply_py, "rb").read() if summary is not None else b""
                ply_equal = bool(summary is not None and py_bytes == rs_bytes)
                summary_equal = bool(summary is not None and doc_equal(summary, doc_rs))
                good = ply_equal and summary_equal
            writer.writerow([
                row["sha256"][:16], row["path"], row["split"], population,
                py_err, "OK" if proc.returncode == 0 else "error",
                ply_equal, summary_equal,
            ])
            if good:
                ok += 1
            else:
                bad += 1
                print(f"MISMATCH {row['path']} pop={population} ply={ply_equal} doc={summary_equal}")
            gc.collect()
        out.close()
    print(f"parity: {ok} ok, {bad} bad (fires {fires_checked}, no-surface {no_surface})")
    print(f"data: {OUT}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
