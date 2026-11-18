# Evidence: what the L2 export recovers — the viewer-fidelity proxy harness (2026-11-18)

Baseline: **`df02aed`** (`main`), the commit this run measures. Corpus:
`manifests/corpus-manifest.csv` (read-only). Every number below comes from the
shipped Python decode — no CATIA, no new laws, no `src/` change.

Artifacts:

- harness: [`scripts/triage/measure_viewer_fidelity.py`](../../scripts/triage/measure_viewer_fidelity.py)
- data: [`docs/evidence/data/fidelity-2026-11-18.csv`](data/fidelity-2026-11-18.csv) (20 rows)
- pins: [`tests/test_measure_viewer_fidelity.py`](../../tests/test_measure_viewer_fidelity.py) (corpus-free synthetic fixtures)

## Why

L2 "pass" (`catpart-export` through the fitness runner) certifies **topology
legality**: the mesh is non-empty, edges are manifold, the bounding box is
finite and plausible, and degenerate triangles stay under the cap. It says
nothing about **surface completeness**. The 2026-11-18 viewer audit measured
four files by hand and found L2-pass parts with most of their surface missing
(`docs/releases/v1.0.md`, "Viewer fidelity"). This harness makes that
measurement repeatable, comparable across parts, and explicit about what its
normalized numbers do — and do not — mean.

## Method

`measure_path` replays the shipped export seam,
`catpart.geometry.export._export_data` (the same private seam
`scripts/triage/not_manifold_audit.py` and the stage-14 probe already replay;
`build_export` wraps it unchanged). Nothing is re-decoded and no decode law is
added. A classified `ExportError` is reported as a row with its
`error_class`/`error_detail` and no metrics; a file missing from disk is
`unavailable`, never silently skipped.

Per part the CSV records:

| Column | Meaning |
|---|---|
| `pool_vertices` | the exporter's `vertex_count` (the decoded pool; for composite stores, the re-listed element space) |
| `used_vertices` | how many of those any exported triangle references |
| `triangle_count` | emitted triangles |
| `exported_area_mm2` | sum of the emitted triangles' Euclidean areas (`math.fsum`, 3-D cross product) |
| `degenerate_count` | the exporter's skipped degenerate strips (`degenerate_triangle_count`) |
| `boundary_edge_count` | edges used exactly once |
| `manifold` / `closed` / `oriented` | the exporter's `mesh` invariants |
| `bbox_diag_mm` | diagonal of the exporter's bounding box, plus its min/max |
| `warnings` | the exporter's warning records **verbatim** (class + detail), as compact JSON |

## The two normalized proxies — what they mean and what they do not

- `used_vertex_fraction` = `used_vertices / pool_vertices`.
- `area_density` = `exported_area_mm2 / bbox_diag_mm²`.

**They are coverage proxies, not a fidelity claim and not ground truth.** The
corpus carries no reference surface, so the numerator is only what the
exporter *emitted* and the denominator is only the exporter's own envelope:

- A low fraction/density does **not** prove a decode bug. A legitimately
  sparse part (open shell, wire-frame geometry, a solid stored outside the
  decoded CGM payload) can score low for content reasons.
- A high fraction/density does **not** prove completeness. `area_density` is
  not bounded by 1: a folded, self-overlapping or multi-shell mesh sums area
  over the same envelope (the `LedStrips_Smooth` row scores 24.55).
- Neither proxy measures missing interior surface by area; `used_vertex_fraction`
  only says how much of the *found* pool the triangles touch. A part can use
  every pool vertex and still recover a fraction of its true surface.
- The bounding box is the pool's, not the true part's; an outlier vertex or a
  declared store envelope changes the denominator.
- Units: the format's unit field is **not decoded** (the units probe is a
  documented negative). Coordinates are in the part's stored units; the `_mm`
  suffix follows the repo/release convention and the ratio itself is
  unit-free.

Read the proxies as a **screen**: they separate "the export emitted a
plausible amount of surface inside its envelope" from "it emitted only a rim,
a sliver, or nothing". They do not rank fidelity.

## The sample (20 parts)

The run is fixed and reproducible:

- **4 audit anchors** (the release-note files): `Gabarit_trou_alu_alpha`,
  `labios/main`, `SP02_BETA_COIFFE` (the `new_catia` copy the audit measured —
  424 pool vertices), `CAAMmrPartCopy_Comp1`.
- **16 deterministic picks** from the accepted fitness row
  `20261118T171127Z-0882ce`, covering the L2 classes: `pass:closed`,
  `pass:curve-entry`, `pass:open-shell`, `fail:empty-mesh`, `fail:not-manifold`,
  `fail:degenerate-triangles`, `fail:undecoded-variant`,
  `fail:missing-geometry-store`.

Selection rule (implemented in `select_sample`): anchors keep command order,
then two rows per class in the order above, each class sorted by SHA-256 and
excluding already-chosen rows; a class with fewer than its quota (here only
`fail:degenerate-triangles`, with one corpus file) is backfilled in SHA-256
order (`sample_class = backfill`). The report and manifest are joined by
SHA-256. Same inputs, same 20 rows.

| `sample_class` | rows |
|---|---|
| `audit-anchor` | 4 |
| `pass:closed` | 2 |
| `pass:curve-entry` | 2 |
| `pass:open-shell` | 2 |
| `fail:empty-mesh` | 2 |
| `fail:not-manifold` | 2 |
| `fail:degenerate-triangles` | 1 |
| `fail:undecoded-variant` | 2 |
| `fail:missing-geometry-store` | 2 |
| `backfill` | 1 |

