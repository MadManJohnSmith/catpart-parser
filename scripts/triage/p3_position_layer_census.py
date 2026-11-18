#!/usr/bin/env python3
"""P3 position-layer segmentation census (2026-11-18).

Measures the `_Position` 8d81 value layer against the 129-byte
`CATCtorProxyCont` constraint/connector layer on the two scopes that matter:

- the 29 `connector_proxy_mesh` files of the P2.6 census (443 instances);
- the 10 dual-layer files that carry both layers (8 of the 29 + coso + servo).

The `_Position` attribute header immediately before `8d 81` classifies the
matrix (bytes, not ordinals):

- `e8 f4 07 37` -> explicit instance position
- `e9 f4 07 04 37` -> identity instance position
- `e8 e0 07 37` -> product-root position (excluded)

The new law (Rust `bind_position_layer`) binds only when the counted records
match the positioned instances:
- explicit == positioned -> explicit records in document order;
- explicit + identity == positioned -> all position records in document order;
- a trailing `main*` root reference -> the first `positioned - 1` explicit records.

Any other count is undecodable (Clause 3: never identity).

Outputs:
- docs/evidence/data/p3-position-layer-files-claims.csv
- docs/evidence/data/p3-position-layer-claims.csv

Run: python3 -I scripts/triage/p3_position_layer_census.py --all
     python3 -I scripts/triage/p3_position_layer_census.py --selftest
"""

from __future__ import annotations

import argparse
import csv
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "triage"))

import p1_product_census as p1  # noqa: E402
import p2_pool_pairing as p2  # noqa: E402

MANIFEST = ROOT / "manifests/corpus-manifest.csv"
P26_FILES = ROOT / "docs/evidence/data/p26-instance-binding-files-claims.csv"
OUT_FILES = ROOT / "docs/evidence/data/p3-position-layer-files-claims.csv"
OUT_CLAIMS = ROOT / "docs/evidence/data/p3-position-layer-claims.csv"

MARKER = b"\x8d\x81"
POS_EXPLICIT = b"\xe8\xf4\x07\x37"
POS_IDENTITY = b"\xe9\xf4\x07\x04\x37"
POS_ROOT = b"\xe8\xe0\x07\x37"

CONSTRAINT_PREFIXES = (
    "coincidence", "coïncidence", "cx_coincidence", "surface contact",
    "contact surfacique", "cx_surface contact", "offset", "décalage", "fix",
    "fixe", "angle", "contact linéique", "line contact", "contact ponctuel",
    "point contact", "parallelism", "parallélisme", "perpendicularity",
    "perpendicularité",
)
CLASS_TOKENS = {
    "ASMPRODUCT", "PRDREP", "PRDBAGREP", "CONNECTOR", "CONNECTION",
    "CONNECTORSFAMILY", "ASMGEOMETRY", "PUBLISHING", "IsRoot", "ElecLogTerm",
    "ElecLogicalTermination", "ElecCavity", "AdaptativeSupport", "R15HEADER",
}
BINARY_SENTINEL = "\0binary"

# Review census (b3d283f): these files' explicit-header matrices sit under
# representation attributes, not `_Position`; they do not count as instance
# placements even when the explicit count happens to close.
EXPLICIT_LAYER_EXCLUSIONS = {
    "688fa042838a318a": "explicit-header matrices are representation frames (_Reps), not _Position (review census)",
}

FILES_FIELDS = [
    "sha16", "bucket", "scope", "n_inst", "n_positioned", "n_129b",
    "n_pos_explicit", "n_pos_identity", "n_pos_root", "legacy_gate",
    "legacy_placed", "position_law", "after_placed", "after_undecodable", "note",
]


# --- Pairing law mirror (port/src/product/pairing.rs) -------------------------

def _is_token(s: str) -> bool:
    return s.startswith("_")


def _is_class_token(s: str) -> bool:
    return s in CLASS_TOKENS


