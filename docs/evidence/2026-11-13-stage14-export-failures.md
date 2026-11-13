# Evidence: the empty-mesh and not-manifold export families — the mechanism census and the ceiling at the stage-13 landed baseline (stage 14, 2026-11-13)

Ticket #34 (G6, stage 14, owner direction cont. 17/19: keep grinding to
the bar): byte-level mechanism census of the two largest remaining L2
failing families — the EXPORTED rows whose gate fails `empty-mesh`
(triangles == 0) or `not-manifold` (an undirected edge used more than
twice, `mesh.mesh_stats`) — with the dispatch's question answered
byte-level: WHY does each family fail, is the failure a decode artifact
(a law we get wrong) or the content, and how many stores WOULD pass if
the mechanism were solved.  Phase B (CONDITIONAL) DID NOT RUN: the gate
is not met (section 6) — the only >= 2-store pinnable mechanism is
exactly the one the stage-10 decision deliberately ruled conservative,
which the dispatch names STOP-and-report.  The grind answer, plainly:
**the measured dev ceiling through both families is 25 flips (24 of
them gated on overturning the stage-10 U4 conservative rule) < 104 —
the bar is not reachable through these families.**

Population re-derived LIVE at main `a3edbab`: the full corpus A/B
re-run (`ab_identity_export.py`) is **byte-identical** to the accepted
stage-13 CSV (`stage13-identity-export-files.csv`, cmp) — dev 1,116
exports / 1,001 L2 pass (72.48%), held-out 57/55 — and partitions
**117 exported-but-failing rows = 84 empty-mesh (83 dev + 1 held-out
`1b1ae784`) + 33 not-manifold (32 dev + 1 held-out `d4127e6b`)**
(the dispatch's ~83 + 32 holds on the dev split).  Method:
`scripts/triage/stage14_export_failure_probe.py` (committed with this
note; the stage-13 probe's method — own span walk, the exporter anchor
`build_export` as the black box — plus module-level capture wrappers
recording every committed-decode call so the committed code runs
UNMODIFIED) and own per-loop / per-edge walkers over the captures, with
every triangle attributed to its source (record offset, marker, loop).
Per-store census: `stage14-export-failures-census.csv` (117 rows);
ceilings: `stage14-dup-pin-ceiling.csv` (26 rows) +
`stage14-notmanifold-mechanism.csv` (33 rows); claims SF1-SF17 in
`stage14-claims.csv`.  Anchor byte detail ran ad-hoc (session dir;
the committed probe carries the census — the stage-13 precedent).

Labels: **fact** = measured here and reproducible from the committed
CSVs + reproduction commands; **inference** = interpretation, reasoning
shown; **unknown** = open.

## The headline

**Both families are in-decode-classified and the decode is NOT the
problem — except in exactly one store.**  Empty-mesh splits 55 + 26 + 3
(three named mechanisms, section 2): 55 stores carry NO parseable facet
record (the stage-13 no-pool collapse pattern, now measured INSIDE the
exported population), 26 are the U4 curve-entry class (every loop drops
on the any-skip-ref rule; the stage-10 E0-b dup-pin law declined on all
26 — 25 for normal-less loops, 1 nonplanar), and 3 carry only
unpinned-marker records whose committed byte law (0x49 n == 3*type)
yields zero valid triangles even hypothetically.  Not-manifold splits
31 + 1 + 1 (section 3): 31 stores' over-edges join DISTINCT
non-coplanar triangles from distinct records (content-level folds — 0
of 89 over-edges are repeated-ref or double-parse artifacts), 1 is a
13-page coplanar book (same reading), and exactly 1 store
(1d256d12) is a genuine decode-adjacent artifact — the same three
triangles emitted by two different 0x4a records — which dedup solves.

## 1. The live memberships (fact)

- Full A/B re-run at `a3edbab` -> cmp byte-identical to the committed
  stage-13 CSV (1,442 rows; dev 1,001/1,381 = 72.48%, held-out 55/61).
  The 117 family rows re-export through `build_export` inside the probe
  with identical gate verdicts (vertex/triangle counts cross-checked
  row-for-row, 0 mismatches).
- Split by `stage`: empty-mesh = 46 identity-table-walk + 13 raw-array
  + 13 mixedwrite-reps + 12 per-rep; not-manifold = 8 table-walk + 19
  per-rep + 6 mixedwrite-reps.  All 117 spans re-located by the probe's
  own walk (0 span-not-matched).

## 2. empty-mesh — 84 stores: 55 no-facet-records + 26 U4 + 3 records-without-loops (fact)

Per-store census: `stage14-export-failures-census.csv` (mechanism
column); per-store dup-pin ceiling: `stage14-dup-pin-ceiling.csv`.

- **`no-facet-records` (55, all dev) — the collapse pattern.**  43/55
  carry ZERO `01 4x ff` (STRIP_RE) candidates in the body; the other
  12 carry 1-12 candidates (whole-file scan up to 36 on 086a4eff) that
  ALL decline the record parse — each verified individually, not
  extrapolated: the u32le n behind the marker reads 1e8-4e9 (out of the
  committed 0..1,000,000 bound; junk behind a false-positive regex hit)
  or no (width, k) parse tiles (2c5d2542 1x 0x41, 85ceb131 4x 0x41,
  a9a564cd/c3973a6f 2x 0x47 each — 0x41/0x47 are not exported markers
  anyway).  **Anchor 2039ff97** (table-walk, elem_decl 11,041): the 2
  candidates are 0x4f markers at absolute 236,028/237,038 with n =
  1,795,373,314 / 3,523,265,280.  Ceiling **0 under any vertex-source
  law** (fact by construction — there is nothing to triangulate; the
  stores export vertices-only with the `no-facet-records` warning).
- **`u4-curve-entry-all-loops` (26 = 25 dev + 1 held-out) — the E0
  class, re-derived live.**  Every facet loop of the exported markers
  (0x42/0x4a/0x4c) drops on the any-skip-ref rule (loops_total ==
  loops_skip_ref on 26/26).  **Refinement of the stage-13 wording
  (section 5): the dropped loops are MIXED** — their references split
  between skip slots (curve entries) and written elements — not
  "every loop referencing only skip slots".  **Anchor 1467e3df**
  (stdcont/shipped, body 578,883 B, elem_decl 27,707, points 26,401,
  skips 1,306): one 0x42 record at absolute 696,888, NO normal,
  width 2, loop0 n=138, refs [24, 27164], 70/138 skip-referencing.
  **Anchor b9f61739** (stdcont/shipped, elem 470/310/160): one 0x42
  record at 133,640, loop0 n=6, refs [241, 311], 3/6 skip-referencing.
  Stage-13's 4 new vertices-only rows (1467e3df, 77168b28, 9ed8c3e1,
  b9f61739) are all in this bucket, as the dispatch projected; the
  other 22 include the stage-4a E0 members (the 4 fired E0-b stores
  2fca9bc4/4ad53b87/4ae0392d/505bbe1f are NOT here — they pass, as the
  stage-10 landing measured).
  **The E0-b decline reasons (fact):** 25/26 carry at least one
  NORMAL-LESS dropped loop (untestable by the committed battery), 1/26
  is 3dff4d93 (2 dropped loops, both normal-carrying, 1 nonplanar
  under the dup pin — exactly the stage-4a analysis's own exclusion,
  re-derived live); 0 unpinnable (every referenced skip slot has a
  preceding written element to weld to).
  **The dup-pin-ALL ceiling (fact, probe-measured):** exporting every
  dropped loop under the U4-D dup law WITHOUT the E0-b battery
  (each loop-referenced skip slot welded to the written vertex of its
  immediately preceding written element, no new vertices — the law is
  already committed inside `composite._e0b_dup_pin`; the probe only
  removes the battery criterion) gives **25/26 L2 passes (24 dev + 1
  held-out)** — pinned triangles 32-3,456 (sum 14,761), 0 skipped
  degenerates among the passes — and 1 not-manifold (3dff4d93, 90
  tris).  This is a probe MEASUREMENT of the hypothetical, not a
  landing: the conservative rule stands unless overturned (section 6).
