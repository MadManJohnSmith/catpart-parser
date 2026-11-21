#!/usr/bin/env python3
"""#63 micro-probe: the CAT3DFaceGP law on the ``d2 d2 51`` patch
sub-records (read-only, 2026-11-20).

Applies the deduced law over every ``30 04 04 ff ff ff d2 d2 51``
sub-record of the 43 bag-rep carriers (``bagrep-probe.csv`` rows with
``subrecords > 0``) plus ``CAAMaiUserToolDatabaseCustomization`` (the
BLANK, whose sub-records sit outside the named containers), discarding
the ``type 0x00`` boundary artifacts:

- ``+57..+72``: ``kind:u32le, N_tris:u32le, N_strips:u32le,
  N_fans:u32le``;
- after the marker (the first ``ff 7f`` or ``01 80`` at >= +73; the
  stream starts at +73 when neither appears):
  ``N_tris`` independent triangles (``3*N_tris`` u16be indices),
  then ``N_strips`` strips (``count:u32be`` + ``count`` u16be
  indices), then ``N_fans`` fans (same framing);
- every index maps ``v = idx // 3`` into the class record's declared
  point array (the t5 index-space finding); strips/fans emit through
  the strip/fan windows (count-2 triangles each).

Reports per file: sub-records tried, exact byte closures (``pos ==
len - 1`` — the trailing dangling byte), the index-space fit, the
assembled mesh's triangle count, manifold verdict and the physicality
ratio ``area / bbox_diag^2``; then the projected L2 dev jump (the
carriers' current ``l2.status`` from the last committed fitness report
vs the files this law renders manifold + physical).

The ``0x50`` extra applies the same layout to one Plate 105 B and one
CAAMai 173 B sub-record and reports which framing closes them.

Run::

    .venv/bin/python -I scripts/triage/probe_t63_face_gp.py

Read-only over the corpus; no ``src/`` change.
"""

import csv
import json
import math
import os
import struct
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "triage"))

from probe_bagrep import (  # noqa: E402
    SUBREC,
    load_manifest,
)

IDX_MAX = 1024
PHYSICAL_RATIO_MAX = 100.0
LATEST_REPORT = os.path.join(ROOT, "fitness", "reports", "20261120T221222Z-6aa551.json")


def class_record_spans(data):
    """(start, end, name) of the bag-rep class records, file-wide."""
    found = []
    for name, n in ((b"CAT3DBagRep", 11), (b"CATSurfacicRep", 14)):
        pos = 0
        while True:
            pos = data.find(name, pos)
            if pos < 0:
                break
            if pos >= 4 and int.from_bytes(data[pos - 4 : pos], "little") == n:
                found.append((pos - 4, name.decode()))
            pos += 1
    found.sort()
    out = []
    for i, (start, nm) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else len(data)
        out.append((start, end, nm))
    return out


def subrecord_positions(data, lo, hi):
    pos = []
    i = lo
    while True:
        i = data.find(SUBREC, i, hi)
        if i < 0:
            break
        pos.append(i)
        i += 1
    return pos


