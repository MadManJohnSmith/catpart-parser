# Unsynthesized findings — index and decisions (2026-11-25)

**Status**: living index. It collects measured findings that live only on
branches, statements in `main` that the tree already superseded, and
coverage gaps that no note owns. Each item keeps its own evidence; this
page only says where it is, what it means and whether it is still open.

Decision log (owner, 2026-11-25): merge W6, W12 and W20 (done); keep
`acc-Cont-Lft` as a documented known gap; re-run the open-rate probe and
unify the 97.99 % / 97.92 % pair (done — see §2); leave the W26/docs
working tree uncommitted for review.

## 1. Branch-only evidence (merged 2026-11-25)

### W6 — spaghetti detection, Laya and the distilled head

- **Where**: branch `marathon/w6-laya-oracle` (`d5975ae`), note
  `docs/evidence/marathon/w6-progress.md`, scripts `scripts/triage/w6_*.py`
  and `scripts/triage/top-targets.md`. Not in `main`.
- **What it measured**:
  - Laya-vision on flat orthographic rasters **does not discriminate
    spaghetti from a clean solid**: three clean controls land
    `debris_spaghetti` at 0.59–0.62 with higher confidence than the real
    suspect (0.417); the three-view montage attempt is uniform
    (0.47–0.53). Negative, with a reopening criterion (shaded/AA renders
    from the real WASM viewer, or a validated CAD vision model).
  - The text head's 1.0 accuracy is **circular**: its features include
    `error_class`/`failed_check`/`open_kind`, from which the label is
    derived. It is a router-contract check, not generalization.
  - The leakage-free logistic head (log tris, log verts, degenerate
    ratio, boundary only) reaches **LOO 0.775**, and **0.923** on the
    `elem_decl <= 255` band. The weights say spaghetti parses carry many
    triangles over few real vertices plus degenerates. Useful as a review
    flag, not as a gate.
  - The positive label is the `duplicate-triangles-dedup-declined`
    signature (n=315) — the same family `acc-Cont-Lft` belongs to.
  - Top-targets ROI: `fail-unclassified` 366 files/1.09M tris/529 MB,
    `not-manifold` 357/713k/250 MB, `empty-mesh` V5R24 1/237 MB.
- **Why it matters**: it is the only measured answer to "can we detect
  spaghetti without a human?" and it says the visual oracle does not;
  the geometric head is a weak flag. It also names `acc-Cont-Lft` as a
  suspect, which is where this index started.

### W12 vs W20 — the Dodge contradiction

- **W12** (`marathon/w12-inverse-oracle`, `f481106`): inverse spatial
  oracle. Audi/Motor: the missing area is **missing connectivity between
  shared vertices**, not far geometry (raw vertex-set Hausdorff
  0.0007 mm). Dodge: `matched=0`; the export is a "~10× foreign
  geometry; fix class ROUTING". 12 CSVs + checker.
- **W20** (`marathon/w20-dodge-routing`, `334b76d`): refutes the routing
  reading. Identity is 0.0 at 9 candidate factors; the reference's
  x-extent is f32-exact at ×10 while y/z differ 9.3 %/1.4 % — the same
  car family, independently re-tessellated, not a rescale. All 6,310
  reps export as ONE connected body (99.999 % of triangles); 424,754
  points (21.05 %) are unused. No parser-side routing fix.
