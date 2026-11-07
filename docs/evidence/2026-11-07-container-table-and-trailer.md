# Evidence: container-table records and trailer decoded (2026-11-07)

Scope: all 1818 unique `magic_ok` corpus files; the container-name table
parsed on 1810 of them (19300 records), the trailer on the 1556 that end
with `CB__END\0`. Method: read-only byte analysis with committed scripts —
`scripts/triage/decode_container_table.py` (emits
`docs/evidence/data/container-table.csv` plus a per-record sample,
`docs/evidence/data/container-table-records-sample.csv`) and
`scripts/triage/decode_trailer.py` (emits
`docs/evidence/data/trailer-scan.csv`). Run with `python3 -I`. Digests for
every claim are in the scan CSVs and the corpus manifest.

All observations are byte-level facts; interpretations are marked
*inference*. Every layout claim below was validated corpus-wide unless
stated otherwise; the exception families are described, not massaged.

## Container-name table record format

The Phase 1 open question ("name + offsets? bounds?") resolves to a
fixed-layout record, one per container row. Records were located by the
anchor dword `02 00 81 20` (bytes 20 81 00 02, little-endian
`0x20810002`) and every one of the 19300 records on 1810 files parsed
under the model with **zero rejected anchor positions** corpus-wide.

Record layout (all multi-byte fields little-endian), starting at S:

| offset | size | field | observed |
|--------|------|-------|----------|
| S+0  | 4 | f1  | stream-position value; join key with the directory table (see below) |
| S+4  | 4 | f2  | per-record weight: 11 (9455 recs), 12 (4930), 13 (3070), 21 (1198, the `AppliCont` row), then a tail of rarer values (22, 14, 25, 33, ...; large values only outside leading groups) |
| S+8  | 4 | f3  | table id: `0x00030001` (17488 recs), `0x00040001` (1441, the `AppliCont` row), `0x00050001` (371) |
| S+12 | 4 | idx | 1-based index within the table id (1, 2, 3, ...; skips observed) |
| S+16 | 4 | f5  | constant `0x006c0001` |
| S+20 | 4 | f6  | constant 2 |
| S+24 | 4 | f7  | small value: 0 (15219), 1 (1876), 8, 2, 9, 10, 11, 12, 3, ... |
| S+28 | 4 | f8  | constant 0 |
| S+32 | 4 | f9  | constant `0x20810002` (the anchor) |
| S+36 | 4 | f10 | names-area 8-byte slots + 1 (law below) |
| S+40 | n | names | `name1 00 name2 00`, printable ASCII, zero-padded so the names area is a multiple of 8 bytes |
| then | 8 | tail | constant `03 00 f7 00 03 00 00 00` |
| then | 16 | GUID | per-record object id |

`name1` is the container name; `name2` is a parent/base name — corpus
vocabulary (sample of 1088 records): `CATContainer` (627), `CATFeatCont`
(382), `CATProdCont` (70), `CATSiMuGenCont` (5), `CATDrwCont` (4).

**Law T1 (names-area size):** `f10 == ceil((len(name1)+len(name2)+2)/8) + 1`
— held on 19300/19300 records (100%). The names area is zero-padded to a
multiple of 8; the padding bytes verified zero.

**Law T2 (record size / contiguity):** record size =
`64 + 8*ceil((len(name1)+len(name2)+2)/8)`; the next record starts
immediately after the GUID. 1428/1810 files are strictly contiguous
chains; the other 382 files carry satellite blobs between records (see
below).

**Law T3 (constants):** f5, f6, f8, f9 held on every parsed record by
construction of the validator; f3 takes exactly the three values above
corpus-wide (19300/19300).

