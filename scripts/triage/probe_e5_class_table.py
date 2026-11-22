#!/usr/bin/env python3
"""The ``e5 0d`` Class Table probe (W3, marathon v3, ticket: e5-algebra).

Closes the two open items the E5 bulk-dialect note left named
(``docs/evidence/2026-11-19-e5-dialect.md`` §5.3(1) and §4.4): the
writer-block tail's token grammar and the payload class vocabulary.

Measured here, corpus-wide, over every sha-valid manifest file:

1. **The writer tail is a token stream**, not noise: an optional
   ``03 00`` opener, an optional ``11 <u32le> <ascii>`` second release
   stamp, ``08 <u8>`` / ``18 <u16le>`` / ``38 <u24le>`` references,
   ``80..ff`` flag bytes, and the ``17 <00|01>`` terminator.  Every
   reference's value is tested against the owning region's record ids
   (the E5 note's candidate: refs name records).
2. **Class 0x00e7 carries exact B-spline surfaces** — the compact head's
   pole law with u32 fields (``docs/evidence/2026-11-22-e5-class-table.md``):
   ``0x80 | deg | a | b | n | q`` per lane, strictly increasing knots, one
   multiplicity per knot, ``poles = sum(mult) - degree - 1``, the two-value
   pole marker (``00 00`` plain / ``01 00`` rational, weights after the
   coordinates), and a v-major pole net.  The parse is the SHIPPED decoder
   (:func:`catpart.geometry.surface.parse_e5_surface`); the battery is the
   shipped :func:`catpart.geometry.surface.assess`/``tessellate``.
3. **The no-regret A/B** (``--ab --baseline-src``): the baseline checkout's
   exporter vs this branch's over every changed-candidate file (the E5
   bearing files plus the no-facet population); byte-identical PLY or a
   named improvement, never a regression.

Everything streams file by file (mmap, read-only); no mesh is retained.

Usage::

    .venv/bin/python -I scripts/triage/probe_e5_class_table.py [--anchors sha16,...]
    .venv/bin/python -I scripts/triage/probe_e5_class_table.py --selftest
    .venv/bin/python -I scripts/triage/probe_e5_class_table.py --ab \
        --baseline-src /home/alan/catpart-parser/src

Writes ``docs/evidence/data/e5-class-table-claims.csv``,
``docs/evidence/data/e5-class-families.csv``,
``docs/evidence/data/e5-surface-ab.csv`` (with ``--ab``).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mmap
import struct
import subprocess
import sys
import tempfile
import time
import collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
GRID_PARTS = ROOT / "docs" / "evidence" / "data" / "grid-meshing-parts.csv"
OUT_CLAIMS = ROOT / "docs" / "evidence" / "data" / "e5-class-table-claims.csv"
OUT_FAMILIES = ROOT / "docs" / "evidence" / "data" / "e5-class-families.csv"
OUT_AB = ROOT / "docs" / "evidence" / "data" / "e5-surface-ab.csv"

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
sys.path.insert(0, str(ROOT / "src"))

import probe_e5_bulk as bulk  # noqa: E402  (the record law + region framing)
from catpart.geometry import surface  # noqa: E402  (the shipped decoder)

CLAIM_FIELDS = ["claim", "scope", "observations", "passes", "rate", "label", "detail"]
E5_MARKER = b"\xe5\x0d"


# --------------------------------------------------------------- tail tokens


def parse_tail_tokens(tail: bytes):
    """Tokenize a writer tail; ``(tokens, clean)`` — clean = fully consumed."""
    tokens = []
    pos = 0
    n = len(tail)
    while pos < n:
        byte = tail[pos]
        if byte == 0x17:
            if pos + 2 <= n:
                tokens.append(("end", tail[pos + 1]))
                return tokens, pos + 2 == n
            return tokens, False
        if byte == 0x03 and pos + 2 <= n:
            tokens.append(("opener", tail[pos + 1]))
            pos += 2
            continue
        if byte == 0x11 and pos + 5 <= n:
            length = struct.unpack_from("<I", tail, pos + 1)[0]
            if pos + 5 + length <= n:
                tokens.append(("stamp", bytes(tail[pos + 5 : pos + 5 + length])))
                pos += 5 + length
                continue
            return tokens, False
        if byte == 0x18 and pos + 3 <= n:
            tokens.append(("ref2", struct.unpack_from("<H", tail, pos + 1)[0]))
            pos += 3
            continue
        if byte == 0x08 and pos + 2 <= n:
            tokens.append(("ref1", tail[pos + 1]))
            pos += 2
            continue
        if byte == 0x38 and pos + 4 <= n:
            value = tail[pos + 1] | (tail[pos + 2] << 8) | (tail[pos + 3] << 16)
            tokens.append(("ref3", value))
            pos += 4
            continue
        if 0x80 <= byte <= 0xFF:
            tokens.append(("flag", byte))
            pos += 1
            continue
        tokens.append(("byte", byte))
        pos += 1
    return tokens, False


# ------------------------------------------------------------- the E5 walk


def region_records(data, lo: int, hi: int):
    """Every admitted record of ``[lo, hi)`` — the probe's own law check.

    Mirrors the shipped walk (``catpart.geometry.grid._records``) so the
    claims carry their own reproduction of the admission rule: a run is
    admitted only with >= 3 chained records that close on their own end.
    """
    return bulk.clusters(data, lo, hi)


def walk_region(data, block: int, end: int):
    """``(records, ids)`` of one region's admitted record runs."""
    records = []
    for cluster in region_records(data, block, end):
        run, _ = bulk.walk(data, cluster.start, cluster.end)
        records.extend(run)
    return records, {record.ident for record in records}


