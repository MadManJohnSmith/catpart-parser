# W2 marathon progress (ronda v3) — brep → exporter / empty-mesh 211

Branch `marathon/w2-brep-mesh`, base `d8554e0`. Worker lane:
`src/catpart/brep/`, `src/catpart/geometry/brep_mesh.py` (new),
`port/src/geometry/brep_mesh.rs` (new), tests, `docs/evidence/`;
`export.{py,rs}` wiring only in a minimal isolated commit.

## Baseline (committed probe: `scripts/triage/w2_empty_mesh_census.py`)

Official population: fitness run `20261121T103944Z-d2c9ff` (baseline of
the round) — L2 `failed_check == "empty-mesh"` rows: **211 = 207 dev +
4 held-out**. L2 dev rate 0.8240405 (1138/1381), held-out 0.9344262
(57/61).

Census command (streaming, one file in memory):

```bash
python -B -I scripts/triage/w2_empty_mesh_census.py \
    fitness/reports/20261121T103944Z-d2c9ff.json \
    --corpus-root /home/alan/Documents/Repos/catpart-parser
```

CSV: `docs/evidence/data/w2-empty-mesh-baseline.csv` (211 rows,
sha16-keyed). Aggregates:

| measure | value |
| :--- | ---: |
| files with a located store span | 124 (77 stdcont, 29 other, 18 seebody); 87 with no span |
| files with pool points | 19 (95,819 points; ALL 19 in composite index space) |
| files with facet candidates in-span | 14 (178,240 candidates) |
| accepted facet records in-span | 6,206 (0x42: 616, 0x4a: 2,863, 0x4c: 1,231, other 0x49/0x41/0x44: 1,496) |
| unresolved candidates in-span | 172,034 (one file, `PalmDown5motors2`, carries 171,978) |
| `CGMGeom` containers | 210/211 |
| `33 32` line records file-wide | 178,124 |

Route facts: every one of the 211 falls through the committed chain
(store → a5 surface → grid → face-gp → display) with zero triangles;
export summaries carry `no-surface-display`. The 9 files that carry
both a pool and accepted 0x42 records are composite stores whose
`decode_composite_store` raises `undecoded-variant` (U3-variant
element-region residue + stage-8 mixed-write miss), so the accepted
records never export.

## Hipótesis 1 — conectar `brep/` y triangular los 796 loops 0x42

**NEGATIVE (2 attempts, documented;STOP condition met).**

Attempt 1 — pool-first/lex mapping + EdgeGuard assembly (in-lane
simulation, `PalmDown5motors2`): the store's 171,916 unresolved
candidates parse as a **counts-less `0x49` triangle-record family**
(`01 49 ty ff | u32le n=3*ty | 12B unit f32 normal | 3*ty u16be refs`,
26 B/record at ty=1) with zero parse failures, all unit-normal and
in-bounds. Assembled with the accepted records behind a per-record
manifold gate: 180,859 triangles, **manifold true**, 3,695 records
declined, 124 degenerate members filtered.

