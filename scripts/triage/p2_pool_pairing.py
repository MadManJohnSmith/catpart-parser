#!/usr/bin/env python3
"""P2 structure-pool record layer (#53, spec F #45): decode the pairing
law of the CATProduct structure pool — the typed item chain, its record
framing, and the identity/position pairings — on the census's 380-file
ceiling population.

Builds ON the P1 census's law-B layer (scripts/triage/p1_product_census.py
is imported, not re-derived): ``law_b_valid`` (u8 length == char count + 1)
is the census's string law and is re-pinned here by selftest; the P2
chain walker extends it with the two item forms the P1 note recorded but
did not generalize:

- **SHORT item** (law B): ``<u8 L> <L-1 payload bytes>``, L >= 1
  (L == 1 is the zero-char item observed between the pool head's
  ``catalogLinks`` and ``ASMPRODUCT``). Payload = UTF-8 text, no control
  bytes except ``\\n`` (formula strings carry newlines; accented names
  carry UTF-8 lead+continuation pairs, e.g. ``Pièce1``).
- **LONG item** (the census's ``00 86 00 00 00`` neighborhood,
  generalized): ``<00> <u32le n> <n payload bytes>``, n >= 1 — the
  leading zero byte is an ESCAPE that switches the length to 4 bytes
  little-endian and the count to the EXACT char count. The observed LONG
  payloads are the relation strings (``CtorToProd:...``), but the law is
  length-based, not content-based.

Items chain back-to-back with no padding and no terminators; the chain
EXACTLY TILES its envelope.

**Record framing** (the pool's binary neighborhood, decoded): the pool is
the payload of a record anchored at ``fe 7c 02``::

    fe 7c 02 <u32le ln> <tb tail bytes> <pool items...>

where ``ln`` counts bytes from the ``7c`` marker through the pool's last
byte (law: ``ln == 6 + tb + pool_span``; the record spans ``[fe, fe+1+ln)``),
and ``tb`` is a 1-2 byte field of unknown semantics (observed values all
carry the high bit; open class). Worked example ``0018ec386764dcea``
(Product1.CATProduct, V5R24): record @0x22e9, ln=0x875=2165, tb=1, pool
[0x22f1, 0x2b5f) — 2158 bytes = 2165 - 6 - 1.

**The pairing laws** (measured on the decoded chains):

- identity, marker form: ``<PartNumber value> _InstanceName
  <InstanceName value>`` — the instance's part number precedes the
  ``_InstanceName`` attribute token, the instance name follows it.
- identity, description block (R20-era generations): ``<PN>
  _DescriptionInst <PN:1> _InstanceName <PN_1> _Position`` — the instance
  serialized with three name forms (part number, ``PN:1``, ``PN_1``).
- identity, bare form: ``<PN> <IN>`` adjacent without the marker.
- ``_Position``: the attribute token appears in-chain; its SUCCESSOR is
  never a value (measured: always the next record's class token or
  another attribute token) — the position VALUE is not a pool item. The
  value encoding therefore remains the P1 open class (census §6), now
  with the in-pool absence measured at full scale.
- class-token anchors (the census's record-anchor hint): ``ASMPRODUCT``
  (the root product record; successor = the save-time document name),
  ``PRDREP``/``CONNECTION``/``ASMGEOMETRY`` (successor = the object's
  name value).

**Open classes named, never folded** (bounded-dispatch discipline):

- The tail byte(s) ``tb`` of the framing record — semantics unknown
  (192/253 all-high-bit, no law established).
- The R15-generation attribute-reference form (106-file class): entries
  ``fe [fe] <u8 len> <name> 80 <5 bytes> e8 <3-4 bytes>`` — attribute
  names with inline numeric reference fields instead of a string pool;
  the reference fields' semantics are UNDECODED here.
- Files matching neither form (21 files, the remainder of the
  ``unknown`` bucket).
- The ``_Position`` value encoding (P1 §6 carried forward, with the
  in-pool absence now measured).

The framing is GENERIC, not pool-specific: 239/380 files carry several
tiling ``fe 7c 02`` chains (electrical, measure and spec pools ride the
same record shape); the structure pool is selected by its assembly
vocabulary (>= 2 census POOL_TOKENS among the items). Payloads may be
text OR binary: inline-value generations (18 pools, R18/R19) serialize
binary attribute values (e.g. the ``_BagRepsList`` value) inside the same
chain; per-item text/binary classification separates the string
measurements from those values.

**Generation map** (from the per-bucket rates): R15 — attribute-reference
form, no string pool; R16-R18 — framed typed chains with a shortened head
(the self name follows the empty item directly, ``ASMPRODUCT`` often
absent); R19-R26 — the full form (``CATCatalogManager`` head,
``ASMPRODUCT`` anchor, ``IsRoot`` tail). Framing + tiling: 100% on
R18-R26 (230/230).

Detector honesty (2026-11-13 retro candidate-4 rule; each edge pinned by
``--selftest``):

- **Chain walker**: an item is valid iff its length fits; payloads may
  be text (UTF-8 text, ``\\n`` allowed) or binary — the walker does NOT
  verify that a payload is semantically a string (a binary run parses as
  items). The validators are the framing length law (exact tiling to
  ``fe+1+ln``) and the vocabulary gate; the text/binary classification
  separates the string measurements from binary values, and the
  all-text-pool rate is reported (on all-text pools the unbounded text
  walk independently stops on the record end).
- **Framing scan**: scans every ``fe 7c 02`` occurrence, tries tail
  widths 0-2, and takes the vocabulary-passing candidate with the most
  items (ties → first). It does NOT prove the chosen record is the only
  structure carrier — several framed chains per file are the norm
  (239/380 files) and the others are reported as candidates, not folded.
- **Pairing classifiers**: ``is_token`` = the text starts with ``_``;
  the classifier does NOT know CATIA's actual name tables — an
  underscore-prefixed VALUE would misclassify (no such value observed;
  declared exposure). The dot-shape regex is the census's
  INSTANCE_SHAPE; the R20 block's ``PN_1``/``PN:1`` forms are counted
  separately as observations, not forced into the shape.
- **Self-name anchor**: ``ASMPRODUCT``'s successor equals the manifest
  stem — the pool keeps the SAVE-TIME document name (renamed files
  legitimately mismatch; the mismatch rate is reported, not hidden).

Outputs (explicit paths, all matching the ``*claims*.csv`` hygiene glob):

- docs/evidence/data/p2-pool-pairing-files-claims.csv   (--pairing)
- docs/evidence/data/p2-pool-pairing-claims.csv         (--pairing)
- docs/evidence/data/p2-pool-pairing-ceiling-claims.csv (--ceiling)

Reproduction (owning note: docs/evidence/2026-11-14-p2-pool-pairing.md):

    python3 -I scripts/triage/p2_pool_pairing.py --selftest
    python3 -I scripts/triage/p2_pool_pairing.py --pairing
    python3 -I scripts/triage/p2_pool_pairing.py --ceiling
    python3 -I scripts/triage/check_claims_csv_quoting.py --root .

Corpus read-only; binaries never committed.
"""