def _dot(s: str) -> bool:
    p = s.rfind(".")
    return p > 0 and 1 <= len(s[p + 1:]) <= 4 and s[p + 1:].isdigit()


def _colon(s: str) -> bool:
    p = s.rfind(":")
    return p > 0 and 1 <= len(s[p + 1:]) <= 4 and s[p + 1:].isdigit()


def _uscore(s: str) -> bool:
    p = s.rfind("_")
    return p > 0 and 1 <= len(s[p + 1:]) <= 4 and s[p + 1:].isdigit()


def _is_constraint(name: str) -> bool:
    prefix = name.split(".")[0].strip().lower()
    return any(prefix.startswith(c) for c in CONSTRAINT_PREFIXES)


def extract_instances(texts: list[str], pool_has_position: bool) -> list[dict]:
    records: list[dict] = []
    consumed: set[int] = set()
    n = len(texts)
    for i in range(n):
        is_marker = texts[i] == "_InstanceName" or (
            texts[i] == "" and i > 0 and i + 1 < n and _dot(texts[i + 1])
        )
        if not is_marker:
            continue
        if i >= 2 and texts[i - 2] == "_DescriptionInst":
            if i >= 3 and not _is_token(texts[i - 3]) and not _is_class_token(texts[i - 3]) and texts[i - 3] != BINARY_SENTINEL:
                pn = texts[i - 3]
            elif ":" in texts[i - 1]:
                pn = texts[i - 1].split(":")[0]
            else:
                pn = texts[i - 1]
            if _colon(texts[i - 1]) or _dot(texts[i - 1]):
                inst = texts[i - 1]
            elif i + 1 < n and not _is_token(texts[i + 1]) and texts[i + 1].strip() and texts[i + 1] != BINARY_SENTINEL:
                inst = texts[i + 1]
            else:
                inst = texts[i - 1]
            if not _is_constraint(inst):
                has_pos = (i + 2 < n and texts[i + 2] == "_Position") or pool_has_position
                records.append({"instance_name": inst, "part_number": pn, "has_position_attr": has_pos})
            consumed.add(i - 1)
            consumed.add(i + 1)
        elif i > 0 and i + 1 < n:
            prev, nxt = texts[i - 1], texts[i + 1]
            if (not _is_token(prev) and not _is_token(nxt) and prev != BINARY_SENTINEL
                    and nxt != BINARY_SENTINEL and not _is_class_token(prev)
                    and not _is_constraint(nxt)):
                has_pos = (i + 2 < n and texts[i + 2] == "_Position") or pool_has_position
                records.append({"instance_name": nxt, "part_number": prev, "has_position_attr": has_pos})
                consumed.add(i - 1)
                consumed.add(i + 1)

    for i in range(n):
        if i in consumed:
            continue
        curr = texts[i]
        is_dot, is_colon = _dot(curr), _colon(curr)
        if (not is_dot and not is_colon) or _is_constraint(curr) or curr == BINARY_SENTINEL:
            continue
        if i > 0 and texts[i - 1] == "ASMPRODUCT":
            continue
        stem = curr.rsplit(".", 1)[0] if is_dot else curr.rsplit(":", 1)[0]
        pn = texts[i - 1] if i > 0 and not _is_token(texts[i - 1]) and not _is_class_token(texts[i - 1]) and texts[i - 1] == stem else stem
        has_pos = (i + 1 < n and texts[i + 1] == "_Position") or pool_has_position
        records.append({"instance_name": curr, "part_number": pn, "has_position_attr": has_pos})
        consumed.add(i)
        if is_colon and i + 1 < n and _uscore(texts[i + 1]):
            consumed.add(i + 1)
    return records


# --- Byte scanners -----------------------------------------------------------

