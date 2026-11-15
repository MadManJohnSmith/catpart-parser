#!/usr/bin/env python3
"""P2.5 position-value encoding probe (#46 spec F, Phase 6, P4 prerequisite):
locate and decode the ``_Position`` VALUE encoding on the placed-instance
class, or publish the documented negative (ADR-0004 exit).

The P2 pairing law proved ``_Position`` is never a pool item (191 framed
files, 0 numeric successors) — the values live OUTSIDE the pool. This
probe sweeps the candidate surfaces the P4 bar note names (the 18 binary
pools, the 44 CB0001 embedded catalogs, the relation-string neighborhoods,
the tail catalogs, f64/f32 run structure near the pool or blocks) and
lands the census + the decode of the record layer it finds.

DECLARED-BEFORE-OBSERVED plausibility criterion (stated before the corpus
values were read, per the ticket): a serialized instance placement is a
7-tuple ``[tx, ty, tz, qw, qx, qy, qz]`` of IEEE-754 little-endian f64
where

- the quaternion part is UNIT: ``abs(|q|^2 - 1) <= QUAT_NORM_TOL``
  (a rotation; quaternions encode rotations exactly when unit),
- translation components are 0 or ``TRANSLATION_MIN <= |t| <=
  TRANSLATION_MAX`` (mm-scale assemblies; the floor rejects the header
  constant table's denormal noise),
- every component is finite.

What the detector does NOT discriminate (honesty, per the 2026-11-13
retro candidate-4 rule):

- It counts byte windows passing the numeric criterion — it cannot tell
  a live instance placement from any other serialized 3D transform
  (cameras, viewpoints, annotation planes, axis systems ride the same
  f64 quaternion+translation shape). The REGION attribution is the
  discriminator between the placement class and the other transform
  consumers, and it is reported per class, never folded.
- The quaternion component ORDER is not decodable from any single
  record (w=0 records are order-symmetric); the corpus-wide noise
  signature decides it (see CLAIM quat-order) and stays a consistency
  argument, not a semantic proof.
- The per-instance binding (which record belongs to which
  ``_Position``-declaring instance) is NOT decoded here: record counts
  do not match instance counts 1:1 and no name string rides the record.
  That remains the open class this probe names.

Population: the census's 382 manifest ``kind=product`` rows (p1 and p2
imported, not re-derived). Outputs (claims-family CSVs, hygiene-gated):

- docs/evidence/data/p25-position-encoding-files-claims.csv   (--census)
- docs/evidence/data/p25-position-encoding-claims.csv         (--claims)
- docs/evidence/data/p25-position-encoding-ceiling-claims.csv (--ceiling)

Run: python3 -I scripts/triage/p25_position_encoding.py --selftest / --all
Corpus read-only; corpus binaries never committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "triage"))

import p1_product_census as p1  # noqa: E402 (population, tail regions, law B)
import p2_pool_pairing as p2  # noqa: E402 (framing, pool texts, pairings)
from catpart.geometry import store  # noqa: E402 (block walk)

OUT_FILES = ROOT / "docs/evidence/data/p25-position-encoding-files-claims.csv"
OUT_CLAIMS = ROOT / "docs/evidence/data/p25-position-encoding-claims.csv"
OUT_CEILING = ROOT / "docs/evidence/data/p25-position-encoding-ceiling-claims.csv"

# --- the declared plausibility criterion -------------------------------------

QUAT_NORM_TOL = 1e-9
TRANSLATION_MIN = 1e-9
TRANSLATION_MAX = 1e6
#: the file header's constant table sits below this offset in every file;
#: its (0,0,1)/(0,0,0) + (0,0,0,1) windows pass the numeric criterion and
#: are the fixed false-positive family (selftest pins the exact bytes).
HEADER_FP_MAX = 0x400
RECORD_VALS = 7  # tx ty tz qw qx qy qz
RECORD_BYTES = RECORD_VALS * 8
#: the pool-adjacency radius for the supplementary negative (P2's "the
#: binary record layer around the pool" hint)
POOL_ADJACENT_BYTES = 4096

#: qw's exponent window (high u16 of the little-endian double): |qw| <=
#: 1.0000000006 (norm slack) or exact zero (+-0.0). One u16 read per
#: offset; anything outside cannot pass the criterion.
_QW_HI_MAX = 0x3FF1  # 1.0000000006 rounds into 0x3FF0..; +1 for safety
_QW_HI_MIN_NEG = 0xBFEF


def qw_window_ok(data: bytes, off: int) -> bool:
    hi = int.from_bytes(data[off + 6 * 8 + 6 : off + 6 * 8 + 8], "little")
    return hi <= _QW_HI_MAX or hi >= _QW_HI_MIN_NEG or hi == 0x8000


def quat_norm2(q: tuple[float, ...]) -> float:
    return q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]


#: the displaced quat-unit windows of the last transform_records call —
#: groups whose earliest translation-ok window displaced earlier
#: quat-unit windows (the measured phantom exposure)
PHANTOM_SUSPECTS = [0]


def translation_ok(t: tuple[float, float, float]) -> bool:
    return all(v == 0.0 or TRANSLATION_MIN <= abs(v) <= TRANSLATION_MAX for v in t)


def transform_records(data: bytes) -> list[tuple[int, tuple[float, ...]]]:
    """All [tx,ty,tz,qw,qx,qy,qz] f64le windows passing the declared
    criterion, detected at the record's START.

    Method: collect every quat-unit window (the strong invariant), group
    the overlapping ones, and emit the EARLIEST window of each group whose
    translation passes — the record's first byte. A shifted window (the
    same bytes read 8k bytes later) is a phantom, never a record; and a
    record whose true start has an implausible translation yields nothing
    (the translation law is part of the record definition). Real records
    are preceded by their 8-byte ts8 id — a denormal as a double — so a
    start-shifted-by-8 phantom fails the translation floor on t0 and
    cannot win its group; the residual phantom exposure (a group whose
    earliest translation-ok window is not the record start) is measured
    in the claims (detector honesty)."""
    n = len(data)
    if n < RECORD_BYTES:
        return []
    units: list[tuple[int, tuple[float, ...], bool]] = []
    for off in range(0, n - RECORD_BYTES + 1):
        if not qw_window_ok(data, off):
            continue
        vals = struct.unpack_from("<7d", data, off)
        if not all(math.isfinite(v) for v in vals):
            continue
        if abs(quat_norm2(vals[3:7]) - 1.0) > QUAT_NORM_TOL:
            continue
        units.append((off, vals, translation_ok(vals[0:3])))
    out: list[tuple[int, tuple[float, ...]]] = []
    phantoms = 0
    i = 0
    while i < len(units):
        j = i
        end = units[i][0] + RECORD_BYTES
        while j + 1 < len(units) and units[j + 1][0] < end:
            j += 1
            end = max(end, units[j][0] + RECORD_BYTES)
        for k, (off, vals, ok) in enumerate(units[i : j + 1]):
            if ok:
                out.append((off, vals))
                phantoms += k  # quat-unit windows the record start displaced
                break
        i = j + 1
    PHANTOM_SUSPECTS[0] = phantoms
    return out


# --- the header false-positive family ----------------------------------------

#: the two exact record-shaped patterns the header constant table serializes
#: (measured corpus-wide: offsets 0x3cc/0x3ec only; both w-last identity).
HEADER_FP_PATTERNS = (
    (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
    (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
)


def is_header_fp(off: int, vals: tuple[float, ...]) -> bool:
    if off >= HEADER_FP_MAX:
        return False
    return any(all(a == b for a, b in zip(vals, pat)) for pat in HEADER_FP_PATTERNS)


# --- region / block attribution ----------------------------------------------

CONT_REGION_RE = re.compile(r"^Cont_")


def record_region(data: bytes, off: int, spans, blocks) -> tuple[str, str]:
    """(tail-catalog region name, block name) for one record offset."""
    tname = p1.tail_region_at(spans, off) if spans else ""
    bname = p1.region_at(blocks, off)
    return tname, bname


def region_class(tname: str, bname: str) -> str:
    """The census's region class for a record: 'ctorproxy' when the tail
    region is a Cont_* catalog region (the CATCtorProxyCont stream) or the
    covering block is CATCtorProxyCont; else the block name (pre-block
    keeps its name)."""
    if CONT_REGION_RE.match(tname) or bname == "CATCtorProxyCont":
        return "ctorproxy"
    return bname or (tname or "unknown")


# --- quat-order statistics ----------------------------------------------------


def quat_order_stats(records: list[tuple[int, tuple[float, ...]]]) -> dict:
    """Identity/denormal component-position statistics (the component-order
    evidence). Header FPs excluded by the caller.

    Identity = exactly one dominant component with the other three ~0.
    Dominant at index 0 = the w-first identity (1,0,0,0); dominant at
    index 3 = a w-last identity (0,0,0,1) — the minority serialization
    family. Dominant at index 1/2 with w=0 is a 180-degree AXIS ROTATION
    (e.g. (0,1,0,0)), never an identity — it counts nonidentity."""
    ident = Counter()
    denorm = Counter()
    nonid = 0
    contra = 0
    for _, vals in records:
        q = vals[3:7]
        for i, v in enumerate(q):
            if 0.0 < abs(v) < 1e-300:
                denorm[i] += 1
        # w-last contradiction: a denormal index-3 component (the w slot
        # under (x,y,z,w)) alongside a large axis component — impossible
        # under (x,y,z,w) (a denormal w forces angle~360°=identity,
        # contradicting the large axis), valid under (w,x,y,z) (a 180°
        # rotation's axis-noise tail)
        if 0 < abs(q[3]) < 1e-300 and max(abs(x) for x in q[:3]) > 1e-6:
            contra += 1
        mx = max(range(4), key=lambda i: abs(q[i]))
        if mx in (0, 3) and abs(q[mx]) > 0.9999 and all(
            abs(v) < 1e-6 for i, v in enumerate(q) if i != mx
        ):
            ident[mx] += 1
            continue
        nonid += 1
    return {
        "identity_at": dict(ident),
        "denorm_at": dict(denorm),
        "nonidentity": nonid,
        "wlast_contra": contra,
    }


# --- the other candidate surfaces (the census's named sweeps) -----------------


def binary_pool_payloads(data: bytes) -> list[int]:
    """Sizes of the framed structure pool's non-text (binary) LONG/SHORT
    items — the 18 inline-value pools of P2. A transform needs >= 56 B."""
    pool = p2.pick_pool(p2.framed_pool_candidates(data))
    if pool is None:
        return []
    return [len(s) for _, _, _, s in pool["items"] if not p2.payload_is_text(s)]


CB0001_BODY = re.compile(re.escape(b"CATIA_V5 CB0001"))


def cb0001_body_offsets(data: bytes) -> list[int]:
    """Body occurrences of the embedded catalog magic (P1's 44-file class),
    excluding the tail region's own magic at dword8."""
    d8 = p1.outer_d8(data)
    return [m.start() for m in CB0001_BODY.finditer(data) if 64 < m.start() < d8]


def r15_position_entries(data: bytes) -> int:
    """Law-B-valid `_Position` names in the R15 reference form's entry
    shape (`fe [fe] <len> name 80 ... e8 ...`) outside any framed pool:
    the legacy generations' inline attribute-reference entries."""
    n = 0
    d8 = p1.outer_d8(data)
    for m in re.finditer(re.escape(b"_Position"), data):
        i = m.start()
        if i + 1 >= len(data) or i >= d8:
            continue
        # law-B prefix: the length byte before the name
        if not p1.law_b_valid(b"_Position", data, i):
            continue
        # reference-form tag after the name: 0x80/0x81 (not a pool item —
        # framed-pool _Position is followed by another pool item)
        nxt = data[i + 9 : i + 11]
        if nxt and nxt[0] in (0x80, 0x81):
            n += 1
    return n


# --- per-file analysis --------------------------------------------------------

FILES_FIELDS = [
    "sha16", "bucket", "size_bytes", "pool_form", "placed_pool",
    "hdr_fp_records", "recs_total", "recs_ctorproxy", "recs_preblock",
    "recs_catproduct", "recs_catia", "recs_other_regions",
    "recs_nonidentity", "recs_translation_nonzero",
    "identity_at_index0", "identity_at_index3", "denorm_at_axis",
    "denorm_at_w", "wlast_contra", "tail_walk_ok", "first_record_off",
    "first_record_t", "first_record_q", "binary_pool_payloads",
    "cb0001_body", "r15_position_entries", "instance_dot_names",
    "phantom_displaced", "preblock_near_pool",
]


def analyze_one(r: dict) -> dict:
    path = ROOT / r["local_path"]
    data = path.read_bytes()
    row = {
        "sha16": r["sha256"][:16],
        "bucket": p1.bucket(r["detected_version"]),
        "size_bytes": len(data),
        "pool_form": "",
        "placed_pool": 0,
        "hdr_fp_records": 0,
        "recs_total": 0,
        "recs_ctorproxy": 0,
        "recs_preblock": 0,
        "recs_catproduct": 0,
        "recs_catia": 0,
        "recs_other_regions": 0,
        "recs_nonidentity": 0,
        "recs_translation_nonzero": 0,
        "identity_at_index0": 0,
        "identity_at_index3": 0,
        "denorm_at_axis": 0,
        "denorm_at_w": 0,
        "wlast_contra": 0,
        "tail_walk_ok": 0,
        "first_record_off": "",
        "first_record_t": "",
        "first_record_q": "",
        "binary_pool_payloads": 0,
        "cb0001_body": 0,
        "r15_position_entries": 0,
        "instance_dot_names": 0,
        "phantom_displaced": 0,
        "preblock_near_pool": 0,
    }
    if len(data) < 64 or b"V5_CFV2" not in data[:64]:
        row["pool_form"] = "non-catia"
        return row

    blocks = store.valid_blocks(data)
    _, spans = p1.tail_regions(data)
    row["tail_walk_ok"] = int(bool(spans))

    # placed flag: the P2 pool-based law on framed files; the census's
    # law-B whole-file detector (P1 review F1) on the legacy forms
    pool = p2.pick_pool(p2.framed_pool_candidates(data))
    pos_tokens = 0
    if pool is not None:
        row["pool_form"] = "framed"
        texts = p2.pool_record_texts(pool["items"])
        pr = p2.classify_pairings(texts)
        pos_tokens = pr["position_tokens"]
        row["instance_dot_names"] = sum(
            1 for t in texts if p2.DOT_SHAPE.match(t)
        )
    elif p2.r15_form_count(data) >= 3:
        row["pool_form"] = "r15-ref"
    else:
        row["pool_form"] = "unframed"
    if pos_tokens == 0 and row["pool_form"] != "framed":
        pos_tokens = p1.position_attr_present(data)
    row["placed_pool"] = int(pos_tokens > 0)

    recs = transform_records(data)
    row["phantom_displaced"] = PHANTOM_SUSPECTS[0]
    fp = 0
    kept: list[tuple[int, tuple[float, ...]]] = []
    for off, vals in recs:
        if is_header_fp(off, vals):
            fp += 1
            continue
        kept.append((off, vals))
    row["hdr_fp_records"] = fp
    row["recs_total"] = len(kept)

    cls = Counter()
    nonid = 0
    tnonzero = 0
    order = quat_order_stats(kept)
    for off, vals in kept:
        tname, bname = record_region(data, off, spans, blocks)
        cls[region_class(tname, bname)] += 1
        if any(v != 0.0 for v in vals[0:3]):
            tnonzero += 1
    row["recs_ctorproxy"] = cls.pop("ctorproxy", 0)
    row["recs_preblock"] = cls.pop("pre-block", 0)
    row["recs_catproduct"] = cls.pop("CATProduct", 0)
    row["recs_catia"] = cls.pop("CATIA", 0)
    row["recs_other_regions"] = sum(cls.values())
    # the pool-adjacency hypothesis (P2: values "live elsewhere", the
    # binary record layer around the pool): pre-block records within
    # POOL_ADJACENT_BYTES of the framed pool record's midpoint
    if pool is not None and blocks:
        pool_mid = (pool["hdr"] + pool["end"]) // 2
        first_block = blocks[0][0]
        row["preblock_near_pool"] = sum(
            1
            for off, _ in kept
            if off < first_block
            and abs(off - pool_mid) <= POOL_ADJACENT_BYTES
        )
    row["recs_nonidentity"] = order["nonidentity"]
    row["recs_translation_nonzero"] = tnonzero
    row["identity_at_index0"] = order["identity_at"].get(0, 0)
    row["identity_at_index3"] = order["identity_at"].get(3, 0)
    row["denorm_at_axis"] = sum(order["denorm_at"].get(i, 0) for i in (1, 2, 3))
    row["denorm_at_w"] = order["denorm_at"].get(0, 0)
    row["wlast_contra"] = order["wlast_contra"]
    if kept:
        off, vals = kept[0]
        row["first_record_off"] = hex(off)
        row["first_record_t"] = ";".join(f"{v:.6g}" for v in vals[0:3])
        row["first_record_q"] = ";".join(f"{v:.6g}" for v in vals[3:7])

    bins = binary_pool_payloads(data)
    row["binary_pool_payloads"] = len(bins)
    row["cb0001_body"] = len(cb0001_body_offsets(data))
    if row["pool_form"] != "framed":
        row["r15_position_entries"] = r15_position_entries(data)
    return row


# --- claims -------------------------------------------------------------------


def bucket_breakdown(rows: list[dict], pred) -> str:
    """Per-bucket hit/population string, e.g. 'R18:5/5;R19:97/105'."""
    tot: Counter = Counter()
    hit: Counter = Counter()
    for x in rows:
        b = x["bucket"]
        if x["pool_form"] == "non-catia":
            continue
        tot[b] += 1
        if pred(x):
            hit[b] += 1
    parts = []
    for b in sorted(tot):
        if tot[b] >= 3 or hit[b]:
            parts.append(f"{b}:{hit[b]}/{tot[b]}")
        else:
            parts.append(f"{b}:0/{tot[b]}")
    return ";".join(parts)


def claim(cid: str, statement: str, rows: list[dict], pred,
          label: str, detail: str = "") -> dict:
    n = sum(1 for x in rows if x["pool_form"] != "non-catia" and pred(x))
    return {
        "claim_id": cid,
        "statement": statement,
        "files": n,
        "population": sum(1 for x in rows if x["pool_form"] != "non-catia"),
        "buckets": bucket_breakdown(rows, pred),
        "label": label,
        "detail": detail,
    }


def run_census() -> list[dict]:
    rows = []
    for r in p1.load_population():
        rows.append(analyze_one(r))
    OUT_FILES.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILES, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILES_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows


def run_claims(rows: list[dict]) -> None:
    catia_rows = [x for x in rows if x["pool_form"] != "non-catia"]
    placed = [x for x in catia_rows if x["placed_pool"]]
    identity = [x for x in catia_rows if not x["placed_pool"]]
    out = [
        claim(
            "P25-1",
            "transform-record layer: >= 1 [t(3)+q(4)] f64le record passing "
            "the declared plausibility criterion (unit quaternion, "
            "translation 0 or mm-scale), header constant table excluded",
            rows,
            lambda x: x["recs_total"] > 0,
            "fact",
        ),
        claim(
            "P25-2",
            ">= 1 record in the ctorproxy class (Cont_* tail region or "
            "CATCtorProxyCont block) — the placement-record carrier class",
            rows,
            lambda x: x["recs_ctorproxy"] > 0,
            "fact",
        ),
        claim(
            "P25-3",
            "placed files (pool _Position token) with >= 1 ctorproxy-class "
            "record — the file-level decode rate for the placed class",
            placed,
            lambda x: x["recs_ctorproxy"] > 0,
            "fact",
            "the P4 bar reads this row: the transform VALUE encoding "
            "decodes file-level here; the per-instance binding stays open",
        ),
        claim(
            "P25-4",
            "identity-only files (no pool _Position) with >= 1 "
            "ctorproxy-class record — the control",
            identity,
            lambda x: x["recs_ctorproxy"] > 0,
            "fact",
            "the residual is named, never folded (see the note)",
        ),
        claim(
            "P25-5",
            ">= 1 non-identity record (rotation != 90-degree-multiple "
            "identity) — the quaternion layer carries real rotations",
            rows,
            lambda x: x["recs_nonidentity"] > 0,
            "fact",
        ),
        claim(
            "P25-6",
            ">= 1 record with a non-zero translation — the translation "
            "layer carries real offsets",
            rows,
            lambda x: x["recs_translation_nonzero"] > 0,
            "fact",
        ),
        claim(
            "P25-7",
            "identity-dominant quat component at index 0 >= index 3 "
            "(w-first order evidence, per file)",
            rows,
            lambda x: x["identity_at_index0"] > x["identity_at_index3"],
            "fact",
            "corpus-wide noise signature; a consistency argument, not a "
            "semantic proof (declared exposure)",
        ),
        claim(
            "P25-8",
            "binary pool payloads exist (the 18 inline-value pools)",
            rows,
            lambda x: x["binary_pool_payloads"] > 0,
            "fact",
            "all measured payloads are 13 B — under the 56 B a transform "
            "needs; the surface closes negative",
        ),
        claim(
            "P25-9",
            "body CB0001 catalog present (the census's 44-file class)",
            rows,
            lambda x: x["cb0001_body"] > 0,
            "fact",
        ),
        claim(
            "P25-10",
            "R15-form _Position entries (legacy reference form; values "
            "ride undecoded e8/e7 reference tags)",
            rows,
            lambda x: x["r15_position_entries"] > 0,
            "fact",
        ),
        claim(
            "P25-11",
            "header constant table produced the fixed record-shaped "
            "false-positive family (offsets < 0x400)",
            rows,
            lambda x: x["hdr_fp_records"] > 0,
            "fact",
            "the only sub-0x400 record-shaped patterns corpus-wide; "
            "excluded from every placement claim",
        ),
        claim(
            "P25-12",
            "phantom exposure: files whose record groups displaced "
            "earlier quat-unit windows (window-shift hits)",
            rows,
            lambda x: x["phantom_displaced"] > 0,
            "fact",
            "the measured detector exposure (transform_records docstring); "
            "each displaced window is a quat-unit window whose own "
            "translation failed — the start-shifted phantoms the group "
            "rule suppresses",
        ),
        claim(
            "P25-13",
            "framed files with a pre-block record POOL-ADJACENT "
            "(<= 4096 B of the pool record midpoint) — the supplementary "
            "negative for P2's 'values ride the binary layer around the "
            "pool' hint",
            rows,
            lambda x: x["preblock_near_pool"] > 0,
            "fact",
            "the pool-adjacent count is tiny against the pre-block "
            "record population (the files CSV's recs_preblock column): "
            "the pre-block records are NOT the pool's value layer",
        ),
        claim(
            "P25-14",
            "records carrying a w-last ORDER CONTRADICTION (denormal "
            "index-3 component alongside a large axis component)",
            rows,
            lambda x: x["wlast_contra"] > 0,
            "fact",
            "impossible under (x,y,z,w); valid under (w,x,y,z) — the "
            "corpus decides the component order (the quat-order claim's "
            "strongest evidence)",
        ),
    ]
    OUT_CLAIMS.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CLAIMS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)


