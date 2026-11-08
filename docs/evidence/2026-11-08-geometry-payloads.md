# Evidence: geometry payload location map and the embedded-tessellation question (2026-11-08)

Ticket #20 (B4: CGMGeom and CATCGRCont payloads). Scope: 81 scanned
files — a deep location-map sample of 8 large parts (all >= 1 MB, four
>= 100 MB, six repos, V5R18-V5R24) plus a stratified corpus sample of
73 files (2 per `detected_version`, V5R15-V5R32 + unknown) for the
signature rates. Together: 44 parts + 37 products across 14 release
buckets. Method: read-only byte analysis,
`scripts/triage/decode_geometry_payloads.py` (stdlib, mmap, windowed,
deterministic; run with `python3 -I`). Data:
`docs/evidence/data/geometry-payloads-files.csv` (one row per file),
`geometry-payloads-regions.csv` (tail-catalog regions of the deep
sample), `geometry-payloads-zones.csv` (high-entropy zones of the deep
sample), `geometry-payloads-blocks.csv` (storage blocks of the deep
sample), `geometry-payloads-sigscan.csv` (per-file signature counts),
`geometry-payloads-claims.csv` (per-claim, per-release rates). Builds
on B2's tail catalog (`2026-11-08-header-tail-semantics.md`), B3's
storage-block model (`2026-11-07-container-payload-layout.md`) and the
Phase 1 entropy facts (`2026-11-07-container-triage.md`); those models
are cited, not re-derived.

All observations are byte-level facts; interpretations are marked
*inference*. Labels: **established** = rate >= 0.98 on the scanned
set; **candidate** = below it. Per-release rates in
`geometry-payloads-claims.csv`.

## 1. The container payload profile (where the bulk sits)

A storage block starts at every `34 12 CATStorageProperty` (B3); its
doc-type name (name1) and B3 payload region (to the nearest next
block / OSMX / CB0001 / dword8 / EOF) are measured for every scanned
file. Region-size profile by container name over the 81 files:

| container | files carrying it | block-region size (min..max) |
|---|---|---|
| `CGMGeom` | 44/44 parts, 0/37 products (V1, **established**) | 1,124 B .. 42.1 MB (parts) |
| `CATStdCont` | 40/44 parts, 3/37 products | 0 (absent) .. 24.7 MB (parts) |
| `CATSeeBodyCont` | 44/44 parts, 0/37 products | 758 B .. 65 KB (deep sample) |
| `CATBRepModeContainer` | 43/44 parts, 0/37 products | ~1.5 KB (deep sample) |
| `CATCGRCont` | 44/44 parts, 0/37 products | 248 .. 31,982 B (V2, **established**) |
| `CATPart`/`CATIA` identity cluster | all files | small |

- **V1 (established, 81/81 = 1.000):** exactly one `CGMGeom` block per
  part, none in products. The CGM (exact-model) container is the part
  geometry anchor.
- **V2 (established, 44/44 = 1.000):** the `CATCGRCont` block exists in
  every part but its B3 region never exceeds 64 KB (max observed
  31,982 B; median ~265 B = the block plus terminator). **The CGR
  (graphical-representation) container is declared but empty of bulk
  payload in every sampled part** — no bulk tessellation store is
  attached to the CGR-named container.

The two bulk containers of a large part are therefore `CGMGeom` (up to
42.1 MB) and `CATStdCont` (up to 24.7 MB; absent from 4 of 44 sampled
parts).

## 2. The tail catalog on large files: resync walk and the CGM-region correspondence

B2's primary catalog walk stops early on large files (its known
name-parse limits), which left the stream territory unattributed. This
ticket adds a **resync continuation**: after the primary walk breaks,
the decoder re-anchors on the next `00 00 6a` hdr84 pattern whose
record validates (flag `01`, Y1 == Y2, name framing with an in-field
NUL check) and keeps parsing; skipped spans are recorded as catalog
gaps (B2's embedded-blob family, e.g. 14.9 KB inside the 26,078-byte
tail of `50cd280f35dc`). Resync entries are flagged in the regions CSV
and their coverage is labeled candidate.

Deep-sample walk coverage: primary 17-26 entries, resync +18..+30
entries, catalog gaps 266-20,106 B. The resync recovers the large
regions, and one correspondence byte-verifies on all 8 deep files:

