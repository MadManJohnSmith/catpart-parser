#!/usr/bin/env python3
"""W17 container-family scan (read-only, 2026-11-22).

Scans .CATPart files for the W10 head-record container family: token
nodes (``04 04 fd ff`` + LIST_TOKEN) whose point-region walk fails the
committed table law AND whose bytes right after the declared counts are
``00 00 00 01`` (W10's "second layout family" signature, U2).

Per hit this dumps:
- the node's absolute offset, payload length, elem_decl (c1), c2;
- the exact ``decode_region`` failure detail;
- the first 64 bytes after the counts (hex + u32le/BE words);
- whether a nested LIST_TOKEN / NODE_MAGIC lives inside the payload.

Census mode (``--census``) sweeps every .CATPart under the given
directories and counts per file: token nodes, walk-exact nodes, and
container-family hits, so sibling instances of the family can be found
outside the Submarino snapshot (which is absent on this host — the four
named parts LS-Valv-75 / LS-Muzzle / BW-Proa-A01B75 / BW-chain-vertical
are NOT locally available; W10's measured figures for them,
docs/evidence/marathon/w10-progress.md + marathon-w10-tail-claims.csv,
are the cross-reference).

Run::

    .venv/bin/python -I scripts/triage/probe_w17_container_scan.py <file.CATPart>...
    .venv/bin/python -I scripts/triage/probe_w17_container_scan.py --census <dir>...

Read-only; no src/ change.
"""

import argparse
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import composite  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

NODE_MAGIC = composite.NODE_MAGIC
LIST_TOKEN = composite.LIST_TOKEN


def scan_nodes(data, lo=0, hi=None):
    """All token nodes of one byte buffer within [lo, hi)."""
    if hi is None:
        hi = len(data)
    nodes = []
    pos = lo
    while True:
        pos = data.find(NODE_MAGIC, pos, hi)
        if pos < 0:
            break
        end = data.find(NODE_MAGIC, pos + 4, hi)
        if end < 0:
            end = hi
        payload = data[pos + 4 : end]
        tok = payload.find(LIST_TOKEN)
        if 0 <= tok <= 64:
            p = tok + 5
            try:
                c1, p = composite.read_count(payload, p)
                c2, p = composite.read_count(payload, p)
            except (IndexError, struct.error):
                pos += 1
                continue
            if 0 < c1 <= composite.MAX_ELEMENT_COUNT:
                nodes.append((pos, payload, c1, c2))
        pos += 1
    return nodes


def scan_file(path):
    """All token nodes of one file with their walk outcome."""
    with open(path, "rb") as fh:
        data = fh.read()
    return data, scan_nodes(data)


def classify(payload, c1):
    """(status, detail, counts_end) for one node payload."""
    try:
        _elements, info = composite.decode_region(payload, c1)
        return "walk-exact", "", info["walk_end"]
    except ExportError as exc:
        return "walk-fail", exc.detail, composite._token_counts_end(payload)


def dump_hit(data, pos, payload, c1, c2, detail, verbose=True):
    counts_end = composite._token_counts_end(payload)
    post = payload[counts_end : counts_end + 64] if counts_end is not None else b""
    head = []
    for w in range(0, min(16, len(post)), 4):
        word = post[w : w + 4]
        head.append(
            f"+{w:02x}: {word.hex()} le={int.from_bytes(word, 'little') if len(word) == 4 else '-'} "
            f"be={int.from_bytes(word, 'big') if len(word) == 4 else '-'}"
        )
    nested_tok = payload.find(LIST_TOKEN, counts_end)
    nested_node = payload.find(NODE_MAGIC, 4)
    zero_run = 0
    if counts_end is not None:
        while payload[counts_end + zero_run : counts_end + zero_run + 1] == b"\x00":
            zero_run += 1
    out = [
        f"  HIT node@0x{pos:x} payload={len(payload)}B c1={c1} c2={c2} "
        f"zero_run@counts_end={zero_run}",
        f"    fail: {detail}",
    ]
    out += ["    " + h for h in head]
    out.append(
        f"    nested LIST_TOKEN@{nested_tok} nested NODE_MAGIC@{nested_node} "
        f"(payload-relative)"
    )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--census", action="store_true")
    args = ap.parse_args()

    files = []
    if args.census:
        for root in args.paths:
            for dirpath, _dirs, names in os.walk(root):
                for nm in names:
                    if nm.lower().endswith(".catpart"):
                        files.append(os.path.join(dirpath, nm))
    else:
        files = args.paths

    total_nodes = exact = hits = 0
    hit_files = []
    for path in sorted(files):
        try:
            data, nodes = scan_file(path)
        except OSError as exc:
            print(f"SKIP {path}: {exc}")
            continue
        n_exact = 0
        file_hits = []
        for npos, payload, c1, c2 in nodes:
            status, detail, counts_end = classify(payload, c1)
            if status == "walk-exact":
                n_exact += 1
                continue
            post4 = payload[counts_end : counts_end + 4] if counts_end is not None else b""
            if post4 == b"\x00\x00\x00\x01":
                file_hits.append((npos, payload, c1, c2, detail))
        total_nodes += len(nodes)
        exact += n_exact
        if file_hits:
            hits += len(file_hits)
            hit_files.append(path)
            print(f"{path}: {len(nodes)} nodes ({n_exact} walk-exact), "
                  f"{len(file_hits)} CONTAINER-FAMILY hits")
            if not args.census or len(file_hits) <= 4:
                for h in file_hits:
                    print("\n".join(dump_hit(data, *h)))
    print(f"\n== census: {len(files)} files, {total_nodes} token nodes, "
          f"{exact} walk-exact, {hits} container-family hits in {len(hit_files)} files")
    for f in hit_files:
        print(f"   {f}")


if __name__ == "__main__":
    main()
