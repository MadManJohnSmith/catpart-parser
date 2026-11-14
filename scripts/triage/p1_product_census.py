#!/usr/bin/env python3
"""P1 product census (#46, spec F #45): classify 100% of the corpus
CATProduct population by root cause — containers, link/instance/transform
records, absences — with per-file byte evidence and ceiling arithmetic.

Phase 6 opens with the Phase 4 method at full scale: the Phase 4-era
negative (0/37 sampled products carry a geometry store, the container
table carries no instance hierarchy — ticket #24;
docs/evidence/2026-11-08-geometry-payloads.md) was a SAMPLED result on
37 products. This census classifies every manifest kind=product row
(382 rows, 2026-11-14) with the shipped scanners plus targeted probes.

Population: rows of manifests/corpus-manifest.csv with kind=product,
sorted by local_path (deterministic). The manifest kind comes from the
source path/extension; the census re-derives the byte-level kind and
reports the delta (manifest-kind misfits are named, never folded).

Shipped infrastructure (imported, not re-implemented):
- ``catpart.containers.parse_container_table`` / ``detect_kind`` — the
  container-name table model (B1, docs/format/container-table.md) and
  the kind law K1.
- ``catpart.geometry.store.valid_blocks`` / ``locate_store`` — the
  storage-block walk (B3 boundary rule) and the nested-store law.

The census's own detectors (each with a committed synthetic negative in
``--selftest``, per the 2026-11-13 retro candidate-4 rule):

- **Document-reference strings (law A)**: CATIA's length-prefixed
  ASCII string ``34 <len> <bytes>`` (``0x34`` marker, u8 length =
  exact char count). Worked example System_demo_doc.CATProduct @0x109:
  ``34 1a "System_demo_doc.CATProduct" 9f``. Extracted corpus-wide,
  classified self vs child (against the file's own basename), resolved
  against the corpus manifest (basename and relative-path tails).
  What the detector does NOT discriminate: it cannot tell a live link
  record from a copied display string (e.g. a title-block annotation);
  both count. The 9f-termination rate is reported separately.
- **Structure-pool strings (law B)**: the product-structure stream's
  string pool encodes ``<len> <bytes>`` with u8 length = char count + 1,
  chained without terminators (worked example Product1.CATProduct
  @0x23f2: ``08 "Part001" 0e "_InstanceName" 0a "Part001.1"
  0a "_Position" ...``). The +1 law discriminates it from law A
  (selftest asserts both directions). The pool's pairing structure
  (which instance owns which position) is NOT decoded here — P2.
- **Strip-record grammar (V5)**: the geometry-payloads note's record
  family ``01 <0x41..0x4f> <0x01..0x0a> ff [u32le n][2n bytes]``
  with the verification predicate (1 <= n <= 1e6, record fits) —
  measured as a signature, not a decode.
- **Nested-store locator**: the shipped ``store.locate_store`` probed
  on EVERY storage block of every product regardless of container name
  (the stage-3a/12 container-independent extension) — the strongest
  form of the geometry-store-absent sweep.

Region model: storage blocks own ``[block_start, next_block_start)``
(B3, the shipped ``probe_region`` law); bytes before the first block
form the ``pre-block`` region. Caveat recorded in the note: data
belonging to a stream whose block header follows it is attributed to
the preceding region by this model — the marker×region table is a
localization, not an ownership law (the stream-to-block binding is
unparsed: the name table's f1 join, P2 territory).

Root-cause classes (per file, one class each):
- ``non-catia``: no V5 structure at all (placeholder text files saved
  with a .CATProduct name).
- ``catia-notable``: CATIA storage blocks present, no container-name
  table (the B31CAADoc/CAA sample family + Gardena).
- ``table-…``: container-name table parsed; suffixed by the evidence
  flags present (sorted): ``pool`` (structure-pool vocabulary), ``pos``
  (_Position attribute), ``refs`` (child document-reference strings);
  ``table-min`` = table but no flag. The flags are also separate CSV
  columns — the class label is the join, never the only record.

Outputs (explicit paths, one row-set per claim family; all match the
``*claims*.csv`` hygiene glob):
- docs/evidence/data/p1-census-product-files-claims.csv   (--census)
- docs/evidence/data/p1-census-container-inventory-claims.csv (--census)
- docs/evidence/data/p1-census-absence-sweeps-claims.csv  (--sweeps)
- docs/evidence/data/p1-census-reference-resolution-claims.csv (--refs)
- docs/evidence/data/p1-census-ceiling-claims.csv         (--ceiling)

Run: python3 -I scripts/triage/p1_product_census.py --all
(reproduction commands in the owning note,
docs/evidence/2026-11-14-p1-product-census.md). Corpus binaries are
never written; the corpus itself is read-only input addressed through
the manifest's local_path columns.
"""

from __future__ import annotations

import argparse
import csv
import re
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from catpart.containers import (  # noqa: E402
    SCAN_WINDOW,
    detect_kind,
    parse_container_table,
)
from catpart.geometry import store  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "triage"))
import decode_tail_region as tail_dec  # noqa: E402  (committed decoder, G1/B4)

MANIFEST = ROOT / "manifests" / "corpus-manifest.csv"
OUT_FILES = ROOT / "docs/evidence/data/p1-census-product-files-claims.csv"
OUT_CONTAINERS = ROOT / "docs/evidence/data/p1-census-container-inventory-claims.csv"
OUT_SWEEPS = ROOT / "docs/evidence/data/p1-census-absence-sweeps-claims.csv"
OUT_REFS = ROOT / "docs/evidence/data/p1-census-reference-resolution-claims.csv"
OUT_CEILING = ROOT / "docs/evidence/data/p1-census-ceiling-claims.csv"

# --- the swept vocabularies -------------------------------------------------

