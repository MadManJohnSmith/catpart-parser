# Evidence: the P1 product census — 100% of the CATProduct population classified by root cause (2026-11-14)

Ticket #46 (P1, parent spec F #45, Phase 6 assemblies). The Phase 4-era
negative ("products carry no geometry store, 0/37 sampled; the container
table carries no instance hierarchy", ticket #24) was a SAMPLED result on
37 products. This census classifies the full product population —
**382 manifest `kind=product` rows** (manifests/corpus-manifest.csv,
2026-11-14) — with the shipped scanners plus targeted probes, and
publishes the ceiling arithmetic toward the Phase 6 assembly bar.

Method discipline: census only — no decode implementation, no parser
changes, no viewer changes. Every figure below traces to a committed CSV
under `docs/evidence/data/` (the `p1-census-*claims.csv` family); every
census-owned detector carries a committed synthetic negative
(`--selftest`), and every absence claim carries an enumerated mechanical
sweep (the 2026-11-13 retro rules).

## 1. Population and method

Probe: `scripts/triage/p1_product_census.py` (committed with this note).
Modes: `--census` (per-file classification + container inventory),
`--sweeps` (absence claims), `--refs` (reference resolution),
`--ceiling` (the arithmetic), `--all`, `--selftest`. Deterministic
(manifest `kind=product` rows sorted by `local_path`); explicit output
paths; corpus read-only.

    python3 -I scripts/triage/p1_product_census.py --selftest
    python3 -I scripts/triage/p1_product_census.py --all
    python3 -I scripts/triage/check_claims_csv_quoting.py --root .

Full run: ~14 s wall (382 files). Population facts (all rows present on
disk; FACT):

| Fact | Value | CSV |
|---|---|---|
| manifest kind=product rows | 382 (370 dev / 12 held-out), 382 distinct sha256 | product-files |
| byte-verified CATIA documents | 380 (0.995) | product-files (`class` != non-catia) |
| manifest-kind misfits | 2 (non-CATIA placeholder/text files saved as .CATProduct) | product-files |
| header law H1 (dword8+dword12==size) | 379/380 CATIA files; 1 exception (unknown bucket) | product-files (`header_h1`) |
| detected-version buckets | 33 raw values; R15..R26 + `unknown` (104) | product-files |

The 2 misfits: `4097889236a2af26` (11 B, content `placeholder`) and
`8046a05915207b5a` (464 B, a markdown-ish file listing naming
`fpb_skin_panel.CATPart` etc. — the source of the Phase-1-era raw
`.CATPart` string hits; neither is a CATIA document). The census
classifies them `non-catia` and does not fold them into any CATIA class.

## 2. The classification — 382/382 covered

Per-file class (`class` column, one class per file; the evidence flags
are separate columns, the label is their join):

| Class | Files | Definition |
|---|---|---|
| `table-pool-pos-refs` | 14 | name table + structure pool + `_Position` + child doc refs |
| `table-pool-pos` | 246 | name table + structure pool + `_Position` |
| `table-pool-refs` | 8 | name table + structure pool + child doc refs, no `_Position` |
| `table-pool` | 106 | name table + structure pool |
| `catia-notable` | 6 | CATIA blocks, NO container-name table (the CAA sample family: 5× `CAAPstPrdFileSel_Prd*.CATProduct` B31CAADoc + `Gardena.CATProduct`; all `unknown` bucket) |
| `non-catia` | 2 | the manifest misfits above |

Coverage: 382/382 classified; no file forced into a wrong bucket; the
open sub-classes that resist full classification are named in §6, not
hidden. Container-name table: **374/382 parse under the shipped model**
(`catpart.containers.parse_container_table`), and the kind law K1 holds
**374/374** (detect_kind == product; zero disagreements at full scale).
2436 table records total.

Container inventory (files carrying each container among the 374
with-table products; full per-file rows in container-inventory CSV):
`CATCompoundCont` 374, `CATProdCont` 374, `CameraStartupContainer` 297,
`CGMGeom` 144 (name-TABLE rows — contrast: 0 CGMGeom storage BLOCKS,
§4), `CATMechProdCont` 139, `CATMFBRP` 136, `CATCtorProxyCont` 104,
`CATElecBehaviourCont` 67, `contmeasure` 46, `CATDrwCont` 34, ... — 73
distinct container names corpus-wide.

## 3. Where the assembly records live (byte evidence)

### 3.1 The structure pool — instances and the `_Position` attribute (FACT + law, pairing UNDECODED)

Every byte-verified CATIA product (380/380, including the 6 no-table
files) carries a **length-prefixed string pool** whose encoding law is
distinct from the block-string law:

- **Law B (pool)**: `<u8 len> <ASCII chars>` with `len == char count + 1`,
  chained without terminators. Worked example `0018ec386764dcea`
  (Dictor/HaneulMyo `Product1.CATProduct`, V5R24, 40983 B) @0x23e9:
  `08 "Part001" 0e "_InstanceName" 0a "Part001.1" 0a "_Position" 07
  "PRDREP" 08 "Shape 1" 09 "Part0024" 0b "Part0024.1" 0a "CONNECTOR" ...`
  (offsets in the hex readout: `Part001` @0x23f2, `_InstanceName`
  @0x23fa, `Part001.1` @0x2408, `_Position` @0x2412).
- **Law A (block strings)**: `34 <u8 len> <ASCII chars>` with
  `len == char count`, `9f`-terminated. Worked example `00c9533dcd4e219e`
  (System_demo_doc.CATProduct) @0x109: `34 1a "System_demo_doc.CATProduct" 9f`.

The pool carries the product-structure vocabulary: class tokens
(`ASMPRODUCT` 221 files, `PRDREP` 183, `PRDBAGREP` 227), attribute
tokens (`_Component` 380, `_PartNumber` 380, `_RefProduct` 375,
`_InstanceName` 315, `_Position` 260), instance names shaped
`<name>.<N>` (`Part001.1`), relation long strings (u32le-length-prefixed —
length @0x2477, string @0x247b of the worked example,
e.g. `CtorToProd:Product!ProdToRep:Shape 1!RepToShape:Shape!Geometry:...`). Rates: product-files CSV
(`pool_tokens`, `instance_name_strings` — 290 files carry ≥1
`name.N`-shaped pool string; median 5.0, max 208).

The pool proves the records EXIST to decode (instances declared with
names and a position attribute); the pairing structure (which instance
owns which position) and the `_Position` VALUES' byte encoding are NOT
decoded here — that is exactly the P2 dispatch (§8).

### 3.2 Region attribution — the file's own tail catalog localizes the pool (FACT)

The tail region `[dword8, EOF)` is the file's own catalog of named
regions (docs/format/tail-catalog.md; law H1). Walking it with the
committed decoder (`decode_tail_region.scan_tail`) succeeds on 273/380
CATIA products (6515 region entries; the 107 non-walking files are
89 `unknown` + 18 across R15-R21 — the CAA/other-writer generations; an
open class, §6). Attribution of the instance markers to the file's own
region names (marker_regions column; occurrences per region name,
markers `_InstanceName`/`_Position`): `Project` (175/141),
`CATIA` (27/24), `ProjectHeader` (20/17), pre-block bulk (18/16),
`CATProduct` (13/14), then a tail of catalog namings. The region NAME
varies by writer generation; the LOCATION does not: the pool sits in
exactly one catalog region per file (plus the pre-block bulk on files
whose catalog does not walk). This is a localization map, not an
ownership law — the stream-to-region binding is the name table's f1
join, unparsed (P2).

### 3.3 Document references (law A strings) — self names, sub-products, and part numbers (FACT + candidate)

Validated law-A strings ending in a document extension: **261, all
`.CATProduct`, all `9f`-terminated, zero `.CATPart`** (a validated
`.CATPart` child reference does not occur in this corpus — the earlier
raw `.CATPart` string hits were the markdown misfit file's text). Per
file (reference-resolution CSV): 254 files carry at least one document
reference — 239 carry their own document name (232 own-only + 7 both;
15 child-only) — 232 carry ONLY their own name (the CATIA block's
self-reference), 7 carry both their own and a child reference; **22
files carry 22 child `.CATProduct` references** (sub-assembly links);
child resolution against the manifest: 3 by basename, 8 by relative-path
tail (the povdoigt/SP-02 chains, e.g. `CATIA/CATIA_vol/Sepa_beta_Finale/
SP02_BATA_SEPA_V2.CATProduct`).

Part numbers: the pool's `_PartNumber`-adjacent strings join corpus
part files by stem: **248/382 files (0.649)** contain ≥1 pool string
equal to a same-repo part-file stem (verified real: Apoloo13 products
declare `ac1`, `ac2`, `main`, `lengua_1..9`, `LOWER_teeth_blend_lqstl001`;
corpus carries `ac1.CATPart`, `lengua_2.CATPart`, ... in the same repo).
NEGATIVE CONTROL (ceiling CSV): the same sweep against other repos'
stems only hits 40/382 (0.105) — the same-repo rate clears the
stem-collision floor ~6x. Label: **candidate** — stem equality is not a
decoded reference; the detector does not discriminate a true
`_PartNumber` binding from a coincidental stem match (§5).

### 3.4 The link-table container `CATXDocLinkCont` — rare here (FACT)

2/382 files (`2b6c0970df9fa5c7` `servo 996r_MODIFICADO.CATProduct`,
`b95f535fde09f5d4` `Cuerpo.CATProduct`, both V5R21): `CATXDocLinkCont`
appears as a container-name-table ROW (name1=`CATXDocLinkCont`,
name2=`CATFeatCont`, anchor `02 00 81 20` — worked readout @0x1fcc of
the servo file, string @0x2109 in the Cuerpo file), as a storage-block
name, and as raw bytes (6 raw
occurrences across the 2 files). The remaining 380 products carry NO
`CATXDocLinkCont` anywhere — the named link-table container is NOT the
carrier of assembly references in this corpus; the references live in
the structure pool (§3.1) and the law-A document strings (§3.3).

## 4. Absence claims — the Phase-4 negatives re-measured at 382 scale (all sweeps in absence-sweeps CSV)

Each claim: the enumerated mechanical sweep (one row per term), the
population 382, hit counts and version buckets from the CSV.

| Claim | Sweep terms (all enumerated, mechanically swept over 100%) | Result |
|---|---|---|
| **G1: no geometry store in any product** | storage-block names `CGMGeom`/`CATStdCont`/`CATSeeBodyCont`/`CATBRepModeContainer`/`CATCGRCont`; body-scoped `V5_CFV2` (>0), `CATIA_V5 CB0001` (>0); the shipped `store.locate_store` probed on EVERY body block (stage-3a/12 container-independent extension, regions bounded at dword8); UTF-16 stream names `SurfacicReps`/`SceneGraph`/`MainDataStream`/`Describe`/`Header`/`MAIN` (word-precise); strip-record grammar (V5) | **CONFIRMED, 0 hits**: 0 files with a `CGMGeom`/`CATSeeBodyCont`/`CATBRepModeContainer`/`CATCGRCont` block; 0 `V5_CFV2` beyond offset 0; 0 located stores; 0 strip records; 0 word-precise UTF-16 stream names. `CATStdCont` BLOCKS exist in 18 files (R15 1, R16 1, R17 2, R19 4, R21 3, unknown 7) but locate NO store and carry no strip records — a named block with no geometry content, not a store. `CB0001` appears inside the body of 44 files — the open class of §6, validated under nothing. |
| **T1: no instance hierarchy in the container-name table** (the #24 negative) | shipped name-table model over all 374 product tables: `parent_name` → same-file `name1` resolution | **CONFIRMED at scale**: 230/2436 records (9.4%) resolve a parent_name — the base-class annotation rate, matching the corpus-wide 8.8% of #24; **0/374 files resolve fully**. The negative holds identically at product scale. |
| **D1: `CATXDocLinkCont` is not the link carrier** | name-table rows, block names, raw bytes | 2/382 files only (§3.4); 0 files outside R21. |
| **F1: the tail catalog exists (the exclusion the sweeps rely on)** | `decode_tail_region.scan_tail` per file | walks on 273/380; its `CB0001` + UTF-16 region names are why whole-file byte sweeps must be body-scoped (a whole-file `CB0001` sweep reports the format itself: 380/382 — recorded in the sweeps CSV notes, not counted as a hit). |

The X1 sweep (raw float arrays as transform values) is committed as a
NON-rate with its non-discrimination documented (§5): 380/382 files
carry ≥8 consecutive plausible f64le (and ≥12 f32le) — the string pools
themselves unpack as plausible doubles, so the sweep cannot
discriminate. Transform-value presence is claimed ONLY via the
`_Position` attribute (§3.1), never via this sweep.

## 5. Detector-honesty declarations (per the 2026-11-13 retro candidate-4 rule)

- **Law A string extractor** (`p1_product_census.py`, `law_a_strings`):
  does NOT discriminate a live link record from a copied display string
  (title-block annotation, preview metadata); both count. Edge pinned
  by selftest: length-overflow, non-printable payload, and the pool
  mis-read (law A validates zero pool strings — the +1 off-by-one is
  the discriminator between the laws).
- **Law B pool detector** (`law_b_valid`): validates the +1 length law
  on the preceding byte; does NOT verify chain consistency beyond the
  token (a coincidental `len+1` byte before a printable run validates).
  The join rate's exposure is quantified by the cross-repo control (§3.3).
- **`position_attr` detector** (`position_attr_present`, added by the
  P1 review F1 amendment): counts `_Position` only when LAW-B-VALIDATED
  at the occurrence offset; does NOT discriminate the attribute's
  semantic role (a coincidental law-B-valid `_Position` string would
  count). The raw-substring version miscounted 4 Elec_X/Y/Z_Position
  wrapper files as placed instances (264 → 260; identity 116 → 120).
  Edge pinned by selftest: the law-B-valid Elec_X_Position wrapper
  negative, the law-B-valid `_Position` positive, the raw-substring
  negative.
- **Stem-join**: does NOT discriminate a true `_PartNumber` reference
  from a coincidental stem collision (control: 40/382 cross-repo floor).
  Same-repo scoping + pool context mitigate; P2 must decode the actual
  reference record before any per-part claim.
- **Strip-record grammar**: signature count, not a decode; isolated
  matches can be binary coincidences (0 found here, so moot at 382).
- **`locate_store` on products**: the shipped law validates the file's
  OWN tail catalog as a store when a block region extends past dword8 —
  the census's first run measured exactly this false positive (306
  files) with an 8-byte dword8 read; the committed sweep uses the
  documented 4-byte BE dword8 (header.md HDR-dword8-lt-size) and bounds
  regions at the tail start. The false-positive mechanism is recorded
  here because it is a live trap for any future whole-file probe.
- **Region attribution**: localization by the file's own catalog where
  it walks, block-walk fallback otherwise; a catalog-gap offset falls
  back to the block region name. Not an ownership law (§3.2).

## 6. Corrections and open classes

Corrections of prior records (decisions are final; corrections recorded,
not massaged):

1. "0/37 sampled products carry a geometry store" → **confirmed at full
   scale (0/382)** under every established signature plus the shipped
   store locator; the claim's scope narrows honestly to: no geometry
   store, no strip records, no nested store, no stream-name tokens.
2. "the container table carries no instance hierarchy" (#24) → confirmed
   at product scale (0/374; §4 T1) — AND LOCATED the records that DO
   carry the instance structure: the structure pool (§3.1), which the
   Phase-4-era notes did not examine (the 2026-11-08 notes swept
   payload regions and stream tokens, not the pre-block/`Project`
   region string pool).
3. "3/37 sampled products carry CATStdCont" → 18/382 at full scale
   (block names; no store inside any of them).
4. `CGMGeom` in products: 144 files carry CGMGeom name-TABLE rows
   (187 rows) while 0 carry a CGMGeom BLOCK — the name table lists
   containers the file never materializes; name-row presence is not
   structure presence (the Phase-4 table conflated these only by
   sampling; both columns are now separate claims).
5. Population: the "37 products" of the Phase-4 sample was a sample;
   the population is 382 manifest rows / 380 byte-verified products.

Open classes (named, never folded):

- **CB0001-in-body (44 files**, R15/R16/unknown; per-file detail in
  cb0001-body CSV: offsets + containing block — CATIA 21, CATProduct 14,
  CameraStartupContainer 6, CATMechProdCont 1, CATStdCont 1,
  CATDrwCont 1): an embedded `CATIA_V5 CB0001\0` catalog-format
  structure inside a body block (worked example `1f93f165fc0e3ec5`
  PID_ANSI_Equipment_.CATProduct @0x1bb7: the magic followed by a
  `4e 03e8 0040 000c` header — the tail-catalog shape, embedded). None
  validates as a store under the shipped law. This is the nested-store
  CATALOG structure proper — the highest-value P2 lead (§8).
- **Non-walking tail catalogs (107 files**, 89 `unknown`): the committed
  walk (tail-catalog.md laws) breaks; other-writer generations.
- **`catia-notable` (6 files)**: CATIA blocks without a container-name
  table — the CAA sample family + Gardena; structure pool present
  (pool_flag holds on all 6), name table absent.
- **`_Position` value encoding: UNKNOWN.** The attribute is present in
  260 files across every bucket (R15 8/14 ... R19 97/105 ... unknown
  55/104 — product-files CSV); where the 12 numbers live and their
  encoding is undecoded. No per-instance transform value is claimed.

## 7. Ceiling arithmetic — what an assembly bar CAN demand (ceiling CSV)

Per-class counts toward assembly support, each joined to its evidence
claim (all 382-row population):

| An assembly bar can demand | Count | Rate | Bounded by |
|---|---|---|---|
| byte-verified products | 380 | 0.995 | census |
| container table + kind law verified | 374 | 0.979 | shipped model, full scale |
| instance records DECLARED (structure pool) | 380 | 0.995 | pool law B — decode is P2 |
| identity placement (pool without `_Position`) | 120 | 0.314 | `_Position` absence |
| placed instances (`_Position` attribute present) | 260 | 0.681 | value encoding UNKNOWN — ceiling, not a delivery promise |
| sub-assembly links by filename, resolving IN CORPUS | 8 | 0.021 | law A + manifest join |
| part references joining same-repo corpus parts (candidate) | 248 | 0.649 | stem join + control (40/382 floor) |
| geometry from the product file itself | 0 | 0.000 | G1 negative — geometry MUST come from referenced parts |
| instance hierarchy from the name table | 0 | 0.000 | T1 negative |
| `CATXDocLinkCont`-style link tables | 2 | 0.005 | D1 |

Reading (the P3/P4 shape per ROADMAP): the "user supplies the product
and its referenced part files together" bar is the right one — in-corpus
child resolution is rare (8 files by filename) while the part-number
join (candidate, 248 files) gives the user-supplied-files bar its
in-corpus rehearsal surface. A defensible bar: **assemble the 380
pool-carrying products' instance lists (names + part numbers), identity
placement on all of them, and placed instances pending the `_Position`
value decode (260-file ceiling)** — with documented negatives for
product-internal geometry (0) and name-table hierarchies (0).

## 8. P2 decode dispatch proposal (what the next ticket builds)

Priority by ceiling-per-unit-work (the resume-template ordering):

1. **The structure pool record layer** (380-file ceiling, the whole
   bar): decode the pool's non-string layer — how entries pair
   (`_PartNumber` ↔ value, `_InstanceName` ↔ `name.N`, `_Position` ↔
   value). Entry points: the pool's binary neighborhood (e.g.
   `00 86 00 00 00` u32le-length relation strings after the byte-length
   strings in the worked example), the `IsRoot`/`PRDREP`/`ASMPRODUCT`
   class tokens as record anchors. Deliverable: a committed decoder +
   the pairing law at ≥3-files-per-marked-line version scope, per the
   decode template.
2. **The embedded CB0001 catalogs (44 files)**: decode the embedded
   catalog's region table (name/start/len) — the tail-catalog record
   shape already documented (tail-catalog.md) applied one level down;
   worked example @0x1bb7. This unlocks the CATStdCont-region internals
   for the 18 CATStdCont-block files and likely the stream-to-region
   binding for the `unknown` generations.
3. **The name table f1 join** (the directory d6/d5 laws, TB-dir-*):
   bind container names to stream offsets — the prerequisite for
   claiming WHICH region is the product-structure stream by law rather
   than by localization.
4. **`_Position` values** (the 260-file placed-instance ceiling): only
   after 1 — the values presumably ride the pool's record layer.
   Explicitly NOT promised by P1; the census's only transform claim is
   attribute presence.

Not P2: any viewer work (P3), any bar derivation (P4, owner-facing,
pre-commitment gating applies), any decode of the 2 `CATXDocLinkCont`
files' link tables beyond the byte evidence recorded here (2 files, no
population).

## 9. Reproduction

    # selftest (no corpus IO)
    python3 -I scripts/triage/p1_product_census.py --selftest
    # the census (all five CSVs; ~14 s)
    python3 -I scripts/triage/p1_product_census.py --all
    # CSV hygiene (the gate covers this family via the *claims*.csv glob)
    python3 -I scripts/triage/check_claims_csv_quoting.py --root .
    # single-class re-checks, e.g. the CB0001 class
    # WARNING (P1 review F4): --sha16 REWRITES the committed CSVs at the
    # OUT_* paths with the subset — run it in a scratch checkout, or
    # restore the CSVs from git afterwards (git checkout -- <paths>).
    python3 -I scripts/triage/p1_product_census.py --census --sha16 1f93f165fc0e3ec5

Worked-example files (by sha16, resolvable through the manifest):
`0018ec386764dcea` (Dictor structure pool), `00c9533dcd4e219e`
(System_demo law-A self name), `b95f535fde09f5d4` (servo CATXDocLinkCont
row), `1f93f165fc0e3ec5` (PID_ANSI embedded catalog).

Data: `docs/evidence/data/p1-census-product-files-claims.csv` (382 rows),
`p1-census-container-inventory-claims.csv` (2318 rows),
`p1-census-pool-tokens-claims.csv` (14 rows: the §3.1 vocabulary rates),
`p1-census-absence-sweeps-claims.csv` (21 rows: 20 enumerated sweep
terms, absent terms included, + the T1 hierarchy row),
`p1-census-cb0001-body-claims.csv` (44 rows),
`p1-census-reference-resolution-claims.csv` (347 rows),
`p1-census-ceiling-claims.csv` (13 rows).
