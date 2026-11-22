#!/usr/bin/env python3
"""P3.2 probe: W9 STEP-oracle join over the assemblies (marathon v4).

Read-only. W9 (marathon round v4) deliverable evidence, continuing W5 law C
(`scripts/triage/p30_step_oracle.py`, `p31_lawc_census.py`):

* ``--join DIR STEPS_DIR``: per-instance join of the binary walk rows
  (``resolve_owned_assembly``) against every snapshot ``.stp`` export, keyed
  by (parent product, instance name). Per joined instance: the walk
  placement status, the STEP transform class (identity / rotated), the
  rotation error of the bound matrix against the STEP per-instance rotation,
  and, for ``placed`` rows, the W5 bbox-containment position check. Writes
  ``docs/evidence/data/w9-step-oracle-join-claims.csv``.
* ``--rejected-census DIR``: the corpus-wide count of ``_Position`` ``8d81``
  records that the proper-rotation gate rejects (mirror det<0, scale != 1,
  non-orthonormal) — W9 hypothesis 1's negative evidence. Writes
  ``docs/evidence/data/w9-rejected-matrix-census-claims.csv``.
* ``--body-census DIR``: per matrix body of the walked corpus, the rotation
  class (identity / angle), the translation, and the per-carrying-document
  ``#records == #own(D)`` count-match state — the law-R evidence table.
  Writes ``docs/evidence/data/w9-shared-body-rotation-census-claims.csv``.
* ``--walk-delta DIR``: per walked root, walk-level placement counts under
  the committed W5 state (as recorded in
  ``docs/evidence/data/w5-walk-delta-claims.csv``) vs the W9 law-R state.
  Writes ``docs/evidence/data/w9-walk-delta-claims.csv``.
* ``--parity DIR``: canonical-JSON parity (sha256) of the Python walk vs the
  Rust ``fidelity-cli tree`` on the nine W9 roots.

The per-file STEP scale (raw value -> mm) follows the W5 convention: the
writer's unit clauses are inconsistent, so the scale that makes each export
self-consistent is recorded per root (CPR/Compart/Medio carry the
``SI_UNIT(.MILLI., .METRE.)`` clause and millimetre-sized values; MB81 and
the ``submarine-Tr-1700-S42-vela-Mast`` export carry metre-sized values with
no MILLI clause; vela raw = mm per the M2 reference bbox; flooding/bow keep
``None`` — their raw clouds carry +-1e6 outlier points).

Modes:
    python3 -I scripts/triage/p32_w9_step_oracle_join.py --join DIR STEPS_DIR
    python3 -I scripts/triage/p32_w9_step_oracle_join.py --rejected-census DIR
    python3 -I scripts/triage/p32_w9_step_oracle_join.py --body-census DIR
    python3 -I scripts/triage/p32_w9_step_oracle_join.py --walk-delta DIR
    python3 -I scripts/triage/p32_w9_step_oracle_join.py --parity DIR
    python3 -I scripts/triage/p32_w9_step_oracle_join.py --selftest
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "triage"))

import catpart.fixtures_assembly as fa  # noqa: E402
import p30_step_oracle as p30  # noqa: E402
import p31_lawc_census as p31  # noqa: E402

REPO = ROOT
DATA = REPO / "docs" / "evidence" / "data"

#: The nine snapshot STEP exports and the walked root each covers. The
#: ``submarine-Tr-1700-S42-vela-Mast`` file is a second export of the sail
#: assembly (root product ``VM-vela-Mast``, 33 NAUO, all identity) — a
#: cross-check of the W5 vela oracle, not a new root.
JOIN_ROOTS: dict[str, str] = {
    "VM-vela-Mast": "VM-vela-Mast",
    "MD-swbd-panel-0A1w": "MD-swbd-panel-0A1w",
    "BW-Flooding-compartment-sup": "BW-Flooding-compartment-sup",
    "BW-section-bow": "BW-section-bow",
    "MD-Compart-02A-mtu": "MD-Compart-02A-mtu",
    "MD-Control-power-room": "MD-Control-power-room",
    "MD-Medio-Stern": "MD-Medio-Stern",
    "MD-MTU-16V-652-MB81": "MD-MTU-16V-652-MB81",
    "submarine-Tr-1700-S42-vela-Mast": "VM-vela-Mast",
}

#: Per-STEP numeric scale (raw value -> mm), W5 convention. ``None`` = no
#: absolute-frame check (outlier-polluted cloud or foreign frame).
JOIN_SCALES: dict[str, float | None] = {
    "VM-vela-Mast": 1.0,
    "MD-swbd-panel-0A1w": 1000.0,
    "BW-Flooding-compartment-sup": None,
    "BW-section-bow": None,
    "MD-Compart-02A-mtu": 1.0,
    "MD-Control-power-room": 1.0,
    "MD-Medio-Stern": 1.0,
    "MD-MTU-16V-652-MB81": 1000.0,
    "submarine-Tr-1700-S42-vela-Mast": None,
}

#: The nine walked roots for the W9 parity seam.
W9_ROOTS = (
    "VM-vela-Mast",
    "MD-swbd-panel-0A1w",
    "BW-Flooding-compartment-sup",
    "BW-section-bow",
    "MD-MTU-16V-652-MB81",
    "MD-Compart-02A-mtu",
    "MD-Control-power-room",
    "MD-Medio-Stern",
)

FIDELITY_CLI = p31.FIDELITY_CLI


def _rotation_of_quat(q: list[float]) -> str:
    w = max(-1.0, min(1.0, q[0]))
    angle = 2.0 * math.degrees(math.acos(w))
    return "identity" if angle <= 1e-6 else f"{angle:.4f}deg"


def _rot_err_deg(a: list[list[float]], b: list[list[float]]) -> float:
    """Angle of A * B^T (two orthonormal rotations)."""
    tr = sum(a[i][k] * b[i][k] for i in range(3) for k in range(3))
    return math.degrees(math.acos(max(-1.0, min(1.0, (tr - 1.0) / 2.0))))


def _quat_to_mat(q: list[float]) -> list[list[float]]:
    w, x, y, z = q
    return [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]


def _containment_error(
    t_mm: tuple[float, float, float],
    bbox: tuple[tuple[float, float, float], tuple[float, float, float]],
) -> float:
    """0.0 when the point is inside the export bbox, else the distance to it."""
    (lo, hi) = bbox
    d = [max(lo[i] - t_mm[i], 0.0, t_mm[i] - hi[i]) for i in range(3)]
    return math.sqrt(sum(v * v for v in d))


def join(directory: Path, steps_dir: Path) -> int:
    docs = p31.load_docs(directory)
    out_csv = DATA / "w9-step-oracle-join-claims.csv"
    bboxes: dict[str, tuple | None] = {}
    rows_out: list[list] = []
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for stem, root in JOIN_ROOTS.items():
        step_path = steps_dir / f"{stem}.stp"
        if not step_path.exists():
            print(f"  missing STEP for {stem}")
            continue
        orc = p30.parse_step_assembly(step_path)
        scale = JOIN_SCALES[stem]
        if scale is not None:
            bbox = p31._cloud_bbox(step_path, sample_every=11)
            if bbox is not None:
                (lo, hi), _robust, _n = bbox
                # W5 convention: the placed translation t (mm) is divided by
                # the per-file scale and checked against the RAW export bbox
                # (same units as the export's own values).
                bboxes[stem] = (
                    (lo[0], lo[1], lo[2]),
                    (hi[0], hi[1], hi[2]),
                )
            else:
                bboxes[stem] = None
        else:
            bboxes[stem] = None
        walk = p31._walk_counts(docs, root, law_c=True)
        walk_by_key: dict[tuple[str, str], dict] = {}
        for row in walk["rows"]:
            walk_by_key.setdefault((row["placing_doc"], row["name"]), row)
        for inst in orc["instances"]:
            key = (inst["parent_product"], inst["name"])
            row = walk_by_key.get(key)
            status = row["placement_status"] if row else "no-walk-row"
            step_class = (
                "identity" if inst["identity"] is True
                else "rotated" if inst["identity"] is False
                else "no-transform"
            )
            rot_err = ""
            pos_err = ""
            detail = ""
            if row is None:
                detail = "instance outside the name-table walk (sub-product leaf)"
            elif step_class == "rotated":
                r_step = inst["transform"]["rot"]
                if status == "placed":
                    t = row["transform"]
                    r_bound = _quat_to_mat(t[3:7])
                    rot_err = f"{_rot_err_deg(r_bound, r_step):.6f}"
                    if stem in bboxes and bboxes[stem] is not None:
                        tp = (t[0] / scale, t[1] / scale, t[2] / scale)
                        pos_err = f"{_containment_error(tp, bboxes[stem]):.6f}"
                    else:
                        pos_err = "no-frame-check"
                else:
                    rot_err = "n/a"
                    pos_err = "n/a"
                    detail = (
                        f"STEP moves this instance; the walk status is {status}"
                    )
            totals[stem]["joined"] += 1 if row is not None else 0
            totals[stem]["step_rotated"] += step_class == "rotated"
            if status == "placed" and step_class == "rotated":
                totals[stem]["placed_rot_confirmed"] += (
                    1 if rot_err and float(rot_err) <= 1e-4 else 0
                )
            if status == "identity" and step_class == "rotated":
                totals[stem]["refuted_identity"] += 1
            rows_out.append(
                [stem, root, inst["name"], inst["parent_product"] or "",
                 status, step_class, rot_err, pos_err, detail]
            )
    with out_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["step_file", "walk_root", "instance_name", "parent_product",
             "walk_status", "step_transform", "rotation_error_deg",
             "position_error_raw", "detail"]
        )
        for r in rows_out:
            w.writerow(r)
    print(f"join: {len(rows_out)} instances across {len(JOIN_ROOTS)} exports")
    for stem in JOIN_ROOTS:
        t = totals.get(stem)
        if t:
            print(
                f"  {stem}: joined={t['joined']} step_rotated={t['step_rotated']} "
                f"placed_rot_confirmed={t['placed_rot_confirmed']} "
                f"refuted_identity={t['refuted_identity']}"
            )
    print(f"  {out_csv.relative_to(REPO)}")
    return 0


def _raw_position_records(data: bytes) -> list[tuple[str, list[list[float]]]]:
    """Every 8d81 explicit/identity record, WITHOUT the rotation gate."""
    out: list[tuple[str, list[list[float]]]] = []
    idx = 0
    while True:
        pos = data.find(b"\x8d\x81", idx)
        if pos < 0:
            break
        pre = data[max(0, pos - 8) : pos]
        if pre.endswith(fa.POSITION_IDENTITY_HEADER):
            kind = "identity"
        elif pre.endswith(fa.POSITION_EXPLICIT_HEADER):
            kind = "explicit"
        else:
            idx = pos + 2
            continue
        vals = fa._parse_run_length_floats(data[pos + 2 :], 12)
        if vals is not None:
            values, _consumed = vals
            out.append((kind, [values[0:3], values[3:6], values[6:9]]))
        idx = pos + 2
    return out


def _rejection_class(r: list[list[float]]) -> str:
    det = fa._det3(r)
    norms = [math.sqrt(sum(x * x for x in row)) for row in r]
    if abs(det) < 1e-9:
        return "singular"
    if det < 0:
        return "mirror-det-negative"
    if any(abs(n - 1.0) > 1e-4 for n in norms):
        return "scale-non-unit"
    return "non-orthonormal"


def rejected_census(directory: Path) -> int:
    docs = p31.load_docs(directory)
    out_csv = DATA / "w9-rejected-matrix-census-claims.csv"
    n_records = n_rejected = 0
    classes: dict[str, int] = defaultdict(int)
    with out_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["document", "n_records_raw", "n_records_accepted", "n_rejected",
             "rejected_classes"]
        )
        for name in sorted(docs):
            raw = _raw_position_records(docs[name])
            accepted = fa.parse_position_matrix_records(docs[name])
            n_rej = len(raw) - len(accepted)
            rej_classes = [
                f"{kind}:{_rejection_class(r)}"
                for kind, r in raw
                if not fa._is_proper_rotation(r)
            ]
            n_records += len(raw)
            n_rejected += n_rej
            for c in rej_classes:
                classes[c] += 1
            w.writerow(
                [name, len(raw), len(accepted), n_rej,
                 ";".join(rej_classes) or "none"]
            )
    print(
        f"rejected-census: {len(docs)} documents, {n_records} raw records, "
        f"{n_rejected} rejected by the proper-rotation gate, classes={dict(classes)}"
    )
    print(f"  {out_csv.relative_to(REPO)}")
    return 0


def body_census(directory: Path) -> int:
    docs = p31.load_docs(directory)
    out_csv = DATA / "w9-shared-body-rotation-census-claims.csv"
    tables: dict[str, dict | None] = {}
    for name in docs:
        data = docs[name]
        pool = fa.scan_structure_pool(data) if data else None
        tables[name] = fa.read_product_name_table(pool[2]) if pool else None
    child_tables = {
        n: {c: tables[c]["names"] for c in t["names"] if tables.get(c) is not None}
        for n, t in tables.items()
        if t
    }
    doc_recs: dict[str, list] = {
        name: fa.parse_position_matrix_records(docs[name]) for name in docs
    }
    body_docs: dict[bytes, set[str]] = defaultdict(set)
    for name, recs in doc_recs.items():
        for rec in recs:
            body_docs[rec["matrix"]].add(name)
    shared = {b for b, ds in body_docs.items() if len(ds) >= 2}

    def own(n: str) -> list[str]:
        t = tables.get(n)
        return fa.own_instance_names(t["names"], child_tables[n]) if t else []

    rows_out = []
    for body in sorted(shared, key=lambda b: -len(body_docs[b])):
        rec0 = next(r for r in doc_recs[sorted(body_docs[body])[0]]
                    if r["matrix"] == body)
        q = rec0["quaternion"]
        t = rec0["translation"]
        for doc_name in sorted(body_docs[body]):
            recs_d = [r for r in doc_recs[doc_name] if r["matrix"] == body]
            n_own = len(own(doc_name))
            rows_out.append([
                hashlib.sha256(body).hexdigest()[:16],
                len(body_docs[body]),
                _rotation_of_quat(q),
                f"({t[0]:.6f}, {t[1]:.6f}, {t[2]:.6f})",
                doc_name,
                len(recs_d),
                n_own,
                "count-matched" if len(recs_d) == n_own else "count-mismatch",
            ])
    with out_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["body_sha16", "n_documents", "rotation", "translation_mm",
             "document", "n_records", "n_own", "count_match"]
        )
        for r in rows_out:
            w.writerow(r)
    n_matched = sum(1 for r in rows_out if r[7] == "count-matched")
    print(
        f"body-census: {len(shared)} shared bodies, "
        f"{len(rows_out)} (body, document) rows, {n_matched} count-matched"
    )
    print(f"  {out_csv.relative_to(REPO)}")
    return 0


def walk_delta(directory: Path) -> int:
    docs = p31.load_docs(directory)
    out_csv = DATA / "w9-walk-delta-claims.csv"
    #: The committed W5 walk-level counts (w5-walk-delta-claims.csv).
    w5_committed = {
        "VM-vela-Mast": (0, 45, 0),
        "MD-swbd-panel-0A1w": (5, 33, 5),
        "BW-Flooding-compartment-sup": (0, 43, 11),
        "BW-section-bow": (0, 85, 0),
        "MD-MTU-16V-652-MB81": (0, 163, 38),
    }
    with out_csv.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["root", "total", "placed_w5", "identity_w5", "undecodable_w5",
             "placed_w9", "identity_w9", "undecodable_w9"]
        )
        for root in W9_ROOTS:
            if root not in docs:
                print(f"  missing root document: {root}")
                continue
            counts = p31._walk_counts(docs, root, law_c=True)
            placed = sum(1 for r in counts["rows"]
                         if r["placement_status"] == "placed")
            identity = sum(1 for r in counts["rows"]
                           if r["placement_status"] == "identity")
            undec = sum(1 for r in counts["rows"]
                        if r["placement_status"] == "undecodable")
            before = w5_committed.get(root)
            w.writerow(
                [root, counts["total"],
                 before[0] if before else "", before[1] if before else "",
                 before[2] if before else "",
                 placed, identity, undec]
            )
            delta = (
                f" (placed {before[0]}->{placed})" if before else " (new root)"
            )
            print(
                f"  {root}: total={counts['total']} placed={placed} "
                f"identity={identity} undec={undec}{delta}"
            )
    print(f"  {out_csv.relative_to(REPO)}")
    return 0


def parity(directory: Path) -> int:
    docs = p31.load_docs(directory)
    binary = FIDELITY_CLI
    if not binary.exists():
        print(f"fidelity-cli not built: {binary}")
        return 1
    ok = True
    for root in W9_ROOTS:
        if root not in docs:
            print(f"  missing root document: {root}")
            continue
        py = p31._canonical_sha(fa.resolve_owned_assembly(root, docs))
        proc = subprocess.run(
            [str(binary), "tree", root, str(directory)],
            capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            print(f"  {root}: fidelity-cli failed: {proc.stderr.strip()[:120]}")
            ok = False
            continue
        rs = p31._canonical_sha(json.loads(proc.stdout))
        status = "match" if py == rs else "MISMATCH"
        ok = ok and py == rs
        print(f"  {root}: py={py[:16]} rust={rs[:16]} {status}")
    print("parity:", "byte-identical canonical JSON on all roots" if ok else "FAILED")
    return 0 if ok else 1


def selftest() -> int:
    """Synthetic law-R round trip + rejected-matrix census on a mirror body."""
    tail9 = [0xE9, 0xE8, 0xE8, 0xE8, 0xE9, 0xE8, 0xE8, 0xE8, 0xE7]

    def rotated_entry(t: tuple[float, float, float]) -> bytes:
        stream = bytearray(tail9)
        for v in t:
            stream.append(0xE6)
            stream.extend(struct.pack("<d", v))
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

    entry = rotated_entry((-4682.6207, 0.0, 0.0))
    docs = {
        "Solo": doc("Solo", ("Widget", "Bracket"), entry * 2),
        "Elsewhere": doc("Elsewhere", ("Nut",), entry),
    }
    tree = fa.resolve_owned_assembly("Solo", docs)
    assert tree["placed_instances"] == 2, tree["placed_instances"]
    assert "rotation-witnessed shared placement (W9 law R)" in (
        tree["instances"][0]["classification_detail"]
    )
    # identity-rotation shared body: W5 refusal stands
    id_entry = fa.POSITION_EXPLICIT_HEADER + b"\x8d\x81" + bytes(
        [0xE7, 0xE8, 0xE8, 0xE8]) * 2 + bytes([0xE7]) + b"".join(
        b"\xe6" + struct.pack("<d", v) for v in (12.5, 0.0, 14.4)) + b"\xfe"
    docs2 = {
        "Solo": doc("Solo", ("Widget", "Bracket"), id_entry * 2),
        "Elsewhere": doc("Elsewhere", ("Nut",), id_entry),
    }
    tree2 = fa.resolve_owned_assembly("Solo", docs2)
    assert tree2["placed_instances"] == 0, tree2["placed_instances"]
    assert tree2["identity_instances"] == 2
    # rejected census: a mirror (det<0) matrix is counted and classified
    mirror = fa.POSITION_EXPLICIT_HEADER + b"\x8d\x81" + bytes(
        [0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE9]
    ) + b"".join(b"\xe6" + struct.pack("<d", v) for v in (10.0, 0.0, 0.0)) + b"\xfe"
    recs = fa.parse_position_matrix_records(mirror)
    assert len(recs) == 0, "the gate must reject the mirror matrix"
    raw = _raw_position_records(mirror)
    assert len(raw) == 1, raw
    assert _rejection_class(raw[0][1]) == "mirror-det-negative"
    print("selftest ok: law R places, identity-rot refused, mirror rejected")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--join", nargs=2, type=Path, metavar=("DIR", "STEPS_DIR"))
    mode.add_argument("--rejected-census", type=Path, metavar="DIR")
    mode.add_argument("--body-census", type=Path, metavar="DIR")
    mode.add_argument("--walk-delta", type=Path, metavar="DIR")
    mode.add_argument("--parity", type=Path, metavar="DIR")
    mode.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.join:
        return join(args.join[0], args.join[1])
    if args.rejected_census:
        return rejected_census(args.rejected_census)
    if args.body_census:
        return body_census(args.body_census)
    if args.walk_delta:
        return walk_delta(args.walk_delta)
    return parity(args.parity)


if __name__ == "__main__":
    sys.exit(main())
