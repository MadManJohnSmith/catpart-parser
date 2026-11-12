# Stage-6 review: the raw-array law's exporter integration (pre-merge)

Dated 2026-11-12. Reviewer: the stage-6 review sub-agent (#34), independent
of the implementing delegate. Scope: branch `t3/integrate-raw-array-decode`
@ `c7986bc` (3 commits on `cd5dc44`, linear) — the stage-4a raw-array law
integrated into `src/catpart/geometry/composite.py`, fixtures/tests, the
trigger probe, and the A/B artifacts. The coordinator had verified the
headline accounting from the committed CSVs; this review is the layer
below: code control flow, reference-port fidelity, row-level joins, and
test sensitivity, all re-derived or re-run by the reviewer.

## Verdict: MERGE

Zero blocking objections. Two non-blocking objections (N1, N2 below), one
factual correction to the dispatch record (N3), and two pin-completeness
notes (P1, P2). Every claim below is labeled fact (measured/cited, with
command or file:line) or inference (reasoning shown).

## Review environment (fact)

Detached review worktree at `~/.local/state/catpart-parser/stage6-review/checkout`
(`git worktree add --detach ... c7986bc`), worktree-local venv
(`python -m venv .venv-review && .venv-review/bin/pip install -e '.[test]'` —
the editable install resolves to the review checkout's src, verified via
`catpart.__file__`), corpus symlink to the read-only corpus. Review
verification scripts live OUTSIDE the repo tree
(`~/.local/state/catpart-parser/stage6-review/verify/`); the branch tree
was never modified by this review.

## Checklist results

### 1. Environment / check gate — PASS (fact)

`check.sh`'s two checks run with the review venv (check.sh itself prefers
`.venv/` then system python3, neither present in the review worktree, so
the reviewer ran the identical commands: `scripts/check.sh:9-17`):

- `.venv-review/bin/python -m pytest -q` → **309 passed, 7 skipped**,
  exit 0 (log `stage6-review/check-sh.log`).
- `.venv-review/bin/ruff check .` (ruff==0.17.4, the pyproject pin,
  `pyproject.toml:41`) → **All checks passed**.

### 2. Reproducibility — PASS (fact)

`.venv-review/bin/python -I scripts/triage/ab_identity_export.py --out-dir
<staging> --out-name stage6-identity-export-files.csv` re-run by the
reviewer on the branch code: **1,442 rows; `cmp` vs the committed
`docs/evidence/data/stage6-identity-export-files.csv` → byte-identical,
exit 0.** Zero drift. Summary lines match: dev 982 exports / 886 L2 pass;
held-out 57 / 55.

### 3. Trigger safety (the key risk) — PASS (fact + structural proof)

Structural (fact, `src/catpart/geometry/composite.py:588-608`):

- The raw path lives **inside the walk's `except ExportError`** and is
  reached only after the `_walk_mismatch` signature guard: a store whose
  table walk succeeds (walk-OK, junk coordinates or not) never enters the
  branch; a store whose census-semantics walk is exact gets the ORIGINAL
  failure re-raised (`raise` before the raw attempt). The composite diff
  is 4 hunks (`git diff -U0`): two docstrings, this try/except wrap, and
  the appended functions — nothing else in src changed
  (`git diff --stat 39541a1..c7986bc -- src/` → composite.py only,
  +274/−1).
- If the raw reading fails, the wrapper names BOTH gaps
  (`undecoded-variant`, `exc.detail; the stage-4a raw-array law does not
  cover the store either (...)`, composite.py:604-609) — classification
  never changes.
- `parse_strip_records`/`_loop_plane_status`/`_triangulate` contain no
  raise/except at all (grep over composite.py:326-530); every
  `decode_raw_array` failure mode is an explicit ExportError
  (start not pinned / fit undefined / weak fit / pool not absorbed,
  composite.py:987-1033).

Empirical (fact) — the reviewer wrote an INDEPENDENT re-derivation
(`verify/rederive_trigger.py`, census walk + escape rule + fit predicate
re-typed from the reference sources, not calling `_walk_mismatch` or
`decode_raw_array`) over all 1,442 manifest parts and cross-checked every
row against the committed probe CSV:

- verdict/signature/walk_raise/raw_start agreement: **0 mismatches on
  1,442 rows**; 829 walk-ok + 492 no-list-node + 121 family
  (99 walk-mismatch + 22 layout-raise; walk_raise 61 overrun / 38
  non-finite / 22 layout) — exactly the committed
  `stage6-raw-trigger-probe.csv`.
- Escape candidates re-derived from raw bytes: **84 stores select 0,
  37 select exactly 1, 0 stores select ≥2** — the claim "none of the 121
  stores selects >1 trail-escape start" is confirmed independently.
- 28 projected raw-export stores, sha-set-equal to the committed 28 and
  to the A/B CSV's `identity-raw-array` rows.
- Probe CSV accounting closes: 829 + 492 + 121 = 1,442; 0 audit-error
  rows; no walk-OK store routed; **no store swallowed** (every family
  store carries a named verdict).
