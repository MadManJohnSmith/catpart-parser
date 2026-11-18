# 4. Trailer — the last 36 bytes, and the writer registration block

Parsed by `catpart.trailer` (schema v1: `trailer` with `a`,
`registration_offset`, `c`, `d`, `e`, `f`, `tail_region_length`,
`registration`). Trailer fields are reported as-is; the equality laws
below are enforced by the fitness invariants (`trailer-constants`,
`tail-region-chain`), not by the parser.

Evidence: [2026-11-07-container-table-and-trailer.md](../evidence/2026-11-07-container-table-and-trailer.md)
("Trailer"; data in `docs/evidence/data/trailer-scan.csv`),
[2026-11-08-header-tail-semantics.md](../evidence/2026-11-08-header-tail-semantics.md)
(the trailer == final xrec decode) and
[2026-11-08-r19-r21-differential.md](../evidence/2026-11-08-r19-r21-differential.md).
Claim IDs are the differential CSV's IDs where they exist.

## 4.1 Existence and fields (all dwords big-endian)

| ID | Offset (from end) | Field | Claim | Label | Scope |
|---|---|---|---|---|---|
| TR-exists | -8 | marker | The trailer exists when the file ends with `CB__END\0` (`43 42 5F 5F 45 4E 44 00`) — 1556/1818 files (85.6%). The other 262 (106 dual-region files ending in zeros + 156 no-trailer ff x 8 files) have none and `trailer` is null. 100% of R19/R21 files end with the marker. | established | corpus |
| TR-A-eq-1 | -36 | A | constant `0x00000001` — 1556/1556. Reported as `a`. | established | CB__END-ending files |
| TR-B-lt-d8 | -32 | B | absolute file offset of the writer registration block — a pointer, byte-proven (it moves by exactly the file-size delta between near-identical saves: +18 on the Motor-V6 pair, -763028 on the hssnadr pair, +2236574 vs +2230937 size on the Apoloo13 pair where content changed too). B < dword8 on 1556/1556 (100% on both lines): the registration block is NOT inside the tail region — the tail merely names its region (page 2, tail-catalog.md 2.4). Reported as `registration_offset`. | established | CB__END-ending files |
| TR-C-eq-D | -28, -24 | C, D | a pair stored twice, equal on every file (1556/1556; 100% on both lines). Decoded (B2): C == D == the final region record's length — the xrec form stores Y twice — and the region [B, B+C) starts with the registration block. The value is file-dependent (the B1-era "constant 0x000000e7" reading is corrected below). Reported as `c`, `d`; equality enforced by `trailer-constants`. | established | CB__END-ending files |
| TR-C-mode-e7 | -28 | C value | C == `0x000000e7` is a corpus-mix artifact, not a writer behavior: 9.4% of R19 (61/649) vs 72.1% of R21 (256/355) bucket-wide, but the same-repo pair B31CAADoc shows 70% (R19) vs 51% (R21) and povdoigt's R19 files are 0/559 — the share follows the repo mix, not the writer version. Byte examples: B31 R19 `f3862d22fd9025ff` C = D = 0xe7; B31 R21 `9179fcf5` C = D = 0x00001f71 (8049). | established (classification) | CB__END-ending; per-line rates in the differential CSV |
| TR-E-eq-0 | -20 | E | 0 on 1555/1556; the one exception is a dual-region file (E = 4089, F = 2, `4851df05...`). Reported as-is (`e`), never enforced. | established | CB__END-ending files |
| TR-F-eq-0 | -16 | F | Version scope (B5): F == 0 on every file of every bucket from R19 on — 1004/1004 across R19/R20/R21, and 0 exceptions through R32. F == 1 belongs to R15-R18 + unknown (177 files: 28 + 28 + 47 + 2 + 72, matching the corpus count); one file carries F == 2 (unknown). F's semantics are open: nonzero F cannot be probed on the primary lines. Reported as-is (`f`). | established (scope) + open (semantics) | CB__END-ending |
| TR-G-eq-d12 | -12 | G | == header dword12 == size - dword8 (law H1) — the tail region's length (1556/1556; 100% on both lines). The trailer's first 16 bytes are the final xrec: A = 01, B = region start, C == D = region length (page 2, tail-catalog.md 2.2). Reported as `tail_region_length`; equality enforced by `tail-region-chain`. | established | CB__END-ending files |

Worked example (F09VP.CATPart, 41976 B): trailer at 0xa3d4-0xa3f7 —
A = `00000001` @0xa3d4, B = `00007971` @0xa3d8, C = D = `000000e7`
@0xa3dc/0xa3e0, E = F = 0 @0xa3e4/0xa3e8, G = `00002568` @0xa3ec,
`CB__END\0` @0xa3f0.

## 4.2 The writer registration block at B

TR-registration **(established)**: at absolute offset B the file
carries, byte-exact, the 41-byte pattern

    [tag 0x4d|0x4e][u32le 17]"DASSAULT-SYSTEMES"[u32le 5]"CATIA"[u32le 6]"041803"

— 1553/1556 CB__END-ending files (the 3 failures are dual-region
files); 100% on both lines (B31 paired: 87/87, 35/35). Reported as
`registration` (`tag` as `M`/`N`, plus the three strings) only when the
pattern matches, else null; the parser never raises. Worked example: at
B (0x7971) of F09VP: `4e 11000000 "DASSAULT-SYSTEMES" 05000000 "CATIA"
06000000 "041803"` — the block follows the preview image in the payload
(a JPEG EOI ends 2 bytes before B in this file).

Paragraph claims:

- TR-reg-tag-M **(established, classification)**: the tag byte M/N is
  repo-dependent, not version-dependent. B1's "0x4e on most R15-R18 and
  R21 files, 0x4d on most R19/R20 and R23+" is a corpus-mix reading:
  bucket-wide it flips from M-majority on R19 (559/649 = 86%, all
  povdoigt) to N-majority on R21 (310/355 = 87%), but B31CAADoc is
  all-N on BOTH lines (87/87, 35/35) and within R21 the repos disagree
  (dolganin 30 M/63, huanhuan233 15 M/62, hssnadr 0 M/124). Any future
  claim tying the tag to a writer version would contradict the
  same-repo pairing. What the tag means is open.
- **(open)**: the `041803` code is identical across all observed
  versions (not the writing release; meaning open), and the identical
  41-byte pattern occurs 3-27 times per file (median 12) — B targets
  one of them; what distinguishes the B-target occurrence is open.
