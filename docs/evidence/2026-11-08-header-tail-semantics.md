# Evidence: the CB0001 tail region decoded - the header length fields close (2026-11-08)

Ticket #18 (B2: header length-field semantics). Scope: all 1818
`magic_ok` corpus files; the deep model validates on the 1516 ff x 8
files that end with `CB__END\0` ("main scope"), with the 156 no-trailer
ff x 8 files and the 146 dual-region files (B1) measured separately.
Method: read-only byte analysis, `scripts/triage/decode_tail_region.py`
(stdlib, mmap, deterministic; run with `python3 -I`). Data:
`docs/evidence/data/tail-scan.csv` (one row per file) and
`docs/evidence/data/tail-entries-sample.csv` (per-entry rows for the
deterministic version-stratified sample, 108 files). Builds on law H1
(B1: dword8 = start of the `CATIA_V5 CB0001\0` tail region, dword12 =
its length, `dword8 + dword12 == size`, trailer G == dword12) - that
law is cited, not re-derived.

All observations are byte-level facts; interpretations are marked
*inference*. "Walk-complete" = the entry walk below parsed the catalog
to its end without hitting a byte pattern it rejects; walk coverage is
a property of this decoder, not of the files (the laws that do not need
the walk are validated on all 1516).

## The tail region is a named-region catalog

The ~10 KB that the header carves off (dword8..EOF) is a **catalog of
named file regions**: a list of fixed-layout entries, each carrying a
UTF-16 name and a (start, length) pair of *absolute file offsets*,
plus a final record that IS the B1 trailer. Together the named regions
tile the file body - every byte from offset 64 (just past the 64-byte
file header area the catalog never claims) up to dword8 (where the
catalog itself starts). *Inference: this is the file's own table of
contents; the header's dword8/dword12 locate it and dword12 states its
exact length. The "size - ~10 KB" Phase 1 observation is this catalog.*

Worked example (`0018baa84f3bff6b`, povdoigt/SP-02 part, 224039 B,
V5R19SP0HF0, tail = 9306 B): 42 catalog records name 41 regions tiling
[64, 214733) - `GesToler` [64, 88), `Indexe` [88, 1628) (the B1
directory table), `Data` [1628, 2068) (the B1 name records), ...,
`CATStorageProperty` [210933, 213507) (the region holding the writer
registration block), `Format` [213781, 214639), `CATIA1`
[214639, 214733) - plus the trailer record's own region [213507,
213781), which starts with the registration block.

## Tail layout (ff x 8 generation; offsets relative to dword8)

    T+0    16 B   magic "CATIA_V5 CB0001\0"                     (law H1, B1)
    T+16   20 B   tail header (below)
    T+36   28 B   zeros
    T+64   entry 0 (root entry, below)
    then   catalog entries: [hdr84][xrec13][fil87][name]
    then   end block (81 B, fixed) + trailer (36 B, B1's model)

**Tail header (T+16, 20 B)** - 1516/1516 main scope:

| offset | field | observed |
|---|---|---|
| +0 | tag | `0x4e` on 1516/1516 main-scope files (the 8 exceptions are all no-trailer `unknown`-version files and carry `0x55`) |
| +1 | u16be | 1000, constant (1818/1818) |
| +3 | u16be | 64 - the region-chain origin (law R1) |
| +5 | u16be | 12, constant (1818/1818); semantics open |
| +7 | u16le | cntA == named entries + 1 (the trailer) - exact on walk-complete files (1070/1070) |
| +9 | u16le | cntB == cntA + 1 == named entries + 2 (entry 0 included) - exact on walk-complete files (1070/1070); 1483/1516 main raw, 156/156 no-trailer, 146/146 dual. The 33 exceptions (R20/R21/R24) have a nonzero high byte (0x01..0x0d) - the count field exceeds one byte there; semantics open. |
| +11 | 8 B | file-dependent (256-distinct bytes; samples `033e3500 036b2700`, `0081e300 00a01700`); bytes +0/+4 take few values (0/1/6, 0/1/2). Semantics open. |

Zeros at T+36..T+64: 1818/1818.

**Entry 0 (root, at T+64)** - its length is file-dependent:
`[u32be M][u32be 1][zeros][01][u32be 94][u32be 0][ts8][zeros 19][12]
[zeros 35][name0]`, where M = 86 + 20k
(k = 0..5 corpus-wide: 86/106/126/146/166/186 on 1188/398/156/65/10/1 files) and the entry-0
length == M + 87 (1806/1818). The `[01][X0][0][ts8]` record always sits
at (name0 start - 72) and **X0 == 94 == the first catalog entry's region
length** (1516/1516 main, 146/146 dual, 144/156 no-trailer). The u32be
1 after M is entry 0's sequence number (the named entries then number
2..cntB). The name0 texts are per-file hex-ish strings (e.g.
`.0e01a0000acb49169bb140000`).