- The re-raise arm has zero corpus coverage (0 not-family rows — fact),
  and is pinned synthetically by
  `test_composite_walk_nan_stays_out_of_the_raw_family`
  (tests/test_composite_export.py:524-536), which asserts the walk's own
  failure stands and `"raw-array" not in error["detail"]` — it would go
  red if the guard were dropped or the trigger order flipped, because the
  wrapper's text would then inject "raw-array" into the detail.

### 4. Port fidelity vs the reference — PASS (fact)

Compared line-by-line against `classify_residue_family.py --raw`
(`raw_scan`, `_nice_f32`) and `probe_residue_anchor.py`:

- Coordinate predicate `_raw_nice` (composite.py:889-894) ≡
  `_nice_f32` (classify_residue_family.py:152-153): `v == v and (v == 0.0
  or 1e-6 < abs(v) < 1e7)` — verbatim, including the deliberately
  different floor from the exporter's `_nice` (composite.py:133-142,
  `abs(v) < 1e9`), with the docstring naming why (the raw rate IS the
  parse validation).
- Pair tolerance: `b >= a - 1e-6`, denominator `c1 - 1`
  (composite.py:1013) ≡ raw_scan's asc (classify_residue_family.py:178-182).
- Strong-fit bar 0.98 both halves (composite.py:886,1014-1021) ≡ the scan
  (classify_residue_family.py:270-273).
- Pool absorption: `set(poolv) - set(points)` empty
  (composite.py:1022-1033) ≡ the scan's exact-f32 tuple-membership
  `hits == len(set(poolv))` (classify_residue_family.py:171-172,237).
  NaN-semantics equivalent (both fail-closed).
- Start rule: unique 4-aligned candidate in 32..64 with
  `payload[s + 12*elem_decl] == 0xFF` (composite.py:979-995) — the
  committed law (docs/evidence/2026-11-10-node-streams.md, stage
  4a-residue). Deliberately NOT the scan's best-rate start: that
  difference is the dated correction, below.
- Dated corrections re-verified by the reviewer (fact):
  - `f21255ac`: scan-best start 44 (nice 1.0 / asc 1.0 / absorbed,
    residue-raw-scan.csv:114) vs the escape-pinned start **52 with asc
    0.5161** — re-measured by the reviewer's own code (nice 0.9983,
    absorbed=False at the pin): weak-fit, fail-closed, exactly as
    declared. This is the 29 → 28 delta.
  - "32/39": **32 = scan-strong ∩ escape-unique = 28 raw-export + 3
    pool-unabsorbed + 1 f21255ac weak-at-pin** — reproduced exactly by
    joining `residue-raw-scan.csv` (35 strong / 29 absorbed) with the
    escape-uniqueness re-derivation (37 unique among 121, 0 multi). The
    39 denominator does not reproduce (measured 37) — the correction
    stands.
- Export ladder port (`_decode_raw_array`, composite.py:1045-1087,
  refs-gate raise at :1064):
  records over the store body via the UNCHANGED `parse_strip_records`,
  the M2b identity refs gate (`max ref < elem_decl`), the unchanged
  `_triangulate` — the same ladder walk-OK stores take, with
  `elements = [(0, pt) ...]` (slot 0 = shape 3 = a full triple, the
  correct raw equivalent).

### 5. Row-level accounting — PASS (fact)

Reviewer's join script over the committed CSVs (`verify/accounting.py`;
the A/B CSV is byte-identical to the reviewer's own re-run, so committed
== reproduced):

- exports 1,011 → 1,039; replay join: LOST 0, GAINED 28 (all
  `identity-raw-array`, all dev) — the 28's sha set == probe CSV
  raw-export set == A/B raw rows.
- The 28: 27 big + 1 small; raw_start 48×26 / 40×2; elem_decl 146..20,976
  (A/B + probe CSVs).
- L2: 15 pass + 13 fail(empty-mesh, triangle_count 0, vertices-only), **0
  not-manifold** (manifold=True on 28/28); 926 → 941 with 926 preserved
  (gained passes 15 = 941 − 926 exactly).
- Error classes: undecoded-variant 253 → 225 (−28, no other movement),
  missing-geometry-store 178 → 178; 42 of the 225 stage6 details carry
  the raw-array suffix (the replay's 200-char cap hides the rest; the
  probe CSV names all 93 fail-closed trigger stores per store).
- Stage distribution both ends: 747 identity-table-walk + 152
  identity-per-rep + 112 clean (stage "") + 28 raw — baseline's 747/152/112
  preserved row-for-row (composite_stage changed on 0 baseline rows).

### 6. Fixtures/tests — PASS (fact)

- 9 new test IDs (fact: `git show 39541a1:tests/test_composite_export.py
  | grep -c '^def test_'` = 17 vs 25 on the branch (+8 functions), plus
  the determinism test now parametrized over the raw-array fixture
  (+1 case); suite 300+7 → 309+7).
- The raw-array fixture (`tests/fixtures_gen.py:_composite_raw_node_payload`,
  :1179-1250) is deterministic, 4-aligned start 40, escape byte only at
  start 40's array end; the wrong-offset variant places the escape at
  end+1, unreachable by any 4-aligned candidate for elem_decl=12
  (inference from the byte layout: candidates hit {176..208}, end+1=185).
