# Phase 7 close-out — DRAFT (not applied)

**Date** 2026-11-18 · **Repo** main @ `c06664e` · **Scope** design draft only: this file is the only
artifact created; nothing in `docs/ROADMAP.md`, `README.md`, `src/`, `tests/`, `scripts/`, `fitness/`
was touched. Every figure below is a committed claims-CSV row, a committed note line, or arithmetic on
committed counts, named at the point of use.

**Deliverables in this file**

| § | Deliverable |
| :-- | :--- |
| 0 | The two preconditions the drafted close text depends on (read first) |
| 1 | The exact ROADMAP Phase 7 status block to insert |
| 2 | The exact README L3 row replacement (plus the companion lines that carry the same claim) |
| 3 | The draft closure evidence note `docs/evidence/2026-11-18-phase7-close.md` |
| 4 | Why the adopted reading is the honest one (standalone paragraph) |
| 5 | The exact `catpart-fitness` invocation and the expected row fields |
| 6 | Assembly order and stop conditions |
| 7 | What this draft does not assert |

Placeholders: `[[L3_RUN_ID]]` (the appended history row's `run_id`) and `[[L3_RATE]]` (the L3 headline
rate the final run records). No other slot is left open.

---

## 0. Two preconditions — the text is honest only if both hold

**(P1) The adopted reading is 21/23, and the committed scorer emits 23/23 today.** The design rule is
"a construct is **resolved** iff a committed decoder *or* a documented negative covers it; **candidate
is not resolved**" (`docs/agents/br6-graph-design.md:158`). The committed scorer does not implement
that rule as written: `RESOLVED_OUTCOMES = frozenset(OUTCOME_ORDER) - {PENDING_MERGE}`
(`src/catpart/fitness/l3.py:114`) counts `candidate`, so `resolved` is 23 and the emitted rate is
`1.0` (`l3.py:519-520`; pinned by `tests/test_fitness_l3.py:115-121`, `:130`, `:189`, `:219`,
`:598-609`; recorded as rows `BR6H-03` = 23/23 and `BR6H-15` = 23/23). The close text drafted here
reports **21/23** (14 decoded + 3 documented negatives + 4 documented-opens; `BR6L3-03`, `BR6L3-06`,
`BR6L3-04`). For the prose and the row to agree, **one** of these must happen before the append:

- (a) the numerator becomes `decoded + documented-negative + documented-open`; this is not a one-line
  change — `src/catpart/fitness/l3.py:914-918` asserts `resolved + pending-merge == total` and would
  fail at 21/23, and the real-repo pins in `tests/test_fitness_l3.py` encode 23/23; `BR6L3-02`
  ("decoded + documented-negative + documented-open + candidate; the L3 headline numerator", 23/23)
  and `BR6H-03`/`BR6H-15` must be corrected or superseded in the same commit; **or**
- (b) the owner rules that `candidate` counts as resolved. That contradicts
  `br6-graph-design.md:158` and the checklist's reading (§3.2 of
  `docs/agents/br6-close-checklist.md`), so it is recorded here as **declined**, not as a live option.

**STOP if the appended row's `resolved` is not 21.** A 23/23 row under a 21/23 status block is exactly
the prose-vs-data drift the dispatch rules forbid (`docs/agents/dispatch-recipes.md:126-140`).

**(P2) The close depends on a dated owner ruling.** ROADMAP Phase 7's literal acceptance is "100% of
the frozen vocabulary resolved (decoded or negatived)" (`docs/ROADMAP.md:245-247`). At 21/23 the close
is a **documented 21/23 close**, not a 100% count, and it rests on two sub-rulings recorded dated in
the closure note (§3 §5 of this draft): documented-open-with-ceiling counts as *negatived*
(`ROADMAP.md:245-247` wording; recommendation D4(a) in `docs/agents/v1-readiness.md:259`), and CRV-08
and SRF-07 are declared out of reach for v1.0. **The pre-authorized bar-revision rule does not cover
this**: it requires published ceiling arithmetic showing the reachable ceiling is *below* the bar
(`ROADMAP.md:267-274`), and nothing shows CRV-08/SRF-07 unreachable — they are open, not capped
(`docs/agents/br6-close-checklist.md:203-206`). The ruling is therefore a separate owner decision, and
it is the close's load-bearing document, not a footnote.

---

## 1. ROADMAP Phase 7 status block (exact text to insert)

**Insertion point.** `docs/ROADMAP.md`, immediately after the Phase 7 acceptance line at `:245-247`
and before `## Terminal state and closure` (currently `:249`). It follows the shape of the Phase 4
(`:96`), Phase 5 (`:158`) and Phase 6 (`:209`) blocks: one bolded verdict paragraph, then the
provenance and the pointer to the close-out note.

**Text to insert** (verbatim; the `[[…]]` tokens are the two run-decided values):

