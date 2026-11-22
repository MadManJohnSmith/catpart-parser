#!/usr/bin/env python3
"""W8 unclassified census + binary-signature taxonomy.

Two modes, one script:

``census`` (the Top-1 fact-check)
    Apply the W6 ``fail_family`` law (``pass`` | ``check:<failed_check>`` |
    ``error:<error_class>`` | ``fail-unclassified``) over the committed
    per-file evidence (the W7 parity CSVs, the latest fitness report)
    and emit one per-file row per input. The W6 Top-1 ROI row (366
    ``fail-unclassified`` submarine parts) was computed from the W1-era
    bench CSV, before the harness named failure causes; at base dae7dd1
    the census counts **0** unclassified rows on both corpora
    (docs/evidence/2026-11-22-w8-unclassified.md).

``taxonomy`` (the brief's signature clustering)
    For every ``.CATPart`` file given, measure the stable binary
    signature the brief pins: detected version, container-table shape
    (block count + sorted container names), per-located-store body
    signature (body size bucket, pool-group count, wrapper sub-kinds,
    facet-candidate bucket, first record header at ``body_lo``). Rows
    cluster on the sha16 of the signature tuple and rank by files x
    triangles (triangles joined from the census CSV when given; zero-
    mesh rows rank by files). The measured residual (W8): the
    ``empty-geometry-store`` cluster — located stores carrying no
    geometry payload of any pinned kind.

Streaming, one file in RAM (the census never reads binaries; the
taxonomy reads one file at a time, ``gc.collect()`` between files).
Stdlib only; no parser invocation in census mode.

Usage:
  python -B scripts/triage/w8_unclassified_census.py census \
      --parity-csv docs/evidence/data/w7-parity-claims-python-sub757.csv \
      [--fitness-report fitness/reports/<run>.json] \
      [--out docs/evidence/data/w8-unclassified-census.csv]

  python -B scripts/triage/w8_unclassified_census.py taxonomy \
      --dir <dir> [--dir <dir2> ...] [--family-csv <census.csv>] \
      --out docs/evidence/data/w8-unclassified-clusters.csv
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import mmap
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

from catpart.geometry import pool, store, unclassified  # noqa: E402
from catpart.version import detect_version  # noqa: E402


def fail_family(l2: dict) -> str:
    """The W6 label law (verbatim semantics)."""
    if l2.get("status") == "pass":
        return "pass"
    if l2.get("error_class"):
        return f"error:{l2['error_class']}"
    if l2.get("failed_check"):
        return f"check:{l2['failed_check']}"
    return "fail-unclassified"


def census_rows(args) -> list[dict]:
    """One row per labeled file across the given evidence inputs."""
    rows: list[dict] = []
    for csv_path in args.parity_csv:
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                status = r["l2_status"]
                fam = fail_family(
                    {
                        "status": status,
                        "error_class": r["l2_error_class"],
                        "failed_check": r["l2_failed_check"],
                    }
                )
                rows.append(
                    {
                        "source": Path(csv_path).name,
                        "path": r["path"],
                        "sha16": r["sha256"][:16],
                        "engine": r.get("engine", ""),
                        "detected_version": r.get("detected_version", ""),
                        "l2_status": status,
                        "error_class": r["l2_error_class"],
                        "failed_check": r["l2_failed_check"],
                        "fail_family": fam,
                        "triangle_count": int(r["l2_triangle_count"] or 0),
                    }
                )
    if args.fitness_report:
        report = json.loads(Path(args.fitness_report).read_text(encoding="utf-8"))
        for f in report["files"]:
            l2 = f.get("l2")
            if not l2:
                continue
            fam = fail_family(l2)
            rows.append(
                {
                    "source": Path(args.fitness_report).name,
                    "path": f["path"],
                    "sha16": f["sha256"][:16],
                    "engine": "python-fitness",
                    "detected_version": f.get("detected_version") or "",
                    "l2_status": l2.get("status") or "",
                    "error_class": l2.get("error_class") or "",
                    "failed_check": l2.get("failed_check") or "",
                    "fail_family": fam,
                    "triangle_count": int(l2.get("triangle_count") or 0),
                }
            )
    return rows


def write_census(rows: list[dict], out_path: Path) -> Counter:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "source",
        "path",
        "sha16",
        "engine",
        "detected_version",
        "l2_status",
        "error_class",
        "failed_check",
        "fail_family",
        "triangle_count",
    )
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    agg: Counter = Counter()
    tris: Counter = Counter()
    for r in rows:
        agg[r["fail_family"]] += 1
        tris[r["fail_family"]] += r["triangle_count"]
    return Counter({k: (agg[k], tris[k]) for k in agg})


def _bucket(size: int) -> str:
    for bound, name in (
        (0, "0"),
        (1024, "<=1K"),
        (4096, "<=4K"),
        (16384, "<=16K"),
        (65536, "<=64K"),
        (262144, "<=256K"),
    ):
        if size <= bound:
            return name
    return ">256K"


def _cand_bucket(count: int) -> str:
    if count == 0:
        return "0"
    if count <= 4:
        return "1-4"
    if count <= 64:
        return "5-64"
    return ">64"


def file_signature(path: Path) -> dict:
    """The brief's binary signature: version + container shape + store
    bodies (one file in RAM; the body scan is the pinned scanners).

    The file mmaps flat (anti-OOM: a 375 MB part stays page-cached, not
    heap-resident) and the sha256 runs over the same fd in chunks."""
    fh = open(path, "rb")
    data = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
    digest = hashlib.sha256()
    fh.seek(0)
    for chunk in iter(lambda: fh.read(65536), b""):
        digest.update(chunk)
    digest = digest.hexdigest()
    version = detect_version(data) or "unknown"
    blocks = store.valid_blocks(data)
    names = tuple(sorted(nm for _, nm in blocks))
    d8_outer = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    store_sigs: list[str] = []
    located = 0
    empty_payload = 0
    # The export walk, verbatim (_export_store_data): the three named
    # probe families, then the stage-12 ``others`` family (every
    # remaining valid block) — the submarine corpus's stores sit in
    # CATProdCont blocks, recovered there.
    probes: list[tuple[str, list[int]]] = [
        (nm, [blk for blk, bnm in blocks if bnm == nm])
        for nm in store.NAMED_PROBE_CONTAINERS
    ]
    probes.append(
        (
            "other-container",
            [blk for blk, nm2 in blocks if nm2 not in store.NAMED_PROBE_CONTAINERS],
        )
    )
    for probe, blocks_in_probe in probes:
        located_in_probe = 0
        for blk in blocks_in_probe:
            try:
                span = store.locate_store(data, blk, blocks, d8_outer)
            except Exception:
                continue  # malformed-store-header: the locator's own family
            if span is None:
                continue
            located += 1
            located_in_probe += 1
            # The pool scan is the same call the exporter makes; its
            # group count feeds the signature (and the empty-payload
            # law: 0 groups is a precondition there).
            try:
                groups, _kinds = pool.scan_pool_groups(data, span.body_lo, span.body_hi)
                pool_count = len(groups)
            except Exception:
                pool_count = -1  # malformed-pool-*: the pool's own family
            sig = unclassified.body_signature(
                data, span.body_lo, span.body_hi, pool_groups=max(pool_count, 0)
            )
            if sig.is_empty_payload:
                empty_payload += 1
            first_header = bytes(data[span.body_lo : span.body_lo + 4]).hex()
            store_sigs.append(
                f"{probe}:{_bucket(sig.body_bytes)}:p{pool_count}"
                f":k{','.join(k.hex() for k in sig.kinds) or '-'}"
                f":c{_cand_bucket(sig.facet_candidates)}:h{first_header}"
            )
        if located_in_probe:
            break  # the export walk's early stop: a located family wins
    data.close()
    fh.close()
    gc.collect()
    container_shape = (
        f"{len(blocks)}:"
        + hashlib.sha256("|".join(names).encode()).hexdigest()[:12]
    )
    components = (
        f"v={version}",
        f"ct={container_shape}",
        f"stores={located}",
        *store_sigs,
    )
    key = hashlib.sha256("\n".join(components).encode()).hexdigest()[:16]
    return {
        "sha16": digest[:16],
        "cluster": key,
        "version": version,
        "blocks": len(blocks),
        "container_shape": container_shape,
        "located_stores": located,
        "empty_payload_stores": empty_payload,
        "store_signatures": ";".join(store_sigs) or "-",
        "signature": " | ".join(components),
    }


def taxonomy_rows(dirs: list[Path], family_csv: Path | None) -> list[dict]:
    """One signature row per .CATPart file (streamed)."""
    families: dict[str, dict] = {}
    if family_csv:
        with open(family_csv, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                # Both evidence shapes join here: the census CSV's
                # ``fail_family`` + ``sha16``, and the head-decode
                # sweep's ``family`` + full ``sha256``.
                fam = r.get("fail_family") or r.get("family") or ""
                sha16 = r.get("sha16") or (r.get("sha256") or "")[:16]
                if not sha16:
                    continue
                families.setdefault(sha16, {**r, "fail_family": fam})
    rows: list[dict] = []
    for directory in dirs:
        for path in sorted(directory.rglob("*.CATPart")):
            sig = file_signature(path)
            fam_row = families.get(sig["sha16"], {})
            rows.append(
                {
                    "path": str(path),
                    "fail_family": fam_row.get("fail_family", ""),
                    "triangle_count": fam_row.get("triangle_count", ""),
                    **sig,
                }
            )
    return rows


def write_clusters(rows: list[dict], out_path: Path) -> list[tuple]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "path",
        "sha16",
        "cluster",
        "version",
        "blocks",
        "container_shape",
        "located_stores",
        "empty_payload_stores",
        "store_signatures",
        "fail_family",
        "triangle_count",
        "signature",
    )
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    clusters: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        clusters[r["cluster"]].append(r)
    ranked = []
    for key, members in clusters.items():
        files = len(members)
        tris = sum(int(m["triangle_count"] or 0) for m in members)
        fams = Counter(m["fail_family"] or "(unlabeled)" for m in members)
        # The residual-ROI ranking: files x triangles over the FAILING
        # members only (a passing cluster owns no open work). Zero-mesh
        # failures rank as files x 1 (their blocked geometry carries no
        # triangles to weigh).
        failing = [m for m in members if m["fail_family"] not in ("", "pass")]
        fail_tris = sum(int(m["triangle_count"] or 0) for m in failing)
        roi = (
            len(failing) * fail_tris
            if fail_tris
            else len(failing)
        )
        ranked.append((roi, files, tris, key, fams.most_common(3), members[0]["signature"]))
    ranked.sort(reverse=True)
    return ranked


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    c = sub.add_parser("census", help="the fail_family census over evidence CSVs")
    c.add_argument("--parity-csv", action="append", type=Path, default=[])
    c.add_argument("--fitness-report", type=Path, default=None)
    c.add_argument("--out", type=Path, required=True)

    t = sub.add_parser("taxonomy", help="the binary-signature clustering")
    t.add_argument("--dir", action="append", type=Path, required=True)
    t.add_argument("--family-csv", type=Path, default=None)
    t.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(argv)
    if args.mode == "census":
        rows = census_rows(args)
        agg = write_census(rows, args.out)
        print(f"rows: {len(rows)} -> {args.out}")
        for fam, (count, tris) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
            print(f"  {fam:30s} files={count:5d} tris={tris}")
        unclassified_count = sum(v[0] for k, v in agg.items() if k == "fail-unclassified")
        print(f"fail-unclassified total: {unclassified_count}")
        return 0

    ranked = write_clusters(taxonomy_rows(args.dir, args.family_csv), args.out)
    print(f"rows: {len(ranked)} clusters -> {args.out}")
    for roi, files, tris, key, fams, sig in ranked[:12]:
        print(f"  roi={roi:6d} files={files:4d} tris={tris:7d} {key} {dict(fams)}")
        print(f"    {sig[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
