# Stage-3d reconciliation: `d832b86` (alt) vs `1a5c4b4` (merged) — 2026-11-11

Read-only analysis of git history + committed CSVs/scripts (no corpus, no
src/test changes, nothing merged). Labels: **fact** = read directly from the
cited commit/file/CSV; **inference** = derived from facts, reasoning shown;
**unknown** = could not be determined, why named.

Cites use `alt:` = `d832b86` (parent `249135b`) and `main:` = `1a5c4b4`
(parent `b255cb9` over `d3a574b` over `249135b`). Line numbers are in the
file at that commit (`git show <c>:<path>`). CSV figures were recomputed
by joining the two committed CSVs on `sha256` (script is inline-trivial;
no new artifact committed).

## Verdict (one line)

**Materially equivalent decoder; discard `d832b86` as a branch.** On the
672 composite stores both integrations export, vertex/triangle counts are
identical (672/672, fact). Every difference is either (i) a measurement-state
difference (3a locator recovery present in alt's CSV, absent from main's),
(ii) a stage-2c fallback main deliberately removed, or (iii) a plane gate
that 4b shows is a symptom detector for the width gap. Three small items
survive for stage 5 (section 5).

## 1. Law-by-law diff (what alt does differently)

Both implement the same stage-3b laws: P1t layout (`ceil(elem/4)` table
bytes + P1g count), U1 table shapes 0/1/2/3 = 3/0/1/2 words, LSB-first slots,
origin LCP, M2b identity refs, skip-slot loops not triangulated,
stage-3b width rank (tiling, no-repeat, no-OOB, width, k), pool absorption
required, refs-beyond-element-space fail-closed. (fact: alt `walk_layout`
:174 / main `layout` :149; alt `walk_decode_region` :220 / main
`decode_region` :202; alt rank :609-616 / main rank :347-353.) The deltas:

| # | Law / behavior | alt (`d832b86`) | main (`1a5c4b4`) |
|---|---|---|---|
| D1 | Stage-2c DP + sigma fallback | KEPT for small-form walk failures: `_decode_small_form_dp` composite.py:1003, `solve_shift_profile` :659, `decode_stream` :325, `WALK_SMALL_FORM` :82, dispatch :974-1000; big-form walk failure stays labeled | REMOVED entirely (module docstring dated note; `solve_shift_profile`, DP stream decode, ambiguity path gone) |
| D2 | Loop plane law as an EXPORT GATE | `_decode_identity` :842-870: 0x49/0x4c loops must be coplanar vs the stored normal (`WALK_PLANE_TOL`=2e-3, :91) else `undecoded-variant`; zero-normal fails closed (:842) | No gate. Docstring: "the law's validation battery, not an export gate" (multi-plane fillet/bevel). No residual check in `decode_composite_store` :436-519 |
| D3 | Walk-failure signalling | `walk_decode_region` :220 never raises; returns `walk_ok`/`failure`; overrun checked against `len(payload)` (:253); end check `pos != region_end` | `decode_region` :202 raises `ExportError` directly; extra pre-guard `write_count > 3*element_count` (:217); overrun checked against `region_end` (:234); same end check (:260) |
| D4 | Record parser | `parse_composite_facets` :532: local `re.compile` (:560), `width_law` selector keeping the stage-2c rank (:617) next to the 3b rank; 5-tuples (no width in record) | `parse_strip_records` :292: shared `STRIP_RE` (:303), single law, 6-tuples carrying `width` (the field the 4b width extension needs) |
| D5 | Curve-entry loop reporting | Reuses `WARN_UNRESOLVED_FAMILY` (alt export.py:375-385); counts `skipref_loops` over 0x42/0x49/0x4a/0x4c (:807/:826/:837), i.e. includes 0x49 loops that are never triangulated | New `WARN_CURVE_ENTRY` `curve-entry-loops-unexported` (main export.py:50, :360-369) + additive `export-summary-v1.json` enum; counts only triangulated families (main composite.py:363-431) |
| D6 | Skipped-marker accounting | Re-parses records in export.py (`_composite_skipped_markers` alt export.py:442-455) under the matching width law | Carried in decode `info["skipped_markers"]` (main composite.py:500-514); no re-parse |
| D7 | Summary `composite` block | `stage:"walk"`, `mapping:"identity"`, **`node_bytes`**, `coplanar_loops`, `skipref_loops` (alt composite.py:904-918) | `stage:"identity-table-walk"`, `loops_exported`, `loops_curve_entry`, `skipped_markers`, no `node_bytes` (main :505-519) |
| D8 | Replay/A-B harness | `scripts/triage/replay_export_seam.py`: all `kind=part` rows, per-store SIGALRM guard, **ply_sha256 + summary_sha256**, no L2 gate | `scripts/triage/ab_identity_export.py`: dev+held-out, scores the L2 gate via `_score_export`, no byte digests, no timeout guard |
| D9 | Fixtures/tests | `tests/test_composite_walk.py` (5 tests, one pins the DP fallback) + `fixtures_gen.py` +149 | `tests/test_composite_export.py` rewritten (11 tests: slanted quad, curve-entry loops, no-repeat width, walk-mismatch, unabsorbed) + `fixtures_gen.py` +410 |
| D10 | Docs | note stage-3d section (+112), claims row `EXP3d-walk-gate`, geometry.md 6.3.2 | note stage-3d section, claims +5 rows, schema doc |

