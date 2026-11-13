# Evidence: the non-composite fail-closed mass, classified to root cause — the stage-12 census (2026-11-13)

Ticket #34 (G6, stage 12): byte-level census of the **310 non-composite
fail-closed stores** at the stage-10 baseline (the largest unexamined
mass after stage-11 closed the subnode-index lever at 0), with a
per-family ceiling table in the stage-1 precedent's format, the
stage-11 review F2 sub-question (the 16 unlocated-bytes files)
answered, and the Phase B gate evaluated. Scope discipline: Phase A is
**analysis only** — src/ untouched; the conditional Phase B (a family
whose law is pinnable from committed evidence) is a separate commit
series on this branch.

Population: the fail-closed rows (`export_ok != 1`) of the accepted
stage-10 A/B (`stage10-identity-export-files.csv`): **322**, of which
the stage-12 own-walker span walk finds composite spans on exactly the
12 stage-11 composite fail-closed stores (11 UV + bad44bdf — set
equality with the stage-11 CSV, zero other), leaving **310** — all
`dev` split (the held-out fail-closed 4 are UV members). The committed
stage-11 classification column is joined for reference only, never
trusted (the stage-11 method).

Method: `scripts/triage/stage12_noncomposite_census_probe.py`
(committed with this note) — the committed geometry modules are
infrastructure (`store`/`pool`/`facets`/`composite`/`export`), the
orchestration and every byte census is the probe's own:

- **span walk**: `export._export_data`'s probe order replicated
  (CATStdCont first; the xdoclink/seebody recovery probes only when
  nothing located and no header raised; within the recovery phase both
  families probe in full); composite = `pool.scan_pool_groups` +
  `has_composite_space` per located span.
- **exporter anchor**: `build_export` per population part (the real
  seam, black box); the failure family = error class + detail head.
- **located-store census** (no-pool, refs-beyond): pool groups/kinds,
  the clean path's own facet scan (candidates, records, max ref,
  skipped markers), a `05 08 01` record census (occurrences, max
  contiguous 15-B run, records outside pool spans), NODE_MAGIC and
  token-bearing list-node censuses (the census `_scan_token_nodes`
  convention), and the stage-6 raw-array signature of the body read as
  stride-12 f32le triples (the committed `_raw_nice` predicate +
  x-ascending rate — measured as a signature, not a decode).
