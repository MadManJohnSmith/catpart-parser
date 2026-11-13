# Stage-11 pre-merge review: the subnode-index population probe — the lever is dead (2026-11-13)

Reviewer: stage-11 review sub-agent. Under review: `t3/subnode-index-absorption`
@ `3ea96a4` (one commit off main `d837f1a`: the Phase-A probe + CSVs + claims
row MW16 + the dated addendum; analysis-only, src/ untouched). Main has since
moved to `5e03e74` and `77deab2`, both docs-only handoff amendments — the
coordinator rebases at merge. Worktree note: the harness had renamed this
worktree's branch to `t3/stage11-pre-merge-review` at `5e03e74` (zero unique
commits, contained in main); I reset it to `3ea96a4` — the branch the note
lands on is `3ea96a4` + this commit.

Method per convention: every headline claim re-derived with my OWN walkers —
my own pool parse from raw bytes (not `pool.py`'s scan), my own token-node
scan and flat-law decode, my own diagonal/union absorption accounting, a
law-independent whole-body byte census, an exhaustive all-container store
walk (no short-circuit) plus a locator-free raw wrapper scan, and my own
`build_export` runs over all 322 fail-closed parts. The child's committed
probe was used only as a black box for the reproduction check (re-run +
`cmp`). The committed exporter/`composite`/`pool`/`store` modules served as
infrastructure (the stage-10 review's precedent); the child's probe
functions were never imported. My probes and artifacts live outside the
repo (`~/.local/state/catpart-parser/stage11-review/`); corpus read-only via
the gitignored `corpus` symlink; no binaries committed.

Labels: **fact** = measured/cited (file:line or command); **inference** =
derived, reasoning shown.

## Verdict: MERGE

All four briefed claims verify independently, and the decisive one (C2)
verifies two ways: by the child's absorption accounting (reproduced with my
own decode) and by a decode-free byte census that cannot be an artifact of
any law implementation — exactly 1 of the 93,518 distinct pool vertices of
bad44bdf has zero occurrences outside the pool's own records, and it occurs
EXACTLY ONCE in the 24.7 MB body. I also closed the one alternative reading
the child's method leaves open (a noise-twin hidden by the 10,000-vertex
noise cap): the uncovered vertex's nearest relative delta to ANY decoded
rep's points is 2.153e-05, above the committed 1e-5 tolerance and ~4 decades
above the stage-4b measured noise — genuinely uncovered, so
"unpinnable pool residue" is the honest class. C3 confirms the dated
correction 2 at byte level: the stage-8 "vertex sub-node" is the pool
group's own wrapper read 2 bytes shifted. Two findings, both non-blocking
docs wording in the addendum; two code observations, zero corpus incidence.
The probe re-run is byte-identical on both CSVs and the gate is green.

## Checklist results

1. **C1: the fail-closed population and its composite subset — VERIFIED.**
   Own join over `stage10-identity-export-files.csv`: 1,442 rows;
   `export_ok != 1` → **322** = 178 `missing-geometry-store` + 144
   `undecoded-variant` (318 dev + 4 held-out); exported rows with
   `vertex_count == 0`: **0** (the "exported-empty on absorption grounds"
   disjunct is vacuous, as claimed). My exhaustive walk — every block of
   stdcont/xdoclink/seebody located (the probe short-circuits like
   `export.py`; I did not) — finds located composite spans in exactly the
   child's **12** shas (11 UV + bad44bdf; single span each, all
   `stdcont#0`; set difference empty). My own `build_export` run over all
   322 reproduces the baseline classes exactly (178 + 144, 0 exports) and
   tabulates the 310 non-composite parts' failure families as **178
   missing-locator + 94 "no 01 06 vertex pool decoded" (G2 P8) + 38 "facet
   references beyond the pool" = 310, zero other** — none names an
   absorption/composition family, so "probe and exporter agree
   store-by-store" holds. F2 below names the one wording caveat.
   Probe: `probe_a_population.py` (out: `probe-a-322.csv`).
