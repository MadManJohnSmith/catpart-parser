#!/usr/bin/env python3
"""W21 visual QA — deterministic stratified batch sampler (Bloque D14).

Emits one JSON list per batch with the parts to render in the shipped
viewer. Sources are committed CSVs only, so every list is reproducible:

- Submarino: docs/evidence/data/w7-parity-claims-python-sub757.csv
  (757 rows at the shipped base). "Mayor used_written" is operationalized
  as the largest decoded geometry (l2_triangle_count, then
  l2_vertex_count) — the term does not exist in the codebase or the
  committed CSVs; the note records the mapping.
- Corpus: docs/evidence/data/w4-open-rate-files.csv (1,442 rows) +
  manifests/corpus-manifest.csv for full shas and on-disk resolution.
- Bench external (Audi/Motor/...): ~/.local/state/catpart-parser/
  bench-external/pairs.json (uncommitted, named in the note).

Off-disk rows (62 dev parts moved upstream after the 2026-11-07 freeze)
are skipped and replaced by the next row under the same ordering key;
each skipped row is recorded in the emitted JSON so the rate is known.

Usage: python -B scripts/triage/w21_visual_sample.py --out <jsonl>
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUB_SNAPSHOT = (
    Path.home()
    / ".local/state/catpart-parser/w9-sub"
    / "submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20"
)
SUB_PREFIX = "Submarine-Tr-1700-S42-Catia"
MAIN_REPO = Path("/home/alan/Documents/Repos/catpart-parser")
BENCH = Path.home() / ".local/state/catpart-parser/bench-external"

BATCHES = ("sub-top", "sub-notmanifold", "corpus-top", "corpus-flips", "bench")


def tri_key(row):
    return (int(row["l2_triangle_count"] or 0), int(row["l2_vertex_count"] or 0))


def sub_rows():
    with open(REPO / "docs/evidence/data/w7-parity-claims-python-sub757.csv") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 757
    return rows


def corpus_rows():
    with open(REPO / "docs/evidence/data/w4-open-rate-files.csv") as fh:
        rows = list(csv.DictReader(fh))
    return rows


_MANIFEST = None


def manifest_by_sha16():
    global _MANIFEST
    if _MANIFEST is None:
        by_rp = {}
        with open(REPO / "manifests/corpus-manifest.csv") as fh:
            for row in csv.DictReader(fh):
                by_rp[row["sha256"][:16]] = row
        _MANIFEST = by_rp
    return _MANIFEST


def corpus_disk_path(sha16: str) -> Path | None:
    """Resolve via the manifest's local_path — the open-rate CSV's path
    column lacks the repo prefix, so match on the sha16."""
    row = manifest_by_sha16().get(sha16)
    if row is None:
        return None
    cand = MAIN_REPO / row["local_path"]
    return cand if cand.is_file() else None


def sub_disk_path(path: str) -> Path | None:
    cand = SUB_SNAPSHOT / path
    return cand if cand.is_file() else None


def emit(out, batch, entries):
    for e in entries:
        e["batch"] = batch
        out.write(json.dumps(e, sort_keys=True) + "\n")
    print(
        f"{batch}: {len(entries)} parts, {len([e for e in entries if e.get('skip')])} skips"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out", type=Path, required=True, help="output JSONL (one part per line)"
    )
    ap.add_argument("--per-batch", type=int, default=20)
    args = ap.parse_args()

    manifest = manifest_by_sha16()

    with open(args.out, "w") as out:
        # --- sub-top: largest decoded geometry among passing parts -------
        rows = [r for r in sub_rows() if r["l2_status"] == "pass"]
        rows.sort(key=tri_key, reverse=True)
        picked, skipped = [], []
        for r in rows:
            if len(picked) >= args.per_batch:
                break
            disk = sub_disk_path(r["path"])
            entry = {
                "path": r["path"],
                "sha256": r["sha256"],
                "triangles": int(r["l2_triangle_count"] or 0),
                "vertices": int(r["l2_vertex_count"] or 0),
                "family": "sub-pass",
            }
            if disk:
                entry["abs_path"] = str(disk)
                entry["bytes"] = disk.stat().st_size
                picked.append(entry)
            else:
                entry["skip"] = "off-disk"
                skipped.append(entry)
        emit(out, "sub-top", picked + skipped)

        # --- sub-notmanifold: largest not-manifold residuals -------------
        rows = [r for r in sub_rows() if r["l2_failed_check"] == "not-manifold"]
        rows.sort(key=tri_key, reverse=True)
        picked, skipped = [], []
        for r in rows:
            if len(picked) >= args.per_batch:
                break
            disk = sub_disk_path(r["path"])
            entry = {
                "path": r["path"],
                "sha256": r["sha256"],
                "triangles": int(r["l2_triangle_count"] or 0),
                "vertices": int(r["l2_vertex_count"] or 0),
                "family": "sub-notmanifold",
            }
            if disk:
                entry["abs_path"] = str(disk)
                entry["bytes"] = disk.stat().st_size
                picked.append(entry)
            else:
                entry["skip"] = "off-disk"
                skipped.append(entry)
        emit(out, "sub-notmanifold", picked + skipped)

        # --- corpus-top: largest MESH corpus parts ----------------------
        rows = [r for r in corpus_rows() if r["open kind"] == "MESH"]
        rows.sort(key=lambda r: -int(r["triangles"] or 0))
        picked, skipped = [], []
        for r in rows:
            if len(picked) >= args.per_batch:
                break
            m = manifest.get(r["sha16"])
            disk = corpus_disk_path(r["sha16"])
            entry = {
                "path": r["path"],
                "sha16": r["sha16"],
                "sha256": m["sha256"] if m else "",
                "triangles": int(r["triangles"] or 0),
                "vertices": int(r["points"] or 0),
                "family": "corpus-mesh-top",
            }
            if disk:
                entry["abs_path"] = str(disk)
                entry["bytes"] = disk.stat().st_size
                picked.append(entry)
            else:
                entry["skip"] = "off-disk"
                skipped.append(entry)
        emit(out, "corpus-top", picked + skipped)

        # --- corpus-flips: recent flip families + big point carriers ----
        # The recent documented flips: not-manifold (5) + degenerate (2)
        # report rows, the W4 display->mesh flip (CAAPstPad1_2), and the
        # largest DISPLAY rows (points-only renders, the panels/point
        # carriers the scalar metrics cannot judge).
        rows = corpus_rows()
        flip_rows = [
            r
            for r in rows
            if r["report class"] in ("not-manifold", "degenerate-triangles")
        ]
        disp_rows = [r for r in rows if r["open kind"] == "DISPLAY"]
        disp_rows.sort(key=lambda r: -int(r["points"] or 0))
        chosen = flip_rows + disp_rows[: args.per_batch]
        picked, skipped = [], []
        for r in chosen:
            if len(picked) >= args.per_batch:
                break
            m = manifest.get(r["sha16"])
            disk = corpus_disk_path(r["sha16"])
            entry = {
                "path": r["path"],
                "sha16": r["sha16"],
                "sha256": m["sha256"] if m else "",
                "triangles": int(r["triangles"] or 0),
                "vertices": int(r["points"] or 0),
                "family": f"corpus-{r['report class']}-{r['open kind']}",
            }
            if disk:
                entry["abs_path"] = str(disk)
                entry["bytes"] = disk.stat().st_size
                picked.append(entry)
            else:
                entry["skip"] = "off-disk"
                skipped.append(entry)
        emit(out, "corpus-flips", picked + skipped)

        # --- bench: external Audi/Motor etc. (budget permitting) --------
        pairs = BENCH / "pairs.json"
        if pairs.is_file():
            data = json.loads(pairs.read_text())
            items = data if isinstance(data, list) else data.get("pairs", [])
            picked = []
            for it in items:
                catpart = it.get("catpart") or it.get("catpart_path") or it.get("path")
                if not catpart:
                    continue
                cand = (
                    (BENCH / catpart)
                    if not Path(catpart).is_absolute()
                    else Path(catpart)
                )
                if cand.is_file():
                    picked.append(
                        {
                            "path": catpart,
                            "sha256": "",
                            "triangles": int(it.get("triangles") or 0),
                            "vertices": int(it.get("vertices") or 0),
                            "family": f"bench-{it.get('name', it.get('repo', 'x'))}",
                            "abs_path": str(cand),
                            "bytes": cand.stat().st_size,
                        }
                    )
            emit(out, "bench", picked[: args.per_batch])
        else:
            print("bench: pairs.json not present on this host — batch skipped")


if __name__ == "__main__":
    main()