#: Structure-pool vocabulary (observed token set, Product1.CATProduct
#: worked example + corpus string inventory). Law B encoding is tested
#: per token; the per-file pool flag requires >= 3 distinct tokens.
POOL_TOKENS = (
    "ASMPRODUCT",
    "PRDREP",
    "PRDBAGREP",
    "_Component",
    "_PartNumber",
    "_RefProduct",
    "_InstanceName",
    "_Position",
    "CONNECTOR",
    "CONNECTION",
    "IsRoot",
    "_Version",
    "_Reps",
    "3DIC",
)

#: Attribute markers whose region attribution the census reports.
REGION_MARKERS = ("_InstanceName", "_Position", "_PartNumber", "ASMPRODUCT")

#: Document extensions a product link may name (law A strings).
DOC_EXT_RE = re.compile(rb"\.(CATPart|CATProduct|CATShape|cgr|CATSystem|CATSwl|model)$")

#: The V4 stream-name vocabulary of the nested store (geometry-payloads
#: note section 4), swept as UTF-16LE, word-precise (see
#: :func:`utf16_name_hits` — 'Header' must not match 'ProjectHeader').
STREAM_NAMES_UTF16 = tuple(
    name.encode("utf-16-le")
    for name in ("SurfacicReps", "SceneGraph", "MainDataStream", "Describe", "Header", "MAIN")
)


def _utf16_char(data: bytes, i: int) -> int:
    return data[i] | (data[i + 1] << 8)


def _is_alnum_utf16(ch: int) -> bool:
    return (
        0x30 <= ch <= 0x39 or 0x41 <= ch <= 0x5A or 0x61 <= ch <= 0x7A or ch == 0x5F
    )


def utf16_name_hits(data: bytes, needle: bytes, lo: int, hi: int) -> list[int]:
    """Word-precise UTF-16LE occurrences of ``needle``: the utf16 char
    on each side (when in range) must not be alphanumeric/underscore, so
    'Header' does not match 'ProjectHeader' and 'MAIN' not 'DOMAIN'."""
    out = []
    n = len(needle)
    for o in store.find_all(data, needle, lo, hi):
        prev_ok = o < 2 or not _is_alnum_utf16(_utf16_char(data, o - 2))
        next_ok = o + n + 1 >= len(data) or not _is_alnum_utf16(
            _utf16_char(data, o + n)
        )
        if prev_ok and next_ok:
            out.append(o)
    return out

PRINTABLE = re.compile(rb"[\x20-\x7e]{2,240}")
INSTANCE_SHAPE = re.compile(r"^.+\.\d{1,4}$")


def bucket(version: str) -> str:
    """Release bucket of a detected_version string (R15..R26/unknown)."""
    m = re.match(r"V5R(\d+)", version)
    return f"R{m.group(1)}" if m else "unknown"


# --- detectors ---------------------------------------------------------------


def law_a_strings(data: bytes) -> list[tuple[int, str, bool]]:
    """Law A: ``34 <len> <len printable bytes>`` document strings.

    Returns (offset, string, terminated_9f). The length byte must equal
    the exact char count and every string byte printable.
    """
    out = []
    n = len(data)
    for i in range(n - 3):
        if data[i] != 0x34:
            continue
        ln = data[i + 1]
        if ln < 2 or i + 2 + ln > n:
            continue
        s = data[i + 2 : i + 2 + ln]
        if not all(0x20 <= b <= 0x7E for b in s):
            continue
        out.append((i, s.decode("ascii"), i + 2 + ln < n and data[i + 2 + ln] == 0x9F))
    return out


def law_b_valid(token: bytes, data: bytes, i: int) -> bool:
    """Law B at position ``i`` of ``token``: the preceding byte equals
    len(token) + 1 (the pool's char-count+1 length encoding)."""
    return i >= 1 and data[i - 1] == len(token) + 1

def position_attr_present(data: bytes) -> int:
    """1 when ``_Position`` appears as a LAW-B-VALIDATED string (P1
    review F1, ticket #46): a raw whole-file substring also matches
    Elec_X_Position / Elec_Y_Position / Elec_Z_Position pool strings (4
    files miscounted as placed instances on the first run). The law-B
    check at the occurrence offset rejects embedded occurrences: a
    law-B length prefix for "_Position" (9+1) disagrees with the longer
    wrapper string's prefix."""
    for m in re.finditer(re.escape(b"_Position"), data):
        if law_b_valid(b"_Position", data, m.start()):
            return 1
    return 0



def strip_records_robust(data: bytes) -> int:
    """Verified strip-index records (geometry-payloads note, V5 grammar),
    non-overlapping left-to-right scan.

    ``01 <0x41..0x4f> <0x01..0x0a> ff [u32le n][2n bytes]``; verified =
    1 <= n <= 1e6 and the record fits in the buffer. Signature count —
    not a decode (isolated matches can be binary coincidences).
    """
    count = 0
    i = 0
    n = len(data)
    while i < n - 8:
        if (
            data[i] == 0x01
            and 0x41 <= data[i + 1] <= 0x4F
            and 0x01 <= data[i + 2] <= 0x0A
            and data[i + 3] == 0xFF
        ):
            k = int.from_bytes(data[i + 4 : i + 8], "little")
            if 1 <= k <= 1_000_000 and i + 8 + 2 * k <= n:
                count += 1
                i += 8 + 2 * k
                continue
        i += 1
    return count


def plausible_runs(data: bytes, width: int, min_run: int) -> int:
    """Longest run of plausible IEEE floats at ``width`` bytes; returns
    1 if a run >= min_run exists else 0.

    KNOWN NON-DISCRIMINATING for min_run=8/width=8 on this corpus (the
    string pools unpack as plausible doubles — see the note). Swept
    anyway so the non-rate is committed, per the detector-honesty rule.
    """
    n = len(data) // width * width
    if n < min_run * width:
        return 0
    fmt = {8: "d", 4: "f"}[width]
    vals = struct.unpack_from(f"<{n // width}{fmt}", data, 0)
    best = cur = 0
    for v in vals:
        ok = v == v and abs(v) != float("inf") and (v == 0 or 1e-8 < abs(v) < 1e12)
        cur = cur + 1 if ok else 0
        best = max(best, cur)
    return 1 if best >= min_run else 0


