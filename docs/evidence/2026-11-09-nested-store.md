# Evidence: the nested V5_CFV2 stream store, decoded (2026-11-09)

Ticket #29 (G1, spec D #28): decode the nested `V5_CFV2` store inside
the `CATStdCont` block regions corpus-wide. Scope: **all 1,377 dev
parts** of the corpus manifest (`kind=part`, `split=dev` — every repo
except the Motor-V6 holdout — `magic_ok=yes`), so every rate below is
corpus-wide, not a sample: per-release n is the actual manifest count
(marked lines R15-R24 have n = 14-544; R25/R28/R32 have n = 1 and R26
n = 2 — stated as-is; `unknown` n = 236). The products negative (0/37)
is B4's, not re-derived here. Method: read-only byte analysis,
`scripts/triage/decode_nested_store.py` (stdlib, mmap, deterministic;
run with `python3 -I`; ~2 s wall clock, three consecutive runs
byte-identical, md5-verified). Data:
`docs/evidence/data/nested-store-files.csv` (one row per part),
`nested-store-regions.csv` (one row per decoded store),
`nested-store-streams.csv` (one row per named stream region),
`nested-store-claims.csv` (per-claim, per-release rates). Builds on B4
([2026-11-08-geometry-payloads.md](2026-11-08-geometry-payloads.md),
which discovered the store), B2's tail catalog
([2026-11-08-header-tail-semantics.md](2026-11-08-header-tail-semantics.md))
and B1's container/trailer laws; those models are cited, not re-derived.

Labels: **established** = the byte-level model validates with rate
>= 0.98 on its scope (counterexamples named); **candidate** = below the
bar or otherwise unproven. Structural presence claims carry
"established (observed)"; negatives "established (negative)". Every
claim states whether it is a fact (byte-measured), an inference, or an
unknown.

The headline: **the nested store is a faithful copy of the outer file
architecture one level down** — same 64-byte-header-like generation
marker, same `CATIA_V5 CB0001\0` catalog with B2's record layout and
stop behavior, same 36-byte `CB__END` trailer, same 126-byte
inter-block tail — with four measured deltas (entry-0 X0 = 132, trailer
A/E pairing, no registration block in the trailer region, and two
header variants). The catalog names the stream regions; X/Y are
relative to the store origin (B4 open question 6 answered).

## 1. The store and its header variants (N1, N2, N10)

Of the 1,377 dev parts, 1,173 carry a `CATStdCont` block and 204 carry
none. Store classes over the 1,173 (claims CSV, per release):

| class | parts | share | lines |
|---|---|---|---|
| header store (32-B `V5_CFV2` header) | 1,056 | 0.900 | every line R15-R32 + unknown |
| header-less store (origin = block start) | 12 | 0.010 | **R19 only** |
| embedded-document catalog (not a store) | 8 | 0.007 | `unknown` only |
| no store in region (region carries neither marker) | 63 | 0.054 | unknown 58, R23 4, R16 1 |
| store on the next block instead (`CATXDocLinkCont`) | 34 | 0.029 | **R19 only** |

- **N1 (established (observed), prevalence):** a nested stream store
  (header or header-less) sits in the `CATStdCont` block region of
  1,068/1,173 = 0.910 CATStdCont-carrying parts = 0.776 of all dev
  parts; per-release store rate among CATStdCont parts 0.64 (R23, 7/11)
  - 1.00 (R15, R17, R18, R20, R21, R24-R32), with R16 17/18, R19
  504/538, unknown 48/114. Fact; the misses are classified in
  section 6, not model failures.
- **N1h (established (observed)):** the header variant — 1,056/1,173 =
  0.900. The store origin (magic offset from the block start) spans
  246..322 B; 248..268 covers 1,051/1,056 (mode 252, n = 330; 250,
  n = 286) — the block's property preamble, the nested analog of the
  V8 `X = block_start + 244..262` law. The five outliers are the four
  padded/variant stores (310 x2, 322 x2) and one R20 store at 246.