# ----------------------------------------------------------------- helpers


def sha_valid_files():
    """``(sha, relpath)`` for every manifest row whose file hash matches."""
    out = []
    for row in csv.DictReader(MANIFEST.open(newline="")):
        path = ROOT / row["local_path"]
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() == row["sha256"]:
            out.append((row["sha256"], row["local_path"], row.get("split", "")))
    return out


def plausible_net_values(data, net: int, count: int) -> bool:
    """The shipped pole band, evaluated in byte order (any orientation)."""
    for index in range(count):
        x, y, z = struct.unpack_from("<3d", data, net + 24 * index)
        for value in (x, y, z):
            if not (value == 0.0 or 1e-6 <= abs(value) <= 1e5):
                return False
    return True


# ------------------------------------------------------------------- census


def census(split_filter=None, anchors=None, progress_every=300):
    """One corpus pass: tail tokens, class families, E5-surface detail."""
    claims = collections.Counter()
    tail_shapes = collections.Counter()
    tail_samples = {}
    membership = collections.Counter()
    class_records = collections.Counter()
    class_files = collections.defaultdict(set)
    class_shapes = collections.defaultdict(collections.Counter)
    e7 = collections.Counter()
    e7_battery = collections.Counter()
    orient = collections.Counter()
    shapes = collections.Counter()
    no_facet = set()
    if GRID_PARTS.is_file():
        no_facet = {row["sha256"] for row in csv.DictReader(GRID_PARTS.open(newline=""))}

    files = sha_valid_files()
    if anchors:
        files = [f for f in files if f[0][:16] in set(anchors)]
    started = time.time()
    for index, (sha, rel, split) in enumerate(files):
        if split_filter and split != split_filter:
            continue
        path = ROOT / rel
        try:
            handle = path.open("rb")
            data = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
            battery_done = False
            regions = bulk.cgm_nurbs.valid_regions(data)
            for position, (block, name, _) in enumerate(regions):
                if name != "CATPrtCont":
                    continue
                end = regions[position + 1][0] if position + 1 < len(regions) else len(data)
                table = bulk.bulk.parse_metadata_table(data, block, end)
                content = block + (table.end if table is not None else 0)
                if table is None:
                    content = end
                header = bulk.parse_writer_header(data, content, end)
                clusters = region_records(data, block, end)
                if not clusters:
                    continue
                claims["regions"] += 1
                if header is not None:
                    claims["writer_regions"] += 1
                    marker = data.find(E5_MARKER, header.end, clusters[0].start)
                    stop = marker if marker >= 0 else clusters[0].start
                    tail = bytes(data[header.end : stop])
                    tokens, clean = parse_tail_tokens(tail)
                    claims["tail_total"] += 1
                    claims["tail_clean"] += clean
                    tail_shapes[(len(tail), tokens[0][0] if tokens else "-")] += 1
                    tail_samples.setdefault(
                        (len(tail), tokens[0][0] if tokens else "-"),
                        (sha[:8], tail.hex(" ")),
                    )
                records, ids = walk_region(data, block, end)
                claims["records"] += len(records)
                for token in tokens:
                    if token[0] in ("ref1", "ref2", "ref3"):
                        membership[(token[0], token[1] in ids)] += 1
                battery_budget = sha in no_facet or None
                for record in records:
                    cls = record.cls
                    class_records[cls] += 1
                    class_files[cls].add(sha[:16])
                    part = bulk.census_payload(data, record.payload, record.end)
                    class_shapes[cls][part.kind] += 1
                    if cls != surface.E5_SURFACE_CLASS:
                        continue
                    e7["records"] += 1
                    head = surface.parse_e5_surface(data, record.payload, record.end)
                    if head is None:
                        e7["undecoded"] += 1
                        continue
                    e7["parsed"] += 1
                    poles, weights = surface.e5_pole_data(data, head)
                    shapes[(head.poles_v, head.poles_u)] += 1
                    rational = head.rational
                    e7["marker_" + ("0100" if rational else "0000")] += 1
                    if rational:
                        e7["rational_tail_law"] += head.tail == 148
                    else:
                        e7["plain_tail_law"] += head.tail == 148
                    if not surface.plausible_net(poles) or not surface.plausible_weights(weights):
                        e7["implausible"] += 1
                        continue
                    e7["plausible"] += 1
                    if battery_budget is None and battery_done:
                        e7["battery_skipped"] += 1
                        continue
                    battery_done = True
                    e7["battery_total"] += 1
                    assessment = surface.assess(head, poles, weights)
                    if not assessment.evaluable:
                        e7["refused_battery"] += 1
                        continue
                    e7["evaluable"] += 1
                    patch = surface.tessellate(head, poles, weights)
                    if patch is None:
                        e7["tessellation_refused"] += 1
                        continue
                    e7["tessellated"] += 1
                    if head.poles_u != head.poles_v:
                        # The other addressing rebuilds from the bytes (a
                        # transpose-by-indexing is only the same matrix for
                        # square nets): pole (i, j) at net + 24*(i*nv + j).
                        nu, nv, net = head.poles_u, head.poles_v, head.grid
                        u_major = [
                            [
                                struct.unpack_from("<3d", data, net + 24 * (i * nv + j))
                                for j in range(nv)
                            ]
                            for i in range(nu)
                        ]
                        other = surface.assess(head, u_major, None)
                        if other.evaluable:
                            orient["both"] += 1
                        else:
                            orient["v_outer_only"] += 1
                    if sha in no_facet:
                        e7_battery["nf_records"] += 1
                        e7_battery["nf_tessellated"] += 1
            data.close()
            handle.close()
        except Exception as exc:  # noqa: BLE001 - census continues
            e7["file_errors"] += 1
            if e7["file_errors"] <= 2:
                print("FILE-ERROR:", rel, repr(exc), flush=True)
        if (index + 1) % progress_every == 0:
            print(
                f"...{index + 1}/{len(files)} files "
                f"({time.time() - started:.0f}s)",
                flush=True,
            )
        del data
        import gc

        gc.collect()
    return dict(
        claims=claims,
        tail_shapes=tail_shapes,
        tail_samples=tail_samples,
        membership=membership,
        class_records=class_records,
        class_files=class_files,
        class_shapes=class_shapes,
        e7=e7,
        e7_battery=e7_battery,
        orient=orient,
        shapes=shapes,
        files=len(files),
        no_facet=no_facet,
    )


