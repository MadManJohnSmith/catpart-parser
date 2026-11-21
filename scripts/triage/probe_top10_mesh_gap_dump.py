#!/usr/bin/env python3
"""Top-10 MESH residue micro-probe (read-only, 2026-11-20).

For every named part: locate the composite store span(s) the shipped
exporter probes, run the EXACT committed record parsers
(:func:`composite.parse_strip_records` +
:func:`composite.parse_extended_facet_records` — the 6-byte law AND the
#64 escaped pass), and frame the gap clusters between accepted record
spans.  Every unresolved candidate header inside a gap gets its first
48 bytes dumped (hex + interpreted fields) and a per-law diagnosis:

- short-form candidates (0x42/0x43): the (width, k) search the cap
  ``MAX_LOOP_COUNTS = 16`` bounds, re-run to k 512 — which k works,
  whether it exact-tiles and stays in-bounds, and whether the first
  count escapes (P1g ``ff + u32le``).
- extended candidates (0x47/0x4f): the 6-byte law's gates (marker,
  counts law ``n == 3*ty + sum(counts)``, width vote) AND the #64
  escaped law's gates (which header bytes escape — the double-escape
  question, the fixed ``ff``, ``n`` bounds, ``k > ESCAPED_MAX_K``,
  counts law, width vote, in-bounds).

``--census-42`` runs the corpus-wide count instead: over every part's
composite stores, how many unresolved 0x42 candidates have a working
(width, k > 16) parse today — i.e. records the ``0..16`` cap alone
declines.  Exact tiling + in-bounds is the acceptance bar (the same
gates the shipped rank applies); a near-miss (tiles but out-of-bounds)
is tallied separately.

Run::

    .venv/bin/python -I scripts/triage/probe_top10_mesh_gap_dump.py \
        <manifest-name-substring>...        # dump mode
    .venv/bin/python -I scripts/triage/probe_top10_mesh_gap_dump.py \
        --census-42                         # corpus census

Read-only over the corpus; no ``src/`` change.
"""

import argparse
import csv
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import composite, facets, pool, store  # noqa: E402
from catpart.geometry.errors import ExportError  # noqa: E402

MANIFEST = os.path.join(ROOT, "manifests", "corpus-manifest.csv")

#: the (width, k) search ceiling the diagnosis uses (the shipped cap is
#: MAX_LOOP_COUNTS = 16; the diagnosis asks what k the record NEEDS).
DIAG_MAX_K = 512

ESCAPED_FMT = "ff+u32le"


def load_manifest():
    with open(MANIFEST, newline="") as fh:
        return list(csv.DictReader(fh))


def locate_spans(data):
    """Every store span the exporter's probe order locates."""
    size = len(data)
    d8_outer = int.from_bytes(data[8:12], "big") if size >= 12 else 0
    blocks = store.valid_blocks(data)
    stdcont = [(b, nm) for b, nm in blocks if nm == "CATStdCont"]
    xdoclink = [(b, nm) for b, nm in blocks if nm == "CATXDocLinkCont"]
    seebody = [(b, nm) for b, nm in blocks if nm == "CATSeeBodyCont"]
    others = [(b, nm) for b, nm in blocks if nm not in store.NAMED_PROBE_CONTAINERS]
    spans = []
    for container, cands in (
        ("stdcont", stdcont),
        ("xdoclink", xdoclink),
        ("seebody", seebody),
        ("other", others),
    ):
        for blk, _nm in cands:
            try:
                span = store.locate_store(data, blk, blocks, d8_outer)
            except ExportError:
                continue
            if span is not None:
                spans.append((container, span))
    return spans


