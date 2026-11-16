# Evidence: the CB0001 catalog & container directory census (2026-11-16)

Ticket #46 follow-on (Phase 6 assembly decoding, following the P1 product census
[2026-11-14-p1-product-census.md](2026-11-14-p1-product-census.md) §8 item 2 and the P2.5 position encoding
probe [2026-11-14-p25-position-encoding.md](2026-11-14-p25-position-encoding.md) §2.2, §5.2).

The P1 product census noted 44 product files carrying an embedded `CATIA_V5 CB0001\0`
structure inside the body (`[0, dword8)`), proposing it as a lead into nested-store
catalog architecture. P2.5 noted that the 44 body catalogs are region tables rather
than numeric transform tables. This probe performs the comprehensive census and
structural decode of all 44 `CB0001` catalog blocks across the corpus, establishing
their exact byte schema, their role as the physical region directory in legacy
dual-region files, their mapping of container UUIDs to stream offsets, and their
relationship to the 40 placed `CATCtorProxyCont` transform-carrying files.

**Verdict: FULL STRUCTURAL DECODE & CENSUS.** The 44 `CB0001` body blocks are not
isolated application-layer stores; they are the primary region directory of the
**dual-region (no-ff8) legacy CATProduct writer generation** (pointed to by header
`dword16`). The byte layout, header constants, counter law, span law (`dword20`),
fixed-width entry framing, region tiling law, and container UUID mapping are decoded
with 100% byte verification.

## 1. Population and method

Probe: `scripts/triage/p6_cb0001_catalog_census.py` (committed with this note).
Population: 382 manifest `kind=product` rows (380 byte-verified CATIA files, 2 manifest misfits).
Corpus read-only; deterministic execution.

```bash
python3 -I scripts/triage/p6_cb0001_catalog_census.py --selftest
python3 -I scripts/triage/p6_cb0001_catalog_census.py --all
python3 -I scripts/triage/check_claims_csv_quoting.py --root .
```

Outputs:
- [p6-cb0001-catalog-files-claims.csv](data/p6-cb0001-catalog-files-claims.csv) (382 rows)
- [p6-cb0001-catalog-claims.csv](data/p6-cb0001-catalog-claims.csv) (12 claims)

## 2. The census: identification and header architecture

Across all 382 manifest product rows, searching for the 16-byte magic `CATIA_V5 CB0001\0`
in the document body (`[0, header_dword8)`) isolates **exactly 44 files** (Claim P6-CB-1).

### 2.1 The dual-region header link (law H2)

Every single one of the 44 files satisfies the following structural invariants:

| Law | Formula / Value | Rate | Claim |
|---|---|---|---|
| **No-ff8 marker** | `header[16:24] != 0xff * 8` | 44/44 (1.000) | P6-CB-3 |
| **Catalog offset identity** | `catalog_offset == header.dword16` | 44/44 (1.000) | P6-CB-2 |
| **Catalog span identity** | `header_val2 == dword16 + dword20` | 44/44 (1.000) | P6-CB-6 |
| **Tail catalog at dword8** | `header.dword8` has second CB0001 | 44/44 (1.000) | P6-CB-1 |

The corpus contains 45 product files with `has_ff8 == False`. 44 of them carry their first
catalog at `dword16 < dword8` (the 44 files analyzed here). The 45th file
(`f4bfd20cb40d0a33`, `CAASchEduIn.CATProduct`) has `d16 > d8` (0x1d848 > 0x1a92a) and
carries only a single tail catalog at `dword8`.

Thus, the 44 "CB0001 in body" occurrences are not random embedded blocks:
**they comprise 100% of the corpus product files featuring the dual-region body catalog format.**

### 2.2 Version scoping

All 44 files belong exclusively to legacy writer releases:
- `unknown` bucket: 39 files
- `R16` (V5R16SP0HF0): 4 files
- `R15` (V5R15SP1HF0): 1 file
- `R17`..`R32`: **0 files**

All 44 files originate from Dassault CAA use case repositories (`corpus/SSadayuki/B31CAADoc`).
Modern files (V5R17+) uniformly use the single-tail `ff x 8` header layout, rendering the
dual-region body catalog obsolete in modern CATIA releases.

## 3. Raw byte structure & entry schema

The embedded `CB0001` block follows the identical binary format as the tail catalog
documented in [tail-catalog.md](../format/tail-catalog.md), consisting of a 64-byte header
area, a variable-length root entry (entry 0), a series of fixed-framing named region entries,
an 81-byte end block, and a 36-byte trailer.

### 3.1 The 64-byte catalog header

