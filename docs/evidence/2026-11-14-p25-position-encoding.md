# Evidence: the P2.5 `_Position` value encoding — the transform-record layer located, its core decoded (2026-11-14)

Ticket P2.5 (spec F #46, Phase 6; the declared prerequisite of the P4
assembly bar [2026-11-14-p4-assembly-bar.md](2026-11-14-p4-assembly-bar.md)).
P2 proved `_Position` is never a pool item (191 framed files, 0 numeric
successors — [2026-11-14-p2-pool-pairing.md](2026-11-14-p2-pool-pairing.md)
§5): the values live OUTSIDE the pool. This probe ran the census-first
method (Phase-4 discipline) over the candidate surfaces the P4 note
names, then decoded what the census found.

**Verdict: PARTIAL DECODE (the ticket's legitimate partial).** The
transform value encoding — the record layer's `[tx, ty, tz, qw, qx, qy,
qz]` f64le core with the unit-quaternion law — is decoded with byte
evidence and per-bucket validation. The PER-INSTANCE BINDING (which
record belongs to which `_Position`-declaring instance) does NOT decode
within this probe's bound and stays the open class; the record layer's
carrier class covers 40/260 placed files at file level (P25-3). For the
P4 bar this is neither the full decode nor the ADR-0004 negative: the
owner decision point is recorded in §8 verbatim.

## 1. Population and method

Probe: `scripts/triage/p25_position_encoding.py` (committed with this
note). Imports `p1_product_census` (population, tail regions, law B)
and `p2_pool_pairing` (framing, pool texts, pairings) — not re-derived.
Modes: `--census` (per-file classification), `--claims`, `--ceiling`,
`--all`, `--selftest` (synthetic negatives for every P25-owned detector,
no corpus IO), `--sha16` (per-file JSON anchor). Deterministic
(the census's `load_population` order); explicit output paths; corpus
read-only.

    python3 -I scripts/triage/p25_position_encoding.py --selftest
    python3 -I scripts/triage/p25_position_encoding.py --all
    python3 -I scripts/triage/check_claims_csv_quoting.py --root .

Full run: ~39 s wall (382 manifest `kind=product` rows; 380 byte-verified
products analyzed, the 2 misfits classify `non-catia` and enter no
claim). Outputs: `docs/evidence/data/p25-position-encoding-files-claims.csv`
(382 rows), `p25-position-encoding-claims.csv` (14 claims),
`p25-position-encoding-ceiling-claims.csv` (7 rows). Every figure in
this note traces to those CSVs.

**The declared-before-observed plausibility criterion** (stated in the
probe's module docstring before any corpus value was read, per the
ticket): a serialized instance placement is a 7-tuple of IEEE-754
little-endian f64 where the quaternion part is UNIT
(`abs(|q|²−1) ≤ 1e-9`), translation components are 0 or mm-scale
(`1e-9 ≤ |t| ≤ 1e6`), and every component is finite. The sanity-check
the ticket demands is this criterion itself plus the geometric reading
of the decoded examples (§3.3).

## 2. The census — where transform-carrying structures live

Per-file classification with byte evidence; region attribution by the
file's own tail catalog (`p1.tail_regions`) with the block-walk fallback
(the census's localization model, not an ownership law).

### 2.1 The transform-record layer exists corpus-wide (FACT)

166/380 byte-verified products carry ≥ 1 record passing the declared
criterion after the header false-positive exclusion (P25-1; buckets in
the claims CSV: every generation contributes — `unknown` 79/102, R19
28/105, R21 17/53, R16 16/18, ...). 1995 records total (files-CSV
`recs_total` sum), by region class:

| Region class | Records | Carrier |
|---|---|---|
| `ctorproxy` (a `Cont_*` tail-catalog region or the CATCtorProxyCont block) | 542 | the placement-record carrier class (§3) |
| `CATIA` block | 635 | cameras/annotations/other transform consumers |
| pre-block bulk | 350 | mixed; NOT pool-adjacent (§5.3) |
| `CATProduct` block | 199 | mixed |
| other regions | 269 | `CameraStartupContainer`, `CATDrwCont`, ... |

The header constant table produced a FIXED record-shaped false-positive
family — exactly two patterns at offsets < 0x400 (`(0,0,1, 0,0,0,1)` at
0x3ec ×252 files, `(0,0,0, 0,0,0,1)` at 0x3cc ×43 files; no other
sub-0x400 pattern exists corpus-wide) — excluded from every claim
(P25-11).

### 2.2 The candidate surfaces the P4 note names (each closed or carried)

- **The 18 inline-value pools** (P2's binary-payload split, R18 5 + R19
  13 — P25-8 reproduces the 18-file rate): every binary payload is
  **13 bytes** — the `_BagRepsList` values P2 worked through; 13 B < 56 B
  cannot hold a transform. **The surface closes negative.**
- **The 44 embedded CB0001 catalogs** (P25-9 reproduces the census's
  44-file rate): the embedded structure is the tail-catalog REGION-TABLE
  shape one level down (P1 §6: name/start/len entries), which carries
  names and offsets, not float tables; the record-layer windows found
  near body-CB0001 occurrences attribute (by the tail-catalog regions)
  to the SURROUNDING blocks' regions, never to the catalog payload
  itself. **The surface closes negative as an independent carrier** (the
  records near it are the same record layer §3 decodes).
- **The relation-string neighborhoods**: P2 already classified the LONG
  items as text (107 files carry `CtorToProd:...` strings); no numeric
  payload. **Negative** (carried from P2 §3).
- **The tail catalogs**: POSITIVE — the carrier class's regions are
  NAMED by the file's own tail catalog (`Cont_<guid>` regions = the
  CATCtorProxyCont stream; worked example in §3.1). The tail catalog is
  the map that finds the records.
- **f64/f32 run structure near the pool** (P2's supplementary hint "the
  binary record layer around the pool"): **closes negative** — of 350
  pre-block records on framed files, 5 sit within 4 KB of their pool
  record's midpoint (P25-13, 3 files; the files-CSV
  `preblock_near_pool`/`recs_preblock` columns). The pre-block records
  are generic transform consumers, not the pool's value layer.
- **The R15-era reference form** (P25-10: 45 files with law-B-valid
  `_Position` entries carrying the `80/81 ... e8/e7` reference tags —
  e.g. `Fix.CATProduct` @0x3413: `0a "_Position" 81 e9 f4 07 04 01 8d
  81 e7 e8e8e8 e7e8e8 e7e8e8`): the values ride UNDECODED reference
  fields (pool indexes), not inline floats. **Stays the legacy open
  class** (P2 §6 already scoped it; this probe adds the `_Position`
  specific observation).

## 3. The decode — the transform-record layer

### 3.1 The record core (FACT, ≥ 3 files per marked bucket)

A record is, at its start offset `s`:

| Field | Bytes | Encoding | Claim |
|---|---|---|---|
| translation | `s..s+24` | 3 × f64le `(tx, ty, tz)` | mm-scale coordinates or exact 0 (FACT: the declared criterion; every record passes it by construction — the LAW is what validates) |
| quaternion | `s+24..s+56` | 4 × f64le `(qw, qx, qy, qz)` — **w FIRST** (§4) | unit-norm law `abs(|q|²−1) ≤ 1e-9` (FACT: 1995/1995 kept records) |
| id prefix | `s−9..s−1` | 8-byte time-like value + 1 trailer byte | OBSERVED on the R19/R20 chain records (e.g. `b5 13 27 79 88 00 00 00` + `80`), NOT a uniform law — prefix first-bytes vary (`b5 13` 173/622, `20 00` 160/622, ...); semantics UNKNOWN, open |
| trailing fields | `s+56..` | variable-length f64 run | record-type-dependent: bbox sentinels (`±1e7`), flag-like runs (`1,0,1,1,0` / `1,0,18,0,4`), further coordinates; anatomy UNDECODED, open |

Worked examples (by sha16, resolvable through the manifest; offsets from
the files-CSV `first_record_*` columns and the probe's `--sha16` mode):

- `0018ec386764dcea` (Dictor `Product1.CATProduct`, R24) @0x5621:
  `t = (−5, −15.5, 179.99999999983928)`, `q = (1, 8.24e−12, −8.24e−12,
  4.78e−12)` — an identity rotation (w=1 exact, noise on the axis) with
  a pure translation. The census's own worked example file.
- `126c9fda3c4218c3` (Apoloo13 `lengua.CATProduct`, R20) @0x45725:
  `t = (5, 0, 1.45)`, `q = (−1, 0, 0, 0)` — identity (w=−1 ≡ 1);
  177 records in ONE `Cont_0_448c_6ab71ee0_bbc0` region, id-counter
  sequence visible (`...2a, 2b, ...` increasing), mirrored translation
  pairs (`(5,0,1.45)/(-5,0,1.45)`, `(−10,−37.51,−5)/(10,−37.51,5)`) —
  the symmetric left/right layout of the assembly.
- `9a9d8a85ae5e59b6` (Apoloo13 `head.CATProduct`, R20) @0x38e8e:
  `t = (−75.566977, 14.05, −10.328967)`, `q = (−0.0033079697, 0,
  0.99999453, 0)` — a 180° rotation about Y (w=−0.0033≈0, axis=(0, 1,
  0)) with a real translation; the 15-f64 anatomy + id `b5 13 27 79 88
  00 00 00` + trailer `80` visible in full.

### 3.2 Validation scope (the decode template's ≥ 3 files per marked line)

Per-bucket rates live in the claims CSV (`buckets` column). The
ctorproxy carrier class (P25-2, 42/380): R19 19/105, R20 10/26, R21
5/53, `unknown` 6/102 are the ≥ 3-file marked lines; R16 1/18, R24 1/17
fall below the bar and are NAMED there, never folded. The record layer
as a whole (P25-1) spans every bucket (R15 3/14 through `unknown`
79/102).

### 3.3 The geometric sanity-check (declared criterion + the decoded examples)

The declared criterion (§1) IS the pre-stated plausibility gate; the
decoded examples pass it and read as placements: identity rotations
with mm-scale translations (Dictor −5/−15.5/180; lengua ±5/±10/±37.511
mirrored pairs); 180°/90° axis rotations for flipped components (head's
parts at −75.57/14.05/−10.33); no non-finite or denormal component ever
passes (the detector rejects them — selftest-pinned). The quaternion
layers carry REAL rotations (P25-5: 11 files with non-identity records;
279 non-identity records corpus-wide) and the translation layer real
offsets (P25-6: 97 files carry ≥ 1 record with a non-zero translation).

## 4. The quaternion component order — `(w, x, y, z)`, w FIRST

No single record decides the order (w=0 records are order-symmetric);
the corpus decides, two consistency arguments (a consistency argument,
not a semantic proof — declared exposure):

1. **The w-last contradiction records (DECISIVE)**: 504 records carry a
   DENORMAL index-3 component alongside a large axis component
   (P25-14, 47 files, every generation) — e.g. lengua
   `q = (0, 1.0000000000000002, 5.1e−312, 2.2e−314)`. Under `(x,y,z,w)`
   that is IMPOSSIBLE (a denormal w forces angle ≈ 360° = identity,
   contradicting the large axis); under `(w,x,y,z)` it is a 180°
   rotation's axis-noise tail (valid). Zero records contradict the
   w-first reading structurally.
2. **The identity majority**: 1576 identity quats have their dominant
   component at index 0 vs 140 at index 3 (files-CSV
   `identity_at_index0`/`identity_at_index3` sums). A uniform w-last
   convention would make the 1576 a 180°-about-X population —
   implausible; under w-first they are identities, and the 140 are the
   minority w-last-serialized family (concentrated in non-ctorproxy
   regions — cameras/viewpoints; semantics open, never folded).

## 5. What the census ruled out (the negatives)

1. **The 18 binary pools**: all payloads 13 B (`_BagRepsList` values) —
   under the 56 B a transform needs (P25-8).
2. **The 44 CB0001 catalogs**: region tables, not numeric tables (§2.2).
3. **The relation-string neighborhoods**: text, not values (P2 §3).
4. **Pool-adjacent pre-block records**: 5/350 within 4 KB of the pool
   (P25-13) — the pool's neighborhood does not carry its values.
5. **The header constant table**: the fixed record-shaped FP family
   (two exact patterns, offsets < 0x400; P25-11) — excluded, and the
   only sub-0x400 record-shaped bytes corpus-wide.
6. **The legacy generations**: 7 of the 8 placed files with ZERO records
   anywhere are `unknown`-bucket legacy forms (4 r15-ref + 3 unframed;
   the 8th is an R23 framed file whose CtorProxy block carries no
   record layer and no `27 79` id family — a writer generation without
   this record layer). Their `_Position` values ride the R15 reference
   form's undecoded `e8/e7` fields or structures this probe did not
   find. **Open class**, named.

## 6. The open classes (named, never folded)

- **The per-instance binding**: which record belongs to which
  `_Position`-declaring instance. Record counts do NOT match instance
  counts 1:1 (lengua 177 records vs 143 dot-shaped pool names; head 85
  vs 46; most placed files carry 0 ctorproxy records), no name string
  rides the record layer, and the id-counter sequence does not
  demonstrably bind to the pool order. The P4 bar's placement clause
  needs exactly this binding — it is THE remaining gap.
- **The trailing-field anatomy** (`s+56..`): variable per record type;
  observed shapes (bbox sentinels ±1e7, flag runs, further coordinates)
  recorded, semantics undecoded.
- **The id prefix families**: time-like 8-byte values + 1 trailer byte;
  several byte families, no uniform law; semantics unknown.
- **The minority w-last-serialized identity family** (140 records,
  non-ctorproxy regions): a second serialization convention or a
  different record type; open.
- **The R15 reference form's `e8/e7` fields** (45 files): the legacy
  value layer, undecoded (P2 §6 scope stands).
- **The R23 writer without the record layer** (1 file): a generation
  that serializes positions some other way; open.

## 7. Detector-honesty declarations

- **`transform_records`**: counts byte windows passing the DECLARED
  criterion; it cannot tell a live instance placement from any other
  serialized 3D transform (cameras, viewpoints, annotation planes ride
  the same shape) — the REGION attribution is the placement-class
  discriminator and it is reported per class, never folded. Grouping
  rule: a record is detected at its START (the earliest translation-ok
  window of each overlapping quat-unit group); the measured residual
  exposure is the displaced-window count (P25-12: 2855 windows corpus-
  wide, 292 files) — each displaced window is a quat-unit window whose
  own translation failed. Selftest pins: synthetic positive, norm-
  violation negative, denormal-translation negative, out-of-range
  translation negative, the ts8-prefix start-wins case, both header-FP
  patterns detected-AND-excluded, the shifted-phantom exposure (declared,
  pinned as observed behavior).
- **`quat_order_stats`**: identity = exactly one dominant component with
  the others ~0, dominant at index 0 (w-first) or index 3 (the minority
  family); dominant at index 1/2 with w=0 is a 180° AXIS ROTATION, never
  an identity (the first draft mislabeled these; fixed before the CSV
  was generated — the selftest pins both counts). The order claim rests
  on corpus consistency (§4), not on a semantic proof — declared
  exposure.
- **Region attribution**: the census's localization model (tail-catalog
  regions where the walk completes, block names otherwise) — a
  localization, not an ownership law (P1 §5 carries over).
- **The placed flag**: framed files use the P2 pool-token law; legacy
  forms use the census's law-B whole-file detector (`position_attr_present`,
  P1 review F1) — 260 placed reproduces the P1/P2 ceiling exactly.
- **The R15 entry counter** (`r15_position_entries`): requires the
  0x80/0x81 reference tag after the law-B name; a framed-pool-style
  successor does not count (selftest-pinned both directions).

## 8. Ceiling arithmetic — what P2.5 moves (ceiling CSV)

| Ceiling row | P1/P2 | P2.5 | Delta |
|---|---|---|---|
| population byte-verified | 380 | 380 | 0 |
| placed instances (`_Position` attribute) | 260 | 260 | 0 — the ceiling stands |
| placed files with ≥ 1 transform record (any region) | — (open) | **106** | NEW — the file-level record-layer rate |
| placed files with ≥ 1 ctorproxy-class record | — (open) | **40** | NEW — the placement-carrier class rate (P25-3) |
| placed files with ≥ 1 non-identity (rotated) record | — (open) | 10 | NEW |
| identity-only files with ctorproxy records (control) | — | 2 | NEW — the control residual, named |
| per-instance transform binding | — (open) | **OPEN** | 0 — the binding does not decode in this probe's bound |

**The owner decision point (recorded verbatim for the P4 bar):** the
value ENCODING decoded (the record core, §3); the per-instance BINDING
did not (§6). The P4 bar's placement clause ("instances render with
DECODED transforms") requires the binding, so the bar is not met by
this probe alone — but this is NOT the ADR-0004 negative (the encoding
did not resist; the binding was never attempted at decode depth because
the census shows the carrier class covers 40/260 placed files and no
1:1 count law exists to force). The decision — bind the records
(P2.6-style follow-up on the id-chain/occurrence layer), re-scope the
bar to the decoded file-level class, or take the negative path —
returns to the owner with this evidence.

## 9. Reproduction

    # selftest (no corpus IO)
    python3 -I scripts/triage/p25_position_encoding.py --selftest
    # the census + claims + ceiling (~39 s)
    python3 -I scripts/triage/p25_position_encoding.py --all
    # CSV hygiene (the gate covers this family via the *claims*.csv glob)
    python3 -I scripts/triage/check_claims_csv_quoting.py --root .
    # per-file JSON anchor
    python3 -I scripts/triage/p25_position_encoding.py --sha16 0018ec386764dcea

Worked examples (by sha16): `0018ec386764dcea` (Dictor, identity +
translation), `126c9fda3c4218c3` (lengua, the 177-record Cont_ region +
mirrored pairs), `9a9d8a85ae5e59b6` (head, the 15-f64 anatomy + the
180°-about-Y record).

Gate: ruff clean; pytest 377 passed 7 skipped; claims CSV hygiene 40
files (3 new, all at header width).
