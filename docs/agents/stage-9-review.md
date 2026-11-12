# Stage-9 pre-merge review: the stage-8 locator/predicate laws integrated into the exporter (2026-11-12)

Reviewer: stage-9 review sub-agent. Under review: `t3/integrate-stage8-locator-artifacts`
@ `39a3ff1` (efd8644 src + 84a961b declared delta + 39a3ff1 observed A/B, linear on
`678afc1`). Method: every headline claim re-derived independently — own worktree
venv, own re-runs at BOTH A/B ends, own pairing-loop re-derivation, own scope
probe, own byte-anchor checks; the implementing delegate's numbers were treated
as claims, not facts. Corpus read-only via the gitignored `corpus` symlink; no
binaries committed; my scripts and re-run artifacts live outside the repo
(`~/.local/state/catpart-parser/stage9-review/`). The branch was reviewed in a
detached worktree checkout (`stage9-review-target`); this note lands on
`t3/stage9-pre-merge-review`.

Labels: **fact** = measured/cited (file:line or command); **inference** =
derived, reasoning shown.

## Verdict: MERGE

All six amended declarations (D1-D6) verified against independent re-runs;
every headline number reproduces byte-exactly (four committed corpus artifacts
re-run, all four `cmp`-identical); the three stage-8 fixes match the reference
implementation on every semantic point checked; the census-artifact finding
(the "22 subnode-assisted" class) re-derived from scratch and confirmed.
Three objections, none blocking, none touching src/tests: two factual/wording
corrections to committed claim rows or comments (O1, O2), one stale gate
figure in the dispatch brief (O3). O1/O2 are docs-only corrections the
implementer should land with or immediately after the merge.

## Checklist results

1. **Environment — PASS (fact).** Worktree-local `.venv-review`
   (`python -m venv .venv-review && .venv-review/bin/pip install -e '.[test]'
   && pip install 'ruff==0.17.4'` — ruff is the `lint` extra, pyproject.toml:41,
   not in `[test]`). `sh scripts/check.sh` on 39a3ff1 with that venv as `.venv`:
   **ruff clean, 321 passed + 7 skipped in 4.20 s** (check.log). Main `678afc1`
   collects 322 tests (`pytest --collect-only` on the main checkout = 315 + 7);
   the branch adds exactly 6 `def test_` functions + 1 dated rename (diff of
   test names). The dispatch brief's expected "320 passed + 7 skipped" is
   stale — see O3.

2. **Reproducibility — PASS (fact).** All four committed corpus artifacts
   reproduce byte-identically from my own runs (`cmp`):
   - branch A/B (`ab_identity_export.py --out-dir <staging>`) == committed
     `stage9-identity-export-files.csv`;
   - branch replay (`replay_export_seam.py`) == committed
     `stage9-replay-stage9.csv`;
   - baseline end (staging worktree at `4e705a5`, own venv) replay ==
     committed `stage9-replay-baseline.csv` — 1,039 exported = 747 + 152 +
     28 + 112 clean; 225 undecoded-variant + 178 missing-geometry-store;
   - baseline end A/B == committed `stage6-identity-export-files.csv` @
     `4e705a5`.
   Digest preservation from my own replay pair: **0 ply_sha256 and 0
   l2_fields_sha256 changes on all 1,039 baseline-exported rows**, 0 lost
   exports, 0 timeouts, the 322 still-failing rows identical (class + 200-char
   detail), all 81 new exports carry both digests + stage
   `identity-mixedwrite-reps`, 0 preserved-row `node_bytes` changes.