2. **C2: bad44bdf's single uncovered vertex is unpinnable — VERIFIED,
   twice.** (a) *Law path, own walkers:* my own pool parse finds 3 groups
   64,539/14,490/14,493 = 93,522 vertices / **93,518 distinct**; my own
   node scan finds 6 token nodes (c1 = 86, 86, 86, 64538, 14490, 14493);
   my own flat-law decode + the exporter's own `_decode_node_mixedwrite`
   port agree: 3 flat reps (x-asc 1.000 each) + 3 nodes failing "table: no
   walk-exact zero-block extent"; my own absorption accounting: diag
   residue == union residue == **1** (group 0; groups 1-2 fully absorbed;
   no pairing slack); refs **3/3 in-bounds** (max 62,481 < 64,538;
   11,522 < 14,490; 10,084 < 14,493), identical under both parse shapes.
   (b) *Decode-free byte census:* sliding every byte offset of the body,
   exactly **1** of 93,518 distinct 12-B pool patterns has zero
   occurrences outside the pool's own records — it occurs **exactly
   once** in the whole body, inside pool records, and it IS the measured
   uncovered vertex (35.6140556, 32.3708992, 28.3772793). Occurrence
   histogram 1×1 / 2×93,513 / 4×4 (the four 4s are the in-pool duplicate
   values, 93,522 − 93,518). Under ANY exact law implementation, a vertex
   listed nowhere but the pool is unabsorbable — the census cannot inherit
   a law artifact. (c) *Noise-twin check (closes the cap question the
   child's cap-mirroring skips):* nearest relative delta of the uncovered
   vertex to its own diagonal rep's region and to ALL reps' regions =
   **2.153e-05** > NOISE_REL 1e-5 (stage-4b measured noise ≤ 1.25e-08) —
   not a noise-cap artifact; a bigger cap would be a different law, not a
   correction. (d) *Exporter anchor:* my own `build_export` names
   "does not establish pool absorption: **1 of 93518** pool vertices are
   absent from every decoded rep region (3 law-decoded reps for 3 pool
   groups...)" — residue 1 == measured 1, as claimed. (e) The claimed
   orphan-draft fix is real and load-bearing: the draft computed pool
   spans from the absolute `g.offset` (`stage11-phaseA-orphan-probe.py:174`),
   the committed probe rebases by `body_lo`
   (`stage11_subnode_population_probe.py:186`), and on this store
   `body_lo = 213,136,251` — unrebased spans would classify every marker
   "outside the pool", flipping the conclusion. Probe:
   `probe_b_bad44bdf.py`.
3. **C3: the UV "sub-node re-listing" is the census record-set artifact —
   CONFIRMED (dated correction 2 warranted).** Own marker census over the
   11 UV stores: **3,166 `05 08 01` markers total; every one at a
   pool-record start** (0 inside a pool record's payload, 0 outside the
   pool's records); per-store totals equal the pool sizes: 12dc542e 248,
   17dca565 73, 1b0eef98 82, 219c099e 340, 38d65967 56, 58ed8b28 384,
   6c6a2e9f 396, 8e8500b1 203, a722b491 1,056, abacf110 40, e42e3805 288 —
   matching the child's 3,166 in / 0 out. The mechanism is byte-visible:
   on 12dc542e the pool wrapper is `10 24 04 ff ff 00 00 00 01 06 f8`
   followed by 248 × `05 08 01`+12-B records — read 2 bytes in, that is
   EXACTLY the stage-8 note's "vertex sub-node (`04 ff ff` + `00 00 00 01`
   + kind + count + count × `05 08 01` ...)": same bytes, shifted framing,
   count `f8` = 248 = the pool size; same on 8e8500b1 (`cb` = 203). The
   "re-lists the pool verbatim 248/248" was the pool's own canonical
   listing counted as a second route. The committed census's verdict
   column reads `unexplained` on all 11 (row-for-row with the child's
   join). The stage-8 note fix is the coordinator's (dated, per the
   brief). Probe: `probe_c_uv_census.py`.
4. **C4: the 11 UV stores decode 0 reps — VERIFIED.** My own node scan +
   the exporter's own law port decode **0 of 14** token nodes (1 each,
   except 38d65967 with 4; every failure "table: no walk-exact
   zero-block extent"), and my own `build_export` runs fail all 11 with
   the composition's "decodes none of the N token nodes" clause in the
   chained detail. Row-for-row: the child's CSV carries the same
   `token_nodes`/`decoded_reps=0`/failure strings; `mixedwrite-reps-nodes.csv`
   has exactly 14 rows for the 11, all law-empty with the same failure;
   `mixedwrite-reps-files.csv` verdict `unexplained` on all 11.