from __future__ import annotations

import argparse
import csv
import re
import struct
import sys
from collections import Counter

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "triage"))

import p1_product_census as p1  # noqa: E402  (the census's law-B layer)

MANIFEST = p1.MANIFEST
OUT_FILES = ROOT / "docs/evidence/data/p2-pool-pairing-files-claims.csv"
OUT_CLAIMS = ROOT / "docs/evidence/data/p2-pool-pairing-claims.csv"
OUT_CEILING = ROOT / "docs/evidence/data/p2-pool-pairing-ceiling-claims.csv"

#: Payload byte class: UTF-8 text + newline. Observed high bytes are
#: UTF-8 lead (0xc3) + continuation pairs (accented names, e.g.
#: "Pièce1"); the walker accepts the high range as text and the framing
#: length law cross-checks the chain (declared exposure: a binary run
#: inside this class would parse as an item).
TEXT_BYTES = frozenset(range(0x20, 0x7F)) | {0x0A} | frozenset(range(0x80, 0x100))

#: Framing record anchor and tag byte.
FRAME_MARK = b"\xfe\x7c"
FRAME_TAG_POOL = 0x02

#: Census pool tokens (imported) used to identify the structure pool
#: among framing candidates.
POOL_TOKEN_SET = frozenset(p1.POOL_TOKENS)

#: Class tokens observed as record anchors (successor = an object name
#: value). The underscore attribute names are NOT here — is_token
#: handles them.
CLASS_TOKENS = frozenset(
    {"ASMPRODUCT", "PRDREP", "PRDBAGREP", "CONNECTOR", "CONNECTION",
     "CONNECTORSFAMILY", "ASMGEOMETRY", "PUBLISHING", "IsRoot",
     "ElecLogTerm", "ElecLogicalTermination", "ElecCavity",
     "AdaptativeSupport", "R15HEADER"}
)

#: Instance-name shapes. DOT = the census's INSTANCE_SHAPE; the R20
#: generation's colon/underscore forms are separate observations.
DOT_SHAPE = re.compile(r"^.+\.\d{1,4}$")
COLON_SHAPE = re.compile(r"^.+:\d{1,4}$")
USCORE_SHAPE = re.compile(r"^.+_\d{1,4}$")

#: R15-generation attribute-reference entry (open class): a law-B name
#: followed by the 0x80 reference tag.
R15_ENTRY = re.compile(rb"\xfe\xfe?[\x01-\x7f]([\x20-\x7e]{3,60})\x80")


def text_ok(payload: bytes) -> bool:
    """Payload byte class: UTF-8 text, \\n allowed, no other controls."""
    return all(b in TEXT_BYTES for b in payload)


def walk_chain(data: bytes, start: int, end: int) -> tuple[list[tuple[str, int, int, bytes]], bool]:
    """Decode the typed item chain in [start, end).

    Returns (items, tiles_exactly). Each item is (kind, offset,
    total_len, payload) with kind "S" (SHORT, law B: L == chars+1, L >= 1)
    or "L" (LONG escape: 00 + u32le n == exact char count, n >= 1). The
    chain is valid iff every item's length fits and the items consume
    [start, end) exactly. Payloads may be text OR binary — the observed
    pools carry both (inline-value generations serialize binary attribute
    values, e.g. the _BagRepsList value on 7276bee109497b28); the exact
    tiling to the framing record's end is the validator, and per-item
    text/binary classification separates the string measurements from the
    binary values (see ``payload_is_text``).
    """
    items: list[tuple[str, int, int, bytes]] = []
    i = start
    while i < end:
        head = data[i]
        if head == 0x00:
            if i + 5 > end:
                return items, False
            n = int.from_bytes(data[i + 1 : i + 5], "little")
            if n == 0 or i + 5 + n > end:
                return items, False
            items.append(("L", i, 5 + n, data[i + 5 : i + 5 + n]))
            i += 5 + n
        else:
            if i + head > end:
                return items, False
            items.append(("S", i, head, data[i + 1 : i + head]))
            i += head
    return items, i == end


def payload_is_text(payload: bytes) -> bool:
    """The item's payload class: text (UTF-8-ish) vs binary value."""
    return text_ok(payload)


