# Stage-15 pre-merge review: the two owner-authorized levers — the dup-pin relaxation + the unordered-triangle dedup (2026-11-13)

Reviewer: stage-15 review sub-agent. Under review:
`t3/dup-pin-all-unordered-tri-dedup` @ `03adec3` (3 commits off main
`6fc5935`: `8241006` implementation -> `270464d` DECLARED A/B ->
`03adec3` observed A/B; parent verified `6fc5935`; the child's branch
head is `03adec3` in the shared repo). Main may have moved docs-only —
the coordinator rebases at merge. Worktree note: the harness had parked
this worktree's `t3/stage15-pre-merge-review` branch at main's head
(`2b80185`); reset to `03adec3` — the branch the note lands on is
`03adec3` + this commit. (The first review dispatch died on a provider
3008 before doing any work; this is a fresh start, zero residual.)

Authorization (verified, dated): handoff cont. 23 (2026-11-13) records
the owner's decision to land BOTH levers — the dup-pin-ALL relaxation
EXPLICITLY OVERTURNS the stage-10 U4 conservative rule, and the
unordered-dedup law lands with the Phase-B >= 2 gate MET per stage-14
review F1. The implementation matches the authorized scope; nothing
beyond the two levers shipped.

Method per convention: every headline claim re-derived with my OWN
walkers — my own observe-only capture wrappers on the committed decode
calls (`composite._triangulate`, `composite._e0b_dup_pin`,
`composite._apply_unordered_dedup`,
`composite.decode_composite_store`), my own corpus walk over the
manifest through the real seam (`build_export` black box +
`fitness.runner._score_export` as the single gate authority), my OWN
dup-pin weld re-implementation (the U4-D weld + my own strip/fan
triangle emission re-written from the committed loop semantics as read
at `03adec3`) with my own gate replication in committed order, my own
unordered-triple dedup census over every captured pre-dedup assembled
mesh corpus-wide, my own warning-class dumps on 7 named stores, and my
own full-corpus A/B re-run (cmp-checked). The child's functions were
NEVER imported. My probes and artifacts live outside the repo
(`~/.local/state/catpart-parser/stage15-review/`: `probe_stage15_
review.py`, `stage15-live-ab.csv`, `stage15-subset-ab.csv`,
`capture.json`, `pins.pickle`, `own-duppin.json`, `own-warnings.json`,
`mutations.json`, `gate.log`); corpus read-only via the gitignored
`corpus` symlink; `python3 -I` throughout; no binaries committed;
`src/` untouched (verified by `git status` before/after every run and
byte-restored after each mutation run).

Labels: **fact** = measured here (command or file:line); **inference**
= derived, reasoning shown.

## Verdict: MERGE

