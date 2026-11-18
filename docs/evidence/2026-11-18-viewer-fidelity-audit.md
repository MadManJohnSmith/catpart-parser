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
- **Sample, not corpus rates.** 20 of 1,442 L2 parts. Nothing here changes the
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

## Post-weld re-measurement (2026-11-18)

**Base: `e783d03` (`main`)** — the merge of `c3e1653` (this harness and its
gate) and `ae254b1` (the per-loop dup-pin weld behind the mesh-manifold
guard). The sample, anchors, report row and command are the baseline's,
unchanged; only `--out` differs. Data:
[`fidelity-2026-11-18-post-weld.csv`](data/fidelity-2026-11-18-post-weld.csv)
(20 rows, SHA-256 `d741503c9f66be512b5d90ff2d3632ac16ec18878423c08cc2ef8c0a1d913775`,
byte-identical on a second run).

The comparison is like-for-like: the same 20 parts, the same deterministic
selection, the same shipped `_export_data` seam. The baseline row for each
part is [`fidelity-2026-11-18.csv`](data/fidelity-2026-11-18.csv) at
`df02aed`; "after" is the new CSV. `sample_index` is the join key (the CSV's
`path` column carries the full path). `◆` marks a coverage change; `†` marks
an audit anchor. Metric cells are `before → after`; an em dash is a row that
did not export before or after.

### Totals

| metric | before (`df02aed`) | after (`e783d03`) |
|---|---|---|
| parts exported / sampled | 15 / 20 | 15 / 20 |
| pass rows exported | 9 / 9 | 9 / 9 |
| fail rows exported | 6 / 11 | 6 / 11 |
| `used_vertex_fraction` pass, min / median | 0.064858 / 0.783919 | 0.066181 / 0.820513 |
| `used_vertex_fraction` fail, min / median | 0 / 0 | 0 / 0 |
| triangles, all exported rows | 50,318 | 182,098 |
| triangles, exported rows excluding `LedStrips_Smooth` | 20,026 | 43,952 |
| exported area, all exported rows (mm²) | 35,028,907.871 | 516,163,640.545 |
| exported area excluding `LedStrips_Smooth` (mm²) | 1,351,528.286 | 1,361,732.757 |
| parts that moved from no triangles to triangles | — | **0** |

Medians follow the conservative summary above: a non-exported row counts as
zero coverage. The fail min/median stay zero because five partitions still
fail to export and three still emit no triangles; only the exported fail
rows move. The aggregate area is not a fidelity total: it is dominated by one
already-non-manifold row (see below) and sums overlapping triangles.

### Per part

