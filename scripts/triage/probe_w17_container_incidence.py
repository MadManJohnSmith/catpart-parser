#!/usr/bin/env python3
"""W17 container-family incidence (read-only, 2026-11-22).

Fast byte-level sweep: every .CATPart's composite-store territory is
scanned for token nodes whose counts end carries ``00 00 00 01`` (the
W17 container family) — no export, no decode beyond the node scan, so
it runs at byte-scan speed over the whole corpus.  Per hit: the
container decode is attempted (the committed ``_container_decode``)
and the result recorded (decoded / declined-with-reason).

Run::

    .venv/bin/python -I scripts/triage/probe_w17_container_incidence.py \
        --out <csv> <dir>...
"""

import argparse
import csv
import gc
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from catpart.geometry import composite, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

from probe_w17_container_scan import scan_nodes  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    files = []
    for root in args.dirs:
        for dirpath, _dirs, names in os.walk(root):
            for nm in sorted(names):
                if nm.lower().endswith(".catpart"):
                    files.append(os.path.join(dirpath, nm))
    fields = [
        "part", "nodes", "walk_exact", "containers_decoded",
        "containers_declined", "decline_reason_short",
    ]
    nfiles = nhits = 0
    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for i, path in enumerate(files):
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                continue
            nfiles += 1
            size = len(data)
            d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
            blocks = store.valid_blocks(data)
            classes = {"walk-exact": 0}
            decoded = declined = 0
            reason = ""
            hit = False
            for blk, nm in blocks:
                try:
                    span = store.locate_store(data, blk, blocks, d8_outer)
                except ExportError:
                    continue
                if span is None:
                    continue
                for _p, payload, c1, _c2 in scan_nodes(
                    data, span.body_lo, span.body_hi
                ):
                    counts_end = composite._token_counts_end(payload)
                    if counts_end is None:
                        continue
                    try:
                        composite._region_decode_with_extent(payload, c1)
                        classes["walk-exact"] += 1
                        continue
                    except ExportError:
                        pass
                    if payload[counts_end : counts_end + 4] == b"\x00\x00\x00\x01":
                        hit = True
                        cont = composite._container_decode(payload, c1)
                        if cont is None:
                            declined += 1
                            end = counts_end + 4 + 12 * c1
                            reason = (
                                "window-overruns"
                                if end > len(payload)
                                else "implausible"
                            )
                        else:
                            decoded += 1
                break
            if hit:
                nhits += 1
                w.writerow({
                    "part": os.path.basename(path),
                    "nodes": "",
                    "walk_exact": classes["walk-exact"],
                    "containers_decoded": decoded,
                    "containers_declined": declined,
                    "decline_reason_short": reason,
                })
            if (i + 1) % 250 == 0:
                print(f".. {i + 1}/{len(files)} files, {nhits} hits", flush=True)
            del data
            gc.collect()
    print(f"== {nfiles} files scanned, {nhits} files carry container nodes -> {args.out}")


if __name__ == "__main__":
    main()