All six briefed claims verify independently at every level I could
reach. My own full-corpus A/B re-run at `03adec3` is **cmp
BYTE-IDENTICAL** to the committed `stage15-identity-export-files.csv`
(1,442 rows); exactly **35 of 1,442 rows differ** vs the accepted
stage-13 CSV, set-identical to the declared 26 dup-pin rows + 9 dedup
carriers with the exact declared transitions; exports **1,173
unchanged**; dev L2 **1,001 -> 1,033/1,381 = 74.80% (+32 exactly)**;
held-out **55 -> 56 (+1b1ae784)**; every row NOT in the 35 is
byte-identical to the stage-13 accepted CSV. Lever 1: my own weld
re-derivation reproduces the committed ceiling **row-for-row on all
26** (`triangle_count` == `pinned_tris`, degenerate == `pinned_
degenerate`, sum 14,761 over the 25 passes); the corpus fire set is
exactly the 26 (plus the 4 stage-10 E0-b passers that fire identically
under both laws — rows byte-identical); **0 unpinnable, 0 whole-store
scope violations corpus-wide**; 3dff4d93 stays not-manifold. Lever 2:
my own dedup census over every not-manifold assembled mesh finds
**exactly 10 duplicate-carrying inputs corpus-wide — 9 carriers (my
own drop counts match the law's and the observed deltas exactly: 4, 2,
13, 2, 2, 1, 2, 1, 2) + 1 declined (a61588e5, kept verbatim)**; 0
duplicates on any manifold input (the gate never fires on a passing
store corpus-wide); 0 raw-array incidence; b912cbef dedups to manifold
(10,030 tris) and stays failed `degenerate-triangles` on its 3
pre-existing skips. Tests: nothing deleted — 3 pins re-scoped in
place, 6 new variants; **all 4 of my own mutation runs went red on
exactly their named pins** (battery restore, pre-manifold removal,
post-manifold removal, unpinnable-arm removal). Schema/warnings:
additive only (2 new enum values, 2 re-dated descriptions, 0 removed
paths). Commit order verified impl -> declared -> observed by
timestamps AND tree contents (the observed CSV does not exist in the
declared commit's tree). Gate re-run green in a worktree-local venv
under `set -o pipefail`: **ruff clean, 361 passed + 7 skipped**. The
declared-before-observed discipline held: the declaration (committed
`270464d`, before the corpus run) matches the observed run on every
gate D1-D6. Zero STOP gates fired. No blocking findings; two
non-blocking observations (both no-action, recorded for the record).

## Checklist results

1. **C1: the observed A/B — VERIFIED (cmp-identical live run).** My
   own full-corpus run of `ab_identity_export.py` at `03adec3` ->
   `cmp` **byte-identical** to the committed
   `stage15-identity-export-files.csv` (1,442 rows; dev 1,033/1,381 =
   0.7480, held-out 56/61, exports 1,173 = dev 1,116 + held-out 57).
   My own diff vs the accepted `stage13-identity-export-files.csv`:
   **exactly 35 rows differ** — 26 empty-mesh-origin + 9
   not-manifold-origin; transitions **25x fail/empty-mesh -> pass, 8x
   fail/not-manifold -> pass, 1x fail/empty-mesh -> fail/not-manifold
   (3dff4d93, 0 -> 3 tris, manifold True -> False), 1x
   fail/not-manifold -> fail/degenerate-triangles (b912cbef, 10,031 ->
   10,030 tris, manifold False -> True)** — exactly the declared
   table. Set identity: the 26 == the committed
   `stage14-dup-pin-ceiling.csv` rows (0 outside, 0 declared-but-
   unchanged); the 9 == the declared carriers (1d256d12, 25aeb5a0,
   2d59ff19, 396a9d79, 4a21610f, e1eed721, f4a5df2a, ef61cfc2,
   b912cbef) with drop deltas == the declared −1..−13; the other 24
   not-manifold rows AND a61588e5 are byte-identical. The other 1,407
   rows: byte-identical. 0 lost exports, 0 lost passes. Stage mix of
   the 35: table-walk x24 / per-rep x5 / mixedwrite x6 — exactly the
   note's section 8.
2. **C2: lever 1 (the dup-pin relaxation) — VERIFIED with my own
   walkers.** Code: the battery criterion is removed from
   `_e0b_dup_pin` (the normal-less `return None` and the
   `_loop_plane_status` coplanarity check are gone); the fail-closed
   arms stay — the unpinnable arm (`j < 0` -> no pin -> `None`,
   composite.py:612-621), the E0 whole-store scope (fire points only
   where the whole-store primary mesh is empty: single-rep
   `not triangles and dropped` at :707, per-rep/mixedwrite store-level
   gates `if not triangles and reps_dup_pin and all(...)` at :1197 and
   :1874), and the per-rep None-candidate veto re-scoped to unpinnable
   (the None now arises ONLY from unpinnable — battery-based `None`s
   removed). Fire-set re-derivation, corpus-wide: **30 stores fire at
   `03adec3` = the 26 changed rows + the 4 stage-10 E0-b passers
   (2fca9bc4, 4ad53b87, 4ae0392d, 505bbe1f) that fire identically
   under the relaxed law (rows byte-identical, 4/35/35/4 tris —
   exactly the stage-14 note's "not here — they pass" set)**; 9
   further stores evaluate rep-level candidates but are correctly
   vetoed by the whole-store gate (their assembled primary is
   non-empty — 0 scope violations); **0 None candidates corpus-wide**
   (0 unpinnable, matching the stage-14 census). My own dup-pin
   re-derivation (my own weld + my own strip/fan emission + my own
   gate in committed order) over the captured `_e0b_dup_pin` args:
   **26/26 rows agree exactly** — my triangle count == the observed
   A/B `triangle_count` == the ceiling CSV's `pinned_tris` (32-3,456,
   sum 14,761 over the 25 passes), my degenerate == `pinned_
   degenerate` (0 on every pass, 1 on 3dff4d93), my gate verdict ==
   the observed gate (25 pass + 3dff4d93 not-manifold). 3dff4d93: my
   own dedup census on its pinned mesh = 3 triangles, **0 duplicate
   unordered triples** -> the dedup correctly never fires there -> it
   stays failed not-manifold.
3. **C3: lever 2 (the unordered-triangle dedup) — VERIFIED with my
   own census.** Code: `_apply_unordered_dedup` wired on all 4
   exported composite exits (single-rep tail composite.py:989 after
   the dup-pin merge; `_decode_per_rep` :1228; `_decode_raw_array`
   :1455; `_decode_mixedwrite` :1904 — each path applies it exactly
   once); fire gate = input mesh NOT manifold AND duplicate unordered
   triples AND post-dedup manifold; declined arm keeps the emitted
   list verbatim and names the gap; degenerate-shaped triples never
   deduped. My own census over EVERY captured pre-dedup assembled mesh
   corpus-wide (1,442 stores): **exactly 10 inputs carry duplicate
   unordered triples — the 9 carriers + a61588e5; 0 on manifold
   inputs** (the gate's pre-manifold condition never even evaluates a
   drop on a passing store — zero-regression by construction,
   measured); **23 no-fire not-manifold inputs** (duplicates absent)
   plus 3dff4d93's pinned mesh (duplicates absent); **0 raw-array
   not-manifold inputs** (the child's "measured corpus incidence 0"
   confirmed). My own drop counts == the law's own dropped counts ==
   the observed row deltas on all 9 carriers (1d256d12 -4, 25aeb5a0
   -2, 2d59ff19 -13, 396a9d79 -2, 4a21610f -2, e1eed721 -2, f4a5df2a
   -2, ef61cfc2 -1, b912cbef -1), post-dedup manifold True on all 9.
   The declined branch has **exactly 1 corpus store: a61588e5** (my
   own census: 1 duplicate pair, post-dedup NOT manifold — fins
   residue alongside; the law kept the 1,383 emitted triangles
   verbatim, `ret_n == n`, row byte-identical, and my own seam run
   shows `duplicate-triangles-dedup-declined` on its warnings).
   b912cbef: dedup fires (10,031 -> 10,030, manifold True) and the
   store stays failed `degenerate-triangles` — my own seam run: 3
   degenerate skips ride untouched + `curve-entry-loops-unexported`
   (1,731) + `duplicate-triangles-deduped` — exactly the declared
   fail-class change. Warning spot-checks (my own seam runs, D4):
   08f2eccb + e8dbf460 gain ONLY `curve-entry-loops-exported-dup-pin`
   (closed meshes); 109bcfe7 additionally open-shell + unused-pool-
   vertices; 3dff4d93 additionally open-shell + unused + degenerate-
   triangles-skipped (1); 1d256d12 gains `duplicate-triangles-deduped`
   keeping its own counters — all as declared.
4. **C4: the re-scoped test inventory — VERIFIED, mutations run.**
   `git diff 6fc5935..03adec3 -- tests/`: nothing deleted — 3 test
   functions re-scoped IN PLACE (the two old battery negatives ->
   `..._exports_under_relaxed_law` fire pins; `unsupported_veto` ->
   `unpinnable_veto` with the fixture's rep-0 skip slot moved to
   element 0), 6 new fixture variants + tests (`e0b-relaxed-not-
   manifold`, `e0b-multi-rep-relaxed`, 4 dedup variants), the
   unchanged pins (`e0b-unpinnable`, `e0b-nonempty`,
   `e0b-multi-rep-conservative`, the 2 positives) intact; fixtures are
   generated in-memory (`fixtures_gen.py`), no fixture binaries. My
   own mutation runs (4, each applied to the worktree src and
   byte-restored after; `run_mutations.py`):
   - **M1 restore the stage-10 battery** (normal-less veto +
     coplanarity check): **4 red** — exactly the fire pins
     (`e0b-nonplanar...relaxed_law`, `e0b-normal-less...relaxed_law`,
     `e0b-relaxed-not-manifold`, `e0b-multi-rep-relaxed`); 14 green
     (the conservative pins stay conservative — the positives are
     battery-supported).
   - **M2 remove the dedup PRE-manifold condition**:
     `dedup-manifold-no-fire` **red** (the two-sided sheet would
     collapse); the other dedup tests green.
   - **M3 remove the dedup POST-manifold condition** (always drop):
     `dedup-declined` **red**; the other dedup tests green.
   - **M4 remove the unpinnable arm**: `e0b-unpinnable` +
     `e0b-multi-rep-unpinnable-veto` **red** (KeyError on the
     unresolved skip ref — the arm is load-bearing); 16 green.
   The new guards are genuinely red under their named mutations; the
   veto fixture genuinely tests the NEW scope (under M1 it stays
   green — its rep-0 loop is unpinnable, not normal-less).
5. **C5: schema/warnings additive only — VERIFIED.** My own
   structural diff of `export-summary-v1.json` (6fc5935 vs 03adec3):
   **2 added enum values** (`duplicate-triangles-deduped`,
   `duplicate-triangles-dedup-declined`), **0 removed paths**, 2
   description re-datings (the warning-class description + the
   composite-block description — prose only). export.py: 2 new
   warning constants + 2 additive warning-emission blocks + the
   re-dated dup-pin detail; composite.py: the two levers + wiring +
   docstring/comment updates; **no other src surface touched**
   (`git diff 6fc5935..03adec3 --name-only` = composite.py, export.py,
   the schema, fixtures_gen.py, test_composite_export.py, 4 docs
   files — no scripts/, no fitness/, no manifests/). The behavioral
   proof corpus-wide: the 1,407 rows outside the declared 35 are
   byte-identical through the whole seam, 0 lost exports/passes.
6. **C6: commit order + gate — VERIFIED.** Commit timestamps:
   `8241006` 16:52:43 (impl) -> `270464d` 16:53:50 (DECLARED, adds
   `stage15-claims.csv` SG1-SG7) -> `03adec3` 16:55:36 (observed, adds
   `stage15-identity-export-files.csv`) — the stage-10/12/13
   declared-before-observed precedent; tree contents confirm the
   order (the observed CSV does not exist in `270464d`'s tree;
   `git log --diff-filter=A` per file). The declared D1-D6 gates all
   MET in the observed run (no STOP gate fired; the declared 35 ==
   the observed 35). Gate re-run in a worktree-local venv under
   `set -o pipefail`: **ruff clean, 361 passed + 7 skipped** (=
   the child's report; 349+7 at main + 6 new tests + 6 determinism
   params). The note's reproduction commands run: the full A/B (cmp
   identical), the 59-store pre-declaration subset (26 dup-pin + 33
   not-manifold sha16s from the two committed ceiling CSVs) ->
   **exactly 35 changed + 24 byte-identical** (SG6's figure), and the
   gate. Claims SG1-SG7: all seven verified by the checks above.

## Findings

Classification: **no blocking findings**; two non-blocking
observations (no action required — recorded so the numbers are
CSV-composable and the next reader does not re-derive them).

- **O1 (non-blocking, no action): the corpus fire set of lever 1 is
  30 stores, not 26 — the 4 extra are the stage-10 E0-b passers.**
  2fca9bc4, 4ad53b87, 4ae0392d, 505bbe1f fire under BOTH the stage-10
  battery-supported law and the relaxed law with identical output;
  their rows are byte-identical and they are NOT in the 35 (the
  stage-14 note already names them as passing). Any future counter
  that counts "stores where `curve_entry_law` is set" at a stage-15+
  baseline will read 30, not 26 — the 26 is the DELTA set (changed
  rows), and the two figures are both correct for their own
  questions. (Measured: fired=30 = 26 changed + 4 unchanged passers;
  plus 9 rep-candidate stores correctly vetoed by the whole-store
  gate.)
- **O2 (non-blocking, no action): the stage-14 mechanism CSV's
  `dup_triangle_extras` column undercounts the carriers' duplicates**
  (it counts ORDERED triples — the stage-14 detector's scope; e.g.
  a61588e5 shows 0 while my own unordered census finds 1). The
  stage-15 note already declares this ("the measured drop counts are
  the law's own unordered census"); no CSV needs changing — the
  authoritative per-store drop counts for stage 15 are the law's own
  (`unordered_dedup_dropped`), which my own census matches on all 9
  carriers.

## What the coordinator should do at merge

1. Rebase over main (docs-only movement expected), ff-only merge.
2. The fitness row stays with the coordinator (dev 1,033 projected;
   the observed A/B already matches it exactly).
3. Then the item-5 close sequence per handoff cont. 23 (owner
   decision, dated): failure-classification table, render sanity,
   publish, #34/#28 closure, follow-up tickets (incl. the named
   CSV-quoting debt). This review adds nothing to that queue.

## Reproduction (my own probes, outside the repo)

All runs in this worktree (`t3/stage15-pre-merge-review` @ `03adec3`),
venv `.venv`, corpus symlinked read-only, `python3 -I`:

    # C1: my own full A/B re-run + byte-identity (cmp)
    .venv/bin/python -I scripts/triage/ab_identity_export.py \
      --out-dir ~/.local/state/catpart-parser/stage15-review \
      --out-name stage15-live-ab.csv
    cmp ~/.local/state/catpart-parser/stage15-review/stage15-live-ab.csv \
      docs/evidence/data/stage15-identity-export-files.csv

    # C1/C2/C3: my own capture walk (observe-only wrappers on the
    # committed decode calls; my own dedup census per store; my own
    # dup-pin args capture) + my own weld re-derivation + warning dumps
    .venv/bin/python -I ~/.local/state/catpart-parser/stage15-review/probe_stage15_review.py \
      --phase capture
    .venv/bin/python -I ~/.local/state/catpart-parser/stage15-review/probe_stage15_review.py \
      --phase duppin
    .venv/bin/python -I ~/.local/state/catpart-parser/stage15-review/probe_stage15_review.py \
      --phase warn --include 08f2eccb,e8dbf460,109bcfe7,3dff4d93,b912cbef,a61588e5,1d256d12

    # C4: my own 4 mutation runs (battery restore / pre-manifold /
    # post-manifold / unpinnable arm), src byte-restored after each
    .venv/bin/python ~/.local/state/catpart-parser/stage15-review/run_mutations.py

    # C6: the note's subset reproduction (59 stores = 26 + 33)
    .venv/bin/python -I scripts/triage/ab_identity_export.py \
      --include-sha16 <the 59 sha16s> \
      --out-dir ~/.local/state/catpart-parser/stage15-review \
      --out-name stage15-subset-ab.csv     # -> 35 changed + 24 identical

    # C5/C6: additive-only + no stray surface
    git diff 6fc5935 03adec3 --name-only   # 8 files, docs/src/tests only
    git diff 6fc5935 03adec3 -- tests/     # nothing deleted (3 renames in place)

    # Gate (worktree-local venv, pipefail):
    set -o pipefail && bash scripts/check.sh   # ruff clean; 361 passed + 7 skipped

Anchor numbers quoted in this note (per-store drop counts, pinned tris,
warning classes, mutation outcomes) are in the archived artifacts:
`capture.json` / `own-duppin.json` / `own-warnings.json` /
`mutations.json` / `gate.log` under
`~/.local/state/catpart-parser/stage15-review/`.