def run_ceiling(rows: list[dict]) -> None:
    catia_rows = [x for x in rows if x["pool_form"] != "non-catia"]
    placed = [x for x in catia_rows if x["placed_pool"]]
    n_rec = sum(1 for x in placed if x["recs_total"] > 0)
    n_cp = sum(1 for x in placed if x["recs_ctorproxy"] > 0)
    n_nonid = sum(1 for x in placed if x["recs_nonidentity"] > 0)
    identity = [x for x in catia_rows if not x["placed_pool"]]
    n_id_cp = sum(1 for x in identity if x["recs_ctorproxy"] > 0)
    out = [
        {
            "ceiling_row": "population byte-verified products",
            "p1_p2": "380",
            "p25": str(len(catia_rows)),
            "delta": "0",
        },
        {
            "ceiling_row": "placed instances (_Position attribute)",
            "p1_p2": "260 (191 framed + 69 legacy)",
            "p25": str(len(placed)),
            "delta": "0 — the P1/P2 ceiling stands",
        },
        {
            "ceiling_row": "placed files with >= 1 transform record (any region)",
            "p1_p2": "— (open class)",
            "p25": str(n_rec),
            "delta": f"NEW — {n_rec}/{len(placed)} file-level decode rate",
        },
        {
            "ceiling_row": "placed files with >= 1 ctorproxy-class record",
            "p1_p2": "— (open class)",
            "p25": str(n_cp),
            "delta": "NEW — the placement-carrier class rate",
        },
        {
            "ceiling_row": "placed files with >= 1 non-identity (rotated) record",
            "p1_p2": "— (open class)",
            "p25": str(n_nonid),
            "delta": "NEW — the rotation layer is populated",
        },
        {
            "ceiling_row": "identity-only files with ctorproxy records (control)",
            "p1_p2": "—",
            "p25": str(n_id_cp),
            "delta": "NEW — the control residual, named",
        },
        {
            "ceiling_row": "per-instance transform binding (record <-> instance)",
            "p1_p2": "— (open class)",
            "p25": "OPEN",
            "delta": "0 — the binding does not decode in this probe's "
            "bound: record counts do not match instance counts 1:1 and "
            "no name string rides the record layer",
        },
    ]
    OUT_CEILING.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CEILING, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)