| # | part | report class | triangles | exported_area_mm2 | used_vertex_fraction | manifold | area_density |
|---|---|---|---|---|---|---|---|
| 1†◆ | `Gabarit_trou_alu_alpha` | pass:curve-entry | 4,420 → 5,338 | 401.892 → 714.027 | 0.448823 → 0.566402 | True → True | 0.015886 → 0.028224 |
| 2†◆ | `labios/main` | pass:curve-entry | 4,261 → 4,464 | 2,299.087 → 5,410.181 | 0.783919 → 0.819447 | True → True | 0.570431 → 1.34233 |
| 3† | `SP02_BETA_COIFFE (new_catia)` | fail:empty-mesh | 0 → 0 | 0.000 → 0.000 | 0.0 → 0.0 | True → True | 0.0 → 0.0 |
| 4† | `CAAMmrPartCopy_Comp1` | fail:undecoded-variant | — → — | — → — | — → — | — → — | — → — |
| 5 | `F09VP` | pass:closed | 12 → 12 | 401.143 → 401.143 | 1.0 → 1.0 | True → True | 0.428772 → 0.428772 |
| 6 | `10uF` | pass:closed | 12 → 12 | 1.678 → 1.678 | 1.0 → 1.0 | True → True | 1.043158 → 1.043158 |
| 7◆ | `SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT` | pass:curve-entry | 388 → 512 | 921.789 → 1,121.686 | 0.765799 → 0.959108 | True → True | 0.21659 → 0.26356 |
| 8◆ | `SP02_MAQUETTE_VITE` | pass:curve-entry | 105 → 108 | 136,491.219 → 138,727.888 | 0.064858 → 0.066181 | True → True | 0.026794 → 0.027233 |
| 9 | `SpatialLoft-4072E` | pass:open-shell | 28 → 28 | 1,176,263.968 → 1,176,263.968 | 0.820513 → 0.820513 | True → True | 0.71639 → 0.71639 |
| 10 | `MutliSupport` | pass:open-shell | 160 → 160 | 29,970.323 → 29,970.323 | 1.0 → 1.0 | True → True | 0.863988 → 0.863988 |
| 11 | `SP02_BETA_COIFFE (CATIA_vol)` | fail:empty-mesh | 0 → 0 | 0.000 → 0.000 | 0.0 → 0.0 | True → True | 0.0 → 0.0 |
| 12 | `Shell_VStf_006.1` | fail:empty-mesh | 0 → 0 | 0.000 → 0.000 | 0.0 → 0.0 | True → True | 0.0 → 0.0 |
| 13◆ | `LedStrips_Smooth` | fail:not-manifold | 30,292 → 138,146 | 33,677,379.585 → 514,801,907.789 | 0.254465 → 0.692983 | False → False | 24.547972 → 375.247212 |
| 14◆ | `Guntle.ver5` | fail:not-manifold | 268 → 868 | 4,495.893 → 6,921.069 | 0.099964 → 0.277878 | False → False | 0.092787 → 0.142838 |
| 15◆ | `_NPart#194321` | fail:degenerate-triangles | 10,030 → 31,175 | 268.429 → 2,018.729 | 0.282168 → 0.842457 | True → True | 0.059496 → 0.447441 |
| 16 | `attribut` | fail:undecoded-variant | — → — | — → — | — → — | — → — | — → — |
| 17 | `CAACafSearch` | fail:undecoded-variant | — → — | — → — | — → — | — → — | — → — |
| 18 | `BundleSegment3` | fail:missing-geometry-store | — → — | — → — | — → — | — → — | — → — |
| 19 | `CAAAxisSystemCreation` | fail:missing-geometry-store | — → — | — → — | — → — | — → — | — → — |
| 20◆ | `_NPart#194294` | pass:curve-entry | 342 → 1,275 | 12.864 → 182.064 | 0.124956 → 0.453843 | True → True | 0.023955 → 0.339034 |

### Highlights

