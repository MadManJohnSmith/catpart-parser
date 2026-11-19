#!/usr/bin/env python3
"""Bag-rep payload probe: does the missing-store carrier hold faces or only
points? (2026-11-19, read-only).

Scope: the 103 payload-bearing parts of the ``missing-geometry-store``
population characterized in
``docs/evidence/2026-11-19-missing-store.md`` (61 ``point-array`` + 25
``topology-only`` + 17 ``bag-rep-named``). That census established the
files carry no stream store, no pool group and no vertex-record stream;
this probe answers the one question left: does the carrier it *did*
find — the bag-rep payload — hold **connectivity** (faces, index lists,
facet records) or **only points**?

Method (all byte facts, stdlib + the committed measurement
infrastructure; deterministic, manifest order):

- **record framing**: a class record is a ``u32le`` length equal to the
  ASCII class name's length immediately followed by the name
  (``CAT3DBagRep`` 11 B, ``CATSurfacicRep`` 14 B). The record span runs
  to the next class name, or to the payload region's end. The 8 bytes
  after the name (the variant / kind bytes) are reported raw: their
  semantics are not established here.
- **node records**: the ``04 fd ff`` tag and the ``04 ff ff ff ff ff 01``
  form the ``CAT3DBagRepT`` records carry, with the flag byte in front of
  them (the census's 4-byte ``04 04 fd ff`` pattern is one flag value of
  this family, so its count undercounts).
- **point arrays, count-first**: a ``u32le V`` field (``V % 3 == 0``,
  ``9 <= V <= 3e6``) whose next ``V`` f32 at one 4-byte frame are all
  clean (finite, zero or ``1e-6 <= |v| <= 1e6``) *and* which end where the
  clean run ends. The declared float count is what separates a real array
  from a byte pattern that merely reads as plausible floats — the previous
  note's "21,846-point run" in ``AnalysisMechfeat`` is that artifact (a run
  of repeated ``0.5`` words; see the note).
- **connectivity, three ways**: (1) **index lists** — runs at four widths
  and both byte orders (u16le/u16be/u32le/u32be; ``u8`` is too dense to be
  evidence at these point counts) whose every value is inside the span's
  own point space, which reach that space's top and which vary, at a
  length a face law could use (multiple of 3, >= 6); (2) **facet/strip
  records** — ``01 41..4f .. ff`` headers under the pinned facet grammar,
  accepted only when the record tiles exactly to the next header (the
  strict test the shipped decoders use); (3) the **scene-graph list token**
  ``ff ff 02 00 01``, counted because the 2-bit table law hangs off it.
- **the patch sub-record stream** (``30 04 04 ff ff ff d2 d2 50|51``):
  counted and its u16be words tallied, not decoded — it is the one carrier
  whose layout is not pinned, so the note names it as the reopen criterion.

Run::

    .venv/bin/python -I scripts/triage/probe_bagrep.py \
        [--out docs/evidence/data/bagrep-probe.csv] \
        [--anchor <manifest path>] [--anchors]

``--anchors`` frames the six anchor files: three ``bag-rep-named``
(``Plate``, ``Screw``, ``CAAKhwRuleBaseCreate``) and three
``point-array`` (``AnalysisMechfeat``, ``CAAMmrTableWood``,
``Bundle_Segment2``).

Read-only with respect to the corpus; no ``src/`` change.
"""

import argparse
import csv
import math
import os
import struct
import sys
from itertools import accumulate

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import facets, store  # noqa: E402

CENSUS = os.path.join(ROOT, "docs", "evidence", "data", "missing-store-census.csv")

PAYLOAD_BLOCKS = (
    "CATStdCont",
    "CATSeeBodyCont",
    "CATBRepModeContainer",
    "CGMGeom",
    "CATCGRCont",
)

#: Class records the payload carries, with their declared name lengths.
CLASSES = ((b"CAT3DBagRep", 11), (b"CATSurfacicRep", 14))

NODE_TAG = b"\x04\xfd\xff"
NODE_TAG_T = b"\x04\xff\xff\xff\xff\xff\x01"
LIST_TOKEN = b"\xff\xff\x02\x00\x01"

