# Evidence: the element space beyond the pool — the no-pool and refs-beyond families at the stage-12 landed baseline (stage 13, 2026-11-13)

Ticket #34 (G6, stage 13, owner direction cont. 17: keep grinding to
the bar): byte-level structure research on the two unpinned families of
the stage-12 census — the no-pool family (94 stores at the stage-10
baseline **plus the 37 locator-recovered no-pool bodies**, whose spans
LOCATE under the landed stage-12 other-container probe) and the
refs-beyond family (38) — with the question answered byte-level: WHERE
do the non-pool elements' vertices live, and is a decode law pinnable
from committed evidence + the measured bytes.  Phase B (CONDITIONAL)
ran: the routing extension is a separate commit series on this branch
(declared before observed, standing gates).

Population re-derived LIVE (the stage-12 census CSVs are
stage-10-baseline artifacts; the exporter anchor shifted per its A/B):
every fail-closed row of the accepted stage-12 A/B
(`stage12-identity-export-files.csv`, `export_ok != 1`) — **310, not
the dispatch's suspect "330"** — through
`scripts/triage/stage13_elementspace_probe.py` (committed with this
note; own code porting the stage-12 method: own 4-family span walk
replicating `export._export_data`'s probe order INCLUDING the landed
other-container family, composite-span detection per located span, and
the exporter anchor `build_export` as the black box).  The committed
geometry modules (`store`/`pool`/`facets`/`composite`/`export`/the
gate `fitness.runner._score_export`) are infrastructure; the
orchestration and every census below is the probe's own.

Labels: **fact** = measured here and reproducible from the committed
CSVs + reproduction commands; **inference** = interpretation, reasoning
shown; **unknown** = open.

## The headline

**The refs-beyond family IS the composite element-space structure
minus its routing predicate.**  Every one of the 38 stores carries a
token-bearing list node whose declared element count satisfies the N2
shape (c1 = max_ref + 1 on 24/38, > max_ref + 1 on 14, < on 0), and on
33/38 the node's point region DECODES under the COMMITTED 2-bit table
law with the pool absorbed verbatim (exact f32 on 30) — the facets'
"beyond-pool" references are 0-based element indices of that decoded
region, exactly the M2b identity law.  The exporter never routes there
only because `pool.has_composite_space(kinds)` is false (the stores
carry no `01 02` edge group and no `ff ..` opener).  Called through
the REAL composite path with only the routing predicate bypassed:
**32/38 export (28 pass the L2 gate) on the exporter window; +3 of the
no-pool family's 131 also export and pass — 31 L2 passes total, all
dev** (964 -> 995 = 72.05% projected).  The "no second pool form"
negative claim re-verifies with own walkers: 0/38.

**The no-pool family is NOT a hidden facet-mesh family.**  Of 131
stores, exactly **3 facet carriers** (66049cf3, bf350820, fac22ea3)
have the same unrouted-composite structure pool-less and export+pass
under the same law; the other **128 carry ZERO facet records**
(max_ref = -1) — no vertex-source law can ever give them triangles.
Their bytes decompose: 38 without token nodes, 90 whose largest node
payloads are a 70-97 B template (direction-cosine floats, the
`14 04 ff ff ff ff ff` records — no P1t layout, no raw-array fit), 8
wireframe stores (unwrapped `05 08 01` vertex tables of single-z 2-D
profiles + inline-coordinate edge records `03 02 01` + two xyz
triples), and big bodies whose bulk is non-token node records
(structured u32-run data at 1.59 bits/byte entropy — not compressed,
not vertices).  **The stage-12 IF-solved grant of +94 (+37 recovered)
collapses to +3 measured**; the honest hypothetical bound that reached
the bar (181) is gone: the corrected post-stage-13 hypothetical is
12 + 3 + 38 = 53 < 141.

## 1. The live memberships and the delta vs the stage-12 census (fact)