- **N1l (established (observed family)):** the header-less variant —
  12 parts, **all R19**, tail length 2,686-2,690 B, origin = block
  start. The header is simply absent: the payload starts at block + 64
  (like the outer file's body), the catalog sits directly in the
  region, and every model law below holds for these stores unchanged.
- **N2 (established, 1,056/1,056):** the nested header, field by field
  (all offsets relative to the magic; multi-byte fields **big-endian**):

| offset | size | field | content |
|---|---|---|---|
| +0..+8 | 8 | magic | `56 35 5F 43 46 56 32 00` = `V5_CFV2\0` — the outer file header's own magic |
| +8..+12 | 4 | dword8 | offset of the nested catalog (`CATIA_V5 CB0001\0`) from the origin |
| +12..+16 | 4 | dword12 | nested catalog tail length |
| +16..+24 | 8 | ff x 8 | `ff` x 8 (the outer header's generation marker) |
| +24..+32 | 8 | zeros x 8 | `00` x 8 |

  The outer file header's first 32 bytes carry exactly this layout (its
  body starts at 64; the nested header is the outer header truncated to
  32 bytes). Dwords read little-endian are implausible (~3.3e9), so the
  outer header's big-endian convention is reused — fact.
- **N10 (established (classification)):** a `CB0001` magic inside the
  region that does not validate as a store catalog is an **embedded
  document's own outer-style catalog** (8 parts, all `unknown`-version
  CAA files; names `CATStorageProperty`/`CATIA1`/`Cont_*`, entry-0
  X0 = 94 — the outer constant, not the nested 132). Not a stream
  store.

## 2. The nested catalog = B2's tail model one level down (N4)

Every store's catalog (found at origin + dword8, header variant, or at
the last `CB0001` before the 126-B tail, header-less) parses under
B2's outer tail model unchanged:

- **N4 (established):** entry-0 M-law `e0_len == M + 87` with
  **M = 86** on 1,068/1,068 stores; `cntB == cntA + 1` on
  1,067/1,068; record sequence numbers run 2, 3, ... in list order on
  1,068/1,068; records are B2's hdr84 + xrec13 + fil87 + UTF-16 name
  form (11,321 primary entries parsed corpus-wide). cntA = 12 on 993
  clean-tail header stores, 11 on 45 — the nested catalog carries ~12
  records regardless of store size.
- **N4x (established, 1,066/1,068 = 0.998):** entry-0 X0 = **132**
  (the outer tail's constant is 94). The 2 exceptions are the
  `CGRHEADER` variant below (X0 = 110).
- **N4w (established, 740/741 = 0.999 on scope):** on stores whose
  primary walk runs to a clean end and end with `CB__END` (741 stores),
  B2's exact length accounting holds (the one exception
  `498edddda534e60c`, one of the E-pairing variants below).
- **Stop condition (fact):** the primary walk stops where B2's does —
  at a record whose name field is not followed by `00 00`, i.e. the
  next bytes are not another hdr84-record (the trailing variant-record
  families begin `01 82 ...` / `01 6e ...`). The outer tail of the
  worked example breaks the same way (`name@5781`, 25/45 records), so
  this is B2's known limitation reappearing one level down, not a
  nested variant. B4's resync continuation applies but rarely fires
  (5 stores, 5 recovered entries).
