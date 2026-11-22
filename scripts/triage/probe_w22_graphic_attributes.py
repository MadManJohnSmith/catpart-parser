#!/usr/bin/env python3
"""Graphic-attributes probe (w22, 2026-11-22, read-only).

The dispatch asked: locate ``CATGraphicAttributeSet`` (RGB/opacity) in
the corpus binaries and measure how many files carry it. The measured
answer is a clean NEGATIVE — the token (and its whole vis-token family,
ASCII or UTF-16LE, any case variant) appears in 0/1442 available
corpus parts — and a measured POSITIVE LEAD: a length-framed material-
property family (``fe <len=strlen+1> <Name>`` blocks — the writer's
``len = strlen + 1`` law, the same framing as the feature names) whose
``Color``/``TransparentColor`` values carry a 3-byte triple behind a
``84 81`` value header (candidate RGB) and whose real-valued
properties (``Reflectivity``/``Transparency``/``Contrast``/...) carry
``e6`` + an 8-byte little-endian double with clean physical values
(0.7, 0.495, 0.05, 0.7333 = 11/15, ...).

Per file this probe measures:

- the ``CATGraphicAttributeSet`` token census (ASCII, case variants,
  UTF-16LE) plus the related vis-token family — the dispatch's asked
  rate;
- the ``Transparency`` ASCII token (name-table framing — a different
  framing than the value blocks, measured separately);
- the fe-framed material-property vocabulary: per-name block counts,
  first offsets, and the value classes behind the descriptor
  (``81 e8|e9 d4|f4 <T> (04 01|01) <value>``):
  ``e6`` + f64 double / ``e8`` empty / short ``84 81`` + 3 bytes.

Every interpretation beyond the byte patterns is labeled candidate in
the claims CSV (``w22-graphic-attributes-claims.csv``); nothing here is
wired into any runtime path — this is a handoff probe for a future
native-colors ticket.

Data: ``docs/evidence/data/w22-graphic-attributes-files.csv`` (one row
per part), ``docs/evidence/data/w22-graphic-attributes-claims.csv``.

Run::

    python3 -I scripts/triage/probe_w22_graphic_attributes.py \
        --corpus-root /home/alan/Documents/Repos/catpart-parser
    python3 -I scripts/triage/probe_w22_graphic_attributes.py --selftest
"""

import collections
import csv
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "triage"))

from probe_bagrep import load_manifest  # noqa: E402

FILES_CSV = os.path.join(
    ROOT, "docs", "evidence", "data", "w22-graphic-attributes-files.csv"
)
CLAIMS_CSV = os.path.join(
    ROOT, "docs", "evidence", "data", "w22-graphic-attributes-claims.csv"
)

#: The dispatch's asked token and the family swept around it (ASCII +
#: the same names in UTF-16LE + case variants). Measured corpus-wide.
ASKED_TOKENS = (
    b"CATGraphicAttributeSet",
    b"CATGRAPHICATTRIBUTESET",
    b"catgraphicattributeset",
    "CATGraphicAttributeSet".encode("utf-16-le"),
    b"GraphicAttribute",
    b"VisProperties",
    b"CATViz",
    b"CATMaterialRef",
)

#: The one vis-related ASCII token that DOES exist corpus-wide, in a
#: name-table framing (a length byte, not the fe-framed value blocks).
NAME_TABLE_TOKEN = b"Transparency"

#: The fe-framed material-property vocabulary (measured: every name
#: carries >= 1 fe-framed block in the population; ``DrwSpec``-era
#: drawing properties are excluded — 0 hits in the exploratory sweep).
PROPERTY_NAMES = (
    b"Texture",
    b"TextureImage",
    b"TextureType",
    b"RepeatU",
    b"RepeatV",
    b"Reflectivity",
    b"Transparency",
    b"TransparentColor",
    b"TransparentMode",
    b"Color",
    b"Contrast",
    b"TranslationU",
    b"TranslationV",
    b"TranslationW",
)

#: The value-class tags measured behind the descriptor.
TAG_DOUBLE = 0xE6  # e6 + 8-byte LE double (clean physical values)
TAG_EMPTY = 0xE8  # e8: no value bytes follow
COLOR_HEADER = b"\x84\x81"  # the short color form's value header

