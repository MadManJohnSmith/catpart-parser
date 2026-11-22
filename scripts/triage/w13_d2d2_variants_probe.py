#!/usr/bin/env python3
"""W13 (B7 continuation): the ``d2 d2 XX`` / ``30 04 XX`` sibling sweep.

Static reads over the corpus binaries only — nothing parses code and the
package runtime is not modified.  The probe reproduces, command by
command, every figure in the evidence note
``docs/evidence/2026-11-22-w13-d2d2-variants.md``:

  - the corpus-wide pattern census: every ``30 04 XX ff ff ff d2 d2``
    prefix and the byte that follows (the ``d2 d2 XX`` flag), per hit
    and per file (``census``);
  - the 211 ``empty-mesh`` population's carrier zones: no hits / hits
    only between the bag-rep class-record spans / hits inside a
    ``CATSurfacicRep`` span (``zones``);
  - the in-span closure rates under the WIRED laws (0x50 counter-table,
    0x51 face-GP) corpus-wide, with the non-closing deltas (``closure``);
  - the per-file sweep CSV of the 211 (class, carriers, variant,
    mesh-under-current-law) (``sweep``).

Commands that produced the committed figures (from the worktree root;
``CORPUS`` defaults to ``/home/alan/catpart-parser/corpus``):

    python3 -B scripts/triage/w13_d2d2_variants_probe.py census
    python3 -B scripts/triage/w13_d2d2_variants_probe.py zones
    python3 -B scripts/triage/w13_d2d2_variants_probe.py closure
    python3 -B scripts/triage/w13_d2d2_variants_probe.py sweep \
        --out docs/evidence/data/w13-empty-mesh-sweep.csv
    python3 -B scripts/triage/w13_d2d2_variants_probe.py --selftest

Anti-OOM (agentvm2): single process, one file in memory at a time,
``gc.collect()`` after every file; the 175 MB outlier is streamed
alone.  Streaming only — no corpus binary is written.
"""

from __future__ import annotations

import argparse
import collections
import csv
import gc
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))

from catpart.geometry import face_gp  # noqa: E402  (path set above)

CORPUS_DEFAULT = "/home/alan/catpart-parser/corpus"
MANIFEST = os.path.join(REPO, "manifests", "corpus-manifest.csv")
W4_OPEN_RATE = os.path.join(REPO, "docs", "evidence", "data", "w4-open-rate-files.csv")

#: The full sibling census pattern: ``30 04 <b2> ff ff ff d2 d2 <flag>``.
PATTERN = re.compile(rb"\x30\x04(.)\xff\xff\xff\xd2\xd2(.)")
#: The 7-byte core (prefix-free form, for the prefix census).
CORE7 = re.compile(rb"\x04\x04\xff\xff\xff\xd2\xd2")
#: The chain filler: consecutive 8-byte copies share no flag byte.
FILLER_FLAG = 0x30


def corpus_parts(root: str) -> list[str]:
    out = []
    for dirpath, _, names in os.walk(root):
        for n in sorted(names):
            if n.endswith(".CATPart"):
                out.append(os.path.join(dirpath, n))
    return out


def empty_mesh_paths(root: str) -> list[tuple[str, str, str, str]]:
    """The 211 ``empty-mesh`` rows as ``(sha16, path, report class, open kind)``.

    The w4 open-rate CSV keys files by sha16; the manifest maps sha16 to
    the on-disk corpus path (repo + path columns).  Off-disk rows are
    skipped (they were 0 on this host, 2026-11-22).
    """
    man = {}
    for row in csv.DictReader(open(MANIFEST)):
        if row["kind"] == "part":
            man[row["sha256"][:16]] = os.path.join(root, row["repo"], row["path"])
    out = []
    for row in csv.DictReader(open(W4_OPEN_RATE)):
        if row["report class"] != "empty-mesh" or not row["path"].endswith(".CATPart"):
            continue
        p = man.get(row["sha16"])
        if p and os.path.exists(p):
            out.append((row["sha16"], p, row["report class"], row["open kind"]))
    return out


def _zones(data: bytes) -> tuple[int, int, int, collections.Counter]:
    """``(hits, in_span, between_spans, flags)`` for one file's hits.

    Zones follow the shipped framing: a hit inside any bag-rep
    class-record span is in-span, everything else is between-spans
    (before the first record, after the last, or between two).
    """
    spans = face_gp._class_record_spans(data)
    hits = face_gp._subrecord_positions(data, 0, len(data))
    flags: collections.Counter = collections.Counter()
    in_span = 0
    for h in hits:
        flags[data[h + 8]] += 1
        if any(lo <= h < hi for lo, hi, _ in spans):
            in_span += 1
    return len(hits), in_span, len(hits) - in_span, flags


