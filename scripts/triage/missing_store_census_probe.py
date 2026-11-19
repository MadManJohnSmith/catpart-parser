"""Missing-geometry-store census probe (2026-11-19, read-only).

Scope: the ``missing-store`` rows of a fitness report — the parts whose
export fails with ``missing-geometry-store`` after the stage-3a and
stage-12 locator extensions. The probe answers one question per file:
does a nested ``V5_CFV2`` stream store exist anywhere in the file (under
*any* container / locator name), and if not, what does the file carry
instead?

Method (all byte facts, stdlib only, deterministic, manifest order):

- **store markers**: every ``V5_CFV2\\0``, ``CATIA_V5 CB0001\\0`` and
  ``CB__END\\0`` occurrence, the storage-block inventory
  (``store.valid_blocks``) with region sizes, and the export seam's own
  ``store.locate_store`` over every block (the shipped probe order:
  stdcont, xdoclink, seebody, other-container).
- **stream payload primitives**: ``10 24 04 ff ff 00 00 00`` wrappers
  with the ``01 06`` pool sub-kind (G2) and ``05 08 01`` vertex records.
  A file with neither cannot be turned into a mesh by *any* locator law:
  the locator would have nothing decodable to point at.
- **self-named document catalogs** (the extended-header / dual-catalog
  generation): a ``CB0001`` inside a block region whose tail
  ``[cb, next CB__END]`` satisfies the N6 laws on its own length. The
  shipped header-less law derives the tail length from the region end,
  so it rejects these by construction; this probe measures what a
  *self-named-tail* law would locate, and whether that span's body
  carries a pool (the L2 question).
- **outer wrapper law**: the file's own ``V5_CFV2`` at offset 0 is a
  store header by the documented layout (dword8 = trailing catalog
  offset, dword12 = catalog length). The probe measures whether its
  tail validates and whether its body (offset 64..dword8) carries a
  pool — the second candidate locator law.
- **representation payload**: the bag-rep carrier the extended-header
  family actually stores — ``CAT3DBagRep`` / ``CAT3DBagRepT`` /
  ``CATSurfacicRep`` class tokens, ``04 04 fd ff`` node records, and
  12-byte float point runs (a run of >= 3 consecutive plausible points
  at stride 12; the detector is a presence measure, not a decode).

Run::

    .venv/bin/python -I scripts/triage/missing_store_census_probe.py \
        [--report fitness/reports/20261119T035609Z-7dc3ea.json] \
        [--corpus-root .] [--out docs/evidence/data/missing-store-census.csv] \
        [--sample-out docs/evidence/data/missing-store-sample-15.csv]

Writes two CSVs and prints the class tally. Read-only with respect to
the corpus; no ``src/`` dependency beyond the committed geometry modules
(``store``/``pool``), which are used as the measurement infrastructure.
"""

import argparse
import csv
import json
import math
import os
import re
import struct
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from catpart.geometry import pool, store  # noqa: E402

DEFAULT_REPORT = os.path.join(
    ROOT, "fitness", "reports", "20261119T035609Z-7dc3ea.json"
)

BAG_TOKENS = (b"CAT3DBagRep", b"CATSurfacicRep")
FEATURE_TOKENS = (
    b"Sketch",
    b"Constraints",
    b"ContourList",
    b"PlanarSupport",
    b"MechMod.feat",
    b"PartDesign.feat",
    b"Geometries",
)

PAYLOAD_BLOCKS = (
    "CATStdCont",
    "CATSeeBodyCont",
    "CATBRepModeContainer",
    "CGMGeom",
    "CATCGRCont",
)

SAMPLE_SIZE = 15


def load_manifest(corpus_root):
    out = {}
    with open(os.path.join(ROOT, "manifests", "corpus-manifest.csv"), newline="") as fh:
        for row in csv.DictReader(fh):
            local = row["local_path"]
            out[row["path"]] = {
                "sha256": row["sha256"],
                "repo": row["repo"],
                "split": row["split"],
                "local": os.path.join(corpus_root, local),
            }
    return out