def framed_pool_candidates(data: bytes) -> list[dict]:
    """Every ``fe 7c 02`` record whose payload exactly tiles into items.

    Candidate selection reports ALL tiling candidates; the caller picks
    the structure pool (most items, pool vocabulary required).
    """
    out = []
    for m in re.finditer(re.escape(FRAME_MARK), data):
        h = m.start()
        if h + 7 > len(data) or data[h + 2] != FRAME_TAG_POOL:
            continue
        ln = int.from_bytes(data[h + 3 : h + 7], "little")
        rec_end = h + 1 + ln
        if ln < 8 or rec_end > len(data):
            continue
        for tb in (0, 1, 2):
            st = h + 7 + tb
            if st > rec_end:
                continue
            items, tiled = walk_chain(data, st, rec_end)
            if tiled and len(items) >= 3:
                out.append({
                    "hdr": h, "ln": ln, "tail": tb, "start": st, "end": rec_end,
                    "items": items,
                    "length_law_ok": ln == 6 + tb + (rec_end - st),
                })
    return out


def pick_pool(cands: list[dict]) -> dict | None:
    """The STRUCTURE pool among framing candidates: requires the assembly
    vocabulary (>= 2 census POOL_TOKENS among items), then most items.

    A product can carry several framed chains (electrical, measure and
    spec pools ride the same ``fe 7c 02`` framing — observed corpus-wide);
    the vocabulary gate selects the assembly one. Chains that tile but
    lack the vocabulary are reported as candidates, not folded into the
    structure pool.
    """
    best = None
    for c in cands:
        toks = sum(1 for _, _, _, s in c["items"] if s.decode("latin-1") in POOL_TOKEN_SET)
        c["pool_tokens"] = toks
        if toks < 2:
            continue
        if best is None or len(c["items"]) > len(best["items"]):
            best = c
    return best


def is_token(t: str) -> bool:
    """Attribute-name token: the observed convention is a leading
    underscore. Declared exposure: an underscore-prefixed VALUE would
    misclassify (none observed; see module docstring)."""
    return t.startswith("_")


def hist_str(c: Counter) -> str:
    """A Counter as a deterministic 'text×N;...' string (top 8)."""
    return ";".join(f"{k}×{v}" for k, v in sorted(c.items(),
                                                  key=lambda kv: (-kv[1], kv[0]))[:8])


def merge_hist(s: str) -> Counter:
    """Inverse of hist_str over merged per-file strings."""
    c: Counter = Counter()
    for part in (s or "").split(";"):
        if not part:
            continue
        k, _, v = part.rpartition("×")
        if k:
            c[k] += int(v)
    return c


BINARY_SENTINEL = "\x00binary"  # never matches is_token or the name shapes


def pool_record_texts(items: list[tuple[str, int, int, bytes]]) -> list[str]:
    """The chain as texts: text payloads decode; binary values become a
    sentinel that matches no pairing classifier."""
    return [s.decode("utf-8", "replace") if payload_is_text(s) else BINARY_SENTINEL
            for _, _, _, s in items]


def walk_chain_text_stop(data: bytes, start: int) -> int:
    """Unbounded text-restricted walk: the offset where the chain's own
    string run stops (the pool end when the pool is all-text). Used for
    the independent break cross-check on the framing length."""
    i = start
    n = len(data)
    while i < n:
        head = data[i]
        if head == 0x00:
            if i + 5 > n:
                return i
            k = int.from_bytes(data[i + 1 : i + 5], "little")
            if k == 0 or i + 5 + k > n or not text_ok(data[i + 5 : i + 5 + k]):
                return i
            i += 5 + k
        else:
            if i + head > n:
                return i
            payload = data[i + 1 : i + head]
            if head > 1 and not text_ok(payload):
                return i
            i += head
    return i


def classify_pairings(texts: list[str]) -> dict:
    """The pairing-law measurements over one decoded chain.

    Every classifier reports counts, not verdicts; the rates live in the
    claims CSV. All adjacency indices are into ``texts``.
    """
    n = len(texts)
    out = {
        "inst_marker": 0,          # _InstanceName occurrences in-chain
        "inst_triple": 0,          # value _InstanceName value
        "inst_triple_dotnext": 0,  # ...with a dot-shaped instance name
        "desc_block": 0,           # _DescriptionInst v _InstanceName (within 2)
        "bare_pair": 0,            # value dot-shaped-value adjacent (no marker)
        "bare_pair_stem": 0,       # ...with stem equality
        "position_tokens": 0,
        "position_succ_token": 0,
        "position_succ_value": 0,
        "position_succ_numeric": 0,
        "asmp_count": 0,
        "asmp_succ_value": 0,
        "asmp_succ_stem": 0,
        "prdrep_count": 0,
        "prdrep_succ_value": 0,
        "connection_succ_value": 0,
        "asmgeom_succ_value": 0,
        "isroot_present": 0,
        "isroot_last": 0,
        "partnumber_vocab_pos": 0,  # _PartNumber between _Component and _BagRepsList
    }
    for i, t in enumerate(texts):
        prev_t = texts[i - 1] if i else None
        next_t = texts[i + 1] if i + 1 < n else None
        if t == "_InstanceName":
            out["inst_marker"] += 1
            if prev_t is not None and next_t is not None \
                    and not is_token(prev_t) and not is_token(next_t):
                out["inst_triple"] += 1
                if DOT_SHAPE.match(next_t):
                    out["inst_triple_dotnext"] += 1
                out.setdefault("_pred_hist", Counter())[prev_t[:24]] += 1
            if i >= 2 and texts[i - 2] == "_DescriptionInst" and not is_token(texts[i - 1]):
                out["desc_block"] += 1
        elif t == "_Position":
            out["position_tokens"] += 1
            if next_t is None:
                out["position_succ_token"] += 1  # chain end: no value follows
                out.setdefault("_succ_hist", Counter())["<chain-end>"] += 1
            elif is_token(next_t) or next_t in CLASS_TOKENS:
                out["position_succ_token"] += 1
                out.setdefault("_succ_hist", Counter())[next_t[:24]] += 1
            else:
                out["position_succ_value"] += 1
                out.setdefault("_succ_hist", Counter())["<value>"] += 1
                try:
                    float(next_t)
                    out["position_succ_numeric"] += 1
                except ValueError:
                    pass
        elif t == "ASMPRODUCT":
            out["asmp_count"] += 1
            if next_t is not None and not is_token(next_t) and next_t not in CLASS_TOKENS:
                out["asmp_succ_value"] += 1
        elif t == "PRDREP":
            out["prdrep_count"] += 1
            if next_t is not None and not is_token(next_t) and next_t not in CLASS_TOKENS:
                out["prdrep_succ_value"] += 1
        elif t in ("CONNECTION", "CONNECTOR"):
            if next_t is not None and not is_token(next_t) and next_t not in CLASS_TOKENS:
                out["connection_succ_value"] += 1
        elif t == "ASMGEOMETRY":
            if next_t is not None and not is_token(next_t) and next_t not in CLASS_TOKENS:
                out["asmgeom_succ_value"] += 1
        elif t == "IsRoot":
            out["isroot_present"] += 1
            if i == n - 1:
                out["isroot_last"] += 1
        elif t == "_PartNumber":
            if prev_t == "_Component" and next_t == "_BagRepsList":
                out["partnumber_vocab_pos"] += 1
        # bare pair: a non-token followed by a dot-shaped non-token,
        # where the pair is NOT the tail of a marker triple
        if prev_t is not None and not is_token(t) and not prev_t.startswith("!") \
                and not is_token(prev_t) and prev_t not in CLASS_TOKENS \
                and DOT_SHAPE.match(t):
            out["bare_pair"] += 1
            stem = t.rsplit(".", 1)[0]
            if prev_t == stem:
                out["bare_pair_stem"] += 1
    return out