- **`labios/main`** (the fix's motivating part): 4,261 → 4,464 triangles,
  2,299.087 → **5,410.181 mm²**, `used_vertex_fraction` 0.784 → 0.819,
  manifold True → True. This reproduces the weld note's fix-1+2 row exactly.
- **`Gabarit_trou_alu_alpha`**: 4,420 → 5,338 triangles, 401.892 →
  714.027 mm², uvf 0.449 → 0.566, manifold True → True (10 welded loops).
- **`SP02_BETA_COIFFE`** (the `new_catia` anchor): **unchanged at 0
  triangles / 0 mm²**. It still reports `no-facet-records`; the weld does not
  create a mesh from a store whose facet loops do not map. The `CATIA_vol`
  copy and `Shell_VStf_006.1` are likewise still empty-mesh.
- **`CAAMmrPartCopy_Comp1`**: still `undecoded-variant`; no metrics.
- **Every changed row is a composite store**: 8 of 20. Seven gained
  `curve-entry-loops-exported-dup-pin` (Gabarit 10 loops, labios 10,
  `SP02_ALPHA5...` 12, `LedStrips_Smooth` 32,565, `Guntle.ver5` 161,
  `_NPart#194321` 1,711, `_NPart#194294` 54); `SP02_MAQUETTE_VITE` gained 3
  triangles without a dup-pin warning (the width-rank change). The other 12
  rows are byte-for-byte unchanged in every metric.
- **No row changed report class or status**, and **no `manifold` flag
  changed** (the two `not-manifold` rows stay `not-manifold`; every `True`
  stays `True`). **0 parts moved from zero triangles to a non-empty mesh.**
- The fail-class aggregate is dominated by `LedStrips_Smooth`, which was
  already `not-manifold`: 30,292 → 138,146 triangles and `area_density`
  24.55 → 375.25. A density that far above 1 is folded/overlapping emitted
  area inside the bounding box, exactly the case the proxy's limits call
  out; it is **not** recovered surface, and the row's L2 failure is
  unchanged.

Warning classes over the sample before → after:
`curve-entry-loops-unexported` 8 files → 3; new
`curve-entry-loops-exported-dup-pin` 7;
`duplicate-triangles-dedup-declined` 0 → 1 (`LedStrips_Smooth`);
`open-shell` 10 → 10; `unused-pool-vertices` 9 → 9;
`no-facet-records` 3 → 3; `degenerate-triangles-skipped` 2 → 2;
`duplicate-triangles-deduped` 1 → 1; `unresolved-facet-family` 1 → 1.

### Still a proxy, not fidelity

The weld changes what the exporter *emits*, and that is exactly what these
numbers measure: more of the found element space is referenced, and more
triangle area is emitted inside the same bounding box. **That is not a
fidelity claim.** The corpus still carries no reference surface, so the run
cannot say how much of either part is truly recovered; `area_density` is
still not bounded by 1, and `used_vertex_fraction` still only describes the
found pool. The movement is evidence that the weld emits the loops it
accepts, not that the resulting surface matches the part. The screen's
verdict is unchanged: 15/20 export, the same 5 rows fail to export, and the
three empty-mesh rows stay empty.

## Post-extended-header re-measurement (2026-11-18)

**Base: `8c1b120` (`main`, merged as `4b51443`)** — the extended-header facet
family (`bce5073`, `b26f563`, `def16ea`): escaped counts are read, the
`0x47`/`0x4f` records are ported (Python + Rust parity) and their geometry is
gated on manifold assembly. The comparison baseline is the post-weld run at
`e783d03`. The harness and its pin module are **byte-identical** to that
baseline (verified with `diff`), and the sample, anchors, report row and
command are unchanged; only `--out` differs. Data:
[`fidelity-2026-11-18-post-extended.csv`](data/fidelity-2026-11-18-post-extended.csv)
(20 rows, SHA-256 `943e3ed18e5ec663be6d0f9a24d0bc54df3a738ccc1d6244f362b24bcee9c7fd`,
byte-identical on three runs).

`◆` marks a coverage change, `†` an audit anchor. Metric cells are
`before (e783d03) → after (8c1b120)`; an em dash is a row that did not export
before or after.

### Totals

| metric | before (`e783d03`) | after (`8c1b120`) |
|---|---|---|
| parts exported / sampled | 15 / 20 | 15 / 20 |
| pass rows exported | 9 / 9 | 9 / 9 |
| fail rows exported | 6 / 11 | 6 / 11 |
| sampled rows emitting triangles | 12 / 20 | **15 / 20** |
| `used_vertex_fraction` pass, min / median | 0.066181 / 0.820513 | 0.461946 / 1.0 |
| `used_vertex_fraction` fail, min / median | 0 / 0 | 0 / 0.320319 |
| triangles, all exported rows | 182,098 | 221,869 |
| triangles, exported rows excluding `LedStrips_Smooth` | 43,952 | 69,764 |
| exported area, all exported rows (mm²) | 516,163,640.545 | 1,088,166,151.874 |
| exported area excluding `LedStrips_Smooth` (mm²) | 1,361,732.757 | 24,046,498.514 |
| parts that moved from no triangles to triangles | — | **3** |

Medians stay conservative: a non-exported row counts as zero coverage. The
fail median rises only to 0.320319 because five sampled rows still fail to
export (four classified errors and `CAAMmrPartCopy_Comp1`); the three rows
that used to export an empty mesh now carry real triangles. The aggregate area
is still dominated by one non-manifold row and sums overlapping triangles; it
is not a fidelity total.

### Per part

| # | part | report class | triangles | exported_area_mm2 | used_vertex_fraction | manifold | area_density |
|---|---|---|---|---|---|---|---|
| 1†◆ | `Gabarit_trou_alu_alpha` | pass:curve-entry | 5,338 → 15,688 | 714.027 → 27,082.120 | 0.566402 → 1.0 | True → True | 0.028224 → 1.070514 |
| 2†◆ | `labios/main` | pass:curve-entry | 4,464 → 8,995 | 5,410.181 → 7,024.812 | 0.819447 → 1.0 | True → True | 1.34233 → 1.742939 |
| 3†◆ | `SP02_BETA_COIFFE (new_catia)` | fail:empty-mesh | 0 → 424 | 0.000 → 636.850 | 0.0 → 1.0 | True → True | 0.0 → 0.012489 |
| 4† | `CAAMmrPartCopy_Comp1` | fail:undecoded-variant | — → — | — → — | — → — | — → — | — → — |
| 5 | `F09VP` | pass:closed | 12 → 12 | 401.143 → 401.143 | 1.0 → 1.0 | True → True | 0.428772 → 0.428772 |
| 6 | `10uF` | pass:closed | 12 → 12 | 1.678 → 1.678 | 1.0 → 1.0 | True → True | 1.043158 → 1.043158 |
| 7◆ | `SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT` | pass:curve-entry | 512 → 1,066 | 1,121.686 → 3,548.697 | 0.959108 → 1.0 | True → True | 0.26356 → 0.833828 |
| 8◆ | `SP02_MAQUETTE_VITE` | pass:curve-entry | 108 → 750 | 138,727.888 → 675,346.063 | 0.066181 → 0.461946 | True → True | 0.027233 → 0.132575 |
| 9 | `SpatialLoft-4072E` | pass:open-shell | 28 → 28 | 1,176,263.968 → 1,176,263.968 | 0.820513 → 0.820513 | True → True | 0.71639 → 0.71639 |
| 10 | `MutliSupport` | pass:open-shell | 160 → 160 | 29,970.323 → 29,970.323 | 1.0 → 1.0 | True → True | 0.863988 → 0.863988 |
| 11◆ | `SP02_BETA_COIFFE (CATIA_vol)` | fail:empty-mesh | 0 → 2,764 | 0.000 → 60,936.404 | 0.0 → 1.0 | True → True | 0.0 → 1.310128 |
| 12◆ | `Shell_VStf_006.1` | fail:empty-mesh | 0 → 1,961 | 0.000 → 22,020,586.541 | 0.0 → 0.320319 | True → True | 0.0 → 0.045848 |
| 13◆ | `LedStrips_Smooth` | fail:not-manifold | 138,146 → 152,105 | 514,801,907.789 → 1,064,119,653.360 | 0.692983 → 0.718802 | False → False | 375.247212 → 775.653562 |
| 14◆ | `Guntle.ver5` | fail:not-manifold | 868 → 3,060 | 6,921.069 → 41,415.443 | 0.277878 → 0.722122 | False → False | 0.142838 → 0.854739 |
| 15◆ | `_NPart#194321` | fail:degenerate-triangles | 31,175 → 31,205 | 2,018.729 → 2,585.261 | 0.842457 → 0.842943 | True → True | 0.447441 → 0.57301 |
| 16 | `attribut` | fail:undecoded-variant | — → — | — → — | — → — | — → — | — → — |
| 17 | `CAACafSearch` | fail:undecoded-variant | — → — | — → — | — → — | — → — | — → — |
| 18 | `BundleSegment3` | fail:missing-geometry-store | — → — | — → — | — → — | — → — | — → — |
| 19 | `CAAAxisSystemCreation` | fail:missing-geometry-store | — → — | — → — | — → — | — → — | — → — |
| 20◆ | `_NPart#194294` | pass:curve-entry | 1,275 → 3,639 | 182.064 → 699.209 | 0.453843 → 0.862408 | True → True | 0.339034 → 1.302046 |

### Highlights

- **The three formerly empty-mesh parts now export triangles**: the
  `new_catia` anchor `SP02_BETA_COIFFE` **0 → 424 triangles / 636.850 mm²**
  (uvf 1.0), the `CATIA_vol` copy **0 → 2,764 / 60,936.404 mm²** (uvf 1.0,
  **closed**, zero boundary edges, no warning at all) and `Shell_VStf_006.1`
  **0 → 1,961 / 22,020,586.541 mm²** (uvf 0.320). The `no-facet-records`
  warning disappears from all three: the extended family supplies the facet
  records that had no mapping before. None changes report class — all three
  are still L2 `fail:empty-mesh`, the row the accepted fitness report
  classified at the time of selection.
- **`Gabarit_trou_alu_alpha`** (audit anchor): 5,338 → **15,688** triangles,
  714.027 → **27,082.120 mm²**, uvf 0.566 → **1.0**, boundary edges
  3,510 → **0**, and **`closed` False → True**. The dup-pin warning grows
  from 10 to **542** loops. It is now an exported closed mesh.
- **`labios/main`** (the weld's motivating part): 4,464 → **8,995**
  triangles, 5,410.181 → **7,024.812 mm²**, uvf 0.819 → **1.0**, boundary
  edges 3,408 → 651, still `closed=False`. Dup-pin loops 10 → 29.
- **Every changed row is a composite store**: 11 of 20. The four non-composite
  success rows (`F09VP`, `10uF`, `SpatialLoft-4072E`, `MutliSupport`) are
  unchanged in every metric, and the five undecodable rows are unchanged
  errors. No report class or status changed; **no `manifold` flag changed**
  (the two `not-manifold` rows stay `False`). `closed` changed on three rows:
  Gabarit `False → True`, `new_catia` and `Shell_VStf_006.1` `True → False`
  (the last two were vacuously closed while empty).
- **`LedStrips_Smooth`** (already `not-manifold`) dominates the aggregate:
  138,146 → 152,105 triangles and `area_density` 375.25 → 775.65. Its new
  `extended-header-geometry-declined` warning records **493** `0x47`/`0x4f`
  records refused by the manifold-assembly gate, so the gain is what survived
  the gate, not the whole discovered family. A density in the hundreds is
  folded/overlapping emitted area inside the bounding box — **not** recovered
  surface, and its L2 failure is unchanged.
- Several rows now post `area_density` above 1 (`Gabarit` 1.07, `labios`
  1.74, `new_catia` 1.31, `_NPart#194294` 1.30). That is expected inside a
  bounding-box envelope (a compact solid can exceed 1 as well as a folded
  mesh); it is not evidence of completeness.
- The extended family moved loops as well as triangles: dup-pin loop counts
  rise on nearly every composite row (`Gabarit` 10 → 542, `labios` 10 → 29,
  `SP02_ALPHA5...` 12 → 44, `LedStrips_Smooth` 32,565 → 40,609,
  `Guntle.ver5` 161 → 499, `_NPart#194321` 1,711 → 1,717,
  `_NPart#194294` 54 → 166) and `SP02_MAQUETTE_VITE` gains the class
  (282 loops; 108 → 750 triangles). `SP02_ALPHA5...` and `_NPart#194294`
  reach uvf 1.0.

Warning classes over the sample before → after (files):
`no-facet-records` 3 → **0**; new `extended-header-geometry-declined` 1
(`LedStrips_Smooth`); `curve-entry-loops-exported-dup-pin` 7 → 8;
`open-shell` 10 → 11; `unused-pool-vertices` 9 → 7;
`curve-entry-loops-unexported` 3 → 3 (`LedStrips_Smooth` 1,654 → 20,276
loops, `Guntle.ver5` 5 → 23); `degenerate-triangles-skipped` 2 → 2;
`duplicate-triangles-deduped` 1 → 1; `duplicate-triangles-dedup-declined`
1 → 1 (`LedStrips_Smooth`, 34 → 35 duplicates).

### What this run does and does not show

The extended family changes what the exporter *emits*, and these numbers
measure exactly that: three stores that emitted only vertices now emit
triangles, and several composite stores reference all of their element space.
**That is still not a fidelity claim, and it is not a claim that the three
rows now pass L2.** The corpus carries no reference surface; the report
classes come from the fixed accepted fitness row, not from this CSV.
`used_vertex_fraction` describes the found pool (and for composite stores the
re-listed element space), `area_density` sums emitted triangle area inside the
exporter's own bounding box and is not bounded by 1, and the manifold gate
declines records instead of repairing them. The screen's verdict moves from
"12/20 rows emit triangles" to "15/20", but the five undecodable rows and the
two `not-manifold` rows are unchanged, and the proxies cannot rank how close
any surface is to the real part.

### Reproduction and verification

```bash
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH   # this host
.venv/bin/python scripts/triage/measure_viewer_fidelity.py \
  --manifest --sample-size 20 \
  --anchor CATIA/CATIA_vol/Usinage/Gabarit_trou_alu_alpha.CATPart \
  --anchor 'diseño_3d/labios/main.CATPart' \
  --anchor CATIA/new_catia/SP02_BETA/SP02_BETA_COIFFE.CATPart \
  --anchor sample/CAAMechanicalModeler.edu/InputData/CAAMmrPartCopy_Comp1.CATPart \
  --out docs/evidence/data/fidelity-2026-11-18-post-extended.csv

.venv/bin/python -m pytest -q tests/test_measure_viewer_fidelity.py
.venv/bin/python scripts/triage/check_claims_csv_quoting.py
bash scripts/check.sh
```

- Determinism: three independent runs (including one from the editable `src/`
  install) produced the same SHA-256,
  `943e3ed18e5ec663be6d0f9a24d0bc54df3a738ccc1d6244f362b24bcee9c7fd`;
  all 21 rows parse at the 34-column header width.
- Pins: `tests/test_measure_viewer_fidelity.py` — 10 passed, 1 skipped.
- Claims-CSV quoting checker: 60 claims CSVs, 14,356 rows, all at header
  width.
- Full merge gate `scripts/check.sh` — PASS: ruff clean, **706 passed / 7
  skipped**, cargo build (native + wasm32), fmt, clippy, port tests,
  wasm-pack build/test, `port/pkg` ↔ `site/viewer/pkg` sync, Node tests and
  the assembly viewer acceptance.