def accepted_spans(data, lo, hi, elem_decl, elements, hdrs):
    """The accepted record spans [(start, end, kind)] the shipped laws take."""
    out = []
    records, _n_hdrs = composite.parse_strip_records(
        data, lo, hi, elem_decl, elements=elements
    )
    for o, mk, normal, counts, _refs, width in records:
        has_normal = mk in facets.NORMAL_MARKERS_ALL
        base = o + facets.header_len(data, o) + 4 + (12 if has_normal else 0)
        read = facets.read_counts(data, base, len(counts), hi)
        counts_bytes = read[1] if read else 0
        end = base + counts_bytes + width * sum(counts)
        out.append((o, end, f"short 0x{mk:02x} w{width} k{len(counts)}"))
    extended, _cands = composite.parse_extended_facet_records(
        data, lo, hi, elem_decl, elements=elements
    )
    for rec in extended:
        out.append(
            (
                rec.offset,
                rec.end,
                f"ext 0x{rec.marker:02x} ty{rec.triangles} "
                f"b3{rec.strips} b4{rec.polygons} w{rec.width}",
            )
        )
    return out, records, extended


def candidate_offsets(data, lo, hi):
    """Every discovery position: STRIP_RE, the 6-byte form, the #64 escapes."""
    pos = {m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)}
    pos |= set(facets.facet_headers(data, lo, hi))
    pos |= {m.start() for m in facets.EXTENDED_ESCAPED_TY_RE.finditer(data, lo, hi)}
    pos |= {m.start() for m in facets.EXTENDED_ESCAPED_B4_RE.finditer(data, lo, hi)}
    return sorted(pos)


def gap_clusters(data, lo, hi, accepted, cands):
    """Maximal non-accepted regions that contain a candidate header."""
    spans = sorted((a, e) for a, e, _k in accepted)
    clusters = []
    cov = 0
    for o in cands:
        if any(a <= o < e for a, e in spans):
            continue
        if clusters and clusters[-1][1] >= o:
            clusters[-1] = (clusters[-1][0], max(clusters[-1][1], o), clusters[-1][2])
        else:
            clusters.append([o, o, []])
        clusters[-1][2].append(o)
        clusters[-1] = [clusters[-1][0], clusters[-1][1], clusters[-1][2]]
    # widen each cluster to the surrounding accepted-span boundaries
    out = []
    for start, _end, os_ in clusters:
        prev_end = lo
        for a, e in spans:
            if e <= start:
                prev_end = max(prev_end, e)
        nxt = hi
        for a, e in spans:
            if a > os_[-1]:
                nxt = min(nxt, a)
        out.append((os_[0], nxt, os_, prev_end))
    return out


def hexdump(data, start, length):
    rows = []
    for i in range(0, length, 16):
        chunk = data[start + i : start + min(i + 16, length)]
        rows.append(f"  +{i:>3}: {chunk.hex(' ')}")
    return rows


def read_count_shape(data, pos):
    """(value, byte_len, escaped?) at one P1g count."""
    if pos < len(data) and data[pos] == 0xFF:
        return int.from_bytes(data[pos + 1 : pos + 5], "little"), 5, True
    return data[pos], 1, False


def diag_short(data, o, nxt, hi, elem_decl, marker):
    """The (width, k) search past the shipped cap for a short candidate."""
    hlen = facets.header_len(data, o)
    if hlen is None or hlen == 6:
        return {"error": f"header_len={hlen}"}
    if o + hlen + 4 > hi:
        return {"error": "header past body end"}
    n = int.from_bytes(data[o + hlen : o + hlen + 4], "little")
    has_normal = marker in facets.NORMAL_MARKERS_ALL
    base = o + hlen + 4 + (12 if has_normal else 0)
    v0, l0, esc0 = read_count_shape(data, base)
    widths = (1, 2, 3) if elem_decl is not None and elem_decl > 65_535 else (1, 2)
    working = []
    for width in widths:
        for k in range(0, DIAG_MAX_K + 1):
            read = facets.read_counts(data, base, k, min(nxt, hi))
            if read is None:
                break
            counts, clen = read
            if sum(counts) != n:
                continue
            end = base + clen + width * n
            if end > min(nxt, hi):
                continue
            oob = False
            if elem_decl is not None:
                for j in range(n):
                    r = int.from_bytes(
                        data[base + clen + width * j : base + clen + width * (j + 1)],
                        "big",
                    )
                    if r >= elem_decl:
                        oob = True
                        break
            working.append((width, k, end == nxt, oob))
    cap_ok = [w for w in working if w[1] <= composite.MAX_LOOP_COUNTS]
    past_cap = [w for w in working if w[1] > composite.MAX_LOOP_COUNTS]
    return {
        "hlen": hlen,
        "n": n,
        "base": base,
        "first_count": f"{v0} ({ESCAPED_FMT})" if esc0 else str(v0),
        "working": working,
        "cap_blocked": bool(past_cap) and not cap_ok,
        "min_k": min((w[1] for w in working), default=None),
        "min_k_exact": [w for w in working if w[2]],
    }