Relative to the catalog start offset `d16`:

```text
+0    16 B   magic "CATIA_V5 CB0001\0"
+16    1 B   tag 0x4E (ASCII 'N')
+17    2 B   u16be 1000 (0x03E8)
+19    2 B   u16be 64 (0x0040) — region tiling origin (law R1)
+21    2 B   u16be 12 (0x000C)
+24    2 B   u16le cntA (named entries count + 1)
+26    2 B   u16le cntB (cntB == cntA + 1, low-byte law)
+28    4 B   val1: 24-bit BE offset into Format mini-directory + 0x00
+32    4 B   val2: 24-bit BE offset equal to (d16 + d20) + 0x00
+36   28 B   zeros (0x00 * 28)
```

Invariants across the 44 files (Claims P6-CB-4, P6-CB-5, P6-CB-6):
- Magic `CATIA_V5 CB0001\0`: **44/44** (100.0%)
- Constants `0x4e`, `1000`, `64`, `12`, and 28 zero bytes: **44/44** (100.0%)
- Counter law `cntB == cntA + 1`: **44/44** (100.0%)
- Span law `val2 == dword16 + dword20`: **44/44** (100.0%)

> [!NOTE]
> This span law formally decodes the open question in `docs/format/header.md` regarding
> `dword20`: in dual-region files, **`dword20` is the allocated byte length of the first
> CB0001 catalog region.**

### 3.2 Root entry (entry 0)

Located at `+64`:
- Header: `[u32be M][u32be seq=1]` where `M = 86 + 20k`
- Anchor record at `(name_offset - 72)`: `01 [X0=94 u32be] [0 u32be] [ts8]`
- Root name: UTF-16LE hex identifier string (e.g. `.d03e9b471404000048c0b13cc5130000`)
- Present and verified: **44/44** (100.0%)

### 3.3 Named catalog entries (184 B fixed + UTF-16LE name)

Each named entry occupies exactly 184 fixed bytes followed by a length-prefixed UTF-16LE string:

1. `hdr84` (84 bytes):
   - `+0..+2`: `00 00`
   - `+2`: marker `0x6A`
   - `+6..+8`: sequence number `seq` (u16le: 2, 3, ...)
   - `+8..+12`: space flag (u32le: 1 for container/stream records, 2 for property records)
   - `+12`: space copy (u8)
   - `+13..+17`: `Y_hdr` (u32be copy of region length)
   - `+21..+45`: 3 × 8-byte timestamps / sequence counters
   - `+48`: marker `0x12`
   - `+49..+84`: 35 zeros
2. `xrec13` (13 bytes):
   - `+0`: record flag `0x01`
   - `+1..+5`: `X` (u32be, absolute file start offset of the named region)
   - `+5..+9`: `Y` (u32be, length in bytes of the named region)
   - `+9..+13`: `Y` (u32be, duplicate copy of region length)
3. `fil87` (87 bytes):
   - `+18..+22`: `Y_next` (u32be, region length of the successor entry)
   - `+25..+49`: 3 × 8-byte timestamps / sequence counters
   - `+52`: marker `0x12`
   - `+53..+87`: 35 zeros
4. `name`: UTF-16LE length-prefixed string:
   - Storage form: `u16le len == 2*chars + 2`, UTF-16LE text + `\x00\x00`
   - Property form: `u16le len == 2*chars + 4`, marker `0x0003` or `0x0005` (u16le) + UTF-16LE text + `\x00\x00`

### 3.4 Endblock & trailer

- End block (81 bytes): truncated `hdr84` record with `seq == cntB`, `space == 2`, `Y == trailer.C`
- Trailer (36 bytes): final `xrec` + fields `A..G`, terminating with 8-byte marker `CB__END\0`
- Walk completeness: **43/44 files (97.7%)** complete the walk cleanly to the end block and trailer (Claim P6-CB-7).
- Exception: 1 file (`d8a3e505473ba1f4`, `CAASchEduIn2.CATProduct`) where Cat1 and Cat2 share identical headers and Cat1 terminates at 0x27a51 without a trailing `CB__END`.

## 4. Structural function: physical region directory (law R1/R2)

Measuring the region coordinates `[X, X + Y)` across all 44 body catalogs establishes their
structural role:

| Invariant | Observed value | Rate | Claim |
|---|---|---|---|
| Minimum region start | `min(X) == 64` (byte after 64-byte header) | 44/44 (1.000) | P6-CB-8 |
| Maximum region end | `max(X + Y) == dword16` (catalog start offset) | 44/44 (1.000) | P6-CB-8 |
| Region placement | Every region sits strictly in `[64, dword16)` | 44/44 (1.000) | P6-CB-8 |