- 310 fail-closed at eed27a9 = **131 no-pool + 38 refs-beyond + 125
  missing-locator + 16 composite-failclosed** (zero other; the anchor
  partition re-derives the stage-12 review's tabulation with the
  stage-12 A/B's shifts applied).
- The delta vs the committed stage-12 census (a stage-10-baseline
  artifact) is exactly **41 rows**: 37 `missing-locator` -> `no-pool`
  (the locator-recovered bodies — all 37 recovered via the
  other-container probe with the padded tail law, error detail
  carrying the `store_recovery` suffix) and 4 `missing-locator` ->
  `composite-failclosed` (the stage-12 recovered composites 416d14fd,
  434d4bb4, 4902c650, c6eaac5e).  The 94 no-pool and 38 refs-beyond
  re-derive identically row-for-row; the 12 stage-11 composites are
  absent from the stage-12 census as expected.
- The 37 recovered bodies are structurally the SAME no-pool family as
  the 94 (11 no-token-node + 26 largest-node layout failures, **0
  facet records, 0 unwrapped vertex runs**): the surface the stage-12
  extension opened adds zero decodable stores (SE10).

## 2. refs-beyond — 38 stores: the element space is the list node's point region (fact)

Per-store census: `stage13-elementspace-census.csv` (family
refs-beyond); decode probe: `stage13-decode-probe.csv`.

- **The structure (fact, anchors byte-verified):** wrapper + `01 06`
  pool (37 stores 1 group, 1 store 2 groups) + one non-pool group
  (`00 00` x30 — the curve-record group of the stage-2a C1 census —
  `00 01` x6, `9c 00` x2, `00 ff` x2, `75 00`/`31 ff`/`62 00` x1) + a
  scene-graph node territory whose token-bearing list node declares
  the element space.  The pool is a small SUBSET of that space
  (4-168 vertices vs declared 10-27,264), re-listed verbatim in the
  node's decoded points.
- **Anchor b86baae6ec9412ba (byte-ranged):** body [54407, 56827);
  node at body+467, payload 893 B, token `ff ff 02 00 01` at
  payload+29, counts c1=40/c2=38, 2-bit table at payload[35,45),
  write count 136, region payload[46,590).  The walk decodes exactly
  40 distinct points = a tessellated cylinder (20-point circle at
  z=0 and z=5, r=2.5); the pool's 4 vertices sit at region indices
  7, 8, 32, 36 (exact f32); facet rec0 (marker 0x42, 38 refs) walks
  the cylinder side as (z=0, z=5) pairs per angular step, max ref 39
  < 40.  The `00 00` group at body+1351 opens count=98 followed by a
  nested node record — the curve/scene-graph carrier, not a vertex
  source.
- **The N2 shape (fact):** c1_of_largest = max_ref + 1 on 24/38; the
  14 `>` stores declare slack (skip slots — curve entries — and
  unreferenced tail elements); **0/38 have c1 < max_ref + 1**: every
  reference resolves inside the declared space.  The clean path's
  "facet references beyond the pool" is an artifact of reading only
  the pool as the vertex source.
- **The decode probe (fact):** `_export_composite_store` called
  directly (routing bypassed) raises the marker check on all 169
  family stores — the ONLY blocker.  With the bypassed flow (the
  committed `find_list_node`/`decode_region`/`parse_strip_records`/
  `_triangulate`/`_decode_per_rep` exactly as `decode_composite_store`
  sequences them):
  - **32/38 export on the exporter window** (the window the landed
    `decode_composite_store` uses): identity-table-walk x29 +
    identity-per-rep x3 (03c67888 96 pts/92 tris; 996fc82b and
    fcc76b63 9,938 pts/276 tris — the per-rep composition absorbs the
    two-pool/two-rep bodies);
  - **28/38 pass the L2 gate** (the committed
    `fitness.runner._score_export`); 4/38 export EMPTY-mesh
    (1467e3df/77168b28 26,401 pts, 1,306 skips; 9ed8c3e1 212/123;
    b9f61739 310/160 — every facet loop references skip slots, the
    U4 curve-entry case, so 0 triangles);
  - 5/38 raise: 531350af + c3d79133 (table walk exceeds at c1=10,218),
    c5b31a94 (at c1=10), 086b9dd9 (non-finite coordinate at c1=30),
    a60156f7 (walk consumed 188 of 268 words at c1=24);
  - **477abcad (27,264 elements) passes only via the full-body
    window**: its list node is truncated by the first STRIP_RE match
    in the exporter window (the stage-8 truncation artifact) — 2,372
    triangles from the 27,264-point region when the window is full.
- **The "no second pool form" negative claim re-verified (fact, own
  walkers):** 0/38 carry a `10 24`-wrapped `01 06` group outside the
  located pool groups; `05 08 01` runs >= 3 outside pool spans on 3
  stores (03c67888 runs 1;1;1;6 — extra vertex records beside a
  two-rep body; 0c889913/4ce00502 runs 1;1;4 — beside a fully
  absorbed pool).  The stage-12 census's wording stands.

## 3. no-pool — 131 stores: 3 facet carriers, 128 with no facet geometry (fact)

- **The 3 facet carriers (fact):** 66049cf3, bf350820, fac22ea3 carry
  STRIP_RE facet records (8/4/16 records, max_ref 43/237/1836) and a
  token-bearing list node whose point region decodes under the
  committed law (44 pts + 0 skips / 236 + 2 / 1,592 + 271);
  c1_of_largest = max_ref + 1 on 66049cf3 and bf350820, max_ref + 27
  on fac22ea3 (the 271 skips' slack).  All 3 export+PASS through the
  bypassed committed decode (88 / 118 / 1,100 triangles;
  `stage13-decode-probe.csv`).  **Anchor 66049cf3 (byte-ranged):**
  body [37761, 42170); node at body+917, payload 2,224 B, c1=44/c2=32,
  table payload[35,46), write count 136, region payload[47,591); the
  44 points are a two-z-level tessellation (z=139.721/149.721); the 8
  facet records (0x4a, 4-ref quads) reference 0..43 in-bounds; the
  store's UNWRAPPED `05 08 01` run at body+2892 (16 records, no pool
  wrapper anywhere) re-lists 16 of the 44 element-space points
  EXACT-f32 — a pool-record vertex table without a pool group.
- **The 128 non-carriers (fact):** ZERO facet records on all (the
  clean facet scan finds no records; 125/131 zero STRIP_RE
  candidates).  Decomposition:
  - **38/131 carry no token node** at all.  Minimal bodies (635-695 B)
    are pure scene-graph directories — name entries ("MainDataStream",
    "SceneGraph", "Header", "Describe", "MAIN" in UTF-16LE) + two
    small `04 04 fd ff` nodes with direction-cosine payloads;
    **anchor 61765d51d3d73cb1** (635 B, dump in the reproduction
    block): two nodes (kind 2 and kind 9 templates, `ff 03 01 00 00
    ff` sub-records), no geometry records of any family.
  - **90/131 largest-node layout failures**: the payload is a 70-97 B
    template — `00 00 00 01` header, token `ff ff 02 00 01`, c1=84/86,
    c2 = 0/1 or cumulative values (1/39/77 — the stage-3b residue's
    per-rep node signature), 16 B zero block, direction-cosine floats
    (`f3 04 35 3f` = 0.70709229 x2, `f3 04 35 bf` = -0.70709229),
    f32 15.0 (`00 00 70 41`), then the `14 04 ff ff ff ff ff 00`
    records and a `00 62 00 00` tail.  Byte-identical templates recur
    across stores (05fe6c233d50ab53 and 45bee87f37c06cf6 share the
    86/1 payload).  No P1t layout fits (the committed failures: 51
    walk-exceeds-at-0, 20 write-count-overrun `6422783` = the ff-escape
    eating a `00 62 00 ..` tail, 12 `255` overruns, 7 other) and the
    stage-6 raw-array signature stays absent (the stage-12 census's
    0/94 carries to 0/131 at this baseline).
  - **8 wireframe stores** (1968ce85, 4e8feabe, 65564a9b, 853788c3,
    9fa8cb5a, a15e5740, be3ff691, e1cef8ab): unwrapped `05 08 01`
    vertex tables (10-16 records, 100% finite mm-scale, z = 0 or a
    single plane) + inline-coordinate edge records `03 02 01` +
    24 B of two xyz triples (8-12 per store; the edges' coordinates
    repeat the vertex table's values — **anchor 4e8feabe34c9b620**:
    body [66557, 69311); the vertex run at body+1543 = 10 records of a
    z=0 profile; the node at body+1496 carries token `ff ff 02 00 00`
    (NOT the list token) + f32 0.2 before the records; 8 `03 02 01`
    segment records follow at body+1693).  Zero facet headers — these
    are 2-D profile/wireframe bodies (annotation content), not meshes.
  - **The big bodies' bulk (fact, 45bee87f37c06cf6):** 265,054 B body,
    19 `04 04 fd ff` node spans covering 264,961 B, largest TOKEN node
    97 B — the bulk sits in non-token node records whose payloads are
    structured non-geometry data (runs of u32le 12, direction-cosine
    heads; Shannon entropy 1.59 bits/byte — structured, not
    compressed, no vertex records, no facet headers).

## 4. The pinnability verdicts (the dispatch's deliverable)

- **refs-beyond: PINNABLE from committed evidence.**  The decode law
  IS the committed composite law (P1t/U1/M2b/per-rep — no new byte law
  needed); the only blocker is the routing predicate.  Measured
  ceiling through the probe's single-rep bypass on the exporter
  window: 32 exports / 28 passes (+3 no-pool passes); the REAL
  landing measured higher — the landed raw/mixedwrite fallbacks and
  the stage-4b noise tolerance push it to **41 exports / 37 L2
  passes** (section 6, all dev — dev 964 -> 1,001 = 72.48%).  Phase B
  ran (section 6).
- **no-pool: pinnable ONLY for the 3 facet carriers** (+3 exports/+3
  passes, the same routing change).  The other 128 are structurally
  incapable of L2 passes: with 0 facet records there is nothing to
  triangulate under ANY vertex-source law.  **The stage-12 note's
  IF-solved grant for this family (+94, and the review-F1 arithmetic's
  +37 recovered cap-raisers) collapses to +3 measured.**  Dated
  correction to the stage-12 note section 5 (the no-pool row's
  IF-solved column): the honest post-stage-13 hypothetical for the
  non-composite mass is 12 + 3 + 38 = **53 < 141** — the bar is again
  unreachable through this mass even hypothetically, and the 38
  refs-beyond are now a MEASURED lever (28-31 of them), not a
  hypothetical.

## 5. Corrections to existing notes (dated, none massaged)

1. **2026-11-13, stage-12 note section 5 + review F1's IF-solved
   arithmetic:** the no-pool family's 100%-yield grant (94 + 37) is
   measured impossible: 128/131 stores carry no facet records (this
   note's section 3), so no vertex-source law can pass them; the
   family's L2 ceiling is the 3 facet carriers.  The honest
   hypothetical sum becomes 12 + 3 + 38 = 53 < 141 (the stage-12
   F1-corrected 181 >= 153 assumed the grant; the grant is now
   byte-refuted).  The refs-beyond +38 grant is REPLACED by a measured
   +28/+31 (section 6).
2. **2026-11-13, stage-12 census SC7 ("no second pool form"):**
   CONFIRMED with own walkers at the landed baseline (0/38, section
   2); the 3 stores with outside-pool `05 08 01` runs are named and
   are not a second pool form.

## 6. Phase B: the routing extension (the conditional gate met, declared before observed)

Gate: the law is pinnable from committed evidence (section 4) and >= 2
stores are blocked on the routing (169).  Implementation: a
**second-chance composite decode** in `export._export_store` — when
the clean path is about to raise `no 01 06 vertex pool decoded` (the
no-pool raise) or `facet references beyond the pool` (the refs-beyond
raise) AND the span's body carries a token-bearing list node
(`composite.find_list_node` on the exporter window), the store is
re-routed through the UNCHANGED `_export_composite_store` /
`decode_composite_store` (an additive `allow_unrouted_elements` flag
skips ONLY the marker-routing check; every other gate — layout,
walk-exact, absorption, per-rep, refs, triangulation — is the landed
code).  On any composite failure the ORIGINAL clean-path error is
re-raised unchanged (fail-closed; row-identical).  Precedence is
unchanged: marker stores still route first; the second chance fires
only on the two named failure classes; the P7 vertices-only export is
unaffected (it happens before the raise).

Declared delta (the declaration commit precedes the corpus run; the
measurement behind it ran through the REAL seam — `build_export` on
each of the 169 population parts with the landed implementation, gated
by the committed `_score_export` — pre-declaration):

- D1: exports 1,132 -> **1,173 (+41, 0 lost)** — 38/38 refs-beyond
  (34 `pass` + 4 `empty-mesh`) + 3 no-pool facet carriers.  The real
  landing EXCEEDS the probe's single-rep bypass measurement
  (35 exports / 31 passes): the landed stage-6 raw-array and stage-8
  mixed-write fallbacks rescue 6 more stores (086b9dd9, 477abcad,
  531350af, a60156f7, c3d79133, c5b31a94 — all `identity-mixedwrite-
  reps`), and the stage-4b noise tolerance absorbs the two near-pool
  twins (5a4dcd70/e3d4c2d1) the probe's exact-only check declined.
- D2: dev L2 **964 -> 1,001/1,381 = 72.48% (+37)**; held-out
  **unchanged** (all 169 population rows are dev); 0 lost passes.
- D3: exactly **41 of the 1,442 A/B rows differ**: 41 rows
  `undecoded-variant` -> exported (37 `pass` + 4 `empty-mesh`);
  every other row byte-identical — the 128 no-pool stores that still
  fail re-raise their ORIGINAL error unchanged (detail included), and
  no non-population row moves.
- D4: the 41 exports' `stage`: identity-table-walk x32 (28 of the
  passes + the 4 empty-mesh vertices-only exports, warning class
  `no-facet-records`) + identity-per-rep x3 (03c67888, 996fc82b,
  fcc76b63) + identity-mixedwrite-reps x6 (the rescue list in D1);
  `store_recovery` rides on the 8 stage-3a-recovered stores among the
  41 (seebody/padded — the landed provenance law, unchanged); 0 of the
  37 stage-12 recovered no-pool bodies export.
- D5: no schema change (the composite summary block and warnings are
  already committed schema-additive); the empty-mesh exports carry the
  vertices-only `no-facet-records` warning.
- D6: STOP gates: any lost export or lost pass = STOP; any changed
  row outside the 41 = stop-and-root-cause.

## 7. Claims

See `stage13-elementspace-claims.csv` (SE1-SE12).  Phase B observed
results: the section-6 table is completed in the claims CSV (SE13)
and the wrap-up commit.

## 8. Reproduction

```
cd <worktree> && ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus
python3 -I scripts/triage/stage13_elementspace_probe.py
# outputs: docs/evidence/data/stage13-membership.csv (310 rows)
#          docs/evidence/data/stage13-elementspace-census.csv (169 rows)
#          docs/evidence/data/stage13-decode-probe.csv (507 rows)
# anchor subset:
python3 -I scripts/triage/stage13_elementspace_probe.py --sha16 b86baae6ec9412ba
# anchor byte-dumps used in sections 2-3 (ad-hoc, the committed probe
# carries the census): the node layouts of b86baae6 (body+467),
# 66049cf3 (body+917), 4e8feabe (vertex run body+1543), 61765d51
# (the 635-B directory body), 45bee87f (the 265-KB non-token bulk)
```

Corpus binaries are not committed (corpus symlinked read-only).  The
probe imports the committed geometry modules read-only and writes
nothing outside `docs/evidence/data/`; `src/` was untouched by Phase A
(the Phase B commit series touches `export.py`/`composite.py` + tests
under the standing gates).
