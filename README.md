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

[![L1 clean-parse (Dev)](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/MadManJohnSmith/catpart-parser/gh-pages/fitness-latest.json)](https://github.com/MadManJohnSmith/catpart-parser/blob/main/fitness/history.jsonl)

**L1 parser shipped — Phase 3 closed (2026-11-08).** `catpart-inspect`
emits schema-v1 JSON (header, container inventory with base-class
annotation, `document_name`, trailer, detected version) and
`catpart-fitness` measures clean-parse over the corpus: **Dev 99.66%
(1745/1751), held-out 100% (73/73)**, no-regret per ADR-0001. See
[docs/ROADMAP.md](docs/ROADMAP.md) (Phase 3 status block),
[docs/format/README.md](docs/format/README.md) (documented structures)
and `fitness/history.jsonl`. Published live: the badge above reads the
`gh-pages` endpoint, refreshed locally by `scripts/publish_fitness.py`
(ADR-0003, never in CI) — rebuilds and force-pushes the `gh-pages` JSON.

## Progress

Implementation tracker — 23 tickets under specs
[#8](https://github.com/MadManJohnSmith/catpart-parser/issues/8) (tooling),
[#9](https://github.com/MadManJohnSmith/catpart-parser/issues/9) (format
inference) and [#10](https://github.com/MadManJohnSmith/catpart-parser/issues/10)
(L1 parser). Updated as tickets close; authoritative state lives in the
issue tracker.

**Specs A/B/C complete (17/17, 2026-11-09). Phase 4 opened: spec D (#28, L2 geometry) with 6 tickets — 0/6.**

| Spec | Ticket | State |
|---|---|---|
| A | [#11](https://github.com/MadManJohnSmith/catpart-parser/issues/11) A1 package skeleton & CLI | done |
| A | [#13](https://github.com/MadManJohnSmith/catpart-parser/issues/13) A3 version detection + manifest backfill | done |
| A | [#14](https://github.com/MadManJohnSmith/catpart-parser/issues/14) A4 fitness runner | done |
| A | [#12](https://github.com/MadManJohnSmith/catpart-parser/issues/12) A2 fixture generator | done |
| A | [#15](https://github.com/MadManJohnSmith/catpart-parser/issues/15) A5 GitHub Actions CI (after A2) | done |
| A | [#16](https://github.com/MadManJohnSmith/catpart-parser/issues/16) A6 gh-pages publication | done |
| B | [#17](https://github.com/MadManJohnSmith/catpart-parser/issues/17) B1 container table & trailer | done |
| B | [#19](https://github.com/MadManJohnSmith/catpart-parser/issues/19) B3 container payload blocks | done |
| B | [#18](https://github.com/MadManJohnSmith/catpart-parser/issues/18) B2 header/tail semantics | done |
| B | [#20](https://github.com/MadManJohnSmith/catpart-parser/issues/20) B4 CGMGeom/CATCGRCont payloads | done |
| B | [#21](https://github.com/MadManJohnSmith/catpart-parser/issues/21) B5 R19 vs R21 differential | done |
| B | [#22](https://github.com/MadManJohnSmith/catpart-parser/issues/22) B6 format document v1 (Phase 2 close) | done |
| C | [#23](https://github.com/MadManJohnSmith/catpart-parser/issues/23) C1 schema v1 + L1 baseline | done |
| C | [#24](https://github.com/MadManJohnSmith/catpart-parser/issues/24) C2 feature tree (documented negative) | done |
| C | [#25](https://github.com/MadManJohnSmith/catpart-parser/issues/25) C3 units/names (document_name; units negative) | done |
| C | [#26](https://github.com/MadManJohnSmith/catpart-parser/issues/26) C4 Phase 3 acceptance | done |
| C | [#27](https://github.com/MadManJohnSmith/catpart-parser/issues/27) C5 fitness publication (after A6) | done |
| D | [#29](https://github.com/MadManJohnSmith/catpart-parser/issues/29) G1 nested store navigation decoded | planned |
| D | [#30](https://github.com/MadManJohnSmith/catpart-parser/issues/30) G2 vertex pool decoded | planned |
| D | [#31](https://github.com/MadManJohnSmith/catpart-parser/issues/31) G3 primitive semantics (triangles) | planned |
| D | [#32](https://github.com/MadManJohnSmith/catpart-parser/issues/32) G4 catpart-export CLI + geometry fixtures | planned |
| D | [#33](https://github.com/MadManJohnSmith/catpart-parser/issues/33) G5 L2 fitness + publication | planned |
| D | [#34](https://github.com/MadManJohnSmith/catpart-parser/issues/34) G6 grind L2 to the bar (Phase 4 close) | planned |

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
