#!/usr/bin/env python3
"""P3.1 probe: W5 law C evidence (matrix census, walk delta, oracle check).

Read-only. W5 (marathon v3) deliverable evidence:

* ``--census DIR``: the corpus-wide matrix-body census over every
  ``.CATProduct`` — per document, the non-root ``_Position`` records
  classified explicit/identity and per-body document spread; per body, the
  documents carrying it. Writes the claims CSVs:
  ``docs/evidence/data/w5-matrix-census-files-claims.csv`` and
  ``docs/evidence/data/w5-matrix-census-claims.csv``.
* ``--walk DIR``: per walked root, the walk-level placement counts under the
  pre-W5 law (no shared-body classification) vs W5 law C (shared bodies
  refused). Writes ``docs/evidence/data/w5-walk-delta-claims.csv``.
* ``--oracle DIR STEPS_DIR``: per instance of the four STEP-backed roots,
  the per-instance position check: the placed/refused transform against the
  exported assembly frame. Writes
  ``docs/evidence/data/w5-oracle-placement-claims.csv``.
* ``--parity DIR``: canonical-JSON parity (sha256) of the Python walk vs the
  Rust ``fidelity-cli tree`` on the five roots.

The STEP files carry inconsistent unit clauses (the writer's), so the
absolute-frame check uses, per file, the scale that makes the export
self-consistent (vela raw = mm, matching the M2 reference bbox; swbd raw =
m per its own clause and panel size) and, for the outlier-polluted flooding
/ bow exports, reports the scale-free span ratio instead. The decisive
contradiction is scale-free: the refused connector translation (2179.457 mm)
exceeds the whole exported extent of VM-vela-Mast (120.4 units) by 18x.

Modes:
    python3 -I scripts/triage/p31_lawc_census.py --census DIR
    python3 -I scripts/triage/p31_lawc_census.py --walk DIR
    python3 -I scripts/triage/p31_lawc_census.py --oracle DIR STEPS_DIR
    python3 -I scripts/triage/p31_lawc_census.py --parity DIR
    python3 -I scripts/triage/p31_lawc_census.py --selftest
"""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import catpart.fixtures_assembly as fa  # noqa: E402

REPO = ROOT
DATA = REPO / "docs" / "evidence" / "data"

#: The five walked roots measured for W5 (the four STEP-backed products and
#: the MB81 engine assembly).
W5_ROOTS = (
    "VM-vela-Mast",
    "MD-swbd-panel-0A1w",
    "BW-Flooding-compartment-sup",
    "BW-section-bow",
    "MD-MTU-16V-652-MB81",
)

#: Per-STEP numeric scale (raw value -> mm) with the byte evidence noted in
#: the claims CSV; flooding/bow are excluded (``None``) because their raw
#: clouds carry +-1e6 outlier points.
ORACLE_SCALES = {
    "VM-vela-Mast": 1.0,
    "MD-swbd-panel-0A1w": 1000.0,
    "BW-Flooding-compartment-sup": None,
    "BW-section-bow": None,
}

FIDELITY_CLI = REPO / "port" / "target" / "debug" / "fidelity-cli"


def load_docs(directory: Path) -> dict[str, bytes]:
    return {
        p.stem: p.read_bytes()
        for p in sorted(directory.glob("*.CATProduct"))
    }


def classify_records(name: str, records, shared: set[bytes]) -> dict[str, int]:
    classes: Counter = Counter()
    for rec in records:
        if rec["kind"] == "identity":
            classes["identity"] += 1
        elif rec["matrix"] in shared:
            classes["shared"] += 1
        else:
            classes["unique"] += 1
    return classes