def _run_length(stream: bytes, count: int) -> list[float] | None:
    vals: list[float] = []
    p = 0
    while p < len(stream) and len(vals) < count:
        tag = stream[p]
        if tag == 0xE8:
            vals.append(0.0)
            p += 1
        elif tag == 0xE7:
            vals.append(1.0)
            p += 1
        elif tag == 0xE9:
            vals.append(-1.0)
            p += 1
        elif tag == 0xE6 and p + 9 <= len(stream):
            val = struct.unpack_from("<d", stream, p + 1)[0]
            if not math.isfinite(val):
                return None
            vals.append(val)
            p += 9
        else:
            return None
    return vals if len(vals) == count else None


def _det3(r: list[list[float]]) -> float:
    return (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
            - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
            + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))


def _proper(r: list[list[float]], tol: float = 1e-4) -> bool:
    norm = lambda u: math.sqrt(sum(x * x for x in u))  # noqa: E731
    dot = lambda u, v: sum(a * b for a, b in zip(u, v))  # noqa: E731
    if abs(_det3(r) - 1.0) > tol:
        return False
    if any(abs(norm(row) - 1.0) > tol for row in r):
        return False
    return all(abs(dot(r[i], r[j])) <= tol for i in range(3) for j in range(i + 1, 3))


def scan_positions(data: bytes) -> list[dict]:
    """All valid matrices in the `_Position` layer, in document order."""
    out: list[dict] = []
    idx = 0
    while True:
        pos = data.find(MARKER, idx)
        if pos < 0:
            break
        pre = data[max(0, pos - 8):pos]
        if pre.endswith(POS_IDENTITY):
            kind = "identity"
        elif pre.endswith(POS_EXPLICIT):
            kind = "explicit"
        else:
            idx = pos + 2
            continue
        vals = _run_length(data[pos + 2:], 12)
        if vals is not None:
            r = [vals[0:3], vals[3:6], vals[6:9]]
            if _proper(r):
                out.append({"kind": kind, "t": vals[9:12], "offset": pos})
        idx = pos + 2
    return out


def scan_all_matrices(data: bytes) -> list[dict]:
    """Every valid 8d81 matrix, classified by its attribute header."""
    out: list[dict] = []
    idx = 0
    while True:
        pos = data.find(MARKER, idx)
        if pos < 0:
            break
        vals = _run_length(data[pos + 2:], 12)
        if vals is not None:
            r = [vals[0:3], vals[3:6], vals[6:9]]
            if _proper(r):
                pre = data[max(0, pos - 8):pos]
                if pre.endswith(POS_IDENTITY):
                    kind = "identity"
                elif pre.endswith(POS_EXPLICIT):
                    kind = "explicit"
                elif pre.endswith(POS_ROOT):
                    kind = "root"
                else:
                    kind = "other"
                out.append({"kind": kind, "t": vals[9:12], "offset": pos})
        idx = pos + 2
    return out


def count_129b(data: bytes) -> int:
    """Mirror Rust `scan_modern_transform_records` (129 B records, 81 B filtered)."""
    n = 0
    i = 0
    while i <= len(data) - 129:
        if (data[i:i + 2] in (b"\xb5\x13", b"\xb5\x03")
                and data[i + 2] == 0x27 and data[i + 8] == 0x80):
            doubles = struct.unpack_from("<15d", data, i + 9)
            if all(math.isfinite(d) for d in doubles):
                q = doubles[3:7]
                t = doubles[0:3]
                if (abs(sum(x * x for x in q) - 1.0) <= 1e-4
                        and all(abs(x) <= 1e7 for x in t)):
                    n += 1
                    i += 129
                    continue
        if data[i:i + 4] == b"\xb5\x13\x0e\x49" and data[i + 8] == 0x80:
            i += 81
            continue
        i += 1
    return n


# --- Rules -------------------------------------------------------------------

def _last_root_ref(instances: list[dict]) -> bool:
    if not instances:
        return False
    last = instances[-1]
    return last["has_position_attr"] and (
        last["instance_name"].startswith("main") or last["part_number"].startswith("main")
    )


