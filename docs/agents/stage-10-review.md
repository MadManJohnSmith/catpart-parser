# Stage-10 pre-merge review: the E0-b dup-pin law (restricted curve-entry export) (2026-11-13)

Reviewer: stage-10 review sub-agent. Under review: `t3/e0-curve-entry-impl`
@ `014005d` (49d76ad recompute + a34da46 law + 97b8cf4 declared delta +
014005d observed A/B, linear on `9630285`; main `e488265` is base + a
docs-only handoff commit, outside the range). Method per convention:
every headline claim re-derived independently — own CSV joins, own
decode + own law evaluation (the base-commit `9630285` decode as
infrastructure, a spy capturing its `_triangulate` inputs, the dup-pin /
battery / fire decision implemented fresh in the probe), own mutation
battery, own full-corpus base-vs-branch replay, worktree-local venv.
The implementer's numbers were treated as claims, not facts. Corpus
read-only via the gitignored `corpus` symlink; no binaries committed;
my probes and re-run artifacts live outside the repo
(`~/.local/state/catpart-parser/stage10-review/`).

Labels: **fact** = measured/cited (file:line or command); **inference**
= derived, reasoning shown.

## Verdict: MERGE

All four commits do what they say and all six declared deltas (D1-D6)
match what was then measured, verified independently end to end: the
26-member recompute reproduces (own join), the live law predicate
selects exactly the 4 battery-supported stores on my own decode with my
own battery (and agrees with the committed `e0_battery_supported`
classification on every store the analysis measured), the A/B
accounting reproduces to the digit from the committed CSVs, and the
full-corpus replay is byte-identical on 1,116/1,120 exports with the
only 4 differences being the declared firing set (322 fail-closed
stores raise byte-identical errors). The mutation battery proves every
declared negative pin bites. Four findings, none blocking; F1 is a
real latent defect in the NEW per-rep code (zero corpus incidence
today, proven) that the coordinator should fix before the next
baseline's E0 recompute; F2-F4 are docs/tests corrections per the dated
convention.

## Checklist results (the 8 review requirements)

1. **E0 membership at the stage-9 baseline — VERIFIED.** Own join over
   `docs/evidence/data/stage9-identity-export-files.csv`
   (`export_ok=1 AND 'empty-mesh' in failed_check AND loops_curve_entry>0`)
   → **26** (25 dev + 1 held-out `1b1ae784`). Diff vs
   `stage5-identity-export-files.csv` (same join) → 24 → 26, new
   members exactly `4dfef8f2` + `65eb023d` (both stage
   `identity-mixedwrite-reps` in the CSV), 0 lost — matches 49d76ad's
   claims row `U4-E0-recompute-stage9`.
   Probe: `python3 -I probe_csv_ab.py <worktree>` (item-1 section).
2. **Live predicate on my own decode — VERIFIED.** My probe decodes
   each of the 26 members with the base-commit (9630285) decode in an
   isolated src copy (spy on `_triangulate` captures each call's
   elements/records) and evaluates its OWN dup-pin + coplanarity
   battery (tol 2e-3) + whole-store fire decision: fires on exactly
   {`2fca9bc4`, `4ad53b87`, `4ae0392d`, `505bbe1f`} with pinned
   triangle counts 4/35/35/4 (matching the observed CSV); `3dff4d93`
   nonplanar under the pin; every other member normal-less — 16
   table-walk + 2 mixedwrite + the 3 former census-scope-blind stores
   (`4540eacc`, `d4a67129`, `f97b4c86`, reached through the stage-3a
   recovery probes in my own discovery) — matching the
   "live evaluation closes their battery-unknown gap" claim.
   Three-way agreement: my fire set = the committed
   `e0_battery_supported` column (True exactly on the 4; False on
   `3dff4d93`/`1b1ae784`/`08f2eccb`) = the branch's observed A/B flips.
   Probe: `python3 -I probe_own_decode.py <worktree> <base-src>`.
3. **Port fidelity — VERIFIED, one latent defect found (F1).**
   - The U4-D dup_prev port is exact: `_e0b_dup_pin`
     (composite.py:596-606) walks back to the nearest preceding WRITTEN
     element per loop-referenced skip slot — the same walk as the
     decoder's `pin_skips` dup_prev branch
     (`scripts/triage/decode_curve_entries.py:158-170`) — and welds the
     bit-exact `elements[j][1]` coordinates; triangles remap through
     `written_rank` (composite.py:620-621), so the exported vertex list
     is unchanged (no new vertices; the positive fixtures pin this:
     `vertex_count == 12`, exact welded face indices).
   - U4-M mid law absent: no mid logic anywhere in composite.py
     (docstring mentions only); unreferenced skips are never pinned
     (correct — they enter no loop).
   - Fail-closed arms all present: unpinnable (no preceding written
     element → `None`, composite.py:607-608), normal-less record
     (`None` at composite.py:615-616), nonplanar / zero-normal
     (`_loop_plane_status` ≠ coplanar → `None`, composite.py:617-619) —
     one unsupported dropped loop keeps the WHOLE store conservative.
   - Per-rep merges gate on the whole store's mesh being empty
     (composite.py:1078/1744) and the gate bites (M4 below) — but the
     "every unsupported rep blocks" half is broken; see F1.
