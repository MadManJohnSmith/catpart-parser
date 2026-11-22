# W5: the `CATProdCont` placement layer — shared connector bodies, law C (2026-11-22, Python + Rust)

Marathon round v3, worker W5 (assemblies). Base `d8554e0`, branch
`marathon/w5-assemblies`. Oracle: the four snapshot `.stp` files as ground
truth (probe `scripts/triage/p30_step_oracle.py`), corpus census and law
evidence (`scripts/triage/p31_lawc_census.py`), data subset at
`/tmp/w5-oracle-subset.tar.gz` (sha256 `d42ae23e…dc212`, verified; binaries
never committed).

## What the `CATProdCont` stream carries (structure, fact)

Facts from byte inspection of `VM-vela-Mast.CATProduct` (39,562 B; probe
reproduction in the claims CSVs):

* The document serializes objects tagged `ea <oid:u32LE> 00 00 00`. Vela
  carries 77 such oids, a dense id space 1–78 (10 missing). The five
  matrix-bearing objects carry oids 14, 23, 26, 29, 67 at `+0xeea (3818)`,
  `+0x1217 (4615)`, `+0x1344 (4932)`, `+0x1471 (5233)`, `+0x2363 (9059)` —
  each 39 B before its `8d 81` marker (fact).
* Three `_Position`-adjacent record families exist:
  1. the known run-length layer: `e8 f4 07 37` (explicit) / `e9 f4 07 04 37`
     (identity frame) / `e8 e0 07 37` (root) + `8d 81` + 12 run-length
     floats (fact, pre-W5);
  2. an `e6`-double variant of the same layer — vela's root record at
     `+0x45d0 (17872)` is a full 3×4 matrix in twelve `e6` doubles with
     `T = (14256.831, 4884.789, 8760.799)` mm: the document's placement in
     the submarine frame (fact; submarine-scale, consistent with part
     geometry below);
  3. `e8 c0 XX 37`-headed scalar records without the `8d 81` marker
     (attribute values, e.g. 13.75 / 12791.9 / 4.4e-5 at `+0x4656 (18006)`
     — not placements) (fact).
* The name pool is interned text (`fe 7c 02`-framed, names length-prefixed,
  each name appears exactly once per document — vela: 45 names at
  `+0x3f14 (16148)` ff.). No name→oid table exists anywhere in the file
  (fact: exhaustive substring scan; every name occurs once).
* Root records exist ONLY in the five top-of-forest documents (vela,
  flooding, bow, MB81 + none in swbd); none of the 194 child documents
  carries one (fact: `p31 --census`, 199 files). So the pre-W5 hypothesis
  that child placements live in child root records is empty: children have
  no root records at all.
* The parts are modeled in place: `.CATPart` local geometry carries
  submarine-frame coordinates (`VM-alumin-Op` local bbox X [3525.4, 3631.0]
  mm, `Bitt` X [9998.3, 10046.2] mm — m1/`build_export` bboxes), while the
  products themselves group with identity placements (fact).

## The STEP oracle (fact)

`p30 --instances` extracts, per top-level product: 48 (vela) / 43 (swbd) /
53 (flooding) / 85 (bow) `NEXT_ASSEMBLY_USAGE_OCCURRENCE` instances, each
with its `ITEM_DEFINED_TRANSFORMATION`. All 229 transformations are
identity — CATIA exported the assemblies with positions baked into the
component geometry, per-file local frames (fact).

Unit clauses are unreliable per file: vela's clause says metre but its
numbers are mm (the sail spans 1206 units; the M2 `stp_reference_bbox`
matches the raw values, diag 1225.05); swbd's metre clause matches a sane
2.6 m panel. The per-instance check therefore uses raw = mm for vela and
raw = m for swbd, documented per row (inference, noted in the CSV).

## Law C: shared matrix bodies are connector frames (the W5 correction)

The pre-W5 S7 law placed 19 walk rows across the snapshot with ONE
byte-identical matrix body. The corpus census
(`docs/evidence/data/w5-matrix-census-claims.csv`): 111 non-root records,
25 distinct bodies, **6 shared bodies carried by ≥ 2 documents**:

| body sha16 | docs | class |
|---|---|---|
| `9178dabde3636d53` | 13 (vela + bow + flooding-side + swbd-side …) | shared |
| `ba2a3c4e20f91f95` | 5 (MB81-0001/0002/0003, base-motor-01/-Mtu) | shared |
| `d7bba242fe58d7be` | 3 (swbd cuerpo A3K/B3K/C3K) | shared |
| `ecde1383cc94a778` | 2 | shared |
| `09d5c78f312dfeac` | 2 | shared |
| `55036aec9129c58e` | 2 | shared |

