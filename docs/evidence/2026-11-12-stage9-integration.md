# Evidence: stage-9 integration of the stage-8 mixed-write laws into the exporter (2026-11-12)

Ticket #34 (G6 stage 9): the stage-8 census's three locator/predicate
artifacts land in `src/catpart/geometry/composite.py` (branch
`t3/integrate-stage8-locator-artifacts`), ported from the committed
reference implementation (`scripts/triage/mixedwrite_decode.py` — not
re-derived):

- **(a) The list-node window** (artifact 1): the walk-mismatch path's
  per-rep scan runs over the FULL body (`_scan_token_nodes`, the
  exporter's own NODE_MAGIC-to-NODE_MAGIC convention).  The single-rep
  locator keeps the stage-3d window (first STRIP_RE match): a
  full-window single-rep locator re-selects the payload on 823/857
  walk-OK composite stores (the "largest span" heuristic flips to
  later nodes once spans extend past the records — measured, pre-
  declaration), so the full-body scan is scoped to the walk-mismatch
  path, where the artifact's entire incidence lives (a store whose
  window truncates its node fails the primary walk and lands there).
- **(b) The zero-block extent** (artifact 2): the walk-mismatch path's
  table law takes the zero-block EXTENT as a candidate (1..k groups);
  exactly one extent must yield the walk-exact decode, ambiguity stays
  fail-closed.  The committed `layout()` is untouched: a store whose
  committed skip overshoots into the table fails the primary walk
  (the artifact IS a walk mismatch), so the candidates cover the full
  incidence without re-routing walk-OK stores.  Extents inside the
  zero block read a zero count and cannot walk exact (the committed
  skip position is the only alternative the law can select).
- **(c) The flat law** (artifact 3): the stage-7 container PART-1
  reading joins the raw law as the third per-node fallback — c1 full
  triples straight after the 4-B tail field, start pinned by
  counts_end, NO escape required, all-nice under the exporter
  predicate (the raw scan's 1e-6 floor rejects real near-zero
  coordinates), x-ascending or the pool fully re-listed.  Per-node law
  order = the census's: table (extents) -> raw (escape-pinned) -> flat.
- **(d) Per-rep before fail-closing**: on a walk-mismatch the raw-array
  law runs FIRST, unchanged (the stage-6 trigger discipline and its 28
  exports' byte-identity); when it declines, the stage-8 composition
  runs over ALL token nodes — pool group k absorbed by the k-th
  law-decoded rep's region (diagonal; exact f32, then the stage-4b
  noise tolerance capped at 10,000-vertex pools), per-rep M2b refs
  gate, per-rep records/triangulation, stage-5 merge.  A store exports
  only when EVERY pool vertex is region-absorbed.
- **(e) The sub-node route stays fail-closed**: vertices re-listed only
  by the `05 08 01` records have unpinned element indices — they keep
  the store fail-closed for export, with the gap named.

New stage name: `identity-mixedwrite-reps` (the A/B CSV's `stage`
column maps every changed row; `rep_laws` rides the composite info
block additively — schema `additionalProperties: true`).

Labels: **fact** = measured/cited from a committed artifact;
**inference** = derived, reasoning shown; **unknown** = open.

## The amended declaration basis (fact, pre-declaration probe)

The brief's delta table (the stage-8 note's D1-D6) declares +60 exports
(the census's "strict 60": verdict reps-full AND pool_subnode_only ==
0).  The pre-declaration absorption probe
(`scripts/triage/mixedwrite_absorption_probe.py` ->
`stage9-absorption-probe.csv`, 93 rows, committed with this note)
re-measures pool absorption WITHOUT the census's early break and finds
the census's pairing artifact:

- The census pairs each pool group to the FIRST rep that fully matches
  it, and its sub-node record set (every `05 08 01` occurrence in the
  body) includes the pool wrappers' own vertex records — so on
  multi-rep stores, pools 1+ "match" at rep 0 (via the pool's own
  records) before their diagonal rep's region is ever tested.
- Consistency check: all 60 strict stores are single-rep; ALL 22
  "subnode-assisted" stores are multi-rep.
- Re-measured without the break: **81 of the 82 reps-full stores are
  fully region-absorbed DIAGONALLY** (60 single-rep + 21 multi-rep; all
  dev; exact f32 — 0 noise, 0 refs violations, decoded_reps ==
  pool_groups on every one).  Only bad44bdf (1 of 28,980+ pool
  vertices in no decoded region) and the 11 UV-family stores (0
  decoded reps) stay fail-closed.