- **`records-without-loops` (3, all dev) — the unpinned-marker
  residue.**  cf7394ee (table-walk, elem 1,430/515/915) carries 118
  parsed records, ALL 0x49; f21255ac (mixedwrite, elem 590) carries 7,
  all 0x49; ccbb7862 (mixedwrite, elem 245,621) carries 1, a 0x44.
  The committed grammar gives 0x49/0x44 no loops (G3 open questions
  3-5).  **The 0x49 byte law holds (fact):** n == 3*type with n=3 on
  every record (counts partitions (3,) x105 / (2,1) x3 / (1,2) x10 on
  cf7394ee — the count-byte split is ambiguous, the n=3 group is not).
  **The single-triangle ceiling (measured under the named hypothesis):
  cf7394ee 118/118 loops SKIP-REFERENCE** (the U4 content class inside
  the 0x49 family — 0 triangles even with the reading pinned; the
  compound 0x49 + dup-pin probe fails the E0-b battery 117/118
  nonplanar and exports non-manifold raw: 90 tris, 82 boundary edges);
  **f21255ac 6/7 loops coordinate-duplicate + 1 valid triangle** — a
  1-triangle mesh that still FAILS the gate (6 skipped degenerates >
  MAX_DEGENERATE_TRIANGLES = 0); ccbb7862's single 0x44 record has no
  byte law (unknown).  Ceiling **0 measured** (inference beyond the
  named hypothesis: a different 0x49 grammar is not excluded by the
  bytes in hand, but nothing in the committed evidence supports one).

