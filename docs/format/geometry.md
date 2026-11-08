# 6. Geometry containers — CGMGeom / CATStdCont / CATCGRCont **(documented, not parsed)**

No schema v1 field touches the geometry containers; this page documents
their location, architecture and the embedded-tessellation answer (the
L3 fitness gate of ADR-0001).

Evidence: [2026-11-08-geometry-payloads.md](../evidence/2026-11-08-geometry-payloads.md)
(B4, ticket #20; verified by `scripts/triage/decode_geometry_payloads.py`;
per-file rows in `docs/evidence/data/geometry-payloads-files.csv`,
per-claim per-release rates in
`docs/evidence/data/geometry-payloads-claims.csv`, plus the regions /
zones / blocks / sigscan CSVs), building on the block model of page 5
(payload-blocks.md) and B2's tail catalog (page 2), and the B5
differential ([2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md)).

Scope: rates on an 81-file scan (44 parts, 37 products, V5R15-V5R32 +
unknown); the location map on 8 large parts (V5R18-V5R24, four
>= 100 MB). Labels follow page 5's convention. Claim IDs are the B4
note's V/G/Z claims (the differential carries the GE- prefixed rows).

## 6.1 Container cardinality and bulk holders

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-V1-cgmgeom (V1) | CGMGeom | exactly one `CGMGeom` storage block (page 5's block model) per part, none per product — 81/81 = 1.000; 1.000 on every sampled release (R19 4, R21 5 sampled parts). The CGM (exact-model) container is the part geometry anchor; block-region size 1,124 B .. 42.1 MB. | established | 81-file scan, R15-R32 + unknown |
| GE-V2-cgrcont (V2) | CATCGRCont | the `CATCGRCont` block exists in every part (44/44) but its payload region never exceeds 64 KiB (max observed 31,982 B; median ~265 B = the block plus terminator) — the CGR (graphical-representation) container is declared but empty of bulk payload in every sampled part; no bulk tessellation store is attached to the CGR-named container. | established | 44 parts |
| (CATStdCont) | CATStdCont | present in 40/44 parts and 3/37 products; block-region size 0 (absent) .. 24.7 MB. One of the two bulk containers of a large part. | established (observed) | 81-file scan |
| (other part containers) | CATSeeBodyCont, CATBRepModeContainer | `CATSeeBodyCont` in 44/44 parts (block region 758 B .. 65 KB on the deep sample), `CATBRepModeContainer` in 43/44 (~1.5 KB); none in products. | established (observed) | 81-file scan |
| GE-V8-cgm-catalog (V8) | tail catalog | the `CGMGeom` block's payload region is named by a tail-catalog region `CATStorageProperty` with `X == block_start + 244..262` (the offset varies with the block's name/GUID lengths, like the variable GUID slot) and `Y == block_region_size - (X - block_start) - 126` — the catalog names the CGM payload proper, excluding the block's ~250-byte property preamble and a ~126-byte tail before the next block. Examples: `13bb5c0c` block 172,217,066, region 8,430,068 B -> region (X = 172,217,326, Y = 8,429,682). The largest `CATStorageProperty`-named catalog regions of every deep file are exactly these CGM regions plus the CATStdCont regions. | established (deep sample, 8/8; 1/1 R19, 3/3 R21) | 8 deep files, R18-R24 |
| GE-Z1 (Z1) | entropy zones | the high-entropy geometry bulk of large parts sits in the unnamed stream territory between the property sections (attributed to `CATPrtCont` by the region rule; claimed by no tail-catalog entry), secondarily inside the `CATStdCont` block region (0.26-1.64 MB on four files). No high-entropy zone falls inside a `CGMGeom` or `CATCGRCont` block region in any deep file — the CGM region is the opposite of high-entropy (3.6-3.8 bits/byte: dense repeating record structure) and the CGR region is tiny. 84-100% of high-entropy bytes are unnamed on the four files with large high-entropy shares. | established (deep sample) | 8 deep files, R18-R24 |
| GE-V6-specificity (V6) | specificity | strip-index records (6.2) never occur inside `CGMGeom` regions — 0/44; the signature separates the two containers. Products carry no strip record, no stream store and no `CGMGeom` block. | established (negative) | 81-file scan |

Paragraph claims:

- The unnamed bulk **(candidate)**: the stream territory is a
  record-structured stream, not archive compression — a worked 256 KB
  window at 40 MB of `13bb5c0c` (entropy 7.5) carries 1,473 occurrences
  of a `b2 03`-marked record family and embedded little-endian float64
  values (e.g. 0.1 at 160 MB). Dense record + coordinate payloads
  plausibly reach 7.2-7.8 bits/byte without compression; the codec and
  record semantics are open — the largest undecoded territory (up to
  172 MB per file).

