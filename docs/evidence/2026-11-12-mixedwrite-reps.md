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

## Stage-11 Phase A addendum (2026-11-13, #34): the corpus-wide subnode-only-blocked population at the stage-10 baseline

The stage-11 dispatch measured the subnode-index lever corpus-wide at
the accepted stage-10 baseline (c0e46e1) — the ceiling paragraph's
"the subnode law <= +22" and the stage-9 correction's residual
("only bad44bdf keeps a genuine subnode-index vertex gap WITHIN the
93") had never been re-measured outside the 93 trigger stores.
Probe: `scripts/triage/stage11_subnode_population_probe.py` ->
`stage11-subnode-population.csv` (322 rows, one per fail-closed
part-span).  Method: OWN walkers (the stage-9 correction method —
the census's `pool_subnode_only` column is joined for reference only,
never trusted), population = every stage-10 `export_ok != 1` row
(322 = 178 missing-geometry-store + 144 undecoded-variant; the
"exported-empty on absorption grounds" disjunct measured vacuous,
0 exported rows with `vertex_count == 0`), per part the exporter's
container walk, per composite span the full-body law-ladder decode
(the committed `decode_node`), DIAGONAL absorption (the exporter's
`_decode_mixedwrite` precondition, noise capped at 10,000-vertex
groups exactly as landed) plus a no-early-break union diagnostic,
byte verification of EVERY uncovered vertex value (position of each
12-B occurrence: at an `05 08 01` prefix / inside the pool's own
records / elsewhere; per-vertex pinnability = >= 1 occurrence
OUTSIDE the pool's own records), and an exporter anchor (pass 2:
`build_export` must fail naming the absorption gap; the
composition's residue count must equal the byte measure).

**The headline (fact): the pinnable subnode-only-blocked population
corpus-wide is 0.**  The fail-closed composite population is exactly
the stage-9 residual 12 — the lever has no store to act on:

- 310 of 322 fail-closed rows carry no composite pool at all
  (no-composite-store: 178 missing-geometry-store + 132
  undecoded-variant whose exporter failures are other families —
  "no 01 06 vertex pool decoded" (G2 P8), "facet references beyond
  the pool", etc.; probe and exporter agree store-by-store).
- The 11 UV-family stores: 0 decoded reps under the law ladder
  (walk-mismatch co-blocker; residues 40..1,056, byte-verified all at
  pool-record positions, none pinnable — see correction 2 below).
  Their blocker remains the family's open element semantics.
- bad44bdf (dev, 24.7 MB body, 3 pool groups = 93,522 vertices /
  93,518 distinct, 3 flat-law decoded reps, refs 3/3 in-bounds):
  uncovered = 1 vertex, diagonal == union (no pairing slack), and
  that vertex occurs EXACTLY ONCE in the whole body — inside the
  pool's own `05 08 01` records (0 occurrences elsewhere).  There is
  no sub-node record re-listing it: nothing for an element-index law
  to pin.  UNPINNABLE.  The exporter anchor agrees to the vertex:
  the composition's own absorption raise names residue 1 == the
  byte measure.

**Ceiling correction (fact):** "the subnode law <= +22 on the
corrected reading" corrects to **0** — the census's 22 was its
early-break artifact (S9-census-artifact), the stage-9 residue within
the 93 (bad44bdf) is unpinnable, and no store outside the 93 is
subnode-only-blocked at the stage-10 baseline.  Stage-11 Phase B's
gate (>= 2 stores blocked AND the element-index law pinnable from
committed evidence) is NOT met on both arms: Phase B does not run.

**DATED CORRECTION 1 — bad44bdf's gap label:** the stage-8 note's
open 2 and the stage-9 residual named "bad44bdf's 1 subnode-index
vertex"; the label was the census column's semantics
(`subnode_only_vertices = len(pset - covered)`, stage-9 probe —
a count of uncovered vertices, never a byte verification of sub-node
presence).  Byte truth: the vertex occurs once, in the pool's own
records.  The store's honest class is **unpinnable pool residue**,
not "subnode-index gap".

**DATED CORRECTION 2 — the UV family's "vertex sub-node re-lists
the pool verbatim" clause is the census record-set artifact:** the
stage-8 UV paragraph claimed "a vertex sub-node (`04 ff ff` +
`00 00 00 01` + kind + count + count x `05 08 01` + 12 B f32) whose
record count equals the pool size and whose records re-list the pool
verbatim (248/248 on 12dc542e, 203/203 on 8e8500b1)".  Measured
now: on ALL 11 UV stores every `05 08 01` marker in the body sits
inside the pool's own records (12dc542e 248 in / 0 out; 8e8500b1
203 in / 0 out; family total 3,166 in / 0 out) — the counts equaled
the pool sizes because the counted record set WAS the pool's own
wrapper records (the stage-9 pairing-artifact mechanism,
S9-census-artifact, applied to the record set instead of the pairing
loop).  The twins' second route does not exist on the UV family's
bytes; the family's element semantics stay the (unchanged) blocker.

Reproduction:

```
ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
python3 -I scripts/triage/stage11_subnode_population_probe.py
# -> docs/evidence/data/stage11-subnode-population.csv (322 rows)
# anchor subset (bad44bdf, the unpinnable residue):
python3 -I scripts/triage/stage11_subnode_population_probe.py --sha16 bad44bdf
# -> docs/evidence/data/stage11-subnode-population-anchor.csv (1 row)
```

Corpus run ~3 s wall (322 fail-closed parts; the exporter anchor runs
only on the 12 composite fail-closed stores).  Claims row:
`MW16-stage11-population` in `mixedwrite-reps-claims.csv`.  Phase B:
not run (gate unmet on both arms — 0 pinnable stores, and no
committed-evidence law question even arises).
