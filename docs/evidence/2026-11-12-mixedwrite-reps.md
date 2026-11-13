# Evidence: the mixed-write float stream is the committed laws on FULL node windows (stage 8, 2026-11-12, #34)

Bounded structure-decode ticket (dispatch-recipes template, G6 stage 8):
the mixed-write float stream behind the stage-7 unexplained stores —
the grind's remaining mass (owner direction: push for the 80% L2 bar).
Population: the 93 fail-closed walk-mismatch composite stores of the
stage-6 raw trigger probe (84 start-unpinned / 6 weak-fit /
3 pool-unabsorbed — `stage6-raw-trigger-probe.csv`), which is the
stage-7 note's 68 unexplained plus its 14 pair-variant / 10
container-partial / 1 container-tiled stores.  Anchors: ccbb7862 (the
mass case), 221df959 (the layout misalignment), 0f18f772 (the
multi-rep body), d51eb38c (the flat reading), 12dc542e (the UV
family).  Analysis only — src/ untouched.

Labels: **fact** = byte-measured on the corpus by the committed
script; **inference** = derived, reasoning shown; **unknown** = open.
Below-bar claims (fewer than 3 files) are labeled **candidate**.

## The headline

**The mixed-write stream is NOT a new packing.**  On the FULL node
window (NODE_MAGIC to NODE_MAGIC — the exporter's own
`_scan_token_nodes` convention), the committed decode laws parse 82 of
the 93 stores end-to-end: 166 reps decode (133 table-law, 14
raw-law, 19 flat-law), every pool group is accounted verbatim, and
every gated record reference stays in-bounds (0 violations on 126
record-bearing reps).  The stage-7 "68 unexplained" resolves to **67
explained / 1 open**.  What blocked the exporter was three LOCATOR and
PREDICATE artifacts, each named below with its incidence — the
write-shape laws themselves (stage-3b table, stage-4a raw array) were
never wrong on these payloads.

The committed script (`scripts/triage/mixedwrite_decode.py`, outputs
`mixedwrite-reps-files.csv` + `mixedwrite-reps-nodes.csv`) decodes
each token node with the committed laws and composes the stage-5
per-rep law on top; every byte the laws cannot tie to a section stays
fail-closed and named per store.

## The three artifacts (fact, each with its incidence)

1. **The list-node window truncates at the first STRIP_RE match**
   (`composite.decode_composite_store`: `node_hi = hdrs[0]`;
   `find_list_node(data, lo, node_hi)`).  STRIP_RE (`01 [41-4f] ? ff`)
   false-matches INSIDE point regions, so on 8/93 stores the window
   cuts the real list node.  The mass case ccbb7862: window payload
   2,516,042 B vs full payload 6,620,640 B; the true point region is
   payload[48, 2,947,500) = 245,621 full-write triples (all-nice,
   x-ascending rate 1.000, 0 x-drops), closing with the raw law's FF
   trail-escape and count3 = 491,242 = **2 x elem_decl** — all
   invisible in the truncated window (the stage-7 note's "209,666
   triples to 2 B short of the end" was the truncation boundary, not a
   structure).  The raw law's start rule then finds 0 candidates
   ("start-unpinned") purely because 12 x elem_decl no longer fits.