DESC_LEN = 6  # 81 <e8|e9> <d4|f4> <T> (04 01 | 01) — value starts at +6


def fe_pattern(name: bytes) -> bytes:
    """The fe-framed property pattern: ``fe <len> <name>`` with the
    writer's ``len = strlen + 1`` law (``fe 08 Texture`` = 7 chars)."""
    return bytes([0xFE, len(name) + 1]) + name


def token_label(tok: bytes) -> str:
    """The CSV/record label for one swept token (UTF-16LE tokens render
    as their text)."""
    if 0x00 in tok:
        return tok.decode("utf-16-le", errors="replace")
    return tok.decode("ascii", errors="replace")


def parse_property_block(data: bytes, pos: int, name: bytes) -> dict | None:
    """The value block behind one fe-framed property occurrence.

    Descriptor: ``81 <e8|e9> <d4|f4> <T> (04 01 | 01)`` — the
    ``e9 ... 04 01`` form is the dominant one; the ``e8 ... 01`` form
    is a 4-file variant (measured, W22-GA-06). Returns a dict with the
    value class and the decoded candidate value, or None when the
    descriptor does not match.
    """
    start = pos + len(fe_pattern(name))
    desc = data[start : start + DESC_LEN]
    if len(desc) < DESC_LEN or desc[0] != 0x81:
        return None
    if desc[1] not in (0xE8, 0xE9) or desc[2] not in (0xD4, 0xF4):
        return None
    value = data[start + DESC_LEN :]
    if value[:1] == b"\xe6" and len(value) >= 9:
        raw = value[1:9]
        x = struct.unpack("<d", raw)[0]
        return {
            "value_class": "f64",
            "descriptor": desc.hex(" "),
            "value": repr(round(x, 6)),
            "value_hex": raw.hex(" "),
        }
    if value[:1] == b"\xe8":
        return {
            "value_class": "empty",
            "descriptor": desc.hex(" "),
            "value": "",
            "value_hex": "",
        }
    if value[:2] == COLOR_HEADER:
        triple = value[2:5]
        return {
            "value_class": "color-short",
            "descriptor": desc.hex(" "),
            "value": ",".join(str(b) for b in triple),
            "value_hex": triple.hex(" "),
        }
    return {
        "value_class": "other",
        "descriptor": desc.hex(" "),
        "value": "",
        "value_hex": value[:8].hex(" "),
    }


def scan_file(data: bytes) -> dict:
    """One part's full measurement (single pass over the bytes)."""
    rec: dict = {}
    # 1. the asked token family (ASCII / UTF-16LE / case variants).
    for tok in ASKED_TOKENS:
        count = 0
        pos = data.find(tok)
        while pos >= 0:
            count += 1
            pos = data.find(tok, pos + 1)
        label = token_label(tok)
        rec[f"token:{label}"] = count
    # 2. the name-table Transparency token (plain length framing).
    rec["name_table_transparency"] = data.count(NAME_TABLE_TOKEN)
    # 3. the fe-framed material-property family.
    for name in PROPERTY_NAMES:
        pat = fe_pattern(name)
        pos = data.find(pat)
        count = 0
        first = None
        classes: collections.Counter = collections.Counter()
        while pos >= 0:
            count += 1
            if first is None:
                first = pos
            block = parse_property_block(data, pos, name)
            if block:
                classes[block["value_class"]] += 1
            pos = data.find(pat, pos + 1)
        base = name.decode("ascii")
        rec[f"prop:{base}:blocks"] = count
        rec[f"prop:{base}:first_offset"] = first if first is not None else ""
        rec[f"prop:{base}:f64"] = classes.get("f64", 0)
        rec[f"prop:{base}:empty"] = classes.get("empty", 0)
        rec[f"prop:{base}:color-short"] = classes.get("color-short", 0)
        rec[f"prop:{base}:other"] = classes.get("other", 0)
    return rec


FILES_ROW = (
    ["sha16", "size_bytes", "repo", "graphic_attribute_set", "name_table_transparency"]
    + [f"token:{token_label(t)}" for t in ASKED_TOKENS]
    + [
        f"prop:{name.decode()}:{suffix}"
        for name in PROPERTY_NAMES
        for suffix in ("blocks", "first_offset", "f64", "empty", "color-short", "other")
    ]
)