## 3. not-manifold — 33 stores: 31 content-fins + 1 coplanar book + 1 duplicated content (fact)

Per-store census: `stage14-notmanifold-mechanism.csv`.

- **The over-edge census (fact):** 89 over-used edges (use count 3-37)
  across 33 stores; histogram by use count {3: xN} dominant, one edge
  of 37 on 13bb5c0c.  Cause classification with triangle-to-record
  attribution: **0/89 from repeated-ref loops** (the stage-4b
  width-residual signature does NOT explain this family — its 21/29
  width fixes landed in stage 5 and the residual 8's pattern is absent
  here), **0 records parsed twice** (territory overlap 0 on all 33),
  and duplicate coordinates (present on 8 stores, up to 2,105 on
  341bd488) create BOUNDARY edges (under-use), never over-use.
- **`content-fins` (31 = 30 dev + 1 held-out).**  Every store's
  over-edges join DISTINCT triangles (no duplicate triples) that are
  pairwise NON-COPLANAR at the edge — three or more distinct sheets
  meeting along one segment, from distinct records and loops.
  **Anchor 44e63faa** (mixedwrite, 543 tris, 2 over-edges): edge (0,1)
  used 3x — two consecutive windows of one 0x42 strip (record at
  27,620,068) plus one triangle from a different record (27,630,319);
  plane normals ~(0.98, 0.00, 0.20) / (-0.995, -0.08, 0.06) /
  (-0.998, -0.05, -0.02) — a genuine fold.  **The content-vs-artifact
  verdict is inference from these bytes:** the identity mapping
  (refs 0-based element indices) and the width laws are landed and
  validated on exactly these stores (refs in-bounds, no repeats,
  normals agree with loop planes where carried); a law that would make
  this mesh manifold would have to CHANGE which triangles exist —
  i.e. re-read the records — for which no byte evidence exists in the
  committed notes or this census.  Ceiling **0** (inference).
- **`coplanar-overlap` (1, dev: 97a0a420, table-walk, 525 tris).**
  Edge (3,4) used 13x by 13 DISTINCT triangles from 13 different 0x42
  records (~3,231 B apart), all loop1, third vertices 127..155 (odd
  steps), ALL stored normals ~(1,0,0) agreeing with the triangle
  planes — a 13-page coplanar "book" along the segment (3,4) written
  in the bytes (each page a distinct record; the decode reproduces the
  records faithfully).  Ceiling **0** (inference, same grounds).
- **`duplicate-triangles-dedup-solves` (1, dev: 1d256d12, per-rep, 6
  reps, 24 tris).**  4 duplicate index triples, each emitted by TWO
  DIFFERENT 0x4a records 621 B apart in the SAME rep (offset pairs
  1,018,583/1,019,204 and 1,018,558/1,019,179) —
  duplicated CONTENT in the bytes (the writer listed the same three
  facets twice), not a double-parse (territory overlap 0, different
  offsets).  **Dedup ceiling: dropping the 4 extras -> manifold
  (fact, measured).**  1 store < the Phase-B >= 2 gate (section 6).

## 4. The ceiling table (the dispatch's deliverable)

Dev flips are what the bar counts (104 needed after the stage-13
fitness row; held-out steady at 55/61).

| mechanism | stores (dev) | ceiling if solved | label |
|---|---|---|---|
| empty-mesh `no-facet-records` | 55 | **0** — nothing to triangulate | fact |
| empty-mesh `u4-curve-entry-all-loops` | 25 | **24 pass** under dup-pin-ALL (1 not-manifold: 3dff4d93) | fact (probe-measured), GATED on overturning the stage-10 conservative rule |
| empty-mesh `records-without-loops` | 3 | **0 measured** under the 0x49 n==3*type hypothesis (cf7394ee all-skip-ref; f21255ac degenerate-fail; ccbb7862 unknown) | fact (measurement) / unknown (a different 0x49 grammar) |
| not-manifold `content-fins` | 30 | **0** — distinct non-coplanar sheets; no law re-reads them | inference (byte evidence SF12) |
| not-manifold `coplanar-overlap` | 1 | **0** — the book is in the bytes | inference |
| not-manifold `duplicate-triangles` | 1 | **1** (dedup) | fact |
| **total measured** | 117 | **25 dev** (24 + 1) | < 104 |

**The grind answer, plainly: the bar is NOT reachable through the
empty-mesh and not-manifold families.**  Even the full hypothetical
(overturning the conservative rule) measures 25 < 104; without it the
measured ceiling is 1.  For scale: the remaining unpinned mass after
this stage is the 128 no-facet no-pool stores (stage-13: structurally
incapable), 125 missing-locator, 16 composite, 3 carriers — the
close-conversation arithmetic should re-open on THESE numbers.