**Catalog entry** = 184-byte fixed part + a UTF-16 name. Per entry
(region-relative to the entry start = the previous name field's end):

    hdr84  [00 00][6a][000][seq u16le][space u32le][space u8][Y u32be]
           [0000][ts8][ts8][ts8][000][12][35 zeros]
    xrec13 [01][X u32be][Y u32be][Y u32be]          (the region record)
    fil87  [11 zeros][u8][000][u8][00][Ynext u32be][000][ts8][ts8][ts8]
           [000][12][35 zeros]
    name   u16le len + UTF-16LE chars + NUL char, two framings:
           storage:  len = 2*chars + 2        (e.g. `0e 00 "CATIA1"`)
           property: len = 2*chars + 4 with a marker u16 (3 or 5) before
                     the text (e.g. `28 00 03 00 "CATStorageProperty"`)

All multi-byte region fields are big-endian; seq/space are
little-endian (measured; the skeleton mixes widths). The three ts8
values are 8-byte per-file time-like values repeated within an entry
and across its neighbours; their semantics are open.

Laws (rates on the main scope; per-entry rates across all files in
parentheses):

| law | statement | rate |
|---|---|---|
| W1 | from name0, each next name starts exactly 184 B after the previous name field ends; each xrec has flag `01` and Y1 == Y2 | walk-complete 1070/1516 = 0.706 (decoder coverage; per-version walk rates 0.24-1.00, see below); failures are flag-check stops (decoder rejects a byte pattern), not model violations |
| W2 | hdr84 Y == xrec Y (same entry) | per-file 1818/1818 where entries parse (per-entry 100%) |
| W3 | fil87 Y == the NEXT entry's xrec Y | per-file 1818/1818 where two consecutive entries parse |
| W4 | seq runs 2, 3, ... in list order | 1806/1818 |
| S1 | skeleton markers: `6a` at hdr+2, `12` at hdr+48 and fil+64 | per-entry 61458/63555 = 0.967 |
| N1 | name framing: len == 2*chars+2 (storage) or == 2*chars+4 with marker 3/5 (property), NUL-terminated UTF-16LE, chars >= U+0020 | holds on every parsed entry by construction of the walk; vocabulary led by `CATStorageProperty`, `CATPropertySets`, then the per-file fixed set `CATIA1`, `Format`, `GesToler`, `Indexe`(d), `Data`, `Project`, `ProjectHeader`, `TimeStamp`, and GUID-derived stream names `Cont_0_1ae0_6991af79_dba` / `0_1ae0_6991af79_dba` |

**The xrec is the region record** *inference with strong byte
corroboration*: X = region start, Y = region length, both absolute file
offsets; the two Y copies and the hdr84/fil87 Y copies agree (W2/W3).
*Interpretation of the space flag*: `space` (u32le at hdr+8, echoed as
u8 at hdr+12) is 1 exactly on `Cont_*`-named entries and on the three
fixed names {CATIA1, Format, CATPreview} - 1426/1516 main; the
converse (`Cont_*` always space 1) holds on 1280/1516 = 0.844. The
flag's meaning is open; the one-directional law is corpus-wide
(includes no-trailer and dual files where entries parse).

**End block (81 B, fixed) + trailer.** After the last named entry comes
an 81-byte block: the final record's hdr84 truncated after its `12`
marker (`[00 00][6a][000][seq u16le = cntB][space 2][space 2][Y u32be]
[0000][ts8 x3][000][12]` + zero fill to 81), followed by B1's 36-byte
trailer. Law: end block seq == cntB, space == 2, Y == trailer C -
1089/1096 walk-complete main files; the 81-byte length is constant
(1070/1070 walk-complete main). The trailer's first 16 bytes are
exactly the final xrec: `[A=01][B][C][D]` with C == D (B1's pair) -
**this decodes B1's open question on the C == D pair: C is the final
region record's length, stored twice because the xrec form stores Y
twice** - 1556/1556 CB__END-ending files. E, F, G keep B1's readings
(G == dword12 == tail length, 1556/1556).

**Trailer B (the registration pointer).** B < dword8 on 1556/1556 -
*correction/precision vs the ticket's framing: the registration block
is NOT inside the tail region* (B1 already placed it in the payload;
this makes it corpus-wide). B is always the X of the final region
record: the region [B, B+C) starts with the registration block
(B1 byte-proof) - "previous named region ends exactly at B" holds on
1066/1070 walk-complete main files, and the 41-byte registration
pattern byte-verifies AT B on 1516/1516 main files. The same 41-byte
pattern (`[4d|4e][u32le 17]"DASSAULT-SYSTEMES"[u32le 5]"CATIA"[u32le
6]"041803"`) occurs 3-27 times per file (median 12) - the B target is
one of a family of identical-format blocks; what distinguishes the
others is open (one was observed as the first bytes of a stream
region).

## The region-tiling laws (R1-R3)

On walk-complete main-scope files (1070), with the region set = {the
entries' (X, Y)} + {the trailer's (B, C)}, sorted by X:

| law | statement | rate |
|---|---|---|
| R1 | min region start == 64 (the header's u16be@+19) | 1070/1070 = 1.000 |
| R2 | max region end == dword8 (the tail start) | 1070/1070 = 1.000 |
| R3a | full tiling: consecutive regions are contiguous (no unclaimed bytes) | 868/1070 = 0.811 |
| R3b | at most one unclaimed gap | 1055/1070 = 0.986 |
| R4 | the trailer's region starts at B == the previous region's end | 1066/1070 = 0.996 |

The residual gaps are small (227 files carry gaps, 276,706 unclaimed
bytes total; sizes 1-6280 B across 217 gaps) and their bytes contain
*entry-like records with UTF-16 names* - e.g. `00fe73a09c8c7d70` has a
290 B gap at [7051, 7341) containing `2a 00 00 00 0c 00 02 00 00 00 1c
00 "ProjectHeader" ...` - and the `CATIA1` / `Format` regions'
contents are themselves entry-like mini-structures (the `CATIA1`
region of the worked example starts `00 00 00 5e 00 00 00 02 00 00 00
02 00 00 00 36 00 00 00 2a 00 02 00 00 00 28 00 03 00
"CATStorageProperty" ... 0e 00 "CATIA1" 00`). *Inference: the catalog
is recursive - some regions embed sub-catalogs; the main catalog still
tiles everything else. The recursion is undocumented beyond these
bytes (open).*

**Exact length accounting** (the deliverable's "internal length
fields"): on walk-complete main files the tail length is fully
determined by the entry list,

    tail_len == 64 (magic+header+zeros)
             + (entry0 area incl. its name field)
             + sum over named entries of (184 + name field)
             + 81 (end block) + 36 (trailer)

1095/1096 (the one exception differs by a few bytes). Equivalently:
dword12 == the catalog's exact length; the "size - ~10 KB" value is
~237 bytes per named region (per-entry quotient median 237, range
230-243) plus the fixed ~350 B overhead. This is why the tail is
9-12 KB regardless of file size: the region count is (per-file)
~15-50, and big files simply have huge regions.

## Generations and exceptions

- **No-trailer ff x 8 (156 files, all `unknown` version)**: the tail
  holds the same header (tag `0x4e` on 149/156, tag `0x55` on 8) and a
  catalog (entries parse on 156/156; cnt law 156/156; e0 laws
  144/156; e1 name `CATIA1` on 118/156) but **no end block and no
  trailer** - the file ends in zeros (B1's "all-zero tails" is the
  tail end, not the whole tail). The regions found still reach dword8
  on 138/156. The trailer-dependent claims (R4, C==D) do not apply.
- **Dual-region (146 files, B1's generation)**: magic at dword8
  146/146 (dword8 = the second CB0001 region); the tail parses as the
  same catalog on the entries that parse (e0 laws 146/146, cnt law
  146/146, tag `0x4e` 145/146); the 40 CB__END-ending dual files have
  trailer == final xrec 40/40. dword16 = first CB0001 region 143/146,
  dword8 = last CB0001 region 145/146 (re-measures B1). **dword20
  stays open**: "length of the first region" (first region end = first
  `CB__END` + 8) holds on only 39/146, and dword12/2 on 19/146 - no
  model reached the bar.
- **Walk coverage by release** (main scope): R15 0.815, R16 0.243,
  R17 0.935, R18 0.870, R19 0.764, R20 0.603, R21 0.639, R23 0.824,
  R24 0.879, R25+ 1.000, unknown 0.780. The failures are decoder
  stops (flag checks on R16; name-parse stops on R19/R20/R21), not law
  violations: W2/W3 hold on 100% of files in every release bucket
  where any entry parses, and R3b (<= 1 gap) holds at 0.889-1.000 per
  bucket on walk-complete files.

## Outlier classification (tail_delta = size - dword8)

Corpus: min 3138, p25 9308, median 10280, p75 11694, max 124164
(matches Phase 1). With the catalog model the distribution is
explained by construction: tail ~ 237 B x regions + ~350 B fixed.

- **Min (3138, 3 files: `71c7447e0a42` R19, `b83a2e9d0982` R19,
  `c75525329d87` R20)**: small parts with the minimal catalog - cntB
  15, 13 entries parsed, walk-complete, tiling holds. Explained: few
  regions -> short tail.
- **p25-p75 (9308-11694)**: the normal band (25-45 regions).
- **Max (124164, `ca047ae9ad9e`, 124228 B, `unknown` version)**:
  dword8 = 64 - the catalog starts right after the header and the
  region set reaches the file SIZE (not dword8; the catalog's own
  extent falls inside the tiled range). The catalog itself is small
  (cntB 19, 17 entries parsed, walk stops at +4055); the remaining
  ~120 KB of the tail is unclaimed bytes. **Open** (single file,
  unknown generation).
- **The 26-70 KB tails (`ae85fae7b1e6` R20 69502, `13bb5c0c4961` R21
  31326, `ab1c7b09f52a` R20 30514, `50cd280f35dc` R21 26078,
  `9c14d692c9e1` unknown 33644)**: the catalog tiles [64, dword8)
  normally (region_max_end == dword8 on the R20/R21 four) but the tail
  additionally embeds a 20-65 KB binary blob between catalog sections
  (e.g. `ae85fae7b1e6` at tail+4289..+62694, content unidentified).
  For the two `unknown`-version files the regions reach file size
  instead of dword8 (same self-inclusive pattern as the max outlier).
  **Open**: what the blob is and why the region convention differs on
  the unknown-generation files.
- **Correlation with no-trailer/dual files**: none - the min and max
  outliers are all CB__END-ending ff x 8 files; the no-trailer (156)
  and dual (146) files sit inside the normal tail_delta band (their
  delta distribution matches the main scope's).

## Corrections and precisions vs documented assumptions

- B1's C == D "semantics unproven" pair: **decoded** - it is the final
  xrec's Y (the last region's length), stored twice by the xrec form;
  C == D == 274 in the worked example == the region [213507, 213781)
  that begins with the registration block.
- The ticket's "the writer registration block(s) the trailer's B
  pointer targets" as tail content: B targets a **payload** block
  (B < dword8 on 1556/1556) - the tail merely *names* its region. The
  registration pattern is not unique per file (3-27 occurrences,
  median 12); B's occurrence is distinguished only by being the
  trailer's pointer.
- B1's "the 156 ff x 8 files without CB__END (all-zero tails)": the
  zero region is the tail END; the tail START carries a normal catalog
  (entries parse on 156/156) without end block/trailer.
- Phase 1's "per-file structured tail of ~9-12 KB": it is a region
  catalog whose length the header states exactly (dword12) and whose
  entry count the header states (cntB).

## Unknowns / next questions

1. Semantics of the space flag (1 on `Cont_*`/top regions, 2
   otherwise) and of the header's constant 12 and 8 varying bytes.
2. The region-name semantics: which regions map to which format
   structures beyond `Indexe`/`Data` == the B1 directory/name tables
   (byte-verified in the worked example) - e.g. are `Cont_*` regions
   the OSMX stream territory?
3. The nested sub-catalogs (gap family + `CATIA1`/`Format` region
   contents) and the 20-65 KB blobs inside the largest tails.
4. dword20 in the dual-region generation (two hypotheses tested, both
   fail: 39/146 and 19/146).
5. The cnt field's high bytes on 33 files (R20/R21/R24) and the
   decoder walk-coverage limits on R16 (flag stops) and R19-R21
   (name stops) - a future pass with a wider name charset may close
   the coverage gap.
6. The `0x55` tag on the 8 no-trailer `unknown` files.

## Reproduction

```
python3 -I scripts/triage/decode_tail_region.py
```

Runtime: ~2 min (one regex pass over the corpus for the registration
multiplicity + per-file tail parsing). Outputs the two CSVs above and
the claim summary to stdout. The near-identical save pairs of B1 keep
their interpretation under this model: the catalog (and with it B)
moves by the size delta because the regions' offsets shift.

## Ready-to-adopt claim block for docs/format/README.md

Coordinator: fold into section 1 (header) and a new section 1b, or
merge with B6. Labels follow section 4's convention (established =
>= 0.98 on the scanned set; candidate below).

```markdown
## 1b. Tail region - the CB0001 catalog **(documented, not parsed)**

Evidence: docs/evidence/2026-11-08-header-tail-semantics.md (verified
by scripts/triage/decode_tail_region.py; per-file rows in
docs/evidence/data/tail-scan.csv). The tail region is the bytes
[dword8, dword8+dword12) - B1's law H1 - and is a catalog of named
file regions. Claims are version-scoped: the ff x 8 + CB__END
generation (1516/1818 files, V5R15-V5R32 + unknown) unless stated.

| Tail offset | Field | Claim |
|---|---|---|
| +0 | magic | `CATIA_V5 CB0001\0` (law H1, B1; 1818/1818 incl. dual-region files). |
| +16 | header | 20 B: tag `0x4e` (1516/1516 main), u16be 1000, u16be 64 (region-chain origin), u16be 12 (constant, semantics open), u16le cntA, u16le cntB == cntA+1 (0.978; == the catalog record count incl. the trailer), then 8 file-dependent bytes (open). Zeros at +36..+64 (1818/1818). |
| +64 | entry 0 | Root entry: `[u32be M][u32be 1]` with M in {86+20k}, length M+87 (0.994), containing `[01][u32be 94][u32be 0][ts8]` at (name0-72) and a UTF-16 name; 94 == the first region's length (1516/1516 main). |
| then | entries | `[hdr84][xrec13][fil87][name]` (184 B fixed + name): hdr84 = `00 00 6a 000` + seq u16le + space u32le/u8 + Y u32be + 3 ts8 + `12` + zeros; xrec = `01 [X u32be][Y u32be][Y u32be]` (region start/length, absolute file offsets, Y twice); fil87 repeats the NEXT entry's Y at +29; name = u16le len + UTF-16LE + NUL char, storage (len=2n+2) or property (len=2n+4, marker 3/5). Y-copy laws hold on 100% of parsed entries. |
| -117 | end block | 81 B fixed: the final record's hdr84 truncated after `12`, seq == cntB, Y == C (0.994); then the 36 B trailer. |
| -36 | trailer | == the final xrec + tail fields: A=01 (flag), B (region start; the writer registration block sits at B, payload-side), C==D (region length, stored twice - decodes B1's pair), E, F, G == dword12. |

Region model (**established** on walk-complete files, 1070/1516; walk
coverage is a decoder property, per-release 0.24-1.00): the entries'
(X, Y) pairs + the trailer's (B, C) tile the file body [64, dword8) -
min start == 64 and max end == dword8 on 1070/1070; full contiguity
868/1070 (<= 1 gap 1055/1070; residual gaps carry nested sub-catalog
bytes, open). The tail length is exactly determined by the entry list
(184 + name field per entry + fixed 161 B; 1095/1096) - the "size -
~10 KB" of Phase 1 is this catalog (~237 B per region). The space
flag is 1 exactly on `Cont_*`/`CATIA1`/`Format`/`CATPreview` entries
(0.941; converse 0.844 - candidate).

Generations: no-trailer ff x 8 files (156, all unknown version) carry
the catalog without end block/trailer and end in zeros; dual-region
files (146, B1) carry the same catalog in their dword8 tail
(e0/cnt laws 146/146, trailer == final xrec on their 40 CB__END
files); dword20 remains open. Outlier tail lengths (3138 .. 124164)
are explained by region count (min) or by unidentified 20-65 KB blobs
embedded in the tail (max family; open).
```
