# 5. Container payload blocks — CATStorageProperty, identity block, document_name

Partially parsed: the only payload-level L1 output is `document_name`
(page 5.2, `catpart.identity`); the block model, region rule and string
framings are **documented, not parsed** — this page exists so the B/C
branches parse only what is documented.

Evidence: [2026-11-07-container-payload-layout.md](../evidence/2026-11-07-container-payload-layout.md)
(B3; rates on a 114-file sample spanning V5R15-V5R32, per-release
values in `docs/evidence/data/container-payloads-claims.csv`; the
sample includes the 10 step-(a) R19/R21 files across 7 repos),
[2026-11-08-units-names-probe.md](../evidence/2026-11-08-units-names-probe.md)
(C3 phase A, ticket #25; 108-file R15-R24 sample,
`docs/evidence/data/units-names-probe-claims.csv`) and the B5
differential ([2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md)).
Labels: **established** = rate >= 0.98 on the scanned set; **candidate**
= below that bar; negative results that were measured are established
(negative).

## 5.1 Block model

A storage block starts at every ASCII `CATStorageProperty` prefixed by
`34 12` **(established, 1082/1082 sample blocks, 0 exceptions)**.
Header layout (example from `0018baa84f3bff6b`, block at 0x12e3):

    34 12 "CATStorageProperty" 80 01 00 00 00 00 22 0c 00 00 00
    34 01 03 00 34 10 "CATUnicodeString"
    a0 02 00 00 00 00 34 0b "CATProdCont" 9f          <- name1 (doc type)
    a0 02 00 00 00 00 34 0b <name2> 9f                <- name2
    3b 10 <8 bytes> <16-byte GUID>

| ID | At | Field | Claim | Label | Scope |
|---|---|---|---|---|---|
| (prefix) | +0 | prefix | `34 12` on all 1082 sample blocks. | established | 114-file sample, V5R15-R32 |
| PL-C3b-tag34 | +2.. | type name, name1 | After `CATStorageProperty` and the `80 01 00 00 00 00 22 <u8> 00 00 00` framing, tag34-framed names follow. name1 is the doc-type name: `34 <len> <name>` followed by `0x9f` or a type-tag byte (0x80/0xa0/0xe0) — 4438/4475 = 0.992 (1.000 R19, 0.991 R21, 0.940 R20; the residuals are binary coincidences of the `34 <len>` pattern inside stream data, not a framing variant). The raw claim C3 ("terminated by 0x9f only") is 0.431 and is refined by this law. Vocabulary: `CATProdCont` (parts), `CATProduct` (products), `CATPrtCont`, `CGMGeom`, `CATSeeBodyCont`, `CATMFBRP`, `CATStdCont`, `CATCGRCont`, `CATPart`, `CATIA`, `CameraStartupContainer`, `CATBRepModeContainer`, ... | established | 114-file sample; per-release rates in the claims CSV |
| (name2) | then | name2 | second tag34-framed name (`a0 02 00 00 00 00 34 <len> <name> 9f`); empty (`34 00`) when absent. | established (framing) | 114-file sample |
| PL-C1b-join | then | GUID | 16 bytes after the `3b 10` marker, at a variable slot (observed 0x57-0x7b; it shifts with the two name lengths) inside the first 0x90 bytes — the join searches the window, not a fixed offset. Join to the name-table records: every non-identity block's GUID equals one record's GUID on 941/968 = 0.972 (raw claim C1, including the identity block, is 941/1082 = 0.870) — below the bar (candidate); the 27 residual blocks (`PDMLogCont`, `CATPDMDataObjectCont`, `CATInfraCont`, `CameraStartupContainer`, `CATTTRSCont`, `CATStrFunctionalDesignExtCont`) are containers absent from those files' (sometimes strictly partial) name tables — B1's subset phenomenon, not a framing change (1.000 R19 vs 0.969 R21). | candidate | 114-file sample |
| PL-C2-region-rule | block start | payload region | The block's payload region runs from the block start to the nearest of: next storage block (650 regions), next `OSMX` (244), next `CATIA_V5 CB0001\0` (188), the header dword8 tail start (0), EOF (0). Boundary bytes verify against the claimed boundary kind on 1082/1082 = 1.000 (1.000 on every sampled release). Whether every OSMX/CB0001 match is a real stream header is open. | established | 1082 regions on the 114-file sample |
| (identity slot) | GUID slot | identity | the block named `CATIA` carries a 16-zero-byte GUID slot — it never joins a record by design (5.2). | established | 114/114 files |

## 5.2 The CATIA identity block and document_name (parsed)

Paragraph claims:

- D1 (differential ID-model) **(established, 114/114 + 108/108)**:
  exactly one storage block
  per file is named `CATIA` (the identity block), with the 16-zero-byte
  GUID slot; it never joins a name-table record. 1.000 on every
  sampled release.
- D2 **(established, 108/108)**: after name1's terminator, the name2
  field walks as `a0 02 00 00 00 00 34 <len> <ascii> <0x9f or
  type-tag>` on every identity block; the empty form is `34 00 9f`.
- ID-doc-name **(established, version-scoped)**: the walk's name2 is
  the save-time document name, reported as-is (`document_name`).
  Present on 40/108 sample files — per release R15 8/9, R16 7/14, R17
  12/17, R18 8/9, R19 5/16, and **0/43 on R20/R21/R23/R24**. The R20
  spot-check byte-confirms the flip (`0a64c44c` carries the empty
  form): the writer stopped storing it between R19 and R20 — the one
  clean writer-version change the differential found. Version scope:
  "R15-R19 partial (declining), null from R20 onward (in this corpus)".
- D4 **(established, 40/40)**: when present, the name always carries
  the `.CATPart`/`.CATProduct` extension.
