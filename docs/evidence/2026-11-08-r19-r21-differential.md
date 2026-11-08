# Evidence: R19 vs R21 structural differential (2026-11-08)

Ticket #21 (B5, Spec B). Question: on the structures already decoded -
header, container-name table, kind law, trailer, tail catalog, storage
blocks, nested geometry stores, identity block, version marker - what
actually changes between the two primary release lines, and what is
writer-version change vs content variation?

Method: rate analysis over the committed scans (no new decoding), plus
byte spot checks on named files. Every rate below is computed from the
committed CSVs by `scripts/triage/version_differential.py`; the full
claim table with per-release n/pass/rate is
`docs/evidence/data/differential-r19-r21.csv` (78 claims: 58 identical,
8 differs, 12 untested). Byte examples were taken with
`python3 -I scripts/triage/version_differential.py --bytes <sha16,...>`
(read-only; offsets are absolute file offsets).

## Scope and pairing

Buckets: R19 = 649 files (povdoigt/SP-02 559, SSadayuki/B31CAADoc 87,
zhoujason457-stack/CAA_PrjSrc 3); R21 = 355 files (hssnadr/HTBX
124, Guilherme115/Motor-V6 65, dolganin/SO_SPIDAR300 63,
huanhuan233/CAAclean 62, B31CAADoc 35, HOLYNOTBAD/holydrone 6); R20 =
189 files for the spot checks. The buckets are NOT repo-matched beyond
one repo: **SSadayuki/B31CAADoc is the only repository holding both
lines** (87 R19 + 35 R21 files, plus 69 R20). It is a CAA
documentation corpus (534 parts / 218 products), so it is a natural
same-author pair set - but a narrow one (CAA-sample documents).
Consequence: every bucket-level rate difference below was checked
against the B31 same-repo rates before being called a version change;
three apparent differences flipped to content variation that way
(`TR-C-mode-e7`, `TR-reg-tag-M`, and part of `TL-walk-ok`). Rates in
`differential-r19-r21.csv` are bucket-level; rerun the script with
`--repo SSadayuki/B31CAADoc` for the paired view.

## Result in one paragraph

The decoded structures are **structurally identical across R19 and
R21**. Every constant, law and framing of the header, container-name
table (T1-T3), directory laws (L4-L7), kind law (K1), trailer fields
(A-G), tail catalog (header constants, entry model, Y-copies, seq,
end block, length accounting, region tiling R1/R2, B-pointer laws) and
the payload-block model (C2/C3b/C6/C7) holds at the same or
indistinguishable rates on both lines - most at 100%. The 8 "differs"
tags are: one clean writer-version change (the identity block's
save-time document name disappears after R19), two version-scoped
constants whose change point lies outside the pair (dual-region header
absent since R17; trailer F constant 0 since R19), one size-confounded
tail-header difference (cntB high byte on parts >= 18.6 MB, first seen
at R20), one decoder-coverage difference (tail walk), one
driver-unresolved framing statistic (u16le share), and two corpus-mix
artifacts that the same-repo pairing reclassifies as content (C = 0xe7
concentration, registration tag M/N).

## Header (bytes 0-32)

Identical: magic (scan scope), `dword8 < size`, `dword8 + dword12 ==
size` (649/649, 355/355), dword12 never 0xFFFFFFFF/0, ff x 8 at 16-24
(649/649, 355/355), zeros at 24-28.

Differs (version-scoped, not between the pair): the **dual-region
header** (dword16/dword20 instead of ff x 8) does not occur on R19/R21
(0/1004). The corpus's 146 dual files are R15 (2), R16 (12) and
unknown (132), all in the two CAA repos (B31CAADoc 142, CAA_PrjSrc 4)
- an R15/R16/unknown generation, absent from every bucket R17+. Byte
example of the variant (same repo as the pair, R16SP0
`137b897fc0c276e3`): header bytes 16-24 read `00 00 18 9a 00 00 11 34`
(dword16 = 6298 = the first `CATIA_V5 CB0001\0` offset; dword20 =
4404, semantics open) where an R19/R21 file reads
`ff ff ff ff ff ff ff ff`.

Untested: dword16/dword20 semantics (no dual files on the pair);
bytes 28-32 (no committed scan reads them).

## Container-name table records

Identical: the table parses under the record model on every file of
both lines (649/649, 355/355 - T3 constants, anchor `02 00 81 20`,
tail bytes, names, padding all validated); law T1 (f10 == area/8 + 1)
on 106/106 R19 and 64/64 R21 sample records; f3 vocabulary
{0x00030001, 0x00040001, 0x00050001} unchanged; f2 weights dominated
by {11, 12, 13, 21} (0.95 / 0.94 of sample records; rare larger
values are content); idx 1-based. Directory laws: L4 count
0.974 R19 (632/649) vs 0.989 R21 (351/355), L5 join-subset 0.988 /
0.983, L6 cumulative where L4 holds, L7 d7 == d6 - same laws, same
failure mode (subset directories), slightly different exception files.
Satellite blobs between records: 20.5% / 24.5% of table files.