- **Padded-tail variant (established (observed family), 18 stores, all
  `unknown`):** 18 header stores (cntA 4-11) carry a valid catalog whose
  trailer is *inside* the tail, followed by zero padding to a round
  dword12 (3,072 or 4,096 B). For them `G == tail_len` fails by
  construction (the trailer's G names the true catalog length) —
  measured, not massaged.
- **`CGRHEADER` variant (established (observed family), 2 stores,
  `unknown`):** the catalog names `SceneGraph;CGRHEADER;Header` — a
  CGR-flavored stream set without `SurfacicReps` — and carries
  X0 = 110. Both facts are in the regions CSV.

## 3. The nested region model (N5, N7)

- **N5 (established):** catalog entry X/Y are **relative to the store
  origin** — B4 open question 6 answered. Header stores: the largest
  named region ends exactly at `origin + dword8` on 1,056/1,056 (the
  nested analog of B2's R2, exact). Header-less stores: the smallest
  named region starts at 64 on 12/12 (the outer file's own R1 = 64
  convention, with the block start as origin). The trailer's B pointer
  is origin-relative too (B < dword8 everywhere, absolute values would
  precede the block).
- **N7a (established, 1,066/1,068 = 0.998):** the parsed entry names
  come from one vocabulary: `MAIN`, `Describe`, `MainDataStream`,
  `Header`, `SceneGraph`, `SurfacicReps` (+ `CGRHEADER` on the 2
  variant stores). The stream records tile the end of the store body in
  origin-relative terms: per stream name a small (9-63 B) record and a
  larger (84-132 B) record on the non-variant stores; `MAIN` (132 B)
  closes the territory at dword8. Exceptions live on the 8 padded/
  variant stores: three 66-B `Describe` records, six `Header` records
  up to 210 KB, two `CGRHEADER` records (1,329/1,420 B); the
  `SurfacicReps` payload records (647 B-2.5 MB) are N7c's, not
  end-tiling records.
- **N7b (established, one-sided):** every `sp == 1` record has Y in
  84..132, inside [80, 200] (4,248/4,248); every small record and every
  `SurfacicReps` payload record is `sp == 2` (6,372 + 696). The
  per-store reading — `sp == 1` on the larger record of each stream —
  holds on non-variant stores; the 8 padded/variant stores break it
  (`sp == 2` also on 10 payload-region records, including two
  `Header` records with Y = 125, inside [80, 200]). A nested-specific
  space-flag law (the outer's sp = 1 set is
  `Cont_*`/`CATIA1`/`Format`/`CATPreview`).
- **N7c (established (observed), 1,005/1,068 = 0.941):** the catalog
  names a `SurfacicReps` stream — parsed as an entry on 696 stores
  (the walk runs past it when the following record is another
  hdr84-record), present as the unparsed record's name text on the
  rest. Where parsed, it names the store's payload region: header-less
  stores name it `[64, <catalog>)` — the whole body is one stream
  region (worked example `0e4bc645`: X = 64, Y = 38,160, origin =
  block start). Header stores' SurfacicReps record sits among the
  walk-unparsed records; its region bound is G2 work.
- **N7d (fact):** the trailer's own region `[B, B+C)` (the nested
  analog of the outer registration region) is a *stream payload
  region*: median 2,936 B, up to 5.5 MB, carrying dense numeric
  record data (not float-aligned arrays — encoding open).

Worked example (`e9ca6192a2854002`, R19, CATStdCont block 8,026,341;
verified, extends B4's): origin = 8,026,593 (block + 252), dword8 =
841,923, dword12 = 3,230; catalog at 8,868,516, container end 8,871,746
= next block 8,871,872 - 126. Parsed regions (origin-relative):
trailer region [812,056, 841,360); `MainDataStream` 9 B; `Header` 19 B;
`Describe` 88 B; `MainDataStream` 9 B; `SceneGraph` 63 B; `Header` 84
B; `SceneGraph` 132 B; `Describe` 9 B; `MAIN` 132 B ending exactly at
841,923; two 9-B gaps (one filled by the resync entry `MainDataStream`
X = 841,641 Y = 9). Full per-file map in `nested-store-streams.csv`.

## 4. The nested trailer (N6)

The last 36 bytes of the catalog tail, byte ranges (big-endian dwords):

| offset | size | field | law | rate |
|---|---|---|---|---|
| -36..-32 | 4 | A | 1 (970) / 0 (80); see below | A=1: 0.924 |
| -32..-28 | 4 | B | origin-relative region start, B < dword8 | 1,050/1,050 |
| -28..-24 | 4 | C | == D | 1,050/1,050 |
| -24..-20 | 4 | D | == C | 1,050/1,050 |
| -20..-16 | 4 | E | 0 on A=1 stores; non-zero on all 80 A=0 stores | E=0: 967/1,050 |
| -16..-12 | 4 | F | mirrors the outer generation scope | F=0: 972/1,050 |
| -12..-8 | 4 | G | == catalog tail length (dword12) | 1,050/1,050 |
| -8..0 | 8 | marker | `CB__END\0` | 1,068/1,068 within tail |

- **N6 (established laws):** the nested trailer is the outer trailer
  structure with `CB__END\0` (1,068/1,068 counting the 18 padded-tail
  stores, whose `CB__END` sits inside the zero padding),
  `C == D` (1,050/1,050) and `G == tail length` (1,050/1,050).
- **N6a (measured, interpretation open — candidate):** trailer
  `A == 0` on 80/1,050 = 0.076 of stores (all lines R18-R24, body
  >= 43,650 B), `A == 1` on 970/1,050 = 0.924. B4's worked example is
  an A = 0 store — **the exception, not the nested norm** (correction
  C2). The A = 0 stores pair exactly with `E != 0` (80/80; the 3
  remaining E != 0 stores carry A = 1 and F = 2), and `F` mirrors the
  outer trailer's generation scope one level down (F = 0 on every
  store of every bucket from R19 on — 921/921 — F = 1 concentrated on
  R15-R17 + unknown). What (A, E) mark is unknown.
- **N6r (established (negative), 1,050/1,050):** the trailer's region
  `[B, B+C)` **never** starts with a writer registration block — the
  outer trailer's region always does. The nested trailer names stream
  payload instead (N7d).

## 5. Container extent and the 126-byte tail (N3, N9)

- **N3 (established + variant):** dword8 points at the nested catalog
  exactly on 1,045/1,056 = 0.990 header stores. The 11 exceptions
  (1.0%; R16/R17 except one R20) **overshoot** it by k = 5..28 B
  (k = 13 x5, 9 x2, 28 x2, 14, 5): the catalog magic sits at
  `origin + dword8 - k`, the tail parses with dword12 as its length
  from the true magic, and the region/extent laws hold unchanged
  (regions still end at dword8, R2 exact). Correction C3.
- **N3b (established, 1,068/1,068):** the store ends at
  `catalog_start + tail length` (dword12 for header stores; the
  validated length for header-less stores) — the nested analog of law
  H1. The next valid storage block starts exactly **126 B** later on
  1,067/1,068 = 0.999 (within [1, 200] on 1,068/1,068; the one
  exception is the `CGRHEADER`-variant store `00198dd9de8caadf` at
  190). This is the same inter-block tail the outer V8 delta law
  shows, now exact at the nested level.
- **N9 (established, 1,067/1,068 = 0.999):** the 126 B carry the
  writer registration block (41 B, `[\x4d|\x4e] 11 00 00 00
  "DASSAULT-SYSTEMES" 05 00 00 00 "CATIA" 06 00 00 00 "041803"`) at
  the container end, followed by zeros to the next block.

## 6. The header-variant misses, classified (N10, correction C1)

B4's probe used a fixed 0x400 window after the block start; the corpus
shows the window must be the **block region** (next valid block /
outer dword8 / EOF): 34 R19 parts have a short CATStdCont region
followed by a `CATXDocLinkCont` block whose own region carries the
store — the 0x400 window crosses the boundary and reads the neighbour's
header (B4's `dword8`-sanity numbers absorbed them). With the
region-bounded probe (decoder's `probe_region`), B4's "5/44 misses"
become five classified families (section 1 table):

1. **header-less store** (12, R19): one store, not two — the header is
   absent and the same catalog names the `SurfacicReps` payload region
   `[64, <catalog>)`. Answers B4's "SurfacicReps-only variant — one
   store or two": one.
2. **store on the next block** (34, R19): the CATStdCont region is
   store-less; the neighbouring `CATXDocLinkCont` region carries a
   normal header store (N10 claims CSV).
3. **embedded-document catalog** (8, `unknown`): B1's distributed
   family — an outer-style catalog of an embedded document, not a
   stream store.
4. **no store in region** (63: `unknown` 58, R23 4, R16 1): regions
   without `V5_CFV2` or a validating `CB0001` (26 of them < 1,000 B).
5. **no CATStdCont block** (204): nothing to probe.

Secondary: `CATSeeBodyCont` regions carry their own nested header store
on 95/1,377 parts (R16 50, `unknown` 25, R17 6, R23 6, R21 3, R20 3,
R19 1, R15 1) — the same architecture one container over; not decoded
further here.

The decoder also defines a `header_invalid` class (header found, then
ff/zeros or catalog validation fails); it never fired on this corpus
(0/1,377 — every file lands in the families above) and is tallied as
`N10_header_invalid` so a future corpus cannot silently undercount it.

## 7. The store payload (N8)

- **N8 (established (existence), 953/1,068 = 0.892 of stores):** the
  store body (origin + 32/64 .. catalog start) carries verified
  strip-index records (B4's grammar) — the tessellation payload of
  B4's V5 claim, now tied to the decoded store. The 115 strip-less
  stores are the 63 SurfacicReps-less stores (body median 1,579 B,
  quartiles 1,071/1,579/3,629, min 635 — mostly small, but 12 exceed
  5 KB and 5 reach 73-271 KB, so size alone does not explain their
  missing strips; unknown 7) plus stores with the stream named but no
  verified strip records (B4's float64 content variant
  `086a4effaab7` among them).

## 8. Corrections to the B4 model (recorded, none massaged)

1. **C1 — probe window:** the nested probe must be bounded by the
   block region, not 0x400 B: the fixed window reads the *next*
   block's store on 34 R19 parts (CATXDocLinkCont family) and produced
   B4's container-end anomalies. `decode_nested_store.py` implements
   the region-bounded rule.
2. **C2 — nested trailer A:** B4 recorded A = 0 from its worked
   example; corpus-wide A = 0 is the minority (80/1,050 = 0.076), and
   it pairs exactly with E != 0. The A = 1 form (0.924) is the nested
   norm and matches the outer.
3. **C3 — dword8 pointer:** "nested tail magic byte-verifies at
   nested + dword8" holds on 99.0%; the 11 exceptions overshoot by
   5-28 B with everything else standard (variant, not failure).
4. **C4 — miss structure:** B4's "5 misses keep SurfacicReps in 4
   cases" generalizes to the five-family taxonomy above; the
   SurfacicReps-only files are complete header-less stores (one store,
   catalog-names-the-payload), not a second store kind.
5. **C5 — rate refresh:** V3's 39/44 = 0.886 (B4 sample) becomes
   1,056/1,173 = 0.900 header stores + 12 header-less = 0.910
   stores per CATStdCont-carrying dev part (0.776 over all dev parts,
   which include 204 parts without CATStdCont at all).

## Claims

| claim | statement | rate | label |
|---|---|---|---|
| N1 | nested stream store in the CATStdCont block region (header or header-less) | 1,068/1,173 = 0.910 of CATStdCont parts (0.776 of dev parts); per-release 0.64-1.00 (unknown 0.42) | established (observed) |
| N1h | header variant (32-B header at block + 246..322; 248..268 on 1,051/1,056) | 1,056/1,173 = 0.900 | established (observed) |
| N1l | header-less variant (origin = block start, body at +64) | 12/1,173 = 0.010, all R19 | established (observed family) |
| N2 | header layout (magic + BE dwords + ff x 8 + zeros x 8, 32 B) | 1,056/1,056 | established |
| N3 | dword8 = catalog offset (CB0001 byte-verifies at origin + dword8) | 1,045/1,056 = 0.990; overshoot k = 5..28 on 11 (0.010, else standard) | established + variant (candidate) |
| N3b | store = origin .. catalog + dword12 (nested H1); next block exactly 126 B later | delta 126 on 1,067/1,068 = 0.999 ([1,200] 1,068/1,068) | established |
| N4 | catalog = B2 outer record model (M = 86 law, cntB = cntA+1, seq from 2, accounting on clean walks) | 1,068/1,068; accounting 740/741 = 0.999 on scope | established |
| N4x | entry-0 X0 = 132 (outer 94) | 1,066/1,068 = 0.998 | established |
| N5 | X/Y relative to store origin (R2 max end == dword8; header-less min start == 64) | 1,056/1,056 and 12/12 | established |
| N6 | trailer: CB__END within tail, C == D, G == tail length | 1,068/1,068; 1,050/1,050 on cbend-at-end scope | established |
| N6a | trailer A = 0 on 80/1,050 = 0.076, pairing A = 0 <=> E != 0; F mirrors outer generation scope | A=1 0.924 | candidate (meaning open) |
| N6r | the trailer region never starts with a registration block | 0/1,050 | established (negative) |
| N7 | stream vocabulary + small-record tiling; sp == 1 <=> Y in [80, 200]; SurfacicReps named | vocabulary 0.998; sp 1,068/1,068; SurfacicReps 1,005/1,068 = 0.941 | established + observed |
| N8 | strip-index records in the store body | 953/1,068 = 0.892 of stores | established (existence) |
| N9 | 126-B tail carries the registration block at container end | 1,067/1,068 = 0.999 | established |
| N10 | miss taxonomy: headerless 12 / next-block 34 / embedded-doc 8 / none 63 / no-stdcont 204 | classification, per-release in claims CSV | established (classification) |

Version scope: N1-N10 hold on every sampled release bucket R15-R32 +
`unknown` except where a family is line-scoped (N1l and the
next-block family R19-only; embedded-doc `unknown`-only); the
per-release table is in `nested-store-claims.csv`.

## Unknowns / next questions (G2 pointers)

1. **Vertex pool location candidates** (the strip records' u16be
   indices point somewhere): (a) the unnamed bulk between origin+32/64
   and the trailer region — B4's repeating ~29.6 KB record groups; (b)
   the trailer-named region `[B, B+C)` — dense numeric record data
   (median 2.9 KB, up to 5.5 MB; not float-aligned arrays); (c) the
   SurfacicReps payload region itself. G2 should walk the bulk's
   record grammar against the strip indices.
2. The (A = 0, E != 0) trailer pairing — what the writer marks with it
   (all stores with body >= 43,650 B, but 374 A = 1 stores are as
   large — the condition is open).
3. Why the primary walk parses 9-12 records of ~12 and which variant
   record families follow (`01 82`/`01 6e ...` continuations + the
   offset-pair tables of the worked example) — the SurfacicReps
   record's region bound on header stores needs this.
4. The 11 dword8-overshoot stores (R16/R17 writer?): what the 5-28 B
   delta measures.
5. The 18 padded round-tail stores (3,072/4,096 B): why the catalog is
   zero-padded to a round dword12.
6. The 63 store-less CATStdCont regions and the 95 `CATSeeBodyCont`
   stores — second-tier container stores, undecoded.
7. Why the 12 SurfacicReps-less stores over 5 KB (5 of them 73-271 KB)
   carry no verified strip records — size alone does not explain it.

## Reproduction

```
python3 -I scripts/triage/decode_nested_store.py
```

Deterministic: file order is the sorted manifest order; three
consecutive runs produce byte-identical CSVs (md5-verified). Runtime
~2 s. Corpus binaries are not committed.
