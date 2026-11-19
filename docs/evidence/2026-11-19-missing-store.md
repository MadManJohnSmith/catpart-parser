# Evidence: the 119 missing-geometry-store parts — no store under any locator, and no stream payload to point one at (2026-11-19)

**Date**: 2026-11-19
**Status**: COMPLETE — documented negative for the locator lever; the
carrier class that does exist (a bag-rep payload) is named and counted,
with its reopen criterion.
**Scope**: the 125 report rows classified `missing-geometry-store` in
[`fitness/reports/20261119T035609Z-7dc3ea.json`](../../fitness/reports/20261119T035609Z-7dc3ea.json)
— **119 `kind=part`** (the ticket's population) plus 6 `kind=unknown`
rows, which are kept in the census so the report total ties out.
**Method**: read-only byte census over the corpus, `scripts/triage/missing_store_census_probe.py`
(stdlib + the committed `catpart.geometry.store`/`pool` measurement
infrastructure; deterministic, manifest order, ~7 s). Data:
[`data/missing-store-census.csv`](data/missing-store-census.csv) (one
row per report row), [`data/missing-store-sample-15.csv`](data/missing-store-sample-15.csv)
(the stratified 15), [`data/missing-store-claims.csv`](data/missing-store-claims.csv)
(every figure below is a row there or arithmetic on rows).
**No `src/` change** in this task.

Labels: **fact** = byte-measured here and reproducible from the CSVs;
**inference** = interpretation of measured bytes, reasoning shown;
**unknown** = open, carried forward.

---

## 1. Executive summary

| Question | Measured answer |
| :--- | :--- |
| Does a part store exist under *another* container / locator? | **No.** All 119 carry exactly one `V5_CFV2` magic, at offset 0 (the file's own header). Zero carry a second one anywhere in the file. All four shipped probe families (`CATStdCont`, `CATXDocLinkCont`, `CATSeeBodyCont`, other-container) are therefore vacuous, not merely exhausted. |
| Could a *new locator law* open any of them? | **No.** 0/119 files carry a `10 24 04 ff ff 00 00 00` + `01 06` pool group (the decodable unit G2 reads) or a `05 08 01` vertex-record stream. Two candidate laws were written and measured: **L-SN** (self-named-tail document catalogs) locates 33 spans in 33 files; **L-OW** (the offset-0 outer wrapper) validates on **121/121** files. Both find **0 pool groups** in every candidate body. Span-level gain: 33 / 121; L2 gain: **0**. |
| Are some of them products/catalogs with no part geometry (data)? | **0 products** (every one of the 119 declares `CATPrtCont`); **0 catalog documents**. 16 parts (13.4%) carry a feature/spec tree but no measurable point-array or bag-rep payload — these are the "data" end (shape not saved in either encoding this census detects). |
| Are some malformed? | **4 rows are not CATIA binaries at all** (two text stubs, one YAML-ish placeholder, one saved GitHub HTML page); **0 malformed-store-header** in the 119. Two further rows are CATIA binaries with **no container-name table** (`kind=unknown`), yet both carry a point-array payload. |
| What do they carry instead? | A **bag-rep representation payload**: 61 parts with 12-byte-stride point arrays (longest run 21,846 points), 25 with `04 04 fd ff` node records but no point run, and **17 with the self-describing class tokens** `CAT3DBagRep` / `CAT3DBagRepT` / `CATSurfacicRep` (198 tokens). 103/119 are in a payload-bearing class (point-array, topology-only or bag-rep-named). |
| The lever | **Not a locator.** It is a payload decoder for the bag-rep records (name it **R-BAG** in a follow-up spec); ceiling 17 named / 103 payload-bearing parts, today 0 exports. The locator lever is closed with a hard reopen criterion (§9). |

---

## 2. The population

From the report: 125 rows fail with `missing-geometry-store`
(`l2.status=fail`), of which 119 are `kind=part`. The count has been
stable at 125 across the last six accepted runs
(2026-11-13 → 2026-11-19), while L2 rose 1,033 → 1,084: the missing
mass is not moving with the content levers.

| axis | value | count |
| :--- | :--- | ---: |
| kind | part / unknown | 119 / 6 |
| split | dev / held-out | 119 / 0 |
| repo | `SSadayuki/B31CAADoc` / `zhoujason457-stack/CAA_PrjSrc` | 114 / 5 |
| detected version | `unknown` (no `CNEXTINFOS` marker) | 119 |
| reported version | empty | 119 |

Size 37,289–1,059,040 B (median 93,589). This is the **CAA education
corpus**. 32 of the 119 belong to the 146-file extended-header
(dual-catalog) family characterized in
[2026-11-07-container-table-and-trailer.md](2026-11-07-container-table-and-trailer.md)
("a distinct writer generation … a dual-region layout and a header that
continues past the ff×8 marker"); the other 87 carry the ff×8 marker but
the same document-generation catalog layout, and still no stream store.

*Inference (from the bytes, not the repo names):* `unknown` is not the
cause. Corpus-wide 38 unknown-version parts **pass L2** (37 of them from
these two repos), and every one of them carries a nested `V5_CFV2` store (e.g.
`CAATestBasicGeometry.CATPart` V5 at `[0, 108356]`). The 119 are the
subset of the same writer family whose writer did not emit a stream
store at all.

### 2.1 Two header generations inside the 119 (fact)

| header family | bytes at 16..24 | parts | meaning |
| :--- | :--- | ---: | :--- |
| `dual-catalog` | two big-endian dwords at 16..24 | 32 | `dword16` = a leading `CATIA_V5 CB0001` region (the extended-header note's 143/146); `dword20`'s target is that catalog's tail on `CAAPriPocket` (4,152 = tail) but not on `BundleSegment3` (6,144 vs tail 4,176) — **unknown**, carried as measured |
| `ff8` | `ff × 8` | 87 | modern header shape, but no nested store was written |

Both families carry the same marker inventory (below); the split
matters only for *where* the second (document) catalog sits.

### 2.2 Container families (fact)

Declared in the container-name table of the 119 parts:

| declared container | parts | what its region actually holds here |
| :--- | ---: | :--- |
| `CGMGeom` | 119 | CGM object dictionary (BR5 identity + id runs); no stream payload |
| `CATSeeBodyCont` | 116 | the bag-rep payload (§5) |
| `CATCGRCont` | 103 | 306 B–12,593 B cache blocks (median 908 B); point runs start here in 2 files |
| `CATBRepModeContainer` | 48 | BRep-mode region; carries point arrays in 14 files |
| `CATStdCont` | 28 | `CATOctetArray` document storage: 10 hold the `catalogManager`/camera spec, 1 holds an in-block document catalog, the rest raw octet payload; **none carries a store** |
| `CATXDocLinkCont` | **0** | the xdoclink probe family never even applies |

The ticket's three buckets, answered directly: **CB0001 catalog
documents 0**, **products without a part 0**, **parts 119**. Every one
of the 119 declares `CATPrtCont`; the `CB0001` regions they do carry are
the file's container catalog (all 119) and, in the dual family, an
embedded document catalog (32) — not part geometry. The four
`CAACatalogs.edu` samples (`CAANuts6Sides`, `CAAScrew`,
`CAAGroovedScrew`, `CAANuts4Sides`) are catalog *chapters*, but each is
a part with a bag-rep payload (point runs 9 / 76 / 24 / 9).

Three parts declare no `CATSeeBodyCont` at all
(`CAAPriPocket`, `CAA-Rod-Part`, `fou`); for those, the declared
geometry containers have **no storage block that parses** in this
generation (their payload sits in the unblocked region before the
trailer) — a block-framing (L1-adjacent) fact, not a store fact.

---

## 3. The store-marker census (whole file, all 125 rows)

| marker | measured |
| :--- | :--- |
| `V5_CFV2\0` | **121** occurrences over 121 CATIA files: exactly **1 per file at offset 0**; **0 files carry a second one** |
| `CATIA_V5 CB0001\0` | **154** occurrences: 119 parts carry 151 (87 × 1 outer container catalog at `dword8`, 32 × 2 outer + leading document catalog at `dword16`); the 2 container-less binaries carry 3 |
| `CB__END\0` | 154 (one per catalog; every in-block catalog tail validates under N6 on its own length — §4.1) |
| blocks (`CATStorageProperty`) | 2–17 per file; `store.locate_store` over **every** block returns **0 spans** (all four families, including the stage-12 other-container family) |
| `10 24 04 ff ff 00 00 00` | 33 occurrences in 13 files — **never** followed by the `01 06` sub-kind (they occur inside bag-rep/plane records); **0 pool groups corpus-wide** |
| `05 08 01` vertex record | 4 single-byte-pattern hits in 4 files, no run; no vertex stream |
| `04 04 fd ff` node records | present in **101 parts** (1–49 per file, every hit inside a payload region; 25 parts have nodes but no point run) |
| `CAT3DBagRep` / `CATSurfacicRep` | 198 tokens in 17 parts |

So the locator's search space is *empty by construction*: there is no
nested header to validate and no decodable payload primitive to point a
span at. The 0 pool groups is the load-bearing fact — it makes every
candidate span below worthless for L2 regardless of how it is bounded.

---

## 4. Two candidate locator laws, measured

### 4.1 L-SN — self-named-tail document-catalog span law

*Statement tested:* when a `CB0001` sits inside a block region and its
tail `[cb, next CB__END]` satisfies the N6 laws **on its own length**
(`CB__END` last, `C == D`, `G == len(tail)`), treat the block as a store:
body = `block + 64 .. cb` (the header-less prefix) **or** the suffix
`END + 8 .. region end` (the catalog-first shape this generation uses).

*Why the shipped law misses it:* `locate_store`'s header-less branch
derives the tail length from the region end (`region_end − 126 − cb`,
`region_end − cb`); in this generation the catalog is followed by more
payload, so both derived lengths fail. The shipped law returns
`None` — correctly classified as "no store in region", not malformed.

*Measured:* **33 spans in 33 files** (all 32 dual-catalog parts + the
container-less `CAAMaiUdfForMfgHoleInstance`); **33/33 are document
catalogs** (33/33 carry a document-property entry — `CATPreview`,
`CATPropertySets` or `ProjectHeader` — as UTF-16 names); **0/33 span bodies contain a pool
group**, before or after the catalog.

*Inference:* these are the "embedded document's own outer-style
catalog" family G1 recorded as N10 — a document storage, not a geometry
store. L-SN is a true structural law (it validates 33/33) but it buys
nothing on L2.

### 4.2 L-OW — offset-0 outer-wrapper span law

*Statement tested:* the file's own `V5_CFV2` at offset 0 is a store
header by the documented layout (`dword8` = catalog offset, `dword12` =
catalog length). Accept it as a store span, tail either shipped
(`[d8, d8+d12)` ends `CB__END`, N6 holds) or trimmed (the `CB__END`
inside the window names the true tail, the rest zero padding), body =
`64 .. d8`.

*Measured:* tail **valid on 121/121** CATIA files — 5 shipped
(`rod_3d`, `fix_3d`, `driver_3d`, `piston_3d`, `CAAPriPocket`) and 116
trimmed (the dual/ff8 extended-header tail: `G` names the trimmed
length, the remainder is zeros; e.g. `BundleSegment3` `d12 = 12,288`,
`G = 11,196`, 1,092 trailing zeros). **0/121 outer bodies contain a pool
group.**

*Inference:* the outer wrapper is the container directory. Its body is
the container table (and, in the catalog-first layout, the feature
payload that follows it). It is a store in the container-format sense
and carries no facet stream.

### 4.3 The yield table (fact)

| law | files with a validated span | spans | bodies with a pool group | files that would export |
| :--- | ---: | ---: | ---: | ---: |
| shipped (all four probe families) | 0 | 0 | — | 0 |
| L-SN | 33 (32 parts) | 33 | 0 | **0** |
| L-OW | 121 | 121 | 0 | **0** |

Both laws locate *something* and decode *nothing*. The blocker is the
payload encoding, not the locator — hence the negative, not a new law.

---

## 5. What the files carry instead: the bag-rep payload

The 119 parts split by carrier evidence (fact; detector definitions in
§9):

| class | parts | what is measured |
| :--- | ---: | :--- |
| `point-array` | 61 | a run of ≥ 3 consecutive plausible float32 triples at 12-byte stride inside a payload region (longest run 21,846 points, `AnalysisMechfeat`, `CATSeeBodyCont` 274,993 B) |
| `topology-only` | 25 | `04 04 fd ff` node records, no point run ≥ 3 |
| `bag-rep-named` | 17 | the explicit class tokens `CAT3DBagRep`/`CAT3DBagRepT`/`CATSurfacicRep` (198 tokens); 13 carry a point run (12 of them ≥ 3 points) |
| `feature-only` | 16 | feature/spec tokens (`Sketch`, `Constraints`, `ContourList`, `PlanarSupport`, `Geometries`) and **no** point array / node record / bag token |

Where the longest run starts: `CATSeeBodyCont` 61,
`CATBRepModeContainer` 14, `CGMGeom` 14, `CATStdCont` 11, `CATCGRCont` 2
(counting all runs, including the 1–2-point runs of the topology-only
class). Node markers are likewise inside payload regions on every spot
checked (101 parts, 1–49 hits each).

This is a *different representation generation*, not a broken stream
store: coordinates are stored as loose 12-byte float triples alongside
`CAT3DBagRep`/`CATSurfacicRep` records and `04 04 fd ff` nodes, with no
`01 06` pool, no `05 08 01` vertex records and no facet records. A
decoder for it would be new payload work (R-BAG), not a locator change.

The `feature-only` 16 are the "data" end: their `CATSeeBodyCont` is
0–919 B except `CAAPriPad` (31,231 B, 62% zero bytes, 1 triple), and
the design intent lives in `CATPrtCont` (`Sketch`/`Constraints`/
`ContourList`). *Inference:* the shape is recomputed on open or was not
saved; there is nothing to decode from the file. `CAAPriPocket` is the
clearest case: 51,670 B of `MechMod.feat`/`PartDesign.feat` feature
records, zero geometry containers with a parseable block.

---

## 6. The 15-file sample (stratified 1-per-cell, then round-robin)

`data/missing-store-sample-15.csv`; rule in `stratify()` — sort by
(header family, geometry class, path), take one row per cell per pass.

| # | file | size | hdr | blocks | V5 | CB0001 (owner) | seeB | point run (region) | class |
| ---: | :--- | ---: | :--- | ---: | :--- | :--- | ---: | :--- | :--- |
| 1 | `CAAPriPocket.CATPart` | 124,228 | dual | 8 | `0` | `outer@64; CATIA@59882` | 0 | 0 | feature-only |
| 2 | `CAAOmbPart1ForSamplePDM.CATPart` | 55,308 | dual | 10 | `0` | `CATIA@7265; outer@44044` | 4,550 | 7 / seebody | point-array |
| 3 | `CAAOmbPart2ForSamplePDM.CATPart` | 61,702 | dual | 10 | `0` | `CATIA@7651; outer@50438` | 4,550 | 2 / seebody | topology-only |
| 4 | `Plate.CATPart` | 98,626 | ff8 | 9 | `0` | `outer@88386` | 442 | 27 / cgmgeom | bag-rep-named |
| 5 | `p3.CATPart` | 48,678 | ff8 | 7 | `0` | `outer@39462` | 456 | 0 | feature-only |
| 6 | `Part1.CATPart` | 47,487 | ff8 | 8 | `0` | `outer@37247` | 4,550 | 7 / seebody | point-array |
| 7 | `L8x6x1.CATPart` | 71,722 | ff8 | 11 | `0` | `outer@59434` | 1,729 | 1 / stdcont | topology-only |
| 8 | `Bundle_Segment2.CATPart` | 83,901 | dual | 9 | `0` | `CATIA@6748; outer@72637` | 12,744 | 14 / seebody | point-array |
| 9 | `PN-27112000-1700.CATPart` | 93,954 | dual | 10 | `0` | `CATTTRSCont@8901; outer@81666` | 1,388 | 2 / cgr | topology-only |
| 10 | `Screw.CATPart` (`CAAScrew`) | 67,800 | ff8 | 9 | `0` | `outer@56536` | 8,634 | 76 / seebody | bag-rep-named |
| 11 | `p4.CATPart` | 48,906 | ff8 | 7 | `0` | `outer@39690` | 456 | 0 | feature-only |
| 12 | `CAAMmrTableWood.CATPart` | 913,161 | ff8 | 11 | `0` | `outer@899849` | 639 | 78 / stdcont | point-array |
| 13 | `TPSPartToleranced.CATPart` | 399,838 | ff8 | 11 | `0` | `outer@385502` | 913 | 1 / cgr | topology-only |
| 14 | `Bundle_Segment3.CATPart` | 82,138 | dual | 9 | `0` | `CATIA@6974; outer@70874` | 12,744 | 14 / seebody | point-array |
| 15 | `PartKIN_2.CATPart` | 46,631 | dual | 10 | `0` | `outer@35367` | 891 | 0 | topology-only |

Every row: one `V5_CFV2` at 0, no pool group, no vertex record; one or
two `CB0001` (the outer container catalog plus, in the dual family, the
leading document catalog); `store.locate_store` returns nothing on any
block.

Notable rows outside the sample: the three parts with **no
`CATSeeBodyCont`** (`CAAPriPocket`, `CAA-Rod-Part`, `fou`), the four
**non-CATIA** rows (§7), and the two **container-less** CATIA binaries
(§7).

---

## 7. The 6 non-part rows

| file | size | what it is | verdict |
| :--- | ---: | :--- | :--- |
| `caa_new/tests/dummy.CATPart` | 35 | `bootstrap extension-only test file\n` | malformed input (not CATIA) |
| `CAAxPDMInterfaces.edu/.../MyTextDocCheck.CATPart` | 40 | `It is a txt file, and not a V5 document\n` | malformed input |
| `C-AMEDEO-.../fpb_assy_v3.CATPart` | 528 | YAML-ish placeholder (`# CATIA V5 Part File …`) | malformed input |
| `CATIA/CATIA_vol/test_tolerence.CATPart` | 224,643 | saved GitHub HTML error page (`<!DOCTYPE html>`) | malformed input |
| `CAAMaiUdfForMfgHoleInstance.CATPart` | 100,935 | CATIA binary, **no container-name table** (`kind=unknown`), 10 blocks, V5 `[0]`, CB0001 `[13506, 89671]`, point run 93 | container-less; payload present |
| `CAAMaiUdfForMfgHoleTemplate.CATPart` | 106,142 | same, 9 blocks, V5 `[0]`, CB0001 `[94878]`, point run 13 | container-less; payload present |

None of the four malformed rows is a parser bug: the bytes are not a
CATIA document. The two container-less rows are real CATIA bytes; their
`kind=unknown` is an L1 container-table finding, separate from L2.

---

## 8. Byte anchors (the negative, pinned)

Reproduce any of these with
`.venv/bin/python -I scripts/triage/missing_store_census_probe.py --anchor <manifest path>`.

### 8.1 `CAAScrew.CATPart` — ff8, geometry exists as points, not as a store

```
size 71987  sha256 79f1b764…dd95d7   header_family ff8
dwords [magic, 1180054016, 60723, 11264, 0xffffffff, 0xffffffff, 0, 0]
V5 [0]   CB0001 [60723]   CB__END [70483]   blocks 9
CB0001 60723 owner outer
  tail_len 9768  trailer A..G [1, 53329, 5135, 5135, 0, 1, 9768]  n6_valid True
  catalog_names [ … Cont_59b51795_5dc_3d04b03e_182 … ]
point_run 20  triples 31  start 47036
  points [(-57.436, -0.849, 20.0), (-56.664, -10.16, 20.0),
          (-54.371, -19.217, 20.0), (-50.618, -27.773, 20.0)]
```

The only `V5_CFV2` is the file header; the only `CB0001` is the
container catalog at `dword8`. Real coordinates exist (20-point run in
`CATSeeBodyCont`), but there is no nested header and no `01 06` pool:
the geometry is the bag-rep payload, not a stream store.

### 8.2 `BundleSegment3.CATPart` — dual-catalog, the leading catalog is a document catalog

```
size 81771  sha256 009cc605…9cd4d1e8  header_family dual-catalog
dwords [magic, 1180054016, 69483, 12288, 7398, 6144, 0, 0]
blocks: 190 CATIA(2023) 2213 CATPart(3275) 5488 CATStdCont(903)
        6391 CameraStartupContainer(13146) 19537 CATProdCont(10520)
        30057 CATPrtCont(19356) 49413 CGMGeom(3625) 53038 CATSeeBodyCont(727)
        53765 CATBRepModeContainer(4564) 58329 CATCGRCont(3007)
        61336 CATElecBehaviourCont(8147)
V5 [0]  CB0001 [7398, 69483]  CB__END [11566, 80671]
CB0001 7398 owner CameraStartupContainer@6391
  tail_len 4176  trailer A..G [1, 6595, 69, 69, 0, 1, 4176]  n6_valid True
  catalog_names [CATPreview, CATPropertySets, Project, ProjectHeader,
                 TimeStamp, GesToler, Format, CATIA1, CATStorageProperty,
                 Cont_479ec662_ee_3d466e60_8ae7]
CB0001 69483 owner outer  (container catalog, trimmed tail 11196, 1092 trailing zeros)
point_run 20  triples 17  start 54501   (inside CATBRepModeContainer)
```

The header's `dword16 = 7398` is the leading catalog the extended-header
note recorded; its entries are document properties (`CATPreview`,
`Project`, `TimeStamp`), not stream names. Body before it is 943 B,
after it 7,963 B; neither contains a pool. This is L-SN in one file.

### 8.3 `CAAPriPocket.CATPart` — catalog-first layout, feature-only

```
size 124228  header_family dual-catalog
dwords [magic, 1180054016, 64, 4172, 59882, 4152, 0, 0]
V5 [0]  CB0001 [64, 59882]  CB__END [4228, 64026]
CB0001 64 owner outer         tail 4172  n6_valid True  (container catalog)
CB0001 59882 owner CATIA@59188 tail 4152  n6_valid True  (leading catalog:
                                    ProjectHeader, CATDocumentProperty, Data, Indexe)
parsed blocks: CameraStartup/CATPart/CATIA only (55906…)
4,236 ≤ region < 55,906: MechMod.feat / PartDesign.feat / Sketch /
                       Constraints / PlanarSupport (feature tree)
point_run 0
```

The whole outer wrapper is 32 B of body + a 4,172-B catalog at offset
64; the payload that follows is the feature tree. The declared
`CGMGeom`/`CATPrtCont`/`CATSeeBodyCont` have **no parseable block** in
this generation. Nothing to locate and nothing faceted to decode.

### 8.4 The four non-CATIA rows

```
dummy.CATPart          35 B   b'bootstrap extension-only test file\n'
MyTextDocCheck.CATPart 40 B   b'It is a txt file, and not a V5 document\n'
fpb_assy_v3.CATPart   528 B   b'# CATIA V5 Part File - fpb_assy_v3.CATPart\n…'
test_tolerence.CATPart 224643 B b'\n\n\n\n\n<!DOCTYPE html>\n<html lang="en"…'
```

---

## 9. Quantification and the lever

### 9.1 Split of the 125 report rows

| bucket | rows | composition |
| :--- | ---: | :--- |
| store-absent, bag-rep/point payload present | 105 | 103 parts + the 2 container-less CATIA binaries |
| store-absent, no facet payload (feature-only) | 16 | 16 parts |
| malformed input (non-CATIA bytes) | 4 | 4 `kind=unknown` rows |

Of the 119: **0** recoverable by a locator law; **103** carry a payload
a new *payload* decoder would target; **16** are data (feature/spec
tree, no saved shape representation in the encodings this census
detects).

### 9.2 Why "0" is a measurement, not a guess

A mesh export needs a pool group (`10 24 04 ff ff 00 00 00` + `01 06`)
or, for the composite path, a pool plus facet records. The census
measures **0 pool groups and 0 vertex-record streams** over the whole
125-row file set (33 wrapper-suite occurrences, none with the `01 06`
sub-kind; 4 single `05 08 01` byte-pattern hits). No locator law —
existing or new — can recover a mesh from a file that contains none of
the stream primitives. That is why L-SN and L-OW were measured and
reported as span-only wins.

### 9.3 The lever that is left: R-BAG (payload, not locator)

*Name:* **R-BAG** — decode the bag-rep records
(`CAT3DBagRep` / `CAT3DBagRepT` / `CATSurfacicRep`, `04 04 fd ff` nodes,
12-byte float32 point runs) into the export's vertex/facet model.

- Ceiling: **17 parts** with the self-describing tokens (198 tokens),
  and up to **103 parts** counting unnamed point arrays — but only if
  the unnamed payload is the same record grammar (unknown; the 17 are
  the honest start).
- Today's L2 gain: **0**; R-BAG would be a new decode law with its own
  evidence note, not a change to `store.locate_store`.
- Risk: the unnamed 86 payloads may be a different encoding; the four
  `bag-rep-named` files with `point_run = 0`
  (`CAAMaiToolEditionCustomization`, `CAAMaiUserToolDatabaseCustomization`,
  `p1`, `p2`) show the tokens can appear without a point array in the
  scanned regions, so the class is heterogeneous.

### 9.4 Reopen criterion for the locator lever (documented negative)

Reopen the missing-store question **only** if a future report or corpus
change shows any of:

1. a `missing-geometry-store` part with a **second** `V5_CFV2` occurrence
   (offset > 0) — that is a real locator miss; or
2. a `missing-geometry-store` part with a `10 24 04 ff ff 00 00 00` +
   `01 06` pool group anywhere; or
3. a `missing-geometry-store` part with a `05 08 01` vertex-record run.

Absent all three, the class is a payload-generation gap, and locator
work cannot move it. The census probe re-runs in ~7 s, so the check is
cheap to repeat on any later report.

---

## 10. Reproduction

```
export LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH TMPDIR=/home/alan/.cache/t3-tmp

# full census + stratified 15 (writes the two CSVs)
.venv/bin/python -I scripts/triage/missing_store_census_probe.py \
  --report fitness/reports/20261119T035609Z-7dc3ea.json \
  --sample-out docs/evidence/data/missing-store-sample-15.csv

# byte evidence for one sample
.venv/bin/python -I scripts/triage/missing_store_census_probe.py \
  --anchor 'sample/CAAComponentsCatalogs.edu/InputData/CAAScrew.CATPart'
```

Deterministic: manifest order, no randomness, three consecutive runs
produce byte-identical CSVs.

## 11. Files

- `scripts/triage/missing_store_census_probe.py` — the probe (`--anchor`
  mode included).
- `docs/evidence/data/missing-store-census.csv` — 125 rows, 46 columns.
- `docs/evidence/data/missing-store-sample-15.csv` — the 15.
- `docs/evidence/data/missing-store-claims.csv` — the claims.

---

## Appendix A — the 119 parts (path, header generation, carrier class)

All 119 are `split=dev`, `detected_version=unknown`; sizes are in the
census CSV. `hdr` is the header generation (§2.1), `class` the measured
carrier (§5). Sorted by class, then header, then path.

| # | path (manifest) | hdr | class |
| ---: | :--- | :--- | :--- |
| 1 | `online/CAAScdAsmUseCases/samples/Plate.CATPart` | ff8 | bag-rep-named |
| 2 | `online/CAAScdAsmUseCases/samples/Screw.CATPart` | ff8 | bag-rep-named |
| 3 | `online/CAAScdDriUseCases/samples/Cube.CATPart` | ff8 | bag-rep-named |
| 4 | `online/CAAScdGsiUseCases/samples/CAAGsiCreateJoinSurface.CATPart` | ff8 | bag-rep-named |
| 5 | `online/CAAScdKhwUseCases/samples/CAAKhwRuleBaseCreate.CATPart` | ff8 | bag-rep-named |
| 6 | `online/CAAScdKhwUseCases/samples/CAAKhwRuleBaseRead.CATPart` | ff8 | bag-rep-named |
| 7 | `online/CAAScdKniUseCases/samples/p1.CATPart` | ff8 | bag-rep-named |
| 8 | `online/CAAScdKniUseCases/samples/p2.CATPart` | ff8 | bag-rep-named |
| 9 | `online/CAAScdPriUseCases/samples/Pad.CATPart` | ff8 | bag-rep-named |
| 10 | `online/CAAScdPstUseCases/samples/CAAPstFunnel.CATPart` | ff8 | bag-rep-named |
| 11 | `online/CAAScdPstUseCases/samples/CAAPstHull.CATPart` | ff8 | bag-rep-named |
| 12 | `online/CAAScdPstUseCases/samples/CAAPstPad1_1.CATPart` | ff8 | bag-rep-named |
| 13 | `online/CAAScdPstUseCases/samples/CAAPstPad1_2.CATPart` | ff8 | bag-rep-named |
| 14 | `online/CAAScdStrUseCases/samples/grille/grid.CATPart` | ff8 | bag-rep-named |
| 15 | `sample/CAACATMatInterfaces.edu/CNext/resources/graphic/CAASamplePart.CATPart` | ff8 | bag-rep-named |
| 16 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiToolEditionCustomization.CATPart` | ff8 | bag-rep-named |
| 17 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiUserToolDatabaseCustomization.CATPart` | ff8 | bag-rep-named |
| 18 | `online/CAAScdPriUseCases/samples/CAAPriPocket.CATPart` | dual | feature-only |
| 19 | `online/CAAScdKniUseCases/samples/p3.CATPart` | ff8 | feature-only |
| 20 | `online/CAAScdKniUseCases/samples/p4.CATPart` | ff8 | feature-only |
| 21 | `online/CAAScdKniUseCases/samples/p5.CATPart` | ff8 | feature-only |
| 22 | `online/CAAScdPriUseCases/samples/CAAPriPad.CATPart` | ff8 | feature-only |
| 23 | `online/CAAScdStrUseCases/samples/HEA120.CATPart` | ff8 | feature-only |
| 24 | `sample/CAAAnalysisInterfaces.edu/CNext/reffiles/CAA-Rod-Part.CATPart` | ff8 | feature-only |
| 25 | `sample/CAAAssemblyUI.edu/CNext/resources/graphic/fou.CATPart` | ff8 | feature-only |
| 26 | `sample/CAADMAPSInterfaces.edu/CNext/resources/graphic/screw.CATPart` | ff8 | feature-only |
| 27 | `sample/CAADMAPSInterfaces.edu/CNext/resources/graphic/sheet.CATPart` | ff8 | feature-only |
| 28 | `sample/CAADMAPSInterfaces.edu/CNext/resources/graphic/table.CATPart` | ff8 | feature-only |
| 29 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiToolPathCustomization.CATPart` | ff8 | feature-only |
| 30 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiUdfFor2DProfileContouringInstance.CATPart` | ff8 | feature-only |
| 31 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiUdfFor2DProfileContouringTemplate.CATPart` | ff8 | feature-only |
| 32 | `sample/CAAMechanicalModeler.edu/CAAMechanicalModelerEduRscCNext.m/src/CNext/resources/graphic/PadFillet.CATPart` | ff8 | feature-only |
| 33 | `sample/CAAProductStructure.edu/CNext/resources/graphic/CAAPstImport.CATPart` | ff8 | feature-only |
| 34 | `CAAxPDMInterfaces.edu/InputData/CAAOmbPart1ForSamplePDM.CATPart` | dual | point-array |
| 35 | `online/CAAEwrUseCases/samples/Bundle_Segment2.CATPart` | dual | point-array |
| 36 | `online/CAAEwrUseCases/samples/Bundle_Segment3.CATPart` | dual | point-array |
| 37 | `online/CAAEwrUseCases/samples/Bundle_Segment4.CATPart` | dual | point-array |
| 38 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/BundleSegment1.CATPart` | dual | point-array |
| 39 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/BundleSegment2.CATPart` | dual | point-array |
| 40 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/BundleSegment3.CATPart` | dual | point-array |
| 41 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/BundleSegment4.CATPart` | dual | point-array |
| 42 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/BundleSegment5.CATPart` | dual | point-array |
| 43 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/BundleSegment6.CATPart` | dual | point-array |
| 44 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-07122000-1609.CATPart` | dual | point-array |
| 45 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-0812000-1707.CATPart` | dual | point-array |
| 46 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-12012001-1146.CATPart` | dual | point-array |
| 47 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-15012001-1307.CATPart` | dual | point-array |
| 48 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-15122000-1615.CATPart` | dual | point-array |
| 49 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-15122000-1655.CATPart` | dual | point-array |
| 50 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-29112000-1650.CATPart` | dual | point-array |
| 51 | `sample/CAAGeometryVisualization.edu/InputData/CAAProperty.CATPart` | dual | point-array |
| 52 | `sample/CAAMechanicalCommands.edu/InputData/CAAUdfLoft.CATPart` | dual | point-array |
| 53 | `sample/CAAMechanicalCommands.edu/InputData/CAAUdfLoftWithType.CATPart` | dual | point-array |
| 54 | `CAAxPDMInterfaces.edu/InputData/DocCheck/Part1.CATPart` | ff8 | point-array |
| 55 | `online/CAAMmrTechArticles/images/CAAMmrTableWood.CATPart` | ff8 | point-array |
| 56 | `online/CAAScdAniUseCases/samples/AnalysisMechfeat.CATPart` | ff8 | point-array |
| 57 | `online/CAAScdAniUseCases/samples/Crankshaft.CATPart` | ff8 | point-array |
| 58 | `online/CAAScdAsmUseCases/samples/NewScrew.CATPart` | ff8 | point-array |
| 59 | `online/CAAScdDmuUseCases/samples/driver_3d.CATPart` | ff8 | point-array |
| 60 | `online/CAAScdDmuUseCases/samples/fix_3d.CATPart` | ff8 | point-array |
| 61 | `online/CAAScdDmuUseCases/samples/piston_3d.CATPart` | ff8 | point-array |
| 62 | `online/CAAScdDmuUseCases/samples/rod_3d.CATPart` | ff8 | point-array |
| 63 | `online/CAAScdDriUseCases/samples/CAADriDimension.CATPart` | ff8 | point-array |
| 64 | `online/CAAScdMaiUseCases/Part_ToolMotion.CATPart` | ff8 | point-array |
| 65 | `sample/CAAAssemblyUI.edu/CNext/resources/graphic/Jack_Frame.CATPart` | ff8 | point-array |
| 66 | `sample/CAAComponentsCatalogs.edu/InputData/CAAGroovedScrew.CATPart` | ff8 | point-array |
| 67 | `sample/CAAComponentsCatalogs.edu/InputData/CAANuts4Sides.CATPart` | ff8 | point-array |
| 68 | `sample/CAAComponentsCatalogs.edu/InputData/CAANuts6Sides.CATPart` | ff8 | point-array |
| 69 | `sample/CAAComponentsCatalogs.edu/InputData/CAAScrew.CATPart` | ff8 | point-array |
| 70 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_BundleSegment1_1.CATPart` | ff8 | point-array |
| 71 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_BundleSegment1_2.CATPart` | ff8 | point-array |
| 72 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_BundleSegment2_2.CATPart` | ff8 | point-array |
| 73 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_BundleSegment3_2.CATPart` | ff8 | point-array |
| 74 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_BundleSegment4_2.CATPart` | ff8 | point-array |
| 75 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_EConnector.CATPart` | ff8 | point-array |
| 76 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_Equipment.CATPart` | ff8 | point-array |
| 77 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_FConnector.CATPart` | ff8 | point-array |
| 78 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_MConnector.CATPart` | ff8 | point-array |
| 79 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_Structure.CATPart` | ff8 | point-array |
| 80 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_Support1.CATPart` | ff8 | point-array |
| 81 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_Support2.CATPart` | ff8 | point-array |
| 82 | `sample/CAAElecHarnessItf.edu/CNext/resources/graphic/Ehi_clamp1.CATPart` | ff8 | point-array |
| 83 | `sample/CAAKnowHow.edu/CNext/resources/graphic/HolesWithChecksRules.CATPart` | ff8 | point-array |
| 84 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiDumpToolPath123.CATPart` | ff8 | point-array |
| 85 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiDumpToolPath4.CATPart` | ff8 | point-array |
| 86 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiDumpToolPath56.CATPart` | ff8 | point-array |
| 87 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiDumpToolPath7.CATPart` | ff8 | point-array |
| 88 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiDumpToolPath8.CATPart` | ff8 | point-array |
| 89 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiUdfWithNCMacroDataInstance.CATPart` | ff8 | point-array |
| 90 | `sample/CAAManufacturingItf.edu/CNext/resources/graphic/CAAMaiUdfWithNCMacroDataTemplate.CATPart` | ff8 | point-array |
| 91 | `sample/CAAMechanicalCommands.edu/InputData/CAALoft.CATPart` | ff8 | point-array |
| 92 | `sample/CAAMechanicalCommands.edu/InputData/CAAUdfModelWithTypeInst.CATPart` | ff8 | point-array |
| 93 | `sample/CAAPrismaticMachiningItf.edu/CNEXT/resources/graphic/CAAPmiDoublePocketUdfInstance.CATPart` | ff8 | point-array |
| 94 | `sample/CAAPrismaticMachiningItf.edu/CNEXT/resources/graphic/CAAPmiDoublePocketUdfTemplate.CATPart` | ff8 | point-array |
| 95 | `CAAxPDMInterfaces.edu/InputData/CAAOmbPart2ForSamplePDM.CATPart` | dual | topology-only |
| 96 | `online/CAAEwrUseCases/samples/PN-27112000-1700.CATPart` | dual | topology-only |
| 97 | `online/CAAScdDmuUseCases/samples/PartKIN_2.CATPart` | dual | topology-only |
| 98 | `online/CAAScdDmuUseCases/samples/skeleton.CATPart` | dual | topology-only |
| 99 | `online/CAAScdMaiUseCases/Sample_Part.CATPart` | dual | topology-only |
| 100 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/Alimentation-PW10-50Watts.CATPart` | dual | topology-only |
| 101 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-06122000-0836.CATPart` | dual | topology-only |
| 102 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-19102000-1100.CATPart` | dual | topology-only |
| 103 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-27112000-1700.CATPart` | dual | topology-only |
| 104 | `sample/CAAElecDeviceItf.edu/CNext/resources/graphic/PN-29112000-1640.CATPart` | dual | topology-only |
| 105 | `sample/CAAMechanicalCommands.edu/InputData/CAAUdfModelWithInstances.CATPart` | dual | topology-only |
| 106 | `CAAStructureInterfaces.edu/CNext/resources/graphic/SectionPath/L8x6x1.CATPart` | ff8 | topology-only |
| 107 | `CAATPSInterfaces.edu/FunctionTests/InputData/TPSPartToleranced.CATPart` | ff8 | topology-only |
| 108 | `online/CAAScdAniUseCases/samples/bielle.CATPart` | ff8 | topology-only |
| 109 | `online/CAAScdAniUseCases/samples/cyl.CATPart` | ff8 | topology-only |
| 110 | `online/CAAScdDmuUseCases/samples/PartKIN_1.CATPart` | ff8 | topology-only |
| 111 | `online/CAAScdGsiUseCases/samples/CAAGsiStart.CATPart` | ff8 | topology-only |
| 112 | `online/CAAScdInfUseCases/samples/CAAInfReadDocument.CATPart` | ff8 | topology-only |
| 113 | `online/CAAScdMaiUseCases/PartLathe_ToolMotion.CATPart` | ff8 | topology-only |
| 114 | `sample/CAAAssemblyUI.edu/CNext/resources/graphic/Jack_Branch_3.CATPart` | ff8 | topology-only |
| 115 | `sample/CAAGeometryVisualization.edu/InputData/CAAVisuBatch.CATPart` | ff8 | topology-only |
| 116 | `sample/CAAKinematicsInterfaces.edu/CNext/resources/graphic/PartForCylindrical.CATPart` | ff8 | topology-only |
| 117 | `sample/CAAMechanicalCommands.edu/InputData/CAAUdfModel.CATPart` | ff8 | topology-only |
| 118 | `sample/CAAMechanicalModeler.edu/InputData/CAAAxisSystemCreation.CATPart` | ff8 | topology-only |
| 119 | `sample/CAAMechanicalModeler.edu/InputData/CAACombinedCurveForReplace.CATPart` | ff8 | topology-only |