def header_dwords(data):
    return [int.from_bytes(data[k : k + 4], "big") for k in range(0, 32, 4)]


def header_family(data):
    if len(data) < 32 or data[:8] != store.V5_CFV2:
        return "non-catia"
    if data[16:24] == b"\xff" * 8:
        return "ff8"
    d16 = int.from_bytes(data[16:20], "big")
    d20 = int.from_bytes(data[20:24], "big")
    if d16 and d20:
        return "dual-catalog"
    return "v5-other"


def point_runs(data, spans):
    """(longest 12-byte-stride point run, aligned triple count, run start).

    Scanned only inside the payload container regions (``spans``): a
    12-byte float triple anywhere else (catalog text, feature records) is
    a coincidence, not geometry.
    """
    n = len(data)
    inside = bytearray(n)
    for lo, hi in spans:
        inside[lo:hi] = b"\x01" * max(0, hi - lo)
    ok = bytearray(max(0, n - 11))
    for o in range(n - 12):
        if not inside[o]:
            continue
        x, y, z = struct.unpack_from("<3f", data, o)
        if (
            math.isfinite(x)
            and math.isfinite(y)
            and math.isfinite(z)
            and 1e-2 < abs(x) < 1e5
            and 1e-2 < abs(y) < 1e5
            and 1e-2 < abs(z) < 1e5
        ):
            ok[o] = 1
    best = 0
    start = -1
    for o in range(len(ok)):
        if ok[o] and (o < 12 or not ok[o - 12]):
            k = 0
            q = o
            while q < len(ok) and ok[q]:
                k += 1
                q += 12
            if k > best:
                best = k
                start = o
    return best, sum(ok[::12]), start


def regions(data, blocks):
    out = {}
    for blk, name in blocks:
        out.setdefault(
            name,
            (
                blk,
                store.probe_region(
                    data, blk, blocks, int.from_bytes(data[8:12], "big")
                ),
            ),
        )
    return out


def has_pool_group(seg):
    """True when ``seg`` carries a ``01 06`` pool group (G2 decodable unit)."""
    for w in store.find_all(seg, pool.FULL_WRAP, 0, len(seg)):
        if bytes(seg[w + 8 : w + 10]) == pool.POOL_SUBKIND:
            return True
    return False


def self_named_catalog(data, cb, blocks, d8):
    """(owner block name, before-pool, after-pool, doc-catalog flag) or None.

    A ``CB0001`` inside a block region whose tail ends at the next
    ``CB__END`` and satisfies the N6 laws on its own length. The shipped
    header-less law derives the tail length from the region end, so it
    rejects these by construction; this measures what a *self-named-tail*
    law would locate. Both candidate bodies are checked for a pool: the
    prefix the header-less law reads (block + 64 .. catalog) and the
    suffix after the catalog (catalogue-first layout, the extended-header
    family's shape).
    """
    end = data.find(store.CB_END, cb)
    if end < 0:
        return None
    tail = bytes(data[cb : end + 8])
    if not store.validate_catalog_tail(tail):
        return None
    owner = None
    for blk, name in blocks:
        if blk <= cb < store.probe_region(data, blk, blocks, d8):
            owner = (blk, name)
            break
    if owner is None:
        return None
    rend = store.probe_region(data, owner[0], blocks, d8)
    before = data[owner[0] + 64 : cb]
    after = data[end + 8 : rend]
    doc = any(
        t.encode("utf-16-le") in tail
        for t in ("CATPreview", "CATPropertySets", "ProjectHeader")
    )
    return owner[1], has_pool_group(before), has_pool_group(after), doc