```markdown
**Status (2026-11-18): CLOSED at 21/23 frozen constructs — 14 decoded, 3 documented
negatives, 4 documented-opens with published ceilings, 2 candidates disclosed as
unresolved (owner ruling 2026-11-18, recorded in the close-out note §5).** The
denominator is the 23-row vocabulary frozen by the census (BR1, #48; commit `df02b7d`;
sha256 `2b2f54d9fbabe0f09082357e0469a22286fc2e48e4930098c782a2317c9ff611`), unchanged
since the freeze (`docs/evidence/data/brep-construct-vocabulary.csv`; `BR6L3-01` /
`BR6L3-24`). Five decode slices landed and were independently reviewed (#54–#57 and
the BR6 shell slice of #58): [BR2 planar faces & loops](../evidence/2026-11-17-br2-planar-loops.md),
[BR3 curves](../evidence/2026-11-17-br3-curves.md), [BR4 quadrics](../evidence/2026-11-17-br4-quadrics.md),
[BR5 CGM/NURBS](../evidence/2026-11-17-br5-cgm-nurbs.md), [BR6 shell](../evidence/2026-11-17-br6-shell.md).
Verdicts over the 23 rows (`docs/evidence/data/br6-l3-claims.csv`, `BR6L3-03..07`):
**14 decoded** (TOP-01, TOP-03..TOP-07, CRV-01/02/03/07, SRF-01..SRF-04); **3
documented negatives with numeric ceilings** (TOP-02 `BR5-06b_top02_lump_ceiling`;
CRV-06 and SRF-08 `BR5-06d_crv06_srf08_ceiling`); **4 documented-open with
published ceiling arithmetic** (CRV-04 / CRV-05: no eccentricity field in the 30-B
`33 38` layout, ceiling = the 357-file conic carrier set `C03_census_presence`;
SRF-05 / SRF-06: the upper bound is the whole classified strip-loop total, 67,919
loops `SRF-05_upper_bound_classified_patches`, which is a bound on the *classified*
population and explicitly **not** a corpus ceiling); **2 candidates not resolved**
(CRV-08, parameter-carrier evidence only, `C08_midring_dir_law`; SRF-07,
negative-space pencil signature, `SRF-07_pencil_noncyl_allscopes_presence`);
pending-merge 0. **The L3 headline adopted is 21/23 = 0.9130** — decoded +
documented negative + documented-open; `candidate` is not resolved
(`docs/agents/br6-graph-design.md:158`). It lands in `fitness/history.jsonl` as row
`[[L3_RUN_ID]]` under no-regret with L1/L2 unchanged: L1 1,745/1,751 = 99.66% Dev,
73/73 held-out; L2 1,033/1,381 = 74.80% Dev, 56/61 held-out; L3
`{"rate": [[L3_RATE]], "resolved": 21, "total": 23, …}` — one split-less scalar,
accepted on the introduction rule (`L3 recorded with L1/L2 intact`), never a
re-run gate of its own. **The corpus rate is reported alongside and never gates**:
21,659 of 33,166 construct × part presence slots = 0.6530 (`BR6L3-16` / `BR6L3-17`),
with `corpus_context.gating: false`. **Disclosure — 15 of 23 denominator cells are
provenanced**: `CRV-04` 214, `CRV-05` 143, `CRV-08` 1,280, `SRF-03` 542, `SRF-04`
412, `SRF-05` 320, `SRF-06` 680, `SRF-07` 890 have no committed generator, no claims
row, and no `round(n/1089, 4)` form (`docs/agents/br6-vocabulary-provenance.md:52`);
they are quoted as frozen input only and never as decode rates. `TOP-02`, `CRV-03`,
`CRV-06` and `SRF-08` carry provenanced but mis-scoped denominators, so their frozen
rates are not decode rates either. **No exact B-rep is claimed**: faces are decoded
records and tessellated shells, not analytic surfaces; NURBS content is 0/1,089
knot- and weight-signature files (`BR5-03a/b/c`); 1,036 of 1,317 located stores
(116,057 face candidates) stay unplaced in the composite index space (`BR6S-08`,
`BR6S-23`); parametric recipe recovery stays out of scope (`ROADMAP.md:241-243`);
and the BR6 topology-graph / STEP exporter is not part of this phase's acceptance —
`src/catpart/brep/graph.py` and `step_export.py` are not on main. The full
acceptance table, the per-construct verdicts and every disclosure:
[docs/evidence/2026-11-18-phase7-close.md](../evidence/2026-11-18-phase7-close.md).
```

**Why this shape.** It states the result (21/23 with the outcome split), the date, the artifacts
(vocabulary sha, five notes, the two claims CSVs), the documented-opens with their ceilings, the 8
unprovenanced cells by id, and the L3 reading actually adopted — with the two run-decided values left
as tokens. It says what is *not* claimed (exact B-rep, NURBS, composite placement, graph/STEP) in the
same paragraph that says what is, so no reader can take the close as an exact-B-rep claim.

**Companion edits this block assumes** (outside this draft's four deliverables, listed so the close is
not landed half-consistent):

| file:line | current | needed |
| :--- | :--- | :--- |
| `README.md:126` | `G — B-rep ([#47](…)) \| full parametric B-rep (Phase 7) \| in progress` | `21/23 resolved (Phase 7, 2026-11-18)` |
| `README.es.md:49` | `… \| en curso (Fase 7, …) \| — \|` | the §2 row, translated |
| `README.es.md:113` | `\| L3 \| … \| planeado, el más difícil (Fase 7) \|` | `cerrada en 21/23 (Fase 7)` |
| `site/index.html:89` | `<span class="pill plan">planned · hardest</span>` | the closed state (this page is published verbatim to gh-pages) |
| `docs/ROADMAP.md:258` | `4. **Phase 7 (B-rep)** acceptance met.` | a dated clause: `(CLOSED 2026-11-18 at 21/23, owner ruling)` |

