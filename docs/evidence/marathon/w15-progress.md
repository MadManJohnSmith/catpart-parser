# W15 — progress (marathon wave 4, continuous mode)

Branch: `marathon/w15-e5-tail` (base `d4a1fbc`, W3's tip).
Scope: the E5 line's open spans — the `0x00e7` record's 148-byte tail,
the CT-02 id graph at file level — plus the L2 regression the
Orchestrator bisected to W3's merge (priority interrupt, fixed first).

## 0. The bisected L2 regression — fixed first (Orchestrator interrupt)

- **Bug**: `First_Back_Shell.CATPart` and `backshell_M.CATPart` moved
  PASS → FAIL `degenerate-triangles` exactly at W3's merge: the E5
  tessellation filters zero-area members (collapsed pole rows) but fed
  the skip count into `degenerate_triangle_count`, and the L2 gate
  (`MAX_DEGENERATE_TRIANGLES = 0`) fails on any nonzero.
- **Fix**: the established member-filter law (`e4cb87a`) applied to the
  surface route — the skips are named on the new
  `surface-members-filtered` warning + `SurfaceScan.degenerate_filtered`
  and never count as degenerate (gate untouched).  Python + Rust twins;
  schema enum/description updated.
- **Measured**: both parts `degenerate_triangle_count == 0`, manifold,
  L2 pass; PLY byte-identical Python=Rust; the corpus L2 fast pass
  (`scripts/triage/l2_fast_pass.py`, three hands: pre-E5 `2e3a4da`,
  main `d8554e0`, branch) shows **0 pass→fail** branch-vs-main and the
  dev L2 landing at the class-table A/B's expected +15 (see
  `docs/evidence/data/e5-member-filter-l2.csv` and
  `docs/evidence/2026-11-22-e5-member-filter.md`).
- **Pinned-test correction**: `test_corpus_population_renders_the_
  decoded_carriers` (host-only, red since W3's merge — CI skips without
  the corpus) re-pinned to the measured census `mesh: 10, display: 100`
  (the E5 flips), triangles 4,422 → 63,848.

## 1. The 148-byte tail — measured structure (H1)

- `docs/evidence/2026-11-22-e5-surface-tail.md` +
  `scripts/triage/probe_e5_surface_tail.py` +
  `docs/evidence/data/e5-surface-tail-claims.csv`.
- The tail is a fixed 148-byte descriptor: u16 pair header
  (`+2 = n_v - 1` on 98.57 %, `+6 = n_u - 1` on 98.61 % — v-first like
  the head), per-direction size pair (offset 0.0, size), three constant
  f64s (1.0 / 0.0 / 1.0), and an all-zero reserved region +64..147.
- **Negative with criterion**: the sizes do not clip the decoded
  surface — the record's own knots are the face's parameterization
  (arc-vs-span in a 1 % band on ~99.9 %); the sizes read as the face's
  extents in the *original surface's* parameterization (candidate).

## 2. The CT-02 id graph at file level (H2)

- `scripts/triage/probe_e5_id_graph.py` +
  `docs/evidence/data/e5-id-graph-claims.csv` /
  `e5-id-graph-refs.csv`.
- (pending final corpus numbers)

## Gates

- `tests/test_e5_surface.py` 17 ✓ (2 new member-filter pins); port
  `geometry::surface` 22 ✓ (1 new); full pytest suite green after the
  population-test re-pin; ruff clean.
- Parity: the 2 bisected parts PLY byte-identical Python=Rust.
