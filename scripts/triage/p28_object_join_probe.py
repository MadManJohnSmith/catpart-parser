#!/usr/bin/env python3
"""P2.8 probe: object-level `_Position` -> instance join on the 10
explicit-only `connector_proxy_mesh` files.

Read-only. Re-measures the three candidate joins with a literal object
scan (the P2.7 `re.finditer(b"\\xfe\\x7c\\x05")` pattern is an alternation
and over-counts frames; `find` is literal):

  H1 object successor: the position object is the next serialized object
      (object id + 1, first reference + 1);
  H2 shared parent: some object references both the instance object and its
      position object (direct; the transitive walk from the constraint
      objects is reported too);
  H3 constraint frames: a `CstIndex` / `_hasConnections` object references
      either object.

Modes:
    python3 -I scripts/triage/p28_object_join_probe.py --selftest
    python3 -I scripts/triage/p28_object_join_probe.py --report
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "triage"))

import catpart.fixtures_assembly as fa  # noqa: E402
import p27_position_attr_probe as p27  # noqa: E402

#: The ten explicit-only count-consistent files of P3 §3 (95 instances).
TARGETS = {
    "0d60a2bc": 5, "1b8c4500": 5, "2107dc0a": 9, "2b6c0970": 10,
    "322c8e13": 10, "590430c6": 14, "974ef60f": 4, "a5d51be5": 28,
    "b96ef5f9": 5, "bad5257b": 5,
}


def scan_records(data: bytes) -> list[dict]:
    """Object records `7c 05 <u32 len>` (one generation) or
    `fe 7c 05 <u32 len>` (the other).

    The record body opens with a `7c 06` header holding `ea <u32>` and the
    `80 <u32>` references.  This is a literal `find`; the P2.7 probe used
    `re.finditer(b"\\xfe\\x7c\\x05")`, where `0x7c` is the regex alternation
    operator, so it matched single `0xfe`/`0x05` bytes and over-counted.
    """
    out: list[dict] = []
    i = 0
    while True:
        j = data.find(b"\x7c\x05", i)
        if j < 0:
            break
        i = j + 1
        length = int.from_bytes(data[j + 2 : j + 6], "little")
        if length < 12 or j + 2 + length > len(data):
            continue
        body = data[j + 6 : j + 2 + length]
        k = 0
        while k < len(body) and body[k] == 0:
            k += 1
        if body[k : k + 2] != b"\x7c\x06":
            continue
        header_len = int.from_bytes(body[k + 2 : k + 6], "little")
        header_end = k + header_len
        if not (6 <= header_len <= 400 and header_end <= len(body)):
            continue
        em = re.search(rb"\xea(....)", body[k:header_end], re.S)
        if em is None:
            continue
        refs = [
            int.from_bytes(m.group(1), "little")
            for m in re.finditer(rb"\x80(....)", body[k:header_end], re.S)
        ]
        attrs: list[bytes] = []
        p = header_end
        while p + 4 <= len(body):
            if body[p] == 0x7C and body[p + 1] == 0x07:
                n = int.from_bytes(body[p + 2 : p + 6], "little")
                if 6 <= n and p + n <= len(body):
                    attrs = [c for c in body[p + 6 : p + n].split(b"\xfe") if len(c) >= 3]
                break
            p += 1
        out.append(dict(
            offset=j, end=j + 2 + length,
            obj_id=int.from_bytes(em.group(1), "little"),
            refs=refs, attrs=attrs,
        ))
    return out


def attr_names(chunk: bytes, texts: list[str]) -> str | None:
    if chunk and 0x34 <= chunk[0] < 0x34 + len(texts):
        return texts[chunk[0] - 0x34]
    return None


def analyze(path: Path, expected: int) -> dict | None:
    data = path.read_bytes()
    table = p27.load_name_table(data)
    if table is None:
        return None
    texts, _ = table
    inst_id = p27.name_id_of(texts, "_InstanceName")
    pos_id = p27.name_id_of(texts, "_Position")
    frames = scan_records(data)
    recs = [r for r in fa.parse_position_matrix_records(data) if r["kind"] == "explicit"]

    owners = []
    for r in recs:
        cand = [f for f in frames if f["offset"] <= r["offset"] < f["end"]]
        owners.append(min(cand, key=lambda f: f["end"] - f["offset"]) if cand else None)
    positions = [o for o in owners if o is not None]

    named = []
    for f in frames:
        for chunk in f["attrs"]:
            if chunk and chunk[0] == inst_id:
                nm = p27.instance_name_of(chunk, texts)
                if nm:
                    named.append((f, nm))
    struct = fa.read_product_structure(data)
    order = [i["instance_name"] for i in struct["instances"]]

    by_obj: dict[int, list[dict]] = defaultdict(list)
    for f in positions:
        by_obj[f["obj_id"]].append(f)

    rows = []
    seen: set[str] = set()
    for f, nm in named:
        if nm not in order or nm in seen:
            continue
        seen.add(nm)
        cand = by_obj.get(f["obj_id"] + 1, [])
        pf = cand[0] if len(cand) == 1 else None
        rows.append(dict(
            instance=nm,
            inst_obj=f["obj_id"], pos_obj=None if pf is None else pf["obj_id"],
            id_plus_1=pf is not None,
            ref0_plus_1=bool(pf is not None and f["refs"] and pf["refs"]
                             and pf["refs"][0] == f["refs"][0] + 1),
            shared=0 if pf is None else len(set(f["refs"]) & set(pf["refs"])),
        ))
    missing_names = [n for n in order if n not in seen]

    # H2 direct: a frame referencing both object handles.
    h2 = 0
    for r in rows:
        if r["pos_obj"] is None:
            continue
        fi = next(f for f in frames if f["obj_id"] == r["inst_obj"] and
                  any(c and c[0] == inst_id for c in f["attrs"]))
        fp = next(f for f in frames if f["obj_id"] == r["pos_obj"] and
                  any(c and c[0] == pos_id for c in f["attrs"]))
        if not fi["refs"] or not fp["refs"]:
            continue
        h2 += any(
            g is not fi and g is not fp
            and fi["refs"][0] in g["refs"] and fp["refs"][0] in g["refs"]
            for g in frames
        )
    # H3: a constraint frame referencing either handle.
    cst = [f for f in frames
           if {attr_names(c, texts) for c in f["attrs"]} & {"CstIndex", "_hasConnections"}]
    h3 = 0
    for r in rows:
        if r["pos_obj"] is None:
            continue
        fi = next(f for f in frames if f["obj_id"] == r["inst_obj"] and
                  any(c and c[0] == inst_id for c in f["attrs"]))
        fp = next(f for f in frames if f["obj_id"] == r["pos_obj"] and
                  any(c and c[0] == pos_id for c in f["attrs"]))
        for g in cst:
            if g is fi or g is fp:
                continue
            if (fi["refs"] and fi["refs"][0] in g["refs"]) or \
               (fp["refs"] and fp["refs"][0] in g["refs"]):
                h3 += 1
                break
    order_ok = [r["instance"] for r in rows] == order
    return dict(
        path=path, sha16=hashlib.sha256(data).hexdigest()[:8],
        instances=len(order), expected=expected, frames=len(frames),
        explicit=len(recs), positions=len(positions), named=len(named),
        rows=rows, missing=missing_names, order_ok=order_ok,
        id_plus_1=sum(r["id_plus_1"] for r in rows),
        ref0_plus_1=sum(r["ref0_plus_1"] for r in rows),
        shared1=sum(r["shared"] >= 1 for r in rows),
        h2=h2, h3=h3, cst=len(cst),
    )


def report() -> None:
    results = []
    for path in sorted((ROOT / "corpus").rglob("*.CATProduct")):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        if sha not in TARGETS:
            continue
        r = analyze(path, TARGETS[sha])
        if r is None:
            print(f"{sha}: no name table")
            continue
        results.append(r)
        print(f"\n{sha} {path.name}")
        print(f"  instances={r['instances']} explicit={r['explicit']} "
              f"positions={r['positions']} named={r['named']} frames={r['frames']}")
        print(f"  order_ok={r['order_ok']} id+1={r['id_plus_1']}/{len(r['rows'])} "
              f"ref0+1={r['ref0_plus_1']} shared>=1={r['shared1']} "
              f"H2={r['h2']} H3={r['h3']} cst={r['cst']}")
        if r["missing"]:
            print(f"  names not on an object: {r['missing']}")
    rows = sum(len(r["rows"]) for r in results)
    print(f"\ncorpus-wide: files={len(results)} instances={sum(r['instances'] for r in results)} "
          f"named_rows={rows} id+1={sum(r['id_plus_1'] for r in results)} "
          f"ref0+1={sum(r['ref0_plus_1'] for r in results)} "
          f"shared>=1={sum(r['shared1'] for r in results)} "
          f"H2={sum(r['h2'] for r in results)} H3={sum(r['h3'] for r in results)} "
          f"order_ok_files={sum(r['order_ok'] for r in results)}/{len(results)}")


def _record(obj_id: int, ref0: int, shared: int) -> bytes:
    header_rest = (b"\x00\x00\x46\x47\xea" + obj_id.to_bytes(4, "little")
                   + b"\x80" + ref0.to_bytes(4, "little")
                   + b"\x00\x80" + shared.to_bytes(4, "little"))
    header = b"\x7c\x06" + (6 + len(header_rest)).to_bytes(4, "little") + header_rest
    body = b"\x00" + header + b"\x02\xfd\x82\x7c\x07\x06\x00\x00\x00"
    return b"\x7c\x05" + (len(body) + 4).to_bytes(4, "little") + body


def selftest() -> None:
    """Synthetic two-object record: instance -> position, id + 1."""
    data = b"\x00" * 8 + _record(7, 0xAA, 0xBB) + _record(8, 0xAB, 0xBB) + b"\x00" * 8
    frames = scan_records(data)
    assert [f["obj_id"] for f in frames] == [7, 8], frames
    assert frames[1]["refs"][0] == frames[0]["refs"][0] + 1
    assert frames[1]["refs"][1] == frames[0]["refs"][1]
    # the literal scan does not match a stray 0xfe (the P2.7 regex defect)
    assert scan_records(b"\xfe" * 16) == []
    print("selftest: ok")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return 0
    report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