def diag_extended(data, o, hi, elem_decl, cands):
    """Walk the 6-byte law AND the #64 escaped law gate by gate."""
    out = {}
    mk = data[o + 1]
    hlen = facets.header_len(data, o)
    out["hlen"] = hlen
    out["rides_hdrs"] = mk in composite.EXTENDED_HEADER_MARKERS
    # ---- the 6-byte raw-u8 law
    if hlen == 6 and mk in composite.EXTENDED_HEADER_MARKERS:
        ty, b3, b4 = data[o + 2], data[o + 3], data[o + 4]
        k = b3 + b4
        n = int.from_bytes(data[o + 6 : o + 10], "little")
        has_normal = mk in composite.EXTENDED_NORMAL_MARKERS
        base = o + 10 + (12 if has_normal else 0)
        counts = tuple(data[base : base + k]) if base + k <= hi else ()
        out["law6"] = {
            "ty": ty,
            "b3": b3,
            "b4": b4,
            "k": k,
            "n": n,
            "n_law": n == 3 * ty + sum(counts) if base + k <= hi else None,
            "n_law_gap": n - (3 * ty + sum(counts)) if base + k <= hi else None,
            "counts_tail_cut": base + k > hi,
        }
    # ---- the #64 escaped law (read_count chain, per-field escape flags)
    try:
        steps = {}
        p0 = o + 2
        ty, p1 = facets.read_count(data, p0)
        b3, p2 = facets.read_count(data, p1)
        b4, p3 = facets.read_count(data, p2)
        p = p3
        steps["ty"] = ty
        steps["ty_esc"] = (p1 - p0) == 5
        steps["b3"] = b3
        steps["b3_esc"] = (p2 - p1) == 5
        steps["b4"] = b4
        steps["b4_esc"] = (p3 - p2) == 5
        steps["escapes"] = sum((steps["ty_esc"], steps["b3_esc"], steps["b4_esc"]))
        fixed_ff = p < hi and data[p] == 0xFF
        steps["fixed_ff"] = fixed_ff
        if fixed_ff and p + 5 <= hi:
            n = int.from_bytes(data[p + 1 : p + 5], "little")
            steps["n"] = n
            steps["n_ok"] = 0 <= n <= facets.MAX_REFS
            k = b3 + b4
            steps["k"] = k
            steps["k_over_cap"] = k > composite.ESCAPED_MAX_K
            if steps["n_ok"] and not steps["k_over_cap"]:
                has_normal = mk in composite.EXTENDED_NORMAL_MARKERS
                q = p + 5 + (12 if has_normal else 0)
                read = facets.read_counts(data, q, k, hi)
                steps["counts_read"] = read is not None
                if read is not None:
                    counts, clen = read
                    # per-entry escape tally: a count whose byte is 0xff
                    qq = q
                    esc_n = 0
                    for _c in counts:
                        esc_n += 1 if data[qq] == 0xFF else 0
                        _v, qq = facets.read_count(data, qq)
                    steps["escaped_counts"] = esc_n
                    steps["counts_bytes"] = clen
                    steps["n_law"] = n == 3 * ty + sum(counts)
                    steps["n_law_gap"] = n - (3 * ty + sum(counts))
                    widths = (
                        (1, 2, 3)
                        if elem_decl is not None and elem_decl > 65_535
                        else (1, 2)
                    )
                    # boundaries: all candidate headers vs accepted spans
                    nxt_all = min((c for c in cands if c > o), default=hi)
                    if steps["n_law"]:
                        refs_start = q + clen
                        # tiling under each width, oob and repeats
                        tiles = []
                        for width in widths:
                            end = refs_start + width * n
                            if end > min(nxt_all, hi):
                                continue
                            refs = [
                                int.from_bytes(
                                    data[refs_start + width * j : refs_start + width * (j + 1)],
                                    "big",
                                )
                                for j in range(n)
                            ]
                            oob = (
                                any(r >= elem_decl for r in refs)
                                if elem_decl is not None
                                else False
                            )
                            repeats = any(
                                len(set(refs[s : s + 3])) < 3
                                for s in range(0, 3 * ty, 3)
                            ) or any(
                                c > 0 and len(set(refs[off : off + c])) < c
                                for off, c in _loop_offsets(counts)
                            )
                            tiles.append(
                                (width, end, end == nxt_all, oob, repeats)
                            )
                        steps["width_vote"] = tiles
                        steps["nxt_all_candidate"] = nxt_all
                    # u16be-counts probe: the same law with a 2-byte counts
                    # table (the BundleSegment3 0x47 variant). Counts law +
                    # tiling + oob, reported raw.
                    if steps["n_ok"] and not steps["k_over_cap"]:
                        has_normal = mk in composite.EXTENDED_NORMAL_MARKERS
                        q16 = p + 5 + (12 if has_normal else 0)
                        if q16 + 2 * k <= hi:
                            counts16 = [
                                int.from_bytes(data[q16 + 2 * j : q16 + 2 * j + 2], "big")
                                for j in range(k)
                            ]
                            s16 = sum(counts16)
                            nlaw16 = n == 3 * ty + s16
                            probe = {"n_law": nlaw16, "sum": s16}
                            if nlaw16:
                                refs_start16 = q16 + 2 * k
                                for width in widths:
                                    end16 = refs_start16 + width * n
                                    if end16 > min(nxt_all, hi):
                                        continue
                                    refs16 = [
                                        int.from_bytes(
                                            data[refs_start16 + width * j : refs_start16 + width * (j + 1)],
                                            "big",
                                        )
                                        for j in range(n)
                                    ]
                                    oob16 = (
                                        any(r >= elem_decl for r in refs16)
                                        if elem_decl is not None
                                        else False
                                    )
                                    probe.setdefault("tiles", []).append(
                                        (width, end16, end16 == nxt_all, oob16)
                                    )
                            steps["u16be_counts_probe"] = probe
        out["law_esc"] = steps
    except (IndexError, struct.error) as exc:
        out["law_esc"] = {"error": str(exc)}
    return out