---

## 2. README L3 row replacement (`README.md:48`)

**Current line** (exact):

```markdown
| **L3 — full parametric B-rep** | in progress (Phase 7, [Spec G #47](https://github.com/MadManJohnSmith/catpart-parser/issues/47)) | — |
```

**Replacement** (exact):

```markdown
| **L3 — B-rep construct coverage** | 21/23 frozen constructs resolved (14 decoded, 3 documented negatives, 4 documented-opens with published ceilings); the 2 `candidate` rows (CRV-08 trimmed curve, SRF-07 extruded surface) are disclosed as unresolved; L3 row `[[L3_RUN_ID]]` = [[L3_RATE]] under no-regret, L1/L2 unchanged — Phase 7 closed 2026-11-18 | [ROADMAP](docs/ROADMAP.md), [close-out](docs/evidence/2026-11-18-phase7-close.md) |
```

**The label change is deliberate.** "Full parametric B-rep" is not what shipped: NURBS content is
0/1,089 (`BR5-03a/b/c`), 1,036 stores have no placeable geometry (`BR6S-08`), and parametric recipe
recovery is out of scope (`ROADMAP.md:241-243`). Keeping the old label while saying "resolved 21/23"
would advertise the capability the phase explicitly did not deliver; the replacement names the
capability actually measured and keeps "L3" as the level id, matching the ROADMAP title.

**Style check.** The row keeps the table's four-column shape, the existing L1/L2/Phase-5/Phase-6 rows'
pattern (`result — phase closed YYYY-MM-DD`), and links the same two artifact classes those rows link
(status doc + the dated close-out note).

---

## 3. Closure evidence note — draft of `docs/evidence/2026-11-18-phase7-close.md`

````markdown
# Evidence: Phase 7 close — the frozen B-rep vocabulary resolved at 21/23 (Spec G #47, Ticket #58)