#: The second stream the bag-rep records carry: a per-patch sub-record the
#: census did not name (``30`` flag, the node tag, then ``d2 d2`` and a
#: per-patch type byte ``50``/``51``). Its field layout is NOT pinned here;
#: the probe counts it so the note can name it as the reopen criterion.
SUBREC = b"\x30\x04\x04\xff\xff\xff\xd2\xd2"

MAX_DECLARED = 3_000_000

#: Minimum non-zero share for a declared array: a block of zeros passes the
#: clean-f32 test and would frame a count by accident.
MIN_NONZERO = 0.5

#: Longest run of identical consecutive f32 words a coordinate array may
#: carry. A tessellation/point array never repeats one word 64 times in a
#: row; a fill region does — this is what separates the ``AnalysisMechfeat``
#: 0.5 fill the previous note counted as a 21,846-point array from a real
#: array.
MAX_CONST_RUN = 64

ANCHORS = (
    "online/CAAScdAsmUseCases/samples/Plate.CATPart",
    "online/CAAScdAsmUseCases/samples/Screw.CATPart",
    "online/CAAScdKhwUseCases/samples/CAAKhwRuleBaseCreate.CATPart",
    "online/CAAScdAniUseCases/samples/AnalysisMechfeat.CATPart",
    "online/CAAMmrTechArticles/images/CAAMmrTableWood.CATPart",
    "online/CAAEwrUseCases/samples/Bundle_Segment2.CATPart",
)