def region_at(blocks: list[tuple[int, str]], off: int) -> str:
    """Region name for byte ``off``: the last block starting at or
    before it, else pre-block (B3 regions own [start, next start))."""
    name = "pre-block"
    for b, nm in blocks:
        if b <= off:
            name = nm
        else:
            break
    return name


def outer_d8(data: bytes) -> int:
    """Outer header dword8 (docs/format/header.md HDR-dword8-lt-size):
    big-endian uint32 at [8:12], the tail region's start (law H1)."""
    return int.from_bytes(data[8:12], "big")


def outer_d12(data: bytes) -> int:
    """Outer header dword12: big-endian uint32 at [12:16]; law H1:
    dword8 + dword12 == file size."""
    return int.from_bytes(data[12:16], "big")


def tail_regions(data: bytes) -> tuple[bool, list[tuple[int, int, str]]]:
    """Walk the file's own tail catalog (decode_tail_region.scan_tail).

    Returns (walk_ok, sorted [(start, end, name)]) — the catalog's named
    regions tile the body [64, dword8) when the walk completes. The tail
    region itself ([dword8, EOF)) is the catalog and is never a region.
    """
    d8 = outer_d8(data)
    if not (64 < d8 < len(data)):
        return False, []
    out = tail_dec.scan_tail(data[d8:], d8)
    if not out.get("walk_ok"):
        return False, []
    spans = []
    for e in out.get("entries", []):
        x, y = e.get("X"), e.get("Y")
        if isinstance(x, int) and isinstance(y, int) and y >= 0:
            spans.append((x, x + y, e.get("name", "")))
    spans.sort()
    return True, spans


def tail_region_at(spans: list[tuple[int, int, str]], off: int) -> str:
    """Tail-catalog region name covering ``off`` ('' outside the tiling)."""
    for lo, hi, nm in spans:
        if lo <= off < hi:
            return nm
    return ""


# --- the census proper -------------------------------------------------------


def load_population() -> list[dict]:
    """Manifest kind=product rows, deterministic order, file presence."""
    rows = []
    with open(MANIFEST, newline="") as fh:
        for r in csv.DictReader(fh):
            if r["kind"] != "product":
                continue
            r["size_bytes"] = int(r["size_bytes"])
            rows.append(r)
    rows.sort(key=lambda r: r["local_path"])
    return rows


def census_one(r: dict) -> dict:
    """All per-file evidence for one manifest row (no IO beyond the read)."""
    path = ROOT / r["local_path"]
    data = path.read_bytes()
    out = {
        "sha16": r["sha256"][:16],
        "split": r["split"],
        "version": r["detected_version"],
        "bucket": bucket(r["detected_version"]),
        "size_bytes": len(data),
        "manifest_size_ok": int(r["size_bytes"]) == len(data),
        "magic_ok": r["magic_ok"],
        "n_blocks": 0,
        "block_names": "",
        "has_catia_block": 0,
        "has_catproduct_block": 0,
        "table_found": 0,
        "table_records": 0,
        "kind_law": "",
        "containers": "",
        "xdoclink_table_row": 0,
        "pool_tokens": 0,
        "pool_flag": 0,
        "instance_name_strings": 0,
        "position_attr": 0,
        "marker_regions": "",
        "refs_total": 0,
        "refs_9f": 0,
        "own_name_refs": 0,
        "child_refs": 0,
        "child_ref_names": "",
        "class": "",
    }
    if len(data) < 64 or b"V5_CFV2" not in data[:64]:
        out["class"] = "non-catia"
        return out

    blocks = store.valid_blocks(data)
    out["n_blocks"] = len(blocks)
    names = sorted({nm for _, nm in blocks})
    out["block_names"] = "|".join(names)
    out["has_catia_block"] = int("CATIA" in names)
    out["has_catproduct_block"] = int("CATProduct" in names)

    d8 = outer_d8(data)
    out["header_h1"] = int(64 < d8 < len(data) and d8 + outer_d12(data) == len(data))
    walk_ok, spans = tail_regions(data)
    out["tail_walk_ok"] = int(walk_ok)
    out["tail_entries"] = len(spans)

    recs = parse_container_table(data[:SCAN_WINDOW])
    if recs:
        out["table_found"] = 1
        out["table_records"] = len(recs)
        out["kind_law"] = detect_kind(recs)
        counts = Counter(rec.name for rec in recs)
        out["containers"] = "|".join(f"{nm}x{c}" for nm, c in sorted(counts.items()))
        out["xdoclink_table_row"] = int(any(rec.name == "CATXDocLinkCont" for rec in recs))

    # structure pool (law B) — token set and instance-shaped strings
    tokens = 0
    for tok in POOL_TOKENS:
        for i in store.find_all(data, tok.encode(), 0, len(data)):
            if law_b_valid(tok.encode(), data, i):
                tokens += 1
                break
    out["pool_tokens"] = tokens
    out["pool_flag"] = int(tokens >= 3)
    seen_inst = set()
    for m in PRINTABLE.finditer(data):
        s = m.group()
        if INSTANCE_SHAPE.match(s.decode("ascii")) and law_b_valid(s, data, m.start()):
            seen_inst.add(s.decode("ascii"))
    out["instance_name_strings"] = len(seen_inst)
    out["position_attr"] = position_attr_present(data)
    if walk_ok and spans:
        # attribution prefers the file's own tail-catalog region names
        # (the catalog tiles [64, dword8)); block-walk regions are the
        # fallback for files whose catalog does not walk.
        regs = {
            tok: sorted(
                {
                    tail_region_at(spans, i) or region_at(blocks, i)
                    for i in store.find_all(data, tok.encode(), 0, min(len(data), d8))
                }
            )
            for tok in REGION_MARKERS
            if tok.encode() in data
        }
    else:
        regs = {
            tok: sorted(
                {
                    region_at(blocks, i)
                    for i in store.find_all(data, tok.encode(), 0, min(len(data), d8))
                }
            )
            for tok in REGION_MARKERS
            if tok.encode() in data
        }
    out["marker_regions"] = "|".join(
        f"{tok}:{'+'.join(rs)}" for tok, rs in sorted(regs.items())
    )

    # document references (law A)
    own = r["path"].rsplit("/", 1)[-1]
    refs = [s for _, s, _ in law_a_strings(data) if DOC_EXT_RE.search(s.encode())]
    out["refs_total"] = len(refs)
    out["refs_9f"] = sum(1 for _, s, t in law_a_strings(data) if DOC_EXT_RE.search(s.encode()) and t)
    children = [s for s in refs if s.rsplit("/", 1)[-1] != own]
    out["own_name_refs"] = len(refs) - len(children)
    out["child_refs"] = len(children)
    out["child_ref_names"] = "|".join(sorted(set(children)))

    flags = []
    if out["pool_flag"]:
        flags.append("pool")
    if out["position_attr"]:
        flags.append("pos")
    if out["child_refs"]:
        flags.append("refs")
    out["class"] = "table-" + ("-".join(flags) if flags else "min") if recs else "catia-notable"
    return out


