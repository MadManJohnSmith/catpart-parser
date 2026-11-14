# Phase 5 spec DRAFT — Web viewer, parts (L2 delivery surface)

**Status: DRAFT, coordinator review pending. Nothing here is published to
GitHub yet.** This document is the design deliverable for the Phase 5
spec: it pins what the ROADMAP's Phase 5 section (opened 2026-11-13 per
ADR-0004) leaves to design judgment — the port architecture, the
Fidelity harness, the ticket graph, the CI shape, the risks — and
proposes the publication shape (spec doc vs issue, section 9). Policy
already decided stays cited, never re-derived: ROADMAP Phase 5 +
"Terminal state and closure", ADR-0004 (Rust→WASM, Fidelity mandatory,
closure at v1.0), ADR-0001 (fitness protocol, Python is the seam),
ADR-0002 (Python-first stands for the reference implementation),
ADR-0003 (corpus local-only, gh-pages publication), GLOSSARY
(**Fidelity**, **Port**, **Viewer**).

Branch: `t3/phase5-spec-draft` off main `6c6b3e8` (Phase 4 closed
2026-11-13: L2 Dev 1,033/1,381 = 74.80% margin 0, held-out 56/61,
exports 1,173; no-regret intact). Docs-only change: the gate stays at
365 passed + 7 skipped.

---

## 1. Scope

**In scope (this phase):**

- The **Port** (GLOSSARY): the decode pipeline as it exists in
  `src/catpart/` today, to Rust compiled to WASM — the L1 slice
  (header, container-name table, trailer, version marker, identity
  block) and the L2 slice (nested V5_CFV2 store navigation, vertex
  pool, primitive/facet semantics with lex-rank references and
  winding, the composite index space — table-walk, per-rep, raw-array,
  mixedwrite laws — and the export orchestration with its classified
  error seam). Not one line of new format decoding: the port
  reproduces the Python reference's behavior, including its
  fail-closed behavior.
- The **Fidelity harness** proving Port ≡ Python over the Corpus
  (section 4, section 3 for the exact definition).
- The **Viewer shell**: static app on gh-pages — WASM glue + render
  layer (Three.js, vendored): drag-drop of a user-supplied
  `.CATPart`, orbit/zoom, wireframe/solid, in-browser mesh sanity,
  metadata panel rendering the schema-v1 JSON (document name,
  detected version, container inventory), curve overlay of the
  decoded polyline tables, classified-failure display.
- The **in-browser reproduction run**: automated headless-browser run
  over the L2 population; its sanity rate equals the published L2
  scalar within the declared margin (section 3.4: margin 0).
- CI extended to cover the Port with the A2 synthetic fixtures
  (section 7). The corpus never enters CI (ADR-0003 untouched).

**Out of scope (stays where the ROADMAP put it):**

- Phase 6 assemblies (`.CATProduct` geometry — documented negative
  0/37; the viewer loads parts this phase) and Phase 7 B-rep (L3).