Kind law (K1): **identical, 100% on both lines** (649/649, 189/189,
355/355). The corpus's two `CATMechProdCont`-next-to-`CATPrtCont`
parts are one R20 and one R21 file; the part name still decides.

Container tree: the documented negative holds identically - 0/649 and
0/355 files resolve the candidate parent-name assembly; record-level
parent resolution 9.4% R19 / 8.1% R20 / 9.1% R21.

## Trailer (last 36 bytes)

Identical: every R19/R21 file ends with `CB__END\0` (1004/1004;
no-trailer files are unknown-version only); A == 1, C == D, E == 0,
G == dword12, B < dword8, and the 41-byte registration block
byte-verifies at B on 100% of both buckets (B31 paired: 87/87, 35/35).

Differs:

- **F is constant 0 on R19+** (1004/1004 across R19/R20/R21 and every
  later bucket) vs F = 1 on R15-R18 + unknown (28 + 28 + 47 + 2 + 72 =
  177 files, matching the format doc's count) and one F = 2
  (unknown). Between the two primary lines: identical.
- **C's value** is file-dependent on both lines (it is the final
  region record's length, B2). The B1-era framing "0x000000e7 on most
  R19/R21 parts" is a corpus-mix artifact: C == 0xe7 on 9.4% of R19
  (61/649) vs 72.1% of R21 (256/355) bucket-wide, but 70% of B31's R19
  files (61/87) vs 51% of its R21 files (18/35), and 0/559 on
  povdoigt's R19 files - the share follows the repo mix, not the
  writer version. Byte example: B31 R19 `f3862d22fd9025ff` trailer
  C = D = 0x000000e7; B31 R21 `9179fcf5` C = D = 0x00001f71 (8049).
- **Registration tag M/N is repo-dependent, not version-dependent.**
  Bucket-wide it flips from M-majority on R19 (559/649 = 86%, all
  povdoigt) to N-majority on R21 (310/355 = 87%) - but B31CAADoc is
  all-N on BOTH lines (87/87, 35/35), and within R21 the repos
  disagree (dolganin 30 M/63, huanhuan233 15 M/62, hssnadr 0 M/124).
  Byte example: `0018baa84f3bff6b` (R19, povdoigt) registration at
  B = `4d 11 00 00 00 "DASSAULT-SYSTEMES" ...`; `f3862d22fd9025ff`
  (R19, B31) and `9179fcf5` (R21, B31) both start `4e ...`. What the
  tag means remains open (untested below).

## Tail catalog (CB0001 region)

Identical: magic at dword8, header constants (tag 0x4e, u16be 1000,
u16be 64, u16be 12, zeros at +36..+64) on 100% of both buckets; entry
0 laws (e0_len == M + 87, X0 == 94) 100%; first entry Y == 94 100%;
first entry named `CATIA1` on 98.5% / 98.6% (exceptions: the first
parsed entry is a `CATStorageProperty` region - occurs on both
lines); seq law and both Y-copy laws (W2/W3/W4) on 100% wherever
entries parse; trailer == final xrec 100%; end block and exact length
accounting on 100% of walk-complete files (496/496, 227/227); R1
(min start 64) and R2 (max end dword8) 100%; R4 (previous region ends
at B) 100%; B is a registration-pattern occurrence 100% (multiplicity
median 11 R19 / 12 R21); space-flag laws same shape (sp1-implies-name
0.966 / 0.980; converse 0.897 / 0.865 - candidate on both lines).

Differs:

- **cntB == cntA + 1 fails on 15/355 R21 files (and 16/189 R20,
  2/33 R24) with 0/649 on R19.** On all 33 files the cntB slot reads
  >= 256: the HIGH byte is nonzero. Precision over B2's "the count
  field exceeds one byte": `cntB & 0xFF == cntA + 1` holds on **33/33**
  - the count still lives in the low byte, the high byte carries
  something else (open). The comparison is size-confounded: all 33
  files are parts >= 18.6 MB and R19's largest file is 8.9 MB (0 R19
  files >= 15 MB), so R19 is untested at that size. Byte example
  (`13bb5c0c49616ade`, R21, 190 MB): tail header
  `4e 03 e8 00 40 00 0c 00 | 31 00 | 32 0b` - cntA = 0x0031 = 49,
  cntB = 0x0b32 = 2866, low byte 0x32 = 50 = cntA + 1; contrast
  `0018baa84f3bff6b` (R19): `29 00 2a 00` = 41, 42.