def census(directory: Path) -> int:
    docs = load_docs(directory)
    body_docs: dict[bytes, set[str]] = defaultdict(set)
    doc_recs: dict[str, list] = {}
    for name, data in docs.items():
        records = fa.parse_position_matrix_records(data)
        doc_recs[name] = records
        for rec in records:
            body_docs[rec["matrix"]].add(name)
        gc.collect()
    shared = {b for b, d in body_docs.items() if len(d) >= 2}

    files_csv = DATA / "w5-matrix-census-files-claims.csv"
    claims_csv = DATA / "w5-matrix-census-claims.csv"
    with files_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["document", "n_records", "n_shared", "n_unique", "n_identity",
             "classes", "body_sha16s"]
        )
        for name in sorted(doc_recs):
            c = classify_records(name, doc_recs[name], shared)
            w.writerow(
                [name, len(doc_recs[name]), c["shared"], c["unique"],
                 c["identity"],
                 "+".join(k for k in ("shared", "unique", "identity") if c[k])
                 or "none",
                 ";".join(sorted(hashlib.sha256(r["matrix"]).hexdigest()[:16]
                                 for r in doc_recs[name])) or "none"]
            )
    with claims_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["body_sha16", "n_documents", "class", "documents", "n_records_total"]
        )
        for body, names in sorted(body_docs.items(), key=lambda kv: -len(kv[1])):
            n = sum(len(doc_recs[d]) for d in names if body in
                    {r["matrix"] for r in doc_recs[d]})
            w.writerow(
                [hashlib.sha256(body).hexdigest()[:16], len(names),
                 "shared" if body in shared else "unique",
                 ";".join(sorted(names)), n]
            )
    n_records = sum(len(r) for r in doc_recs.values())
    print(
        f"census: {len(docs)} documents, {n_records} non-root records, "
        f"{len(body_docs)} distinct bodies, {len(shared)} shared (>=2 docs)"
    )
    print(f"  {files_csv.relative_to(REPO)}")
    print(f"  {claims_csv.relative_to(REPO)}")
    return 0


def _walk_counts(docs: dict[str, bytes], root: str, law_c: bool) -> dict:
    """Walk-level counts; ``law_c=False`` reproduces the pre-W5 state."""
    table_cache: dict[str, dict | None] = {}
    records_cache: dict[str, list] = {}

    def records_for(name: str):
        if name not in records_cache:
            data = docs.get(name)
            records_cache[name] = (
                fa.parse_position_matrix_records(data) if data else []
            )
        return records_cache[name]

    if law_c:
        body_docs: dict[bytes, set[str]] = defaultdict(set)
        for name in docs:
            for rec in records_for(name):
                body_docs[rec["matrix"]].add(name)
        shared = {b for b, d in body_docs.items() if len(d) >= 2}
    else:
        shared = set()

    def table_for(name: str):
        if name not in table_cache:
            data = docs.get(name)
            pool = fa.scan_structure_pool(data) if data else None
            table_cache[name] = (
                fa.read_product_name_table(pool[2]) if pool else None
            )
        return table_cache[name]

    rows: list[dict] = []
    visiting: set[str] = set()

    def visit(name: str, depth: int):
        table = table_for(name)
        data = docs.get(name)
        if table is None or data is None or name in visiting:
            return
        child_tables = {
            child: ct["names"]
            for child in table["names"]
            if (ct := table_for(child)) is not None
        }
        own = fa.own_instance_names(table["names"], child_tables)
        placement = fa._name_table_placement(
            records_for(name), n_own=len(own), shared_bodies=shared
        )
        visiting.add(name)
        try:
            for child in own:
                row = {"name": child, "depth": depth, "placing_doc": name}
                row.update(placement)
                rows.append(row)
                if child in docs:
                    visit(child, depth + 1)
        finally:
            visiting.remove(name)

    visit(root, 0)
    counts = Counter(r["placement_status"] for r in rows)
    return {
        "root": root,
        "total": len(rows),
        "placed": counts["placed"],
        "identity": counts["identity"],
        "undecodable": counts["undecodable"],
        "rows": rows,
    }


def walk_delta(directory: Path) -> int:
    docs = load_docs(directory)
    out_csv = DATA / "w5-walk-delta-claims.csv"
    with out_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["root", "total", "placed_before", "placed_after",
             "identity_before", "identity_after", "undecodable_before",
             "undecodable_after"]
        )
        for root in W5_ROOTS:
            if root not in docs:
                print(f"  missing root document: {root}")
                continue
            before = _walk_counts(docs, root, law_c=False)
            after = _walk_counts(docs, root, law_c=True)
            w.writerow(
                [root, after["total"], before["placed"], after["placed"],
                 before["identity"], after["identity"],
                 before["undecodable"], after["undecodable"]]
            )
            print(
                f"  {root}: placed {before['placed']}->{after['placed']} "
                f"identity {before['identity']}->{after['identity']} "
                f"undec {before['undecodable']}->{after['undecodable']}"
            )
    print(f"  {out_csv.relative_to(REPO)}")
    return 0


