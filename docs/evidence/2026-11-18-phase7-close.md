# Phase 7 close — the frozen B-rep vocabulary is resolved (Spec G #47)

**Date**: 2026-11-18
**Status**: CLOSED — 23/23 constructs resolved (14 decoded, 3 documented negative, 6 documented open with published ceilings, 0 candidate); L3 headline 23/23 accepted under no-regret.
**Tickets**: Spec G #47 (BR1 #48, BR2 #54, BR3 #55, BR4 #56, BR5 #57, BR6 #58)
**Method**: RE-only over the observed corpus (1,442 parts, 1,089 L2-pass); every figure below is a committed claims-CSV row or arithmetic on committed counts. Corpus binaries are never committed.

---

## 1. Result

The frozen vocabulary (`docs/evidence/data/brep-construct-vocabulary.csv`, 23 constructs,
`sha256 2b2f54d9…ff611`) is resolved row by row:

| Outcome | Count | Meaning |
| :--- | :--- | :--- |
| decoded | 14 | byte layout / recognition law + corpus rate + tests + synthetic negative |
| documented negative | 3 | absent or undecodable, with a numeric ceiling |
| documented open | 6 | not isolable from the tessellation, with a published superset ceiling |
| candidate | 0 | — (CRV-08 and SRF-07 adjudicated 2026-11-18) |
| pending-merge | 0 | — |

