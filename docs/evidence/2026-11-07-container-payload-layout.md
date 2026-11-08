# Evidence: container payload regions - CATStorageProperty blocks (2026-11-07)

Step (b) of ticket #19 (CATProdCont / CATFeatCont payload layouts);
empirical base from step (a). Companion to
`2026-11-07-container-table-and-trailer.md` (B1): that note decoded the
*container-name table*; this note formalizes the *payload* side and the
GUID join between the two.

Tool: `scripts/triage/decode_container_payloads.py` (read-only, mmap,
deterministic). Validation run:

    .venv/bin/python -I scripts/triage/decode_container_payloads.py \
        --manifest --sample 3 \
        --include-sha16 0018baa84f3bff6b,b83a2e9d09820603,f3862d22fd9025ff,01f2a48c9151197e,62aa3a4f2d11665a,803c9860f69c88f7,9ee5735167e37ac2,c110aebb4509f3cc,f0479c1606dfcf4b,67b37d06c40d6eed

Sample: 114 files, up to 3 per marked `detected_version` (evenly spaced
by size) plus the 10 step-(a) files force-included - 13 release buckets,
V5R15 through V5R32, ~54 s wall clock. Outputs committed here:
`container-payloads-scan.csv` (one row per block/region),
`container-payloads-strings.csv` (bounded string inventory; at most 3000
rows per region per text kind, text capped at 60 chars),
`container-payloads-claims.csv` (per-claim, per-release rates). Claim
rates are tallied on the *full* per-file inventory inside the scanner
and are recomputable from the scan CSV's `n_by_framing` column, which
carries complete per-region framing counts.

All observations are byte-level facts; interpretations are marked
*inference*.

## Block and region model

A **storage block** starts at every ASCII occurrence of
`CATStorageProperty`; all 1082 blocks in the sample carry the `34 12`
prefix (0 exceptions). Header layout (example from
`0018baa84f3bff6b`, block at 0x12e3):

    34 12 "CATStorageProperty" 80 01 00 00 00 00 22 0c 00 00 00
    34 01 03 00 34 10 "CATUnicodeString"
    a0 02 00 00 00 00 34 0b "CATProdCont" 9f          <- name1 (doc type)
    a0 02 00 00 00 00 34 0b <name2> 9f                <- name2
    3b 10 <8 bytes> <16-byte GUID>

- name1 is the doc-type name (CATProdCont, CATProduct, CATPrtCont,
  CGMGeom, CATSeeBodyCont, CATMFBRP, CATStdCont, CATCGRCont, CATPart,
  CATIA, CameraStartupContainer, CATBRepModeContainer, ...).
- The 16-byte GUID sits **inside the first 0x90 bytes** at a variable
  slot (observed 0x57-0x7b; it shifts with the two name lengths). The
  join therefore searches the window rather than a fixed offset.
- The block's **payload region** runs to the nearest boundary after the
  block start: next storage block, next `OSMX`, next
  `CATIA_V5 CB0001\0`, the header dword8 tail start (big-endian u32 at
  file offset 8), or EOF. Boundary kinds over 1082 regions: next-block
  650, OSMX 244, CB0001 188, dword8 0, EOF 0.

**The CATIA identity block.** Exactly one block per file (114/114) is
named `CATIA` and never joins: its GUID slot holds 16 zero bytes. It
carries the *document file name* as name2 in 37/114 files (e.g.
`34 2b "SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT.CATPart" 9f`); the other 77
have name1 `CATIA` only. *Inference: a file-identity property block
with a null object id; the stored name is the save-time name (renamed
files would keep the old one) - not verified.*

## Claims

Rates are over the 114-file sample; per-release values are in
`container-payloads-claims.csv`. Label = established when >= 0.98 on
the scanned set, else candidate.

| claim | statement | rate | label |
|---|---|---|---|
| C1 | every block's GUID equals one name-table record's GUID | 941/1082 = 0.870 | candidate |
| C1b | C1 excluding the CATIA identity block (null GUID by design) | 941/968 = 0.972 | candidate |
| C2 | region end byte-verifies against the claimed boundary kind, region non-empty | 1082/1082 = 1.000 | established |
| C3 | tag34 names are terminated by 0x9f | 1929/4475 = 0.431 | candidate (refined by C3b) |
| C3b | tag34 names are followed by 0x9f or a type-tag byte (0x80/0xa0/0xe0) | 4438/4475 = 0.992 | established |
| C4 | non-tag34 ASCII runs are length-prefixed (u16le, u32le or u8tag) | 264941/6091218 = 0.043 | candidate |
| C4b | among u16le/u32le framed rows, the u16le share | 1999/255170 = 0.008 | candidate |
| C5 | UTF-16 runs match 2*chars+4 (property) or 2*chars+2 (storage) | 3776/6563 = 0.575 | candidate |
| C5b | among framed utf16 rows, the property-formula share | 1908/3776 = 0.505 | candidate |
| C6 | exactly one CATProdCont record, joined by exactly one block, per file | 114/114 = 1.000 | established |
| C7 | CATFeatCont: no record, no block, no literal outside the name table | 114/114 = 1.000 | established |

