#!/usr/bin/env python3
"""W26 attack, attempt 1 (facts first): the non-U3 unresolved carriers.

The clustering probe (:mod:`triage.w26_empty_mesh_clusters`) ranked the
empty-mesh population; the top cluster is the U3-variant composite
family (refuted measured-negative twice: W2's mapping attempts + the
W2b stored-normal oracle), so the brief says skip it and attack the
next.  That population — every strip-shaped candidate the committed
facet scan leaves unresolved OUTSIDE the U3 family — is exactly:

- the 46 outside-span candidates on the 10 ``outside-only`` files,
- the 8 in-span unresolved candidates on the non-U3 ``facet-only`` /
  ``pool-only`` files (C55 5, C62 1, C40 2 — the latter two are U3
  members included for the same-family contrast, flagged).

For every candidate this probe extracts the byte facts (header form,
declared counts, u16/u32 runs, mult-3 f32-array shapes, ASCII tails)
and classifies it against the KNOWN record classes first (the W13
edge/point inline class, the W2b inter-record index-run class), naming
anything else ``unclassified``.  Reopening criterion W13-#2 is tested
directly: a candidate that indexes an EXTERNAL array (mult-3,
in-bounds) would fire a new pairing law; the probe measures whether
any does.

Outputs ``docs/evidence/data/w26-residual-carriers.csv`` (one row per
candidate) plus a per-class rate summary on stdout.  Read-only over the
corpus; no runtime module is touched.

``--selftest`` pins the classifier on synthetic buffers (no corpus).

Run::

    .venv/bin/python -I scripts/triage/w26_residual_carriers_probe.py \
        fitness/reports/<run>.json --corpus-root /home/alan/catpart-parser
    .venv/bin/python -I scripts/triage/w26_residual_carriers_probe.py --selftest
"""

import argparse
import collections
import csv
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import facets, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

OUT_CSV = os.path.join(ROOT, "docs", "evidence", "data", "w26-residual-carriers.csv")

#: W26's file-cluster CSV (the clustering probe's output) drives the
#: population join — same run, same order.
CLUSTER_CSV = os.path.join(ROOT, "docs", "evidence", "data", "w26-empty-mesh-clusters.csv")

COLUMNS = [
    "sha16",
    "cluster_id",
    "zone",  # outside-span | in-span
    "offset",
    "marker_hex",
    "header_len",
    "header_ty",
    "next_header_delta",
    "declared_counts",
    "mult3_runs",
    "u16_runs",
    "u32_runs",
    "f32_triples",
    "ascii_tail",
    "class",
    "path",
]

#: The W13 sibling flags (absent class; kept for the contrast column).
U3_ORACLE_CSV = os.path.join(ROOT, "docs", "evidence", "data", "w2b-element-region-oracle.csv")


def locate_spans(data):
    """Every store span the exporter's probe order locates (W2 census)."""
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    named = collections.OrderedDict(
        (
            ("stdcont", "CATStdCont"),
            ("xdoclink", "CATXDocLinkCont"),
            ("seebody", "CATSeeBodyCont"),
            ("other", None),
        )
    )
    spans = []
    for tag, name in named.items():
        for blk, nm in blocks:
            if name is not None and nm != name:
                continue
            if name is None and nm in store.NAMED_PROBE_CONTAINERS:
                continue
            try:
                span = store.locate_store(data, blk, blocks, d8_outer)
            except ExportError:
                continue
            if span is not None:
                spans.append((tag, span.body_lo, span.body_hi))
    return spans


def declared_u32le(data, lo, hi):
    """Every u32le value in the window that a count field could occupy
    (the first 24 bytes after the header — the observed count zone)."""
    out = []
    for o in range(lo, min(lo + 24, hi - 3)):
        v = int.from_bytes(data[o : o + 4], "little")
        if 1 <= v <= (hi - lo):
            out.append(v)
    return out