**L3 headline 23/23 = 1.0** (`fitness/history.jsonl`, run `20261118T171127Z-0882ce`,
`tool_version 1.0.0`, `accepted: true`, `reason: L3 recorded with L1/L2 intact`). L1 and L2 are
unchanged: **L1 1,745/1,751 Dev + 73/73 held-out; L2 1,033/1,381 = 74.80% + 56/61**. The corpus
rate (the sum of the vocabulary's per-class occurrence cells) is reported alongside and **never
gates**: 21,659/33,166 = 0.653048.

## 2. Per-construct verdicts

| Construct | Outcome | Cited claim |
| :--- | :--- | :--- |
| TOP-01 Solid/Body | decoded (structural carrier: block + store root) | `BR5-04b_top01_store_root` |
| TOP-02 Lump | documented negative (ceiling) | `BR5-06b_top02_lump_ceiling` |
| TOP-03 Shell | decoded (derived partition law) | `BR6S-04_shell_files_corpus` |
| TOP-04 Face | decoded | `BR2-03_face_files_corpus` |
| TOP-05 Loop | decoded | `BR2-04_planar_files_corpus` |
| TOP-06 Edge | decoded | `T06_census_presence` |
| TOP-07 Vertex | decoded | `T07_pool_count_law` |
| CRV-01 Line/Segment | decoded | `C01_line_block_finite` |
| CRV-02 Circle/Arc | decoded | `C02_circle_decode_ok` |
| CRV-03 Ellipse | decoded | `C03_conic_decode_ok` |
| CRV-04 Parabola | documented open (ceiling) | `C04_parabola_ceiling` |
| CRV-05 Hyperbola | documented open (ceiling) | `C05_hyperbola_ceiling` |
| CRV-06 NURBS curve | documented negative (ceiling) | `BR5-06d_crv06_srf08_ceiling` |
| CRV-07 Polyline | decoded | `C07_polyline_strips` |
| CRV-08 Trimmed curve | documented open (ceiling, superset) | `C08_trim_curve_ceiling` |
| SRF-01 Plane | decoded (record-local plane) | `BR2-10_plane_coplanar_poolonly` |
| SRF-02 Cylindrical | decoded (tessellation-level) | `SRF-02_cylinder_allscopes_presence` |
| SRF-03 Conical | decoded (tessellation-level, thin) | `SRF-03_cone_allscopes_presence` |
| SRF-04 Spherical | decoded (tessellation-level) | `SRF-04_sphere_allscopes_presence` |
| SRF-05 Toroidal | documented open (no law isolates a torus) | `SRF-05_upper_bound_allscopes_presence` |
| SRF-06 Revolution | documented open (superset problem) | `SRF-05_upper_bound_allscopes_presence` |
| SRF-07 Extruded | documented open (negative-space signature is a floor) | `SRF-07_extrusion_ceiling` |
| SRF-08 NURBS surface | documented negative (ceiling) | `BR5-06d_crv06_srf08_ceiling` |

## 3. The documented opens, with their ceilings

- **CRV-04 / CRV-05** — no parabola/hyperbola discriminator is decoded. Ceiling: the **357** files
  carrying any `33 38` conic carrier (`C04_parabola_ceiling`, 313 L2); the frozen split
  214 + 143 = 357 is not a partition of a decoded family.
- **CRV-08** — a trimmed curve is indistinguishable from an untrimmed one in the decoded fields.
  Ceiling: **1,277/1,442** files (0.8856; 1,086/1,089 L2) carrying any walked `33 3X` record, and
  **1,573,239** records (`C08_trim_curve_ceiling_records`). The narrow 969-file carrier reading is
  published as a reading, **not** as the ceiling.
- **SRF-05 / SRF-06** — a torus band is a valid cylinder at either equator and planar at the pole
  (fixtures `test_torus_equator_lands_cylinder`, `test_torus_pole_band_lands_planar`), so no class
  population is a torus population. Ceiling: the full classified strip-loop total **67,919**
  (`SRF-05_upper_bound_classified_patches`, 975/1,442 files). The earlier 4,289 "ceiling" was false
  and is withdrawn in the BR4 note §6.4.
- **SRF-07** — the `pencil-noncyl` signature isolates non-circular profile extrusions only; a
  circular-profile extrusion **is** a cylinder. The 5,517 loops (388 files) are a **floor**, never a
  bound; the published bound is the same 67,919 superset (`SRF-07_extrusion_ceiling`).

## 4. Graph and STEP export (BR6)

`src/catpart/brep/graph.py` assembles Body→Lump→Shell→Face→Loop→Edge→Vertex with mandatory
provenance (decoder, construct, claim, scope, unit, index space, byte anchor);
`src/catpart/brep/step_export.py` writes the measured subset (AP203/AP214, `facet` default,
`exact` for ring-only faces) and refuses with 20 named classes rather than inventing topology.

Corpus expectations, published before the run and then measured (`br6-graph-claims.csv`):

- **66/1,442** parts decode ≥ 1 closed shell (`BR6G-01`, BR6S-04 tie-out).
- **0/76** closed shells satisfy the loop-segment pairing law (**76/76** carry a one-use segment);
  the B-rep pairing law is distinct from `shell.py`'s triangle closure, and the exporter refuses
  with `shell-not-brep-paired` (`BR6G-05b/05c`).
- **exact mode: 0/1,442** (predicted 0/76 pre-run: no closed shell is ring-only, 16 rings among 522
  closed-shell face records); **facet mode: 53/1,442** (`BR6G-06`, `BR6G-07`).
- `body-no-shell` 283 = 125 no-store + 128 face-free + 30 no-placeable (`BR6G-06b`).
- 708 unread `0x44` records counted in `unknown`, never noded (`BR6G-09`).

## 5. Disclosures

1. **Eight frozen denominator cells have no committed generator** (`CRV-04`, `CRV-05`, `CRV-08`,
   `SRF-03`, `SRF-04`, `SRF-05`, `SRF-06`, `SRF-07`): 15 of 23 cells reproduce exactly from the
   census columns, and the 8 do not; their rates are not expressible as `round(k/1089, 4)` for any
   integer `k` (`docs/agents/br6-vocabulary-provenance.md`). The L3 headline is row-level construct
   coverage and does not rest on those cells; the corpus rate is reported and never gates.
2. **Four denominators are mis-scoped carriers**: TOP-02 (body/CGM presence, no lump class),
   CRV-06 and SRF-08 (1,435 = `cgm_present`, content measured at 0/1,089), CRV-03 (357 = every
   conic, not ellipses).
3. **CRV-03 + CRV-04 + CRV-05 double-count** the 357-file conic carrier set; they are not a
   partition.
4. **TOPO_LUMP is not a census label**: the census emits only `TOPO_BODY`, which cannot separate
   bodies from lumps (BR5 §5).

## 6. Fitness protocol

The L3 scalar now lands in a history row (`{"rate","resolved","total","by_outcome"}`), is
corpus-split independent (construct coverage is a property of committed evidence), and participates
in no-regret: introduction, rise, fall and drop are defined; a flat L3 is **not** an increment; a
Dev regression is reported before an L3 fall. The corpus rate never gates. The site publishes the
L1/L2 series only; an L3 surface is a #49 release item.

## 7. Reproduction

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
.venv/bin/python scripts/triage/decode_brep_planar.py  --out-dir /tmp/br2
.venv/bin/python scripts/triage/decode_brep_curves.py  --out-dir /tmp/br3
.venv/bin/python scripts/triage/decode_brep_quadrics.py --out-dir /tmp/br4
.venv/bin/python scripts/triage/decode_brep_cgm_nurbs.py --out-dir /tmp/br5
.venv/bin/python scripts/triage/decode_brep_shell.py   --out-dir /tmp/br6s
.venv/bin/python scripts/triage/decode_brep_graph.py   --out-dir /tmp/br6g
.venv/bin/python scripts/triage/score_l3_constructs.py
bash scripts/check.sh
```

## 8. What this note does not claim

- It does not claim exact solids for the corpus: exact STEP exports **0/1,442** parts; the shipped
  output is the measured faceted B-rep subset, labelled as such in the STEP `FILE_DESCRIPTION`.
- It does not claim the eight unprovenanced frozen cells as measurements.
- It does not claim product structure in STEP, parametric recipe recovery, or NURBS payload decode.
