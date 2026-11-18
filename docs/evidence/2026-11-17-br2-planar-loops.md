# Evidence: exact planar faces & boundary loops — TOP-04 / TOP-05 / SRF-01 (Ticket #54, BR2, Spec G #47)

**Date**: 2026-11-17
**Status**: COMPLETE (3/3 constructs decoded; post-merge audit corrections landed 2026-11-18 — every prose figure below traces to a committed CSV row)
**Target Ticket**: Ticket #54 (`BR2: Exact planar faces & boundary loop decoder`)
**Parent Spec**: Spec G #47 (Phase 7, B-rep / L3 fitness)
**Method**: RE-only corpus-wide decode over all 1,442 manifest parts (store-class scope: 281 pool-only / 1,036 composite of 1,317 located stores), L2-pass join 1,089 files. Decoder `scripts/triage/decode_brep_planar.py` (stdlib, mmap, deterministic, manifest order); shipped module `src/catpart/brep/planar.py`; claims `docs/evidence/data/br2-planar-claims.csv` (60 rows — every prose figure below is a CSV row or row-derived sum; the post-merge audit added the provenance rows BR2-07b/07c/07d/07e, 08b/08c, 12d/12e, 18b, 21-24, 25, 26/26b/26c/26d, 27/27b, 28 and the marker-blind + perpendicular-winding fixtures, Ticket #54 audit). Builds on G3's facet model ([2026-11-09-facet-semantics.md](2026-11-09-facet-semantics.md)) — its grammar, index space and primitive semantics are cited, not re-derived.

---

## 1. Executive summary

| Construct | Census label | Verdict | Corpus rate (this decode) | Census tie-out |
| :--- | :--- | :--- | :--- | :--- |
| `TOP-04` Face | `TOPO_FACE` | **Decoded** | 1,133/1,442 parts; 1,087/1,089 L2-pass (0.998163) | exact (BR2-01/03) |
| `TOP-05` Loop | `TOPO_LOOP` | **Decoded** | 895/1,442 parts; 856/1,089 L2-pass (0.786042) | exact (BR2-02/04) |
| `SRF-01` Plane | `GEOM_SURF_PLANE` | **Decoded** (record-local plane; surface identity documented-open) | 54,265/54,265 normals unit (1.000); plane validation 1,480/1,495 on the pool-only scope (0.989967) | exact file counts (BR2-02/04) |

New decode content beyond BR1/G3: (a) the **count-width law** — the per-loop reference lengths are integers at a per-record COUNT WIDTH (u8 or u16be) independent of the record's reference width, so `ty` is the true loop count and the G3 byte-parse's `(0, lo)`-pair reading of u16 counts emits phantom empty loops (benign for triangle geometry — the zeros consume no references — wrong for loop counting); (b) the **derived plane offset** `d = -mean(n.p)` with corpus coplanarity rates; (c) the **plane-level reproduction of G3 F8** on composite stores (16.3% in-pool pass rate — the composite numbering is not pool-first).

## 2. The decoded byte layout (both bases)

One accepted facet record (G3 F1 4-byte header form), offsets from record start `+0x00 (0d)`:

| offset | field |
| :--- | :--- |
| `+0x00 (0d)` | marker byte `01` |
| `+0x01 (1d)` | marker `mk` (`0x41`-`0x4f`; planar slice `0x49`/`0x4a`/`0x4c`) |
| `+0x02 (2d)` | `ty` = **loop count** (TOP-05 law, see §3) |
| `+0x03 (3d)` | `ff` form byte (4-byte form; 0 accepted records corpus-wide use the 5-byte form — BR2-17) |
| `+0x04 (4d)` | `u32le n` — total reference count (`+0x04 (4d)`..`+0x08 (8d)`) |
| `+0x08 (8d)` | **12B normal, three f32le components** (`nx` at `+0x08 (8d)`, `ny` at `+0x0c (12d)`, `nz` at `+0x10 (16d)`) — markers `0x49`/`0x4a`/`0x4c` only (SRF-01) |
| `+0x14 (20d)` | `ty` count integers, `count_width` bytes each (u8, or u16be big-endian) |
| `+0x14 (20d) + ty*count_width` | `n` references, `ref_width` bytes each (u8 or u16be **big-endian**, G3 F1w) |

- Record end: `+0x14 (20d) + ty*count_width + n*ref_width`. Normal-bearing records tile their region header-to-header under the G3 tiling law — 50,528 accepted `0x4a`/`0x4c` records corpus-wide (BR2-05), 0 accepted on the 5-byte header form (BR2-17; the 534 gap-start `0x4b`/`0x4e` candidates of G3 §2 remain unresolved gap content on the accepted-path). That 0 is an absence observed on 118,807 records: the 95% upper bound is 2.5e-5 (rule of three, 3/118,807).
- The normal endianness/layout is byte-measured through G3's winding test (F2/F5: `'<fff'` unpacking reproduces stored normals at 0.9923 — any other reading gives garbage) and by this ticket's unit-norm law: **54,265/54,265 = 1.000 of normal-bearing records are unit within 1e-6, max |n-1| = 4.3813e-08** (BR2-06/06b, corpus-wide, no index space needed).
- **The plane offset `d` is NOT stored** — it is derived (inference): `d = -mean(n.p)` over the record's loop vertices; the record-local plane is `n.p + d = 0`.

## 3. TOP-05: the loop delimitation law (count width independent of ref width)

G3's grammar reads the count bytes as `k` raw bytes summing to `n`. Corpus evidence splits the accepted records into three count-encoding classes (BR2-07: 118,586/118,807 = 0.99814 established; 221 record-level variants). The resolved count INCLUDES 3,657 `0x49` triangle-list records whose loop/primitive semantics remain candidate (BR2-07b: 3,657 of the 118,586 resolved records) — excluding the whole `0x49` family, the law resolves **114,929/115,070 = 0.998775** (BR2-07c), so the header figure is not propped up by the candidate family:

1. **u8 counts** — `len(counts) == ty`; one byte per loop (the box `10b9ae4a…`, the soup seed `369fc90b…`).
2. **u16be counts** — `len(counts) == 2*ty` with zero high bytes; one big-endian u16 per loop. 3,053 records corpus-wide (BR2-08), of which **489 sit over u8 references** (BR2-08b) on **36 of the 39 stores** that carry u16 counts at all (BR2-08c); both directions are observed on the single store `02ee1544…` (`w=1` with counts `(0, 4)` and `w=2` with counts `(0, 6)`) — **the count width is a per-record property independent of the reference width**.
3. **count-encoding variant** — neither law fits (e.g. `ty=1` with nonzero high bytes): 221 records (0.19%) at the RECORD level. Of those, **92 sit on normal-bearing records** (BR2-07e: 92/54,265) — the subset the face decoder can reach; the other 129 are normal-less records it never sees. The face STATUS `count-variant` is narrower still: **82 reports** (BR2-07d), because the decoder tests the index space FIRST, so 10 of the 92 report `out-of-pool` instead. Three distinct populations (221 / 92 / 82), not one. The loop structure is NOT established for any of them (no guessing); the byte-parse split still consumes all references, so triangle geometry is stable.

Consequence for the shipped G3 module: `facets.record_loops` (the byte-parse split) yields phantom empty loops on u16-count records — `("EMPTY", n=6)` instead of one 6-ref loop on the `02ee1544` pattern. `planar.record_true_loops` is the corrected split. **Triangle geometry is unaffected** (zero-length slices consume no references), which is why G3's soup results stand unchanged; the correction matters for loop-count claims (a `ty=1` record is ONE loop, not two).

Primitive readings per loop (G3 F3/F4, retained): `0x4c` loops are **closed rings** (cyclic boundary cycles, 6,462 corpus-wide — BR2-15); `0x4a`/`0x49` loops are **strip segments** — 51,673 measured on the geometry scan's population, the strip-kind loops of NORMAL-BEARING records (BR2-16); normal-less `0x41`/`0x42` records sit outside that population and their loops are counted separately: `0x42` carries 104,600 loops across all located stores (BR2-26), and `0x41` carries 88 loops over 61 records in two subsets — 45 records under the count law (53 loops, BR2-27) and 16 count-variant records through the byte-parse fallback (35 loops, BR2-27b); the closure of a ring is a READING assertion (last->first edge), not a byte flag.

**The 9.8x gap to G3's `0x42` figure, reconciled.** G3 §3 documents `0x42` as "loops 10,684 corpus-wide"; this ticket measures **104,600** (BR2-26), and no scope reproduces G3's number: pool-only stores carry **889** (BR2-26c), records whose references all sit in the pool carry **62,806** (BR2-26d), and G3's own committed loop table (`facet-semantics-loops.csv`) carries **857 `0x42` loop rows over 108 clean stores**. BR2-26 is the all-store count from this decoder's geometry scan (1,317 located stores, true-loop split, committed generator); G3's 10,684 is a prose-only tally with no committed generator or artifact behind it — the same defect class as the pre-audit "489 across 36 stores" (now committed as BR2-08b/08c). The 104,600 / 10,684 = **9.79x** difference is an unbacked figure against a measured one, not a scope disagreement between two measurements.

Multi-loop face carriers (`ty >= 2`): 2,331/54,265 = 4.30% of normal-bearing records (BR2-09) — for `0x4c` these are the outer-boundary + hole-loop faces; for `0x4a` they are strip segments of one face patch (G3: phase reset per loop).

## 4. SRF-01: the record-local plane (decoded) and the surface identity (open)

- **Normal layout (fact, corpus-wide)**: 12B = three f32le at `+0x08 (8d)`/`+0x0c (12d)`/`+0x10 (16d)`; unit norm on 100% of 54,265 normal-bearing records (BR2-06/06b).
- **Coplanarity (fact, pool-only scope)**: every in-pool loop vertex satisfies `n.p + d = 0` within `tol = 1e-4 x scale` (scale = max(max |coordinate| of the record's points, 1.0) — the floor keeps degenerate point clouds finite-tolerance): **1,480/1,495 = 0.989967** of decodable pool-only faces (BR2-10). Relative spread distribution: median 0 (BR2-12 — half the faces measure EXACTLY zero), p95 = 3.08392e-05 of tol (BR2-12c), max = 10,189.6 x tol (BR2-12b). The threshold is not load-bearing: the 1,480 passes span **0 .. 4.60718e-04 x tol** (max pass = BR2-12d; the p95 figure is the distribution, not the pass boundary) and the 15 failures span **33.3 .. 10,189.6 x tol** (min fail = BR2-12e) — a **~72,000x gap** between the worst pass and the best failure (BR2-12e / BR2-12d), so the 1e-4 threshold sits inside empty space rather than bisecting a continuum.
- **Orientation (fact, pool-only scope)**: **1,483/1,495 = 0.991973** sign-positive (winding triangles for strips, Newell for rings — the G3 F5 CCW law re-measured at face level, BR2-11). The denominator is the ORIENTATION-CANDIDATE population — the 1,495 decodable in-pool faces whose winding signs are actually computed (BR2-11's observations column) — measured, not asserted.
- **Failure attribution (fact, pool-only, measured — the pre-audit attribution corrected)**: the 15 coplanarity failures sit on **8 stores**, **13 of them on 6 stores G3 already names** as off-plane (`b9b887db…` 5, `1ffad596…` 4, `0ae8c3e7…`, `a6d450ed…`, `aa84a202…`, `bd79fa8e…` 1 each — BR2-21/21b; per-store rows in the BR2-23 block) and **2 on stores G3 never named** (`137b897fc0c276e3`, `9ed8c3e1e6675bff`). The 12 sign-negative faces span 8 stores: **11 on 7 G3-named stores** (the same six plus the anti-parallel store `6888b986…`) and **1 on `9ed8c3e1e6675bff`** (BR2-22 for the store count, BR2-22b for the face count; per-store rows in the BR2-24 block). Two corrections to the pre-audit reading, recorded rather than massaged: (a) **"anti-parallel" is wrong for the sign-negative set** — the decoder computes only the SIGN of `n·w` (`planar.py`, `_dot(...) > 0.0`), and 5 of the 12 are `b9b887db…`'s five exactly-PERPENDICULAR loops (`n·w = 0` reads as sign-negative; pinned by `test_negative_perpendicular_winding_is_sign_negative`); (b) **`bd79fa8e…` is not an anti-parallel store** since G3 correction #35 ([2026-11-09-facet-semantics.md](2026-11-09-facet-semantics.md) lines 159-165): it is one of the six off-plane stores, so `--sha16 bd79fa8e` reproduces that store's ONE failing face, not the 15-face set (a filtered run cannot; see §9).
- **Composite stores (documented-open with ceiling arithmetic)**: 19,509/54,265 = 35.95% of normal-bearing records have references beyond the pool (BR2-14) and are NOT geometry-validated (composite index space, G3 F8/unknown 1). Of the 33,179 in-pool faces on composite stores only 5,420 = 0.163356 pass the plane test (BR2-13) — reproducing G3's "in-pool-looking loops wind at ~0.13-0.16 under pool-only mapping" at plane level: **the composite numbering is not pool-first**, and per-face geometry on 1,036 composite stores (78.7% of located stores) stays undecodable until BR5 decodes the CGM streams. Ceiling if BR5 resolves the numbering: these 33,179 in-pool-looking records plus the 19,509 out-of-pool records re-enter validation; nothing in this ticket's pool-only laws needs revision for that (the laws are index-space-agnostic). The composite stores also hold the corpus's sign-negative mass: **21,447 of 32,257 oriented candidates = 0.664879** (BR2-28) against the pool-only **12 of 1,495 = 0.008027** (BR2-11). Those composite signs are a property of the mis-mapped numbering, not counterexamples — which is why the counterexample attribution (BR2-21..24) is POOL-ONLY: it is the one population whose geometry the pool mapping validates. The composite mass is declared here rather than hidden, and stays parked with the index space on BR5.
- **0x49 extension candidate**: 3,737 records carry a normal and **all 3,737 satisfy `n == 3*ty`** (BR2-18/18b — both predicates measured, 3,737/3,737; volume anchors, because the CANDIDATE content is the loop/primitive semantics, not these rates). The count law resolves 3,657 of them and leaves 80 record-level count variants, which is why BR2-07c re-states the count law with the family carved out. Their dominant form (`ty=1`, one triangle) validates jointly with the pool-only plane claims; multi-loop `0x49` primitive semantics stay open (G3 F10) — candidate, not established.

**Per-store failure attribution** (the BR2-23/24 blocks; cop = coplanarity failures, sign = sign-negative faces; both pool-only):

| store (sha16) | G3 citation | cop | sign | rows |
| :--- | :--- | ---: | ---: | :--- |
| `b9b887db0d516d88` | named, off-plane | 5 | 5 | BR2-23/24 |
| `1ffad5964894f1ff` | named, off-plane | 4 | 1 | BR2-23/24 |
| `0ae8c3e7dd3e74ad` | named, off-plane | 1 | 1 | BR2-23/24 |
| `a6d450edd4a8ff17` | named, off-plane | 1 | 1 | BR2-23/24 |
| `aa84a202df09ed45` | named, off-plane | 1 | 1 | BR2-23/24 |
| `bd79fa8e39e8fab2` | named, off-plane | 1 | 1 | BR2-23/24 |
| `6888b9868df81c00` | named, anti-parallel | — | 1 | BR2-24 |
| `137b897fc0c276e3` | **NOT named** | 1 | — | BR2-23 |
| `9ed8c3e1e6675bff` | **NOT named** | 1 | 1 | BR2-23/24 |
| **total** | 9 distinct stores, 7 G3-named | **15** | **12** | BR2-21b/22b |

## 5. TOP-04: the face decode

A face = one accepted facet record on the planar markers, decoded as: header (`mk`, `ty` loop count, form byte), `u32le n` at `+0x04 (4d)`, the 12B f32le normal at `+0x08 (8d)` (markers `0x49`/`0x4a`/`0x4c`), the count integers at `+0x14 (20d)`, the references (u8/u16be big-endian), and the derived record-local plane. File-level census tie-out is EXACT: 1,133/1,442 corpus and 1,087/1,089 L2-pass files carry >= 1 accepted facet record (BR2-01/03 vs the census's `TOPO_FACE` row).

Scope honesty: the record-level decode is corpus-wide; the geometric face validation (plane + orientation) is pool-only-scope (§4). The record == topological-face equivalence is a READING validated geometrically on the pool-only scope, not a byte-marked boundary — the mapping into `CGMGeom`'s face objects is BR5/BR6 territory. No accepted record carries `ty == 0` (BR2-25: 0/118,807; 95% upper bound 2.5e-5, rule of three), so the decoder's `no-loops` status is unreachable on the corpus and pinned by a synthetic fixture only (`test_no_loops_status_pinned`, selftest check 15).

## 6. Detector honesty (per construct)

- **TOP-04**: the record-acceptance detector does NOT discriminate face records from any other accepted `01 [41-4f]` record (0x41/0x42 strip content and 0x44 parse under the same grammar) — "record == planar face" is the geometric reading (plane validation), not a byte marker; on composite stores it is unverifiable (refs leave the pool). Negative fixtures, one per edge of that declaration: `test_negative_marker_blind_face_record` (a normal-less `0x42` record with in-pool refs decodes as status `ok` with `normal is None`, `plane is None`) and `test_negative_marker_blindness_across_markers` (`0x42` and `0x44` records differing only in the marker decode identically).
- **TOP-05**: the count-structure law does NOT discriminate outer boundary loops from inner hole loops (no orientation/role byte is claimed) and does not establish closure on the strip families — ring closure is a `0x4c` reading assertion. Negative fixtures: the count-variant record (structure NOT established, no guessing), the non-tiling record (`parse_facet_record` returns None) and the reversed-ring winding (`0x4c` refs reversed -> `oriented is False`; the closure reading, not a byte property).
- **SRF-01**: the normal detector does NOT discriminate an exact plane SURFACE from a planar tessellation PATCH of a curved surface — each `0x4a` strip record carries its own facet normal and a cylinder's facets are individually planar; the decode establishes record-local planes only, never the underlying B-rep surface. Negative fixtures: the non-coplanar points with a plane normal stamped on them, the non-unit normal (|n-1| flagged), the out-of-pool refs (composite index space: no plane, no orientation, no guessing — also TOP-04's unverifiability on composite stores), and the perpendicular-winding record (`n·w = 0` reads sign-negative: the sign-only edge §4's attribution rests on, pinned by `test_negative_perpendicular_winding_is_sign_negative`).

Nine negative fixtures live in `tests/test_brep_planar.py`; the same edges run among the sixteen `--selftest` checks (the nine fixture edges, six positive/constructional checks, plus the `no-loops` status pin). §6 names every one: TOP-04's two marker-blindness fixtures, TOP-05's count-variant and reversed-ring fixtures, SRF-01's non-coplanar, non-unit-normal and perpendicular-winding fixtures, plus the grammar's non-tiling negative and the composite-index out-of-pool negative.

## 7. Claims (docs/evidence/data/br2-planar-claims.csv)

| claim | statement (abridged) | label | scope | observations | passes | rate |
| :--- | :--- | :--- | :--- | ---: | ---: | ---: |
| BR2-01 | L2-pass files with >=1 accepted facet record (TOP-04 tie-out) | fact | L2-pass | 1,089 | 1,087 | 0.998163 |
| BR2-02 | L2-pass files with >=1 accepted 01 4a/4c record (TOP-05/SRF-01 tie-out) | fact | L2-pass | 1,089 | 856 | 0.786042 |
| BR2-03 | corpus parts with >=1 accepted facet record | fact | full corpus | 1,442 | 1,133 | 0.785714 |
| BR2-04 | corpus parts with >=1 accepted 01 4a/4c record | fact | full corpus | 1,442 | 895 | 0.620666 |
| BR2-05 | accepted 01 4a/4c records (volume anchor) | fact | located stores, census scan | 50,528 | 50,528 | 1.0 |
| BR2-06 | normals unit within 1e-6 | fact | all normal-bearing records | 54,265 | 54,265 | 1.0 |
| BR2-06b | max \|n-1\| (value row) | fact | all normal-bearing records | — | — | 4.3813e-08 |
| BR2-07 | loop delimitation resolves (u8 or u16be; includes 3,657 candidate 0x49 records) | fact | accepted records, ty>0 | 118,807 | 118,586 | 0.99814 |
| BR2-07b | resolved records that are 0x49 triangle lists (candidate family) | fact | resolved records | 118,586 | 3,657 | 0.0308384 |
| BR2-07c | count law excluding the 0x49 family (the carve-out) | fact | accepted, 0x49 excluded | 115,070 | 114,929 | 0.998775 |
| BR2-07e | record-level variants that are normal-bearing | fact | normal-bearing records | 54,265 | 92 | 0.00169538 |
| BR2-07d | normal-bearing records whose FACE decode is count-variant | fact | normal-bearing records | 54,265 | 82 | 0.0015111 |
| BR2-08 | u16be-count records (volume anchor) | fact | accepted records, ty>0 | 118,807 | 3,053 | 0.0257 |
| BR2-08b | u16be-count records over u8 references | fact | u16be-count records | 3,053 | 489 | 0.16017 |
| BR2-08c | stores with u16 counts / with u16-count-over-u8-ref | fact | located stores | 39 | 36 | 0.923077 |
| BR2-09 | multi-loop face carriers (ty>=2) | fact | normal-bearing records | 54,265 | 2,331 | 0.042954 |
| BR2-10 | loop vertices coplanar with stored normal | fact | pool-only faces | 1,495 | 1,480 | 0.989967 |
| BR2-11 | winding/Newell sign-positive | fact | pool-only faces (oriented candidates) | 1,495 | 1,483 | 0.991973 |
| BR2-12/12b/12c | relative spread median / max / p95 (value rows) | fact | pool-only faces | — | — | 0 / 10,189.6 / 3.08392e-05 |
| BR2-12d/12e | max PASSING / min FAILING relative spread (value rows) | fact | pool-only faces, split | — | — | 4.60718e-04 / 33.3333 |
| BR2-13 | composite in-pool faces passing the plane test | fact | composite stores | 33,179 | 5,420 | 0.163356 |
| BR2-14 | normal records with out-of-pool refs | fact | all normal records | 54,265 | 19,509 | 0.359513 |
| BR2-15 | 0x4c loops decoded as closed rings (volume anchor) | fact | loops, geometry scan | 6,462 | 6,462 | 1.0 |
| BR2-16 | strip-kind loops of normal-bearing records (0x49/0x4a) decoded as strip segments (volume anchor; normal-less 0x41/0x42 in BR2-26/27) | fact | strip loops, normal-bearing | 51,673 | 51,673 | 1.0 |
| BR2-28 | composite sign-negative mass (declared, not a counterexample population) | fact | composite in-pool faces | 32,257 | 21,447 | 0.664879 |
| BR2-17 | accepted records on the 5-byte header form | fact | accepted records | 118,807 | 0 | 0.0 |
| BR2-18 | 0x49 records carrying a normal (volume anchor) | candidate | 0x49 records | 3,737 | 3,737 | 1.0 |
| BR2-18b | 0x49 records satisfying n == 3*ty | fact | 0x49 records | 3,737 | 3,737 | 1.0 |
| BR2-19 | located stores classified pool-only (geometry-validated scope) | fact | located stores | 1,317 | 281 | 0.213364 |
| BR2-20 | located stores classified composite (index space parked on BR5) | fact | located stores | 1,317 | 1,036 | 0.786636 |
| BR2-21/21b | cop-failure stores / faces on G3-named stores | fact | pool-only stores | 8 / 15 | 6 / 13 | 0.75 / 0.866667 |
| BR2-22/22b | sign-negative stores / faces on G3-named stores | fact | pool-only stores | 8 / 12 | 7 / 11 | 0.875 / 0.916667 |
| BR2-23 (8 rows) | per-store cop-failure counts (volume anchors; §4 table) | fact | pool-only stores | — | — | 1.0 |
| BR2-24 (8 rows) | per-store sign-negative counts (volume anchors; §4 table) | fact | pool-only stores | — | — | 1.0 |
| BR2-25 | accepted records with ty == 0 (no-loops population) | fact | accepted records | 118,807 | 0 | 0.0 |
| BR2-26 | normal-less 0x42 loops, ALL located stores (volume anchor) | fact | normal-less 0x42 records | 104,600 | 104,600 | 1.0 |
| BR2-26c | normal-less 0x42 loops, pool-only stores (G3 scope test) | fact | normal-less 0x42 records | 889 | 889 | 1.0 |
| BR2-26d | normal-less 0x42 loops, in-pool records (G3 scope test) | fact | normal-less 0x42 records | 62,806 | 62,806 | 1.0 |
| BR2-26b | normal-less 0x41 loops: 45 count-law records (53 loops) + 16 fallback records (35 loops) (volume anchor) | fact | normal-less 0x41 records | 88 | 88 | 1.0 |
| BR2-27/27b | 0x41 records with NO count structure / their fallback loop share | fact | normal-less 0x41 records | 61 / 88 | 16 / 35 | 0.262295 / 0.397727 |

Version scope: all rows are all-release pooled ("all"); per-release reruns are reproducible via the script (deterministic manifest order). The claims CSV is the committed artifact; this table abridges it.

## 8. Unknowns / parked (with ceiling arithmetic)

1. **Composite index space** (G3 F8/unknown 1, owned by BR5): 1,036/1,317 = 78.7% of located stores; 19,509 out-of-pool records + 27,759 composite in-pool records failing the plane test (33,179 - 5,420) are the decode ceiling. Plane-level corroboration: pass rate 0.163356 (BR2-13) vs the ~0.13-0.16 winding band G3 measured — the numbering is not pool-first.
2. **221 count-encoding variants** (BR2-07): loop delimitation not established; 0.19% of accepted records. Of them 92 are normal-bearing (BR2-07e) and 82 report face status `count-variant` (BR2-07d; the other 10 report `out-of-pool`, the index-space test runs first), so the record-level variant count and the face-level status are different populations (§3). Ceiling: they re-enter the loop claims if a third count-encoding family is established.
3. **The clean stores with out-of-pool refs** (G3 unknown 2): inside BR2-14's 19,509 (pool-only stores are 281 of 1,317; their out-of-pool normal records are counted in the same row). Plane-level corroboration: 13 of the 15 pool-only coplanarity failures sit on the 6 G3-named off-plane stores, but **2 sit on stores G3 never named** (`137b897fc0c276e3`, `9ed8c3e1e6675bff`, BR2-23) — they are NEW counterexamples, recorded as such (§4).
4. **5-byte header form** (G3 unknown 3): 0 accepted records (BR2-17; 95% upper bound 2.5e-5, rule of three); the 534 gap-start candidates stay unresolved gap content — outside BR2's marker slice.
5. **Multi-loop 0x49 primitive semantics** (G3 F10): open; the dominant single-triangle form validates jointly with §4.

## 9. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python scripts/triage/decode_brep_planar.py                       # all-corpus: the ONLY run that writes br2-planar-claims.csv
.venv/bin/python scripts/triage/decode_brep_planar.py --selftest            # the synthetic negative fixtures
.venv/bin/python scripts/triage/decode_brep_planar.py --sha16 bd79fa8e --out-dir /tmp/br2-sha16
```

Filtered runs (`--sha16` / `--limit`) never touch the committed CSV: they write `br2-planar-claims-sha16-<prefix>.csv` / `br2-planar-claims-limit-<n>.csv` into `--out-dir` (regression-pinned by `test_filtered_runs_never_target_the_committed_claims_csv`). `--sha16 bd79fa8e` reproduces that ONE store's single failing face, not the 15-face failure set (§4) — the attribution needs the unfiltered run or the `--sha16` prefixes of all 9 stores in §4's table.

Corpus binaries are read READ-ONLY from the main checkout (`--corpus-root`, default `/home/alan/Documents/Repos/catpart-parser`), resolved via `manifests/corpus-manifest.csv` `local_path`; never copied into the repo tree, never committed. Runtime ~3 min; stdlib only; deterministic (sorted manifest order). The census tie-out uses the census script's exact probe order (including its `other-container` pass, which probes every valid block — the census's name filter compares the block name against itself and always matches).