Worked example (`0018baa84f3bff6bdad1f29f00d1a4840ff3d4e9d45ace711aa8bd8725a6f505`,
povdoigt/SP-02 SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT.CATPart, 224039 B,
V5R19SP0HF0): the `CATProdCont` record at S=0x91c — f1=16, f2=11,
f3=`0x00030001`, idx=1, f5=`0x006c0001`, f6=2, f7=0, f8=0,
f9=`0x20810002` @0x93c, f10=4 @0x940, names
`CATProdCont\0CATFeatCont\0` @0x944-0x95b (24 B, no pad), tail
`0300f700 03000000` @0x95c, GUID @0x964-0x973
(`00000000 00001ae0 6991af79 00000dba`). Full record: 88 bytes; next
record at 0x974.

Reference rows for every record of 108 sample files (42 version buckets
V5R15→V5R32, 11 repos, incl. R19 x12 and R21 x6) are in
`container-table-records-sample.csv`.

### Directory table (binds the name records)

Immediately before the name records sits a directory of 40-byte records
(one per row, in the same order), at 0x65c in the examples:

| offset | field | observed |
|--------|-------|----------|
| +0  | d0 | low u16 varies, high u16 `0x00bf` |
| +4  | d1 | constant 0x2e |
| +8  | d2 | 0 |
| +12 | d3 | usually `0xe7000200`; varies on some files (e.g. `0x0a0ce405`) |
| +16 | d4 | `0x01000000 | k`, k = 1..N |
| +20 | d5 | cumulative counter (law D2) |
| +24 | d6 | join key (law D1) |
| +28 | d7 | equals d6 |
| +32 | d8 | two u16 values (low = array length after some records) |
| +36 | d9 | 0 |

4-byte arrays (values = the subsequent records' f1 sequence, second u16
`0x1a00`) follow some directory records; the parser skips them as gaps.

**Law D1 (join):** every directory d6 equals the f1 of a name record —
the binding between the directory and the names is the shared value, not
record order. As an exact bijection it holds on 1702/1810 files (94.0%);
as a subset (the directory may cover fewer rows than exist) 1712/1810
(94.6%).

**Law D2 (cumulative):** d5 == 1 + sum of f2 over the name records that
precede, in table order, the record bound by that directory row —
1702/1810 (94.0%).

**Law D3:** d7 == d6 — 1712/1810 (94.6%).

Worked example (same file): directory rows at 0x65c-0x814, k=1..10,
d5 = 1, 22, 34, 45, 56, 67, 78, 90, 103, 114; d6 = f1 sequence
1, 7, 16, 21, 26, 31, 36, 41, 46, 51. The f2 weights of rows 1..9 are
21, 12, 11, 11, 11, 11, 12, 13, 11 and their prefix sums reproduce d5
exactly.

### Exception families (documented, not massaged)

- **Distributed table** (26/1810 files, span > 64 KB, mostly
  `unknown`-version B31CAADoc/CAA products with embedded documents): name
  records appear next to their embedded documents throughout the file
  (e.g. `0x5444, 0x54e4, ..., 0x62c8, 0x12eec, ...` in a 32-record
  product) while the directory group covers only the leading rows.
- **Drifted join keys** (rare): in a V5R21 CAAclean part
  (`1fe91dee7622c6b49859874d07f3117f44161368b0c8bdcac6fc69ee34c05a25`),
  directory k=13 carries d6=100/d7=95 while the bound row (by the d5
  cumulative law) has f1=70 — the join key references a value absent from
  the table. 3 files (2 more in the same family) show matched counts with
  drifted keys.
- **Satellite blobs** (382 files): records of a second family sit between
  container rows, starting `04 00 c0 20` (e.g. the `V5USERID` row:
  `04 00 c0 20 0a 00 00 00 01 00 00 00 00 00 00 00 "V5USERID" ...` in
  F09VP at 0x86c-0x8bb) or `04 00 fc 3f`; 350 satellite + 205 unclassified
  gap instances.
- **No table at all** (8/1818): small `unknown`-version B31CAADoc files
  (5 products of 12-13 KB, one 66 KB product, two parts of ~100 KB).

## Trailer

Phase 1's open trailer fields decode as follows. Model: the last 36 bytes
of a file ending with `CB__END\0` = seven big-endian dwords + the 8-byte
marker. All rates on the 1556 files that end with `CB__END\0`:

| offset | field | value | corpus rate |
|--------|-------|-------|-------------|
| -36 | A | constant `0x00000001` ("…01" dword) | 1556/1556 |
| -32 | B | absolute file offset of the writer registration block | 1553/1556 |
| -28 | C | == D (pair, stored twice); value varies per file | 1556/1556 |
| -24 | D | == C | 1556/1556 |
| -20 | E | 0 | 1555/1556 |
| -16 | F | 0 (1378), 1 (177), 2 (1) | — |
| -12 | G | == header dword12 == size - dword8 | 1556/1556 |
| -8  | — | ASCII `CB__END\0` | by construction |

**Registration block at B:** the file carries, at absolute offset B,
`[tag byte][u32le 17]"DASSAULT-SYSTEMES"[u32le 5]"CATIA"[u32le 6]"041803"`
— tag byte `0x4e` (768 files) or `0x4d` (785); `0x4e` on most R15-R18 and
R21 files, `0x4d` on most R19/R20 and R23+ files. Validation: tag in
{0x4d, 0x4e} and the three length-prefixed strings byte-exact —
1553/1556. The 3 failures are dual-CB0001-generation files (below).

Worked example (F09VP.CATPart, 41976 B): trailer at 0xa3d4-0xa3f7 —
A=`00000001` @0xa3d4, B=`00007971` @0xa3d8, C=D=`000000e7` @0xa3dc/0xa3e0,
E=F=0 @0xa3e4/0xa3e8, G=`00002568` @0xa3ec, `CB__END\0` @0xa3f0. At B
(0x7971): `4e 11000000 "DASSAULT-SYSTEMES" 05000000 "CATIA" 06000000
"041803"`. The block follows the preview image in the payload; in this
file a JPEG EOI (`ff d9`) ends 2 bytes before B.

**The Phase 1 "size-like" dword is B, and it is a pointer, not a size**
*inference with byte proof*: in the near-identical save pairs, B moves by
exactly the file-size delta while everything else stays put:

- `body 1 - TRABALHO MOTOR.CATPart` (`5a4b8c75…55749`, 4014750 B) vs
  `…- Copia.CATPart` (`9ab6a78b…781f`, 4014768 B): size **+18**,
  dword8 **+18**, **B +18** (0x3d1227 → 0x3d1239); A, C, D, E, F and
  G (0x2b80) unchanged. (The Phase 1 note said "+12": the actual delta
  is +18; the quoted `0x2b80` is G, not B.)
- `Case_Logo_Black` vs `Case_Logo_Blue` (hssnadr): size -763028,
  B -763028, all other trailer fields unchanged.
- `lengua_1` v1 vs v2 (Apoloo13): these saves differ in content too —
  size +2230937, B +2236574, dword8 +2231053, dword12 -116, C=D -5577.

**Law H1 (header chain):** bytes 8-12 (BE dword8) + bytes 12-16 (BE
dword12) == file size, and trailer G == dword12 — 1556/1556 on
CB__END-ending files (153/156 on the no-CB__END ff×8 files). dword8 is
the start offset of the `CATIA_V5 CB0001\0` tail region (magic verified
at dword8 in 1516/1516 ff×8 files); dword12 is its length. This decodes
the Phase 1 "size - dword8 ≈ 10 KB" observation: the tail region is a
structured block whose length the header states exactly.

**C == D pair values:** equal on every file; the value varies —
`0x000000e7` (231) is the mode (517/1556 = 33%); values 242-321 are
common on R19-R24 parts, larger values (4-15k) on B31CAADoc/CAA files. Semantics
remain unknown (see open questions); the "constant e7" reading of Phase 1
is corrected to "pair, equal within a file, value file-dependent".

## The 146 files without ff×8 at bytes 16-24

Characterization (trailer-scan.csv, `ff8_at_16_24=False`):

- **Where:** SSadayuki/B31CAADoc 142, zhoujason457-stack/CAA_PrjSrc 4 —
  the CAA documentation-tree repos, no other repo.