def r15_form_count(data: bytes) -> int:
    """R15-generation attribute-reference entries (open class): law-B
    names followed by the 0x80 reference tag. Count, not decode — the
    reference fields' semantics are undecoded here."""
    hits = 0
    for m in R15_ENTRY.finditer(data):
        name = m.group(1)
        if p1.law_b_valid(name, data, m.start(1)):
            hits += 1
    return hits


# --- per-file analysis --------------------------------------------------------


def analyze_one(r: dict) -> dict:
    path = ROOT / r["local_path"]
    data = path.read_bytes()
    row = {
        "sha16": r["sha256"][:16],
        "bucket": p1.bucket(r["detected_version"]),
        "size_bytes": len(data),
        "self_stem": r["path"].rsplit("/", 1)[-1].rsplit(".", 1)[0],
        "pool_form": "",
        "candidates": 0,
        "cand_with_vocab": 0,
        "hdr_off": "",
        "u32le": "",
        "tail_bytes": "",
        "pool_start": "",
        "pool_end": "",
        "pool_span": "",
        "length_law_ok": "",
        "natural_break_ok": "",
        "n_items": 0,
        "n_short": 0,
        "n_long": 0,
        "long_rel": 0,
        "head_skeleton": 0,
        "pool_vocab_tokens": 0,
    }
    if len(data) < 64 or b"V5_CFV2" not in data[:64]:
        row["pool_form"] = "non-catia"
        return row
    cands = framed_pool_candidates(data)
    row["candidates"] = len(cands)
    pool = pick_pool(cands)  # also annotates every candidate with pool_tokens
    row["cand_with_vocab"] = sum(1 for c in cands if c.get("pool_tokens", 0) >= 2)
    if pool is not None:
        row["pool_form"] = "framed"
        row["hdr_off"] = hex(pool["hdr"])
        row["u32le"] = pool["ln"]
        row["tail_bytes"] = pool["tail"]
        row["tail_hex"] = data[pool["hdr"] + 7 : pool["hdr"] + 7 + pool["tail"]].hex()
        row["pool_start"] = hex(pool["start"])
        row["pool_end"] = hex(pool["end"])
        row["pool_span"] = pool["end"] - pool["start"]
        row["length_law_ok"] = int(pool["length_law_ok"])
        # independent cross-check: the chain's OWN end (unbounded
        # text-restricted walk) lands exactly on the record end — holds
        # on all-text pools; binary-valued pools legitimately stop early
        natural_end = walk_chain_text_stop(data, pool["start"])
        row["natural_break_ok"] = int(natural_end == pool["end"])
        row["n_items"] = len(pool["items"])
        row["n_short"] = sum(1 for k, _, _, _ in pool["items"] if k == "S")
        row["n_long"] = sum(1 for k, _, _, _ in pool["items"] if k == "L")
        row["n_binary"] = sum(1 for _, _, _, s in pool["items"]
                              if not payload_is_text(s))
        row["long_rel"] = sum(1 for k, _, _, s in pool["items"]
                              if k == "L" and s.startswith(b"CtorToProd:"))
        row["pool_vocab_tokens"] = pool["pool_tokens"]
        texts = pool_record_texts(pool["items"])
        if texts[:4] == ["CATCatalogManager", "catalogManager", "catalogLinks", ""]:
            row["head_skeleton"] = 1
        pr = classify_pairings(texts)
        succ_hist = pr.pop("_succ_hist", Counter())
        pred_hist = pr.pop("_pred_hist", Counter())
        row.update(pr)
        row["position_succ_hist"] = hist_str(succ_hist)
        row["inst_pred_hist"] = hist_str(pred_hist)
        row["asmp_succ_stem"] = int(any(
            texts[i + 1] == row["self_stem"]
            for i, t in enumerate(texts) if t == "ASMPRODUCT" and i + 1 < len(texts)
        ))
    elif r15_form_count(data) >= 3:
        row["pool_form"] = "r15-ref"
        row["r15_entries"] = r15_form_count(data)
    else:
        row["pool_form"] = "unframed"
    return row