**Conclusion:** The body `CB0001` catalog is the **physical storage region directory for the
initial body of the file**, indexing all streams written prior to the catalog itself.
Any data written after the catalog (`[d16 + d20, d8)`) is subsequently indexed by Cat2
(the tail catalog at `dword8`).

### Stream vocabulary across the 44 catalogs

The entries name standard document streams and container payload regions:

```text
Fixed document streams:
  CATIA1             44/44 files
  Format             44/44 files
  GesToler           44/44 files
  Project            44/44 files
  ProjectHeader      44/44 files
  TimeStamp          44/44 files
  CATStorageProperty 44/44 files
  CATPreview         43/44 files
  Indexe             12/44 files
  Data               12/44 files
```

## 5. Container UUID to stream mapping

In files containing application containers, the container table's 16-byte binary UUIDs
map directly to the catalog's region names.

### 5.1 The hex-stripping transform

Given a 32-character hexadecimal container GUID from the container table (parsed via
`catpart.containers.parse_container_table`), CATIA strips leading zeros from each 8-character
nibble group (retaining a single `0` for all-zero groups):

$$\text{GUID: } \underbrace{\text{6b520668}}_{p_1} \underbrace{\text{0000061c}}_{p_2} \underbrace{\text{40b4b8de}}_{p_3} \underbrace{\text{000007c8}}_{p_4}$$
$$\implies \text{Stream names: } \begin{cases} \text{Data stream: } & \text{"6b520668\_61c\_40b4b8de\_7c8"} \\ \text{Identity descriptor: } & \text{"Cont\_6b520668\_61c\_40b4b8de\_7c8"} \end{cases}$$

### 5.2 Mapping rates

- Body catalog (Cat1) alone: **22/44 files** define application container UUID streams (Claim P6-CB-9).
- Body + Tail catalogs (Cat1 + Cat2) combined: **41/44 files** map their container UUIDs directly (Claim P6-CB-10).
- The remaining 3 files (`f09e7fbc81848bc2`, `c0f11142aab05958`, `d8a3e505473ba1f4`) contain only system/startup containers (e.g. `CATCompoundCont`, `MarkerStartupContainer`) without dedicated payload streams.

## 6. Structural negatives for assembly decoding

A key objective of this probe was evaluating whether `CB0001` catalogs carry assembly
information, instance hierarchy, or placement transforms.

### 6.1 Assembly tokens negative (Claim P6-CB-11)

Sweeping the entire byte payload and entry names of all 44 `CB0001` catalogs:

| Token / Structure | Hits in CB0001 catalogs |
|---|---|
| `_InstanceName` | **0** |
| `_Component` | **0** |
| `_PartNumber` | **0** |
| `_Position` | **0** |
| `ASMPRODUCT` / `PRDREP` / `PRDBAGREP` | **0** |
| Dot-shaped instance names (`name.N`) | **0** |

The assembly instance hierarchy and `_Position` attribute tokens live in the
**structure pool** (Law B) inside the `Project` stream or post-catalog payload streams,
completely outside the catalog structures.

### 6.2 Overlap analysis with CATCtorProxyCont transform records (Claim P6-CB-12)

The P2.5 position encoding probe ([2026-11-14-p25-position-encoding.md](2026-11-14-p25-position-encoding.md))
decoded the transform-record layer `[tx, ty, tz, qw, qx, qy, qz]` on 40 placed files carrying
`CATCtorProxyCont` records.

Comparing the 44 `CB0001` catalog files against the 40 placed transform files:

| Metric | Overlap | Notes |
|---|---|---|
| Placed files with ctorproxy records in CB0001 class | **1 / 40** (0.025) | Only `fad540f761d4eebd` (`CAAPsp3DEduIn.CATProduct`, 2 records) |
| Total files with ctorproxy records in CB0001 class | **2 / 42** (0.048) | Adds unplaced `768ee165f50ea874` (`CAAPspEduIn.CATProduct`, 2 records) |
| Files declaring `CATCtorProxyCont` in container table | **4 / 44** (0.091) | `3a40ea07`, `0b714b22`, `8a94dd30`, `fad540f7` |

**Conclusion:** The `CB0001` catalog is orthogonal to the `CATCtorProxyCont` transform-record
carrier class. The 40 placed transform-carrying files belong almost entirely to the modern
`ff x 8` single-tail releases (R19 19, R20 10, R21 5, unknown 5, R24 1), whereas `CB0001`
in the body is an artifact of the legacy dual-region writer architecture (R15/R16/unknown).