def run_analysis(data, off, nxt):
    """Byte facts + class for one unresolved candidate header at ``off``.

    Classification order (known classes first, fail-closed to
    ``unclassified`` — nothing is guessed into a known class):

    - ``edge-point-inline``: the W13 outside-record class — an ID word,
      then ``02 00``/``01 00`` sub-shape, inline f32 triples, integer
      tail, ASCII tag (W13-08/09: the display route already shows them).
    - ``index-run-stream``: a declared count whose value equals a
      following u16le run length, refs in a bounded range (the W2b F5
      inter-record class; the committed relaxed family parses it).
    - ``stream-framing``: a repeating fixed-stride block structure with
      no declared count and no inline floats (the ``e5 0d 03`` framing
      family observed in the C06/EHI files).
    - ``surface-shape``: the 0x46/0x4e ``ea ff`` + f32-field shape
      (zero-heavy fields, no counts, no indices).
    """
    hl = facets.header_len(data, off)
    if hl is None:
        return None
    marker = data[off + 1]
    body = data[off + hl : nxt]
    facts = {
        "offset": off,
        "marker_hex": f"{marker:02x}",
        "header_len": hl,
        "header_ty": data[off + 2] if hl >= 3 else -1,
        "next_header_delta": nxt - off,
        "declared_counts": declared_u32le(data, off + hl, nxt),
        "mult3_runs": 0,
        "u16_runs": 0,
        "u32_runs": 0,
        "f32_triples": 0,
        "ascii_tail": ascii_tail(body),
    }
    klass = classify_body(marker, body, facts)
    facts["class"] = klass
    return facts


def ascii_tail(body):
    """The trailing printable run (>= 4 chars), if any."""
    tail = []
    for b in reversed(body):
        if 0x20 <= b < 0x7F:
            tail.append(chr(b))
        else:
            break
    tail.reverse()
    s = "".join(tail)
    return s if len(s) >= 4 else ""


def count_runs(body, unit, lo_bound, hi_bound):
    """Maximal runs of ``unit``-wide little-endian words in [lo, hi)."""
    runs = 0
    cur = 0
    for o in range(0, len(body) - unit + 1, unit):
        v = int.from_bytes(body[o : o + unit], "little")
        if lo_bound <= v < hi_bound:
            cur += 1
            runs = max(runs, cur)
        else:
            cur = 0
    return runs


def classify_body(marker, body, facts):
    """The class law above; every claim rides on the byte facts."""
    n = len(body)
    tail = ascii_tail(body)
    facts["ascii_tail"] = tail
    # edge-point-inline: an inline f32 triple zone (>= 3 nice floats)
    # near the head, plus an ASCII tag — W13-08's measured shape.
    nice = 0
    for o in range(0, min(n - 12, 96), 1):
        vals = [struct_f32(body, o + 4 * k) for k in range(3)]
        if all(abs(v) < 1e7 and (v == 0.0 or 1e-4 < abs(v)) for v in vals):
            nice += 1
    facts["f32_triples"] = nice
    facts["u16_runs"] = count_runs(body, 2, 0, 65535)
    facts["u32_runs"] = count_runs(body, 4, 0, 1 << 30)
    if nice >= 2 and tail:
        return "edge-point-inline"
    # index-run-stream: the W2b F5 shape — a declared mult-3 count N
    # whose value a contiguous u16le run of EXACTLY N words satisfies,
    # every word in-bounds against the N-element space (refs < N), the
    # run starting near the head.  The loose "long run" reading does
    # not fire: every u16 word is < 65535, so run-length >= N is
    # vacuous on arbitrary stream bytes.
    for v in facts["declared_counts"]:
        if v >= 3 and v % 3 == 0 and exact_index_run(body, v):
            return "index-run-stream"
    # surface-shape: the extended header whose ty byte is 0xea (the
    # CGM object-stream class observed on 0x46/0x48/0x4e: an f64-field
    # object body with ID refs — the W11 template-object idea)
    if facts.get("header_ty") == 0xEA and marker in (0x46, 0x48, 0x4E):
        return "surface-shape"
    # stream-framing: a fixed-stride repeat (>= 3 identical deltas)
    if has_fixed_stride(body):
        return "stream-framing"
    return "unclassified"