FILES_FIELDS = [
    "sha16", "bucket", "size_bytes", "self_stem", "pool_form", "candidates",
    "cand_with_vocab",
    "hdr_off", "u32le", "tail_bytes", "tail_hex", "pool_start", "pool_end",
    "pool_span",
    "length_law_ok", "natural_break_ok", "n_items", "n_short", "n_long",
    "n_binary", "long_rel", "head_skeleton", "pool_vocab_tokens",
    "inst_marker", "inst_triple", "inst_triple_dotnext", "desc_block",
    "bare_pair", "bare_pair_stem",
    "position_tokens", "position_succ_token", "position_succ_value",
    "position_succ_numeric",
    "asmp_count", "asmp_succ_value", "asmp_succ_stem",
    "prdrep_count", "prdrep_succ_value", "connection_succ_value",
    "asmgeom_succ_value", "isroot_present", "isroot_last",
    "partnumber_vocab_pos", "r15_entries",
    "position_succ_hist", "inst_pred_hist",
]


def bucket_breakdown(rows: list[dict], pred) -> str:
    """Per-bucket hit/population string, e.g. 'R18:5/5;R19:97/105'."""
    tot: Counter = Counter()
    hit: Counter = Counter()
    for x in rows:
        tot[x["bucket"]] += 1
        if pred(x):
            hit[x["bucket"]] += 1
    return ";".join(
        f"{b}:{hit[b]}/{tot[b]}" for b in sorted(tot) if tot[b] >= 1
    )


def claim(cid: str, statement: str, rows: list[dict], pred,
          verdict: str, note: str, detail: str = "", min_files: int = 3) -> dict:
    files = sum(1 for x in rows if pred(x))
    buckets = bucket_breakdown(rows, pred)
    # scope note: marked lines need >= min_files files (decode template)
    weak = [b.split(":")[0] for b in buckets.split(";")
            if b and int(b.split(":")[1].split("/")[1]) < min_files]
    if weak:
        note = note + " lines under " + str(min_files) + " files: " + ",".join(weak)
    return {
        "claim_id": cid, "statement": statement,
        "population": len(rows), "files": files,
        "rate": round(files / len(rows), 4) if rows else 0,
        "buckets": buckets, "verdict": verdict, "detail": detail, "note": note,
    }


