# Evidence: the per-rep decomposition law (unabsorbed pools) and the width-law gaps behind the not-manifold exports (2026-11-11)

Ticket #34 (G6, stage 4b): two decode-class residues, one ticket, two
analyses.  **(1)** On the walk-exact composite stores whose pool is not
re-listed by the node list (the stage-3d `unabsorbed-pool` family —
92 big + 55-56 small), where do the missing pool vertices' element
slots come from?  **(2)** 29 composite stores decode fully, export,
pass the planarity battery, and fail only the runner's manifold check —
what is the non-manifold signature, and does G3's strip-degenerate skip
convention applied ACROSS loop boundaries resolve it?  Analysis +
decoder scripts only — `src/` untouched, no fitness writes, no
publication.

Method: `scripts/triage/unabsorbed_pool_law.py` (analysis 1 census,
one row per composite store in `unabsorbed-pool-files.csv` + one row
per decoded rep in `unabsorbed-pool-reps.csv`) and
`scripts/triage/not_manifold_audit.py` (analysis 2, one row per
not-manifold export in `not-manifold-files.csv` + one row per degree>2
edge use in `not-manifold-edges.csv`).  Both replay the committed
decode machinery (`catpart.geometry.composite`,
`decode_big_form_points.py`'s battery) read-only; the export seam is
replayed through `catpart.geometry.export._export_data` unchanged.
Deterministic, sorted manifest order; corpus symlinked read-only;
binaries not committed.

Labels: **fact** = byte-measured here and reproducible from the CSVs;
**inference** = interpretation of measured bytes, named as such;
**unknown** = open.  The house bar (>= 0.98 on scope) applied
mechanically; below-bar claims stay candidate.

## 1. The per-rep decomposition law (analysis 1)

The headline: **a composite store body is a sequence of reps, and the
stage-3d "unabsorbed pool" family is the single-rep reading applied to
multi-rep stores.**  Rep k = (the k-th `01 06` pool wrapper, the k-th
walk-exact token-bearing list node, the strip records in that node's
territory), and

- **REP-law (fact on the census):** the k-th pool group re-lists
  **verbatim (exact f32)** in the k-th walk-exact node's region —
  per-rep absorption holds on **107/148** of the stage-3d unabsorbed
  family outright.
- **REP-noise (fact, 4 stores, 6 vertices):** the residue on 4
  single-pool-group stores is double-rounding noise — the pool vertex
  and its region re-listing differ by at most **1.25e-08 relative**
  (e.g. 0a64c44c's pool `(30, 5, -1.22461e-15)` vs the region's
  `(30, 5, 0)`).  Under a noise-aware equality (per-coordinate
  relative tolerance 1e-5 — the measured gap between the noise deltas
  and the smallest real coordinate difference is 4 decades) absorption
  holds on **111/148 (0.750)**.
- **REP-refs (fact):** references are 0-based element indices in their
  OWN rep's region (M2b identity per rep).  elem_decl == max gated
  u16be ref + 1 on **315/369** ref-carrying family reps (0.854, vs the
  absorbed control's 400/481 = 0.832); only **4 rep rows on 3 stores**
  carry out-of-bounds gated refs (named residue below).  The stage-3d
  "refs beyond the element space" observations were other reps'
  references measured against rep 0's element count (02ff71f5: max
  gated ref 6,278 = rep 1's elem_decl 6,283 - 1 — N2 exact for rep 1).
- **REP-battery (fact):** the loop plane battery (committed stage-3b
  criterion) over the family's per-rep normal-carrying loops:
  **20,486 loops = 15,631 coplanar + 4,674 skip-ref + 0 beyond +
  181 nonplanar**; the committed multi-plane decomposition of the 181
  (110 multi-plane + 56 single-plane-uniform + 13 4-plus-plane +
  2 no-triangles) gives **coplanar + skip-ref + multi-plane =
  20,415/20,486 = 0.9965** — above the 0.98 house bar.

Byte evidence for the structure (fact, worked stores):

- 02ff71f5b7a33d13: 5 pool groups (143, 374, 411, 264, 54) and 5 token
  nodes; each pool 100% verbatim in exactly its own node's region
  (diagonal, byte-verified per rep); per-rep N2 exact on all 5 reps
  (1,775/1,776, 6,278/6,283, 5,618/5,619, 3,579/3,580, 2,790/2,791);
  battery 271 loops, 0 nonplanar.
- 351426c065146ee9 (the extreme "pool 2,166 vs elem 8" store): 5 reps;
  rep 3 carries the 2,134-vertex pool, elem_decl 2,958, pts 2,812,
  max ref 2,957 = elem-1; the stage-3d reader saw elem 8 because its
  list-node window ends at the FIRST strip record — rep 0's node only.
- 61d72b598f9c21fa: 2 pool groups of 8 (the y = +/-26.8 box corners);
  2 nodes (elem 764 each); each re-lists its own group verbatim — the
  "missing mirror corners" sit in the second rep's region.
- dd213a2eb240da3d: 4 pools (32, 2, 4, 6) + 4 walk-exact nodes;
  diagonal verbatim 100% (the small pools are also geometric subsets
  of rep 0's region — content pairing alone is ambiguous, the
  body-order diagonal is the pairing law).

The stage-3d reader's window is the artifact (fact): `find_list_node`
searches `[body_lo, first strip record)` — on multi-rep stores that is
rep 0's node (often a stub), while `poolv` concatenates EVERY rep's
wrapper; absorption then fails on the other reps' vertices and refs
"beyond" are other reps' references.  The single-rep reading stays
correct for single-rep stores (the control: **681/681 absorbed stores
re-verify per-rep verbatim**, 680 of them single-pool; the one
multi-pool control, aed33a66, has both pools inside the largest node's
region).

**The refuted candidates (fact, measured):** the brief's three
hypotheses for the unexplained slots —

1. *the 2-bit table's skip slots are pool-implied entries*: REFUTED —
   missing <= skip_slots on only 36/148 stores (missing == skips on 1),
   and the missing pool vertex's lex-bracket among the written points
   contains a skip slot on **3/148**; under the lex law a pool vertex
   at a skip slot must sort between its written neighbours, and on
   145/148 stores the brackets have no skip.  (The skip slots remain
   the curve entries, U4.)
2. *region order differs from element order*: REFUTED structurally —
   elem_decl == pts_written + skip_slots holds on 148/148 (the table
   law leaves no unaccounted slots for pool insertions), and the
   per-rep identity with N2-exact refs needs no re-ordering.
3. *a third element source*: unnecessary on 111/148 — the per-rep law
   explains those stores with exactly the two established sources
   (pool + node region) plus the curve entries.

**Residue (open, named):** 37 stores carry >= 1 pool group absorbed in
NO decoded region — **138 pools**, of which **179** others are
verbatim-absorbed in a non-diagonal decoded rep ("shifted": absorption
holds, the naive diagonal-over-decoded pairing mis-aligns when earlier
reps' nodes fail the walk).  On 35/37 stores unpaired == pool_groups -
decoded_reps: the unpaired pools belong to reps whose list node failed
the walk (the U3-variant second layout family, now at rep granularity).
The 2 exceptions (4abf3eeaf892be44, 6ab9e107b7f30308 — near-duplicate
stores) decode all 14 reps and still miss exactly **2 pool vertices
each** at a real 0.001 x-offset (`x=5.0` vs the region's
`x=5.0009999`) — a genuine absorption residue of 4 vertices corpus-wide
(noise excluded).  Refs residue: 4 rep rows OOB (4d1b6c35 rep 11,
d748c70c reps 8+13, e8d9a358 rep 2) — d748c70c's max refs sit at the
u16be ceiling (65,359), the signature of the missing u24be width
family (section 2); the other two are records whose re-parse is not
pinned by any committed law.

**Reconciliation (fact):** the decode-level census counts 148
unabsorbed walk-exact stores = 92 big + 56 small (payload > 4096 B;
`stage3d_node_bytes` column); the stage-3d export seam reported 92+55 —
one small store's seam path differs from the decode-level audit; the
committed stage-3b CSV carries the same 56.  All stage-3d figures
(677 composite exports, 29 not-manifold) are seam-scope and unchanged.

## 2. The not-manifold classification (analysis 2)

Population: the 29 composite exports whose only failed L2 check is
`not-manifold` (28 dev + 1 held-out, d4127e6b; identity-export-files.csv).
3 of the 29 carry ZERO skip slots — curve entries play no role in the
signature.

**Signature (fact, per-store rows in not-manifold-files.csv):** the
corpus edge-degree histogram over the 29 exports is deg1 41,257 /
deg2 43,688 / **deg3 217 / deg4 52 / deg5+ 232**.  28 of 29 stores
have a tiny signature (1-12 excess uses over 1-7 non-manifold edges;
17 stores have exactly ONE deg-3 edge with excess 1); **13bb5c0c49616ade
dominates** (177 deg-3 + 44 deg-4 + 229 deg-5+ edges, 4,323 excess
uses, 724 duplicate triangles — degrees up to 162).  Provenance of the
5,398 triangle uses on degree>2 edges: **cross-record 5,209 (96.5%)**,
same-loop 183 (all 13bb5c0c), cross-loop-same-record 6.

**The cross-loop skip test (the brief's hypothesis):** extending G3
F7's strip-degenerate skip across loop boundaries (drop a triangle
that duplicates a coordinate-triangle another loop produced, or whose
edge is already used twice) re-measures **manifold on 29/29** by
dropping 2,245 triangles.  So the gate symptom is universally
suppressible — but this is a degree cap (it constructs manifoldness),
not an explanation, and it masks the real cause:

**Root cause: the width rank, not strip joins (fact, byte-evidenced).
Two gaps in the stage-3b width law (`u8`/`u16be` candidates, ranked
exact-tiling > no-repeated-refs > no-oob > narrower):**

1. **u24be is missing.**  13bb5c0c's element_count 236,385 > 65,535
   cannot index in two bytes.  Byte-verified: record 182386003
   (`01 4a 01 ff`, n=4, 12-B normal) tiles EXACTLY at u24be k=1 —
   8 + 4 + 12 + 1 + 4x3 = 33 B = the header-to-header delta — with refs
   178,404/177,456/178,403/177,455; record 182388608's n=9 refs are
   9 x 3 B after counts [5,4] (first ref 163,528).  Under the u16be
   enumeration these records misread into low-index junk (the 724
   duplicate triangles, the degree-162 edges, the 4,323 excess uses).
   The u24be re-parse yields **19,133 width-3 records**, 5,855 ->
   **30,292 triangles**, and the loop battery validates the reading:
   3,960 normal-carrying loops = 92 coplanar + 3,868 skip-ref +
   **0 nonplanar** (max residual 1.5e-05).  u24be covers the whole
   corpus: MAX_ELEMENT_COUNT 10,000,000 < 2^24.
2. **The narrow-width tiebreak lacks the plane law.**  Records whose
   byte stream carries interleaved non-STRIP_RE families (e.g.
   ef30cb2f's `01 4d 03 01 ...` blocks) never tile onto the next
   STRIP_RE header, so u8 and u16be candidates tie on
   (tiling, repeats, oob) and the narrower wins — ef30cb2f rec 261274
   (`01 4a`, normal (0.894, 0, 0.447)): the u8 loop `[1, 23, 0, 243]`
   is **nonplanar** against the stored normal, the u16be loop
   `[279, 243, 277, 242]` is **coplanar**, and the committed rule
   chose u8.  The u8 triangle was the non-manifold use.

**The width re-test (fact, analysis-only):** re-parse each store's
records with candidate widths (1, 2, 3) and the rank
(tiling, repeats, oob, NONPLANAR-LOOP-COUNT, width, k) — the committed
enumeration with width 3 added and the loop plane law demoting
nonplanar candidates — then re-triangulate and re-measure:
**21/29 stores re-measure manifold with no triangle suppressed**
(13bb5c0c included: 15 residual non-manifold edges, down from 450).
The width re-test is the honest resolution; the cross-loop skip
convention is not (on 13bb5c0c it would keep exporting the 5,855
misread triangles instead of the 30,292 the u24be law decodes).

**Residual 8 stores (open, named):** their remaining non-manifold uses
sit in **0x42 records (no stored normal) whose content does not tile
onto the next STRIP_RE header** — interleaved non-matching families
leave 80+ unaccounted bytes per record — so NO in-store arbiter exists:
the plane law is silent (no normal), the tiling law is silent (nothing
tiles), and both widths are in-bounds.  97a0a420923c5c67 is the
structured flavor: **13 same-shape records** (`01 42 02 ff`, n=9,
delta 74, counts [5,4]) at a 3,233-B stride, each triangulating one
triangle over the shared edge (written 3,4) — either the encoded
connectivity genuinely carries a 13-fan there, or those records are
containers of an unpinned family.  The other 7 stores carry 1-2 such
edges each.  The 4 analysis-1 ref-residue rows (d748c70c's u16be-ceiling
refs) are the same width gap seen from the decode side.

**Consequence for the exporter (named, NOT implemented — src/
untouched):** the width-law extension (u24be candidate + the plane-law
tiebreak) belongs in `composite.parse_strip_records` at the next
integration stage; the analysis re-test covers the 29 failing exports
only — its effect on the 610 passing composite exports (and the clean
class) is unmeasured here and needs the integration A/B.  The per-rep
decomposition (section 1) is the larger integration: multi-rep stores
need per-rep decode (each rep's pool absorption, refs gate, battery,
and triangulation) and a decision on how reps merge into one exported
mesh — named for the next stage, not decided here.

## Claims

| claim | statement | rate | label |
|---|---|---|---|
| R1 | a composite store body is a sequence of reps (k-th `01 06` pool wrapper + k-th walk-exact token node + that node's record territory); the stage-3d unabsorbed family is the single-rep reading on multi-rep stores | 148-store family re-classified; control 681/681 per-rep verbatim | fact |
| R2 | per-rep pool absorption verbatim (f32-exact) | 107/148 unabsorbed stores; control 681/681 | fact |
| R3 | per-rep absorption under noise tolerance 1e-5 (measured noise <= 1.25e-8 rel, smallest real difference 2e-4) | 111/148 (0.750) | fact |
| R4 | per-rep identity refs (M2b per rep): N2 exact | 315/369 family reps (0.854); control 400/481 (0.832) | fact |
| R5 | per-rep loop battery holds (coplanar + skip-ref + multi-plane, committed criterion) | 20,415/20,486 = 0.9965 family loops | fact (above the 0.98 bar) |
| R6 | skip-slots-as-pool-entries refuted (lex-bracket correlation) | brackets with a skip: 3/148 stores | fact (refutation) |
| R7 | absorption residue: pools of walk-failed reps unpaired (unpaired == pools - decoded on 35/37) + 4 genuinely un-re-listed vertices at a 0.001 offset (2 near-duplicate stores) | 138 unpaired pools on 37 stores | fact / inference for the mechanism |
| R8 | not-manifold signature: cross-record edge uses dominate | 5,209/5,398 uses (96.5%); 20 stores exactly one deg-3 edge | fact |
| R9 | cross-loop skip convention suppresses the symptom | 29/29 manifold after dropping 2,245 triangles | fact (gate-level, not causal) |
| R10 | width gap 1: u24be refs (element_count > 65,535); byte-verified exact tiling; u24be battery validates | 13bb5c0c: 19,133 w3 records, 30,292 triangles, battery 92 cop + 3,868 skipref + 0 nonplanar | fact |
| R11 | width gap 2: narrow-width tiebreak without the plane law misreads normal-carrying records over interleaved families | ef30cb2f rec 261274: u8 nonplanar vs u16be coplanar | fact |
| R12 | width re-test (widths 1-3 + plane tiebreak) resolves the export | 21/29 manifold, 0 triangles suppressed | fact (analysis-only, 29-store scope) |
| R13 | residual 8: normal-less non-tiling 0x42 records, no in-store arbiter; 97a0a420's 13-record 3,233-B-stride fan | 8 stores | fact / unknown (the interleaved family) |
| R14 | corpus-wide effect of the width re-test on the 610 passing exports; per-rep exporter integration (how reps merge into one mesh) | — | unknown (next stage) |

## Reproduction

```
.venv/bin/python -I scripts/triage/unabsorbed_pool_law.py
# anchor subset:
.venv/bin/python -I scripts/triage/unabsorbed_pool_law.py \
  --include-sha16 02ff71f5b7a33d13,351426c065146ee9,61d72b598f9c21fa,0a64c44c29e6cfa6
.venv/bin/python -I scripts/triage/not_manifold_audit.py
# anchor subset:
.venv/bin/python -I scripts/triage/not_manifold_audit.py \
  --include-sha16 13bb5c0c49616ade,ef30cb2f71dc2c73,97a0a420923c5c67
```

Outputs: `docs/evidence/data/unabsorbed-pool-files.csv` +
`unabsorbed-pool-reps.csv` (analysis 1) and
`not-manifold-files.csv` + `not-manifold-edges.csv` (analysis 2) — all
committed, deterministic.  Both scripts import the committed decode
machinery read-only; no `src/` change, no fitness write.  Baseline at
this base: pytest 294 passed / 7 skipped, ruff clean.