Attempt 2 — mapping validation by stored normals (the plane-agreement
law: a mapped triangle's geometric normal must be parallel to the
record's stored normal): **refuted**. Agreement rates: identity
mapping 1/800, lex mapping 290/800 (36%), offsets δ ∈ [-16,16] all
≤ 10/800. The accepted records' own triangles disagree with their
stored normals at 8,072/12,036 under lex. A correct mapping would
score ~100% (the pool-only scope validates at 98.99%, BR2-10).
**Conclusion: the refs index the composite element space, whose
element region does not decode under any committed law (U3-variant);
pool/lex/shifted mappings produce a manifold mesh with scrambled
positions — geometry, not a guess we are allowed to ship.**

Prerequisite (outside this worker's lane): an element-region decode
law for the U3-variant family / stage-8 mixed-write extension in
`catpart/geometry/composite.py`. **Reopening criterion**: when that
law lands, the counts-less 0x49 family + the EdgeGuard member-filter
assembly (attempt 1, measured here) meshes these stores with the
correct mapping; `brep_mesh` picks it up unchanged.

The 796 loops 0x42 figure reproduces as 784 measured loops of accepted
0x42 records across 8 files (+ the 9th file's 12 = 796); 232/784 are
in-pool under raw refs, 135 of those pass the BR2 coplanarity bar —
but on stores whose mapping is refuted (above), so none of them
exports honestly.

## Hipótesis 2 — polilíneas `01 01` + pool → segmentos reales en DISPLAY

**NEGATIVE-IN-PART on the 211 (measured; the honest-emission
prerequisite is the same element space as hypothesis 1).**

- Edge groups (`01 02`, E1): 98,543 records on 11 files carry refs
  under the pool count, only 334 above — numerically pool-shaped.
  But refs index the FULL merged space on composite stores (the
  committed F8-corrected detector honesty in `curves.py`), and the
  mapping discriminator is inconclusive: the segment-length test on
  `PalmDown5motors2`'s 98,469 segments gives identity 9.18% jumps vs
  lex 11.28% — no mapping separates (W2-19). Correia 1 / separador
  favor identity, Coxa favors lex — inconsistent, not a law.
- Unwrapped `01 01` polyline lists (E3): 303 records, **0 in-pool**
  (W2-17) — nothing to pair on the 211.
- `33 32` line records: 178,688 walked file-wide, **8,670 hold BOTH
  G2 laws on 63 files** (W2-18) — real absolute-coordinate segments,
  no index space needed. The committed display route does not reach
  them: it scans the located store spans + `CATPrtCont` regions, and
  these records sit outside both. Wiring that read into the display
  fallback lives in `src/catpart/geometry/display.py`, which is
  outside this worker's lane (the brief allows `export.{py,rs}` wiring
  only). **Hand-off to the orchestrator**: the region extension is a
  measured, law-validated surface (63 files, 8,670 segments); whoever
  owns display.py can adopt it with the numbers above.

STOP condition: two attempts spent (the in-pool pairing measurement
and the mapping discriminator); both documented.

## Hipótesis 3 — superficies evaluables en `cgm_nurbs.py` / `shell.py`

**NEGATIVE (documented with reopening criteria).**

- `brep/cgm_nurbs.py`: no evaluation entry point exists (W2-20) — the
  module is the BR5 object-dictionary identity + NURBS payload
  SIGNATURE detector; the committed BR5 outcome is "the dictionary
  carries no coordinate payload" and the knot/weight signatures carry
  no record framing. No evaluatable surface for the 211 from this
  module. Reopening: a CGM record-level spline decode (BR5 successor
  ticket) — out of this round's scope.
- `brep/shell.py`: assembles shells from pool-mapped accepted facet
  records — the same mapping hypothesis 1 refutes on every empty-mesh
  composite store. No honest shell without the element space.
- The brief's "22 BLANK": the committed fitness report carries only
  clean / missing-invariant / crash classifications (W2-21) — the
  BLANK roster is a viewer-layer population this worker cannot
  recompute; needs the orchestrator's roster to attack.

## Entregables de esta unidad

- `scripts/triage/w2_empty_mesh_census.py` — the streaming census
  probe (selftest pins the pool vs curve-entry populations).
- `docs/evidence/data/w2-empty-mesh-baseline.csv` — 211 rows,
  sha16-keyed, width-checked.
- `docs/evidence/data/w2-brep-mesh-claims.csv` — 21 claims rows
  (W2-01..W2-21; passes the claims-quoting checker).
- `src/catpart/geometry/brep_mesh.py` — the counts-less 0x49 family
  decoder + census (UNWIRED; the module doc is the negative record).
- `port/src/geometry/brep_mesh.rs` — the Rust twin (registered in
  `port/src/geometry/mod.rs`), 8 unit tests, `cargo fmt` + `clippy -D
  warnings` clean.
- `tests/test_brep_mesh.py` — 14 synthetic regression tests mirroring
  the Rust fixtures (structural parity; export-path byte parity
  applies when the route is wired, per the module doc).

## Next steps

1. The decisive lever is OUTSIDE worker lanes: an element-region
   decode law for the U3-variant composite family in
   `catpart/geometry/composite.py`. Reopening criteria for the W2
   route are in the brep_mesh module doc (per-record plane agreement,
   EdgeGuard assembly, member-filter law).
2. The display.py owner can adopt the 63-file `33 32` region
   extension (W2-18) for the honest Open-Rate lift.
