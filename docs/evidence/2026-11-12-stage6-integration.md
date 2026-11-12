# Evidence: stage-6 integration of the stage-4a raw-array law into the exporter (2026-11-12)

Ticket #34 (G6 stage 6): the raw-array decode law — the walk-mismatch
residue family — lands in `src/catpart/geometry/composite.py` (branch
`t3/integrate-raw-array-decode`, base `cd5dc44`), ported from the
committed reference implementations (`scripts/triage/classify_residue_family.py`
`--raw` + `scripts/triage/probe_residue_anchor.py` — not re-derived):

- **The law as committed** (docs/evidence/2026-11-10-node-streams.md
  section "Stage 4a-residue"): a walk-mismatch composite payload
  continues past the header as RAW f32 triples — ``[token][count1]
  [count2][tail][elem_decl x [x][y][z] stride 12, x ascending][FF]
  [count3 u32le][trail]``; the start is pinned by the trail-escape
  condition ``payload[start + 12*elem_decl] == 0xFF`` over the scan's
  4-aligned candidate range 32..64, and the law applies only when that
  condition selects EXACTLY ONE candidate.  Strong fit = nice >= 0.98
  AND x-ascending >= 0.98 over the full elem_decl span (the scan's
  per-triple rates, its coordinate predicate and its 1e-6 pair
  tolerance, ported verbatim) AND the pool re-listed verbatim in the
  triples (exact f32 — the scan's ``pool_absorbed_raw``).
- **The trigger** (the brief's ordering requirement): the raw path runs
  ONLY where the table walk raises with the census family signature —
  the layout raises, or the probe-semantics walk (all slots, bounded
  only by the payload, no coordinate aborts — ``_walk_mismatch``)
  does not end exactly at the declared region end.  A store the table
  walk handles never reaches the branch (it lives inside the walk's
  ``except``); a walk-EXACT store with junk coordinates is not the
  family (the walk's own failure is re-raised); the stage-5 per-rep
  path is untouched (it only sees walk-OK stores).  When the raw
  reading does not cover the store either, BOTH gaps are named in the
  ``undecoded-variant`` detail — the classification never changes.
- **Named opens stay open**: the tail field's semantics, count3's
  semantics (recorded as ``raw_count3``, never validated), the weak-fit
  and no-fit stores (fail-closed, named per store).

Labels: **fact** = measured/cited from a committed artifact;
**inference** = derived, reasoning shown; **unknown** = open.

## The trigger population (fact, `stage6-raw-trigger-probe.csv`, committed with this note)

Store-level scan through the committed census locator
(`classify_residue_family.locate_payload`), exporter-side walk and raw
criteria (`.venv/bin/python -I scripts/triage/raw_array_trigger_probe.py`):

- The trigger population is EXACTLY the census's 121 walk-mismatch
  stores (99 walk-mismatch + 22 layout-raise; forms 104 big + 17
  small; splits 117 dev + 4 held-out).  The exporter's walk detects
  61 of the walk-mismatch stores by overrun and 38 by a non-finite
  coordinate BEFORE the walk ends (the census's probe walk prunes
  coordinates and reports the end mismatch instead — same stores,
  different detection point; the signature check routes both).
- 829 composite stores walk OK (never routed — the
  never-swallows property, measured); 492 parts have no token-bearing
  list node through this locator.
- Escape-candidate distribution over the 121: **84 stores select 0
  candidates, 37 select exactly 1, NONE select more than one** (the
  multi-candidate fail-closed arm is corpus-vacuous).
- Verdicts at the pinned start: **28 raw-export** (all strong-fit AND
  absorbed), 6 weak-fit (below the 0.98 bar), 3 pool-unabsorbed, 84
  start-unpinned.

### Reconciliation with the committed scan (fact, joined rows)

`residue-raw-scan.csv`: 121 stores, 80 fitted, 35 strong (nice/asc >=
0.98 at the scan's BEST-RATE start), 29 absorbed among the strong.
The law's start rule is the trail-escape, not the best rate — the
pinned-start re-measure reconciles the sets:

- Of the 35 scan-strong: **28 export at the pinned start** (identical
  starts on 27/28 — the anchors' 40/48; rates 0.9831..1.0),
  3 stay fail-closed pool-unabsorbed (`0f18f772`, `948aa851`,
  `d696356b` — scan-absorbed=False on all three, consistent),
  3 stay fail-closed start-unpinned (`81ad336b`, `cb49f9f4`,
  `e23423d6` — also scan-non-absorbed),
  and **1 store, `f21255ac`, is weak-fit at its pinned start** (scan:
  start 44, nice 1.0, asc 1.0, absorbed; the escape condition pins
  start 52 — a +4 shift reads (y,z,x') triples, nice 0.9983 but
  x-ascending 0.5161, exactly the shifted reading the 4a note
  describes).  This is the one store where the committed start rule
  costs an export the scan's best-rate reading allowed: the law's
  start rule is the escape, the scan's best-rate start was the
  analysis tool — the port keeps the law, and the store is named
  fail-closed rather than exported on a start the law does not pin.
- The 29 -> 28 delta is exactly that store.  The note's "unique start
  in 32/39 scan-fit stores" reconciles as: 32 = the scan-strong &
  escape-unique stores (28 + 3 + 1, exact); the 39 denominator does
  not reproduce against this probe (measured: 37 escape-unique among
  the 121 and among the scan-fitted; 0 multi-candidate stores) — no
  claim of this integration rests on it (dated correction).
- All 6 scan-strong non-exporting stores: baseline rows are
  undecoded-variant and stay failed (only the detail text gains the
  raw gap).

## Declared expected A/B delta (2026-11-12, written BEFORE the corpus run)

External-changeset gate rule (dispatch-recipes.md): the expected delta
is stated first; any unexplained delta is a stop-and-re-root-cause
gate.  Baseline: `stage5-identity-export-files.csv` @ `cd5dc44` (the
post-stage-5 seam A/B) — 1,442 rows; exports 1,011 (composite 899);
L2 gate pass 926 (dev 871/1,381 = 63.07%, held-out 55/61); error
classes: missing-geometry-store 178, undecoded-variant 253; failed
checks: empty-mesh 58, not-manifold 27 (fact).

| # | family | expected delta | source |
|---|---|---|---|
| D1 | the raw-array family (the 28 escape-pinned raw-export stores) | **+28..+30 composite exports**, all dev-split (the 28 measured store-level at the committed start rule + up to 2 census-scope-blind stores — the seam's 3a recovery reach exceeds the census locator; stage-5 measured 4 such on the 148-store per-rep family).  The brief's +29..+31 cited the scan's 29 absorbed strong-fit; the committed START RULE re-measures 28 (f21255ac weak at its pinned start, above) — the honest range moves down accordingly.  All 28 baseline rows are undecoded-variant, so each is a new export, no replacement. | fact (probe CSV) + inference (seam reach) |
| D2 | L2 gate | the new exports' L2 split is **unknown, measured not projected**: the manifold/empty-mesh gates cut some (stage-5 family precedent: 117 pass / 19 not-manifold / 12 empty-mesh of 148 = 79% pass).  Declared: passes = a strict subset of D1's exports. | declaration |
| D3 | held-out | **0 held-out movement**: all 28 stores are dev-split (probe CSV); held-out stays 55/61, dev 871 -> 871 + (D2's passing share). | fact (probe) |
| D4 | fail-closed trigger stores (121 - 28 = 93) | error_class UNCHANGED (undecoded-variant): the raw gap joins the detail text (CSV rows identical — the A/B CSV does not carry details; the probe CSV names each store's gap).  0 of them export. | fact (probe) |
| D5 | walk-OK stores (829 composite) + per-rep + unabsorbed paths | **0 changed rows**: the trigger lives inside the table walk's except branch; walk-OK stores take the identical code path; the per-rep path is unreached by this change.  Includes the stage-5 gains (per-rep 152, u24be, tiebreak rows) and the clean 112. | fact (code path) |
| D6 | error classes | undecoded-variant 253 -> 253 - 28 = 225; missing-geometry-store 178 unchanged.  (Inference: no other class touches the composite decode.) | inference |
| D7 | preservation (hard gate) | exports 1,011 -> 1,039..1,041, pass set a SUPERSET of 926, **0 lost exports, 0 lost passes**; clean 112 unchanged; L2-fail rows keep their failed_check (the raw path creates exports, it does not alter existing ones).  A lost pass or lost export = STOP. | declaration |
| D8 | replay digests (replay_export_seam.py at BOTH ends, baseline = `cd5dc44` src) | ply_sha256 + l2_fields_sha256 identical on every row EXCEPT D1's new exports (no baseline row to differ from) — every baseline-exported row byte-identical.  A digest change on any baseline-exported row = STOP. | declaration |
| D9 | performance | no explosion: the raw path adds one escape scan (<= 9 candidate checks) + one array rate pass per walk-failed store only; walk-OK stores pay nothing.  Slowest export stays ~1.4 s. | inference |

Interactions named in advance: a raw store's records parse under the
stage-5 width laws (u24be only above 65,535 elements — the raw family's
elem_decl values are far below, measured max in the scan 245,621 is a
NO-fit store; the 28's elem_decl range is bounded by their payloads);
the plane tiebreak applies unchanged.  A baseline-exported row regressing
to fail, or any D8 digest change, = STOP (D7/D8).

## Observed A/B (filled AFTER the run)

Pending: the corpus run (`ab_identity_export.py --out-name
stage6-identity-export-files.csv` + the two-end replay) follows this
commit; this section records declared-vs-observed per D-row.