## 2. The 479-vs-464 delta (fact unless marked)

Population: **same.** Both CSVs have 1,442 rows, identical `sha256` sets,
1,381 dev + 61 held-out (alt `replay-export-seam.csv`,
`ab_identity_export.py`-style manifest filter `kind=part` ⇒ same rows).

Measurement state: **different.** The two runs are not the same
measurement:

- alt CSV (replay, at `d832b86` = 3a-inclusive lineage): 854 exports =
  112 clean + 742 composite (479 big + 263 small; every composite row has
  `composite_stage=walk`, i.e. 0 stores exported through the DP fallback).
- main CSV `identity-export-files.csv`: 753 exports = 76 clean + 677
  composite. Error classes: 313 `missing-geometry-store` + 29
  `malformed-store-header`, vs alt's 178 + 0.
- Join: composite both=672, alt-only=70, main-only=5. Clean: both=76,
  alt-only=36, main-only=0.
- All 106 alt-only exports (70 composite + 36 clean) are stores main's CSV
  records as `missing-geometry-store` (66+36) or `malformed-store-header`
  (4): the stage-3a locator recovery. The alt baseline CSV (stage-2c, 249135b)
  already shows 112 clean + 61 composite exports; main's CSV shows only 34
  of those 61 baseline composites exporting.
- **Inference:** main's A/B ran on a lineage without 3a's recovery effect
  (even though `e86e046` IS an ancestor of `1a5c4b4`, `git merge-base
  --is-ancestor`, fact: commit `1a5c4b4` is dated after `249135b`).
  Corroboration: the handoff says the later fitness row measured 734 =
  686 + 36 recovery-clean + recovered composites. **Unknown:** exactly why
  the committed CSV lacks recovery despite the ancestry (likely generated
  pre-rebase then rebased without re-run); the branch reflog is not
  available to me.
- Big-form arithmetic: `479 = 459 (common) + 20 (alt-only, 19
  missing-geometry-store + 1 malformed-store-header; locator recovery) `;
  `464 = 459 + 5`. The 5 main-only stores (02ee1544, 41cde56a, 8672275d,
  a34acec5, cf7394ee) are all rejected by alt's plane gate (residuals
  0.35-82.2 on 0x49/0x4c loops, alt CSV error_detail; fact). Main's
  `big 464` is its commit-message decode count (fact) and equals
  459+5 (inference: all five are big-form; node_bytes absent from main's
  CSV so form is not directly checkable).
- **Net: +15 = +20 (3a recovery, not an alt decode improvement) − 5
  (alt plane-gate rejections).** Alt's decoder yields no big-form gain over
  main on the common population; the "deeper" appearance is the locator.