## Results

Conservative summary: rows that did not export (classified error, unavailable)
count as **zero coverage** for the min/median/max, because "how much of the
part the exporter recovered" is zero there. 15/20 exported.

| report L2 | parts | exported | triangles (min/median/max) | area mm² (min/median/max) | `used_vertex_fraction` (min/median/max) | `area_density` (min/median/max) |
|---|---|---|---|---|---|---|
| pass | 9 | 9 | 12 / 160 / 4,420 | 1.678 / 921.8 / 1.176e6 | 0.0649 / 0.7839 / 1.000 | 0.0159 / 0.4288 / 1.043 |
| fail | 11 | 6 | 0 / 0 / 30,292 | 0 / 0 / 3.368e7 | 0 / 0 / 0.2822 | 0 / 0 / 24.55 |

Exported-only ranges inside the fail group (the 6 rows that did decode) are
0 / 134 / 30,292 triangles and `used_vertex_fraction` 0 / 0.0500 / 0.2822: the
fail rows that export are small and barely use their pool; the other five
contribute nothing at all. The pass group's spread is wide — the box-like
`F09VP` row is 12 triangles of a fully used pool, while the audit anchors are
in the thousands of triangles with 45–78% of their pool used — which is the
point: L2 status does not predict coverage.

### The four audit anchors (raw numbers reproduce the release note)

| path | status | pool | triangles | area mm² | `used_vertex_fraction` | `area_density` |
|---|---|---|---|---|---|---|
| `Gabarit_trou_alu_alpha.CATPart` | L2 pass | 7,816 | 4,420 | 401.892 | 0.449 | 0.0159 |
| `labios/main.CATPart` | L2 pass | 4,813 | 4,261 | 2,299.087 | 0.784 | 0.5704 |
| `SP02_BETA_COIFFE.CATPart` (`new_catia`) | L2 fail, `empty-mesh` | 424 | 0 | 0 | 0 | 0 |
| `CAAMmrPartCopy_Comp1.CATPart` | L2 fail, `undecoded-variant` | — | — | — | — | — |

The triangle counts and areas match the audit exactly (4,420 / 402 mm² and
4,261 / 2,299 mm²). Do **not** compare the release note's rough "~3% / ~41% of
envelope" with `area_density`: the note used a looser envelope estimate
(one bbox face), while this harness divides by the full bounding-box diagonal
squared. The raw counts and area are the reproducible facts.

## Warnings observed (verbatim classes, files affected)

`curve-entry-loops-unexported=8`, `open-shell=10`, `unused-pool-vertices=9`,
`no-facet-records=3`, `degenerate-triangles-skipped=2`,
`unresolved-facet-family=1`, `duplicate-triangles-deduped=1`. The CSV keeps
each warning's full `detail` string unchanged, including the per-file counts
(e.g. "4,308 of 7,816 element-space vertices are not referenced by any
exported triangle").

## Optional screenshot evidence

`--screenshot DIR` drives the shipped viewer headlessly with the same file
(Playwright; the `scripts/assembly_viewer_acceptance.py` static-server pattern),
saves one PNG per part (`<sha16>.png`) and records `viewer_status`,
`canvas_visible`, `canvas_has_content` and `canvas_nonbackground_fraction`. A
pixel is non-background when any RGB channel differs from the image's dominant
colour by more than 8; the PNG reader is stdlib-only (`zlib` + PNG filters). A
part whose canvas is hidden — the viewer's `empty-mesh` failure state — records
`canvas_visible=false`, `canvas_has_content=false`, and its PNG is the page
screenshot documenting the failure, not a canvas capture. The run above was
made without this flag (the screenshot PNGs are local evidence and are not
committed); the flag and the PNG/canvas logic are pinned by the test module.

## Limits

- **Proxy, not fidelity.** No ground-truth surface exists in the corpus; these
  numbers cannot say "this part is 41% recovered" in any absolute sense.
- **Sample, not corpus rates.** 20 of 1,436 L2 parts. Nothing here changes the
  fitness record; L2 stays 1,033/1,381 Dev and 56/61 held-out at `df02aed`.
- **Conservative summary.** The table above zeroes non-exported rows; the CSV
  leaves their metric cells empty so "no metrics" and "zero" stay
  distinguishable.
- **Composite counts.** For composite stores `pool_vertices` is the element
  space the exporter re-lists as its vertex set, not a separate raw-pool
  count.
- **Browser variance.** Screenshot pixels depend on the local Chromium and
  GPU; that path is evidence, never a gate.

## Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH   # this host
.venv/bin/python scripts/triage/measure_viewer_fidelity.py \
  --manifest --sample-size 20 \
  --anchor CATIA/CATIA_vol/Usinage/Gabarit_trou_alu_alpha.CATPart \
  --anchor 'diseño_3d/labios/main.CATPart' \
  --anchor CATIA/new_catia/SP02_BETA/SP02_BETA_COIFFE.CATPart \
  --anchor sample/CAAMechanicalModeler.edu/InputData/CAAMmrPartCopy_Comp1.CATPart \
  --out docs/evidence/data/fidelity-2026-11-18.csv

.venv/bin/python -m pytest -q tests/test_measure_viewer_fidelity.py
```