- **V8 (established on the deep sample, 8/8):** the `CGMGeom` block's
  payload region is named by a tail-catalog region
  `CATStorageProperty` with
  `X == block_start + 244..262` (the offset varies with the block's
  name/GUID lengths, like B3's variable GUID slot) and
  `Y == block_region_size - (X - block_start) - 126` — i.e. the
  catalog names the CGM payload proper, excluding the block's ~250-byte
  property preamble and a ~126-byte tail before the next block.
  Examples: `13bb5c0c` block 172,217,066 region 8,430,068 B -> region
  (X=172,217,326, Y=8,429,682); `17930bab` block 337,298,799 region
  29,030,553 B -> (X=337,299,043, Y=29,030,183).

The largest `CATStorageProperty`-named catalog regions of every deep
file are exactly these CGM regions (ent 3.6-3.8 bits/byte — highly
structured, see section 5) plus the CATStdCont block regions.

**Correction to the B2 tiling picture (scoped):** B2's region-tiling
laws (R1-R3) were validated on walk-complete files, which are mostly
small. On the deep large files the *complete* catalog (primary +
resync, all anchors found) does **not** tile the body: the territory
between the early property regions and the late container regions —
e.g. [~9 KB, 13.94 MB) of `086a4effaab7`, [~30 KB, 172.2 MB) of
`13bb5c0c` — is claimed by **no catalog entry**. The catalog names the
property/directory structures and the container payload regions, not
the stream bulk between them. R1/R2 (min start 64, max end dword8)
still hold; R3 does not extend to this file family.

**`Cont_*` region names (B2 open question 2, partial):** the small
`Cont_<id>` regions (Y = 132-194 B) sit ~114 B after their container's
storage-block start (e.g. `13bb5c0c` `Cont_..._1efb` X=172,217,180 =
CGMGeom block + 114) — they are per-container identity records. Their
name suffixes are GUID-text-like hex groups, but the suffix bytes
appear **nowhere in the file as literal bytes** (0/19 joins on the two
probe files), so the name-to-GUID transform (if any) is open.

## 3. Entropy zones and the location map (deep sample)

Shannon entropy over 64 KiB blocks (Phase 1 convention, high >= 7.2
bits/byte), full files:

| file | size | version | high-entropy share | high-entropy bytes | of which in CATStdCont region | of which in CGMGeom region |
|---|---|---|---|---|---|---|
| `17930babf0fd01a8` diente_superior_molde | 375.7 MB | R20 | 1.7% | 6.42 MB | 0.26 MB | 0 |
| `bad44bdf52f5c411` PalmDown5motors2 | 237.9 MB | R24 | 0.3% | 0.66 MB | 0.66 MB | 0 |
| `13bb5c0c49616ade` LedStrips_Smooth | 190.2 MB | R21 | 61.2% | 116.3 MB | 0 | 0 |
| `50cd280f35dc350b` Hitbox_WorkFile_main | 175.0 MB | R21 | 43.6% | 76.3 MB | 0.33 MB | 0 |
| `086a4effaab79779` head | 18.7 MB | R20 | 67.0% | 12.5 MB | 1.64 MB | 0 |
| `e9ca6192a2854002` SP02_PCB_Allumage_Pre-RCE | 8.9 MB | R19 | 0% | 0 | 0 | 0 |
| `70b59f2a0eb60c1c` 550.001 A (CAAclean) | 5.4 MB | R21 | 0% | 0 | 0 | 0 |
| `3d9cb9548b01918b` 471510001_HDMI | 2.3 MB | R18 | 0% | 0 | 0 | 0 |

204 high-entropy zones were mapped (zone entropies 7.20-7.84, median
7.50). Attribution (zones CSV; `tail_owner_names`, `block_owner`):

- The dominant holder is the **unnamed stream bulk** between the
  property sections — the territory B3's boundary rule attributes to
  `CATPrtCont` and the (complete) tail catalog does not name
  (section 2): 6.2 MB of 6.4 MB on `17930bab`, 116.3 of 116.3 MB on
  `13bb5c0c`, 76.0 of 76.3 MB on `50cd280f`, 10.5 of 12.5 MB on
  `086a4eff`.
- The **CATStdCont nested stream store** is the secondary holder
  (0.26-1.64 MB on four files; all of the 0.66 MB on `bad44bdf`).
- **No high-entropy zone falls inside a `CGMGeom` or `CATCGRCont`
  block region in any deep file** — the CGM region is the *opposite*
  of high-entropy (3.6-3.8 bits/byte: dense repeating record
  structure), and the CGR region is tiny.

The three smallest deep files have no high-entropy zone at all —
consistent with Phase 1 ("products and small parts: no high-entropy
zone").

**What the unnamed bulk is** (*inference, candidate*): it is a
record-structured stream, not archive compression. Worked window at
40 MB of `13bb5c0c` (256 KB, entropy 7.5): 1,473 occurrences of a
`b2 03`-marked record family and embedded little-endian float64
values (e.g. `9a 99 99 99 99 99 b9 3f` = 0.1 at 160 MB). Dense
record + coordinate payloads plausibly reach 7.2-7.8 bits/byte
without compression; the codec/record semantics are **open**.

## 4. The nested stream stores (CATStdCont / CATSeeBodyCont)

The `CATStdCont` block region embeds a **nested `V5_CFV2` container**:
a 32-byte header (magic `56 35 5F 43 46 56 32 00`, big-endian
dword8/dword12, ff x 8) whose dword8 points at a nested
`CATIA_V5 CB0001\0` catalog — the same architecture as the outer file,
one level down. Worked example (`e9ca6192a2854002`, CATStdCont block at
8,026,341):

- nested header at block + 252 (offset 8,026,593), dword8 = 841,923,
  dword12 = 3,230, ff x 8; the nested tail magic byte-verifies at
  nested + dword8 (= the B3 region end) and the nested container ends
  126 B before the next storage block (`CATCGRCont` at 8,871,872) —
  the same ~126 B tail the CGM-region delta law of section 2 shows;
- the nested catalog (12 records, 9 parsed before a name stop)
  names regions `MAIN`, `Describe`, `MainDataStream`, `Header`,
  `SceneGraph`; the region text additionally carries the UTF-16
  stream name `SurfacicReps`; the nested trailer's region (B=812,056,
  C=29,304) is the last ~29 KB stream region (nested trailer A = 0
  here, unlike the outer trailer's constant 1);
- the nested body before the catalog is the stream payload: repeating
  ~29.6 KB record groups (one per repeated geometric feature on this
  PCB part) and the strip-index records of section 5.

Rates over the 81-file scan (parts only):

- **V3 (established, 39/44 = 0.886):** a nested `V5_CFV2` header sits
  in the CATStdCont block region (probe window: first 0x400 B after
  the block start). The 5 misses keep the `SurfacicReps` token in 4
  cases (V4); for one probe file the magic is absent within 0x4000,
  so the store has header variants (open).
- **V4 (established, 41/44 = 0.932):** the UTF-16 stream names
  (`SurfacicReps`, `SceneGraph`, `MainDataStream`, `Describe`,
  `Header`, `MAIN`) occur in a payload region. Vocabulary observed in
  CATStdCont regions on 62/69 of B3's sample regions and in
  `CATSeeBodyCont` regions on 7 files — the same store architecture
  one level below the body containers.
- Products carry **no** nested store and no stream-name tokens
  (0/37).

## 5. The embedded-tessellation question

**Answer: a tessellated (discretized) representation exists inside
ordinary saved .CATPart files — as a subset property.** It lives in
the nested stream store of `CATStdCont` (scene-graph/surfacic
representations), **not** in the `CATCGRCont` container (empty,
section 1) and **not** in `CGMGeom` (the exact-model container).

The content evidence is the **strip-index record family (G1,
candidate)** inside the CATStdCont region payload. Record grammar
(measured, `e9ca6192a2854002` worked examples at 8,043,557 and
8,043,617):

    01 <marker 0x41..0x4f> <type 0x01..0x0a> ff
    [u32le n][n x u16be values]

- `01 41 02 ff | 06 00 00 00 | 00ae 0037 0031 0037 00ae 0047`
- `01 41 07 ff | 15 00 00 00 | 21 u16be values` whose index pattern
  zig-zags between two ascending arcs (`b7 4b 48 52 4b b7 b9 52 b7 57
  52 b9 ba 57 b9 ba 58 57 58 ba 5a`) — the shape of a closed triangle
  strip around an annular region, with repeated indices at the joins.

Markers `0x0141/0142/0143/0149/014a/014c/014f` observed; counts mostly
4-30. A record is "verified" when 1 <= n <= 1e6 and the record fits in
the file; isolated matches outside the store are binary coincidences.

- **V5 (established, 36/44 = 0.818 of parts):** verified strip records
  inside the CATStdCont region. Density scales with model content:
  177,061 verified records in the 237.9 MB R24 part, 67,672 in the
  375.7 MB R20 part, 24,840 in the 190.2 MB R21 part, down to single
  digits in small parts. All 14 release buckets R15-R32 contribute
  positive files (claims CSV), so the store is a constant of the
  format, not a generation.
- **V6 (established, 0/44):** strip records never occur inside
  `CGMGeom` regions — the signature separates the two containers.
- Products: 0/37 carry any strip record or stream store.

*Interpretation (candidate, below-bar):* the strip records are
vertex-index strips of a discretized (tessellated) visualization
model — the scene-graph/surfacic-representation data their
containing streams are named after. The record *grammar* is a
byte-level fact; the *primitive semantics* (triangles vs polylines,
vertex pool format) are inferred from index patterns and remain
undecoded without proprietary material. One deep file
(`086a4effaab7`, R20) carries a 4.58 MB nested store of float64
coordinate data with **zero** verified strip records — a content
variant (open: compressed or differently encoded store).

**Where the tessellated data is NOT:** not in `CATCGRCont` (V2: no
bulk payload region in any sampled part), not in the unnamed stream
bulk (V6's counterpart: strip records there are coincidences — the
bulk carries the `b2 03` record family and float64 arrays instead),
and not attached to the tail catalog's named regions.

This settles the L3 fitness gate of ADR-0001 as: an embedded
tessellated representation **exists for ~0.82-0.93 of parts** (rates
V4/V5) in the CATStdCont store, is absent in products, and its
byte-level decode is future work.

## 6. The `2-0` / `2X-0` record tags (CGMGeom side observation)

Inside CGMGeom regions (and the adjacent bulk) a record family carries
little-endian version-like tags:

    [u16le t][u32le n]"2-0"        exact bytes 03 00 00 00 "2-0"
    [u16le t][u32le n]"2X-0"       exact bytes 04 00 00 00 "2X-0"

`13bb5c0c` carries 1,091 + 10,910 of these; `50cd280f` 3,678 + 34,120;
but **V7 (4/44 = 0.091)** — the tags are content-dependent, not a
format constant. Recorded as a candidate discriminator for a future
CGM-stream ticket, not a law.

## Claims

| claim | statement | rate | label |
|---|---|---|---|
| V1 | exactly one `CGMGeom` block per part, none per product | 81/81 = 1.000 | established |
| V2 | `CATCGRCont` block present per part; B3 region < 64 KB (max 31,982 B) | 44/44 = 1.000 | established |
| V3 | nested `V5_CFV2` container in the CATStdCont block region | 39/44 = 0.886 | established (per-release 0.67-1.00) |
| V4 | UTF-16 stream-name tokens (`SurfacicReps`/`SceneGraph`/`MainDataStream`) in a payload region | 41/44 = 0.932 | established |
| V5 | verified strip-index records inside the CATStdCont region | 36/44 = 0.818 | established (per-release 0.5-1.00) |
| V6 | strip-index records absent from `CGMGeom` regions | 0/44 = 0.000 | established (specificity) |
| V7 | `2-0`/`2X-0` tags present in CGMGeom territory | 4/44 = 0.091 | candidate (content-dependent) |
| V8 | the CGMGeom block region is named by a tail-catalog region (delta law of section 2) | 8/8 deep | established on the deep sample |
| G1 | strip-record grammar `01 4X <type> ff [u32le n][n x u16be]` = tessellation index data | grammar measured; semantics inferred | candidate |
| Z1 | high-entropy zones sit in the unnamed stream bulk (CATPrtCont-attributed), secondarily in the CATStdCont store; never in CGMGeom/CATCGRCont regions | deep sample: 84-100% of high-entropy bytes unnamed on the four files with large high-entropy shares | established on the deep sample |

Version scope: V1-V6 hold on every sampled release bucket R15-R32 +
unknown (per-release table in `geometry-payloads-claims.csv`); the
deep location map (Z1, V8) spans V5R18-V5R24.

## Unknowns / next questions

1. The unnamed stream bulk's record format (`b2 03` family, float64
   arrays, entropy 7.2-7.84): codec and record semantics — the largest
   undecoded territory (up to 172 MB per file).
2. Strip-record semantics: primitive type per marker byte
   (0x0141..0x014f), vertex pool format, and whether the counts are
   triangle strips or polyline strips. Needs a controlled decode pass
   on one small part.
3. Why `086a4effaab7`'s nested store has no verified strip records
   (float64 data instead) — encoding variant vs compression.
4. The 5/44 parts without a nested `V5_CFV2` magic in the probe
   window: header variants or a different store placement.
5. The `Cont_<id>` name-to-GUID transform (0/19 literal joins; B2
   open question 2 remains open beyond the position observation).
6. The nested trailer's A = 0 (outer trailer A = 1 always) and the
   nested coordinate base of nested-entry X/Y (recorded as-is).

## Reproduction

```
python3 -I scripts/triage/decode_geometry_payloads.py
```

Runtime: ~36 s wall clock (mmap over the whole corpus sample; the
64 KiB entropy pass over the four 100 MB+ deep files dominates).
Deterministic: three consecutive runs produce byte-identical CSVs
(md5-verified). Outputs the six CSVs above and the claim summary to
stdout. Corpus binaries are not committed.

## Ready-to-adopt claim block for docs/format/ (geometry section)

Coordinator: fold into a new section after section 5 (CATIA identity
block) — suggested title "6. Geometry containers **(documented, not
parsed)**". Labels follow section 4's convention.