5. **Probe method soundness — VERIFIED by line-by-line read against the
   committed sources.** The route column mirrors
   `decode_composite_store`'s prelude exactly (STRIP_RE window,
   `find_list_node`, `decode_region`, `_walk_mismatch` gate — the
   exporter's own functions); the pool-record spans rebase `g.offset` by
   `body_lo` and match `pool.py`'s count-width law and 15-B stride;
   the diagonal mirrors `_decode_mixedwrite`'s precondition to the letter
   (distinct set, noise only when `len(distinct) <= 10_000`, per-group
   sum = the exporter's uncovered count); per-vertex pinnability
   (`05 08 01` position AND ≥ 1 occurrence outside pool records) is
   permissive in the right direction for a population-of-zero claim; the
   classification chain (walk-mismatch → pairing → refs → noise-cap →
   other-cause → unpinnable → candidate) can only err conservative. Two
   observations, O1/O2 below.
6. **CSV/claims/addendum consistency — VERIFIED with two wording
   findings.** 322 rows, 322 distinct shas (one row per fail-closed part;
   every fail-closed part has at most one composite span per my walk);
   split and `stage10_error_class` match `stage10-identity-export-files.csv`
   row-for-row; the 12 ⊆ the census's 93 and all fail-closed; the anchor
   CSV is the bad44bdf row, matching the full-run row; claims row
   `MW16-stage11-population` exists and its numbers match the CSV and my
   re-derivations; the addendum's headline figures all reproduce —
   except the two wording items F1/F2 below.
7. **Reproducibility — VERIFIED.** The child's committed probe re-run in
   my worktree (stdlib, `-I`): `stage11-subnode-population.csv` and the
   anchor CSV both `cmp`-IDENTICAL to the committed files; wall time
   **2.80 s** (the addendum's "~3 s" holds). Worktree clean after the
   re-runs.
8. **Gate green — VERIFIED.** Worktree-local venv
   (`python3 -m venv .venv && .venv/bin/pip install -e '.[test]'` +
   `ruff==0.17.4`), `set -o pipefail; bash scripts/check.sh` (ruff runs
   first and is fatal, then `pytest -q`): **ruff clean, 335 passed +
   7 skipped, exit 0** — matches the child's report.

## Findings

1. **F1 — non-blocking, docs. The addendum's anchor-scope sentence
   overstates.** The addendum says "the exporter anchor runs only on the
   12 composite fail-closed stores"; actually pass 2 runs only on pass-1
   candidates (`classification` in {`subnode-only-blocked-candidate`,
   `subnode-residue-unpinnable`} — `stage11_subnode_population_probe.py:595-607`),
   which is bad44bdf alone: the CSV has `exporter_error_class` filled on
   **1 of 322 rows**. The method docstring states the candidate rule
   correctly. No conclusion touches this (the 11 UV stores are
   walk-mismatch-co-blocker and the exporter's own failure for them was
   verified by MY runs instead); a dated wording fix coordinator-side.
2. **F2 — non-blocking, docs. "310 of 322 fail-closed rows carry no
   composite pool at all" is locator-relative.** My locator-free whole-file
   scan finds composite-space pool wrappers (`10 24 04 ff ff 00 00 00` +
   `01 02` edge or `ff..` trailer sub-kind) in **16 of the 178
   missing-geometry-store files** (1-11 wrapper occurrences each), in
   bytes no store locator reaches. Precise wording: "no composite pool in
   any store the exporter's locator locates". The population and ceiling
   conclusions are unaffected — those bytes reach no decode path, so a
   subnode-index law cannot act on them (they are locator-blocked
   families, part of the next-lever mass).
3. **O1 — observation, probe code, zero incidence.** In the union pass's
   budget-trip branch the `continue` skips `unc_union = still`
   (`stage11_subnode_population_probe.py:310-312`), discarding that rep's
   exact-set reduction and leaving the union residue larger than needed.
   Conservative direction only (a tripped budget flags
   `noise-cap-ambiguous` or pushes toward a co-blocker label; it cannot
   create a false candidate), and `noise_skipped_pairs == 0` on all 322
   rows at this baseline. Note for future re-runs on other baselines.
4. **O2 — observation, probe code, verified immaterial.** The refs gate
   calls `parse_strip_records(..., elements=None)` where the exporter
   passes the rep's element list. On the one store whose refs figure is
   load-bearing (bad44bdf) I ran both shapes: identical record counts and
   identical max gated refs per rep (62,481/11,522/10,084, all in-bounds).

## What the coordinator should do at merge

- Verdict MERGE: rebase `3ea96a4` over main `77deab2` (docs-only on both
  sides; this note touches only `docs/agents/stage11-review.md`), then
  ff-only merge. Do NOT push from the review branch (brief: no push).
- C3 CONFIRMED: land the dated stage-8 note correction coordinator-side
  (the "vertex sub-node re-lists the pool verbatim" clause is the census
  record-set artifact — the pool wrapper read 2 bytes shifted; the
  addendum already carries the correction, the stage-8 note itself gets
  the dated fix).
- F1/F2: dated wording fixes in the stage-11 addendum. No src/tests
  changes required; O1/O2 need no action now.
- No fitness row (analysis-only stage; none applies). Next-lever
  selection per cont. 13: the non-composite fail-closed families (310;
  the largest unexamined mass — note F2's 16 files carry unlocated
  composite pools, a locator-recovery sub-question inside that mass),
  UV element semantics (11), empty-mesh record reading (13).

## Reproduction (my own probes, outside the repo)

```
cd <worktree @ 3ea96a4> && ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus
python3 -I ~/.local/state/catpart-parser/stage11-review/probe_a_population.py <worktree>
python3 -I ~/.local/state/catpart-parser/stage11-review/probe_b_bad44bdf.py <worktree>
python3 -I ~/.local/state/catpart-parser/stage11-review/probe_c_uv_census.py <worktree>
# reproduction of the child's committed probe (byte-identical check):
python3 -I scripts/triage/stage11_subnode_population_probe.py
python3 -I scripts/triage/stage11_subnode_population_probe.py --sha16 bad44bdf
set -o pipefail; bash scripts/check.sh   # ruff clean, 335 passed + 7 skipped
```
