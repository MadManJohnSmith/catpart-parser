# Stage-12 pre-merge review: the non-composite census + the other-container probe (2026-11-13)

Reviewer: stage-12 review sub-agent. Under review:
`t3/stage12-noncomposite-failclosed-census` @ `dd77a58` (6 commits off
main `e1cba4f`: Phase A census + CSVs + claims, Phase B implementation,
the declared A/B, the composite-path provenance fix, the observed A/B +
claims row SC9, the wrap-up). Main has moved since (`c46a359`, the
cont. 15 handoff amendment) — verified docs-only (81 insertions to
`docs/agents/handoff-2026-11-11.md`, nothing else), the coordinator
rebases at merge. Worktree note: the harness had parked this worktree's
`review` branch at `c0f495c` (main + cont. 14, zero stage-12 commits);
reset to `dd77a58` — the branch the note lands on is `dd77a58` + this
commit.

Method per convention: every headline claim re-derived with my OWN
walkers — my own span walk replicating `export._export_data`'s probe
order over all 322 fail-closed parts (exhaustive, no short-circuit),
my own baseline-semantics anchor (my loop over the committed
`locate_store`/`_export_store` WITHOUT the stage-12 other-container
family = the stage-10 seam), my own every-block locate extension with
each recovered span decoded through the committed `_export_store` and
scored by the committed gate (`fitness.runner._score_export` — the
gate authority, not a replica), my own locator-free whole-file wrapper
census with sub-kind classification and region attribution, my own
token-node/NODE_MAGIC/STRIP_RE body counts, and my own row-level diff
of the two committed A/B CSVs. The committed geometry modules
(`store`/`pool`/`facets`/`composite`/`export`) served as
infrastructure (the stage-10/11 reviews' precedent); the child's probe
functions were never imported — it was re-run as a black box at the
baseline commit for the byte-identical check. My probes and artifacts
live outside the repo (`~/.local/state/catpart-parser/stage12-review/`;
probe: `probe_a_taxonomy.py`, output `review-a-partition.json`); corpus
read-only via the gitignored `corpus` symlink; no binaries committed.
Mutations were applied to a clean tree and reverted (`git status`
clean before and after).

Labels: **fact** = measured/cited (file:line or command); **inference**
= derived, reasoning shown.

## Verdict: MERGE

All six briefed claims verify independently, and the decisive measured
ones verify at every level I could reach: the 310-row taxonomy
reproduces from my own walk + anchor with **0 mismatches** on every
decisive census column row-for-row (and my wrapper-row multiset equals
the committed 177 rows exactly); the missing-locator byte census
reproduces at 125 / 121 / 53 with my own header scans and every-block
probes; the +12 passes reproduce through the committed decode + the
committed gate with the same 12 shas, stages, and container/tail
attributions; the 16 F2 files all locate with exactly one recovered
span each and 12/16 pass, wrappers byte-checked inside the recovered
bodies. Phase B's code is correct and fail-closed (precedence
statically and corpus-verified; the provenance helper emits on BOTH
decode paths; my two mutations go red exactly as the child claimed),
the declared-vs-observed table reproduces from the committed CSVs to
the row (exactly 53, error_class the only changed field on all 41,
0 lost), and the gate is green (343 + 7). Two findings, both
non-blocking docs items in the note (one an arithmetic correction to
the hypothetical ceiling bound — the decision it supports survives the
correction; one a wording slip on "72 composite wrappers"); two
observations, zero corpus incidence.

## Checklist results