def _cloud_bbox(path: Path, sample_every: int = 7) -> tuple | None:
    """Point-cloud bbox: ((full_min, full_max), (robust_min, robust_max), npts).

    The full extremes are the export's own extent; the percentile band
    (0.05%/99.95% per axis) records how much of the cloud the extremes
    outlier-pollute (flooding/bow carry +-1e6 outlier points; vela/swbd are
    clean and use the full extent).
    """
    import re

    sys.path.insert(0, str(ROOT / "scripts" / "triage"))
    import p30_step_oracle as p30  # noqa: E402

    ref_re = re.compile(b"#(\\d+)")
    vals: list[tuple[float, float, float]] = []
    full = [[None, None, None], [None, None, None]]
    buf = b""
    with open(path, "rb") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if not line.startswith(b"#") and not buf:
                continue
            if buf:
                line = buf + b" " + line
                buf = b""
            m = p30._ENT_RE.match(line)
            if m is None:
                if line.count(b"(") > line.count(b")") and len(line) < 4096:
                    buf = line
                continue
            if m.group(2) != b"CARTESIAN_POINT":
                continue
            args = p30._split_top(m.group(3))
            try:
                v = p30._floats(args[1])
            except Exception:
                continue
            for i in range(3):
                full[0][i] = v[i] if full[0][i] is None else min(full[0][i], v[i])
                full[1][i] = v[i] if full[1][i] is None else max(full[1][i], v[i])
            vals.append((v[0], v[1], v[2]))
    if not vals:
        return None
    _ = ref_re
    robust = []
    for axis in range(3):
        column = sorted(v[axis] for v in vals)
        lo = column[int(len(column) * 0.0005)]
        hi = column[int(len(column) * 0.9995) - 1]
        robust.append((lo, hi))
    return (full[0], full[1]), robust, len(vals)


def oracle_check(directory: Path, steps_dir: Path) -> int:
    docs = load_docs(directory)
    out_csv = DATA / "w5-oracle-placement-claims.csv"
    rows_out = []
    for root in W5_ROOTS:
        if root not in ORACLE_SCALES:
            continue
        scale = ORACLE_SCALES[root]
        step_path = steps_dir / f"{root}.stp"
        if not step_path.exists():
            print(f"  missing STEP for {root}")
            continue
        bbox = _cloud_bbox(step_path)
        if bbox is None:
            print(f"  no points in {step_path.name}")
            continue
        (full_lo, full_hi), robust, npts = bbox
        # vela/swbd are clean exports: the full extent is the frame. The
        # flooding/bow exports carry +-1e6 outlier points, so they get no
        # absolute-frame check (scale None).
        lo, hi = full_lo, full_hi
        axis_spans = [hi[i] - lo[i] for i in range(3)]
        before = _walk_counts(docs, root, law_c=False)
        after = _walk_counts(docs, root, law_c=True)
        if len(before["rows"]) != len(after["rows"]):
            print(f"  {root}: row count changed between laws — skipping")
            continue
        for b_row, row in zip(before["rows"], after["rows"]):
            t = row["transform"]
            status = row["placement_status"]
            status_before = b_row["placement_status"]
            detail = row.get("classification_detail") or ""
            bbox_lo = f"({lo[0]:.4f}, {lo[1]:.4f}, {lo[2]:.4f})"
            bbox_hi = f"({hi[0]:.4f}, {hi[1]:.4f}, {hi[2]:.4f})"
            if status == "placed" and t is not None and scale is not None:
                # placed translation in the document frame (mm) -> STEP units
                tp = (t[0] / scale, t[1] / scale, t[2] / scale)
                inside = all(lo[i] <= tp[i] <= hi[i] for i in range(3))
                if inside:
                    error = 0.0
                else:
                    d = [max(lo[i] - tp[i], 0.0, tp[i] - hi[i]) for i in range(3)]
                    error = math.dist([0, 0, 0], d) * scale
                rows_out.append(
                    [root, row["name"], row["depth"], status_before, "placed",
                     f"({t[0]:.6f}, {t[1]:.6f}, {t[2]:.6f})", npts,
                     bbox_lo, bbox_hi, f"{error:.3f}", ""]
                )
            elif "connector-frame records" in detail:
                # The refused connector body: what the pre-W5 law would have
                # bound, and the scale-free contradiction against the export.
                recs = fa.parse_position_matrix_records(
                    docs.get(row["placing_doc"], b"")
                )
                body_t = recs[0]["translation"] if recs else None
                note = "refused-connector"
                if body_t is not None:
                    z_ratio = (
                        body_t[2] / axis_spans[2] if axis_spans[2] > 0 else None
                    )
                    note = (
                        f"refused-connector; T_z / exported Z-span = {z_ratio:.1f}x"
                        if z_ratio and scale is not None
                        else "refused-connector (outlier-polluted export)"
                    )
                rows_out.append(
                    [root, row["name"], row["depth"], status_before, "identity",
                     f"({body_t[0]:.6f}, {body_t[1]:.6f}, {body_t[2]:.6f})"
                     if body_t else "none", npts, bbox_lo, bbox_hi,
                     "frame-outside" if scale else "n/a", note]
                )
            else:
                rows_out.append(
                    [root, row["name"], row["depth"], status_before, status, "none",
                     npts, bbox_lo, bbox_hi,
                     "0.000" if scale else "n/a",
                     "identity" if scale else "identity (outlier-polluted export)"]
                )
    out_csv.write_text("")
    with out_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["root", "instance", "depth", "status_before", "status_after",
             "transform_T_mm", "step_n_points", "step_bbox_min",
             "step_bbox_max", "position_error_mm", "note"]
        )
        w.writerows(rows_out)
    print(f"  {out_csv.relative_to(REPO)}: {len(rows_out)} instance rows")
    return 0