Per-release notes (full table in the claims CSV):

- **C1b** is 1.000 on R15, R18, R19, R24-R32; the residual 27 blocks are
  spread over R16 (6), R17 (12), R20 (3), R21 (3), R23 (3). Their GUIDs
  are structurally present (after the `3b 10` marker) but match no name
  -table record: `PDMLogCont`, `CATPDMDataObjectCont`, `CATInfraCont`,
  `CameraStartupContainer` (2), `CATTTRSCont`,
  `CATStrFunctionalDesignExtCont` (9). *Inference: these containers'
  records are absent from the (sometimes strictly partial) name table
  of those files - consistent with B1's "directory sometimes a strict
  subset" observation.*
- **C3b** holds at 1.000 on ten of thirteen releases; the 37 residual
  rows (R20 30, R21 4, R24 3) have scattered random follow bytes
  (0x01, 0x05, 0xc5, ...) - binary-coincidence matches of the
  `34 <len>` pattern inside stream data, not a variant framing. Caveat:
  the marker set {0x80, 0x9f, 0xa0, 0xe0} was read off the step-(b)
  trial sample and applied as a fixed model here; step (a)
  independently established the 0x9f terminator on 10 files.
- **C4/C4b context.** The raw C4 denominator is dominated by printable
  runs inside binary payloads: of the 5,829,064 unframed ASCII runs in
  the full inventory, 5,803,208 (99.6%) sit in geometry/stream regions
  (>= 64 KiB); JPEG table bytes add ~2.6k rows in the committed
  inventory (flagged `in_jpeg` in the strings CSV). Even restricted to
  property-scale regions (< 4096 B, non-JPEG; never capped, so exact)
  only 0.556 of non-tag34 ASCII runs are length-prefixed - the regions
  legitimately embed small binary blobs. Among the rows the model *does*
  frame, the u32le form dominates at corpus scale (253171 u32le vs
  1999 u16le vs 9771 u8tag): the step-(a) wording "ASCII strings are
  u16le-prefixed" describes the *property/registration sections* (there
  u16le leads, e.g. `0b 00 "OMBDoc_0002"`), while geometry-stream
  attribute strings are u32le-framed (`12 00 00 00
  "2011Spring@3ds.com"`, `19 00 00 00 "CATCGMCleanerAttribute"`).
  C4b collapses to ~0.003 on R20/R21/R24 (large part files) and sits at
  0.19-0.35 on R15-R19.
- **C5/C5b context.** 0.575 of UTF-16 runs match a length formula; the
  residual is UTF-16-shaped noise inside binary. The formulas
  themselves hold on every framed run by construction; the split is
  nearly even between property names (2*chars+4, marker u16 3 - or 5
  for `CATPreview`) and storage/stream names (2*chars+2), e.g.
  `28 00 03 00 "CATStorageProperty" UTF-16LE` vs
  `32 00 "2Cont_0_1ae0_6991af79_dba" UTF-16LE`.
- **C6** distribution: every one of the 114 files has exactly one
  CATProdCont record joined by exactly one block (products: the block's
  doc-type name is `CATProduct`; parts: `CATProdCont`).

## The CATFeatCont negative finding (C7)

- B1 corpus-wide: **0 of 19,300 container-table records** (1,818 files)
  have `name1 == CATFeatCont`. CATFeatCont does appear as *name2* on
  other containers' records (382 of the B1 sample records: CATProdCont
  x108, CameraStartupContainer x78, CATCtorProxyCont x20, ...).
- Sample: 114/114 files have no CATFeatCont record, no CATFeatCont
  -named block, no block joined to a CATFeatCont record, and **zero
  literal `CATFeatCont` byte sequences outside the name table**.
- Step (a) reported the same on its 10 files (0 blocks, 0 occurrences
  outside the table).

*Inference: CATFeatCont is a display/secondary name of other
containers' records in this corpus, not a container that owns a payload
region. Any CATFeatCont *layout* work should start from the observation
that there is nothing to decode at the payload level.*

