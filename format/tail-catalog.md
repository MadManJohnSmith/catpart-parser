# 2. Tail region — the `CATIA_V5 CB0001\0` catalog **(documented, not parsed)**

No schema v1 field walks the catalog; the trailer's `G` field
(`tail_region_length`) is its only L1 output (page 4, trailer.md).

Evidence: [2026-11-08-header-tail-semantics.md](../evidence/2026-11-08-header-tail-semantics.md)
(verified by `scripts/triage/decode_tail_region.py`; per-file rows in
`docs/evidence/data/tail-scan.csv` and per-entry rows in
`docs/evidence/data/tail-entries-sample.csv`), building on law H1
([2026-11-07-container-table-and-trailer.md](../evidence/2026-11-07-container-table-and-trailer.md)),
B4's large-file resync correction
([2026-11-08-geometry-payloads.md](../evidence/2026-11-08-geometry-payloads.md))
and the B5 differential
([2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md)).
The tail region is the bytes `[dword8, dword8 + dword12)` (law H1) and
exists on all 1818 magic-verified files. Claims are version-scoped to
the ff x 8 + CB__END generation (1516/1818 files, V5R15-V5R32 + unknown
— the "main scope") unless stated. "Walk-complete" = the entry walk of
the committed decoder parsed the catalog to its end without hitting a
byte pattern it rejects; walk coverage is a property of that decoder,
not of the files.

## 2.1 What the tail is

The ~10 KB the header carves off (dword8..EOF) is a **catalog of named
file regions**: a list of fixed-layout entries, each carrying a UTF-16
name and a (start, length) pair of absolute file offsets, plus a final
record that IS the trailer. Together the named regions tile the file
body — every byte from offset 64 (just past the 64-byte header area the
catalog never claims) up to dword8, where the catalog itself starts
**(established, 1070/1070 walk-complete files; R1/R2 below)**. The
header's dword8/dword12 locate the catalog and dword12 states its exact
length; the Phase 1 "size - ~10 KB" observation is this catalog, at
~237 B per named region plus ~350 B fixed overhead.

Worked example (`0018baa84f3bff6b`, povdoigt/SP-02 part, 224039 B,
V5R19SP0HF0, tail = 9306 B): 42 catalog records name 41 regions tiling
[64, 214733) — `GesToler` [64, 88), `Indexe` [88, 1628) (the directory
table), `Data` [1628, 2068) (the name records), ...,
`CATStorageProperty` [210933, 213507) (the region holding the writer
registration block), `Format` [213781, 214639), `CATIA1` [214639,
214733) — plus the trailer record's own region [213507, 213781), which
starts with the registration block.

## 2.2 Tail layout (offsets relative to dword8)

    T+0    16 B   magic "CATIA_V5 CB0001\0"                     (law H1)
    T+16   20 B   tail header (below)
    T+36   28 B   zeros
    T+64   entry 0 (root entry, below)
    then   catalog entries: [hdr84][xrec13][fil87][name]
    then   end block (81 B, fixed) + trailer (36 B, trailer.md)

