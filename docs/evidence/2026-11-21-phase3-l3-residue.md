# Fase 3 L3: the post-L1 residual of the submarine `not-manifold` family (2026-11-21)

Ticket #70 (parent #50). Reference `main` @ `febe74f` (Fase 3 L1/L2 merged).
Snapshot: `submarine-ssk-tr-1700-s42-ara-san-juan-1.snapshot.20` (757
`.CATPart`, external to the L2 corpus). Read-only probes and raw artifacts:
`~/.local/state/catpart-parser/bench-submarine/` (`m1_probe.py`,
`postl1_gate_probe.py`, `sew_redundancy_probe.py`, `split_prototype.py`).

## What L1 already fixed

The Fase 3 L1 fail-closed relist skip (`3e178c7`, merged `84bd793`) took the
submarine's `not-manifold` set from **357 to 240** parts: 117 no longer fail
that check. Of those, **80 pass L2** and **37 land on `degenerate-triangles`**
(the adopted candidate's triangulation), so the net L2 pass gain is **80**
(366 → 446); the 37 remain L2 failures and are a named side effect of the
current L1 gate. The 240 are a strict subset of the 357; 149 of them already
failed before Phase 2, 91 were unlocked by #76 (`c796a08`) and expose the same
native signature. All 240 carry `primary-loop-manifold-kept`; the L1 candidate
was declined for them, not silently applied.

## Why the L1 candidate is declined

For each of the 240, the L1 candidate was reproduced exactly (seam-off area →
decode with `_relist_skip=True`). One store per part; no export errors.

| Adoption condition | Result |
| :--- | :--- |
| candidate mesh is manifold | **240/240** |
| all skipped-loop vertex coordinates survive in the candidate | **145/240** |
| boundary-edge count does not grow | **0/145** of the covered set (all 60 non-growing cases are uncovered) |
| all three conditions (the shipped L1 gate) | **117/357 of the original set, 0/240 here** |

The 240 split into **145 covered** (the S5 "sewable" bucket) and **95 not
covered** (60 with no boundary growth, 35 tears plus uncovered vertices). The
95 are unique-surface loops: dropping them loses real surface and they must
stay kept.

## The S5 "sewable" bucket is not a clean duplicate skin

Vertex coverage alone does not prove surface redundancy. The new geometric
probe measures the distance from every dropped triangle (vertices + centroid)
to the candidate surface, relative to the part's bounding-box diagonal:

| max relative distance | parts (of 145) |
| :--- | ---: |
| `< 1e-6` | 18 |
| `< 1e-5` | 19 |
| `< 1e-4` | **19** |
| `< 1e-3` | 23 |
| `< 1e-2` | 54 (centroid screen; the 19 exact cases were confirmed with the full 4-point probe) |

The 19 exact cases are genuine re-listed skins (max absolute deviation
`≤ 4.3e-6 mm`, one `3.8e-3 mm` outlier on `LS-Valv-75`). The other 126 exceed
`1e-4` relative: 4 sit below `1e-3` and 122 by millimetres to infinity — the
skip would drop surface. The S5 projection of ~107 sewable parts is **refuted**
by the geometric measure: the honest ceiling for an exact-skin skip is
**19 parts** (7.9% of the residue, 5.3% of the original 357).

## A topology-only split makes all 240 manifold, but it is a different lever

As a diagnostic, every over-used undirected edge was cut by giving its
incident triangles fresh vertex copies (no triangle dropped, no coordinate
changed):

| Result | Value |
| :--- | :--- |
| manifold after split | **240/240** |
| area delta | **exactly 0** on all 240 |
| cut edges | median 129, max 4,094 |
| boundary-edge growth | median +1,210, max +122,623 |
| vertices added | median +986, max +122,506 |

This is a valid topology-only repair (surface preserved exactly), but it
turns the L2 gate's `not-manifold` signal into a pass by fragmenting the
native non-manifold seams into disconnected patches. It is **not adopted**
here: it changes what the gate measures, it is not a decoding fix, and it
should be an explicit product decision (viewer-side repair with its own
warning and provenance), not a silent L2 lever.

## Consequence

* The planned L3 "sewing" lever is **not justified** by measurement: only 19
  of the 145 covered candidates are exact skins; the other 126 exceed `1e-4`
  relative deviation, so the skip is not surface-preserving for them. No L3
  code is added.
* Issue #70's actionable part is delivered: Phase 3 resolves 117
  `not-manifold` parts (80 now pass L2, 37 land on `degenerate-triangles`);
  the remaining 240 are documented native writer content (the NX→CATIA
  writer re-lists skins with another diagonal and shares their edges), not a
  regression of #74/#76.
* The official L2 corpus is unaffected: its 1,442 files include 5
  `not-manifold` failures, none of them in this external residue. The
  submarine remains an external generalization set, not a fitness input.

## What this note does not assert

* It does not claim the 240 are unfixable in principle; it measures that the
  skip is not surface-preserving for 221 of them (95 lose unique vertices,
  126 deviate from the surviving surface), and that the topology-only split
  is not a surface-fidelity improvement.
* It does not reopen the L1 adoption: the 117 fixed parts stay fixed
  byte-for-byte.
* It does not change `PRIMARY_LOOP_AREA_REL`, the L2 gate, or the corpus
  fitness rate.

## Artifacts

* `out-fase3-l1l2/m1_files.csv` + `m1_summary.json` — the post-L1/L2 757-part
  sweep (the 240).
* `out-postl1-gate/postl1_gate.json` + `.csv` — per-part L1 gate conditions.
* `out-postl1-gate/sew_redundancy.json` — geometric redundancy (full 4-point
  probe on the 19 exact cases; centroid screen on the rest).
* `out-postl1-gate/split_prototype.json`, `split_grouped.json` — the
  topology-only split measurements.