The exporter's composition therefore exports **81 stores, not 60**.
D1/D4 below are AMENDED accordingly (the brief allows an amended delta
committed before the run); every other declaration is the note's.

## Declared expected A/B delta (2026-11-12, written BEFORE the corpus run)

External-changeset gate rule (dispatch-recipes.md): the expected delta
is stated first; any unexplained delta is a stop-and-re-root-cause
gate.  Baseline: `stage6-identity-export-files.csv` @ `4e705a5` (the
post-stage-6 seam A/B) — 1,442 rows; exports 1,039 (composite 927 =
747 table-walk + 152 per-rep + 28 raw + 112 clean); L2 gate pass 941
(dev 886/1,381 = 64.16%, held-out 55/61); error classes:
undecoded-variant 225, missing-geometry-store 178; failed checks:
empty-mesh 71, not-manifold 27 (fact).  The 93 trigger stores are all
baseline `undecoded-variant` (fact, probe join).

| # | family | expected delta | source |
|---|---|---|---|
| D1 (amended) | the mixed-write family | **+81 composite exports** (the 81 region-absorbed stores: 60 single-rep strict + 21 multi-rep; all dev; all baseline undecoded-variant; 0 replacements — named per store in `stage9-absorption-probe.csv`).  The stage-8 note declared +60 (its strict 60); the probe's no-early-break re-measure amends to +81 — the census's "22 subnode-assisted" class is its early-break artifact (above). | fact (probe CSV) |
| D2 | L2 gate | the new exports' L2 split is **unknown, measured not projected**: passes form a strict subset of D1's exports.  The note's share inference (the stage-6 raw family's 15 pass / 13 empty of 28) would project ~43 pass + ~38 empty across 81 — declared as the share-based expectation, INFERENCE only (the 21 multi-rep merged meshes may split differently; the manifold/empty-mesh/plane gates are the A/B's to measure). | declaration + inference |
| D3 | held-out | **0 held-out movement**: all 81 stores are dev-split (probe CSV); the 4 held-out UV-family stores keep undecoded-variant; held-out stays 55/61. | fact (probe) |
| D4 (amended) | fail-closed trigger stores | **12 of the 93 keep undecoded-variant** with the gap named (bad44bdf: 1 subnode-index vertex + the 11 UV-family stores — the note declared 33 = 22 + 11; the probe amends to 12 = 1 + 11).  0 error-class changes elsewhere: undecoded-variant 225 -> 225 - 81 = 144; missing-geometry-store 178 unchanged. | fact (probe) + inference |
| D5 | preservation (hard gate) | walk-OK + per-rep + unabsorbed rows **byte-identical** (the primary path's code and inputs are unchanged — the full-window scan and the extent law live only in the walk-mismatch branch); the 28 raw rows byte-identical (the raw path returns first, unchanged inputs); the 12 fail-closed rows keep error_class (only the replay detail gains the composition suffix); **0 lost exports, 0 lost passes; replay digests identical on every baseline-exported row** — a violation = STOP. | declaration (code path) |
| D6 | performance | the composition runs only on the walk-mismatch fail-closed stores (93): per store one node scan + per-node law probes + per-rep records; the census ran the same work corpus-wide in ~27 s; the extent candidates add <= k walks per node (k = the zero-group run, measured max 75); the noise fallback is capped at pools <= 10,000 — no explosion expected (inference). | inference |

Interactions named in advance: the 81's per-rep records parse under the
stage-5 width laws unchanged (u24be only above 65,535 elements); the
plane tiebreak applies unchanged; the flat law's pool-absorption
criterion uses the FULL pool vertex set (the census's `decode_node`
port, verbatim).  A baseline-exported row regressing to fail, or any
D5 digest change, = STOP.

## Observed A/B (2026-11-12, post-declaration run)

(filled in after the run — declared-vs-observed table + per-row
accounting + the claims ledger `stage9-claims.csv`)

## Reproduction

```
ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus   # gitignored, read-only
.venv/bin/python -I scripts/triage/mixedwrite_absorption_probe.py    # pre-declaration probe
.venv/bin/python -I scripts/triage/ab_identity_export.py --out-name stage9-identity-export-files.csv
# replay at both ends (baseline end = the 4e705a5 src in a staging tree):
.venv/bin/python -I scripts/triage/replay_export_seam.py --out-dir <dir> --out-name stage9-replay-stage9.csv
```

Committed artifacts: `stage9-absorption-probe.csv` (93 rows, pre-
declaration), `stage9-identity-export-files.csv` (the seam A/B),
`stage9-replay-*.csv` (PLY + L2-fields digests at both ends),
`stage9-claims.csv`, this note.