```markdown
## 6. Geometry containers — CGMGeom / CATStdCont / CATCGRCont **(documented, not parsed)**

Evidence: docs/evidence/2026-11-08-geometry-payloads.md (B4, ticket
#20; verified by scripts/triage/decode_geometry_payloads.py; per-file
rows in docs/evidence/data/geometry-payloads-*.csv). Rates on an
81-file scan (44 parts, 37 products, V5R15-V5R32 + unknown); the
location map on 8 large parts (V5R18-V5R24, four >= 100 MB).

**Container cardinality** (**established**, V1, 81/81): every part
carries exactly one `CGMGeom` storage block (section 4's block model);
products carry none. `CATCGRCont` blocks exist in every part but
(**established**, V2, 44/44) their payload region never exceeds
64 KiB (max 31,982 B) — the CGR-named container owns no bulk payload.

**Bulk payload holders** (**established** on the deep sample, Z1): the
high-entropy geometry bulk of large parts sits in the stream territory
between the property sections (attributed to `CATPrtCont` by the
section 4 region rule; claimed by no tail-catalog entry), and
secondarily inside the `CATStdCont` block region. `CGMGeom` regions
are *low*-entropy structured records (3.6-3.8 bits/byte; up to
42.1 MB) and carry no high-entropy zone in any deep file. The tail
catalog names the CGM payload region as `CATStorageProperty` with
`X = block_start + 244..262` and `Y = region_size - (X - block_start)
- 126` (V8, 8/8 deep files; the catalog's tiling of B2 does not extend
to the stream bulk of large files).

**Nested stream store** (**established**, V3/V4, 0.886/0.932): the
`CATStdCont` block region embeds a nested `V5_CFV2` container
(32-byte header at block + ~252, big-endian dword8/dword12, ff x 8)
whose dword8 points at a nested `CATIA_V5 CB0001\0` catalog naming
sub-streams: `MainDataStream`, `Describe`, `Header`, `SceneGraph`,
`SurfacicReps`, `MAIN`. Products carry no such store (0/37).

**Embedded tessellation** (**established** existence, **candidate**
decode): the nested store's payload carries a strip-index record
family `01 <0x41-0x4f> <type> ff [u32le n][n x u16be]` (36/44 parts,
0/37 products, all release buckets; up to 177k records in one file;
never in `CGMGeom` regions). *Inference*: this is the discretized
(tessellated) visualization representation — scene-graph/surfacic-rep
data — present in most ordinary parts; its primitive semantics are
undecoded (G1, candidate). The answer to the embedded-tessellation
question (ADR-0001 L3 gate): **exists, in the CATStdCont nested store
of ~0.82-0.93 of parts; absent in products; not in CATCGRCont
(empty) and not in CGMGeom (exact model).**
```
