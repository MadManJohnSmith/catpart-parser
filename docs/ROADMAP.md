# ROADMAP — catpart-parser

Goal: a free, open-source reader for CATIA V5 `.CATPart` / `.CATProduct`
binaries, growing in capability levels. Each phase has explicit acceptance
criteria; a phase is done when they pass, not before.

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
(2026-11-08 probe) — see `docs/format/README.md` sections 2, 4, 5 and
the #24/#25 resolution comments.

## Phase 4 — L2 geometry

- Extract mesh/curve data; export to STEP or a renderable mesh format.
- Geometric sanity checks become part of fitness (no NaNs, closed volumes
  where expected).

**Acceptance:** subset of corpus exports geometry that a neutral viewer
renders sanely.

## Phase 5 — L3 B-rep

Full parametric B-rep extraction. Long-term, incremental; may remain partial
indefinitely — every additional construct supported is a gain.
