# 6. Geometry containers — CGMGeom / CATStdCont / CATCGRCont **(partially parsed)**

The L1 schema (`catpart-inspect`, schema v1) still emits no geometry
field; the geometry-touching schema is G4's `export-summary-v1.json`
(`src/catpart/schema/export-summary-v1.json`, #32), written by
`catpart-export` from the decoded nested store (6.2-6.3.1). This page
documents the containers' location, architecture, the decoded
store/pool/facet model and the embedded-tessellation answer (the L3
fitness gate of ADR-0001); what stays undecoded is named in the claims
below (the composite index space, GE-F8, and the 0x44/0x49/0x4b/0x4e
families).

Evidence: [2026-11-08-geometry-payloads.md](../evidence/2026-11-08-geometry-payloads.md)
(B4, ticket #20; verified by `scripts/triage/decode_geometry_payloads.py`;
per-file rows in `docs/evidence/data/geometry-payloads-files.csv`,
per-claim per-release rates in
`docs/evidence/data/geometry-payloads-claims.csv`, plus the regions /
zones / blocks / sigscan CSVs), the G1 corpus-wide nested-store decode
([2026-11-09-nested-store.md](../evidence/2026-11-09-nested-store.md),
ticket #29; verified by `scripts/triage/decode_nested_store.py`;
per-file / per-store / per-region / per-claim rows in
`docs/evidence/data/nested-store-*.csv`), the G2 vertex-pool decode
([2026-11-09-vertex-pool.md](../evidence/2026-11-09-vertex-pool.md),
ticket #30; verified by `scripts/triage/decode_vertex_pool.py`;
per-file / per-pool-group / per-claim rows in
`docs/evidence/data/vertex-pool-*.csv`), building on the block model
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
| GE-N2-header (N2) | nested header | 32-byte header at the store origin (block + 246..322, mode 252; 248..268 on 1,051/1,056 — outliers are the padded/variant stores and one R20 store at 246): [0:8] magic `56 35 5F 43 46 56 32 00` (`V5_CFV2\0` — the outer header's own magic), [8:12] dword8 big-endian = catalog offset, [12:16] dword12 big-endian = catalog tail length, [16:24] `ff` x 8, [24:32] zeros x 8 — the outer header truncated to 32 B. 1,056/1,056. | established | header stores |
| GE-N3-pointer (N3) | dword8 pointer | the nested `CATIA_V5 CB0001\0` catalog byte-verifies at origin + dword8 on 1,045/1,056 = 0.990 header stores; 11 (R16/R17 + one R20) overshoot by k = 5..28 B with every other law unchanged (regions still origin-relative, the tail parses with dword12 length) — a pointer variant, not a model failure (G1 correction C3). | established + variant (candidate) | header stores |
| GE-N3b-extent (N3b) | container extent | the store ends at catalog_start + dword12 (the nested H1 analog) and the next valid storage block starts exactly 126 B later — 1,067/1,068 = 0.999 exact ([1, 200] on 1,068/1,068; the exception is the CGRHEADER-variant store at 190). The 126 B carry the writer registration block (41 B) at the container end followed by zeros (N9, 1,067/1,068) — the same inter-block tail the V8 delta law shows, now exact. | established | decoded stores |
| GE-N4-catalog (N4) | nested catalog | B2's outer tail record model one level down, unchanged: entry-0 M-law with M = 86 (1,068/1,068), cntB == cntA + 1 (1,067/1,068), seq from 2 (1,068/1,068), hdr84 + xrec13 + fil87 + UTF-16 name records (11,321 primary entries); the primary walk stops at B2's known name-stop condition (the outer tail of the same files breaks identically) and B4's resync applies; B2's exact length accounting holds on 740/741 clean-walk stores. Entry-0 X0 = 132 (outer 94; 1,066/1,068 — two CGRHEADER-variant stores carry 110). Variants: 18 `unknown`-release stores zero-pad the catalog to a round dword12 (3,072/4,096) — `CB__END` inside the tail, the G law off by the padding. | established | decoded stores |
| GE-N5-coords (N5) | coordinate base | catalog entry X/Y are relative to the store origin (the `V5_CFV2` magic; the block start for the header-less variant) — B4 open question 6 answered: header stores end their last named region exactly at origin + dword8 (1,056/1,056, R2 exact); header-less stores tile [64, catalog) with min region start 64 (12/12); the trailer's B is origin-relative too. | established | decoded stores |
| GE-V4-stream-names (V4, N7) | stream names | the catalog names the stream regions from one vocabulary — `MAIN`, `Describe`, `MainDataStream`, `Header`, `SceneGraph`, `SurfacicReps` (+ `CGRHEADER` on 2 variant stores) — as small records (9-63 B) plus a larger record per stream (84-132 B) tiling the end of the body on non-variant stores (the 8 padded/variant stores carry larger payload-region records, up to 210 KB, `sp == 2`); every `sp == 1` record has Y in [80, 200] (4,248/4,248 one-sided — a nested-specific space-flag law). A `SurfacicReps` stream is named on 1,005/1,068 = 0.941 stores (parsed entry on 696, name text otherwise); where parsed it names the store's payload region. B4's token-level claim (41/44) is refreshed corpus-wide. | established | decoded stores |
| GE-N6-trailer (N6) | nested trailer | the catalog ends with `CB__END\0` within the tail (1,068/1,068; at the tail end on 1,050 — 18 padded stores carry it inside zero padding) with C == D (1,050/1,050) and G == tail length (1,050/1,050); the trailer's region `[B, B+C)` never starts with a writer registration block (0/1,050 — the outer's always does; it names stream payload instead, median 2,936 B, up to 5.5 MB). | established (negative) | decoded stores |
| GE-N6a-AE (N6a) | trailer A/E/F | trailer A = 1 on 970/1,050 = 0.924, A = 0 on 80/1,050 = 0.076 (all lines R18-R24, body >= 43,650 B) — B4's worked example is an A = 0 store, the exception not the norm (G1 correction C2). A = 0 pairs exactly with E != 0 (80/80; the 3 remaining E != 0 stores carry A = 1 and F = 2), and F mirrors the outer trailer's generation scope (F = 0 on every store from R19 on, 921/921; F = 1 concentrated on R15-R18 + unknown, 75 total — one on R18). What (A, E) mark is open. | candidate (laws measured, meaning open) | decoded stores |
| GE-N10-variants (N10) | header variants | the parts without a probe-window header classify into: header-less stores (12, R19 — one store, the same catalog naming the `SurfacicReps` payload `[64, <catalog>)`); stores on the next block (34, R19 — a `CATXDocLinkCont` neighbour carries a normal header store; B4's 0x400 probe window crossed the region boundary, G1 correction C1); embedded-document catalogs (8, `unknown` — B1's distributed family, entry-0 X0 = 94, not a stream store); no store in region (63: unknown 58, R23 4, R16 1); no CATStdCont block (204). `CATSeeBodyCont` regions carry their own header store on 95 parts. Answers B4 open question 4 and the "one store or two" question: one. | established (classification) | dev parts |
| GE-N8-strip (N8) | payload tie-in | the store body (origin + 32/64 .. catalog start) carries B4's verified strip-index records on 953/1,068 = 0.892 of stores — the tessellation payload tied to the decoded store; the 115 strip-less stores are the mostly-small SurfacicReps-less ones (body median 1,579 B, 12 over 5 KB) plus content variants (B4's float64 store among them). | established (existence) | decoded stores |
| (products) | products | products carry no nested store and no stream-name tokens (0/37). | established (negative) | 37 products |
| (worked example) | nested store | `e9ca6192a2854002` (R19 part): origin at block + 252, dword8 = 841,923, dword12 = 3,230; catalog at 8,868,516; container end 8,871,746 = next block - 126; trailer (A = 0, B = 812,056, C = 29,304, G = 3,230) — one of the A = 0 / E != 0 stores. Parsed regions tile [812,056, 841,923) origin-relative: the trailer region plus `MAIN`/`Describe`/`MainDataStream`/`Header`/`SceneGraph` records (9-132 B), the last region ending exactly at dword8, two 9-B gaps (one filled by the resync entry); the catalog text additionally carries the UTF-16 stream name `SurfacicReps` (its record is one of the walk-unparsed ones). | established (observed, one file) | e9ca6192a2854002 |