## 6.2 The nested stream store (CATStdCont / CATSeeBodyCont)

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-V3-nested (V3) | nested container | a nested `V5_CFV2` container sits in the `CATStdCont` block region (probe window: first 0x400 B after the block start): a 32-byte header (magic `56 35 5F 43 46 56 32 00`, big-endian dword8/dword12, ff x 8) whose dword8 points at a nested `CATIA_V5 CB0001\0` catalog — the same architecture as the outer file, one level down. 39/44 = 0.886 (per-release 0.67-1.00; R19 4/4, R21 5/5); the 5 misses keep the `SurfacicReps` token in 4 cases, and for one probe file the magic is absent within 0x4000 — the store has header variants (open). | established | parts of the 81-file scan |
| GE-V4-stream-names (V4) | stream names | the UTF-16 stream names (`SurfacicReps`, `SceneGraph`, `MainDataStream`, `Describe`, `Header`, `MAIN`) occur in a payload region — 41/44 = 0.932 (R19 4/4, R21 4/5). The vocabulary appears in CATStdCont regions on 62/69 of B3's sample regions and in `CATSeeBodyCont` regions on 7 files — the same store architecture one level below the body containers. | established | 81-file scan |
| (products) | products | products carry no nested store and no stream-name tokens (0/37). | established (negative) | 37 products |
| (worked example) | nested trailer | `e9ca6192a2854002` (R19 part): nested header at block + 252, dword8 = 841,923, dword12 = 3,230; the nested tail magic byte-verifies at nested + dword8 and the nested container ends 126 B before the next storage block (the same ~126 B tail the V8 delta law shows). The nested catalog (12 records, 9 parsed before a name stop) names regions `MAIN`, `Describe`, `MainDataStream`, `Header`, `SceneGraph`; the region text additionally carries the UTF-16 stream name `SurfacicReps`; the nested trailer's region (B = 812,056, C = 29,304) is the last ~29 KB stream region. The nested trailer's A = 0 here, unlike the outer trailer's constant 1 (open). | established (observed, one file) | e9ca6192a2854002 |

## 6.3 Embedded tessellation — the L3-gate answer (ADR-0001)

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-V5-strip (V5) | strip records | verified strip-index records (grammar below) inside the `CATStdCont` region — 36/44 parts = 0.818 (per-release 0.5-1.00; R19 4/4, R21 4/5; small-part misses are content density). Density scales with model content: 177,061 verified records in the 237.9 MB R24 part, 67,672 in the 375.7 MB R20 part, 24,840 in the 190.2 MB R21 part, down to single digits in small parts. All 14 release buckets R15-R32 contribute positive files — the store is a constant of the format, not a generation. | established (existence) | parts of the 81-file scan |
| GE-G1 (G1) | record grammar | strip-index record family: `01 <marker 0x41..0x4f> <type 0x01..0x0a> ff [u32le n][n x u16be values]` — markers `0x0141/0142/0143/0149/014a/014c/014f` observed; counts mostly 4-30. A record is verified when 1 <= n <= 1e6 and the record fits in the file; isolated matches outside the store are binary coincidences. Worked examples (`e9ca6192a2854002` at 8,043,557 and 8,043,617) include an index pattern zig-zagging between two ascending arcs — the shape of a closed triangle strip around an annular region, with repeated indices at the joins. The grammar is a byte-level fact; the primitive semantics (triangles vs polylines, vertex pool format) are inferred from index patterns and remain undecoded. | candidate (semantics) | grammar measured on the sample; semantics inferred |
| GE-V7 (V7) | 2-0 tags | little-endian version-like tags `[u16le t][u32le n]"2-0"` (bytes `03 00 00 00 "2-0"`) and `"2X-0"` (`04 00 00 00 "2X-0"`) inside CGMGeom regions and the adjacent bulk — `13bb5c0c` carries 1,091 + 10,910 of them, `50cd280f` 3,678 + 34,120, but only 4/44 files = 0.091: content-dependent, not a format constant. Recorded as a candidate discriminator for a future CGM-stream ticket, not a law. | candidate | 81-file scan |
| (float64 variant) | content variant | one deep file (`086a4effaab7`, R20) carries a 4.58 MB nested store of float64 coordinate data with zero verified strip records — a content variant (open: compressed or differently encoded store). | open | 086a4effaab7 |

**The L3-gate statement (ADR-0001)**: an embedded tessellated
(discretized) representation **exists for ~0.82-0.93 of parts** (rates
V4/V5) in the CATStdCont nested store (scene-graph/surfacic
representations); it is **absent in products**; it is **not** in
`CATCGRCont` (empty, V2) and **not** in `CGMGeom` (the exact-model
container). Its byte-level decode is future work (post-Phase-2; B4 open
questions 1-3).

Reproduction: `python3 -I scripts/triage/decode_geometry_payloads.py`
(~36 s; outputs the six CSVs).