## 7. Worked examples

- `1f93f165fc0e3ec5` (`PID_ANSI_Equipment_.CATProduct`, 773,994 B, unknown bucket):
  - Catalog at `dword16 == 0x1bb7` (7095 B), span `dword20 == 0x1050` (4176 B).
  - 17 named entries tiling `[64, 7095)`.
  - Maps `CameraStartupContainer` (`b779c4f0000000fe3a24382a00000198`) to `Cont_b779c4f0_fe_3a24382a_198`.
  - Clean walk to end block (`seq=19`) and trailer (`CB__END\0`).
- `21392fc55f7f9f8c` (`Electrical_Bundle1.CATProduct`, 61,502 B, unknown bucket):
  - Catalog at `dword16 == 0xa625` (42,533 B), span `dword20 == 0x1000` (4096 B).
  - 12 named entries tiling `[64, 42533)`.
  - Structure pool sits inside Cat1's `Project` stream `[1764, 39884)`.
- `4851df0586cc8dea` (`CAAMmrPartCopy.CATProduct`, 30,741 B, unknown bucket):
  - Catalog at `dword16 == 0x3e75` (15,989 B), span `dword20 == 0x16fe` (5886 B).
  - 25 named entries tiling `[64, 15989)`.
  - Maps `CATMechProdCont` (`0000000000000b88417501f60000534f`) to `Cont_0_b88_417501f6_534f`.

## 8. Claims summary table

From [p6-cb0001-catalog-claims.csv](data/p6-cb0001-catalog-claims.csv):

| Claim ID | Statement | Files | Pop | Buckets | Label |
|---|---|---|---|---|---|
| **P6-CB-1** | body CB0001 catalog population: exactly 44 product files carry a CB0001 catalog in `[0, dword8)` | 44 | 380 | R15:1;R16:4;unknown:39 | fact |
| **P6-CB-2** | header dword16 identity: catalog start offset equals `header.dword16` exactly (law H2) | 44 | 44 | R15:1;R16:4;unknown:39 | fact |
| **P6-CB-3** | dual-region header class: body CB0001 files have `has_ff8 == False` (44 of 45 corpus dual files) | 44 | 44 | R15:1;R16:4;unknown:39 | fact |
| **P6-CB-4** | CB0001 magic & header constants: magic `CATIA_V5 CB0001\0`, tag `0x4e`, `1000`, `64`, `12`, 28 zeros | 44 | 44 | R15:1;R16:4;unknown:39 | fact |
| **P6-CB-5** | catalog entry count law: `cntB == cntA + 1` in the 20-byte catalog header | 44 | 44 | R15:1;R16:4;unknown:39 | fact |
| **P6-CB-6** | header dword20 catalog span law: header field `val2` satisfies `val2 == offset + dword20` | 44 | 44 | R15:1;R16:4;unknown:39 | fact |
| **P6-CB-7** | catalog walk completeness: full record walk to end block and `CB__END` trailer | 43 | 44 | R15:1;R16:4;unknown:38 | fact |
| **P6-CB-8** | physical region tiling law: entries tile body from byte 64 to catalog offset (`min(X)==64, max(X+Y)==d16`) | 44 | 44 | R15:1;R16:4;unknown:39 | fact |
| **P6-CB-9** | container table GUID mapping (body catalog): container UUIDs map to paired `<guid>` and `Cont_<guid>` streams | 22 | 44 | R15:1;R16:4;unknown:17 | fact |
| **P6-CB-10** | container table GUID mapping (any catalog): container UUIDs map to paired streams across file catalogs | 41 | 44 | R15:1;R16:4;unknown:36 | fact |
| **P6-CB-11** | assembly semantic negative: 0/44 catalogs carry instance names, part numbers, or pool markers | 0 | 44 | all:0/44 | fact |
| **P6-CB-12** | placed `CATCtorProxyCont` transform carrier overlap: placed files with ctorproxy records in CB0001 class | 1 | 40 | unknown:1/40 | fact |

## 9. Reproduction

```bash
# Selftest (no corpus IO)
python3 -I scripts/triage/p6_cb0001_catalog_census.py --selftest

# Census + claims generation (~2 s)
python3 -I scripts/triage/p6_cb0001_catalog_census.py --all

# Inspect individual file JSON
python3 -I scripts/triage/p6_cb0001_catalog_census.py --sha16 1f93f165fc0e3ec5

# Claims CSV hygiene check
python3 -I scripts/triage/check_claims_csv_quoting.py --root .
```
