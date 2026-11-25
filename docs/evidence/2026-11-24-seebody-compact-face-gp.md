# Compact see-body face-GP (W26) — 80 official `empty-mesh` parts

**Status**: accepted 2026-11-25 as run **`20261125T161156Z-c85026`**
(baseline `20261124T125633Z-38c46d`, `accepted: true`, no-regret
`L2 dev rose with L1 dev flat`). Python reference and Rust port decode
the compact stream; the WASM boundary exposes the native per-triangle
colors. No gate was relaxed: the prototype's "accepted but not
byte-exact" arm was tightened to the same closure gate the law states.

## The law

The official `empty-mesh` parts carry a compact CAT3DFaceGP stream inside
`CATSeeBodyCont` / `CATBRepModeContainer` regions instead of the 01 06
pool the composite route needs:

1. A `04 04 fd ff` node's `ff ff 02 00` token declares `n_floats@P1g`;
   `n_verts = n_floats // 3`.
2. The `a5 d4 68 53 00` header is followed by `ceil(n_verts / 4)` bytes
   of the 2-bit LCP table. `SHAPES = {0: 3, 1: 0, 2: 1, 3: 2}`: full
   write, keep, `z` only, `y`/`z` only.
3. The `u32le write_count` must equal `sum(SHAPES[v])` (the walk-exact
   gate); then `write_count` `f32le` words reconstruct the running
   `(x, y, z)`.
4. Immediately after the words, `0x51` face-GP and `0x50` counter-table
   records decode under the CAT3DFaceGP law over that node's own element
   space. A missing element reference resolves to the preceding written
   element (the LCP keep-slot convention). Index width is 1 byte when
   `n_verts <= 255`, 2 bytes (u16be) otherwise.
5. The optional `[0x20|0x30] 04 04 ff ff <B><G><R>` header before the
   record carries the native CATIA color; the bytes are stored BGR and
   exposed as RGB. The default is CATIA V5 lavender-gray `(210, 210, 255)`.

## Gates

- **Walk-exact**: a node whose `write_count` does not match the LCP
  table is skipped.
- **Byte-exact closure**: a record whose stream does not end at the
  record's extent (`p == rend` or `p == rend - 1`) is not emitted.
  The prototype counted those closures but still exported them; the
  landed law refuses them. Of 1,690 candidate records, 1,625 are
  accepted: 64 non-exact closures refused, plus one exact-closing
  record whose triangles the incremental edge guard did not admit.
- **In-bounds**: every reference resolves inside the node's element
  space; a bad reference refuses the record whole.
- **Incremental edge guard**: a record that would push an undirected
  edge past two uses is refused whole.
- **Merged mesh**: the scan returns `None` unless the concatenated soup
  is non-empty and manifold. Zero-area/repeated-coordinate loop members
  are skipped by the strip/fan law and named in the summary; they never
  count as `degenerate_triangle_count`.

## Census (189 accepted `empty-mesh` rows)

Reproduce with `.venv/bin/python -B scripts/triage/w26_seebody_census.py
fitness/reports/20261124T125633Z-38c46d.json` (the sweep drives the real
`_export_data` chain and `_score_export`).
The committed claim rows are
`docs/evidence/data/w26-seebody-census-claims.csv`.

| measure | value |
|---|---:|
| candidate rows | 189 |
| now L2 `pass` | **80** (all `dev`) |
| still `empty-mesh` | 109 |
| errors / crashes | 0 |
| compact nodes | 89 |
| records exact / total | 1,626 / 1,690 |
| records accepted | 1,625 |
| vertices | 26,802 |
| triangles | 31,887 |
| closed meshes | 23 |
| degenerate triangles | 0 |

The largest wins are `Ehi_BundleSegment1_1` (3,561 triangles),
`CAAPriChangePattern` (3,366), `Ehi_BundleSegment4_2` (3,096) and
`Ehi_BundleSegment1_2` (2,919). `Ehi_Equipment` is water-tight
(`506` vertices, `1,008` triangles, `boundary_edges = 0`); 
`PN-0812000-1707` carries `718` triangles and `8` boundary edges.

