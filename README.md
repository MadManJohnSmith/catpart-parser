# catpart-parser

An open-source parser for Dassault Systèmes **CATIA V5** part and product
files (`.CATPart`, `.CATProduct`) — reading the binary format directly,
**without a CATIA installation**.

## Why

CATIA V5 stores models in a proprietary, undocumented binary format. Today the
only ways to read these files are:

- Commercial converters (paid, closed source).
- COM automation of a running CATIA instance (requires a paid license).

There is no free, open-source binary parser. This project aims to be the
first complete one, enabling interoperability, archival access, and tooling
for everyone who receives CATIA files without owning a CATIA seat.

## Status

**L1 parser shipped — Phase 3 closed (2026-11-08).** `catpart-inspect`
emits schema-v1 JSON (header, container inventory with base-class
annotation, `document_name`, trailer, detected version) and
`catpart-fitness` measures clean-parse over the corpus: **Dev 99.66%
(1745/1751), held-out 100% (73/73)**, no-regret per ADR-0001. See
[docs/ROADMAP.md](docs/ROADMAP.md) (Phase 3 status block),
[docs/format/README.md](docs/format/README.md) (documented structures)
and `fitness/history.jsonl`. Phase 2 (format document assembly) is the
active front.

## Roadmap

| Level | Deliverable | Status |
|---|---|---|
| L0 | Public corpus + byte-level triage with reproducible evidence | done (Phase 0/1) |
| L1 | Container/section map, metadata, container inventory, names | done (Phase 3) |
| L2 | Geometry basics: meshes and curves exportable to STEP or renderable | planned |
| L3 | Full parametric B-rep (precise CAD solids) | planned, hardest |

## Method

- **Corpus-driven.** Fitness is the share of the corpus that parses cleanly,
  plus geometric sanity checks (renderable without NaNs, closed volumes).
- **Evidence-driven.** Every structural claim is tied to concrete byte ranges
  and file digests; negative findings are recorded too.
- **Interop-only reverse engineering.** We document observed structures; no
  proprietary code is redistributed. See *Legal* below.

## Legal

Reverse engineering a file format for interoperability. This project
redistributes no Dassault code and does not use leaked specifications. The
format documentation produced here is derived from observing real files and
documented tool behavior.

## License

[Apache-2.0](LICENSE) — chosen for its explicit patent grant.