| ID | Tail offset | Field | Claim | Label | Scope |
|---|---|---|---|---|---|
| TL-magic | +0 | magic | `CATIA_V5 CB0001\0` byte-verifies at dword8 — 1516/1516 ff x 8 files and 146/146 dual-region files. | established | ff x 8 + dual, every bucket |
| TL-header-constants | +16..+36 | tail header | 20 B: tag `0x4e` (1516/1516 main), u16be 1000 (1818/1818), u16be 64 (the region-chain origin, law R1), u16be 12 (constant, semantics open), u16le cntA, u16le cntB, then 8 file-dependent bytes (+11..+19; 256-distinct-byte samples like `033e3500 036b2700`; bytes +0/+4 take few values). Zeros at +36..+64 (1818/1818). | established (constants) + open (u16be 12, the 8 bytes) | main scope; constants 1818/1818 |
| TL-cnt-law | +25..+27 | cntA, cntB | cntB == cntA + 1 (u16 read): exact on walk-complete files (1070/1070), 1483/1516 main raw, 156/156 no-trailer, 146/146 dual. Precision over B2 (B5): on the 33 exceptions (R20 16, R21 15, R24 2 — all parts >= 18.6 MB) the cntB slot's HIGH byte is nonzero while `cntB & 0xFF == cntA + 1` holds on 33/33 — the count lives in the low byte; the high byte's semantics are open. Byte example (`13bb5c0c49616ade`, R21, 190 MB): tail header `4e 03 e8 00 40 00 0c 00 31 00 32 0b` — cntA = 49, cntB = 2866, low byte 50 == cntA + 1; contrast `0018baa84f3bff6b` (R19): 41, 42. | established (low-byte law) + open (high byte) | R19 0/649 exceptions; R20 16/189; R21 15/355; R24 2/33; all parts >= 18.6 MB |
| TL-e0-laws | +64 | entry 0 (root) | `[u32be M][u32be 1]` with M = 86 + 20k (k = 0..5 corpus-wide: 86/106/126/146/166/186 on 1188/398/156/65/10/1 files); the entry-0 length == M + 87 (1806/1818; 100% on R19/R21). It contains `[01][u32be 94][u32be 0][ts8]` at (name0 start - 72); X0 == 94 == the first catalog entry's region length (1516/1516 main, 146/146 dual, 144/156 no-trailer). The u32be 1 is entry 0's sequence number (named entries number 2..cntB). name0 is a per-file hex-ish string (e.g. `.0e01a0000acb49169bb140000`). What sets M is open. | established + open (M's driver) | main scope + dual + no-trailer |
| TL-walk-ok | T+64.. | walk coverage | The primary walk completes on 1070/1516 = 0.706 of main-scope files; per-release coverage 0.24 (R16) to 1.00 (R25+). Failures are decoder stops (flag checks on R16, name-parse stops on R19-R21), not model violations: W2/W3 hold on 100% of files in every release bucket where any entry parses. A resync continuation (re-anchoring on the next `00 00 6a` hdr84 whose record validates) recovers the large-file entries. | open (decoder coverage; a statistic, not a law) | main scope, per-release in tail-scan.csv |
| TL-endblock | -117 | end block | 81 B fixed: the final record's hdr84 truncated after its `12` marker, seq == cntB, space == 2, Y == trailer C — 1089/1096 walk-complete main files (100% of walk-complete files on R19/R21); the 81-byte length is constant (1070/1070). | established | walk-complete main |
| TL-trailer-xrec | -36 | trailer | The trailer's first 16 bytes are exactly the final xrec `[A=01][B][C][D]` with C == D — this decodes B1's "semantics unproven" pair: C is the final region record's length, stored twice because the xrec form stores Y twice (1556/1556 CB__END-ending files). E, F, G keep the trailer.md readings. | established | 1556 CB__END-ending files; 40/40 dual CB__END files |
| TL-accounting | - | length accounting | On walk-complete main files the tail length is exactly `64 + entry0 area (incl. its name field) + sum over named entries of (184 + name field) + 81 + 36` — 1095/1096 (the one exception differs by a few bytes). dword12 == the catalog's exact length. | established | walk-complete main (496/496 R19, 227/227 R21) |

## 2.3 Catalog entry — 184-byte fixed part + UTF-16 name

Per entry (region-relative to the entry start = the previous name
field's end):

    hdr84  [00 00][6a][000][seq u16le][space u32le][space u8][Y u32be]
           [0000][ts8][ts8][ts8][000][12][35 zeros]
    xrec13 [01][X u32be][Y u32be][Y u32be]          (the region record)
    fil87  [11 zeros][u8][000][u8][00][Ynext u32be][000][ts8][ts8][ts8]
           [000][12][35 zeros]
    name   u16le len + UTF-16LE chars + NUL char, two framings:
           storage:  len = 2*chars + 2        (e.g. `0e 00 "CATIA1"`)
           property: len = 2*chars + 4 with a marker u16 (3 or 5) before
                     the text (e.g. `28 00 03 00 "CATStorageProperty"`)

All multi-byte region fields are big-endian; seq/space are little-endian
(measured; the skeleton mixes widths). The three ts8 values are 8-byte
per-file time-like values repeated within an entry and across its
neighbours; their semantics are open.

| ID | Field | Claim | Label | Scope |
|---|---|---|---|---|
| TL-Y-laws (W2/W3) | Y copies | hdr84 Y == xrec Y within an entry (W2) and fil87 Y == the NEXT entry's xrec Y (W3): 1818/1818 where entries parse (per-entry 100%); 100% on R19/R21 wherever entries parse. | established | all files where entries parse |
| TL-seq-law (W4) | hdr84 seq | seq runs 2, 3, ... in list order — 1806/1818; 100% on both lines wherever entries parse. | established | main scope |
| (xrec) | xrec13 | `[01][X u32be][Y u32be][Y u32be]` is the region record: X = region start, Y = region length, both absolute file offsets (inference with strong byte corroboration: the two Y copies and the hdr84/fil87 copies agree). The flag byte is `01` on every parsed entry. | established (layout) + open (flag semantics) | every parsed entry |
| W1 | entry spacing | from name0, each next name starts exactly 184 B after the previous name field's end — holds on walk-complete files; failures are flag-check stops, not model violations. | established (on walk-complete files) | walk-complete main (1070/1516) |
| S1 | skeleton | markers `6a` at hdr+2, `12` at hdr+48 and fil+64 — per-entry 61458/63555 = 0.967. | established | per-entry, corpus |
| N1 | name field | u16le len + UTF-16LE chars + NUL char; storage form len == 2*chars + 2, property form len == 2*chars + 4 with marker u16 3 or 5; chars >= U+0020. Vocabulary led by `CATStorageProperty`, `CATPropertySets`, then the per-file fixed set `CATIA1`, `Format`, `GesToler`, `Indexe`(d), `Data`, `Project`, `ProjectHeader`, `TimeStamp`, and GUID-derived stream names `Cont_0_1ae0_6991af79_dba` / `0_1ae0_6991af79_dba`. | established | every parsed entry (by construction of the walk) |
| TL-e1-name / TL-e1-Y94 | first entry | the first catalog entry is named `CATIA1` (98.5% R19 / 98.6% R21 — exceptions are files whose first parsed entry is a `CATStorageProperty` region, on both lines) and its region length is 94 (100% on both lines). | established | R19/R21 + main scope |
| (ts8) | hdr84/fil87 | three 8-byte time-like values repeated within an entry and across its neighbours; semantics open. | open | every parsed entry |

## 2.4 Region-tiling laws (R1-R4) and the large-file correction

The region set = {the entries' (X, Y)} + {the trailer's (B, C)}, sorted
by X, on walk-complete main-scope files (1070):

| ID | Law | Claim | Label | Scope |
|---|---|---|---|---|
| TL-R1-min64 | R1 | min region start == 64 (the header's u16be at +19) — 1070/1070; 100% on both lines. | established | walk-complete main |
| TL-R2-max-d8 | R2 | max region end == dword8 (the tail start) — 1070/1070; 100% on both lines. | established | walk-complete main |
| TL-tiling-full | R3a/R3b | full tiling (no unclaimed bytes) 868/1070 = 0.811 (R3a); at most one unclaimed gap 1055/1070 = 0.986 (R3b; 0.998 R19 / 0.991 R21). Residual gaps are small (227 files, 276,706 unclaimed bytes total, sizes 1-6280 B across 217 gaps) and their bytes contain entry-like records with UTF-16 names (e.g. a 290 B gap of `00fe73a09c8c7d70` contains `..."ProjectHeader"...`) — the catalog is recursive (regions embed sub-catalogs; the `CATIA1`/`Format` region contents are themselves entry-like mini-structures). The recursion is undocumented beyond these bytes. | established (R3b) + open (recursion) | walk-complete main |
| (B4 correction) | R3 scope | on the 8 deep large parts the COMPLETE catalog (primary + resync, all anchors found) does not tile the body: the stream bulk between the early property regions and the late container regions (e.g. [~9 KB, 13.94 MB) of `086a4effaab7`, [~30 KB, 172.2 MB) of `13bb5c0c`) is claimed by no catalog entry — the catalog names the property/directory structures and the container payload regions, not the stream bulk between them. R1/R2 still hold; R3 does not extend to this file family. | established (scoped correction) | 8 deep files, V5R18-V5R24 |
| TL-B-eq-prev-end | R4 | the trailer's region starts at B == the previous region's end — 1066/1070 = 0.996; 100% on both lines. | established | walk-complete main |

Paragraph claims:

- TL-B-is-registration **(established)**: B < dword8 on 1556/1556 (100%
  on both lines) and B is always the X of the final region record; the
  region [B, B+C) starts with the writer registration block (B1's byte
  proof). Correction/precision vs the B2 ticket framing: the
  registration block is NOT inside the tail region — it is a payload
  block; the tail merely names its region. B is one of a family of
  identical-format registration occurrences (3-27 per file, median 12);
  what distinguishes the B target is open.
- Space flag **(candidate)**: `space` (u32le at hdr+8, echoed as u8 at
  hdr+12) is 1 exactly on `Cont_*`-named entries and the three fixed
  names {CATIA1, Format, CATPreview} — 1426/1516 = 0.941 (0.966 R19 /
  0.980 R21); the converse (`Cont_*` always space 1) holds on 0.844
  (0.897 R19 / 0.865 R21). Below the bar on both lines; the flag's
  meaning is open.
- `Cont_*` regions **(established, partial)**: the small `Cont_<id>`
  regions (Y = 132-194 B) sit ~114 B after their container's
  storage-block start — per-container identity records. Their name
  suffixes are GUID-text-like hex groups, but the suffix bytes appear
  nowhere in the file as literal bytes (0/19 joins on the two probe
  files): the name-to-GUID transform, if any, is open.

## 2.5 Generations and outliers

- **No-trailer ff x 8 (156 files, all `unknown` version)**: the tail
  holds the same header (tag `0x4e` on 149/156, tag `0x55` on 8 —
  open) and a normal catalog (entries parse on 156/156; cnt law
  156/156; e0 laws 144/156; e1 name `CATIA1` on 118/156) but no end
  block and no trailer — the file ends in zeros. Correction of B1's
  "all-zero tails": the zero region is the tail END; the tail START
  carries the catalog. The regions found still reach dword8 on 138/156.
  The trailer-dependent claims (R4, C == D) do not apply.
- **Dual-region (146 files)**: dword8 is the last `CATIA_V5 CB0001\0`
  region (145/146) and dword16 the first (143/146); the tail parses as
  the same catalog on the entries that parse (e0 laws 146/146, cnt law
  146/146, tag `0x4e` 145/146); the 40 CB__END-ending dual files have
  trailer == final xrec 40/40. dword20 stays open — "length of the
  first region" holds on only 39/146 and dword12/2 on 19/146 (both
  hypotheses tested and failed).
- **Outlier tail lengths** (corpus 3138..124164): the minimum band
  (3138, 3 files) is the minimal catalog — few regions, walk-complete,
  tiling holds. The maximum family (124164 max; the 26-70 KB tails of
  `ae85fae7b1e6` R20, `13bb5c0c` R21, `ab1c7b09f52a` R20,
  `50cd280f` R21, `9c14d692c9e1` unknown) embeds a 20-65 KB binary
  blob between catalog sections (content unidentified, open); on the
  two unknown-version files the regions reach file size instead of
  dword8 (open). No correlation with the no-trailer/dual generations.

Reproduction: `python3 -I scripts/triage/decode_tail_region.py`
(~2 min; outputs `tail-scan.csv` + `tail-entries-sample.csv`).
