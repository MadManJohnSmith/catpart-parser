#!/usr/bin/env python3
"""W11 probe: exact-analytic surface availability over the undecoded-variant
population (marathon B8).

The dispatch question: do the parts without ``CAT3DFaceGP`` tessellation
(the ``undecoded-variant`` rows of the latest fitness report) carry
evaluable exact surfaces — analytic blocks (plane/cylinder/cone/sphere
with axis+radius+limits) or a NURBS payload — that a decoder could
tessellate deterministically from the record's own law?

This probe measures it per file with the shipped scanner
(:mod:`catpart.geometry.analytic`): the store body's object-stream walk
(``01 56`` plane objects — template vs per-part under the byte-exact
template law — scene records, property values), the ``CATPrtCont``
content bulk under the committed A/B frame law (cluster census, frame
classes, payload float census with the fixed-point alias guard), the
BR5 NURBS signature detector, and the shipped ``a5 03 34`` frame scan.
The export path is re-run per file so the row carries the current
failure class next to the taxonomy.

Outputs
``docs/evidence/data/w11-analytic-files.csv`` (one row per population
file, plus the seeded passing-file control rows) and
``docs/evidence/data/w11-analytic-claims.csv`` (``W11-01``..). Exit 2
when any population file's verdict flips to
``analytic-surface-records-present`` — the reopening signal. Read-only
over the corpus; ``src/`` and the exporter are untouched by the probe.

Determinism: fixed corpus walk order (sha256), a seeded control sample,
no wall-clock input. One part in memory at a time.

Usage::

    .venv/bin/python -I scripts/triage/w11_analytic_probe.py
    .venv/bin/python -I scripts/triage/w11_analytic_probe.py --selftest
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import random
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from catpart.brep.cgm_nurbs import valid_regions  # noqa: E402
from catpart.geometry.analytic import (  # noqa: E402
    TEMPLATE_PLANE_UV,
    VERDICT_ANALYTIC_PRESENT,
    VERDICT_NO_ANALYTIC,
    analytic_shape_candidates,
    bulk_clusters,
    plane_records,
    parse_frame,
    scan_part,
)
from catpart.geometry.errors import ExportError  # noqa: E402
from catpart.geometry.export import build_export  # noqa: E402

DEFAULT_REPORT = ROOT / "fitness/reports/20261121T103944Z-d2c9ff.json"
#: the corpus is not committed; it lives in the main checkout this
#: worktree branches from (every corpus probe reads it read-only from
#: there — decode_brep_graph.py's ``--corpus-root`` precedent)
DEFAULT_CORPUS = Path("/home/alan/catpart-parser/corpus")
FILES_CSV = ROOT / "docs/evidence/data/w11-analytic-files.csv"
CLAIMS_CSV = ROOT / "docs/evidence/data/w11-analytic-claims.csv"
CONTROL_SAMPLE = 6
CONTROL_SEED = 11

FILES_FIELDS = [
    "sha16",
    "path",
    "corpus_path",
    "split",
    "report_class",
    "export_class",
    "verdict",
    "store_body_size",
    "object_records",
    "plane_records",
    "template_planes",
    "per_part_planes",
    "plane_ids",
    "scene_records",
    "property_values",
    "bulk_dialect",
    "bulk_frame_count",
    "bulk_framed_bytes",
    "cylinder_hits",
    "cylinder_distinct",
    "cone_hits",
    "cone_distinct",
    "nurbs_knot_runs",
    "nurbs_weight_runs",
    "a5_surface_frames",
    "cgm_region_bytes",
]

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]


def index_corpus(corpus: Path) -> dict[str, tuple[str, str]]:
    """sha256 -> (absolute path, corpus-relative path), sorted walk.

    The corpus-relative path is what the parity test resolves from the
    checkout's own ``corpus/`` (a read-only symlink in worktrees, the
    ``.gitignore``-covered convention).
    """
    index: dict[str, tuple[str, str]] = {}
    for dirpath, _, files in os.walk(corpus):
        for fn in sorted(files):
            path = os.path.join(dirpath, fn)
            digest = hashlib.sha256()
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    digest.update(chunk)
            rel = os.path.relpath(path, corpus)
            index[digest.hexdigest()] = (path, rel)
    return index


def cgm_region_bytes(data: bytes) -> int:
    for blk, name, rend in valid_regions(data):
        if name == "CGMGeom":
            return rend - blk
    return 0


def _bulk_framed_bytes(data: bytes) -> int:
    for blk, name, rend in valid_regions(data):
        if name != "CATPrtCont":
            continue
        clusters, _ = bulk_clusters(data, blk, rend)
        return sum(end - start for start, end in clusters)
    return 0


def measure_row(data: bytes, path: str, meta: dict, corpus_rel: str = "") -> dict:
    scan = scan_part(data)
    export_class = "export-ok"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            build_export(path, os.path.join(tmp, "w11.ply"))
    except ExportError as exc:
        export_class = exc.error_class
    except OSError:
        export_class = "unreadable-file"
    return {
        "sha16": meta["sha256"][:16],
        "path": meta["path"],
        "corpus_path": corpus_rel,
        "split": meta.get("split", ""),
        "report_class": meta.get("report_class", ""),
        "export_class": export_class,
        "verdict": scan.verdict,
        "store_body_size": scan.store_body_size,
        "object_records": scan.object_records,
        "plane_records": len(scan.plane_records),
        "template_planes": scan.template_planes,
        "per_part_planes": scan.per_part_planes,
        "plane_ids": ";".join(str(p.object_id) for p in scan.plane_records),
        "scene_records": scan.scene_records,
        "property_values": scan.property_values,
        "bulk_dialect": scan.bulk_dialect or "",
        "bulk_frame_count": sum(f.count for f in scan.bulk_frame_classes),
        "bulk_framed_bytes": _bulk_framed_bytes(data),
        "cylinder_hits": scan.cylinder_candidates.count,
        "cylinder_distinct": scan.cylinder_candidates.distinct,
        "cone_hits": scan.cone_candidates.count,
        "cone_distinct": scan.cone_candidates.distinct,
        "nurbs_knot_runs": scan.nurbs_knot_runs,
        "nurbs_weight_runs": scan.nurbs_weight_runs,
        "a5_surface_frames": scan.a5_surface_frames,
        "cgm_region_bytes": cgm_region_bytes(data),
    }


def population(report_path: Path) -> list[dict]:
    report = json.loads(report_path.read_text())
    rows = []
    for entry in report["files"]:
        l2 = entry.get("l2") or {}
        if l2.get("error_class") == "undecoded-variant":
            rows.append(
                {
                    "sha256": entry["sha256"],
                    "path": entry["path"],
                    "split": entry.get("split", ""),
                    "report_class": "undecoded-variant",
                }
            )
    rows.sort(key=lambda r: r["sha256"])
    return rows


def control_rows(report_path: Path, corpus_index: dict[str, str]) -> list[dict]:
    """A seeded sample of clean part rows: the template-plane control."""
    report = json.loads(report_path.read_text())
    clean = [
        e
        for e in report["files"]
        if e.get("classification") == "clean" and e.get("kind") == "part"
    ]
    clean.sort(key=lambda e: e["sha256"])
    rng = random.Random(CONTROL_SEED)
    sample = rng.sample(clean, min(CONTROL_SAMPLE, len(clean)))
    rows = []
    for entry in sample:
        path = corpus_index.get(entry["sha256"])
        if path is None:
            continue
        rows.append(
            {
                "sha256": entry["sha256"],
                "path": entry["path"],
                "split": entry.get("split", ""),
                "report_class": "clean(control)",
            }
        )
    rows.sort(key=lambda r: r["sha256"])
    return rows


def run(corpus: Path, report_path: Path) -> tuple[list[dict], list[dict]]:
    corpus_index = index_corpus(corpus)
    rows: list[dict] = []
    for meta in population(report_path):
        found = corpus_index.get(meta["sha256"])
        if found is None:
            print(f"  MISSING {meta['sha256'][:16]} {meta['path']}", flush=True)
            continue
        path, rel = found
        with open(path, "rb") as fh:
            data = fh.read()
        rows.append(measure_row(data, path, meta, rel))
        print(
            f"  {rows[-1]['sha16']} verdict={rows[-1]['verdict']} "
            f"planes={rows[-1]['plane_records']}(tpl {rows[-1]['template_planes']}) "
            f"dial={rows[-1]['bulk_dialect']} export={rows[-1]['export_class']}",
            flush=True,
        )
    for meta in control_rows(report_path, corpus_index):
        path, rel = corpus_index[meta["sha256"]]
        with open(path, "rb") as fh:
            data = fh.read()
        rows.append(measure_row(data, path, meta, rel))
        print(
            f"  control {rows[-1]['sha16']} verdict={rows[-1]['verdict']} "
            f"planes={rows[-1]['plane_records']}(tpl {rows[-1]['template_planes']})",
            flush=True,
        )
    return rows, claims(rows)


def claims(rows: list[dict]) -> list[dict]:
    pop = [r for r in rows if r["report_class"] == "undecoded-variant"]
    ctrl = [r for r in rows if r["report_class"].startswith("clean")]
    obj_stream = [r for r in pop if r["bulk_dialect"] == "object-stream"]
    e5 = [r for r in pop if r["bulk_dialect"] == "E5"]

    def claim(cid, scope, obs, passes, label, detail):
        rate = (passes / obs) if obs else ""
        return {
            "claim": cid,
            "scope": scope,
            "observations": obs,
            "passes": passes,
            "rate": f"{rate:.4f}" if obs else "",
            "label": label,
            "detail": detail,
        }

    no_analytic = sum(1 for r in pop if r["verdict"] == VERDICT_NO_ANALYTIC)
    out = [
        claim(
            "W11-01",
            "population",
            len(pop),
            no_analytic,
            "fact",
            "verdict no-evaluable-analytic-surface on the whole "
            "undecoded-variant population (no per-part analytic record, "
            "no a5 03 34 frame, no NURBS signature)",
        ),
        claim(
            "W11-02",
            "population",
            sum(r["a5_surface_frames"] for r in pop),
            0,
            "fact",
            "a5 03 34 surface frames across the population (the shipped "
            "exact-surface carrier is absent everywhere)",
        ),
        claim(
            "W11-03",
            "population",
            sum(r["nurbs_knot_runs"] + r["nurbs_weight_runs"] for r in pop),
            0,
            "fact",
            "NURBS signatures (knot runs + weight runs) across store "
            "bodies and CATPrtCont regions (BR5 detector)",
        ),
        claim(
            "W11-04",
            "population",
            sum(r["plane_records"] for r in pop),
            sum(r["template_planes"] for r in pop),
            "fact",
            "01 56 plane objects: every observed one carries a measured "
            "template direction pair (byte-exact law) — none is "
            "per-part geometry, none carries bounds",
        ),
        claim(
            "W11-05",
            "population",
            len(obj_stream) + len(e5),
            len(obj_stream),
            "fact",
            "bulk dialect split (object-stream vs E5) under the "
            "bulk-stream cluster law; E5 frames nothing at 4,116 B "
            "template content",
        ),
        claim(
            "W11-06",
            "population",
            sum(r["cylinder_hits"] + r["cone_hits"] for r in pop),
            0,
            "fact",
            "axis+radius shape hits after the fixed-point alias guard "
            "(the phase-census detector is diagnostic only)",
        ),
        claim(
            "W11-07",
            "population",
            sum(1 for r in pop if r["export_class"] == "undecoded-variant"),
            len(pop),
            "fact",
            "the export path still classifies every population file "
            "undecoded-variant (no runtime change intended or made)",
        ),
    ]
    if ctrl:
        tpl = sum(r["template_planes"] for r in ctrl)
        out.append(
            claim(
                "W11-08",
                "control",
                len(ctrl),
                tpl,
                "fact",
                "seeded clean-part control: the template plane objects "
                "also live in passing files' bodies (format constant, "
                "not an undecoded-variant signature)",
            )
        )
    return out


def selftest() -> int:
    """Synthetic fixtures pinning the detector's discriminating edges."""
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)
        print(f"  {'ok' if cond else 'FAIL'} {name}")

    # --- the template plane byte law fires on a synthetic body
    template_pair = TEMPLATE_PLANE_UV[0]
    body = (
        bytes(4)  # preamble
        + b"\xff\xff\x02\x00\x01\x56" + struct.pack("<I", 34)
        + bytes(14)
        + template_pair
        + bytes.fromhex("000070410000")  # 15.0 offset + tail bytes
        + b"\x00\x00\x14\x04\xff\xff\xff\xff\xff"
    )
    recs = plane_records(body, 0, len(body))
    check("template plane detected", len(recs) == 1)
    check("template plane id", bool(recs) and recs[0].object_id == 34)
    check("template flagged", bool(recs) and recs[0].is_template)

    # --- a per-part plane (different direction pair) is NOT template
    other_dir = struct.pack("<3f", 0.6, 0.8, 0.0) + struct.pack("<3f", 0.8, -0.6, 0.0)
    body2 = (
        b"\xff\xff\x02\x00\x01\x56" + struct.pack("<I", 7)
        + bytes(14)
        + other_dir
        + struct.pack("<f", 3.5)
        + b"\x00\x00\x14\x04\xff\xff\xff\xff\xff"
    )
    recs2 = plane_records(body2, 0, len(body2))
    check("per-part plane detected", len(recs2) == 1 and not recs2[0].is_template)

    # --- the alias guard: a 2^-k ladder is not an axis
    ladder = [2.0**-13, 1.0, 2.0**-11, 1.0] * 4
    hits = analytic_shape_candidates(ladder)
    check("fixed-point alias refused", hits["cylinder"].count == 0)
    real = analytic_shape_candidates([0.6, 0.8, 0.0, 5.0])
    check("real unit axis accepted", real["cylinder"].count == 1)

    # --- the frame law: widths, flags, closure
    a5_frame = (
        bytes([0xA5, 0x03, 0x34]) + struct.pack("<I", 7) + b"\x0f" + b"payload"
    )
    frame = parse_frame(a5_frame, 0, len(a5_frame))
    check("A-family frame closes", frame is not None and frame[:3] == ("A", 1, 0x34))
    b1_frame = bytes([0xB2, 0x03, 0x06, 2, 0x5A]) + b"xy"
    frame_b = parse_frame(b1_frame, 0, len(b1_frame))
    check("B-family frame closes", frame_b is not None and frame_b[:3] == ("B", 1, 0x06))
    check("B-family byte0 b1 rejected", parse_frame(b"\xb1\x03\x06\x02Zxy", 0, 7) is None)

    # --- verdict vocabulary and the two measured template pairs
    check(
        "verdict vocabulary",
        VERDICT_NO_ANALYTIC != VERDICT_ANALYTIC_PRESENT
        and len(TEMPLATE_PLANE_UV) == 2,
    )
    if failures:
        print(f"selftest: {len(failures)} failing checks")
        return 1
    print("selftest: all checks pass")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    rows, claim_rows = run(args.corpus, args.report)
    FILES_CSV.write_text(_to_csv(rows, FILES_FIELDS))
    CLAIMS_CSV.write_text(_to_csv(claim_rows, CLAIM_FIELDS))
    print(f"wrote {FILES_CSV} ({len(rows)} rows)")
    print(f"wrote {CLAIMS_CSV} ({len(claim_rows)} rows)")
    flips = [
        r
        for r in rows
        if r["report_class"] == "undecoded-variant"
        and r["verdict"] != VERDICT_NO_ANALYTIC
    ]
    if flips:
        print(f"REOPEN: {len(flips)} population file(s) carry analytic records")
        return 2
    return 0


def _to_csv(rows: list[dict], fields: list[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in fields})
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(main())