- Small form: alt 263 vs main 213 = +50, all alt-only (locator recovery);
  both=213 (fact).
- The 5 main-only: 4 fail L2 on main (3 not-manifold, 1 empty-mesh), 1
  passes (8672275d, 1,821 v / 183 t; fact, main CSV). Net L2 cost of alt's
  gate: −1 pass on this population. Three of the five (02ee1544, 41cde56a,
  a34acec5) are in stage-4b's `not-manifold-files.csv` as `width-rank
  artifact`, `v2_manifold=1` after the width re-test (fact, fceaa5e CSV):
  the plane gate fires on records the width gap misread.

Replay-vs-stage-2c baseline (alt only): of 61 baseline composite exports,
61 still export under alt; 54 keep (vertex, triangle) counts, 45 keep PLY
bytes (fact; matches alt's commit message "45 identical / 16 law-corrected").
Main's CSV: only 34 of the 61 export (pre-recovery) and 28 of those 34
keep counts (fact). "All 34 stage-2c exports preserved" in `1a5c4b4`
therefore means export success, not byte/count identity (fact, joined).

## 3. Classification of each delta

| Delta | Class | Reason |
|---|---|---|
| D1 DP/sigma fallback | **(c) equivalent in outcome; keep REMOVED** | 0/742 alt composite exports used it (CSV `composite_stage`); main removed on purpose (stage-2c artifact). Its only live role was keeping stage-2c fixtures alive, which main rebuilt under the table law. |
| D2 plane export gate | **(b) superseded by 4b** | Fires on width-gap misreads (3 of 5 victims are 4b `width-rank artifact` stores). The plane law's validated role is the width tiebreak (4b R11), not an export gate. Also premise weakened by `b255cb9`/F3: loop-battery share re-measured 0.957 < 0.98 bar, M2b battery clause relabeled candidate; alt was built on `249135b`, before F3. Costs 1 L2 pass. |
| D3 walk signalling | **(c)** | Same accept set (end check `pos == region_end`); only error text and which bound raises first differ (inference from reading both walks; confirmed by identical v/t on 672 common). |
| D4 record parser | **(c)** for the law; main's 6-tuple with `width` is the better 4b base | Rank identical. `STRIP_RE` shared. |
| D5 warning | **(c); main better** | alt overloads `unresolved-facet-family` and overcounts 0x49; no schema edit needed on alt side but semantically muddy. |
| D6 skipped markers | **(c); main better** | No re-parse. |
| D7 `node_bytes` in summary | **(a) small fold-in** | Lets big/small be derived from CSVs. Main's CSV cannot split its 464/213 by form (above). **Unknown:** whether `export-summary-v1.json` allows it (the schema file mentions no `node_bytes` property in either tree; needs an additive property, same pattern as main's warning enum). |
| D8 replay harness | **(a) fold-in** | The stage-5 gate "610/734 passes must be preserved" needs byte-identity digests (ply/summary sha256) and a timeout guard that `ab_identity_export.py` lacks. |
| D9 tests | **(c)** | Main covers a superset; alt's walk-count-mismatch test ≈ main `test_composite_walk_mismatch_stays_undecoded`; the DP-fallback test is obsolete with D1. |
| D10 docs | **(a) partial** | Carry the "16 law-corrected / 45 PLY-identical" replay finding (above) as a dated statement; do not merge alt's prose (it states D1/D2 as shipped). |

Stage-4b laws (not in alt): per-rep decomposition and u24be/plane-tiebreak
widths are **absent from both** integrations (fact: alt width loop
`for width in (1,2)` :582, main :322; pool absorption is single-rep in
both: alt `_decode_identity` :796-800 / main :472). Alt has no head start
there; its 168 `unabsorbed` rows (CSV, includes 3a-recovered stores) vs
main's 92+55 are the same multi-rep family.

## 4. Semantic conflict map (wholesale merge of `d832b86` onto current main)

Dry-run `git merge-tree --write-tree main d832b86` (read-only; objects only,
worktree untouched): **6 content conflicts** — `composite.py`, `export.py`,
`tests/fixtures_gen.py`, `docs/evidence/2026-11-10-node-streams.md`,
`docs/evidence/data/node-streams-claims.csv`, `docs/format/geometry.md`
(fact). Beyond textual conflicts, semantic clashes:

1. **Resurrects removed code** (D1): reintroduces `solve_shift_profile`
   (sigma CSP) and the DP stream decode that `1a5c4b4` removed and dated;
   re-opens the sigma-explosion exposure for small-form walk failures
   (alt's own 0.07 s claim for 05208403 is on the walk path only).
2. **Re-adds the plane export gate** (D2): −5 composite exports on the A/B
   population, incl. 3 stores 4b repairs and 1 current L2 pass; contradicts
   the post-F3 "battery, not gate" wording in main's docstring.
3. **Two width laws coexist** (`width_law` selector, D4): collides with the
   4b width extension (u24be, plane tiebreak, `width` in record tuples),
   which must edit exactly the function alt forked.
4. **Summary/schema divergence** (D5/D7): alt's `info["mapping"]`,
   `skipref_loops`, `coplanar_loops` keys vs main's `loops_curve_entry`,
   `skipped_markers`; `export.py` branches on `info["mapping"]` (alt :346)
   which main never sets; main's schema enum + tests would not match.
5. **Test suite**: alt's `test_stage2c_fixture_takes_the_dp_fallback` and
   stage-2c fixtures fail under main's fixtures_gen rebuild.
6. **Evidence docs**: two dated stage-3d sections with different shipped
   claims (DP fallback / plane gate vs removed / no gate); claims row
   `EXP3d-walk-gate` contradicts main's rows; `geometry.md` 6.3.2 flag.
7. **Measurement lineage**: alt's replay CSVs (3a-inclusive) and main's
   identity CSV (pre-recovery) are not comparable (section 2); merging both
   would leave two stage-3d numbers for the same code.

## 5. Recommendation

**Discard `d832b86` as a merge candidate; fold in three small things at
stage 5** (the stage-5 integration should start from `main` + 4b):

1. `scripts/triage/replay_export_seam.py` — cherry-pick as a new file
   (no overlap with `ab_identity_export.py`); point its baseline at the
   current main export CSV; use it for the 4b-law A/B on the passing
   exports (PLY/summary digests are what "preserve the 610/734 passes"
   needs). Adapt: the summary hash will change whenever `info` keys change,
   so hash the PLY and the L2-relevant fields separately.
2. `composite.decode_composite_store` info block + `export-summary-v1.json`
   — add `node_bytes` (additive property). One line each.
3. Evidence: a dated sentence in the stage-3d note that `1a5c4b4`'s
   "34 stage-2c exports preserved" is export-success only (28/34 keep
   vertex/triangle counts; alt measured 45/61 PLY-identical, 54/61 count-
   identical) — source: both CSVs above.

Do **not** carry: DP/sigma fallback, the plane export gate, `width_law`
selector, alt's warning reuse, alt's tests. Stage-5 composite.py work
stays: `parse_strip_records` (:292) gains width 3 + plane tiebreak and
`decode_composite_store` (:436) gains per-rep absorption, per 4b
(`fceaa5e`: `scripts/triage/unabsorbed_pool_law.py`,
`not_manifold_audit.py` `parse_width_test` :206).

**Before stage 5 (not mine to do, named):** regenerate main's A/B CSV on a
3a-inclusive tree so the stage-5 baseline is the true post-3a state
(expected from this analysis: composite ≈ 677 + 70 locator-recovered = 747
exports, inference, unverified); without that, any stage-5 delta is
confounded by the 106 locator-recovery stores exactly as 479-vs-464 was.

## Not determined

- Why `identity-export-files.csv` lacks 3a recovery while `1a5c4b4` has
  `e86e046` as an ancestor (CSV staleness vs rebase order; no reflog/corpus).
- Form (big/small) of main's 677 exports individually (no `node_bytes`).
- Whether `node_bytes` is already schema-legal (grep of the v1 schema in the
  current tree found no such property; additive edit assumed).
