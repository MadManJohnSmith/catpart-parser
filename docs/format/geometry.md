# 6. Geometry containers — CGMGeom / CATStdCont / CATCGRCont **(documented, not parsed)**

No schema v1 field touches the geometry containers; this page documents
their location, architecture and the embedded-tessellation answer (the
L3 fitness gate of ADR-0001).

Evidence: [2026-11-08-geometry-payloads.md](../evidence/2026-11-08-geometry-payloads.md)
(B4, ticket #20; verified by `scripts/triage/decode_geometry_payloads.py`;
per-file rows in `docs/evidence/data/geometry-payloads-files.csv`,
per-claim per-release rates in
`docs/evidence/data/geometry-payloads-claims.csv`, plus the regions /
zones / blocks / sigscan CSVs), the G1 corpus-wide nested-store decode
([2026-11-09-nested-store.md](../evidence/2026-11-09-nested-store.md),
ticket #29; verified by `scripts/triage/decode_nested_store.py`;
per-file / per-store / per-region / per-claim rows in
`docs/evidence/data/nested-store-*.csv`), building on the block model
of page 5 (payload-blocks.md) and B2's tail catalog (page 2), and the
B5 differential ([2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md)).

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

Evidence: B4's discovery scan (first table row keeps its sample rate
for history) and the G1 corpus-wide decode —
[2026-11-09-nested-store.md](../evidence/2026-11-09-nested-store.md)
(ticket #29; verified by `scripts/triage/decode_nested_store.py`;
per-file rows in `docs/evidence/data/nested-store-files.csv`,
per-store rows in `nested-store-regions.csv`, per-region rows in
`nested-store-streams.csv`, per-claim per-release rates in
`nested-store-claims.csv`). G1 scope: all 1,377 dev parts
(`split=dev` — every repo except the Motor-V6 holdout), so rates are
corpus-wide; per-line n is the actual manifest count (R25/R28/R32
n = 1, R26 n = 2). The nested store is the outer file architecture one
level down: same header generation marker, same B2 catalog record
model and stop behavior, same 36-B `CB__END` trailer, same 126-B
inter-block tail — with four measured deltas (entry-0 X0 = 132,
trailer A/E pairing, no registration block in the trailer region, and
two header variants).

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-V3-nested (V3, N1) | nested container | a nested stream store sits in the `CATStdCont` block region of 1,068/1,173 = 0.910 CATStdCont-carrying dev parts (0.776 of all dev parts; 204 parts carry no CATStdCont block): a header variant (1,056 = 0.900, every release line R15-R32 + unknown; per-release store rate among CATStdCont parts 0.64 (R23) - 1.00) and a header-less variant (12, R19 only). B4's sample rate 39/44 = 0.886 is refreshed by the G1 note's correction C5. Products carry no such store (0/37, B4). | established (observed) | dev parts, R15-R32 + unknown |
| GE-N2-header (N2) | nested header | 32-byte header at the store origin (block + 248..268, mode 252): [0:8] magic `56 35 5F 43 46 56 32 00` (`V5_CFV2\0` — the outer header's own magic), [8:12] dword8 big-endian = catalog offset, [12:16] dword12 big-endian = catalog tail length, [16:24] `ff` x 8, [24:32] zeros x 8 — the outer header truncated to 32 B. 1,056/1,056. | established | header stores |
| GE-N3-pointer (N3) | dword8 pointer | the nested `CATIA_V5 CB0001\0` catalog byte-verifies at origin + dword8 on 1,045/1,056 = 0.990 header stores; 11 (R16/R17 + one R20) overshoot by k = 5..28 B with every other law unchanged (regions still origin-relative, the tail parses with dword12 length) — a pointer variant, not a model failure (G1 correction C3). | established + variant (candidate) | header stores |
| GE-N3b-extent (N3b) | container extent | the store ends at catalog_start + dword12 (the nested H1 analog) and the next valid storage block starts exactly 126 B later — 1,067/1,068 = 0.999 exact ([1, 200] on 1,068/1,068; the exception is the CGRHEADER-variant store at 190). The 126 B carry the writer registration block (41 B) at the container end followed by zeros (N9, 1,067/1,068) — the same inter-block tail the V8 delta law shows, now exact. | established | decoded stores |
| GE-N4-catalog (N4) | nested catalog | B2's outer tail record model one level down, unchanged: entry-0 M-law with M = 86 (1,068/1,068), cntB == cntA + 1 (1,067/1,068), seq from 2 (1,068/1,068), hdr84 + xrec13 + fil87 + UTF-16 name records (11,321 primary entries); the primary walk stops at B2's known name-stop condition (the outer tail of the same files breaks identically) and B4's resync applies; B2's exact length accounting holds on 740/741 clean-walk stores. Entry-0 X0 = 132 (outer 94; 1,066/1,068 — two CGRHEADER-variant stores carry 110). Variants: 18 `unknown`-release stores zero-pad the catalog to a round dword12 (3,072/4,096) — `CB__END` inside the tail, the G law off by the padding. | established | decoded stores |
| GE-N5-coords (N5) | coordinate base | catalog entry X/Y are relative to the store origin (the `V5_CFV2` magic; the block start for the header-less variant) — B4 open question 6 answered: header stores end their last named region exactly at origin + dword8 (1,056/1,056, R2 exact); header-less stores tile [64, catalog) with min region start 64 (12/12); the trailer's B is origin-relative too. | established | decoded stores |
| GE-V4-stream-names (V4, N7) | stream names | the catalog names the stream regions from one vocabulary — `MAIN`, `Describe`, `MainDataStream`, `Header`, `SceneGraph`, `SurfacicReps` (+ `CGRHEADER` on 2 variant stores) — as small records (9-63 B) plus a larger record per stream (84-132 B) tiling the end of the body; `sp == 1` exactly on the larger records (Y in [80, 200], 1,068/1,068 one-sided — a nested-specific space-flag law). A `SurfacicReps` stream is named on 1,005/1,068 = 0.941 stores (parsed entry on 696, name text otherwise); where parsed it names the store's payload region. B4's token-level claim (41/44) is refreshed corpus-wide. | established | decoded stores |
| GE-N6-trailer (N6) | nested trailer | the catalog ends with `CB__END\0` within the tail (1,068/1,068; at the tail end on 1,050 — 18 padded stores carry it inside zero padding) with C == D (1,050/1,050) and G == tail length (1,050/1,050); the trailer's region `[B, B+C)` never starts with a writer registration block (0/1,050 — the outer's always does; it names stream payload instead, median 2,936 B, up to 5.5 MB). | established (negative) | decoded stores |
| GE-N6a-AE (N6a) | trailer A/E/F | trailer A = 1 on 970/1,050 = 0.924, A = 0 on 80/1,050 = 0.076 (all lines R18-R24, body >= 43,650 B) — B4's worked example is an A = 0 store, the exception not the norm (G1 correction C2). A = 0 pairs exactly with E != 0 (80/80; the 3 remaining E != 0 stores carry A = 1 and F = 2), and F mirrors the outer trailer's generation scope (F = 0 on every store from R19 on, 921/921; F = 1 on R15-R17 + unknown). What (A, E) mark is open. | candidate (laws measured, meaning open) | decoded stores |
| GE-N10-variants (N10) | header variants | the parts without a probe-window header classify into: header-less stores (12, R19 — one store, the same catalog naming the `SurfacicReps` payload `[64, <catalog>)`); stores on the next block (34, R19 — a `CATXDocLinkCont` neighbour carries a normal header store; B4's 0x400 probe window crossed the region boundary, G1 correction C1); embedded-document catalogs (8, `unknown` — B1's distributed family, entry-0 X0 = 94, not a stream store); no store in region (63: unknown 58, R23 4, R16 1); no CATStdCont block (204). `CATSeeBodyCont` regions carry their own header store on 95 parts. Answers B4 open question 4 and the "one store or two" question: one. | established (classification) | dev parts |
| GE-N8-strip (N8) | payload tie-in | the store body (origin + 32/64 .. catalog start) carries B4's verified strip-index records on 953/1,068 = 0.892 of stores — the tessellation payload tied to the decoded store; the 115 strip-less stores are the small SurfacicReps-less ones plus content variants (B4's float64 store among them). | established (existence) | decoded stores |
| (products) | products | products carry no nested store and no stream-name tokens (0/37). | established (negative) | 37 products |
| (worked example) | nested store | `e9ca6192a2854002` (R19 part): origin at block + 252, dword8 = 841,923, dword12 = 3,230; catalog at 8,868,516; container end 8,871,746 = next block - 126; trailer (A = 0, B = 812,056, C = 29,304, G = 3,230) — one of the A = 0 / E != 0 stores. Parsed regions tile [812,056, 841,923) origin-relative: the trailer region plus `MAIN`/`Describe`/`MainDataStream`/`Header`/`SceneGraph` records (9-132 B), the last region ending exactly at dword8, two 9-B gaps (one filled by the resync entry); the catalog text additionally carries the UTF-16 stream name `SurfacicReps` (its record is one of the walk-unparsed ones). | established (observed, one file) | e9ca6192a2854002 |

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
