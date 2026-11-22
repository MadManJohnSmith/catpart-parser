# Evidence: the deterministic Feature / Spec Tree — the BLANK CATIA lever that is NOT geometry (w4, 2026-11-22)

**Date**: 2026-11-22
**Status**: COMPLETE. The BLANK parts' parametric records are readable
under a pinned, deterministic framing: the writer stores feature-type
names as a **length byte `L` followed by exactly `L - 1` ASCII name
bytes** (`len = strlen + 1` — measured anchors `00 07 "Sketch"`,
`05 "Pad1"`, `09 "Sketch.1"`, `0b "EdgeFillet"`, `fe 12
"EdgeFillet_Radius"`). The extractor
(`display.scan_feature_tree`, Python = Rust = viewer JS, cross-checked
16/16 files) names the part's feature records; the viewer renders them
as a **Feature / Spec Tree panel labeled `feature-tree-only`** with a
`no-geometry` badge on the empty parts. **No triangle, no point, no
segment is emitted from it and the honest open rate does not credit
it** — the no-carrier parts keep their classified failure (the export
contract is unchanged), so L2 is untouched and the BLANK count is
honest.
**Scope**: the 56 BLANK parts of the open-rate measurement
([2026-11-19-open-rate.md](2026-11-19-open-rate.md) §6); the shipped
extractor runs on every display-fallback summary corpus-wide.
**Method**: `src/catpart/geometry/display.py` (`scan_feature_tree` +
the additive `feature_tree` summary block), `port/src/geometry/display.rs`
(the twin), `site/viewer/viewer.{js,html,css}` (the panel); audit probe
`scripts/triage/probe_w4_feature_tree.py`; data
`docs/evidence/data/w4-feature-tree-files.csv` (one row per BLANK
file), `docs/evidence/data/w4-feature-tree-claims.csv` (`FT-01`..`FT-05`).

---

## 1. Executive summary