**Date**: 2026-11-18
**Status**: CLOSED — 21 of the 23 frozen constructs resolved (14 decoded, 3 documented
negatives, 4 documented-opens with published ceilings); CRV-08 and SRF-07 stay
`candidate` and are disclosed as unresolved. The L3 headline row `[[L3_RUN_ID]]`
records `[[L3_RATE]]` under no-regret with L1/L2 unchanged.
**Target tickets**: #47 (Spec G), #58 (BR6); decode slices #54–#57 closed.
**Base commit**: `c06664e`.
**Artifacts**: [`brep-construct-vocabulary.csv`](data/brep-construct-vocabulary.csv)
(23 rows, sha256 `2b2f54d9fbabe0f09082357e0469a22286fc2e48e4930098c782a2317c9ff611`),
[`br6-l3-claims.csv`](data/br6-l3-claims.csv) (29 rows),
[`br6-l3-history-claims.csv`](data/br6-l3-history-claims.csv) (18 rows),
[`br6-shell-claims.csv`](data/br6-shell-claims.csv) (38 rows),
the five slice notes ([BR1](2026-11-17-br1-brep-census.md),
[BR2](2026-11-17-br2-planar-loops.md), [BR3](2026-11-17-br3-curves.md),
[BR4](2026-11-17-br4-quadrics.md), [BR5](2026-11-17-br5-cgm-nurbs.md),
[BR6 shell](2026-11-17-br6-shell.md)), the L3 scorer note
([2026-11-17-br6-l3-scorer.md](2026-11-17-br6-l3-scorer.md)), the history-wiring note
([2026-11-18-br6-l3-history.md](2026-11-18-br6-l3-history.md)), and the two audits
([`br6-vocabulary-provenance.md`](../agents/br6-vocabulary-provenance.md),
[`br6-close-checklist.md`](../agents/br6-close-checklist.md)).
**Not this note**: `src/catpart/brep/graph.py` and `step_export.py` (not on main; not a
ROADMAP Phase 7 acceptance item), the gh-pages L3 surface (#49), the v1.0 tag
release (terminal-state item 5).

---

## 1. Result

Phase 7's acceptance (`docs/ROADMAP.md:245-247`) has three clauses:

| clause | result | basis |
| :--- | :--- | :--- |
| 100% of the frozen vocabulary resolved (decoded or negatived) | **met at 21/23 only under the §5 ruling — not a 100% count**: 14 decoded + 3 documented negatives + 4 documented-opens; the 2 candidates are outside the numerator and disclosed | `BR6L3-03` 14, `BR6L3-06` 3, `BR6L3-04` 4, `BR6L3-05` 2, `BR6L3-07` 0 |
| the L3 headline reported alongside L1/L2 under no-regret | **met** — row `[[L3_RUN_ID]]`, `scalars.L3 = {"rate": [[L3_RATE]], "resolved": 21, "total": 23, "by_outcome": {…}}`; L1/L2 unchanged | row fields; `BR6H-01`, `BR6H-02`, `BR6H-11` |
| the corpus rate reported alongside and never gates | **met** — 21,659 / 33,166 slots = 0.6530, `corpus_context.gating: false` | `BR6L3-16`, `BR6L3-17` |

**#47's four boxes** against the same artifacts (the close checklist's A1–A4):

| # | item | state |
| :-- | :--- | :--- |
| A1 | census closed, vocabulary frozen and committed | **MET** — 23 rows, `df02b7d`, census CSV re-runs byte-identical (provenance §2.1), #48 closed; denominator provenance 15/23 (disclosure §7) |
| A2 | every frozen construct resolved: decoded or negatived with published ceiling arithmetic | **MET at 21/23 under §5** — CRV-08 (parameter-bound semantics unestablished, `br3 §3`) and SRF-07 (extrusion-vs-cylinder is construction history the tessellation cannot answer, `br4 §3`) remain `candidate` |
| A3 | L3 headline in `fitness/history.jsonl` under no-regret | **MET** — row `[[L3_RUN_ID]]`; the schema widening, runner wiring and no-regret table landed before it (`2026-11-18-br6-l3-history.md` §3–§5) |
| A4 | ROADMAP status block + README updated at close | **MET by this close's commit** — `ROADMAP.md` Phase 7 block and the README L3 row land with this note |

`B4` of #47's "what to build" (parametric recipe recovery out of scope) is **MET** by citation:
`ROADMAP.md:241-243` plus the Phase 3 negative (`2026-11-08-container-tree.md:7-33`, 0/1,810 files
resolve a parent hierarchy) — cited, not re-derived.

---

## 2. The denominator (frozen, not re-derived)

- 23 constructs: topology 7 (`TOP-01..07`), curves 8 (`CRV-01..08`), surfaces 8 (`SRF-01..08`) —
  `BR6L3-01`, `BR6L3-11`/`BR6L3-12`/`BR6L3-13`.
- The scored file's identity: sha256
  `2b2f54d9fbabe0f09082357e0469a22286fc2e48e4930098c782a2317c9ff611` (`BR6L3-24`). A vocabulary
  differing in rows, ids, duplicates or `frozen` status is a **denominator change**, not a rerun, and
  the scorer fails closed (`2026-11-17-br6-l3-scorer.md` §2).
- Citation integrity: 23/23 resolved rows verify against exactly one row of their cited claims CSV,
  across 5 committed CSVs (`BR6L3-19`, `BR6L3-18`); 11 rows declare a `claim_label` and 1 declares an
  inherited `claim_construct` (`BR6L3-28`, `BR6L3-29`).
- **Not re-frozen.** The provenance audit found the committed census generator emits an 18-row
  vocabulary in a different schema; re-freezing would delete two independently established outcomes
  (SRF-03, SRF-04) and CRV-08's only evidence row (`docs/agents/br6-vocabulary-provenance.md:132-141`).
  Denominator changes are a STOP-and-report owner decision (`ROADMAP.md:231`).

---

## 3. Per-construct verdicts (23 rows)

Citation column = the exact claim id the L3 registry validates (`BR6L3-19`). Counts below are row
counts, not the frozen `corpus_occurrences` cells (§7).

| # | id | construct | verdict | cited claim |
| --: | :--- | :--- | :--- | :--- |
| 1 | TOP-01 | Solid/Body | decoded — structural carrier only, no body-count semantics | `BR5-04b_top01_store_root` |
| 2 | TOP-02 | Lump | documented negative — no record-level detector (`observations=0`), numeric ceiling | `BR5-06b_top02_lump_ceiling` |
| 3 | TOP-03 | Shell | decoded — derived partition law; "stored shell record" is a byte-level negative | `BR6S-04_shell_files_corpus` (law: `BR6S-13` 76 components) |
| 4 | TOP-04 | Face | decoded — record == face is a geometric reading | `BR2-03_face_files_corpus` |
| 5 | TOP-05 | Loop | decoded — count-width law; 0.19% variants named | `BR2-04_planar_files_corpus` |
| 6 | TOP-06 | Edge | decoded grammar; E1 end-alignment residue named | `T06_census_presence` |
| 7 | TOP-07 | Vertex | decoded structural walk; identity/order/duplicates not discriminated | `T07_pool_count_law` |
| 8 | CRV-01 | Line/Segment | decoded layout; field semantics open (G2 law on 10.04% of corpus) | `C01_line_block_finite` |
| 9 | CRV-02 | Circle/Arc | decoded; sign convention open (named) | `C02_circle_decode_ok` |
| 10 | CRV-03 | Ellipse | decoded layout; ellipse-axis reading candidate; no conic-type field | `C03_conic_decode_ok` |
| 11 | CRV-04 | Parabola | documented-open with ceiling | `C04_parabola_ceiling` |
| 12 | CRV-05 | Hyperbola | documented-open with ceiling | `C05_hyperbola_ceiling` |
| 13 | CRV-06 | NURBS/BSpline Curve | documented negative — 0/1,089 content signatures | `BR5-06d_crv06_srf08_ceiling` |
| 14 | CRV-07 | Polyline | decoded (n > 2 strips, strict walk) | `C07_polyline_strips` |
| 15 | CRV-08 | Trimmed Curve | **candidate** — parameter carriers only, bounds semantics open | `C08_midring_dir_law` |
| 16 | SRF-01 | Plane | decoded record-local plane; surface identity documented-open | `BR2-10_plane_coplanar_poolonly` |
| 17 | SRF-02 | Cylindrical Surface | decoded at tessellation level; composite scope candidate; counts are floors | `SRF-02_cylinder_allscopes_presence` |
| 18 | SRF-03 | Conical Surface | decoded, thin population (4 files), floor | `SRF-03_cone_allscopes_presence` |
| 19 | SRF-04 | Spherical Surface | decoded, floor (the cone law absorbs short sphere spans by precedence) | `SRF-04_sphere_allscopes_presence` |
| 20 | SRF-05 | Toroidal Surface | documented-open — measured upper bound, not a class-shaped ceiling | `SRF-05_upper_bound_allscopes_presence` |
| 21 | SRF-06 | Surface of Revolution | documented-open — no separable bound; inherits SRF-05's | `SRF-05_upper_bound_allscopes_presence` (declared inheritance) |
| 22 | SRF-07 | Extruded Surface | **candidate** — negative-space pencil signature; extrusion vs cylinder needs CGM | `SRF-07_pencil_noncyl_allscopes_presence` |
| 23 | SRF-08 | NURBS/BSpline Surface | documented negative — 0/1,089 content signatures | `BR5-06d_crv06_srf08_ceiling` |

Outcome split (`BR6L3-03..07`): **decoded 14** (TOP-01, TOP-03, TOP-04, TOP-05, TOP-06, TOP-07,
CRV-01, CRV-02, CRV-03, CRV-07, SRF-01, SRF-02, SRF-03, SRF-04) · **documented-negative 3** (TOP-02,
CRV-06, SRF-08) · **documented-open 4** (CRV-04, CRV-05, SRF-05, SRF-06) · **candidate 2** (CRV-08,
SRF-07) · **pending-merge 0** = 23.

---

## 4. The L3 headline: the four readings and the one adopted

Pure arithmetic on the committed outcome counts (§3; `BR6L3-03..07`) — no new measurement:

| reading | resolved | rate | what it assumes |
| :--- | --: | --: | :--- |
| decoded only | 14/23 | 0.6087 | neither negatives nor opens count |
| strict design contract (decoder or documented negative, `br6-graph-design.md:158`) | 17/23 | 0.7391 | documented-open is a third state and does not count |
| **adopted: decoded + documented negative + documented-open with ceilings** | **21/23** | **0.9130** | documented-open is the ROADMAP's "negatived with published ceiling arithmetic" (`ROADMAP.md:245-247`); candidate is **not** resolved |
| full | 23/23 | 1.0 | candidate counts as resolved — no committed claim raises either candidate to `decoded` |

**23/23 is not available as an honest reading.** The two candidate rows are not a documentation gap:
CRV-08's parameter-bound semantics are unestablished (`br3 §3`, the 26-B `33 33` payload carries an
in-plane direction pair and a radius, not arc extent) and SRF-07's extrusion-vs-cylinder split is a
construction-history question the tessellation cannot answer (`br4 §3`, §4). Promoting either needs a
new claim row, not a relabel. The committed scorer nonetheless emits 23/23 because its numerator
includes `candidate` (`src/catpart/fitness/l3.py:114`); that is the divergence the close had to
adjudicate, not evidence that the construct is resolved.

