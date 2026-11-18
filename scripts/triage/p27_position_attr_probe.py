#!/usr/bin/env python3
"""P2.7 probe (#47 follow-up): which ``8d 81`` streams are ``_Position``?

Read-only probe. It answers one question only — can the interned
attribute-name reference that precedes a ``7c 07`` value record be
resolved to a name from the CATProduct name table, so that the
``_Position`` streams are selected by their *attribute* rather than by
ordinal position in the file?

Two independent decodes are probed:

1. **The name table (PINS).** The structure pool (``fe 7c 02`` record,
   ``src/catpart/product`` / ``scripts/triage/p2_pool_pairing.py``) is the
   file's interned name table.  An attribute/name reference is one byte
   ``id``; the name is ``pool[id - 0x34]`` (0-based ordinal), i.e.
   ``pool[id - 0x35]`` with 1-based ordinals.  Ids ``< 0x34`` name
   predefined (non-document) entries and are never pool strings.
   Consequence: ``_Position`` is ``id = 0x34 + index_of('_Position')``
   in that file, whatever the file's pool order is.  Worked examples:
   coso (index 25 -> ``0x4d``), servo (index 34 -> ``0x56``).

2. **The object -> instance join (DOES NOT PIN).** The ``_Position`` entry
   lives on a serialized object (``ea <u32>`` header).  The
   ``_InstanceName`` entry of the instance lives on a *different*
   object in the same file (or a nested one).  No reference joins the
   two.  In coso the position object's first ``80 <u32>`` handle is the
   instance object's first handle + 1 (obj 7 -> obj 8:
   ``0x6cb83caa`` -> ``0x6cb83cab``) and two later handles are shared;
   in servo the two objects share no reference at all (instance obj 4:
   ``0x6d230c84 0x3d7e14fd 0x6aac9437 0x6aac9437``; position obj 5:
   ``0x4f3749d6 0x432ad640 0x6ac7f7fd 0x6aea768c``).  That is stream
   adjacency, not a join key, and it is not universal corpus-wide (see
   ``--report``: 2,226 of 3,016 ``_Position`` objects have no byte-level
   instance link).  Binding by it would be the very ordinal guess the
   ticket forbids, so this probe stops here.

Modes:
    python3 -I scripts/triage/p27_position_attr_probe.py --selftest
    python3 -I scripts/triage/p27_position_attr_probe.py --report
    python3 -I scripts/triage/p27_position_attr_probe.py --sha16 81b1fe655b83f7ee

The probe writes nothing; the committed CSVs are produced by hand from
the ``--report`` output (the note pins every figure).
"""

from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "triage"))

import p2_pool_pairing as p2  # noqa: E402

#: Base of the document name ids (0-based pool ordinal + BASE).
NAME_ID_BASE = 0x34

#: Value type tag of a placed transform (CATMathTransformation payload).
POSITION_TYPE_TAG = bytes.fromhex("e8f40737")

#: Value type tags of the matrix consumers this probe discriminates
#: against (camera/view matrices observed with ``e8 e0 07 37``).
OTHER_MATRIX_TAGS = {
    bytes.fromhex("e8e00737"): "e8-e0-07-37 (view/camera matrix)",
    bytes.fromhex("e8e00701"): "e8-e0-07-01 (view/camera matrix)",
}


# --------------------------------------------------------------------------- #
# RLE float stream (shared by the R15 and framed generations)
# --------------------------------------------------------------------------- #
def parse_rle_floats(stream: bytes, count: int = 12) -> tuple[list[float], int] | None:
    """Decode up to ``count`` run-length floats: e8=0.0, e7=1.0, e9=-1.0, e6=f64le."""
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
            vals.append(struct.unpack("<d", stream[p + 1 : p + 9])[0])
            p += 9
        else:
            return None
    return (vals, p) if len(vals) == count else None


def det3(r: list[list[float]]) -> float:
    return (
        r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
        - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
        + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0])
    )