- **unlocated census** (missing-locator): container inventory; V5_CFV2
  hits outside offset 0 with the full N2 header signature; CB0001
  hits; `locate_store` probed on **every block regardless of container
  name** (the stage-3a vocabulary extension test — the law is
  container-independent by construction); every recovered span runs
  the REAL decode path (`_export_store` — relabelled to the
  schema-neutral container tag "seebody" for the measurement run; the
  true containing block is recorded in the probe's own columns) and
  yields its content class + L2-gate outcome as FACT; a locator-free
  whole-file wrapper census (`10 24 04 ff ff 00 00 00` + sub-kind) with
  per-occurrence region attribution; the stage-1 C6 `02 02` edge-table
  walk per `01 02` wrapper.

Full census run: ~1 s wall, deterministic (sorted manifest order).
Data: `docs/evidence/data/stage12-noncomposite-census.csv` (one row per
store, 46 census fields) and
`docs/evidence/data/stage12-unlocated-wrappers.csv` (one row per
wrapper occurrence in the missing-locator files, 177 rows).

Labels: **fact** = measured here and reproducible from the CSVs;
**inference** = interpretation of measured bytes, reasoning shown;
**unknown** = open, carried forward.

## 1. The taxonomy (fact)

The exporter anchor partitions the 310 exactly as the stage-11 review
tabulated (its own `build_export` runs) — **178 + 94 + 38 = 310, zero
other**, now re-derived and committed:

| family | stores (all dev) | anchor error | detail head |
|---|---|---|---|
| missing-locator | 178 | `missing-geometry-store` | "no validated nested stream store in any CATStdCont/CATXDocLinkCont/CATSeeBodyCont region" |
| no-pool | 94 | `undecoded-variant` | "no 01 06 vertex pool decoded from the store body (G2 P8 family)" |
| refs-beyond | 38 | `undecoded-variant` | "facet references beyond the pool" |

## 2. missing-locator — 178 dev: the mandatory lever, measured (fact + arithmetic)

Byte anatomy (one row per store in the census CSV):

- **125/178 carry NO V5_CFV2 header anywhere outside offset 0**
  (the outer magic). 121 of them carry `CATIA_V5 CB0001` catalogs that
  validate as neither store tail form (the header-less law probes every
  block and finds no validating tail — embedded-document / outer-style
  catalogs, G1 N10). These are unreachable for the locate law BY
  CONSTRUCTION — no header and no validating CB0001 tail to relax onto
  (fact).
- **53/178 carry a full-signature V5_CFV2 header (ff x 8 / zeros x 8)
  in a block region the probe loop never visits** — and `locate_store`,
  probed on every block, VALIDATES a store span on every one of the 53
  (fact). Container attribution reproduces the stage-1 census's C11
  candidate-upside figure exactly: CATBRepModeContainer **39**,
  CameraStartupContainer **8**, contmeasure **2**, CATMaterialCont /
  CATCameraContainer / CATElecBehaviourCont / CATSiFiContShuttle **1**
  each (= the stage-1 "39 + 8 + 2, four others 1 each"). Tail laws:
  padded 39, shipped 12, overshoot 2. Zero `malformed-store-header`
  probes corpus-wide (probe_malformed = 0).
- **The 53 recovered spans through the real decode path (fact):**
  **12 export and PASS the L2 gate** (v/t and mesh invariants measured
  through `_export_store` + the runner's `_score_export` logic);
  4 recover composite spans that fail under the committed composite
  laws (2 table-walk-exceeds, 1 primary "does not re-list the pool:
  82 of 86", 1 non-finite coordinate at the raw path); **37 recover
  no-pool content** (the P8 family behind the locator — cap-raisers
  for the content levers, not pass-levers themselves).

The 12 (case table, fact — each verified through the shipped decode):
56080410 (CameraStartup/shipped/table-walk, 356v/124t manifold),
82acf24b, 8f1bb5e3, b2e43013 (CameraStartup/shipped/table-walk),
636b13f6 (CATBRepMode/padded/**identity-per-rep**),
8ecd197d (CATBRepMode/overshoot/table-walk),
d67512e6 (CATBRepMode/shipped/**identity-mixedwrite-reps**),
a5cb3096, b0de68d8 (contmeasure shipped/overshoot),
bb335cff (CATCameraContainer/shipped),
c2a5696e (CATElecBehaviourCont/shipped),
e3963960 (CATSiFiContShuttle/shipped). Spot verification
(5608041010b20335): block at 116,614 named CameraStartupContainer,
V5_CFV2 header at 117,020 with the full N2 signature, SHIPPED tail
law, body kinds `0102/0106/0001` (a composite store), pool 32
vertices, `identity-table-walk` element_decl 488 -> 356 written
points, 124 triangles, manifold True / closed False (a legitimate
open shell). The store was invisible to the shipped locator only
because the probe loop stops after seebody.

- **The stage-11 review F2 sub-question (fact — answered):** the
  16 missing-locator files carrying composite-space wrappers
  (`01 02` edge / `ff ..` opener) re-derive at exactly **16**; ALL 16
  are among the 53 recovered (each has exactly one recovered span, and
  every one of their 72 composite wrappers sits INSIDE the recovered
  span's body [CORRECTED 2026-11-13 (review F2): the 72 counts ALL
  wrapper occurrences on the 16 files — 31 are composite-space
  (`01 02` edge / `ff ..` opener), the other 41 are pool `01 06` /
  other sub-kinds; verified inside: all 31 composite AND all 72
  total]). **12 of the 16 export+pass through the committed
  composite decode; 4 stay composite-fail-closed** (416d14fd,
  434d4bb4, 4902c650, c6eaac5e). The review's "bytes no store locator
  reaches" was locator-relative and stands; the recovery question it
  named resolves: the stage-3a vocabulary extends verbatim (the law
  was already container-independent), and the wrapper bytes were never
  the blocker — the missing probe was.
- **The 125 non-recovered wrappers (fact):** 33 wrapper occurrences on
  13 parts (CATBRepModeContainer 10, CATStdCont 9, CATSeeBodyCont 8,
  CATMaterialCont 6) — regions that carry no V5_CFV2 header and no
  validating CB0001 tail (the stdcont/seebody ones already probed by
  the shipped law). Wrapper bytes without store structure: not
  reachable by any committed law (unknown whether a NEW form of store
  framing could use them — carried, not claimed).

## 3. no-pool — 94 dev: the P8 family, measured (fact; semantics unknown)

- **76/94 carry NO wrapper at all** in the store body (kinds empty);
  the 18 others carry only non-pool wrappers (universal-vocabulary
  `0000`/`0001`/`0100`/`0108` forms, `0062` x22 corpus-wide, and
  back-to-back `10 24` wrappers where one FULL_WRAP's sub-kind bytes
  are the next FULL_WRAP's opening) — never an `01 06` pool, which is
  what the anchor says (fact).
- **89/94 have zero STRIP_RE header candidates**; the clean path's
  facet scan is empty structure-wise (fact).
- **94/94 carry NODE_MAGIC hits in the body; 67/94 carry
  TOKEN-BEARING list nodes** (the census convention: LIST_TOKEN within
  64 bytes of NODE_MAGIC, sane declared counts) — the composite node
  vocabulary is present in pool-less bodies. The exporter never
  routes there (`has_composite_space` is false), and the composite
  law itself would refuse ("composite decode invoked on a store
  without composite markers"). Whether those nodes' point regions
  carry a decodable vertex source is **unknown** — pinnable only by a
  NEW law finding (routing + decode on wrapper-less bodies), not from
  committed evidence.
- **0/94 carry the stage-6 strong raw signature** (nice >= 0.98 AND
  x-ascending >= 0.98 over the stride-12 body scan) — the raw-array
  law's vocabulary does not describe these bodies either (fact).
- 12/94 carry `05 08 01` records in the body (isolated vertex records
  without an `01 06` pool wrapper — counts and runs in the CSV).

## 4. refs-beyond — 38 dev: G3 open question 2, re-measured (fact)

- Pool decodes on all 38 (single pool group on 37, two on 1); **max
  facet ref >= own pool size on 38/38** (the anchor family,
  re-measured with the clean path's own scan).
- Sub-kinds beside the pool on ALL 38: `0000` x30, `0001` x6, `9c00`
  x2, `00ff` x2, `7500`, `31ff`, `6200` x1 each — the stage-1 C8
  family, reproduced at this baseline. No second `01 06` pool form
  exists in the bodies (the "second pool form" disjunct of G3 open
  question 2 has no corpus instance here; the "further element
  source" disjunct stays open — unknown).

## 5. The ceiling table (fact for measured figures; inference where labeled)

Dev population 1,381; accepted dev passes **952** (68.94%); bar =
1,105 (**153 flips needed**). Dev failure mass at the baseline =
**429** = 310 (this stage) + 8 composite fail-closed dev (7 UV +
bad44bdf) + 79 exported empty-mesh dev + 32 exported not-manifold dev.

| family | dev stores | blocker (byte level) | measured/pinnable ceiling | IF-solved ceiling (inference, 100%-yield upper bound) |
|---|---|---|---|---|
| missing-locator | 178 | no header (125) / unprobed-container header (53) | **+12 passes (FACT)** — measured through the shipped decode + gate | +12 measured — the locator lever is fully measured; the 41 remaining recoveries need the content levers below [CORRECTED 2026-11-13 (review F1): those 41's content-lever mass must be counted IN the IF-solved column it delegates to — the 37 recovered no-pool bodies raise the no-pool row's hypothetical cap; see the corrected grind answer 2] |
| no-pool (P8) | 94 | no `01 06` pool; 76 wrapper-less; node vocabulary present, semantics unknown | 0 pinnable from committed evidence | <= +94 IF a vertex-source law is found |
| refs-beyond | 38 | refs exceed the pool; no second pool form in the bytes | 0 pinnable from committed evidence | <= +38 IF the wider element space decodes |
| composite fail-closed (reference: UV 7 + bad44bdf) | 8 | UV: element coordinates not in the payload (the committed UV note: a surface evaluation would be required); bad44bdf: unpinnable (stage-11, byte-verified) | 0 | 0 pinned; UV open (unknown) |
| empty-mesh exports (reference) | 79 | triangles = 0 exports; stage-9's named 13 all still empty-mesh at stage-10 (verified from the committed CSVs); record reading open | 0 pinnable | open |
| not-manifold exports (reference) | 32 | manifold = False exports; no named lever in the handoff | 0 pinnable | open |

**The grind answer (fact + arithmetic):**

1. The only MEASURED, pinnable lever in the entire remaining dev mass
   is the locator extension: **+12** (12/178 of the missing-locator
   family, decoded and gate-passed through the committed code — no new
   law required). After landing it, dev sits at **964/1,381 =
   69.80%**; **141 flips would remain**.
2. Even granting BOTH unpinned families of this stage's mass at a
   100% pass yield (the no-pool and refs-beyond laws do not exist
   today), this stage's ceiling is 12 + 94 + 38 = **144 < 153** — the
   non-composite mass CANNOT carry the bar even hypothetically.
   [CORRECTED 2026-11-13 (review F1): the 100%-yield sum above
   undercounts its own cap-raisers — the 37 locator-recovered
   no-pool bodies (of the 41 measured-family residuals) belong in
   the IF-solved sum per this note's own section 2 grant rules. The
   honest hypothetical bound is **12 + 94 + 37 + 38 = 181 >= 153**
   (185 if the 4 recovered composite stores are granted too): the
   non-composite mass CAN carry the bar hypothetically, barely —
   but ONLY via BOTH unpinned laws at 100% yield AND with the
   extension landed, with zero committed evidence for either law
   and no partial-credit mechanism measured anywhere in their
   families. The decision is unaffected: the only MEASURED pinnable
   lever is +12, and the close-sequence conversation stands.]
3. Reaching 153 requires the export-fail families too (79 empty-mesh +
   32 not-manifold + the UV 8) — every one blocked behind a law no
   committed evidence pins (record reading, winding/manifold, UV
   element semantics, surface evaluation). The close-sequence
   conversation with the owner is DUE: the levers are measured, and
   the only committed-evidence lever left lands +12.

Double-counting caution for the handoff's shorthand: "UV 11" and
"float-pair 10" overlap by 10 stores (the UV unexplained 11 = the
12dc542e anchor + 10 pair-variant members — MC-pair-variant claims
row); the 4 OTHER pair-variant members (17930bab, 802a6207, 86205bfb,
ccbb7862) export at the baseline (3 pass, ccbb7862 empty-mesh). The
"empty-mesh 13" (stage-9's named cohort) is a subset of the 79 dev
empty-mesh, all 13 verified still empty-mesh at this baseline.

## 6. Corrections to existing notes (none massaged)

1. **2026-11-13, stage-11 review F2 ("16 of the 178 missing-geometry-
   store files carry composite-space wrappers in UNLOCATED bytes — a
   locator-recovery sub-question"):** CONFIRMED and ANSWERED. The 16
   re-derive exactly; their wrappers sit in OTHER-container regions
   the probe loop never visits; the stage-3a vocabulary locates all
   16 spans verbatim and the committed composite decode passes 12 of
   them. F2's locator-relative wording ("no composite pool in any
   store the exporter's locator locates") was correct and needs no
   fix; this note is the dated answer to the sub-question it opened.

## 7. Claims

| claim | statement | rate | label |
|---|---|---|---|
| SC1 | taxonomy 178 + 94 + 38 = 310, zero other; membership = fail-closed with zero composite spans (own walk); the excluded 12 = the stage-11 composite set, set-equal | 310/322 | fact |
| SC2 | locator extension reach: `locate_store` validates a span on 53/178 blocks outside the three probed families (CATBRepMode 39 / CameraStartup 8 / contmeasure 2 / four others 1; padded 39 / shipped 12 / overshoot 2); probe_malformed = 0 | 53/178 | fact |
| SC3 | the 53 recovered spans through the real decode: 12 export+pass, 4 composite-fail-closed, 37 no-pool content | 12 pass | fact |
| SC4 | F2: exactly 16 files with composite wrappers; all 16 recovered; all 72 wrapper occurrences (31 composite-space — corrected 2026-11-13 review F2) inside recovered bodies; 12 of 16 pass | 16/16 located, 12/16 pass | fact |
| SC5 | the 125 non-recovered: zero V5_CFV2 outside offset 0; 121 CB0001 catalogs validate as neither store form; 13 carry wrappers with no store structure | 125/178 | fact |
| SC6 | no-pool census: 94; 76 wrapper-less; 94 NODE_MAGIC / 67 token-bearing nodes; 89 zero strip candidates; 0 strong-raw signature | 94/94 | fact (semantics unknown) |
| SC7 | refs-beyond census: 38; max ref >= pool on 38/38; non-pool sub-kind on all; no second pool form | 38/38 | fact |
| SC8 | grind ceiling: measured/pinnable = +12; IF-solved corrected 2026-11-13 review F1: 12+94+37+38 = 181 >= 153 (both unpinned laws at 100% yield + extension landed; zero committed evidence for either); after the locator extension 964/1,381 = 69.80%, 141 flips remain with no pinnable lever | — | fact (arithmetic) + inference (labeled) |

## 8. Phase B: the DECLARED A/B delta (committed BEFORE the corpus run, 2026-11-13)

Phase B gate (met): the missing-locator family has 178 stores blocked
(>= 2), and its law is pinnable from COMMITTED evidence — the locate
law is already committed and container-parameterized; the extension
probes the remaining blocks with it unchanged, and the 12 passes were
measured through the committed decode pre-declaration (section 2).
Implementation commit precedes this declaration; the observed A/B
commit follows it.

- **D1 (exports)**: 1,120 -> **1,132 (+12, 0 lost)**.
- **D2 (L2 gate)**: dev **952 -> 964 (+12 EXACTLY, the section-2
  stores measured pre-declaration through the real decode + the
  runner's gate logic; 964/1,381 = 69.80%)**; held-out **55/61
  UNCHANGED** (the 178 population rows are all dev; every held-out
  fail-closed part has a located stdcont span, so the recovery
  families never run there); 0 lost passes.
- **D3 (row-level)**: EXACTLY 53 of the 1,442 A/B rows differ; every
  other row byte-identical. All 53 are today `missing-geometry-store`:
  - **12 rows** `missing-geometry-store` -> export + `pass` (the named
    section-2 stores);
  - **41 rows** `missing-geometry-store` -> `undecoded-variant` (still
    fail-closed: 37 recovered no-pool bodies + 4 recovered composite
    spans failing under the committed composite laws);
  - the other 125 missing-locator rows (no header, no validating
    CB0001 tail) and all non-population rows unchanged.
- **D4 (the 12 rows' provenance and decode paths)**: `store_recovery`
  = `{container: "other-container", tail_law, container_name}` with
  the section-2 case table's block/law pairs (CameraStartupContainer
  shipped x4; CATBRepModeContainer padded/overshoot/shipped;
  contmeasure shipped/overshoot; CATCameraContainer,
  CATElecBehaviourCont, CATSiFiContShuttle shipped); `stage` =
  identity-table-walk x10, identity-per-rep x1 (636b13f6),
  identity-mixedwrite-reps x1 (d67512e6); `manifold` True, `failed_
  check` "" on all 12.
- **D5 (errors/details, schema)**: the 41 fail rows' details gain the
  `[store recovered via the other-container (NAME) probe, LAW tail
  law]` suffix; the schema change is additive (enum value +
  optional `container_name`; schema v1 preserved). The known behavior
  change — a V5_CFV2 header in an other-container region failing both
  tail families would now raise `malformed-store-header` instead of
  `missing-geometry-store` — has **0 corpus incidence** measured
  pre-declaration (census `probe_malformed` = 0).
- **D6 (STOP gates)**: ANY lost export or lost pass = STOP; any
  changed row outside the 53 = stop-and-root-cause.

## 9. Observed A/B (2026-11-13, this branch) — declared-vs-observed

Run: `.venv/bin/python -I scripts/triage/ab_identity_export.py
--out-name stage12-identity-export-files.csv` (1,442 rows, committed;
the stage-10 baseline CSV untouched). Observed headline: exports
1,120 -> **1,132** (dev 1,075 + held-out 57); dev L2 **964/1,381 =
69.80%** (was 952), held-out **55/61** steady; error classes:
`missing-geometry-store` 178 -> 125, `undecoded-variant` 140 -> 181
dev (+4 held-out unchanged).

| declaration | declared | observed | verdict |
|---|---|---|---|
| D1 exports | 1,120 -> 1,132 (+12, 0 lost) | 1,132 (1,075 + 57), 0 lost | MET |
| D2 dev L2 | 952 -> 964 (+12 exactly, 69.80%) | 964/1,381 = 69.80% (+12) | MET |
| D2 held-out | 55/61 unchanged | 55/61 unchanged | MET |
| D2 lost passes | 0 | 0 (all 1,007 baseline passes preserved row-identical) | MET |
| D3 changed rows | exactly 53 of 1,442 | exactly 53: 12 `missing-geometry-store` -> exported/pass, 41 -> `undecoded-variant` (error_class the ONLY changed field on all 41); every other row byte-identical | MET |
| D3 the 12 names | the section-2 case table | the same 12 sha16s, `stage` = identity-table-walk x10 / identity-per-rep (636b13f6) / identity-mixedwrite-reps (d67512e6) | MET |
| D4/D5 provenance | `store_recovery` on the 12 summaries; recovery suffix on the 41 details | suffix verified on the 41 at the seam; the 12's summary record VERIFIED ONLY AFTER A FIX — see below | MET after fix |
| D6 STOP gates | any lost export/pass = STOP | none triggered | n/a |

**Found-and-fixed during the observed run (fact):** the first
implementation emitted `store_recovery` only on the clean decode path;
the 12 corpus passes export through the COMPOSITE path
(`_export_composite_store` builds its own summary), so their summaries
carried no provenance — the first fixtures could not catch this (they
export clean stores). Fixed (shared `_store_recovery_record` helper on
both paths; the committed `geometry-othercontainer-composite-law`
fixture exports a recovered composite store and pins the summary
record, mutation-verified); corpus re-verified at the seam
(d67512e6 -> `{other-container, shipped, CATBRepModeContainer}`;
56080410 -> `..., CameraStartupContainer`); the full A/B re-run on the
fixed code is row-level identical (53 rows, same transitions, 0 lost).

## 10. Reproduction

```
cd <worktree> && ln -s /home/alan/Documents/Repos/catpart-parser/corpus corpus
python3 -I scripts/triage/stage12_noncomposite_census_probe.py
# outputs: docs/evidence/data/stage12-noncomposite-census.csv (310 rows)
#          docs/evidence/data/stage12-unlocated-wrappers.csv (177 rows)
# anchor run (subset):
python3 -I scripts/triage/stage12_noncomposite_census_probe.py \
  --sha16 5608041010b20335,416d14fd09a8c68d
```

Corpus binaries are not committed (corpus symlinked read-only). The
probe imports the committed geometry modules read-only and writes
nothing outside `docs/evidence/data/`; `src/` is untouched by Phase A.
BASELINE SCOPE (dated 2026-11-13): the committed CSVs are the stage-10-
baseline measurement; re-running the probe on a tree that carries this
stage's Phase B shifts the live exporter anchor exactly per the
declared/observed A/B (the 53 recoverable parts: 12 export, 41 raise
`undecoded-variant`, all 53 drop out of the census) — the shift is the
probe's own cross-check of Phase B, observed on the branch-final tree;
re-run at the baseline on commit 42132fc for byte-identical CSVs.