**The adopted headline is therefore `[[L3_RATE]]`, resolved 21 of 23** — the value the appended row
records, with the outcome block still reporting all five states so a reader sees the 2 candidates
instead of a rounded 100%.

---

## 5. The owner ruling this close depends on (dated record)

**Decision (2026-11-18).** Two sub-rulings, recorded here because the close is not honest without
them:

1. **Documented-open with published ceiling arithmetic counts as negatived** — CRV-04/CRV-05 and
   SRF-05/SRF-06 are inside the resolved set, each with its ceiling disclosed per row (§7).
   *Rationale*: the phase's acceptance says "decoded or negatived with published ceiling arithmetic"
   (`ROADMAP.md:245-247`); these four rows are precisely a measured ceiling on what was not decoded,
   not an absence claim. *Not chosen*: excluding them (17/23) would report four constructs as
   unresolved after their ceilings were published, contradicting the phase's own negative path.
2. **CRV-08 and SRF-07 are outside the v1.0 scope** — they stay `candidate`, are not counted in the
   numerator, and are carried into the release notes as the two named B-rep items a later version may
   pick up. *Rationale*: neither is reachable from the committed evidence without new work (CGM
   construction history for SRF-07; a parameter-bound decoder for CRV-08), and neither is capped, so
   the pre-authorized bar rule (`ROADMAP.md:267-274`) cannot be invoked for them. *Not chosen*:
   leaving the phase open for two rows whose probes do not exist on main.

**Precedent and cost.** This is the shape the owner-decision protocol requires — one recommendation,
the declined alternative stated honestly, dated, with the sub-decisions to the construct id
(`docs/agents/dispatch-recipes.md:240-262`). The cost of ruling (2) the other way is that Phase 7
stays open with no committed probe to close it; the cost of ruling (1) the other way is a 17/23 close
that treats published ceilings as non-evidence. Both alternatives are recorded, not hidden.