- Any new decode capability. Where the Python reference fails closed
  (`undecoded-variant`, `missing-geometry-store`, …), the Port fails
  closed identically. The L2 residual families (#50, post-v1.0) are
  not reopened here.
- STEP export, parametric recovery (Phase 3 negative stands).
- The Pyodide fallback (ADR-0004 "Considered Options"): documented
  fallback only, not activated by this spec; if the port stalls
  irrecoverably, that decision returns to the owner.
- Mobile browsers and small-memory devices: desktop is the target
  surface; the largest corpus file is ~120 MB and the viewer holds
  the file plus its decoded arrays (section 10, risk 8).

## 2. Port architecture

### 2.1 Crate layout and module mapping

One Rust crate, `port/` (top-level, sibling of `src/` — same clarity
as `site/`), mirroring the Python package's module boundaries 1:1 so
review can walk them side by side and the Fidelity harness can name
the seam per module:

| Python (reference)          | Lines | Rust (`port/src/`)        | Notes |
| --------------------------- | ----: | ------------------------- | ----- |
| `catpart/header.py`         |    89 | `header.rs`               | 32-byte header, H1 law |
| `catpart/containers.py`     |   216 | `containers.rs`           | B1 records, kind law |
| `catpart/trailer.py`        |   151 | `trailer.rs`              | A..G dwords, CB__END |
| `catpart/version.py`        |    75 | `version.rs`              | CNEXTINFOS detection |
| `catpart/identity.py`       |   126 | `identity.rs`             | document_name (C3) |
| `catpart/geometry/store.py` |   330 | `geometry/store.rs`       | G1 + stage-3a/12 probes |
| `catpart/geometry/pool.py`  |   113 | `geometry/pool.rs`        | G2, `01 06` groups |
| `catpart/geometry/facets.py`|   313 | `geometry/facets.rs`      | G3 tiling + soup |
| `catpart/geometry/mesh.py`  |    63 | `geometry/mesh.rs`        | invariants |
| `catpart/geometry/ply.py`   |    45 | `geometry/ply.rs`         | binary-LE PLY writer |
| `catpart/geometry/errors.py`|    48 | `geometry/errors.rs`      | classified error seam |
| `catpart/geometry/export.py`|   623 | `geometry/export.rs`      | orchestration + recovery |
| `catpart/geometry/composite.py` | 1,916 | `geometry/composite.rs` | **the whale** (§10.2) |

Reference size: 4,108 decode lines (657 L1 + 3,451 geometry); composite.py
alone is 55% of the geometry package. Rust lands at roughly the same
line count for this byte-walking code style (1.0–1.3×). Every Rust
module's doc header cites the same evidence notes its Python twin
cites (ADR-0002's docstring discipline, carried over).

`Cargo.toml`: `crate-type = ["cdylib", "rlib"]` — **one crate, two
targets**. The `rlib` compiles native (the Fidelity harness drives
this — faster and simpler than driving a browser); the `cdylib`
compiles `wasm32-unknown-unknown` (what the viewer ships). Same code
proves Fidelity natively and ships to the browser; the in-browser
reproduction run (§3.4) closes the residual gap (a
wasm-linkage-only bug would be invisible to native runs — caught
there, not by hope). Toolchain pinned by `rust-toolchain.toml`.

Dependencies, kept minimal (the decode is `struct`-walking, the JSON
is output-only):

- `wasm-bindgen` (+ `wasm-bindgen-test` dev) — the boundary and the
  headless WASM tests. Chosen over a bare `wasm32-unknown` target
  with hand-rolled JS imports: wasm-bindgen generates the `--target
  web` ES-module glue that gh-pages serves without a bundler, and
  its Node test runner gives CI a real run of the shipped artifact
  (section 7).
- `serde` + `serde_json` — serialize the summary structs mirroring
  `export-summary-v1.json` and schema-v1 fields (field declaration
  order = Python dict construction order, so even *byte* JSON
  equality is reachable, though Fidelity compares parsed documents —
  §3.2). Hand-rolled JSON rejected: the input side is the CATIA
  binary, not JSON; only the output needs JSON and serde is
  battle-tested for it.
- No other runtime crates. No `wasm-pack` dependency in the crate
  itself; `wasm-pack build --target web` is the packaging step
  (pinned version, documented in the ticket) producing
  `port/pkg/` — plain ES module + `.wasm`, importable directly.

### 2.2 The numeric contract (the Fidelity keystone)

The decode is **bit-exact by construction only if the port preserves
the Python reference's float behavior**. Measured surface of the
reference (verified by reading the modules, 2026-11-13):

- All coordinates are read as **f32 and widened to f64 at load**
  (`struct.unpack('f')` yields an exact widening; `_f32` at
  `composite.py:222`, pool records at `pool.py`). Every downstream
  value is an f64 derived from these or from integers.
- **Every decision arithmetic is IEEE-exact**: `+ - * /` and
  comparisons only. There are no transcendentals, no `sqrt`, no
  library calls beyond `math.isfinite` in the decode path. The
  decisive predicates are exact-equality or verbatim-constant
  comparisons: the degenerate-triangle test is tuple equality against
  `(0.0, 0.0, 0.0)` on a cross product (`facets.py:decode_soup`);
  `_nice` is `v == v and abs(v) < 1e9` (`composite.py:226`); the
  raw-array nicety is `v == v and (v == 0.0 or 1e-6 < abs(v) < 1e7)`
  (`composite.py:1258`); plane classification uses `PLANE_TOL = 2e-3`
  (`composite.py:524`); re-listing matching uses `NOISE_REL = 1e-5`
  with the exact `max(1.0, abs(...), ...)` scale expression
  (`composite.py:1002-1018`); the L2 sanity gate pins
  `MAX_DEGENERATE_TRIANGLES = 0` (`fitness/runner.py:265`).

Therefore the port MUST:

1. Load coordinates as f32 and widen to f64 once, at load; **all
   arithmetic in f64, never f32** (f32 rounding at a different point
   flips exact-equality decisions).
2. Preserve **operation order and expression shape** verbatim from
   the Python (no reassociation, no factoring: `a*b - c*d` stays
   exactly that).
3. **No fused multiply-add.** Rust never applies fast-math on
   stable — but `clippy::suboptimal_flops` *suggests* `mul_add` for
   `a*b ± c*d` patterns, and accepting that suggestion changes
   rounding and breaks exact-equality decisions. The decode modules
   carry `#![allow(clippy::suboptimal_flops)]` (or the lint set
   denies it — pinned in V0's clippy configuration) and the rule is
   written into the port's crate docs.
4. Copy every tolerance/equality constant verbatim
   (`1e9`, `1e-6`, `1e7`, `2e-3`, `1e-5`, `0`) — including exact
   `==` comparisons that a "robustness" refactor would replace with
   epsilon tests.

The Fidelity harness is the detector of any violation: a single
flipped decision cascades into a different triangle list and a PLY
digest mismatch on the corpus. Fixture-mode parity additionally
covers each decision path explicitly (the degenerate-skip and
noise-matching fixtures exist; V2/V3 add the missing ones, §5).

### 2.3 What the WASM boundary exposes

**Two whole-buffer entries, no streaming:**

- `decode_inspect(bytes) -> JsValue` — the schema-v1 inspect document
  (what the metadata panel renders).
- `decode_export(bytes) -> { summary, vertices: Float32Array,
  triangles: Uint32Array, curves: Array<Float32Array> }` — the
  export-summary object, the pool in walk order, the decoded
  triangles, and the decoded polyline loops (the curve-entry point
  sequences) for the overlay.
- Failure: both return a classified error
  `{ error_class, detail }` with the exact Python error-class
  vocabulary (`missing-geometry-store`, `undecoded-variant`,
  `malformed-store-header`, `malformed-pool-group`,
  `malformed-pool-vertex`, `unreadable-file`/`io-error`) — the
  viewer displays it; nothing is hidden.

Rationale, with alternatives:

- **Single entries vs streaming pieces**: the decode is one pass over
  an in-memory buffer (the Python reference mmaps the whole file;
  `build_export` writes the PLY only after the whole store decodes);
  the viewer loads the whole file on drag-drop anyway (wasm32's 4 GB
  address space vs ≤ ~120 MB corpus maxima); streaming would split
  the seam the harness compares and buy nothing at this scale. If a
  future corpus outgrew the model, that is a new decision, not this
  spec's shape.
- **Typed arrays vs JSON strings at the boundary**: the viewer
  consumes arrays directly (a JSON round-trip per mesh is waste);
  serde_wasm_bindgen converts the summary struct to a JsValue with
  no string intermediate. The **JSON contract lives where it is
  measured**: the native CLI (below) writes the JSON documents the
  harness compares.
- **`curves` is additive and NOT part of the Fidelity definition**:
  the Python reference has no counterpart artifact (the curve-entry
  laws land the loops either unexported or dup-pinned *into the
  mesh*; the overlay shows the pre-weld decoded point sequences).
  Pinned here so nobody later "repairs" a Fidelity run by comparing
  curves. Fidelity compares exactly what §3.2 says.

### 2.4 The native CLI seam

`port/src/bin/fidelity-cli.rs` — a native binary with the **same I/O
contract as `catpart-export`/`catpart-inspect`**: file path argument,
summary JSON on stdout, PLY to a second path argument, classified
error as one JSON line on stderr with exit 1 (usage errors exit 2).
The harness drives both implementations as subprocesses through one
shape, so a mismatch is attributable to the decoder, never to harness
plumbing. (Alternative considered: harness links the `rlib` in
Python via PyO3 — rejected: a second FFI seam to keep bit-faithful;
subprocess is the house's proven shape — the fitness runner already
drives the console scripts.)

## 3. Fidelity and the in-browser margin — pinned definitions

The ROADMAP acceptance words ("Fidelity-1 on the corpus, 0
mismatches"; "in-browser sanity = published L2 scalar ± declared
margin") get exact meanings here; tickets cite these subsections.

### 3.1 Populations

- **L1-JSON slice**: all 1,824 manifest rows (`kind` = part, product,
  and the `magic_ok=no` junk the manifest records) — the inspect
  document is compared for every file the reference parses, junk
  included: the port must reproduce the reference's behavior on
  garbage, not only on well-formed parts.
- **L2-export slice**: the L2 population = manifest rows with
  `kind=part` (the runner's `L2_POPULATION_KIND`; 1,442 today:
  Dev 1,381 + held-out 61). **Successes and fail-closed parts
  alike**: a part where the reference raises `undecoded-variant`
  must raise the same class in the port. A port that matched only
  the 1,173 exports would be silently wrong on the classified 269.
- Both measured on the machine holding `corpus/` (ADR-0003); the
  corpus never leaves it and never enters CI.

### 3.2 Artifacts and diff definition

| Artifact | Python source | Port source | Diff |
| -------- | ------------- | ----------- | ---- |
| inspect document (schema v1) | `catpart-inspect` stdout | `fidelity-cli inspect` stdout | parsed-document equality |
| export summary (`export-summary-v1`) | `catpart-export` stdout | `fidelity-cli export` stdout | parsed-document equality |
| mesh | the binary-LE PLY file | `fidelity-cli export` PLY | **byte-identical** |
| classified failure | stderr JSON line, exit 1 | same | `error_class` string equality |

- **Parsed-document equality** (JSON): parse both sides, recursive
  structural equality — object key sets equal, arrays equal *in
  order* (the warnings array is order-fixed by the schema's
  description; the composite block's counters compare fully — the
  schema's `additionalProperties: true` is an evolution promise for
  *consumers*, not a slack license for the port), numbers equal with
  int/float distinction preserved, floats compared exactly (f64 `==`
  after parse). Both sides emit shortest-round-trip decimals of
  f64s that hold widened f32s, so parsed equality is robust even
  where the decimal *renderings* differ — but any such rendering
  divergence is logged in the run note as an observation, not a
  mismatch.
- **Byte-identical PLY** = vertex-and-triangle equality exactly (the
  format is fixed and little-endian f32/u32), reusing the
  established artifact; when a mismatch fires, both PLYs can be
  opened in a neutral viewer for triage.
- **`error_class` equality; `detail` not compared byte-wise** — the
  detail is human prose citing evidence; the machine contract is the
  class (that is what the fitness classification consumes). The
  detail must be non-empty and cite the violated claim (house
  convention, carried into the port).
- Any harness-level failure (timeout, missing binary, unreadable
  output) is recorded as its own outcome class and **never counts as
  a match** — the run is invalid until every row is
  match/mismatch/error-class-mismatch by evidence.

Fidelity-1 = 0 mismatches across both slices in one run (one CSV,
per-file rows, #37-arithmetic-composable note).

### 3.3 Reference drift rule

The Python package remains the reference (ADR-0001). If Phase 5 needs
a reference change (e.g. a bug fix that changes an export), the
change lands in Python first with its own fitness row under no-regret,
the Fidelity run re-baselines on the new reference, and the port
follows. The port never diverges from the reference to "win" a
comparison — a mismatch is always repaired on the port side or
documented as a reference correction (dated, never massaged).

### 3.4 In-browser reproduction margin

**Declared margin: 0.** The in-browser sanity rate must equal the
published L2 scalar exactly, per split (Dev and held-out). Rationale:
the browser runs the same crate the harness proved byte-faithful;
IEEE arithmetic inside WASM is fixed; there is no legitimate source
of rate variance, only bugs — and margin 0 makes any of them a hard,
visible failure ("never hidden"). The one declared exclusion:
**harness-error files** (browser crash, timeout, OOM on a
pathological file) drop out of the compared rate and are reported
per-file in the run note — excluded from the arithmetic, never
silent.

The page's in-browser gate reimplements `_score_export` exactly:
same check order (empty → manifold → finite plausible bbox →
degenerate ≤ 0), same constants. V5's harness compares **per-file
per-check outcomes** against the Python fitness record, not only the
aggregate scalar — stronger than the ROADMAP wording, adopted here.

## 4. Fidelity harness design

`scripts/fidelity_run.py` — stdlib-only Python (the
`publish_fitness.py` convention for local tools), **dual-mode**:

- **Fixture mode** (`--fixtures`): generates the A2 synthetic
  fixtures via `tests/fixtures_gen.py` in-process, runs both
  implementations over them, diffs — wired into the gate as
  `tests/test_port_fidelity.py`. This is how "CI covers the port
  with the synthetic fixtures from A2" is satisfied **with one
  harness**: the same diff code proves parity in CI on fixtures and
  locally on the corpus. Fixture mode also drives the WASM artifact
  subset under Node (§7) so CI runs, not merely builds, the shipped
  artifact.
- **Corpus mode** (default, local-only): walks
  `manifests/corpus-manifest.csv`, applies the slice populations
  (§3.1), drives:
  - Python reference: the console scripts as subprocesses (the
    exact shipped seam — no in-process imports).
  - Rust port: `target/release/fidelity-cli` (built once per run by
    `cargo build --release`; the run aborts if the binary is stale
    or missing).
- Run shapes: `--sample stratified:N` (stratify by detected_version
  × split × export outcome class, drawing from the accepted run's
  CSV — the stage CSVs name the per-family stores, so V2/V3 samples
  can bias to the families under work), `--split dev|held-out|all`,
  `--slice l1|l2|both`.
- Outputs: a dated evidence note + per-file CSV under
  `docs/evidence/data/` in the established format (outcome =
  match / output-mismatch / error-class-mismatch / harness-error;
  python/port error classes; PLY equality flag; first-divergence
  detail). The note's figures are CSV-composable (#37 arithmetic
  gate applies, as to every note).

**Runtime budget** (target, measured and corrected at V1's first
sample run — stated as design target, not measurement): full
dual-slice run ≤ 2 h wall-clock on the corpus machine. Basis: the
existing full fitness runs (L1+L2 over the corpus, same subprocess
shape) complete comfortably inside this; the Python pass dominates
(Rust native is expected 10-100× faster on the byte-walking). No
caching of reference outputs: the corpus is frozen and a full run
fits the budget; a digest cache would add a stale-cache failure mode
to a tool whose only job is to be believed. Per-ticket sample runs:
≤ 15 min at N=100.

## 5. Viewer shell

- **Location**: `site/viewer/` (viewer.html, viewer.js ES modules,
  vendored `three.module.min.js`, wasm-bindgen `pkg/` output copied
  at build). `scripts/publish_fitness.py` copies `site/` verbatim
  into gh-pages — **the publication mechanism needs zero changes**;
  the viewer publishes as soon as its files are committed. That
  purity is why the next decision goes the way it does.
- **Committed build artifacts**: `port/pkg/` (wasm + glue) and the
  vendored three.js are committed. Rejected alternative: building at
  publish time — that would put node/wasm-pack into the publication
  path and break ADR-0003's stdlib-only, pure-function-of-committed-
  content design (two machines must render byte-identical gh-pages
  trees). Cost accepted: binary blobs in review diffs, mitigated by
  pinned toolchains (§10.5).
- **No bundler, no framework, no node_modules in the published
  tree** — the existing site/ is hand-written static ES modules with
  zero runtime dependencies (shields badges excepted), and the
  viewer keeps that property: wasm-bindgen `--target web` glue is a
  plain ES module; three.js ships as a single vendored ES module;
  viewer code is hand-written ES modules.
- **Three.js policy: vendored, version-pinned, sha256-recorded**
  (URL + digest in the vendoring ticket's evidence note). CDN import
  rejected: a floating runtime dependency breaks the reproduction
  run's "exactly what ships" property and the site's offline
  robustness; the shields badge remains the one accepted external
  service (ADR-0003), and this policy keeps it that way. The pin
  floats only by a deliberate, dated re-vendor.
- **UI surface** (all client-side): drag-drop / file-picker of a
  `.CATPart`; orbit/zoom + wireframe/solid toggle on the decoded
  mesh; in-browser sanity invariants computed and displayed (the §3.4
  gate); metadata panel rendering the schema-v1 document (document
  name, detected version, kind, container inventory); curve overlay
  toggle over the decoded polyline tables; **classified-failure
  display** — a file that fails decode shows its `error_class` and
  detail, never a blank screen.

## 6. Ticket breakdown

Pattern: spec issue #39 (exists) with child tickets, bounded per
`docs/agents/dispatch-recipes.md` (one concrete deliverable, explicit
STOP, partial-with-named-ambiguity acceptable). **Recommendation on
the existing V1–V5 (#40–44): re-scope in place** — keep the numbers
(#40/#41/#42/#43/#44 map to V1/V2/V3/V4/V6 below), edit bodies at
publication time, add V0 and V5 as new issues. They are stale in two
places this spec corrects: V3's "gated on the numbering law
(candidate today)" predates the Phase 4 close (the composite model —
table-walk, per-rep, raw-array, mixedwrite, dup-pin, dedup — **is
landed** in the reference; there is no gating question left, only a
port), and the ticket set lacks the toolchain/CI slice and the
separated in-browser harness. Closing and recreating would churn
issue numbers for nothing.

Order is dependency-linear (the graph is a chain; the only
parallelizable pair is V4-glue drafting against V3's late stages, and
the house rule serializes child turns anyway — no schedule is built
on overlap). The harness lands **early (V1)** so every later port
ticket re-runs it per-stage and drift is caught per-ticket, not at
acceptance.

### V0 — Rust toolchain, crate skeleton, CI wiring — **S**

- **Scope**: `port/` crate skeleton (modules per §2.1 as stubs),
  `rust-toolchain.toml`, clippy/rustfmt configuration carrying the
  §2.2 numeric-contract lint policy, CI steps added
  (`.github/workflows/ci.yml`: cargo build native + wasm32,
  fmt/clippy/test), `scripts/check.sh` mirrors the same steps (the
  gate grows the cargo steps; gate count changes are documented in
  the ticket). Fixture-mode fidelity test lands as a skip-pending
  stub.
- **Acceptance**: `cargo build` (native) and
  `cargo build --target wasm32-unknown-unknown` green locally and in
  CI; gate green including the new steps; CI runtime measured and
  recorded (budget: the whole workflow stays under ~10 min with
  cargo cache).
- **Depends**: nothing. **Estimate: S.**

### V1 — L1 slice port + Fidelity harness — **L** (re-scopes #40)

- **Scope**: port `header.rs`/`containers.rs`/`trailer.rs`/
  `version.rs`/`identity.rs` + `fidelity-cli` (inspect mode);
  `scripts/fidelity_run.py` dual-mode + `tests/test_port_fidelity.py`
  fixture pin; the corpus-sample run machinery.
- **Acceptance**: fixture-mode parity green in the gate (inspect
  document equality on the A2 fixtures incl. corrupted variants);
  one local corpus run on a stratified sample (≥ 100 files, both
  splits, parts + products + junk rows) recorded as evidence note +
  CSV with **0 L1-JSON mismatches**; the run's wall-clock measured
  against the §4 budget and the budget note corrected if needed.
- **Depends**: V0. **Estimate: L.**

### V2 — Geometry core port (non-composite) — **L** (re-scopes #41)

- **Scope**: port `store.rs`, `pool.rs`, `facets.rs`, `mesh.rs`,
  `ply.rs`, `errors.rs`, `export.rs` (store location incl. the
  stage-3a/12 recovery probes, pool, tiling, soup, PLY write,
  classified failures) — everything except `composite.rs`.
  `fidelity-cli` grows export mode. Fixture generator gains the
  missing non-composite parity shapes if the harness exposes any
  gap.
- **Acceptance**: fixture parity green on all geometry-bearing A2
  variants (canonical store, recovery variants, corrupted classes)
  — summary + PLY byte-identical + error classes equal; local
  corpus sample (≥ 100 parts, biased to non-composite exports AND
  to fail-closed classes: `undecoded-variant`, missing-store
  families) 0 mismatches; per-stage harness re-runs recorded.
- **Depends**: V1. **Estimate: L.**

### V3 — Composite decode port — **L** (re-scopes #42; stale gate resolved)

- **Scope**: port `composite.rs` — the full landed model: table-walk
  identity, per-rep decomposition, raw-array, mixedwrite, the
  E0/dup-pin curve-entry law, unordered dedup, the composite summary
  block. Internal stage order (each stage ends with a harness
  re-run, the stage grind's discipline at port speed):
  walk + per-rep → raw-array + mixedwrite → dup-pin + dedup +
  curve exposure for the overlay. Fixture generator gains the
  composite family shapes (multi-rep, raw-array, mixedwrite,
  dup-pin-firing, dedup-firing) — the fixture work belongs here,
  where the families are known.
- **Acceptance**: fixture parity green on the composite variants;
  local corpus run over a composite-family-stratified sample
  (≥ 100 stores drawn per-family from the accepted stage-15 CSV,
  incl. every firing law and the fail-closed composite class)
  0 mismatches incl. the composite summary block; PLY bytes equal.
- **Depends**: V2. **Estimate: L.**

### V4 — WASM boundary + viewer shell — **M** (re-scopes #43)

- **Scope**: wasm-bindgen entries (§2.3), `wasm-pack --target web`
  packaging, three.js vendoring (pinned + sha256 note),
  `site/viewer/` app: drag-drop, orbit/zoom, wireframe/solid,
  in-browser sanity display, metadata panel, curve overlay,
  classified-failure display. Committed pkg/ artifacts; publish
  flow unchanged (§5).
- **Acceptance**: scripted fixture checks in a headless browser
  (Playwright, local): canonical fixture renders non-empty with
  finite bbox; metadata fields present; overlay toggles; a corrupted
  fixture shows its classified error; no server component (static
  files only, verified by serving `site/` read-only during the
  check). wasm-bindgen Node tests green in CI (§7).
- **Depends**: V3 (the viewer needs the full decode; glue may be
  drafted against V2 but not accepted). **Estimate: M.**

### V5 — In-browser reproduction harness — **M** (new; split out of #44)

- **Scope**: the automated headless-browser run over the L2
  population (local, corpus machine): drives the committed viewer
  from a read-only local static serve of `site/`, feeds every L2
  population file, reads the per-file per-check outcome the page
  computes (§3.4 gate mirror), aggregates per split, writes note +
  CSV (#37-composable). Playwright + pinned Chromium, local-only,
  never CI.
- **Acceptance**: full-population run recorded; rate equals the
  published L2 scalar with **margin 0** per split (§3.4);
  per-file outcomes match the Python fitness records' per-check
  outcomes; harness-error files excluded-but-reported; the run
  note states the margin declaration and the exclusion list
  explicitly.
- **Depends**: V4. **Estimate: M.**

### V6 — Acceptance + publication — **M** (re-scopes #44)

- **Scope**: the full Fidelity-1 corpus run (both slices, §3.1/§3.2,
  0 mismatches) + the full in-browser reproduction run + publication:
  viewer live on gh-pages via the unchanged publish flow, ROADMAP
  Phase 5 status block, README/README.es updates, spec E #39 closed
  with the acceptance evidence.
- **Acceptance**: ROADMAP Phase 5 acceptance criteria verbatim:
  Fidelity-1 (0 mismatches); in-browser sanity = published scalar
  ± 0; mesh, metadata panel, curve overlay operational; every
  failure classified, never hidden; close artifacts landed (note +
  CSVs + status blocks), no-regret untouched (the phase changes no
  fitness row — the Python reference is not modified).
- **Depends**: V1 V2 V3 V4 V5. **Estimate: M.**

**Totals: 3 L + 3 M + 1 S.** Effort shape: the whale is V3
(~1,900 reference lines, the subtle laws); V2 is the widest slice;
V1 carries the harness that de-risks both.

## 7. CI strategy (A5 amended deliberately)

ADR-0003 keeps GitHub Actions light; the ROADMAP separately mandates
"CI covers the port with the synthetic fixtures from A2". The
reconciliation, sized:

**CI gains** (all fixture-only, corpus-free):

1. Rust toolchain (pinned via `rust-toolchain.toml`, cargo cached).
2. `cargo build` native + `wasm32-unknown-unknown` (the port
   compiles = the WASM artifact is buildable; V0).
3. `cargo fmt --check` + `cargo clippy -D warnings` (the ruff
   analog; the numeric-contract lint policy from §2.2 pinned here).
4. `cargo test` (Rust-internal unit tests, fixture-free micro tests).
5. The fixture-mode fidelity harness as a pytest pin
   (`tests/test_port_fidelity.py`) — native-vs-Python on A2
   fixtures (V1+).
6. `wasm-pack build --target web` succeeds + `wasm-bindgen-test`
   under **Node** on a small fixture subset (canonical store +
   corrupted variants) — CI *runs* the shipped artifact headlessly,
   catching wasm-linkage-only bugs the native tests cannot see
   (V4+).

**CI stays out of**: the corpus (ADR-0003), real-browser runs (the
in-browser reproduction is a local corpus-machine job — browser
install and 1,442 file feeds do not belong in Actions), publication
(publish_fitness.py stays hand-run, ADR-0003).

**Weight honestly stated**: the workflow grows from ~1 min
(ruff+pytest) to ~5-10 min with a cold cargo cache (seconds warm).
That is the price of the ROADMAP's own requirement; it is an
amendment of A5's "light" in letter, not in spirit — no corpus, no
browsers, no publish automation cross the line. `scripts/check.sh`
mirrors every added step (the #38 rule: the gate is CI's local
copy), which makes the Rust toolchain a required dev dependency from
V0 on.

## 8. What this spec decides vs what it leaves

Decided here (design judgment, reasoned): crate layout and module
mapping (§2.1); the numeric contract (§2.2); whole-buffer entries,
typed-array boundary, additive curves artifact (§2.3); native
CLI seam (§2.4); Fidelity populations/diff/margin-0 definitions
(§3); harness location and dual-mode design (§4); viewer location,
committed artifacts, vendored pinned three.js, no-bundler policy
(§5); ticket graph V0-V6 with estimates and acceptance (§6); CI
shape and honest weight (§7).

Left to the owner (review points, not blockers): the issue-vs-doc
recommendation below (§9) needs a yes; the committed-build-artifacts
decision (§5) and the margin-0 declaration (§3.4) are
owner-reviewable before publication; the gate's new toolchain
requirement (§7) lands with V0 and should be noted at publication.

## 9. Recommendation: spec doc + spec issue + tickets (hybrid)

**Recommendation: this document (committed at `docs/specs/`) becomes
the design authority; ONE spec issue (#39, re-scoped) carries the
acceptance checklist and links here; the V-tickets stay GitHub
sub-issues.** Not the spec D pattern (one issue whose body holds the
whole design).

Reasons:

1. **Diffability**: the design content here (numeric contract,
   harness definition, margin declaration) reviews and corrects
   better as a versioned file — the house records corrections dated,
   never massaged, and a git diff shows that; issue bodies don't.
2. **Citable**: Rust module docstrings will cite this spec's
   sections the way Python docstrings cite evidence notes
   (ADR-0002's discipline); an anchor (`docs/specs/…#numeric-
   contract`) is a stable citation, an issue comment is not.
3. **Bounded tickets**: dispatch discipline wants each ticket small;
   tickets cite spec sections instead of restating design, so the
   issue bodies stay short and the spec stays single-sourced.
4. **The tracker keeps its job**: #39 + sub-issues + labels
   (`ready-for-agent`) + wayfinding keep working unchanged;
   `docs/agents/issue-tracker.md`'s "specs live as GitHub issues"
   convention is amended by this recommendation in exactly one
   respect (the *design document* is a repo file; the *spec issue*
   still exists and links it).

Publication mechanics for the coordinator (not this branch's job):
commit the doc (this branch), edit #39's body to link the doc and
carry the acceptance checklist, re-scope #40–44 per §6's mapping,
create V0 and V5, set dependencies per §6, apply labels.

## 10. Risks, honestly

1. **Float-decision drift (the top risk)** — §2.2's contract exists
   because a single flipped exact-equality decision (degenerate
   test, `_nice`, `NOISE_REL` match) cascades into a different mesh.
   Concrete trap identified: `clippy::suboptimal_flops` *recommends*
   `mul_add`, which changes rounding; the lint policy must freeze
   arithmetic shape, and the harness must run before any "clippy
   cleanup" is allowed near the decode modules. Detection is
   structural: any flip is a corpus-visible PLY mismatch; fixtures
   exercise each decision path.
2. **The composite whale** — `composite.py` is 1,916 lines (55% of
   the geometry package) carrying the subtlest laws (walk-exact
   lists, per-rep decomposition, raw-array, mixedwrite, dup-pin,
   dedup). Mitigation: V3's internal stage order with a harness
   re-run per stage, and family-stratified corpus samples drawn from
   the accepted stage CSVs (every firing law represented).
3. **Summary-detail parity long tail** — the composite block's
   counters and the ordered warnings array make parity
   all-or-nothing per file. Mitigation: the harness reports the
   *first divergence per file* structurally (path + both values),
   and fixtures cover each warning class so the tail is met in CI
   before the corpus sees it.
4. **In-browser gate drift** — the JS gate reimplements
   `_score_export`; logic drift would move the measured rate
   silently. Mitigation: §3.4's margin 0 plus per-file per-check
   comparison against the Python fitness records (not just the
   aggregate).
5. **Committed build artifacts** — `port/pkg/` and vendored three.js
   put binary blobs in review diffs; wasm builds are not guaranteed
   byte-stable across toolchain versions. Mitigation: pinned
   toolchain + pinned wasm-pack + sha256-recorded vendor pin; the
   publish flow stays a pure function of committed content (the
   alternative — build-at-publish — was rejected in §5 for breaking
   ADR-0003's design).
6. **wasm-bindgen glue churn** — major versions change the generated
   glue API. Mitigation: pin the crate version; upgrades are
   deliberate, dated, and re-run the harness.
7. **CI weight** — §7 states it: ~5-10 min cold. The failure mode to
   watch is scope creep (browsers, corpus-adjacent artifacts) — the
   spec pins the exclusion list.
8. **Browser memory on big files** — the largest corpus file is
   ~120 MB; drag-drop holds the ArrayBuffer plus the WASM copy plus
   decoded arrays (≈3× transient peak). Desktop-target only (§1);
   the reproduction run surfaces any file the browser cannot hold as
   a reported harness-error (excluded-but-reported, §3.4).
9. **Curve overlay scope** — the overlay consumes decoded
   element-space polylines that the reference never emits as a
   standalone artifact; §2.3 pins them additive and outside
   Fidelity. The residual risk is scope creep into re-decoding the
   `33 3X` curve-record families beyond what the landed laws
   produce — not in this phase.
10. **Reference drift mid-port** — a Python-side correction during
    Phase 5 invalidates in-flight parity. §3.3's rule makes Python
    first, harness re-baseline, port follows — never the reverse.

## 11. Amendment register

- 2026-11-13: initial draft (branch `t3/phase5-spec-draft`, off main
  `6c6b3e8`). Coordinator review pending; nothing published.
