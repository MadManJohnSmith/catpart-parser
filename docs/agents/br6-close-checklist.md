# BR6 / Spec G close checklist — #47 and ROADMAP Phase 7

**Date** 2026-11-18 · **Repo** main @ `e610bbc` · **Scope** close-readiness audit of Spec G (#47) against the committed
artifacts. Read-only: no audited file was modified; this note is the only new file.

**Inputs** [#47](https://github.com/MadManJohnSmith/catpart-parser/issues/47) (0 comments),
[#58](https://github.com/MadManJohnSmith/catpart-parser/issues/58) (open), [#48](https://github.com/MadManJohnSmith/catpart-parser/issues/48)
(closed) and #54–#57 (all closed); [`ROADMAP.md:227-265`](../ROADMAP.md); [`brep-construct-vocabulary.csv`](../evidence/data/brep-construct-vocabulary.csv);
the six evidence notes `2026-11-17-br{1..6}-*.md`; the five merged claims CSVs `br1..br6`; [`br6-vocabulary-provenance.md`](br6-vocabulary-provenance.md);
[`br6-graph-design.md`](br6-graph-design.md); [`fitness/history.jsonl`](../../fitness/history.jsonl).

**Status legend** MET · MET WITH DISCLOSURE · PARTIAL · **MISSING**.

## 0. Result

**#47 cannot be closed honestly today.** Two of its four acceptance items are missing outright (L3 row; ROADMAP/README
close blocks), one is short of 100 % (2 candidate constructs), and one is met only with a disclosed provenance defect
(8 unprovenanced denominator cells). The pending BR6 integration (#58) has not started: `src/catpart/brep/graph.py`,
`src/catpart/brep/step_export.py`, `br6-graph-claims.csv`, `br6-l3-claims.csv` and `2026-11-17-br6-graph-l3.md` do not
exist on main, and `src/catpart/brep/__init__.py:1-9` still declares itself the scaffold to be populated "at the BR6
integration step".

## 1. Acceptance checklist

### 1.1 #47 acceptance criteria (the four checkboxes)

| # | Item (verbatim) | Satisfied by | Status |
| :-- | :--- | :--- | :--- |
| A1 | "Census closed; construct vocabulary frozen and committed (BR1)." | [`2026-11-17-br1-brep-census.md:15-20`](../evidence/2026-11-17-br1-brep-census.md) (3/3 criteria claimed); vocabulary 23 rows at [`brep-construct-vocabulary.csv:2-24`](../evidence/data/brep-construct-vocabulary.csv), commit `df02b7d`; census CSV 1,442 rows, re-run **byte-identical** ([provenance §2.1:58-61](br6-vocabulary-provenance.md)); #48 CLOSED 2026-11-17 | **MET WITH DISCLOSURE** — 15/23 frozen counts reproduce from committed census columns; 8 do not and have no generator ([provenance:52](br6-vocabulary-provenance.md)) |
| A2 | "Every frozen construct resolved: decoded or negatived with published ceiling arithmetic." | §2 table: 14 decoded, 3 documented-negative, 4 documented-open, 2 candidate | **MISSING (pre-adjudication)** — 21/23 at the widest honest reading; CRV-08 and SRF-07 are `candidate` (§3). **Superseded 2026-11-18:** both were adjudicated to `documented-open` on committed ceiling rows (`C08_trim_curve_ceiling` 1,277/1,442 superset; `SRF-07_extrusion_ceiling` 67,919-loop superset), `c636172`; A2 is now 23/23 with 0 candidates. |
| A3 | "L3 headline in `fitness/history.jsonl` under no-regret." | — | **MISSING** — all 14 rows carry `"L3":null` (`fitness/history.jsonl:1-14`); the committed schema types L3 as **null only** ([`fitness-history-row-v0.json:186-189`](../../src/catpart/schema/fitness-history-row-v0.json)); no L3 path exists in [`history.py:31-34`](../../src/catpart/fitness/history.py), [`history.py:197-220`](../../src/catpart/fitness/history.py) |
| A4 | "ROADMAP Phase 7 status block + README updated at close." | — | **MISSING** — `ROADMAP.md:227-247` has no `**Status (...)**` block (contrast Phase 4 at `:96`, Phase 6 at `:209`); [`README.md:48`](../../README.md) still says "in progress" |

### 1.2 ROADMAP Phase 7 acceptance (`ROADMAP.md:245-247`)

| # | Item (verbatim) | Satisfied by | Status |
| :-- | :--- | :--- | :--- |
| R1 | "100% of the frozen vocabulary resolved (decoded or negatived)" | §2 | **MISSING** — same as A2 |
| R2 | "the L3 headline reported alongside L1/L2 under no-regret" | — | **MISSING** — same as A3; the last accepted row still reports L1 1,745/1,751 dev / 73/73 held-out and L2 1,033/1,381 dev / 56/61 held-out (`fitness/history.jsonl:14`) |
| R3 | "the corpus rate is reported alongside and never gates" | per-construct corpus rates are committed (e.g. `BR6S-05_shell_rate_on_label_population` 66/1,133 = 0.0582524; `SRF-02_cylinder_allscopes_presence` 702/1,442 = 0.486824) | **PARTIAL** — no aggregate L3/BR6L corpus-rate row set exists (`docs/evidence/data/br6-l3-claims.csv` absent) |

### 1.3 #47 "What to build" sub-items

| # | Item | Satisfied by | Status |
| :-- | :--- | :--- | :--- |
| B1 | "one decode ticket per census class (created at census close)" | #54–#57 CLOSED (`gh issue view`), #58 OPEN; 23 constructs mapped onto the five slices ([`br1:74-90`](../evidence/2026-11-17-br1-brep-census.md)) | **MET** |
| B2 | "the grind+close ticket": graph + STEP + L3 row + docs, then close BR6 and #47 | #58 deliverables absent on main (`git ls-files` shows no `brep/graph.py`, no `brep/step_export.py`, no `scripts/triage/decode_brep_graph.py`, no `tests/test_brep_graph.py`, no `br6-*-claims.csv`, no `2026-11-17-br6-graph-l3.md`) | **MISSING** |
| B3 | "corpus rate reported, never gating" | as R3 | **PARTIAL** |
| B4 | "Parametric recipe recovery is out of scope (documented negative; the Phase 3 specification-tree negative stands)" | `ROADMAP.md:81-85` (feature tree landed as container inventory only); [`2026-11-08-container-tree.md:7-33`](../evidence/2026-11-08-container-tree.md) (parent_name hierarchy law fails: 0/1,810 files resolve fully) | **MET** (cited, not re-derived) |

### 1.4 #58 dependency checkboxes (not #47 acceptance — the pending integration)

All four remain unchecked (`gh issue view 58`): graph + STEP with corpus-free tests and a synthetic negative fixture;
L3 row under no-regret; ROADMAP + README + `bash scripts/check.sh`; close #58 and #47. The committed interface contract
for the first two is [`br6-graph-design.md`](br6-graph-design.md) (design only, "no code", `:3`).

## 2. Per-construct verdict table (23 rows)

Verdicts are the notes' own states, keyed by the frozen `construct_id`. Claim ids and labels are from the merged
claims CSVs on main; a second id is given where a row's verdict rests on two claims. `frozen` = the vocabulary cell
(`corpus_occurrences / rate_l2_pass`, over 1,442 / 1,089 files); **†** = unprovenanced, **‡** = provenanced but produced
by a detector that does not measure the named construct — neither may be quoted as a decode rate (§3.3).

| # | id | construct | verdict | claim id (label) | frozen cell |
| --: | :--- | :--- | :--- | :--- | :--- |
| 1 | TOP-01 | Solid/Body | decoded — structural carrier only (no body-count/semantics claim, BR5 §4) | `BR5-04a_top01_seebody_block` (fact); `BR5-04b_top01_store_root` (fact) | 1,435 / 1.0 |
| 2 | TOP-02 | Lump | documented-negative — no record-level detector (observations = 0) | `BR5-06a_top02_lump_detector` (**unknown**); `BR5-06b_top02_lump_ceiling` (fact) | 1,435 / 1.0 ‡ |
| 3 | TOP-03 | Shell | decoded — derived partition law; "stored shell record" is a byte-level negative | `BR6S-13_closed_shells` (fact); `BR6S-05_shell_rate_on_label_population` (fact) | 1,133 / 0.9982 |
| 4 | TOP-04 | Face | decoded (record == face is a geometric reading, BR2 §5) | `BR2-01_face_files_l2_pass` (fact); `BR2-03_face_files_corpus` (fact) | 1,133 / 0.9982 |
| 5 | TOP-05 | Loop | decoded — count-width law; 0.19 % variants named | `BR2-02_planar_files_l2_pass` (fact); `BR2-07_count_structure_established` (fact) | 895 / 0.786 |
| 6 | TOP-06 | Edge | decoded grammar; E1 end-alignment residue named | `T06_census_presence` (established); `T06_edge_residue_files` (named residue) | 1,311 / 1.0 |
| 7 | TOP-07 | Vertex | decoded structural walk; identity/order/duplicates not discriminated | `T07_census_presence` (established); `T07_pool_count_law` (established) | 1,282 / 1.0 |
| 8 | CRV-01 | Line/Segment | decoded layout; **field semantics open** (G2 law holds on 10.04 % corpus) | `C01_line_block_finite` (established); `C01_line_prep_law` (candidate) | 1,231 / 0.9853 |
| 9 | CRV-02 | Circle/Arc | decoded (sign convention open, named) | `C02_circle_decode_ok` (established); `C02_circle_pool_law` (candidate) | 1,077 / 0.8503 |
| 10 | CRV-03 | Ellipse | decoded layout; ellipse-axis reading **candidate**; no conic-type field | `C03_conic_decode_ok` (established); `C03_conic_dir_law` (candidate) | 357 / 0.2874 ‡ |
| 11 | CRV-04 | Parabola | documented-open with ceiling | `C04_parabola_ceiling` (open (ceiling)) | 214 / 0.182 † |
| 12 | CRV-05 | Hyperbola | documented-open with ceiling | `C05_hyperbola_ceiling` (open (ceiling)) | 143 / 0.115 † |
| 13 | CRV-06 | NURBS/BSpline Curve | documented-negative — 0/1,089 content signatures | `BR5-03c_nurbs_content_rate_vs_census` (fact); `BR5-06d_crv06_srf08_ceiling` (fact) | 1,435 / 1.0 ‡ |
| 14 | CRV-07 | Polyline | decoded (n > 2 strips; strict walk) | `C07_polyline_strips` (established) | 996 / 0.8365 (proper n > 2: 366 corpus) |
| 15 | CRV-08 | Trimmed Curve | **candidate** — parameter carriers only, bounds semantics open | `C08_trim_presence` (candidate); `C08_midring_dir_law` (candidate) | 1,280 / 0.975 † |
| 16 | SRF-01 | Plane | decoded record-local plane; **surface identity documented-open** | `BR2-10_plane_coplanar_poolonly` (fact); `BR2-06_unit_normal` (fact) | 895 / 0.786 |
| 17 | SRF-02 | Cylindrical Surface | decoded at tessellation level; composite scope candidate; counts are floors | `SRF-02_cylinder_allscopes_presence` (fact); `SRF-02_cylinder_composite_presence` (candidate) | 1,128 / 0.9972 (strip presence, not cylinders) |
| 18 | SRF-03 | Conical Surface | decoded, thin population (4 files), floor | `SRF-03_cone_allscopes_presence` (fact); `SRF-03_cone_composite_presence` (candidate) | 542 / 0.465 † |
| 19 | SRF-04 | Spherical Surface | decoded, floor (cone law absorbs short sphere spans by precedence) | `SRF-04_sphere_allscopes_presence` (fact); `SRF-04_sphere_composite_presence` (candidate) | 412 / 0.354 † |
| 20 | SRF-05 | Toroidal Surface | documented-open — measured upper bound, **not** a class-shaped ceiling | `SRF-05_upper_bound_classified_patches` (upper bound (row-derived sum), 67,919 loops) | 320 / 0.275 † |
| 21 | SRF-06 | Surface of Revolution | documented-open — no separable bound; inherits SRF-05's bound | no own row; inherits `SRF-05_upper_bound_classified_patches` | 680 / 0.582 † |
| 22 | SRF-07 | Extruded Surface | **candidate** — negative-space pencil signature; extrusion vs cylinder needs CGM | `SRF-07_pencil_noncyl_allscopes_presence` (fact); `SRF-07_pencil_noncyl_composite_presence` (candidate) | 890 / 0.795 † |
| 23 | SRF-08 | NURBS/BSpline Surface | documented-negative — 0/1,089 content signatures | `BR5-03c_nurbs_content_rate_vs_census` (fact); `BR5-06d_crv06_srf08_ceiling` (fact) | 1,435 / 1.0 ‡ |

Counts: **decoded 14** (TOP-01, 03–07 = 6; CRV-01, 02, 03, 07 = 4; SRF-01, 02, 03, 04 = 4) ·
**documented-negative 3** (TOP-02, CRV-06, SRF-08) · **documented-open 4** (CRV-04, CRV-05, SRF-05, SRF-06) ·
**candidate 2** (CRV-08, SRF-07) = 23.

## 3. The L3 headline

### 3.1 Counting rule in force

[`br6-graph-design.md:158`](br6-graph-design.md): "a construct is **resolved** iff a committed decoder *or* a documented
negative covers it; **candidate is not resolved**. Denominator = the 23 frozen rows keyed by `construct_id`, never their
per-class counts." The row shape fixed there is `scalars.L3 = {"resolved","total","candidate","documented_negative","rate"}`.

### 3.2 Arithmetic (derived from §2; no new measurement)

| reading | resolved | rate | what it assumes |
| :--- | --: | --: | :--- |
| decoded only | 14/23 | 0.6087 | neither negatives nor opens count |
| **strict contract** (decoder or documented negative; `br6-graph-design.md:158`) | **17/23** | **0.7391** | documented-open is a third state and does **not** count |
| wide (open accepted as "negatived + ceiling arithmetic", `ROADMAP.md:245-247`) | 21/23 | 0.9130 | the four ceiling rows count as closed |
| full | 23/23 | 1.0 | CRV-08 and SRF-07 leave `candidate` — **no committed claim does this today** |

**23/23 is not available.** The two candidate rows are not a documentation gap: CRV-08's parameter-bound semantics are
unestablished ([`br3:86-88`](../evidence/2026-11-17-br3-curves.md)) and SRF-07's extrusion-vs-cylinder split is a
construction-history question the tessellation cannot answer ([`br4:100-103`](../evidence/2026-11-17-br4-quadrics.md)).
Promoting either needs a new claim row, not a relabel.

**Recommendation:** write **17/23 = 0.7391** as the rule-faithful headline and record 21/23 as the wide reading in the
row's annotations. The 4-row difference is an owner decision, not an implementer choice: BR5's review explicitly
rejected a third "open/parked" state and relabelled its rows as documented negatives
([`br5:114-128`](../evidence/2026-11-17-br5-cgm-nurbs.md), finding B1), while BR3/BR4 left the same kind of
ceiling-only outcome labelled `open (ceiling)`. Overturning that labelling is a STOP-and-report under
[`dispatch-recipes.md:240-262`](dispatch-recipes.md), and re-choosing what "resolved" means is the same class of
decision as re-freezing the denominator ([`provenance §4:132-141`](br6-vocabulary-provenance.md)).

### 3.3 Disclosure items that must travel with the headline

1. **8 unprovenanced denominator cells** ([`provenance:52`](br6-vocabulary-provenance.md), test table `:74-83`) —
   CRV-04 `214 / 0.182`, CRV-05 `143 / 0.115`, CRV-08 `1,280 / 0.975`, SRF-03 `542 / 0.465`, SRF-04 `412 / 0.354`,
   SRF-05 `320 / 0.275`, SRF-06 `680 / 0.582`, SRF-07 `890 / 0.795`. No column, column pair or `round(n/1089, 4)`
   reproduces them; they are not output of the committed generator on the stated population
   (`tests/test_brep_vocabulary.py:114` pins only "23 rows"). Report the construct-level decode counts instead, or
   `unprovenanced`.
2. **4 mis-scoped denominators** ([`provenance §3.3:110-114`](br6-vocabulary-provenance.md)) — TOP-02 `1,435`
   (= body/CGM presence), CRV-06 and SRF-08 `1,435` (= `cgm_present`; BR5 measures content at 0/1,089), CRV-03 `357`
   (= every conic carrier; no ellipse discriminator). Their frozen rates are **not** decode rates.
3. **Documented-opens** — SRF-05 and SRF-06 carry no class-shaped ceiling: SRF-05's bound is the whole classified
   total, 67,919 loops ([`br4:92`](../evidence/2026-11-17-br4-quadrics.md)), which is explicitly "not a corpus ceiling";
   SRF-06 inherits it because no separable signature exists ([`br4:98`](../evidence/2026-11-17-br4-quadrics.md)).
   CRV-04/CRV-05's ceiling is the reproducible 357-file conic carrier set, but the 214 + 143 split inside their claim
   text is unprovenanced ([`br3:77-79`](../evidence/2026-11-17-br3-curves.md),
   [`provenance:88-92`](br6-vocabulary-provenance.md)).
4. **Candidates** — CRV-08, SRF-07 (§3.2).
5. **Corpus rate, never gating** — the reportable corpus figures are the per-construct rows in the merged claims CSVs
   (e.g. `BR6S-05` 66/1,133 = 0.0582524 for shell closure on the census label population; `SRF-02_cylinder_allscopes_presence`
   702/1,442; `C07_polyline_strips` 366/1,442; `C08_trim_presence` 969/1,442). No aggregate corpus rate exists for L3,
   and the frozen cells in §2 must not be reused as one.
6. **Scope floors** — every recognized surface/curve count is a floor (per-loop granularity, composite identity-only
   scope, 90,451 excluded loops = 0.576437 of 156,914; [`br4:29`](../evidence/2026-11-17-br4-quadrics.md)).

### 3.4 A blocker the L3 row will hit before it can land

The design's L3 object **cannot be appended to `fitness/history.jsonl` today**: the schema declares
`"L3": {"type": "null"}` ([`fitness-history-row-v0.json:186-189`](../../src/catpart/schema/fitness-history-row-v0.json)),
and a row carrying the `{"resolved",…}` object is rejected (`$.scalars.L3: expected type null, got dict`, checked with
`catpart.schema.validate` on this base). Two further consequences of any schema widening:

- `history.py` round-trips each level through `SPLIT_SCORE_CLASSES = {"L1": SplitScore, "L2": PartScore}`
  ([`history.py:197-220`](../../src/catpart/fitness/history.py)) and would need an L3 entry, or every read of the
  history raises.
- `evaluate_no_regret` iterates `LEVELS` ([`history.py:270-313`](../../src/catpart/fitness/history.py)); the moment a
  baseline row also carries a non-null L3 in the dev/held-out shape, L3 becomes a comparable level whose Dev fall
  rejects a run — directly contradicting "reported, never gating". L3 must be carved out of the comparison explicitly.

`src/catpart/schema/` and `src/catpart/fitness/` are **not** in #58's declared file ownership (brep modules, triage
script, tests, `fitness/`, ROADMAP, README, evidence), so this is an unowned prerequisite, not a BR6 implementation
detail.

## 4. Close comment draft for #47 (Spanish, ≤ 25 líneas)

*Precondición: no postear como cierre hasta que A2/A3/A4 estén verdes. Cada hueco `<...>` se reemplaza por una fila
comprometida; si `L3` no da 23/23, el texto no cierra #47.*

```text
Cierre de Spec G (#47) — Phase 7 / L3

Censo + vocabulario: docs/evidence/2026-11-17-br1-brep-census.md; 23 filas en
docs/evidence/data/brep-construct-vocabulary.csv (df02b7d); censo byte a byte
(br6-vocabulary-provenance.md §2.1); #48 cerrado. Decode: #54-#57 cerrados; BR6
(#58) TOP-03 + grafo + STEP en <commit>.
L3: fila <BR6L-xx> en fitness/history.jsonl, L1/L2 intactos (última aceptada: L1
1.745/1.751 dev, 73/73 held-out; L2 1.033/1.381 dev, 56/61 held-out).
Veredicto (23): 14 decodificados; 3 negativos documentados (TOP-02, CRV-06, SRF-08);
4 abiertos con techo (CRV-04, CRV-05, SRF-05, SRF-06); 0 candidatos. L3 = <resolved>/23
(docs/agents/br6-graph-design.md:158); candidato no cuenta como resuelto, y CRV-08 y
SRF-07 se promovieron en <claim ids>.
Divulgaciones, sin maquillar:
- 8 celdas de corpus_occurrences/rate_l2_pass sin generador (CRV-04, CRV-05, CRV-08,
  SRF-03, SRF-04, SRF-05, SRF-06, SRF-07): no se usan como tasas de decode
  (br6-vocabulary-provenance.md §2.3).
- TOP-02, CRV-03, CRV-06 y SRF-08 no reportan su tasa congelada como tasa de decode:
  el denominador no mide el constructo nombrado (§3.3).
- Tasa corpus reportada, nunca gating: <filas BR6L>.
- Techos: SRF-05/06 sin techo de clase (cota = 67.919 loops clasificados, no corpus);
  CRV-04/CRV-05 comparten los 357 portadores 33 38.
Fuera de alcance, negativo documentado: recuperación paramétrica (ROADMAP:81-85).
No se reclama B-rep exacto: caras trianguladas, sin NURBS (0/1.089), sin índice
compuesto (1.036 stores sin ubicar).
```

## 5. What cannot be closed honestly — exact reasons

1. **A2 / R1 — 2 candidate rows.** CRV-08 (`C08_trim_presence`, candidate) and SRF-07
   (`SRF-07_pencil_noncyl_composite_presence`, candidate) are not decoded and not negatived. The acceptance text is
   "100 % resolved"; 21/23 is the maximum today under any reading of the four states, and 17/23 is the maximum under
   the rule the BR6 contract itself fixed. **No new probe exists on main that would promote either.** The pre-authorized bar-revision rule
   (`ROADMAP.md:267-274`) does not apply: it requires a published ceiling showing the reachable ceiling is *below* the
   bar, and nothing here shows CRV-08/SRF-07 are unreachable — they are open, not capped.
2. **A3 / R2 — the L3 row is not writable as specified.** Schema `"L3": {"type": "null"}`
   (`fitness-history-row-v0.json:186-189`), no L3 branch in `history.py`, and no BR6L claims CSV from which the counts
   would be cited. Recording `null` and calling it the headline would satisfy the letter of the checkbox and none of its
   content. The widening is additive to schema v0 but touches `src/catpart/schema/` and `src/catpart/fitness/`, outside
   #58's declared ownership (§3.4) — it needs an owner or a new ticket.
3. **A4 — no close blocks.** `ROADMAP.md:227-247` has no status block and `README.md:48` still reads "in progress".
   Writing them now would assert a closure that A2/A3 do not support; they belong in the same commit as the L3 row.
4. **A1 — met, but the denominator is only 15/23 provenanced.** The vocabulary is frozen and committed as required, so
   the checkbox is satisfiable; what is *not* satisfiable is quoting its counts as decode rates. The provenance note's
   own recommendation (a `provenance` column + a mechanical guard, [`provenance:120-130`](br6-vocabulary-provenance.md))
   has not landed: `tests/test_brep_vocabulary.py:114` still checks only the 23-row inventory. Re-freezing is an owner
   decision and would shrink coverage 23 → 18, deleting two independently established outcomes
   ([`provenance:132-141`](br6-vocabulary-provenance.md)); it must not happen as a side effect of closing #47.
5. **B2 — the close ticket's own deliverables are absent.** #58 asks for `graph.py`, `step_export.py`, a claims CSV, a
   dated note and the L3 scorer; only the TOP-03 slice landed. Closing #47 with a pointer to "the evidence" would point
   at a graph/STEP/L3 record that does not exist.
6. **R3 — partial.** Per-construct corpus rates are reported; the aggregate "corpus rate reported alongside" for L3 has
   no committed artifact. Reporting the frozen `rate_l2_pass` column instead would be the mis-scoping defect in §3.3.

## 6. What a clean close would require (order)

1. Owner ruling on the third state: accept `documented-open + ceiling` as negatived (L3 21/23) or keep the strict rule
   (L3 17/23). Record it dated in the owning note (Phase 5 retro, `dispatch-recipes.md:117-121`).
2. A new claim row promoting CRV-08 and SRF-07 — or an owner-accepted scope cut recorded with ceiling arithmetic (the
   pre-authorized rule, if and only if unreachability is demonstrated).
3. Schema + `history.py` change: L3 object, additive, carved out of `evaluate_no_regret`; one appended row with
   `resolved/total/candidate/documented_negative/rate` and the §3.3 disclosures in its report.
4. #58's graph/STEP/tests/`--selftest` slice + `br6-graph-claims.csv`, then the ROADMAP status block and README row in
   the same commit.
5. `bash scripts/check.sh` green at the head that lands the above (not re-run by this audit), then BR6 → #47 closure,
   with the §4 comment posted only after steps 1–4 are committed.

## 7. Verification commands used

```bash
export LD_LIBRARY_PATH=/usr/lib:${LD_LIBRARY_PATH:-}
git ls-files | grep -E 'brep/(graph|step_export)|br6-(graph|l3)'   # only docs/agents/br6-graph-design.md
grep -c '"L3":null' fitness/history.jsonl                          # 14 of 14 rows
.venv/bin/python -c "from catpart.schema import load_schema; from catpart.schema.validate import validate; ..."
# -> $.scalars.L3: expected type null, got dict
```

Corpus binaries were not read and no corpus run was made: every figure above is a committed CSV row, a note line, or
arithmetic on §2's counts (14/3/4/2), named as such.