def cmd_census(root: str) -> None:
    """Corpus-wide ``30 04 XX | flag`` census + the prefix check."""
    parts = corpus_parts(root)
    census: collections.Counter = collections.Counter()
    per_file: collections.Counter = collections.Counter()
    prefixes: collections.Counter = collections.Counter()
    core_total = 0
    for p in parts:
        data = open(p, "rb").read()
        local: collections.Counter = collections.Counter()
        for m in PATTERN.finditer(data):
            k = (m.group(1)[0], m.group(2)[0])
            census[k] += 1
            local[k] += 1
        for k in local:
            per_file[k] += 1
        for m in CORE7.finditer(data):
            core_total += 1
            if m.start():
                prefixes[data[m.start() - 1]] += 1
        del data
        gc.collect()
    print(f"corpus .CATPart files: {len(parts)}")
    print(f"7-byte core hits: {core_total}; preceding byte: "
          + ", ".join(f"{b:02x}={v}" for b, v in prefixes.most_common()))
    print("30 04 <b2> ff ff ff d2 d2 <flag> -> hits, files:")
    for (b2, flag), v in sorted(census.items(), key=lambda kv: -kv[1]):
        print(f"  30 04 {b2:02x} | flag {flag:02x}: {v} hits in {per_file[(b2, flag)]} files")


def cmd_zones(root: str) -> None:
    """The 211 empty-mesh population: carrier zones + in-span closures."""
    rows = empty_mesh_paths(root)
    zone_files: collections.Counter = collections.Counter()
    flags_em: collections.Counter = collections.Counter()
    span_closed: collections.Counter = collections.Counter()
    for sha, p, _cls, _kind in rows:
        data = open(p, "rb").read()
        hits, in_span, between, flags = _zones(data)
        if not hits:
            zone_files["no-hits"] += 1
        elif in_span:
            zone_files["has-in-span"] += 1
        else:
            zone_files["between-spans-only"] += 1
        flags_em.update(flags)
        if in_span:
            subs = face_gp._subrecord_positions(data, 0, len(data))
            for j, s in enumerate(subs):
                e = subs[j + 1] if j + 1 < len(subs) else len(data)
                sub = face_gp.decode_sub_record(data, s, e)
                span_closed[(data[s + 8], sub.closed_exact)] += 1
        del data
        gc.collect()
    print(f"empty-mesh files: {len(rows)}")
    print("zone -> files:", dict(sorted(zone_files.items())))
    print("hits by flag in the population:", {f"{k:02x}": v for k, v in sorted(flags_em.items())})
    print("in-span closures (flag, closed):",
          {f"{k[0]:02x}/{k[1]}": v for k, v in sorted(span_closed.items())})


def cmd_closure(root: str) -> None:
    """Corpus-wide in-span sub-record closure under the WIRED laws."""
    parts = corpus_parts(root)
    stat: collections.Counter = collections.Counter()
    deltas: collections.Counter = collections.Counter()
    for p in parts:
        data = open(p, "rb").read()
        for _s, _e, name in face_gp._class_record_spans(data):
            if name != "CATSurfacicRep":
                continue
            subs = face_gp._subrecord_positions(data, _s, _e)
            for j, s in enumerate(subs):
                e = subs[j + 1] if j + 1 < len(subs) else _e
                sub = face_gp.decode_sub_record(data, s, e)
                flag = data[s + 8]
                stat[(flag, sub.closed_exact)] += 1
                if not sub.closed_exact:
                    deltas[(flag, sub.pos_rel - (sub.rel_len - 1))] += 1
        del data
        gc.collect()
    print("in-span sub-records corpus-wide (flag, closed):")
    for (flag, closed), v in sorted(stat.items(), key=lambda kv: -kv[1]):
        print(f"  flag {flag:02x} closed={closed}: {v}")
    print("non-closing deltas (flag, pos_rel-(rel_len-1)):")
    for (flag, d), v in sorted(deltas.items(), key=lambda kv: -kv[1]):
        print(f"  flag {flag:02x} delta {d:+d}: {v}")