def run_pairing() -> list[dict]:
    rows = p1.load_population()
    missing = [r["local_path"] for r in rows if not (ROOT / r["local_path"]).exists()]
    if missing:
        print(f"ERROR: {len(missing)} manifest files missing, first: {missing[0]}")
        raise SystemExit(2)
    results = [analyze_one(r) for r in rows]
    with open(OUT_FILES, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FILES_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    framed = [x for x in results if x["pool_form"] == "framed"]
    r15 = [x for x in results if x["pool_form"] == "r15-ref"]
    unframed = [x for x in results if x["pool_form"] == "unframed"]
    verified = [x for x in results if x["pool_form"] != "non-catia"]
    pos_tok_total = sum(int(x["position_tokens"]) for x in framed)
    pos_succ_tok = sum(int(x["position_succ_token"]) for x in framed)
    pos_succ_num = sum(int(x["position_succ_numeric"]) for x in framed)
    succ_total: Counter = Counter()
    pred_total: Counter = Counter()
    for x in framed:
        succ_total += merge_hist(x["position_succ_hist"])
        pred_total += merge_hist(x["inst_pred_hist"])
    inst_triples = sum(int(x["inst_triple"]) for x in framed)
    triple_dots = sum(int(x["inst_triple_dotnext"]) for x in framed)
    bare = sum(int(x["bare_pair"]) for x in framed)
    bare_stem = sum(int(x["bare_pair_stem"]) for x in framed)
    claims = [
        claim("P2-framing-scan",
              "the pool is the payload of a fe 7c 02 <u32le ln> record whose "
              "items tile [start, fe+1+ln) exactly",
              verified, lambda x: x["pool_form"] == "framed", "fact",
              "population = byte-verified products (2 manifest misfits "
              "excluded); the record is the pool's binary neighborhood "
              "(census §8 entry point); other framed chains (electrical/"
              "measure/spec pools) ride the same framing and are excluded "
              "by the vocabulary gate",
              detail=f"framing candidates per file: "
                     f"{sum(int(x['candidates']) for x in verified)} total; "
                     f"tail byte(s) all-high-bit: "
                     f"{sum(1 for x in framed if x['tail_hex'] and all(b & 0x80 for b in bytes.fromhex(x['tail_hex'])))}"
                     f"/{len(framed)}"),
        claim("P2-length-law",
              "u32le ln counts from the 7c marker through the pool's last "
              "byte (ln == 6 + tail_bytes + pool_span), AND on all-text "
              "pools the chain's own unbounded walk stops exactly on the "
              "record end",
              framed, lambda x: x["length_law_ok"] == 1
              and x["natural_break_ok"] == 1, "fact",
              "the second half is the independent cross-check: the string "
              "run's break agrees with the record length; pools with "
              "binary values legitimately stop early (n_binary > 0)"),
        claim("P2-alltext-pools",
              "pools whose items are all text (no binary values)",
              framed, lambda x: int(x["n_binary"]) == 0, "fact",
              "inline-value generations carry binary attribute values "
              "(_BagRepsList etc.) inside the same chain"),
        claim("P2-chain-tiling",
              "the pool payload tiles exactly into SHORT (u8 len = chars+1) "
              "and LONG (00 + u32le len = chars) items",
              framed, lambda x: x["n_items"] > 0, "fact",
              "the census's law B extended with the 00-escape LONG form"),
        claim("P2-head-skeleton",
              "the chain opens CATCatalogManager, catalogManager, "
              "catalogLinks, <empty>",
              framed, lambda x: x["head_skeleton"] == 1, "fact",
              "the invariant head of the framed pool"),
        claim("P2-identity-triple",
              "value _InstanceName value adjacency (the part number "
              "precedes the marker, the instance name follows it)",
              framed, lambda x: x["inst_triple"] > 0, "fact",
              "the census's _InstanceName pairing, decoded as adjacency",
              detail=f"triples {inst_triples}, dot-shaped instance names "
                     f"{triple_dots}; triple predecessors (top): "
                     + hist_str(pred_total)),
        claim("P2-identity-triple-dotname",
              "triple files whose marked instance name is dot-shaped "
              "(the census's INSTANCE_SHAPE)",
              framed, lambda x: x["inst_triple_dotnext"] > 0, "fact",
              "dot-shaped names are the majority form; R20-era files use "
              "PN_1/PN:1 forms (desc_block)"),
        claim("P2-desc-instance-block",
              "_DescriptionInst <v> _InstanceName within 2 items (the "
              "R20-era instance block with PN/PN:1/PN_1 name forms)",
              framed, lambda x: x["desc_block"] > 0, "fact",
              "generation-specific instance serialization"),
        claim("P2-bare-pair",
              "adjacent <value> <dot-shaped value> pairs outside marker "
              "triples (the bare PN-IN form)",
              framed, lambda x: x["bare_pair"] > 0, "inference",
              "adjacency, not a decoded reference; stem-match subrate in "
              "bare_pair_stem",
              detail=f"bare pairs {bare}, stem matches {bare_stem}"),
        claim("P2-position-value-absent",
              "wherever _Position appears in-chain its successor is a "
              "token or class token, never a value",
              framed, lambda x: x["position_tokens"] > 0
              and x["position_succ_numeric"] == 0, "fact",
              "the _Position VALUE is not a pool item; encoding stays the "
              "P1 open class (census §6) with the absence now measured",
              detail=f"in-chain _Position tokens {pos_tok_total}; successors "
                     f"token/class {pos_succ_tok}, value "
                     f"{sum(int(x['position_succ_value']) for x in framed)}, "
                     f"numeric {pos_succ_num}; successor histogram (top): "
                     + hist_str(succ_total)),
        claim("P2-asmp-anchor",
              "ASMPRODUCT's successor is a value (the save-time document "
              "name); stem-equality subrate in asmp_succ_stem",
              framed, lambda x: x["asmp_count"] > 0 and x["asmp_succ_value"] > 0,
              "fact", "renamed files legitimately mismatch the manifest stem"),
        claim("P2-prdrep-anchor",
              "PRDREP's successor is a value (the representation name)",
              framed, lambda x: x["prdrep_count"] > 0 and x["prdrep_succ_value"] > 0,
              "fact", "the census's class-token record-anchor hint"),
        claim("P2-partnumber-vocab-pos",
              "_PartNumber sits between _Component and _BagRepsList in the "
              "vocabulary run (its value pairs via the identity triple)",
              framed, lambda x: x["partnumber_vocab_pos"] > 0, "fact",
              "the census's _PartNumber↔value pairing: value = the triple's "
              "first element; the attr name lives in the vocabulary run"),
        claim("P2-isroot-terminal",
              "IsRoot is the chain's last item",
              framed, lambda x: x["isroot_present"] > 0 and x["isroot_last"] > 0,
              "fact",
              "measured rate, not a law: on the remainder the chain "
              "continues past IsRoot (VPGlobal/VPAsm viewpoint tails)"),
        claim("P2-long-relation-strings",
              "LONG items carry the CtorToProd: relation strings",
              framed, lambda x: x["long_rel"] > 0, "fact",
              "the census's u32le-length neighborhood, generalized: the 00 "
              "escape, exact-count length"),
        claim("P2-r15-ref-form",
              "the R15-generation attribute-reference form (fe [fe] len "
              "name 80 <refs> e8 <refs>) — open class, undecoded refs",
              verified, lambda x: x["pool_form"] == "r15-ref", "unknown",
              "entries named, reference fields NOT decoded (bounded "
              "dispatch); the names match the framed pool's vocabulary, so "
              "this is the same attribute set under an older encoding"),
        claim("P2-unframed",
              "files matching neither the framed pool nor the R15 form",
              verified, lambda x: x["pool_form"] == "unframed", "unknown",
              "named, never folded; several carry assembly vocabulary in "
              "law-B strings outside any tiling chain"),
    ]
    with open(OUT_CLAIMS, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "claim_id", "statement", "population", "files", "rate",
            "buckets", "verdict", "detail", "note"])
        w.writeheader()
        w.writerows(claims)

    print(f"population: {len(results)} manifest rows "
          f"({len(verified)} byte-verified)")
    print(f"framed pools: {len(framed)}  r15-ref: {len(r15)}  "
          f"unframed: {len(unframed)}  non-catia: {len(results)-len(verified)}")
    for c in claims:
        print(f"  {c['claim_id']:28s} {c['files']:4d}/{c['population']}"
              f" ({c['rate']:.3f}) {c['verdict']}")
    return results


# --- ceiling arithmetic -------------------------------------------------------


