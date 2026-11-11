# ROADMAP — catpart-parser

Goal: a free, open-source reader for CATIA V5 `.CATPart` / `.CATProduct`
binaries, growing in capability levels and terminating in a web viewer
that parses and renders these files entirely client-side. Each phase has
explicit acceptance criteria; a phase is done when they pass, not
before. The terminal state, the closure definition and the bar revision
rule are defined in **Terminal state and closure** below (owner
decision 2026-11-10, ADR-0004).

## Phase 0 — Corpus (L0)

Build a diverse, reproducible corpus of public CATIA V5 files.

- Source public `.CATPart` files (model-sharing sites, university course
  archives, open repositories) covering multiple CATIA V5 release lines
  (e.g. V5R19–V5-6R2024) and domains (mechanical parts, sheet metal,
  products/assemblies).
- Target: ≥ 100 files, multi-version coverage.
- Every file is recorded in `manifests/corpus-manifest.csv` with SHA-256,
  source URL, reported CATIA version, size. Binaries live in gitignored
  `corpus/`; only manifests are committed.

**Acceptance:** manifest complete, spot-check digests reproduce, version
coverage summarized in `docs/corpus-report.md`.

## Phase 1 — Byte-level triage (L0)

Reproducible evidence, not guesses.

- Inventory and hash every file; measure byte entropy per region; identify
  magic numbers, container boundaries, compression candidates.
- Compare structurally similar files (same author/version) to isolate
  per-object vs per-file fields.
- Record dated evidence notes under `docs/evidence/` referencing byte ranges
  and digests. Negative results are recorded too.

**Acceptance:** a written triage report identifying at least the outer
container structure and compression status, backed by evidence notes.

## Phase 2 — Structure inference (L1)

- Infer section layout: object containers, name/type tables, units,
  parameter blocks.
- Cross-validate inferred fields across the whole corpus (a field that only
  explains one file is not yet a field).

**Acceptance:** a draft format document (`docs/format/`) describing the outer
structure with evidence per claim.

