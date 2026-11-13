# Stage-14 pre-merge review: the empty-mesh / not-manifold mechanism census + the ceiling (2026-11-13)

Reviewer: stage-14 review sub-agent. Under review:
`t3/empty-mesh-not-manifold` @ `15ba3a8` (1 commit off main `a3edbab`,
parent verified `a3edbab`; the child's branch head is `15ba3a8` in the
shared repo). Main may have moved docs-only — the coordinator rebases
at merge. Worktree note: the harness had parked this worktree's
`t3/stage14-pre-merge-review` branch at `a3edbab` (main, zero stage-14
commits); reset to `15ba3a8` — the branch the note lands on is
`15ba3a8` + this commit.

Method per convention: every headline claim re-derived with my OWN
walkers — my own observe-only capture wrappers on the committed
composite decode calls (`composite._triangulate`,
`composite.parse_strip_records`), my own span enumeration replicating
`export._export_data`'s probe order, my own per-loop census with
triangle-to-(record, marker, loop) attribution re-implemented from
`composite._loop_triangles`/`parse_strip_records` as read at
`15ba3a8`, my own body-wide `01 4x ff` candidate scan with my own
record-law check (u32le n bound, width/k tiling), my own edge census
with my own plane-normal coplanarity test (SIGN-INSENSITIVE — this
matters, see F2), my own dup-pin-ALL ceiling implementation, my own
unordered-triple dedup ceiling, and my own corpus-wide fire-condition
counter over the A/B CSV. `build_export` served as the exporter black
box; the committed gate order (`fitness.runner._score_export`) and
`mesh.mesh_stats` as infrastructure (the stage-10/11/12/13 reviews'
precedent). The child's probe functions were NEVER imported — the
committed probe was re-run as a black box at `15ba3a8` for the
byte-identical check. My probes and artifacts live outside the repo
(`~/.local/state/catpart-parser/stage14-review/`; `probe_stage14_review.py`,
`own-census.json`, `stage14-live-ab.csv`, `child-rerun/`, `scope.json`);
corpus read-only via the gitignored `corpus` symlink; `python3 -I`
throughout; no binaries committed; `src/` untouched (verified by diff
and by `git status` before and after every run).

Labels: **fact** = measured here (command or file:line); **inference**
= derived, reasoning shown.

## Verdict: MERGE

All six briefed claims verify independently at every level I could
reach: the live full-A/B re-run at `15ba3a8` is **byte-identical** to
the accepted stage-13 CSV (`cmp`; dev 1,116 exports / 1,001 L2 pass =
72.48%, held-out 55/61) and partitions **117 exported-but-failing rows
= 84 empty-mesh (83 dev + 1 held-out `1b1ae784`) + 33 not-manifold
(32 dev + 1 held-out `d4127e6b`)**, row-for-row identical to
`stage14-export-failures-census.csv` on every measured column (0
factual mismatches on facet_records, loops_total/written/skip_ref,
strip_candidates, territory overlap, degenerate causes, vertex/triangle
counts, containers; the only diffs are the 14 mechanism labels F2
below); the empty-mesh taxonomy reproduces **55 + 26 + 3** (my own
body-wide candidate scan: 42 zero-candidate stores, 12 all-decline
verified candidate-by-candidate incl. the named anchors' exact n
values, PLUS one store the child's claim misses — F3; 26/26
loops_total == loops_skip with ALL 26 carrying MIXED dropped loops —
213/226 — stronger than the note states; the two loop anchors
byte-exact; 25 normal-less + `3dff4d93` nonplanar declines, 0
unpinnable); the not-manifold census reproduces **0/89 repeated-ref
over-edges, 0 territory overlap, distinct triangles throughout, dedup
solves exactly `1d256d12` at the ordered-triple level** — but my own
sign-insensitive plane test and my own unordered-triple dedup find TWO
material corrections (F1: the duplicated-content family is 8 stores,
not 1 — 7 more full-gate flips, measured; F2: 14 stores' "fins" are
exact-opposite-normal coplanar overlaps) — the corrected store
taxonomy is **15 content-fins + 10 coplanar-overlap + 8
duplicate-triangles** and the corrected measured dev ceiling is **32,
not 25** (still < 104; the grind answer stands); C4's dup-pin-ALL
verifies end-to-end with my own implementation (25/26 = 24 dev +
`1b1ae784`, `3dff4d93` stays not-manifold, pinned tris 32-3,456 sum
14,761, 0 degenerate among passes, 26/26 rows agree with the child's
ceiling CSV, fire condition = exactly 26 rows corpus-wide, fire points
and whole-store gates verified in the committed code, nothing
implemented in src/); C5 verifies (probe re-run cmp-IDENTICAL x3 into
a scratch dir, no src/ change vs main, stage-13/stage-9 artifacts
byte-untouched, corrections dated with originals intact); C6 verifies
with one prose correction (the "+ 3 carriers" in the remaining-mass
enumeration is stale — all 3 export and PASS today; the mass is 269 =
128 + 16 + 125). The gate is green (349 + 7). Six findings, all
NON-BLOCKING (three require dated coordinator fixes — F1/F2/F3 — none
touch src/, none change the verdict-relevant conclusions: the bar is
NOT reachable through these families under either ceiling figure, and
the dup-pin-ALL overturn decision correctly stays with the
coordinator/owner). F1 additionally REOPENS one Phase-B input: the
unordered-dedup mechanism has 8 stores (>= 2) and a pinnable law, so
the child's "no >= 2-store pinnable mechanism besides the ruled-
conservative dup-pin" holds only at the ordered-triple reading — the
coordinator should weigh the dedup law (7 measured dev flips) alongside
the dup-pin-ALL report.

