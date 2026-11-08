# CATIA V5 container format — documented structures

This directory is the format documentation the parser implements
(Spec B / Spec C: "parser modules implement exactly the structures
documented in `docs/format/`; a structure without a documented claim is
not implemented"). Every claim below cites the dated evidence note under
`docs/evidence/` and the byte ranges it was measured on; interpretations
are marked. This file covers exactly the structures L1 parses
(`catpart-inspect`, schema v1, ticket #23); later tickets extend it as
structures are decoded — sections beyond the L1 set are marked
**(documented, not parsed)** and impose no parser behavior until a
parser ticket adopts them.

Evidence method: read-only byte analysis over the 1818 magic-verified
corpus files, reproduced by the committed scripts named in each evidence
note. All rates are corpus-wide observations on those files unless a
smaller scope is stated.

Parser mapping:

| Structure | Parser module | Evidence note |
|---|---|---|
| Header (bytes 0-32) | `catpart.header` | Phase 1 + B1 |
| Container-name table records | `catpart.containers` | B1 + kind-law note |
| Trailer (last 36 bytes) | `catpart.trailer` | B1 |

## 1. Header — bytes 0-32

Evidence: `docs/evidence/2026-11-07-container-triage.md` ("Outer
container structure", 1818/1818 files) and
`docs/evidence/2026-11-07-container-table-and-trailer.md` (law H1 and
the dual-region variant).

| Bytes | Field | Claim |
|---|---|---|
| 0-8 | magic | `56 35 5F 43 46 56 32 00` = ASCII `V5_CFV2\0` on 1818/1818 magic-verified files; 6 corpus files (mislabeled, non-CATIA) lack it. Reported as-is by the parser; enforced by the `magic-v5-cfv2` invariant. |
| 8-12 | dword8 | Big-endian uint32, always < file size (1818/1818; `size - dword8` median 10280, min 3138). Law H1 (B1, 1556/1556 CB__END-ending files): start offset of the `CATIA_V5 CB0001\0` tail region. Reported as-is. |
| 12-16 | dword12 | Big-endian uint32, never `0xFFFFFFFF` (0/1818). Law H1: `dword8 + dword12 == file size` and dword12 == trailer G on CB__END-ending files — the tail region's length. |
| 16-24 | ff×8 / dword16, dword20 | Eight `0xFF` bytes on 1672/1818 (92.0%). The 146 exceptions are the dual-region variant (B1: a distinct writer generation, CAA documentation-tree repos): two more big-endian dwords — dword16 at 16-20 (the offset of an additional `CATIA_V5 CB0001\0` region in 143/146) and dword20 at 20-24 (semantics unproven). Both reported as-is, null on the ff×8 generation. |
| 24-32 | zeros | Zeros in all examined samples (not parsed). |

## 2. Container-name table records

Evidence: `docs/evidence/2026-11-07-container-table-and-trailer.md`
("Container-name table record format"): 19300 records on 1810 corpus
files parsed with zero rejected anchor positions. Records are located by
the anchor dword `02 00 81 20` (little-endian `0x20810002`) at record
offset S+32 and validated against the full model before being reported;
the scan covers the evidence-validated first 2 MB of the file, starting
after the header. Satellite blobs (tags `04 00 c0 20` / `04 00 fc 3f`,
e.g. the `V5USERID` row) and other gaps sit between records on 382
files. 8 corpus files have no table at all (small `unknown`-version CAA
documents).

Record layout (all multi-byte fields **little-endian**):

| Offset | Field | Claim |
|---|---|---|
| S+0 | f1 | stream-position value; join key with the (unparsed) directory table (law D1). Reported as `stream_id`. |
| S+4 | f2 | per-record weight: 11 (9455 recs), 12 (4930), 13 (3070), 21 (1198, the `AppliCont` row), then rarer values. Reported as `weight`. |
| S+8 | f3 | table id: exactly three values corpus-wide (law T3, 19300/19300) — `0x00030001` (17488), `0x00040001` (1441 rows, 1198 of them the `AppliCont` row; container-tree note), `0x00050001` (371). Reported as `table_id`. |
| S+12 | idx | 1-based index within the table id (skips observed). Reported as `index`. |
| S+16 | f5 | constant `0x006c0001` (law T3). Validated, not reported. |
| S+20 | f6 | constant 2 (law T3). Validated, not reported. |
| S+24 | f7 | small value (0/1/8/2/9/... observed); semantics unproven. Not reported. |
| S+28 | f8 | constant 0 (law T3). Validated, not reported. |
| S+32 | f9 | constant `0x20810002` — the anchor (law T3). Validated, not reported. |
| S+36 | f10 | names-area 8-byte slots + 1 (law T1: `f10 == ceil((len(name1)+len(name2)+2)/8) + 1`, 19300/19300). Validated, not reported. |
| S+40 | names | `name1 00 name2 00`, printable ASCII, zero-padded to a multiple of 8 bytes (padding verified zero, law T1). `name1` reported as `name` (the container's name), `name2` as `parent_name` (parent/base name; corpus vocabulary led by `CATContainer`, `CATFeatCont`, `CATProdCont`). |
| then 8 | tail | constant `03 00 f7 00 03 00 00 00` (law T3). Validated, not reported. |
| then 16 | GUID | per-record object id. Reported lowercase-hex as `guid`. |

Record size = `64 + 8*ceil((len(name1)+len(name2)+2)/8)` (law T2); the
next record starts immediately after the GUID on the 1428/1810 strictly
contiguous files.

**Kind law (K1).** Evidence:
`docs/evidence/2026-11-07-container-kind-law.md` (verified by
`scripts/triage/verify_kind_law.py`, 0 disagreements). Among the 1810
with-table files: `CATPrtCont` among the record names <=> part
(1436/1436); `CATProdCont`/`CATMechProdCont` without `CATPrtCont` <=>
product (374/374; 2 parts carry `CATMechProdCont` next to `CATPrtCont`,
so the part name decides). No table => kind `unknown` (8 files).
Reported as `kind`.

### Container tree (documented, not parsed)

Evidence: `docs/evidence/2026-11-08-container-tree.md` (verified by
`scripts/triage/verify_container_tree.py`; per-file rows in
`docs/evidence/data/container-tree-scan.csv`). Ticket #24's owner
decision names the L1 "feature tree" the container tree assembled from
these records (node = {name, parent_name, table_id, index, guid,
weight}). The candidate assembly law — records form a connected
hierarchy via `parent_name` (child's `name2` = parent's `name1`),
rooted at `AppliCont`/`CATContainer`-style roots — **was tested and
fails corpus-wide**: only 1699/19300 records (8.8%) have a `parent_name`
matching a same-file `name1`; 0/1810 files resolve fully; the
`parent_name` vocabulary is exactly 5 values corpus-wide, and its two
dominant members (`CATContainer` 63.8%, `CATFeatCont` 26.0%) appear 0
times as `name1` — `name2` is a base-class/secondary-name annotation,
not a within-file parent pointer. `AppliCont` is not a root under that
relation (its own `name2` is `CATContainer`; absent from 377 files).

Ticket #24 resolution (2026-11-08): **documented negative**. No tree
model is implemented and the parser emits no tree field — the evidence
rule ("a structure without a documented claim is not implemented", Spec
C) forbids inventing a hierarchy the name table does not carry.
`containers[]` (the section 2 fields) is the L1 container inventory and
already carries `parent_name` as measured. A real instance-hierarchy
claim (e.g. the directory table's d5 = 1 + cumsum(f2) ordering law, or
product-region properties) would be a new B-branch ticket documenting
it here first.

## 3. Trailer — last 36 bytes

Evidence: `docs/evidence/2026-11-07-container-table-and-trailer.md`
("Trailer"). The trailer exists when the file ends with
`CB__END\0` (`43 42 5F 5F 45 4E 44 00`) — 1556/1818 files; the other
262 (including 106 dual-region files ending in zeros) have none, and
`trailer` is null for them. All fields **big-endian**:

| Offset (from end) | Field | Claim |
|---|---|---|
| -36 | A | constant `0x00000001`, 1556/1556. Reported as `a`; enforced by `trailer-constants`. |
| -32 | B | absolute file offset of the writer registration block; byte-proven as a pointer (moves by exactly the size delta between near-identical saves). Reported as `registration_offset`. |
| -28 | C | first half of the C==D pair (1556/1556); value file-dependent (`0x000000e7` is the mode), semantics unproven. Reported as `c`. |
| -24 | D | second half of the pair, == C. Reported as `d`; equality enforced by `trailer-constants`. |
| -20 | E | 0 on 1555/1556 (the one exception is a dual-region file). Reported as-is (`e`), never enforced. |
| -16 | F | 0 (1378 files), 1 (177), 2 (1); semantics unproven. Reported as-is (`f`). |
| -12 | G | == header dword12 == `size - dword8` (law H1, 1556/1556) — the tail region's length. Reported as `tail_region_length`; equality enforced by `tail-region-chain`. |
| -8 | marker | ASCII `CB__END\0`. |

**Writer registration block at B** (41 bytes):
`[tag 0x4d|0x4e][u32le 17]"DASSAULT-SYSTEMES"[u32le 5]"CATIA"[u32le
6]"041803"` — validated byte-exact on 1553/1556 CB__END-ending files
(the 3 failures are dual-region files). Reported as `registration`
(`tag` as `M`/`N`, plus the three strings) only when the pattern
matches, else `registration` is null; the tag's meaning and the
`041803` code are open questions.

## 4. Container payload blocks — CATStorageProperty **(documented, not parsed)**

Evidence:
`docs/evidence/2026-11-07-container-payload-layout.md` (B3; rates on a
114-file sample spanning V5R15–V5R32, per-release values in
`docs/evidence/data/container-payloads-claims.csv`; the sample includes
the 10 step-(a) R19/R21 files across 7 repos). Labels: **established**
= rate >= 0.98 on the scanned set; **candidate** = below that bar. No
field in this section has an L1 output yet — the section exists so the
B/C branch parses only what is documented.

**Block model.** A storage block starts at every ASCII
`CATStorageProperty` prefixed by `34 12` (1082/1082 blocks, 0
exceptions):

| Bytes | Field | Claim |
|---|---|---|
| +0 | prefix | `34 12` on all 1082 sample blocks. |
| +2 | type name | ASCII `CATStorageProperty` + `80 01 00 00 00 00 22 <u8> 00 00 00` framing, then tag34-framed names. |
| then | name1 | doc-type name: `34 <len> <name>` followed by `0x9f` or a type-tag byte — law C3b (**established**, 4438/4475 = 0.992; the 37 residuals are binary coincidences in stream data, not a framing variant). Vocabulary: `CATProdCont` (parts), `CATProduct` (products), `CATPrtCont`, `CGMGeom`, `CATCGRCont`, `CATPart`, `CATIA`, ... |
| then | name2 | second tag34-framed name (`a0 02 00 00 00 00 34 <len> <name> 9f`); empty (`34 00`) when absent. |
| then | GUID | 16 bytes after the `3b 10` marker, at a **variable slot** (observed 0x57–0x7b, shifts with the name lengths) inside the first 0x90 bytes. Join key to the name-table records (section 2): C1b (**candidate**, 941/968 = 0.972 — the 27 residual blocks' containers are absent from those files' name tables, consistent with B1's subset observation). |

**Region rule** (**established**, C2, 1082/1082 byte-verified): a
block's payload region runs from the block start to the nearest of —
next storage block (650), next `OSMX` (244), next
`CATIA_V5 CB0001\0` (188), header dword8 tail start (0), EOF (0).
Whether every OSMX/CB0001 match is a real stream header is open
(evidence note, open question 2).

**The CATIA identity block.** Exactly one per file (114/114), named
`CATIA`, with a 16-zero-byte GUID slot — it never joins a record by
design. It carries the save-time document file name as name2 in 37/114
files (*inference*: file-identity block with a null object id; not
verified).

**Cardinality law** (**established**, C6, 114/114): exactly one
`CATProdCont` record per file, joined by exactly one block (doc-type
name `CATProdCont` on parts, `CATProduct` on products).

**CATFeatCont negative finding** (**established**, C7, 114/114,
cross-checked corpus-wide): 0 of 19,300 name-table records have
`name1 == CATFeatCont`; it appears only as *name2* of other containers'
records, and there are **zero literal `CATFeatCont` byte sequences
outside the name table**. *Inference*: a display/secondary name, not a
container that owns a payload region — there is no CATFeatCont layout
to decode at payload level.

**String framing families inside regions** (context, not laws; rates
from the note's decompositions):

| Family | Form | Where seen |
|---|---|---|
| tag34 name | `34 <len> <ascii> <0x9f \| type-tag>` | property sections (names above) |
| u16le ASCII | `<u16le n> <n ascii>` | property/registration sections (`0b 00 "OMBDoc_0002"`) |
| u32le ASCII | `<u32le n> <n ascii>` | stream attribute strings, dominant at corpus scale (253k vs 1999 u16le rows) — its own sub-format, unproven (C4/C4b **candidate**) |
| u8-tag | `0x30–0x3f <len> <ascii>` | short codes (`36 08 "FINJPL  "`) |
| UTF-16 property | `<u16le 2n+4> <marker u16 3> <n utf16le chars>` | property names (`28 00 03 00 "CATStorageProperty"`) |
| UTF-16 storage | `<u16le 2n+2> <n utf16le chars>` | storage/stream names (`32 00 "Cont_0_1ae0_6991af79_dba"`) |

C5 (**candidate**, 3776/6563 = 0.575): framed UTF-16 runs match these
formulas; the residual is UTF-16-shaped binary noise. Known anomalies
carried in the note: container GUIDs re-referenced downstream (136
blocks, worst 19x), JPEG previews embedded in product regions (106/1082
regions), `CB0001` recurring as a stream-area delimiter (73/114 sample
files).

## Not yet documented (not parsed)

The B1 evidence note additionally documents the **directory table**
(40-byte records binding the name records via laws D1-D3) — it has no
L1 output field yet and is deliberately unparsed. Beyond section 4's
block model: the **OSMX/CB0001 stream headers** (boundary semantics
unproven), the **u32le attribute-string sub-format** inside geometry
streams, the **displayed part/product name and unit system for parts**
(bounded probe: negative inside payload regions; u32le `"Pixel"`/`"mm"`
scale properties found in stream territory of 3 drafting files; open
question 1 of the B3 note), and everything else await later tickets;
`docs/evidence/` is the register of open questions.