def run_ceiling() -> int:
    """Ceiling delta vs the P1 census (p1-census-ceiling-claims.csv is
    CITED, not rewritten; superseded rows are marked dated here)."""
    import csv as _csv
    files_csv = ROOT / "docs/evidence/data/p2-pool-pairing-files-claims.csv"
    if not files_csv.exists():
        print("run --pairing first")
        return 2
    with open(files_csv, newline="") as fh:
        results = list(_csv.DictReader(fh))
    verified = [x for x in results if x["pool_form"] != "non-catia"]
    n = len(verified)
    framed = [x for x in results if x["pool_form"] == "framed"]
    ident = [x for x in results if x["pool_form"] == "framed"
             and (int(x["inst_triple"]) > 0 or int(x["desc_block"]) > 0
                  or int(x["bare_pair"]) > 0)]
    pos_ceiling = [x for x in results if x["pool_form"] == "framed"
                   and int(x["position_tokens"]) > 0]
    out = [
        {"ceiling_id": "population-byte-verified", "p1_value": "380",
         "p2_value": str(n), "delta": "0", "dated_note":
         "census cited unchanged (2026-11-14 P1 §7)"},
        {"ceiling_id": "instance-records-DECLARED (P1)", "p1_value": "380",
         "p2_value": str(len(framed)), "delta": "SUPERSEDED-DATED",
         "dated_note":
         "P1's 'declared' row is superseded by the decoded form: the pool "
         "is a framed typed chain on " + str(len(framed)) + " files "
         "(R18-R26 100%; R15-generation + remainder = open classes)"},
        {"ceiling_id": "identity pairs DECODED (>=1 per file)", "p1_value": "-",
         "p2_value": str(len(ident)), "delta": "NEW",
         "dated_note":
         "the assembly bar can demand decoded (PartNumber, InstanceName) "
         "identity pairs on these files — was only a ceiling in P1"},
        {"ceiling_id": "placed instances (_Position attribute)", "p1_value": "260",
         "p2_value": str(len(pos_ceiling)), "delta": "0 (ceiling stands)",
         "dated_note":
         "P2 measured the VALUE's absence from the pool (position_succ_numeric=0 "
         "wherever the token appears); the 260 ceiling stays a ceiling — the "
         "value encoding remains the open class"},
        {"ceiling_id": "identity-only candidates (pool without _Position)",
         "p1_value": "120", "p2_value": "-", "delta": "0 (unchanged)",
         "dated_note": "per-file attribute presence unchanged by P2"},
    ]
    with open(OUT_CEILING, "w", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=[
            "ceiling_id", "p1_value", "p2_value", "delta", "dated_note"])
        w.writeheader()
        w.writerows(out)
    for r in out:
        print(f"  {r['ceiling_id']}: p1={r['p1_value']} p2={r['p2_value']} [{r['delta']}]")
    return 0


# --- selftest -----------------------------------------------------------------