## 5. Corrections to existing notes (dated, none massaged)

1. **2026-11-13, stage-13 note section 7 ("every facet loop references
   skip slots") + the stage-13 dispatch framing:** the 4 new
   vertices-only rows' dropped loops are MIXED — their references
   split between skip slots and written elements (1467e3df loop0:
   70/138 skip-referencing; b9f61739 loop0: 3/6), not "referencing ONLY
   skip slots".  The drop rule is any-skip-ref (`_triangulate`); the
   dup pin handles mixed loops (written refs resolve directly).  The
   stage-13 CSV figures are unaffected (the mechanism attribution
   below them stands; the 26 U4 stores re-derive from the committed
   census's own loops_curve_entry column).
2. **2026-11-13, stage-9 note residual open (2) ("the 13 empty-mesh
   exports' record reading: facet records parse but produce no
   pinned-family triangles"):** at this baseline the family's emptiness
   decomposes — 55/84 stores carry NO parseable facet record at all
   (the stage-9 13 are all in the no-facet-records / records-without-
   loops buckets: 086a4eff 36 junk candidates, cf7394ee 118 0x49, ...)
   — the "records parse but produce no triangles" reading was the
   0x49/0x44-marker subset, now measured ceiling-0 under the committed
   byte law.  The stage-9 A/B figures are unaffected.

## 6. Phase B: DOES NOT RUN (the conditional gate is not met)

The dispatch gate: a mechanism with >= 2 stores whose law is pinnable
from COMMITTED evidence + measured bytes, AND not already deliberately
ruled conservative.

- **The dup-pin-ALL mechanism (26 stores, 24-dev measured ceiling) is
  pinnable — the law is already committed inside
  `composite._e0b_dup_pin` — but it is exactly the mechanism the
  stage-10 decision deliberately ruled conservative** (E0-b =
  battery-supported only; the analysis's grounds stand: 90.4% of
  dropped loops battery-untestable, dup-law rate 95.6% vs 98.9%
  control on the tested ones, twin invariance n=1 pair).  The dispatch
  names this case explicitly: overturning the U4 conservative rule is
  a STOP-and-report, not a unilateral change.  THIS NOTE IS THAT
  REPORT: the measured ceiling of the relaxation is 24 dev + 1
  held-out passes, zero regressions by construction (E0: every
  candidate store already fails the gate — the dup-pin mesh can only
  move fail -> pass; measured: 25/26 pass, 1 stays not-manifold, no
  pass row touches the dup path).  The counter-evidence the stage-10
  decision weighed is unchanged (no new twin pairs; the battery cannot
  test normal-less loops); what IS new is the measured yield and that
  25/26 pinned meshes pass every gate check including the
  degenerate-triangles check.  Decision: coordinator/owner's.
- **duplicate-triangle dedup: 1 store** — below the >= 2 gate; no law
  to pin (the duplication is writer-side content).
- **No other mechanism has a pinnable law** (sections 2-3).

No src/ file was touched by this stage; no A/B delta to declare; the
corpus runs were probe-only (the census/ceiling CSVs are committed
artifacts; the probe's anchor mode writes `*-anchor.csv` outside the
committed names).

## 7. Claims

See `stage14-claims.csv` (SF1-SF17).

## 8. Reproduction

```
cd <worktree @ a3edbab> && ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus
python3 -m venv .venv && .venv/bin/pip install -e '.[test]' -e '.[lint]'
# live membership (the byte-identical check the note cites):
.venv/bin/python -I scripts/triage/ab_identity_export.py \
  --out-dir ~/.local/state/catpart-parser/stage14 --out-name stage14-live-ab.csv
cmp ~/.local/state/catpart-parser/stage14/stage14-live-ab.csv \
  docs/evidence/data/stage13-identity-export-files.csv
# the census + ceilings (writes the three committed CSVs under docs/evidence/data/):
.venv/bin/python -I scripts/triage/stage14_export_failure_probe.py
# anchor subsets (write *-anchor.csv, never the committed names):
.venv/bin/python -I scripts/triage/stage14_export_failure_probe.py \
  --include-sha16 1467e3df5f6507b0,44e63faa2d9abf84 --out-dir /tmp/stage14 "--suffix=-anchor"
```

Corpus binaries are not committed (corpus symlinked read-only).  The
probe imports the committed geometry modules read-only through capture
wrappers (the wrapped references are restored per-process; `src/` is
untouched on disk).  Anchor byte detail (record layouts, over-edge
geometry, the 0x49/ceiling probes of sections 2-3) ran ad-hoc in the
session dir; every number it produced is either in the committed CSVs
or quoted above with its store named.
