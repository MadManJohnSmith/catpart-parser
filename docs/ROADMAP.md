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

## Phase 4 — L2 geometry

- Extract mesh/curve data; export to STEP or a renderable mesh format.
- Geometric sanity checks become part of fitness (no NaNs, closed volumes
  where expected).

**Acceptance:** subset of corpus exports geometry that a neutral viewer
renders sanely.

## Phase 5 — L3 B-rep

Full parametric B-rep extraction. Long-term, incremental; may remain partial
indefinitely — every additional construct supported is a gain.