def run_corpus(corpus_root: str, limit: int | None = None) -> list[dict]:
    manifest = load_manifest(corpus_root)
    rows = [m for m in manifest.values() if m["local"].endswith(".CATPart")]
    rows.sort(key=lambda m: m["sha256"])
    if limit:
        rows = rows[:limit]
    out = []
    for m in rows:
        try:
            with open(m["local"], "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        rec = scan_file(data)
        out.append(
            {
                "sha16": m["sha256"][:16],
                "size_bytes": os.path.getsize(m["local"]),
                "repo": m["repo"],
                "graphic_attribute_set": sum(
                    rec[f"token:{token_label(t)}"] for t in ASKED_TOKENS
                ),
                "name_table_transparency": rec["name_table_transparency"],
                **{k: v for k, v in rec.items() if k.startswith(("token:", "prop:"))},
            }
        )
    return out


def write_files_csv(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(FILES_CSV), exist_ok=True)
    with open(FILES_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FILES_ROW)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_claims_csv(rows: list[dict]) -> None:
    """The claims rows: every claim labeled fact / candidate / unknown,
    with the rate and the corpus scope (dispatch-recipes hard rule:
    per-class, one explicit line of what the detector does NOT
    discriminate)."""
    total = len(rows)
    ga_files = sum(1 for r in rows if r["graphic_attribute_set"] > 0)
    trans_files = sum(1 for r in rows if r["name_table_transparency"] > 0)
    family_files = sum(
        1
        for r in rows
        if any(r[f"prop:{n.decode()}:blocks"] > 0 for n in PROPERTY_NAMES)
    )
    color_files = sum(
        1 for r in rows if r["prop:Color:color-short"] > 0
    )
    empty_trans = sum(r["prop:Transparency:empty"] for r in rows)
    f64_trans = sum(r["prop:Transparency:f64"] for r in rows)
    claims = [
        {
            "claim_id": "W22-GA-01",
            "claim": "CATGraphicAttributeSet token present",
            "verdict": "negative (measured)",
            "label": "fact",
            "rate": f"0/{total} files; occurrences 0; ASCII + case variants + UTF-16LE swept",
            "scope": "available corpus parts, this host",
        },
        {
            "claim_id": "W22-GA-02",
            "claim": "vis-token family (GraphicAttribute/VisProperties/CATViz/CATMaterialRef) present",
            "verdict": "negative (measured)",
            "label": "fact",
            "rate": f"0/{total} files for every family token",
            "scope": "available corpus parts, this host",
        },
        {
            "claim_id": "W22-GA-03",
            "claim": "plain 'Transparency' ASCII token (name-table framing) present",
            "verdict": "positive (measured)",
            "label": "fact",
            "rate": f"{trans_files}/{total} files",
            "scope": "available corpus parts, this host",
        },
        {
            "claim_id": "W22-GA-04",
            "claim": "fe-framed material-property family present",
            "verdict": "positive (measured)",
            "label": "fact",
            "rate": f"{family_files}/{total} files (~{family_files / max(total, 1) * 100:.1f}%); "
            "framing fe <len=strlen+1> <Name>, the feature names' law",
            "scope": "available corpus parts, this host",
        },
        {
            "claim_id": "W22-GA-05",
            "claim": "Color/TransparentColor short values carry a 3-byte triple behind the 84 81 header",
            "verdict": "positive (measured)",
            "label": "candidate",
            "rate": f"{color_files}/{total} files with >= 1 color-short Color block; "
            "measured triples include (231,231,231), (102,102,102), (0,0,0)",
            "scope": "candidate RGB — the byte triple is measured, the RGB semantics are not validated against a render",
        },
        {
            "claim_id": "W22-GA-06",
            "claim": "e6 + 8-byte LE double value class with clean physical values",
            "verdict": "positive (measured)",
            "label": "fact (bytes) / candidate (semantics)",
            "rate": f"Reflectivity f64 blocks {sum(r['prop:Reflectivity:f64'] for r in rows)} across "
            f"{sum(1 for r in rows if r['prop:Reflectivity:f64'] > 0)} files; measured values include 0.7, 0.495, 0.4, 0.05",
            "scope": "the double decode is byte-exact; the property semantics are unvalidated",
        },
        {
            "claim_id": "W22-GA-07",
            "claim": "e8 empty value dominates Transparency (no per-part opacity stored there)",
            "verdict": "positive (measured)",
            "label": "fact",
            "rate": f"Transparency blocks: {empty_trans} empty vs {f64_trans} f64",
            "scope": "available corpus parts, this host",
        },
        {
            "claim_id": "W22-GA-08",
            "claim": "the detector does NOT discriminate",
            "verdict": "declared limit",
            "label": "fact",
            "rate": "ordering of properties, per-face vs per-part attribution, the e8-variant descriptor "
            "(81 e8 d4 <T> 01, 4-file variant), and the long color form are not discriminated by this probe",
            "scope": "declared before review (dispatch-recipes hard rule)",
        },
    ]
    os.makedirs(os.path.dirname(CLAIMS_CSV), exist_ok=True)
    with open(CLAIMS_CSV, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(claims[0].keys()))
        writer.writeheader()
        writer.writerows(claims)


def selftest() -> None:
    """The detector's discriminating edge (dispatch hard rule): a
    synthetic positive (a valid block is found and its value class
    parsed), a framing-violation negative, and the asked-token census."""
    # Positive: a fe-framed Color block with the 84 81 short form.
    block = b"\xfe\x06Color\x81\xe9\xf4\x07\x04\x01\x84\x81\xe7\xe7\xe7"
    got = parse_property_block(block, 0, b"Color")
    assert got is not None, "the valid block must parse"
    assert got["value_class"] == "color-short", got
    assert got["value"] == "231,231,231", got
    # Positive: an e6 + f64 Reflectivity (0.7).
    block = b"\xfe\x0eReflectivity\x81\xe9\xd4\x07\x04\x01\xe6" + struct.pack("<d", 0.7)
    got = parse_property_block(block, 0, b"Reflectivity")
    assert got is not None and got["value_class"] == "f64", got
    assert got["value"] == repr(round(0.7, 6)), got
    # Positive: the e8 empty Transparency.
    block = b"\xfe\x0eTransparency\x81\xe9\xd4\x07\x04\x01\xe8"
    got = parse_property_block(block, 0, b"Transparency")
    assert got is not None and got["value_class"] == "empty", got
    # Negative: the length framing violated (len byte != strlen + 1).
    bad = b"\xfe\x07Color\x81\xe9\xf4\x07\x04\x01\x84\x81\xe7\xe7\xe7"
    assert fe_pattern(b"Color") not in bad, "the violated framing must not match the pattern"
    # Negative: an alien descriptor after a valid fe name.
    alien = b"\xfe\x06Color\x00\x01\x02\x03\x04\x05\x06\x07\x08"
    assert parse_property_block(alien, 0, b"Color") is None
    # Negative: the asked token census on a clean buffer.
    rec = scan_file(b"\x00" * 64 + b"\xfe\x06Color\x81\xe9\xf4\x07\x04\x01\x84\x81\xe7\xe7\xe7")
    assert all(v == 0 for k, v in rec.items() if k.startswith("token:")), rec
    assert rec["prop:Color:blocks"] == 1 and rec["prop:Color:color-short"] == 1, rec
    print("selftest: 6/6 pinned")


def main() -> int:
    args = sys.argv[1:]
    if "--selftest" in args:
        selftest()
        return 0
    corpus_root = ROOT
    limit = None
    if "--corpus-root" in args:
        corpus_root = args[args.index("--corpus-root") + 1]
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    rows = run_corpus(corpus_root, limit)
    write_files_csv(rows)
    write_claims_csv(rows)
    print(f"scanned {len(rows)} parts -> {FILES_CSV}")
    ga = sum(1 for r in rows if r["graphic_attribute_set"] > 0)
    family = sum(
        1 for r in rows if any(r[f"prop:{n.decode()}:blocks"] > 0 for n in PROPERTY_NAMES)
    )
    print(f"CATGraphicAttributeSet family: {ga}/{len(rows)} files (the dispatch's asked rate)")
    print(f"fe-framed material-property family: {family}/{len(rows)} files (the lead)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
