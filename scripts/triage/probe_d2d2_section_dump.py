#!/usr/bin/env python3
"""Section-header micro-probe of the ``d2 d2 50|51`` patch sub-records
(read-only, 2026-11-20, #63 lever 2).

For the anchor parts the bag-rep census framed (``Plate.CATPart`` — the
``CATSurfacicRep`` with 10 sub-records; ``CAAMaiUserToolDatabaseCustomization``
— the ``CATSurfacicRep`` with 18 sub-records), every sub-record
``30 04 04 ff ff ff d2 d2 50|51`` is dumped annotated from +57 (the
counter block the prior forensics pinned) to the start of the next
sub-record:

- the hex, 16 B rows with sub-record-relative offsets;
- every ``ff 7f`` pair with its exact surrounding bytes (4 before,
  2 the pair, 4 after);
- the u16be index-like runs — maximal consecutive u16be words below
  1024 — each with its [start, end) sub-record-relative offsets, its
  word count, the mult-3 flag and the value range (the word parity is
  chosen per sub-record: even or odd relative offset, whichever reads
  the higher share of sub-1024 words);
- the section changes — positions where a word leaves the index range
  or the ``ff 7f``/run boundaries sit — with their surrounding bytes.

Regions longer than ``--max-region`` bytes are dumped to the cap with
the remaining length named.

Run::

    .venv/bin/python -I scripts/triage/probe_d2d2_section_dump.py \
        [--max-region 256] [manifest-name-substring ...]

Read-only over the corpus; no ``src/`` change.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "triage"))

from probe_bagrep import SUBREC, load_manifest, payload_regions, records  # noqa: E402

IDX_MAX = 1024
DUMP_FROM = 57


def word_runs(seg, start_rel, parity, order):
    """Maximal u16<1024 runs over [start_rel, len(seg)) at one parity/order.

    Returns (runs) with runs = (rel_start, rel_end, values)."""
    runs = []
    cur = None
    o = start_rel + ((parity - start_rel) % 2)
    while o + 2 <= len(seg):
        v = int.from_bytes(seg[o : o + 2], order)
        if v < IDX_MAX:
            if cur is None:
                cur = [o, o + 2, []]
            cur[1] = o + 2
            cur[2].append(v)
        else:
            if cur is not None and len(cur[2]) >= 3:
                runs.append(tuple(cur))
            cur = None
        o += 2
    if cur is not None and len(cur[2]) >= 3:
        runs.append(tuple(cur))
    return runs


def best_reading(seg, start_rel):
    """(order, parity, share) maximizing the sub-1024 word share."""
    best = (None, 0, 0.0)
    for order, oname in (("big", "u16be"), ("little", "u16le")):
        for parity in (0, 1):
            o = start_rel + ((parity - start_rel) % 2)
            n = idx = 0
            while o + 2 <= len(seg):
                n += 1
                if int.from_bytes(seg[o : o + 2], order) < IDX_MAX:
                    idx += 1
                o += 2
            if n and idx / n > best[2]:
                best = (oname, parity, idx / n)
    return best


def context(seg, pos, before=4, after=4):
    lo = max(0, pos - before)
    hi = min(len(seg), pos + 2 + after)
    return seg[lo:hi].hex(" ")


def dump_subrecord(data, p, end, max_region):
    rel_end = min(end - p, DUMP_FROM + max_region)
    seg = data[p : p + rel_end]
    cut = end - p > rel_end
    if data[p + 8] == 0x00:
        print(
            f"  sub-record match @{p} type=0x00 — boundary artifact "
            f"(next bytes {data[p + 9 : p + 13].hex(' ')} = node magic), "
            "not a patch sub-record; skipped"
        )
        return
    print(
        f"  sub-record @{p} len={end - p}B type=0x{data[p + 8]:02x} "
        f"header(+0..+56): {data[p : p + 57].hex(' ')}"
    )
    print(f"    +57..{rel_end}" + (" (CAPPED)" if cut else "") + ":")
    ff7f = []
    o = DUMP_FROM
    while True:
        o = seg.find(b"\xff\x7f", o)
        if o < 0 or o >= rel_end:
            break
        ff7f.append(o)
        o += 1
    first_ff = ff7f[0] if ff7f else None
    if first_ff is not None:
        # the index stream starts right after the ff 7f pair: its parity
        # and the 00-xx big-endian alignment are fixed by the marker
        oname, parity, share = "u16be", (first_ff + 2) % 2, None
        order = "big"
        runs = word_runs(seg, first_ff + 2, parity, order)
    else:
        oname, parity, share = best_reading(seg, DUMP_FROM)
        order = "big" if oname == "u16be" else "little"
        runs = word_runs(seg, DUMP_FROM, parity, order)
    run_starts = {r[0]: r for r in runs}
    run_ends = {r[1]: r for r in runs}
    for r in range(DUMP_FROM, rel_end, 16):
        row = seg[r : min(r + 16, rel_end)]
        tags = []
        for j in range(r, min(r + 16, rel_end)):
            if j in run_starts:
                s, e, vals = run_starts[j]
                tags.append(
                    f"RUN[{s},{e}) {oname} len={len(vals)} "
                    f"mult3={len(vals) % 3 == 0} min={min(vals)} max={max(vals)}"
                )
            if j in run_ends:
                tags.append(f"run-end@{j}")
            if j in ff7f:
                tags.append(f"ff7f@{j} ctx={context(seg, j)}")
        hexs = row.hex(" ")
        if tags:
            print(f"    +{r:>4}: {hexs:<47} | {'; '.join(tags)}")
        else:
            print(f"    +{r:>4}: {hexs}")
    # section changes: non-index words inside the post-ff7f stream zone
    # with their surrounding bytes
    lo = DUMP_FROM if first_ff is None else first_ff + 2
    breaks = []
    o = lo + ((parity - lo) % 2)
    while o + 2 <= rel_end:
        v = int.from_bytes(seg[o : o + 2], order)
        if v >= IDX_MAX and o not in run_ends:
            breaks.append(o)
        o += 2
    if breaks:
        print(
            "    section changes (non-index words in the stream zone): "
            + "; ".join(f"@{b} ctx={context(seg, b)}" for b in breaks[:12])
        )
    if ff7f:
        print(
            "    ff 7f contexts: "
            + "; ".join(f"@{j} [{context(seg, j)}]" for j in ff7f)
        )
    print(
        f"    reading: {oname} parity={parity}"
        + (f" sub-1024 share={share:.2f}" if share is not None else "")
        + (f" first-ff7f@{first_ff}" if first_ff is not None else " (no ff 7f)")
    )
    if cut:
        print(f"    ... {end - p - rel_end}B more to the next sub-record (capped)")


def probe_file(rel, meta, max_region):
    path = os.path.join(ROOT, meta["local"] if "local" in meta else meta["path"])
    with open(path, "rb") as fh:
        data = fh.read()
    print(f"\n== {rel} ({len(data)}B sha {meta['sha256'][:16]})")
    from catpart.geometry import store as _store

    blocks = _store.valid_blocks(data)
    d8 = int.from_bytes(data[8:12], "big") if len(data) >= 12 else 0
    regions = payload_regions(data, blocks, d8)
    spans = []
    for _name, lo, hi in regions:
        spans.extend(records(data, lo, hi))
    subs_all = []
    pos = []
    i = 0
    while True:
        i = data.find(SUBREC, i)
        if i < 0:
            break
        pos.append(i)
        i += 1
    covered = [p for p in pos if any(lo <= p < hi for _n, lo, hi in regions)]
    if covered:
        for start, nm, _ne, end in spans:
            ins = [p for p in pos if start <= p < end]
            if ins:
                print(f"  record {nm} [{start},{end}) {end - start}B subrecs={len(ins)}")
                for j, p in enumerate(ins):
                    nxt = ins[j + 1] if j + 1 < len(ins) else end
                    dump_subrecord(data, p, nxt, max_region)
        return
    # the unnamed-region family (CAAMaiUserToolDatabase*): the bag-rep
    # records sit outside the named containers — frame class records
    # over the whole file.
    found = []
    for name, n in ((b"CAT3DBagRep", 11), (b"CATSurfacicRep", 14)):
        p = 0
        while True:
            p = data.find(name, p)
            if p < 0:
                break
            if p >= 4 and int.from_bytes(data[p - 4 : p], "little") == n:
                found.append((p - 4, name.decode(), p + len(name)))
            p += 1
    found.sort()
    if not found:
        print("  no class records and no sub-records in named regions")
        return
    recs = []
    for i2, (start, nm, _ne) in enumerate(found):
        end = found[i2 + 1][0] if i2 + 1 < len(found) else len(data)
        ins = [p for p in pos if start <= p < end]
        if ins:
            recs.append((start, nm, end, ins))
    if not recs:
        print("  class records found but none contains a d2 d2 sub-record")
        return
    for start, nm, end, ins in recs:
        print(f"  record {nm} [{start},{end}) {end - start}B subrecs={len(ins)}")
        for j, p in enumerate(ins):
            nxt = ins[j + 1] if j + 1 < len(ins) else end
            dump_subrecord(data, p, nxt, max_region)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="manifest path substrings")
    ap.add_argument("--max-region", type=int, default=256)
    args = ap.parse_args()
    man = load_manifest(ROOT)
    rows = list(man.items())
    if args.names:
        picked = [
            (rel, m)
            for rel, m in rows
            if any(name.lower() in rel.lower() for name in args.names)
        ]
    else:
        picked = [
            (rel, m)
            for rel, m in rows
            if rel.endswith("Plate.CATPart") or "CAAMaiUserToolDatabase" in rel
        ]
    for rel, m in picked:
        probe_file(rel, m, args.max_region)


if __name__ == "__main__":
    main()