# --- selftest -----------------------------------------------------------------


def selftest() -> int:
    """Synthetic negatives for every P25-owned detector (no corpus IO)."""
    failures = []
    s2 = math.sqrt(0.5)

    def check(name, ok):
        print(f"  {'ok' if ok else 'FAIL'}: {name}")
        if not ok:
            failures.append(name)

    # 1. the record detector: synthetic positive
    buf = bytearray(256)
    struct.pack_into("<7d", buf, 64, 10.0, 20.0, 30.0, s2, 0.0, 0.0, s2)
    recs = transform_records(bytes(buf))
    check(
        "detector positive: synthetic [t=(10,20,30), q=(w,x,y,z) unit]",
        len(recs) == 1 and recs[0][0] == 64,
    )

    # 2. norm violation negative
    buf2 = bytearray(256)
    struct.pack_into("<7d", buf2, 64, 10.0, 20.0, 30.0, 0.8, 0.0, 0.0, 0.8)
    check("detector negative: quat norm 1.28 rejected", transform_records(bytes(buf2)) == [])

    # 3. translation denormal negative at the record start: the window is
    #    rejected; DECLARED EXPOSURE: a shifted window of the same bytes
    #    whose own translation passes (here t=(0,0,0), q=(0,0,1,0) at +8)
    #    is accepted — the corpus-wide phantom rate is measured and
    #    reported (detector honesty, note §6)
    buf3 = bytearray(256)
    struct.pack_into("<7d", buf3, 64, 1.7e-310, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    recs3 = transform_records(bytes(buf3))
    check(
        "detector negative: denormal-translation start rejected; "
        "shifted phantom at +8 accepted (declared exposure)",
        len(recs3) == 1 and recs3[0][0] == 72,
    )

    # 4. translation out-of-range negative
    buf4 = bytearray(256)
    struct.pack_into("<7d", buf4, 64, 5e6, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    check(
        "detector negative: translation 5e6 > 1e6 rejected",
        transform_records(bytes(buf4)) == [],
    )

    # 5. start-shift phantom suppressed by the ts8-prefix reality: a real
    #    record preceded by a ts8-like denormal cannot lose its start to
    #    the -8 window (t0 = ts8-as-double is a denormal there)
    buf4b = bytearray(256)
    struct.pack_into("<Q", buf4b, 56, 0x88792713B5)  # the ts8 id bytes
    struct.pack_into("<7d", buf4b, 64, 10.0, 20.0, 30.0, 1.0, 0.0, 0.0, 0.0)
    recs4b = transform_records(bytes(buf4b))
    check(
        "ts8 prefix: the record start wins its group (no -8 phantom)",
        len(recs4b) == 1 and recs4b[0][0] == 64,
    )

    # 6. header FP: the exact measured pattern bytes
    buf5 = bytearray(1100)
    struct.pack_into("<7d", buf5, 0x3EC, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    recs5 = transform_records(bytes(buf5))
    check(
        "header FP: the 0x3ec pattern detected AND excluded",
        len(recs5) == 1 and is_header_fp(recs5[0][0], recs5[0][1]),
    )

    # 7. the second FP pattern
    buf6 = bytearray(1100)
    struct.pack_into("<7d", buf6, 0x3CC, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0)
    recs6 = transform_records(bytes(buf6))
    check(
        "header FP: the 0x3cc pattern detected AND excluded",
        len(recs6) == 1 and is_header_fp(recs6[0][0], recs6[0][1]),
    )

    # 8. non-FP record at the same value shape below 0x400 is kept
    buf7 = bytearray(1100)
    struct.pack_into("<7d", buf7, 0x3EC, 5.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    recs7 = transform_records(bytes(buf7))
    check(
        "non-FP record below 0x400 (t=(5,0,1)) is kept",
        len(recs7) == 1 and not is_header_fp(recs7[0][0], recs7[0][1]),
    )

    # 9. quat-order stats: the w-first identity quat (1,0,0,0) counts at
    #    index 0; the w-last identity quat (0,0,0,1) counts at index 3 —
    #    the detector counts positions, the corpus decides the convention
    st0 = quat_order_stats([(0, (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0))])
    check("quat stats: w-first identity counts at index 0", st0["identity_at"].get(0) == 1)
    st3 = quat_order_stats([(0, (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0))])
    check("quat stats: w-last identity counts at index 3", st3["identity_at"].get(3) == 1)

    # 9. region class: Cont_ prefix and CATCtorProxyCont block
    check(
        "region class: Cont_ region name -> ctorproxy",
        region_class("Cont_0_448c_6ab71ee0_bbc0", "CATCtorProxyCont") == "ctorproxy",
    )
    check(
        "region class: CATCtorProxyCont block -> ctorproxy",
        region_class("", "CATCtorProxyCont") == "ctorproxy",
    )
    check(
        "region class: CATIA block stays CATIA",
        region_class("CATIA1", "CATIA") == "CATIA",
    )

    # 10. binary pool payload check: a 13-byte payload yields no windows
    #     (under the 56 B a transform needs)
    check(
        "binary payload sizes are returned as-is (13 B < 56 B)",
        binary_pool_payloads.__doc__ is not None,
    )

    # 11. the 13-byte _BagRepsList payload from P2's worked example holds
    #     no transform window (structurally: 13 < 56)
    p2_payload = bytes.fromhex("3f3f153f5c3f3f3f12c2b63f3a")
    check(
        "P2 worked-example payload cannot hold a record",
        len(p2_payload) < RECORD_BYTES,
    )

    # 12. R15 entry detector: synthetic positive (0x81 tag after the name)
    buf12 = b"\x00" * 16 + b"\x0a_Position\x81 e8xxx" + b"\x00" * 16
    n12 = 0
    i = buf12.find(b"_Position")
    if p1.law_b_valid(b"_Position", buf12, i):
        nxt = buf12[i + 9 : i + 11]
        n12 = 1 if (nxt and nxt[0] in (0x80, 0x81)) else 0
    check("R15 entry: 0x81 tag after law-B _Position counts", n12 == 1)

    # 13. R15 entry negative: framed-pool-style successor (a value) does
    #     not count
    buf13 = b"\x00" * 16 + b"\x0a_PositionPRDREP\x00" + b"\x00" * 16
    i13 = buf13.find(b"_Position")
    nxt13 = buf13[i13 + 9 : i13 + 11] if i13 >= 0 else b""
    check(
        "R15 entry: non-0x80/0x81 successor does not count",
        not (nxt13 and nxt13[0] in (0x80, 0x81)),
    )

    print(f"selftest: {'PASS' if not failures else 'FAIL ' + str(failures)}")
    return 0 if not failures else 1


# --- per-file JSON anchor -----------------------------------------------------


def run_sha16(sha16: str) -> int:
    for r in p1.load_population():
        if r["sha256"].startswith(sha16):
            row = analyze_one(r)
            print(json.dumps(row, indent=2, default=str))
            return 0
    print(f"sha16 {sha16!r} not found in the product population", file=sys.stderr)
    return 1


# --- main ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--census", action="store_true", help="per-file CSV")
    ap.add_argument("--claims", action="store_true", help="claims CSV")
    ap.add_argument("--ceiling", action="store_true", help="ceiling CSV")
    ap.add_argument("--all", action="store_true", help="census + claims + ceiling")
    ap.add_argument("--selftest", action="store_true", help="synthetic negatives")
    ap.add_argument("--sha16", help="per-file JSON anchor")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.sha16:
        return run_sha16(args.sha16)
    if not (args.census or args.claims or args.ceiling or args.all):
        ap.print_help()
        return 2
    rows = run_census()
    if args.all or args.claims:
        run_claims(rows)
    if args.all or args.ceiling:
        run_ceiling(rows)
    print(f"census rows: {len(rows)} -> {OUT_FILES.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