**What the ruling does not do.** It does not re-freeze the denominator (§2), does not promote a
candidate (no claim supports it), and does not touch L1/L2 or the no-regret rule.

---

## 6. The L3 row and the expected fields

The append is one `catpart-fitness` run (ADR-0003: local, on the corpus host, never CI):

```console
$ export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
$ .venv/bin/catpart-fitness \
    --manifest manifests/corpus-manifest.csv \
    --corpus-root . \
    --fitness-dir fitness
```

The flags exist exactly as documented (`src/catpart/cli.py:150-171`): `--manifest` and `--fitness-dir`
carry the repository defaults verbatim, and `--corpus-root .` is equivalent to that flag's default
(the repository root derived from the manifest, `src/catpart/fitness/runner.py:642-644`) when run from
the repository root, as the CLI's own description requires. Expected effects: one line appended to
`fitness/history.jsonl` (14 rows today — `BR6H-09`, `BR6H-10`), one full report at
`fitness/reports/[[L3_RUN_ID]].json`, the row JSON on stdout.

Expected row (fields that this close claims; values from the committed rows named):

| field | expected | basis |
| :--- | :--- | :--- |
| `run_id` / `timestamp` | `[[L3_RUN_ID]]` / its UTC instant | generated per run (`src/catpart/fitness/runner.py:579-585`) |
| `schema_version` / `inspect_schema_version` | 0 / 1 | current row schema |
| `tool_version` | the installed package version — `0.1.0` at this base (all 14 committed rows); `1.0.0` if the #49 version bump lands first | `fitness/history.jsonl:1-14` |
| `corpus_digest` | `dc75f8fe9156dd69b26f2a44ff642c396c7c484d4049a831b88cf6b91d11b164` | unchanged in all 14 rows; manifest is the corpus definition |
| `accepted` | `true` | L3 introduction rule (`2026-11-18-br6-l3-history.md` §5) |
| `baseline_run_id` | `20261113T231506Z-c2ab64` | last accepted row (`BR6H-10`) |
| `no_regret.dev_rose` / `held_out_fell` | `false` / `false` | `BR6L3-20..23` are the same counts as the baseline |
| `no_regret.l2_dev_rose` / `l2_dev_fell` / `l2_held_out_fell` | `false` / `false` / `false` | same |
| `no_regret.reason` | `L3 recorded with L1/L2 intact` | `src/catpart/fitness/history.py:74` (introduction reason) |
| `scalars.L1.dev` | clean 1,745 / total 1,751, rate 0.9965733866362079 | `BR6L3-20`, `BR6H-10` |
| `scalars.L1.held-out` | 73 / 73, rate 1.0 | `BR6L3-21` |
| `scalars.L2.dev` | pass 1,033 / total 1,381, rate 0.7480086893555394 | `BR6L3-22` |
| `scalars.L2.held-out` | 56 / 61, rate 0.9180327868852459 | `BR6L3-23` |
| `scalars.L3` | `{"rate": [[L3_RATE]], "resolved": 21, "total": 23, "by_outcome": {"decoded": 14, "documented-negative": 3, "documented-open": 4, "candidate": 2, "pending-merge": 0}}` | `BR6L3-03..07`; §0 P1 |
| `report` | `reports/[[L3_RUN_ID]].json` | runner |

If L1 or L2 moved in the meantime, the reason follows the rule table
(`2026-11-18-br6-l3-history.md` §5) and the close's "L1/L2 unchanged" sentence must be re-derived
from the new row — never carried over.

---

## 7. Disclosures that travel with the headline

1. **8 unprovenanced denominator cells** (`docs/agents/br6-vocabulary-provenance.md:52`, table
   `:74-83`): CRV-04 `214 / 0.182`, CRV-05 `143 / 0.115`, CRV-08 `1,280 / 0.975`, SRF-03
   `542 / 0.465`, SRF-04 `412 / 0.354`, SRF-05 `320 / 0.275`, SRF-06 `680 / 0.582`, SRF-07
   `890 / 0.795`. No single column or pair of columns of `brep-census-files.csv` reproduces them and
   none is `round(n/1089, 4)`; they are frozen input, never decode rates. The construct-level decode
   counts above replace them everywhere a rate is stated.
2. **4 mis-scoped denominators**: TOP-02 `1,435` (= body/CGM presence; the census cannot separate
   lump from body, `BR5-06a`), CRV-06 and SRF-08 `1,435` (= `cgm_present`; content measures 0/1,089,
   `BR5-03c`), CRV-03 `357` (= every conic carrier, no ellipse discriminator). Their frozen rates are
   not decode rates.
3. **The documented-opens' ceilings are uneven, and that is stated per row**: CRV-04/CRV-05 are capped
   by the reproducible 357-file conic carrier set (`C03_census_presence`) — but the 214 + 143 split
   *inside* their claim text is unprovenanced (`provenance §2.4`), so 214+143=357 must not be read as
   a partition. SRF-05's bound is the whole classified strip-loop total, 67,919 loops
   (`SRF-05_upper_bound_classified_patches`, 975/1,442 = 0.676144 corpus and 952/1,089 = 0.874197
   L2-pass, `SRF-05_upper_bound_allscopes_presence`), explicitly **not** a corpus ceiling; SRF-06
   inherits it because no separable signature exists.