1. **C1: the 310-row taxonomy — VERIFIED.** Own join over
   `stage10-identity-export-files.csv`: 1,442 rows, `export_ok != 1` →
   **322** (178 `missing-geometry-store` + 144 `undecoded-variant`;
   318 dev + 4 held-out). My span walk finds located composite spans on
   exactly **12** shas — set-equal to the stage-11 composite set (11 UV
   + bad44bdf; prefix-compared; no other) — leaving **310**. My own
   baseline-semantics anchor over the 310 partitions them **178
   missing-locator + 94 no-pool + 38 refs-beyond = 310, zero other**
   (my family counts match the child's note and its census CSV family
   column row-for-row: 0 mismatches on all 310 rows; sha-set diff
   empty; `split`/`stage10_error_class` match the baseline CSV on all
   310). My independent body counts also reproduce the child's
   located-row columns row-for-row (0 mismatches across `container`,
   `span_ordinal`, `tail_law`, `strip_candidates`, `node_magic_hits`,
   `token_nodes`, `pool_groups`, `pool_vertices`, `max_ref` on the 132
   located rows) and the family aggregates (no-pool: 89/94 zero strip
   candidates, 94/94 NODE_MAGIC hits, 67/94 token-bearing, 76/94
   wrapper-less, 12/94 with `05 08 01` records; refs-beyond: max ref ≥
   own pool on 38/38, 37 single + 1 double pool group).
   Probe: `probe_a_taxonomy.py`.
2. **C2: the missing-locator byte census — VERIFIED.** My own scans
   over the 178: **125 carry no `V5_CFV2\0` hit outside offset 0**
   (the outer magic), **121 of them carry `CATIA_V5 CB0001` catalogs
   that validate as neither store form** (my every-block probe recovers
   nothing on each, with CB0001 present); **53 carry a full-signature
   header** (`ff`×8 / zeros×8 at [origin+16, +32)) in blocks the
   three named families never visit — and my own `locate_store` probed
   on **every** block validates exactly one recovered span on **53/53**
   parts (53 spans total; `probe_malformed` = **0**). Container
   attribution reproduces stage-1 C11 exactly:
   **CATBRepModeContainer 39 / CameraStartupContainer 8 / contmeasure
   2 / CATMaterialCont, CATCameraContainer, CATElecBehaviourCont,
   CATSiFiContShuttle 1 each**; tails **padded 39 / shipped 12 /
   overshoot 2**. Through the real decode path (my runs, committed
   gate): **12 spans export and PASS** — the same 12 shas as the
   child's case table (56080410, 82acf24b, 8f1bb5e3, b2e43013,
   636b13f6, 8ecd197d, d67512e6, a5cb3096, b0de68d8, bb335cff,
   c2a5696e, e3963960), stages **identity-table-walk ×10 /
   identity-per-rep ×1 (636b13f6, 34v/32t) / identity-mixedwrite-reps
   ×1 (d67512e6, 64v/62t)**; the other **41 recovered spans fail**
   closed (37 with the no-pool clause, 4 composite-flavored: 2
   "table walk exceeds the declared region", 1 "does not re-list the
   pool: 82 of 86" on 4902c650, 1 non-finite raw coordinate on
   c6eaac5e — the note's four, verbatim).
3. **C3: the 16 F2 stores — VERIFIED.** My locator-free whole-file
   wrapper census (`10 24 04 ff ff 00 00 00` + sub-kind) finds
   composite-space wrappers in exactly **16** of the 178 files; **all
   16 are among the 53 recovered, each with EXACTLY ONE recovered
   span**; my wrapper-row multiset equals the committed
   `stage12-unlocated-wrappers.csv` exactly (177 rows, 0 diff on
   sha+offset+sub-kind+occurrence-index). **All 72 wrapper occurrences
   on the 16 files sit inside the recovered span's body** (my own
   region test; 31 of the 72 are composite-space — see F2's wording
   caveat). **12 of the 16 export+pass** through the committed
   composite decode; **4 stay composite-fail-closed** (416d14fd,
   434d4bb4, 4902c650, c6eaac5e — the named four).
