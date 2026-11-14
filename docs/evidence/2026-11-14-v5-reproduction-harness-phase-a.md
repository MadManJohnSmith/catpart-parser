# Phase 5 V5, phase A (ticket #52): the reproduction harness + the margin proposal package

**Status: implemented on the V5 worktree branch, 2026-11-14; coordinator
review pending.** Design authority: `docs/specs/phase5-viewer-spec.md`
— this note cites §3.4 (the in-browser reproduction margin AS AMENDED:
declared-before-run, native-evidence-only inputs, never re-declared to
absorb a failing run; the harness-error exclusion; the per-file
per-check comparison), §3.1 (populations), §3.2 (diff definition and
the harness-failure discipline), §4 (harness design: note + CSV
outputs, #37-composable, `*claims*.csv`-named), §5 (the viewer), §6 V5
(ticket scope), §7 (local-only, never CI), §11 (the amendment
register); the ticket is #52, the viewer it drives is V4 (#43).
Nothing is merged or pushed: commits live on the worktree branch only.

**The phase-A boundary, stated first (the hard stop, respected):**
THE FULL L2 POPULATION RUN DID NOT EXECUTE. No population subset ran
either — not even a pilot. The harness's corpus mode exists, is
complete, and is margin-gated BY CONSTRUCTION (it refuses to start
without an explicit `--margin` value; there is no `--limit` flag, so
no subset rate is even expressible). Every in-browser number this note
contains comes from the fixture machinery smoke and is labeled
mechanical validation, never a rate. The population run is phase B's,
dispatched only after the owner's margin declaration.

## What landed

### 1. The reproduction harness — `scripts/reproduction_run.py`

Stdlib + Playwright (pinned 1.65.2, the `viewer_acceptance.py`
precedent), local-only, never CI (§7). Two modes:

- **`--smoke`** — the fixture machinery validation. Generates a fixed
  population of 10 A2 fixture variants in-process
  (`tests/fixtures_gen.py`, the binary guard respected: files live in
  a run-scoped temp dir, never committed), builds reference per-check
  outcomes for them by running the SHIPPED fitness seam
  (`catpart-fitness` as a subprocess over a generated mini-manifest —
  the production scoring path, so the reference records have the true
  report shape, unavailable-rows discipline included; the runner's
  fail-closed no-empty-split rule is why the mini-manifest carries one
  held-out row, measured for the record's sake, never browser-fed),
  serves `site/` read-only (`python3 -m http.server --bind 127.0.0.1`,
  the V4 serving pattern), drives the COMMITTED viewer headlessly,
  reads the per-file per-check outcome the page computes, compares,
  and writes the CSV + figures-note. Its outcome data is mechanical
  validation ONLY — the note labels it `MACHINERY VALIDATION ONLY —
  NOT A RATE` and §3.4's letter forbids it informing the margin.
- **Corpus mode (default)** — the full L2 population (§3.1: ALL
  manifest rows with `kind=part`, successes AND fail-closed alike;
  1,442 rows today: Dev 1,381 + held-out 61, including the 4
  `magic_ok=no` part rows the population law keeps). It is
  margin-gated by construction:
  - `--margin M` is REQUIRED; without it the tool exits with a loud
    refusal citing §3.4 (the declaration is the owner's, recorded
    dated in the spec §11 BEFORE the run, native-evidence-only
    inputs). A negative margin is refused. `--margin` with `--smoke`
    is refused (machinery validation is never a rate).
  - There is NO `--limit`/`--sample`: the only population run this
    tool can make is the FULL population, so no subset rate (not even
    a pilot) can precede the declaration.
- **The reference record source** (named here per the ticket's
  instruction): the last `accepted=true` row of the committed
  `fitness/history.jsonl` → its report
  `fitness/reports/20261113T231506Z-c2ab64.json` (run_id
  `20261113T231506Z-c2ab64`; an explicit `--fitness-report` overrides).
  The tool sha256-verifies the accepted report's `corpus_digest`
  against the manifest bytes before anything runs (the runner's own
  manifest-binds-the-corpus rule) — the reference records cannot be
  silently stale. Verified today: the digest matches
  (`dc75f8fe9156dd69…`), all 1,442 population rows join to a per-file
  `l2` record, and the published L2 scalars are dev
  0.7480086893555394 (1,033/1,381) and held-out 0.9180327868852459
  (56/61) — the figures the phase-B in-browser rate must equal within
  the declared margin, per split.
- **The per-file per-check comparison** (§3.4's drift detector that
  does not depend on the margin value at all): status, `error_class`,
  `failed_check`, the three counts, the runner's mesh projection
  (manifold/closed/oriented/boundary_edge_count — `edge_count` is not
  in the fitness record, so not compared), the bounding box
  (null-ness agreement + exact float equality — both sides hold
  widened f32s, §3.2's parsed-equality convention), and the warnings'
  class sequence in order (the human detail prose is never compared —
  the §3.2 error_class convention). A mismatch names its first
  diverging field in a fixed order.
- **The exclusion discipline** (§3.4's one declared exclusion,
  independent of the margin value): harness-error files — browser
  crash, per-file timeout, unrecoverable page state — drop out of the
  compared rate and are named PER-FILE in the note, never silent; the
  recovery ladder (reload → fresh context → fresh browser, each
  verified idle) lets the run continue, and `--restart-every N`
  (default 250) bounds any slow cumulative growth across the ~3.4 GB
  population. `reference-unavailable` rows (no accepted-run record, or
  the file missing on disk) are likewise named per-file and make the
  run invalid (§3.2: every row must be match/mismatch by evidence).
- **Aggregation + the margin verdict**: per split — population,
  compared, matched, rate, the published scalar, |delta| vs the
  margin, WITHIN/EXCEEDED — plus a conservative cross-check in the
  note (the same split's rate with harness-errors counted as not-pass,
  the published scalar's own unavailable-as-not-pass convention), both
  figures CSV-composable. Deterministic ordering: manifest row order
  (the committed CSV order). Wall-clock measured: total + per-file
  seconds on every row.
- **Outputs**: `docs/evidence/data/v5-reproduction-l2-claims.csv`
  (named for the `*claims*.csv` glob — verified covered by
  `scripts/triage/check_claims_csv_quoting.py` from birth) + a dated
  figures-only note under `docs/evidence/` (the fidelity_run.py
  convention: figures a pure function of the run; prose curation
  before commit). Exit 0 only when every row is a match; 1 names each
  non-match row on stderr (the note is written either way).
- One implementation quirk recorded for the next runner of this tool:
  on the pinned Playwright 1.65.2, `wait_for_function`'s `arg=`
  binding does not reliably reach the polled function (probed:
  the same expression evaluates correctly through `evaluate` with
  `arg`, yet never goes true through `wait_for_function`, with and
  without explicit `polling`). The feed therefore embeds the unique
  per-feed link name (`f{i}.CATPart`, this tool's own token) in the
  wait expression as a constant — which doubles as the race-free
  marker that a previous file's terminal state can never satisfy.

### 2. The mechanical viewer exposure addition — `site/viewer/viewer.js`

`window.viewer.summary` grows the full mesh block and the ordered
warnings (class + detail) — exactly what the boundary's summary
carries and what the fitness record's l2 shape holds. **No gate
change**: `gate.js` is untouched (git shows one file in the commit);
the margin appears nowhere in the viewer. The V4 Playwright acceptance
re-ran green on the same build (verbatim output below), confirming the
page's visible behavior is unchanged.

### 3. The machinery pin — `tests/test_reproduction_smoke.py`

Five tests, all fixture- or committed-artifact-only:

1. `test_margin_arithmetic` — the §3.4 verdict function's contract
   (|rate − published| ≤ margin; margin 0 admits only equality; the
   delta is signed-agnostic). Pure arithmetic; runs in CI.
2. `test_compare_records_fields_and_divergence_order` — the comparison's
   field order, the decode-failure null-shape equality, exact-float
   bbox equality, the warnings class-sequence rule, the counts.
3. `test_reproduction_smoke_fixture_mode` — the browser machinery
   smoke end-to-end (10 fixtures, all-match, every branch pinned per
   variant, constant CSV row width, the not-a-rate label present).
   Skips without Chromium — the gate stays browser-free in CI (§7).
4. `test_corpus_mode_requires_margin` — the loud refusals (no margin;
   negative margin; margin + smoke). No browser.
5. `test_reference_records_join_the_population` — accepted-run
   resolution, corpus-digest binding, the 1,442-row join, both
   published scalars present — over the committed artifacts only (the
   manifest CSV + history; corpus binaries never read). Runs in CI.

## The margin proposal package (PROPOSES; does not declare)

**The proposal: margin = 0.** This package presents the
native-Fidelity-evidence-only case for the owner's §3.4 declaration.
It is a PROPOSAL: the declaration is the owner's, delivered via the
coordinator, recorded dated in the spec §11 BEFORE any population run
exists. Nothing in this package is an in-browser measurement; the only
in-browser numbers in this note are the smoke's, which are machinery
validation and are NOT inputs to this package.

### The V1–V4 native Fidelity chain (0 mismatches on every compared surface)

Every figure below traces to a committed artifact (the CSVs under
`docs/evidence/data/` and the notes they belong to); recount today,
verbatim from the CSVs: 120 + 120 + 452 + 334 rows, all `match`.

| Stage | Surface | Population | Result | Artifact |
| ----- | ------- | ---------: | ------ | -------- |
| V1 (#40) | L1 inspect documents, corpus sample (parts, products, junk) | 120 | 120/120 match, 0 mismatches | `v1-fidelity-l1-claims.csv`, note 2026-11-13 |
| V2 (#41) | L2 non-composite exports: summary parsed-document equality + PLY byte-identical + error_class equality | 120 | 120/120 match, 0 mismatches | `v2-fidelity-l2-claims.csv`, note 2026-11-13 |
| V3 (#42) | L2 composite-family-stratified sample (per-family seats from the stage-15 roster; composite-path exports compared FULLY incl. the composite block; 59 forced firing-law rows: 26 dup-pin + 33 dedup-fire-surface) | 452 (291 pass, 61 fail, 100 undecoded-variant) | 452/452 match, 0 mismatches | `v3-fidelity-l2-claims.csv`, note 2026-11-14 |
| V3 (#42) | The A2 fixture matrix, both slices (inspect + export: summary + PLY bytes + error classes, all refusal classes equal) | 334 (313 part, 21 product) | 334/334 match, 0 mismatches | `v3-fidelity-fixture-claims.csv`, note 2026-11-14 |

The chain covers every surface the in-browser comparison reads: the
summary document (whose `vertex_count`/`triangle_count`/
`degenerate_triangle_count`/`mesh`/`bounding_box`/`warnings` are what
the page's gate consumes), the PLY bytes (the vertex/triangle payloads
the page renders), and the classified error vocabulary (what a
fail-closed part shows). The composite block — the subtlest surface —
compared fully in the 452-row run, including the fail-closed composite
class and every firing law.

### The boundary facts (what the browser actually runs)

- The committed `port/pkg/` is the pinned-toolchain build output,
  wasm-pack 0.15.1 (tarball sha256 recorded in the V4 note), wasm-opt
  DISABLED — the shipped artifact is rustc's verbatim output, no
  binaryen pass near a bit-exact decode. `port/pkg/` and the served
  copy `site/viewer/pkg/` are committed byte-identical (re-verified
  today: both `port_bg.wasm` copies sha256
  `8c8bc1c73484271b334dbc8ff1a44678d817a20a3b40f44008405b5e60f43e4f`;
  `diff -q -r` clean — the gate pins this sync since V4 review F1).
  The reproduction run drives exactly these bytes: the static serve of
  committed `site/`, no rebuild step in the run path. The coordinator
  review verified the pkg is a byte-identical rebuild of the pinned
  toolchain (V4 merge fixup, 2026-11-14).
- The boundary's only numeric operation is the exact `f64 → f32`
  narrowing of the pool coordinates — §2.2's widening point makes it
  bit-exact recovery, not a rounding decision; the boundary performs
  no decode arithmetic and carries no `suboptimal_flops` allow (V4
  note §1).
- IEEE arithmetic inside WASM is fixed: the decode executes the same
  operations in the same order as the native binary the Fidelity
  chain proved (spec §2.2's numeric contract; the one platform
  question — wasm32 `powf` resolving to the libm crate rather than
  glibc — is quantified in the spec §11 register, 2026-11-14: the
  decision margins on the real decision surface (closest corpus call
  to the `PLANE_TOL` boundary: 1.06e-5; 70,605 calls, 11,263 distinct
  f32 triples) dwarf any re-rounding, 0 bit divergences and 0 status
  flips under either lowering, no NaN reaches the law — so the
  in-browser decode inherits that proof).
- The page computes its per-check outcome with `gate.js`'s
  `scoreExport`, the line-by-line mirror of `runner.py::_score_export`
  (the law at `src/catpart/fitness/runner.py:309-329`): same check
  order (empty → manifold → finite plausible bbox → degenerate ≤ 0),
  same constants (`MAX_DEGENERATE_TRIANGLES = 0` imported, not
  re-typed), same failed-check vocabulary, the plausibility check
  mirrors `_bbox_plausible`, bbox records null when implausible. No
  margin is declared or hard-coded anywhere in the viewer — the
  display is rate-agnostic (V4's hard stop, respected).

### The exclusion rule mechanics (already pinned, independent of the margin value)

§3.4's one declared exclusion: harness-error files (browser crash,
timeout, OOM on a pathological file) drop out of the compared rate and
are reported per-file in the run note — excluded from the arithmetic,
never silent. The harness implements exactly this: a harness-error row
records the failure (`type` + the page's pageerror text), the rate's
denominator excludes it, the note names the file, and the note's
conservative cross-check (harness-errors as not-pass, the published
scalar's own unavailable convention) shows how much arithmetic weight
the exclusion carries. §3.2's discipline rides along: a run with any
harness-error or reference-unavailable row exits 1 — the run is
invalid until every row is evidence-based — and a
corpus-digest-bound reference (sha256-verified before the run) pins
the comparison to this corpus.

### The spec's expected-0 rationale, with its honest counter

The draft's rationale (retained by the owner's 2026-11-13 deferral as
the expected value): the browser runs the same crate the harness
proved byte-faithful; IEEE arithmetic inside WASM is fixed; there is
no legitimate source of rate variance, only bugs — so the expected
declaration is 0, and any nonzero declaration must name the measured
phenomenon it tolerates and why repair is not the response.

The honest counter — what a nonzero margin would tolerate: a nonzero
margin exists to absorb measurement noise around a quantity whose
variance is legitimate. Here the compared quantity is a rate over a
frozen corpus of deterministic decodes; the chain above shows the
decodes are byte-faithful on every surface the rate aggregates, so
there is no phenomenon to tolerate — a rate shortfall inside a nonzero
margin would be a real per-file divergence (bugs) absorbed into
"passing", which is precisely what §3.4's never-re-declared rule
exists to prevent. The margin's only legitimate work in this design is
to be 0: the per-file per-check comparison is the drift detector (it
does not depend on the margin at all), and the scalar-within-margin
check is its aggregate echo. If a phase-B run ever fails margin 0, the
response is repair (a port bug) or a declared exclusion (harness
error) or a reference correction (§3.3's drift rule) — never a wider
margin.

**What the declaration must not cite:** any in-browser measurement —
including this note's smoke rows (mechanical validation) and any
future pilot (inexpressible — there is no subset flag). The
declaration may cite the native chain above, the boundary facts, and
the gate mirror. **The protocol:** the owner approves the value (the
proposal on the table is 0); the coordinator records it dated in the
spec §11; phase B dispatches the population run; the run note states
the declaration and the exclusion list explicitly (the harness's
figures-note already carries the margin value it ran with and the
per-file exclusions).

## Acceptance evidence (commands + counts, 2026-11-14, this branch)

### The fixture machinery smoke (the deliverable's mechanical proof)

    .venv/bin/python scripts/reproduction_run.py --smoke

Exit 0. Note written: `docs/evidence/2026-11-14-v5-reproduction-smoke.md`;
CSV: `docs/evidence/data/v5-reproduction-smoke-claims.csv` (10 rows).
Figures block (verbatim, and MACHINERY VALIDATION ONLY — NOT A RATE):

- Page requests: 10 total; external: 0 (§5's zero-external property,
  re-proven for the harness's own session)
- Wall-clock: 0.8 s (measured); per-file viewer seconds: n=10, mean
  0.031, max 0.108
- Outcomes: {'match': 10} — counts, mesh invariants, exact bbox
  floats and warnings class sequences equal on every row
- Comparison branches exercised: {'degenerate-triangles': 2,
  'malformed-pool-vertex': 1, 'malformed-store-header': 1,
  'missing-geometry-store': 1, 'not-manifold': 1, 'pass': 3,
  'undecoded-variant': 1} — every branch the A2 fixture population can
  produce: gate passes (warning-free, warning-bearing, composite),
  gate failures (not-manifold, degenerate-triangles), and four
  classified decode-failure classes. The `empty-mesh` and
  `nonfinite-bbox` gate branches are NOT reachable on fixtures (no
  vertices-only variant exists) — named honestly; their comparison
  code path is the field-generic one the other branches exercise, and
  the corpus holds 58 empty-mesh records for phase B to compare.
- The claims CSV hygiene checker covers the new CSV from birth:
  `python scripts/triage/check_claims_csv_quoting.py` → 25 files,
  2,787 rows, all at header width.

### The V4 acceptance re-run (the exposure change changed nothing visible)

    .venv/bin/python scripts/viewer_acceptance.py

    viewer acceptance — PASS
      - canonical fixture: loaded, gate pass, 8 vertices / 12 triangles, finite bbox [0, 0, 0]..[20, 100, 60]
      - metadata panel: schema v1 fields present (version, kind, 3 containers)
      - curve overlay: 1 decoded loop(s), toggle off->on->off (aria-pressed tracked)
      - corrupted fixture: classified error shown (malformed-pool-vertex, 99-char detail), page alive
      - no server component: 10 requests, all on the serving origin; zero uncaught page errors

### The machinery pin in the suite

    .venv/bin/python -m pytest tests/test_reproduction_smoke.py -q
    → 5 passed in 1.4s

In CI (no Playwright, §7): the browser test skips — the gate stays
corpus-free and browser-free; the other four run everywhere. Gate
count effect: V4 closed at 368 passed + 7 skipped; this branch adds 5
tests = 373 passed + 7 skipped locally (Chromium present), 372 passed
+ 8 skipped in CI (the browser smoke skips).

### The reference-records machinery against the committed artifacts

Verified in-run and pinned by test 5: the last accepted history row is
`20261113T231506Z-c2ab64`; its report's `corpus_digest` sha256-matches
the committed manifest; all 1,442 `kind=part` rows (dev 1,381 +
held-out 61, the §3.1 population) join to a per-file `l2` record; the
published scalars are dev 0.7480086893555394 and held-out
0.9180327868852459.

## What phase A deliberately does NOT do (the hard stop, respected)

- The full L2 population run did not execute — corpus mode is
  margin-gated by construction and was never invoked with a margin.
  No subset rate exists or is expressible (no `--limit`).
- No changes to `src/catpart/`, `fitness/`, the spec, or `port/`
  decode code (git status shows the three commits touch
  `site/viewer/viewer.js`, the harness, the tests, and the smoke
  evidence only).
- Nothing merged or pushed; the margin is NOT declared — the package
  above proposes; the owner decides via the coordinator.

## Known gaps / partial results

- The `empty-mesh` and `nonfinite-bbox` gate-fail branches are
  unreachable on the fixture population (named above); the corpus-only
  branch coverage lands with phase B's run (58 empty-mesh records
  exist in the accepted report; 0 nonfinite-bbox — the vocabulary
  exists but has never fired on the corpus).
- Corpus-scale operational facts (per-file decode time for the
  ~120 MB maxima, cumulative browser memory growth across 1,442
  feeds, the restart-every cadence) are design targets, not
  measurements — they land measured with the phase-B run's wall-clock
  note; the harness measures per-file seconds and supports
  `--restart-every` and `--per-file-timeout` for exactly that.
- The Playwright 1.65.2 `wait_for_function` `arg=` quirk is documented
  in the harness (probed, worked around with the embedded-constant
  form); a Playwright bump should re-probe it.
- The smoke's figures-note names the serving port (8933) and the
  worktree site path verbatim — local-tool evidence, regenerable per
  run; the CSV is the committed artifact.