4. **Candidates are disclosed, never rounded**: CRV-08 (`C08_midring_dir_law`; its presence row
   `C08_trim_presence` = 969/1,442 differs from the frozen 1,280) and SRF-07
   (`SRF-07_pencil_noncyl_allscopes_presence` = 388/1,442 = 0.269071).
5. **The corpus rate has no aggregate L3 artifact beyond the slot rows**: 21,659 / 33,166 = 0.6530
   (`BR6L3-16`/`BR6L3-17`) is census file presence (construct × part slots), not a decode rate, and
   `corpus_context.gating: false` records that it never gates.
6. **Scope floors**: every recognized surface/curve count is a floor — per-loop granularity, the
   composite identity-only scope, and 90,451 of 156,914 composite loops excluded
   (`composite_loops_excluded_share` = 0.576437; `BR4 §1`). SRF-02's 702/1,442 = 0.486824
   (`SRF-02_cylinder_allscopes_presence`) and CRV-07's 366/1,442 (`C07_polyline_strips`) are floors,
   not populations.

---

## 8. What this phase does not claim

- **Not exact B-rep.** Faces and shells are decoded records and tessellated partitions (`BR6S-13`,
  76 closed components; `BR6S-16`/`BR6S-17` 76/76 wound and positive-volume), not analytic surfaces.
- **No NURBS.** 0/1,089 knot-signature and 0/1,089 weight-signature files in the CGM regions
  (`BR5-03a/b/c`); the frozen 100% rows were carrier-presence labels (`br5 §1` item 2).
- **No composite placement.** 1,036 of 1,317 located stores (`BR6S-08` = 0.786636) hold 116,057 face
  candidates (`BR6S-23`) that leave the pool; 708 `0x44` records (`BR6S-22`) and 531 out-of-pool
  records (`BR6S-20`) are counted, never guessed.
- **No graph/STEP exporter.** `src/catpart/brep/graph.py` and `step_export.py` are not on main; the
  interface is design only (`docs/agents/br6-graph-design.md:3`). Phase 7's acceptance does not
  require them, and this note does not claim them.
- **No parametric recovery.** Out of scope by decision (`ROADMAP.md:241-243`), with the Phase 3
  negative standing (`2026-11-08-container-tree.md:7-33`).
- **No units.** The corpus length unit stays a documented negative (U2 0/108), so no exact-solid
  claim can be made downstream of this phase.

---

## 9. Verification

```console
$ export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
# the headline the run will record (committed evidence only; no corpus read)
$ .venv/bin/python -I scripts/triage/score_l3_constructs.py \
    --json-out /tmp/opencode/l3.json --summary-out /tmp/opencode/l3.txt
# the append (§6)
$ .venv/bin/catpart-fitness --manifest manifests/corpus-manifest.csv \
    --corpus-root . --fitness-dir fitness
# the gate at the head that lands the docs
$ bash scripts/check.sh
$ .venv/bin/python -I scripts/triage/check_claims_csv_quoting.py
```

Expected: the scorer summary reads `21/23 resolved (0.9130)` with outcomes
`decoded 14 | documented-negative 3 | documented-open 4 | candidate 2 | pending-merge 0`
(§0 P1: a 23/23 summary means the numerator still counts candidates — STOP, the close text is then
wrong); `fitness/history.jsonl` grows 14 → 15 lines; `scripts/check.sh` green (ruff, pytest, claims
quoting, cargo build/test, wasm build/test, pkg sync, node suites, Playwright where installed — the
documented skip).

---

## 10. Zero-invention statement

No corpus binary was read for this note and no fitness run was made by it: every figure is a committed
claims-CSV row, a committed note line, or arithmetic on row counts, named at the point of use. The one
computation this note performs is the 14 / 17 / 21 / 23 reading table (§4), which is addition and
division over `BR6L3-03..07`. The two placeholders (`[[L3_RUN_ID]]`, `[[L3_RATE]]`) are the run's own
values.
````

---

## 4. Why the adopted reading is the honest one

> The close reports **21 of 23**, not 23 and not 17. 23/23 would count CRV-08 and SRF-07 as resolved,
> and nothing in the committed evidence does that: CRV-08's `33 33` payload carries an in-plane
> direction pair and a radius but no arc extent, so its parameter-bound semantics stay open
> (`2026-11-17-br3-curves.md` §3), and SRF-07's extrusion-versus-cylinder split is a construction-history
> question the tessellation cannot answer (`2026-11-17-br4-quadrics.md` §3, §4) — promoting either needs
> a new claim row, not a relabel. The committed scorer's 23/23 comes from a numerator that includes
> `candidate` (`src/catpart/fitness/l3.py:114`), which contradicts the counting rule the BR6 contract
> fixed in writing ("candidate is not resolved", `docs/agents/br6-graph-design.md:158`) and the close
> checklist's arithmetic (`docs/agents/br6-close-checklist.md:104-116`). 17/23 would go the other way
> and treat a published ceiling as non-evidence: ROADMAP Phase 7 accepts a construct "decoded or
> **negatived** with published ceiling arithmetic" (`docs/ROADMAP.md:245-247`), and CRV-04/CRV-05
> (ceiling = the 357-file conic carrier set) and SRF-05/SRF-06 (upper bound = 67,919 classified loops)
> are exactly that, with the SRF pair's weakness — a bound on the classified population, explicitly not
> a corpus ceiling — disclosed in the same table rather than absorbed into the number. So 21/23 is the
> only reading that keeps both halves of the contract: the four ceiling-only constructs count as closed,
> the two candidates do not count, and the 8 unprovenanced denominator cells never enter a rate. It is
> the reading the owner ruling records (§3 §5), and it is deliberately *not* laundered into 100% — the
> outcome block still prints `candidate 2` beside the 21.

