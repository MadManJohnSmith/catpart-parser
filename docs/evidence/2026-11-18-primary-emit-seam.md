# Composite exporter: the primary-emit manifold seam (#34)

Date: 2026-11-18
Base: `68daa5e` (main)
Status: **implemented (Python + Rust, port-parity verified), full-corpus
A/B clean (0 pass→fail, 0 manifold regressions), gate green.**

Claims: `docs/evidence/data/br6-primary-seam-claims.csv`
A/B data: `docs/evidence/data/primary-emit-seam-ab.csv` (one row per
part), `docs/evidence/data/primary-emit-seam-loops.csv` (one row per
refused loop: area, store area, ratio, decision).
Reproduce: `.venv/bin/python -I scripts/triage/primary_emit_seam_ab.py`
(~3.5 min, deterministic, read-only over the corpus).

## 1. The seam

`composite._triangulate`'s short-record emission was the last geometry
path without a manifold guard:

```python
tris, deg = _loop_triangles(kind, idxs, points)
degenerate += deg
triangles.extend(tris)          # no topology check
```

The dup-pin weld (§2.1 of `2026-11-18-composite-loop-weld.md`) and the
extended-header family (`2026-11-18-extended-header-family.md`) both
pass `_mesh_safe` before emitting. The primary loops did not, and the 24
remaining not-manifold corpus parts (23 dev + 1 held-out) over-use their
edges exactly there: a re-listed facet, a fin strip, or a strip that
shares a boundary edge with the already-emitted mesh. The stage-15 dedup
law resolves the duplicate-triple subset; these 24 are the residue the
dedup does not explain.

## 2. The fix — the same lever, made fidelity-neutral by an area rule

`_triangulate` now carries the incremental histogram from the first
primary loop (`EmitState.edge_uses` in the port). Every short-record
candidate runs `_mesh_safe`:

- **accepted** → emitted, edges folded in (unchanged behaviour);
- **refused and a sliver** (the candidate's area ≤
  `PRIMARY_LOOP_AREA_REL` = 1% of the store mesh's area) → dropped,
  counted in `primary_loop_skips`, named by the warning class
  `primary-loop-manifold-skip`;
- **refused and larger** → KEPT exactly as before (real surface is never
  dropped for topology), counted in `primary_loop_kept`, named by
  `primary-loop-manifold-kept`; its edges still fold in, so later loops
  see the same over-used histogram today's emission produces.

The reference is the **store-level** mesh area, measured by a registry
pass with the seam off (`decode_composite_store` decodes twice; the
second pass is the shipped one). That matters: in a per-rep store a
duplicate loop can be 100% of its rep's area and 0.003% of the part
(2fb5b092's sole loop), so a per-rep reference would classify every
duplicate as real surface. The registry pass is deterministic and costs
one extra triangulation of already-parsed records (the A/B run is
~1.9 min for 1,442 parts with both passes).

### 2.1 The fire gate (fail-closed, the dedup law's discipline)

The seam fires **only where it resolves the store's over-use**: after
the slivers are out, the guarded mesh must be manifold. If it is not —
a larger over-use is kept — the entry point returns the **pre-seam
decode unchanged** and names the candidates
(`primary_loop_seam_declined`, warning class
`primary-loop-manifold-declined`).

Without this gate, the six "mixed" not-manifold stores below lose
slivers and stay not-manifold: 545707b9871a535c alone loses 12 loops /
417.83 mm² (2.62% of its area) for **no L2 gain**. With it, all nine
larger-over-use stores keep their exact pre-seam geometry (triangle
counts and areas identical to the baseline) while the declined
candidates are still reported. This is the same "fires only where it
resolves" rule the stage-15 dedup law applies.

## 3. The threshold: the ticket's 0.1% does not reproduce its own target

The brief asked for "≤ 0.1% of the mesh area assembled so far", 15
flips, and every declined loop ≤ 0.1%. The measurements do not support
that constant:

- **0.1% of the store mesh area** → **11 flips, not 15**: the four
  remaining flips need larger loops (44e63faa 0.3589%, c9fdd852
  0.1556%, cd76cab5 0.5883%, d4127e6b 0.7599%), so the held-out row the
  ticket expects to flip would not. 0.1% of the *running* area flips just
  3 parts: an early sliver is a large fraction of an almost-empty mesh
  (97a0a420's twelve refused loops measure 0.25–0.95% of the area at
  their turn, but 0.006–0.018% of the part).
- **The measured split** over the 24 parts' refused loops is
  **0.760% → 2.918%**: the largest declined loop is d4127e6b's
  2,531.64 mm² = **0.7599%** of its 333,142 mm² mesh (the held-out row
  the ticket expects to flip), and the smallest kept over-use is
  26504a08's 1,208.32 mm² = **2.9175%** of its 41,415 mm² mesh.
- **1% of the store mesh area** sits inside that gap and yields
  **exactly the briefed 15/9 split**. It is the shipped constant
  (`PRIMARY_LOOP_AREA_REL = 1e-2`, `port::...::PRIMARY_LOOP_AREA_REL`).

The 0.1% **per-file removal** bar also cannot hold together with the
15-flip target: the held-out flip d4127e6b necessarily removes its
0.76% loop. The measured per-file removals are in section 4.4 — the
15 flips remove 0.0026%–0.76%, and no other part changes area.

This is the one place the note deviates from the ticket's numbers; the
ticket's own oracle (15 flips, dev 1,063 → ~1,077, held-out 56 → 57)
is the shipped behaviour.

## 4. Full-corpus A/B (all 1,442 manifest parts)

Run: `scripts/triage/primary_emit_seam_ab.py`, baseline = the same code
with the seam off (`_seam_area=None`; the registry pass), after = the
shipped path. The baseline pass is row-for-row identical to the
pre-change `identity-export-files.csv` emission (triangle count,
manifold, L2 status, failed check, error class on every row; 0
mismatches).

### 4.1 Gate

| | before | after |
|---|---:|---:|
| exports | 1,173 | 1,173 |
| dev L2 pass | 1,063 / 1,381 = 76.97% | **1,076 / 1,381 = 77.91% (+0.94 pp)** |
| held-out L2 pass | 56 / 61 | **57 / 61** |
| total L2 pass | 1,119 | **1,133 (+14)** |
| pass → fail | — | **0** |
| manifold regressions | — | **0** |
| manifold flips | — | **15** |
| triangle/area decreases | — | 15 (the flips; see 4.4) |

The ticket's ~1,077 / +1.01 pp is 1 short: **13bb5c0c** flips to a
manifold mesh (152,105 → 152,010 triangles) but still fails on **33
pre-existing degenerate triangles** (`MAX_DEGENERATE_TRIANGLES` is 0 and
is not changed here). Its row is `fail/degenerate-triangles` before and
after; the manifold flip is real (32,232 edges, 0 over-use) and the
held-out flip d4127e6b lands as expected.

### 4.2 The 15 flips (all now manifold; 14 now pass)

| sha16 | split | triangles | area removed | skips |
|---|---|---:|---:|---:|
| d4127e6b5cc39236 | held-out | 5,094 → 5,080 | 0.7599% | 1 |
| cd76cab52cf2fbe5 | dev | 1,573 → 1,563 | 0.5883% | 1 |
| 44e63faa2d9abf84 | dev | 2,520 → 2,516 | 0.3960% | 2 |
| c9fdd85256ae1eba | dev | 17,773 → 17,771 | 0.1556% | 1 |
| 97a0a420923c5c67 | dev | 8,665 → 8,641 | 0.1419% | 12 |
| a61588e5fe2cca5f | dev | 2,992 → 2,986 | 0.0173% | 1 |
| ba0900267e2072e1 | dev | 4,075 → 4,071 | 0.0060% | 1 |
| 4abf3eeaf892be44 | dev | 1,533 → 1,529 | 0.0042% | 1 |
| 6ab9e107b7f30308 | dev | 854 → 850 | 0.0041% | 1 |
| d31ea2c17d63c041 | dev | 2,350 → 2,346 | 0.0038% | 1 |
| 4a32f59c1e637acd | dev | 2,227 → 2,223 | 0.0032% | 1 |
| 612c5e7cc7291c71 | dev | 4,391 → 4,387 | 0.0029% | 1 |
| 2fb5b092857f70ec | dev | 1,625 → 1,621 | 0.0026% | 1 |
| bc235805f71fdf5a | dev | 1,625 → 1,621 | 0.0026% | 1 |
| 13bb5c0c49616ade | dev | 152,105 → 152,010 | **+0.1095%** (grew) | 71 |

13bb5c0c's area grows while it loses 95 triangles: skipping the 71
sliver loops changes the extended-header histogram, so 491 → fewer
extended records are declined and more extended triangles land. Both
counts are in the A/B CSV.

### 4.3 The 9 kept over-uses — geometry unchanged

Each of these stays not-manifold exactly as before (triangle counts and
areas identical to the baseline). Six carry declined candidates (the
fire gate returned the pre-seam emission); three carry only large
over-use loops.

| sha16 | kept loops (ratio of store area) | declined candidates |
|---|---|---:|
| 26504a08b641ad7a | 1 (2.9175%) | 1 |
| 341bd488e61d6061 | 1 (22.5701%) | 0 |
| 4d1b6c35efc860a1 | 3 (5.97–10.97%) | 2 |
| 545707b9871a535c | 1 (21.3281%) | 12 |
| 5689954c867a0f70 | 1 (15.3706%) | 0 |
| 5a982112b4f5edc1 | 8 (2.31–8.17%) | 0 |
| 995383c2e6aacd4d | 2 (1.13–4.38%) | 1 |
| cd88ae9d4d51a439 | 1 (47.8354%) | 1 |
| e8d9a35806f5fcf7 | 3 (11.85–23.08%) | 1 |

Totals over the corpus: **106 skipped** loops (max ratio 0.7599%),
**18 declined** candidates (max 0.9396%), **24 kept** loops (min
1.1297%, max 47.8354%) on 33 stores.

### 4.4 Area removed per file

The 15 flips remove 0.0026%–0.7599% of their own area (table 4.2);
every other exported part is byte-identical except:

- **b912cbef805c541b** (a stage-15 dedup carrier, `fail/degenerate`):
  the pre-dedup mesh's duplicate pair makes the seam skip 1 sliver, and
  the dedup then keeps one more duplicate copy — the net is −2 triangles
  / −0.0004% area; its status is unchanged (`fail/degenerate-triangles`).
- the **8 passing dedup carriers** (1d256d12, 25aeb5a0, 2d59ff19,
  396a9d79, 4a21610f, e1eed721, ef61cfc2, f4a5df2a): the seam's skips
  are exactly absorbed by the dedup's drops — triangle counts and areas
  are identical (rel 0.0), so no passing row's geometry changed.

## 5. Option 1 is NOT taken (owner decision, measured cost)

Option 1 — apply the guard to every refused loop regardless of area —
is the higher-yield alternative and is **deliberately not taken**: it
drops real surface. Measured on the same 24 parts (threshold = ∞, the
shipped gate otherwise unchanged):

- **24/24** become manifold and **22** would pass L2 (13bb5c0c and
  341bd488e61d6061 keep pre-existing degenerate failures) — +8 L2 rows
  over the shipped seam;
- cost: 11 of the 24 parts lose more than 0.1% of their area, and six
  lose more than 15%: e8d9a35806f5fcf7 **53.88%** (50,823.60 mm²),
  cd88ae9d4d51a439 **48.78%** (17,727.51 mm²), 5a982112b4f5edc1
  **34.96%** (204.12 mm²), 545707b9871a535c **23.94%** (3,825.30 mm²),
  4d1b6c35efc860a1 **20.76%** (489.19 mm²), 5689954c867a0f70
  **15.37%** (12.03 mm²).

That is real geometry dropped for a failing-row flip; the area rule plus
the fire gate is the fidelity-neutral alternative.

## 6. Port parity (Rust)

`port/src/geometry/composite.rs` carries the same seam: the incremental
histogram in `EmitState`, `loop_area`/`mesh_area` (`f64::sqrt`, the same
IEEE operation as Python's `math.sqrt`), `PRIMARY_LOOP_AREA_REL = 1e-2`,
the two-pass entry (`decode_store_once` + `decode_composite_store`), the
fire gate and the same counters (`primary_loop_skips`,
`primary_loop_seam_declined`, `primary_loop_kept`) and warning strings
(`primary-loop-manifold-skip` / `-declined` / `-kept`).

- `cargo test --locked`: 152 lib + 6 bin tests pass, including
  `primary_seam_skips_tiny_overuse_and_keeps_large` (synthetic quad +
  a 0.005 mm² fin over a twice-used edge + a 25 mm² fin: skip 1 / keep 1;
  seam-off keeps both; sliver-only ends manifold).
- Parity differential on all 15 flips (corpus-gated pytest
  `test_primary_seam_port_parity_on_the_flips`): parsed summaries equal
  and PLY **byte-identical** on 15/15.
- `wasm-pack build --target web --release` rebuilt `port/pkg`;
  `site/viewer/pkg` refreshed (byte-identical copies). The shipped
  artifact runs the same summary in the reproduction smoke test.

## 7. Tests

- New fixtures (`tests/fixtures_gen.py`):
  `geometry-composite-law-primary-seam-tiny` (the fin is a 0.05 mm²
  sliver over the box's twice-used edge → skipped, 12-triangle manifold
  box, skip counted/named) and `-declined` (the same sliver plus a
  500 mm² fin → kept, mesh still not-manifold → the fire gate returns
  the 14-triangle pre-seam emission and names the decline + the keep).
  Both are in the fidelity harness's composite export matrix (stage 3),
  so the port parity fixture run covers both warnings and counters.
- `tests/test_composite_export.py` pins both fixtures end-to-end (PLY
  face counts included) and the corpus-gated 15-part port differential.
- Rust unit test as above.
- Full suite: **711 passed, 7 skipped** (ruff clean; claims-CSV quoting
  clean).

## 8. What was NOT changed

- `MAX_DEGENERATE_TRIANGLES` (still 0) and the L2 gate policy.
- The dup-pin weld, the extended-header gate and the stage-15 dedup law
  are untouched; the seam sits before the dedup (the registry/guarded
  passes precede `_apply_unordered_dedup`), which is why the dedup
  carriers' net geometry is unchanged.
- Option 1 (guard every large over-use loop) — documented above with its
  measured cost; owner decision pending if that surface loss is ever
  accepted.