def load_manifest(corpus_root):
    out = {}
    with open(os.path.join(ROOT, "manifests", "corpus-manifest.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            out[row["path"]] = {
                "sha256": row["sha256"],
                "repo": row["repo"],
                "split": row["split"],
                "local": os.path.join(corpus_root, row["local_path"]),
            }
    return out


def header_family(data):
    if len(data) < 32 or data[:8] != store.V5_CFV2:
        return "non-catia"
    return "ff8" if data[16:24] == b"\xff" * 8 else "dual-catalog"


def payload_regions(data, blocks, d8):
    """(name, lo, hi) for the geometry containers, in block order."""
    out = []
    for blk, name in blocks:
        if name in PAYLOAD_BLOCKS:
            out.append((name, blk, store.probe_region(data, blk, blocks, d8)))
    return out


def records(data, lo, hi):
    """Class records in [lo,hi): (span_lo, name, name_end, span_hi)."""
    found = []
    for name, n in CLASSES:
        pos = lo
        while True:
            pos = data.find(name, pos, hi)
            if pos < 0:
                break
            if pos >= 4 and int.from_bytes(data[pos - 4 : pos], "little") == n:
                found.append((pos - 4, pos, name))
            pos += 1
    found.sort()
    out = []
    for i, (start, name_off, name) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else hi
        out.append((start, name.decode(), name_off + len(name), end))
    return out


def _clean_f32(v):
    if not math.isfinite(v):
        return False
    return v == 0.0 or 1e-6 <= abs(v) <= 1e6


class Clean(object):
    """Clean-f32 prefix sums for the four 4-byte frames of a window."""

    def __init__(self, data, lo, hi):
        self.data = data
        self.lo = lo
        self.hi = hi
        self.sum = {sh: [0] for sh in range(4)}
        view = memoryview(data)
        for sh in range(4):
            n = (hi - lo - sh) // 4
            if n <= 0:
                continue
            words = view[lo + sh : lo + sh + 4 * n].cast("f")
            self.sum[sh] = [0] + list(
                accumulate(
                    1 if (math.isfinite(v) and (v == 0.0 or 1e-6 <= abs(v) <= 1e6)) else 0
                    for v in words
                )
            )

    def _frames(self, start):
        rel = start - self.lo
        for sh in range(4):
            if rel < sh or (rel - sh) % 4:
                continue
            i = (rel - sh) // 4
            acc = self.sum[sh]
            if 0 <= i < len(acc) - 1:
                yield i, acc

    def clean_at(self, start):
        return any(
            acc[i + 1] - acc[i] == 1 for i, acc in self._frames(start)
        )

    def all_clean(self, start, count):
        if count <= 0:
            return False
        for i, acc in self._frames(start):
            if i + count < len(acc) and acc[i + count] - acc[i] == count:
                return True
        return False

    def nonzero(self, start, count):
        n = 0
        for i in range(count):
            if struct.unpack_from("<f", self.data, start + 4 * i)[0] != 0.0:
                n += 1
        return n / count if count else 0.0

    def max_const_run(self, start, count):
        """Longest run of identical consecutive f32 words."""
        best = run = 1
        prev = struct.unpack_from("<f", self.data, start)[0]
        for i in range(1, count):
            v = struct.unpack_from("<f", self.data, start + 4 * i)[0]
            if v == prev:
                run += 1
                if run > best:
                    best = run
            else:
                run = 1
                prev = v
        return best


def declared_arrays(data, lo, hi, clean=None):
    """Count-first point arrays: (count_off, start, floats, points).

    The declared count is the evidence that the array is an array: a long
    run of clean f32 can also be a byte pattern (a repeated ``0.5`` word),
    so the count has to sit in front of it, and the block must *end* where
    the clean run ends — otherwise every 9-float window inside a long
    quantized region would frame itself against some nearby integer.
    """
    if clean is None:
        clean = Clean(data, lo, hi)
    unpack = struct.Struct("<I").unpack_from
    out = []
    seen = set()
    for o in range(lo, hi - 4):
        # a count below 1e9 has a zero top byte; one byte test per offset
        # keeps the scan cheap on multi-hundred-KB payload regions.
        if data[o + 3]:
            continue
        v = unpack(data, o)[0]
        if v < 9 or v > MAX_DECLARED or v % 3:
            continue
        for delta in range(0, 17):
            s = o + 4 + delta
            if s + 4 * v > hi:
                break
            if not clean.all_clean(s, v):
                continue
            if clean.clean_at(s + 4 * v):
                continue
            if clean.nonzero(s, v) < MIN_NONZERO:
                continue
            if clean.max_const_run(s, v) > MAX_CONST_RUN:
                continue
            key = (s, v)
            if key not in seen:
                seen.add(key)
                out.append((o, s, v, v // 3))
            break
    # drop arrays contained in a longer array at the same or earlier start
    out.sort(key=lambda x: (x[1], -x[2]))
    keep = []
    for item in out:
        if any(
            k[1] <= item[1] and k[1] + 4 * k[2] >= item[1] + 4 * item[2] for k in keep
        ):
            continue
        keep.append(item)
    return keep


def non_declared_blocks(data, lo, hi, min_floats=9, min_nonzero=0.5):
    """Clean f32 blocks with no declared count (reported, not relied on)."""
    out = []
    for sh in range(4):
        cur = None
        o = lo + sh
        while o + 4 <= hi:
            if _clean_f32(struct.unpack_from("<f", data, o)[0]):
                if cur is None:
                    cur = [o, o]
                else:
                    cur[1] = o
            else:
                if cur:
                    out.append(tuple(cur))
                cur = None
            o += 4
        if cur:
            out.append(tuple(cur))
    blocks = []
    for a, b in out:
        n = (b - a) // 4 + 1
        if n < min_floats:
            continue
        vals = [struct.unpack_from("<f", data, a + 4 * i)[0] for i in range(n)]
        nz = sum(1 for v in vals if v != 0.0)
        if nz < min_nonzero * n:
            continue
        blocks.append((a, n))
    return blocks


def index_runs(data, lo, hi, n_points, min_len=6):
    """Integer runs bounded by n_points that reach the space's top.

    Tries the widths a face law could use: u16le, u16be, u32le, u32be.
    u8 is deliberately absent: with a point space of a few hundred, a
    six-byte run of bytes below the bound occurs at ~1 in 100 offsets, so
    a u8 "hit" cannot be told apart from noise at the length a face list
    needs. A hit must (a) keep every reference inside the point space,
    (b) run at least 6 entries, (c) reach the space's top (a list that
    never cites the last point is a count table, not an index list),
    (d) have a length a face law can split (multiple of 3), and (e) vary —
    a count followed by zeros is not a reference list.
    Returns (tag, start, length, max) per hit.
    """
    hits = []
    if n_points < 3:
        return hits
    for width, order in ((2, "little"), (2, "big"), (4, "little"), (4, "big")):
        tag = {1: "u8", 2: ("u16le", "u16be")[order == "big"], 4: ("u32le", "u32be")[order == "big"]}[width]
        o = lo
        while o + width <= hi:
            v = int.from_bytes(data[o : o + width], order)
            if v < n_points:
                s = o
                vals = []
                while o + width <= hi:
                    v = int.from_bytes(data[o : o + width], order)
                    if v >= n_points:
                        break
                    vals.append(v)
                    o += width
                if (
                    len(vals) >= min_len
                    and max(vals) >= n_points - 1
                    and len(vals) % 3 == 0
                    and len(set(vals)) >= 4
                    and vals.count(0) < len(vals) / 2
                ):
                    hits.append((tag, s, len(vals), max(vals)))
            else:
                o += width
    return hits


def subrecords(data, lo, hi):
    """(count, flag tally, index-like value tally) of the patch sub-records.

    The sub-record stream holds ``00 xx`` u16be words (values < 1024) in
    index-like ranges. The tally is reported, not interpreted: the stream's
    field layout is not pinned, and its values sit outside the record's own
    declared point space (see the note), so it cannot be an index list over
    the points this probe frames.
    """
    pos = []
    i = lo
    while True:
        i = data.find(SUBREC, i, hi)
        if i < 0:
            break
        pos.append(i)
        i += 1
    flags = {}
    n_lo = 0
    max_lo = -1
    for j, p in enumerate(pos):
        f = data[p + 8]
        flags[f] = flags.get(f, 0) + 1
        end = pos[j + 1] if j + 1 < len(pos) else hi
        for o in range(p + 9, end - 1, 2):
            v = int.from_bytes(data[o : o + 2], "big")
            if v < 1024:
                n_lo += 1
                max_lo = max(max_lo, v)
    return len(pos), flags, n_lo, max_lo


def facet_census(data, lo, hi):
    """(headers, exact_tiles) under the pinned facet grammar."""
    hdrs = [m.start() for m in facets.FACET_HEADER_RE.finditer(data, lo, hi)]
    exact = 0
    for i, o in enumerate(hdrs):
        hl = facets.header_len(data, o)
        if hl is None:
            continue
        nxt = hdrs[i + 1] if i + 1 < len(hdrs) else hi
        n, p = facets.read_count(data, o + hl)
        if not 0 < n < facets.MAX_REFS:
            continue
        for w in (1, 2):
            if p + n * w == nxt:
                exact += 1
                break
    return len(hdrs), exact


def node_flags(data, lo, hi):
    """Tally of the byte in front of each ``04 fd ff`` / ``04 ff ff``."""
    small = {}
    bag = {}
    for tag, tally in ((NODE_TAG, small), (NODE_TAG_T, bag)):
        pos = lo
        while True:
            pos = data.find(tag, pos, hi)
            if pos < 0:
                break
            flag = data[pos - 1] if pos > 0 else -1
            tally[flag] = tally.get(flag, 0) + 1
            pos += 1
    return small, bag



def segment(data, lo, hi, clean=None):
    """Measurements over one span: the whole region or one class record."""
    if clean is None:
        clean = Clean(data, lo, hi)
    arrays = declared_arrays(data, lo, hi, clean)
    points = max((a[3] for a in arrays), default=0)
    small, bag = node_flags(data, lo, hi)
    n_sub, sub_flags, sub_lo, sub_max = subrecords(data, lo, hi)
    return {
        "arrays": arrays,
        "bare": non_declared_blocks(data, lo, hi),
        "points": points,
        "index_runs": index_runs(data, lo, hi, points),
        "nodes": sum(small.values()),
        "nodes_t": sum(bag.values()),
        "subrecords": n_sub,
        "sub_flags": sub_flags,
        "sub_index_words": sub_lo,
        "sub_index_max": sub_max,
    }


def frame_record(data, rec, region_hi, clean=None):
    start, name, name_end, end = rec
    nxt = min(end, region_hi)
    m = segment(data, start, nxt, clean)
    m["start"] = start
    m["name"] = name
    m["end"] = nxt
    m["header"] = bytes(data[name_end:nxt][:10]).hex(" ")
    if name == "CATSurfacicRep":
        m["form"] = "surfacic"
    elif nxt > name_end and data[name_end] == 0x54:
        m["form"] = "t"
    else:
        m["form"] = "small"
    return m


def measure(row, meta):
    with open(meta["local"], "rb") as fh:
        data = fh.read()
    size = len(data)
    fam = header_family(data)
    blocks = store.valid_blocks(data)
    d8 = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    regs = payload_regions(data, blocks, d8)

    recs = []
    spans = []
    for _name, lo, hi in regs:
        clean = Clean(data, lo, hi)
        found = records(data, lo, hi)
        if found:
            for rec in found:
                r = frame_record(data, rec, hi, clean)
                recs.append(r)
                spans.append(r)
        else:
            s = segment(data, lo, hi, clean)
            s["start"] = lo
            s["name"] = _name
            s["end"] = hi
            s["header"] = ""
            spans.append(s)

    names = {}
    forms = {}
    for r in recs:
        names[r["name"]] = names.get(r["name"], 0) + 1
        forms[r["form"]] = forms.get(r["form"], 0) + 1
    arrays = [a for s in spans for a in s["arrays"]]
    bare = [b for s in spans for b in s["bare"]]
    idx = [x for s in spans for x in s["index_runs"]]
    fh_headers = fh_exact = 0
    for _name, lo, hi in regs:
        h, e = facet_census(data, lo, hi)
        fh_headers += h
        fh_exact += e
    tokens = sum(data.count(LIST_TOKEN, lo, hi) for _name, lo, hi in regs)
    n_sub = sum(s["subrecords"] for s in spans)
    sub_words = sum(s["sub_index_words"] for s in spans)
    sub_max = max((s["sub_index_max"] for s in spans), default=-1)

    biggest = max(arrays, key=lambda a: a[3], default=None)
    points_total = sum(a[3] for a in arrays)
    if fh_exact or idx:
        verdict = "faces"
    elif arrays or bare:
        verdict = "points-only"
    else:
        verdict = "no-payload"

    return {
        "path": row["path"],
        "sha256": meta["sha256"],
        "size_bytes": size,
        "header_family": fam,
        "geometry_class": row["geometry_class"],
        "bag_records": len(recs),
        "bag_record_names": ";".join(f"{k}x{v}" for k, v in sorted(names.items())),
        "records_small": forms.get("small", 0),
        "records_t": forms.get("t", 0),
        "records_surfacic": forms.get("surfacic", 0),
        "node_04fdff": sum(r["nodes"] for r in recs),
        "node_04ffff01": sum(r["nodes_t"] for r in recs),
        "subrecords": n_sub,
        "sub_index_words": sub_words,
        "sub_index_max": sub_max,
        "point_arrays": len(arrays),
        "points_total": points_total,
        "points_max": biggest[3] if biggest else 0,
        "points_max_offset": biggest[1] if biggest else -1,
        "largest_floats": biggest[2] if biggest else 0,
        "largest_declared_at": biggest[0] if biggest else -1,
        "bare_blocks": len(bare),
        "bare_max_floats": max((b[1] for b in bare), default=0),
        "index_runs": len(idx),
        "facet_headers": fh_headers,
        "facet_exact_tiles": fh_exact,
        "list_tokens": tokens,
        "census_point_run": row["point_run"],
        "verdict": verdict,
    }


def anchor(rel, meta):
    """Print the byte framing of one file (the note's pinned anchors)."""
    with open(meta["local"], "rb") as fh:
        data = fh.read()
    size = len(data)
    blocks = store.valid_blocks(data)
    d8 = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    print(f"path {rel}")
    print(
        f"size {size} sha256 {meta['sha256'][:16]}… "
        f"header_family {header_family(data)}"
    )
    for name, lo, hi in payload_regions(data, blocks, d8):
        print(f"  region {name:<22} [{lo}, {hi})  {hi - lo} B")
    for name, lo, hi in payload_regions(data, blocks, d8):
        recs = records(data, lo, hi)
        if not recs:
            m = segment(data, lo, hi)
            print(
                f"records in {name} @{lo}: none — unnamed payload, "
                f"{m['points']} points in {len(m['arrays'])} arrays, "
                f"subrec={m['subrecords']} nodes={m['nodes']}/{m['nodes_t']}"
            )
            for (coff, a, nf, npts) in m["arrays"]:
                pts = [
                    struct.unpack_from("<3f", data, a + 12 * i)
                    for i in range(min(2, npts))
                ]
                print(
                    f"      array declared@{coff}={nf} floats -> @{a} "
                    f"{npts} points  head="
                    f"{[tuple(round(c, 3) for c in p) for p in pts]}"
                )
            print(f"      index runs over {m['points']} points: {m['index_runs']}")
            continue
        print(f"records in {name} @{lo}:")
        for rec in recs:
            r = frame_record(data, rec, hi)
            print(
                f"  [{r['start']}, {r['end']}) {r['end'] - r['start']:>6} B "
                f"{r['name']:<14} post={r['header']:<23} "
                f"nodes={r['nodes']}/{r['nodes_t']} subrec={r['subrecords']}"
            )
            for (coff, a, nf, npts) in r["arrays"]:
                pts = [
                    struct.unpack_from("<3f", data, a + 12 * i)
                    for i in range(min(2, npts))
                ]
                print(
                    f"      array declared@{coff}={nf} floats -> @{a} "
                    f"{npts} points  head="
                    f"{[tuple(round(c, 3) for c in p) for p in pts]}"
                )
            if r["bare"]:
                print(f"      undeclared clean blocks: {r['bare'][:6]}")
            print(f"      index runs over {r['points']} points: {r['index_runs']}")
    h, e = facet_census(data, 0, size)
    print(f"facet headers whole file {h} exact tiles {e}")
    print(f"list tokens whole file {data.count(LIST_TOKEN)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--census", default=CENSUS)
    ap.add_argument("--corpus-root", default=ROOT)
    ap.add_argument(
        "--out",
        default=os.path.join(ROOT, "docs", "evidence", "data", "bagrep-probe.csv"),
    )
    ap.add_argument("--anchor", default=None, help="manifest path to frame")
    ap.add_argument("--anchors", action="store_true", help="frame the six anchors")
    args = ap.parse_args()

    manifest = load_manifest(args.corpus_root)
    if args.anchor:
        anchor(args.anchor, manifest[args.anchor])
        return
    if args.anchors:
        for rel in ANCHORS:
            anchor(rel, manifest[rel])
            print()
        return

    with open(args.census, newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["geometry_class"] != "non-catia"]

    out = [measure(r, manifest[r["path"]]) for r in rows]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out[0]))
        writer.writeheader()
        writer.writerows(out)

    print("rows", len(out), "payload-bearing", sum(1 for r in out if r["verdict"] == "points-only"))
    for key in ("geometry_class", "verdict", "header_family"):
        tally = {}
        for r in out:
            tally[r[key]] = tally.get(r[key], 0) + 1
        print(key, dict(sorted(tally.items())))
    print("bag records", sum(r["bag_records"] for r in out))
    print(
        "record forms",
        "small",
        sum(r["records_small"] for r in out),
        "t",
        sum(r["records_t"] for r in out),
        "surfacic",
        sum(r["records_surfacic"] for r in out),
    )
    print("node 04fdff", sum(r["node_04fdff"] for r in out))
    print("point arrays", sum(r["point_arrays"] for r in out))
    print("parts with an array", sum(1 for r in out if r["point_arrays"]))
    print("points total", sum(r["points_total"] for r in out))
    print("max points in one part", max((r["points_max"] for r in out), default=0))
    print("index runs", sum(r["index_runs"] for r in out))
    print("facet headers", sum(r["facet_headers"] for r in out))
    print("facet exact tiles", sum(r["facet_exact_tiles"] for r in out))
    print("list tokens", sum(r["list_tokens"] for r in out))
    print("parts with raw census run >= 3", sum(1 for r in out if int(r["census_point_run"]) >= 3))


if __name__ == "__main__":
    main()
