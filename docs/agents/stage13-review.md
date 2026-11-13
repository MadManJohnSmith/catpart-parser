# Stage-13 pre-merge review: the element space beyond the pool + the second-chance route (2026-11-13)

Reviewer: stage-13 review sub-agent. Under review:
`t3/element-space-beyond-pool` @ `9c5bad8` (5 commits off main
`eed27a9`: the live-baseline membership re-derivation, the
element-space finding + census CSVs + claims SE1-SE12, the
second-chance route implementation, the declared A/B, the observed A/B
wrap-up). Main moved during the review: `6841959` (the cont. 18 handoff
amendment, docs-only — 53 insertions to
`docs/agents/handoff-2026-11-11.md`, nothing else; verified from the
commit), merge-base still `eed27a9` — the coordinator rebases at merge
per the brief. Worktree note: the harness had parked this worktree's
`review` branch at `eed27a9` (main, zero stage-13 commits); reset to
`9c5bad8` — the branch the note lands on is `9c5bad8` + this commit.

Method per convention: every headline claim re-derived with my OWN
walkers — my own replication of `export._export_data`'s probe order
(own orchestration of the committed `store.locate_store` law) + the
exporter anchor `build_export` as the black box, run at the BASELINE
commit `eed27a9` (detached worktree, its own venv — the membership
census is an eed27a9-semantics measurement; the Phase B tree would show
the routed stores as exported, the probe's own cross-check), my own
token-node census with my own P1g/P1t layout reader (absolute byte
positions, committed `decode_region` as the law under test), my own
pool-wrapper/VREC-record census with my own record-span arithmetic, my
own correction-2 artifact test on the carriers' re-list claim, my own
row-level diff of the committed A/B CSVs, and my own three mutations
(applied to a clean tree, reverted after each, `git status` clean
before and after). The committed geometry modules
(`store`/`pool`/`facets`/`composite`/`export`) and the committed gate
(`fitness.runner._score_export`) served as infrastructure (the
stage-10/11/12 reviews' precedent); the child's probe functions were
never imported — the committed probe was re-run as a black box at the
Phase-A commit for the byte-identical check. My probes and artifacts
live outside the repo (`~/.local/state/catpart-parser/stage13-review/`;
`probe_c1_membership.py`, `probe_c2_refs_beyond.py`,
`probe_c3_nopool.py` + the JSON outputs); corpus read-only via the
gitignored `corpus` symlink; no binaries committed.

Labels: **fact** = measured/cited (file:line or command); **inference**
= derived, reasoning shown.

## Verdict: MERGE

All six briefed claims verify independently, and the decisive measured
ones verify at every level I could reach: the live 310-row partition
reproduces from my own walk + anchor at `eed27a9` with my walk/anchor
agreeing on **310/310** rows and 0 factual mismatches against the
child's membership CSV row-for-row; the refs-beyond law reproduces on
**all 38** (32/38 + 477abcad decode through the committed law, c1 vs
max_ref 24 eq / 14 gt / **0 lt**, every ref in-bounds, pool absorbed
exact-f32, second-pool-form 0/38 with my own wrapper census); the
no-pool collapse reproduces on **all 131** (128 zero facet records
under the clean path's own scan, the 38/90 split with the 8 named
wireframes nested inside the 90, the 3 carriers exporting and PASSING
through the real seam) and the correction-2 artifact check the brief
asked for PASSES on all three carriers (the counted `05 08 01` record
sets are byte-disjoint from the decoded point regions, all re-listed
values exact f32 at distinct region indices, no pool wrapper anywhere);
Phase B's route is correct and fail-closed (the two named raises are
the only fire points, marker stores still route first, the composite
decode is byte-unchanged apart from the additive flag, my three
mutations go red exactly as the contract requires), the
declared-vs-observed table reproduces from the committed CSVs to the
row (exactly 41, all 1,019 baseline pass rows byte-identical, commit
order impl → declared → observed verified), the dated correction lands
honestly (53 < 141; stage-12 artifacts byte-untouched on the branch),
and the gate is green (349 + 7). Three findings, all non-blocking docs
items in the note (one REQUIRES a dated coordinator fix: the b86baae6
anchor prose carries five byte-position errors — the substance and the
committed CSVs are right, the prose alone is wrong); four observations,
zero blocking incidence.

## Checklist results

1. **C1: the live membership partition — VERIFIED.** Population: my
   join over the committed stage-12 A/B (`stage12-identity-export-
   files.csv`): 1,442 rows, `export_ok != 1` → **310**. My own walk +
   the `eed27a9` anchor partition them **131 no-pool + 38 refs-beyond
   + 125 missing-locator + 16 composite = 310, zero other** (my
   span-level prediction agrees with the anchor family on 310/310;
   the 16 composites are the 12 stage-11 composites + the 4 recovered
   416d14fd/434d4bb4/4902c650/c6eaac5e). Row-for-row vs the child's
   `stage13-membership.csv`: **0 factual mismatches** on family/split/
   container/tail_law — the only diffs are presentational (the child
   labels the composite family `composite-failclosed` where my tally
   says `composite`, and leaves container/tail_law blank on those 16
   rows where my walk fills them; the values agree where filled).
   Delta vs the stage-12 census (a stage-10-baseline artifact): among
   the 298 shared shas **exactly 41 changed family — 37
   missing-locator → no-pool + 4 missing-locator → composite (the
   named four)**, plus the expected set asymmetries (12 live-only =
   the stage-11 composite set, 12 census-only = the 12 now-passing
   locator recoveries) — all three sets verified shas-and-families.
   Probe: `probe_c1_membership.py`.
2. **C2: the refs-beyond law on all 38 — VERIFIED.** My own node
   census + my own layout reader (committed `decode_region` as the
   law under test): **38/38 carry a token-bearing list node**; the
   largest node's point region decodes **32/38 on the exporter window
   and 33/38 on the full body** — the 33rd is 477abcad, whose window
   payload ends at the first STRIP_RE match (write count 53,722
   overruns the truncated window at 205,503 B; the full body decodes
   27,264 points, walk-exact — the stage-8 truncation artifact, as
   claimed). **c1 vs max_ref: eq (max_ref+1) 24, gt 14, LT 0** — 0/38
   reference outside the declared space; **every facet ref < c1 on
   38/38**; **c1 > pool size on 38/38** (pool 4-168 vertices, declared
   10-27,707). Pool absorbed exact-f32 into the region on 30/33
   decoded, partial on 03c67888 (4/8), 996fc82b (4/6), fcc76b63 (4/6)
   — the per-rep composition's stores, as claimed. The 5 raises
   byte-match the claimed signatures (086b9dd9 non-finite; 531350af +
   c3d79133 walk-exceeds; a60156f7 consumed 188 of 268; c5b31a94
   walk-exceeds at element 0). **The stage-12 negative claim re-verifies
   0/38**: my own FULL_WRAP census (78 occurrences, per-store equal to
   the child's census on all 38) finds no `01 06` wrapper the
   committed pool law does not establish; the 3 stores with outside-
   pool `05 08 01` records (03c67888 8 occurrences, 0c889913 /
   4ce00502 6 each) carry unwrapped vertex records beside pool spans —
   named, not a pool form (see O1 for the run-split convention).
   Anchor b86baae6ec9412ba: node at body+467, payload 893 B
   (magic-to-magic), token at payload+29, c1=40/c2=38, **40 points =
   the tessellated cylinder** (20 per z-level at z=0/5, r=2.5 plus
   on-axis points), pool absorbed 4/4 exact f32, rec0 0x42 with 38
   refs walking (z=0, z=5) pairs 19/19, the `00 00` group at body+1351
   with count 0x62=98 followed by a node record — **the substance
   verifies; the prose byte offsets do not (F1)**.
3. **C3: the no-pool collapse on all 131 — VERIFIED.** The clean
   path's own facet scan (my runs): **128/131 carry ZERO facet
   records** (max_ref −1), **125/131 zero STRIP_RE candidates**; the
   only 3 with facet records are the carriers 66049cf3 / bf350820 /
   fac22ea3 — **so the stage-12 IF-solved grant of +94 (+37 recovered)
   collapses to +3 measured**. My decomposition: **38/131 carry no
   token node; 90/131 largest-node layout failures (c1 ∈ {84, 86} on
   ALL 90; the committed `decode_region` raises on each)**; the **8
   named wireframe stores** (1968ce85, 4e8feabe, 65564a9b, 853788c3,
   9fa8cb5a, a15e5740, be3ff691, e1cef8ab) all sit INSIDE the 90 and
   all carry the wireframe signature (unwrapped `05 08 01` vertex
   tables of 10-16 records, 100% finite, single-z; 8 inline `03 02 01`
   edge records whose 27 B = header + 24 B of two xyz triples that
   repeat the vertex table's values — measured byte-exact on
   4e8feabe; 0 facet headers). Anchor spot-checks: 61765d51 (635 B
   body, 2 nodes, `ff 03 01 00 00 ff` sub-records, 0 facet
   candidates), 45bee87f (265,054 B body, **19 node spans covering
   264,961 B — exact**, largest token node 97 B, no facet headers,
   runs of u32le 12: 14,728 `0c 00 00 00` occurrences incl.
   back-to-back runs — see O2 on the 1.59 figure). **The 3 carriers
   export and PASS at the REAL seam** (my `build_export` runs on the
   landed tree: 44v/88t, 236v/118t, 1,592v/1,100t, stage
   identity-table-walk, pool_group_count 0; c1 vs max_ref eq / eq /
   +27 with the +27 = the 271 skips' slack). **The correction-2
   artifact check PASSES on all three**: no pool wrapper anywhere in
   the body; the counted unwrapped VREC runs (16 / 4 / 32 records)
   are byte-DISJOINT from the decoded point regions; every record's
   12-B payload equals a decoded region point EXACT f32; the matches
   hit 16 / 4 / 32 DISTINCT region indices — the counted record set
   is NOT the region being re-listed (the S9-census-artifact trap the
   brief flagged is genuinely absent here). **The 37 recovered bodies
   are the same family: 11 no-node + 26 layout failures, 0 facet
   records, 0 unwrapped runs ≥ 3** (SE10 exact); **none of the 3
   carriers is a recovered body**; the stage-6 raw-array signature is
   absent 0/131 (my own stride-12 scan with the committed nice/asc
   predicates).
4. **C4: Phase B code review — VERIFIED.** (a) *Fire points*: the
   second chance is called from exactly two sites — the no-pool raise
   (`export.py:262-274`) and the refs-beyond raise (`export.py:287-
   300`); marker stores still route first (`export.py:253-260`); the
   P7 vertices-only export is downstream of the refs gate and
   unaffected; no other raise routes. (b) *Fail-closed*: `_unrouted_
   element_space` re-raises the ORIGINAL error object (`raise original
   from None`) on any composite ExportError. (c) *Composite decode
   byte-unchanged*: the branch diff on `composite.py` is exactly two
   hunks (the `allow_unrouted_elements=False` parameter + the
   docstring; the marker-check condition
   `composite.py:771`); `grep allow_unrouted_elements src/` shows the
   flag ONLY in that condition and its threading — it skips ONLY the
   marker check, nothing else; `export.py`'s other behavior is
   untouched (the two raise sites become route calls with
   identically-constructed ExportError objects). (d) *Schema*: no
   schema file in the branch diff (additive-only claim holds — nothing
   changed). (e) *Tests/fixtures*: 2 valid + 2 corrupted fixture
   variants; 6 tests, both directions (2 positives, 1 precedence pin,
   3 fail-closed negatives), green unmutated. **Mutation verification
   (mine, each on a clean tree, reverted after):** dropping the no-pool
   route → `test_no_pool_routes_to_composite` RED (1 failed, 5
   passed); dropping the refs-beyond route →
   `test_refs_beyond_routes_to_composite` RED; re-raising the
   composite error instead of the original → ALL THREE fail-closed
   negatives RED (`test_refs_beyond_without_node_keeps_original_
   error`, `test_no_node_keeps_no_pool_error`,
   `test_walk_failing_node_keeps_no_pool_error`) — the
   row-identity contract is genuinely pinned by the tests. (f)
   O3 below notes the `except ExportError` scope; zero corpus
   incidence.
5. **C5: declared-vs-observed — VERIFIED.** Commit order (all
   2026-11-13 -06:00): impl `c1b5194` 14:19:13 → **declared `5eaf762`
   14:21:03** → **observed `9c5bad8` 14:23:22** — the declaration
   precedes the observed run's commit (checkout mtimes are fresh, so
   commit order is the corroboration; the stage-12 precedent). My
   row-level diff of the committed CSVs (`stage12-identity-export-
   files.csv` vs `stage13-identity-export-files.csv`): 1,442 rows,
   same shas in the same order; **exactly 41 rows differ**, all dev —
   **37** `undecoded-variant` → exported + `pass` and **4** →
   exported + `fail` (`empty-mesh`: 1467e3df/77168b28 26,401
   vertices, 9ed8c3e1 212, b9f61739 310 — 0 triangles each,
   vertices-only), every other row byte-identical; **all 1,019
   baseline pass rows byte-identical** (0 lost exports, 0 lost
   passes); exports **1,132 → 1,173**; L2 pass rows 1,019 → 1,056;
   dev L2 **964 → 1,001 / 1,381 = 72.48% (+37)**; held-out **55**
   steady; dev error classes `undecoded-variant` 181 → 140,
   `missing-geometry-store` 125 unchanged. Stage mix **table-walk x32
   / per-rep x3 (03c67888, 996fc82b, fcc76b63) / mixedwrite-reps x6
   (086b9dd9, 477abcad, 531350af, a60156f7, c3d79133, c5b31a94)** —
   the named rescue list, exact; the 37 pass names = 34 refs-beyond +
   the 3 carriers, matching my C2/C3 decode populations row-for-row.
   All D1-D6 declarations reproduce from the committed artifacts.
6. **C6: the dated correction — VERIFIED, honestly landed.** The
   arithmetic: **12 + 3 + 38 = 53 < 141** (the no-pool grant 94+37 is
   byte-refuted by my C3 measurement — 128/131 with zero facet
   records; the refs-beyond +38 stays hypothetical and is separately
   replaced by the measured +37 in the A/B). The correction lives in
   the stage-13 note section 5 (dated 2026-11-13) + claims rows
   SE11/SE12; **the stage-12 artifacts are byte-untouched on the
   branch** (`git diff main..HEAD` empty on
   `2026-11-13-noncomposite-census.md`, `stage12-noncomposite-census.csv`,
   `stage12-unlocated-wrappers.csv`, `2026-11-12-mixedwrite-reps.md`,
   `stage12-identity-export-files.csv`) — corrections dated, originals
   intact, no retro-massaging (the B1 precedent's rule holds).
7. **Reproducibility — VERIFIED.** The child's committed probe re-run
   by me at the Phase-A commit `93f3a85` (detached worktree, corpus
   symlinked, that tree's own venv — src == eed27a9 there since Phase
   A is analysis-only): `stage13-membership.csv`,
   `stage13-elementspace-census.csv`, `stage13-decode-probe.csv` all
   **cmp-IDENTICAL** to the committed files; the probe's own delta
   tally (37 missing-locator → no-pool, 4 → composite, 94/38
   identical) matches mine. The committed CSVs are unchanged between
   `93f3a85` and `9c5bad8` (git diff empty).
8. **Gate green — VERIFIED.** Worktree-local venv, `set -o pipefail;
   bash scripts/check.sh`: **ruff clean, 349 passed + 7 skipped,
   exit 0** — matches the child's report.

## Findings

1. **F1 — non-blocking for the merge, REQUIRES a dated coordinator fix
   (docs, prose only): the note's section-2 anchor prose carries five
   byte-position errors on b86baae6, and the same wrong-frame recurs on
   the 66049cf3 anchor and in one range claim.** The prose numbers vs
   my byte-level read (payload-relative, the committed layout law):
   - 2-bit table: claimed `payload[35,45)` — measured **`payload[40,50)`**;
   - write count: claimed **136** — measured **80** (136 = 0x88 is a
     table byte read at the mis-shifted count position; the claimed
     layout is self-inconsistent — 136 > 3×40 — the committed
     `decode_region` would raise its write-count budget check, so the
     child's own committed CSV rows (largest_points 40, skips 0; the
     decode probe's 40v/40t L2-pass on both windows) cannot have come
     from it; the probe used the correct layout, only the prose is
     wrong);
   - region: claimed `payload[46,590)` — measured **`[51,371)`**
     (walk-exact, my reader and `decode_region`'s walk end agree);
   - pool slots: claimed **7/8/32/36** — measured **0/1/36/37** (first
     region-index hits under the committed region order, exact f32);
     note: the handoff cont. 18 (on main, not this branch) repeats the
     7/8/32/36 figure — correct it there too when rebasing;
   - "facet rec0 (marker 0x42, 38 refs) ... max ref 39": rec0's max
     ref is **37**; the 39 comes from **rec1 (0x4a, 6 refs)** — the
     store's max_ref 39 is right, its attribution to rec0 is not.
   The same wrong write-count/region frame recurs on the 66049cf3
   anchor (claimed write count 136, region `payload[47,591)` —
   measured **88** / **`[52,404)`**; the c1=44/c2=32, payload 2,224 B
   claims are right). Also: "declared 10-27,264" — the census's own
   c1_of_largest max is **27,707** (1467e3df/77168b28, the 578,544-B
   nodes; 27,264 is 477abcad's), and "the `00 00` x30" distribution —
   the census's own wrap_subkinds column says **x26** (my census
   agrees; totals 78 = 78 per-store on all 38). The SUBSTANCE of every
   anchor claim verifies (node positions, token, counts, the cylinder,
   the absorption, the side-walk pairs, the `00 00` group + count 98 +
   nested node record, the carriers' structure), and the headline law
   claims rest on the committed CSVs, which are correct — the fix is a
   dated prose correction to the note's sections 2-3 (the stage-12
   F1/F2 precedent; no decision changes).
2. **F2 — non-blocking, docs precision: the no-pool decomposition
   prose overstates the template's coverage and presents nested counts
   as a partition.** (a) "90/131 largest-node layout failures: the
   payload is a 70-97 B template" — the largest-node payload is 67-97 B
   on **72/90**; the other 18 carry largest nodes of 286-608 B
   (2×286, 5×296, 2×300, 8×564, 1×608) that ALSO fail the layout with
   the same c1 ∈ {84,86} signature; body-wide, the template's
   direction-cosine floats appear on 69/90 and the `14 04 ff...`
   records on 77/90 (the `00 62` tail on 90/90). The byte-exact
   template itself verifies on the named pair (05fe6c23's 94-B payload
   = 45bee87f's first 94 bytes; the 97-B variant adds 3 trailing
   zeros). (b) The note's bullets read as 38 + 90 + 8 = 136 > 131:
   the 8 wireframe stores are a SUBSET of the 90 (verified nested) —
   one clarifying sentence fixes the arithmetic. The decisive numbers
   (90 failures, c1s, 0 facet records, 0 raw signature) all verify.
3. **O1 — observation, review method.** The run-split display for the
   3 stores with outside-pool `05 08 01` records differs by
   convention: the note says runs "1;1;1;6" / "1;1;4"; my
   contiguous-record chains measure "2;6" / "2;4" (two records exactly
   15 B apart form one chain at the byte level). Totals are identical
   (occurrences 16/10/10, outside-pool 8/6/6) and the claim's
   substance (extra vertex records, not a pool form) is unaffected.
4. **O2 — observation, docs figure.** The 45bee87f bulk entropy "1.59
   bits/byte" is model-dependent: my byte-level entropy of the big
   non-token span (262,395 B) is 4.62; the u32 word-value entropy is
   5.48 bits/word = 1.37 bits/byte-equivalent. The substance
   ("structured, not compressed, not vertices": back-to-back runs of
   u32le 12, 1,872 distinct word values with the top 3 covering 63.8%)
   verifies; the specific figure I could not reproduce under either
   model. Optional: state the model next to the number.
5. **O3 — observation, code, zero corpus incidence.**
   `_unrouted_element_space` catches only `ExportError`; a
   non-ExportError escaping the composite decode on a never-before-
   routed body would crash the run rather than fail-closed. The
   corpus A/B (1,442 rows, exit 0) shows zero incidence, and the
   committed decode raises ExportError on every pinned failure class.
   Note for future baselines only.
6. **O4 — observation, positive.** The probe's BASELINE SCOPE note
   (anchor runs on the Phase B tree show the routed stores as
   exported) is exactly what my baseline-worktree setup avoids; the
   committed membership CSV is an eed27a9-semantics artifact and my
   independent walk reproduces it there.

## What the coordinator should do at merge

- Verdict MERGE: rebase `9c5bad8` over main `6841959` (docs-only on
  main's side; this note touches only `docs/agents/stage13-review.md`),
  then ff-only merge. Do NOT push from the review branch (brief: no
  push).
- F1: land the dated prose correction coordinator-side — the note's
  section 2 (b86baae6 anchor: table [40,50), write count 80, region
  [51,371), pool slots 0/1/36/37, rec0 max 37 with max_ref 39 from
  rec1; the declared range 10-27,707; the `00 00` x26), section 3
  (66049cf3: write count 88, region [52,404)), and the handoff cont.
  18's 7/8/32/36 mention when rebasing. No CSV changes; no decision
  changes.
- F2: dated precision fix in the note's section 3 (the 72/90 + 18
  larger-variant scoping; the wireframe-8-inside-the-90 nesting).
- O1-O4: no action required.
- The +37 is a src change with a measured A/B: the fitness row runs
  coordinator-side after merge per convention (dev 1,001 projected =
  72.48%; held-out 55/61).
- Next-lever framing after merge: the collapse cuts the hypothetical
  ceiling to 53 < 141 (verified); the measured +37 lands dev at
  1,001/1,381 — 104 flips remain behind the empty-mesh (79),
  not-manifold (32), composite (16) and carrier (3) families, per the
  handoff's grind note.

## Reproduction (my own probes, outside the repo)

```
cd <worktree @ 9c5bad8> && ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus
python3 -m venv .venv && .venv/bin/pip install -e '.[test]' -e '.[lint]'

# baseline worktree for the eed27a9-semantics anchor (my C1):
git worktree add --detach ~/.local/state/catpart-parser/stage13-review/baseline-eed27a9 eed27a9
ln -s /home/alan/Documents/Repos/catpart-parser/corpus \
  ~/.local/state/catpart-parser/stage13-review/baseline-eed27a9/corpus
python3 -m venv ~/.local/state/catpart-parser/stage13-review/baseline-eed27a9/.venv
~/.local/state/catpart-parser/stage13-review/baseline-eed27a9/.venv/bin/pip install -q -e .

cd ~/.local/state/catpart-parser/stage13-review
<review-worktree>/.venv/bin/python -I probe_c1_membership.py \
  ~/.local/state/catpart-parser/stage13-review/baseline-eed27a9 <review-worktree>
#   -> 310 = 131 + 38 + 125 + 16, walk/anchor agree 310/310,
#      0 factual mismatches vs stage13-membership.csv, delta 41 (+12/12 sets)
<review-worktree>/.venv/bin/python -I probe_c2_refs_beyond.py <review-worktree>
#   -> 32/38 window + 33/38 full decodes, eq24/gt14/LT0, refs<c1 38/38,
#      absorb 30 exact + 3 partial, 5 raises named, second-pool 0/38
<review-worktree>/.venv/bin/python -I probe_c3_nopool.py <review-worktree>
#   -> 128 zero-facet (38 no-node + 90 layout-fail, 8 wireframe inside),
#      carriers export+pass at the real seam, correction-2 artifact check
#      PASS (disjoint + distinct + exact), recovered-37 = 11+26, raw 0/131

# reproduction of the child's committed probe at the Phase-A commit:
git worktree add --detach ~/.local/state/catpart-parser/stage13-review/phasea-93f3a85 93f3a85
ln -s /home/alan/Documents/Repos/catpart-parser/corpus \
  ~/.local/state/catpart-parser/stage13-review/phasea-93f3a85/corpus
~/.local/state/catpart-parser/stage13-review/phasea-93f3a85/.venv/bin/python -I \
  ~/.local/state/catpart-parser/stage13-review/phasea-93f3a85/scripts/triage/stage13_elementspace_probe.py
#   -> all three CSVs cmp-IDENTICAL to the committed files

# mutations (each on a clean tree, `git checkout -- src/catpart/geometry/export.py` after):
#   M1 restore the no-pool raise            -> test_no_pool_routes_to_composite RED
#   M2 restore the refs-beyond raise        -> test_refs_beyond_routes_to_composite RED
#   M3 `raise` the composite error, not the original -> 3 fail-closed negatives RED
set -o pipefail; bash scripts/check.sh   # ruff clean, 349 passed + 7 skipped
```