2. **`layout()` skips ALL consecutive zero groups after the counts**
   (`while payload[p:p+4] == zeros: p += 4`) — when the region opens
   with >= 4 full-write slots, the 2-bit table's own leading bytes are
   zero and the skip overshoots INTO the table: the P1g count reads
   from a misaligned position and the walk fails.  Incidence: 38 of
   the 133 decoded table reps (36 stores) misalign, by 1-75 4-byte
   groups (the misalign=75 store's table is mostly zeros — an
   all-full-write region).  Named byte case 221df959 (c1 = 3,864,
   counts_end 44, zero block [44,48), table [48,1014) opening
   `00 00 00 00`): the committed skip eats [44,56) (3 groups), reads
   the count at 1,022 and fails ("the declared 194" the exporter
   reports); the correct count 8,156 sits at 1,014 and the walk is
   exact.  Fix law: the zero-block EXTENT is a candidate
   (1..k groups); exactly one extent must yield the walk-exact decode
   (count == the table's shape sum, region all-nice) — ambiguity stays
   fail-closed.  All 133 table reps resolve at a UNIQUE extent (the
   true zero block).
3. **The raw law's `_raw_nice` floor (1e-6 < |v| < 1e7) rejects real
   near-zero coordinates** on these stores (the stage-7 note already
   measured this: 7d27c73d z = -1.19e-14, dd610ca5 x = 9.4e-15).
   d51eb38c: the region [40, 2356) = 193 full triples (x-ascending
   1.000, pool 5/5 verbatim) closes with a REAL FF escape at 2356 —
   but the floor-predicate fit measures nice 0.632 and the committed
   raw law rejects it.  The exporter-predicate reading (v == v,
   |v| < 1e9) is all-nice.  The stage-7 "container PART-1" reading is
   the general law: the region starts at counts_end+4 (the 4-B tail
   field), holds c1 full-write triples, and needs NO FF escape — the
   sub-sections follow byte-adjacent.

## The reading (and what it composes)

Per store, over the FULL body: every token node is decoded with the
ladder (a) the stage-3b table law with the zero-block extent
candidates, (b) the stage-4a raw law (committed start rule and
criteria), (c) the flat law (c1 full triples from counts_end+4,
all-nice under the exporter predicate, x-ascending >= 0.98 OR the pool
fully absorbed verbatim).  Decoded nodes are the reps; the stage-5
per-rep composition applies unchanged (content pairing by absorption —
the diagonal when every rep decodes, content-matched when earlier reps
fail — the stage-4b "shifted" case is the same measurement).  Pool
absorption runs on exact f32 first, then the stage-4b noise tolerance
(relative 1e-5, full triples only), then the twins' second route: the
`05 08 01` vertex sub-node records re-list pool verbatim (stage-7's
vertex sub-node law, now corpus-wide).  The refs gate parses the gated
records in each rep's territory (region end -> the next node magic)
and requires max gated ref < the rep's element count.

- **Reps decode (fact, 166 reps on 2,709 token nodes):** 133 table +
  14 raw + 19 flat.  Multi-rep bodies decode per rep: 0f18f772 carries
  17 pool groups and 17 decoded reps (15 table + 2 raw) — its
  exporter failure ("table walk exceeds the declared region at
  element 0 ... 0 left of the declared 0") came from the window
  retaining only 67-B stub nodes, and the per-rep path is unreachable
  whenever the single-rep decode raises first (the stage-5 flow gates
  `_decode_per_rep` behind a successful `decode_region`).
- **Pool absorption (fact):** 82/93 stores account EVERY pool group:
  172,276 pool vertices verbatim in decoded regions + 29,986 only in
  the `05 08 01` sub-node records.  On the 60 strict-exportable
  stores the absorption is EXACT f32 in regions — the noise tolerance
  fires on zero strict pools (the stage-4b double-rounding residue
  does not appear here).
- **The refs gate (fact):** 126 reps carry gated records; every
  reference resolves inside its own rep's element count — 0 violations
  corpus-wide on the 93.
- **The twins' container readings (fact):** the 10 container-partial
  stores and the container-tiled f21255ac all resolve reps-full —
  stage-7's unexplained ~3,044 B residue was additional reps whose
  nodes the truncated window never reached (948aa851: 3 raw + 1 flat
  rep; cb49f9f4: 4 flat reps).

## The verdict that matters: the measured split of the 93

(fact, `mixedwrite-reps-files.csv`; every store named with its per-rep
rows in `mixedwrite-reps-nodes.csv`.)

| class | stores | strict-exportable | notes |
|---|---|---|---|
| reps-full (all pools accounted, refs in-bounds) | **82** | **60** | law mix of the strict 60: 47 table + 7 raw + 6 flat; all dev |
| — pool fully region-absorbed | 60 | — | export-ready under the current law (absorption + refs + triangulation gates apply at the A/B) |
| — pool needs the sub-node route | 22 | — | the pool's element INDICES are unpinned (open) |
| unexplained | **11** | 0 | the UV family (below), 7 dev + 4 held-out |

Mapped onto the stage-7 classes: the 68 "unexplained" -> **67
reps-full (50 strict) + 1 open**; the 14 pair-variant -> 4 reps-full +
10 open; the 10 container-partial -> 10 reps-full; the container-tiled
1 -> reps-full.

## The UV family (the 11 remaining stores, unknown, named)

12dc542e (anchor), 17dca565, 1b0eef98, 219c099e, 38d65967, 58ed8b28,
6c6a2e9f, 8e8500b1, a722b491, abacf110, e42e3805.  Common signature
(fact): tail field `01 00 01 01`/`01 00 01 02` (the stage-7 tail
classes, now family-discriminating); no zero block, no table, no FF
escape; the payload = a dense span of small-magnitude f32 PAIRS
(stride 8 — the stage-3b "float-pair data"; sampled values 0..3, e.g.
1b0eef98 opens 0.537/0.5/0.48 with 16-B cycles `u,v1,u,v2`) +
interleaved `02 <n> <n u16be refs>` polyline groups (the stage-2a
POLYLINE law, refs < c1) + `04 04 ff ff` 8-B records (40-541 per
store) + a vertex sub-node (`04 ff ff` + `00 00 00 01` + kind + count
+ count x `05 08 01` + 12 B f32) whose record count equals the pool
size and whose records re-list the pool verbatim (248/248 on
12dc542e, 203/203 on 8e8500b1).  The span's budget is ~48-53 B per
declared element across all 11 stores — MORE data than full triples —
and the non-pool elements' 3-D coordinates are NOT in the payload
(the pairs read as parametric values; a surface evaluation would be
required to reconstruct points).  c2 < c1 on 9/11 (e.g. 1,780/1,870,
604/1,312), equal on 2.  **The family's element semantics are OPEN** —
the exporter cannot triangulate without the elements' 3-D positions,
and no committed law provides them.

## Composition with the per-rep absorption law, and the ceiling

- The stage-5 per-rep law composes unchanged (inference, shown by the
  census): per-rep decode, per-rep absorption, per-rep refs gate,
  disjoint element spaces.  No new absorption machinery beyond the
  sub-node route (itself the twins' law at corpus scale).
- **Projected export ceiling (INFERENCE, not a fitness projection):**
  the strict 60 give **<= +60 composite exports** (all dev, all
  currently undecoded-variant rows, 0 replacements — named in the
  CSV).  The 22 subnode-assisted stores need the sub-node element-index
  law first (candidate, open).  At the stage-6 raw family's measured
  L2 share (15 pass / 13 empty of 28 exports) that projects to roughly
  **+32 L2 gate passes** on dev (dev 886 -> ~918 of 1,381; the bar is
  1,105).  The lever is the largest measured ceiling since stage 5
  (+152) and roughly 5x stage 7's container ceiling (+6) — but the
  bar still needs the remaining levers (E0 <= +24, the subnode law
  <= +22, the UV family unknown).

## If integrated: the falsifiable test (declaration, pre-run)

Trigger ONLY where the table walk raises with the walk-mismatch family
signature (the stage-6 probe population).  The integration changes the
locator and the layout, NOT the laws: (a) the list-node window = the
full body (the `_scan_token_nodes` convention), (b) `layout()` takes
the zero-block extent as a candidate with unique walk-exact selection,
(c) the flat reading joins the raw law as the third fallback, (d) on a
walk-mismatch the per-rep composition runs over ALL token nodes before
fail-closing, (e) pool absorption counts the `05 08 01` sub-node
records as a named second route (subnode-only vertices keep the store
fail-closed for EXPORT until their element indices are pinned).
Declared expected delta (external-changeset gate rule,
dispatch-recipes.md):

- D1: **+60 composite exports** (the strict 60 — all dev, all baseline
  undecoded-variant; named per store in `mixedwrite-reps-files.csv`,
  verdict reps-full AND pool_subnode_only == 0), 0 replacements.
- D2: L2 split **declared from the stage-6 raw family's measured
  share**: ~32 pass + ~28 empty-mesh (0 not-manifold expected at the
  candidate parse — the refs gate already holds; the plane battery is
  the A/B's to measure).  INFERENCE, not a fitness projection.
- D3: held-out 0 movement (the strict 60 are all dev; the 4 held-out
  unexplained stores keep undecoded-variant).
- D4: the other 33 trigger stores keep undecoded-variant with the gap
  named (22 subnode-index + 11 UV-family); 0 error-class changes
  elsewhere.
- D5: walk-OK + per-rep + unabsorbed rows byte-identical; 0 lost
  exports, 0 lost passes; replay digests identical on every
  baseline-exported row — a violation = STOP.
- D6: performance: the per-rep scan is one linear pass per body; the
  extent candidates add <= k walks per node (k = the zero-group run,
  measured max 75); the noise fallback is capped at pools <= 10,000 —
  no explosion expected (inference; the census runs the corpus in
  ~27 s).

## Named opens (per store where applicable)

1. The UV family's element semantics (11 stores, named above): what
   the pair span encodes, where the non-pool elements' 3-D coordinates
   live (surface law?), and c2's relation to the span.
2. The sub-node element-index law (22 stores): the pool vertices
   re-listed ONLY in `05 08 01` records — which element slots they
   occupy (29,986 vertices).  Until pinned, those stores stay
   fail-closed for export.
3. count3's semantics on the raw law (readable on 12 stores; = 2 x
   elem_decl on 3: 086a4eff, ab1c7b09, ccbb7862 — the 4a note's open,
   now with the 2x relation measured).
4. The tail field's semantics: the 5 byte-value classes now
   discriminate readings (zero block -> table; `00 00 00 01` -> flat/
   raw; `01 00 01 02`/`01 00 01 01` -> the UV family) — semantics
   still open, discriminating power measured.
5. c2 (edge_bound) semantics when it differs from c1 (the stage-7 open
   carries; 9/11 UV stores have c2 < c1).

## Reproduction

```
ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
python3 -I scripts/triage/mixedwrite_decode.py
# -> docs/evidence/data/mixedwrite-reps-files.csv (93 rows)
#    docs/evidence/data/mixedwrite-reps-nodes.csv (2709 rows)
# anchor subset:
python3 -I scripts/triage/mixedwrite_decode.py --sha16 ccbb7862
python3 -I scripts/triage/mixedwrite_decode.py --sha16 0f18f772
python3 -I scripts/triage/mixedwrite_decode.py --sha16 12dc542e
```

Committed artifacts: `mixedwrite-reps-files.csv` (per store),
`mixedwrite-reps-nodes.csv` (per token node), the claims ledger
`mixedwrite-reps-claims.csv`, this note.  The decoder re-uses the
committed decoders (`composite.decode_region` semantics mirrored in
`table_decode`/`decode_node`, `composite.read_count`, `composite.STRIP_RE`,
`composite._nice`/`_raw_nice`/`SHAPES`) — no law re-derivation beyond
the artifacts and the flat law stated above.

## Stage-11 Phase A addendum (2026-11-13, #34): the subnode-only-blocked population, re-measured corpus-wide at the stage-10 baseline

Phase A of the stage-11 dispatch re-derives, at the accepted stage-10
fitness row (`20261113T155028Z-1aac63`: L2 dev 952/1,381 = 68.94%,
exports 1,120), the corpus-wide population of fail-closed stores whose
ONLY pool-absorption blocker is `05 08 01` sub-node-only vertices, and
re-measures this note's ceiling claim ("the 22 subnode-assisted stores
need the sub-node element-index law first ... <= +22", MW14; carried as
"<= +22 on the corrected reading" by the stage-9 claims).  The probe
(`scripts/triage/stage11_subnode_population_probe.py` ->
`stage11-subnode-population.csv`, 322 rows) re-measures with OWN
walkers — the stage-9 correction method; this note's census columns
are joined for reference only (MW8's `pool_subnode_only` figures are
the early-break artifact the stage-9 probe corrected):

- **Population (fact):** every fail-closed store of the stage-10 row
  (322 = 178 missing-geometry-store + 144 undecoded-variant).
  Exported stores cannot carry subnode-only vertices (the exporter's
  absorption precondition — every pool vertex region-absorbed — gates
  export), and the "exported-empty on absorption grounds" disjunct is
  measured vacuous: 0 exported rows with `vertex_count == 0` (the
  L2-failing exports are empty-MESH, not absorption-empty).
- **Method (fact):** composite spans walked per store (CATStdCont in
  body order, then the exporter's xdoclink/seebody recovery probes —
  `export.py`'s order); token nodes over the FULL body decoded with
  the committed law set (`decode_node`: table with the zero-block
  extent candidates -> raw -> flat); absorption per pool group WITHOUT
  the early break — the UNION over ALL decoded reps (exact f32, then
  the exporter's `_tol_match` noise capped at 10,000-vertex groups) AND
  the exporter's diagonal; per uncovered vertex (cap 200 distinct
  values per store) every occurrence of its 12-B pattern in the body
  is classified by position (at an `05 08 01` record prefix / inside
  the pool's own record spans / elsewhere); per-rep refs gate on the
  exporter's territories.

### The measured population (fact, per store)

**1 store: `bad44bdf52f5c411`** (dev, anchor named):

- 3 pool groups (64,539 / 14,490 / 14,493 vertices; 93,518 distinct),
  6 token nodes, 3 flat reps decoded (c1 64,538 / 14,490 / 14,493, asc
  1.000), 3 undecoded 86-element nodes (the stage-3b note's U3-variant
  small per-rep nodes with cumulative edge bounds 1/34/67 — NOT
  pool-carrying reps; the exporter's composition does not gate on
  them).
- Absorption: groups 1 and 2 fully absorbed diagonally (exact f32);
  group 0 holds 64,539 distinct vertices against its rep's 64,538
  element slots — exactly 1 vertex is re-listed by NO decoded region,
  and the union residue equals the diagonal residue (no pairing
  co-blocker).  Refs 3/3 in-bounds.
- Its uncovered vertex's 12-B pattern occurs EXACTLY ONCE in the
  24.7 MB body — at an `05 08 01` record position (its own pool
  record).  Classification: **subnode-only-blocked** (fail-closed
  `undecoded-variant`; pool vertex re-listed by no region; appears
  only at an `05 08 01` record; no other gate blocker).

The 11 UV-family stores (12dc542e, 17dca565, 1b0eef98, 219c099e,
38d65967, 58ed8b28, 6c6a2e9f, 8e8500b1, a722b491, abacf110, e42e3805):
classified **unabsorbed-walk-mismatch** — 0 decoded reps (each store's
single token node fails the table/raw/flat laws), so the pool group has
no diagonal rep; their blocker is this note's named open (the UV
element semantics), NOT the index law.  The other 310 fail-closed rows
carry NO composite span (178 missing-geometry + 132 undecoded-variant
whose located store has no composite space) — no pool, no absorption
blocker.

### The ceiling verdict

- "(<= +22 on the corrected reading)" is CORRECTED to **<= +1**
  (fact): 21 of the census's 22 "subnode-assisted" stores export at
  stage-10 (stage `identity-mixedwrite-reps`, inside the stage-9 +81);
  the 22nd is bad44bdf.  The +22 was the early-break count.
- The lever's ACTIONABLE population is **0** (fact, byte-measured): no
  fail-closed store carries ANY outside-pool `05 08 01` re-listing —
  bad44bdf 0/1 verified; the 11 UV stores 0/40..0/200 verified each.
  The stage-8 reading behind MW8/MW11 ("a vertex sub-node ... whose
  records re-list the pool verbatim (248/248 on 12dc542e)") is
  byte-measured as the POOL WRAPPER ITSELF: `04 ff ff` + `00 00 00 01`
  + kind `06` + count IS `FULL_WRAP` (`10 24 04 ff ff 00 00 00`) +
  subkind `01 06` + the P1g count — the "re-listing" is the pool's own
  records (the whole-body `05 08 01` scan is vacuous for exactly this
  reason: pool.py's `VREC` and the sub-node record marker are the same
  bytes; a pool vertex's own pool record always matches).  The stage-7
  census's own columns agree (`multipart-container-files.csv`:
  `vertex_subnodes=0`, `vertex_records=0` on 12dc542e/8e8500b1); the
  genuine DISTINCT vertex sub-nodes are the twins' 11-record ones
  (81ad336b/e23423d6, `vertex_subnodes=1`), and both twins export at
  stage-10.  MW11's "re-list the pool verbatim" wording is therefore a
  **candidate** correction (the UV family's other structural
  descriptions stand).
- Consequence (inference, from the exporter's committed gate): a
  sub-node element-index law has NO evidence source on any fail-closed
  store — there are no sub-node records beyond the pools' own to pin
  indices from.  bad44bdf's 1-vertex gap would need a DIFFERENT law
  (candidate sources: the undecoded 86-element U3-variant nodes, or a
  pool/element-count reconciliation on group 0 — 64,539 pool vertices
  vs a 64,538-element rep; both opens are beyond committed evidence).
  Phase B's gate ("Phase A finds >= 2 stores blocked AND the
  element-index law is pinnable from COMMITTED evidence") is NOT met
  on either clause: the population is 1, the pinnable-from-records
  population is 0.  **The subnode-index lever closes as measured** —
  residual ceiling <= +1 export (bad44bdf, contingent on a law that
  committed evidence cannot state), actionable 0.

### Reading notes and judgment calls (named)

- "No other blocker" is operationalized at the exporter's committed
  gate structure (inference): a pool group counts walk-mismatch-blocked
  iff its DIAGONAL rep is missing; undecoded non-pool-carrying nodes do
  not block (the composition ignores them — bad44bdf's 3 failed
  86-element nodes are named in the probe CSV).  A stricter whole-body
  reading (any undecoded node = "walk mismatch applies") would empty
  the population to 0; the ceiling verdict (actionable 0) is UNCHANGED
  under either reading.
- The definition's clause "those vertices appear only in `05 08 01`
  sub-node records" is byte-checkable (every occurrence of the vertex's
  12-B pattern sits at an `05 08 01` record position) but is
  tautological given clause 2 for any pool vertex — the pool's own
  records carry the same marker.  The measurable content is the
  OUTSIDE-pool re-listing (a distinct sub-node record set), reported
  per store (`uncovered_outside_pool_relisted`): 0 across the whole
  fail-closed population.
- Union vs diagonal: the stage-9 probe measured union coverage; the
  exporter gates DIAGONALLY.  A store whose diagonal residue exceeds
  its union residue is pairing-blocked (class `unabsorbed-pairing`);
  the probe found none (bad44bdf's residues are equal, 1 == 1).
- Unknown (carried): what bad44bdf's 3 small undecoded nodes encode,
  and where group 0's 64,539th element slot lives (if anywhere) — the
  U3-variant/multipart opens, not subnode-index questions.

Reproduction:

```
ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
.venv/bin/python -I scripts/triage/stage11_subnode_population_probe.py
# -> docs/evidence/data/stage11-subnode-population.csv (322 rows; 12 composite-span rows)
```