def run_census(rows: list[dict]) -> list[dict]:
    results = []
    for r in rows:
        try:
            results.append(census_one(r))
        except Exception as exc:  # pragma: no cover — surfaced, never folded
            results.append(
                {
                    "sha16": r["sha256"][:16],
                    "split": r["split"],
                    "version": r["detected_version"],
                    "bucket": bucket(r["detected_version"]),
                    "size_bytes": -1,
                    "manifest_size_ok": False,
                    "magic_ok": r["magic_ok"],
                    "class": f"probe-error:{type(exc).__name__}",
                }
            )
    return results


FILES_FIELDS = [
    "sha16", "split", "version", "bucket", "size_bytes", "manifest_size_ok",
    "magic_ok", "header_h1", "tail_walk_ok", "tail_entries",
    "n_blocks", "block_names", "has_catia_block",
    "has_catproduct_block", "table_found", "table_records", "kind_law",
    "containers", "xdoclink_table_row", "pool_tokens", "pool_flag",
    "instance_name_strings", "position_attr", "marker_regions",
    "refs_total", "refs_9f", "own_name_refs", "child_refs",
    "child_ref_names", "class",
]


def write_files_csv(results: list[dict]) -> None:
    with open(OUT_FILES, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILES_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)


def write_containers_csv(results: list[dict]) -> None:
    with open(OUT_CONTAINERS, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim_id", "sha16", "container_name", "row_count", "bucket"])
        for row in results:
            if not row.get("containers"):
                continue
            for item in row["containers"].split("|"):
                nm, _, c = item.rpartition("x")
                w.writerow(
                    [
                        "container-inventory",
                        row["sha16"],
                        nm,
                        c,
                        row["bucket"],
                    ]
                )


OUT_POOL_TOKENS = ROOT / "docs/evidence/data/p1-census-pool-tokens-claims.csv"


def write_pool_tokens_csv(rows: list[dict]) -> None:
    """Per-token law-B presence over the population (the structure-pool
    vocabulary rates the note cites)."""
    counts = Counter()
    for r in rows:
        data = (ROOT / r["local_path"]).read_bytes()
        for tok in POOL_TOKENS:
            if tok.encode() in data:
                counts[tok] += 1
    with open(OUT_POOL_TOKENS, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["claim_id", "token", "files", "population", "note"])
        for tok in POOL_TOKENS:
            w.writerow([
                "structure-pool-vocabulary",
                tok,
                counts.get(tok, 0),
                len(rows),
                "raw byte presence; the law-B validated per-file count is pool_tokens in the product-files CSV",
            ])


# --- absence sweeps ----------------------------------------------------------


def run_sweeps(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Every absence claim gets an enumerated mechanical sweep: one row
    per (claim, sweep term) over 100% of the population. Returns
    (sweep_rows, cb0001_detail_rows)."""
    out = []
    cb_detail = []
    sweep = Counter()
    occ = Counter()
    buckets_hit: dict[tuple[str, str], set] = {}

    def record(claim: str, term: str, kind: str, hit_files: int, occurrences: int,
               bset: set, verdict: str, note: str) -> None:
        out.append({
            "claim_id": claim, "sweep_term": term, "term_kind": kind,
            "files_hit": hit_files, "population": len(rows),
            "occurrences": occurrences, "file_rate": round(hit_files / len(rows), 4),
            "buckets_hit": "|".join(sorted(bset)) or "-",
            "verdict": verdict, "note": note,
        })

    for r in rows:
        data = (ROOT / r["local_path"]).read_bytes()
        b = bucket(r["detected_version"])
        d8 = outer_d8(data)
        body_end = d8 if 64 < d8 < len(data) else len(data)
        # G1 geometry store — block-name family
        blocks = store.valid_blocks(data)
        bnames = [nm for _, nm in blocks]
        for cont in ("CGMGeom", "CATStdCont", "CATSeeBodyCont",
                     "CATBRepModeContainer", "CATCGRCont", "CATXDocLinkCont"):
            k = (f"G1-blockname-{cont}", b)
            hit = bnames.count(cont)
            if hit:
                sweep[k] += 1
                occ[k] += hit
                buckets_hit.setdefault(k, set()).add(b)
        # G1 — nested store signatures, BODY-scoped ([0, dword8)): the
        # tail region [dword8, EOF) is the file's OWN catalog (law H1,
        # docs/format/tail-catalog.md) and carries CB0001 + UTF-16 region
        # names on every file by format law — whole-file sweeps there
        # would report the format itself, not a product structure.
        v5 = [o for o in store.find_all(data, store.V5_CFV2, 0, body_end) if o > 0]
        cb = [o for o in store.find_all(data, store.CB0001, 0, body_end) if o > 0]
        for label, hits in (("G1-body-V5_CFV2>0", v5), ("G1-body-CB0001>0", cb)):
            if hits:
                k = (label, b)
                sweep[k] += 1
                occ[k] += len(hits)
                buckets_hit.setdefault(k, set()).add(b)
        # shipped store locator on every block, container-independent,
        # regions bounded at the tail-region start (probe_region's
        # d8_outer input — dword8 is 4 bytes BE at [8:12])
        located = 0
        if blocks:
            for blk, _nm in blocks:
                if store.locate_store(data, blk, blocks, d8) is not None:
                    located += 1
        k = ("G1-locate_store-any-block", b)
        if located:
            sweep[k] += 1
            occ[k] += located
            buckets_hit.setdefault(k, set()).add(b)
        # G1 — UTF-16 stream-name tokens, body-scoped, word-precise
        for name in STREAM_NAMES_UTF16:
            hits = utf16_name_hits(data, name, 0, body_end)
            if hits:
                k = (f"G1-utf16-{name.decode('utf-16-le')}", b)
                sweep[k] += 1
                occ[k] += len(hits)
                buckets_hit.setdefault(k, set()).add(b)
        # G1 — CB0001-in-body per-file detail (the sweeps CSV carries the
        # rate; this CSV carries the file-level resolution)
        for o in cb:
            cb_detail.append({
                "sha16": r["sha256"][:16],
                "bucket": b,
                "offset": hex(o),
                "block": region_at(blocks, o),
                "d8": hex(d8),
                "size": len(data),
            })
        # G1 — strip-record grammar (V5), body-scoped
        n = strip_records_robust(data[:body_end])
        if n:
            k = ("G1-strip-records", b)
            sweep[k] += 1
            occ[k] += n
            buckets_hit.setdefault(k, set()).add(b)
        # D1 doc-link container raw bytes (whole file: a container NAME
        # is format vocabulary wherever it appears)
        hits = store.find_all(data, b"CATXDocLinkCont", 0, len(data))
        if hits:
            k = ("D1-bytes-CATXDocLinkCont", b)
            sweep[k] += 1
            occ[k] += len(hits)
            buckets_hit.setdefault(k, set()).add(b)
        # F1 tail-catalog fact (the exclusion this sweep family relies on)
        walk_ok, spans = tail_regions(data)
        if walk_ok:
            k = ("F1-tail-catalog-walks", b)
            sweep[k] += 1
            occ[k] += len(spans)
            buckets_hit.setdefault(k, set()).add(b)
        # X1 raw-array transforms (the non-discriminating sweep, committed)
        if plausible_runs(data, 8, 8):
            k = ("X1-f64run>=8", b)
            sweep[k] += 1
            occ[k] += 1
            buckets_hit.setdefault(k, set()).add(b)
        if plausible_runs(data, 4, 12):
            k = ("X1-f32run>=12", b)
            sweep[k] += 1
            occ[k] += 1
            buckets_hit.setdefault(k, set()).add(b)

    notes = {
        "G1-locate_store-any-block": "shipped nested-store law on every body block (stage-3a/12 extension), regions bounded at dword8; hit = a store span validated",
        "G1-strip-records": "V5 strip-record grammar, verified count, body-scoped (signature, not a decode)",
        "X1-f64run>=8": "NON-DISCRIMINATING on this corpus: string pools unpack as plausible doubles; swept to commit the non-rate",
        "X1-f32run>=12": "NON-DISCRIMINATING, same mechanism as f64",
        "G1-blockname-CGMGeom": "block NAME occurrence; contrast with the name-TABLE rows the container inventory counts",
        "G1-body-CB0001>0": "CB0001 within the body only; the tail region's own CB0001 (every file, law H1) is excluded by the scoping",
        "G1-body-V5_CFV2>0": "V5_CFV2 within the body only; offset 0 is the outer header",
        "F1-tail-catalog-walks": "the file's own tail catalog walks (decode_tail_region.scan_tail); occurrences = region entries",
    }
    agg_files: Counter = Counter()
    agg_occ: Counter = Counter()
    agg_buckets: dict[str, set] = {}
    for (claim, b), files in sweep.items():
        agg_files[claim] += files
        agg_occ[claim] += occ.get((claim, b), 0)
        agg_buckets.setdefault(claim, set()).update(buckets_hit.get((claim, b), set()))
    kind = "sweep"
    # the enumerated term list: every swept term gets a row, absent
    # terms included (files_hit=0) — the sweep's completeness is the
    # row set, not just the hits
    ENUMERATED_TERMS = (
        [f"G1-blockname-{c}" for c in (
            "CGMGeom", "CATStdCont", "CATSeeBodyCont", "CATBRepModeContainer",
            "CATCGRCont", "CATXDocLinkCont")]
        + ["G1-body-V5_CFV2>0", "G1-body-CB0001>0", "G1-locate_store-any-block"]
        + [f"G1-utf16-{n}" for n in (
            "SurfacicReps", "SceneGraph", "MainDataStream", "Describe", "Header", "MAIN")]
        + ["G1-strip-records", "D1-bytes-CATXDocLinkCont",
           "F1-tail-catalog-walks", "X1-f64run>=8", "X1-f32run>=12"]
    )
    for claim in ENUMERATED_TERMS:
        term = claim.split("-", 1)[1] if "-" in claim else claim
        record(
            claim.split("-")[0],
            term,
            kind,
            agg_files.get(claim, 0),
            agg_occ.get(claim, 0),
            agg_buckets.get(claim, set()),
            "present" if agg_files.get(claim) else "absent",
            notes.get(claim, ""),
        )
    # T1: the #24 name-table hierarchy negative, re-measured on products
    t_recs = t_resolving = t_files = t_full = 0
    for r in rows:
        data = (ROOT / r["local_path"]).read_bytes()
        recs = parse_container_table(data[:SCAN_WINDOW])
        if not recs:
            continue
        names1 = {rec.name for rec in recs}
        resolving = sum(1 for rec in recs if rec.parent_name in names1)
        t_recs += len(recs)
        t_resolving += resolving
        t_files += 1
        t_full += resolving == len(recs) and len(recs) > 0
    out.append({
        "claim_id": "T1", "sweep_term": "parent_name-in-name1", "term_kind": "hierarchy",
        "files_hit": t_files, "population": len(rows),
        "occurrences": f"{t_resolving}/{t_recs}",
        "file_rate": round(t_files / len(rows), 4) if t_files else 0,
        "buckets_hit": "-",
        "verdict": "negative" if t_full == 0 else "present",
        "note": f"files resolving FULLY: {t_full} (the #24 negative at product scale; partial record-level resolution is the base-class annotation)",
    })
    return out, cb_detail


SWEEP_FIELDS = ["claim_id", "sweep_term", "term_kind", "files_hit", "population",
                "occurrences", "file_rate", "buckets_hit", "verdict", "note"]

CB_FIELDS = ["sha16", "bucket", "offset", "block", "d8", "size"]

OUT_CB = ROOT / "docs/evidence/data/p1-census-cb0001-body-claims.csv"


def write_sweeps_csv(sweeps: list[dict], cb_detail: list[dict]) -> None:
    with open(OUT_SWEEPS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SWEEP_FIELDS)
        w.writeheader()
        w.writerows(sweeps)
    with open(OUT_CB, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CB_FIELDS)
        w.writeheader()
        w.writerows(cb_detail)


# --- reference resolution ----------------------------------------------------


def run_refs(rows: list[dict]) -> tuple[list[dict], dict]:
    """Resolve product document references to the corpus (basename and
    relative-path tails) and part-number pool strings to same-repo part
    stems. One row per product file with refs or joins. Returns
    (rows, control) — ``control`` carries the cross-repo negative
    control for the stem join (the same sweep against OTHER repos'
    part stems, same files): it quantifies the stem-collision floor the
    same-repo rate must clear (the detector-honesty rule; stem equality
    is not a decoded reference)."""
    by_base: dict[str, set] = {}
    by_path = set()
    part_stems: dict[str, set] = {}
    all_part_stems: set = set()
    with open(MANIFEST, newline="") as fh:
        for r in csv.DictReader(fh):
            by_path.add(r["path"])
            by_base.setdefault(r["path"].rsplit("/", 1)[-1], set()).add(r["kind"])
            repo = r["repo"].split("/", 1)[0]
            if r["kind"] == "part":
                stem = r["path"].rsplit("/", 1)[-1].rsplit(".", 1)[0]
                part_stems.setdefault(repo, set()).add(stem)
                all_part_stems.add(stem)
    out = []
    join_files = control_files = 0
    for r in rows:
        data = (ROOT / r["local_path"]).read_bytes()
        own = r["path"].rsplit("/", 1)[-1]
        repo = r["repo"].split("/", 1)[0]
        refs = [s for _, s, _ in law_a_strings(data) if DOC_EXT_RE.search(s.encode())]
        children = [s for s in refs if s.rsplit("/", 1)[-1] != own]
        res_base = sum(1 for s in children if s.rsplit("/", 1)[-1] in by_base)
        res_path = sum(1 for s in children if s in by_path or any(p.endswith(s) for p in by_path))
        # part-number join: any law-B pool string matching a same-repo part stem
        pool_strings = set()
        for m in PRINTABLE.finditer(data):
            s = m.group()
            if law_b_valid(s, data, m.start()):
                pool_strings.add(s.decode("ascii"))
        join_stems = {
            s.rsplit(".", 1)[0]
            for s in pool_strings
            if s.rsplit(".", 1)[0] in part_stems.get(repo, ())
        }
        control_stems = {
            s.rsplit(".", 1)[0]
            for s in pool_strings
            if s.rsplit(".", 1)[0] in all_part_stems
            and s.rsplit(".", 1)[0] not in part_stems.get(repo, ())
        }
        join_files += bool(join_stems)
        control_files += bool(control_stems)
        if refs or join_stems or control_stems:
            out.append({
                "sha16": r["sha256"][:16],
                "split": r["split"],
                "bucket": bucket(r["detected_version"]),
                "refs_total": len(refs),
                "own_name_refs": len(refs) - len(children),
                "child_refs": len(children),
                "child_resolved_basename": res_base,
                "child_resolved_path": res_path,
                "child_ref_names": "|".join(sorted(set(children))),
                "partnumber_join_stems": "|".join(sorted(join_stems)),
                "cross_repo_collision_stems": "|".join(sorted(control_stems)),
            })
    control = {
        "same_repo_join_files": join_files,
        "cross_repo_collision_files": control_files,
        "population": len(rows),
    }
    return out, control


REFS_FIELDS = ["sha16", "split", "bucket", "refs_total", "own_name_refs",
               "child_refs", "child_resolved_basename", "child_resolved_path",
               "child_ref_names", "partnumber_join_stems",
               "cross_repo_collision_stems"]


def write_refs_csv(refs: list[dict]) -> None:
    with open(OUT_REFS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REFS_FIELDS)
        w.writeheader()
        w.writerows(refs)


# --- ceiling arithmetic ------------------------------------------------------


def run_ceiling(rows: list[dict], results: list[dict], refs: list[dict],
                ref_control: dict | None = None) -> list[dict]:
    """What an assembly bar CAN demand: per-class counts toward assembly
    support, each row joined to the claim family that evidences it."""
    n = len(results)
    refby = {r["sha16"]: r for r in refs}

    def cnt(pred) -> int:
        return sum(1 for x in results if pred(x))

    def files(x: dict) -> str:
        return x["sha16"]

    classes = Counter(x["class"] for x in results)
    pool = [x for x in results if x["pool_flag"]]
    pos = [x for x in results if x["position_attr"]]
    withrefs = [x for x in results if x["child_refs"]]
    resolved = [
        x for x in results
        if refby.get(x["sha16"], {}).get("child_resolved_basename", 0) > 0
        or refby.get(x["sha16"], {}).get("child_resolved_path", 0) > 0
    ]
    joined = [x for x in results if refby.get(x["sha16"], {}).get("partnumber_join_stems")]

    def row(demand: str, count: int, claim: str, note: str) -> dict:
        return {
            "ceiling_id": demand,
            "products": count,
            "population": n,
            "rate": round(count / n, 4),
            "example_sha16": files(results[0]) if results else "",
            "evidence_claim": claim,
            "note": note,
        }

    out = [
        row("population-byte-verified", cnt(lambda x: x["class"] != "non-catia" and x["size_bytes"] >= 0),
            "census-files", "manifest kind=product rows that are byte-level CATIA documents"),
        row("container-table-parsed (kind law K1)", cnt(lambda x: x["kind_law"] == "product"),
            "census-files", "shipped name-table model + kind law, full product population"),
        row("structure-pool (instances declared)", len(pool), "census-files",
            "law-B pool >= 3 tokens: instance records exist to decode (P2)"),
        row("pool + _Position attribute", cnt(lambda x: x["pool_flag"] and x["position_attr"]),
            "census-files", "ceiling for PLACED instances; value encoding undecoded (unknown)"),
        row("pool without _Position (identity-only candidates)",
            cnt(lambda x: x["pool_flag"] and not x["position_attr"]), "census-files",
            "assembly bar can demand identity placement here"),
        row("child document refs (any)", len(withrefs), "census-files",
            "law-A .CATProduct child strings (sub-products; zero .CATPart)"),
        row("child refs resolving to corpus", len(resolved), "reference-resolution",
            "basename or relative-path tail joins a manifest path"),
        row("partnumber -> same-repo part stem join", len(joined), "reference-resolution",
            "law-B pool string equals a same-repo part file stem; stem equality is not a decoded reference"),
        row("partnumber join NEGATIVE CONTROL (cross-repo stems)",
            (ref_control or {}).get("cross_repo_collision_files", 0), "reference-resolution",
            "same sweep against other repos' part stems only — the stem-collision floor the same-repo rate must clear"),
        row("geometry store in the product itself", 0, "absence-sweeps",
            "G1 sweeps at 382 scale: no CGMGeom/CATStdCont/CATSeeBodyCont/"
            "CATCGRCont/BRepMode block, no nested store, no strip records"),
        row("name-table instance hierarchy", 0, "absence-sweeps",
            "T1: the #24 negative re-measured at product scale"),
        row("CATXDocLinkCont container", cnt(lambda x: x["xdoclink_table_row"] or "CATXDocLinkCont" in x["block_names"]),
            "census-files", "name-table rows + block names; the link table is rare in this corpus"),
    ]
    out.append({
        "ceiling_id": "class-distribution",
        "products": len(classes),
        "population": n,
        "rate": 1.0,
        "example_sha16": "",
        "evidence_claim": "census-files",
        "note": "|".join(f"{k}={v}" for k, v in sorted(classes.items())),
    })
    return out


CEILING_FIELDS = ["ceiling_id", "products", "population", "rate",
                  "example_sha16", "evidence_claim", "note"]


def write_ceiling_csv(ceiling: list[dict]) -> None:
    with open(OUT_CEILING, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CEILING_FIELDS)
        w.writeheader()
        w.writerows(ceiling)


# --- selftest ----------------------------------------------------------------


def selftest() -> int:
    """Synthetic positives + negatives for every census-owned detector."""
    failures = []

    def check(name: str, got, want) -> None:
        if got != want:
            failures.append(f"{name}: got {got!r} want {want!r}")

    # law A positive: 34 05 "CATIA" 9f (System_demo_doc worked example shape)
    blob = b"\x00\x00\x00\x00\x34\x05CATIA\x9f\x00rest"
    hits = law_a_strings(blob)
    check("lawA-positive-count", len(hits), 1)
    check("lawA-positive-text", hits[0][1] if hits else None, "CATIA")
    check("lawA-positive-9f", hits[0][2] if hits else None, True)
    # law A negative: length byte too large for the buffer
    check("lawA-negative-overrun", law_a_strings(b"\x34\xffAB"), [])
    # law A negative: non-printable payload
    check("lawA-negative-unprintable", law_a_strings(b"\x34\x03\x01\x02\x03"), [])

    # law B positive: 08 "Part001" — len = chars+1
    pool = b"\x08Part001\x0e_InstanceName\x0aPart001.1\x0a_Position\x07PRDREP"
    check("lawB-Part001", law_b_valid(b"Part001", pool, pool.find(b"Part001")), True)
    check("lawB-_InstanceName", law_b_valid(b"_InstanceName", pool, pool.find(b"_InstanceName")), True)
    check("lawB-Part001.1", law_b_valid(b"Part001.1", pool, pool.find(b"Part001.1")), True)
    # law B negative: the same string with an exact-len prefix must FAIL
    exact = b"\x07Part001\x0d_InstanceName"
    check("lawB-negative-exact-len", law_b_valid(b"Part001", exact, exact.find(b"Part001")), False)
    # the discriminator between laws: law A's exact-len read must NOT
    # validate any pool string (its length byte is off by one)
    law_a_on_pool = [s for _, s, _ in law_a_strings(pool)]
    check("lawA-misreads-pool", law_a_on_pool, [])

    # strip-record grammar: the geometry-payloads note's G1 worked example
    rec = b"\x01\x41\x02\xff" + struct.pack("<I", 6) + bytes.fromhex(
        "00ae" "0037" "0031" "0037" "00ae" "0047"
    )
    check("strip-worked-example", strip_records_robust(rec), 1)
    # negative: n too large (record does not fit)
    check("strip-negative-overflow", strip_records_robust(b"\x01\x41\x02\xff" + struct.pack("<I", 10_000_000)), 0)
    # negative: marker out of range
    check("strip-negative-marker", strip_records_robust(b"\x01\x50\x02\xff" + struct.pack("<I", 2) + b"\x00" * 4), 0)

    # kind law end-to-end on a synthetic container record (worked example
    # layout from docs/format/container-table.md 3.1)
    def synth_record(name1: bytes, name2: bytes, f1: int, idx: int) -> bytes:
        names = name1 + b"\x00" + name2 + b"\x00"
        pad = (-len(names)) % 8
        names += b"\x00" * pad
        rec = struct.pack("<IIIIIIIIII", f1, 11, 0x00030001, idx, 0x006C0001, 2, 0, 0, 0x20810002,
                          (len(name1) + len(name2) + 2 + 7) // 8 + 1)
        rec += names + b"\x03\x00\xf7\x00\x03\x00\x00\x00" + b"\x11" * 16
        return rec

    rec = synth_record(b"CATProdCont", b"CATFeatCont", 16, 1)
    parsed = parse_container_table(rec)
    check("synth-table-count", len(parsed), 1)
    check("synth-kind", detect_kind(parsed), "product")
    check("synth-name", parsed[0].name if parsed else None, "CATProdCont")
    bad = bytearray(rec)
    bad[16] ^= 0xFF  # corrupt f5
    check("synth-negative-corrupt", parse_container_table(bytes(bad)), [])

    # position_attr detector (P1 review F1): a law-B-valid
    # Elec_X_Position wrapper must NOT count as a _Position attribute;
    # a law-B-valid _Position must; a raw substring without a valid
    # prefix must not.
    elec = b"\x10Elec_X_Position"  # len 16 = chars+1 (15 chars)
    check("lawB-elec-wrapper", law_b_valid(b"Elec_X_Position", elec, elec.find(b"Elec_X_Position")), True)
    check("position-attr-negative-embedded", position_attr_present(elec), 0)
    check("position-attr-positive-lawb", position_attr_present(b"\x0a_Position"), 1)
    check("position-attr-negative-raw", position_attr_present(b"junk_Positionjunk"), 0)

    # region attribution
    blocks = [(0x100, "CATIA"), (0x200, "CATProduct")]
    check("region-pre", region_at(blocks, 0x0F), "pre-block")
    check("region-catia", region_at(blocks, 0x1FF), "CATIA")
    check("region-catproduct", region_at(blocks, 0x200), "CATProduct")

    if failures:
        print("SELFTEST FAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("selftest: all detector edges hold")
    return 0


# --- main --------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--census", action="store_true", help="per-file classification CSVs")
    ap.add_argument("--sweeps", action="store_true", help="absence-claim sweep CSV")
    ap.add_argument("--refs", action="store_true", help="reference-resolution CSV")
    ap.add_argument("--ceiling", action="store_true", help="ceiling-arithmetic CSV")
    ap.add_argument("--all", action="store_true", help="run census+sweeps+refs+ceiling")
    ap.add_argument("--selftest", action="store_true", help="detector selftest, no corpus IO")
    ap.add_argument("--sha16", action="append", default=[],
                    help="restrict --census to these sha16 prefixes (repeatable)")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not (args.all or args.census or args.sweeps or args.refs or args.ceiling):
        ap.error("nothing to do: pass --all or a mode")
    rows = load_population()
    missing = [r["local_path"] for r in rows if not (ROOT / r["local_path"]).exists()]
    if missing:
        print(f"ERROR: {len(missing)} manifest files missing on disk, first: {missing[0]}")
        return 2
    results = run_census(rows)
    if args.sha16:
        results = [x for x in results if any(x["sha16"].startswith(p) for p in args.sha16)]
    if args.all or args.census:
        write_files_csv(results)
        write_containers_csv(results)
        write_pool_tokens_csv(rows)
    refs = []
    ref_control = {}
    if args.all or args.refs:
        refs, ref_control = run_refs(rows if not args.sha16 else
                                     [r for r in rows if any(r["sha256"][:16].startswith(p) for p in args.sha16)])
        write_refs_csv(refs)
    sweeps_out = None
    if args.all or args.sweeps:
        sweeps_out, cb_detail = run_sweeps(rows)
        write_sweeps_csv(sweeps_out, cb_detail)
    if args.all or args.ceiling:
        write_ceiling_csv(run_ceiling(rows, results, refs, ref_control))

    # console summary (figures live in the CSVs; this is a run receipt)
    classes = Counter(x["class"] for x in results)
    print(f"population: {len(results)} manifest kind=product rows, all present on disk")
    print("classes:", dict(sorted(classes.items())))
    if sweeps_out is not None:
        present = [s for s in sweeps_out if s["verdict"] == "present"]
        print("sweeps: %d terms swept; terms that HIT: %s" % (
            len(sweeps_out),
            [f"{s['claim_id']}-{s['sweep_term']} ({s['files_hit']} files)" for s in present],
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