def measure(path, meta, report_row):
    with open(meta["local"], "rb") as fh:
        data = fh.read()
    size = len(data)
    fam = header_family(data)
    d = header_dwords(data) if size >= 32 else [0] * 8
    blocks = store.valid_blocks(data)
    regs = regions(data, blocks)
    declared = report_row.get("container_names") or []
    v5 = store.find_all(data, store.V5_CFV2, 0, size)
    cbs = store.find_all(data, store.CB0001, 0, size)
    ends = store.find_all(data, store.CB_END, 0, size)
    pgroups = 0
    wrappers = store.find_all(data, pool.FULL_WRAP, 0, size)
    for w in wrappers:
        if bytes(data[w + 8 : w + 10]) == pool.POOL_SUBKIND:
            pgroups += 1
    vrecs = store.find_all(data, pool.VREC, 0, size)
    nodes = store.find_all(data, b"\x04\x04\xfd\xff", 0, size)
    spans = [(regs[nm][0], regs[nm][1]) for nm in PAYLOAD_BLOCKS if nm in regs]
    run, triples, run_start = point_runs(data, spans)
    run_region = ""
    for nm in PAYLOAD_BLOCKS:
        if nm in regs and regs[nm][0] <= run_start < regs[nm][1]:
            run_region = nm
            break

    # Shipped locator over every block (the export seam's own law).
    shipped = []
    for blk, name in blocks:
        try:
            span = store.locate_store(
                data, blk, blocks, d[2], container=store.CONTAINER_OTHER
            )
        except Exception:  # malformed-store-header is a classification, not a crash
            span = None
        if span is not None:
            shipped.append(name)

    # Candidate law A: self-named-tail document catalogs.
    ext = []
    for cb in cbs:
        got = self_named_catalog(data, cb, blocks, d[2])
        if got is not None:
            ext.append(got)

    # Candidate law B: the offset-0 outer wrapper as a store span.
    outer_shipped = False
    outer_trimmed = False
    outer_body_pool = False
    # The H1 chain (d8 + d12 == size) holds on the modern generation, not
    # on the extended-header/dual-catalog one (catalog at 64, or a trailing
    # document region after the catalog); accept any window that fits.
    if fam != "non-catia" and d[2] >= 64 and d[2] + d[3] <= size:
        if store.validate_catalog_tail(bytes(data[d[2] : d[2] + d[3]])):
            outer_shipped = True
        else:
            end = data.find(store.CB_END, d[2], d[2] + d[3])
            if end >= 0 and store.validate_catalog_tail(bytes(data[d[2] : end + 8])):
                outer_trimmed = True
        if outer_shipped or outer_trimmed:
            outer_body_pool = has_pool_group(data[64 : d[2]])

    owners = []
    for cb in cbs:
        got = self_named_catalog(data, cb, blocks, d[2])
        owners.append(got[0] + "@" + str(cb) if got else "outer@" + str(cb))
    bag = sum(data.count(t) for t in BAG_TOKENS)
    feat = sum(1 for t in FEATURE_TOKENS if t in data)
    doc_catalogs = sum(1 for got in ext if got[3])

    if fam == "non-catia":
        cls = "non-catia"
    elif bag:
        cls = "bag-rep-named"
    elif run >= 3:
        cls = "point-array"
    elif nodes:
        cls = "topology-only"
    elif feat:
        cls = "feature-only"
    else:
        cls = "no-representation"

    row = {
        "path": report_row["path"],
        "sha256": meta["sha256"],
        "repo": meta["repo"],
        "split": meta["split"],
        "kind": report_row.get("kind"),
        "detected_version": report_row.get("detected_version"),
        "size_bytes": size,
        "header_family": fam,
        "hdr_d8": d[2],
        "hdr_d12": d[3],
        "hdr_d16": d[4],
        "hdr_d20": d[5],
        "n_v5_cfv2": len(v5),
        "v5_offsets": ";".join(map(str, v5)),
        "n_cb0001": len(cbs),
        "cb0001_offsets": ";".join(map(str, cbs)),
        "cb0001_seen": ";".join(owners),
        "n_cb_end": len(ends),
        "n_blocks": len(blocks),
        "block_names": ";".join(name for _, name in blocks),
        "declared_containers": ";".join(declared),
        "container_table": "yes" if declared else "no",
        "stdcont_bytes": regs.get("CATStdCont", (0, 0))[1]
        - regs.get("CATStdCont", (0, 0))[0],
        "seebody_bytes": regs.get("CATSeeBodyCont", (0, 0))[1]
        - regs.get("CATSeeBodyCont", (0, 0))[0],
        "brepmode_bytes": regs.get("CATBRepModeContainer", (0, 0))[1]
        - regs.get("CATBRepModeContainer", (0, 0))[0],
        "cgm_bytes": regs.get("CGMGeom", (0, 0))[1] - regs.get("CGMGeom", (0, 0))[0],
        "cgr_bytes": regs.get("CATCGRCont", (0, 0))[1]
        - regs.get("CATCGRCont", (0, 0))[0],
        "pool_wrappers": len(wrappers),
        "pool_groups_0106": pgroups,
        "vrec_hits": len(vrecs),
        "node_records": len(nodes),
        "point_run": run,
        "point_run_start": run_start,
        "point_run_region": run_region,
        "point_triples": triples,
        "bag_tokens": bag,
        "feature_tokens": feat,
        "shipped_located_blocks": ";".join(shipped),
        "ext_located_spans": len(ext),
        "ext_doc_catalogs": doc_catalogs,
        "ext_body_pools": sum(1 for _, before, after, _ in ext if before or after),
        "outer_tail_shipped": int(outer_shipped),
        "outer_tail_trimmed": int(outer_trimmed),
        "outer_body_pool": int(outer_body_pool),
        "geometry_class": cls,
    }
    if fam == "non-catia":
        row["verdict"] = "malformed-input"
    elif pgroups:
        row["verdict"] = "store-absent-pool-present"
    elif cls in ("feature-only", "no-representation"):
        row["verdict"] = "store-absent-no-facet-payload"
    else:
        row["verdict"] = "store-absent-bag-rep-payload"
    return row