def _loop_offsets(counts):
    off = 0
    for c in counts:
        yield off, c
        off += c


def dump_candidate(data, o, nxt, hi, elem_decl, elements, cands_all):
    mk = data[o + 1]
    lines = [
        f"  candidate @{o} (abs in store) marker=0x{mk:02x} "
        f"nxt_candidate={nxt} span_to_nxt={nxt - o}B"
    ]
    lines += hexdump(data, o, 48)
    hlen = facets.header_len(data, o)
    fields = [f"hlen={hlen}"]
    if hlen == 4:
        fields.append(f"ty={data[o + 2]}")
    elif hlen == 6:
        fields.append(f"ty={data[o + 2]} b3={data[o + 3]} b4={data[o + 4]}")
    if hlen in (4, 5, 6) and o + hlen + 4 <= hi:
        n = int.from_bytes(data[o + hlen : o + hlen + 4], "little")
        fields.append(f"n@+{hlen}(u32le)={n}")
        has_normal = mk in facets.NORMAL_MARKERS_ALL or mk in (
            0x4F,
        )
        if has_normal and o + hlen + 16 <= hi:
            normal = struct.unpack("<fff", data[o + hlen + 4 : o + hlen + 16])
            fields.append(f"normal=({normal[0]:.4g},{normal[1]:.4g},{normal[2]:.4g})")
    lines.append("    fields: " + "; ".join(fields))
    if mk in (0x47, 0x4F):
        d = diag_extended(data, o, hi, elem_decl, cands_all)
        lines.append(f"    6-byte law: {d.get('law6', 'skipped (hlen != 6)')}")
        lines.append(f"    #64 escaped law: {d.get('law_esc')}")
    else:
        d = diag_short(data, o, nxt, hi, elem_decl, mk)
        if "error" in d:
            lines.append(f"    short-law diagnosis: {d['error']}")
            if hlen == 6:
                # not an extended-family marker: the 6-byte form is a
                # family the shipped parsers all skip. Probe the f32
                # reading (explicit-coordinate record?).
                lines.append(
                    "    6-byte non-extended marker: skipped by the short law "
                    "(hlen==6) and both extended laws (marker != 0x47/0x4f)"
                )
                for off in (6, 7):
                    clean = 0
                    vals = []
                    pos = o + off
                    while pos + 4 <= hi:
                        v = struct.unpack_from("<f", data, pos)[0]
                        if not (v == v and abs(v) < 1e9):
                            break
                        clean += 1
                        if len(vals) < 9:
                            vals.append(round(v, 4))
                        pos += 4
                    lines.append(
                        f"    f32 probe from +{off}: {clean} clean f32 words "
                        f"({clean // 3} triples) then non-clean; head={vals}"
                    )
        else:
            lines.append(
                f"    short law: n={d['n']} first_count={d['first_count']} "
                f"working(w,k,exact,oob)={d['working'][:8]}"
                + (f" ... {len(d['working'])} total" if len(d["working"]) > 8 else "")
            )
            lines.append(
                f"    cap MAX_LOOP_COUNTS={composite.MAX_LOOP_COUNTS}: "
                f"min_k={d['min_k']} cap_blocked={d['cap_blocked']} "
                f"exact_tiling_combos={d['min_k_exact'][:4]}"
            )
    return lines


