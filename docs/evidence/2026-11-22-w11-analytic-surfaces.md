# Evidence: W11 — direct analytic surfaces are absent from the undecoded-variant population (the taxonomy and the template law) (2026-11-22)

**Date**: 2026-11-22
**Status**: COMPLETE as a measured **negative with taxonomy** (the dispatch's
outcome 3): the `undecoded-variant` population carries no direct analytic
surface record — no plane with bounds, no cylinder/cone/sphere
axis+radius+limits block, no NURBS payload — so no deterministic
tessellation law exists for these parts and no flip is available from
this family. The detector that classifies the population ships
(`src/catpart/geometry/analytic.py` + the Rust twin) with corpus parity.
**Target**: the 10 `undecoded-variant` rows of
`fitness/reports/20261121T103944Z-d2c9ff.json` (all dev; the wave's "≈10
official" list) plus a seeded clean-part control.
**Method**: byte-level probe `scripts/triage/w11_analytic_probe.py`
(`--selftest` pins the discriminating edges; exit 2 is the reopen
signal) over the shipped scanner `src/catpart/geometry/analytic.py` and
`port/src/geometry/analytic.rs` (parity gate
`port/tests/analytic_parity.rs`); data
`docs/evidence/data/w11-analytic-files.csv` (16 rows) and
`w11-analytic-claims.csv` (`W11-01`..`W11-08`). Read-only over the
corpus; `export.py` untouched (commit W11-07: the export path still
classifies all 10 `undecoded-variant` — 0 regressions by construction).

---

## 1. Executive summary

Three measured facts, one verdict. The population's exact-model
territory is (a) the CGM region — W2's decisive negative stands, no
coordinate arrays; (b) the `CATStdCont` store body — a template
object stream whose only analytic objects are byte-identical default
plane records; (c) the `CATPrtCont` content bulk — scalar parameters
and limits under the committed A/B frame law, no surface frames. The
E5 exact-surface route (W3) does not reach these files either: **0
class-`0x00e7` records** (cross-measured with W3's own census at
`d4a1fbc`).

| measurement | value |
| :--- | ---: |
| population rows (report `d2c9ff`) | 10 |
| verdict `no-evaluable-analytic-surface` | **10/10** (`W11-01`) |
| `a5 03 34` surface frames across the population | **0** (`W11-02`) |
| NURBS signatures (knot + weight runs, BR5 detector) | **0** (`W11-03`) |
| `01 56` plane objects observed | 19, **19/19 template** (`W11-04`) |
| bulk dialect split (object-stream / E5) | 5 / 5 (`W11-05`) |
| axis+radius shape hits after the alias guard | **0** (`W11-06`) |
| export class after the scan (unchanged path) | 10/10 `undecoded-variant` (`W11-07`) |
| control (6 clean files): template planes present | 5/6 (`W11-08`) |
| control verdicts flipping `analytic-present` | 3/6 (real carriers: 2,218 `a5` frames + 18 knot runs; 2 × 3 weight runs) |
| Python vs Rust taxonomy rows | **10/10 equal** (parity gate, 10 columns/row) |

**Verdict.** The dispatch's H1 and H2 both close negative on this
population: there is no record whose own law pins a bounded analytic
patch, and no evaluable B-spline/NURBS payload either. The 10 are
**zero-carrier parts** — the same conclusion the open-rate note reached
by the display route (`docs/evidence/2026-11-19-open-rate.md` §6), now
reached through the exact-surface question: nothing in their bytes
describes a surface.

## 2. Where the bytes are (the three-stream model)

### 2.1 The CGM region — negative (inherited)

The `CGMGeom` regions of the 10 are 1.5–3.8 KB dictionary records. W2's
decisive CGM-grid probe (`docs/evidence/2026-11-18-cgm-grid-probe.md`)
covers this population (its 128 no-facet stores include these 10): no
f64 coordinate triples, no knot runs, no weight runs anywhere in the
region. This scan re-censused the regions (only the file-header
constant family `133216.0015`/`12.1919`/`144.2031` recurs); no new
content.

### 2.2 The store body — a template object stream (the new law)

The `CATStdCont` store bodies (648–2,575 B) are a **property-bag object
stream**, not the G1 strip format (no `10 24 04 ff ff 00 00 00` wrapper,
hence no `01 06` pool — the P8 error's mechanism). Records are
`<seq u32le>`-prefixed; four header families observed: `ff ff 02 00`
objects (class `01 5X`/`07 5X`), `ff 03 01 00` property definitions,
`04 04 fd ff` property values, and `14 0c ff ff ff ff ff` scene records.

The only analytic shapes in these bytes are the class-`0x56` **plane
objects**, and every observed one carries one of two **measured default
direction pairs** (byte-exact, `TEMPLATE_PLANE_UV`):

- the Z-normal pair: u = `(0.7071, 0.7071, 0)`, v = `(0.7071, -0.7071, 0)`
  (bytes `f3 04 35 3f f3 04 35 3f 00 00 00 00 f3 04 35 3f f3 04 35 bf`);
- the Y-normal twin: u = `(0.7071, 0, 0.7071)`, v = `(-0.7071, 0, 0.7071)`.

19/19 plane objects across the population (ids `1;39;77` on the four
template-only files, `1;34;67;122` on the two CAA GSD fixtures) carry a
template pair (`W11-04`), and the seeded clean-part control shows the
same template objects in passing files' bodies (`W11-08`: 5/6) — **the
`01 56` plane record is the store format's default object, not part
geometry**. No record carries parametric bounds (nothing bounds a
patch), and no `01 57`–`01 58` analytic family was observed. The
`gsd_analytic_elements` fixture's per-part content is seven scene
records and 18 property values carrying scalars (the box dimensions
`(50, 20, 30)`, the vector+norm pair `30.8221 = |(15, 25, 10)|`, one
π/4 angle) — feature parameters, not surfaces.

### 2.3 The content bulk — scalar limits, no surfaces

The `CATPrtCont` content bulk splits 5 object-stream / 5 E5 (`W11-05`).
The object-stream halves frame 91–95 % of content under the committed
A/B frame law (573/229/120/99/409 frames; e.g. WELD-W1 12,660 of
13,324 B). Their frame classes carry scalar parameters and limits only:
`0x06`/`0x18`/`0x24` limit ladders (±1e6/±5e5/±1e5/±5e4), `0x02`/`0x0e`
/`0x27`/`0x5b` per-part scalars (WELD-W1's `±6.5043`/`±0.0909`,
BENDABLE-PIPE's `2.7967`/`14.2935`/`25.3871`, gsd's `50`/`20`/`30`).
No `a5 03 34` frame exists anywhere in the population (`W11-02`), and
the frame payloads yield 0 axis+radius tuples after the fixed-point
alias guard (`W11-06` — the guard removes the measured 2^-k ladder
alias that produced 3 false cylinder hits on `550.000` pre-guard).

The E5 halves are a **4,116-B template stream**: byte-comparison across
the five files shows ≤ 20 differing bytes per pair (a few per-file
scalars); they frame nothing (0 clusters) and carry no record the
shipped E5 machinery admits.

### 2.4 The E5 cross-measurement (W3's route, not re-derived)

W3's class-table algebra (`origin/marathon/w3-e5-algebra` at `d4a1fbc`,
`docs/evidence/2026-11-22-e5-class-table.md`) decodes exact B-spline
surfaces from class `0x00e7` of the `e5 0d` stream — including the
degree-(3,1) sweeps that model analytic cylinders/planes. That route
does **not** reach this population: running W3's committed census
anchored on the 10 sha16s (`probe_e5_class_table.py --anchors …`,
from the W3 worktree) reports 5 writer tails tokenizing cleanly and
**`CT-03` = 0/0 — zero `0x00e7` records**, 0 parsed, 0 evaluable.
Consistent with W3's corpus A/B (0 error-class changes): the 15
display→mesh flips the route ships live elsewhere. H2 therefore closes
as "no NURBS payload outside W3's route": the route itself is not
duplicated here.

### 2.5 The carrier census (all routes, one table)

Every shipped carrier route runs empty on the population (measured
through the shipped scans, the same calls the exporter makes):

| route | result on the 10 |
| :--- | :--- |
| facet store (`01 06` pool + facets) | 0 pool groups, 0 facet candidates (the P8 error) |
| `a5 03 34` compact-head surfaces | 0 candidates |
| E5 class-`0x00e7` surfaces (W3) | 0 records |
| structured point grid | no mesh |
| `CATSurfacicRep` patch streams (face-gp, BagRep) | `scan_part` → `None` on all 10 |
| display carriers | 0 pool points, 0 run points, 0 arrays; 1 undecoded `33 3X` curve record on the two GSD fixtures |

The two CAA fixture names say it too: `negative_empty_surface_imported`
(a negative test fixture) and the five harness/assembly-context parts.

## 3. Taxonomy of the 10

| sha16 | file | store body | planes (tpl) | bulk dialect | per-part content |
| :--- | :--- | ---: | :--- | :--- | :--- |
| `3590d6f9f029e8f8` | WELD-W1 | 648 B | 0 | object-stream (573 frames, 12,660 B) | limits ±5e4/±1e5, scalars ±6.5043/±0.0909 |
| `3a6238219bc6f133` | TypedPartforBKT | 1,085 B | 3 (3) | E5 template | ≤ 20 differing bytes vs the other E5 files |
| `3c6ea0125d026aee` | Part3 | 1,085 B | 3 (3) | E5 template | idem |
| `40120449192bc8b5` | CAAPstBrowsePstPart | 843 B | 3 (3) | E5 template | idem |
| `540d2d33d9e9a3c7` | gsd_analytic_elements | 2,165 B | 4 (4) | object-stream (229 frames, 5,623 B) | dims (50,20,30), \| (15,25,10) \| = 30.8221, π/4 |
| `67b37d06c40d6eed` | negative_empty_surface_imported | 1,592 B | 3 (3) | object-stream (120 frames, 2,574 B) | scalars (20, 10, 10) |
| `731c6b5f3f20425f` | CAAPstPrdProperties_Part | 872 B | 0 | E5 template | −129.0651 f64 param ×62 (CATBRepModeContainer) |
| `b859a61d1ab6c00d` | 550.000_NOTE A | 2,575 B | 0 | object-stream (99 frames, 2,187 B) | −41.7266 f64 param ×62 (one per ~84-B record) |
| `d4115ad2bdebe6c0` | CAAMmrPartCopy_Comp1 | 1,226 B | 3 (3) | E5 template | idem TypedPart family |
| `e87d1693be7068f9` | BENDABLE-PIPE-BW-4in | 696 B | 0 | object-stream (409 frames, 9,387 B) | limits ±5e4/±1e5, scalars 2.7967/14.2935/25.3871 |

Every row: `no-evaluable-analytic-surface`, export class
`undecoded-variant` unchanged (`W11-01`, `W11-07`).

## 4. What this does and does not say

- **It says no direct analytic surface record exists in these bytes.**
  It does not say the parts are broken: they are CAA edu samples
  (8/10) whose `.CATPart` carries feature parameters and a template
  store without a solid, or whose geometry lives in the assembly
  context. The `undecoded-variant` class is the honest classification.
- **The template plane law generalizes**: the same `01 56` default
  objects appear in passing files' bodies (`W11-08`), so the family is
  a format constant — a future decoder must not mistake them for part
  planes.
- **The shape census is diagnostic, never verdict-driving.** Its
  phase-tolerant f32 reads alias (the measured 2^-k ladder family);
  the fixed-point guard removes it, and a unit-vector pair still does
  not discriminate intent (axis frames and rotation rows look
  identical). The verdict flips only on law-pinned detections: a
  per-part `01 56` object, an `a5 03 34` frame, or a NURBS signature.
- **W3's route is not re-derived**: the E5 membership figure is a
  cross-measurement from W3's committed probe at `d4a1fbc`, cited, not
  re-implemented.
- **No gate or source of the export path changed.** The scanner is an
  additive module; the A/B column (`export_class`) re-runs the shipped
  `build_export` per file and shows the pre-W11 classification on all
  10.

## 5. Reopening criteria

1. **A population file gains an analytic record** — the probe exits 2.
   Any future corpus drop whose no-pool parts carry per-part `01 56`
   planes (with bounds), or cylinder/cone/sphere axis+radius blocks,
   flips the taxonomy mechanically.
2. **The store-body object-stream framing law** — the seq-prefixed
   records frame by header-to-header spans here; a class/length
   discriminator (the same law W2's CGM probe named) would let the
   per-part scalars bind to their records. Needed before any scalar
   (e.g. gsd's π/4, the ±500000 ladders) can drive geometry.
3. **The `b2` bulk classes** — the frame law tiles 91–95 % of the
   object-stream files; the class bytes (`0x06`, `0x0e`, `0x27`, `0x5b`,
   …) are a measured vocabulary, not schemas. A schema recovery could
   expose feature limits that pair with sketch profiles — the profiles
   themselves are not in these bytes.
4. **The two `×62` f64 parameter ladders** (`550.000`'s −41.7266,
   CAAPstPrd's −129.0651) — per-record parameters of a repeated ~84-B
   record; their meaning (angle? offset?) is open and does not bound a
   surface.

## 6. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python -B scripts/triage/w11_analytic_probe.py --selftest
.venv/bin/python -B scripts/triage/w11_analytic_probe.py
.venv/bin/python -m pytest tests/test_analytic_surfaces.py -q
(cd port && cargo test --lib geometry::analytic && cargo test --test analytic_parity)
# the W3 cross-measurement (from the W3 worktree, at d4a1fbc):
cd ~/marathon-wt/w3 && .venv/bin/python -B -I scripts/triage/probe_e5_class_table.py \
    --anchors 3590d6f9f029e8f8,3a6238219bc6f133,3c6ea0125d026aee,40120449192bc8b5,540d2d33d9e9a3c7,67b37d06c40d6eed,731c6b5f3f20425f,b859a61d1ab6c00d,d4115ad2bdebe6c0,e87d1693be7068f9
```

The probe streams one part at a time (mmap-sized reads only; the
population is 10 files ≤ 81 KB), resolves corpus files by sha256
(drifted files surface as `MISSING`, never silently measured), writes
the two CSVs deterministically (a re-run is byte-identical), and exits
2 on any population flip. The parity gate re-runs the Rust scanner
against the committed CSV; without a corpus checkout it skips (the
corpus-free fixture parity lives in the mirrored unit tests, 22 Python
+ 17 Rust).

## 7. Detector honesty

- **What "template" means**: the byte-exact presence of one of the two
  measured default direction pairs inside the `01 56` object span. It
  is a byte law, not a value law — no float comparison.
- **What the span walk does not frame**: bytes before the first header
  (the body's preamble) and the tail after the last one. The walk
  classifies record content, not record boundaries against a length
  law (no length discriminator exists — criterion 2).
- **What the shape census does not discriminate**: intent (axis frame
  vs rotation row vs analytic axis), phase aliases beyond the dyadic
  ladder family, and spheres entirely (no law distinguishes a center
  from an axis; spheres are reported absent rather than guessed).
- **The selftest pins the discriminating edges**: template vs per-part
  plane, alias vs real axis, both frame families plus the refused
  `b1` byte, and the knot/weight guard set.