4. **Declared-before-observed — VERIFIED, with bracket evidence.**
   Commit order: 97b8cf4 18:31:06 < 014005d 18:32:16 (commit
   timestamps alone are a 70 s window, so I corroborated): the corpus
   run's output file in the impl worktree has mtime 18:31:37 — strictly
   between the two commits — and the committed
   `stage10-identity-export-files.csv` is `cmp`-identical to that run
   output. D1-D4/D6 verified from the committed CSVs (item 5); D5
   verified through the seam with two undeclared warning changes (F2).
5. **A/B accounting — VERIFIED to the digit.** Own probe over the two
   committed CSVs: exports 1,120 → 1,120 (dev 1,063, held-out 57), 0
   gained/lost; L2 dev 948 → 952 (+4), held-out 55 steady; 0 lost
   passes; fail→pass exactly the 4 E0-b stores; exactly 4 of 1,442
   rows differ; the changed field set is exactly {l2_status,
   failed_check, triangle_count, closed, loops_curve_entry} on each;
   transitions 0→4/35/35/4 triangles, 2/1/1/2→0 loops, closed
   True→False, manifold stays True, all identity fields
   (vertex_count/element_decl/node_points/curve_entries/node_bytes/
   stage/raw_start) unchanged; error classes byte-identical
   (1,003 pass + 113 fail preserved + 4 flips = 1,120).
   Probe: `python3 -I probe_csv_ab.py <worktree>` (item-5 section).
6. **Tests bite — VERIFIED (6 mutations, one at a time, restored after
   each; `pytest tests/test_composite_export.py -k e0b`, 12 tests).**
   Baseline 12 passed. M0 law removed (`if False and dropped:`) → both
   positives red. M1 empty-mesh condition removed (`if dropped:`) →
   `test_composite_e0b_nonempty_stays_conservative` red. M2 coverage
   requirement removed (normal-less arm → treated as coplanar) →
   `test_composite_e0b_normal_less_loop_keeps_conservative` red. M3
   nonplanar arm removed → `test_composite_e0b_nonplanar_loop_...`
   red. M4 store-level scope removed (per-rep gate drops
   `not triangles`) → `test_composite_e0b_multi_rep_store_gate` red.
   M5 unpinnable arm removed → **no red** (F4: no fixture for the
   no-preceding-written-element shape; the arm stays fail-closed in
   code and 0 corpus members hit it in my probe).
7. **Gate green — VERIFIED.** Worktree-local venv
   (`python3 -m venv .venv && .venv/bin/pip install -e '.[test]'` +
   the `lint` extra's pinned `ruff==0.17.4` — check.sh expects
   `.venv/bin/ruff`), `set -o pipefail; bash scripts/check.sh` → ruff
   clean, **333 passed + 7 skipped** (matches the note). Beyond the
   suite: full-corpus base-vs-branch replay (both code trees, same
   runner, 1,442 parts): 1,116/1,120 exports `cmp`-byte-identical, the
   only 4 differing exactly the E0-b firing set, 322 fail-closed
   stores with exit code AND stderr byte-identical, 0 mismatches.
8. **Summarize quirk — VERIFIED pre-existing and non-blocking.**
   `scripts/triage/ab_identity_export.py` is untouched by the branch
   (not in any of the 4 commits; the same `len(passed) / len(fr)`
   division exists at base 9630285) and `main()` calls `summarize`
   only after the CSV is written. Reproduced live:
   `--include-sha16 2fca9bc4bb7a0e23` (dev-only) → CSV written with
   its 1 row, then ZeroDivisionError on the empty held-out split, exit
   1. The run's deliverable is intact; the full A/B run is unaffected.

## Findings