4. **C4: Phase B code review — VERIFIED.** (a) *Precedence*: the
   other-container family is nested inside
   `if not located and first_error is None` INSIDE the stage-3a guard,
   after the stdcont loop (`export.py:128` phase guard, the family at
   `export.py:158-188`, the final raise at `export.py:190`): it fires
   only when
   stdcont located nothing and raised nothing AND xdoclink/seebody
   located nothing and raised nothing. Corpus-scale corroboration: all
   1,120 baseline exports row-identical in the observed A/B (any
   preemption would have shifted a row). The order-sensitive pin
   (`test_located_stdcont_store_wins_unchanged` asserts no
   `store_recovery` on a real-stdcont export) covers the ordering
   behaviorally. (b) *Fail-closed*: an other-container header that
   fails both tail families raises the shipped
   `malformed-store-header` (first_error → re-raised; the bad-tail
   fixture pins it; corpus incidence 0 — my probe_malformed = 0 on all
   178); a part nothing recovers keeps `missing-geometry-store`
   (125/125 unchanged in the A/B). (c) *The shared-helper fix*: the
   mid-run bug (provenance emitted on the clean path only) is real and
   the fix is correct on BOTH paths — `_store_recovery_record` is
   families: `_export_store` (clean, `export.py:385`) and
   `_export_composite_store` (composite, `export.py:515-519`); my seam
   spot-checks:
   d67512e6 → `{other-container, shipped, CATBRepModeContainer}`,
   56080410 → `..., CameraStartupContainer` (the child's claimed
   re-verification reproduces exactly); 416d14fd's error detail
   carries `[store recovered via the other-container
   (CATBRepModeContainer) probe, shipped tail law]`. **Mutation
   verification (mine):** dropping the composite-path emission turns
   `test_recovered_composite_summary_carries_provenance` RED
   (KeyError `store_recovery`, 7 stay green); dropping
   `container_name` from the helper turns both provenance pins RED.
   The child's third mutation claim (probe-before-stdcont →
   precedence red) I did not reproduce with an equivalent edit — my
   reformulation was a no-op while the loop order stands — see O2; the
   static guard + corpus row-identity carry the property. (d) *Schema*:
   additive only (enum value + optional `container_name`;
   `additionalProperties: true` unchanged; v1 preserved). (e) *Tests*:
   8 new tests, both directions (4 positive/provenance, 1 gating pin,
   1 precedence pin, 2 fail-closed negatives) + the L1
   clean-parse cross-check; 6 new fixture variants; mutation-red
   verified for the two I ran.
5. **C5: declared-vs-observed — VERIFIED.** Commit order (all
   2026-11-13 -06:00): impl `8b167c6` 11:40:57 → **declared `5b3faf5`
   11:41:52** → fix `77e8629` 11:45:59 → **observed `2ed4965`
   11:46:23** → wrap-up `dd77a58` 11:48:31 — the declaration precedes
   the observed run's commit, with the mid-run fix between them (the
   found-and-fixed story's shape). (The stage-10 precedent's mtime
   corroboration is not available in a fresh checkout — checkout
   stamps mtimes — so commit order is the corroboration here; it is
   unambiguous.) My row-level diff of the committed CSVs
   (`stage10-identity-export-files.csv` vs
   `stage12-identity-export-files.csv`): 1,442 rows, same sha sets in
   the same order; **exactly 53 rows differ** — **12**
   `missing-geometry-store` → exported + `pass` (the same 12 names as
   my C2 walk; stages table-walk ×10 / per-rep / mixedwrite-reps;
   manifold True, `failed_check` "" on all 12), **41** →
   `undecoded-variant` with **error_class the ONLY changed field on
   every one**, 0 other rows touched; **0 lost exports, 0 lost
   passes** (all 1,007 baseline pass rows byte-identical); exports
   **1,120 → 1,132**; dev L2 **952 → 964**; held-out **55/55**
   steady; `missing-geometry-store` 178 → 125. All six declarations
   (D1-D6) reproduce from the committed artifacts.