### 6.2.1 The vertex pool (G2)

Evidence: the G2 corpus-wide decode
([2026-11-09-vertex-pool.md](../evidence/2026-11-09-vertex-pool.md),
ticket #30; verified by `scripts/triage/decode_vertex_pool.py`;
per-file rows in `docs/evidence/data/vertex-pool-files.csv`,
per-pool-group rows in `vertex-pool-pools.csv`, per-claim per-release
rates in `vertex-pool-claims.csv`). Scope: all 1,377 dev parts
(corpus-wide; per-release n is the actual manifest count).

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-P1-pool (P1) | pool location | the strip records' indices point into runs of 15-byte vertex records `[05 08 01][f32le x][f32le y][f32le z]` inside pool groups of the store body: a wrapper `10 24 04 ff ff 00 00 00` + `01 06` + a vertex count (one byte, `ff` escaping to a u32le count) followed by exactly that many vertex records. 995/1,377 = 0.723 dev parts carry pool groups (2,090 groups, 493,775 vertices; every release line positive). The trailer-named region `[B, B+C)` is NOT the pool — it carries edge/curve geometry records (a `P Q P` pattern of f32le triples with a trailing f32le length equal to the norm of the middle triple, on the small-store worked example — semantics partly open) plus an increasing u32le offset directory. | established (observed) | dev parts, R15-R32 + unknown |
| GE-P2-count (P2/P2g) | count law | the walked vertex-record count equals the group's count field on every decoded group — 2,090/2,090 = 1.000; the count field is a true vertex count. | established | decoded pool groups |
| GE-P3-f32 (P3) | float format | vertex coordinates are little-endian float32 xyz triplets, interleaved per record, 100% finite (2,090/2,090 groups; no f16/f64 pool vertices observed). | established | decoded pool groups |
| GE-P4-scale (P4/P9) | magnitude | coordinates plausible mm-scale (all components <= 1e5 in absolute value) on 2,033/2,090 = 0.973 groups and 970/995 = 0.975 parts (median max coordinate magnitude 55, p90 1,500, max 2.3e5) — the 2.5% tail (110-230 m-scale parts) keeps the unit question open; no unit field decoded. | candidate (unit assumption) | decoded pools |
| GE-P5-facet (P5/P6) | facet grammar | the connectivity records refine B4's grammar into families: 0x41 triangle lists (n == 3*type, no normal), 0x49 triangles with a 12-byte f32le unit normal, 0x42 boundary loops without normal, 0x4a/0x4c boundary loops with normal; loop-count u8 bytes precede the indices and sum to n; index width is u8 on every facet the committed decoder accepts corpus-wide (a manual probe reads larger pools as u16be — per-group width/binding is open question 1 of the G2 note). Normals carry fixed epsilon bit patterns for near-zero components (`00 00 00 a5` = -1.11e-16, `32 31 0d 25` = 1.225e-16 as f32le — normal-range magnitudes, not subnormals). Facet indices are local to their pool group; on single-pool-group stores the functional test is exact (all indices < count); on pool-less stores a grammar-shape accept counts as unresolved, never strict. Corpus-wide 612/1,377 = 0.444 parts have candidates strict-parsing in-bounds and 834 keep unresolved variants (per-file strict rates 0.000-1.000 — the grammar is incomplete on some writers). G3 refines this row (6.3.1, corrections C8-C11): the u16be records exist wherever the element space exceeds 255 (the mass of the unresolved candidates), the references are lexicographic ranks rather than walk positions, and the primitive readings split per marker family. | candidate (grammar incomplete corpus-wide) | dev parts, R15-R32 + unknown |
| GE-P7-variants (P7/P8) | variants | pools without connectivity exist (36/1,377 = 0.026 parts decode pool groups with zero strip candidates — related to G1 unknown 7: pools can exist without strips; *why* G1's 12 SurfacicReps-less stores carry none stays open); strip candidates without any pool group are near-absent (3/1,377 = 0.002). B4's "float64 store" `086a4effaab7` is reclassified (G2 correction C6): its 4.58 MB store carries a normal f32le pool (1 group, 916 vertices) with 20 strip candidates none of which verify — a pool without *verified* connectivity, not an encoding variant. | established (observed) | dev parts |

## 6.3 Embedded tessellation — the L3-gate answer (ADR-0001)

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-V5-strip (V5) | strip records | verified strip-index records (grammar below) inside the `CATStdCont` region — 36/44 parts = 0.818 (per-release 0.5-1.00; R19 4/4, R21 4/5; small-part misses are content density). Density scales with model content: 177,061 verified records in the 237.9 MB R24 part, 67,672 in the 375.7 MB R20 part, 24,840 in the 190.2 MB R21 part, down to single digits in small parts. All 14 release buckets R15-R32 contribute positive files — the store is a constant of the format, not a generation. | established (existence) | parts of the 81-file scan |
| GE-G1 (G1) | record grammar | strip-index record family: `01 <marker 0x41..0x4f> <type 0x01..0x0a> ff [u32le n][n x u16be values]` — markers `0x0141/0142/0143/0149/014a/014c/014f` observed; counts mostly 4-30. A record is verified when 1 <= n <= 1e6 and the record fits in the file; isolated matches outside the store are binary coincidences. Worked examples (`e9ca6192a2854002` at 8,043,557 and 8,043,617) include an index pattern zig-zagging between two ascending arcs — the shape of a closed triangle strip around an annular region, with repeated indices at the joins. The grammar is a byte-level fact; the primitive semantics are decoded one level further by G2 (6.2.1) and refined by G3 (6.3.1: the references are lexicographic ranks of the pool coordinates, 0x4a/0x42 loops are triangle-strip segments and 0x4c loops closed polygons — corrections C8-C10). | established (grammar); semantics established by G2/G3 on pool-only stores (candidate corpus-wide) | grammar measured on the sample; G2 decode in 6.2.1; G3 semantics in 6.3.1 |
| GE-V7 (V7) | 2-0 tags | little-endian version-like tags `[u16le t][u32le n]"2-0"` (bytes `03 00 00 00 "2-0"`) and `"2X-0"` (`04 00 00 00 "2X-0"`) inside CGMGeom regions and the adjacent bulk — `13bb5c0c` carries 1,091 + 10,910 of them, `50cd280f` 3,678 + 34,120, but only 4/44 files = 0.091: content-dependent, not a format constant. Recorded as a candidate discriminator for a future CGM-stream ticket, not a law. | candidate | 81-file scan |
| (float64 variant) | content variant | one deep file (`086a4effaab7`, R20) carries a 4.58 MB nested store with zero verified strip records — reclassified by G2 (correction C6): the store carries a normal f32le vertex pool (1 group, 916 vertices; 20 strip candidates, none verified) — a pool without verified connectivity, not a float64 encoding variant. | established (observed, one file) | 086a4effaab7 |

**The L3-gate statement (ADR-0001)**: an embedded tessellated
(discretized) representation **exists for ~0.82-0.93 of parts** (rates
V4/V5) in the CATStdCont nested store (scene-graph/surfacic
representations); it is **absent in products**; it is **not** in
`CATCGRCont` (empty, V2) and **not** in `CGMGeom` (the exact-model
container). Its byte-level decode is under way: the nested store, vertex
pool and facet-record primitive semantics are decoded (6.2, 6.2.1,
6.3.1) — on pool-only stores the facet decode already yields closed
oriented triangle soups (GE-F6-soup); the composite stores' edge-table
grammar and their declared element space are decoded (6.3.2) — the
global numbering law of the composite space stays candidate and the
unit question remains open.

### 6.3.1 The facet-record primitive semantics (G3)

Evidence: the G3 corpus-wide decode
([2026-11-09-facet-semantics.md](../evidence/2026-11-09-facet-semantics.md),
ticket #31; verified by `scripts/triage/decode_facet_semantics.py`;
per-file rows in `docs/evidence/data/facet-semantics-files.csv`,
per-loop rows in `facet-semantics-loops.csv`, per-claim per-release
rates in `facet-semantics-claims.csv`, the acceptance-seed soup in
`facet-soup-369fc90b25b4977d.obj`). Scope: all 1,377 dev parts (1,068
decoded stores); the established scopes below are the **179 pool-only
stores** (no `01 02` edge group, no trailer opener — 76 of which soup
end-to-end); the other 889 stores (0.832) reference a larger composite
index space that stays open. Corrections C8-C11 are recorded in the
G3 note.

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-F1-record (F1) | record grammar | facet records tile their region header-to-header: `01 <mk> [<ty>] [b3] ff [u32le n][12B f32le normal on 0x49/0x4a/0x4c/0x4b/0x4e][k u8 counts][n refs]`, the k count bytes (0..4) summing to n and delimiting the type-many sub-loops; a record's (width, k) parse must end at or before the next header, exact tiling wins; on a clean store's gap edge (no `01 02` group, no trailer opener) a unanimous exact-tile width vote wins the tie-break, composite stores keep the narrower-width preference (2026-11-10 #35). Two header forms: 4-byte and a 5-byte variant (`01 4b 01 01 ff`-shaped — G2 unknown 6; 534 gap-start records on 121 parts — 2026-11-10 #35 correction: was 446/105 before the clean-store width fix). 516/1,068 = 0.483 stores tile completely (the composite-space stores carry gap content); per-file tiling rate 0.0-1.000. | established (observed) | decoded stores, R15-R32 + unknown |
| GE-F1w-width (F1w) | index width | the reference width is per-record u8 or u16be (BIG-endian), chosen by the tiling law — u8 on small element spaces; u16be appears wherever refs exceed 255, per-record adaptive otherwise (G2 correction C11: these are the mass of G2's unresolved candidates). 2026-11-10 (#35): on a clean store's gap edge a unanimous exact-tile width vote wins the tie-break — 115 records across the 16 mixed-width clean stores decode u16be that previously half-read as u8; composite stores keep the narrower-width preference. | established (observed) | every accepted record |
| GE-F2-lex (F2) | index mapping | facet references are **lexicographic ranks of (x, y, z) within the pool**, not walk positions (G3 correction C8): on the 76 souped stores the per-family readings reproduce the stored normals at 1,290/1,300 = 0.9923 winding triangles, vs 0.2746 under walk order and <= 0.38 under the five other axis orders (approximate); on the full 179-clean scope 1,297/1,345 = 0.9643 (2026-11-10 #35: was 1,299/1,349 = 0.9629); the 8-vertex box decodes to its six faces with correct stored normals only under lex ranks (12/12, walk order fails 0/12 parallel). | established (souped-store scope) | 76 in-pool souped stores; box worked example |
| GE-F3-strips (F3) | 0x4a/0x42 primitive | each 0x4a loop is a **triangle-strip segment** (n_refs-2 triangles, alternating flip, phase reset per loop): the consistent strip normal equals the stored 12-byte normal. Souped stores: 1,274/1,284 strip triangles parallel, 1,272 sign+ (anti-parallel stores named in the note: 6888b986 — 2026-11-10 #35: the anti-parallel dots on aa84a202/bd79fa8e sat on cluster-final u16be records that half-read as u8 and left the measured scope with the width fix). 0x42 = the same strip content without the normal payload — adding 0x42-as-strips closes the two open R17 shells (closure 64/76 -> 66/76). B4's strip reading is right about the content and wrong about the grammar (G3 correction C9). | established (souped-store scope; 0x42 functional via closure) | 76 in-pool souped stores |
| GE-F4-polygons (F4) | 0x4c primitive | each 0x4c loop is a **closed polygon in ring order** (Newell normal == stored normal, 16/16 sign+); the strip reading of the same loops is 16/16 sign-mixed (rejected). G2's "boundary loops" reading was right for 0x4c and wrong for 0x4a (G3 correction C9). | established (souped-store scope) | souped stores with 0x4c |
| GE-F5-winding (F5) | winding law | all normal-bearing facet geometry is counter-clockwise seen from the stored normal (right-hand rule = the OBJ convention): souped stores 1,288 sign+ vs 2 sign- of 1,290 parallel winding triangles (0.9984); full-179 scope 1,295+/2- of 1,297 (2026-11-10 #35: was 1,294+/5- of 1,299); the export consumes triangles as decoded. | established (souped-store scope) | 76 in-pool souped stores |
| GE-F6-soup (F6/F7) | triangle soup | decoding clean stores end-to-end yields a manifold: 76/76 = 1.000 (no edge used more than twice), closed solids 66/76 = 0.868 (the 10 open are sheet-like shells with paired boundary edges), oriented-consistent 66/66 closed solids, 0 degenerate triangles among 1,354. The n=1 acceptance seed `369fc90b25b4977d` (R20): 80 vertices, 50/50 facet records decoded, 140 triangles, 210 edges all used exactly twice, oriented, bbox (-1.2, 0, -0.95)..(21.2, 30, 0.95) — committed as `facet-soup-369fc90b25b4977d.obj`; coordinator software-render check PASS (2026-11-09). | established (souped-store scope) | 76 souped stores |
| GE-F8-composite (F8) | composite index space | 889/1,068 = 0.832 stores carry an `01 02` group (6-byte records `02 02 (u16be)(u16be)` whose endpoints are lex-adjacent pool vertices — an edge/rim table) and/or a `10 24 04 ff ff 00 00 00 ff [u32le length]` opener of the trailer-named region (the length equals trailer C on the worked example); on 793/889 of them facet references exceed the pool (up to 18,442 vs pool 1,624). Under the pool-only mapping their in-pool-looking loops wind far below the bar (≈ 0.13-0.16 by denominator, review-measured) — the numbering is genuinely incomplete, not a variant. | candidate (numbering open) | decoded stores |
| GE-F9-4149 (F9/F10) | 0x41/0x49 laws | 0x41: n == 3*type on 59/59 records; 0x49: n == 3*type on 3,722/3,722 — both byte laws hold corpus-wide; 0x49's primitive reading stays open (no 0x49 loop sits on a pool-only store, so the winding test is silent), 0x41/0x44 carry no normal so the winding test is silent (0x44: 649 records, semantics open). | established (byte laws); primitive readings open | decoded stores |

### 6.3.2 The composite index space — edge tables and the scene-graph element space (G6 stage 2a)

Evidence: the G6 stage-2a decode
([2026-11-10-composite-space.md](../evidence/2026-11-10-composite-space.md),
ticket #34; verified by `scripts/triage/decode_composite_space.py`;
per-part rows in `docs/evidence/data/composite-space-files.csv`,
per-claim per-release rates in `composite-space-claims.csv`). Scope:
the 939 composite-structure stores of the L2 population (878 dev
composite-space + 61 held-out); the exported families below are the
edge-table grammar and the declared element-space laws — the global
numbering law stays candidate until the big-store node streams decode.
Corrections to stage-1 C6 and G3 F8 are recorded in the G6 note
(edge records are polyline records `02 <n> <n refs>`; edge endpoints
index the full composite space, not only the pool).

| ID | Subject | Claim | Label | Scope |
|---|---|---|---|---|
| GE-E1-edge (C6 refinement) | edge-table grammar | every `10 24 04 ff ff 00 00 00` + `01 02` group is a polyline table: P1g count field at +10 (ff -> u32le at +11), then that many records `02 <n> <n refs>` — n = point count (2 = segment; stage-1's `02 02 (u16be)(u16be)` = the n=2 u16be case; the "157 other 02 0X forms" = n != 2), references u8 or u16be (big-endian) per group, decided by exact end-alignment onto the next wrapper/body end. Walk lands exactly on 812/899 = 0.903 edge-carrying stores (u16be 628, u8 220); residue 87 named (count-unit/record-form variants). | candidate (below bar; grammar byte-verified on 5 anchors) | 899 edge-carrying composite stores, all release lines |
| GE-E3-unwrapped | un-wrapped edge lists | the same records also appear un-wrapped under `01 01 <count>` (the 8-vertex box's 12 edges), located corpus-wide by strict end-alignment: 680/939 = 0.724 composite stores, 64,143 records — stage-1's edge census undercounted the edge territory. | candidate | composite stores |
| GE-N1-token | list-node token | every composite store's scene-graph territory (before the first facet header) contains the token `ff ff 02 00 01` followed by two P1g counts (element_count, edge_ref_bound): 939/939 = 1.000. | established (observed) | 939 composite stores, all release lines |
| GE-N2N3-countlaw | declared element space | element_count = max facet/edge reference + 1 — the declared size of the composite element space. 2026-11-10 stage-2b correction: element_count is read from the LARGEST token-bearing node (the stage-2a max-over-all-nodes reading is superseded — on the 50 disputed stores the largest-node reading satisfies element_count == max_ref_all + 1 on 35, the max reading on 0, 10 carry no refs). Re-measured under the recovered reading over the 916 stores carrying refs: size >= max+1 on 854/916 = 0.932, strict == on 748/916 = 0.817 (the stage-2a wording's 713/939 = 0.759 rested on the superseded reading); element_count == pool_size on 5 (the empty-list degenerate), > pool on 873, < pool on 61 (the stage-2a "smaller than the pool on 59" re-measured). The refs-resolve rate (stage-2a: 883/939 = 0.940) is reading-dependent and awaits re-measurement under the recovered law (#34 stage 2c). Residues named in the notes (62 size-violating, 87 non-walking edge groups). | candidate | 939 composite stores |
| GE-N6-lexlists | node point lists | the scene-graph nodes carry per-rep point lists stored LEX-SORTED (x, y, z) with prefix compression — each point writes only the suffix it does not share with its predecessor ([x][y][z] at a segment/x-group start, [y][z] after an x repeat, [z] after an (x, y) repeat; f32le) — byte-exact on 026d6726 (98 points, 203 f32 writes, DP-unique at pool 10/10) and reproduced on e254a37e; pool vertices re-listed verbatim; no second `05 08 01` vertex pool exists outside `01 06` groups (0/4 anchors; 24/939 marginal runs at corpus scale). The big-store form is the SAME law organized as ascending x-groups (70b59f2a: all 40 pool x values written once, ascending, across an 11,264-B region; the stage-2a "compressed-stream statistics" are the per-node 2-bit tables, not a different encoding). 2026-11-10 stage-2b refinement: the "x if changed / y if changed / z always" stage-2a wording is the y-repeat-confused reading — the suffix-after-LCP law subsumes it and explains the y rewrites. 2026-11-11 stage-3b refinement (GE-N6a/TBL, evidence note stage 3b): the write shapes are TABLE-DRIVEN, not inferred — after the zero block sits a 2-bit table of exactly ceil(element_count/4) bytes (LSB-first, value = f32 words: 0 = [x][y][z], 1 = skip/curve entry, 2 = [z], 3 = [y][z]) followed by a P1g count of the region's f32 words (the stage-2c "+1 byte" was that count byte); the walk is deterministic (no DP) and consumes exactly the declared count on 556/650 big (0.855) + 268/283 small (0.947) audited stores, with the pool fully re-listed on 464/556 decoded big (0.835) and 213/268 decoded small (0.795); big-form was 0/654 before this stage; segment bookkeeping resolved — one table covers the whole region (no per-segment tables; corner groups sit out of x order at their element slots, table pattern 0,2,3,2 each on 70b59f2a). | established (anchor-verified: 2 stores byte-exact + the stage-3b table walk byte-exact on 4 anchors); corpus walk-exact 0.855/0.947 with the residue named (U3-variant multi-node family) | 026d6726 + e254a37e worked lists; 70b59f2a big form; 933-store audit |
| GE-M1-numbering | global numbering (candidate) | the element space = pool vertices + node point lists (+ curve entries), and facet AND edge references are 0-BASED POSITIONS in the globally lex-sorted merge — the clean stores' F2 "lex ranks of the pool" is the degenerate case of this law. RECOVERED CONSTRUCTION (2026-11-10 stage-2b): the pool is absorbed because the node list re-lists the pool vertices verbatim; curve entries interleave (their count = element_count − node points: 26 = 124 − 98 on both anchors; sort positions pinned by a monotone shift profile — 1-4-2-1-2-2-2-1-3-7-1 on 026d6726's record, starting at shift 0 on e254a37e's — 2026-11-10 #34 review F5 clarifies the profile is per-store); no dedup between curve and node entries; values consistent with the `33 3X` circle definitions. The stage-2a outstanding confirmation is DELIVERED: on 026d6726 AND e254a37e the `01 4a 07 ff` record (normal (0,0,-1)) decodes ALL SEVEN loops exactly planar at z = 2.1 under this law (pool-lex indexing stays falsified). 2026-11-11 stage-3b refinement (M2b-element-index): the merged positions ARE the region's element indices — refs are 0-based element indices in REGION order (identity; the shift profile was the written-index matching artifact), the curve entries are the table's skip slots at known indices AND ARE REFERENCED by facet loops (26/316 loops on 70b59f2a; "never referenced" corrected), and the loop plane law is coplanarity against the record's stored 12-B normal (the axis-constant reading fails on slanted planes — 70b59f2a's corner quads). On 70b59f2a: max_ref = 1,819 = element_count − 1 (N2 exact), 316 normal-carrying loops = 290 coplanar (max residual 5.4e-05) + 26 skip-ref + 0 nonplanar. Corpus battery over the 556 decoded big / 268 decoded small stores: 0.519 coplanar + 0.389 skip-ref + 0.092 nonplanar (of the nonplanar, 84% = multi-plane fillet/bevel strips — per-triangle law applies, 6.3.1 GE-F3/F5; coplanar + skip-ref + multi-plane = 0.983 of testable loops). | candidate (numbering; construction recovered, anchor-established; the element-index reading is established on the anchors and measured corpus-wide) | 026d6726 + e254a37e full loop validation; 70b59f2a big-form validation; 464/650 big-form decode rate |
| GE-C1-curves | curve families | `33 3X` records behind a 7-byte header `<u8 a><u8 b><u16le id><00><u16le len>` fill the `00 00`-group bodies and `ff`-opener regions of every composite store (939/939; presence census 1,807,070 hits): 33 32 = [P][Q][P] f32le triples + a trailing f32le equal to the norm of the middle triple Q; 33 37/33 38 carry big-endian f32 payloads. `30 04 04 ff ff` records sit between the facet region and the edge lists (907/939 stores). Point semantics open (G2 unknown 5). | established (observed, layout); semantics unknown | composite stores |

Reproduction:

    python3 -I scripts/triage/decode_geometry_payloads.py    # B4 scan (~36 s; six CSVs)
    python3 -I scripts/triage/decode_nested_store.py         # G1 nested-store decode (6.2)
    python3 -I scripts/triage/decode_vertex_pool.py          # G2 vertex-pool decode (6.2.1)
    python3 -I scripts/triage/decode_facet_semantics.py      # G3 facet semantics + soup (6.3.1)
    python3 -I scripts/triage/decode_composite_space.py      # G6 stage-2a composite space (6.3.2)
    python3 -I scripts/triage/decode_node_streams.py         # G6 stage-2b node streams + merge law (6.3.2)
    python3 -I scripts/triage/decode_big_form_points.py      # G6 stage-3b table-driven point regions, both forms (6.3.2)