## Checklist results

1. **C1: the live populations — VERIFIED.** My own full-A/B re-run at
   `15ba3a8` (src/ byte-identical to `a3edbab`, verified by `git diff
   main 15ba3a8 -- src/` empty) → `cmp` **byte-identical** to the
   committed `stage13-identity-export-files.csv` (1,442 rows; dev
   1,001/1,381 = 72.48%, held-out 55/61). The 117 family rows
   partition **84 empty-mesh (83 dev + 1 held-out `1b1ae784`) + 33
   not-manifold (32 dev + 1 held-out `d4127e6b`)** — set-identical to
   the child's census rows; stage mix **empty-mesh 46 table-walk + 13
   raw-array + 13 mixedwrite + 12 per-rep; not-manifold 8 + 19 + 6**
   — exactly as the note's section 1. My per-row counters agree
   117/117 on every measured column (see the mismatch count in C2/C3).
2. **C2: the empty-mesh taxonomy on all 84 — VERIFIED (one store
   corrected, F3).** My own mechanism classification over my own
   captures: **55 no-facet-records + 26 u4-curve-entry-all-loops + 3
   records-without-loops**, 84/84 agreeing with the child's census
   except nothing (the 14 label diffs are all in the not-manifold
   family). My own body-wide `01 [41-4f] . ff` scan over the winning
   span bodies: **42/55 carry ZERO candidates; 13 carry candidates**
   (counts 1-20, e.g. `086a4eff` 20 in-body / 36 whole-file per the
   note's different scope). The 12 all-decline stores verified
   candidate-by-candidate with my own record law — decline reasons
   match the note: `2039ff97` 2x 0x4f with n = 1,795,373,314 /
   3,523,265,280 (byte-exact), `2c5d2542` 0x41 no-tiling (n=3),
   `85ceb131` 4x 0x41 no-tiling, `a9a564cd`/`c3973a6f` 2x 0x47
   no-tiling each, `086a4eff` 20x n-junk (1.7e9-4.0e9) — EXCEPT
   `839552c2`, whose single candidate is a **parseable 0x4c record**
   (F3). The 26 u4 stores: **loops_total == loops_skip 26/26** (sum
   226, not SF5's 247 — F6); **the dropped loops are MIXED on 26/26
   stores — 213 of 226 loops reference both skip slots and written
   elements** (13 loops all-skip); anchors byte-exact: `1467e3df`
   record at absolute 696,888, 0x42, NO normal, width 2, loop0 n=138,
   refs [24, 27164], **70/138 skip-referencing** (68 written);
   `b9f61739` record at 133,640, loop0 n=6, refs [241, 311],
   **3/6 skip-referencing** (the store carries 21 more dropped loops,
   all mixed, incl. one normal-carrying 0x4c — the note's anchor
   quotes check exactly). E0-b declines re-derived: **25 normal-less +
   1 nonplanar (`3dff4d93`, both loops normal-carrying, 1 nonplanar
   under the pin), 0 unpinnable**; the 4 fired E0-b stores
   (`2fca9bc4`/`4ad53b87`/`4ae0392d`/`505bbe1f`) all export and PASS
   today, absent from the family as claimed. The 3 records-without-
   loops: `cf7394ee` **118x 0x49**, `f21255ac` **7x 0x49**,
   `ccbb7862` **1x 0x44** — the 0x49 law n == 3*type holds on
   **118/118** (n=3, type=1 on every record; counts partitions
   (3,) x105 / (2,1) x3 / (1,2) x10 — exactly the note's split).
   The MIXED-loop stage-13 wording correction is DATED (stage-14 note
   section 5, 2026-11-13) with the originals intact
   (`2026-11-13-stage13-elementspace.md` line 139 unchanged; the child
   commit touches none of the existing notes — verified by `git diff
   a3edbab 15ba3a8 -- docs/`: only the 5 new stage-14 files).
3. **C3: the not-manifold taxonomy on all 33 — VERIFIED with two
   corrections (F1, F2).** My own edge census: **89 over-edges
   total**, use histogram agreeing row-for-row (max 37 on `13bb5c0c`
   — the 37x edge is (0,56); `44e63faa` edge (0,1) used 3x by 3
   distinct triangles from records 27,620,068 + 27,630,319 with plane
   normals (0.98, 0.00, 0.199) / (-0.995, -0.078, 0.062) /
   (-0.998, -0.055, -0.021) — the note's three named sheets,
   byte-exact; `97a0a420` edge (3,4) used 13x by 13 distinct triangles
   from 13 different 0x42 records EXACTLY 3,233 B apart, all loop1,
   plane normals exactly (1,0,0) — a real coplanar book; `1d256d12`
   4 duplicate ordered triples, each from two DIFFERENT 0x4a records,
   offset pairs **1,018,583/1,019,204 and 1,018,558/1,019,179 (621 B
   apart)**, 6 reps — byte-exact as the note). Causes: **0/89 from
   repeated-ref loops** (my repeat-edge count matches the child's on
   33/33), **0 territory overlap** (33/33), duplicate-coordinate
   vertices on 8 stores creating boundary edges — all confirmed.
   Corrections: (a) the child's fin/coplanar test is winding-sign-
   sensitive — on 16 stores it labels over-edges "fins" whose incident
   triangle normals are EXACT OPPOSITES (same plane, opposite
   winding): 14 single-over-edge stores flip wholesale, `13bb5c0c`
   splits 10 fin + 5 coplanar (of 15), `2d59ff19` 12 + 1 (F2);
   (b) unordered-triple dedup (F1) solves 7 more stores. Corrected
   store taxonomy: **15 content-fins + 10 coplanar-overlap + 8
   duplicate-triangles** (of which `b912cbef` stays failing on
   pre-existing degenerate skips). The content-vs-artifact inference
   stands: every over-edge joins distinct triangles from distinct
   records/loops with 0 repeated-ref and 0 double-parse.
4. **C4: the dup-pin-ALL STOP-and-report — VERIFIED, decision
   correctly left to coordinator/owner.** Code: the committed fire
   points are exactly `composite._triangulate`'s `if not triangles and
   dropped` (composite.py:691) and the per-rep whole-store gates
   `if not triangles and reps_dup_pin ...` (composite.py:1098,
   :1764, guarded by the "fire only when the WHOLE store's mesh is
   empty" comment) — the relaxation can only touch stores whose
   whole-store primary mesh is empty. My own corpus-wide counter over
   the A/B (committed AND my live re-run): **fire condition
   (exported ∧ triangle_count == 0 ∧ loops_curve_entry >= 1) = exactly
   26 rows (25 dev + 1 held-out `1b1ae784`)**; the other 58 empty-mesh
   rows have no dropped loops; no pass row and no not-manifold row has
   an empty primary mesh → **zero-regression by construction
   CONFIRMED** (a fired store can only move fail → fail-differently or
   fail → pass). My own dup-pin-ALL measurement (my own weld +
   triangle emission + my own gate replication in committed order):
   **25/26 pass (24 dev + `1b1ae784`), `3dff4d93` stays not-manifold
   (pinned 3 tris, 1 degenerate skipped), pinned tris 32-3,456 sum
   14,761, 0 pinned degenerates among the passes, 0 unpinnable** —
   row-for-row identical to `stage14-dup-pin-ceiling.csv` on all 26
   rows (pinned_tris, gate, normal_less, nonplanar, unpinnable: 0
   mismatches). NOT implemented in src (diff empty) — the review only
   verifies the report, as briefed.
5. **C5: probe reproduction + no retro-massaging — VERIFIED.** The
   committed probe re-run at `15ba3a8` into a scratch out-dir: all
   three CSVs **cmp-IDENTICAL** to the committed files
   (`stage14-export-failures-census.csv`,
   `stage14-dup-pin-ceiling.csv`, `stage14-notmanifold-mechanism.csv`).
   `git diff main 15ba3a8 -- src/` **empty**; the child commit adds
   exactly 6 new files (the note, 4 CSVs, the probe) and touches NO
   existing note — stage-13/stage-9 artifacts byte-untouched; the two
   corrections are dated in the stage-14 note with the original
   wordings intact.
6. **C6: the grind arithmetic — VERIFIED (one prose correction, F5).**
   Measured dev ceiling: the child's 25 (24 + 1) reproduces; my
   corrected figure is **32 dev (24 dup-pin-ALL + 8 unordered dedup,
   of which b912cbef fails the gate → 7 dedup flips + 1d256d12; total
   24 + 8 = 32; +1 held-out)** — **32 < 104 either way; the bar is NOT
   reachable through these families under BOTH figures.** Bar
   arithmetic: 1,105 − 1,001 = 104 confirmed live (dev pass 1,001 in
   my re-run). Remaining unpinned mass after this stage, measured
   live: fail-closed **269 = 144 undecoded-variant (128 no-facet
   no-pool + 16 composite) + 125 missing-geometry-store** (265 dev +
   4 held-out) — the note's 128/125/16 are right; the enumeration's
   **"+ 3 carriers" is stale** (all three export and PASS today:
   `66049cf3`, `bf350820`, `fac22ea3`, l2 pass, triangle counts
   88/118/1,100) and 128+125+16+3 = 272 ≠ 269. The stage-13 landing
   arithmetic closes exactly: 310 fail-closed at stage-12 semantics −
   41 flipped = 269.

## Findings

Classification: all six findings are NON-BLOCKING (the stage is
analysis-only, no src change, no A/B; every verdict-relevant
conclusion stands under the corrected numbers). F1-F3 require DATED
coordinator fixes (the stage-13 F1/F2 precedent); F4-F6 are
prose/figure corrections.

- **F1 (non-blocking, dated fix REQUIRED; changes the ceiling table
  and reopens one Phase-B input): the duplicate-triangle family is 8
  stores, not 1 — the child's dup detector only sees ORDERED index
  triples.** My own unordered-triple census finds 8 stores whose
  over-use resolves after dropping duplicates of the same three
  ELEMENT INDICES written in a different order (geometrically the
  same facet listed twice, opposite winding — the plane normals are
  exact opposites): 6 record PAIRS 13-42 B apart in the same rep
  (`25aeb5a0` 6003327/6003340 = 13 B, 2 groups; `2d59ff19`
  800963/801005 = 42 B, 13 groups; `396a9d79` 1111915/1111932 = 17 B;
  `4a21610f` 723333/723346 = 13 B; `e1eed721` 748547/748560 = 13 B;
  `f4a5df2a` 5748710/5748723 = 13 B) and 2 single-record cases
  (`b912cbef` record 1851771 loop 8 re-walking the same triangle
  forward+backward; `ef61cfc2` record 4747854 loops 0 and 1) —
  duplicated WRITER content, territory overlap 0 on all 8, exactly the
  `1d256d12` mechanism (whose 4 ordered dup triples and 621 B pairs I
  confirm byte-exact). **Measured ceiling (my own gate replication in
  the committed order): dedup → 8/9 manifold, 7 pass the FULL gate
  including degenerate (`b912cbef` keeps 3 pre-existing degenerate
  skips → fails degenerate-triangles); 1d256d12 passes.** Corrected
  measured dev ceiling **24 + 8 = 32** (the note's 25 undercounts by
  the 7). Zero-regression by construction holds for dedup too (a
  passing store's manifold check can only improve: removal never
  creates over-use; degenerate counts unchanged) — but a landing needs
  the full declared-vs-observed discipline, same as any law.
  **Phase-B consequence:** the dispatch's Phase-B gate (>= 2 stores,
  law pinnable from committed evidence + measured bytes, not already
  ruled conservative) is MET for the unordered-dedup law — the child's
  "below the >= 2 gate" held only at the ordered reading. This is a
  coordinator/owner decision exactly like the dup-pin-ALL report; the
  grind answer is unaffected (32 < 104).
- **F2 (non-blocking, dated fix REQUIRED): the fin/coplanar edge
  classifier is winding-sign-sensitive.** `stage14_export_failure_
  probe.py` adds raw normalized cross products to a set; a triangle
  pair with EXACT-opposite normals (same plane, opposite winding)
  counts as two distinct "sheets". Measured on my own sign-insensitive
  plane test: 14 single-over-edge stores flip wholesale from
  content-fins to coplanar-overlap (`25aeb5a0`, `2fb5b092`,
  `396a9d79`, `4a21610f`, `4a32f59c`, `4abf3eea`, `612c5e7c`,
  `6ab9e107`, `b912cbef`, `ba090026`, `bc235805`, `d31ea2c1`,
  `e1eed721`, `f4a5df2a` — each edge's incident normals are exact
  opposites to 6 decimals, e.g. `25aeb5a0` edge (29863,29864) use=4:
  (0.715930, -0.698172, 0) vs (-0.715930, 0.698172, 0)), `13bb5c0c`
  splits 10 fin + 5 coplanar of 15 edges, `2d59ff19` 12 + 1 of 13.
  Corrected taxonomy **15 content-fins + 10 coplanar-overlap + 8
  duplicate-triangles** (with F1 applied). Unaffected and confirmed:
  over-edge totals (89), use histograms, 0 repeated-ref, 0 territory
  overlap, dup extras, dedup results, boundary/oriented columns, and
  every ceiling figure — fins and coplanar overlaps are both
  distinct-triangle over-edges with no pinnable law, so the
  mechanism-attribution substance below the labels stands.
- **F3 (non-blocking, dated fix REQUIRED): SF3's "no parseable facet
  record exists in any of the 55" is false for `839552c2` — ceiling-0
  still stands there.** My own body-wide scan finds a 0x4c candidate
  at absolute 584,318 — INSIDE the winning span body [501529, 594644)
  but OUTSIDE the committed parse window [515694, 581207) (a per-rep
  store; the record lies past the last rep's territory) — that TILES:
  width u8, counts (13, 15, 12, 12) = n 52, refs in [0, 43] (in-bounds
  against the 1,387-element space), normal bytes (0, 0, 1). My own
  hypothetical export of that record (0x4c fan, my own loop
  semantics): **48 triangles, 2 degenerate skips → gate NOT-MANIFOLD**
  — the store cannot flip, so SF4's ceiling-0 conclusion stands.
  Corrections needed: the census counts (42/55 zero-candidate under
  the body scope, 13 stores with candidates, 12 all-decline + 1
  parseable-but-failing) and SF3's wording ("no parseable facet record
  INSIDE THE COMMITTED DECODE WINDOWS exists in any of the 55" would
  be true as measured). The note's "43/55 zero" and "the other 12"
  shift by exactly this store under my scope; `086a4eff`'s "36
  whole-file" vs my 20 in-body shows the note mixed scopes — name
  them in the dated fix.
- **F4 (non-blocking, prose): the dup-pin ceiling paragraph's
  "(3dff4d93, 90 tris)" contradicts the child's own CSV.** The ceiling
  CSV row says `pinned_tris=3, pinned_degenerate=1` — my measurement
  agrees (3 pinned triangles, not-manifold). The 90 is `cf7394ee`'s
  compound-probe figure (note section 2, records-without-loops) copied
  into the wrong anchor.
- **F5 (non-blocking, prose): the remaining-mass enumeration includes
  "+ 3 carriers" — they are landed, not remaining.** All three
  (`66049cf3`, `bf350820`, `fac22ea3`) export and PASS at this
  baseline (verified from the accepted A/B). The remaining unpinned
  mass is 269 = 128 no-facet no-pool + 16 composite + 125
  missing-locator (the note's own three numbers); 128+125+16+3 = 272
  ≠ 269 measured. The close-conversation arithmetic should re-open on
  269 (and on the corrected 32-vs-25 ceiling from F1).
- **F6 (non-blocking, figures): two number slips.** (a) SF5's
  "26/26 loops-total 247": the committed census and my census both sum
  **226** dropped loops on the 26 (loops_total == loops_skip_ref ==
  loops_curve_entry on every row). (b) SF13's `97a0a420` anchor says
  "ALL stored normals ~(1,0,0) agreeing with the triangle planes":
  0x42 records carry NO stored normal under the committed law
  (`NORMAL_MARKERS_ALL` excludes 0x42) and the bytes at the normal
  position read (0, 0, 0) — the (1,0,0) figures are the 13 TRIANGLE
  plane normals (which I confirm exactly); "stored normals" is the
  wrong word. Also "~3,231 B apart" is exactly 3,233 (12 gaps).

## Observations (no action)

- **O1:** the census's `crossloop_edges` column counts distinct
  (record, marker) pairs, not (record, loop) pairs — my loop-level
  reading differs on 2 rows (`cd88ae9d` 3 vs 1, `ef61cfc2` 3 vs 0);
  both stores are content-fins either way; no causal or ceiling
  consequence.
- **O2:** the mixed dropped-loop finding is STRONGER than the note
  states: ALL 26 u4 stores carry mixed loops (213 of 226 loops), not
  just the 4 stage-13 rows — this strengthens, not weakens, the dated
  stage-13 correction.
- **O3:** every other measured column of the three committed CSVs
  matches my own walkers row-for-row with 0 mismatches (117 census
  rows: facet_records, loops, candidates, degenerate causes, vertex/
  triangle counts, containers, body bytes, territory overlap; 26
  ceiling rows incl. pinned_tris and gates; 33 not-manifold rows:
  over-edge totals, histograms, repeat/crossloop causes modulo O1,
  dup extras, dedup, boundary, oriented).

## What the coordinator should do at merge

1. Land F1-F3 as dated corrections coordinator-side (note sections 2,
   3, 4, 6 + the mechanism column of `stage14-notmanifold-mechanism.csv`
   + claims rows SF3/SF5/SF10/SF13/SF15/SF16/SF17), following the
   stage-13 F1/F2 format: dated, originals intact, none massaged.
   The corrected headline: measured dev ceiling **32** (still < 104);
   taxonomy **15 + 10 + 8**; the dedup mechanism has **8 stores and a
   pinnable law** (Phase-B gate met) — present BOTH the dup-pin-ALL
   report (unchanged: 24 dev + 1 held-out, gated on overturning the
   stage-10 U4 conservative rule) and the dedup law (7 measured dev
   flips, zero-regression by construction argued, unverified at A/B
   scale) to the owner as the two open decisions.
2. Rebase over main (docs-only movement expected), ff-only merge.
3. No fitness row from this stage (analysis-only; no A/B delta) —
   per the brief and the child's note section 6.

## Reproduction (my own probes, outside the repo)

All runs in this worktree (`t3/stage14-pre-merge-review` @ `15ba3a8`),
venv `.venv`, corpus symlinked read-only, `python3 -I`:

    # C1: live A/B re-run + byte-identity (cmp)
    .venv/bin/python -I scripts/triage/ab_identity_export.py \
      --out-dir ~/.local/state/catpart-parser/stage14-review --out-name stage14-live-ab.csv
    cmp ~/.local/state/catpart-parser/stage14-review/stage14-live-ab.csv \
      docs/evidence/data/stage13-identity-export-files.csv

    # C2-C4: my own walkers (census over the 117 family rows; my own
    # capture wrappers, span walk, loop/edge census, candidate scan,
    # E0-b declines, dup-pin-ALL ceiling, dedup ceilings)
    .venv/bin/python -I ~/.local/state/catpart-parser/stage14-review/probe_stage14_review.py \
      --repo . --phase census --out ~/.local/state/catpart-parser/stage14-review/own-census.json

    # C4: the corpus-wide fire-condition counter (committed + live CSV)
    .venv/bin/python -I ~/.local/state/catpart-parser/stage14-review/probe_stage14_review.py \
      --repo . --phase scope --out ~/.local/state/catpart-parser/stage14-review/scope.json

    # C5: the child's probe as a black box into a scratch dir, then cmp x3
    .venv/bin/python -I scripts/triage/stage14_export_failure_probe.py \
      --out-dir ~/.local/state/catpart-parser/stage14-review/child-rerun
    cmp ~/.local/state/catpart-parser/stage14-review/child-rerun/stage14-export-failures-census.csv \
      docs/evidence/data/stage14-export-failures-census.csv   # (+ the other two)

    # F1: unordered dedup ceiling (my own weld/canon + my own gate)
    # F3: the 839552c2 0x4c hypothetical (48 tris, not-manifold)
    #   — ad-hoc sessions on the captured records; the JSON + this note
    #     carry the numbers

    # C5: no src change, no retro-massaging
    git diff main 15ba3a8 -- src/          # empty
    git diff a3edbab 15ba3a8 -- docs/      # only the 5 new stage-14 files

    # Gate (worktree-local venv, pipefail):
    set -o pipefail && bash scripts/check.sh   # ruff clean; 349 passed + 7 skipped

Anchor byte details quoted in this note (record offsets, loop refs,
normal values, dedup pair gaps) come from the same captures; every
number is either in `own-census.json` or reproduced by the ad-hoc
sessions archived in `~/.local/state/catpart-parser/stage14-review/`.