---

## 5. The `catpart-fitness` invocation and the expected row

**Invocation** (exact; the flags and their defaults are `src/catpart/cli.py:150-171` and
`src/catpart/fitness/runner.py:642-644`, `pyproject.toml:34`):

```console
$ export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH
$ .venv/bin/catpart-fitness \
    --manifest manifests/corpus-manifest.csv \
    --corpus-root . \
    --fitness-dir fitness
```

No other flag exists on this entry point: `main_fitness` takes exactly `--manifest`, `--corpus-root`,
`--fitness-dir` (`src/catpart/cli.py:124-183`). `--corpus-root .` resolves the manifest's `local_path`
entries against the working directory; run from the repository root, as the CLI's own description
requires. Do **not** pass `--fitness-dir` to a scratch path: the close's headline is the appended row.

**Expected row fields** — the table in §3 §6 above is the spec; the invariants that decide
acceptance are:

- `accepted: true` with `no_regret.reason: "L3 recorded with L1/L2 intact"` (flat L1/L2 + L3
  introduction; `src/catpart/fitness/history.py:74`, rule table
  `2026-11-18-br6-l3-history.md` §5). If L1 or L2 moved, the reason changes and the ROADMAP block's
  "L1/L2 unchanged" clause must be re-derived from the committed row before landing.
- `scalars.L1` and `scalars.L2` byte-equal to the baseline row's counts (`BR6L3-20..23`): L1 dev
  1,745/1,751 (0.9965733866362079), held-out 73/73 (1.0); L2 dev 1,033/1,381 (0.7480086893555394),
  held-out 56/61 (0.9180327868852459).
- `scalars.L3 = {"rate": [[L3_RATE]], "resolved": 21, "total": 23, "by_outcome": {"decoded": 14,
  "documented-negative": 3, "documented-open": 4, "candidate": 2, "pending-merge": 0}}` — one
  split-less scalar, no `dev`/`held-out` keys (`BR6H-02`). **`resolved` must be 21** (§0 P1).
- `corpus_digest: dc75f8fe9156dd69b26f2a44ff642c396c7c484d4049a831b88cf6b91d11b164`,
  `baseline_run_id: 20261113T231506Z-c2ab64`, `report: reports/[[L3_RUN_ID]].json`.
- `fitness/history.jsonl` 14 → 15 lines; `fitness/reports/[[L3_RUN_ID]].json` written and
  schema-valid (the runner self-validates before writing, `src/catpart/fitness/runner.py:588-600`).

**Not an expectation of this run:** the gh-pages L3 surface (#49, `BR6H-17` = 0/1 site surfaces) and
the v1.0 tag. The publisher will carry `runs[].l3` for the new row (`BR6H-16`), but the badge stays L1
(one headline per level).

---

## 6. Assembly order and stop conditions

1. Decide §0 P1 (numerator = 21) and land the code+claims correction **before** the run; §0 P2's
   ruling is recorded by the closure note itself (§3 §5), dated, in the same commit as the ROADMAP
   block.
2. Run `catpart-fitness` (§5). **STOP** if `accepted` is false, if `resolved` ≠ 21, or if L1/L2 are
   not the baseline counts — each of those changes the drafted prose, and the prose must follow the
   row, never the reverse (`docs/agents/dispatch-recipes.md:126-140`).
3. Fill `[[L3_RUN_ID]]` and `[[L3_RATE]]` in the ROADMAP block (§1), the README row (§2) and the note
   (§3). No other token: the restored note must contain no bracketed placeholder.
4. Create `docs/evidence/2026-11-18-phase7-close.md` from §3; if the run lands on a later date, move
   the note's filename and every `2026-11-18` in §1/§2/§3 together (the note is the dated record, not
   a copy).
5. `bash scripts/check.sh` green, then commit docs + `fitness/` + the code/claims correction in one
   changeset, then push.
6. Close #58 → #47 with pointers to the row and this note, and only after step 5.

## 7. What this draft does not assert

- It does not assert that `src/catpart/brep/graph.py`, `step_export.py`, `br6-graph-claims.csv` or
  `2026-11-17-br6-graph-l3.md` exist — they do not, and the drafted close text says so.
- It does not assert an owner ruling happened; §3 §5 is the draft of that record, and §0 P2 names it
  as the close's precondition.
- It does not assert the scorer already emits 21/23: it emits 23/23 at `c06664e` (§0 P1), and the
  drafted text is not applicable until that is resolved.
- It does not touch or predict the v1.0 tag, the release notes, `#49`'s gh-pages L3 surface, or any
  post-v1.0 ticket.