def is_placement_matrix(vals: list[float], tol: float = 1e-4) -> bool:
    """12 RLE floats = row-major R (det +1, unit rows) then T (finite, <=10 km)."""
    r = [vals[0:3], vals[3:6], vals[6:9]]
    if abs(det3(r) - 1.0) > tol:
        return False
    for row in r:
        if abs(math.sqrt(sum(c * c for c in row)) - 1.0) > tol:
            return False
    return all(abs(t) <= 1e7 for t in vals[9:12])


# --------------------------------------------------------------------------- #
# Name table
# --------------------------------------------------------------------------- #
def name_of(texts: list[str], name_id: int) -> str | None:
    """Resolve a one-byte name id against the decoded name table."""
    idx = name_id - NAME_ID_BASE
    return texts[idx] if 0 <= idx < len(texts) else None


def name_id_of(texts: list[str], name: str) -> int | None:
    """The name id of ``name`` in this file's table, or None."""
    try:
        return texts.index(name) + NAME_ID_BASE
    except ValueError:
        return None


def load_name_table(data: bytes) -> tuple[list[str], int] | None:
    """Decode the structure pool (the interned name table) from a product."""
    best = p2.pick_pool(p2.framed_pool_candidates(data))
    if best is None:
        return None
    texts = [item[3].decode("utf-8", "replace") for item in best["items"]]
    return texts, best["hdr"]


# --------------------------------------------------------------------------- #
# ``7c 07`` value records and their attribute chunks
# --------------------------------------------------------------------------- #
def enclosing_7c07(data: bytes, pos: int, back: int = 160) -> tuple[int, int] | None:
    """The nearest ``7c 07 <u32 len>`` record whose span contains ``pos``."""
    found = None
    for start in range(max(0, pos - back), pos):
        if data[start : start + 2] != b"\x7c\x07":
            continue
        length = int.from_bytes(data[start + 2 : start + 6], "little")
        if 6 <= length <= 900 and start + length >= pos:
            found = (start, length)
    return found


def chunk_at(record_payload: bytes, rel: int) -> bytes | None:
    """The ``<attr-id> ... fe`` chunk of a ``7c 07`` payload containing ``rel``."""
    start = 0
    while start < len(record_payload):
        end = record_payload.find(b"\xfe", start)
        if end < 0:
            end = len(record_payload)
        if start <= rel < end:
            return record_payload[start:end]
        start = end + 1
    return None


def type_tag_of(chunk: bytes) -> bytes | None:
    """The 4-byte value type tag immediately before ``8d 81`` in a chunk."""
    marker = chunk.find(b"\x8d\x81")
    if marker < 4:
        return None
    return chunk[marker - 4 : marker]