## Anomalies carried over from step (a), now quantified

1. **Repeated GUIDs.** 136 blocks have a joined record whose GUID
   occurs more than twice outside the name table. Worst in the CAA
   sample files: `08ab03c16e7c4a53` (B31CAADoc) repeats the CATPrtCont
   GUID 19x, `0018ec386764dcea` (Dictor product) the CATProdCont GUID
   7x. The count per joined record is in the scan CSV
   (`guid_occurrences_outside_table`). *Inference: container GUIDs are
   re-referenced by downstream structures (links, XDocLink) - they are
   not unique block anchors.*
2. **JPEG previews inside product regions.** 106 of 1082 regions
   contain a JPEG SOI (`ff d8 ff`); median SOI..EOI span 2,232 B. The
   product region of `b83a2e9d0982` embeds a full preview (JFIF at
   0x1501) whose Huffman/quantization tables produce long printable
   runs (`$3br`, `%&'()*456789:CDEFGHIJ...`). The strings CSV flags
   suspected preview bytes with `in_jpeg` (offset >= the region's
   first SOI; preview blobs trail the property data).
3. **Second CB0001 region.** 73 of 114 sample files contain >= 2
   `CATIA_V5 CB0001\0` markers, and 188 regions end at a CB0001
   boundary. 112 of the 114 sample files carry the `ff`-filled header
   (bytes 16-24), so the effect is broad across that file family, not a
   rare special case. *Inference: CB0001 is a stream-area delimiter
   that recurs; the region rule treats every occurrence as a boundary.*

## Bounded probe: part names and units (deliverable 3)

Time-boxed to ~15 minutes; method: framed-pattern search (tag34 / u16le
/ u32le / utf16-prop / utf16-storage) for the manifest basename and for
unit tokens, over the 114 sample files, split by inside/outside the
payload regions.

- **Part names: partially located.** The document file name appears
  exactly where the CATIA identity block stores it: 37/114 files carry
  the exact current basename as a tag34-framed name2 in that block
  (`34 <len> <name> 9f`, always with extension). The other 77 blocks
  have no name2 at all. **No other basename-like or part-name property
  exists in any payload region** (searched: the full committed string
  inventory, all framings, ASCII and UTF-16). The user-visible part
  name was not localized beyond this - see open questions.
- **Units: negative inside regions; found in stream territory.** Framed
  unit tokens inside payload regions are essentially absent (mm x2,
  cm x2, Pa x2, kg x3 across the whole sample - not localized further).
  The systematic hit is *outside* the regions, in the OSMX/stream
  territory: u32le-framed `"Pixel"` / `"mm"` scale properties in the 3
  drafting-carrying files (e.g. `60fa8686da35215b` at 0xfdade:
  `05 00 00 00 "Pixel" ... 02 00 00 00 "mm" ...` followed by a double).
  Probe stopped there per the time-box.

## Open questions

1. Where does the *displayed* part/product name and the model's unit
   system live for parts? Not in the payload regions (probe above);
   candidates are the OSMX stream territory and the per-file tail. The
   negative probe result above records where we looked.
2. C2 verifies boundary *bytes* only: are all 244 OSMX and 188 CB0001
   ends real stream headers, or do some come from 4-byte literals
   inside binary data? Needs the OSMX/CB0001 header layout (ticket
   #19 step c or later).
3. The u32le attribute-string population inside stream regions (253k
   rows corpus-sample-wide, e.g. `CATCGMCleanerAttribute`) looks like
   its own sub-format (attribute schemas in geometry streams) - worth a
   dedicated pass before any parser reuses it.
4. C1b residual: are the name tables of files with non-joining blocks
   always a strict subset of the file's containers (B1's subset law),
   or are some GUIDs never tabulated?
5. The dword8 and EOF boundaries never bind in the sample (0/1082) -
   under what file shape do they (very small files? truncated files?)?
6. C4b's collapse on R20/R21/R24 (~0.003 u16le share) - did the u16le
   registration framing shrink with version, or did large-file stream
   strings simply drown it? Needs a property-section-only comparison
   across versions with equal context.

## Deviations from the mechanical labeling bar

C3 (0x9f-only) is labeled candidate at 0.431, but the refined C3b
statement - the actual format law - is established at 0.992 with the
caveat that its marker set was read off the trial sample. C4/C5 are
labeled candidate because their raw denominators include binary payload
noise; the note gives the decomposition rather than a cleaned rate, so
the numbers stay recomputable from the committed CSVs.
