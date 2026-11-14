# Evidence: the P2 structure-pool pairing law — the pool's record layer decoded (2026-11-14)

Ticket #53 (P2, parent spec F #45, Phase 6). Implements the P1 census's
dispatch proposal priority 1
([2026-11-14-p1-product-census.md](2026-11-14-p1-product-census.md) §8):
decode the structure pool's non-string layer — how pool entries pair —
on the census's 380-file ceiling population. The census's law-B string
layer is the foundation (`scripts/triage/p1_product_census.py` is
imported, not re-derived; `law_b_valid` is re-pinned by selftest).

Method discipline: the file-format structure decode template
(dispatch-recipes.md, reap-03 adapted) — decode from observed corpus
files only, field by field with byte ranges and endianness, validate
corpus-wide with per-bucket version scoping (>= 3 files per marked
line; lines under 3 files are named in the claims CSV), every claim
fact / inference / unknown with its rate and scope. No parser, port or
viewer changes (RE territory per the ticket's hard stop).

## 1. Population and method

Probe: `scripts/triage/p2_pool_pairing.py` (committed with this note).
Modes: `--pairing` (per-file decode + claims), `--ceiling` (the delta
arithmetic), `--all`, `--selftest` (synthetic negatives for every
P2-owned detector, no corpus IO), `--sha16` (per-file JSON anchor).
Deterministic (the census's `load_population` order); explicit output
paths; corpus read-only.

    python3 -I scripts/triage/p2_pool_pairing.py --selftest
    python3 -I scripts/triage/p2_pool_pairing.py --all
    python3 -I scripts/triage/check_claims_csv_quoting.py --root .

Full run: < 1 s wall (380 files). Population: the census's 382 manifest
`kind=product` rows; 380 byte-verified products analyzed (the 2
manifest misfits classify `non-catia` and enter no CATIA claim).

Outputs: `docs/evidence/data/p2-pool-pairing-files-claims.csv` (380
rows, one per manifest product), `p2-pool-pairing-claims.csv` (17
claims), `p2-pool-pairing-ceiling-claims.csv` (5 rows). Every figure in
this note traces to those CSVs.

## 2. The record framing — the pool's binary neighborhood (FACT, R18-R26 100%)

The structure pool is the payload of a binary record anchored at
`fe 7c 02`:

    fe 7c 02 <u32le ln> <tb tail bytes> <pool items...>

Field by field (offsets relative to the record start `h`, the `fe` byte):

| Field | Bytes | Claim |
|---|---|---|
| mark | `h..h+2` | `fe 7c` — 2-byte anchor (FACT: the pool record's first bytes on every framed file) |
| tag | `h+2` | `02` — the pool record type (other tags exist: `09`-family records share the framing, §3) |
| length | `h+3..h+7` | u32le `ln` — counts from the **`7c` byte** through the pool's LAST byte: `ln == 6 + tb + pool_span`; the record spans `[h, h+1+ln)` (FACT, 253/253 framed; the chain's own unbounded walk independently stops on `h+1+ln` on all 235 all-text pools) |
| tail | `h+7..h+7+tb` | `tb` ∈ {1, 2} bytes on structure pools (140 / 113 files); values 192/253 all-high-bit, no law established (**UNKNOWN**, open class) |
| payload | `h+7+tb..h+1+ln` | the pool item chain, tiling the span EXACTLY (FACT, 253/253) |

Worked example `0018ec386764dcea` (Dictor/HaneulMyo `Product1.CATProduct`,
V5R24, 40983 B — the census's worked example): record @0x22e9,
`fe 7c 02`, ln=0x875=2165, tb=1 (`bf`), pool `[0x22f1, 0x2b5f)` —
2158 bytes = 2165 − 6 − 1; 62 items tile it exactly (53 SHORT, 9 LONG).

Version scope (framing-scan claim, buckets column): **R18 25/25, R19
105/105, R20 26/26, R21 53/53, R23 3/3, R24 17/17 = 100% on R18-R26
(230/230)**; R15 1/14, R16 9/18, R17 12/16, `unknown` 1/102 — the
legacy/transition generations (§6). All 253 framed files tile exactly
and satisfy the length law.

The framing is GENERIC, not pool-specific: 1376 tiling candidates across
the population, 239/380 files carry MORE THAN ONE `fe 7c 02` chain —
electrical (`ElecGeoBundleE`…), measure (`MEASURE`, `Mesure entre`…)
and spec pools ride the same record shape. The structure pool is
selected by its assembly vocabulary (>= 2 census POOL_TOKENS among the
items); the other chains are reported as candidates, never folded.

## 3. The typed item chain — the non-string layer decoded (FACT)

The payload chains back-to-back with no padding and no terminators.
Two item forms (the census's law B plus its generalization — the
census's `00 86 00 00 00` u32le relation-string neighborhood is the
LONG form):

| Form | Encoding | Length law | Observed payloads |
|---|---|---|---|
| SHORT | `<u8 L> <L-1 bytes>`, L >= 1 | L = char count + 1 (law B; L == 1 is the zero-char item observed between `catalogLinks` and `ASMPRODUCT`) | UTF-8 text (`\n` allowed in formula strings; accented names arrive as UTF-8 lead+continuation pairs, e.g. `Pièce1` — 0xc3-led pairs dominate the high-byte histogram) |
| LONG | `<00> <u32le n> <n bytes>`, n >= 1 | n = EXACT char count; the `00` is an escape that switches to a 4-byte little-endian length | the relation strings (`CtorToProd:Product!ProdToRep:...`, 107 files carry them) and, on 18 pools, binary values |

Payloads may be text OR binary: inline-value generations (18 pools, R18
5 + R19 13) serialize binary attribute values inside the same chain —
e.g. `7276bee109497b28`'s `_BagRepsList` value is a 13-byte binary run
(`3f 3f 15 3f 5c 3f 3f 3f 12 c2 b6 3f 3a`) between `_BagRepsList` and
`_PrdVersion`. Per-item text/binary classification separates the string
measurements from those values; all-text pools: 235/253 (the all-text
rate is also what makes the independent break cross-check exact — a
binary value legitimately stops the unbounded TEXT walk early).

The chain walk validates by EXACT TILING to the record end, not by
payload content — the length law is the validator, the byte class is a
classifier (detector honesty, §7).

## 4. The pairing laws (the ticket's core)

All rates on the 253 framed pools (claims CSV carries the per-bucket
breakdown); occurrence counts in the `detail` column.

### 4.1 Identity — the `_InstanceName` pairing (FACT)

**`<PartNumber value> _InstanceName <InstanceName value>`** — the
instance's part number value immediately PRECEDES the `_InstanceName`
attribute token; the instance name immediately FOLLOWS it.

- 216/253 files (0.854) carry >= 1 such triple; 216 triples measured.
- 158/253 files: the marked instance name is dot-shaped (the census's
  INSTANCE_SHAPE `name.N`); 158 dot-shaped instance names measured.
- Support (the triple-predecessor histogram in the claims CSV): the
  predecessors are part-number-like values — `Part1` ×25,
  `ElectricalData` ×15, `Pièce1` ×11, `Adaptive` ×9 — and the successors
  are the instance names; the adjacency IS the pairing.
- Worked example: `Part001` `_InstanceName` `Part001.1` `_Position`
  (items 22-25 of the Dictor pool, offsets 0x23f1/0x23f9/0x2407/0x2411).

### 4.2 Identity — the description-instance block (FACT, generation-specific)

17/253 files (R19-era mostly: 11/105 R19) serialize the instance as a
6-token block with THREE name forms:

    <PN> _DescriptionInst <PN:1> _InstanceName <PN_1> _Position

e.g. `ac2` `_DescriptionInst` `ac2:1` `_InstanceName` `ac2_1`
`_Position` (`91fe0d674f7c30db`, R20). The colon and underscore forms
are counted as observations (COLON_SHAPE/USCORE_SHAPE), never forced
into the census's dot shape.

### 4.3 Identity — the bare pair (INFERENCE)

Adjacent `<value> <dot-shaped value>` pairs outside marker triples:
180/253 files, 3661 raw adjacencies. The adjacency alone does NOT
discriminate a part-number→instance-name pair from any value→name
sequence; the stem-match subrate (predecessor equals the instance
name's stem, e.g. `Part0024` `Part0024.1`) confirms 344 pairs. The
claim is labeled inference for exactly this reason; the marker triple
(4.1) is the decoded law.

### 4.4 `_PartNumber` ↔ value (FACT, via the vocabulary run)

`_PartNumber` sits between `_Component` and `_BagRepsList` in the
vocabulary run on 197/253 files (the census's vocabulary listing); its
VALUE pairs through the identity triple (4.1) — the triple's first
element. On 8 inline-value files the value follows the attribute name
directly (`_PartNumber` `ALETTA-PFC1` — `7276bee109497b28`).

### 4.5 Class-token anchors (FACT — the census's record-anchor hint)

| Anchor | Successor | Files |
|---|---|---|
| `ASMPRODUCT` | a value — the SAVE-TIME document name (stem-equality with the manifest: 127 occurrences; renamed files legitimately mismatch) | 203/253 |
| `PRDREP` | a value — the representation name (`Shape 1`) | 183/253 |
| `CONNECTION`/`CONNECTOR` | a value — the connection name (`Surface contact.1`, `Fixe.5`) | 113/253 (114 occurrences) |
| `IsRoot` | terminal (last item) on 155/253; on the remainder the chain continues with viewpoint tails (`VPGlobal`/`VPAsm`) | 155/253 |

## 5. `_Position` — the value is NOT a pool item (FACT; the open class stands)

Wherever `_Position` appears in-chain (191 files, 191 tokens — exactly
the files where the P1 whole-file law-B detector fires: zero
file-only occurrences on framed files), its SUCCESSOR is:

- a token or class token: 132 occurrences (`PRDREP` ×110, `CONNECTOR`
  ×7, `IsRoot` ×6, `ASMGEOMETRY` ×4 — the successor histogram in the
  claims CSV; the next record's class anchor),
- a non-numeric value: 59,
- a NUMERIC value: **0**.

The instance's position VALUE therefore does not ride the pool chain —
the attribute is DECLARED in-stream and its value lives elsewhere (the
binary record layer around the pool). The P1 open class (census §6:
"where the 12 numbers live and their encoding is undecoded") stands,
now with the in-pool absence measured at full scale and the successor
distribution enumerated. Supplementary negative: no f64le run >= 12
exists in the +-12 KB pool neighborhood of the probed worked examples
(the only plausible runs are the relation strings' ASCII text — the
census's X1 non-discrimination, now scoping the absence instead of
blocking the claim). The value decode remains future work; nothing is
forced.

## 6. Generation map and open classes

| Generation | Files | Pool form |
|---|---|---|
| R15 | 14 | attribute-reference form (below) — 12/14; 1 framed; 1 unframed |
| R16 | 18 | split: 9 framed / 9 reference-form |
| R17 | 16 | split: 12 framed / 4 reference-form |
| R18-R26 | 230 | **framed typed chains, 100%** |
| unknown | 102 | reference-form 81, unframed 20, framed 1 |

Framed-pool content drifts by generation (rates in the claims CSV):
R16-R18 serialize a shortened head — the self name follows the empty
item directly, `ASMPRODUCT` often absent (R17 head-skeleton 1/12, R18
1/25, R19+ 201/205); R19-R26 carry the full form (`CATCatalogManager`
head 4-item skeleton 214/253, `ASMPRODUCT` anchor, `IsRoot` tail).

Open classes (named, never folded):

- **R15-generation attribute-reference form (106 files**: R15 12, R16
  9, R17 4, unknown 81): entries `fe [fe] <u8 len> <ASCII name> 80
  <5 bytes> e8 <3-4 bytes>` — the SAME attribute vocabulary as the
  framed pools' (`_Connectors`, `_Component`, `_PartNumber`,
  `_BagRepsList`, …) under an older encoding where every attribute
  name carries inline numeric reference fields. The reference fields
  are UNDECODED here (bounded dispatch); this is the natural next
  entry point for the legacy generations.
- **Unframed files (21**: unknown 20, R15 1): neither form; several
  carry assembly vocabulary in law-B strings outside any tiling chain.
- **Framing tail byte(s)**: 1-2 bytes, 192/253 all-high-bit, no law —
  semantics unknown.
- **`_Position` value encoding**: §5 — the open class carried forward
  from P1 with the absence measured.

## 7. Detector-honesty declarations

- **Chain walker** (`walk_chain`): validates item LENGTHS and exact
  tiling, not payload semantics — a binary run parses as items. The
  validators are the framing length law and the vocabulary gate; the
  text/binary classification (`payload_is_text`) separates the string
  measurements from binary values. Selftest pins: the census's
  worked-example bytes, LONG with zero/exact length, truncated header,
  binary item classified binary, text walk stopped by control bytes.
- **Framing scan** (`framed_pool_candidates`/`pick_pool`): scans every
  `fe 7c 02`, tries tail widths 0-2, requires >= 3 tiling items and
  >= 2 census pool tokens. It does NOT prove the chosen chain is the
  only structure carrier (239/380 files carry several chains; the
  others are counted, not folded). Selftest pins: synthetic record
  positive, length off-by-one negative, short-length negative,
  non-vocabulary chain rejected.
- **Pairing classifiers** (`classify_pairings`): `is_token` = leading
  underscore — an underscore-prefixed VALUE would misclassify (none
  observed; declared exposure). A numeric successor after `_Position`
  WOULD count (pinned by selftest) — the corpus absence is therefore
  meaningful. The bare pair is adjacency, not a decoded reference; its
  stem-match subrate is reported next to the raw count.
- **Self-name anchor**: `ASMPRODUCT`'s successor equals the manifest
  stem only for unrenamed files — the pool keeps the SAVE-TIME name
  (the mismatch rate is reported, not hidden).
- **Law B** (imported): re-pinned by selftest both directions; the P1
  honesty declarations carry over unchanged.

## 8. Ceiling arithmetic — what P2 moves (ceiling CSV)

The P1 ceiling ([2026-11-14-p1-product-census.md] §7,
`p1-census-ceiling-claims.csv`) stays CITED; the delta rows:

| Ceiling row | P1 | P2 | Delta |
|---|---|---|---|
| population byte-verified | 380 | 380 | 0 |
| instance records DECLARED (pool) | 380 | **SUPERSEDED-DATED**: the pool is a framed typed chain on 253 files; on the remaining 127 the records ride the reference form (106) or are unframed (21) | semantics refined |
| **identity pairs DECODED** (>= 1 per file) | — (was a ceiling only) | **225** | NEW — the assembly bar can demand decoded (PartNumber, InstanceName) identity pairs here |
| placed instances (`_Position` attribute) | 260 | 260 (191 in-chain on framed files + 69 legacy/unframed) | 0 — ceiling stands; the value encoding remains the open class (§5) |
| identity-only candidates (pool without `_Position`) | 120 | unchanged | 0 |

Reading: the pairing law sharpens the P1 bar's first clause —
"assemble the instance lists (names + part numbers)" is now a DECODED
operation on 225 files (identity pairs) with the placed-instance clause
still gated by the `_Position` value encoding.

## 9. Reproduction

    # selftest (no corpus IO)
    python3 -I scripts/triage/p2_pool_pairing.py --selftest
    # the pairing decode (both CSVs; < 1 s)
    python3 -I scripts/triage/p2_pool_pairing.py --pairing
    # the ceiling delta CSV
    python3 -I scripts/triage/p2_pool_pairing.py --ceiling
    # per-file JSON anchor mode
    python3 -I scripts/triage/p2_pool_pairing.py --sha16 0018ec386764dcea
    # CSV hygiene (the gate covers this family via the *claims*.csv glob)
    python3 -I scripts/triage/check_claims_csv_quoting.py --root .

Worked examples (by sha16, resolvable through the manifest):
`0018ec386764dcea` (the framing + full form), `91fe0d674f7c30db` /
`c75525329d87b75d` (the description-instance block),
`7276bee109497b28` (inline-value form with a binary `_BagRepsList`
value), `246ccbf5e0c5f739` (R17 shortened head).

Gate: ruff clean; pytest 377 passed 7 skipped; claims CSV hygiene 37
files (3 new, all at header width).