def scan_matrices(data: bytes) -> list[dict]:
    """Every valid 12-float ``8d 81`` matrix, with its attribute chunk."""
    out = []
    for m in re.finditer(rb"\x8d\x81", data):
        pos = m.start()
        decoded = parse_rle_floats(data[pos + 2 :])
        if decoded is None:
            continue
        vals, used = decoded
        if not is_placement_matrix(vals):
            continue
        record = enclosing_7c07(data, pos)
        if record is None:
            out.append(dict(offset=pos, values=vals, attr=None, tag=None, record=None))
            continue
        start, length = record
        payload = data[start + 6 : start + length]
        chunk = chunk_at(payload, pos - (start + 6))
        out.append(
            dict(
                offset=pos,
                values=vals,
                attr=chunk[0] if chunk else None,
                tag=type_tag_of(chunk) if chunk else None,
                record=(start, length),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Object frames (``fe 7c 05``) — header refs and the first property record
# --------------------------------------------------------------------------- #
def scan_object_frames(data: bytes) -> list[dict]:
    """Serialized objects: ``ea <u32>`` id, header refs, property chunks.

    The frame is ``fe 7c 05 <u32 ln>``.  The body opens with a ``7c 06``
    header record holding ``ea <u32>`` and the ``80 <u32>`` references;
    the property set follows as ``02 <class-id> 7c 07 <u32> <chunks>``.
    Only the header refs and the first property record are decoded; the
    probe needs nothing else.
    """
    seen: dict[int, dict] = {}
    for m in re.finditer(b"\xfe\x7c\x05", data):
        head = m.start()
        length = int.from_bytes(data[head + 3 : head + 7], "little")
        if length < 12 or head + 1 + length > len(data):
            continue
        key = head + 1
        if key in seen:
            continue
        body = data[head + 7 : head + 1 + length]
        i = 0
        while i < len(body) and body[i] == 0:
            i += 1
        if body[i : i + 2] != b"\x7c\x06":
            continue
        header_len = int.from_bytes(body[i + 2 : i + 6], "little")
        header_end = i + header_len
        if not (6 <= header_len <= 200 and header_end <= len(body)):
            continue
        em = re.search(rb"\xea(....)", body[i:header_end], re.S)
        if em is None:
            continue
        obj_id = int.from_bytes(em.group(1), "little")
        refs = [
            int.from_bytes(r.group(1), "little")
            for r in re.finditer(rb"\x80(....)", body[i:header_end], re.S)
        ]
        attrs: list[bytes] = []
        j = header_end
        while j + 4 <= len(body):
            if body[j] == 0x7C and body[j + 1] == 0x07:
                n = int.from_bytes(body[j + 2 : j + 6], "little")
                if 6 <= n and j + n <= len(body):
                    attrs = [c for c in body[j + 6 : j + n].split(b"\xfe") if len(c) >= 3]
                break
            j += 1
        seen[key] = dict(
            offset=head, end=head + 1 + length, obj_id=obj_id,
            refs=refs, attrs=attrs,
        )
    return list(seen.values())


def instance_name_of(chunk: bytes, texts: list[str]) -> str | None:
    """``_InstanceName`` value: ``<id> <flag> e8 c0 12 37 <name-id>``."""
    marker = chunk.find(bytes.fromhex("e8c01237"))
    if marker < 0 or marker + 5 > len(chunk):
        return None
    return name_of(texts, chunk[marker + 4])


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def probe_file(path: Path, sample_matrices: int = 0) -> dict | None:
    data = path.read_bytes()
    table = load_name_table(data)
    if table is None:
        return None
    texts, pool_offset = table
    position_id = name_id_of(texts, "_Position")
    instance_id = name_id_of(texts, "_InstanceName")
    matrices = scan_matrices(data)
    position = [m for m in matrices if position_id is not None and m["attr"] == position_id]
    other = [m for m in matrices if position_id is None or m["attr"] != position_id]

    frames = scan_object_frames(data)
    by_ref = {f["refs"][0]: f for f in frames if f["refs"]}
    name_frames = {
        f["offset"]: f
        for f in frames
        if instance_id is not None and any(c[0] == instance_id for c in f["attrs"])
    }

    position_objects = []
    for m in position:
        rec = m["record"]
        if rec is None:
            continue
        owner = None
        for f in frames:
            if f["offset"] <= rec[0] and rec[0] < f["end"]:
                if owner is None or f["end"] - f["offset"] < owner["end"] - owner["offset"]:
                    owner = f
        position_objects.append(owner)

    direct = 0
    successor = 0
    unbound = 0
    for owner in position_objects:
        if owner is None:
            unbound += 1
            continue
        if instance_id is not None and any(c[0] == instance_id for c in owner["attrs"]):
            direct += 1
            continue
        refs = owner["refs"]
        predecessor = by_ref.get(refs[0] - 1) if refs else None
        if predecessor is not None and predecessor["offset"] in name_frames:
            successor += 1
        else:
            unbound += 1

    instance_names = set()
    for f in name_frames.values():
        for chunk in f["attrs"]:
            if chunk and chunk[0] == instance_id:
                name = instance_name_of(chunk, texts)
                if name and re.match(r"^.+\.\d{1,4}$", name):
                    instance_names.add(name)

    result = dict(
        path=str(path),
        pool_offset=pool_offset,
        pool_items=len(texts),
        position_id=position_id,
        position_ordinal=(position_id - NAME_ID_BASE) if position_id is not None else None,
        instance_id=instance_id,
        matrices=len(matrices),
        position_matrices=len(position),
        other_matrices=len(other),
        other_tags=Counter(
            tag_of(m["tag"]) if m["tag"] else "no-tag" for m in other
        ),
        position_objects=len(position_objects),
        instance_names=sorted(instance_names),
        name_frames=len(name_frames),
        direct=direct,
        successor=successor,
        unbound=unbound,
        samples=matrices[:sample_matrices],
    )
    return result


def tag_of(tag: bytes) -> str:
    return "-".join(f"{b:02x}" for b in tag)


def run_report(limit: int | None) -> int:
    files = sorted((ROOT / "corpus").rglob("*.CATProduct"))
    totals = Counter()
    rows = []
    for path in files:
        info = probe_file(path)
        if info is None:
            continue
        totals["files_with_table"] += 1
        if info["position_id"] is not None:
            totals["files_with_position_attr"] += 1
            totals["matrices"] += info["matrices"]
            totals["position_matrices"] += info["position_matrices"]
            totals["other_matrices"] += info["other_matrices"]
            totals["position_objects"] += info["position_objects"]
            totals["direct"] += info["direct"]
            totals["successor"] += info["successor"]
            totals["unbound"] += info["unbound"]
            totals["instance_names"] += len(info["instance_names"])
            rows.append(info)
    print(f"CATProduct files scanned                 : {len(files)}")
    print(f"files with a decodable structure table   : {totals['files_with_table']}")
    print(f"files whose table names _Position        : {totals['files_with_position_attr']}")
    print(f"valid 8d81 placement matrices            : {totals['matrices']}")
    print(f"  attributed _Position by id == 0x34+idx : {totals['position_matrices']}")
    print(f"  other attributes (camera/rep/...)      : {totals['other_matrices']}")
    print(f"_Position-bearing objects                : {totals['position_objects']}")
    print(f"  object carries _InstanceName itself    : {totals['direct']}")
    print(f"  ref0-1 predecessor carries a name      : {totals['successor']}")
    print(f"  no byte-level instance link            : {totals['unbound']}")
    print(f"distinct dot-shaped _InstanceName values : {totals['instance_names']}")
    print()
    print("worked examples:")
    for info in rows:
        if limit is not None and len(info["samples"]) == 0:
            pass
        name = Path(info["path"]).name
        if name in ("coso.CATProduct", "servo_STS3215_03a v1.CATProduct", "Product1.CATProduct"):
            print(
                f"  {name}: pool_items={info['pool_items']} "
                f"_Position idx={info['position_ordinal']} id=0x{info['position_id']:02x} "
                f"matrices={info['matrices']} position={info['position_matrices']} "
                f"other={info['other_matrices']} names={info['instance_names']}"
            )
    return 0


def run_sha16(sha16: str, limit: int) -> int:
    manifest = ROOT / "manifests" / "corpus-manifest.csv"
    import csv

    target = None
    with manifest.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("sha256", "").startswith(sha16):
                target = row
                break
    if target is None:
        print(f"sha16 {sha16}: not in the manifest", file=sys.stderr)
        return 2
    local = target.get("local_path") or f"corpus/{target.get('path', '')}"
    path = ROOT / local
    info = probe_file(path, sample_matrices=limit)
    if info is None:
        print(f"{sha16}: no structure table", file=sys.stderr)
        return 1
    print(f"{sha16}  {info['path']}")
    print(f"  name table @0x{info['pool_offset']:x}, {info['pool_items']} items")
    print(f"  _Position ordinal {info['position_ordinal']} -> id 0x{info['position_id']:02x}")
    print(f"  matrices {info['matrices']}: _Position {info['position_matrices']}, other {info['other_matrices']}")
    print(f"  other tags: {dict(info['other_tags'])}")
    print(f"  _Position objects {info['position_objects']}: direct={info['direct']} successor={info['successor']} unbound={info['unbound']}")
    print(f"  instance names: {info['instance_names']}")
    for m in info["samples"]:
        t = m["values"][9:12]
        print(f"  @0x{m['offset']:x} attr=0x{m['attr']:02x} tag={tag_of(m['tag']) if m['tag'] else '-'} T={tuple(round(x, 3) for x in t)}")
    return 0


# --------------------------------------------------------------------------- #
# Selftest — synthetic table + object, no corpus IO
# --------------------------------------------------------------------------- #
def _build_pool(items: list[str]) -> bytes:
    payload = b"".join(bytes([len(t.encode()) + 1]) + t.encode() for t in items)
    ln = 6 + 1 + len(payload)
    return b"\xfe\x7c\x02" + ln.to_bytes(4, "little") + b"\xbf" + payload


def _build_object(obj_id: int, ref0: int, attr_id: int, tag: bytes, matrix: bytes) -> bytes:
    header_rest = b"\x00\x00\x46\x47" + b"\xea" + obj_id.to_bytes(4, "little")
    header_rest += b"\x80" + ref0.to_bytes(4, "little")
    header = b"\x00\x7c\x06" + (6 + len(header_rest)).to_bytes(4, "little") + header_rest
    chunk = bytes([attr_id]) + b"\xd4\x3e" + tag + b"\x8d\x81" + matrix
    payload = chunk + b"\xfe"
    props = b"\x02\xfd\x83\x7c\x07" + (6 + len(payload)).to_bytes(4, "little") + payload
    body = header + props
    return b"\xfe\x7c\x05" + (6 + len(body)).to_bytes(4, "little") + body


def selftest() -> int:
    failures = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal failures
        if cond:
            print(f"ok   {name}")
        else:
            failures += 1
            print(f"FAIL {name} {detail}")

    items = [
        "CATCatalogManager", "catalogManager", "catalogLinks", "",
        "ASMPRODUCT", "Product1", "CATMechProdCont", "_PartNumber",
        "Part1", "_InstanceName", "Part1.1", "_Position", "PRDREP",
    ]
    pool = _build_pool(items)
    texts = items
    pos_id = name_id_of(texts, "_Position")
    iname_id = name_id_of(texts, "_InstanceName")
    check("position id = 0x34 + ordinal", pos_id == 0x34 + 11, hex(pos_id or 0))
    check("instance id = 0x34 + ordinal", iname_id == 0x34 + 9, hex(iname_id or 0))
    check("name_of round-trips", name_of(texts, pos_id) == "_Position")
    check("predefined ids stay unresolved", name_of(texts, 0x10) is None)

    matrix = b"\xe7\xe8\xe8\xe8\xe7\xe8\xe8\xe8\xe7\xe8\xe8\xe8"  # identity
    pos = _build_object(7, 0x11223344, pos_id, POSITION_TYPE_TAG, matrix)
    cam = _build_object(9, 0x11223345, 0x3A, bytes.fromhex("e8e00737"), matrix)
    framed = pool + pos + cam

    decoded = parse_rle_floats(matrix)
    check("RLE identity decodes", decoded is not None and decoded[0] == [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    check("identity is a placement matrix", is_placement_matrix(decoded[0]) if decoded else False)

    got = scan_matrices(framed)
    check("two matrices found", len(got) == 2, str(len(got)))
    check("_Position matrix carries the position id", any(m["attr"] == pos_id for m in got))
    check("camera matrix carries the other id", any(m["attr"] == 0x3A for m in got))
    check("camera tag differs", any(m["tag"] == bytes.fromhex("e8e00737") for m in got))

    frames = scan_object_frames(framed)
    check("object frames parsed", len(frames) == 2, str(len(frames)))
    check("object ids parsed", {f["obj_id"] for f in frames} == {7, 9})
    check("ref0 successor relation", frames[1]["refs"][0] == frames[0]["refs"][0] + 1)

    name_chunk = bytes([iname_id, 0x82]) + bytes.fromhex("e8c01237") + bytes([0x34 + 10])
    check("instance name resolves", instance_name_of(name_chunk, texts) == "Part1.1")

    # Non-unit determinant must be rejected.
    bad = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 0.0]
    check("non-proper rotation rejected", not is_placement_matrix(bad))

    print(f"\n{failures} failure(s)")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sha16")
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.sha16:
        return run_sha16(args.sha16, args.limit)
    return run_report(args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