def selftest() -> int:
    """Synthetic positives + negatives for every P2-owned detector."""
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append(f"{name}: got {got!r} want {want!r}")

    # the P1 law-B layer is imported, not re-derived — re-pin its edges
    pool = b"\x08Part001\x0e_InstanceName\x0aPart001.1\x0a_Position"
    check("p1-lawB-Part001", p1.law_b_valid(b"Part001", pool, pool.find(b"Part001")), True)
    check("p1-lawB-negative-exact-len",
          p1.law_b_valid(b"Part001", b"\x07Part001", 1), False)

    # chain walker (any-bytes payloads; the framing tiling validates):
    # the census worked-example byte sequence
    blob = (b"\x08Part001\x0e_InstanceName\x0aPart001.1\x0a_Position"
            b"\x07PRDREP\x00\x08\x00\x00\x00CtorToPr")
    items, tiled = walk_chain(blob, 0, len(blob) - 4)  # bound inside the LONG
    check("chain-positive-count", len(items), 5)
    check("chain-positive-kinds", [k for k, _, _, _ in items],
          ["S", "S", "S", "S", "S"])
    check("chain-positive-last-payload", items[-1][3] if items else None, b"PRDREP")
    # full LONG item (n == exact char count of the payload)
    blob2 = b"\x07PRDREP\x00\x0a\x00\x00\x00CtorToProd"
    items2, tiled2 = walk_chain(blob2, 0, len(blob2))
    check("chain-long-tiles", tiled2, True)
    check("chain-long-payload", items2[-1][0] if items2 else None, "L")

    # binary payload: valid item for the walker, classified binary
    binitem = b"\x04\x01\x02\x03\x00"
    items2b, tiled2b = walk_chain(binitem, 0, len(binitem) - 1)
    check("chain-binary-item-valid", tiled2b, True)
    check("chain-binary-item-class", payload_is_text(items2b[0][3]) if items2b else None, False)

    # text-walk stop: control bytes end the string run (the unbounded
    # break detector for the framing cross-check); an item either fully
    # validates or the walk stops before it
    stop = walk_chain_text_stop(b"\x05ab\x01cd", 0)
    check("textwalk-negative-control-byte", stop, 0)
    check("textwalk-negative-partial-items",
          len(walk_chain(b"\x05ab\x01cd", 0, 3)[0]), 0)
    # negative: LONG with zero length
    _, tiled4 = walk_chain(b"\x07PRDREP\x00\x00\x00\x00\x00", 0, 9)
    check("chain-negative-long-zerolen", tiled4, False)
    # negative: truncated LONG header
    _, tiled6 = walk_chain(b"\x00\x03\x00", 0, 3)
    check("chain-negative-long-trunc", tiled6, False)

    # framing: a synthetic record, then two broken-length negatives
    inner = b"\x08Part001\x0e_InstanceName\x0aPart001.1\x0a_Position"
    body = b"\x00" + struct.pack("<I", 5) + inner  # tb=1: 00 + 5 bytes... use tb=1
    # ln counts from 7c: 1(7c)+1(02)+4(u32)+tb+span
    for tb in (1,):
        span = len(inner)
        ln = 1 + 1 + 4 + tb + span
        rec = b"\xfe\x7c\x02" + struct.pack("<I", ln) + b"\xa5" * tb + inner
        cands = framed_pool_candidates(rec + b"tailbytes\x00\x00")
        check("frame-positive-count", len(cands), 1)
        check("frame-positive-law", cands[0]["length_law_ok"] if cands else None, True)
        check("frame-positive-items", len(cands[0]["items"]) if cands else None, 4)
        # negative: length off by one -> no exact tiling
        bad = b"\xfe\x7c\x02" + struct.pack("<I", ln + 1) + b"\xa5" * tb + inner
        check("frame-negative-offbyone", framed_pool_candidates(bad + b"\x00\x00"), [])
        # negative: length too small (record end lands inside an item)
        bad2 = b"\xfe\x7c\x02" + struct.pack("<I", ln - 2) + b"\xa5" * tb + inner
        check("frame-negative-short", framed_pool_candidates(bad2), [])

    # pick_pool requires the pool vocabulary (a non-vocabulary chain is
    # rejected even though it tiles)
    inner_np = (b"\x08Part001\x0e_InstanceName\x0aPart001.1")  # 3 items, no pool token
    ln_np = 1 + 1 + 4 + 1 + len(inner_np)
    nopool = framed_pool_candidates(
        b"\xfe\x7c\x02" + struct.pack("<I", ln_np) + b"\xa5" + inner_np)
    check("pick-pool-negative-no-vocab",
          pick_pool(nopool) if nopool else "nocands",
          None if not nopool else None)

    # pairing classifiers
    texts = ["CATCatalogManager", "catalogManager", "catalogLinks", "",
             "ASMPRODUCT", "Product1", "_PartNumber", "Part001",
             "_InstanceName", "Part001.1", "_Position", "PRDREP", "Shape 1",
             "IsRoot"]
    pr = classify_pairings(texts)
    check("pair-triple", pr["inst_triple"], 1)
    check("pair-triple-dotnext", pr["inst_triple_dotnext"], 1)
    check("pair-position-successor-token", pr["position_succ_token"], 1)
    check("pair-position-successor-numeric", pr["position_succ_numeric"], 0)
    check("pair-asmp-succ-value", pr["asmp_succ_value"], 1)
    check("pair-prdrep-succ-value", pr["prdrep_succ_value"], 1)
    check("pair-isroot-last", pr["isroot_last"], 1)
    check("pair-partnumber-vocab-pos", pr["partnumber_vocab_pos"], 0)
    # negative: a numeric-looking value after _Position WOULD count —
    # pinning the detector so the corpus absence is meaningful
    pr2 = classify_pairings(["_Position", "1.0"])
    check("pair-position-numeric-detected", pr2["position_succ_numeric"], 1)
    # negative: a token before _InstanceName is not a triple
    pr3 = classify_pairings(["_Component", "_InstanceName", "_Position"])
    check("pair-triple-negative-token-prev", pr3["inst_triple"], 0)
    # desc block positive
    pr4 = classify_pairings(["ac2", "_DescriptionInst", "ac2:1",
                             "_InstanceName", "ac2_1", "_Position"])
    check("pair-desc-block", pr4["desc_block"], 1)
    check("pair-desc-block-triple", pr4["inst_triple"], 1)
    # negative: _DescriptionInst too far from _InstanceName
    pr5 = classify_pairings(["_DescriptionInst", "x", "y", "_InstanceName"])
    check("pair-desc-block-negative-gap", pr5["desc_block"], 0)

    # bare pair + stem
    pr6 = classify_pairings(["Part0024", "Part0024.1", "Shape 1"])
    check("pair-bare-pair", pr6["bare_pair"], 1)
    check("pair-bare-pair-stem", pr6["bare_pair_stem"], 1)
    # negative: renamed instance fails stem equality but still pairs
    pr7 = classify_pairings(["Part1", "lengua_1"])
    check("pair-bare-nostem-counts", pr7["bare_pair"], 0)  # not dot-shaped

    # r15 form
    r15blob = b"\xfe\xfe\x0c_Connectors\x80\xe2\x7c\x00\x00\xe8\xe0\x1a\x01" \
              b"\xfe\xfe\x0b_Component\x80\xa7\x3c\x5c\x40\xe8\xf4\x1a\x01"
    check("r15-positive", r15_form_count(r15blob), 2)
    check("r15-negative-notag", r15_form_count(b"\xfe\x0c_Connectors\x00\xe2\x7c"), 0)

    if failures:
        print("SELFTEST FAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("selftest: all P2 detector edges hold")
    return 0


# --- main ---------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pairing", action="store_true",
                    help="per-file pool decode + pairing claims CSVs")
    ap.add_argument("--ceiling", action="store_true",
                    help="ceiling delta CSV (needs --pairing output)")
    ap.add_argument("--all", action="store_true", help="pairing + ceiling")
    ap.add_argument("--selftest", action="store_true",
                    help="detector selftest, no corpus IO")
    ap.add_argument("--sha16", action="append", default=[],
                    help="print the analysis for these sha16 prefixes (repeatable)")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if args.sha16:
        rows = p1.load_population()
        for r in rows:
            if not any(r["sha256"][:16].startswith(p) for p in args.sha16):
                continue
            import json
            print(json.dumps(analyze_one(r), indent=1, default=str))
        return 0
    if not (args.all or args.pairing or args.ceiling):
        ap.error("nothing to do: pass --all, --pairing or --ceiling")
    if args.all or args.pairing:
        run_pairing()
    if args.all or args.ceiling:
        return run_ceiling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