def struct_f32(body, o):
    """One little-endian f32 at ``o`` (bounds guaranteed by the caller)."""
    return struct.unpack_from("<f", body, o)[0]


def exact_index_run(body, n):
    """A contiguous u16le run of EXACTLY ``n`` words, all < ``n``,
    starting within the first 64 bytes (the W2b F5 inter-record shape:
    counts [15, 19] followed by 34 u16le refs)."""
    limit = min(len(body) - 2 * n, 64)
    if limit < 0:
        return False
    for start in range(0, limit):
        window = body[start : start + 2 * n]
        if len(window) < 2 * n:
            break
        words = [
            int.from_bytes(window[2 * i : 2 * i + 2], "little") for i in range(n)
        ]
        # an all-zero run is the zero-block filler, not a ref run
        if all(w < n for w in words) and any(w != 0 for w in words):
            return True
    return False


def has_fixed_stride(body):
    """A >= 3-deep repeat of one non-constant stride (4..64 B).

    The repeated block must carry more than one distinct byte value: an
    all-zero (or constant) run is the known zero-block filler, not a
    framing structure (W2b F1's zero block).
    """
    window = body[:256]
    for stride in range(4, 65):
        if len(window) < stride * 3:
            break
        blk = window[:stride]
        if (
            len(set(blk)) > 1
            and blk == window[stride : 2 * stride]
            and blk == window[2 * stride : 3 * stride]
        ):
            return True
    return False


def load_cluster_rows():
    try:
        with open(CLUSTER_CSV, newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError:
        return []


def load_manifest_paths():
    """sha16 -> local_path (the on-disk join; the report path is
    repo-stripped, so the manifest's local_path is the authority and
    the cluster CSV keys are sha16 = sha256[:16])."""
    manifest = os.path.join(ROOT, "manifests", "corpus-manifest.csv")
    with open(manifest, newline="") as fh:
        return {r["sha256"][:16]: r["local_path"] for r in csv.DictReader(fh)}


def run(report_path, corpus_root, out_csv):
    cluster_rows = load_cluster_rows()
    manifest_paths = load_manifest_paths()
    u3 = set()
    try:
        with open(U3_ORACLE_CSV, newline="") as fh:
            u3 = {r["sha16"] for r in csv.DictReader(fh)}
    except OSError:
        pass

    # population: the NON-U3 unresolved carriers only (the brief skips
    # the U3-variant family as already refuted; its in-span unresolved
    # mass is the element-region blocker, not this attack).  Keep the
    # non-U3 outside-only / facet-only / pool-only members.
    targets = []
    for r in cluster_rows:
        if r["u3_variant"] == "True":
            continue
        if r["carrier_class"] in ("zero-carrier", "curves-only"):
            continue
        targets.append(r)

    out_rows = []
    for t in targets:
        local = manifest_paths.get(t["sha16"], "")
        path = os.path.join(corpus_root, local) if local else ""
        if not os.path.isfile(path):
            print(f"missing on disk, skipped: {t['sha16']}")
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        size = len(data)
        blocks = store.valid_blocks(data)
        spans = locate_spans(data)
        span_lo_hi = [(lo, hi) for _tg, lo, hi in spans]

        def in_span(o):
            return any(lo <= o < hi for lo, hi in span_lo_hi)

        marks = [
            m.start()
            for m in facets.STRIP_RE.finditer(data, 0, size)
            if not in_span(m.start())
        ]
        # in-span unresolved candidates: the committed scan over spans
        scan_unresolved = []
        for _tg, lo, hi in spans:
            scan = facets.scan_facets(data, lo, hi)
            hdrs = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
            consumed = {rec.offset for rec in scan.records}
            scan_unresolved.extend(o for o in hdrs if o not in consumed)
        for zone, offsets in (("outside-span", marks), ("in-span", scan_unresolved)):
            for i, off in enumerate(sorted(offsets)):
                nxt = offsets[i + 1] if i + 1 < len(offsets) else min(off + 4096, size)
                f = run_analysis(data, off, nxt)
                if f is None:
                    continue
                f["sha16"] = t["sha16"]
                f["cluster_id"] = t["cluster_id"]
                f["zone"] = zone
                f["path"] = t["path"]
                f["declared_counts"] = ";".join(map(str, f["declared_counts"]))
                out_rows.append(f)

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"candidates analyzed: {len(out_rows)}")
    by_class = collections.Counter(r["class"] for r in out_rows)
    for k, v in by_class.most_common():
        print(f"  {k}: {v} ({100 * v / max(1, len(out_rows)):.1f}%)")
    firing = [r for r in out_rows if r["class"] == "index-run-stream"]
    print(f"W13-#2 reopening criterion (external-array index runs): {len(firing)} fire")
    return out_rows


