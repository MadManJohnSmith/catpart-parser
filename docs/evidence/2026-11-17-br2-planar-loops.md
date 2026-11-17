# Evidence: exact planar faces & boundary loops — TOP-04 / TOP-05 / SRF-01 (Ticket #54, BR2, Spec G #47)

**Date**: 2026-11-17
**Status**: COMPLETE (3/3 constructs decoded; gate green)
**Target Ticket**: Ticket #54 (`BR2: Exact planar faces & boundary loop decoder`)
**Parent Spec**: Spec G #47 (Phase 7, B-rep / L3 fitness)
**Method**: RE-only corpus-wide decode over all 1,442 manifest parts (store-class scope: 281 pool-only / 1,036 composite of 1,317 located stores), L2-pass join 1,089 files. Decoder `scripts/triage/decode_brep_planar.py` (stdlib, mmap, deterministic, manifest order); shipped module `src/catpart/brep/planar.py`; claims `docs/evidence/data/br2-planar-claims.csv` (23 rows — every prose figure below is a CSV row or row-derived sum). Builds on G3's facet model ([2026-11-09-facet-semantics.md](2026-11-09-facet-semantics.md)) — its grammar, index space and primitive semantics are cited, not re-derived.

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

- Record end: `+0x14 (20d) + ty*count_width + n*ref_width`. Normal-bearing records tile their region header-to-header under the G3 tiling law — 50,528 accepted `0x4a`/`0x4c` records corpus-wide (BR2-05), 0 accepted on the 5-byte header form (BR2-17; the 534 gap-start `0x4b`/`0x4e` candidates of G3 §2 remain unresolved gap content on the accepted-path).
- The normal endianness/layout is byte-measured through G3's winding test (F2/F5: `'<fff'` unpacking reproduces stored normals at 0.9923 — any other reading gives garbage) and by this ticket's unit-norm law: **54,265/54,265 = 1.000 of normal-bearing records are unit within 1e-6, max |n-1| = 4.3813e-08** (BR2-06/06b, corpus-wide, no index space needed).
- **The plane offset `d` is NOT stored** — it is derived (inference): `d = -mean(n.p)` over the record's loop vertices; the record-local plane is `n.p + d = 0`.

## 3. TOP-05: the loop delimitation law (count width independent of ref width)

G3's grammar reads the count bytes as `k` raw bytes summing to `n`. Corpus evidence splits the accepted records into three count-encoding classes (BR2-07: 118,586/118,807 = 0.99814 established; 221 variants):

1. **u8 counts** — `len(counts) == ty`; one byte per loop (the box `10b9ae4a…`, the soup seed `369fc90b…`).
2. **u16be counts** — `len(counts) == 2*ty` with zero high bytes; one big-endian u16 per loop. 3,053 records corpus-wide (BR2-08). 489 u16-count-over-u8-ref records across 36 stores; both directions observed on the single store `02ee1544…` (`w=1` with counts `(0, 4)` and `w=2` with counts `(0, 6)`) — **the count width is a per-record property independent of the reference width**.
3. **count-encoding variant** — neither law fits (e.g. `ty=1` with nonzero high bytes): 221 records (0.19%). The loop structure is NOT established for these (status `count-variant`, no guessing); their byte-parse split still consumes all references, so triangle geometry is stable.

Consequence for the shipped G3 module: `facets.record_loops` (the byte-parse split) yields phantom empty loops on u16-count records — `("EMPTY", n=6)` instead of one 6-ref loop on the `02ee1544` pattern. `planar.record_true_loops` is the corrected split. **Triangle geometry is unaffected** (zero-length slices consume no references), which is why G3's soup results stand unchanged; the correction matters for loop-count claims (a `ty=1` record is ONE loop, not two).

Primitive readings per loop (G3 F3/F4, retained): `0x4c` loops are **closed rings** (cyclic boundary cycles, 6,462 corpus-wide — BR2-15); `0x4a`/`0x42`/`0x41` loops are **strip segments** — 51,673 measured on the geometry scan's population, the strip-kind loops of NORMAL-BEARING records (`0x49`/`0x4a`, BR2-16); normal-less `0x41`/`0x42` strip records sit outside that population; the closure of a ring is a READING assertion (last->first edge), not a byte flag. Multi-loop face carriers (`ty >= 2`): 2,331/54,265 = 4.29% of normal-bearing records (BR2-09) — for `0x4c` these are the outer-boundary + hole-loop faces; for `0x4a` they are strip segments of one face patch (G3: phase reset per loop).

## 4. SRF-01: the record-local plane (decoded) and the surface identity (open)