def probe_file(rel, meta):
    path = os.path.join(ROOT, rel)
    with open(path, "rb") as fh:
        data = fh.read()
    print(f"\n== {rel}  ({len(data)} B, sha {meta[:16]})")
    for container, span in locate_spans(data):
        lo, hi = span.body_lo, span.body_hi
        groups, kinds = pool.scan_pool_groups(data, lo, hi)
        if not pool.has_composite_space(kinds):
            print(
                f"  span [{lo},{hi}) {hi - lo}B {container}: not composite "
                f"(kinds={[k.hex() for k in kinds][:4]})"
            )
            continue
        stage = None
        info_detail = ""
        try:
            _p, _t, _d, info = composite.decode_composite_store(
                data, span, groups, kinds, _seam_area=None
            )
            stage = info.get("stage")
            info_detail = (
                f"cand={info.get('facet_candidates')} "
                f"recs={info.get('facet_records')} "
                f"ext={info.get('extended_header_records', 0)}"
            )
        except ExportError as exc:
            info_detail = f"decode error: {exc.detail[:120]}"
        hdrs = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
        node_hi = hdrs[0] if hdrs else hi
        ln = composite.find_list_node(data, lo, node_hi)
        if ln is None:
            print(
                f"  span [{lo},{hi}) {hi - lo}B {container}: no list node; {info_detail}"
            )
            continue
        payload, elem_decl, _b = ln
        try:
            elements, _rinfo = composite.decode_region(payload, elem_decl)
        except ExportError as exc:
            print(
                f"  span [{lo},{hi}) {hi - lo}B {container}: decode_region fails "
                f"({exc.detail[:100]}); {info_detail}"
            )
            continue
        print(
            f"  span [{lo},{hi}) {hi - lo}B {container}: elem_decl={elem_decl} "
            f"stage={stage} {info_detail}"
        )
        accepted, _records, _ext = accepted_spans(
            data, lo, hi, elem_decl, elements, hdrs
        )
        cands = candidate_offsets(data, lo, hi)
        clusters = gap_clusters(data, lo, hi, accepted, cands)
        if not clusters:
            print("    no gap clusters: every candidate is inside an accepted record")
            continue
        print(f"    gap clusters: {len(clusters)}")
        for start, end, os_, prev_end in clusters:
            tallies = {}
            for o in os_:
                mk = data[o + 1]
                tallies[mk] = tallies.get(mk, 0) + 1
            t = " ".join(f"0x{m:02x}x{c}" for m, c in sorted(tallies.items()))
            print(
                f"      gap [{start},{end}) {end - start}B (prev rec ends @{prev_end}) "
                f"candidates: {t}"
            )
            for o in os_:
                nxt = min(
                    (c for c in cands if c > o), default=end
                )
                for line in dump_candidate(
                    data, o, nxt, hi, elem_decl, elements, cands
                ):
                    print(line)