- **Walk coverage** (decoder property, not a law; a statistic, so no
  byte example applies): 0.764 R19 (496/649)
  vs 0.639 R21 (227/355); break families are the same (flag stops,
  name stops) at content-shifted offsets (R19 flag@4191-4205, R21
  flag@4291-4303 / name@5863-5893). Parts walk worse than products on
  both lines (R19 0.730/0.943; R21 0.586/0.943).
- Full tiling R3a: 0.909 R19 vs 0.789 R21 of walk-complete files
  (R3b <= 1 gap: 0.998 / 0.991); the residual gaps carry nested
  sub-catalog bytes on both lines - same phenomenon, same caveat.

## Storage-block payloads (114-file sample) and string framings

Identical: `34 12 CATStorageProperty` framing and the region rule C2
(1.000 on every sampled release); tag34 termination C3b (1.000 R19,
0.991 R21 - the 4 residuals are binary coincidences in stream data;
R20 dips to 0.940 with 30, same cause); cardinality C6 and the
CATFeatCont negative C7 (1.000 on both lines); the six string framing
families appear unchanged.

Differs: **C4b, the u16le share among length-framed ASCII rows,
collapses from 0.241 (R19) to 0.003 (R20/R21)** (a framing statistic;
no byte example applies). Driver unresolved (B3
open question 6): R19's sample files are small (max 8.9 MB), R20/R21's
are dominated by large parts whose stream strings drown the property
framing - content vs writer cannot be separated without an
equal-context comparison. Carried as differs-with-open-driver, not as
a format change.

Differs (content, classified): C1b's residual non-joining blocks
(1.000 R19 vs 0.969 R21) are containers absent from partial name
tables (`PDMLogCont`-family) - the B1 subset phenomenon, not a framing
change.

## Identity block and document_name

Identical: the identity model (exactly one `CATIA` block, 16-zero
GUID slot, name2 walk parses) holds on every sampled file of every
release.

**Differs - the one clean writer-version change found:** the identity
block's name2 (the save-time document name) is present on R15-R19 and
**absent from R20+**: R15 8/9, R16 7/14, R17 12/17, R18 8/9, R19 5/16,
then R20 0/12, R21 0/11, R23 0/11, R24 0/9. The R20 spot-check
byte-confirms the flip: `0a64c44c` (R20SP2, B31) carries the empty
form. Byte examples:

- R19 with name (`0018baa84f3bff6b`, block at 213633):
  `a0 02 00 00 00 00 34 2b "SP02_ALPHA5_SEPA2_RETENUE_ROULEMENT.CATPart" 9f`
- R19 without name (`f3862d22fd9025ff`, B31): `... 34 05 "CATIA" 9f
  a0 02 00 00 00 00 34 00 9f 3b 10 ...` - the empty form already
  exists within R19 (5/16 have a name), so R19 is the decline's end,
  R20 the first bucket at zero.
- R21 (`13bb5c0c49616ade`, block at 190132216): `a0 02 00 00 00 00
  34 00 9f` - empty.

Format-doc consequence: `document_name`'s scope is "R15-R19 partial
(declining), null from R20 onward (in this corpus)".

## Geometry containers (81-file scan)

Identical on the pair (small per-release samples: 4 R19 parts, 5 R21
parts): V1 one `CGMGeom` block per part / none per product; V2
`CATCGRCont` present with region < 64 KiB; V3 nested `V5_CFV2` store
in `CATStdCont`; V4 stream-name tokens; V5 strip-index records; V6
specificity (never in `CGMGeom`); V8 the CGM delta law (1/1 R19, 3/3
R21 deep files). V7's `2-0`/`2X-0` tags stay content-dependent
(0/4 R19, 2/5 R21).

## Version marker

Identical mechanics: the CNEXTINFOS-anchored `V5RxxSPxxHFyy` token
defines both buckets; a release token appears in the first 8 KB of
97.7% of R19 and 94.9% of R21 files (unanchored header-scan column;
the anchor + 64 KB fallback covers the rest by construction of
`detected_version`), and no file's token contradicts its bucket. The
SP/HF suffix varies per file within a line (content). No marker at
all: only the 338 unknown-bucket files - none on the pair.

## R20 spot-check outcome

R20 sits between the lines everywhere, and settles the two change
points a flip candidate could hide:

- **document_name**: R20 = 0/12 with the empty name2 byte-verified on
  `0a64c44c` - the flip happened between R19 and R20, not R19 and R21.
- **cntB high byte**: already present at R20 (16/189, e.g.
  `17930babf0fd01a8` cntA = 49, cntB = 5682) - it enters with the
  large-part generation, not with R21.