def stratify(rows, n):
    """Round-robin one row at a time from each (family, class) group."""
    groups = {}
    for row in sorted(
        rows, key=lambda r: (r["header_family"], r["geometry_class"], r["path"])
    ):
        groups.setdefault((row["header_family"], row["geometry_class"]), []).append(row)
    keys = sorted(groups)
    picks = []
    idx = 0
    while len(picks) < n and any(idx < len(groups[k]) for k in keys):
        for k in keys:
            if idx < len(groups[k]) and len(picks) < n:
                picks.append(groups[k][idx])
        idx += 1
    return picks


def anchor(rel_path, meta):
    """Print the byte evidence for one file (the doc's pinned sample)."""
    with open(meta["local"], "rb") as fh:
        data = fh.read()
    size = len(data)
    d = header_dwords(data) if size >= 32 else [0] * 8
    fam = header_family(data)
    blocks = store.valid_blocks(data)
    print(f"path {rel_path}")
    print(f"size {size} sha256 {meta['sha256']}")
    print(f"header_family {fam} dwords {' '.join(str(x) for x in d)}")
    print(f"magic {data[:8]!r} bytes16_24 {data[16:24].hex(' ')}")
    if fam == "non-catia":
        print(f"head {data[:120]!r}")
        return
    print("blocks:")
    for blk, name in blocks:
        rend = store.probe_region(data, blk, blocks, d[2])
        print(f"  {blk:>8} {name:<26} {rend - blk:>8}")
        for w in store.find_all(data, pool.FULL_WRAP, blk, rend):
            if bytes(data[w + 8 : w + 10]) == pool.POOL_SUBKIND:
                print(f"    pool group at {w}")
    print(
        "markers: V5",
        store.find_all(data, store.V5_CFV2, 0, size),
        "CB0001",
        store.find_all(data, store.CB0001, 0, size),
        "CB__END",
        store.find_all(data, store.CB_END, 0, size),
        "bag",
        [data.find(t) for t in BAG_TOKENS if data.find(t) >= 0],
        "nodes",
        store.find_all(data, b"\x04\x04\xfd\xff", 0, size)[:6],
    )
    for cb in store.find_all(data, store.CB0001, 0, size):
        end = data.find(store.CB_END, cb)
        tail = bytes(data[cb : end + 8]) if end >= 0 else b""
        tb = tail[-36:]
        fields = (
            [int.from_bytes(tb[i : i + 4], "big") for i in range(0, 28, 4)]
            if len(tb) == 36
            else []
        )
        owner = ""
        for blk, name in blocks:
            if blk <= cb < store.probe_region(data, blk, blocks, d[2]):
                owner = f"{name}@{blk}"
                break
        names = sorted(
            {
                s.decode("utf-16-le", "replace")
                for s in re.findall(rb"(?:[\x20-\x7e]\x00){4,}", tail)
            }
        )[:10]
        print(f"CB0001 {cb} owner {owner or 'outer'}")
        print(
            f"  tail_len {len(tail)} trailer A..G {fields} n6_valid {store.validate_catalog_tail(tail)}"
        )
        print(f"  catalog_names {names}")
    regs = regions(data, blocks)
    spans = [(regs[nm][0], regs[nm][1]) for nm in PAYLOAD_BLOCKS if nm in regs]
    run, triples, start = point_runs(data, spans)
    print(f"point_run {run} triples {triples} start {start}")
    if start >= 0:
        pts = [
            struct.unpack_from("<3f", data, start + 12 * i) for i in range(min(4, run))
        ]
        print("  points", [tuple(round(v, 3) for v in p) for p in pts])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=DEFAULT_REPORT)
    ap.add_argument("--corpus-root", default=ROOT)
    ap.add_argument(
        "--out",
        default=os.path.join(
            ROOT, "docs", "evidence", "data", "missing-store-census.csv"
        ),
    )
    ap.add_argument("--sample-out", default=None)
    ap.add_argument(
        "--anchor",
        default=None,
        help="manifest path of one file to print byte evidence for",
    )
    args = ap.parse_args()

    with open(args.report) as fh:
        report = json.load(fh)
    manifest = load_manifest(args.corpus_root)
    if args.anchor:
        anchor(args.anchor, manifest[args.anchor])
        return
    targets = [
        f
        for f in report["files"]
        if ((f.get("l2") or {}).get("error_class") == "missing-geometry-store")
    ]
    rows = [measure(f["path"], manifest[f["path"]], f) for f in targets]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("rows", len(rows))
    print("header_family", dict(Counter(r["header_family"] for r in rows)))
    print("geometry_class", dict(Counter(r["geometry_class"] for r in rows)))
    print("verdict", dict(Counter(r["verdict"] for r in rows)))
    print("kind", dict(Counter(r["kind"] for r in rows)))
    print("store markers: v5>1", sum(1 for r in rows if r["n_v5_cfv2"] > 1))
    print("pool groups", sum(r["pool_groups_0106"] for r in rows))
    print("vertex-record hits", sum(r["vrec_hits"] for r in rows))
    print("shipped located blocks", sum(1 for r in rows if r["shipped_located_blocks"]))
    print(
        "ext located spans",
        sum(r["ext_located_spans"] for r in rows),
        "doc catalogs",
        sum(r["ext_doc_catalogs"] for r in rows),
        "with pools",
        sum(r["ext_body_pools"] for r in rows),
    )
    print(
        "outer tail shipped",
        sum(r["outer_tail_shipped"] for r in rows),
        "trimmed",
        sum(r["outer_tail_trimmed"] for r in rows),
        "with pools",
        sum(r["outer_body_pool"] for r in rows),
    )

    if args.sample_out:
        picks = stratify([r for r in rows if r["kind"] == "part"], SAMPLE_SIZE)
        with open(args.sample_out, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(picks)
        print("sample", len(picks), "->", args.sample_out)


if __name__ == "__main__":
    main()