def census_42():
    rows = load_manifest()
    files = 0
    blocked = 0
    blocked_exact = 0
    near_miss = 0
    unresolved_total = 0
    blocked_examples = []
    k_tally = {}
    for row in rows:
        if row["kind"] != "part":
            continue
        path = os.path.join(ROOT, row["local_path"])
        with open(path, "rb") as fh:
            data = fh.read()
        try:
            spans = locate_spans(data)
        except Exception:
            continue
        hit = False
        for _container, span in spans:
            lo, hi = span.body_lo, span.body_hi
            try:
                groups, kinds = pool.scan_pool_groups(data, lo, hi)
                if not pool.has_composite_space(kinds):
                    continue
                hdrs = [m.start() for m in facets.STRIP_RE.finditer(data, lo, hi)]
                node_hi = hdrs[0] if hdrs else hi
                ln = composite.find_list_node(data, lo, node_hi)
                if ln is None:
                    continue
                payload, elem_decl, _b = ln
                elements, _r = composite.decode_region(payload, elem_decl)
                accepted, _records, _ext = accepted_spans(
                    data, lo, hi, elem_decl, elements, hdrs
                )
            except Exception:
                continue
            cands = candidate_offsets(data, lo, hi)
            for o in cands:
                if any(a <= o < e for a, e, _k in accepted):
                    continue
                if data[o + 1] != 0x42:
                    continue
                unresolved_total += 1
                hit = True
                nxt = min((c for c in cands if c > o), default=hi)
                d = diag_short(data, o, nxt, hi, elem_decl, 0x42)
                if d.get("cap_blocked"):
                    blocked += 1
                    k_tally[d["min_k"]] = k_tally.get(d["min_k"], 0) + 1
                    exact = [w for w in d["working"] if w[2] and not w[3]]
                    if exact:
                        blocked_exact += 1
                        blocked_examples.append(
                            (row["path"], o, d["n"], d["min_k"], exact[0][:2])
                        )
                    else:
                        blocked_examples.append((row["path"], o, d["n"], d["min_k"], None))
                elif d.get("working"):
                    near_miss += 1
        if hit:
            files += 1
    print(f"parts scanned with >=1 unresolved 0x42: {files}")
    print(f"unresolved 0x42 candidates total: {unresolved_total}")
    print(f"  working parse ONLY at k > {composite.MAX_LOOP_COUNTS}: {blocked}")
    print(f"    ...of those, exact-tiling + in-bounds parse exists: {blocked_exact}")
    print(f"  (near-miss: some parse exists but never exact+in-bounds: {near_miss})")
    print(f"  min_k distribution: {dict(sorted(k_tally.items()))}")
    for path, o, n, k, exact in blocked_examples[:12]:
        print(f"    {path} @{o} n={n} min_k={k} exact={exact}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="manifest path substrings")
    ap.add_argument("--census-42", action="store_true")
    args = ap.parse_args()
    if args.census_42:
        census_42()
        return
    rows = load_manifest()
    seen = set()
    for name in args.names:
        for row in rows:
            if name.lower() not in row["path"].lower():
                continue
            if row["sha256"] in seen:
                continue
            seen.add(row["sha256"])
            probe_file(row["local_path"], row["sha256"])


if __name__ == "__main__":
    main()