| Measurement | Value |
| :--- | ---: |
| BLANK parts audited | **56** (the open-rate note's §6 table) |
| … with a framed feature tree (≥ 1 feature name) | **38** |
| … `CATPrtCont`-only (the container token, no framed name) | **13** |
| … no tokens at all | **4** (`dummy`, `fpb_assy_v3`, `MyTextDocCheck`, `test_tolerence`) |
| … absent on disk (upstream sha drift, quarantined) | **1** (`cachete_soporte_mirror`) |
| The framed vocabulary | **17 types**, every one measured (§2) |
| The parameter-type family (`Volume`/`Density`/`Area`/`Mass`) | **excluded** — mass-properties headers, 51/51 files as a block, not a feature |
| Python = Rust parity | **5/5 sampled display rows** (summary parsed-document equal, PLY identical) |
| Viewer JS = Python reference | **16/16 sampled files** (containers, names, counts, offsets) |
| Open-rate effect of the feature tree | **0** — by construction (no triangle/point/segment; the raise contract is unchanged) |
| L2 effect | **0** (no gate input changes) |

The task's named rows resolve: `WELD-W1`, `grid`, `550.000_NOTE A`,
`511.000_NOTE A`, `BENDABLE-PIPE-BW-4in` are the **`CATPrtCont`-only**
class (the panel shows the container skeleton + `no-geometry`);
`gsd_analytic_elements` carries a framed `Offset` (a real GSD feature
name) → the feature-tree class.

## 2. The pinned framing

A feature name is accepted only when **all** hold:

1. a length byte `L` with `4 <= L <= 40`;
2. exactly `L - 1` bytes of the name charset `[A-Za-z0-9_.]` follow
   (the maximal run — a run that continues past the length byte's
   promise rejects, the same validation the reference regex + the
   `len(name) + 1` check performs);
3. the full name matches `^(Type)(\.\d+|\d+)?$` for a pinned type
   `Type` (instance suffixes allowed, bare types allowed).

The shipped vocabulary is the **measured** subset (≥ 1 framed
occurrence in the BLANK population) minus the parameter-type family:

```
Axis, Boundary, Chamfer, Circle, Curve, EdgeFillet, Hole, Line,
Mirror, Offset, Pad, Pattern, Plane, Point, Pocket, Rib, Sketch
```

`Fillet` does not frame (`EdgeFillet` does — `0b "EdgeFillet"`,
`fe 12 "EdgeFillet_Radius"`); `Volume` frames but sits in the
mass-properties block (`resultIN 07 Volume 08 Density`) — a parameter
header, not a feature, and it appears in 51/51 files as a block, so the
framing alone cannot carry it; it stays out and the audit CSV labels
the affected files `prtcont-only`. The names live in the parametric
streams **outside** the named containers (289/289 measured inside no
`CATPrtCont` region), so the scan is framing-scoped, not
region-scoped.

## 3. The three implementations, one law

- **Python** (`display.scan_feature_tree`): the reference; the
  additive `feature_tree` summary block rides on every display-fallback
  summary whose part carries the names —
  `{source: "catprtcont-feature-tokens", kind: "feature-tree-only",
  surface: false, containers: {catprtcont: N},
  features: [{type, count, first_offset}, ...], feature_names: total}`,
  integer/string fields only, schema
  `export-summary-v1.json` (additive, `additionalProperties: true`).
- **Rust** (`display::scan_feature_tree`): the twin, same law and
  order; parity 5/5 sampled display rows (Ehi_clamp1 9 names,
  Ehi_Support1 8, Ehi_Equipment 12, Ehi_EConnector 6; `grid` raises
  `missing-geometry-store` in both).
- **Viewer JS**: the same law over the raw bytes, covering the parts
  whose export classified-failed (no summary is emitted for them) —
  the panel reads the summary's block when present, the client-side
  scan otherwise. Cross-check JS = Python on 16/16 sampled files
  (12 feature-tree + the 4 no-token files): identical containers,
  feature lists, counts, first offsets.

**The export contract is unchanged**: a part with no displayable
carrier still raises its classified error (`missing-geometry-store` /
`undecoded-variant` — the export-v1 contract tests pass unchanged); the
tree reaches the viewer for those parts through the client-side scan.

## 4. The BLANK audit

| class | parts | what the panel shows |
| :--- | ---: | :--- |
| `feature-tree` | **38** | the container row + the framed types with counts (e.g. `screw`: Sketch/Point/Line/Pad/Constraints-family; `Ehi_Equipment`: Sketch, Pad 3, Pocket 2, EdgeFillet 4, Rib 5, Chamfer 6, Pattern 7) |
| `prtcont-only` | **13** | the `CATPrtCont` container row + `no-geometry` — the design intent has no framed feature name in the file |
| `none` | **4** | nothing (`dummy`, `fpb_assy_v3`, `MyTextDocCheck`, `test_tolerence` carry neither the container token nor a framed name) |
| `missing` | **1** | off-disk (upstream drift, quarantined: `cachete_soporte_mirror`) |

Full per-file rows: `w4-feature-tree-files.csv`.

## 5. The honest open rate after both w4 levers

The open-rate probe re-measured over the corpus
(`docs/evidence/data/w4-open-rate-files.csv`; the committed
`open-rate-files.csv` stays untouched — it is the 2026-11-20 run whose
tree predates the face-gp route, so its per-row data is stale by 24
rows: the 13 committed face-gp fires + 11 rows the d8554e0 lineage
opened, all re-verified MESH at d8554e0's code during the
reconciliation).

**Raw on this host** (62 dev parts off-disk, §6 — they land as
`unreadable-file` BLANK): MESH 1,142 · DISPLAY 209 · BLANK 91 of 1,442.

**Like-for-like** (drift rows restored to their d8554e0 classes, the
24 stale rows corrected — every correction verified by an export at
d8554e0's code):

| Measurement | d8554e0 true | w4 | movement |
| :--- | ---: | ---: | :--- |
| MESH | 1,202 | **1,203** | +1 (`CAAPstPad1_2`: DISPLAY → MESH, 30 tris) |
| DISPLAY | 211 | **210** | −1 (the same row) |
| BLANK | 29 | **29** | flat — the no-carrier floor |
| **Open (MESH + DISPLAY)** | **1,413/1,442 = 97.99%** | **1,413/1,442 = 97.99%** | flat (the one moved row was already open as a display; it upgrades to a real mesh — the +1 L2 dev pass) |

Exactly **one row changes class** between d8554e0 and w4; the 8
counter-table gains upgrade already-open rows (more triangles, same
class); **every `feature-tree` / `prtcont-only` row stays BLANK** — the
tree is a display aid, not geometry, and the honest open rate does not
move by a single feature-tree row. The 29 remaining BLANKs are the
no-carrier floor: 19 `missing-geometry-store` + 10
`undecoded-variant`, every one verified to carry no count-framed f32
array, no point run and no law-holding curve record.

## 6. The corpus caveat (honest scope)

62 dev parts (and 7 products) of the `Apoloo13/ASE_III` repo are
off-disk on this host: the files changed upstream after the
2026-11-07 freeze and the repo's history does not carry the frozen
bytes (best-effort restore verifies 7/69 shas; 40 commits probed). The
committed baseline (run `d2c9ff`, 2026-11-21) measured them (60 of the
62 were L2 passes), so **a fitness run on this host would be rejected
spuriously** (unavailable rows count as not-pass) and is not recorded.
The w4 no-regret evidence is the scan-local sweep
([2026-11-22-face-gp-counter-table.md](2026-11-22-face-gp-counter-table.md)
§3): 14 fires, 0 regressions, 0 held-out fires, parity 49/49.

## 7. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-} TMPDIR=/home/alan/.cache/t3-tmp
# the BLANK audit + the claims CSVs
python3 -I scripts/triage/probe_w4_feature_tree.py
# the extractor (any part):
.venv/bin/python -c "from catpart.geometry.display import scan_feature_tree; print(scan_feature_tree(open('<part>', 'rb').read()).block())"
# the corpus-wide open-rate re-measure (writes open-rate-files.csv)
.venv/bin/python -I scripts/triage/probe_open_rate.py
```

Deterministic: manifest order, byte-identical CSVs across runs; the
viewer's JS scan agrees with the reference on the sampled files.

## 8. Files

- `src/catpart/geometry/display.py` + `port/src/geometry/display.rs` —
  `scan_feature_tree`, `FeatureTreeScan`, the additive block.
- `src/catpart/geometry/export.py` — the block's wiring (additive only;
  the classified-failure contract untouched).
- `site/viewer/viewer.{js,html,css}` — the Feature / Spec Tree panel.
- `scripts/triage/probe_w4_feature_tree.py` — the audit probe.
- `docs/evidence/data/w4-feature-tree-{files,claims}.csv` — the data.