3. **Scope decision — PASS, verified structurally AND empirically (fact).**
   - Structural: the composite.py diff has exactly 4 hunks (2 docstring
     additions, the failure-branch rework, the +433-line stage-9 block). The
     only behavioral change sits inside the `decode_region` failure branch,
     behind the `_walk_mismatch` family-signature guard
     (src/catpart/geometry/composite.py:653-687; guard at :664, the
     composition call at :679). A walk-OK store returns at :654/:688 and
     cannot reach `_decode_mixedwrite`; the primary path (decode_region,
     layout, find_list_node, parse_strip_records, _triangulate,
     _decode_per_rep, decode_raw_array) is untouched.
   - Empirical (my own store-level probe, all CATStdCont spans in exporter
     order): 950 composite stores corpus-wide; all 93 trigger stores present;
     non-trigger composite stores = 857; the full-window single-rep locator
     (`find_list_node(data, lo, hi)` instead of the stage-3d
     `find_list_node(data, lo, first-STRIP_RE)`) re-selects the payload on
     **823 of the 857** (807 of the 829 walk-exact + 16 of the 28 raw-family
     stores) — the 823/857 measurement reproduces exactly. Wording precision
     note: see O2.
   - Truncation: a window that cuts the node before its declared region end
     always fails the primary walk (`region_end > len(payload)` raise,
     composite.py:273-278). Windows that cut only post-region bytes (the
     records tail) can still walk exact — measured 731 such stores — which is
     harmless: they are walk-OK and never reach the new locator. The claim's
     shorthand "a truncated node always fails the primary walk" holds for
     REGION truncation, which is the only truncation that matters here
     (inference: tail-truncation leaves the declared region intact).