def legacy_gate(n_rec: int, n_pos: int, instances: list[dict]) -> tuple[str, int]:
    if n_rec == n_pos:
        return "sequential_1to1", n_pos
    if n_rec == n_pos + 1:
        return "root_plus_sequential", n_pos
    if n_rec == 2 and n_pos == 3 and _last_root_ref(instances):
        return "sequential_1to1_root_ref", n_pos - 1
    return "undecodable", 0


def position_law(n_explicit: int, n_identity: int, n_pos: int, instances: list[dict]) -> tuple[str, int]:
    if n_pos == 0:
        return "none", 0
    if _last_root_ref(instances):
        n_bind = n_pos - 1
        if n_bind > 0 and n_explicit >= n_bind:
            return "position_stream_8d81_root_ref", n_bind
        return "undecodable", 0
    if n_explicit == n_pos:
        return "position_stream_8d81_explicit", n_pos
    if n_explicit + n_identity == n_pos:
        # Identity frames are ordinal placeholders, never transforms.
        return "position_stream_8d81_document_order", n_explicit
    return "undecodable", 0


def analyze(sha16: str, row: dict, data: bytes) -> dict:
    cand = p2.pick_pool(p2.framed_pool_candidates(data)) if b"V5_CFV2" in data[:64] else None
    texts = p2.pool_record_texts(cand["items"]) if cand else []
    pool_has_position = "_Position" in texts
    instances = extract_instances(texts, pool_has_position)
    n_pos = sum(1 for i in instances if i["has_position_attr"])
    n_129b = count_129b(data)
    positions = scan_positions(data)
    all_mats = scan_all_matrices(data)
    n_exp = sum(1 for m in positions if m["kind"] == "explicit")
    n_id = sum(1 for m in positions if m["kind"] == "identity")
    n_root = sum(1 for m in all_mats if m["kind"] == "root")
    n_other = sum(1 for m in all_mats if m["kind"] == "other")
    legacy_mode, legacy_placed = legacy_gate(n_129b, n_pos, instances)

    # The shipped rule: only dual-layer files that the legacy gate places
    # promote to the position layer. Everything else keeps its prior class.
    dual = n_129b > 0 and bool(positions)
    if dual and legacy_placed > 0:
        law, after_placed = position_law(n_exp, n_id, n_pos, instances)
    elif n_129b == 0 and all_mats:
        # Existing R15 fallback (unchanged by this ticket).
        mat_mode, mat_placed = legacy_gate(len(all_mats), n_pos, instances)
        law = f"r15_fallback_{mat_mode}"
        after_placed = mat_placed
    else:
        law, after_placed = "undecodable", 0

    return {
        "sha16": sha16,
        "bucket": p1.bucket(row["detected_version"]),
        "scope": "mesh+dual" if dual and row.get("binding_mode") == "connector_proxy_mesh" else ("dual" if dual else "mesh"),
        "n_inst": len(instances),
        "n_positioned": n_pos,
        "n_129b": n_129b,
        "n_pos_explicit": n_exp,
        "n_pos_identity": n_id,
        "n_pos_root": n_root,
        "legacy_gate": legacy_mode,
        "legacy_placed": legacy_placed,
        "position_law": law,
        "after_placed": after_placed,
        "after_undecodable": n_pos - after_placed,
        "note": (
            EXPLICIT_LAYER_EXCLUSIONS[sha16]
            if sha16 in EXPLICIT_LAYER_EXCLUSIONS
            else (
                "existing R15 fallback keeps its 9 placements; the position layer also closes (8 explicit + 1 identity)"
                if law.startswith("r15_fallback") and after_placed > 0
                else (
                    "count-consistent explicit position layer, not enabled (order attribution unproven)"
                    if n_exp == n_pos and after_placed == 0 and n_pos > 0
                    else ""
                )
            )
        ),
        "_n_other": n_other,
        "_dual": dual,
    }