- **Versions:** 132 `unknown` (no CNEXTINFOS marker — this set is the
  core of the 338-file unknown bucket), 12 V5R16SP0HF0, 1 V5R15SP0HF0,
  1 V5R15SP1HF0. Kinds: 101 parts, 45 products. Sizes 19359-799216 B.
- **What they have instead:** the header continues as two more BE dwords
  — dword16 @16-20 and dword20 @20-24 (then zeros at 24-32 as usual).
  dword16 is the offset of an additional `CATIA_V5 CB0001\0` region in
  143/146; 145/146 contain two or more CB0001 regions (examples carry
  two; the leading one at dword16, the trailing one at size - dword12 in
  144/146). dword12 == size - dword8 still holds in 144/146.
- **Trailers:** only 40/146 end with `CB__END\0`; 106 end with a zero
  region. The 40 parse under the same trailer model with 37/40 B
  pointers valid; the 3 B-pointer failures and the single E≠0 file
  (E=4089, F=2, `4851df05…`, 30741 B, B31CAADoc) are all in this family.

Worked example
(`009cc6056fb040b9bb2ca794bb480096443f25fd874ca1ea2adb435e9cd4d1e8`,
B31CAADoc BundleSegment3.CATPart, 81771 B): header dwords 0x10f6b, 0x3000,
0x1ce6, 0x1800; CB0001 regions at 7398 (= dword16) and 69483 (=
size - dword12); `CB__END\0` at 11566 and 80671 — neither at EOF; the file
ends with 1092 zero bytes.

*Inference: this is a distinct writer generation (the CAA education
corpus) with a dual-region layout and a header that continues past the
ff×8 marker; it is structurally its own family, not corrupt ff×8 files.*

## Negative results and corrections

- Phase 1's "+12-byte Copia pair": actual delta is +18 on both size and
  B (the pair's manifest sizes differ by 18 B); the quoted trailer dword
  `0x2b80` is G/dword12, which does **not** change between the pair.
- Phase 1's "8 bytes …000000e7 000000e7 constant-looking": the pair is
  real (C == D on 1556/1556) but the value is file-dependent; 0xe7 covers
  only 33%.
- f1 is **not** a function of the row index (`f1 == 5*idx + 11` held on
  only 58/943 sampled records before the multi-row analysis); it is a
  per-row stream value whose corpus law is the directory join (D1), not
  an arithmetic sequence.
- The directory record's d3 is not a constant (`0xe7000200` usually,
  other values observed); identification rests on d4/d1/d0/d2/d9.
- No version marker, entropy pattern, or other aid was needed to find the
  table: the f9 anchor + full-record validation is deterministic on 1810
  files and rejects 0 anchors.

## Unknowns / next questions

- Semantics of C == D (the trailer pair): a file-dependent value stored
  twice; not any count or offset tested (first DASSAULT offset, container
  counts, region sizes all fail). Candidate: a checksum or a stream
  position written twice.
- Deep semantics of f1/f2 (what stream the join key indexes; what the
  weight counts) — the directory laws bind them to each other but not to
  a file region yet.
- Meaning of the registration tag byte (0x4e vs 0x4d) and the `041803`
  code (identical across all versions observed — not the writing release).
- GUID internals: the last u16 increases across rows within a table
  (0x417d, 0x4180, 0x4182, ... in the example); pattern not validated
  corpus-wide.
- f7's meaning (0/1/2/8/9/10/11/12 observed, one row with 0x01000000).
- The 156 ff×8 files without `CB__END\0` (all `unknown` version,
  all-zero tails) — related to the 338-file unknown bucket.
- The dual-CB0001 generation's dword20 (no consistent target found) and
  its C == D value.

## Reproduction

```
python3 -I scripts/triage/decode_container_table.py   # table CSV + record sample + laws
python3 -I scripts/triage/decode_trailer.py           # trailer CSV + laws + save pairs
```

Runtime: seconds (edge reads per file; the table scan reads only the
first 2 MB of each file). Both scripts are stdlib-only and read-only with
respect to the corpus.