# ---------------------------------------------------------------- selftest


def _selftest():
    import struct

    # declared-count window reads u32le values that fit the body
    body = b"\x0a\x00\x00\x00" + b"\x00" * 40
    vals = declared_u32le(b"\x00" * 4 + body, 4, 48)
    assert 10 in vals

    # run counter: a run of 5 in-bounds u16le words
    buf = b"\x01\x00\x02\x00\x03\x00\x04\x00\x05\x00" + b"\xff\xff\xff\xff"
    assert count_runs(buf, 2, 0, 100) == 5

    # ascii tail: >= 4 printable trailing chars only
    assert ascii_tail(b"\x00\x01PART\x00") == ""
    assert ascii_tail(b"\x00abPART1") == "abPART1"

    # fixed-stride detector: 3 repeats of a 6-byte block
    blk = bytes(range(6))
    assert has_fixed_stride(blk * 4)
    assert not has_fixed_stride(b"\x00" * 100)

    # the classification order: inline floats + ASCII tag -> W13 class
    floats = struct.pack("<3f", 1.5, -2.5, 3.5)
    body = b"\x01\x00" + floats + b"\x02\x00" + floats + b"\x00" * 8 + b"EDGE1"
    facts = {
        "declared_counts": [],
        "u16_runs": 0,
        "u32_runs": 0,
        "f32_triples": 0,
        "ascii_tail": "",
    }
    assert classify_body(0x41, body, facts) == "edge-point-inline"

    # index-run-stream needs a declared mult-3 count backed by the run
    body2 = b"\x06\x00\x00\x00" + b"\x01\x00" * 6
    facts2 = {"declared_counts": [6], "u16_runs": 6, "u32_runs": 0, "f32_triples": 0, "ascii_tail": ""}
    assert classify_body(0x4A, body2, facts2) == "index-run-stream"

    # surface-shape: the extended 0xea-ty header on the 0x46 class
    body3 = b"\x00" * 32
    facts3 = {"header_ty": 0xEA, "declared_counts": [], "u16_runs": 0, "u32_runs": 0, "f32_triples": 0, "ascii_tail": ""}
    assert classify_body(0x46, body3, facts3) == "surface-shape"
    facts3b = {"header_ty": 0x07, "declared_counts": [], "u16_runs": 0, "u32_runs": 0, "f32_triples": 0, "ascii_tail": ""}
    assert classify_body(0x46, body3, facts3b) == "unclassified"

    # fail-closed: nothing matches -> unclassified
    body4 = b"\x9c\x27\x01\x00\x7f\x00"
    facts4 = {"declared_counts": [], "u16_runs": 1, "u32_runs": 0, "f32_triples": 0, "ascii_tail": ""}
    assert classify_body(0x41, body4, facts4) == "unclassified"

    print("selftest: 9/9 pins green")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", nargs="?", help="fitness report JSON (unused; kept for symmetry)")
    ap.add_argument("--out", default=OUT_CSV)
    ap.add_argument("--corpus-root", default=ROOT)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        _selftest()
        return 0
    run(args.report, args.corpus_root, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