6. **C6: the ceiling arithmetic — VERIFIED as stated, with one
   arithmetic finding (F1).** The stated sum: 12 + 94 + 38 = **144 <
   153** — reproduces from MY partition (same three numbers). The
   frame arithmetic reproduces: dev failure mass **429** = 318 dev
   fail-closed (310 + 8) + **79** dev empty-mesh exports + **32** dev
   not-manifold exports (my recount from the baseline CSV's
   `failed_check`); 952 + 429 = 1,381; after the +12: 964/1,381 =
   **69.80%**, 1,105 − 964 = **141** remain. The double-counting
   caution reproduces from the committed CSVs + the stage-7 note's
   named 14 (17930bab, 17dca565, 1b0eef98, 219c099e, 38d65967,
   58ed8b28, 6c6a2e9f, 802a6207, 86205bfb, 8e8500b1, a722b491,
   abacf110, ccbb7862, e42e3805): the UV 11 (MW11's list) = the
   12dc542e anchor + **exactly the 10 pair-variant members** (overlap
   10/10); the **4 others export at the baseline** — 17930bab,
   802a6207, 86205bfb `pass`, ccbb7862 exported empty-mesh
   (triangle_count 0) — as claimed; stage-9's named 13 all still dev
   empty-mesh at the stage-10 baseline (my check: 13/13). F1 below
   corrects the hypothetical bound the note derives from this
   arithmetic.
7. **Reproducibility + the two incidents — VERIFIED.** The child's
   committed probe, re-run by me at the **baseline commit `42132fc`**
   (detached temp worktree, corpus symlinked, my worktree's venv):
   `stage12-noncomposite-census.csv` and
   `stage12-unlocated-wrappers.csv` both **cmp-IDENTICAL** to the
   committed files. `git diff 42132fc dd77a58` on both CSVs: **0
   lines** — the wrap-up's "restored byte-identical" claim holds at
   git level, and the anchor-clobber incident's fix is in the code
   (anchor runs write `*-anchor.csv`, `main()`'s output-name branch —
   verified by reading it). No stage-12 guard/raise merge artifact
   survived: the branch diff on `src/` + `tests/` carries exactly the
   probe family, the provenance helper, the schema addition, the
   fixtures and the tests — no duplicated families, no debug
   leftovers (grep clean), no second missing-geometry raise; the
   claims CSV carries SC1-SC9 with numbers matching my re-derivations.
8. **Gate green — VERIFIED.** Worktree-local venv
   (`python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
   -e '.[lint]'`), `set -o pipefail; bash scripts/check.sh`:
   **ruff clean, 343 passed + 7 skipped, exit 0** — matches the
   child's report.

## Findings

1. **F1 — non-blocking for the merge, REQUIRES a dated coordinator fix
   (arithmetic, docs). The note's hypothetical bound undercounts its
   own cap-raisers: 144 is not the 100%-yield upper bound; the honest
   bound is 181, which REACHES the bar.** The note's grind answer 2 and
   claims row SC8 grant the two unpinned content laws at 100% yield
   over their named families (94 no-pool + 38 refs-beyond) but omit
   the **37 locator-recovered no-pool bodies** — which the note's own
   section 2 calls "cap-raisers for the content levers". Under the
   note's own granting rules (the extension landed, both laws solved
   at 100%), the consistent IF-solved sum is **12 + 94 + 37 + 38 =
   181 ≥ 153** (185 if the 4 recovered composite stores are granted
   too). So "the non-composite mass CANNOT carry the bar even
   hypothetically" does not follow as written: hypothetically it can,
   barely, but ONLY via two laws no committed evidence pins, both at
   100% yield, AND with the extension landed. The decision the
   paragraph supports is unaffected — the only MEASURED pinnable lever
   is +12 (verified), no committed evidence pins either content law,
   and the close-sequence conversation remains due — but the ceiling
   table's IF-solved column (the missing-locator row's "+12; the 41
   need the content levers below" delegating mass that the content
   rows then never count) and SC8 need the dated correction (the B1
   `+12 → +18` precedent). Suggested honest wording: "measured
   pinnable ceiling +12; under 100%-yield hypotheticals on BOTH
   unpinned laws the mass reaches 181 ≥ 153 — with zero committed
   evidence for either law and no partial credit below 100% measured
   anywhere in their families; the close-sequence conversation is
   due."