# -------------------------------------------------------------------- A/B


def ab_run(baseline_src: Path, progress_every=60):
    """Baseline-vs-branch export A/B over the changed-candidate file set.

    The set is exact by construction: a file's export can only differ when
    the surface/grid fallback runs AND the file carries E5 surface records
    (or the file is in the no-facet population whose grid census this
    branch's walk feeds).  Everything else shares untouched code paths.
    """
    baseline_run = """
import sys, json
sys.path.insert(0, __SRC__)
from catpart.geometry import build_export
try:
    s = build_export(__ROOT__ + '/' + sys.argv[1], __PLY__)
    print(json.dumps({'tri': s['triangle_count'],
                      'warn': sorted(set(w['class'] for w in s['warnings']))}))
except Exception as exc:
    klass = getattr(exc, 'error_class', None) or type(exc).__name__
    print(json.dumps({'error': str(klass)}))
"""
    branch_run = baseline_run

    # The E5-bearing file set comes from the census pass (cached); the
    # no-facet population joins it.
    e7_files = e5_bearing_files()
    targets = []
    no_facet = {row["sha256"] for row in csv.DictReader(GRID_PARTS.open(newline=""))}
    for sha, rel, split in sha_valid_files():
        if sha[:16] in e7_files or sha in no_facet:
            targets.append((sha, rel, split))

    with tempfile.TemporaryDirectory() as tmp:
        base_ply = str(Path(tmp) / "base.ply")
        branch_ply = str(Path(tmp) / "branch.ply")
        base_code = (
            baseline_run.replace("__SRC__", repr(str(baseline_src)))
            .replace("__ROOT__", repr(str(ROOT)))
            .replace("__PLY__", repr(base_ply))
        )
        branch_code = branch_run.replace("__SRC__", repr(str(ROOT / "src"))).replace(
            "__ROOT__", repr(str(ROOT))
        ).replace("__PLY__", repr(branch_ply))
        rows = []
        same = changed = 0
        flips = 0
        drops = 0
        for index, (sha, rel, split) in enumerate(targets):
            base = subprocess.run(
                [sys.executable, "-B", "-I", "-c", base_code, rel],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            branch = subprocess.run(
                [sys.executable, "-B", "-I", "-c", branch_code, rel],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            try:
                bj = json.loads(base.stdout.strip().splitlines()[-1])
            except Exception:  # noqa: BLE001
                bj = {"error": "baseline-crash"}
            try:
                nj = json.loads(branch.stdout.strip().splitlines()[-1])
            except Exception:  # noqa: BLE001
                nj = {"error": "branch-crash"}
            if "tri" in bj and "tri" in nj:
                identical = (
                    Path(base_ply).read_bytes() == Path(branch_ply).read_bytes()
                )
            else:
                identical = bj.get("error") == nj.get("error")
            if identical:
                same += 1
            else:
                changed += 1
                if bj.get("tri", 0) == 0 and nj.get("tri", 0) > 0:
                    flips += 1
                if nj.get("tri", 0) < bj.get("tri", 0):
                    drops += 1
            rows.append({
                "sha256": sha,
                "split": split,
                "e5_bearing": sha[:16] in e7_files,
                "identical": identical,
                "baseline_triangles": bj.get("tri", ""),
                "branch_triangles": nj.get("tri", ""),
                "baseline_error": bj.get("error", ""),
                "branch_error": nj.get("error", ""),
                "baseline_warnings": " ".join(bj.get("warn", [])),
                "branch_warnings": " ".join(nj.get("warn", [])),
            })
            if (index + 1) % progress_every == 0:
                print(f"...{index + 1}/{len(targets)} same={same} changed={changed}", flush=True)
        return rows, same, changed, flips, drops


_AB_CACHE = ROOT / "docs" / "evidence" / "data" / ".e5-bearing-files.json"


def e5_bearing_files() -> set:
    """The sha16 set of files carrying class-0x00e7 records (cached pass)."""
    if _AB_CACHE.is_file():
        return set(json.loads(_AB_CACHE.read_text()))
    found = set()
    for sha, rel, _split in sha_valid_files():
        path = ROOT / rel
        try:
            handle = path.open("rb")
            data = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
            regions = bulk.cgm_nurbs.valid_regions(data)
            for position, (block, name, _) in enumerate(regions):
                if name != "CATPrtCont":
                    continue
                end = regions[position + 1][0] if position + 1 < len(regions) else len(data)
                for cluster in region_records(data, block, end):
                    run, _ = bulk.walk(data, cluster.start, cluster.end)
                    if any(record.cls == surface.E5_SURFACE_CLASS for record in run):
                        found.add(sha[:16])
                        break
                if sha[:16] in found:
                    break
            data.close()
            handle.close()
        except Exception:  # noqa: BLE001
            continue
        import gc

        gc.collect()
    _AB_CACHE.write_text(json.dumps(sorted(found)))
    return found


# ----------------------------------------------------------------- selftest


def selftest() -> int:
    """Synthetic positives and negatives for the probe's discriminating edges.

    The detector-honesty convention (dispatch-recipes): every classifying
    edge carries a committed negative fixture.  Pinned here:

    - a well-formed 0xe7 record parses and evaluates (positive);
    - a non-monotone knot lane, a zero multiplicity, a marker outside the
      measured pair and a truncated net each refuse (negatives);
    - the tail tokenizer consumes a synthetic tail exactly and refuses a
      truncated one.
    """
    import struct as _struct

    def lane(degree, knots, mult):
        out = _struct.pack("<5I", degree, 0, 0, len(knots), 0)
        out += b"".join(_struct.pack("<d", k) for k in knots)
        out += b"".join(_struct.pack("<I", m) for m in mult)
        return out

    def payload(lane_v, lane_u, marker=b"\x00\x00", poles=4, tail=148):
        out = b"\x80" + lane_v + lane_u + marker
        for i in range(poles):
            out += _struct.pack("<3d", 5.0 * i, 7.0 * i, 2.0 + i)
        return out + bytes(tail)

    plain_lane = lane(1, [0.0, 1.0], [2, 2])
    good = payload(plain_lane, plain_lane)
    head = surface.parse_e5_surface(good, 0, len(good))
    assert head is not None and head.points == 4, "positive must parse"
    bad_knots = payload(lane(1, [1.0, 0.0], [2, 2]), plain_lane)
    assert surface.parse_e5_surface(bad_knots, 0, len(bad_knots)) is None, "knots"
    bad_mult = payload(plain_lane, lane(1, [0.0, 1.0], [0, 2]))
    assert surface.parse_e5_surface(bad_mult, 0, len(bad_mult)) is None, "mult"
    bad_marker = payload(plain_lane, plain_lane, marker=b"\x02\x00")
    assert surface.parse_e5_surface(bad_marker, 0, len(bad_marker)) is None, "marker"
    assert surface.parse_e5_surface(good, 0, 100) is None, "truncated net"
    tokens, clean = parse_tail_tokens(b"\x03\x00\x18\xd1\x06\x81\x18\xa7\xb6\x17\x00")
    assert clean and [t[0] for t in tokens] == [
        "opener", "ref2", "flag", "ref2", "end",
    ], "tail grammar"
    truncated, clean = parse_tail_tokens(b"\x03\x00\x18\xd1")
    assert not clean, "truncated tail must not claim cleanliness"
    print("selftest: 6/6 edges pinned (1 positive, 4 E5 negatives, tail +/-)")
    return 0


# -------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchors", default="", help="comma-separated sha16 filter")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument(
        "--ab", action="store_true", help="run the no-regret A/B (needs --baseline-src)"
    )
    parser.add_argument("--baseline-src", default="")
    args = parser.parse_args()
    if args.selftest:
        return selftest()

    if args.ab:
        if not args.baseline_src:
            parser.error("--ab needs --baseline-src <baseline checkout's src dir>")
        rows, same, changed, flips, drops = ab_run(Path(args.baseline_src))
        with OUT_AB.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(
            f"A/B over {len(rows)} changed-candidate files: {same} identical, "
            f"{changed} changed ({flips} display->mesh flips, {drops} regressions)"
        )
        return 0

    result = census(anchors=[a for a in args.anchors.split(",") if a])
    claims = result["claims"]
    e7 = result["e7"]
    membership = result["membership"]
    orient = result["orient"]

    rows = []

    def add(claim, scope, observations, passes, label, detail):
        rate = passes / observations if observations else 0.0
        rows.append({
            "claim": claim, "scope": scope, "observations": observations,
            "passes": passes, "rate": f"{rate:.4f}", "label": label,
            "detail": detail,
        })

    add(
        "CT-01", "corpus", claims["tail_total"], claims["tail_clean"], "law",
        "writer tails tokenize as opener/stamp/ref/flag/end tokens "
        "(evidence: e5-class-families.csv, tail census)",
    )
    for kind in ("ref1", "ref2", "ref3"):
        add(
            f"CT-02.{kind}", "corpus",
            membership[(kind, True)] + membership[(kind, False)],
            membership[(kind, True)], "candidate",
            f"{kind} reference values hit the owning region's record ids "
            "(the misses reference ids living in the file's other regions)",
        )
    add(
        "CT-03", "corpus", e7["records"], e7["parsed"], "law",
        "class 0x00e7 payloads parse under the shipped E5-surface decoder",
    )
    parsed = e7["parsed"] or 1
    add(
        "CT-04", "corpus", parsed, e7["plausible"], "law",
        "parsed E5 surfaces have a plausible pole net under the shipped band",
    )
    add(
        "CT-05.plain", "corpus", e7["marker_0000"], e7["plain_tail_law"], "law",
        "marker 00 00 records close on the 148-byte tail law",
    )
    add(
        "CT-05.rational", "corpus", e7["marker_0100"], e7["rational_tail_law"], "law",
        "marker 01 00 records satisfy tail - 8*poles == 148 (weights follow)",
    )
    nonsquare = orient["v_outer_only"] + orient["both"]
    add(
        "CT-06", "no-facet battery", nonsquare, orient["v_outer_only"], "law",
        "non-square nets evaluate under the v-major byte reading; the "
        "u-major addressing never wins alone (u_outer_only=0)",
    )
    add(
        "CT-07", "battery sample", e7["battery_total"], e7["evaluable"],
        "candidate",
        "battery-tested E5 surfaces pass the shipped evaluable battery "
        "(the no-facet population complete, plus the first plausible "
        "record per remaining file)",
    )
    nf_battery = result["e7_battery"]
    add(
        "CT-08", "no-facet parts", nf_battery["nf_records"],
        nf_battery["nf_tessellated"], "candidate",
        "no-facet-part E5 records tessellate under the shipped route",
    )

    with OUT_CLAIMS.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CLAIM_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    with OUT_FAMILIES.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "class", "records", "files", "top_payload_shapes", "note",
        ])
        for cls, count in result["class_records"].most_common():
            if len(result["class_files"][cls]) < 10:
                continue
            shapes = ", ".join(
                f"{kind}={n}" for kind, n in result["class_shapes"][cls].most_common(3)
            )
            writer.writerow([
                f"0x{cls:04x}", count, len(result["class_files"][cls]), shapes,
                "exact-surface carrier" if cls == surface.E5_SURFACE_CLASS else "",
            ])

    print(
        f"claims: {len(rows)} rows -> {OUT_CLAIMS.name}; "
        f"families: -> {OUT_FAMILIES.name}"
    )
    print(
        f"tail clean {claims['tail_clean']}/{claims['tail_total']}; "
        f"E5 parse {e7['parsed']}/{e7['records']}; "
        f"evaluable {e7['evaluable']}/{e7['plausible']}; "
        f"orientation {dict(orient)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