**Status (2026-11-08): met** — `docs/format/` v1 (commit `812d630`): one
page per structural area (header, tail catalog, container table, trailer,
payload blocks, geometry) plus `validation.md` (cross-validation summary
across R15–R32, the R19/R21 differential verdicts, corrections register).
146 table claims — 114 established / 15 candidate / 17 open (live
inventory 2026-11-10, #34/#36; plus 19 paragraph claims) — every claim with
byte ranges, version scope, label and evidence link; consistency kept by
`scripts/triage/check_format_claims.py` (pinned by tests), which also
polices this headline against the live inventory. The document
alone supports implementing the outer structure + container-inventory
level that the shipped L1 parser emits.

## Phase 3 — L1 parser

- CLI `catpart-inspect <file>` outputting metadata + feature tree + units as
  JSON.
- A fitness runner that parses the full corpus and reports the clean-parse
  rate; CI keeps it visible.

**Acceptance:** ≥ 80% clean-parse rate on the corpus with stable JSON output.

**Status (2026-11-08): met** — measured as L1 clean-parse on Dev
(1751 non-held-out manifest files): **1745/1751 = 99.66%**, held-out
(Motor-V6) 73/73 = 100%, no-regret chain intact (ADR-0001) in
`fitness/history.jsonl` (4 rows: accepted baseline + 3 rejected
equal/no-op attempts under strictly stronger checklists and extended
output — the climb is strengthening at a constant scalar). Stable JSON:
schema v1, additive evolution, all clean outputs schema-valid.
Remaining 6 failures classified (ticket #26): all `magic_ok=no` corpus
junk (mislabeled non-CATIA files), none are parser bugs or undocumented
structures. The planned "feature tree + units" L1 output landed as the
measured reality allows: container inventory (`containers[]` with
base-class annotation) + `document_name`; units: documented negative
(2026-11-08 probe) — see `docs/format/container-table.md`,
`docs/format/payload-blocks.md` and the #24/#25 resolution comments.

## Phase 4 — L2 geometry

- Extract mesh/curve data; export to STEP or a renderable mesh format.
- Geometric sanity checks become part of fitness (no NaNs, closed volumes
  where expected).

**Acceptance:** subset of corpus exports geometry that a neutral viewer
renders sanely.

## Phase 5 — Web viewer, parts (L2 delivery surface)

A browser viewer that opens arbitrary `.CATPart` files with 100%
client-side parsing at native-level fluidity. Owner decision
(2026-11-10): upfront cost is accepted in exchange for performance and
experience; the decode pipeline is ported to Rust compiled to WASM
(ADR-0004).

- Port the decode pipeline: header, container table, trailer, nested
  store, vertex pool, primitive/facet semantics, composite index space.
  The Python package remains the reference implementation and the
  fitness seam (ADR-0001 untouched) — the port must prove it produces
  what the validated implementation produces (**Fidelity**, see
  GLOSSARY).
- Fidelity harness: port output (mesh + JSON) identical to the Python
  reference over the corpus, measured on the machine holding `corpus/`
  (ADR-0003 — never in CI); CI covers the port with the synthetic
  fixtures from A2.
- Viewer shell: render layer (e.g. Three.js) + WASM glue; orbit/zoom,
  wireframe/solid, mesh sanity in the browser; metadata panel rendering
  the schema-v1 JSON (document name, detected version, container
  inventory); curve overlay of the decoded polyline tables. Static
  hosting on `gh-pages`; no server.
- In-browser reproduction: an automated local run (headless browser)
  over the L2 population; its in-browser sanity rate must equal the
  published L2 scalar within a declared margin.

**Acceptance:** Fidelity-1 on the corpus (0 mismatches vs the Python
reference); in-browser sanity = published L2 scalar ± declared margin;
mesh, metadata panel and curve overlay operational in the browser;
every failure classified, never hidden.

## Phase 6 — Assemblies

`.CATProduct` support in the viewer: load a product, resolve its
referenced parts, place instances. New format territory — today a
documented negative (products carry no geometry store, 0/37 sampled;
the container table carries no instance hierarchy, ticket #24).

- Census first (the Phase 4 method): classify 100% of the corpus
  product population by root cause — link tables (e.g.
  `CATXDocLinkCont`), instance records, transforms, what is absent —
  with per-part byte evidence and ceiling arithmetic.
- Decode the link/transform model the census supports; the viewer grows
  an assembly mode (the user supplies the product and its referenced
  part files together).

**Acceptance:** census closed (100% classified, notes + CSVs committed);
an assembly bar derived from the census arithmetic and met in the
viewer under the same mechanical rules; documented negatives for
everything the census shows unreachable.

## Phase 7 — B-rep (L3)

Precise B-rep extraction (exact solids, surfaces, curves; e.g. STEP
export). The L3 Fitness definition stays ADR-0001's construct coverage
with one finite-making amendment (owner decision 2026-11-10): the
denominator is the construct vocabulary **frozen by this phase's
census**, not the open-ended `docs/format/` inventory — the old
"may remain partial indefinitely" is retired.

- Census first: classify the geometry-store population at B-rep level
  and freeze the construct vocabulary the corpus contains.
- One decode ticket per construct class the census produces; every
  construct ends either decoded with verified semantics or closed with
  a documented negative plus published ceiling arithmetic.
- Parametric recipe recovery (features, sketches, editable parameters)
  is explicitly out of scope for this phase (documented negative; the
  Phase 3 specification-tree negative stands).

**Acceptance:** 100% of the frozen vocabulary resolved (decoded or
negatived); the L3 headline reported alongside L1/L2 under no-regret;
the corpus rate is reported alongside and never gates.

## Terminal state and closure (owner decision 2026-11-10; ADR-0004)

The project is **100% done** when, in order:

1. **Phase 4 (L2)** closed: the 80% Dev bar met under no-regret on
   Held-out with every failure classified — or the bar re-adjusted by
   the pre-authorized rule below.
2. **Phase 5 (viewer, parts)** acceptance met.
3. **Phase 6 (assemblies)** acceptance met.
4. **Phase 7 (B-rep)** acceptance met.
5. **Closure artifacts shipped**: tag `v1.0` + release notes; final
   fitness report published (gh-pages); this ROADMAP with every phase
   closed or negatived; corpus frozen (the verified 2026-11-07 backup
   stands); remaining issues labelled `post-v1.0`.

The repo stays public and usable; no maintenance is promised. A later
bugfix may ship as `v1.0.1` without reopening the project.

**Pre-authorized bar revision rule.** If a phase's census + decode
demonstrate, with published ceiling arithmetic, that the reachable
ceiling is below that phase's bar, the bar is re-adjusted to
ceiling − declared margin and the phase closes with documented
negatives (corrections recorded, never massaged). First applied to the
L2 80% bar: the composite numbering law is candidate, and the located
cap is 75.2% if it fails (2026-11-10 census,
`docs/evidence/2026-11-10-l2-grind-classification.md`).