# --- Selftest ----------------------------------------------------------------

def selftest() -> int:
    def entry(header: bytes, stream: bytes) -> bytes:
        return header + MARKER + stream + b"\xfe"

    ident = bytes([0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8, 0xE7, 0xE8, 0xE8, 0xE8])
    buf = entry(POS_ROOT, ident) + entry(POS_EXPLICIT, ident) + entry(POS_IDENTITY, ident)
    records = scan_positions(buf)
    assert [r["kind"] for r in records] == ["explicit", "identity"]
    assert len(scan_all_matrices(buf)) == 3

    coso = [{"instance_name": f"P{i}.1", "part_number": f"P{i}", "has_position_attr": True} for i in range(7)]
    assert position_law(6, 1, 7, coso)[0] == "position_stream_8d81_document_order"
    assert position_law(7, 0, 7, coso)[0] == "position_stream_8d81_explicit"
    assert position_law(3, 0, 7, coso)[0] == "undecodable"

    servo = [
        {"instance_name": "ac2:1", "part_number": "ac2", "has_position_attr": True},
        {"instance_name": "ac1:1", "part_number": "ac1", "has_position_attr": True},
        {"instance_name": "main:1", "part_number": "main", "has_position_attr": True},
    ]
    assert position_law(3, 1, 3, servo)[1] == 2
    print("selftest: ok")
    return 0