- What the tests actually pin (all verified passing in the reviewer's own
  pytest run): the trigger order (walk-nan fixture → re-raise, no
  "raw-array" in detail, test:524-536); the start rule's uniqueness
  (a second 0xFF pin → "selects 2 of the 9", test:591-609 — red if the
  rule loosened to first/best candidate); the 0.98 bar in BOTH directions
  (49/50 exactly 0.98 exports, 48/50 = 0.96 fails; x-ascending 0.9796
  fails, test:554-589); `_walk_mismatch` semantics (exact → None, lying
  write count → delta, truncated → layout_error, test:611-630); the
  happy path through the seam with the raw anatomy in the info block and
  PLY vertices == raw triples in array order (test:456-490); byte-level
  determinism of the raw export (parametrized determinism test, test:278-283).

### 7. Fold-through — PASS (fact + structural proof)

- Structural: the 4-hunk diff touches no stage-5 code — `_decode_per_rep`
  (composite.py:725-887), `decode_region`, `layout`, `table_slots`,
  `parse_strip_records`, `_triangulate` are byte-identical to baseline
  (`git diff -U0` hunk map; the per-rep path is only reachable for
  walk-OK stores, which never enter the new except branch).
- Empirical: the replay join — **1,011/1,011 baseline-exported rows with
  identical `ply_sha256` AND identical `l2_fields_sha256`** (both digests,
  `stage6-replay-baseline.csv` vs `stage6-replay-stage6.csv`); 0 v/t
  changes; 0 composite_stage changes; the u24be/per-rep/tiebreak tests
  from stage 5 still in the suite and passing inside the 309.

## Objections (none blocking)

### N1 (non-blocking): uncaught non-ExportError exposure in the raw ladder

`_decode_raw_array` calls `parse_strip_records` + `_triangulate`, which
contain no raise/except (fact, composite.py:326-530); the callers in
export.py catch only `ExportError` (export.py:104-170). A non-ExportError
escaping them on a raw store would crash the export instead of naming a
fail-closed gap. Corpus evidence says this never happens today: 1,442 rows,
0 audit-errors, all 28 raw exports and 93 fail-closed stores named (fact).
The same exposure exists at baseline for walk-OK stores, so this is NOT a
new class introduced by the branch. Minimal fix suggestion (may defer to
the record-reading work, which touches exactly this code): wrap the
records/triangulate step in an `except Exception` that re-raises as
`undecoded-variant` naming the raw gap, or leave as-is and note it in the
family's opens.

### N2 (non-blocking): the re-raise arm and the tolerance edges are corpus-vacuous, pinned only synthetically

The probe CSV has 0 not-family rows (fact) — no corpus store exercises
the walk-exact-junk re-raise; and no test pins the nice predicate's 1e-6
lower floor or the asc pair tolerance's ±1e-6 band directly (the fixtures
use clean values; 1e8 pins the upper floor). The reviewer verified the
predicate/tolerance identity by reading the port against the reference
(fact, section 4) and re-deriving all 121 stores with the reference
predicate (0 mismatches), so nothing currently depends on these pins —
but a future edit to either band would go unobserved by tests. Minimal
fix suggestion: two unit tests on `decode_raw_array` — a coordinate at
1e-7 magnitude (must count not-nice) and an x pair descending by 5e-7
(must still count ascending) — 10 lines total, no urgency for merge.

### N3 (factual correction, no code impact): the dispatch's base commit is wrong

The dispatch says "3 commits on 39541a1, linear". Measured:
`git merge-base 39541a1 c7986bc` → **cd5dc44** — the branch is based on
cd5dc44 and `39541a1` (E0 recompute, main's HEAD) is a SIBLING commit, not
an ancestor (fact). The branch's diffstat "deleting" curve-entry files is
an artifact of diffing across the sibling, not a deletion (fact: the
branch never touches those paths). Consequence: none for review — the
integration doc itself states base `cd5dc44`
(2026-11-12-stage6-integration.md:5) — and the 3-way merge into main stays
clean (39541a1 adds two files the branch doesn't touch). Correction is
for the record only; the dispatch line "declared-delta commit 913feba
precedes observed c7986bc" is correct (fact, git log).

### Pin notes P1/P2 (observation, no action)

P1: the multi-candidate fail-closed arm is corpus-vacuous (0 stores ≥2
candidates, fact) but IS pinned by test (test:591-609) — good state.
P2: the declared D9 performance figure ("slowest export ~1.4 s") was not
independently re-measured by the reviewer; the reviewer's own A/B re-run
completed in minutes with 0 timeouts (fact), consistent with D9 but not a
timing reproduction. Immaterial to the verdict.

## What this review did NOT do (fact)

Did not run CI, did not merge, did not modify src/tests on the branch,
did not re-measure per-export timings, and did not audit the corpus
binaries themselves (read-only, symlinked, never committed — verified:
no binary or corpus file appears in the branch diff).