- **Normal layout (fact, corpus-wide)**: 12B = three f32le at `+0x08 (8d)`/`+0x0c (12d)`/`+0x10 (16d)`; unit norm on 100% of 54,265 normal-bearing records (BR2-06/06b).
- **Coplanarity (fact, pool-only scope)**: every in-pool loop vertex satisfies `n.p + d = 0` within `tol = 1e-4 x scale` (scale = max(max |coordinate| of the record's points, 1.0) — the floor keeps degenerate point clouds finite-tolerance): **1,480/1,495 = 0.989967** of decodable pool-only faces (BR2-10). Relative spread distribution: median 0 (BR2-12 — half the faces measure EXACTLY zero), p95 = 3.08392e-05 of tol (BR2-12c), max = 10,189.6 x tol (BR2-12b). The threshold is not load-bearing: the passing mass sits at <= 3e-5 of tol, the failures at >= 100 x tol.
- **Orientation (fact, pool-only scope)**: 1,483/1,495 = 0.991973 sign-positive (winding triangles for strips, Newell for rings — the G3 F5 CCW law re-measured at face level, BR2-11).
- **The 15 coplanarity failures / 12 anti-parallel faces are named G3 counterexample stores**: the worst relative spread sits on `bd79fa8e39e8fab2` (a G3-named anti-parallel store, §3 of the facet-semantics note); the failure set reproduces with `--sha16 bd79fa8e` (§7). Not massaged — recorded.
- **Composite stores (documented-open with ceiling arithmetic)**: 19,509/54,265 = 35.95% of normal-bearing records have references beyond the pool (BR2-14) and are NOT geometry-validated (composite index space, G3 F8/unknown 1). Of the 33,179 in-pool faces on composite stores only 5,420 = 0.163356 pass the plane test (BR2-13) — reproducing G3's "in-pool-looking loops wind at ~0.13-0.16 under pool-only mapping" at plane level: **the composite numbering is not pool-first**, and per-face geometry on 1,036 composite stores (78.7% of located stores) stays undecodable until BR5 decodes the CGM streams. Ceiling if BR5 resolves the numbering: these 33,179 in-pool-looking records plus the 19,509 out-of-pool records re-enter validation; nothing in this ticket's pool-only laws needs revision for that (the laws are index-space-agnostic).
- **0x49 extension candidate**: 3,737 records carry `n == 3*type` with a normal and count bytes `(3,)`-shaped single-triangle loops (BR2-18). Their dominant form (`ty=1`, one triangle) validates jointly with the pool-only plane claims; multi-loop `0x49` primitive semantics stay open (G3 F10) — candidate, not established.

## 5. TOP-04: the face decode

A face = one accepted facet record on the planar markers, decoded as: header (`mk`, `ty` loop count, form byte), `u32le n` at `+0x04 (4d)`, the 12B f32le normal at `+0x08 (8d)` (markers `0x49`/`0x4a`/`0x4c`), the count integers at `+0x14 (20d)`, the references (u8/u16be big-endian), and the derived record-local plane. File-level census tie-out is EXACT: 1,133/1,442 corpus and 1,087/1,089 L2-pass files carry >= 1 accepted facet record (BR2-01/03 vs the census's `TOPO_FACE` row).

Scope honesty: the record-level decode is corpus-wide; the geometric face validation (plane + orientation) is pool-only-scope (§4). The record == topological-face equivalence is a READING validated geometrically on the pool-only scope, not a byte-marked boundary — the mapping into `CGMGeom`'s face objects is BR5/BR6 territory.

## 6. Detector honesty (per construct)

- **TOP-04**: the record-acceptance detector does NOT discriminate face records from any other accepted `01 [41-4f]` record (0x41/0x42 strip content and 0x44 parse under the same grammar) — "record == planar face" is the geometric reading (plane validation), not a byte marker; on composite stores it is unverifiable (refs leave the pool). Negative fixture: the non-coplanar strip record (`test_negative_non_coplanar_points_rejected`).
- **TOP-05**: the count-structure law does NOT discriminate outer boundary loops from inner hole loops (no orientation/role byte is claimed) and does not establish closure on the strip families — ring closure is a `0x4c` reading assertion. Negative fixtures: the count-variant record (structure NOT established, no guessing) and the non-tiling record (`parse_facet_record` returns None).
- **SRF-01**: the normal detector does NOT discriminate an exact plane SURFACE from a planar tessellation PATCH of a curved surface — each `0x4a` strip record carries its own facet normal and a cylinder's facets are individually planar; the decode establishes record-local planes only, never the underlying B-rep surface. Negative fixtures: the non-coplanar points with a plane normal stamped on them, and the non-unit normal (|n-1| flagged).

All six synthetic negative fixtures run in `tests/test_brep_planar.py` and via `scripts/triage/decode_brep_planar.py --selftest` (0 failures) — §6 names the five that map to the per-construct honesty lines; the sixth (reversed-ring winding) is the closure-reading negative.

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
| BR2-07 | loop delimitation resolves (u8 or u16be) | fact | accepted records, ty>0 | 118,807 | 118,586 | 0.99814 |
| BR2-08 | u16be-count records (volume anchor) | fact | accepted records, ty>0 | 118,807 | 3,053 | 0.0257 |
| BR2-09 | multi-loop face carriers (ty>=2) | fact | normal-bearing records | 54,265 | 2,331 | 0.042954 |
| BR2-10 | loop vertices coplanar with stored normal | fact | pool-only faces | 1,495 | 1,480 | 0.989967 |
| BR2-11 | winding/Newell sign-positive | fact | pool-only faces | 1,495 | 1,483 | 0.991973 |
| BR2-12/12b/12c | relative spread median / max / p95 (value rows) | fact | pool-only faces | — | — | 0 / 10,189.6 / 3.08392e-05 |
| BR2-13 | composite in-pool faces passing the plane test | fact | composite stores | 33,179 | 5,420 | 0.163356 |
| BR2-14 | normal records with out-of-pool refs | fact | all normal records | 54,265 | 19,509 | 0.359513 |
| BR2-15 | 0x4c loops decoded as closed rings (volume anchor) | fact | loops, geometry scan | 6,462 | 6,462 | 1.0 |
| BR2-16 | strip-kind loops of normal-bearing records (0x49/0x4a) decoded as strip segments (volume anchor; normal-less 0x41/0x42 outside the scan population) | fact | loops, geometry scan | 51,673 | 51,673 | 1.0 |
| BR2-17 | accepted records on the 5-byte header form | fact | accepted records | 118,807 | 0 | 0.0 |
| BR2-18 | 0x49 records carrying a normal | candidate | 0x49 records | 3,737 | 3,737 | 1.0 |
| BR2-19 | located stores classified pool-only (geometry-validated scope) | fact | located stores | 1,317 | 281 | 0.213364 |
| BR2-20 | located stores classified composite (index space parked on BR5) | fact | located stores | 1,317 | 1,036 | 0.786636 |

Version scope: all rows are all-release pooled ("all"); per-release reruns are reproducible via the script (deterministic manifest order). The claims CSV is the committed artifact; this table abridges it.

## 8. Unknowns / parked (with ceiling arithmetic)

1. **Composite index space** (G3 F8/unknown 1, owned by BR5): 1,036/1,317 = 78.7% of located stores; 19,509 out-of-pool records + 27,759 composite in-pool records failing the plane test (33,179 - 5,420) are the decode ceiling. Plane-level corroboration: pass rate 0.163356 (BR2-13) vs the ~0.13-0.16 winding band G3 measured — the numbering is not pool-first.
2. **221 count-encoding variants** (BR2-07): loop delimitation not established; 0.19% of accepted records. Ceiling: they re-enter the loop claims if a third count-encoding family is established.
3. **The clean stores with out-of-pool refs** (G3 unknown 2): inside BR2-14's 19,509 (pool-only stores are 281 of 1,317; their out-of-pool normal records are counted in the same row). Plane-level corroboration: the pool-only coplanarity failures concentrate on G3's named counterexample stores (§4).
4. **5-byte header form** (G3 unknown 3): 0 accepted records (BR2-17); the 534 gap-start candidates stay unresolved gap content — outside BR2's marker slice.
5. **Multi-loop 0x49 primitive semantics** (G3 F10): open; the dominant single-triangle form validates jointly with §4.

## 9. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python scripts/triage/decode_brep_planar.py                # corpus-wide, writes the claims CSV
.venv/bin/python scripts/triage/decode_brep_planar.py --selftest     # the synthetic negative fixtures
.venv/bin/python scripts/triage/decode_brep_planar.py --sha16 bd79fa8e  # the named counterexample store
```

Corpus binaries are read READ-ONLY from the main checkout (`--corpus-root`, default `/home/alan/Documents/Repos/catpart-parser`), resolved via `manifests/corpus-manifest.csv` `local_path`; never copied into the repo tree, never committed. Runtime ~3 min; stdlib only; deterministic (sorted manifest order). The census tie-out uses the census script's exact probe order (including its `other-container` pass, which probes every valid block — the census's name filter compares the block name against itself and always matches).
