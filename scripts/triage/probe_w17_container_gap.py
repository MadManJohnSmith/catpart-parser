#!/usr/bin/env python3
"""W17 container gap dump (read-only, 2026-11-22).

Dumps the bytes between the container node's raw f32 triple window
(counts_end+4 .. +12*c1) and its first accepted strip record, in
structured views, to one output file per node, plus a summary line:

- the gap length and its hex (rows of 16);
- u32le words of the first 64 B;
- the counts_end, window bounds, first-record offset (payload-relative).

Run::

    .venv/bin/python -I scripts/triage/probe_w17_container_gap.py \
        <file.CATPart>... --out-dir <dir>

Read-only over the corpus; writes only to the --out-dir.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catpart.geometry import composite  # noqa: E402

from probe_w17_container_scan import scan_file  # noqa: E402


def dump_node(path, data, npos, payload, c1, c2, outdir):
    counts_end = composite._token_counts_end(payload)
    if payload[counts_end : counts_end + 4] != b"\x00\x00\x00\x01":
        return
    start = counts_end + 4
    end = start + 12 * c1
    # first accepted strip record at/after the window end
    rec_off = None
    try:
        records, _n = composite.parse_strip_records(
            data, npos + 4 + end, npos + 4 + len(payload), c1
        )
        if records:
            rec_off = records[0][0] - (npos + 4)
    except Exception:
        pass
    gap_hi = rec_off if rec_off is not None else len(payload)
    gap = payload[end:gap_hi]
    name = os.path.basename(path)
    out = [f"# {name} node@0x{npos:x} c1={c1} c2={c2} payload={len(payload)}B"]
    out.append(f"# counts_end={counts_end} window=[{start},{end}) "
               f"first_record={rec_off} gap=[{end},{gap_hi}) len={len(gap)}B")
    for i in range(0, len(gap), 16):
        row = gap[i : i + 16]
        out.append(f"{i:06x}  {row.hex(' ')}")
    out.append("# first 64 B as u32le:")
    for w in range(0, min(64, len(gap)) - 3, 4):
        out.append(
            f"  +{w:03x}: u32le={int.from_bytes(gap[w:w+4], 'little'):<12} "
            f"u16x2=({int.from_bytes(gap[w:w+2],'little')},"
            f"{int.from_bytes(gap[w+2:w+4],'little')})"
        )
    fname = os.path.join(outdir, f"{name}.node{npos:x}.gapdump.txt")
    with open(fname, "w") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"{name} node@0x{npos:x}: c1={c1} c2={c2} gap={len(gap)}B "
          f"[{end},{gap_hi}) -> {fname}")
    return len(gap)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    for path in args.paths:
        data, nodes = scan_file(path)
        for npos, payload, c1, c2 in nodes:
            dump_node(path, data, npos, payload, c1, c2, args.out_dir)


if __name__ == "__main__":
    main()