Accepted L2 impact (`fitness/reports/20261125T161156Z-c85026.json`):
dev `1,167/1,381` (84.50%) → **`1,247/1,381` (90.30%)**; held-out
unchanged at `57/61` (93.44%, none of its four empty-mesh rows carry
compact nodes). A row-level diff against the baseline finds exactly
**80 fail→pass, 0 pass→fail**; 105 dev `empty-mesh` rows remain (plus
19 `missing-geometry-store` and 10 `empty-geometry-store`). No
previously passing row changes: the route only runs after the store,
surface, grid and CATSurfacicRep routes produced no triangles.

The no-surface display census is re-pinned accordingly
(`tests/test_no_surface_fallback.py::test_corpus_population_renders_the_decoded_carriers`):
of the 120 no-facet parts, 51 now mesh (41 compact see-body + the 10
pre-existing grid/facet meshes), 59 still open as display carriers
(2,671 points, 13 segments, 73,168 total mesh triangles) and 10 keep
`empty-geometry-store`. `Plaque1` is the new pinned display part: its
compact records are present but do not close byte-exact, so the display
fallback still renders its 37 points and 6 segments.

## Python ≡ Rust

`port/src/geometry/seebody_gp.rs` mirrors the Python module. On the three
W26 C06 anchors the counters match exactly:

| part | nodes | records | triangles | mesh |
|---|---:|---:|---:|---|
| `Ehi_BundleSegment1_2` | 1 | 5/5 exact | 2,919 | manifold |
| `Ehi_Equipment` | 1 | 55/55 exact | 1,008 | manifold, closed |
| `PN-0812000-1707` | 3 | 84/84 exact | 718 | manifold |

The Rust unit test `geometry::seebody_gp::tests::corpus_samples_if_available`
pins those counters when the corpus is present. The Python and Rust
fixture tests pin the same synthetic tetrahedron, the color bytes, the
walk-exact gate, the closure gate and the over-use guard.

A full Python↔Rust diff over the **80** accepted rows the route meshes
(export summary parsed-equality + PLY bytes) reports **0 mismatches**;
the same diff on the three anchors above is byte-identical.

## Adjacent fixes in the same wave

- **Pool-less multi-region fallback** (`composite.{py,rs}`): a store
  whose single-rep walk raises still decodes through the per-period
  token nodes when — and only when — the store has **no pool groups**.
  The initial fallback did not check the pool and re-opened the
  stage-8 fail-closed verdict on `05 08 01` residue
  (`tests/test_composite_export.py::test_composite_mixedwrite_subnode_stays_fail_closed`);
  the pool gate restores it. The three named Submarine samples
  (`BW-Door-Ade-YR` 3,076 tris, `Cover-hatch-carg-trp-up` 1,468,
  `MD-case Exhaust manifold-B4` 540) still close (`manifold`, `0`
  boundary edges) because all three carry `pool_group_count = 0`.
- **Colored sub-record headers** (`face_gp.{py,rs}`): the face-gp match
  generalizes from the hardcoded lavender-gray `30 04 04 ff ff ff d2 d2`
  to `[0x20|0x30] 04 04 ff ff <B><G><R>`, preserving every strict gate.
- **Viewer**: 28° crease-aware shading, additive per-triangle native
  colors (`decoded.triColors`, `Uint8Array` RGB), the
  `native`/`cad-gray` material presets, and the all-unresolved
  `.CATProduct` guidance banner.

## Remaining work

- 109 of the 189 rows still produce no mesh; their bytes carry neither
  a walk-exact compact node nor any other landed carrier.
- The per-face native color table's **end boundary** (the
  `find_color_table` law measured 131/131 zero-gap on `knurling_screw`,
  Audi R8 and Motor) is not wired into the composite route yet; the
  compact see-body route already carries its colors.
- Full Submarino re-run: the three named `empty-mesh` samples now close,
  but the 757-part sweep was not re-run in this checkout (the accepted
  `742/757` report is a different corpus snapshot).

## Reproduction

```bash
.venv/bin/python -m pytest -q tests/test_seebody_gp.py tests/test_face_gp.py \
  tests/test_composite_export.py::test_composite_mixedwrite_subnode_stays_fail_closed
cd port && cargo test --locked seebody
# the corpus-wide sweep (read-only):
.venv/bin/python -B scripts/triage/w26_seebody_census.py \
  fitness/reports/20261124T125633Z-38c46d.json
```