- C3b's residual coincidences peak at R20 (0.940) - content, per B3.
- F = 0 already constant at R20 (189/189); dual-region absent;
  everything else intermediate (e7 share 81.0%, walk coverage 0.603,
  reg_tag M-share 0.598 - all consistent with the content
  classifications above).

## The untested list (12 claims, with why)

1. **dword16/dword20 semantics** - no dual-region header exists on
   R19/R21 (0/1004); the variant is R15/R16/unknown only, where B2's
   two hypotheses already failed.
2. **Header bytes 28-32** - not captured by any committed scan (only
   word24_be at 24-28); untested on every line.
3. **F = 1 / F = 2 semantics** - F is 0 on all R19/R20/R21 files;
   nonzero values occur only outside the pair.
4. **Registration tag meaning (M vs N)** - both values occur on both
   lines, the split is repo-dependent within a single release, and no
   byte-level model distinguishes M from N files.
5. **cntB high-byte semantics** - value open everywhere; the 33
   affected files are >= 18.6 MB and R19 has none that large, so an
   equal-size comparison is impossible in this corpus.
6. **Tail header's 8 file-dependent bytes (+11..+19)** - file-dependent
   on both lines with overlapping value sets; no model to test.
7. **What sets M (entry-0 length quantum 86 + 20k)** - the law holds
   100% on both lines; the driver (name0 content/length?) is open.
8. **What distinguishes the trailer's B-target registration block from
   the other identical-format occurrences** - 3-22 (R19) / 3-20 (R21)
   occurrences per file, no distinguishing bytes known.
9. **Tail-header tag 0x55** - occurs only on 8 no-trailer
   unknown-version files; absent from the pair.
10. **Are all OSMX/CB0001 region ends real stream headers** - the
    region rule verifies boundary bytes only (B3 open question 2).
11. **The u32le attribute-string sub-format** - candidate framing
    (C4/C4b); no per-version model exists (B3 open question 3).
12. **Strip-record primitive semantics (G1)** - grammar measured on
    both lines; semantics inferred; needs a controlled decode pass
    (B4 open question 2). Not version-scoped.

## Corrections and precisions recorded

- `decode_trailer.py`'s docstring and B1's "0x000000e7 on most
  R19/R21 parts": the e7 mode's share is a corpus-mix property, not a
  writer behavior (povdoigt R19: 0/559; B31 R19: 70%; B31 R21: 51%).
  C == D's decoded semantics (final region length, B2) is unaffected.
- B2's "the count field exceeds one byte" (cnt exceptions): the count
  itself still fits and reads `cntA + 1` in the LOW byte on 33/33
  exceptions; only the high byte's meaning is new territory.
- The dual-region header generation is now version-scoped: R15 (2) +
  R16 (12) + unknown (132), CAA repos only, absent from every bucket
  R17+ - so the ff x 8 header is invariant across the primary lines
  and everything since R17.
- Trailer F's version scope sharpened: F = 0 on every file of every
  bucket from R19 on (1004/1004 on the pair + R20; 0 exceptions
  through R32); F = 1 belongs to R15-R18 + unknown.
- reg_tag M/N is repo-dependent (B31 all-N on both lines; R21 repos
  disagree) - any future claim tying the tag to a writer version would
  contradict the same-repo pairing.

## Deviations and open questions

- Same-author pairing exists for exactly one repo (B31CAADoc), and its
  R19/R21 files are different CAA sample documents - so "same author"
  means same corpus family, not same content. All other comparisons
  are bucket-level rates, checked against B31 before classification.
- The per-claim CSV's payload/geometry/identity rows carry their
  source scans' samples (114 / 81 / 108 files), not full buckets; the
  per-release counts in those rows are the samples'. Small R19/R21
  part samples (4-5) bound the geometry conclusions' precision.
- C4b's driver (writer vs large-file content) is left open on
  purpose: resolving it needs an equal-context property-section
  comparison, which is new-decoding work (B6+).
- The untested items are inherited open questions, re-scoped here to
  the pair; none is newly blocked by this ticket.

## Reproduction

```
python3 -I scripts/triage/version_differential.py                 # CSV + summary
python3 -I scripts/triage/version_differential.py --no-write      # summary only
python3 -I scripts/triage/version_differential.py --repo SSadayuki/B31CAADoc
python3 -I scripts/triage/version_differential.py --bytes 0018baa84f3bff6b,f3862d22fd9025ff,9179fcf5362ed78a,13bb5c0c49616ade,0a64c44c29e6cfa6
```

The CSV is recomputed from the committed scans only (manifest +
`docs/evidence/data/*.csv`); no corpus read is needed except for
`--bytes`. Deterministic.
