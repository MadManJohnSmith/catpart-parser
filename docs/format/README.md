# CATIA V5 container format — format document v1

Version 1 — 2026-11-08. Assembled from the dated evidence notes
`docs/evidence/` (B1-B5, tickets #17-#21); ROADMAP Phase 2 acceptance
deliverable (ticket #22).

This directory is the format documentation the parser implements
(Spec B / Spec C: "parser modules implement exactly the structures
documented in `docs/format/`; a structure without a documented claim is
not implemented"). One page per structural area:

| Page | Structural area | Parser status |
|---|---|---|
| [header.md](header.md) | Outer header (bytes 0-32) + the CNEXTINFOS version marker | parsed (`catpart.header`, `catpart.version`) |
| [tail-catalog.md](tail-catalog.md) | The `CATIA_V5 CB0001\0` tail region: the named-region catalog | documented, not parsed |
| [container-table.md](container-table.md) | Container-name table records, kind law K1, container-tree resolution | parsed (`catpart.containers`) |
| [trailer.md](trailer.md) | Trailer (last 36 bytes) + writer registration block | parsed (`catpart.trailer`) |
| [payload-blocks.md](payload-blocks.md) | CATStorageProperty block model, CATIA identity block, `document_name`, units negative | `document_name` parsed (`catpart.identity`); the rest documented, not parsed |
| [geometry.md](geometry.md) | Geometry containers (CGMGeom / CATStdCont / CATCGRCont), nested stream store, embedded tessellation (the L3-gate answer) | documented, not parsed |
| [validation.md](validation.md) | Cross-validation across the marked lines (R15-R32) + the R19/R21 differential verdicts + corrections register | - |

Evidence method: read-only byte analysis over the 1818 magic-verified
corpus files (releases V5R15-V5R32 + the 338-file `unknown` bucket),
reproduced by the committed scripts named in each evidence note; all
rates are corpus-wide observations on those files unless a smaller
scope is stated. Binaries are never committed; only notes, CSVs and
this document are.

## How to read a claim

Every claim on pages 1-6 carries:

- **byte ranges** (the table's offset column or the claim text);
- a **version scope** (the `Scope` column: which `detected_version`
  buckets, sample or generation the rate was measured on);
- a **label** — **established** = rate >= 0.98 on the scanned set (or a
  corpus-wide law with zero exceptions on its stated scope),
  **candidate** = below that bar, **open** = no validated claim;
  measured negative results are established (negative);
- a **link to its evidence note** (and the per-claim data CSV where one
  exists), under `docs/evidence/`.

Claim IDs reuse the source registers where they exist: the differential
CSV's IDs (`HDR-*`, `VM-*`, `TB-*`, `TREE-*`, `TR-*`, `TL-*`, `PL-*`,
`ID-*`, `GE-*`, `UT-*`), the B1-B4 law and claim IDs (T1-T3, D1-D3, K1,
H1, W1-W4, S1, N1, R1-R4, C1-C7, D1-D5, U1-U2, P1, V1-V8, G1, Z1), so
every claim is traceable from this document through the differential
CSV to the scan that measured it.
[validation.md](validation.md) summarizes the cross-validation and the
corrections register.

`scripts/triage/check_format_claims.py` checks the mechanical part
(evidence links resolve; every claim row carries a label + scope);
`tests/test_format_claims.py` pins it.

## Implementability note (what L1 implements vs what stays documented)

A reader can implement the outer structure and the container-inventory
level — what Spec C's C1 (`catpart-inspect`, ticket #23) and C2 (the
container inventory, ticket #24) emit — from [header.md](header.md),
[container-table.md](container-table.md) and [trailer.md](trailer.md)
alone; `document_name` comes from [payload-blocks.md](payload-blocks.md)
5.2. Exactly what the L1 parser (`catpart-inspect`, schema v1)
implements per page:

| Page | L1 implements | Stays documented, not parsed |
|---|---|---|
| header.md | `catpart.header`: magic, dword8, dword12, ff8 flag, dword16/dword20 (as-is on the dual variant). `catpart.version`: the CNEXTINFOS marker (8 KB window, 64 KB fallback, `unknown` bucket) | bytes 24-32; the dual-region dwords' semantics |
| tail-catalog.md | nothing (only trailer G reaches the output, as `tail_region_length`) | the whole catalog: entry walk, region records, tiling, space flag, generations |
| container-table.md | `catpart.containers`: the anchor scan (2 MB window), full-record validation (T3 constants, f3 vocabulary, T1 padding + f10), the 7-field record; `detect_kind` (law K1) => `containers[]` + `kind` | the directory table (3.3); any tree model — the documented negative (3.5): no tree field, `parent_name` reported as the measured annotation |
| trailer.md | `catpart.trailer`: the last-36-bytes model (7 big-endian dwords) + the registration block when byte-exact; null when no `CB__END\0` | the registration tag's meaning and the `041803` code (open); field semantics are invariant-enforced, not parser-enforced |
| payload-blocks.md | `catpart.identity`: `document_name` via the fixed identity-block walk (D1/D2), null-safe | the block model, region rule, GUID join, framing families, cardinality laws |
| geometry.md | nothing | the nested store, strip records, entropy attribution |

A structure without a documented claim is not implemented — and
conversely, every parsed field above traces to a claim on these pages.

## Not yet documented (not parsed)

- The **directory table**'s d-field semantics beyond laws D1-D3
  (container-table.md 3.3 — the laws are documented, the table is
  deliberately unparsed).
- The **OSMX / CB0001 stream headers** (boundary semantics unproven;
  `UT-osmx-cb0001`) and the **u32le attribute-string sub-format** inside
  geometry streams (`UT-u32le-subformat`).
- The **unnamed stream bulk** record format (`b2 03` family, float64
  arrays, entropy 7.2-7.84) — the largest undecoded territory (geometry.md 6.1).
- **Strip-record primitive semantics** (`UT-strip-semantics`); the
  nested-store header variants (5/44 parts without the nested magic in
  the probe window); the `Cont_<id>` name-to-GUID transform.
- Tail-catalog open fields: the cntB high byte (`UT-cnt-high-byte`),
  the 8 file-dependent tail-header bytes (`UT-tail-var8`), the entry-0
  quantum M's driver (`UT-e0-M-driver`), the tag `0x55` files, the
  nested sub-catalogs and the 20-65 KB tail blobs.
- Header open fields: dword20 (`UT-dual-dwords`), bytes 28-32
  (`UT-header-28-32`).
- Trailer open fields: F = 1/2 semantics (`UT-F-nonzero`), the
  registration tag meaning (`UT-reg-tag-meaning`), the B-target
  discriminator (`UT-reg-others`).
- The **model unit system** is a documented negative, not open work
  (payload-blocks.md 5.3); the **displayed part/product display name
  beyond the save-time document name** likewise (0/108 files carry any
  framed display-name property token or the basename outside the
  identity block — B3 open question 1 is closed by the C3 phase A
  probe).

`docs/evidence/` is the register of open questions; the differential
CSV's 12 `UT-*` rows are the version-scoped form of the same list
(validation.md 7.4).