The 13-document body is `T = (-1.17e-10, -2.241190, 2179.457060)` mm,
identity rotation — the vela connector frame. The STEP oracle refutes
binding it as an instance placement: the vela export spans Z
[-88.72, +31.69] mm; the matrix would put the bound children at
Z = +2179.457 mm, 18.1× the product's entire exported Z extent
(`docs/evidence/data/w5-oracle-placement-claims.csv`, 51 changed rows,
each `frame-outside`, per-instance). The W-C-era reading of
"0002: −4682.62 mm" (MB81) falls the same way: that body is the 5-document
shared family (`ba2a3c4e20f91f95`), not a child placement.

**Law C (landed, walker-only)**: an explicit `_Position` matrix body
byte-identical across two or more documents of the walked set is a shared
connector frame — it never binds an instance. A document whose records are
ALL refused (or Clause 3 identity frames) carries no instance placements
and decodes identity; a document mixing refused records with anything else
stays fail-closed. Single-document reads cannot classify (no set) and keep
the strict path. This corrects the S7-era assumption "all-identical ==
count-matched ⇒ placed"; the oracle-confirmed identity for the four
STEP-backed products is the anti-masking-legal confirmation.

## Before → after (walk level, `docs/evidence/data/w5-walk-delta-claims.csv`)

| root | rows | placed | identity | undecodable |
|---|---|---|---|---|
| VM-vela-Mast | 45 | 5 → **0** | 22 → **45** | 18 → **0** |
| MD-swbd-panel-0A1w | 43 | 5 → **5** (kept) | 29 → **33** | 9 → **5** |
| BW-Flooding-compartment-sup | 54 | 2 → **0** | 41 → **43** | 11 → 11 |
| BW-section-bow | 85 | 10 → **0** | 63 → **85** | 12 → **0** |
| MD-MTU-16V-652-MB81 | 201 | 2 → **0** | 145 → **163** | 54 → **38** |

Net across the five roots (428 rows): placed 24 → 5, undecodable 104 → 54,
identity 300 → 369. The 5 surviving placements are the swbd nut-bt family
(`MD-swbd-0A1W-nut-bt`, 5 identical records, body unique to one document,
`T = (0.140466, 145.906043, 0.0)` mm, inside the swbd export frame —
`position_error_mm = 0.000` per instance). The 19 false placements carried
a per-instance position error of 2179.457 mm (vela, bow) / −4682.621 mm
(MB81, no STEP — corpus evidence only) along Z; they now decode identity
with error 0.

## Parity and tests

* Python `resolve_owned_assembly` vs Rust `fidelity-cli tree` (new seam,
  `port/src/bin/fidelity-cli.rs`): canonical JSON sha256 byte-identical on
  all five roots (method: both sides → `json.dumps(sort_keys=True)`;
  canonical form). SHAs in the parity section of
  `docs/evidence/marathon/w5-progress.md`.
* Rust `port/src/product/{binding,ownership}.rs` mirror the law C branches
  byte-identically (detail strings), walker census included; 232 cargo
  tests green (4 law-C walker tests + 3 binding tests new). Python: 71
  targeted tests green (5 law-C synthetic + vela/swbd real-file tests
  updated); the fixture suites stay green (26 passed).
* Additive schema: the walk document carries `warnings`
  (`connector-frame-records-v5r26`), rows carry the law-C
  `classification_detail`; single-document reads unchanged
  (`position-binding-open-v5r26`, fail-closed).

## Negatives and reopening criteria

1. **No per-document structural discriminator** (negative, 2 attempts):
   the 24-byte object headers before the `8d 81` markers take 55 distinct
   values across the 74 shared-class records (34 across the 37 unique) —
   header anatomy does not separate connector objects from instance
   objects. The cross-document body census is the only corpus-clean
   discriminator; it is set-relative (like `own(D)`), so a caller walking a
   set where the body appears once still fires S7.
   *Reopen when*: a decode of the `ea`-oid object stream separates the
   connector object type from instance objects per document.
2. **Unique-hash unbindable documents stay undecodable** (fail-closed):
   `MD-MTU-16V-652-B4` (34 own children, 1 record — which child?),
   `MD-swbd-panel-0A1w` (4 records, 2 unique bodies), `MB81-0004` (3
   identical records, own > 3), the 3 mixed shared+unique documents.
   *Reopen when*: a per-product oracle for their subtrees exists (the four
   STEP files do not cover them), or the object stream decode above lands.
3. **The connector-frame semantics** (what the frames mean geometrically —
   ports/mating axes) is inferred from the `_Connectors` pool token and the
   submarine-scale positions; the STEP files do not export connectors.
   *Reopen when*: a connector-bearing STEP export becomes available.