2. **F2 — non-blocking, docs wording. "Every one of their 72 composite
   wrappers sits INSIDE the recovered span's body" mislabels the
   count.** The 72 counts ALL `FULL_WRAP` occurrences on the 16 files;
   **31 are composite-space** (`01 02` edge / `ff ..` opener — my
   census: 2+3+11+1+3+1×11), the other 41 are pool `01 06` / other
   sub-kinds. The byte substance holds and I verified it with my own
   region test: **all 31 composite AND all 72 total sit inside the
   recovered spans' bodies**. Same slip in claims row SC4 ("all 72
   composite wrappers inside recovered bodies"). Fix: "all 72 wrapper
   occurrences (31 of them composite-space) sit inside the recovered
   span's body". The F2 answer itself (16/16 located, 12/16 pass) is
   unaffected.
3. **O1 — observation, code, zero corpus incidence.**
   `NAMED_PROBE_CONTAINERS` matches block names exactly; a valid block
   whose doc-type name merely varies from a named family's (case or
   spacing variant) is probed under the `other-container` family with
   its own name in the provenance. Same law, fail-closed, and the
   corpus attribution shows only genuine others — note for future
   baselines only.
4. **O2 — observation, review method.** The child's third claimed
   mutation ("probe before stdcont → precedence red") was not
   independently reproduced by me: my equivalent edit (widening the
   others list to include stdcont blocks) is a no-op while the loop
   order stands. The precedence property is instead established
   statically (guard nesting, checklist 4a) and corpus-wide (checklist
   4a), and the pin test's assertion is order-sensitive by
   construction; no doubt is cast on the child's claim.

## What the coordinator should do at merge

- Verdict MERGE: rebase `dd77a58` over main `c46a359` (docs-only on
  both sides; this note touches only
  `docs/agents/stage12-review.md`), then ff-only merge. Do NOT push
  from the review branch (brief: no push).
- F1: land the dated ceiling correction coordinator-side — note
  section 5 (grind answer 2 + the IF-solved column's semantics),
  claims row SC8, and the handoff's grind arithmetic if restated.
  Cont. 15's "the bar unreachable with measured levers" is accurate
  as written and needs no fix.
- F2: dated wording fix in the note's F2 answer + SC4 row.
- The +12 is a src change with a measured A/B: the fitness row runs
  coordinator-side after merge per convention (dev 964 projected =
  69.80%; held-out 55/61).
- O1/O2: no action.
- The close-sequence conversation with the owner proceeds per the
  note, with F1's corrected hypothetical framing.

## Reproduction (my own probes, outside the repo)

```
cd <worktree @ dd77a58> && ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus
python3 -m venv .venv && .venv/bin/pip install -e '.[test]' -e '.[lint]'
.venv/bin/python -I ~/.local/state/catpart-parser/stage12-review/probe_a_taxonomy.py <worktree>
#   -> family partition 178/94/38, the 12 pass shas, the 53/121/125
#      census, the 16 F2 files, 0 row-for-row mismatches
# reproduction of the child's committed probe at the BASELINE commit:
git worktree add --detach ~/.local/state/catpart-parser/stage12-review/baseline-42132fc 42132fc
ln -s /home/alan/Documents/Repos/catpart-parser/corpus \
  ~/.local/state/catpart-parser/stage12-review/baseline-42132fc/corpus
.venv/bin/python -I \
  ~/.local/state/catpart-parser/stage12-review/baseline-42132fc/scripts/triage/stage12_noncomposite_census_probe.py
cmp ~/.local/state/catpart-parser/stage12-review/baseline-42132fc/docs/evidence/data/stage12-noncomposite-census.csv \
    docs/evidence/data/stage12-noncomposite-census.csv          # identical
cmp ~/.local/state/catpart-parser/stage12-review/baseline-42132fc/docs/evidence/data/stage12-unlocated-wrappers.csv \
    docs/evidence/data/stage12-unlocated-wrappers.csv           # identical
# mutations (each on a clean tree, revert after):
#   drop composite-path emission -> test_recovered_composite_summary_carries_provenance RED
#   drop container_name in _store_recovery_record -> both provenance pins RED
set -o pipefail; bash scripts/check.sh   # ruff clean, 343 passed + 7 skipped
```