def cmd_sweep(root: str, out: str) -> None:
    """The 211-row CSV: class, carriers, variant, mesh under current law."""
    from catpart.geometry import grid

    rows = empty_mesh_paths(root)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "sha16", "path", "report_class", "open_kind",
            "pattern_hits", "flags_hex", "zone",
            "in_span_total", "in_span_closed",
            "mesh_now_route", "mesh_now_tris",
        ])
        for sha, p, cls, kind in rows:
            data = open(p, "rb").read()
            hits, in_span, between, flags = _zones(data)
            zone = "no-hits" if not hits else (
                "in-span" if in_span else "between-spans-only")
            in_closed = 0
            in_total = 0
            if in_span:
                subs = face_gp._subrecord_positions(data, 0, len(data))
                for j, s in enumerate(subs):
                    e = subs[j + 1] if j + 1 < len(subs) else len(data)
                    sub = face_gp.decode_sub_record(data, s, e)
                    in_total += 1
                    in_closed += 1 if sub.closed_exact else 0
            g = grid.scan_part(data)
            f = None if g.has_mesh else face_gp.scan_part(data)
            route = "grid" if g.has_mesh else (
                "facegp" if f is not None and f.triangles else "none")
            tris = len(g.triangles) if g.has_mesh else (
                len(f.triangles) if f is not None and f.triangles else 0)
            w.writerow([
                sha, os.path.relpath(p, root), cls, kind,
                hits, ";".join(f"{b:02x}" for b in sorted(flags)), zone,
                in_total, in_closed, route, tris,
            ])
            del data, g, f
            gc.collect()
    print(f"wrote {out} ({len(rows)} rows)")


def _selftest() -> int:
    """Synthetic fail-closed pins (no corpus) — the mirror of the tests."""
    import struct as st

    SUBREC = face_gp.SUBREC
    # 1. a flag-0x52 sibling is not a sub-record: the scan must not see it
    body = st.pack("<I", 9) + b"XX" + SUBREC + bytes([0x52]) + b"\x00" * 80
    assert face_gp._subrecord_positions(body, 0, len(body)) == [], "0x52 matched"
    # 2. a prefix sibling (30 04 05 ...) is not the family's signature
    not_family = b"\x30\x04\x05\xff\xff\xff\xd2\xd2\x51" + b"\x00" * 80
    assert SUBREC not in not_family, "30 04 05 matched SUBREC"
    # 3. the chain filler (flag 0x30) is not a sub-record
    filler = SUBREC + bytes([FILLER_FLAG]) + SUBREC + bytes([FILLER_FLAG])
    assert face_gp._subrecord_positions(filler, 0, len(filler)) == [], "filler matched"
    # 4. an edge-style record (inline f32 points, no counts) does not close
    points = st.pack("<3f", -50.0, -50.0, 10.0) * 3
    edge = SUBREC + bytes([0x51]) + st.pack("<I", 0x6AB) + st.pack("<H", 2) + b"32" \
        + points + b"\x00\x03\x00\x01\x00\xff\x04\x00\x00\x01\x80\x00\x00\x04DE@A\x00"
    sub = face_gp.decode_sub_record(edge, 0, len(edge))
    assert not sub.closed_exact, "edge record closed?!"
    assert not face_gp._gate_sub_record(sub, 3), "edge record gated"
    # 5. a strip count that overruns the span leaves the record open
    #    (the delta +0 family: pos == rel_len-1 with ok=False)
    n = 12
    arr = st.pack("<I", n * 3) + st.pack("<I", 1) + b"".join(
        st.pack("<3f", 0.0 + i, 1.0 + i, 2.0 + i) for i in range(n))
    rec = SUBREC + bytes([0x51]) + b"\x00" * (57 - 9) + st.pack(
        "<4I", 3, 0, 1, 0) + b"\xff\x7f" + st.pack(">I", 999) \
        + b"\x00" * 6 + b"\x00"
    sub = face_gp.decode_sub_record(rec, 0, len(rec))
    assert sub.kind == 3 and sub.n_strips == 1
    assert not sub.closed_exact, "overrunning strip closed?!"
    assert not face_gp._gate_sub_record(sub, n), "overrunning strip gated"
    print("selftest: 5/5 fail-closed pins hold")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default=CORPUS_DEFAULT)
    ap.add_argument("command", nargs="?", default=None,
                    choices=["census", "zones", "closure", "sweep"])
    ap.add_argument("--out", default=None, help="sweep CSV output path")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return _selftest()
    if args.command == "census":
        cmd_census(args.corpus)
    elif args.command == "zones":
        cmd_zones(args.corpus)
    elif args.command == "closure":
        cmd_closure(args.corpus)
    elif args.command == "sweep":
        cmd_sweep(args.corpus, args.out or "w13-empty-mesh-sweep.csv")
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
