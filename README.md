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

**Research phase — format triage.** No parseable output yet. See
[docs/ROADMAP.md](docs/ROADMAP.md) and
[docs/research/format-landscape.md](docs/research/format-landscape.md).

## Roadmap

| Level | Deliverable | Status |
|---|---|---|
| L0 | Public corpus + byte-level triage with reproducible evidence | planned |
| L1 | Container/section map, metadata, feature tree, units, names | planned |
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