1. **F1 — non-blocking, fix recommended before the next baseline's E0
   recompute. The per-rep/mixedwrite store-level gate silently drops
   unsupported reps instead of keeping the store conservative.**
   `_triangulate` attaches `stats["dup_pin"] = None` for an empty
   primary triangulation with unsupported dropped loops, but the per-rep
   paths append only non-None candidates
   (`if dup_cand is not None: reps_dup_pin.append(...)`,
   composite.py:1043-1051 per-rep, :1716-1720 mixedwrite) — so the
   gate's `all(c is not None for _b, c in reps_dup_pin)`
   (composite.py:1078, :1744) is dead code and can never veto. A
   multi-rep store whose rep A carries unsupported (normal-less or
   nonplanar) dropped loops on an empty rep triangulation and whose rep
   B carries supported ones — whole-store mesh empty — FIRES: rep B's
   loops export, `loop_stats["loops_curve_entry"] = 0` zeroes rep A's
   still-dropped loops, the store is labeled `e0b-dup-pin` with a
   warning claiming "every dropped loop is normal-carrying and
   coplanar", and it leaves E0 membership at the next recompute while
   its unsupported loops remain unexported. This contradicts the
   declared criterion ("one untestable/nonplanar dropped loop keeps the
   WHOLE store on the conservative rule") and the gate's own comment
   (composite.py:1074-1076). Demonstrated end-to-end with a synthetic
   two-rep store (rep 0: empty + normal-less dropped loop; rep 1: the
   committed fixture's supported shape) through `build_fixture` +
   `build_export`: base (no law) → conservative (0 triangles,
   `loops_curve_entry` 2, unexported warning); branch → fires
   (2 triangles, `loops_curve_entry` 0, `e0b-dup-pin`, exported 1).
   **Incidence today: zero** — the full replay (item 7) and the A/B row
   identity (item 5) prove no corpus store hits the configuration at
   this baseline, and a fire can only add triangles to an
   already-failing (empty-mesh) store, so no L2 pass can regress. The
   exposure is evidence integrity (misreported counters/warnings and
   silent E0-membership loss on a future configuration), which the
   next stages will move stores into. Minimal fix (one line + sentinel
   per path): append `(base, dup_cand)` whenever the `dup_pin` key was
   present (None or not), letting the existing `all(...)` do its job;
   then `loops_curve_entry = 0` is correct exactly when every rep
   fired. Add the missing negative fixture (the demo store above) in
   the same change. The single-rep path is NOT affected (one call,
   candidate merged iff not None — correct).
2. **F2 — non-blocking, docs. The D5 declaration is incomplete on the
   4 firing stores' warning sets.** Declared: lose
   `curve-entry-loops-unexported`, gain
   `curve-entry-loops-exported-dup-pin` (+ `open-shell`). Measured
   through the seam: base `[curve-entry-loops-unexported,
   no-facet-records]` → branch `[curve-entry-loops-exported-dup-pin,
   open-shell, unused-pool-vertices]` — `no-facet-records` also drops
   and `unused-pool-vertices` appears (export.py:403-431: both are
   triangle-conditional, so D4's declared `triangle_count` 0→N
   transition mechanically re-evaluates them). The observed-vs-declared
   table marked D5 MET; the row-level accounting is unaffected (the
   CSV carries no warnings and every other row's triangle_count is
   unchanged). Record a dated correction naming the two implied
   warning changes (impl note D5 + the `U4-stage10-observed-ab` claims
   row if amended).
3. **F3 — non-blocking, docs. The normal-less reason count is off by
   2 in the committed narrative.** The `U4-E0b-live-predicate` claims
   row and the analysis addendum say "19 carry at least one
   normal-less (untestable) dropped loop — including the 3 former
   census-scope-blind stores and the 2 new mixed-write members"; my
   measurement is **21** (16 table-walk + 2 mixedwrite + 3 blind) +
   `3dff4d93` nonplanar = 22 conservative. The composite.py docstring's
   "the other 22 E0 members each carry a normal-less dropped loop, and
   3dff4d93 a nonplanar one" is likewise imprecise — `3dff4d93`'s two
   dropped loops are BOTH normal-carrying (1 nonplanar + 1 coplanar,
   full coverage), so it carries no normal-less loop. The substantive
   claim (every non-firing member carries a normal-less OR nonplanar
   loop; the predicate matches the committed classification) is
   confirmed. Dated corrections per convention.
4. **F4 — non-blocking, tests. The unpinnable arm has no negative
   fixture.** Mutation M5 (removing the no-preceding-written-element
   veto, composite.py:607-608) leaves the e0b suite green — no fixture
   exercises a loop-referenced skip slot with no preceding written
   element. The arm is fail-closed in code and 0 of the 26 members hit
   it in my probe, so there is no behavioral exposure today; add the
   fixture with F1's fix (or standalone).

## What the coordinator should do at merge

- Verdict MERGE: ff-merge `014005d` (or rebase over main `e488265` if
  preferred — the range is docs-additive on both sides; no conflicts
  expected in src/tests, and this note + the handoff amendments touch
  different files than the branch's docs).
- Land F1 (one-line fix per path + the two-rep negative fixture +
  `loops_curve_entry` bookkeeping) BEFORE the next baseline's E0
  recompute, or with the next integration branch — not needed for this
  merge (zero corpus incidence, proven above).
- F2/F3 dated corrections; F4 fixture.
- The fitness row itself stays with the coordinator (dev 952
  projected; this review takes no position on the row).
