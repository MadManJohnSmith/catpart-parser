# Stage-5 pre-merge review: stage-4b laws integrated into the exporter (2026-11-12)

Reviewer: stage-5 review sub-agent. Under review: `t3/integrate-decode-laws-exporter`
@ `cfe0dcd` (65a6b19 src + 35b580e declared delta + cfe0dcd observed A/B, linear on
`e8a6f02`). Method: every headline claim re-derived independently (own venv, own
re-runs, own joins, own instrumentation over the corpus); the implementing
delegate's numbers were treated as claims, not facts. Corpus read-only via the
gitignored `corpus` symlink; no binaries committed; my scripts and re-run
artifacts live outside the repo (`~/.local/state/catpart-parser/stage5-review/`).

Labels: **fact** = measured/cited (file:line or command); **inference** = derived,
reasoning shown.

## Verdict: MERGE

All headline accounting verified byte-exact by independent re-runs and joins;
the port matches the 4b reference implementations on every semantic point
checked; the fail-closed ladder is preserved end-to-end. Three objections, none
changing merged behavior on this corpus (one test gap, one latent hardening
edge never exercised, one 2-row documentation gap) — O1 is recommended as a
test-only follow-up that can land before or with the merge.

## Checklist results

1. **Environment — PASS (fact).** Worktree-local `.venv-review`
   (`python -m venv .venv-review && .venv-review/bin/pip install -e '.[test]'
   && pip install 'ruff==0.17.4'` — ruff is the `lint` extra, pyproject.toml:41,
   not in `[test]`). Corpus symlinked. `PATH="$PWD/.venv-review/bin:$PATH"
   sh scripts/check.sh` on cfe0dcd: **ruff clean, 299 passed + 7 skipped**
   (pytest direct). Nuance: with the venv ON PATH the 5 console-script skips
   (`tests/test_console_scripts.py:18`, `shutil.which`-based) execute and pass →
   306 passed / 0 skipped. Both readings are green; the gate figures match.

2. **Reproducibility — PASS (fact).** Re-ran on the branch code:
   - `ab_identity_export.py --out-dir <staging>` → byte-identical to the
     committed `stage5-identity-export-files.csv` (`cmp`).
   - `replay_export_seam.py` (branch src) → byte-identical to
     `stage5-replay-stage5.csv`.
   - Baseline end reproduced independently: `git archive e8a6f02 src manifests`
     extracted to a staging dir + the branch's replay script (the evidence
     doc's own recipe) → byte-identical to `stage5-replay-stage5.csv`'s
     baseline counterpart `stage5-replay-baseline.csv`.
   No drift; name-nothing.