def _canonical_sha(payload: dict) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def parity(directory: Path) -> int:
    docs = load_docs(directory)
    binary = FIDELITY_CLI
    if not binary.exists():
        print(f"fidelity-cli not built: {binary}")
        return 1
    ok = True
    for root in W5_ROOTS:
        if root not in docs:
            print(f"  missing root document: {root}")
            continue
        py = _canonical_sha(fa.resolve_owned_assembly(root, docs))
        proc = subprocess.run(
            [str(binary), "tree", root, str(directory)],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            print(f"  {root}: fidelity-cli failed: {proc.stderr.strip()[:120]}")
            ok = False
            continue
        rs = _canonical_sha(json.loads(proc.stdout))
        status = "match" if py == rs else "MISMATCH"
        ok = ok and py == rs
        print(f"  {root}: py={py[:16]} rust={rs[:16]} {status}")
    print("parity:", "byte-identical canonical JSON on all roots" if ok else "FAILED")
    return 0 if ok else 1


def selftest() -> int:
    """Synthetic law-C round trip: shared refusal, unique placement."""
    entry_tail = bytes([0xE7, 0xE8, 0xE8, 0xE8]) * 2 + bytes([0xE7])
    def entry(t: tuple[float, float, float]) -> bytes:
        import struct as _s
        stream = bytearray(entry_tail)
        for v in t:
            stream.append(0xE6)
            stream.extend(_s.pack("<d", v))
        return fa.POSITION_EXPLICIT_HEADER + b"\x8d\x81" + bytes(stream) + b"\xfe"

    def doc(name: str, names, entries: bytes) -> bytes:
        items = bytearray()
        for text in ("CATCatalogManager", "catalogManager", "catalogLinks", "",
                     "ASMPRODUCT", "ASMProduct", "_ViewsList", "_Connectors",
                     "_RepresentedBy", "_Component", "_PartNumber"):
            items += fa.encode_short_item(text)
        items += fa.encode_short_item(name)
        for text in ("_BagRepsList", "_PrdVersion", "_PubConnectors",
                     "_AttrForLiterals", "_RefProduct", "_Disciplines",
                     "PRDBAGREP", "3DIC", "_Reps", "_InstanceName"):
            items += fa.encode_short_item(text)
        for text in names:
            items += fa.encode_short_item(text)
        items += fa.encode_short_item("IsRoot")
        payload = fa.encode_structure_pool_record(bytes(items)) + entries
        return fa.build_catfile(payload=payload, identity_name2=name)

    entry12 = entry((12.5, 0.0, 14.4))
    docs = {
        "Solo": doc("Solo", ("Widget", "Bracket"), entry12 * 2),
        "Elsewhere": doc("Elsewhere", ("Nut",), entry12),
    }
    tree = fa.resolve_owned_assembly("Solo", docs)
    assert tree["placed_instances"] == 0, tree["placed_instances"]
    assert tree["identity_instances"] == 2
    assert any(
        w["class"] == "connector-frame-records-v5r26" for w in tree["warnings"]
    )
    # unique body still places
    docs2 = {
        "Solo": doc("Solo", ("Widget", "Bracket"), entry12 * 2),
        "Elsewhere": doc("Elsewhere", ("Nut",), entry((1.0, 2.0, 3.0))),
    }
    tree2 = fa.resolve_owned_assembly("Solo", docs2)
    assert tree2["placed_instances"] == 2, tree2["placed_instances"]
    print("selftest ok: shared refused, unique places")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--census", type=Path, metavar="DIR")
    mode.add_argument("--walk", type=Path, metavar="DIR")
    mode.add_argument("--oracle", nargs=2, type=Path, metavar=("DIR", "STEPS"))
    mode.add_argument("--parity", type=Path, metavar="DIR")
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.census:
        return census(args.census)
    if args.walk:
        return walk_delta(args.walk)
    if args.oracle:
        return oracle_check(args.oracle[0], args.oracle[1])
    return parity(args.parity)


if __name__ == "__main__":
    sys.exit(main())