def face_gp(data, start, end):
    """The CAT3DFaceGP law on one 0x51 sub-record.

    Returns (closed_exact, sections, tris) where ``tris`` are
    (v0, v1, v2) with ``v = idx // 3`` (strips/fans through their
    windows), and ``closed_exact`` marks ``pos == len - 1``.
    """
    rel_len = end - start
    kind, n_tris, n_strips, n_fans = struct.unpack_from(
        "<4I", data, start + 57
    )
    marker = -1
    for tag in (b"\xff\x7f", b"\x01\x80"):
        at = data.find(tag, start + 73, end)
        if at >= 0 and (marker < 0 or at < marker):
            marker = at
    pos_rel = (marker + 2 - start) if marker >= 0 else 73
    idxs = []
    ok = True
    for _ in range(n_tris):
        if pos_rel + 6 > rel_len:
            ok = False
            break
        for j in range(3):
            idxs.append(
                int.from_bytes(data[start + pos_rel : start + pos_rel + 2], "big")
            )
            pos_rel += 2
    strips = []
    for _ in range(n_strips if ok else 0):
        if pos_rel + 4 > rel_len:
            ok = False
            break
        count = int.from_bytes(data[start + pos_rel : start + pos_rel + 4], "big")
        pos_rel += 4
        vals = []
        for _ in range(count):
            if pos_rel + 2 > rel_len:
                ok = False
                break
            vals.append(
                int.from_bytes(data[start + pos_rel : start + pos_rel + 2], "big")
            )
            pos_rel += 2
        strips.append(vals)
        if not ok:
            break
    fans = []
    for _ in range(n_fans if ok else 0):
        if pos_rel + 4 > rel_len:
            ok = False
            break
        count = int.from_bytes(data[start + pos_rel : start + pos_rel + 4], "big")
        pos_rel += 4
        vals = []
        for _ in range(count):
            if pos_rel + 2 > rel_len:
                ok = False
                break
            vals.append(
                int.from_bytes(data[start + pos_rel : start + pos_rel + 2], "big")
            )
            pos_rel += 2
        fans.append(vals)
        if not ok:
            break
    tris = []
    # bound by what was actually READ: a junk-huge declared N_tris must
    # not spin this loop past the sub-record's own bytes
    for j in range(0, min(3 * n_tris, len(idxs)) - 2, 3):
        tris.append((idxs[j] // 3, idxs[j + 1] // 3, idxs[j + 2] // 3))
    for vals in strips:
        for j in range(len(vals) - 2):
            tris.append((vals[j] // 3, vals[j + 1] // 3, vals[j + 2] // 3))
    for vals in fans:
        for j in range(1, len(vals) - 1):
            tris.append((vals[0] // 3, vals[j] // 3, vals[j + 1] // 3))
    return {
        "kind": kind,
        "n_tris": n_tris,
        "n_strips": n_strips,
        "n_fans": n_fans,
        "marker_rel": marker - start if marker >= 0 else None,
        "pos_rel": pos_rel,
        "rel_len": rel_len,
        "closed_exact": ok and pos_rel == rel_len - 1,
        "consumed_all": ok and pos_rel == rel_len,
        "tris": tris,
    }


def manifold(tris):
    uses = defaultdict(int)
    for a, b, c in tris:
        if a == b or b == c or a == c:
            return False, "degenerate"
        for e in ((a, b), (b, c), (c, a)):
            uses[tuple(sorted(e))] += 1
    if not uses:
        return False, "empty"
    if any(v != 2 for v in uses.values()):
        return False, "over-use"
    return True, "manifold"


def mesh_report(points, tris):
    """(in_bounds, manifold?, verdict, area, ratio) over the declared points."""
    if not tris:
        return 0, False, "no-triangles", 0.0, 0.0
    n = len(points)
    in_b = all(all(0 <= v < n for v in t) for t in tris)
    if not in_b:
        return False, False, "out-of-index-space", 0.0, 0.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    diag = math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))
    area = 0.0
    degen = False
    for a, b, c in tris:
        pa, pb, pc = points[a], points[b], points[c]
        ux, uy, uz = (pb[k] - pa[k] for k in range(3))
        vx, vy, vz = (pc[k] - pa[k] for k in range(3))
        cx, cy, cz = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
        t = 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
        if t == 0.0:
            degen = True
        area += t
    m, verdict = manifold(tris)
    ratio = area / (diag * diag) if diag > 0 else math.inf
    if degen:
        verdict = "degenerate"
    return in_b, m, verdict, area, ratio


def fast_arrays(data, lo, hi):
    """Count-first point arrays with bounded verification.

    probe_bagrep.declared_arrays verifies every candidate over the full
    ``V`` floats (O(V) per candidate; on the dense missing-store spans
    the candidate count × V dominates the runtime). The probe only needs
    the record's own point array, so the same count-first shape is
    verified over a bounded 96-word window: finite, >= 50% non-zero, no
    constant run > 64 — a fill artifact cannot pass, a real tessellation
    array always does on its head.
    """
    out = []
    seen = set()
    unpack = struct.Struct("<I").unpack_from
    view = memoryview(data)
    for o in range(lo, max(lo, hi - 4)):
        if data[o + 3]:
            continue
        v = unpack(data, o)[0]
        if v < 9 or v > 3_000_000 or v % 3:
            continue
        s = o + 4
        if s + 4 * v > hi:
            continue
        words = view[s : s + 4 * v].cast("f")
        head = words[:96]
        ok = True
        nz = 0
        prev = None
        const = 1
        for w in head:
            if not (w == w and abs(w) < 1e9):
                ok = False
                break
            if w != 0.0:
                nz += 1
            if prev is not None and w == prev:
                const += 1
                if const > 64:
                    ok = False
                    break
            else:
                const = 1
            prev = w
        if not ok or len(head) < 9 or nz < 0.5 * len(head):
            continue
        if (s, v) not in seen:
            seen.add((s, v))
            out.append((o, s, v, v // 3))
    out.sort(key=lambda x: (x[1], -x[2]))
    keep = []
    for item in out:
        if any(
            k[1] <= item[1] and k[1] + 4 * k[2] >= item[1] + 4 * item[2] for k in keep
        ):
            continue
        keep.append(item)
    return keep


def probe_file(rel, meta):
    path = os.path.join(ROOT, meta["local"])
    with open(path, "rb") as fh:
        data = fh.read()
    subs_tried = closed = consumed = oob_records = 0
    tris_total = 0
    best = (False, "-", 0.0, 0.0)
    meshes = []
    physical_only = []
    spans = class_record_spans(data)
    framed = [s for s in spans if subrecord_positions(data, s[0], s[1])]
    if not framed:
        # the whole-file framing (the CAAMai family: the bag-rep records
        # sit outside the named containers): chunk the sub-records by
        # next match to EOF.
        raw = subrecord_positions(data, 0, len(data))
        framed = [(p, raw[j + 1] if j + 1 < len(raw) else len(data), "?") for j, p in enumerate(raw)]
    for start, end, nm in framed:
        pos = subrecord_positions(data, start, end)
        if not pos:
            continue
        arrays = fast_arrays(data, start, end)
        points = []
        if arrays:
            _coff, astart, floats, npts = max(arrays, key=lambda a: a[3])
            points = [
                struct.unpack_from("<3f", data, astart + 12 * i) for i in range(npts)
            ]
        for j, p in enumerate(pos):
            if data[p + 8] == 0x00:
                continue  # the boundary artifact
            nxt = pos[j + 1] if j + 1 < len(pos) else end
            res = face_gp(data, p, nxt)
            subs_tried += 1
            closed += res["closed_exact"]
            consumed += res["consumed_all"]
            tris_total += len(res["tris"])
            if not points:
                continue
            in_b, m, verdict, area, ratio = mesh_report(points, res["tris"])
            if not in_b:
                oob_records += 1
                continue
            if m and verdict == "manifold" and 0 < ratio <= PHYSICAL_RATIO_MAX:
                meshes.append((len(res["tris"]), area, ratio))
                if ratio > best[3] or best[0] is False:
                    best = (True, verdict, area, ratio)
            elif verdict == "over-use" and 0 < ratio <= PHYSICAL_RATIO_MAX:
                # physical but over a partial patch set: the manifold
                # bar needs every patch of the record; report the
                # near-miss separately
                physical_only.append((len(res["tris"]), area, ratio))
    return {
        "rel": rel,
        "subs": subs_tried,
        "closed": closed,
        "consumed": consumed,
        "oob": oob_records,
        "tris": tris_total,
        "meshes": meshes,
        "physical_only": physical_only,
        "best": best,
    }


def main():
    man = load_manifest(ROOT)
    rows = list(csv.DictReader(open(os.path.join(ROOT, "docs", "evidence", "data", "bagrep-probe.csv"))))
    carriers = [r["path"] for r in rows if int(r["subrecords"] or 0) > 0]
    extra = [
        r["path"]
        for r in csv.DictReader(open(os.path.join(ROOT, "manifests", "corpus-manifest.csv")))
        if "CAAMaiUserToolDatabase" in r["path"]
    ]
    report = json.load(open(LATEST_REPORT))
    l2 = {f["path"]: f["l2"] for f in report["files"]}
    dev_total = report["scalars"]["L2"]["dev"]["total"]
    dev_pass = report["scalars"]["L2"]["dev"]["pass"]

    print(f"carriers: {len(carriers)} + extra {extra}")
    total_subs = total_closed = total_consumed = total_oob = 0
    flip = []
    mesh_files = 0
    probe_cache = {}
    for rel in carriers + extra:
        meta = man.get(rel)
        if meta is None:
            print(f"  manifest miss: {rel}")
            continue
        r = probe_file(rel, meta)
        probe_cache[rel] = r
        if r["meshes"]:
            mesh_files += 1
        total_subs += r["subs"]
        total_closed += r["closed"]
        total_consumed += r["consumed"]
        total_oob += r["oob"]
        cur = l2.get(rel, {}).get("status", "?")
        mesh_count = len(r["meshes"])
        phys_only = len(r["physical_only"])
        physical = mesh_count > 0 and r["best"][0]
        mark = ""
        if physical and cur == "fail":
            flip.append(rel)
            mark = "  <-- FLIPS to pass"
        print(
            f"  {rel[-58:]:58} subs={r['subs']:>3} closed@len-1={r['closed']:>3} "
            f"consumed_all={r['consumed']:>3} oob={r['oob']:>3} tris={r['tris']:>5} "
            f"meshes={mesh_count:>3} phys_only={phys_only:>3} ratio={r['best'][3]:.3f} l2={cur}{mark}"
        )
    print(f"\nsub-records tried: {total_subs}")
    print(f"  close exactly at len-1: {total_closed}")
    print(f"  consume every byte:     {total_consumed}")
    print(f"  out-of-index-space:     {total_oob}")
    print(f"files with >=1 manifold+physical mesh: {mesh_files}")
    print(f"files with >=1 physical-but-not-manifold mesh: "
          f"{sum(1 for rel in carriers + extra if rel in man and probe_cache[rel]['physical_only'])}")
    print(f"currently-L2-fail files that flip: {len(flip)}")
    print(
        f"projected L2 dev: {dev_pass}/{dev_total} = {dev_pass / dev_total:.4f} -> "
        f"{dev_pass + len(flip)}/{dev_total} = {(dev_pass + len(flip)) / dev_total:.4f} "
        f"(+{len(flip)}/{dev_total} = +{len(flip) / dev_total * 100:.2f} pp)"
    )
    for rel in flip:
        print(f"    flip: {rel}")


if __name__ == "__main__":
    main()
