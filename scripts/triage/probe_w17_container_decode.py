#!/usr/bin/env python3
"""W17 container-payload micro-decode (read-only, 2026-11-22).

Hypothesis H1: the W10 head-record container node payload is

    [token][c1][c2]["00 00 00 01"][c1 raw f32 triples][0xFF?][more...]

where the triples are the node's OWN point region and the trailing
bytes are facet records resolving against that same space.  This probe
measures, per container-family hit:

1. the nice-rate (the raw scan's predicate) of the triples window
   at counts_end+4 .. +12*c1;
2. the byte at the window's end (trail byte — P1g escape candidate);
3. the first 96 bytes after the window (hex + words);
4. whether composite.parse_strip_records parses records AFTER the
   window against the c1 space, and how many / which markers;
5. whether the payload window [counts_end+4 .. +12*c1] walks exact as
   a RAW ARRAY under the committed stage-4a law
   (composite._raw_escape_probe needs start in [32,64] — these nodes'
   counts_end+4 is typically small, so probe the exact start too).

Run::

    .venv/bin/python -I scripts/triage/probe_w17_container_decode.py <file.CATPart>...

Read-only; no src/ change.
"""

import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import composite  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_w17_container_scan import scan_file  # noqa: E402


def raw_nice(v):
    return v == v and (v == 0.0 or 1e-6 < abs(v) < 1e7)


def probe(path):
    data, nodes = scan_file(path)
    printed_header = False
    for npos, payload, c1, c2 in nodes:
        counts_end = composite._token_counts_end(payload)
        if counts_end is None:
            continue
        if payload[counts_end : counts_end + 4] != b"\x00\x00\x00\x01":
            continue
        if not printed_header:
            print(f"== {path}")
            printed_header = True
        start = counts_end + 4
        end = start + 12 * c1
        fits = end <= len(payload)
        nice = 0
        xs = []
        if fits:
            for k in range(c1):
                x, y, z = struct.unpack_from("<fff", payload, start + 12 * k)
                nice += raw_nice(x) and raw_nice(y) and raw_nice(z)
                xs.append(x)
        rate = nice / c1 if c1 else 0.0
        trail = payload[end] if end < len(payload) else None
        asc = (
            sum(1 for a, b in zip(xs, xs[1:]) if b >= a - 1e-6) / (c1 - 1)
            if c1 > 1
            else 1.0
        )
        after = payload[end : end + 96] if fits else b""
        print(f"\n  node@0x{npos:x} payload={len(payload)}B c1={c1} c2={c2}")
        print(
            f"    triples window [{start}, {end}) fits={fits} "
            f"nice-rate={rate:.3f} x-asc={asc:.3f} trail-byte={trail if trail is None else hex(trail)}"
        )
        print(f"    after window: {after.hex()}")
        # words of the tail, LE u32 + f32 views
        for w in range(0, min(48, len(after)) - 3, 4):
            word = after[w : w + 4]
            f, = struct.unpack("<f", word)
            print(
                f"      +{w:02x}: {word.hex()} le_u32={int.from_bytes(word, 'little'):<11} f32={f:<14.6g}"
                + ("" if w else "   <-- trail word")
            )
        # records AFTER the point window against the c1 space?
        if fits:
            for rstart, label in (
                (end + 1, "after trail byte"),
                (end, "at window end"),
            ):
                try:
                    records, n_hdrs = composite.parse_strip_records(
                        data, npos + 4 + rstart, npos + 4 + len(payload), c1
                    )
                except ExportError as exc:
                    print(f"    strip @{label}: ExportError {exc.detail[:80]}")
                    continue
                print(
                    f"    strip @{label}: {len(records)} records "
                    f"({n_hdrs} hdrs) markers="
                    f"{sorted({hex(mk) for _o, mk, *_r in records})}"
                )
                for o, mk, normal, counts, refs, width in records[:4]:
                    print(
                        f"      rec@0x{o - (npos + 4):x} mk=0x{mk:02x} k={len(counts)} "
                        f"w={width} refs={refs[:6]}{'...' if len(refs) > 6 else ''} "
                        f"max_ref={max(refs) if refs else '-'}"
                    )


def main():
    for path in sys.argv[1:]:
        probe(path)


if __name__ == "__main__":
    main()