4. **Pairing-loop artifact finding — CONFIRMED (fact).**
   - The committed census CSV's own signature (mixedwrite-reps-files.csv @
     678afc1): reps-full 82; strict (`pool_subnode_only == 0`) 60 — all
     single-rep (pool_groups == 1, decoded_reps == 1); subnode-assisted 22 —
     all multi-rep (2..17 groups), every one `diag_paired == 1` with
     `abs_map` of the shape `0->0;1->0s;2->0s;...` (every pool 1+ "matched"
     at rep 0 via the pool wrappers' own `05 08 01` records). The census's
     early break and the sub-node route folded into every rep test are at
     scripts/triage/mixedwrite_decode.py:459-487 (`break` at :487).
   - My own re-implementation of that loop over `decode_node` reproduces it:
     82 reps-full, 22 subnode-assisted, diag_ok total 82 (pool 0 diagonal,
     pools 1+ at rep 0).
   - My own no-break DIAGONAL re-measure (group k vs decoded rep k, exact f32
     then the 1e-5 noise cap at 10,000 vertices): **81/82 fully diagonal, all
     dev**. The only non-diagonal store is bad44bdf52f5c411 (3 pool groups, 3
     decoded reps, **1 vertex of 93,518 in no decoded region** — my any-region
     union measure also fails to cover it), fail-closed with the gap named;
     the exporter's error on it: "1 of 93518 pool vertices". The 11 UV-family
     stores decode 0 reps — fail-closed. 12 fail-closed total.
   - The branch's probe re-run (`mixedwrite_absorption_probe.py`) is
     byte-identical to the committed `stage9-absorption-probe.csv` (`cmp`),
     and its bad44bdf row reads pool_groups 3 / decoded_reps 3 /
     groups_diag_full 2 / groups_uncovered 1 / absorbed 0.

5. **Port fidelity — PASS (fact).** Line-by-line against
   scripts/triage/mixedwrite_decode.py:
   - `table_decode` ↔ `_table_decode_extents` (composite.py:1202-1286): same
     zero-block candidate loop (e in 1..k), same guards (first group zero;
     count_pos bounds; wc > 3*element_count; region_end > len(payload)), same
     walk semantics (SHAPES, LCP carry, `_nice`, exact region_end end), same
     unique / ambiguous / None selection.
   - `raw_probe` ↔ `_raw_escape_probe` (composite.py:1289-1320): identical
     candidate rule (4-aligned 32..64, unique FF escape), identical 1e-6-floor
     predicate and x-ascending rate.
   - `decode_node` ↔ `_decode_node_mixedwrite` (composite.py:1323-1415): same
     law order table -> raw -> flat, same 0.98 thresholds, same flat start
     (`counts_end + 4`), same flat acceptance (asc >= 0.98 OR the pool fully
     re-listed), same weak-fit failure naming.
   - Composition ordering: the raw-array law runs first (composite.py:667),
     the composition second (:679), fail-closing with all three gaps named
     last (:681-687) — per-rep before fail-closing.
   - Byte anchor 221df959 verified (my script): counts_end 44; committed skip
     eats [44,56) (3 groups) and reads 194 at 1,022 (the exporter's "declared
     194" failure; primary walk fails "at element 85 ... 4 left of the
     declared 194"); the extent law returns extent 1 / write_count 8,156,
     count at 1,014 — exactly the S9-extent row's numbers.
   - The exporter's composition over the 93 trigger stores (my run of
     `_decode_mixedwrite`): 81 exported / 12 failed; single-rep law mix
     47 table + 7 raw + 6 flat — exactly the census's strict-60 mix;
     multi-rep 21 with rep counts 2x8, 3x2, 4x2, 5, 7x6, 9, 17 (== pool
     groups on every one, `reps_unexported == 0`); the 12 fail-closed are
     11 UV + bad44bdf.
   - The dated correction is stated (tests/test_composite_export.py:493-529
     "DATED CORRECTION (stage 9, 2026-11-12)"; tests/fixtures_gen.py:1319-1324)
     and the raw start rule's fail-closed arm stays pinned at unit level
     inside that same test (decode_raw_array raises "raw-array start not
     pinned ... selects 0 of the 9 candidate starts",
     tests/test_composite_export.py:528-529).

6. **Row-level accounting — PASS (fact).** From my own A/B pair (4e705a5 vs
   39a3ff1, per-row join): exactly **81 changed rows = 81 gains, 0 losses,
   0 other changes**; all 81 stage `identity-mixedwrite-reps`, all dev, all
   baseline `undecoded-variant`, none with `raw_start` set. L2 split of the
   gains: **62 pass + 13 empty-mesh + 6 not-manifold**, per-store names
   matching the claims CSV/evidence note exactly (13 empty: 086a4eff
   18bb4ca6 2c5d2542 4d2a06a6 4dfef8f2 65eb023d 7d27c73d 81ad336b 85ceb131
   ccbb7862 d696356b e23423d6 f21255ac; 6 not-manifold: 25aeb5a0 44e63faa
   a61588e5 b912cbef ef61cfc2 f4a5df2a). undecoded-variant 225 -> 144
   (140 dev + 4 held-out); missing-geometry-store 178 unchanged; held-out
   **0 changed rows** (57 exports / 55 passes steady); dev L2 pass
   886 -> 948 (948/1,381 = 68.65%). Gain mesh totals 2,362,126 vertices /
   92,023 triangles — matches the evidence note. Per-class split correction:
   see O1.

7. **Fixtures/tests — PASS (fact).** 6 new tests + the dated rename of the
   wrong-offset test. Both-direction pins (the stage-5 O1 lesson) where
   synthesizable:
   - extent law both directions (test_table_decode_extents_both_directions):
     on a no-overshoot payload the extent decode equals `decode_region`'s
     element-for-element; on the overshoot payload the primary walk raises
     and the law recovers the true extent (e == 1, wc == 60).
   - flat law: the near-zero fixture exports (positive) AND the raw law's
     weak-fit decline is pinned at the same payload family ("weak fit",
     "nice 0.9167").
   - strip-false-match: exports via the full-body scan (positive) AND the
     truncated payload's raw decline is pinned ("raw-array start not
     pinned").
   - multi-rep composition: merged export (24/24, per-rep face split asserted
     on the PLY) + the subnode fail-closed negative ("does not establish pool
     absorption", "1 of 17 pool vertices", "05 08 01 sub-node records").
   - The extent ambiguity arm is corpus-vacuous (all 133 census table reps
     resolve at a unique extent) and not unit-synthesizable; the test says so
     and pins it via the census measurement, while the code fails closed
     structurally (`_decode_node_mixedwrite` returns None on "ambiguous").
   Red-capability verified WITHOUT touching src/tests (monkeypatch before
   pytest): kill `_decode_mixedwrite` -> 7 red; kill `_table_decode_extents`
   -> 2 red; neuter `_walk_mismatch` -> 10 red (including the trigger-
   ordering pin `test_composite_walk_nan_stays_out_of_the_raw_family`);
   disable the flat arm -> 6 red. Determinism: my two independent full-corpus
   runs are byte-identical to the committed artifacts.

8. **Fold-through — PASS (fact).** Diff inspection: composite.py = 4 hunks
   (see item 3); the primary path's locator, `layout()`, record parsing,
   triangulation, the stage-5 per-rep path and the stage-6 raw path are
   untouched; fixtures_gen.py and test_composite_export.py are test-only.
   Empirically: all 1,039 baseline-exported rows — including stage-5's 152
   `identity-per-rep` and stage-6's 28 `identity-raw-array` rows — byte-
   identical on BOTH replay digests at both ends; clean 112 unchanged; stage
   counts 747/152/28 unchanged; 0 timeouts both ends.

## Objections

- **O1 (fact, committed-claims row wrong — docs-only fix):**
  `stage9-claims.csv` row S9-L2-split states "single-rep 60: 47 pass / 13
  empty; multi-rep 21: 15 pass / 4 empty / 2 not-manifold". Measured (my
  A/B x probe join): **single-rep 60: 47 pass / 9 empty / 4 not-manifold**
  (44e63faa, a61588e5, b912cbef, ef61cfc2 are single-rep not-manifold); the
  multi-rep row is correct as stated. Totals (62 pass / 13 empty / 6
  not-manifold) and the named store lists are unaffected. Minimal fix:
  correct the row to "single-rep 60: 47 pass / 9 empty / 4 not-manifold".

- **O2 (fact, wording precision — docs-only fix):** the 823/857 measurement
  (S9-window row, composite.py:109, the evidence note) is labeled "walk-OK
  composite stores". The 857 denominator is **non-trigger composite stores**
  (829 walk-exact + 28 raw-family walk-mismatch); the 823 re-selected span
  807 walk-exact + 16 raw-family stores. The measurement itself reproduces
  exactly and the scope decision it supports stands. Minimal fix: reword to
  "823/857 non-trigger composite stores (829 walk-exact + 28 raw-family)".

- **O3 (fact, brief hygiene):** the dispatch brief's expected gate "320
  passed + 7 skipped" is stale: 39a3ff1 runs **321 passed + 7 skipped**
  (main 678afc1 = 315 + 7; the branch adds exactly 6 tests). Record the
  correct figure in the merge checklist. No artifact change needed.

## Observations (not objections)

- The stage-8 note and reference docstring say the layout overshoot fires
  when the region opens with ">= 4 full-write slots"
  (docs/evidence/2026-11-12-mixedwrite-reps.md artifact 2;
  mixedwrite_decode.py:130-131). The correct condition is >= 4 zero BYTES =
  16 zero slots, which is what the stage-9 code and docs state
  (composite.py:114, :1208). Stage-9's wording is the accurate one; no
  action on this branch.
- The exporter's per-rep record territory uses the committed stage-5
  convention ([region_end_k, next DECODED node), composite.py:888 and
  :1537), which differs from the census's refs-gate territory (next NODE
  magic). 40/81 exported stores carry extra token nodes that fail to decode
  (spurious NODE_MAGIC matches inside point data — the same scan convention
  on both sides). Empirically irrelevant here: all 81 export, the
  composition's per-rep refs gate holds, and decoded_reps == pool_groups on
  every one (probe CSV); and the convention matches the committed stage-5
  law (inference).
- 0 decoded nodes with pts == 0 across the census population
  (mixedwrite-reps-nodes.csv) — the probe's and the exporter's diagonal
  index conventions cannot diverge on this corpus (inference from fact).

## Not re-derived (named)

- The UV family's element semantics and the sub-node element-index law stay
  open (the census's opens carry; the branch keeps both fail-closed with the
  gap named — verified for the 12 stores' error paths, not their internals).
- The L2 gate (`catpart.fitness.runner._score_export`) is used as shipped —
  the single gate authority; my A/B runs call it through the seam.
- The 13 empty-mesh exports' underlying record reading ("facet records parse
  but produce no pinned-family triangles"): I verified the class, the count
  and the store names, not the record-reading question itself (it joins the
  family's named opens).

## Method artifacts (outside the repo)

`~/.local/state/catpart-parser/stage9-review/`: my probe/analysis scripts
(scope probe x2, pairing-loop re-derivation, accounting / digest / L2-split
joins, 221df959 anchor check, red-capability runner), the four re-run CSVs
(stage-9 A/B + replay, baseline A/B + replay), the check.sh log, and the
committed-artifact extracts used for `cmp`.