- **Why it matters**: the round-close one-liner ("Dodge: negative, pair
  artifact, not routing") matches W20, but W12's opposite conclusion and
  both evidence sets are outside `main`. Both are now merged; the
  reconciliation is below.
- **Reconciliation (2026-11-25)**: the measurements do not conflict, the
  causal readings do. W12's `matched=0` is correct as an oracle result:
  at µm identity there is no shared triangle/vertex set, so the pair
  cannot be used as a fidelity oracle. W12 inferred "routing failure"
  from the ~10× extent ratio. W20 tested that inference: the 10× is the
  unit relation on x only (f32-exact), y/z differ 9.3 %/1.4 %, and the
  reference is an independently re-tessellated variant. All 6,310 reps
  export; 99.999 % of triangles form one connected body (plus two
  119-triangle mirror twins), so there is no parser-side routing bug.
  **W20 supersedes W12's causal verdict; W12's oracle data and the
  Audi/Motor connectivity findings stand.**

## 2. Statements in `main` that the tree already superseded

| Claim in `main` | Current state | Fix |
|---|---|---|
| W3/W15 "pending re-merge" (round close) | Re-merged as `04de331`; both parts pass (8,278 / 9,142 tris), included in the 2026-11-24/25 rows | Corrected in the round close (2026-11-25) |
| W8 `LS-seg-22` "pending, needs snapshot" | Snapshot on disk; exports a closed 614-vertex / 1,156-triangle mesh via `identity-multiregion` (18 reps, 0 degenerate) | Later update added to W8 |
| Submarino 703/757 (92.87 %, `not-manifold` 20) vs 742/757 (98.02 %, 13 empty + 2 exceptions) | Two different snapshots/measurements; no dated reconciliation | Still open |
| Dev denominator 1,375 (fast engine) vs 1,381 (accepted row) | Local fast pass vs the official manifest population | Still open |
| Open rate 97.99 % like-for-like vs 97.92 % committed census | Fresh probe 2026-11-25: 1,413/1,442 = 97.99 %; 1,304 MESH + 109 DISPLAY + 29 BLANK (19 missing + 10 empty-geometry) | Resolved (see below) |
| W4 "62 dev parts off-disk" | Current manifest has 0 missing `local_path`s | Host-specific caveat; mark historical |

**Open-rate resolution (2026-11-25)**: the fresh probe over the 1,442
part rows gives **1,413/1,442 = 97.99 %** — 1,304 MESH, 109 DISPLAY,
29 BLANK (19 `missing-geometry-store` + 10 `empty-geometry-store`).
Against the 2026-11-20 census: 45 DISPLAY→MESH + 1 BLANK→MESH; the 80
W26 rows were already MESH. The 97.92 % number was the stale committed
CSV; the re-run CSV is now authoritative.

## 3. Coverage gaps in the accepted state

- **105 dev + 4 held-out `empty-mesh` rows** remain after W26. The W26
  note says they carry neither a walk-exact compact node nor another
  landed carrier, but there is **no per-mechanism census** (the 13
  Submarino empty-mesh rows do have one). A row-level "why" census is
  the missing artifact.
- **`acc-Cont-Lft`**: documented known gap — the passing 563-triangle
  emission is node 0's territory, not the 13-rep / 6,602-triangle body;
  the fire gate is residue-only. See
  [2026-11-25-acc-cont-lft-single-rep.md](2026-11-25-acc-cont-lft-single-rep.md).
- **Native colors / crease**: decode and boundary code exist, but there
  is no Playwright assertion for `triColors`, `material-toggle` or the
  28° crease; the fidelity harness compares summary + PLY, not
  `triColors`.
- **Per-face native color table end boundary**: `find_color_table`
  measured 131/131 zero-gap on the three anchors, but the composite route
  does not consume it yet.
- **Submarino exception parts**: the 4-bit note says 15 fail-to-fail =
  13 empty-mesh + "the two exception parts", but does not name the two.
- **W20 checker not wired**: `check_w20_csvs.py` passes on the 3 CSVs but
  is not in `scripts/check.sh` (W12's checker is).
- **W26 record counters**: the 189-row claims CSV records per-part
  outcomes, not the per-record accepted/exact/refused counters (those
  live only in the warning text).

## 4. What is already synthesized

- W6: [w6-progress.md](marathon/w6-progress.md) (merged 2026-11-25)
- W12/W20 Dodge: [w12-progress.md](marathon/w12-progress.md),
  [w20-progress.md](marathon/w20-progress.md), and the reconciliation in
  this note (merged 2026-11-25)
- W26 compact see-body: [2026-11-24-seebody-compact-face-gp.md](2026-11-24-seebody-compact-face-gp.md)
- W1/W1-B/W17: [w1-progress.md](marathon/w1-progress.md),
  [w1b-progress.md](marathon/w1b-progress.md),
  [w17-progress.md](marathon/w17-progress.md)
- W8: [2026-11-22-w8-unclassified.md](2026-11-22-w8-unclassified.md)
- Round close: [2026-11-22-round-v3-close.md](marathon/2026-11-22-round-v3-close.md)
- Fitness rows: `fitness/history.jsonl` (latest accepted
  `20261125T161156Z-c85026`, dev 1,247/1,381 = 90.30 %, held-out 57/61).

## 5. Next actions (from the owner decisions)

1. ~~Merge W6, W12 and W20; add the Dodge reconciliation note.~~ Done
   2026-11-25.
2. ~~Re-run the open-rate probe; make 97.99 % vs 97.92 % one reproducible
   number and update the site/docs.~~ Done 2026-11-25: 1,413/1,442 =
   97.99 %, 29 BLANK (19 + 10).
3. Keep `acc-Cont-Lft` as a known gap unless a narrow multi-node gate is
   approved.
4. Leave the W26/docs working tree uncommitted for review.

## 6. Gates run for this index (2026-11-25)

- `ruff check .` clean.
- Claims CSV quoting: 108 files / 19,775 rows at header width.
- `check_w12_csvs.py`: 12 files OK; `check_w20_csvs.py`: 3 CSVs OK.
- `bash -n scripts/check.sh` OK (the W12 merge added its checker line).
- Site smoke (index, grind, evidence): pass after the final rebuild.
- Open-rate probe: 1,413/1,442 = 97.99 %, 29 BLANK (19 + 10).