3. **Port fidelity vs the 4b references — PASS with one test-gap objection (O1).**
   - (a) u24be guard **in the code**: `src/catpart/geometry/composite.py:325`
     `widths = (1, 2, 3) if element_count > 65_535 else (1, 2)`. Guard applies
     per rep too (the per-rep parse passes `d["elem"]`,
     composite.py:748-750). The 4 gate-event stores (4436caff, 4ff7b61b,
     6b05e15d, d4eace9b — elem_decl 657..26,127) export and PASS in the
     committed stage-5 run (verified in the CSV). **BUT the guard is NOT
     pinned by a negative test**: the branch diff contains exactly two
     `65_535` references — the guard and the positive fixture's
     `assert n > 65_535` (tests/test_composite_export.py:310). See O1.
   - (b) plane tiebreak: the rank tuple `(tiling, repeats, oob, nonplanar,
     width, k)` at composite.py:389-394 is **identical** to the reference
     `parse_width_test` rank (scripts/triage/not_manifold_audit.py:269-274);
     `_loop_plane_status` matches the reference exactly (PLANE_TOL 2e-3 =
     composite.py:408 vs the reference's hardcoded 2e-3; nn==0 → nonplanar;
     skip/OOB loops bypass the plane test in both). Empirical: my
     instrumented double-parse over the whole corpus (branch parse vs
     old-rank parse, same bytes) measures **59 exported-both stores /
     155 records flipped, ALL u8 → u16be** — exactly the S5-width-plane claim
     — plus 29 gained stores / 80 records in the same direction (new per-rep
     exports parse under the new rank; consistent with the doc's interaction
     note). No reverse flips, no unexpected width-3 wins.
   - (c) per-rep ladder: trigger is ONLY the single-rep absorption failure
     (composite.py:563-566; sole call site of `_decode_per_rep`); rep
     admission = `decode_region` success, which raises on every non-walk-exact
     or non-finite path (composite.py:213-286) — equivalent to the reference
     audit's `we == rs + 4*write_count and nok` gate (unabsorbed_pool_law.py
     via decode_big_form_points.py:133-176); `NOISE_REL = 1e-5` (composite.py:620)
     with `_tol_match` semantically identical to the reference `tol_match`
     (same per-coordinate scale). Measured on the corpus: 15 noise-matched
     vertices, max delta **1.25e-8**; smallest rejected delta **2e-4** — the
     threshold sits ~3 decades from both edges (the 4b note's gap claim
     holds). Per-rep refs gate against the REP's own element count
     (composite.py:754); a non-absorbing rep stays unexported with the reason
     named (composite.py:733-742); when no rep exports, the stage-3d
     `unabsorbed` classification is re-raised — and the pre-existing
     corrupted-fixture test (`geometry-composite-law-unabsorbed`, asserting
     `"unabsorbed" in detail`) passes THROUGH the new code path, so the
     fail-closed ladder is exercised end-to-end. Latent edge: see O2.
   - (d) single-rep path: `parse_strip_records` gained an optional
     `elements=None`; passing it activates the plane rank (by design — that
     IS the tiebreak law); with `elements=None` the rank reduces to the
     committed stage-3b one. Consistency evidence: 799/859 exported-both rows
     byte-identical on BOTH digests; 747 single-rep exports all still export
     via `identity-table-walk`; the 112 clean exports 0-changed (my replay
     join). FACT.

4. **Row-level accounting — PASS (fact; my own joins over the committed CSVs,
   which my re-runs reproduced byte-identically).**
   - exports 859 → 1,011: **+152, 0 lost** (superset verified).
   - L2 pass 782 → 926: **0 pass→fail regressions** (hard gate); +144 =
     121 passing new exports + 21 not-manifold→pass + 2 degenerate→pass
     (5f8f00de, 78685667 — both present in my fail→pass set).
   - fail→pass among previously-exported stores: **23** = 21 (baseline
     `failed_check=not-manifold`, matching the 4b census's `v2_manifold=1`
     set of 21, verified in not-manifold-files.csv) + 2 degenerate fixes.
   - gained exports failing the gate: **31 = 19 not-manifold + 12
     empty-mesh** — nothing alarming; empty-mesh and residual not-manifold
     are the documented stage-4a/3d families, and E0 (the membership call on
     them) is correctly left to the coordinator per the 4a order of
     operations.
   - v/t-changed old exports: **18** = 9 pass→pass small decrements + 5
     width-set (of the 21) + 2 degenerate fixes (+4 triangles each) + 2
     fail→fail (13bb5c0c u24be 5,855→30,292 — D2 exact; 26504a08 — D4's
     named correction). Matches the brief's 18.
   - PLY-diff rows: **60**, of which 6 change PLY bytes with identical L2
     fields; 799 byte-identical. Error classes: undecoded-variant 405 → 253
     (−152: the 148 census family + 4 census-blind — count reconciles),
     missing-geometry-store 178 unchanged.
   - Census cross-checks: unabsorbed-pool-files.csv has exactly **148**
     `stage3d_class=unabsorbed` rows, 111 with `per_rep_tol=1` (D1's
     figure); the 4 "census-blind" stores ARE rows in the census file but
     with **empty `store_body`** — the census's strict locator never reached
     them, so "census-blind" is accurate.