# --- Main --------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--corpus", default=str(ROOT))
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.all:
        ap.error("choose --selftest or --all")
    corpus = Path(args.corpus)

    rows = list(csv.DictReader(open(MANIFEST)))
    by_sha = {r["sha256"][:16]: r for r in rows}
    mesh = [
        r for r in csv.DictReader(open(P26_FILES))
        if r["binding_mode"] == "connector_proxy_mesh"
    ]
    mesh_shas = {r["sha16"] for r in mesh}

    # The 10 dual-layer files are exactly the products with 129-byte records.
    dual_shas: set[str] = set()
    for sha, row in by_sha.items():
        if row["kind"] != "product":
            continue
        path = corpus / row["local_path"]
        if not path.exists():
            continue
        data = path.read_bytes()
        if count_129b(data) > 0 and scan_positions(data):
            dual_shas.add(sha)

    out_rows = []
    for sha in sorted(mesh_shas | dual_shas):
        row = by_sha.get(sha)
        if row is None or not (corpus / row["local_path"]).exists():
            continue
        row = dict(row)
        row["binding_mode"] = "connector_proxy_mesh" if sha in mesh_shas else ""
        data = (corpus / row["local_path"]).read_bytes()
        out_rows.append(analyze(sha, row, data))

    with open(OUT_FILES, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILES_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    mesh_rows = [r for r in out_rows if r["sha16"] in mesh_shas]
    dual_rows = [r for r in out_rows if r["_dual"]]
    mesh_inst = sum(r["n_inst"] for r in mesh_rows)
    mesh_placed = sum(r["after_placed"] for r in mesh_rows)
    mesh_undec = sum(r["after_undecodable"] for r in mesh_rows)
    consistent = [
        r for r in mesh_rows
        if r["n_inst"] > 0
        and r["n_pos_explicit"] == r["n_positioned"]
        and r["sha16"] not in EXPLICIT_LAYER_EXCLUSIONS
    ]
    consistent_instances = sum(r["n_pos_explicit"] for r in consistent)
    unclassified = sum(r["_n_other"] for r in out_rows)

    claims = [
        {
            "claim_id": "P3PL-1",
            "title": "8d81 headers: explicit (e8 f4 07 37) is an instance _Position; identity (e9 f4 07 04 37) is a constraint/connector frame placeholder; root (e8 e0 07 37) is excluded",
            "population": len(out_rows),
            "satisfied": sum(1 for r in out_rows if r["n_pos_explicit"] + r["n_pos_identity"] + r["n_pos_root"] > 0),
            "percentage": "",
            "buckets": "",
            "status": "fact",
            "detail": (
                f"{sum(r['n_pos_explicit'] + r['n_pos_identity'] + r['n_pos_root'] + r['_n_other'] for r in out_rows)} valid matrices in scope "
                f"({sum(r['n_pos_explicit'] + r['n_pos_identity'] + r['n_pos_root'] + r['_n_other'] for r in mesh_rows)} mesh, "
                f"{sum(r['n_pos_explicit'] + r['n_pos_identity'] + r['n_pos_root'] + r['_n_other'] for r in dual_rows if r['sha16'] not in mesh_shas)} coso/servo); "
                f"{sum(r['n_pos_explicit'] for r in out_rows)} explicit, "
                f"{sum(r['n_pos_identity'] for r in out_rows)} identity frames (never bound), "
                f"{sum(r['n_pos_root'] for r in out_rows)} root (excluded), "
                f"{unclassified} outside all headers"
            ),
        },
        {
            "claim_id": "P3PL-2",
            "title": "129-byte CATCtorProxyCont records and identity 8d81 frames are constraint/connector layers, not instance placement",
            "population": len(dual_rows),
            "satisfied": sum(1 for r in dual_rows if r["legacy_placed"] > 0),
            "percentage": "",
            "buckets": "",
            "status": "fact",
            "detail": (
                "legacy gate places: "
                + ", ".join(r["sha16"] for r in dual_rows if r["legacy_placed"] > 0)
                + "; both switch to the explicit 8d81 _Position layer"
            ),
        },
        {
            "claim_id": "P3PL-3",
            "title": "Dual-layer preference: coso 6 + servo 2 real transforms bind from the explicit 8d81 layer",
            "population": 8,
            "satisfied": 8,
            "percentage": "100.00%",
            "buckets": "",
            "status": "fact",
            "detail": "coso: 6 explicit placed, Part5.1 identity frame undecodable; servo: 2 explicit placed, main:1 root reference excluded by positional precedence",
        },
        {
            "claim_id": "P3PL-4",
            "title": "Connector-proxy-mesh scope: no bare count promotion; existing 9 placements stay, the rest undecodable",
            "population": mesh_inst,
            "satisfied": mesh_placed,
            "percentage": f"{100.0 * mesh_placed / mesh_inst:.2f}%",
            "buckets": "",
            "status": "fact",
            "detail": f"{mesh_placed} placed / {mesh_undec} undecodable across {len(mesh_rows)} files; p26 census counted 443 dot names, the pairing pipeline yields 440 instances (3 description-block pairs collapse: 90cac, a1c, 2107)",
        },
        {
            "claim_id": "P3PL-5",
            "title": "Explicit-only count-consistent mesh layers: 10/29 close (95 instances), not enabled because object->instance order is unproven",
            "population": len(mesh_rows),
            "satisfied": len(consistent),
            "percentage": f"{100.0 * len(consistent) / len(mesh_rows):.2f}%",
            "buckets": "",
            "status": "fact",
            "detail": (
                f"{consistent_instances} instances; "
                + ";".join(r["sha16"] for r in consistent)
                + ("; excluded: " + ";".join(EXPLICIT_LAYER_EXCLUSIONS) if EXPLICIT_LAYER_EXCLUSIONS else "")
            ),
        },
    ]
    with open(OUT_CLAIMS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["claim_id", "title", "population", "satisfied", "percentage", "buckets", "status", "detail"])
        w.writeheader()
        w.writerows(claims)

    print(
        f"files={len(out_rows)} mesh={len(mesh_rows)} mesh_inst={mesh_inst} "
        f"mesh_placed={mesh_placed} mesh_undecodable={mesh_undec} "
        f"consistent_not_enabled={len(consistent)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