- D3 **(established as the save-time rule, 37/40)**: the stored name
  equals the current manifest basename on 37/40 files; the 3 exceptions
  are renamed files keeping the save-time name (`Geometrical
  Bundle1.CATProduct` with a space vs the current
  `GeometricalBundle1.CATProduct`, 3 V5R18SP2HF74 products). This
  upgrades B3's inference to a measured fact: the field is the
  save-time document name, never a current-file assertion — it is
  reported as-is and never used as the current basename.
- D5 **(established, negative, 0/108)**: the manifest basename occurs
  as a framed string outside the identity block region on 0/108 files —
  there is no second name structure.

Null conditions: `document_name` is null when the name2 field is empty
(`34 00 9f`; 68/108 sample files — every R20+ file of the sample), when
the file has no (or more than one) identity block, or when the walk
fails — the parser never raises on malformed input.

## 5.3 The model unit system — documented negative

**(established, negative)**: the model unit system (length/mass/angle)
has **no documented location** in the two decoded territories. A fixed
vocabulary of 29 unit tokens, framed patterns only, over the 108-file
R15-R24 sample yields zero structured occurrences (U1: only 6/108 files
carry any framed unit-family token at all, every hit accounted for
below): payload regions — 34
scattered hits on 4 files, all verified binary coincidences inside
packed binary data; OSMX/stream territory — only the drafting
`Pixel`/`mm` scale store of the 2 drafting-namespace files (B3's
documented exception: viewport scales, not model units); tail region —
0 hits; 0/108 files carry unit tokens in stream/tail territory without
a drafting namespace (U2). The spec-tree `Volume/Density/Mass/Length/
Angle` tokens (42 hits, u32le) are model content of CAA-sample parts,
not a document-level declaration (P1: 0/108 files carry a display-name
property token either — the displayed part/product name beyond the
save-time document name is a documented negative). The glossary's
`units-present` invariant is therefore **defined, not enforced** (C2
precedent, `catpart.fitness.invariants`): its documented exceptions
cover every current file, so no file is penalized. A future units claim
must come from a new B-branch note; a token-less enum encoding is out
of reach of byte evidence in these territories.

## 5.4 Cardinality and the CATFeatCont negative

| ID | Claim | Label | Scope |
|---|---|---|---|
| PL-C6-cardinality | exactly one `CATProdCont` record per file, joined by exactly one block (doc-type name `CATProdCont` on parts, `CATProduct` on products) — 114/114; 1.000 on both lines. | established | 114-file sample |
| PL-C7-featcont | CATFeatCont negative: 0 of the 19,300 name-table records have `name1 == CATFeatCont`; it appears only as name2 of other containers' records, and there are zero literal `CATFeatCont` byte sequences outside the name table (114/114 sample, cross-checked corpus-wide). Inference: a display/secondary name, not a container that owns a payload region — there is no CATFeatCont layout to decode at payload level. | established (negative) | 114-file sample + corpus records |

## 5.5 String framing families inside regions (context, not laws)

| Family | Form | Where seen | Label | Scope |
|---|---|---|---|---|
| tag34 name | `34 <len> <ascii>` + `0x9f` or a type-tag byte | property sections (names above) | established (framing) | 114-file sample |
| u16le ASCII | `<u16le n> <n ascii>` | property/registration sections (`0b 00 "OMBDoc_0002"`) | established (observed form) | 114-file sample |
| u32le ASCII | `<u32le n> <n ascii>` | stream attribute strings, dominant at corpus scale (253k vs 1999 u16le rows, e.g. `12 00 00 00 "2011Spring@3ds.com"`); its own sub-format, unproven | candidate | 114-file sample |
| u8-tag | `0x30-0x3f <len> <ascii>` | short codes (`36 08 "FINJPL  "`) | established (observed form) | 114-file sample |
| UTF-16 property | `<u16le 2n+4> <marker u16 3 or 5> <n utf16le chars>` | property names (`28 00 03 00 "CATStorageProperty"`) | established (formula holds on every framed run) | 114-file sample |
| UTF-16 storage | `<u16le 2n+2> <n utf16le chars>` | storage/stream names (`32 00 "Cont_0_1ae0_6991af79_dba"`) | established (formula holds on every framed run) | 114-file sample |

| ID | Claim | Label | Scope |
|---|---|---|---|
| C4 | non-tag34 ASCII runs are length-prefixed — 264941/6091218 = 0.043 raw (the denominator is dominated by printable runs inside binary payloads); restricted to property-scale regions (< 4096 B, non-JPEG) 0.556. | candidate | 114-file sample |
| C4b / PL-C4b-u16le | among u16le/u32le-framed ASCII rows, the u16le share — 0.008 corpus-wide (1999/255170); differs across lines: 0.241 R19 vs 0.003 R20/R21. Driver unresolved: R19's sample files are small (max 8.9 MB), R20/R21's are large parts whose stream strings drown the property framing — content vs writer cannot be separated without an equal-context comparison (new-decoding work, B6+). Carried as differs-with-open-driver, not as a format change. | candidate + open (driver) | 114-file sample |
| C5 / C5b | framed UTF-16 runs match the two formulas — 3776/6563 = 0.575; the residual is UTF-16-shaped binary noise. Among framed UTF-16 rows the property/storage split is nearly even (0.505). | candidate | 114-file sample |

Anomalies carried in the B3 note: container GUIDs re-referenced
downstream (136 blocks, worst 19x on a CAA part — GUIDs are not unique
block anchors); JPEG previews embedded in product regions (106/1082
regions, median SOI..EOI span 2,232 B); `CATIA_V5 CB0001\0` recurring
as a stream-area delimiter (73/114 sample files carry >= 2 markers; 188
regions end at a CB0001 boundary).