5. **Fixtures/tests — PASS (fact).** u24be grid is 40×40×41 = 65,600 > 65,535
   with PLY faces asserting max index 65,599 (test_composite_export.py:299-321);
   multi-rep fixtures cover absorb+non-absorb (two pool groups + two token
   nodes with per-node territories; the partial variant's 9th poison vertex,
   tests/fixtures_gen.py `_composite_multi_rep_store`); determinism: fixture
   bytes pinned for ALL `COMPOSITE_VARIANTS` incl. the 4 new
   (test_composite_fixtures_deterministic, parametrized), export-level
   byte-determinism pinned for the base variant (test_composite_export_determinism)
   and exact v/t/faces for the new variants; corpus-level byte determinism
   re-verified by my re-runs (item 2). Informational: the twice-export
   determinism test was not extended to the new variants (their exact-count
   assertions cover the content; no objection).

6. **Fold-ins — PASS (fact).**
   - `node_bytes` additive: at e8a6f02 the schema's top level already has
     `"additionalProperties": true` and no `composite` property — the branch
     only documents the block (export-summary-v1.json, `required` untouched);
     every export validates before and after (export.py:450), and the new
     test asserts schema validity with `node_bytes` present
     (test_composite_export.py:397).
   - Replay harness hashes PLY and L2 fields SEPARATELY
     (replay_export_seam.py:63-71, `l2_fields_sha256` over exactly the 5
     fields `catpart.fitness.runner._score_export` reads — verified against
     runner.py:321-330).
   - The dated stage-3d correction states 28/34 ("28/34 keep vertex/triangle
     counts", docs/evidence/2026-11-10-node-streams.md, dated 2026-11-12).

## Objections

- **O1 (test gap — fix as a test-only follow-up, before or with the merge):**
  the u24be scope guard (composite.py:325) has no corpus-free negative pin.
  The gate event (S5-u24be-scope-correction: 4 exported stores lost to junk
  3-byte parses when u24be was offered unconditionally) is exactly the
  regression this suite would not catch: the positive 65,600 fixture pins
  that width 3 IS offered above the threshold (dropping u24be entirely →
  that fixture fails), but a guard that is REMOVED or NARROWED (widths
  (1,2,3) at elem <= 65,535) leaves the whole corpus-free suite green —
  the first A/B run demonstrated it takes the corpus to notice. Minimal
  fix: one unit test asserting `parse_strip_records` offers no width-3
  candidate at `element_count <= 65_535` on a small buffer where a width-3
  parse would tile onto the next header (the gate event's mechanism), or a
  fixture-level test exporting a small interleaved store and asserting the
  u8/u16be winner. ~15 lines, no src change.
- **O2 (latent fail-open edge in `_decode_per_rep` — hardening, non-blocking):**
  a rep k >= `len(groups)` is gated on an EMPTY pool group
  (`gv = groups[k].vertices if k < len(groups) else ()`, composite.py:726) —
  distinct = ∅ → unmatched = ∅ → the rep exports with NO absorption check.
  This is the one place the stage-4b "fail-closed, no guessing" ladder is
  open by construction. Measured impact on this corpus: **0 of 152** per-rep
  invocations have decoded reps > pool groups (my instrumentation), so no
  behavior changes on the committed A/B. Minimal fix (one line): treat
  `k >= len(groups)` as a named unexported rep (`rep {k}: no pool group to
  absorb`), or assert `len(decoded) <= len(groups)` and name the residue.
- **O3 (documentation, 2 rows):** the evidence doc's D5 effect taxonomy sums
  to 58 stores (21+2+9+24+2) but the measured PLY-diff set is 60. The two
  unaccounted rows are same-v/t and L2-transition-neutral: **d4127e6b**
  (fail→fail, identical v/t, changed PLY bytes) and one pass→pass
  identical-v/t row beyond the named 24 (25 measured). Zero impact on the
  pass arithmetic (782+117+4+21+2 = 926 checks out). Minimal fix: amend D5's
  list ("25 pass→pass identical v/t" and "3 fail→fail incl. d4127e6b
  same-v/t") or name the two rows.

## Not re-derived (named)

- The 4b census's own measurements (noise bounds, u24be byte-verification on
  13bb5c0c) — taken from the committed 4b artifacts, spot-checked where cheap
  (148/111/21 counts, noise gap).
- E0 membership, raw-array law, U3-variant — out of dispatch, correctly
  untouched (no delta claimed from them; none observed).
